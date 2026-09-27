# -*- coding: utf-8 -*-
"""Banc du jalon 56 (étape 4) : photométrie — zéro-point instrumental par bande.

Vérifie la chaîne complète de la photométrie SPCC-relative décidée par Alain :
étoiles détectées → appariement MUTUEL au catalogue Gaia via le WCS (étapes
2-3) → zéro-point par bande → gains relatifs (matière de l'étape 5).

[1] flux_ouverture : flux d'une étoile synthétique retrouvé, fond local retiré
    (gradient linéaire), NaN hors image ;
[2] etoiles_image : détection + rejets propres (image sans étoile, trop petite) ;
[3] apparier : appariement MUTUEL — leurres rejetés, tolérance en PIXELS
    respectée (leurre à 5 px non apparié) ;
[4] zero_point : exactitude (flux × 2 → zéro-point +0,7526 mag), rejet robuste
    d'une aberration, refus sous le minimum d'étoiles ;
[5] gains_depuis_zp : référence = zéro-point MÉDIAN, réciprocité, bornes ;
[6] Photometrie.mesurer bout en bout sur 3 bandes synthétiques dont une
    ATTÉNUÉE ×0,5 → le gain mesuré doit valoir ×2 (vérité analytique) ;
[7] échecs PROPRES : catalogue indisponible, WCS absent, canaux vides ;
[8] GAIA RÉEL (si le catalogue Siril est présent et la brute G de M31 aussi) :
    appariement réel + dispersion des magnitudes résiduelles — la preuve que la
    chaîne fonctionne sur une VRAIE image, sans aucun spectre.

Exécution : python bancs/_test_photometrie_jalon56.py
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
import threading
import time
import tkinter as tk

import numpy as np

from avastack.catalogues import WcsTan, resoudre
from avastack.images import load_image
from avastack.processing import photometrie as ph

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ----------------------------------------------------------- utilitaires
FORME = (400, 500)                     # (H, W)
ECH = 2.0 / 3600.0                     # 2,0 ″/px
CRVAL = (10.700, 41.300)
W_VRAI = WcsTan(CRVAL, ((FORME[1] - 1) / 2.0, (FORME[0] - 1) / 2.0),
                [[-ECH, 0.0], [0.0, ECH]], forme=FORME)


def rendu(forme, xy, flux, sigma=1.2, fond=0.02, gradient=0.0, graine=3):
    """Image synthétique : gaussiennes de flux CONNU (+ fond, + gradient)."""
    rng = np.random.default_rng(graine)
    img = np.full(forme, float(fond), np.float32)
    if gradient:
        yy, xx = np.mgrid[0:forme[0], 0:forme[1]]
        img += (gradient * xx / float(forme[1])).astype(np.float32)
    img += rng.normal(0.0, 0.0015, forme).astype(np.float32)
    h, w = forme
    r = int(5 * sigma)
    for (x, y), f in zip(np.asarray(xy, float), np.asarray(flux, float)):
        ix, iy = int(round(x)), int(round(y))
        if ix - r < 0 or iy - r < 0 or ix + r >= w or iy + r >= h:
            continue
        xs = np.arange(ix - r, ix + r + 1, dtype=np.float64)
        ys = np.arange(iy - r, iy + r + 1, dtype=np.float64)
        r2 = (xs[None, :] - x) ** 2 + (ys[:, None] - y) ** 2
        # `f` = flux TOTAL de l'étoile : l'amplitude du pic vaut f/(2πσ²) — la
        # convention du projet (magnitude ↔ flux) porte sur le flux intégré.
        img[iy - r:iy + r + 1, ix - r:ix + r + 1] += (
            f / (2 * np.pi * sigma * sigma) * np.exp(
                -r2 / (2 * sigma * sigma))).astype(np.float32)
    return img


def catalogue_factice(pos, flux, zp=20.0, leurres=()):
    """Catalogue au format Gaia ({"ra","dec","g"}) dérivé d'une vérité connue :
    mag = zp − 2,5·log10(flux). `leurres` = positions PIXEL supplémentaires
    (aucune étoile correspondante dans l'image)."""
    pos = np.asarray(pos, dtype=np.float64)
    flux = np.asarray(flux, dtype=np.float64)
    ra, dec = W_VRAI.vers_radec(pos)
    g = zp - 2.5 * np.log10(flux)
    if len(leurres):
        ra2, dec2 = W_VRAI.vers_radec(np.asarray(leurres, dtype=np.float64))
        ra = np.concatenate([ra, np.ravel(ra2)])
        dec = np.concatenate([dec, np.ravel(dec2)])
        g = np.concatenate([g, np.full(len(ra2), 16.0)])
    return {"ra": np.asarray(ra), "dec": np.asarray(dec), "g": np.asarray(g)}


# ==================================================== [1] flux par ouverture
print("[1] flux_ouverture : flux retrouvé, fond local retiré, bord → NaN")
une = rendu(FORME, [(250.0, 200.0)], [1000.0], fond=0.02)
f = ph.flux_ouverture(une, [(250.0, 200.0)], rayon=5.0, anneau=(6.0, 9.0))
frac = float(f[0]) / 1000.0                  # fraction du flux dans l'ouverture
verifie(0.85 < frac <= 1.02,
        f"flux d'une étoile connue : {frac * 100:.1f} % retrouvé "
        f"(ouverture finie, gaussienne σ=1,2 px)")
grad = rendu(FORME, [(120.0, 90.0)], [1000.0], fond=0.02, gradient=0.5)
f2 = ph.flux_ouverture(grad, [(120.0, 90.0)], rayon=5.0, anneau=(6.0, 9.0))
verifie(abs(float(f2[0]) - float(f[0])) < 0.06 * float(f[0]),
        f"fond local : un gradient ×25 du fond ne change pas le flux "
        f"({float(f2[0]):.1f} vs {float(f[0]):.1f})")
f3 = ph.flux_ouverture(une, [(2.0, 2.0)], rayon=5.0, anneau=(6.0, 9.0))
verifie(not np.isfinite(f3[0]), "étoile au bord : flux NaN (jamais tronqué)")

# ======================================================= [2] etoiles_image
print("[2] etoiles_image : détection + rejets propres")
rng = np.random.default_rng(11)
pos = np.column_stack([rng.uniform(40, FORME[1] - 40, 60),
                       rng.uniform(40, FORME[0] - 40, 60)])
flux = 10.0 ** (0.4 * (18.0 - np.linspace(11.0, 17.0, 60)))
img = rendu(FORME, pos, flux, graine=7)
pos_i, flux_i, msg = ph.etoiles_image(img)
verifie(len(pos_i) >= 40,
        f"{len(pos_i)} étoiles détectées sur 60 posées ({msg or 'ok'})")
plat = np.full(FORME, 0.02, np.float32)
p_v, f_v, msg_v = ph.etoiles_image(plat)
verifie(len(p_v) == 0 and bool(msg_v), f"image constante → rien (« {msg_v} »)")
p_p, f_p, msg_p = ph.etoiles_image(np.zeros((16, 16), np.float32))
verifie(len(p_p) == 0 and "trop petite" in msg_p, f"image minuscule (« {msg_p} »)")

# ============================================================ [3] apparier
print("[3] apparier : appariement MUTUEL, tolérance en pixels")
cat = catalogue_factice(pos, flux, zp=20.0)
ap, msg_ap = ph.apparier(pos, W_VRAI, cat)
verifie(len(ap["ia"]) == len(pos) and float(np.max(ap["d_px"])) < 0.01,
        f"catalogue exact : {len(ap['ia'])}/{len(pos)} appariés "
        f"({msg_ap})")
leurres = [(pos[0][0] + 6.0, pos[0][1] + 6.0), (pos[1][0] - 20.0,
                                                pos[1][1])]
cat_l = catalogue_factice(pos, flux, zp=20.0, leurres=leurres)
ap_l, msg_l = ph.apparier(pos, W_VRAI, cat_l)
i0 = int(np.where(ap_l["ia"] == 0)[0][0]) if len(ap_l["ia"]) else -1
verifie(len(ap_l["ia"]) == len(pos) and i0 >= 0
        and float(ap_l["d_px"][i0]) < 0.01,
        f"leurres CATALOGUE rejetés (appariement mutuel) : "
        f"{len(ap_l['ia'])} appariés, étoile 0 non volée par un leurre à 6 px")
ap_f, msg_f = ph.apparier(np.array([[10.0, 10.0]]), W_VRAI, cat)
verifie(len(ap_f["ia"]) == 0 and bool(msg_f),
        f"étoile image hors catalogue → aucun appariement (« {msg_f[:44]}… »)")
ap_n, msg_n = ph.apparier(pos, None, cat)
verifie(len(ap_n["ia"]) == 0 and "WCS" in msg_n, f"WCS absent (« {msg_n} »)")

# ========================================================== [4] zero_point
print("[4] zero_point : exactitude, rejet robuste, minimum d'étoiles")
mag = 20.0 - 2.5 * np.log10(flux)
zp, rms, n, msg_zp = ph.zero_point(mag, flux)
verifie(zp is not None and abs(zp - 20.0) < 1e-6 and n == len(flux),
        f"zéro-point exact retrouvé : {zp:.6f} (attendu 20,000000), rms "
        f"{rms:.4f} mag")
zp2, _r2, _n2, _m2 = ph.zero_point(mag, flux * 2.0)
verifie(abs((zp2 - zp) - 2.5 * np.log10(2.0)) < 1e-6,
        f"flux × 2 → zéro-point +{zp2 - zp:.4f} mag "
        f"(attendu +{2.5 * np.log10(2.0):.4f}) — échelle logarithmique juste")
mag_sale = mag.copy()
flux_sale = flux.copy()
mag_sale[5] += 6.0                            # aberration franche
zp3, _r3, n3, _m3 = ph.zero_point(mag_sale, flux_sale)
verifie(abs(zp3 - 20.0) < 0.01 and n3 < len(flux),
        f"aberration à +6 mag REJETÉE ({n3}/{len(flux)} gardées, "
        f"zéro-point {zp3:.4f})")
zp4, r4, n4, msg4 = ph.zero_point(mag[:5], flux[:5])
verifie(zp4 is None and "trop peu" in msg4, f"trop peu d'étoiles (« {msg4} »)")

# ==================================================== [5] gains depuis les ZP
print("[5] gains_depuis_zp : référence médiane, réciprocité, bornes")
g, msg_g = ph.gains_depuis_zp(
    {"R": 21.0, "G": 21.0, "B": 21.0 - 2.5 * float(np.log10(2.0))})
verifie(abs(g.get("R", 0) - 1.0) < 1e-9 and abs(g.get("G", 0) - 1.0) < 1e-9
        and abs(g.get("B", 0) - 2.0) < 1e-9,
        f"zéro-points (21, 21, 21 − 0,7526) → gains R {g.get('R'):.4f}, G "
        f"{g.get('G'):.4f}, B {g.get('B'):.4f} (attendu 1, 1, 2)")
g2, _msg2 = ph.gains_depuis_zp({"R": 21.0, "B": 21.0})
verifie(g2.get("R") == 1.0 and g2.get("B") == 1.0,
        "deux bandes identiques → gains 1,0 (aucune correction inventée)")
g3, msg3 = ph.gains_depuis_zp({"R": 21.0, "B": 10.0})
verifie("B" not in g3 and "hors bornes" in msg3,
        f"gain hors bornes IGNORÉ et signalé (« {msg3[:48]}… »)")
g4, msg4b = ph.gains_depuis_zp({})
verifie(g4 == {} and bool(msg4b), f"aucun zéro-point (« {msg4b} »)")

# ================================================= [6] mesure bout en bout
print("[6] Photometrie.mesurer : 3 bandes, la bande B ATTÉNUÉE ×0,5")
imgR = rendu(FORME, pos, flux, graine=21)
imgG = rendu(FORME, pos, flux, graine=22)
imgB = rendu(FORME, pos, flux * 0.5, graine=23)
cat_vrai = catalogue_factice(pos, flux, zp=20.0)
pho = ph.Photometrie(
    catalogue=lambda w, f: (cat_vrai, "catalogue factice (banc)"))
res, msg = pho.mesurer({"R": imgR, "G": imgG, "B": imgB}, W_VRAI)
verifie(res is not None and pho.valide, f"mesure réussie ({msg})")
verifie(pho.n_paires >= 40,
        f"{pho.n_paires} appariements au total sur 3 bandes")
dzb = pho.zp["B"] - pho.zp["R"]
attendu = 2.5 * np.log10(0.5)                 # −0,7526 mag
verifie(abs(dzb - attendu) < 0.02,
        f"ZP(B) − ZP(R) = {dzb:+.4f} mag (attendu {attendu:+.4f}) — "
        f"l'atténuation est bien MESURÉE")
verifie(abs(pho.gains["B"] - 2.0) < 0.06
        and abs(pho.gains["R"] - 1.0) < 0.01
        and abs(pho.gains.get("G", 0.0) - 1.0) < 0.01,
        f"gains relatifs : R ×{pho.gains['R']:.4f}, G "
        f"×{pho.gains.get('G', float('nan')):.4f}, B ×{pho.gains['B']:.4f} "
        f"(attendu 1 / 1 / 2 — le bruit des bandes R/G diffère un peu)")
verifie(pho.bandes["R"]["rms_mag"] < 0.08,
        f"dispersion du zéro-point R : {pho.bandes['R']['rms_mag']:.4f} mag "
        f"(bruit synthétique + ouverture discrète)")
verifie("Photométrie" in pho.texte_resume()
        and "ZP" in pho.texte_resume()
        and "appariements" in pho.texte_resume(),
        f"ligne d'état lisible (« {pho.texte_resume()[:70]}… »)")

# ======================================================== [7] échecs propres
print("[7] échecs PROPRES : catalogue absent, WCS absent, canaux vides")
pho2 = ph.Photometrie(catalogue=lambda w, f: ({}, "catalogue absent (banc)"))
r_2, m_2 = pho2.mesurer({"R": imgR}, W_VRAI)
verifie(r_2 is None and "catalogue" in m_2, f"catalogue absent (« {m_2} »)")
pho3 = ph.Photometrie(catalogue=lambda w, f: (cat_vrai, "ok"))
r_3, m_3 = pho3.mesurer({"R": imgR}, None)
verifie(r_3 is None and "WCS" in m_3, f"WCS absent (« {m_3} »)")
r_4, m_4 = pho3.mesurer({}, W_VRAI)
verifie(r_4 is None and "canal" in m_4, f"canaux vides (« {m_4} »)")
r_5, m_5 = pho3.mesurer({"R": np.full(FORME, 0.02, np.float32)}, W_VRAI)
verifie(r_5 is None and "aucune bande" in m_5,
        f"image sans étoile (« {m_5[:56]}… »)")
verifie(pho3.texte_resume() == "",
        "aucune mesure → ligne d'état VIDE (rien d'inventé)")

# ============================================== [8] GAIA RÉEL (si présent)
print("[8] GAIA RÉEL : appariement sur la brute G de M31 (si présente)")
_IMG = r"c:\Astro\test\m31_brute_G.fits"
RA0, DEC0, CHAMP = 10.68333, 41.26917, 2.645
if not os.path.isfile(_IMG):
    print("  (image de test absente : section réelle sautée sans échec)")
else:
    img_r = None
    try:
        img_r = load_image(_IMG)
    except Exception as exc:
        print(f"  (lecture impossible : {exc}) — sauté")
    if img_r is not None:
        wcs_r, info_r, msg_r = resoudre(img_r, RA0, DEC0, CHAMP)
        if wcs_r is None:
            print(f"  solve interne indisponible ({msg_r}) — sauté")
        else:
            pho_r = ph.Photometrie()
            res_r, msg_pr = pho_r.mesurer({"G": img_r}, wcs_r)
            if res_r is None:
                print(f"  photométrie : {msg_pr} — sauté (catalogue absent ?)")
            else:
                d = pho_r.bandes["G"]
                verifie(d["n"] >= 20 and d["d_px"] < 1.5,
                        f"{d['n']} appariements Gaia réels (médiane "
                        f"{d['d_px']:.2f} px)")
                verifie(d["rms_mag"] < 0.5,
                        f"magnitudes résiduelles : dispersion "
                        f"{d['rms_mag']:.3f} mag — zéro-point {d['zp']:.3f} "
                        f"(G {d['mag_min']:.1f} → {d['mag_max']:.1f})")

# ============ [9] worker RÉEL : canaux du stacker, WCS du cadre, ligne d'état
print("[9] worker RÉEL : la mesure arrive dans la ligne d'état dédiée")
import tkinter as tk                                  # noqa: E402 (banc linéaire)

import avastack.ui.app as ui                          # noqa: E402
from avastack.processing import astrometrie as astro_mod   # noqa: E402
from avastack.processing.stacking import LiveStacker  # noqa: E402

ui.CONFIG = {}                              # bac à sable config (cf. pièges)
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
CHAMP_DEG = FORME[1] * ECH
app = ui.App(root)
app.var_astro.set(True)
app.var_astro_ra.set(f"{CRVAL[0]:.6f}")
app.var_astro_dec.set(f"{CRVAL[1]:+.6f}")
app.var_astro_champ.set(f"{CHAMP_DEG:.5f}")
app.suivi_astro = astro_mod.SuiviAstrometrie(
    solveur=lambda *a, **k: (
        W_VRAI, {"n_etoiles_img": 50, "n_etoiles_cat": 60,
                 "n_appariements": 45, "rms_px": 0.4, "rms_arcsec": 0.8,
                 "echelle_arcsec_px": 2.0, "angle_deg": 0.0,
                 "methode": "triangles"}, ""))
app._on_astro()
app.photometrie = ph.Photometrie(
    catalogue=lambda w, f: (cat_vrai, "catalogue factice (banc)"))
app.var_photo.set(True)
app._on_photo()
st = LiveStacker(FORME, k=None, method="kappa", window=8)
for _ in range(4):
    st.add(imgG)
st.note_alignement(np.eye(2, 3))          # cadre d'intersection réel
app.stacker = st
app._astro_tour(st)                       # astrométrie (solveur factice)
verifie(app.suivi_astro.resolu, "astrométrie résolue par le worker (factice)")
app._photo_tour(st)
verifie(app.photometrie.valide and app.photometrie.n_paires >= 20,
        f"mesure déclenchée par le worker : {app.photometrie.n_paires} "
        f"appariements sur la bande L")
verifie("Photométrie" in app.photo_info and "ZP" in app.photo_info
        and app.photo_couleur == "#1d7f1d",
        f"ligne d'état alimentée (« {app.photo_info[:54]}… »)")

# Sans WCS résolu : AUCUNE mesure (le WCS est le lien image ↔ catalogue).
app2 = ui.App(root)
app2.photometrie = ph.Photometrie()
app2.var_photo.set(True)
app2._on_photo()
st2 = LiveStacker(FORME, k=None, method="kappa", window=8)
for _ in range(4):
    st2.add(imgG)
st2.note_alignement(np.eye(2, 3))
app2.stacker = st2
app2._photo_tour(st2)
verifie(not app2.photometrie.valide and app2._photo_essais == 0,
        "sans astrométrie résolue : aucune mesure tentée (WCS requis)")

# Le catalogue est extrait dans le champ du CADRE : même grille que les canaux.
capture = {}


def cat_capture(w, f):
    capture["forme"] = tuple(f)
    capture["wcs"] = w
    return cat_vrai, "catalogue factice (banc)"


app3 = ui.App(root)
app3.photometrie = ph.Photometrie(catalogue=cat_capture)
app3.var_photo.set(True)
app3._on_photo()
app3.suivi_astro.adopter(W_VRAI, FORME)   # WCS de la grille COMPLÈTE d'abord
st3 = LiveStacker(FORME, k=None, method="kappa", window=8)
for _ in range(4):
    st3.add(imgG)
st3.note_alignement(np.eye(2, 3))
app3.stacker = st3
app3._photo_tour(st3)
attendu_forme = (st3.cadre[2] - st3.cadre[0], st3.cadre[3] - st3.cadre[1])
verifie(capture.get("forme") == attendu_forme and capture.get("wcs") is not None,
        f"canaux et WCS sur la MÊME grille — celle du cadre {capture.get('forme')}")
root.destroy()

# ============== [10] étape 5 : gains photométriques appliqués (OPT-IN)
print("[10] étape 5 : gains par rôle → canaux du composite, défaut INTACT")
from avastack.processing.composition import CompositeStacker   # noqa: E402

rng2 = np.random.default_rng(31)
ch_a = (0.05 + rng2.normal(0, 0.01, (60, 80))).astype(np.float32)
ch_b = (0.05 + rng2.normal(0, 0.01, (60, 80))).astype(np.float32)
sc = CompositeStacker("HOO", k=None)
sc.add(ch_a, role="Ha")
sc.add(ch_b, role="O3")
sc.note_alignement(np.eye(2, 3))
ref = sc.mean()
verifie(sc.gains_effectifs() == {} and np.allclose(sc.mean(), ref, atol=0),
        "case opt-in DÉCOCHÉE (gains_roles vide) : aucun gain, image identique")
sc.gains_roles = {"Ha": 2.0, "O3": 0.5}
ge = sc.gains_effectifs()
verifie(abs(ge.get("R", 0) - 2.0) < 1e-9 and abs(ge.get("G", 0) - 0.5) < 1e-9
        and abs(ge.get("B", 0) - 0.5) < 1e-9,
        f"conversion RÔLE → CANAL : R ×{ge.get('R')}, G ×{ge.get('G')}, "
        f"B ×{ge.get('B')} (HOO : Ha→R, O3→G ET B)")
apres = sc.mean()
r_ = float(np.median(apres[..., 0] / np.maximum(ref[..., 0], 1e-9)))
g_ = float(np.median(apres[..., 1] / np.maximum(ref[..., 1], 1e-9)))
b_ = float(np.median(apres[..., 2] / np.maximum(ref[..., 2], 1e-9)))
verifie(abs(r_ - 2.0) < 0.02 and abs(g_ - 0.5) < 0.02 and abs(b_ - 0.5) < 0.02,
        f"le COMPOSITE suit : R ×{r_:.3f}, G ×{g_:.3f}, B ×{b_:.3f} "
        f"(attendu 2 / 0,5 / 0,5)")
verifie(r_ != 1.0,
        "l'effet est VISIBLE — un facteur appliqué AVANT la normalisation par "
        "canal aurait été absorbé (le piège corrigé)")
verifie(np.allclose(sc.moyennes(recadre=False)["Ha"], ch_a, rtol=0, atol=1e-6),
        "les COUCHES restent BRUTES (contrat jalon 54 : le solveur les re-compose)")
sc.gains_roles = {}
verifie(np.allclose(sc.mean(), ref, rtol=0, atol=1e-7),
        "gains_roles vidé → composite de nouveau identique au défaut")
sc2 = CompositeStacker("Mono", k=None)
sc2.add(ch_a, role="L")
sc2.note_alignement(np.eye(2, 3))
sc2.gains_roles = {"L": 1.5}
verifie(sc2.gains_effectifs() == {},
        "composition Mono : gains_roles sans effet (aucun canal R/G/B)")

# Worker : c'est la CASE OPT-IN qui écrit les gains dans le stacker.
root10 = tk.Tk()
root10.withdraw()
app10 = ui.App(root10)


class CameraMuette10:
    """Caméra factice : aucune frame — la boucle du worker fait tout de même sa
    passe de resynchronisation des réglages (jalon 55), c'est ce qu'on teste."""
    name = "muette"

    def read(self):
        return None


app10.camera = CameraMuette10()
app10._mode_compo = True
sc3 = CompositeStacker("HOO", k=None)
sc3.add(ch_a, role="Ha")
sc3.add(ch_b, role="O3")
sc3.note_alignement(np.eye(2, 3))
app10.stacker = sc3
app10.photometrie = ph.Photometrie()
app10.photometrie.gains = {"Ha": 2.0, "O3": 0.5}
app10.var_photo_gains.set(False)
app10._on_photo_gains()
app10.running = True
th10 = threading.Thread(target=app10._worker, daemon=True)
th10.start()
time.sleep(0.4)
app10.running = False
th10.join(timeout=2.0)
verifie(sc3.gains_roles == {},
        "worker, case DÉCOCHÉE (défaut) : aucun gain écrit dans le stacker")
app10.var_photo_gains.set(True)
app10._on_photo_gains()
verifie("appliqués" in app10.lbl_photo_gains.cget("text").lower()
        or "en attente" in app10.lbl_photo_gains.cget("text"),
        f"le libellé annonce l'état des gains "
        f"(« {app10.lbl_photo_gains.cget('text')[:44]}… »)")
app10.running = True
th10 = threading.Thread(target=app10._worker, daemon=True)
th10.start()
time.sleep(0.4)
app10.running = False
th10.join(timeout=2.0)
verifie(sc3.gains_roles == {"Ha": 2.0, "O3": 0.5},
        f"worker, case COCHÉE : gains mesurés écrits dans le stacker "
        f"({sc3.gains_roles})")
root10.destroy()

# ============================================================ récapitulatif
print()
if ok:
    print("BANC JALON 56 (étape 4, photométrie) : TOUT AU VERT")
else:
    print("BANC JALON 56 (étape 4, photométrie) : ÉCHECS — voir ci-dessus")
sys.exit(0 if ok else 1)
