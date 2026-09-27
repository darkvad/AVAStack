# -*- coding: utf-8 -*-
"""_diag_planche_etoiles_jalon66.py — planche visuelle « écran ⇄ fichier » sur
les étoiles rouges (preuve à juger par Alain).

Pour chaque étoile, trois vignettes du MÊME champ physique, à la MÊME taille
d'affichage (×3) :
  ① APP  : ce que l'appli affiche (chaîne appliquée à l'APERÇU 1600 px) ;
  ② FICHIER : ce que l'appli enregistre (chaîne appliquée aux 3839 px),
     à la même échelle que ① pour permettre la comparaison ;
  ③ FICHIER réduit à 1600 px : le fichier tel qu'un viewer le montre écran plein.

Sortie : C:\\Astro\\test\\_diag_etoiles_rouges_ECRAN_vs_FICHIER_jalon66.jpg
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
import cv2

RACINE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Astro\test"
sys.argv = [sys.argv[0]]

try:                          # sortie console : jamais de plantage d'encodage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _diag_apercu_fichier_jalon66 as A     # noqa: E402
from avastack.processing import veralux as _veralux     # noqa: E402

ETOILES = [(194, 105), (658, 371), (1150, 737), (1276, 167), (800, 452)]
# Les stars 800,452 est celle du dossier externe : on saute si hors image.
VIGNETTE = 68          # demi-côté de la vignette, en px d'APERÇU
GROSSIR = 3            # facteur d'affichage
SORTIE = os.path.join(RACINE, "_diag_etoiles_rouges_ECRAN_vs_FICHIER_jalon66.jpg")


def vignette(img, x, y, echelle, taille=VIGNETTE, cible=None):
    """Découpe centrée sur (x, y) (px d'aperçu), rayon `taille` px d'aperçu,
    puis met à l'échelle d'affichage `cible`."""
    h, w = img.shape[:2]
    cible = cible or 2 * taille * GROSSIR
    xf, yf = x * echelle, y * echelle
    demi = int(round(taille * echelle))
    x0, x1 = int(round(xf)) - demi, int(round(xf)) + demi
    y0, y1 = int(round(yf)) - demi, int(round(yf)) + demi
    px0, py0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    sous = img[y0:y1, x0:x1]
    pad = np.zeros((py0 * 2 + sous.shape[0], px0 * 2 + sous.shape[1], 3), np.float32)
    pad[py0:py0 + sous.shape[0], px0:px0 + sous.shape[1]] = sous
    interp = cv2.INTER_NEAREST if pad.shape[0] < cible else cv2.INTER_AREA
    gros = cv2.resize(pad, (cible, cible), interpolation=interp)
    return np.clip(gros, 0.0, 1.0)


def bandeau(img, texte, h=28):
    """Bandeau de titre (OpenCV 5 n'écrit de texte que sur du 8 bits)."""
    b = np.full((h, img.shape[1], 3), 20, np.uint8)
    cv2.putText(b, texte, (6, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    return np.vstack([b.astype(np.float32) / 255.0, img])


def main():
    neutre, f_chroma, r_chroma = True, 0.8471, 3.0
    lin = _veralux.normaliser_lin(A.lire_fits(
        os.path.join(RACINE, "M31_traite_lineaire_2.37.3.fits")))
    petit, ech = A.reduire(lin)
    lin_p = A._avant_etirement(lin, neutre, f_chroma, r_chroma, 1.0)
    petit_p = A._avant_etirement(petit, neutre, f_chroma, r_chroma, ech)
    ecran, logd, _ = _veralux.etirer(petit_p, mode=_veralux.MODE_TARGET_BG,
                                     target_bg=A.TARGET_BG, profil=A.PROFIL)
    fichier, _, _ = _veralux.etirer(lin_p, mode=_veralux.MODE_LOG_D, log_d=logd,
                                    target_bg=A.TARGET_BG, profil=A.PROFIL)
    ecran, fichier = A.gamma(ecran), A.gamma(fichier)
    fich_reduit, _ = A.reduire(fichier)
    h, w = ecran.shape[:2]
    rangees = []
    for (x, y) in ETOILES:
        if not (VIGNETTE < x < w - VIGNETTE and VIGNETTE < y < h - VIGNETTE):
            continue
        cible = 2 * VIGNETTE * GROSSIR
        v1 = bandeau(vignette(ecran, x, y, 1.0, cible=cible),
                     f"APP (affiché) — étoile {x},{y}")
        v2 = bandeau(vignette(fichier, x, y, 1.0 / ech, cible=cible),
                     "FICHIER (enregistré, pleine rés.)")
        v3 = bandeau(vignette(fich_reduit, x, y, 1.0, cible=cible),
                     "FICHIER réduit 1600 (viewer)")
        rangees.append(np.hstack([v1, np.ones((v1.shape[0], 6, 3), np.float32),
                                  v2, np.ones((v2.shape[0], 6, 3), np.float32),
                                  v3]))
    if not rangees:
        print("aucune étoile mesurable")
        return
    planche = np.vstack([np.vstack([r, np.ones((8, r.shape[1], 3), np.float32)])
                         for r in rangees])
    cv2.imwrite(SORTIE, cv2.cvtColor((planche * 255).astype(np.uint8),
                                     cv2.COLOR_RGB2BGR),
                [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    print(f"planche écrite : {SORTIE}  ({planche.shape[1]}×{planche.shape[0]} px)")


if __name__ == "__main__":
    main()
