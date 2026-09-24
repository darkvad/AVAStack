# -*- coding: utf-8 -*-
r"""Diagnostic ASTAP en balayage (jalon 56, repli aveugle) — réel.

But : comprendre pourquoi un balayage SANS indices échoue là où le même
fichier se résout en 0,2 s AVEC indices, et quelle valeur de `-fov` débloque.
Écrit la version BORNÉE à [0,1] de l'image (celle que l'appli écrit, cf.
v2.27.1) et essaie plusieurs `-fov` en affichant le verdict brut d'ASTAP, puis
confronte le meilleur résultat au solveur interne indicé (référence croisée).

Usage :
    python _diag_astap_aveugle.py <image.fits> [--ra 10.68333 --dec 41.26917
                                              --champ 2.625]
"""
import argparse
import os
import shutil
import sys
import tempfile
import time

import numpy as np

from avastack.catalogues import astap as _astap
from avastack.catalogues import resoudre
from avastack.images import borner_lineaire, load_image, save_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def principal():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--ra", type=float, default=None,
                    help="indice AD en DEGRÉS (pour la référence interne)")
    ap.add_argument("--dec", type=float, default=None)
    ap.add_argument("--champ", type=float, default=None,
                    help="largeur du champ en degrés (pour la référence interne)")
    ap.add_argument("--timeout", type=float, default=120.0)
    a = ap.parse_args()

    if not os.path.isfile(a.image):
        print(f"ERREUR : image absente : {a.image}")
        return 1
    img = load_image(a.image)
    h, w = img.shape[:2]
    print(f"Image : {os.path.basename(a.image)} — {w}×{h} px, {img.dtype}, "
          f"[{float(np.nanmin(img)):.4g} … {float(np.nanmax(img)):.4g}]")

    exe = _astap.trouver_astap()
    print(f"astap_cli : {exe or 'INTROUVABLE'}")
    if exe is None:
        return 1

    tmp = tempfile.mkdtemp(prefix="avastack_diag_astap_")
    try:
        bornee, entete = borner_lineaire(img)
        chemin = os.path.join(tmp, "bornee.fits")
        save_image(chemin, bornee, entete=entete)
        print(f"Version bornée écrite : max {float(bornee.max()):.4f} "
              f"(AVASCALE={entete.get('AVASCALE')})")

        # Largeur → hauteur : c'est la HAUTEUR que `-fov` attend chez ASTAP
        # (vérifié par le banc réel M31, qui passe champ × h / w).
        ech_hauteur_deg = 2.625 * (h / float(w)) if w else 0.0
        essais = [
            (0.0, "balayage COMPLET (auto)"),
            (ech_hauteur_deg, "hauteur déduite de 2,6° de largeur"),
            (2.625, "LARGEUR passée telle quelle (piège de convention)"),
            (ech_hauteur_deg * 1.3, "hauteur × 1,3"),
        ]
        resultats = []
        for fov, quoi in essais:
            t0 = time.time()
            wcs, msg = _astap.resoudre_avec_astap(chemin, fov_deg=fov,
                                                  timeout=a.timeout,
                                                  dossier_sortie=tmp)
            dt = time.time() - t0
            etat = (f"{wcs.echelle_arcsec:.4f}\"/px, angle "
                    f"{wcs.angle_deg:+.2f}°" if wcs is not None else msg)
            print(f"  -fov {fov:7.4f} ({quoi}) : {dt:6.1f} s → {etat}")
            resultats.append((wcs, fov))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok_wcs = [(x, f) for x, f in resultats if x is not None]
    if not ok_wcs:
        print("AUCUN balayage n'a abouti — ASTAP a besoin d'indices (ou d'une "
              "base différente) sur cette image.")
        return 1
    print(f"{len(ok_wcs)}/{len(resultats)} balayage(s) ont abouti.")

    # Référence interne (si des indices sont fournis) -------------------------
    if a.ra is not None and a.dec is not None and a.champ:
        wcs_in, info, msg = resoudre(img, a.ra, a.dec, a.champ)
        if wcs_in is None:
            print(f"solve interne : ÉCHEC — {msg}")
        else:
            print(f"solve interne (indices) : {wcs_in.echelle_arcsec:.4f}\"/px, "
                  f"rms {info['rms_px']:.2f} px ({info['methode']})")
            pts = np.array([[0.0, 0.0], [w - 1.0, 0.0], [0.0, h - 1.0],
                            [w - 1.0, h - 1.0]])
            for wcs, fov in ok_wcs:
                r1, d1 = wcs_in.vers_radec(pts)
                r2, d2 = wcs.vers_radec(pts)
                sep = 3600.0 * np.hypot((r1 - r2) * np.cos(np.radians(d1)),
                                        d1 - d2)
                print(f"  vs -fov {fov:.4f} : écart max {sep.max():.2f}\", "
                      f"Δ échelle "
                      f"{abs(wcs_in.echelle_arcsec - wcs.echelle_arcsec):.4f}"
                      f"\"/px")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
