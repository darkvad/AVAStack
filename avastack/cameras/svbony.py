# -*- coding: utf-8 -*-
"""Caméras SVBONY (SV105, SV205, SV405CC, SV605CC…).

SDK natif officiel (SVBCameraSDK.dll / .so / .dylib, téléchargeable sur
svbony.com) chargé via ctypes, cf. sdk_loader.py. Une seule classe gère
N'IMPORTE QUELLE caméra SVBONY branchée : caractéristiques lues sur la
caméra (fiche SVBCameraProperty), jamais codées en dur.

API dérivée du SDK officiel SVBONY (quasi-clone de l'API ZWO ASI —
mêmes concepts : num caméras connectées, fiche, contrôles, ROI, flux vidéo)
et des wrappers MIT pysvbony (ssmichael1) / pysvb (olosnet). Attribution
dans le commentaire ; seules les fonctions utilisées par AVAStack sont
reprises ici.

Formats : RGB24 pour les caméras couleur (débayerisation PAR LA CAMÉRA,
(H,W,3) prêt à l'emploi), RAW16 pour les mono ((H,W) 2D).
"""

import ctypes
import platform
import numpy as np

from .base import CameraBase
from .sdk_loader import charger_dll, nom_bibliotheque

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

SVB_SUCCESS = 0

# types d'image (cf. SVB_IMG_TYPE du SDK)
SVB_IMG_RAW16 = 4
SVB_IMG_RGB24 = 10

# contrôles utilisés (SVB_CONTROL_TYPE)
SVB_EXPOSURE = 1     # µs
SVB_GAIN = 0


class _SVBCameraInfo(ctypes.Structure):
    _fields_ = [("FriendlyName", ctypes.c_char * 32),
                ("CameraSN", ctypes.c_char * 32),
                ("PortType", ctypes.c_char * 32),
                ("DeviceID", ctypes.c_uint32),
                ("CameraID", ctypes.c_int32)]


class _SVBCameraProperty(ctypes.Structure):
    _fields_ = [("MaxHeight", ctypes.c_long),
                ("MaxWidth", ctypes.c_long),
                ("IsColorCam", ctypes.c_int),
                ("BayerPattern", ctypes.c_int),
                ("SupportedBins", ctypes.c_int * 16),
                ("SupportedVideoFormat", ctypes.c_int * 8),
                ("MaxBitDepth", ctypes.c_int),
                ("IsTriggerCam", ctypes.c_int)]


def _charger_sdk():
    """Charge SVBCameraSDK.dll/.so/.dylib → objet DLL (None si absent)."""
    nom = nom_bibliotheque("SVBCameraSDK", IS_WINDOWS, IS_MACOS)
    try:
        dll = charger_dll(nom, "AVASTACK_SVBONY_DIR", ("sdk", ""))
    except (RuntimeError, OSError):
        return None
    # signatures
    dll.SVBGetNumOfConnectedCameras.restype = ctypes.c_int
    dll.SVBGetCameraInfo.argtypes = [ctypes.POINTER(_SVBCameraInfo), ctypes.c_int]
    dll.SVBGetCameraInfo.restype = ctypes.c_int
    dll.SVBGetCameraProperty.argtypes = [ctypes.c_int, ctypes.POINTER(_SVBCameraProperty)]
    dll.SVBGetCameraProperty.restype = ctypes.c_int
    dll.SVBSetOutputImageType.argtypes = [ctypes.c_int, ctypes.c_int]
    dll.SVBSetROIFormat.argtypes = [ctypes.c_int] * 6
    dll.SVBStartVideoCapture.argtypes = [ctypes.c_int]
    dll.SVBGetVideoData.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte),
                                    ctypes.c_long, ctypes.c_int]
    dll.SVBSetControlValue.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_long,
                                       ctypes.c_int]
    return dll


_DLL = None          # chargé paresseusement (l'import sans matériel ne doit pas rater)


