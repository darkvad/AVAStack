# -*- coding: utf-8 -*-
"""Calibration dark/flat appliquée à chaque frame entrante."""

import numpy as np

from ..images import load_image


class Calibrator:
    def __init__(self):
        self.dark = None
        self.flat = None

    def load_dark(self, path):
        self.dark = load_image(path)

    def load_flat(self, path):
        self.flat = load_image(path)

    def clear(self):
        self.dark = self.flat = None

    def apply(self, img):
        out = img
        if self.dark is not None and self.dark.shape == img.shape:
            out = out - self.dark
        if self.flat is not None and self.flat.shape == img.shape:
            m = float(np.median(self.flat))
            if m > 1e-6:
                out = out / np.clip(self.flat / m, 0.2, None)
        return np.clip(out, 0, None)
