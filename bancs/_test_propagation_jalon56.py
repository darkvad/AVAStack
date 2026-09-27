# -*- coding: utf-8 -*-
"""Banc du jalon 56 (étape 3) : propagation du WCS par COMPOSITION.

[1] compose_M / inverse_M : composition et inversion de warpAffine exactes ;
[2] identité : propager(wcs, I) ≡ wcs (aller-retours au bruit machine) ;
[3] VÉRITÉ analytique : image synthétique warpée par une matrice connue —
    le WCS propagé doit replacer les étoiles EXACTEMENT (composition exacte,
    1e-9 px), puis confrontation aux centroïdes DÉTECTÉS dans l'image warpée ;
[4] vers_tan() confronté à astropy.wcs (RÉFÉRENCE INDÉPENDANTE — règle de
    CLAUDE.md) : rms du ré-ajustement, déviation exact-vs-TAN, mots-clés FITS ;
[5] validation croisée : re-SOLVE indépendant (étape 2) de l'image warpée
    vs WCS propagé (catalogue Gaia requis, sinon section tronquée sans échec) ;
[6] chaîne de RÉEMPILEREMENT (grille G0 → G1 → frame) : composition exacte
    + StarAligner RÉEL (sens des matrices de l'aligneur, l'appel réel du
    futur branchement) ;
[7] échecs PROPRES : matrice non finie, mauvaise forme, dégénérée, échelle
    aberrante, WCS absent, vers_tan sans forme.

Exécution : python bancs/_test_propagation_jalon56.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import math
import sys

import numpy as np
import cv2

from avastack.catalogues import (CatalogueSiril, WcsTan, compose_M,
                                 dossier_catalogues, etat_local, inverse_M,
                                 propager, resoudre)
from avastack.catalogues import propagation as _prop
from avastack.catalogues import solveur as _solveur
from avastack.processing.alignment import StarAligner

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ----------------------------------------------------------- utilitaires
def ecart_ciel_deg(ra1, dec1, ra2, dec2):
    """Écart angulaire (deg) entre deux listes de positions célestes."""
    p1, d1, p2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    a = (np.sin((d2 - d1) / 2.0) ** 2
         + np.cos(d1) * np.cos(d2) * np.sin((p2 - p1) / 2.0) ** 2)
    return np.degrees(2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


def rendu_etoiles(forme, xy, amplitudes, fond=0.02, bruit=0.004, sigma=1.4,
                  graine=56):
    """Image synthétique : gaussiennes sous-pixel + fond + bruit gaussien."""
    rng = np.random.default_rng(graine)
    img = rng.normal(fond, bruit, forme).astype(np.float32)
    h, w = forme
    r = int(5 * sigma)
    for (x, y), a in zip(np.asarray(xy, float), amplitudes):
        ix, iy = int(round(x)), int(round(y))
        if ix - r < 0 or iy - r < 0 or ix + r >= w or iy + r >= h:
            continue
        xs = np.arange(ix - r, ix + r + 1, dtype=np.float64)
        ys = np.arange(iy - r, iy + r + 1, dtype=np.float64)
        r2 = (xs[None, :] - x) ** 2 + (ys[:, None] - y) ** 2
        img[iy - r:iy + r + 1, ix - r:ix + r + 1] += (
            a * np.exp(-r2 / (2 * sigma * sigma))).astype(np.float32)
    return img


def ecart_wcs_deg(w1, w2, forme, n=9):
    """Écart angulaire max (deg) entre deux WCS (ou WcsCompose) sur une
    grille couvrant l'image (coins inclus)."""
    h, w = forme
    xs = np.linspace(0, w - 1, n)
    ys = np.linspace(0, h - 1, n)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.column_stack([XX.ravel(), YY.ravel()])
    ra1, dec1 = w1.vers_radec(pts)
    ra2, dec2 = w2.vers_radec(pts)
    return float(ecart_ciel_deg(ra1, dec1, ra2, dec2).max())


def mat_transfo(angle_deg, dx, dy, w, h):
    """warpAffine « vérité » : rotation autour du centre + translation du
    contenu (même construction que les tests d'alignement du projet)."""
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    M[0, 2] += dx
    M[1, 2] += dy
    return M


def applique_M(M, pts):
    """p_cible = M @ [p, 1] (sens warpAffine, contenu déplacé de M)."""
    M = np.asarray(M, np.float64)
    return np.asarray(pts, np.float64) @ M[:, :2].T + M[:, 2]


# ============================================== [1] compose_M / inverse_M
print("[1] compose_M / inverse_M : composition et inversion exactes")
rng = np.random.default_rng(56)
pts = np.column_stack([rng.uniform(-500, 500, 200),
                       rng.uniform(-500, 500, 200)])
