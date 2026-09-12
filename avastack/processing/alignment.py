# -*- coding: utf-8 -*-
"""Alignement de chaque frame sur une référence : features ORB + RANSAC
(translation + rotation + échelle), repli sur corrélation de phase (translation)."""

import numpy as np
import cv2


class StarAligner:
    def __init__(self, n_features=1000, ratio=0.75, min_matches=8, min_inliers=8):
        self.orb = cv2.ORB_create(nfeatures=n_features, fastThreshold=8)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.ratio, self.min_matches, self.min_inliers = ratio, min_matches, min_inliers
        self.reset()

    def reset(self):
        self.ref_kp = self.ref_des = self.ref_gray = None

    def set_reference(self, img):
        self.ref_gray = self._norm8(img)
        self.ref_kp, self.ref_des = self.orb.detectAndCompute(self.ref_gray, None)

    def _norm8(self, img):
        mono = img.mean(axis=2) if img.ndim == 3 else img
        f = mono.astype(np.float32)
        lo, hi = np.percentile(f, 1.0), np.percentile(f, 99.7)
        if hi - lo < 1e-6:
            hi = lo + 1e-6
        return (np.clip((f - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)

    def compute(self, frame):
        """→ (M 2x3, confiant)  M transforme la frame courante vers la référence."""
        g = self._norm8(frame)
        kp, des = self.orb.detectAndCompute(g, None)
        if (self.ref_des is None or des is None
                or len(kp) < self.min_matches or len(self.ref_kp) < self.min_matches):
            return self._phase(g)
        good = [pair[0] for pair in self.bf.knnMatch(self.ref_des, des, k=2)
                if len(pair) == 2 and pair[0].distance < self.ratio * pair[1].distance]
        if len(good) < self.min_matches:
            return self._phase(g)
        src = np.float32([kp[m.trainIdx].pt for m in good])           # frame courante
        dst = np.float32([self.ref_kp[m.queryIdx].pt for m in good])  # référence
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.0, maxIters=5000)
        if M is None or inl is None:
            return self._phase(g)
        return M, int(inl.sum()) >= self.min_inliers

    def _phase(self, g):
        if self.ref_gray is None or self.ref_gray.shape != g.shape:
            return np.eye(2, 3), True
        a, b = self.ref_gray.astype(np.float32), g.astype(np.float32)
        (dx, dy), _ = cv2.phaseCorrelate(a, b)
        best_d, best_M = None, np.eye(2, 3)
        for s in (1.0, -1.0):  # signe déterminé empiriquement (comparaison SSD)
            M = np.array([[1.0, 0.0, s * dx], [0.0, 1.0, s * dy]])
            warp = cv2.warpAffine(b, M, (g.shape[1], g.shape[0]))
            d = float(np.mean((warp - a) ** 2))
            if best_d is None or d < best_d:
                best_d, best_M = d, M
        return best_M, True
