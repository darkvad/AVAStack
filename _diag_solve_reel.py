# -*- coding: utf-8 -*-
r"""Diagnostic RÉEL du solveur astrométrique (jalon 56, étapes 2-3).

Résout l'astrométrie d'une VRAIE image (empilement FITS du projet, brute
débayerisée…) avec le solveur INTERNE d'AVAStack, puis — si ASTAP est
installé — avec astap_cli, et confronte les deux (règle de CLAUDE.md :
toute implémentation est confrontée à une référence indépendante).

Utilisation (exemples) :
  python _diag_solve_reel.py "C:\acquisition\M31_stack.fit" ^
      --ra 0h42m44s --dec +41d16m09s --focal 1280 --pixel 2.9
  python _diag_solve_reel.py stack.fit --ra 10.7 --dec 41.3 --champ 0.50
  python _diag_solve_reel.py stack.fit --sans-astap --ra 10.7 --dec 41.3 --champ 0.5

  --ra    : soit sexagésimal en HEURES (« 0h42m44s » ou « 0:42:44 »),
            soit degrés décimaux (« 0.7123 ») ;
  --dec   : soit sexagésimal en degrés (« +41d16m09s »), soit décimal ;
  --champ : largeur du champ (côté est-ouest) en DEGRÉS — si tu ne la
            connais pas, donne --focal (mm) et --pixel (µm) à la place,
            le champ est alors calculé (échelle = 206,265 × pixel / focal) ;
  --sans-astap : ne pas interroger astap_cli (solve interne seul).
  Si --ra/--dec sont absents, ASTAP est interrogé D'ABORD sans indices,
  et son centre sert d'indice au solveur interne (précisé à l'affichage).

Sortie : exit 0 si le solve interne a produit une solution cohérente avec
ASTAP (quand il est disponible), exit 1 sinon — jamais d'exception brute.
"""
import argparse
import math
import os
import sys

import numpy as np

from avastack.catalogues import WcsTan, resoudre
from avastack.catalogues import astap as _astap
from avastack.images import load_image

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_deg(txt, en_heures=False):
    """« 0h42m44s » / « 0:42:44 » (RA en heures), « +41d16m09s » (dec),
    « 0.7123h » (heures décimales), « 41.2692 » (degrés décimaux) → degrés."""
    t = str(txt).strip().lower().replace(",", ".")
    if any(c in t for c in "hdms'\"") or ":" in t:
        signe = -1.0 if t.startswith("-") else 1.0
        t = t.lstrip("+-")
        for ch in ("h", "d", "m", "s", "'", '"'):
            t = t.replace(ch, ":")
        parts = [p for p in t.split(":") if p]
        if not 1 <= len(parts) <= 3:
            raise ValueError(f"angle illisible : {txt!r}")
        v = [float(p) for p in parts] + [0.0] * (3 - len(parts))
        res = v[0] + v[1] / 60.0 + v[2] / 3600.0
        return signe * res * (15.0 if en_heures else 1.0)
    v = float(t)
    return v * 15.0 if en_heures else v


def ecart_wcs_deg(w1, w2, forme, n=9):
    """Écart angulaire max (deg) entre deux WCS sur une grille de pixels."""
    h, w = forme
    xs = np.linspace(0, w - 1, n)
    ys = np.linspace(0, h - 1, n)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.column_stack([XX.ravel(), YY.ravel()])
    ra1, dec1 = w1.vers_radec(pts)
    ra2, dec2 = w2.vers_radec(pts)
    p1, d1, p2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    a = (np.sin((d2 - d1) / 2.0) ** 2
         + np.cos(d1) * np.cos(d2) * np.sin((p2 - p1) / 2.0) ** 2)
    return float(np.degrees(2.0 * np.arcsin(
        np.sqrt(np.clip(a, 0.0, 1.0)))).max())


