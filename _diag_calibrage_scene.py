# -*- coding: utf-8 -*-
"""_diag_calibrage_scene.py — calibrer la scène de banc du miroir.

But : reproduire le MÉCANISME mesuré sur les vraies images — la corrélation
BRUTE (formule v2.38.1) est indécidable (+0,1085 / +0,1212, écart +0,0127)
alors que la corrélation sur images ÉTIRÉES (v2.38.2) tranche (+0,4084 /
+0,6825, écart +0,2741).

Balayage de deux leviers : le GRAIN (σ, en fraction du niveau de ciel : ce qui
n'est PAS partagé entre les deux images) et l'ACCENTUATION appliquée par
l'« outil » (ce qui change la texture fine). On cherche le couple où l'ancienne
formule reste sous la marge de 0,05 et la nouvelle passe largement au-dessus.

Usage : python _diag_calibrage_scene.py
"""
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def corr(x, y):
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 0 else 0.0


def echant(a):
    return a[::max(1, a.shape[0] // 256),
             ::max(1, a.shape[1] // 256)].astype(np.float64)


def etire(x):
    bas, haut = (float(np.percentile(x, 0.5)), float(np.percentile(x, 99.5)))
    return np.sqrt(np.clip((x - bas) / max(1e-9, haut - bas), 0.0, 1.0))


def scene(graine, grain, accent, halo=0.9):
    rng = np.random.default_rng(graine)
    h, w = 900, 1400
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    rr = np.sqrt(((xx - 0.52 * w) / (0.22 * w)) ** 2
                 + ((yy - 0.5 * h) / (0.12 * h)) ** 2)
    gal = halo * np.exp(-rr ** 2 * 1.8) + 0.04 * np.exp(-rr ** 2 * 0.4)
    bande = np.abs((yy - 0.5 * h) - 0.22 * (xx - 0.52 * w)) / (0.03 * h)
    gal *= (1.0 - 0.6 * np.exp(-bande ** 2))
    grad = 1.0 + 1.6 * (yy / h) + 0.4 * (xx / w)
    brut = (0.028 + gal) * grad + rng.normal(0.0, grain, (h, w))
    brut = np.clip(brut, 0.0, None).astype(np.float32)
    out = brut / grad                                   # gradient retiré
    out = cv2.GaussianBlur(out, (0, 0), sigmaX=1.2)     # débruitage (IA)
    out = out + accent * (out - cv2.GaussianBlur(out, (0, 0), sigmaX=2.5))
    out = out + rng.normal(0.0, grain, (h, w))          # texture propre à l'IA
    return brut, (out * 0.85).astype(np.float32)


print(f"{'halo':>6} {'grain':>7} {'accent':>7} | {'ancienne (droite/miroir)':>28} "
      f"| {'nouvelle (droite/miroir)':>28}")
for halo in (0.9, 0.3):
    for grain in (0.001, 0.004):
        for accent in (1.2, 6.0):
            brut, out = scene(6901, grain, accent, halo)
            proc = np.flipud(out).copy()
            a, b = echant(proc), echant(brut)
            c1, c2 = corr(a, b), corr(a, b[::-1])
            e1, e2 = etire(proc), etire(brut)
            d1, d2 = corr(e1, e2), corr(e1, e2[::-1])
            repere = ("   ← REPRODUIT LE DÉFAUT"
                      if (c2 - c1) < 0.05 < (d2 - d1) else "")
            print(f"{halo:6.2f} {grain:7.4f} {accent:7.1f} | {c1:+10.4f} "
                  f"{c2:+10.4f} (écart {c2 - c1:+.4f}) | {d1:+10.4f} "
                  f"{d2:+10.4f} (écart {d2 - d1:+.4f}){repere}")
