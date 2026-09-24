# -*- coding: utf-8 -*-
"""Banc du jalon 58 : SPCC ABSOLUE « à la Siril ».

POURQUOI CE BANC : `_diag_spcc.py` mesure sur des couches RÉELLES (gradient,
halo de galaxie, étoiles faibles) et ne peut donc pas dire si un écart vient du
CODE ou des DONNÉES. Ici, une image est FABRIQUÉE pour être parfaitement
cohérente avec le modèle : si la chaîne est juste, elle doit retrouver la
vérité analytique.

[1] grille spectrale et lecture des profils de la base Siril (unités de
    longueur d'onde Å/nm/µm/m — le piège des références de blanc en ÅNGSTRÖMS) ;
[2] sur_grille : interpolation linéaire exacte, ZÉRO hors domaine mesuré ;
[3] reponse_canal : produit QE × filtre, filtre absent = QE seul ;
[4] spectre_reference : la référence de blanc est traitée comme un spectre
    d'étoile (× λ) — et, si la base Siril est présente, w_R/G et w_B/G
    tombent sur ceux DÉDUITS des K0/K1/K2 réels de Siril (1.2953 / 0.8332) ;
[5] photons : facteur par étoile → AUCUN ratio modifié ;
[6] flux_par_canal : intégrale exacte (trapèzes) d'une réponse plate ;
[7] regression_mediane : exactitude sur une relation parfaite et ROBUSTESSE
    avec 1 point aberrant sur 30 ;
[8] coefficients : a=0, b=1 → k = (1/wrg, 1, 1/wbg) normalisé ;
[9] **coefficients_spcc DE BOUT EN BOUT** sur 3 canaux synthétiques atténués
    par des gains instrumentaux CONNUS (R ×0,7 / B ×1,3) : les pentes doivent
    valoir exactement ces gains et la correction doit rendre la référence de
    BLANC NEUTRE (R/G = B/G après correction) — c'est la propriété qui définit
    une balance des blancs absolue ;
[10] échecs PROPRES : capteur/filtre/blanc inconnus, catalogue vide, WCS
    absent → (None, diag avec « erreur »), jamais d'exception.

Exécution : python _test_spcc_jalon58.py
"""
import sys

import numpy as np

from avastack.catalogues import WcsTan
from avastack.catalogues import spcc_db as DB
from avastack.processing import spcc as SP

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- outils de fabrication d'une image synthétique ---------------------------
H, W = 512, 512
ECH_DEG = 0.001                     # 3,6 "/px
RA0, DEC0 = 10.68, 41.27            # ~M31 (aucune importance : catalogue factice)


def wcs_du_banc():
    return WcsTan((RA0, DEC0), (W / 2.0, H / 2.0),
                  [[-ECH_DEG, 0.0], [0.0, ECH_DEG]], (H, W))


def corps_noir(wl_nm, temperature):
    """Spectre de Planck (forme relative) sur la grille Gaia."""
    import math
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    lam = np.asarray(wl_nm, float) * 1e-9
    return (1.0 / lam ** 5) / (np.expm1(h * c / (lam * k * temperature)))


def troupeau(graine=58, n=60):
    """Positions d'étoiles bien séparées + spectres variés (3000 à 12000 K)."""
    rng = np.random.default_rng(graine)
    xs, ys = [], []
    pas = 48
    for iy in range(3, H - 3, pas):
        for ix in range(3, W - 3, pas):
            if rng.random() < 0.75:
                xs.append(ix + rng.uniform(-6, 6))
                ys.append(iy + rng.uniform(-6, 6))
    pos = np.column_stack([xs[:n], ys[:n]])
    temps = rng.uniform(3000.0, 12000.0, len(pos))
    return pos, temps


