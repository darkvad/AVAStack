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

from avastack.catalogues import (WcsTan, ObjetCelebre, deduplique_celebres,
                                 score_designation)
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
verifie(0 <= tx and tx + tw <= W and 0 <= ty - th and ty + th <= H,
        f"l'étiquette tient dans les bornes ({tx},{ty},{tw},{th})")
vide = np.zeros((H, W, 3), np.uint8)
rects_v = ann.overlay_objets_celebres(vide, WCS, [])
verifie(rects_v == [] and not vide.any(),
        "liste vide : rien dessiné, image au bit")

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

print("[6] déduplication PARTAGÉE : UNE étiquette par objet (jamais « 224 »)")
doublons = [
    ObjetCelebre(designation="224", aliases=[], type_obj="galaxie",
                 mag_v=3.4, size_arcmin=190.0, ra_deg=RA0, dec_deg=DEC0,
                 healpix8=0),
    ObjetCelebre(designation="NGC 224", aliases=[], type_obj="galaxie",
                 mag_v=3.4, size_arcmin=190.0, ra_deg=RA0, dec_deg=DEC0,
                 healpix8=0),
    ObjetCelebre(designation="M 31", aliases=[], type_obj="galaxie",
                 mag_v=3.4, size_arcmin=190.0, ra_deg=RA0, dec_deg=DEC0,
                 healpix8=0),
    ObjetCelebre(designation="M 32", aliases=[], type_obj="galaxie",
                 mag_v=8.1, size_arcmin=8.0, ra_deg=RA0 + 0.02,
                 dec_deg=DEC0 - 0.01, healpix8=0),
]
reps = deduplique_celebres(doublons, RA0, DEC0)
verifie(len(reps) == 2, f"4 entrées / 2 positions → 2 objets ({len(reps)})")
verifie(reps[0].designation == "M 31" and score_designation("M 31") == 0,
        f"le meilleur nom d'abord : {reps[0].designation!r} (pas « 224 »)")
verifie(score_designation("NGC 224") == 1 and score_designation("224") == 3,
        "score_designation : Messier < NGC/IC < nombre nu")

print("[7] forme mesurée (moments d'inertie) : ellipse orientée, cercle sinon")
blob = np.zeros((200, 200, 3), np.uint8)
cv2.ellipse(blob, (100, 100), (70, 28), 30, 0, 360, 200, -1)
forme = ann._mesure_forme(blob, 100.0, 100.0, 80.0)
verifie(forme is not None
        and abs(((forme[0] - 30.0) + 90.0) % 180.0 - 90.0) < 6.0,
        f"angle retrouvé ≈ 30° (mod 180) : "
        f"{forme[0]:.1f}°" if forme else "pas de mesure")
verifie(forme is not None and 0.30 <= forme[1] <= 0.60,
        f"ratio d'axes ≈ 0,4 : {forme[1]:.2f}" if forme else "pas de mesure")
rond = np.zeros((200, 200, 3), np.uint8)
cv2.circle(rond, (100, 100), 60, 200, -1)
verifie(ann._mesure_forme(rond, 100.0, 100.0, 80.0) is None,
        "objet ROND → None (cercle dessiné, pas d'ellipse)")
faible = np.zeros((200, 200, 3), np.uint8)
faible[98:101, 98:101] = 120
verifie(ann._mesure_forme(faible, 100.0, 100.0, 80.0) is None,
        "signal trop faible/ponctuel → None (repli cercle)")

print("[8] entourage : jaune RGB (plus jamais le cyan BGR), taille réelle")
verifie(abs(ann._rayon_entourage(WCS, obj, H, W) - 180.0) < 1e-6,
        f"plafond 50 % : M31 (190′) borné à "
        f"{ann._rayon_entourage(WCS, obj, H, W):.0f} px sur 360×300")
obj_petit = ObjetCelebre(designation="M32", aliases=[],
                         type_obj="amas_globulaire", mag_v=8.1,
                         size_arcmin=2.0, ra_deg=RA0, dec_deg=DEC0, healpix8=0)
r2 = ann._rayon_entourage(WCS, obj_petit, H, W)
verifie(abs(r2 - 60.0) < 1.5, f"2′ à 1″/px → demi-axe 60 px ({r2:.1f})")
obj_inconnu = ObjetCelebre(designation="X", aliases=[], type_obj="galaxie",
                           mag_v=None, size_arcmin=0.0, ra_deg=RA0,
                           dec_deg=DEC0, healpix8=0)