def principal():
    ap = argparse.ArgumentParser(
        description="Solve astrométrique RÉEL : solveur interne AVAStack "
                    "confronté à ASTAP.")
    ap.add_argument("image", help="FITS (empilement ou brute débayerisée)")
    ap.add_argument("--ra", default=None,
                    help="indice RA (« 0h42m44s », heures décimales "
                         "« 0.7123h » ou degrés décimaux « 0.7123 »)")
    ap.add_argument("--dec", default=None,
                    help="indice Dec (« +41d16m09s » ou « 41.2692 »)")
    ap.add_argument("--champ", type=float, default=None,
                    help="largeur du champ en degrés (est-ouest)")
    ap.add_argument("--focal", type=float, default=None,
                    help="focale en mm (avec --pixel, calcule le champ)")
    ap.add_argument("--pixel", type=float, default=None,
                    help="taille du pixel en µm (avec --focal)")
    ap.add_argument("--sans-astap", action="store_true",
                    help="solve interne seul, sans astap_cli")
    args = ap.parse_args()

    if not os.path.isfile(args.image):
        print(f"ERREUR : image absente : {args.image}")
        return 1
    img = load_image(args.image)
    h, w = img.shape[:2]
    print(f"Image : {os.path.basename(args.image)} — {w}×{h} px, "
          f"{img.dtype}, [{float(np.nanmin(img)):.4g} … "
          f"{float(np.nanmax(img)):.4g}]")

    # ---- échelle / champ : donnés ou calculés ------------------------------
    ech = None                               # ″/px
    if args.champ:
        ech = args.champ * 3600.0 / w
    elif args.focal and args.pixel:
        ech = 206.265 * args.pixel / args.focal
    if ech is not None:
        champ = w * ech / 3600.0
        print(f"Échelle indicative : {ech:.3f}\u2033/px — champ "
              f"{champ:.3f}° × {h * ech / 3600.0:.3f}°")
    else:
        champ = None
        if args.ra is None or args.dec is None:
            print("ERREUR : il faut --champ, ou (--focal et --pixel), "
                  "ou laisser ASTAP déduire les indices (ne pas donner "
                  "--ra/--dec et NE PAS passer --sans-astap).")
            return 1

    ra0 = parse_deg(args.ra, en_heures=True) if args.ra else None
    dec0 = parse_deg(args.dec) if args.dec else None
    if ra0 is not None:
        ra0 %= 360.0

    exe = None if args.sans_astap else _astap.trouver_astap()
    wcs_ap = None
    # ---- indices absents : ASTAP d'abord, son centre sert d'indice --------
    if ra0 is None or dec0 is None:
        if exe is None:
            print("ERREUR : pas d'indices et astap_cli absent — impossible "
                  "de démarrer (donnez --ra/--dec et --champ).")
            return 1
        print("\n[1] Indices absents → ASTAP SANS indices d'abord "
              "(balayage, plus lent)…")
        wcs_ap, msg = _astap.resoudre_avec_astap(args.image, fov_deg=0.0)
        if wcs_ap is None:
            print(f"  ASTAP : ÉCHEC — {msg}")
            return 1
        ra0, dec0 = (float(v) for v in wcs_ap.vers_radec(
            np.array([[(w - 1) / 2.0, (h - 1) / 2.0]])))
        ra0 %= 360.0
        print(f"  ASTAP : centre résolu ({ra0:.4f}°, {dec0:.4f}°) — sert "
              "d'indice au solveur interne (PAS une parité indépendante).")
        if champ is None:
            champ = w * wcs_ap.echelle_arcsec / 3600.0
            print(f"  champ déduit d'ASTAP : {champ:.3f}°")

    # ---- solve INTERNE -------------------------------------------------------
    print(f"\n[{'2' if wcs_ap is not None else '1'}] Solve INTERNE "
          f"(indices {ra0:.4f}°, {dec0:.4f}°, champ {champ:.3f}°)…")
    wcs_in, info, msg = resoudre(img, ra0, dec0, champ)
    if wcs_in is None:
        print(f"  INTERNE : ÉCHEC — {msg}")
        return 1
    ra_c, dec_c = wcs_in.vers_radec(np.array([[(w - 1) / 2.0,
                                               (h - 1) / 2.0]]))
    print(f"  INTERNE : centre résolu ({float(ra_c[0]):.4f}°, "
          f"{float(dec_c[0]):.4f}°) — échelle "
          f"{wcs_in.echelle_arcsec:.3f}\u2033/px, angle "
          f"{wcs_in.angle_deg:+.2f}°, rms {info['rms_px']:.2f} px "
          f"({info['rms_arcsec']:.2f}\u2033) sur "
          f"{info['n_appariements']} étoiles")

    # ---- ASTAP avec les mêmes indices + confrontation ------------------------
    if exe is None:
        print("\nASTAP absent (--sans-astap) : pas de confrontation — "
              "verdict sur les seuls garde-fous internes.")
        return 0
    fov_h = (h * wcs_in.echelle_arcsec / 3600.0 if ech is None
             else h * ech / 3600.0)
    print(f"\n[{'3' if wcs_ap is None else '2b'}] ASTAP (mêmes indices, "
          f"fov hauteur {fov_h:.3f}°)…")
    if wcs_ap is None:
        wcs_ap, msg = _astap.resoudre_avec_astap(args.image, ra0=ra0,
                                                 dec0=dec0, rayon_deg=3.0,
                                                 fov_deg=fov_h)
        if wcs_ap is None:
            print(f"  ASTAP : ÉCHEC — {msg} (le solve interne reste "
                  "utilisable, mais pas de référence indépendante)")
            return 0
    ecart = ecart_wcs_deg(wcs_in, wcs_ap, (h, w)) * 3600.0
    ech_rel = wcs_in.echelle_arcsec / wcs_ap.echelle_arcsec
    print(f"  INTERNE vs ASTAP : écart max {ecart:.2f}\u2033 sur la grille, "
          f"échelle {ech_rel * 100:.2f} %")
    bon = ecart < 2.0 and abs(ech_rel - 1.0) < 0.01
    print(("\nVERDICT : solve interne ≈ ASTAP — FIABLE pour le branchement."
           if bon else
           "\nVERDICT : DIVERGENCE interne/ASTAP — à examiner avant "
           "branchement (donne ce résultat à l'agent)."))
    return 0 if bon else 1


if __name__ == "__main__":
    sys.exit(principal())
