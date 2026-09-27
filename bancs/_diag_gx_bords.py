# -*- coding: utf-8 -*-
"""Diagnostic du retrait de gradient GraXpert : mesure objective du fond
aux bords et au centre sur les fichiers LINÉAIRES (avant / après correction).

Usage :
    python bancs/_diag_gx_bords.py empilement.fits [empilement_GraXpert.fits]

- Un seul fichier : indique s'il contient un gradient réel (marche
  bords/centre en %).
- Deux fichiers : compare la marche bords/centre AVANT et APRÈS correction.
  Si la correction crée un « coussin » clair, la marche APRÈS est nettement
  plus forte que celle d'AVANT (le fond des bords est sous-corrigé) ;
  si elle écrase le signal, la médiane du centre chute sous le niveau du
  bruit résiduel des bords.

NB : les valeurs absolues (linéaires, fraction de pleine échelle) comptent
peu — c'est la marche RELATIVE bords/centre qui est parlante. La médiane
est utilisée partout pour ignorer étoiles et bruit de pixels.
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

import numpy as np

from avastack.images import load_image


def luminance(a):
    """(H, W) ou (C, H, W)/(H, W, C) → luminance 2D (moyenne des canaux)."""
    a = np.asarray(a, dtype=np.float64)
    if a.ndim == 2:
        return a
    if a.ndim != 3:
        raise ValueError(f"dimensions inattendues : {a.shape}")
    # (C, H, W) si le premier axe est petit, sinon (H, W, C)
    axis = 0 if a.shape[0] <= 4 else 2
    return a.mean(axis=axis)


def marches(a, label):
    """Affiche médiane du centre et des 4 bandes de bord (+ marche en %)."""
    h, w = a.shape
    b = max(4, int(0.05 * min(h, w)))          # bande de bord : 5 % du petit côté
    centre = a[h // 4: 3 * h // 4, w // 4: 3 * w // 4]   # moitié centrale
    med_c = float(np.median(centre))
    print(f"\n--- {label} ---")
    print(f"centre (médiane)          : {med_c:.8f}")
    pire = 0.0
    for nom, z in (("haut", a[:b, :]), ("bas", a[-b:, :]),
                   ("gauche", a[:, :b]), ("droite", a[:, -b:])):
        m = float(np.median(z))
        pct = (m - med_c) / max(abs(med_c), 1e-12) * 100.0
        pire = max(pire, abs(pct))
        print(f"bande {nom:<7}           : {m:.8f}   (marche vs centre : {pct:+.1f} %)")
    return med_c, pire


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(1)
    chemins = sys.argv[1:]
    for c in chemins:
        if not os.path.isfile(c):
            print(f"Fichier introuvable : {c}")
            sys.exit(1)

    imgs = []
    for c in chemins:
        a = luminance(load_image(c))
        imgs.append((os.path.basename(c), a))
        print(f"chargé : {c}  ({a.shape[1]}×{a.shape[0]})")

    res = []
    for nom, a in imgs:
        res.append(marches(a, nom))

    if len(res) == 2:
        (n1, m1), (n2, m2) = res[0], res[1]     # (médiane centre, pire marche %)
        print("\n--- comparaison ---")
        if m1 < 5.0:
            print(f"AVANT  : fond quasi uniforme (pire marche {m1:.1f} %) — "
                  "pas de vrai gradient à retirer.")
        else:
            print(f"AVANT  : gradient réel présent (pire marche {m1:.1f} %).")
        if m2 > m1 + 10.0:
            print(f"APRÈS  : pire marche {m2:.1f} % (> avant + 10 pts) → "
                  "la correction CRÉE un coussin de bord : mécanisme confirmé.")
        else:
            print(f"APRÈS  : pire marche {m2:.1f} % — pas de coussin significatif "
                  "créé par la correction.")


if __name__ == "__main__":
    main()