verifie(ann._rayon_entourage(WCS, obj_inconnu, H, W) == ann.RAYON_CERCLE,
        "taille inconnue → petit cercle par défaut")
toile = np.zeros((H, W, 3), np.uint8)
toile[145:156, 165:196] = 200       # objet allongé HORIZONTAL (11×31 px)
ann.overlay_objets_celebres(toile, WCS, [obj_petit])
n_jaune = int(((toile[:, :, 0] > 200) & (toile[:, :, 1] > 200)
               & (toile[:, :, 2] < 100)).sum())
verifie(n_jaune > 50,
        f"pixels JAUNES (R et G hauts, B bas → RGB) : {n_jaune}")
zone = toile[124:136, 176:186]      # bord SUPÉRIEUR de l'ellipse attendue
n_bord = int(((zone[:, :, 0] > 60) & (zone[:, :, 2] < 120)).sum())
verifie(n_bord > 0,
        f"l'entourage (demi-axe 60 px) est dessiné autour de l'objet "
        f"({n_bord} px sur le bord)")

print("[9] étiquettes : empilement VERTICAL, plus aucun chevauchement")
def _chevauche(a, b):
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]
                or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
pile = []
ts = []
for _i in range(3):
    t = ann._position_etiquette(100.0, 100.0, 360, 300, (60, 10), pile)
    ts.append(t)
    pile.append((t[0], t[1] - 10, 60, 10))
verifie(not _chevauche(pile[0], pile[1]) and not _chevauche(pile[1], pile[2])
        and not _chevauche(pile[0], pile[2]),
        f"3 étiquettes au même point : aucune chevauchement ({ts})")
verifie(ts[1][1] > ts[0][1] and ts[2][1] > ts[1][1],
        "les étiquettes suivantes sont empilées VERTICALEMENT (vers le bas)")

print("[10] lecteur du .dat : types lisibles + désignations préfixées")
from avastack.catalogues.celebres import (TYPE_CODE_VERS_NOM,
                                          _designations_lisibles)
verifie(TYPE_CODE_VERS_NOM[0] == "galaxie"
        and TYPE_CODE_VERS_NOM[1] == "nebuleuse_diffuse"
        and TYPE_CODE_VERS_NOM[1] in ann.TYPE_ICON,
        "table inverse de type EN FRANÇAIS, cohérente avec TYPE_ICON (plus de « ? »)")
d, al = _designations_lisibles("221", ["M  32"])
verifie(d == "M 32", f"« 221 » + alias « M  32 » → {d!r} (retour Alain)")
d, al = _designations_lisibles("206", ["206"])
verifie(d == "NGC 206",
        f"nombre nu sans alias préfixé → {d!r} (NGC 206, plus « 206 (?) »)")
d, al = _designations_lisibles("224", ["Great Nebula in "])
verifie(d == "NGC 224",
        f"alias non préfixé ignoré → {d!r} (jamais « Great Nebula in »)")
d, al = _designations_lisibles("M  31", [])
verifie(d == "M 31", f"espaces compactés : {d!r}")
d, al = _designations_lisibles("NGC224", [])
verifie(d == "NGC224", f"déjà préfixé (format nouveau) : intact {d!r}")

print("[11] forme mesurée À L'ÉCHELLE de l'objet (crop pleine étendue)")
grande_img = np.zeros((600, 900, 3), np.uint8)
cv2.ellipse(grande_img, (450, 300), (350, 140), 0, 0, 360, 200, -1)
fg = ann._mesure_forme(grande_img, 450.0, 300.0, 350.0)
verifie(fg is not None
        and abs(((fg[0] - 0.0) + 90.0) % 180.0 - 90.0) < 6.0,
        f"angle de l'objet géant retrouvé ≈ 0° : "
        f"{fg[0]:.1f}°" if fg else "pas de mesure")
verifie(fg is not None and 0.30 <= fg[1] <= 0.60,
        f"ratio de l'objet géant ≈ 0,40 (crop INTER_AREA pleine étendue) : "
        f"{fg[1]:.2f}" if fg else "pas de mesure")

