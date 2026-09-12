# -*- coding: utf-8 -*-
"""Webcams et cartes d'acquisition via le backend générique OpenCV."""

import os

import cv2
import numpy as np

from .base import CameraBase


class OpenCVCamera(CameraBase):
    """Webcams et cartes d'acquisition (pilote générique)."""
    def __init__(self, index=0):
        self.index = index
        self.name = f"OpenCV {index}"
        self.cap = None

    def open(self):
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(self.index, backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la caméra OpenCV {self.index}")
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def read(self):
        ok, f = self.cap.read()
        if not ok:
            return None
        return cv2.cvtColor(f, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

    def apply_settings(self, exposure_ms, gain):
        if not self.cap:
            return
        # Ces réglages dépendent fortement du driver (valeurs souvent ignorées) :
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_ms / 1000.0)
        self.cap.set(cv2.CAP_PROP_GAIN, gain)

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None
