# -*- coding: utf-8 -*-
"""DIAG — brutes OSC (Uranus-C Pro, NGC 7023) : pourquoi l'astrométrie échoue.

But : REPRODUIRE l'échec observé par Alain (28/09/2026) sur ses vraies brutes
(champ 0,5005°, C8 @ 1280 mm, IMX585 2,9 µm), pas sur une image de synthèse.

Chemin : lecture de N brutes du dossier réseau (débayerisées par `load_image`,
BAYERPAT=RGGB écrit par N.I.N.A.), moyenne brute (sans alignement — le but est
l'astrométrie, pas le rendu), puis :
  [1] détection d'étoiles (celle du solveur interne) ;
  [2] `catalogues.solveur.resoudre` avec les indices RÉELS du 28/09/2026 ;
  [3] balayage des DÉCALAGES D'INDICES (AD/Dec ±X°, champ ±Y %) pour voir si
      l'échec vient des indices ou de l'image ;
  [4] référence INDÉPENDANTE : ASTAP sur la même moyenne (si installé).

Usage :  python bancs/_diag_osc_ngc7023.py [n_frames]
"""
import os
import sys
import time
import glob
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                            # noqa: E402
import cv2                                                    # noqa: E402

from avastack import images as img_mod                        # noqa: E402
from avastack.catalogues import solveur                       # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOSSIER = (r"\\192.168.155.45\Telechargements\Astro\CPC800\NINA"
           r"\TargetSchedulerSequence\NGC 7023\240.00s\LIGHT")
RA0, DEC0, CHAMP = 315.404167, 68.163333, 0.5005

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12

fichiers = sorted(glob.glob(os.path.join(DOSSIER, "*.fits")))[:N]
print(f"Dossier : {DOSSIER}")
print(f"Fichiers lus : {len(fichiers)} (sur {N} demandés)")
img_mod.CFA_MODE = "Auto"

from avastack.processing import astrometrie as astro_mod        # noqa: E402
from avastack.processing.alignment import StarAligner          # noqa: E402


def astap(img, etiquette, fov=None):
    """Référence INDÉPENDANTE : ASTAP (guidé) sur `img` — dit si l'échec du
    solveur interne est un défaut de NOS données ou du solveur."""
    try:
        with tempfile.TemporaryDirectory(prefix="ava_diag_osc_") as tmp:
            a, ent = img_mod.borner_lineaire(img, {})
            src = os.path.join(tmp, "img.fits")
            img_mod.save_image(src, a, entete=ent)
            h, w = img.shape[:2]
            wcs_a, msg_a = astro_mod._resoudre_astap(
                src, ra0=RA0, dec0=DEC0, rayon_deg=1.0,
                fov_deg=(fov if fov else CHAMP) * h / float(w),
                dossier_sortie=tmp, timeout=300)
        if wcs_a is None:
            print(f"    ASTAP [{etiquette}] : échec — {msg_a}")
        else:
            print(f"    ASTAP [{etiquette}] : RÉSOLU — "
                  f"{wcs_a.echelle_arcsec:.4f}\"/px, angle "
                  f"{wcs_a.angle_deg:+.2f}°, champ "
                  f"{w * wcs_a.echelle_arcsec / 3600.0:.4f}° (attendu "
                  f"{CHAMP:.4f}° / {3600.0 * CHAMP / w:.4f}\"/px)")
        return wcs_a
    except Exception as exc:
        print(f"    ASTAP [{etiquette}] non testé ({type(exc).__name__} : {exc})")
        return None


