# -*- coding: utf-8 -*-
r"""Diagnostic FIN : les étoiles détectées tombent-elles sur le catalogue ?

Prend un WCS VRAI (résolu par ASTAP, référence indépendante), projette au ciel
les étoiles DÉTECTÉES dans l'image, et mesure l'écart à l'étoile de catalogue
la plus proche. Tranche entre :
  • « données décalées » (écarts systématiques de plusieurs px) ;
  • « bug de l'appariement du solveur » (écarts sub-pixel, et pourtant zéro
    appariement mutuel).

Usage : python _diag_appariement.py <image> --ra <deg> --dec <deg> --champ <deg>
"""
import argparse
import sys

import numpy as np

from avastack.catalogues import solveur as _solveur
from avastack.catalogues.astap import resoudre_avec_astap
from avastack.images import borner_lineaire, load_image, save_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def principal():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--ra", type=float, required=True, help="AD en degrés")
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--champ", type=float, required=True,
                    help="LARGEUR du champ en degrés")
    a = ap.parse_args()

    img = load_image(a.image)
    h, w = img.shape[:2]
    print(f"image {w}×{h} — {a.image}")

    # WCS VRAI par ASTAP (sur une copie bornée à [0,1], leçon v2.27.1)
    import tempfile
    import os
    with tempfile.TemporaryDirectory(prefix="avastack_app_") as tmp:
        bornee, _ = borner_lineaire(img)
        copie = os.path.join(tmp, "borne.fits")
        save_image(copie, bornee)
        wcs, msg = resoudre_avec_astap(copie, ra0=a.ra, dec0=a.dec,
                                       rayon_deg=1.0,
                                       fov_deg=a.champ * h / w,
                                       dossier_sortie=tmp, timeout=180)
    if wcs is None:
        print("ASTAP n'a pas résolu — impossible de conclure :", msg)
        return 1
    print(f"WCS vrai (ASTAP) : échelle {wcs.echelle_arcsec:.4f}\"/px, "
          f"angle {wcs.angle_deg:+.2f}°")

    # 1) étoiles DÉTECTÉES dans l'image (exactement le détecteur du solveur)
    pos, msg_det = _solveur._detecter(img, 120)
    print(f"[1] détection : {len(pos)} étoiles ({msg_det or 'ok'})")

    # 2) étoiles de CATALOGUE du champ (exactement l'extraction du solveur)
    et, msg_cat = _solveur._extraire_catalogue(a.ra, a.dec, a.champ, (h, w))
    if not et:
        print(f"[2] catalogue : ÉCHEC — {msg_cat}")
        return 1
    print(f"[2] catalogue : {len(et['ra'])} étoiles ({msg_cat or 'ok'})")
    ra_cat, dec_cat = et["ra"], et["dec"]

    # 3) projeté au ciel : chaque étoile d'image vs catalogue (WCS VRAI)
    ra_img, dec_img = wcs.vers_radec(pos)
    cosd = np.cos(np.radians(float(np.median(dec_img))))
    dra = (ra_img[:, None] - ra_cat[None, :]) * cosd
    ddec = dec_img[:, None] - dec_cat[None, :]
    d_deg = np.hypot(dra, ddec)
    d_px = d_deg * 3600.0 / wcs.echelle_arcsec
    plus_proche = d_px.min(axis=1)
    print(f"[3] écart de CHAQUE étoile d'image à l'étoile de catalogue la plus "
          f"proche (WCS vrai) :")
    print(f"    médiane {np.median(plus_proche):.2f} px ; "
          f"< 1 px : {int((plus_proche < 1).sum())} ; "
          f"< 2 px : {int((plus_proche < 2).sum())} ; "
          f"< 5 px : {int((plus_proche < 5).sum())} sur {len(pos)}")
    print(f"    percentiles 10/50/90 : {np.percentile(plus_proche, 10):.2f} / "
          f"{np.percentile(plus_proche, 50):.2f} / "
          f"{np.percentile(plus_proche, 90):.2f} px")

    # 4) CE QUE LE VOTE UTILISE VRAIMENT : le tri par ÉCLAT est-il fiable ?
    print(f"[4] le vote RANSAC n'utilise que les RANSAC_N_IMG={_solveur.RANSAC_N_IMG} "
          f"étoiles les PLUS BRILLANTES de l'image et les "
          f"RANSAC_N_CAT={_solveur.RANSAC_N_CAT} du catalogue :")
    for k in (12, 20, 40, 60, 120):
        if k > len(pos):
            break
        pp = plus_proche[:k]
        print(f"    top-{k:3d} image : médiane {np.median(pp):5.2f} px ; "
              f"< 2 px : {int((pp < 2).sum()):3d}/{k} "
              f"({100.0 * (pp < 2).mean():4.0f} %)")
    print("    top-15 (position, écart au catalogue) :")
    for i in range(min(15, len(pos))):
        print(f"      #{i:2d} px=({pos[i, 0]:7.1f},{pos[i, 1]:7.1f})  "
              f"écart {plus_proche[i]:8.2f} px")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