err_compo = err_inv = 0.0
for _ in range(20):
    M1 = mat_transfo(rng.uniform(-10, 10), rng.uniform(-80, 80),
                     rng.uniform(-80, 80), 1600, 1200)
    M2 = mat_transfo(rng.uniform(-10, 10), rng.uniform(-80, 80),
                     rng.uniform(-80, 80), 1600, 1200)
    C = compose_M(M2, M1)
    err_compo = max(err_compo, float(np.abs(
        applique_M(C, pts) - applique_M(M2, applique_M(M1, pts))).max()))
    err_inv = max(err_inv, float(np.abs(
        applique_M(inverse_M(M1), applique_M(M1, pts)) - pts).max()))
verifie(err_compo < 1e-9, f"compose_M(M2, M1) ≡ M2∘M1 ({err_compo:.2e} px)")
verifie(err_inv < 1e-9, f"inverse_M(M) ≡ M⁻¹ aller-retour ({err_inv:.2e} px)")

# ================================================== [2] identité + retour
print("[2] Identité : propager(wcs, I) ≡ wcs ; aller-retours exacts")
CRVAL_VRAI = (10.700, 41.300)
FORME = (1200, 1600)                       # (H, W)
ECHELLE_DEG = 1.0 / 3600.0                 # 1,0″/px
CHAMP_DEG = FORME[1] * ECHELLE_DEG
c, s = math.cos(math.radians(-8.0)), math.sin(math.radians(-8.0))
W_VRAI = WcsTan(CRVAL_VRAI, ((FORME[1] - 1) / 2.0, (FORME[0] - 1) / 2.0),
                [[-ECHELLE_DEG * c, ECHELLE_DEG * s],
                 [ECHELLE_DEG * s, ECHELLE_DEG * c]], forme=FORME)
W_id, msg = propager(W_VRAI, np.eye(2, 3))
verifie(W_id is not None and not msg, f"propager(identité) accepté « {msg} »")
rq = pts[:64] + [600.0, 800.0]
ra_q, dec_q = W_VRAI.vers_radec(rq)
e1 = float(ecart_ciel_deg(*W_id.vers_radec(rq), ra_q, dec_q).max())
e2 = float(np.abs(W_id.vers_pixels(ra_q, dec_q)
                  - W_VRAI.vers_pixels(ra_q, dec_q)).max())
verifie(e1 < 1e-12 and e2 < 1e-9,
        f"identité ≡ référence : ciel {e1:.1e}°, pixels {e2:.1e} px")
ra_r, dec_r = W_id.vers_radec(rq)
e3 = float(np.abs(W_id.vers_pixels(ra_r, dec_r) - rq).max())
verifie(e3 < 1e-8, f"aller-retour pixels→ciel→pixels ({e3:.2e} px)")
# translation seule (cas le plus courant : dithering)
# M_d est en sens CONTENU (référence → frame) ; l'aligneur, lui, renvoie
# la matrice INVERSE (frame → référence) — c'est elle que prend `propager`.
M_d = mat_transfo(0.0, 23.0, -11.0, FORME[1], FORME[0])
W_d, _ = propager(W_VRAI, inverse_M(M_d))
e4 = float(np.abs(W_d.vers_pixels(ra_q, dec_q)
                  - applique_M(M_d, W_VRAI.vers_pixels(ra_q, dec_q))).max())
verifie(e4 < 1e-9, f"translation seule exacte ({e4:.2e} px)")

# ================================== [3] vérité analytique + détection
print("[3] Vérité analytique : image warpée, WCS propagé = composition exacte")
etat = etat_local(dossier_catalogues())
if etat.get("astro"):
    cat = CatalogueSiril(etat["astro"])
    et = cat.extraire(*CRVAL_VRAI, 0.45, limmag=15.5)
    ra_l, dec_l, g_l = et["ra"], et["dec"], et["g"]
    print(f"      catalogue Gaia réel : {len(ra_l)} étoiles extraites")
else:
    print("      catalogue Gaia ABSENT — étoiles synthétiques (la section "
          "[5] sera tronquée, sans échec)")
    rr = np.random.default_rng(11)
    ra_l = CRVAL_VRAI[0] + rr.uniform(-0.22, 0.22, 80) / math.cos(
        math.radians(CRVAL_VRAI[1]))
    dec_l = CRVAL_VRAI[1] + rr.uniform(-0.20, 0.20, 80)
    g_l = rr.uniform(11.0, 14.5, 80)
xy_ref = W_VRAI.vers_pixels(ra_l, dec_l)
dans = ((xy_ref[:, 0] > 10) & (xy_ref[:, 0] < FORME[1] - 11)
        & (xy_ref[:, 1] > 10) & (xy_ref[:, 1] < FORME[0] - 11))
