# -*- coding: utf-8 -*-
"""Caméras Player One Astronomy (Uranus-C Pro, Mars-C, Neptune-C…).

SDK natif officiel (téléchargeable sur player-one-astronomy.com) chargé via
ctypes, cf. sdk_loader.py. Une seule classe gère N'IMPORTE QUELLE caméra
Player One branchée : caractéristiques lues sur la caméra (fiche POACameraProperties),
jamais codées en dur.

Formats : la caméra couleur (Uranus-C Pro) est configurée en RGB24 — la
débayerisation est faite PAR LA CAMÉRA, on reçoit (H, W, 3) prêt à l'emploi.
Les caméras mono sortiraient du RAW16 2D (chemin géré aussi).

Dérivé du wrapper pyPOACamera.py (projet poa_view de Filipe Maia, BSD-2-Clause)
— seules les fonctions utilisées par AVAStack sont reprises, avec attribution.
"""

import ctypes
import platform
import numpy as np

from .base import CameraBase
from .sdk_loader import charger_dll, nom_bibliotheque

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

# --- constantes du SDK (cf. PlayerOneCamera SDK, POAxxx) --------------------
POA_OK = 0

# Formats d'image
POA_RAW16 = 1        # mono 16 bits
POA_RGB24 = 2        # couleur débayerisée par la caméra

# Config IDs utilisés
POA_EXPOSURE = 0     # µs
POA_GAIN = 1
POA_USB_BANDWIDTH_LIMIT = 28


class _POACameraProperties(ctypes.Structure):
    _fields_ = [("cameraModelName", ctypes.c_char * 256),
                ("userCustomID", ctypes.c_char * 16),
                ("cameraID", ctypes.c_int),
                ("maxWidth", ctypes.c_int),
                ("maxHeight", ctypes.c_int),
                ("bitDepth", ctypes.c_int),
                ("isColorCamera", ctypes.c_int),
                ("isHasST4Port", ctypes.c_int),
                ("isHasCooler", ctypes.c_int),
                ("isUSB3Speed", ctypes.c_int),
                ("bayerPattern_", ctypes.c_int),
                ("pixelSize", ctypes.c_double),
                ("SN", ctypes.c_char * 64),
                ("sensorModelName", ctypes.c_char * 32),
                ("localPath", ctypes.c_char * 256),
                ("bins_", ctypes.c_int * 8),
                ("imgFormats_", ctypes.c_int * 8),
                ("isSupportHardBin", ctypes.c_int),
                ("pID", ctypes.c_int),
                ("reserved", ctypes.c_char * 248)]


def _charger_sdk():
    """Charge PlayerOneCamera.dll/.so/.dylib → objet DLL (None si absent)."""
    nom = nom_bibliotheque("PlayerOneCamera", IS_WINDOWS, IS_MACOS)
    try:
        dll = charger_dll(nom, "AVASTACK_PLAYERONE_DIR", ("sdk", ""))
    except (RuntimeError, OSError):
        return None
    # signatures utiles
    dll.POAGetCameraCount.restype = ctypes.c_int
    dll.POAGetCameraProperties.argtypes = [ctypes.c_int,
                                           ctypes.POINTER(_POACameraProperties)]
    dll.POAGetCameraProperties.restype = ctypes.c_int
    return dll


_DLL = None          # chargé paresseusement (import sans matériel ne doit pas rater)


class PlayerOneCamera(CameraBase):
    """Une caméra Player One connectée (index = position dans l'énumération)."""

    @staticmethod
    def lister():
        """→ noms des caméras Player One branchées ('' si SDK absent)."""
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            return []
        n = _DLL.POAGetCameraCount()
        noms = []
        for i in range(n):
            props = _POACameraProperties()
            if _DLL.POAGetCameraProperties(i, ctypes.byref(props)) == POA_OK:
                noms.append(props.cameraModelName.decode("utf-8", "replace").strip())
        return noms

    # --- cycle de vie -----------------------------------------------------
    def __init__(self, index=0):
        self.index = index
        self.name = f"Player One #{index}"
        self.id = None
        self._started = False
        self._w = self._h = 0
        self._is_color = False

    def open(self):
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            raise RuntimeError("SDK Player One introuvable : télécharge le SDK "
                               "sur player-one-astronomy.com et place "
                               "PlayerOneCamera.dll dans le dossier du projet "
                               "(ou AVASTACK_PLAYERONE_DIR).")
        n = _DLL.POAGetCameraCount()
        if n == 0:
            raise RuntimeError("Aucune caméra Player One détectée")
        idx = min(self.index, n - 1)
        props = _POACameraProperties()
        if _DLL.POAGetCameraProperties(idx, ctypes.byref(props)) != POA_OK:
            raise RuntimeError("Impossible de lire les propriétés de la caméra")
        self.id = props.cameraID
        self._is_color = bool(props.isColorCamera)
        self.name = props.cameraModelName.decode("utf-8", "replace").strip() or self.name

        if _DLL.POAOpenCamera(self.id) != POA_OK:
            raise RuntimeError(f"Ouverture impossible : {self.name}")
        _DLL.POAInitCamera(self.id)
        # format : RGB24 pour la couleur (débayerisation par la caméra),
        # RAW16 pour le mono
        _DLL.POASetImageFormat(self.id, POA_RGB24 if self._is_color else POA_RAW16)
        _DLL.POASetImageSize(self.id, props.maxWidth, props.maxHeight)
        self._w, self._h = props.maxWidth, props.maxHeight
        # bande passante USB : défaut raisonnable
        _DLL.POASetConfig(self.id, POA_USB_BANDWIDTH_LIMIT, 40, 0)
        _DLL.POAStartExposure(self.id, 0)     # 0 = mode vidéo continu
        self._started = True

    def read(self):
        if not self._started:
            return None
        # frame prête ?
        ready = ctypes.c_int(0)
        _DLL.POAImageReady(self.id, ctypes.byref(ready))
        if not ready.value:
            return None
        # dimensions courantes (peuvent changer via ROI)
        w = ctypes.c_int(self._w)
        h = ctypes.c_int(self._h)
        fmt = ctypes.c_int(0)
        _DLL.POAGetImageSize(self.id, ctypes.byref(w), ctypes.byref(h))
        _DLL.POAGetImageFormat(self.id, ctypes.byref(fmt))
        self._w, self._h = w.value, h.value
        if fmt.value == POA_RGB24:
            buf = np.zeros(h.value * w.value * 3, dtype=np.uint8)
        else:
            buf = np.zeros(h.value * w.value * 2, dtype=np.uint8)   # RAW16
        err = _DLL.POAGetImageData(self.id, buf.ctypes.data_as(ctypes.c_char_p),
                                   buf.nbytes, 1000)
        if err != POA_OK:
            return None
        if fmt.value == POA_RGB24:
            img = buf.reshape(h.value, w.value, 3)
            return img.astype(np.float32) / 255.0
        img = buf.view(np.uint16).reshape(h.value, w.value)
        return img.astype(np.float32) / 65535.0

    def apply_settings(self, exposure_ms, gain):
        if not self._started:
            return
        _DLL.POASetConfig(self.id, POA_EXPOSURE, int(exposure_ms * 1000), 0)  # µs
        _DLL.POASetConfig(self.id, POA_GAIN, int(gain), 0)

    def close(self):
        if self.id is not None and _DLL is not None:
            try:
                if self._started:
                    _DLL.POAStopExposure(self.id)
                _DLL.POACloseCamera(self.id)
            except Exception:
                pass
            finally:
                self.id = None
                self._started = False
