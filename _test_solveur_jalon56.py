# -*- coding: utf-8 -*-
"""Banc du jalon 56 (étape 2) : solveur astrométrique interne.

[1] projection TAN + WcsTan confrontés à astropy.wcs (RÉFÉRENCE
    INDÉPENDANTE — règle de CLAUDE.md) sur plusieurs parités/orientations ;
[2] détection d'étoiles (positions sous-pixel, bruit pur) ;
[3] solve INTERNE de bout en bout sur des images synthétiques construites
    depuis le VRAI catalogue Gaia de Siril : indices exacts, indices
    bruités, parité inversée, indices très faux, image sans étoiles ;
[4] validation croisée astap_cli sur la même image (skippé sans échec si
    ASTAP est absent) ;
[5] récapitulatif.

Exécution : python _test_solveur_jalon56.py
"""
import math
import os
import shutil
import sys
import tempfile

import numpy as np

from avastack.catalogues import (CatalogueSiril, WcsTan, dossier_catalogues,
                                 etat_local, projection_tan,
                                 projection_tan_inverse, resoudre)
from avastack.catalogues import astap as _astap
from avastack.catalogues import solveur as _solveur

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
    """Image synthétique : gaussiennes sous-pixel (tampons locaux) + fond
    uniforme + bruit gaussien. `xy` en (x, y) tableau, 0-based."""
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


def wcs_depuis_cd(crval, crpix, cd, forme):
    """WCS « vérité » pour fabriquer une image."""
    return WcsTan(crval, crpix, cd, forme=forme)


def ecart_wcs_deg(w1, w2, forme, n=9):
    """Écart angulaire maximal (deg) entre deux WCS sur une grille de
    pixels couvrant l'image (les coins inclus)."""
    h, w = forme
    xs = np.linspace(0, w - 1, n)
    ys = np.linspace(0, h - 1, n)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.column_stack([XX.ravel(), YY.ravel()])
    ra1, dec1 = w1.vers_radec(pts)
    ra2, dec2 = w2.vers_radec(pts)
    return float(ecart_ciel_deg(ra1, dec1, ra2, dec2).max())


# ================================================ [1] TAN vs astropy.wcs
print("[1] Projection TAN + WcsTan vs astropy.wcs (référence indépendante)")
from astropy.io import fits
from astropy.wcs import WCS

CAS_WCS = [
    # (nom, crval, crpix, cd) — parités et orientations variées
    ("parité −, PA ≈ −8°", (10.700, 41.300), (599.5, 399.5),
     [[-2.7778e-4, 3.86e-5], [3.86e-5, 2.7778e-4]]),
    ("parité +", (83.630, 22.010), (250.0, 700.0),
     [[2.0e-4, 1.5e-4], [-1.5e-4, 2.2e-4]]),
    ("dec haute, CD diagonale", (200.0, 75.0), (300.0, 300.0),
     [[5.0e-4, 0.0], [0.0, 5.0e-4]]),
]
for nom, crval, crpix, cd in CAS_WCS:
    W = WcsTan(crval, crpix, cd)
    w_apy = WCS(fits.Header(W.mots_cles_fits()))
    rng = np.random.default_rng(7)
    pts = np.column_stack([rng.uniform(0, 1200, 64),
                           rng.uniform(0, 800, 64)])
    pts = np.vstack([pts, [crpix, [0.0, 0.0], [1199.0, 799.0]]])
    ra_a, dec_a = w_apy.all_pix2world(pts[:, 0], pts[:, 1], 0)
    ra_m, dec_m = W.vers_radec(pts)
    e1 = float(ecart_ciel_deg(ra_a, dec_a, ra_m, dec_m).max())
    ra_r, dec_r = W.vers_radec(pts)          # aller
    ret = W.vers_pixels(ra_r, dec_r)         # retour
    e2 = float(np.abs(ret - pts).max())
    # sens inverse : ciel astropy → pixels, vs notre vers_pixels
    px_a = np.column_stack(w_apy.all_world2pix(ra_a, dec_a, 0))
    px_m = W.vers_pixels(ra_a, dec_a)
    e3 = float(np.abs(px_a - px_m).max())
    verifie(e1 < 1e-9 and e3 < 1e-6,
            f"{nom} : pix→ciel écart max {e1:.2e}°, ciel→pix {e3:.2e} px "
            f"(vs astropy)")
    verifie(e2 < 1e-8, f"{nom} : aller-retour pixels exact ({e2:.2e} px)")