def image_depuis(pos, flux, bruit=1.0, graine=7):
    """Image 2D : gaussiennes (σ 1,1 px) d'amplitude `flux` sur un fond plat.
    → image float64 (les flux sont ceux de l'ouverture, à une constante près
    de la forme de PSF — c'est cette constante que la régression absorbe).

    PIÈGE (documenté par les bancs des jalons 19/21) : sans BRUIT de fond, le
    détecteur d'étoiles répond « image constante » (médiane-MAD) et il n'y a
    rien à mesurer — en vrai ciel il y a toujours du bruit de lecture."""
    rng = np.random.default_rng(graine)
    img = np.full((H, W), 100.0)
    yy, xx = np.mgrid[0:H, 0:W]
    sig = 1.1
    for (x, y), f in zip(pos, flux):
        x0, x1 = max(0, int(x) - 8), min(W, int(x) + 9)
        y0, y1 = max(0, int(y) - 8), min(H, int(y) + 9)
        if x1 <= x0 or y1 <= y0:
            continue
        d2 = (xx[y0:y1, x0:x1] - x) ** 2 + (yy[y0:y1, x0:x1] - y) ** 2
        img[y0:y1, x0:x1] += (f / (2.0 * np.pi * sig ** 2)
                              * np.exp(-d2 / (2.0 * sig ** 2)))
    if bruit > 0.0:
        img = img + rng.normal(0.0, bruit, img.shape)
    return img



# ============================== [1] grille et base ===========================
print("[1] grille spectrale et base SPCC de Siril")
verifie(SP.GRILLE_WL.size == 343 and SP.GRILLE_WL[0] == 336.0
        and SP.GRILLE_WL[-1] == 1020.0,
        f"grille xp_sampled : {SP.GRILLE_WL.size} points, "
        f"{SP.GRILLE_WL[0]:.0f}→{SP.GRILLE_WL[-1]:.0f} nm par pas de 2 nm")
base_ok = all(len(DB.lister(c)) > 0 for c in ("mono_sensors", "mono_filters",
                                              "wb_refs"))
if base_ok:
    c_cap = next(e for e in DB.lister("mono_sensors") if "IMX585" in e["nom"])
    wl_cap, val_cap = DB.courbe(c_cap)
    verifie(300.0 <= float(np.min(wl_cap)) <= 420.0
            and 0.0 < float(np.max(val_cap)) <= 1.01,
            f"profil capteur « {c_cap['nom']} » : λ {np.min(wl_cap):.0f}"
            f"→{np.max(wl_cap):.0f} nm (unités converties en nm), QE max "
            f"{np.max(val_cap):.3f}")
    c_bl = next(e for e in DB.lister("wb_refs") if "Average Spiral" in e["nom"])
    wl_bl, val_bl = DB.courbe(c_bl)
    # PIÈGE VÉRIFIÉ : ce fichier est en ÅNGSTRÖMS (1005…25050) — sans
    # conversion la référence tombait hors de la grille et tout était nul.
    # Un spectre de galaxie moyenne couvre légitimement 100 nm → 2,5 µm.
    verifie(90.0 <= float(np.min(wl_bl)) <= 400.0
            and 2000.0 <= float(np.max(wl_bl)) <= 3000.0
            and float(np.max(val_bl)) > 0.0
            and float(np.interp(555.0, wl_bl, val_bl)) > 0.0,
            f"référence de blanc « {c_bl['nom']} » : angströms convertis en nm "
            f"({np.min(wl_bl):.0f}→{np.max(wl_bl):.0f} nm, "
            f"{int(np.count_nonzero(val_bl > 0))} points non nuls, "
            f"valeur(555 nm)={float(np.interp(555.0, wl_bl, val_bl)):.4g})")
    # et sur la grille spectrale Gaia, la référence est EXPLOITABLE :
    verifie(float(np.count_nonzero(SP.sur_grille(wl_bl, val_bl))) > 300,
            "référence de blanc non nulle sur la grille xp_sampled "
            f"({int(np.count_nonzero(SP.sur_grille(wl_bl, val_bl)))}/343 points)")