def resoudre(img, etiquette):
    luma = solveur._canonise_img(img)
    fond = float(np.median(luma))
    bruit = 1.4826 * float(np.median(np.abs(luma - fond)))
    pos, msg = solveur._detecter(img)
    print(f"  [{etiquette}] fond {fond:.5f} · bruit MAD {bruit:.5f} · "
          f"{len(pos)} étoiles (plafond {solveur.MAX_ETOILES_DETECTION})"
          f"{' — ' + msg if msg else ''}")
    t0 = time.perf_counter()
    wcs, info, msg = solveur.resoudre(img, RA0, DEC0, CHAMP)
    print(f"  [{etiquette}] solveur interne : {'SUCCÈS' if wcs else 'ÉCHEC'} "
          f"en {time.perf_counter() - t0:.1f} s — "
          f"{msg or ('%d appariements, rms %.2f px, %.4f\"/px' % (info['n_appariements'], info['rms_px'], info['echelle_arcsec_px']))}")
    return wcs


t0 = time.perf_counter()
CACHE = r"c:\Astro\test\ngc7023_alignee.fits"
if os.path.isfile(CACHE):
    img_al = img_mod.load_image(CACHE)
    brutes = [img_al]
    print(f"empilement aligné RELU du cache : {CACHE} — {img_al.shape}")
else:
    brutes = []
    for i, f in enumerate(fichiers):
        brutes.append(img_mod.load_image(f))
        if (i + 1) % 4 == 0:
            print(f"  … {i + 1} frames lues ({time.perf_counter() - t0:.1f} s)")
    img = np.mean(np.stack(brutes), axis=0).astype(np.float32)
    print(f"{len(brutes)} brutes débayerisées {brutes[0].shape} lues en "
          f"{time.perf_counter() - t0:.1f} s — fond médian "
          f"{float(np.median(img[:, :, 1])):.5f}")

print("\n[1] UNE SEULE BRUTE (240 s, suivi — pas de rotation de champ)")
w1 = resoudre(brutes[0], "1 brute")
if w1 is None and len(brutes) > 1:
    astap(brutes[0], "1 brute")
if len(brutes) == 1:
    print("    (cache : test de la brute unique sauté)")

if len(brutes) > 1:
    print("\n[2] MOYENNE DE %d BRUTES NON ALIGNÉES (ce que fait la dérive seule)"
          % len(brutes))
    img = np.mean(np.stack(brutes), axis=0).astype(np.float32)
    w2 = resoudre(img, "non alignée")

    print("\n[3] EMPILEMENT ALIGNÉ (aligneur RÉEL du projet, comme l'appli)")
    t0 = time.perf_counter()
    al = StarAligner()
    al.set_reference(brutes[0])
    somme = None
    n_ok = 0
    for i, a in enumerate(brutes):
        M, ok = al.compute(a)
        if not ok:
            print(f"    frame {i} refusée par l'aligneur")
            continue
        w = cv2.warpAffine(a, M, (a.shape[1], a.shape[0]),
                           flags=cv2.INTER_LINEAR)
        somme = w.astype(np.float64) if somme is None else somme + w
        n_ok += 1
    img_al = (somme / n_ok).astype(np.float32)
    print(f"    {n_ok}/{len(brutes)} frames alignées en "
          f"{time.perf_counter() - t0:.1f} s")
    try:
        a, ent = img_mod.borner_lineaire(img_al, {})
        img_mod.save_image(CACHE, a, entete=ent)
        print(f"    empilement aligné mis en cache : {CACHE}")
    except Exception as exc:
        print(f"    cache non écrit ({exc})")

w3 = resoudre(img_al, "alignée")
# UNE seule référence indépendante (ASTAP) pour tout le reste du diag.
WREF = astap(img_al, "référence (ASTAP)")

print("\n[4] BALAYAGE DES INDICES sur l'empilement aligné")
src = img_al if w3 is None else None
for dra, ddec in ((0.05, 0.05), (0.1, 0.1), (0.2, 0.2)):
    for dc in (0.0, 0.2, 0.5):
        w4, i4, m4 = solveur.resoudre(src, RA0 + dra, DEC0 + ddec,
                                      CHAMP * (1.0 + dc))
        print(f"    Δ({dra:+.2f},{ddec:+.2f})° ×{1.0 + dc:.1f} champ → "
              f"{'OK ' + str(round(i4['echelle_arcsec_px'], 4)) + '″/px' if w4 else 'échec : ' + m4}")
        if w4 is not None:
            break
    if w4 is not None:
        break

