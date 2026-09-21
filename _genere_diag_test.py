# -*- coding: utf-8 -*-
"""Génère 3 canaux synthétiques pour valider _diag_canaux_compo.py :
G = référence nette · R = décalée de (+1,5, −2,0) px · B = défocalisée ×2."""
import sys

import cv2
import numpy as np

from avastack.images import save_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

rng = np.random.default_rng(7)
H, W = 400, 520
fond = np.full((H, W), 0.02, np.float32)
pts = rng.uniform([8, 8], [H - 8, W - 8], size=(60, 2))
base = rng.uniform(0.2, 1.0, 60)

net = fond.copy()
for (y, x), a in zip(pts, base):
    cv2.circle(net, (int(round(x)), int(round(y))), 2, float(a), -1,
               lineType=cv2.LINE_AA)

noyau = np.zeros((9, 9), np.float32)
cv2.circle(noyau, (4, 4), 4, 1.0, -1, lineType=cv2.LINE_AA)
noyau /= noyau.sum()
flou = cv2.filter2D(net, -1, noyau) + fond

M = np.float32([[1, 0, 1.5], [0, 1, -2.0]])
decale = cv2.warpAffine(net, M, (W, H)) + fond

save_image("_diag_G.fit", net + 0.005 + rng.normal(0, 0.003, (H, W))
           .astype(np.float32))
save_image("_diag_R.fit", decale + rng.normal(0, 0.003, (H, W))
           .astype(np.float32))
save_image("_diag_B.fit", flou + rng.normal(0, 0.003, (H, W))
           .astype(np.float32))
print("canaux synthétiques écrits : _diag_G.fit (réf. nette), "
      "_diag_R.fit (décalée +1,5/−2,0 px), _diag_B.fit (défocalisée ×2)")