# ================================================ [2] détection d'étoiles
print("[2] Détection : positions sous-pixel, bruit pur")
rng = np.random.default_rng(56)
forme_det = (600, 800)
xy_vrai = np.column_stack([rng.uniform(25, 775, 10),
                           rng.uniform(25, 575, 10)])
amp_vrai = np.sort(rng.uniform(0.3, 1.2, 10))[::-1]
img_det = rendu_etoiles(forme_det, xy_vrai, amp_vrai, graine=2)
pos, msg = _solveur._detecter(img_det, max_etoiles=50)
verifie(len(pos) == 10 and not msg,
        f"10 étoiles synthétiques détectées ({len(pos)})")
if len(pos) == 10:
    # les 10 détectées doivent coïncider aux 10 vraies (±0,2 px)
    d = np.hypot(pos[:, None, 0] - xy_vrai[None, :, 0],
                 pos[:, None, 1] - xy_vrai[None, :, 1])
    err = d.min(1).max()
    verifie(err < 0.2, f"centroïdes exacts : écart max {err:.3f} px")
    # ordre par éclat : la plus brillante détectée = la plus grande amplitude
    d0 = np.hypot(pos[0, 0] - xy_vrai[:, 0], pos[0, 1] - xy_vrai[:, 1])
    verifie(int(d0.argmin()) == 0,
            "tri par éclat décroissant respecté")
pos, msg = _solveur._detecter(rng.normal(0.02, 0.004, forme_det))
verifie(len(pos) == 0 and msg == "",
        f"bruit pur : aucune étoile, pas d'exception (msg « {msg} »)")

# ==================================== [3] solve interne (catalogue réel)
print("[3] Solve interne de bout en bout (catalogue Gaia réel de Siril)")
etat = etat_local(dossier_catalogues())
if not etat.get("astro"):
    print("      catalogue astro ABSENT — sections [3]/[4] tronquées, "
          "sans échec (lancez le téléchargeur de l'étape 1).")
    sys.exit(0 if ok else 1)
cat = CatalogueSiril(etat["astro"])

CRVAL_VRAI = (10.700, 41.300)
FORME = (1200, 1600)                       # (H, W)
ECHELLE_DEG = 1.0 / 3600.0                 # 1,0″/px
CHAMP_DEG = FORME[1] * ECHELLE_DEG         # largeur du champ (est-ouest)


def fabrique_image(paire_x=True, pa=math.radians(-8.0), graine=3):
    """Image synthétique : étoiles Gaia projetées par un WCS vérité.
    → (img, wcs_vrai, (ra, dec)). La vérité est construite NUMÉRIQUEMENT
    depuis les positions réellement rendues (le mapping de WcsTan est
    exactement affine dans le plan tangent) — pas de construction
    analytique de la matrice CD, source d'erreurs de signe (constaté en
    3c lors du premier passage du banc)."""
    et = cat.extraire(*CRVAL_VRAI, 0.45, limmag=15.5)
    ra, dec = et["ra"], et["dec"]
    c, s = math.cos(pa), math.sin(pa)
    wcs = WcsTan(CRVAL_VRAI, ((FORME[1] - 1) / 2.0, (FORME[0] - 1) / 2.0),
                 [[-ECHELLE_DEG * c, ECHELLE_DEG * s],
                  [ECHELLE_DEG * s, ECHELLE_DEG * c]], forme=FORME)
    xy = wcs.vers_pixels(ra, dec)
    if not paire_x:                        # parité inversée
        xy = xy.copy()
        xy[:, 0] = (FORME[1] - 1) - xy[:, 0]
    dans = ((xy[:, 0] > 10) & (xy[:, 0] < FORME[1] - 11)
            & (xy[:, 1] > 10) & (xy[:, 1] < FORME[0] - 11))
    xy, ra, dec, g = xy[dans], ra[dans], dec[dans], et["g"][dans]
    amps = 0.8 * np.power(10.0, -0.4 * (g - 11.0))
    img = rendu_etoiles(FORME, xy, amps, graine=graine)

    # vérité exacte : ajustement affine des positions réellement rendues
    # (x = ξ·M[0,0] + η·M[1,0] + M[2,0] → partie linéaire = M[:2,:].T)
    xi, eta = projection_tan(ra, dec, *CRVAL_VRAI)
    A = np.column_stack([xi, eta, np.ones(len(xi))])
    M, *_ = np.linalg.lstsq(A, xy, rcond=None)
    res = float(np.abs(A @ M - xy).max())
    assert res < 1e-6, f"mapping non affine : {res:.2e} px"
    wcs_vrai = WcsTan(CRVAL_VRAI, M[2, :], np.linalg.inv(M[:2, :].T),
                      forme=FORME)
    return img, wcs_vrai, (ra, dec)