# ---------------------------------------------------------------------------
# [5] QUI EST FAUX : LA DÉTECTION OU LE CATALOGUE ?
# Vérité terrain = WCS d'ASTAP (indépendant) : on projette TOUT le catalogue
# Gaia du cône dans l'image et on compte combien des étoiles DÉTECTÉES par le
# solveur tombent vraiment sur une étoile de catalogue.
# ---------------------------------------------------------------------------
print("\n[5] LES 120 ÉTOILES DÉTECTÉES SONT-ELLES DE VRAIES ÉTOILES ?")
import math                                                   # noqa: E402
from avastack.catalogues import dossier_catalogues            # noqa: E402
from avastack.catalogues.telechargeur import etat_local       # noqa: E402
from avastack.catalogues.siril_cat import CatalogueSiril      # noqa: E402


def extraction_complete(ra0, dec0, champ_deg, forme, dossier=None, limmag=None):
    """MÊME extraction que `solveur._extraire_catalogue`, mais SANS le
    plafond N_CAT_MAX (c'est lui qu'on soupçonne) : tout le cône, trié."""
    d = dossier or dossier_catalogues()
    etat = etat_local(d)
    h_i, w_i = forme
    rayon = (0.5 * math.hypot(w_i, h_i) * champ_deg / w_i
             + solveur.MARGE_INDICES)
    et = CatalogueSiril(etat["astro"]).extraire(float(ra0), float(dec0),
                                                float(rayon), limmag=limmag)
    ordre = np.argsort(et["g"])
    return {k: v[ordre] for k, v in et.items()}, f"rayon {rayon:.4f}°"


def verite_terrain(wcs_ref, etiquette):
    h, w = img_al.shape[:2]
    cat, msg_cat = extraction_complete(RA0, DEC0, CHAMP, (h, w))
    xy = wcs_ref.vers_pixels(cat["ra"], cat["dec"])
    dans = ((xy[:, 0] >= 0) & (xy[:, 0] < w) & (xy[:, 1] >= 0) & (xy[:, 1] < h))
    print(f"    catalogue ({msg_cat}) : {len(cat['ra'])} étoiles dans le cône, "
          f"{int(dans.sum())} DANS l'image (G "
          f"{float(cat['g'][dans].min()):.2f} → {float(cat['g'][dans].max()):.2f})"
          )
    if int(dans.sum()) == 0:
        return
    xyd = xy[dans]
    for cap in (120, 300, 600):
        pos, _ = solveur._detecter(img_al, cap)
        if len(pos) == 0:
            continue
        dmin = np.sqrt(((pos[:, None, :] - xyd[None, :, :]) ** 2).sum(-1)).min(1)
        vraies = int((dmin <= 2.0).sum())
        print(f"    [{etiquette}] détection plafonnée à {cap} : {len(pos)} objets"
              f" — {vraies} ({100.0 * vraies / len(pos):.0f} %) sur une étoile de"
              f" catalogue (≤ 2 px), médiane de distance "
              f"{float(np.median(dmin)):.2f} px")
    # Combien d'étoiles de catalogue DANS l'image sont plus brillantes que la
    # plus faible des 120 détectées ? (comparaison des limites de détection)
    pos, _ = solveur._detecter(img_al, solveur.MAX_ETOILES_DETECTION)
    dmin = np.sqrt(((pos[:, None, :] - xyd[None, :, :]) ** 2).sum(-1)).min(1)
    ok = dmin <= 2.0
    gi = np.argmin(np.sqrt(((pos[:, None, :] - xyd[None, :, :]) ** 2)
                           .sum(-1)), 1)
    g_detectees = cat["g"][dans][gi]
    print(f"    magnitudes Gaia des {int(ok.sum())} détections VALIDES : "
          f"{float(np.min(g_detectees[ok])):.2f} → "
          f"{float(np.max(g_detectees[ok])):.2f}")
    print("    les 12 plus brillantes DÉTECTÉES (celles des triangles) :")
    for k in range(min(12, len(pos))):
        print(f"      #{k + 1:2d} ({pos[k, 0]:7.1f},{pos[k, 1]:7.1f}) à "
              f"{dmin[k]:6.2f} px de Gaia — G = {float(g_detectees[k]):.2f}")


