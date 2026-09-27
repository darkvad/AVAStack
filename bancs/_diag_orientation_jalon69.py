# -*- coding: utf-8 -*-
"""_diag_orientation_jalon69.py — LEQUEL des deux fichiers est en MIROIR ?

Constat (27/09/2026, fichiers « tel que vu » v2.38.1 d'Alain) : le fichier
`m31_traite_externe_etire-v2.38.1.fits` et le fichier
`m31_stack_etire-telquevu_traite-v2.38.1.fits` montrent le MÊME champ, mais
l'un des deux est retourné haut-bas (corrélation +0,990 en miroir contre +0,347
tel quel).

Ce banc tranche : chaque fichier est comparé aux fichiers LINÉAIRES de la même
session (produits par la chaîne de sauvegarde, donc dans l'orientation de
l'application). L'hypothèse « tel quel » qui gagne dit l'orientation de chaque
fichier ; celui qui s'écarte de la référence est le retourné.

Méthode : luminance, étirement doux (racine) puis normalisation médiane/MAD —
linéaire et étiré deviennent comparables ; sous-échantillonnage ×8 et recherche
par corrélation normalisée (cv2.matchTemplate), quatre hypothèses.

Usage : python bancs/_diag_orientation_jalon69.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.images import load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ECH = 8
REF = r"C:\Astro\test\M31_traite_lineaire_2.38.0.fits"
FICHIERS = (
    "m31_brute_G.fits",
    "M31_traite_lineaire_2.38.0.fits",
    "m31_stack_lineaire-v2.35.0.fits",
    "m31_stack_etire-telquevu_traite-v2.38.1.fits",
    "m31_stack_etire-telquevu_traite-v2.38.0.fits",
    "m31_traite_externe_lineaire-v2.38.0.fits",
    "m31_traite_externe_etire-v2.38.1.fits",
    "m31_traite_externe_etire-v2.38.2.fits",
    "m31_traite_externe_etire-v2.373..fits",
    "m31_traite_externe_etire-v2.38.0.fits",
)
DOSSIER = r"C:\Astro\test"


def prep(path):
    """Luminance étirée (racine) et normalisée → comparable linéaire/étiré."""
    a = np.asarray(load_image(path), np.float32)
    lum = a if a.ndim == 2 else a.mean(axis=2)
    bas, haut = (float(np.percentile(lum, 0.5)),
                 float(np.percentile(lum, 99.5)))
    x = np.clip((lum - bas) / max(1e-9, haut - bas), 0.0, 1.0)
    x = np.sqrt(x)
    s = cv2.resize(x, (x.shape[1] // ECH, x.shape[0] // ECH),
                   interpolation=cv2.INTER_AREA)
    m = float(np.median(s))
    return (s - m) / max(1e-6, 1.4826 * float(np.median(np.abs(s - m))))


ref = prep(REF)
cote = 160
y0 = (ref.shape[0] - cote) // 2
x0 = (ref.shape[1] - cote) // 2
mot = ref[y0:y0 + cote, x0:x0 + cote]
print("=" * 78)
print("ORIENTATION — référence :", REF)
print(f"  ({ref.shape[0] * ECH}×{ref.shape[1] * ECH} px, morceau central "
      f"{cote * ECH} px)")
print("=" * 78)
print(f"{'fichier':<46} {'tel quel':>9} {'miroir V':>9} {'miroir H':>9} "
      f"{'H+V':>9}   verdict")
for nom in FICHIERS:
    try:
        cible = prep(DOSSIER + "\\" + nom)
    except Exception as e:
        print(f"{nom:<46} illisible ({e})")
        continue
    sc = []
    for mir in (0, 1, 2, 3):
        c = cible
        if mir in (1, 3):
            c = c[::-1]
        if mir in (2, 3):
            c = c[:, ::-1]
        if c.shape[0] < cote or c.shape[1] < cote:
            sc.append(-2.0)
            continue
        r = cv2.matchTemplate(np.ascontiguousarray(c, np.float32),
                              np.ascontiguousarray(mot, np.float32),
                              cv2.TM_CCOEFF_NORMED)
        sc.append(float(cv2.minMaxLoc(r)[1]))
    gagnant = int(np.argmax(sc))
    verdict = ("MÊME orientation que la référence" if gagnant == 0 else
               f"MIROIR ({('V' if gagnant in (1, 3) else '')}"
               f"{('H' if gagnant in (2, 3) else '')}) — "
               f"score {sc[gagnant]:+.3f} contre {sc[0]:+.3f} tel quel")
    if max(sc) < 0.5:
        verdict = "AUCUNE superposition (champ différent ou recadré)"
    print(f"{nom:<46} {sc[0]:+9.3f} {sc[1]:+9.3f} {sc[2]:+9.3f} "
          f"{sc[3]:+9.3f}   {verdict}")