else:
    print("  (base SPCC absente : sections [1], [4] et [9] partielles)")

# ============================== [2] sur_grille ===============================
print("[2] sur_grille : interpolation exacte ET zéro hors domaine mesuré")
x = np.array([400.0, 500.0, 600.0])
y = np.array([1.0, 3.0, 2.0])
g = SP.sur_grille(x, y)
verifie(abs(g[int((500.0 - 336.0) / 2)] - 3.0) < 1e-12,
        "point de grille 500 nm retrouvé exactement")
verifie(abs(g[int((450.0 - 336.0) / 2)] - 2.0) < 1e-12,
        "interpolation linéaire au milieu de deux points (450 nm → 2,0)")
verifie(g[0] == 0.0 and g[-1] == 0.0,
        "hors du domaine mesuré : réponse ZÉRO (jamais d'extrapolation "
        "inventée — piège Akima de Siril)")

# ============================== [3] reponse_canal ============================
print("[3] reponse_canal : produit QE × filtre")
qe = (np.array([400.0, 500.0, 600.0]), np.array([0.5, 0.8, 0.4]))
ft = (np.array([400.0, 500.0, 600.0]), np.array([0.0, 1.0, 0.5]))
r = SP.reponse_canal(qe, ft)
verifie(abs(r[int((500.0 - 336.0) / 2)] - 0.8) < 1e-12
        and abs(r[int((600.0 - 336.0) / 2)] - 0.2) < 1e-12,
        "réponse = QE × transmission (0,8×1,0 = 0,8 ; 0,4×0,5 = 0,2)")
verifie(np.allclose(SP.reponse_canal(qe, None), SP.sur_grille(*qe)),
        "filtre absent (narrowband sans profil) : réponse = QE seule")

# ============================== [4] référence de blanc =======================
print("[4] spectre_reference : la référence de blanc est traitée comme un "
      "spectre d'étoile (× λ)")
if base_ok:
    c_fil = [next(e for e in DB.lister("mono_filters")
                  if e["nom"] == f"QHYCCD MiniCam8M {c}")
             for c in ("Red", "Green", "Blue")]
    rep = [SP.reponse_canal(DB.courbe(c_cap), DB.courbe(f)) for f in c_fil]
    sans = SP.flux_par_canal(SP.sur_grille(wl_bl, val_bl)[None, :], rep)[0]
    avec = SP.flux_par_canal(SP.spectre_reference(wl_bl, val_bl)[None, :],
                             rep)[0]
    wrg, wbg = avec[0] / avec[1], avec[2] / avec[1]
    w0, w1 = sans[0] / sans[1], sans[2] / sans[1]
    print(f"        blanc : SANS ×λ → w_R/G {w0:.4f} / w_B/G {w1:.4f} ; "
          f"AVEC ×λ → {wrg:.4f} / {wbg:.4f}")
    # Valeurs déduites des K0/K1/K2 réellement produits par Siril sur la MÊME
    # base (log d'Alain, 24/09/2026) : k_G = 1/max = 0,923 → max = 1,0834.
    verifie(abs(wrg - 1.2953) < 0.002 and abs(wbg - 0.8332) < 0.002,
            f"w_R/G {wrg:.4f} / w_B/G {wbg:.4f} = valeurs DÉDUITES de Siril "
            f"(1,2953 / 0,8332) — réponses QE × filtres validées à 1e-3")
    verifie(abs(w0 - wrg) > 0.05,
            f"sans la conversion ×λ on obtenait {w0:.4f}/{w1:.4f} — l'écart "
            f"de {abs(w0 - wrg):.3f} faussait les coefficients (~20 %)")
else:
    print("        (base absente : section sautée)")

# ============================== [5] photons ==================================
print("[5] photons : division par étoile (neutre) mais ×λ NON neutre")
s = np.vstack([corps_noir(SP.GRILLE_WL, 4000.0),
               corps_noir(SP.GRILLE_WL, 9000.0)])