wref = WREF
if wref is not None:
    verite_terrain(wref, "alignée")

# ---------------------------------------------------------------------------
# [6] TEST DU CORRECTIF : le plafond N_CAT_MAX est aujourd'hui appliqué AVANT
# le clip au rectangle indicatif, alors que le commentaire du code dit
# l'inverse (« CLIP au rectangle indicatif AVANT la sélection des plus
# brillantes ») — sur un champ ÉTROIT, le cône d'extraction est 2,6× plus
# large que l'image : les 400 plus brillantes du cône sont donc surtout HORS
# champ et l'appariement travaille sur une poignée d'étoiles.
# ---------------------------------------------------------------------------
print("\n[6] TEST : extraction SANS plafond avant le clip")
_orig = solveur._extraire_catalogue
solveur._extraire_catalogue = (
    lambda ra0, dec0, champ, forme, dossier=None, limmag=None:
    (extraction_complete(ra0, dec0, champ, forme, dossier, limmag)[0], ""))
for etiquette, src_img in (("NGC 7023 alignée", img_al),
                           ("M31 composite (non-régression)",
                            img_mod.load_image(r"c:\Astro\test\m31_test_solve.fits")),
                           ("M31 brute G (non-régression)",
                            img_mod.load_image(r"c:\Astro\test\m31_brute_G.fits"))):
    champ = CHAMP if "NGC" in etiquette else 2.625
    ra_i, dec_i = (RA0, DEC0) if "NGC" in etiquette else (10.68333, 41.26917)
    t0 = time.perf_counter()
    w5, i5, m5 = solveur.resoudre(src_img, ra_i, dec_i, champ)
    if w5 is None:
        print(f"    [{etiquette}] ÉCHEC — {m5}")
    else:
        print(f"    [{etiquette}] RÉSOLU en {time.perf_counter() - t0:.1f} s — "
              f"{i5['n_appariements']} appariements, rms {i5['rms_px']:.2f} px, "
              f"{i5['echelle_arcsec_px']:.4f}\"/px, méthode "
              f"« {i5['methode']} », catalogue {i5['n_etoiles_cat']} étoiles")
solveur._extraire_catalogue = _orig

