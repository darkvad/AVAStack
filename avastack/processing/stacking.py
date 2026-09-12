# -*- coding: utf-8 -*-
"""Empilement glissant avec rejet kappa-sigma (traînées de satellites, avions)."""

import numpy as np


class LiveStacker:
    """Moyenne glissante + rejet kappa-sigma séquentiel."""
    def __init__(self, shape, k=3.0, warmup=5):
        self.shape = shape
        self.k = k
        self.warmup = warmup
        self.reset()

    def reset(self):
        self.sum = np.zeros(self.shape, np.float64)
        self.sumsq = np.zeros(self.shape, np.float64)
        self.wsum = np.zeros(self.shape, np.float64)
        self.n = 0
        self.rejected_total = 0

    def add(self, frame):
        f = frame.astype(np.float64)
        if self.k is not None and self.n >= self.warmup:
            mean = self.sum / np.maximum(self.wsum, 1e-9)
            std = np.sqrt(np.maximum(self.sumsq / np.maximum(self.wsum, 1e-9) - mean * mean, 1e-12))
            w = np.where(np.abs(f - mean) > self.k * std, 0.0, 1.0)
            self.rejected_total += int((w == 0).sum())
        else:
            w = 1.0
        self.sum += f * w
        self.sumsq += (f * f) * w
        self.wsum += w
        self.n += 1

    def mean(self):
        if self.n == 0:
            return None
        return (self.sum / np.maximum(self.wsum, 1e-9)).astype(np.float32)