ra_l, dec_l, g_l, xy_ref = (ra_l[dans], dec_l[dans], g_l[dans], xy_ref[dans])
amps = 0.8 * np.power(10.0, -0.4 * (g_l - 11.0))
img0 = rendu_etoiles(FORME, xy_ref, amps, graine=3)
M_vrai = mat_transfo(2.0, 37.0, -23.0, FORME[1], FORME[0])   # dérive 2°
img_w = cv2.warpAffine(img0, M_vrai, (FORME[1], FORME[0]),
                       flags=cv2.INTER_LINEAR)
p_ref = applique_M(M_vrai, xy_ref)         # positions VRAIES dans la warpée

W_p, msg_p = propager(W_VRAI, inverse_M(M_vrai), forme=FORME)
verifie(W_p is not None and not msg_p,
        f"propager(rotation 2° + dérive) « {msg_p} »")
e5 = float(np.abs(W_p.vers_pixels(ra_l, dec_l) - p_ref).max())
verifie(e5 < 1e-9, f"composition EXACTE vs vérité : {e5:.2e} px")
ech_rel = W_p.echelle_arcsec / W_VRAI.echelle_arcsec
verifie(abs(ech_rel - 1.0) < 1e-12, f"échelle inchangée ({ech_rel:.6f})")
# confrontation aux centroïdes DÉTECTÉS dans l'image warpée
pos_w, msg_det = _solveur._detecter(img_w, max_etoiles=120)
verifie(len(pos_w) >= 8 and not msg_det,
        f"détection dans l'image warpée : {len(pos_w)} étoiles « {msg_det} »")
p_pred = W_p.vers_pixels(ra_l, dec_l)
d = np.hypot(pos_w[:, None, 0] - p_pred[None, :, 0],
             pos_w[:, None, 1] - p_pred[None, :, 1])
# appariements MUTUELS (règle « ancre fiable », jalon 13) détection↔prédiction
jc = d.argmin(1)                       # pour chaque détection, prédiction +
jp = d.argmin(0)                       # pour chaque prédiction, détection +
sel = (jp[jc] == np.arange(len(pos_w))) & (d[np.arange(len(pos_w)),
                                              jc] <= 3.0)
err_px = float(d[np.arange(len(pos_w))[sel], jc[sel]].max()) \
    if sel.any() else 99.0
err_med = float(np.median(d[np.arange(len(pos_w))[sel], jc[sel]])) \
    if sel.any() else 99.0
verifie(int(sel.sum()) >= 8 and err_med < 0.2 and err_px < 1.0,
        f"centroïdes vs WCS propagé : {int(sel.sum())} étoiles, "
        f"écart médian {err_med:.3f} px, max {err_px:.3f} px "
        "(rééchantillonnage bilinéaire du warp)")

# ============================= [4] vers_tan vs astropy (réf. indépendante)
print("[4] vers_tan : rms, déviation exact-vs-TAN, mots-clés vs astropy.wcs")
from astropy.io import fits
from astropy.wcs import WCS
W_tan, rms_tan = W_p.vers_tan(FORME)
verifie(rms_tan < 5e-3, f"rms du ré-ajustement TAN : {rms_tan:.2e} px")
dev = ecart_wcs_deg(W_tan, W_p, FORME, n=15)
verifie(dev < 1e-4, f"déviation max TAN ajusté vs composition exacte : "
        f"{dev * 3600.0:.3f}″")
w_apy = WCS(fits.Header(W_tan.mots_cles_fits()))
gp = np.column_stack([rng.uniform(0, FORME[1] - 1, 96),
                      rng.uniform(0, FORME[0] - 1, 96)])
ra_a, dec_a = w_apy.all_pix2world(gp[:, 0], gp[:, 1], 0)
ra_m, dec_m = W_tan.vers_radec(gp)
e6 = float(ecart_ciel_deg(ra_a, dec_a, ra_m, dec_m).max())
px_a = np.column_stack(w_apy.all_world2pix(ra_a, dec_a, 0))
px_m = W_tan.vers_pixels(ra_a, dec_a)
e7 = float(np.abs(px_a - px_m).max())
verifie(e6 < 1e-9 and e7 < 1e-6,
        f"mots-clés FITS du TAN ajusté ≡ astropy : ciel {e6:.1e}°, "
        f"pixels {e7:.1e} px")

# ==================== [5] validation croisée : re-solve indépendant
print("[5] Re-solve interne (étape 2) de l'image warpée vs WCS propagé")
if not etat.get("astro"):
    print("      catalogue astro ABSENT — section skippée, sans échec.")