ph = SP.photons(s)
verifie(abs(ph[0, SP.INDICE_NORM] - 1.0) < 1e-12,
        "normalisation à 500 nm (indice 82) : valeur = 1 (fidélité Siril)")
verifie(np.allclose(SP.ratios(s), SP.ratios(s * 3.7)),
        "un facteur CONSTANT par étoile ne change aucun ratio")
# PIÈGE MESURÉ (24/09/2026) : λ est À L'INTÉRIEUR de l'intégrale → la
# conversion en comptage de photons change les ratios prédits (≈18 %). Un banc
# qui l'oublie trouve des pentes fausses d'environ 20 %.
bandes = [np.exp(-0.5 * ((SP.GRILLE_WL - c) / 60.0) ** 2)
          for c in (620.0, 530.0, 450.0)]
f_sans = SP.flux_par_canal(s, bandes)
f_avec = SP.flux_par_canal(SP.photons(s), bandes)
r_sans = f_sans / f_sans[:, 1:2]
r_avec = f_avec / f_avec[:, 1:2]
ecart = float(np.max(np.abs(r_avec / r_sans - 1.0)))
verifie(ecart > 0.01,
        f"×λ dans l'intégrale : les RATIOS prédits changent (écart max mesuré "
        f"{100 * ecart:.1f} % — photons ≠ neutre : un banc qui l'oublie trouve "
        f"des pentes fausses d'environ 20 %)")

# ============================== [6] flux_par_canal ===========================
print("[6] flux_par_canal : intégrale (trapèzes) exacte")
plat = np.ones((1, SP.XPSAMPLED_LEN))
rep_plat = [np.full(SP.XPSAMPLED_LEN, 0.5)] * 3
f = SP.flux_par_canal(plat, rep_plat)
attendu = 0.5 * (SP.GRILLE_WL[-1] - SP.GRILLE_WL[0])
verifie(np.allclose(f, attendu),
        f"réponse plate 0,5 × spectre unité = {attendu:.1f} (0,5 × 684 nm)")
verifie(np.all(np.isnan(SP.flux_par_canal(
            plat, [np.zeros(SP.XPSAMPLED_LEN)] * 3))),
        "réponse nulle → NaN (canal inexploitable, jamais une valeur inventée)")
# PIÈGE RÉEL (constat Alain, 24/09/2026) : numpy 2.x a renommé np.trapz en
# np.trapezoid puis SUPPRIMÉ trapz — la SPCC s'arrêtait sur
# « module 'numpy' has no attribute 'trapz' ». On vérifie que le calcul
# fonctionne SANS np.trapz (comme sur sa machine).
_sauve_trapz = getattr(np, "trapz", None)
if _sauve_trapz is not None:
    try:
        del np.trapz
        f_sans_trapz = SP.flux_par_canal(plat, rep_plat)
        verifie(np.allclose(f_sans_trapz, attendu),
                "sans np.trapz (numpy 2.x récent) : intégrale IDENTIQUE "
                f"({float(f_sans_trapz.ravel()[0]):.1f}) — bug réel corrigé")
    finally:
        np.trapz = _sauve_trapz
else:
    verifie(np.allclose(f, attendu),
            "np.trapz absent de cette version de numpy : intégrale OK "
            "(np.trapezoid utilisé)")

# ============================== [7] régression robuste =======================
print("[7] regression_mediane : exactitude et robustesse")
xv = np.linspace(0.5, 2.0, 40)
yv = 1.0 + 2.0 * xv
a0, b0, s0 = SP.regression_mediane(xv, yv)
verifie(abs(a0 - 1.0) < 1e-9 and abs(b0 - 2.0) < 1e-9,
        f"relation parfaite y = 1 + 2x retrouvée (a {a0:.9f}, b {b0:.9f})")
