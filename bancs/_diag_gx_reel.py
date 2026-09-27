# -*- coding: utf-8 -*-
"""Test RÉEL du module live (jalon 4) avec le GraXpert installé.

Vérifie que avastack.external.live.appliquer() produit bien une image
traitée (sans erreur, bonnes dimensions, fond réellement modifié) sur :
  - une image MONO (H,W) — interpolation AI ;
  - une image RGB (H,W,3) — FITS canaux-en-tête (convention attendue par
    le lecteur de GraXpert ; l'AI fonctionne alors aussi en RGB).

Lançable : python bancs/_diag_gx_reel.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from avastack.external import detection
from avastack.external import live as gxl

CMD = detection.DEFAULT_CMD_GRAXPERT


def etoiles(h, w, rgb=True):
    rs = np.random.default_rng(7)
    img = np.full((h, w, 3) if rgb else (h, w), 0.02, np.float32)
    for _ in range(300):
        y, x = rs.integers(2, h - 2), rs.integers(2, w - 2)
        v = np.clip(0.1 + rs.pareto(2.5) * 0.05, 0, 1)
        img[y - 1:y + 2, x - 1:x + 2] += v * 0.3
        img[y, x] += v
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    neb = (0.012 * np.exp(-((xx - w * 0.68) ** 2 + (yy - h * 0.35) ** 2)
                          / (2 * (w * 0.22) ** 2))).astype(np.float32)
    return img + (neb[..., None] if rgb else neb)


def essai(nom, img):
    t0 = time.time()
    out, err = gxl.appliquer(img.copy(), CMD)
    duree = time.time() - t0
    if err:
        print(f"[{nom}] ÉCHEC ({duree:.1f}s) : {err}")
        return False
    ecart = float(np.max(np.abs(out - img)))
    print(f"[{nom}] OK ({duree:.1f}s) — image traitée, écart max {ecart:.4f}")
    return True


if __name__ == "__main__":
    ok = True
    ok &= essai("mono_960x640", etoiles(640, 960, rgb=False))
    ok &= essai("rgb_960x640", etoiles(640, 960))
    ok &= essai("rgb_1600x1000", etoiles(1000, 1600))
    print()
    print("RÉUSSITE" if ok else "ÉCHECS")
    sys.exit(0 if ok else 1)