print("[12] échelle de police : textes à taille d'écran constante en pleine résolution")
toile1 = np.zeros((H, W, 3), np.uint8)
toile1[145:156, 165:196] = 200
r1 = ann.overlay_objets_celebres(toile1, WCS, [obj_petit], echelle_police=1.0)
toile3 = np.zeros((H, W, 3), np.uint8)
toile3[145:156, 165:196] = 200
r3 = ann.overlay_objets_celebres(toile3, WCS, [obj_petit], echelle_police=3.0)
verifie(bool(r1) and bool(r3) and r3[0][3] > 2.0 * r1[0][3],
        f"échelle 3 → étiquette ~3× plus haute "
        f"(th {r1[0][3]} → {r3[0][3]} px)")
rj = ann._rayon_entourage(WCS, obj_inconnu, H, W, echelle_police=4.0)
verifie(abs(rj - 4.0 * ann.RAYON_CERCLE) < 1e-6,
        f"taille inconnue : le petit cercle suit l'échelle ({rj:.0f} px)")

print("[13] détection de visibilité (_detecte_visibilite, v2.56.0)")
fond40 = np.full((H, W, 3), 40, np.uint8)
blob = fond40.copy()
cv2.circle(blob, (180, 150), 60, 200, -1)      # objet nettement visible
verifie(ann._detecte_visibilite(blob, 180.0, 150.0, 60.0),
        "objet brillant sur fond plat → VISIBLE")
verifie(not ann._detecte_visibilite(fond40, 180.0, 150.0, 60.0),
        "fond plat (aucun objet) → PAS visible (pas de faux positif sur le grain)")
faible = fond40.copy()
cv2.circle(faible, (180, 150), 60, 45, -1)     # +5 niveaux : le cas NGC 206
verifie(not ann._detecte_visibilite(faible, 180.0, 150.0, 60.0),
        "objet +5 niveaux (NGC 206 mesuré : +5,2) → PAS visible")
etoile = fond40.copy()
etoile[150, 180] = 255                          # une étoile ponctuelle ne
verifie(not ann._detecte_visibilite(etoile, 180.0, 150.0, 60.0),
        "étoile ponctuelle (lissage) → PAS un objet détecté")
verifie(ann._detecte_visibilite(fond40, 180.0, 150.0, 6.0),
        "rayon < seuil de mesure → on ne tranche pas (True conservateur)")
verifie(ann._detecte_visibilite(fond40, 180.0, 150.0, 400.0),
        "rayon > plafond de mesure → on ne tranche pas (True conservateur)")

print("[14] overlay `seulement_visibles` : étiquette TOUJOURS, entourage si détecté")
oi = ObjetCelebre(designation="NGC 206", aliases=[], type_obj="amas_ouvert",
                  mag_v=None, size_arcmin=0.0, ra_deg=RA0, dec_deg=DEC0,
                  healpix8=0)
toile_v = np.full((H, W, 3), 40, np.uint8)
toile_c = np.full((H, W, 3), 40, np.uint8)
rv = ann.overlay_objets_celebres(toile_v, WCS, [oi], seulement_visibles=True)
rc = ann.overlay_objets_celebres(toile_c, WCS, [oi], seulement_visibles=False)
n_v = int((toile_v != 40).any(axis=2).sum())
n_c = int((toile_c != 40).any(axis=2).sum())
verifie(bool(rv) and n_v > 0,
        "objet invisible : l'ÉTIQUETTE reste dessinée")
verifie(n_c > n_v,
        f"objet invisible : le cercle n'est plus dessiné "
        f"({n_v} px avec la case, {n_c} sans)")
obj_vis = ObjetCelebre(designation="M 110", aliases=[], type_obj="galaxie",
                       mag_v=8.1, size_arcmin=1.0, ra_deg=RA0, dec_deg=DEC0,
                       healpix8=0)
toile_o = np.full((H, W, 3), 40, np.uint8)
cv2.circle(toile_o, (180, 150), 30, 200, -1)   # le cœur brillant de M 110
ro = ann.overlay_objets_celebres(toile_o, WCS, [obj_vis],
                                 seulement_visibles=True)
n_o = int((toile_o != 40).any(axis=2).sum())
verifie(n_o > n_v,
        f"objet détecté : le cercle est DESSINÉ ({n_o} px > {n_v} px étiquette seule)")

print()
print("BANC TERMINÉ : " + ("TOUT AU VERT" if ok else "ÉCHEC — corriger avant de continuer"))
sys.exit(0 if ok else 1)