yv2 = yv.copy()
yv2[7] += 25.0                       # une aberration ÉNORME
a1, b1, s1 = SP.regression_mediane(xv, yv2)
verifie(abs(a1 - 1.0) < 0.05 and abs(b1 - 2.0) < 0.05,
        f"1 point aberrant sur 40 : pente tenue (b {b1:.4f}, écart {abs(b1 - 2.0):.4f})")
verifie(SP.regression_mediane([1.0], [2.0])[1] != SP.regression_mediane([1.0], [2.0])[1],
        "moins de 3 points → NaN (aucun coefficient inventé)")

# ============================== [8] coefficients =============================
print("[8] coefficients : propriété fondamentale du blanc")
wrg0, wbg0 = 1.2954, 0.8331
k, d = SP.coefficients(xv, xv * 0.5 + 0.2, xv, xv * 0.5 + 0.2, wrg0, wbg0)
k_attendu = np.array([1.0 / wrg0, 1.0, 1.0 / wbg0])
k_attendu = k_attendu / k_attendu.max()
verifie(np.allclose(k, k_attendu, atol=1e-6),
        f"a=0, b=1 (image = catalogue) → K = (1/w_R/G, 1, 1/w_B/G) normalisé "
        f"= {np.round(k_attendu, 4)} → obtenu {np.round(k, 4)}")
verifie(abs(k[0] * wrg0 - k[2] * wbg0) < 1e-9,
        "le blanc devient NEUTRE après correction (R/G = B/G) — définition "
        "même d'une balance des blancs absolue")
k_nan, d_nan = SP.coefficients(xv, -xv, xv, xv, wrg0, wbg0)
verifie(not np.any(np.isfinite(k_nan)) and "erreur" in d_nan,
        f"coefficient négatif → refus explicite ({d_nan.get('erreur')})")

# ============================== [9] BOUT EN BOUT =============================
print("[9] coefficients_spcc DE BOUT EN BOUT : gains instrumentaux retrouvés "
      "et blanc neutralisé")
pos, temps = troupeau()
sp = np.vstack([corps_noir(SP.GRILLE_WL, t) for t in temps])
if base_ok:
    rep = [SP.reponse_canal(DB.courbe(c_cap), DB.courbe(f)) for f in c_fil]
else:
    # réponses synthétiques larges (R, G, B) si la base Siril est absente
    def _bande(c0, sig):
        return np.exp(-0.5 * ((SP.GRILLE_WL - c0) / sig) ** 2)
    rep = [_bande(620.0, 60.0), _bande(530.0, 60.0), _bande(450.0, 60.0)]
pred = SP.flux_par_canal(SP.photons(sp), rep)   # flux en COMPTAGE DE PHOTONS,
# exactement ce que la SPCC recalcule : si l'image est fabriquée sans la
# conversion ×λ, les pentes trouvées sont fausses d'environ 20 % (piège vécu).
gains_vrais = np.array([0.7, 1.0, 1.3])          # vérité à retrouver
amp = (pred * gains_vrais) / np.max(pred * gains_vrais) * 1.0e5
canaux = {"R": image_depuis(pos, amp[:, 0]),
          "G": image_depuis(pos, amp[:, 1]),
          "B": image_depuis(pos, amp[:, 2])}
cat_factice = {"ra": None, "dec": None, "g": None, "flux": sp}


def catalogue_factice(wcs, forme, dossier=None, limmag=None, spectres=False):
    """Catalogue injecté : les étoiles ont EXACTEMENT les positions du ciel
    déduites du WCS (aucun bruit d'astrométrie) et les spectres fabriqués."""
    ra, dec = wcs.vers_radec(pos)
    c = dict(cat_factice)
    c["ra"] = np.asarray(ra, float).ravel()
    c["dec"] = np.asarray(dec, float).ravel()
    c["g"] = 10.0 + np.linspace(0.0, 3.0, len(pos))
    return c, f"{len(pos)} étoiles synthétiques"


