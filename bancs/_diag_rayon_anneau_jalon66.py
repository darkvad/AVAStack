# -*- coding: utf-8 -*-
"""_diag_rayon_anneau_jalon66.py — l'ANNEAU coloré des étoiles dans le FICHIER
(visible sur la planche `_diag_etoiles_rouges_ECRAN_vs_FICHIER_jalon66.jpg`,
invisible à l'écran) : d'où vient-il, et quel levier l'enlève ?

Variantes rendues en PLEINE RÉSOLUTION (mêmes réglages qu'Alain, config du
26/09/2026), puis réduites à 1600 px pour la mesure :
  - sans la neutralisation du fond ni la chroma (pour savoir si c'est NOUS) ;
  - chroma aux rayons de référence 3 / 5 / 8 px (le curseur v2.37.4 va à 8).
Mesure : R/G par anneau, × le R/G du fond local (anneau 2-3 px = 4,8-7,2 px
pleine résolution = là où la planche montre l'anneau).

Usage : python bancs/_diag_rayon_anneau_jalon66.py [dossier]
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

RACINE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Astro\test"
sys.argv = [sys.argv[0]]

import _diag_apercu_fichier_jalon66 as A                 # noqa: E402
from avastack.processing import veralux as _veralux        # noqa: E402

ETOILES = [(194, 105), (658, 371), (1150, 737), (1276, 167)]
RING = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 7), (7, 10))
FORCE = 0.8471


def profil(img, x, y, echelle=1.0, fond=(28, 40)):
    h, w = img.shape[:2]
    xf, yf = x * echelle, y * echelle
    demi = int(round((fond[1] + 4) * echelle))
    y0, y1 = max(0, int(yf) - demi), min(h, int(yf) + demi + 1)
    x0, x1 = max(0, int(xf) - demi), min(w, int(xf) + demi + 1)
    sous = np.asarray(img[y0:y1, x0:x1], np.float64)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    rr = np.sqrt((yy - yf) ** 2.0 + (xx - xf) ** 2.0) / echelle
    m = (rr >= fond[0]) & (rr <= fond[1])
    f = sous[m].mean(axis=0)
    ref = f[0] / max(f[1], 1e-12)
    out = []
    for (a, b) in RING:
        mm = (rr >= a) & (rr < b)
        out.append(float((sous[mm].mean(axis=0)[0]
                          / max(sous[mm].mean(axis=0)[1], 1e-12)) / ref)
                   if int(mm.sum()) >= 2 else np.nan)
    return out


def main():
    lin = _veralux.normaliser_lin(A.lire_fits(
        os.path.join(RACINE, "M31_traite_lineaire_2.37.3.fits")))
    petit, ech = A.reduire(lin)
    _, logd, _ = _veralux.etirer(
        A._avant_etirement(petit, True, FORCE, 3.0, ech),
        mode=_veralux.MODE_TARGET_BG, target_bg=A.TARGET_BG, profil=A.PROFIL)
    print(f"logD (écran) = {logd:.4f}")
    print("\nanneaux (px d'aperçu)   " + "  ".join(f"{a}-{b}" for a, b in RING))
    cas = [("AUCUNE correction live", lin, None),
           ("chroma rayon 3 px", lin, 3.0),
           ("chroma rayon 5 px", lin, 5.0),
           ("chroma rayon 8 px", lin, 8.0)]
    for nom, base, rayon in cas:
        src = (base if rayon is None
               else A._avant_etirement(base, True, FORCE, rayon, 1.0))
        rendu, _, _ = _veralux.etirer(src, mode=_veralux.MODE_LOG_D,
                                      log_d=logd, target_bg=A.TARGET_BG,
                                      profil=A.PROFIL)
        rendu = A.gamma(rendu)
        petit_r, _ = A.reduire(rendu)
        print(f"\n  {nom}")
        for (x, y) in ETOILES:
            pr = profil(petit_r, x, y)
            print(f"    ({x:4d},{y:3d})  " + "  ".join(f"{v:5.2f}" for v in pr))
    # le fichier réellement enregistré, pour mémoire
    reel = A.lire_fits(os.path.join(
        RACINE, "m31_stack_etire-telquevu_traite-v2.37.3.fits"))
    reel_p, _ = A.reduire(reel)
    print("\n  FICHIER réellement enregistré (celui d'Alain)")
    for (x, y) in ETOILES:
        pr = profil(reel_p, x, y)
        print(f"    ({x:4d},{y:3d})  " + "  ".join(f"{v:5.2f}" for v in pr))

    # --- balayage de la FORCE (rayon de référence 3 px) : anneau contre grain
    print("\n  Bilan force <-> anneau <-> grain chromatique du fond "
          "(rayon 3 px, pleine résolution) :")
    print("    force   anneau moyen des 4 étoiles (anneau 2-3 px)   "
          "grain chromatique du fond")
    base = A._avant_etirement(lin, True, 0.0, 3.0, 1.0)   # neutralisée, chroma OFF
    g0 = (base[:120].reshape(-1, 3)[:, 0] - base[:120].reshape(-1, 3)[:, 1])
    for force in (0.0, 0.25, 0.5, 0.85):
        src = A._avant_etirement(lin, True, force, 3.0, 1.0)
        g1 = src[:120].reshape(-1, 3)[:, 0] - src[:120].reshape(-1, 3)[:, 1]
        grain = float(np.std(g1)) / max(float(np.std(g0)), 1e-12)
        rendu, _, _ = _veralux.etirer(
            src, mode=_veralux.MODE_LOG_D, log_d=logd, target_bg=A.TARGET_BG,
            profil=A.PROFIL)
        petit_r, _ = A.reduire(A.gamma(rendu))
        anneaux = [profil(petit_r, x, y)[2] for (x, y) in ETOILES]
        print(f"    {force:4.2f}    {np.mean(anneaux):5.2f} "
              f"(détail " + " ".join(f"{v:4.2f}" for v in anneaux) + ")      "
              f"×{grain:.2f} du grain d'origine")


if __name__ == "__main__":
    main()
