# -*- coding: utf-8 -*-
"""_diag_planche_chroma_jalon66.py — planche « avec / sans réduction du bruit
chromatique » sur les étoiles, en PLEINE RÉSOLUTION (le fichier « tel que vu »).

But : montrer à Alain le levier CHIFFRÉ (mesuré par `_diag_rayon_anneau_jalon66`)
— la chroma à sa force habituelle (0,85) AMPLIFIE l'anneau de couleur des
étoiles, et c'est ce qui le rend visible dans les fichiers (invisible à l'écran
où la même chaîne est appliquée à une image réduite).

Sortie : C:\\Astro\\test\\_diag_anneau_chroma_jalon66.jpg
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

import _diag_apercu_fichier_jalon66 as A                 # noqa: E402
from avastack.processing import veralux as _veralux        # noqa: E402

ETOILES = [(194, 105), (658, 371), (1150, 737), (1276, 167)]
FORCE = 0.8471
SORTIE = os.path.join(RACINE, "_diag_anneau_chroma_jalon66.jpg")
VIGNETTE, GROSSIR = 60, 3


def decoupe(img, x, y, echelle, taille=VIGNETTE):
    h, w = img.shape[:2]
    cible = 2 * taille * GROSSIR
    xf, yf = x * echelle, y * echelle
    demi = int(round(taille * echelle))
    x0, y0 = int(round(xf)) - demi, int(round(yf)) - demi
    px0, py0 = max(0, -x0), max(0, -y0)
    sous = img[max(0, y0):max(0, y0) + 2 * demi, max(0, x0):max(0, x0) + 2 * demi]
    pad = np.zeros((py0 * 2 + sous.shape[0], px0 * 2 + sous.shape[1], 3), np.float32)
    pad[py0:py0 + sous.shape[0], px0:px0 + sous.shape[1]] = sous
    interp = cv2.INTER_NEAREST if pad.shape[0] < cible else cv2.INTER_AREA
    return np.clip(cv2.resize(pad, (cible, cible), interpolation=interp), 0, 1)


def bandeau(img, texte, h=28):
    b = np.full((h, img.shape[1], 3), 20, np.uint8)
    cv2.putText(b, texte, (6, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    return np.vstack([b.astype(np.float32) / 255.0, img])


def main():
    lin = _veralux.normaliser_lin(A.lire_fits(
        os.path.join(RACINE, "M31_traite_lineaire_2.37.3.fits")))
    petit, ech = A.reduire(lin)
    _, logd, _ = _veralux.etirer(
        A._avant_etirement(petit, True, FORCE, 3.0, ech),
        mode=_veralux.MODE_TARGET_BG, target_bg=A.TARGET_BG, profil=A.PROFIL)
    images = {}
    for nom, force in (("chroma 0,85 (ton réglage)", FORCE),
                       ("chroma ARRÊTÉE", 0.0)):
        src = A._avant_etirement(lin, True, force, 3.0, 1.0)
        rendu, _, _ = _veralux.etirer(src, mode=_veralux.MODE_LOG_D, log_d=logd,
                                      target_bg=A.TARGET_BG, profil=A.PROFIL)
        images[nom] = A.gamma(rendu)
    h, w = images[list(images)[0]].shape[:2]
    noms = list(images)
    rangees = []
    for (x, y) in ETOILES:
        if not (VIGNETTE < x < w * ech - VIGNETTE and VIGNETTE < y < h * ech - VIGNETTE):
            continue
        v = [bandeau(decoupe(images[n], x, y, 1.0 / ech), f"FICHIER — {n}")
             for n in noms]
        rangees.append(np.hstack([v[0], np.ones((v[0].shape[0], 6, 3), np.float32),
                                  v[1]]))
    if not rangees:
        print("aucune étoile mesurable")
        return
    planche = np.vstack([np.vstack([r, np.ones((8, r.shape[1], 3), np.float32)])
                         for r in rangees])
    cv2.imwrite(SORTIE, cv2.cvtColor((planche * 255).astype(np.uint8),
                                     cv2.COLOR_RGB2BGR),
                [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    print(f"planche écrite : {SORTIE} ({planche.shape[1]}×{planche.shape[0]} px)")


if __name__ == "__main__":
    main()