print("\n[7] OÙ L'APPARIEMENT SE PERD-IL ? (recouvrement des listes top-N)")
wref7 = WREF
if wref7 is not None:
    h, w = img_al.shape[:2]
    cat_all, msg7 = extraction_complete(RA0, DEC0, CHAMP, (h, w))
    xi, eta = solveur.projection_tan(cat_all["ra"], cat_all["dec"], RA0, DEC0)
    xy7 = wref7.vers_pixels(cat_all["ra"], cat_all["dec"])
    vis = ((xy7[:, 0] >= 0) & (xy7[:, 0] < w) & (xy7[:, 1] >= 0)
           & (xy7[:, 1] < h))
    pos7, _ = solveur._detecter(img_al, solveur.MAX_ETOILES_DETECTION)
    print(f"    {msg7} — {len(cat_all['ra'])} étoiles de catalogue, "
          f"{int(vis.sum())} VISIBLES dans l'image ; {len(pos7)} détections")
    for mode, marge in (("DISQUE (le correctif mesuré)", None),
                        ("rectangle ×1.6 (ancien code)", 1.6),
                        ("rectangle ×1.0 (transposé : mauvais axe)", 1.0)):
        if marge is None:
            dans = solveur.masque_champ(xi, eta, CHAMP, (h, w))
        else:
            demi_xi = 0.5 * CHAMP * marge
            demi_eta = 0.5 * CHAMP * (h / float(w)) * marge
            dans = (np.abs(xi) <= demi_xi) & (np.abs(eta) <= demi_eta)
        idx = np.flatnonzero(dans)
        idx = idx[np.argsort(cat_all["g"][idx])]        # brillantes d'abord
        xy_rect = xy7[idx]
        print(f"    {mode} : {int(dans.sum())} étoiles dans la zone, dont "
              f"{int(vis[idx].sum())} SEULEMENT visibles (G du rect : "
              f"{cat_all['g'][idx][:1]} …) ; top-20 visible : "
              f"{int(vis[idx][:20].sum())}/20")
        for gmax in (13.0, 14.0, 15.0, 16.0):
            sel_g = cat_all["g"][idx] < gmax
            print(f"      G < {gmax:4.1f} : {int(sel_g.sum()):4d} dans le "
                  f"rectangle, dont {int((sel_g & vis[idx]).sum()):4d} visibles")
        print("      les 20 plus brillantes du rectangle :")
        for j in range(min(20, len(idx))):
            print(f"        #{j + 1:2d} G={float(cat_all['g'][idx][j]):6.2f} "
                  f"px=({xy_rect[j, 0]:8.1f},{xy_rect[j, 1]:8.1f}) "
                  f"{'VISIBLE' if vis[idx][j] else 'hors image'}")
        # recouvrement effectif : top-k détections ↔ top-k du rectangle
        for k in (12, 20, 60, 120, 400):
            if k > len(pos7) or k > len(idx):
                continue
            dmin = np.sqrt(((pos7[:k, None, :] - xy_rect[None, :k, :]) ** 2)
                           .sum(-1)).min(1)
            print(f"      k={k:4d} : {int((dmin <= 2.0).sum()):4d}/{k} "
                  f"détections appariées au catalogue (≤ 2 px)")

# ---------------------------------------------------------------------------
# [8] QUELLE REGLE DE SELECTION MARCHE ? (mesuré sur NGC 7023 ET sur M31)
# Le solveur ne retient que les N_CAT_MAX étoiles les PLUS BRILLANTES de la
# zone extraite : la zone doit donc contenir l'image (sinon ces brillantes
# sont hors champ et invisibles). L'extraction se fait autour des INDICES
# (marge 0,5° pour l'erreur de pointage), mais la SÉLECTION doit se faire
# dans la zone réellement couverte par l'image. Deux questions :
#   • disque (invariant en rotation) ou rectangle (sensible à l'orientation) ?
#   • avec ou sans la marge d'indices (0,5°, énorme devant un champ de 0,5°) ?
# ---------------------------------------------------------------------------
print("\n[8] RÈGLES DE SÉLECTION DU CATALOGUE — essais sur les 3 images")


def extraire_regle(mode, marge_geo, cap, avec_marge_indices=False, limmag=None):
    """Fabrique un `_extraire_catalogue` de remplacement (même signature)."""
    def f(ra0, dec0, champ, forme, dossier=None, limmag=None):
        et = extraction_complete(ra0, dec0, champ, forme, dossier, limmag)[0]
        h_i, w_i = forme
        xi, eta = solveur.projection_tan(et["ra"], et["dec"], ra0, dec0)
        r_vue = 0.5 * math.hypot(w_i, h_i) * champ / w_i
        demi_xi, demi_eta = (0.5 * champ * marge_geo,
                             0.5 * champ * (h_i / float(w_i)) * marge_geo)
        if mode == "rect":                       # (comportement actuel)
            dans = (np.abs(xi) <= demi_xi) & (np.abs(eta) <= demi_eta)
        elif mode == "rect+transposee":          # portrait OU paysage
            dans = (((np.abs(xi) <= demi_xi) & (np.abs(eta) <= demi_eta))
                    | ((np.abs(xi) <= demi_eta) & (np.abs(eta) <= demi_xi)))
        else:                                    # disque (invariant rotation)
            r = r_vue * marge_geo
            dans = (xi * xi + eta * eta) <= r * r
        if avec_marge_indices:
            dans &= (xi * xi + eta * eta) <= (r_vue * marge_geo
                                              + solveur.MARGE_INDICES) ** 2
        idx = np.flatnonzero(dans)[:int(cap)]
        if not len(idx):
            return None, "règle de sélection vide"
        return {k: v[idx] for k, v in et.items()}, ""
    return f


