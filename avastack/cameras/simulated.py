# -*- coding: utf-8 -*-
"""Ciel synthétique : démo sans matériel (étoiles, nébulosité, bruit, dérive)."""

import numpy as np
import cv2

from .base import CameraBase


class SimulatedCamera(CameraBase):
    """Ciel synthétique : étoiles colorées + nébulosité faible + bruit + dérive/rotation lente."""
    name = "Ciel simulé"

    def __init__(self, w=960, h=640, n_stars=400, seed=7):
        self.w, self.h = w, h
        self.rng = np.random.default_rng(seed)
        self.t = 0
        self.exposure_ms = 100.0
        self.gain = 1.0
        xy = self.rng.uniform(0, 1, (n_stars, 2)) * [w, h]
        bright = np.clip(0.08 + self.rng.pareto(2.5, n_stars) * 0.05, 0.05, 1.0)
        temp = self.rng.uniform(3500, 9500, n_stars)          # température de couleur
        self.xy = xy.astype(np.float32)
        self.bright, self.red = bright, np.clip((temp - 3500) / 6000 * 0.45, 0, 0.45)
        self.blue = np.clip((9500 - temp) / 6000 * 0.45, 0, 0.45)
        self.drift = np.array([0.30, 0.12])                   # px / frame
        self.rot_deg = 0.002                                  # ° / frame
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.neb = (0.012 * np.exp(-((xx - w * 0.68) ** 2 + (yy - h * 0.35) ** 2)
                                   / (2 * (w * 0.22) ** 2))
                    + 0.004 * (1 - yy / h)).astype(np.float32)

    def apply_settings(self, exposure_ms, gain):
        self.exposure_ms = float(exposure_ms)
        self.gain = float(gain)

    def read(self):
        self.t += 1
        expo = self.exposure_ms / 100.0
        ang = self.rot_deg * self.t
        M = cv2.getRotationMatrix2D((self.w / 2, self.h / 2), ang, 1.0)
        M[0, 2] += self.drift[0] * self.t
        M[1, 2] += self.drift[1] * self.t
        pts = cv2.transform(self.xy.reshape(-1, 1, 2), M)[:, 0, :]
        canR = np.zeros((self.h, self.w), np.uint8)
        canG = np.zeros_like(canR)
        canB = np.zeros_like(canR)
        for (x, y), b, r, bl in zip(pts, self.bright, self.red, self.blue):
            xi, yi = int(round(x)), int(round(y))
            if -2 <= xi < self.w + 2 and -2 <= yi < self.h + 2:
                scint = 0.75 + 0.25 * self.rng.normal()       # seeing / scintillement
                v = int(np.clip(b * scint * expo * 255, 0, 255))
                if v > 0:
                    cv2.circle(canR, (xi, yi), 1, int(v * (1 - bl)), -1, cv2.LINE_AA)
                    cv2.circle(canG, (xi, yi), 1, v, -1, cv2.LINE_AA)
                    cv2.circle(canB, (xi, yi), 1, int(v * (1 - r)), -1, cv2.LINE_AA)
        img = np.stack([cv2.GaussianBlur(c, (0, 0), 0.8).astype(np.float32) / 255.0
                        for c in (canR, canG, canB)], axis=-1)
        img += (self.neb * expo)[..., None]
        # bruit : photonique (approx. gaussienne de Poisson) + bruit de lecture
        e = img * 1500.0
        noise = self.rng.normal(0.0, 1.0, img.shape).astype(np.float32)
        img = np.clip(e + noise * (np.sqrt(e) + 6.0), 0, None) / 1500.0
        return np.clip(img * self.gain, 0, 1.5)