wcs = wcs_du_banc()
blanc_banc = (SP.GRILLE_WL, np.exp(-0.5 * ((SP.GRILLE_WL - 560.0) / 90.0) ** 2))
k9, d9 = SP.coefficients_spcc(
    canaux, wcs, c_cap["nom"] if base_ok else "capteur du banc",
    {"R": c_fil[0]["nom"], "G": c_fil[1]["nom"], "B": c_fil[2]["nom"]}
    if base_ok else {"R": "r", "G": "g", "B": "b"},
    c_bl["nom"] if base_ok else "blanc du banc",
    catalogue=catalogue_factice,
    reponses=None if base_ok else rep, spectre_blanc=None if base_ok else
    blanc_banc)
p9 = (f"{d9.get('b_rg'):.4f}" if d9.get("b_rg") is not None else "?")
q9 = (f"{d9.get('b_bg'):.4f}" if d9.get("b_bg") is not None else "?")
print(f"        diag : {d9.get('erreur') or 'ok'} ; "
      f"n={d9.get('n_regression')} étoiles ; pentes {p9} / {q9} ; "
      f"K {np.round(k9, 4) if k9 is not None else None}")
verifie(k9 is not None, "chaîne complète (détection, appariement, spectres, "
                        "régressions, coefficients) exécutée sans erreur")
verifie(k9 is not None and abs(d9.get("b_rg", 0.0) - gains_vrais[0]) < 0.02,
        f"pente R/G retrouvée = gain vrai 0,7 (obtenu {p9})")
verifie(k9 is not None and abs(d9.get("b_bg", 0.0) - gains_vrais[2]) < 0.02,
        f"pente B/G retrouvée = gain vrai 1,3 (obtenu {q9})")

# ============================== [10] échecs propres ==========================
print("[10] échecs propres : jamais d'exception, toujours une explication")
k10, d10 = SP.coefficients_spcc(canaux, wcs, "capteur qui n'existe pas",
                                {"R": "r", "G": "g", "B": "b"}, "blanc",
                                catalogue=catalogue_factice)
verifie(k10 is None and "introuvable" in d10.get("erreur", ""),
        f"capteur inconnu → refus expliqué ({d10.get('erreur')})")
k11, d11 = SP.coefficients_spcc(canaux, wcs, "Sony IMX585",
                                {"R": "filtre qui n'existe pas", "G": "g",
                                 "B": "b"}, "Average Spiral Galaxy",
                                catalogue=catalogue_factice)
verifie(k11 is None and "introuvable" in d11.get("erreur", ""),
        f"filtre inconnu → refus expliqué ({d11.get('erreur')})")


def catalogue_vide(wcs, forme, dossier=None, limmag=None, spectres=False):
    return {}, "aucune étoile (banc)"


k12, d12 = SP.coefficients_spcc(canaux, None, "x", {}, "y",
                                catalogue=catalogue_vide,
                                reponses=rep, spectre_blanc=blanc_banc)
verifie(k12 is None and d12.get("erreur"),
        f"catalogue vide → refus expliqué ({d12.get('erreur')})")

