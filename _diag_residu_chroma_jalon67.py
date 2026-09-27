# -*- coding: utf-8 -*-
"""_diag_residu_jalon63.py — POURQUOI le banc jalon63 mesure encore 9 % de grain
chromatique à force 1,0 alors que le masque laisse passer la correction sur le fond.

Hypothèse : le banc mesure un σ (sensible aux rares pixels à forte excursion de
luminance, où le masque protège la couleur — comportement VOULU), au lieu d'une
échelle ROBUSTE du grain (MAD). Ce banc compare les deux.

Usage : python _diag_residu_jalon63.py
"""
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.processing import couleurs as C

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CIEL, GRAIN = 0.031, 0.0005
COULEUR_OBJ = (1.00, 0.80, 0.55)
H, W = 600, 900
rng = np.random.default_rng(7)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt((xx - W / 2.0) ** 2 + (yy - H / 2.0) ** 2)
galaxie = 0.9 * np.exp(-(rr / 40.0) ** 2) + 0.25 * np.exp(-(rr / 140.0) ** 2)
bruit = rng.normal(0.0, GRAIN, (H, W, 3)).astype(np.float32)
scene = np.stack([CIEL + COULEUR_OBJ[c] * galaxie + bruit[..., c]
                  for c in range(3)], -1).astype(np.float32)
ZONE = (slice(20, 160), slice(20, 400))

y = cv2.cvtColor(scene, cv2.COLOR_RGB2YCrCb)[..., 0]
flou = cv2.GaussianBlur(y, (0, 0), sigmaX=3.0)
sig = float(np.median(np.abs((y - flou).ravel()))) * 1.4826
poids = 1.0 / (1.0 + np.power(np.abs(y - flou) / np.float32(3.0 * sig),
                             np.float32(6.0)))
print(f"σ estimé {sig:.6f} · poids moyen (zone de ciel) "
      f"{float(poids[ZONE].mean()):.4f} · part < 0,5 : "
      f"{100.0 * float((poids[ZONE] < 0.5).mean()):.2f} %")


def mesures(a, zone=ZONE):
    out = []
    for i, j in ((0, 1), (2, 1)):
        d = np.asarray(a, np.float32)[..., i][zone] - np.asarray(a, np.float32)[..., j][zone]
        h = d - cv2.GaussianBlur(d, (0, 0), sigmaX=2.0)
        out.append((float(h.std()), float(np.median(np.abs(h))) * 1.4826))
    return out


m0, m1 = mesures(scene), mesures(C.reduire_bruit_chroma(scene, force=1.0))
for k, nom in enumerate(("R−G", "B−G")):
    print(f"  {nom} : σ {m0[k][0]:.6f} → {m1[k][0]:.6f} (×{m1[k][0] / m0[k][0]:.3f})"
          f"   ·   MAD {m0[k][1]:.6f} → {m1[k][1]:.6f} "
          f"(×{m1[k][1] / m0[k][1]:.3f})")
