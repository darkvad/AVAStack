# -*- coding: utf-8 -*-
"""Caméras ZWO ASI via le SDK officiel (zwoasi).

Nécessite : pip install zwoasi + la bibliothèque du SDK placée dans le
dossier du script — ASICamera2.dll (Windows) / libASICamera2.so (Linux) /
libASICamera2.dylib (macOS) — cf. avastack/compat.py.
"""

import ctypes
import os
import sys

import numpy as np

from .base import CameraBase
from .capacites import Capacites, Controle, dedupliquer
from .sdk_loader import charger_dll
from ..compat import ZWO_DLL_NAME

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"

# --- constantes du SDK ASI (ASICamera2.h, cf. wrapper python-zwoasi, MIT) ----
ASI_FALSE, ASI_TRUE = 0, 1

# ASI_IMG_TYPE
NOMS_FORMATS_ASI = {0: "RAW8", 1: "RGB24", 2: "RAW16", 3: "Y8"}

# ASI_CONTROL_TYPE (les seuls utilisés par la sonde)
ASI_GAIN = 0
ASI_EXPOSURE = 1          # µs
ASI_OFFSET = 5            # « brightness » dans les anciennes docs
ASI_TEMPERATURE = 8       # = 10 × la température (°C), lecture seule
ASI_HARDWARE_BIN = 13
ASI_COOLER_POWER_PERC = 15
ASI_TARGET_TEMP = 16      # °C
ASI_COOLER_ON = 17
ASI_MONO_BIN = 18


class _ASICameraInfo(ctypes.Structure):
    """ASI_CAMERA_INFO (cf. wrapper python-zwoasi, MIT — champs dans
    l'ordre exact du SDK)."""
    _fields_ = [("Name", ctypes.c_char * 64),
                ("CameraID", ctypes.c_int),
                ("MaxHeight", ctypes.c_long),
                ("MaxWidth", ctypes.c_long),
                ("IsColorCam", ctypes.c_int),
                ("BayerPattern", ctypes.c_int),
                ("SupportedBins", ctypes.c_int * 16),
                ("SupportedVideoFormat", ctypes.c_int * 8),
                ("PixelSize", ctypes.c_double),
                ("MechanicalShutter", ctypes.c_int),
                ("ST4Port", ctypes.c_int),
                ("IsCoolerCam", ctypes.c_int),
                ("IsUSB3Host", ctypes.c_int),
                ("IsUSB3Camera", ctypes.c_int),
                ("ElecPerADU", ctypes.c_float),
                ("BitDepth", ctypes.c_int),
                ("IsTriggerCam", ctypes.c_int)]


class _ASIControlCaps(ctypes.Structure):
    """ASI_CONTROL_CAPS (cf. wrapper python-zwoasi, MIT)."""
    _fields_ = [("Name", ctypes.c_char * 64),
                ("Description", ctypes.c_char * 128),
                ("MaxValue", ctypes.c_long),
                ("MinValue", ctypes.c_long),
                ("DefaultValue", ctypes.c_long),
                ("IsAutoSupported", ctypes.c_int),
                ("IsWritable", ctypes.c_int),
                ("ControlType", ctypes.c_int),
                ("Unused", ctypes.c_char * 32)]


def _charger_dll():
    """Charge ASICamera2.dll/.so/.dylib via le MÊME chargeur que le reste
    (sdk_loader.py) — ZWO_DLL_NAME (compat.py) est déjà le nom selon l'OS.
    → objet DLL, ou None si absent."""
    try:
        dll = charger_dll(ZWO_DLL_NAME, "AVASTACK_ZWO_DIR", ("sdk", ""))
    except (RuntimeError, OSError):
        return None
    dll.ASIGetNumOfConnectedCameras.restype = ctypes.c_int
    dll.ASIGetCameraProperty.argtypes = [ctypes.POINTER(_ASICameraInfo),
                                         ctypes.c_int]
    dll.ASIGetCameraProperty.restype = ctypes.c_int
    dll.ASIGetNumOfControls.argtypes = [ctypes.c_int,
                                        ctypes.POINTER(ctypes.c_int)]
    dll.ASIGetNumOfControls.restype = ctypes.c_int
    dll.ASIGetControlCaps.argtypes = [ctypes.c_int, ctypes.c_int,
                                      ctypes.POINTER(_ASIControlCaps)]
    dll.ASIGetControlCaps.restype = ctypes.c_int
    dll.ASIGetControlValue.argtypes = [ctypes.c_int, ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_long),
                                       ctypes.POINTER(ctypes.c_int)]
    dll.ASIGetControlValue.restype = ctypes.c_int
    return dll