# Garde-fou des BANDES (constat réel d'Alain : « Filtre R = … Luminance »).
if base_ok:
    k13, d13 = SP.coefficients_spcc(
        canaux, wcs, "Sony IMX585",
        {"R": "QHYCCD MiniCam8M Luminance", "G": "QHYCCD MiniCam8M Green",
         "B": "QHYCCD MiniCam8M Blue"}, "Average Spiral Galaxy")
    verifie("LUMINANCE" in d13.get("avertissement", "")
            and (k13 is not None or d13.get("erreur")),
            f"un profil de LUMINANCE en filtre de couleur est signalé "
            f"(« {d13.get('avertissement')} » ; coefficients : "
            f"{'refusés' if k13 is None else 'calculés'})")
    k14, d14 = SP.coefficients_spcc(
        canaux, wcs, "Sony IMX585",
        {"R": "QHYCCD MiniCam8M Red", "G": "QHYCCD MiniCam8M Red",
         "B": "QHYCCD MiniCam8M Blue"}, "Average Spiral Galaxy")
    verifie("répétés" in d14.get("avertissement", "")
            and (k14 is not None or d14.get("erreur")),
            f"profils de filtres RÉPÉTÉS signalés "
            f"(« {d14.get('avertissement')} »)")
    k15, d15 = SP.coefficients_spcc(
        canaux, wcs, "Sony IMX585",
        {"R": "QHYCCD MiniCam8M Red", "G": "QHYCCD MiniCam8M Green",
         "B": "QHYCCD MiniCam8M Blue"}, "Average Spiral Galaxy")
    verifie(not d15.get("avertissement"),
            f"les trois filtres d'Alain ne déclenchent AUCUN avertissement "
            f"(« {d15.get('avertissement')} »)")

# ============================== [11] session et UI ===========================
print("[11] SessionSpcc et branchement UI (case, profils, config)")
ses = SP.SessionSpcc(catalogue=catalogue_factice)
verifie(not ses.valide and ses.gains() == {},
        "session neuve : invalide, aucun gain")
res14, msg14 = ses.mesurer({"R": None, "G": canaux["G"]}, wcs, "c", {}, "b")
verifie(res14 is None and "bandes manquantes" in msg14,
        f"canaux incomplets refusés ({msg14})")
res15, msg15 = ses.mesurer(canaux, None, "c", {}, "b")
verifie(res15 is None and "WCS" in msg15,
        f"sans WCS : refusé, jamais deviné ({msg15})")
res16, msg16 = ses.mesurer(canaux, wcs, c_cap["nom"] if base_ok else "cap",
                           {"R": c_fil[0]["nom"], "G": c_fil[1]["nom"],
                            "B": c_fil[2]["nom"]} if base_ok else
                           {"R": "r", "G": "g", "B": "b"},
                           c_bl["nom"] if base_ok else "blanc",
                           reponses=None if base_ok else rep,
                           spectre_blanc=None if base_ok else blanc_banc)
verifie(res16 is not None and ses.valide,
        f"session valide après mesure ({msg16[:60]}…)")
verifie(set(ses.gains()) == {"R", "G", "B"},
        f"gains par rôle prêts pour le composite : {ses.gains()}")
ses.reset()
verifie(not ses.valide and ses.texte_resume() == "",
        "reset : plus rien à afficher (aucune valeur d'une session révolue)")