else:
    ra0, dec0 = W_p.vers_radec(np.array([[(FORME[1] - 1) / 2.0,
                                          (FORME[0] - 1) / 2.0]]))
    wcs_rs, info_rs, msg_rs = resoudre(img_w, float(ra0[0]), float(dec0[0]),
                                       CHAMP_DEG)
    if wcs_rs is None:
        verifie(False, f"re-solve de l'image warpée : ÉCHEC — {msg_rs}")
    else:
        e8 = ecart_wcs_deg(wcs_rs, W_p, FORME)
        ech_rs = wcs_rs.echelle_arcsec / W_p.echelle_arcsec
        verifie(e8 < 2.8e-4 and abs(ech_rs - 1.0) < 0.003,
                f"re-solve ≈ propagé : {e8 * 3600.0:.2f}″, échelle "
                f"{ech_rs * 100:.2f} % ({info_rs['n_appariements']} étoiles, "
                f"rms {info_rs['rms_px']:.3f} px)")

# ==================== [6] chaîne de RÉEMPILEREMENT + aligneur RÉEL
print("[6] Chaîne réempilement G0→G1→frame ; StarAligner réel (sens)")
M10 = mat_transfo(1.5, -52.0, 30.0, FORME[1], FORME[0])   # G0 → G1
M_f1 = mat_transfo(0.4, 13.0, -7.0, FORME[1], FORME[0])   # G1 → frame
W1, msg10 = propager(W_VRAI, inverse_M(M10), forme=FORME)
verifie(W1 is not None and not msg10, "W1 = W0 ∘ (R1→G0) accepté")
p1_vrai = applique_M(M10, xy_ref)
e9 = float(np.abs(W1.vers_pixels(ra_l, dec_l) - p1_vrai).max())
verifie(e9 < 1e-9, f"W1 exact vs vérité G1 : {e9:.2e} px")
Wf, msgf = propager(W_VRAI, compose_M(inverse_M(M10), inverse_M(M_f1)),
                    forme=FORME)
p_f_vrai = applique_M(M_f1, p1_vrai)
e10 = float(np.abs(Wf.vers_pixels(ra_l, dec_l) - p_f_vrai).max())
verifie(Wf is not None and e10 < 1e-9,
        f"chaîne composée exacte (frame) : {e10:.2e} px « {msgf} »")
# aligneur RÉEL du projet : le sens des matrices est celui du branchement
# futur (set_reference(ancien empilement) ; compute(nouvelle référence)).
img_R1 = cv2.warpAffine(img0, M10, (FORME[1], FORME[0]),
                        flags=cv2.INTER_LINEAR)
al = StarAligner()
al.set_reference(img0)
M_al, ok_al = al.compute(img_R1)
if not ok_al:
    verifie(False, "StarAligner : la nouvelle référence n'a pas été "
            "recalée sur l'ancien empilement (l'appel réel échouerait)")
else:
    W1r, _ = propager(W_VRAI, M_al, forme=FORME)
    pr = W1r.vers_pixels(ra_l, dec_l)
    dd = np.hypot(pr[:, None, 0] - p1_vrai[None, :, 0],
                  pr[:, None, 1] - p1_vrai[None, :, 1])
    err_al = float(dd.min(1).max())
    meth = (al.dernier or {}).get("methode", "?")
    verifie(err_al < 1.0,
            f"WCS propagé via l'ALIGNEUR RÉEL : écart max {err_al:.3f} px "
            f"(méthode « {meth} »)")

# ============================================== [7] échecs propres
print("[7] Échecs propres : jamais d'exception, jamais de panne silencieuse")
r, m = propager(None, np.eye(2, 3))
verifie(r is None and bool(m), f"WCS absent → « {m} »")
r, m = propager(W_VRAI, np.zeros((3, 3)))
verifie(r is None and bool(m), f"forme (3, 3) → « {m} »")
Mn = np.eye(2, 3); Mn[0, 2] = np.nan
r, m = propager(W_VRAI, Mn)
verifie(r is None and bool(m), f"NaN → « {m} »")
r, m = propager(W_VRAI, np.zeros((2, 3)))
verifie(r is None and bool(m), f"dégénérée (det 0) → « {m} »")
r, m = propager(W_VRAI, np.array([[3.0, 0.0, 5.0], [0.0, 3.0, 5.0]]))
verifie(r is None and bool(m), f"échelle 3,0 (sanity) → « {m} »")
try:
    W_cs = propager(W_VRAI, np.eye(2, 3))[0]     # SANS forme
    W_cs.vers_tan(None)
    verifie(False, "vers_tan sans forme : aurait dû lever ValueError")
except ValueError as exc:
    verifie(True, f"vers_tan sans forme → ValueError propre (« {exc} »)")

# ----------------------------------------------------- récapitulatif
print()
if ok:
    print("BANC JALON 56 ÉTAPE 3 : TOUT AU VERT")
    sys.exit(0)
print("BANC JALON 56 ÉTAPE 3 : ÉCHECS — voir les lignes « ÉCHEC » ci-dessus")
sys.exit(1)