CAS_REGLE = (("NGC 7023 alignée", img_al, RA0, DEC0, CHAMP),
             ("M31 composite", img_mod.load_image(r"c:\Astro\test\m31_test_solve.fits"),
              10.68333, 41.26917, 2.625),
             ("M31 brute G", img_mod.load_image(r"c:\Astro\test\m31_brute_G.fits"),
              10.68333, 41.26917, 2.645))
_orig2 = solveur._extraire_catalogue


def essai(etiquette, fonction):
    solveur._extraire_catalogue = fonction
    lignes = []
    for nom, im, ra_i, dec_i, champ_i in CAS_REGLE:
        w, info, msg = solveur.resoudre(im, ra_i, dec_i, champ_i)
        if w is None:
            lignes.append(f"{nom[:11]} → échec")
        else:
            lignes.append(f"{nom[:11]} → OK {info['n_appariements']} app. / "
                          f"rms {info['rms_px']:.2f} px / "
                          f"{info['echelle_arcsec_px']:.4f}\"/px / cat "
                          f"{info['n_etoiles_cat']}")
    print(f"    {etiquette}")
    for l_ in lignes:
        print(f"        {l_}")
    solveur._extraire_catalogue = _orig2


essai("CODE ACTUEL (plafond 400 AVANT le clip, rectangle ×1,6)",
      _orig2)
for mode, marge_geo, cap, marg_idx in (
        ("rect", 1.6, 400, False),
        ("rect+transposee", 1.6, 400, False),
        ("rect+transposee", 2.2, 400, False),
        ("disque", 1.0, 400, False),
        ("disque", 1.3, 400, False),
        ("disque", 1.0, 800, False),
        ("disque", 1.6, 400, False),
        ("disque", 1.0, 400, True)):
    essai(f"{mode} ×{marge_geo:.1f}, plafond {cap} APRÈS le clip, "
          f"marge_indices={marg_idx}",
          extraire_regle(mode, marge_geo, cap, marg_idx))

# ---------------------------------------------------------------------------
# [9] ROBUSTESSE DE LA RÈGLE RETENUE (disque du cercle CIRCONSCRIT, ×1,0)
# La zone de sélection est centrée sur les INDICES : on mesure jusqu'où elle
# tolère une erreur de pointage (AD/Dec faux) et une erreur de champ.
# ---------------------------------------------------------------------------
print("\n[9] ROBUSTESSE : disque ×1,0, plafond 400 (indices/champ volontairement "
      "faux)")
solveur._extraire_catalogue = extraire_regle("disque", 1.0, 400, False)
for d_ra, d_dec, fac_ch in ((0.0, 0.0, 1.0), (0.05, 0.05, 1.0), (0.1, 0.1, 1.0),
                            (-0.15, 0.15, 1.0), (0.2, 0.0, 1.0),
                            (0.0, 0.0, 0.9), (0.0, 0.0, 1.1),
                            (0.0, 0.0, 0.8), (0.0, 0.0, 1.25),
                            (0.1, 0.1, 1.1)):
    w, info, msg = solveur.resoudre(img_al, RA0 + d_ra, DEC0 + d_dec,
                                    CHAMP * fac_ch)
    print(f"    Δindices ({d_ra:+.2f},{d_dec:+.2f})° · champ ×{fac_ch:.2f} → "
          f"{'OK' if w else 'échec'} {('%.4f\"/px, %d app., rms %.2f px' % (info['echelle_arcsec_px'], info['n_appariements'], info['rms_px'])) if w else msg}")
solveur._extraire_catalogue = _orig2

print("\nFIN DU DIAG")