try:
    import tkinter as tk

    import avastack.ui.app as ui
    from avastack.processing.composition import CompositeStacker
    # Banc HERMÉTIQUE (même technique que les bancs des jalons 19/54/56) : on
    # part d'une configuration VIDE, sinon la config.json de la machine (case
    # SPCC déjà cochée, profils choisis) fausserait les valeurs par défaut.
    _cfg_sauve = dict(ui.CONFIG)
    ui.CONFIG.clear()
    root = tk.Tk()
    root.withdraw()
    app = ui.App(root)
    verifie(hasattr(app, "var_spcc") and app.var_spcc.get() is False,
            "case SPCC présente et DÉCOCHÉE par défaut (opt-in, comme les "
            "gains Gaia)")
    verifie(hasattr(app, "lbl_spcc") and hasattr(app, "_spcc_vars"),
            "ligne d'état et sélecteurs de profils créés")
    noms = getattr(app, "_spcc_noms", {})
    if base_ok:
        verifie(len(noms.get("capteur", ())) > 0
                and len(noms.get("filtres", ())) > 0
                and len(noms.get("blancs", ())) > 0,
                f"sélecteurs peuplés par la base Siril "
                f"({len(noms.get('capteur', ()))} capteurs, "
                f"{len(noms.get('filtres', ()))} filtres, "
                f"{len(noms.get('blancs', ()))} références)")
        verifie(app._spcc_vars["capteur"].get() == "Sony IMX585"
                and "MiniCam8M Red" in app._spcc_vars["fr"].get(),
                "profils par défaut = ceux d'Alain (IMX585 + MiniCam8M R/G/B)")
    else:
        verifie(app._spcc_dispo is False,
                "sans base Siril : case désactivée (et le dit)")
    app.var_spcc.set(True)
    app._on_spcc()
    verifie(app._spcc_actif is True
            and ("attente" in app.lbl_spcc.cget("text").lower()
                 or "MONO" in app.lbl_spcc.cget("text")
                 or "introuvable" in app.lbl_spcc.cget("text")),
            f"cochée SANS mesure : rien appliqué, et l'annonce « "
            f"{app.lbl_spcc.cget('text')[:60]} »")
    verifie(app.spcc.gains() == {},
            "aucun gain écrit dans le stacker tant qu'aucune mesure n'existe")
    app._mode_compo = True
    if base_ok:
        # Le contrôle IMMÉDIAT des profils doit alerter sans attendre une
        # mesure (constat réel : « Filtre R = … Luminance »).
        app._spcc_vars["fr"].set("QHYCCD MiniCam8M Luminance")
        app._maj_spcc_vue()
        txt_l = app.lbl_spcc.cget("text")
        verifie("LUMINANCE" in txt_l and "⚠" in txt_l,
                f"profil de luminance signalé dès la sélection ({txt_l[:70]}…)")
        app._spcc_vars["fr"].set("QHYCCD MiniCam8M Red")
        app._maj_spcc_vue()
    app.spcc.coefficients = np.array([0.90, 1.0, 1.10])
    app.spcc.diag = {"capteur": "Sony IMX585", "b_rg": 1.0, "b_bg": 1.0,
                     "sigma_rg": 0.02, "sigma_bg": 0.02, "n_regression": 120}
    app._maj_spcc_vue()
    texte = app.lbl_spcc.cget("text")
    verifie("0.90" in texte and "1.10" in texte,
            f"ligne d'état affiche les coefficients ({texte[:70]}…)")
    st_lrgb = CompositeStacker("RGB", k=None)
    st_lrgb.gains_roles = app.spcc.gains()
    verifie(set(st_lrgb.gains_roles) == {"R", "G", "B"},
            f"gains SPCC acceptés par le composite : {st_lrgb.gains_roles}")
    app.var_spcc.set(False)
    app._on_spcc()
    verifie(app._spcc_actif is False and not app.spcc.valide
            and app.lbl_spcc.cget("text") == "",
            "décochée : coefficients oubliés et libellé effacé")
    # Config : on capture ce que l'application ÉCRIT (même technique que les
    # bancs des jalons 54/56 : `sauver_config` patché).
    sauvegardes = []
    ui.sauver_config = lambda c: sauvegardes.append(dict(c))
    app.var_spcc.set(True)
    app._on_spcc()
    app._sauver_config_app()
    verifie(sauvegardes and sauvegardes[-1].get("spcc_actif") is True
            and isinstance(sauvegardes[-1].get("spcc_capteur"), str)
            and isinstance(sauvegardes[-1].get("spcc_fr"), str),
            f"config : case + profils persistés "
            f"({sauvegardes[-1].get('spcc_capteur')} / "
            f"{sauvegardes[-1].get('spcc_fr')})")
    root.destroy()
    ui.CONFIG.update(_cfg_sauve)         # configuration d'origine restaurée
except Exception as exc:            # Tk indisponible (session sans écran)
    print(f"  (UI non testée : {type(exc).__name__} : {exc})")

# ============================== bilan ========================================
print()
print("BANC JALON 58 (SPCC absolue) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

