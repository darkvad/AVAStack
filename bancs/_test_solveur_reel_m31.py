# -*- coding: utf-8 -*-
"""Banc de régression RÉEL : stack composite M31 (2,6°, échouait avant) +
brute G (N.I.N.A., cas facile). Confrontation ASTAP incluse (référence
indépendante) : les deux images sortent de la MÊME optique, donc les échelles
résolues doivent coïncider au millième — contrôle croisé gratuit."""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import math
import os
import sys
import tempfile

import numpy as np

from avastack.catalogues import resoudre
from avastack.catalogues.astap import resoudre_avec_astap
from avastack.images import borner_lineaire, load_image, save_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RA0, DEC0 = 10.68333, 41.26917
CAS = [
    (r"c:\Astro\test\m31_test_solve.fits", 2.625,
     "stack composite (2,6° — échouait avant)"),
    (r"c:\Astro\test\m31_brute_G.fits", 2.645,
     "brute G N.I.N.A. (3856×2180)"),
]
ok = True
for chemin, champ, nom in CAS:
    print(f"=== {nom} ===")
    try:
        img = load_image(chemin)
    except Exception as exc:
        print(f"  image absente ({exc}) — skippée sans échec")
        continue
    h, w = img.shape[:2]
    wcs, info, msg = resoudre(img, RA0, DEC0, champ)
    if wcs is None:
        print(f"  ÉCHEC : {msg}")
        ok = False
        continue
    ra_c, dec_c = wcs.vers_radec(np.array([[(w - 1) / 2.0,
                                            (h - 1) / 2.0]]))
    print(f"  centre ({float(ra_c[0]):.4f}°, {float(dec_c[0]):.4f}°), "
          f"échelle {wcs.echelle_arcsec:.4f}\"/px, angle "
          f"{wcs.angle_deg:+.2f}°, rms {info['rms_px']:.2f} px "
          f"({info['rms_arcsec']:.2f}\") sur {info['n_appariements']} "
          f"étoiles — méthode « {info.get('methode')} »")
    ecart_centre = ((float(ra_c[0]) - RA0) * math.cos(math.radians(DEC0))
                    * 3600.0, (float(dec_c[0]) - DEC0) * 3600.0)
    print(f"  écart du centre aux indices : "
          f"({ecart_centre[0]:+.1f}\", {ecart_centre[1]:+.1f}\")")

    # --- confrontation ASTAP (référence indépendante) -----------------------
    pts = np.array([[0.0, 0.0], [w - 1.0, 0.0], [0.0, h - 1.0],
                    [w - 1.0, h - 1.0], [(w - 1) / 2.0, (h - 1) / 2.0]])
    with tempfile.TemporaryDirectory(prefix="avastack_reel_") as tmp:
        wcs_a, msg_a = resoudre_avec_astap(chemin, RA0, DEC0, rayon_deg=1.0,
                                           fov_deg=champ * h / w,
                                           dossier_sortie=tmp)
        if wcs_a is None and float(img.max()) > 1.0:
            # v2.27.1 : le fichier SUR LE DISQUE peut être antérieur au
            # correctif d'échelle (composite > 1 : ASTAP ne détecte alors
            # aucune étoile — « Only 0 stars found in image », constat réel
            # d'Alain du 22/09/2026). On rejoue sur une copie BORNÉE à [0,1],
            # telle que l'appli l'écrit désormais : c'est cette image-là qui
            # doit être confrontée à notre solveur.
            borne, entete = borner_lineaire(img, {"FILTER": "L"})
            copie = os.path.join(tmp, "composite_borne.fits")
            save_image(copie, borne, entete=entete)
            wcs_a, msg_a = resoudre_avec_astap(copie, RA0, DEC0,
                                               rayon_deg=1.0,
                                               fov_deg=champ * h / w,
                                               dossier_sortie=tmp)
            if wcs_a is not None:
                print("  (fichier du disque antérieur au correctif "
                      "d'échelle : ASTAP résout la version BORNÉE, celle que "
                      "l'appli écrit désormais)")
    if wcs_a is None:
        print(f"  astap_cli : indisponible ({msg_a}) — comparaison sautée")
    else:
        r1, d1 = wcs.vers_radec(pts)
        r2, d2 = wcs_a.vers_radec(pts)
        sep = 3600.0 * np.hypot((r1 - r2) * np.cos(np.radians(d1)), d1 - d2)
        d_ech = abs(wcs.echelle_arcsec - wcs_a.echelle_arcsec)
        print(f"  vs astap_cli : écart max {sep.max():.2f}\" (bords + centre), "
              f"échelle {wcs_a.echelle_arcsec:.4f}\"/px "
              f"(Δ {d_ech:.4f}\"/px)")
        # PIÈGE (22/09/2026) : l'angle du CD brut n'est PAS comparable entre
        # deux WCS de POINT TANGENT différent — la convergence des méridiens
        # fait varier l'angle de ~0,5° entre deux crval distants de 0,6°
        # (notre solveur garde crval = centre indicé, ASTAP le pose sur son
        # pixel de référence). Comparer l'orientation LOCALE au même point
        # du ciel, mesurée par différence finie (2 px).
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        paire = np.array([[cx, cy], [cx + 2.0, cy]])
        rA, dA = wcs.vers_radec(paire)
        rB, dB = wcs_a.vers_radec(paire)
        angA = math.degrees(math.atan2(
            dA[1] - dA[0],
            (rA[1] - rA[0]) * math.cos(math.radians(dA[0]))))
        angB = math.degrees(math.atan2(
            dB[1] - dB[0],
            (rB[1] - rB[0]) * math.cos(math.radians(dB[0]))))
        print(f"  orientation locale au centre : {angA:+.3f}° vs "
              f"{angB:+.3f}° (Δ {abs(angA - angB):.3f}°)")
        if sep.max() > 5.0 or d_ech > 0.01 or abs(angA - angB) > 0.05:
            ok = False
            print("  ÉCHEC : divergence avec la référence ASTAP")
print()
print("BANC RÉEL : TOUT AU VERT" if ok else "BANC RÉEL : ÉCHEC")
sys.exit(0 if ok else 1)
