# -*- coding: utf-8 -*-
"""Étirement temps réel (auto STF façon PixInsight, ou manuel)."""

import numpy as np
import cv2


class DisplayProcessor:
    """Étirement temps réel.

    Mode AUTO — « STF » façon PixInsight :
      1. point noir  lo = médiane − k·σ        (coupe le bruit sous le fond)
      2. point blanc hi = percentile 99.9       (vraies hautes lumières, pas med+k·σ !)
      3. midtones m résolues pour que le FOND tombe à self.target (~0.25) après MTF.
    Le fond garde donc une luminosité stable quelle que soit l'exposition :
    c'est la nébulosité qui « monte » avec l'intégration, pas le fond.
    Les stats (médiane, σ, p99.9) sont lissées dans le temps → pas de pompage.

    Mode MANUEL — black/white point.
    Gamma et saturation s'appliquent dans les deux modes.
    """
    def __init__(self):
        self.auto = True
        self.sigma_k = 2.8            # coupure des ombres, en σ SOUS la médiane
        self.target = 0.25            # luminosité cible du fond du ciel après MTF
        self.black, self.white = 0.0, 1.0
        self.gamma, self.saturation = 1.0, 1.0
        self.last_lo, self.last_hi = 0.0, 1.0
        self._stats = None            # (médiane, σ, p99.9) lissées — anti-pompage
        self._ema = 0.25              # réactivité : 0 = figé, 1 = instantané

    def reset(self):
        """Oublie les stats lissées (nouvel empilement / changement de vue)."""
        self._stats = None

    @staticmethod
    def _mtf(x, m):
        """Midtones Transfer Function : x, m ∈ [0,1]."""
        m = min(max(m, 0.001), 0.98)
        return np.clip(((m - 1.0) * x) / ((2.0 * m - 1.0) * x - m), 0.0, 1.0)

    @staticmethod
    def _solve_m(x, t):
        """m tel que MTF(x, m) = t — inversion exacte de la MTF."""
        x = min(max(x, 1e-4), 0.9999)
        m = x * (1.0 - t) / (t + x - 2.0 * t * x)
        return min(max(m, 0.001), 0.98)

    def _auto_params(self, img, live=True):
        mono = img.mean(axis=2) if img.ndim == 3 else img
        s = mono[::max(1, mono.shape[0] // 512), ::max(1, mono.shape[1] // 512)]
        med = float(np.median(s))
        sigma = max(float(np.median(np.abs(s - med))) * 1.4826, 1e-8)  # σ robuste (MAD)
        p999 = float(np.percentile(s, 99.9))

        # Lissage temporel des STATS (pas des paramètres) : les curseurs restent
        # réactifs, mais l'image ne « pompe » pas entre deux frames.
        if self._stats is None:
            self._stats = (med, sigma, p999)
        elif live:
            a = self._ema
            self._stats = tuple(v0 + a * (v1 - v0)
                                for v0, v1 in zip(self._stats, (med, sigma, p999)))
        med, sigma, p999 = self._stats

        lo = med - self.sigma_k * sigma                     # ombres : bruit coupé
        hi = max(p999, med + 10.0 * sigma, lo + 1e-8)        # hautes lumières réelles
        m = self._solve_m((med - lo) / (hi - lo), self.target)
        return lo, hi, m

    def process(self, img, live=True):
        img = img.astype(np.float32, copy=False)
        if self.auto:
            lo, hi, m = self._auto_params(img, live=live)
            self.last_lo, self.last_hi = lo, hi
            x = self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)
        else:
            lo, hi = self.black, self.white
            if hi - lo < 1e-6:
                hi = lo + 1e-6
            x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        if abs(self.gamma - 1.0) > 1e-3:
            x = np.power(x, 1.0 / max(self.gamma, 0.05))
        if img.ndim == 3 and abs(self.saturation - 1.0) > 1e-3:
            hsv = cv2.cvtColor(np.clip(x, 0.0, 1.0), cv2.COLOR_RGB2HSV)
            hsv[..., 1] = np.clip(hsv[..., 1] * self.saturation, 0.0, 1.0)
            x = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        return (np.clip(x, 0.0, 1.0) * 255).astype(np.uint8)
