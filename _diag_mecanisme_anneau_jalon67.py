# -*- coding: utf-8 -*-
"""_diag_mecanisme_anneau_jalon67.py — D'OÙ VIENT l'anneau, au pixel, sur son
empilement réel (pleine résolution).

Pour l'étoile la plus marquée (1150, 737 px d'aperçu → pleine résolution), on
imprime par couronne de 1 px : la luminance Y, l'échelle `den`, le RAPPORT de
couleur `cn` (Cr), sa version lissée `lisse`, et le DÉPÔT de la formule v2.37.4
`den · force · (lisse − cn)` — c'est-à-dire ce que l'ancienne formule ajoute.
But : savoir ce qui rend l'anneau si fort en vrai (et pas sur une synthèse).

Usage : python _diag_mecanisme_anneau_jalon67.py [fichier.fits]
"""
import os
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from astropy.io import fits

from avastack.processing import couleurs as C
from avastack.processing import veralux as V

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHEMIN = (sys.argv[1] if len(sys.argv) > 1
          else os.path.join(r"C:\Astro\test", "M31_traite_lineaire_2.37.3.fits"))
FORCE, RAYON = 0.8471, 3.0
ETOILE_APERCU = (1150, 737)
LARGEUR_APERCU = 1600.0


def lire(p):
    d = np.asarray(fits.getdata(p), np.float32)
    return np.transpose(d, (1, 2, 0)) if (d.ndim == 3 and d.shape[0] == 3) else d


def main():
    lin = V.normaliser_lin(lire(CHEMIN))
    h, w = lin.shape[:2]
    ech = min(1.0, LARGEUR_APERCU / float(max(h, w)))
    lin = C.neutraliser_fond(lin)
    ycc = cv2.cvtColor(lin, cv2.COLOR_RGB2YCrCb)
    y = ycc[..., 0]
    niveau = float(np.median(y))
    flou = cv2.GaussianBlur(y, (0, 0), sigmaX=RAYON)
    den = np.maximum(np.minimum(y, flou),
                     np.float32(max(C.PLANCHER_CHROMA * niveau, 1e-7)))
    cx, cy = ETOILE_APERCU[0] / ech, ETOILE_APERCU[1] / ech
    print(f"étoile d'aperçu {ETOILE_APERCU} → pleine résolution "
          f"({cx:.0f}, {cy:.0f}) · échelle ×{ech:.4f} · rayon {RAYON} px")
    print(f"niveau de ciel (médiane Y) {niveau:.5f} · maximum Y local "
          f"{float(np.max(y[int(cy) - 20:int(cy) + 20, int(cx) - 20:int(cx) + 20])):.4f}")
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    for i in (1, 2):
        cn = (ycc[..., i] - 0.5) / den
        lisse = cv2.GaussianBlur(cn, (0, 0), sigmaX=RAYON)
        depot = den * np.float32(FORCE) * (lisse - cn)
        print(f"\n  canal {'Cr' if i == 1 else 'Cb'} — "
              f"C = {ycc[..., i][int(cy), int(cx)]:.4f}")
        print("    r(px)     Y        den       cn      lisse     dépôt    "
              "(dépôt / Y)")
        for r in range(0, 11):
            m = (d >= r - 0.5) & (d < r + 0.5)
            if int(m.sum()) < 3:
                continue
            print(f"    {r:4d}  {y[m].mean():8.5f} {den[m].mean():9.5f} "
                  f"{cn[m].mean():9.3f} {lisse[m].mean():9.3f} "
                  f"{depot[m].mean():+9.5f}   {depot[m].mean() / max(y[m].mean(), 1e-9):+8.3f}")


if __name__ == "__main__":
    main()