class ZWOASICamera(CameraBase):
    def __init__(self, index=0, dll_path=None):
        self.index, self.dll = index, dll_path or ZWO_DLL_NAME
        self.name = f"ZWO ASI #{index}"
        self.cam = None
        self._asi = None

    def open(self):
        try:
            import zwoasi as asi
        except ImportError:
            raise RuntimeError("SDK manquant :  pip install zwoasi  (+ DLL du SDK ASI)")
        if os.path.exists(self.dll):
            asi.init(self.dll)
        if asi.get_num_cameras() == 0:
            raise RuntimeError("Aucune caméra ZWO détectée")
        self._asi = asi
        self.cam = asi.Camera(self.index)
        self.cam.open()
        self.cam.set_control_value(asi.ASI_BANDWIDTHOVERLOAD, 40)
        self.cam.set_control_value(asi.ASI_HIGH_SPEED_MODE, 0)
        w, h, _, _ = self.cam.get_roi_format()
        self.cam.set_roi_format(w, h, 1, asi.ASI_RGB24)   # débayerisation par la caméra
        self.cam.start_video_capture()

    def apply_settings(self, exposure_ms, gain):
        if not self.cam:
            return
        asi = self._asi
        self.cam.set_control_value(asi.ASI_EXPOSURE, int(exposure_ms * 1000))  # µs
        self.cam.set_control_value(asi.ASI_GAIN, int(gain * 50))               # à adapter

    def read(self):
        try:
            a = self.cam.capture_video_frame(timeout=5000)
        except Exception:
            return None
        if a.ndim == 2:   # mono RAW
            return a.astype(np.float32) / (65535.0 if a.dtype == np.uint16 else 255.0)
        return a[:, :, ::-1].astype(np.float32) / 255.0  # si couleurs inversées: retirer [::-1]

    def close(self):
        if self.cam:
            try:
                self.cam.stop_video_capture()
                self.cam.close()
            finally:
                self.cam = None

    def detecter_capacites(self):
        """→ Capacites rempli EN DYNAMIQUE depuis la caméra OUVERTE.

        Sonde la DLL via ctypes (ASIGetNumOfControls + ASIGetControlCaps —
        le même modèle dynamique que Player One et SVBONY) et la fiche
        ASI_CAMERA_INFO. Contrôles ASI clés : GAIN=0, EXPOSURE=1 (µs),
        OFFSET=5, TEMPERATURE=8 (×10), TARGET_TEMP=16, COOLER_ON=17.
        Ne suppose RIEN du modèle : tout vient des réponses du SDK.
        À appeler APRÈS open() (l'ouverture zwoasi), avant close()."""
        if self.cam is None:
            raise RuntimeError("ouvre d'abord la caméra (open()) avant "
                               "detecter_capacites()")
        dll = _charger_dll()
        if dll is None:
            return None
        info = _ASICameraInfo()
        if dll.ASIGetCameraProperty(ctypes.byref(info),
                                    self.index) != 0:
            return None
        cap = Capacites("ZWO", modele=info.Name.decode("utf-8",
                                                       "replace").strip(),
                        capteur="", couleur=bool(info.IsColorCam),
                        bits=info.BitDepth, max_l=info.MaxWidth,
                        max_h=info.MaxHeight, pixel_um=info.PixelSize)
        cap.st4 = bool(info.ST4Port)
        cap.usb3 = bool(info.IsUSB3Camera)
        cap.bins = dedupliquer([b for b in info.SupportedBins if 1 <= b <= 4])
        cap.formats = dedupliquer([NOMS_FORMATS_ASI.get(f, str(f))
                                   for f in info.SupportedVideoFormat
                                   if f >= 0])[:8]
        cap.extras["elec_per_adu"] = info.ElecPerADU
        # énumération des contrôles (caméra ouverte obligatoire)
        n = ctypes.c_int(0)
        if dll.ASIGetNumOfControls(self.index, ctypes.byref(n)) != 0:
            return cap
        caps = {}
        for i in range(n.value):
            c = _ASIControlCaps()
            if dll.ASIGetControlCaps(self.index, i, ctypes.byref(c)) != 0:
                continue
            cid = c.ControlType
            dic = {"nom": c.Name.decode("utf-8", "replace").strip(),
                   "desc": c.Description.decode("utf-8", "replace"),
                   "min": c.MinValue, "max": c.MaxValue,
                   "defaut": c.DefaultValue,
                   "ecrivable": bool(c.IsWritable),
                   "auto": bool(c.IsAutoSupported)}
            caps[cid] = dic
            cap.controles.append(Controle(
                cid, nom=dic["nom"], mini=dic["min"], maxi=dic["max"],
                defaut=dic["defaut"], ecrivable=dic["ecrivable"],
                lisible=True, auto=dic["auto"], desc=dic["desc"]))
        # Jalon 32 : plages PAR CONTRÔLE (clé = id string) — le câblage de
        # l'UI les lit via CID_CONTROLES_PAR_MARQUE (« gain » → 0,
        # « offset » → 5), jamais un cid d'une autre marque. Le SDK ASI
        # n'expose pas de pas → step 1.
        for cid, dic in caps.items():
            cap.extras[str(cid)] = {"min": dic["min"], "max": dic["max"],
                                    "step": 1, "val": dic["defaut"],
                                    "nom": dic["nom"]}
        # plages, si les contrôles correspondants sont supportés
        c = caps.get(ASI_EXPOSURE)
        if c:
            cap.expo_us = (c["min"], c["max"])
        c = caps.get(ASI_GAIN)
        if c:
            cap.gain = (c["min"], c["max"])
        c = caps.get(ASI_OFFSET)
        if c:
            cap.offset = (c["min"], c["max"])
            # valeur COURANTE (ASIGetControlValue) — jalon 51 : l'appli
            # l'ADOPTE au lieu d'imposer son défaut (l'offset est un réglage
            # de CAPTEUR : l'écraser fausserait les brutes et les darks).
            try:
                if hasattr(dll, "ASIGetControlValue"):
                    v, _auto = ctypes.c_long(0), ctypes.c_int(0)
                    if dll.ASIGetControlValue(self.index, ASI_OFFSET,
                                              ctypes.byref(v),
                                              ctypes.byref(_auto)) == 0:
                        cap.actuels["offset"] = float(v.value)
            except Exception:
                pass
        # bin matériel : contrôle réellement présent (pas la fiche)
        if ASI_HARDWARE_BIN in caps:
            cap.bin_materiel = caps[ASI_HARDWARE_BIN]["ecrivable"]
        # refroidissement : contrôles réellement présents
        if ASI_COOLER_ON in caps:
            cap.tec = True
            c = caps.get(ASI_TARGET_TEMP)
            if c:
                cap.tec_consigne = (c["min"], c["max"])
            cap.temperature_lisible = ASI_TEMPERATURE in caps
        return cap
