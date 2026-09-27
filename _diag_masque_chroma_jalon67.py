# -*- coding: utf-8 -*-
"""_diag_masque_chroma_jalon67.py — POURQUOI le poids de structure ne laisse plus
passer la correction sur le FOND du fichier réel ?

Le banc `_test_chroma_structure_jalon67.py` [7] mesure, sur son empilement M31,
un anneau ramené au niveau « sans chroma » (2,00 contre 1,96) MAIS un grain
chromatique du fond qui ne tombe plus (×0,98 contre ×0,40 pour la v2.37.4) : le
poids vaut donc ~0 sur le fond, alors qu'il devrait valoir ~0,99 à 1 σ.

Ce banc imprime la chaîne d'estimation : σ estimé par MAD, distribution de
|écart| / σ sur le fond ET sur l'image entière, poids moyen, et le facteur de
grain impliqué. Lecture seule, aucun fichier écrit.

Usage : python _diag_masque_chroma_jalon67.py [fichier.fits]
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


def lire(p):
    d = np.asarray(fits.getdata(p), np.float32)
    return np.transpose(d, (1, 2, 0)) if (d.ndim == 3 and d.shape[0] == 3) else d


def stats_ecart(y, flou, titre, masque=None):
    ecart = (y - flou).astype(np.float32)
    pas = max(1, int(ecart.size) // 400000)
    e = ecart.ravel()[::pas]
    sig = float(np.median(np.abs(e))) * 1.4826
    print(f"\n  {titre}")
    print(f"    σ MAD global            : {sig:.6f}   "
          f"(médiane|écart| {float(np.median(np.abs(e))):.6f})")
    if masque is not None:
        em = ecart[masque]
        print(f"    σ réel du fond (MAD)    : "
              f"{float(np.median(np.abs(em))) * 1.4826:.6f}")
    r = np.abs(ecart) / np.float32(max(C.SEUIL_STRUCTURE_CHROMA * sig, 1e-12))
    p = 1.0 / (1.0 + np.power(r, np.float32(C.EXPOSANT_STRUCTURE_CHROMA)))
    for nom, sel in (("image entière", np.ones_like(ecart, bool)),
                     ("fond (rangées 0-120)", None)):
        if sel is None:
            sel = np.zeros_like(ecart, bool)
            sel[:120, :] = True
        rr = r[sel]
        print(f"    {nom:22s} |écart|/σ : p10 {np.percentile(rr, 10):5.2f} · "
              f"p50 {np.percentile(rr, 50):5.2f} · p90 {np.percentile(rr, 90):5.2f} "
              f"· p99 {np.percentile(rr, 99):6.2f}  → poids moyen {p[sel].mean():.3f}"
              f"  → grain ×{1.0 - FORCE * float(p[sel].mean()):.3f}")


def main():
    lin = V.normaliser_lin(lire(CHEMIN))
    lin = C.neutraliser_fond(lin)
    ycc = cv2.cvtColor(lin, cv2.COLOR_RGB2YCrCb)
    y = ycc[..., 0]
    flou = cv2.GaussianBlur(y, (0, 0), sigmaX=RAYON)
    print(f"fichier {os.path.basename(CHEMIN)} — {lin.shape[1]}×{lin.shape[0]}, "
          f"rayon {RAYON} px, force {FORCE}")
    stats_ecart(y, flou, "MÊME FLou QUE LA CHROMA (rayon 3 px)")
    # comparaison : ce que verrait un flou BEAUCOUP plus large (le grain du fond
    # domine alors l'écart, la structure large est retirée)
    for r2 in (12.0, 25.0):
        stats_ecart(y, cv2.GaussianBlur(y, (0, 0), sigmaX=r2),
                    f"COMPARAISON flou de rayon {r2:.0f} px")
    # le bruit de LUMINANCE du fond, mesuré sans flou : MAD dans une fenêtre
    # débarrassée de sa tendance (différence à une version lissée 12 px)
    d = (y - cv2.GaussianBlur(y, (0, 0), sigmaX=12.0))[:120]
    print(f"\n  bruit de luminance du fond (rangées 0-120, écart à un flou 12 px) :"
          f" MAD → σ {float(np.median(np.abs(d))) * 1.4826:.6f}")
    # et le grain CHROMATIQUE du même fond, pour situer l'échelle
    z = lin[:120].reshape(-1, 3)
    print(f"  grain chromatique du fond : σ(R−G) "
          f"{float(np.std(z[:, 0] - z[:, 1])):.6f} · σ(L) "
          f"{float(np.std(y[:120])):.6f}")


if __name__ == "__main__":
    main()