class SVBonyCamera(CameraBase):
    """Une caméra SVBONY connectée (index = position dans l'énumération)."""

    @staticmethod
    def lister():
        """→ noms des caméras SVBONY branchées ('' si SDK absent)."""
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            return []
        n = _DLL.SVBGetNumOfConnectedCameras()
        noms = []
        for i in range(n):
            info = _SVBCameraInfo()
            if _DLL.SVBGetCameraInfo(ctypes.byref(info), i) == SVB_SUCCESS:
                noms.append(info.FriendlyName.decode("utf-8", "replace").strip())
        return noms

    # --- cycle de vie -----------------------------------------------------
    def __init__(self, index=0):
        self.index = index
        self.name = f"SVBONY #{index}"
        self.id = None
        self._started = False
        self._w = self._h = 0
        self._is_color = False

    def open(self):
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            raise RuntimeError("SDK SVBONY introuvable : télécharge le SDK "
                               "sur svbony.com et place SVBCameraSDK.dll dans "
                               "le dossier du projet (ou AVASTACK_SVBONY_DIR).")
        n = _DLL.SVBGetNumOfConnectedCameras()
        if n == 0:
            raise RuntimeError("Aucune caméra SVBONY détectée")
        idx = min(self.index, n - 1)

        info = _SVBCameraInfo()
        if _DLL.SVBGetCameraInfo(ctypes.byref(info), idx) != SVB_SUCCESS:
            raise RuntimeError("Impossible de lire les informations de la caméra")
        self.id = info.CameraID
        self.name = info.FriendlyName.decode("utf-8", "replace").strip() or self.name

        prop = _SVBCameraProperty()
        if _DLL.SVBGetCameraProperty(self.id, ctypes.byref(prop)) != SVB_SUCCESS:
            raise RuntimeError(f"Propriétés illisibles : {self.name}")
        self._is_color = bool(prop.IsColorCam)
        self._w, self._h = prop.MaxWidth, prop.MaxHeight

        if _DLL.SVBOpenCamera(self.id) != SVB_SUCCESS:
            raise RuntimeError(f"Ouverture impossible : {self.name}")
        # format : RGB24 pour couleur (débayerisation par la caméra), RAW16 mono
        _DLL.SVBSetOutputImageType(self.id, SVB_IMG_RGB24 if self._is_color
                                   else SVB_IMG_RAW16)
        _DLL.SVBSetROIFormat(self.id, 0, 0, self._w, self._h, 1)
        if _DLL.SVBStartVideoCapture(self.id) != SVB_SUCCESS:
            raise RuntimeError(f"Démarrage du flux impossible : {self.name}")
        self._started = True

    def read(self):
        if not self._started:
            return None
        if self._is_color:
            nbytes = self._w * self._h * 3
            buf = np.zeros(nbytes, dtype=np.uint8)
            err = _DLL.SVBGetVideoData(
                self.id, buf.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)),
                nbytes, 200)
            if err != SVB_SUCCESS:
                return None
            return buf.reshape(self._h, self._w, 3).astype(np.float32) / 255.0
        nbytes = self._w * self._h * 2
        buf = np.zeros(nbytes, dtype=np.uint8)
        err = _DLL.SVBGetVideoData(
            self.id, buf.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)),
            nbytes, 200)
        if err != SVB_SUCCESS:
            return None
        return (buf.view(np.uint16).reshape(self._h, self._w)
                .astype(np.float32) / 65535.0)

    def apply_settings(self, exposure_ms, gain):
        if not self._started:
            return
        _DLL.SVBSetControlValue(self.id, SVB_EXPOSURE, int(exposure_ms * 1000), 0)
        _DLL.SVBSetControlValue(self.id, SVB_GAIN, int(gain), 0)

    def close(self):
        if self.id is not None and _DLL is not None:
            try:
                if self._started:
                    _DLL.SVBStopVideoCapture(self.id)
                _DLL.SVBCloseCamera(self.id)
            except Exception:
                pass
            finally:
                self.id = None
                self._started = False