def verifie_solve(nom, img, ra0, dec0, champ, wcs_vrai, tol_deg=2.8e-4):
    wcs, info, msg = resoudre(img, ra0, dec0, champ)
    if wcs is None:
        verifie(False, f"{nom} : ÉCHEC — {msg}")
        return None
    ecart = ecart_wcs_deg(wcs, wcs_vrai, FORME)
    ech_rel = wcs.echelle_arcsec / wcs_vrai.echelle_arcsec
    verifie(ecart < tol_deg and abs(ech_rel - 1.0) < 0.003,
            f"{nom} : écart max {ecart * 3600.0:.2f}\" vs vérité, échelle "
            f"{ech_rel * 100:.2f} % ({info['n_appariements']} étoiles, "
            f"rms {info['rms_px']:.3f} px)")
    return wcs


# --- 3a) indices exacts ------------------------------------------------------
img_a, wcs_vrai, _ = fabrique_image()
wcs_a = verifie_solve("3a indices exacts", img_a, *CRVAL_VRAI, CHAMP_DEG,
                      wcs_vrai)

# --- 3b) indices bruités (centre ~6' d'erreur, champ −25 %) ------------------
img_b, wcs_vrai_b, _ = fabrique_image(graine=4)
verifie_solve("3b indices bruités", img_b, CRVAL_VRAI[0] + 0.08,
              CRVAL_VRAI[1] - 0.10, CHAMP_DEG * 0.75, wcs_vrai_b)

# --- 3c) parité inversée -----------------------------------------------------
img_c, wcs_vrai_c, _ = fabrique_image(paire_x=False, graine=5)
verifie_solve("3c parité inversée", img_c, *CRVAL_VRAI, CHAMP_DEG,
              wcs_vrai_c)

# --- 3d) indices très faux : échec PROPRE ------------------------------------
wcs_d, info_d, msg_d = resoudre(img_a, CRVAL_VRAI[0] + 1.5,
                                CRVAL_VRAI[1] - 1.2, CHAMP_DEG)
verifie(wcs_d is None and bool(msg_d),
        f"3d indices à 1,5° : échec propre (« {msg_d} »)")

# --- 3e) image sans étoiles : échec PROPRE -----------------------------------
rng = np.random.default_rng(9)
wcs_e, info_e, msg_e = resoudre(rng.normal(0.02, 0.004, FORME),
                                *CRVAL_VRAI, CHAMP_DEG)
verifie(wcs_e is None and bool(msg_e),
        f"3e bruit pur : échec propre (« {msg_e} »)")

# ============================== [4] validation croisée ASTAP (si présent)
print("[4] Validation croisée astap_cli (référence indépendante + repli)")
exe = _astap.trouver_astap()
if exe is None:
    print("      ASTAP absent — section skippée, sans échec.")
else:
    print(f"      astap_cli : {exe}")
    tmp = tempfile.mkdtemp(prefix="avastack_j56e2_")
    try:
        p_img = os.path.join(tmp, "synth.fit")
        from astropy.io import fits as _fits
        _fits.PrimaryHDU(np.clip(img_a * 65535.0, 0, 65535).astype(
            np.uint16)).writeto(p_img, overwrite=True)
        wcs_ap, msg_ap = _astap.resoudre_avec_astap(
            p_img, ra0=CRVAL_VRAI[0], dec0=CRVAL_VRAI[1], rayon_deg=2.0,
            fov_deg=FORME[0] * ECHELLE_DEG, dossier_sortie=tmp)
        if wcs_ap is None:
            verifie(False, f"astap_cli : échec du solve — « {msg_ap} »")
        else:
            e_truth = ecart_wcs_deg(wcs_ap, wcs_vrai, FORME)
            e_interne = (ecart_wcs_deg(wcs_ap, wcs_a, FORME)
                         if wcs_a is not None else float("nan"))
            verifie(e_truth < 3.0e-4 and e_interne < 3.0e-4,
                    f"astap_cli ≈ vérité ({e_truth * 3600.0:.2f}\") et "
                    f"≈ solveur interne ({e_interne * 3600.0:.2f}\")")
        # échec propre : image absente
        wcs_x, msg_x = _astap.resoudre_avec_astap(
            os.path.join(tmp, "inexistant.fit"), ra0=10.0, dec0=41.0)
        verifie(wcs_x is None and bool(msg_x),
                f"astap_cli image absente : échec propre (« {msg_x} »)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ================================================ [5] récapitulatif
print("BANC JALON 56 (étape 2) :", "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)
