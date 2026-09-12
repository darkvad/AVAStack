# -*- coding: utf-8 -*-
"""Caméras ZWO ASI via le SDK officiel (zwoasi).

Nécessite : pip install zwoasi + la bibliothèque du SDK placée dans le
dossier du script — ASICamera2.dll (Windows) / libASICamera2.so (Linux) /
libASICamera2.dylib (macOS) — cf. avastack/compat.py.
"""

import os

import numpy as np

from .base import CameraBase
from ..compat import ZWO_DLL_NAME


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
