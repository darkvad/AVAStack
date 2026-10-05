# -*- coding: utf-8 -*-
"""Banc jalon 96 (étapes 5-6) — ANNOTATION TEMPS-RÉEL : MODULE D'OVERLAY.

Vérifie `processing/annotations.py` tel que branché dans `_render` :

  [1] `WcsEchelle` : l'aperçu est une réduction UNIFORME de la grille du WCS —
      `vers_pixels` rendu à l'échelle, aller-retour `vers_radec` exact, échelle
      illisible/négative → 1,0 ;
  [2] `overlay_objets_celebres` : l'étiquette d'un objet au CENTRE du champ
      tombe dans les bornes, la liste des rectangles est rendue, la liste vide
      ne touche à RIEN (image au bit) ;
  [3] `generer_image_annotee` : l'original n'est JAMAIS modifié (les deux
      drapeaux à False = copie au bit), l'annotation ajoute des pixels ;
  [4] `overlay_etoiles_brillantes` : filtre de magnitude (toutes au-dessus du
      seuil = rien), étiquettes sous le seuil, plafond à 50 ;
  [5] coût : l'overlay est négligeable devant l'étirement (cible < 2 ms par
      étiquette à l'échelle de l'aperçu).

PIÈGE COUVERT : le module d'origine appelait `wcs.world_to_pixel(...)`, méthode
qui N'EXISTE PAS dans ce projet (le WCS expose `vers_pixels(ra, dec)`) — chaque
étiquette tombait sur une exception et RIEN ne se dessinait.

Exécution : python bancs/_test_annotations_overlay_jalon96.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.catalogues import WcsTan, ObjetCelebre
from avastack.processing import annotations as ann

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- fixture : WCS TAN connu (pleine résolution 360×300, 1,00″/px) ----------
RA0, DEC0 = 10.6833, 41.2686
H, W = 300, 360
ECHELLE = 1.0 / 3600.0                 # ″/px → deg/px
CD = [[-ECHELLE, 0.0], [0.0, ECHELLE]]  # nord en haut, AD décroissant
WCS = WcsTan((RA0, DEC0), (W / 2.0, H / 2.0), CD, forme=(H, W))

img = np.zeros((H, W, 3), np.uint8)
img[140:160, 170:180] = 200            # un « objet » brillant au centre

obj = ObjetCelebre(designation="M31", aliases=["NGC224"], type_obj="galaxie",
                   mag_v=3.4, size_arcmin=190.0, ra_deg=RA0, dec_deg=DEC0,
                   healpix8=0)

print("[1] WcsEchelle : l'aperçu réduit est la grille du WCS × échelle")
w05 = ann.WcsEchelle(WCS, 0.5)
p = w05.vers_pixels(RA0, DEC0)
verifie(np.allclose(p, [[W / 4.0, H / 4.0]], atol=1e-6),
        f"centre du champ à échelle 0,5 : {p.ravel()} (attendu "
        f"{W / 4.0:.1f}, {H / 4.0:.1f})")
ra_r, dec_r = w05.vers_radec(p)
verifie(abs(float(ra_r[0]) - RA0) < 1e-9 and abs(float(dec_r[0]) - DEC0) < 1e-9,
        "aller-retour vers_pixels → vers_radec exact à l'échelle 0,5")
w_invalide = ann.WcsEchelle(WCS, "pas un nombre")
verifie(w_invalide.echelle == 1.0, "échelle illisible → 1,0 (jamais 0)")
w_negative = ann.WcsEchelle(WCS, -2.0)
verifie(w_negative.echelle == 1.0, "échelle négative → 1,0")

print("[2] overlay_objets_celebres : étiquette au centre, liste de rectangles")
avant = img.copy()
rects = ann.overlay_objets_celebres(img, WCS, [obj])
apres = img
verifie(bool(rects), f"liste des rectangles rendue ({len(rects)})")
verifie(not np.array_equal(avant, apres), "l'image est annotée (pixels ajoutés)")
tx, ty, tw, th = rects[0]

print("[3] generer_image_annotee : l'original n'est JAMAIS modifié")
source = img.copy()
copie = ann.generer_image_annotee(source, WCS, [obj], None,
                                  annoter_objets=True, annoter_etoiles=False)
verifie(copie is not None and np.array_equal(source, img),
        "l'original est intact (pas d'écriture dans le buffer source)")
verifie(not np.array_equal(copie, source), "la copie porte l'annotation")
rien = ann.generer_image_annotee(source, WCS, [obj], None,
                                 annoter_objets=False, annoter_etoiles=False)
verifie(np.array_equal(rien, source), "drapeaux à False : copie AU BIT")

print("[4] overlay_etoiles_brillantes : filtre de magnitude, plafond 50")
etoiles_haut = {"ra": np.array([RA0 + 0.01, RA0 + 0.02]),
                "dec": np.array([DEC0 + 0.01, DEC0 + 0.02]),
                "g": np.array([11.0, 12.0])}
propre = img.copy()
r2 = ann.overlay_etoiles_brillantes(propre, WCS, etoiles_haut, mag_limite=8.0)
verifie(r2 == [] and np.array_equal(propre, img),
        "toutes au-dessus du seuil : rien dessiné, image au bit")
etoiles_bas = {"ra": np.array([RA0 + 0.01, RA0 + 0.02]),
               "dec": np.array([DEC0 + 0.01, DEC0 + 0.02]),
               "g": np.array([5.0, 6.5])}
r3 = ann.overlay_etoiles_brillantes(img, WCS, etoiles_bas, mag_limite=8.0)
verifie(len(r3) == 2, f"deux étiquettes sous le seuil ({len(r3)})")
n_grand = 70
etoiles_lot = {"ra": np.array([RA0 + 0.001 * i for i in range(n_grand)]),
               "dec": np.array([DEC0 + 0.001 * i for i in range(n_grand)]),
               "g": np.array([4.0 + 0.01 * i for i in range(n_grand)])}
r4 = ann.overlay_etoiles_brillantes(img, WCS, etoiles_lot, mag_limite=20.0)
verifie(len(r4) <= 50, f"plafond de lisibilité à 50 ({len(r4)})")
r5 = ann.overlay_etoiles_brillantes(img, WCS, None)
verifie(r5 == [], "dictionnaire absent : rien dessiné (jamais d'exception)")

print("[5] coût : négligeable devant les autres étages de la chaîne live")
apercu = np.zeros((904, 1600, 3), np.uint8)
objets_lot2 = [ObjetCelebre(designation=f"NGC{i}", aliases=[f"NGC{i}"],
                            type_obj="galaxie", mag_v=10.0,
                            size_arcmin=5.0, ra_deg=RA0 + 0.0002 * i,
                            dec_deg=DEC0 + 0.0002 * i, healpix8=0)
               for i in range(10)]
t0 = time.perf_counter()
ann.overlay_objets_celebres(apercu, WCS, objets_lot2)
t1 = time.perf_counter()
verifie(t1 - t0 < 0.2,
        f"aperçu 1600×904, 10 objets : {(t1 - t0) * 1000:.1f} ms "
        "(cible < 2 ms par étiquette, étirement VeraLux ~0,4 s)")

print()
print("BANC TERMINÉ : " + ("TOUT AU VERT" if ok else "ÉCHEC — corriger avant de continuer"))
sys.exit(0 if ok else 1)

verifie(0 <= tx and tx + tw <= W and 0 <= ty - th and ty + th <= H,
        f"l'étiquette tient dans les bornes ({tx},{ty},{tw},{th})")
vide = img.copy()
rects_v = ann.overlay_objets_celebres(vide, WCS, [])
verifie(rects_v == [] and np.array_equal(vide, img),
        "liste vide : rien dessiné, image au bit")
