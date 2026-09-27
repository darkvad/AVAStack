# -*- coding: utf-8 -*-
"""_diag_anneaux_fins_jalon66.py — mesure FINE de l'écart écran ⇄ fichier sur
les étoiles rouges (anneaux de 1 px, mêmes rayons PHYSIQUES des deux côtés).

Tous les rendus sortent du MOTEUR d'étirement lui-même (aucune réimplémentation)
et les étapes pré-étirement viennent des fonctions de l'appli : c'est la chaîne
réelle, rejouée en différé sur les fichiers d'Alain.

  ÉCRAN  = chaîne(empilement RÉDUIT à 1600 px)  → ce que l'appli affiche
  FICHIER= chaîne(empilement PLEIN FORMAT)      → ce que l'appli enregistre

Usage : python bancs/_diag_anneaux_fins_jalon66.py [dossier]
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
sys.argv = [sys.argv[0]]                     # évite de propager le dossier

try:                          # sortie console : jamais de plantage d'encodage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _diag_apercu_fichier_jalon66 as A     # noqa: E402  (outils partagés)
import _diag_veralux_resolution_jalon66 as R  # noqa: E402  (réplique du moteur)
from avastack.processing import veralux as _veralux     # noqa: E402

RING = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 7), (7, 10), (10, 14))
ETOILES = [(194, 105), (658, 371), (1150, 737), (1276, 167)]


def profil(img, x, y, echelle=1.0, fond=(28, 40)):
    """R/G par anneau de 1 px (rayons en px d'APERÇU × echelle), rapporté au
    R/G du fond local — mêmes rayons physiques pour toutes les images."""
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
        if int(mm.sum()) < 2:
            out.append(np.nan)
            continue
        c = sous[mm].mean(axis=0)
        out.append(float((c[0] / max(c[1], 1e-12)) / ref))
    return out


def main():
    neutre, f_chroma, r_chroma = True, 0.8471, 3.0     # config d'Alain
    lin = _veralux.normaliser_lin(A.lire_fits(
        os.path.join(RACINE, "M31_traite_lineaire_2.37.3.fits")))
    petit, ech = A.reduire(lin)
    lin_p = A._avant_etirement(lin, neutre, f_chroma, r_chroma, 1.0)
    petit_p = A._avant_etirement(petit, neutre, f_chroma, r_chroma, ech)

    ecran, logd, d_p = _veralux.etirer(
        petit_p, mode=_veralux.MODE_TARGET_BG, target_bg=A.TARGET_BG,
        profil=A.PROFIL)
    fichier, _, d_f = _veralux.etirer(
        lin_p, mode=_veralux.MODE_LOG_D, log_d=logd, target_bg=A.TARGET_BG,
        profil=A.PROFIL)
    ecran, fichier = A.gamma(ecran), A.gamma(fichier)      # gamma v2.15 de l'appli
    # l'ancre PLEINE RÉSOLUTION n'est calculée par le moteur qu'en mode « fond
    # cible » : on la lit en refaisant le rendu dans CE mode (diagnostic seul).
    _, logd_f, d_f2 = _veralux.etirer(
        lin_p, mode=_veralux.MODE_TARGET_BG, target_bg=A.TARGET_BG,
        profil=A.PROFIL)
    print(f"logD résolu sur l'APERÇU {logd:.4f} | résolu en PLEINE RÉS. "
          f"{logd_f:.4f}")
    print(f"ancre de l'APERÇU        {d_p['anchor']:.6f}  (pression étoiles "
          f"{d_p['star_pressure']:.3f})")
    print(f"ancre PLEINE RÉSOLUTION  {d_f2['anchor']:.6f}  (pression étoiles "
          f"{d_f2['star_pressure']:.3f})")
    print(f"  → ancre pleine rés. − ancre aperçu = "
          f"{d_f2['anchor'] - d_p['anchor']:+.6f} ; niveau de ciel de "
          f"l'aperçu {float(np.median(petit_p.mean(axis=2))):.5f}")

    fich_reduit, _ = A.reduire(fichier)
    # variantes : la MÊME chaîne pleine résolution, avec l'ANCRE de l'écran
    _, i_ecran = R.chaine(petit_p, logd)
    var_ancre, _ = R.chaine(lin_p, logd, anchor=i_ecran["ancre"])
    var_const, _ = R.chaine(lin_p, logd,
                            constantes={"plancher": i_ecran["plancher"],
                                        "echelle": i_ecran["echelle"],
                                        "m": i_ecran["m"]})
    var_deux, _ = R.chaine(lin_p, logd, anchor=i_ecran["ancre"],
                           constantes={"plancher": i_ecran["plancher"],
                                       "echelle": i_ecran["echelle"],
                                       "m": i_ecran["m"]})
    va, _ = A.reduire(A.gamma(var_ancre))
    vc, _ = A.reduire(A.gamma(var_const))
    vd, _ = A.reduire(A.gamma(var_deux))
    entete = ("anneaux (px d'aperçu) " + " ".join(f"{a}-{b}" for a, b in RING))
    print(f"\n{entete}")
    for (x, y) in ETOILES:
        print(f"\n  étoile ({x},{y})")
        for nom, img, echl in (("ÉCRAN (aperçu étiré)", ecran, 1.0),
                               ("FICHIER (pleine rés.)", fichier, 1.0 / ech),
                               ("FICHIER réduit 1600", fich_reduit, 1.0),
                               ("FICHIER + ancre écran", va, 1.0),
                               ("FICHIER + const écran", vc, 1.0),
                               ("FICHIER + les deux", vd, 1.0)):
            pr = profil(img, x, y, echelle=echl)
            print(f"    {nom:22s} " + "  ".join(f"{v:5.2f}" for v in pr))


if __name__ == "__main__":
    main()
