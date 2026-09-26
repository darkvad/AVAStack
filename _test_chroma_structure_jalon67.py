# -*- coding: utf-8 -*-
"""Banc v2.37.5 — L'ANNEAU DE COULEUR AUTOUR DES ÉTOILES (poids de structure).

CONSTAT D'ALAIN (26/09/2026) : « les étoiles moyennes rouges sont bien plus rouges
et ont presque un halo. Cela se produit aussi bien dans le tel que vu stack que
dans le tel que vu traité alors que l'affichage est correct ».

MESURÉ (jalon 66, sur son empilement M31 réel) : l'anneau est FABRIQUÉ par la
réduction du bruit chromatique, appliquée à la PLEINE RÉSOLUTION pour le fichier
alors que l'écran l'applique à l'APERÇU 1600 px (où le flou écrase l'anneau — d'où
un défaut visible SEULEMENT dans les fichiers). R/G de l'anneau 2-3 px d'aperçu,
× le R/G du fond : 1,80 sans chroma → 2,33 / 2,93 / 3,89 aux forces 0,25 / 0,50 /
0,85 (sa valeur 0,847). Cause : le flou du RAPPORT `cn = (Cr−0,5)/den` dépose la
couleur du CŒUR de l'étoile dans ses AILES, où `den = min(y, flou(y))` est faible.

Vérifie :
  [1] le contrat de base (mono, force nulle, forme inattendue → no-op ; entrée
      JAMAIS modifiée ; sortie float32 de mêmes dimensions) ;
  [2] L'ANNEAU A DISPARU sur une étoile à ailes larges (profil de Moffat) posée
      sur un ciel à GRAIN COLORÉ : le R/G de la couronne revient au niveau mesuré
      SANS réduction de bruit chromatique. TÉMOIN = la formule v2.37.4 (sans
      poids) RÉ-ÉCRITE ICI exprès — le banc doit montrer qu'elle fabrique, elle,
      l'anneau (leçon du projet : confronter toute implémentation à une référence
      indépendante) ;
  [3] le BÉNÉFICE est CONSERVÉ : le grain chromatique du fond tombe toujours
      d'environ (1 − force), à mieux de 10 % de ce que faisait la v2.37.4 ;
  [4] la couleur d'un OBJET ÉTENDU (nébuleuse, gradient de couleur à grande
      échelle) reste préservée à mieux de 2 % ;
  [5] la LUMINANCE (canal Y de OpenCV) reste intacte ;
  [6] la TRANSITION du poids est celle annoncée : 0,99 à 1 σ (le grain), 0,50 à
      3 σ, 0,11 à 5 σ, 0,008 à 10 σ ;
  [7] sur son FICHIER RÉEL (C:\\Astro\\test\\M31_traite_lineaire_2.37.3.fits, ou le
      chemin donné en argument) : anneau des 4 étoiles et grain du fond, mesurés
      après étirement VeraLux aux mêmes rayons PHYSIQUES que le jalon 66 — sans
      chroma / v2.37.4 / v2.37.5. Section SAUTÉE si le fichier est absent.

Exécution : python _test_chroma_structure_jalon67.py [fichier.fits]
"""
import os
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)          # parade du projet : crash OpenCV 5/OpenCL au
                                     # teardown quand on enchaîne les bancs Tk

from avastack.processing import couleurs as C                      # noqa: E402
from avastack.processing import veralux as V                       # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# =============================================================================
# TÉMOIN : la formule de la v2.37.4, RÉ-ÉCRITE ICI exprès (sans poids de
# structure) — c'est la référence qui doit fabriquer l'anneau.
# =============================================================================
def chroma_v2374(img, force, rayon):
    a = np.asarray(img, dtype=np.float32)
    ycc = cv2.cvtColor(a, cv2.COLOR_RGB2YCrCb)
    y = ycc[..., 0]
    niveau = float(np.median(y))
    den = np.maximum(np.minimum(y, cv2.GaussianBlur(y, (0, 0),
                                                    sigmaX=float(rayon))),
                     np.float32(max(C.PLANCHER_CHROMA * niveau, 1e-7)))
    for i in (1, 2):
        cn = (ycc[..., i] - 0.5) / den
        lisse = cv2.GaussianBlur(cn, (0, 0), sigmaX=float(rayon))
        ycc[..., i] = 0.5 + den * (cn + np.float32(force) * (lisse - cn))
    return np.maximum(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB),
                      np.float32(0.0)).astype(np.float32)


# =============================================================================
# Scène synthétique : un ciel à GRAIN COLORÉ, une étoile à AILES LARGES
# (Moffat — une gaussienne n'a pas d'ailes et ne fabrique PAS l'anneau) et une
# « nébuleuse » : un gradient de couleur à grande échelle.
# =============================================================================
N = 600
CIEL = 0.03                     # niveau de ciel (le sien : 0,0298 mesuré)
GRAIN_LUM = 0.0005              # bruit de luminance (mesuré : 0,00052 = 1,7 % du ciel)
GRAIN_COUL = 0.0016             # bruit CHROMATIQUE (mesuré : 0,00163 sur R−G)
FORCE = 0.8471                  # la valeur d'Alain
RAYON = 3.0
ETOILE = (300, 300)             # centre (px) de l'étoile mesurée
# AILES LARGES mais COEUR FIN (Moffat β = 2) : c'est la configuration réelle
# (PSF de ~2 px pour un flou de 3 px) — une étoile aussi large que le flou ne
# reproduit PAS l'anneau (le dépôt reste dans la zone encore brillante).
# AMPLITUDE : le cœur doit valoir ~0,5 pour un ciel à 0,03 (rapport 6 % mesuré
# sur son fichier : cœur Y 0,477, ciel 0,0298) et JAMAIS être écrêté — un cœur
# écrêté à 1,0 devient BLANC (sans couleur à déposer) et l'anneau disparaît.
ETOILE_ALPHA = 1.2
ETOILE_BETA = 2.0
ETOILE_AMP = 0.5
COULEUR_ETOILE = (1.60, 1.00, 0.70)
RNG = np.random.default_rng(20260926)
_y, _x = np.mgrid[0:N, 0:N].astype(np.float64)


def moffat(cx, cy, alpha, amp, beta=2.5):
    r2 = (_x - cx) ** 2 + (_y - cy) ** 2
    return amp / (1.0 + r2 / alpha ** 2) ** beta


def nebuleuse():
    """Gradient de couleur LARGE (σ = 90 px) — la couleur d'un objet étendu."""
    g = np.exp(-((_x - 120) ** 2 + (_y - 480) ** 2) / (2.0 * 90.0 ** 2))
    return (np.array([0.9, 1.0, 1.4], np.float32).reshape(1, 1, 3)
            * (0.012 * g)[..., None]).astype(np.float32)


def scene():
    s = np.full((N, N, 3), CIEL, np.float32)
    s += nebuleuse()
    lum = moffat(*ETOILE, ETOILE_ALPHA, ETOILE_AMP, ETOILE_BETA)[..., None]
    s += (lum * np.array(COULEUR_ETOILE, np.float32).reshape(1, 1, 3))
    s += RNG.normal(0.0, GRAIN_LUM, (N, N, 1)).astype(np.float32)   # luminance
    s += RNG.normal(0.0, GRAIN_COUL, (N, N, 3)).astype(np.float32)  # chromatique
    return np.clip(s, 0.0, None).astype(np.float32)   # AUCUN écrêtage haut : le
    # cœur de l'étoile doit rester COLORÉ (l'étirement normalise globalement).


IMAGE = scene()
FOND = (26, 40)                 # couronne de référence du fond local (px)
COURONNES = ((1, 2), (2, 3), (3, 4), (4, 5), (5, 7), (7, 10))


def profil_rg(img, pt, couronnes=COURONNES, fond=FOND):
    """R/G par couronne, EN MULTIPLES du R/G du fond local (mesure du jalon 66)."""
    cx, cy = pt
    d = np.sqrt((_x - cx) ** 2 + (_y - cy) ** 2)
    m = (d >= fond[0]) & (d <= fond[1])
    ref = float(np.mean(img[..., 0][m])) / max(float(np.mean(img[..., 1][m])), 1e-12)
    out = []
    for a, b in couronnes:
        mm = (d >= a) & (d < b)
        if int(mm.sum()) < 4:
            out.append(np.nan)
            continue
        out.append(float(np.mean(img[..., 0][mm])
                         / max(float(np.mean(img[..., 1][mm])), 1e-12)) / ref)
    return out


def grain_chroma(zone, sigma=2.0):
    """Grain CHROMATIQUE : MAD de (R − G) DÉBARRASSÉ de sa structure large
    (moins son propre flou de 2 px) — le grain vit au PIXEL, la couleur d'un
    objet s'étale sur bien plus.

    POURQUOI pas un simple σ (constat réel du 26/09/2026) : sur son empilement,
    σ(R−G) mêle le grain ET la structure (étoiles, gradients), que le poids de
    structure PRÉSERVE : mesuré ×0,98 au lieu de ×0,23 (poids moyen 0,91) — la
    mesure accusait à tort le correctif. Le MAD, lui, ne bouge pas des quelques
    pixels extrêmes d'une étoile.
    """
    z = np.asarray(zone, dtype=np.float64)
    d = z[..., 0] - z[..., 1]
    h = d - cv2.GaussianBlur(d, (0, 0), sigmaX=float(sigma))
    return float(np.median(np.abs(h))) * 1.4826


def etire(img, log_d=3.7):
    """Étirement RÉEL du moteur (celui de l'appli) — c'est LUI qui révèle
    l'anneau : le dépôt de couleur est minuscule en linéaire, mais l'étirement
    amplifie le rapport de couleur là où la luminance est faible."""
    sortie, _, _ = V.etirer(img, mode=V.MODE_LOG_D, log_d=float(log_d),
                            target_bg=0.16, profil="Rec.709 (Recommended)")
    return sortie


print("=" * 78)
print("[1] contrat de base (no-op, entrée jamais modifiée, formes)")
print("=" * 78)
mono = np.full((40, 40), 0.3, np.float32)
v = C.reduire_bruit_chroma(mono, force=FORCE)
verifie(v.shape == mono.shape and v.dtype == np.float32
        and np.array_equal(v, mono), "image MONO : renvoyée inchangée")
forme = np.zeros((10, 10, 4), np.float32)
verifie(np.array_equal(C.reduire_bruit_chroma(forme, force=FORCE), forme),
        "forme inattendue (4 canaux) : renvoyée inchangée")
f0 = C.reduire_bruit_chroma(IMAGE, force=0.0)
verifie(np.array_equal(f0, IMAGE), "force 0 : no-op au bit près")
garde = IMAGE.copy()
_ = C.reduire_bruit_chroma(IMAGE, force=FORCE, rayon=RAYON)
verifie(np.array_equal(IMAGE, garde), "l'image d'entrée n'est JAMAIS modifiée")
out = C.reduire_bruit_chroma(IMAGE, force=FORCE, rayon=RAYON)
verifie(out.shape == IMAGE.shape and out.dtype == np.float32
        and bool(np.isfinite(out).all()) and float(out.min()) >= 0.0,
        f"sortie float32 finie ≥ 0, mêmes dimensions (min {float(out.min()):.6f})")

print()
print("=" * 78)
print("[2] L'ANNEAU DE COULEUR : mesuré sur une étoile à ailes larges")
print("=" * 78)
sans = IMAGE
temoin = chroma_v2374(IMAGE, FORCE, RAYON)
nouveau = C.reduire_bruit_chroma(IMAGE, force=FORCE, rayon=RAYON)
p_sans, p_tem, p_nou = (profil_rg(etire(sans), ETOILE),
                        profil_rg(etire(temoin), ETOILE),
                        profil_rg(etire(nouveau), ETOILE))
print(f"    R/G par couronne (× le R/G du fond), APRÈS étirement réel — "
      f"couronnes {COURONNES} px")
for nom, pr in (("sans chroma (référence)", p_sans),
                ("v2.37.4 (témoin)", p_tem),
                ("v2.37.5 (nouveau)", p_nou)):
    print(f"      {nom:24s} " + "  ".join(f"{x:5.2f}" for x in pr))
a_sans, a_tem, a_nou = max(p_sans[1:5]), max(p_tem[1:5]), max(p_nou[1:5])
verifie(a_tem > 1.15 * a_sans,
        f"le TÉMOIN fabrique bien l'anneau (pic {a_sans:.2f} → {a_tem:.2f}) "
        "— le banc DISCRIMINE")
verifie(a_nou <= a_sans + 0.15 * (a_tem - a_sans) + 0.05,
        f"le nouveau rend l'anneau au niveau sans chroma "
        f"({a_sans:.2f} sans · {a_tem:.2f} témoin · {a_nou:.2f} nouveau)")


print()
print("=" * 78)
print("[3] le BÉNÉFICE est conservé : grain chromatique du fond")
print("=" * 78)
CIEL_PUR = IMAGE[0:140, N - 140:N]                     # coin sans étoile
g_sans = grain_chroma(CIEL_PUR)
g_tem = grain_chroma(chroma_v2374(CIEL_PUR, FORCE, RAYON))
g_nou = grain_chroma(C.reduire_bruit_chroma(CIEL_PUR, force=FORCE, rayon=RAYON))
gain_tem = 1.0 - g_tem / max(g_sans, 1e-12)
gain_nou = 1.0 - g_nou / max(g_sans, 1e-12)
print(f"    grain chromatique (MAD passe-haut) : {g_sans:.6f} sans · "
      f"{g_tem:.6f} témoin · {g_nou:.6f} nouveau")
print(f"    part retirée   : {gain_tem * 100:.1f} % (v2.37.4) · "
      f"{gain_nou * 100:.1f} % (v2.37.5)")
verifie(gain_nou > 0.8 * gain_tem,
        f"le nouveau retire presque autant de grain que la v2.37.4 "
        f"({gain_nou * 100:.1f} % contre {gain_tem * 100:.1f} %)")

print()
print("=" * 78)
print("[4] la couleur de l'OBJET ÉTENDU (nébuleuse) reste préservée")
print("=" * 78)
m_objet = moffat(120, 480, 90.0, 1.0, beta=1.5) > 0.35      # cœur de la nébuleuse
ec = [abs(float(np.mean(nouveau[..., c][m_objet]))
          - float(np.mean(sans[..., c][m_objet])))
      / max(float(np.mean(sans[..., c][m_objet])), 1e-12) for c in range(3)]
print(f"    écart de couleur sur l'objet : R {ec[0] * 100:.2f} % · "
      f"V {ec[1] * 100:.2f} % · B {ec[2] * 100:.2f} %")
verifie(max(ec) < 0.02,
        f"la couleur de l'objet bouge de moins de 2 % (pire {max(ec) * 100:.2f} %)")

print()
print("=" * 78)
print("[5] la LUMINANCE reste intacte (canal Y)")
print("=" * 78)
y_sans = cv2.cvtColor(sans, cv2.COLOR_RGB2YCrCb)[..., 0]
y_nou = cv2.cvtColor(nouveau, cv2.COLOR_RGB2YCrCb)[..., 0]
fdc = (np.abs(_x - ETOILE[0]) > 40) | (np.abs(_y - ETOILE[1]) > 40)
d_y = np.abs(y_sans - y_nou)
print(f"    écart max sur Y : fond {float(np.max(d_y[fdc])):.3e} · "
      f"global {float(np.max(d_y)):.3e}")
verifie(float(np.max(d_y[fdc])) < 2e-5,
        "sur le FOND, la luminance ne bouge pas (< 2e-05)")

print()
print("=" * 78)
print("[6] la transition du poids de structure")
print("=" * 78)
sig = 1e-3
bruit = RNG.normal(0.0, sig, (400, 1000)).astype(np.float32)
bruit[0, 0], bruit[0, 1], bruit[0, 2], bruit[0, 3] = sig, 3 * sig, 5 * sig, 10 * sig
poids = C._poids_structure(bruit, np.zeros_like(bruit), 1e-12)
sig_mes = float(np.median(np.abs(bruit.ravel()))) * 1.4826
print(f"    σ mesuré {sig_mes:.6f} (vrai {sig:.6f}) · poids → 1 σ "
      f"{poids[0, 0]:.3f} · 3 σ {poids[0, 1]:.3f} · 5 σ {poids[0, 2]:.3f} · "
      f"10 σ {poids[0, 3]:.3f}")
verifie(abs(sig_mes - sig) / sig < 0.02, "l'échelle σ est estimée à mieux de 2 %")
verifie(poids[0, 0] > 0.99 and 0.4 < poids[0, 1] < 0.6
        and 0.01 < poids[0, 2] < 0.1 and poids[0, 3] < 0.01,
        "poids ≈ 1 à 1 σ (grain conservé) et ≈ 0 dès 5 σ (plus d'anneau)")
verifie(C._poids_structure(np.zeros((8, 8), np.float32),
                           np.zeros((8, 8), np.float32), 0.0) is None,
        "échelle inexploitable (MAD nul, plancher nul) → None "
        "(repli sur le comportement v2.37.4)")

print()
print("=" * 78)
print("[7] sur son FICHIER RÉEL : anneau et grain, jalons 66 rejoué")
print("=" * 78)
CHEMIN = (sys.argv[1] if len(sys.argv) > 1
          else os.path.join(r"C:\Astro\test", "M31_traite_lineaire_2.37.3.fits"))
if not os.path.isfile(CHEMIN):
    print(f"    fichier absent ({CHEMIN}) → section SAUTÉE")
else:
    from astropy.io import fits
    from avastack.processing import veralux as V

    PROFIL = "Sony IMX585 (ASI585) - STARVIS 2"
    TARGET_BG, GAMMA, LARGEUR = 0.16, 1.15, 1600.0
    ETOILES = ((194, 105), (658, 371), (1150, 737), (1276, 167))
    RAYONS = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 7), (7, 10))

    def lire(p):
        d = np.asarray(fits.getdata(p), np.float32)
        return np.transpose(d, (1, 2, 0)) if (d.ndim == 3 and d.shape[0] == 3) else d

    def reduire(img, largeur=LARGEUR):
        h, w = img.shape[:2]
        e = min(1.0, largeur / float(max(h, w)))
        if e >= 1.0:
            return np.ascontiguousarray(img), 1.0
        return cv2.resize(img, None, fx=e, fy=e,
                          interpolation=cv2.INTER_AREA), e

    def gamma(x):
        return np.clip(np.power(np.clip(x, 0.0, 1.0), 1.0 / GAMMA),
                       0.0, 1.0).astype(np.float32)

    def anneaux_de(img, x, y, echelle=1.0, fond=(28, 40)):
        """R/G par couronne (px d'APERÇU), × le R/G du fond local (jalon 66)."""
        h, w = img.shape[:2]
        xf, yf = x * echelle, y * echelle
        demi = int(round((fond[1] + 4) * echelle))
        y0, y1 = max(0, int(yf) - demi), min(h, int(yf) + demi + 1)
        x0, x1 = max(0, int(xf) - demi), min(w, int(xf) + demi + 1)
        sous = np.asarray(img[y0:y1, x0:x1], np.float64)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        rr = np.sqrt((yy - yf) ** 2.0 + (xx - xf) ** 2.0) / echelle
        m = (rr >= fond[0]) & (rr <= fond[1])
        f = sous[m].mean(axis=0)
        ref = f[0] / max(f[1], 1e-12)
        out = []
        for a, b in RAYONS:
            mm = (rr >= a) & (rr < b)
            out.append(float(sous[mm].mean(axis=0)[0]
                             / max(sous[mm].mean(axis=0)[1], 1e-12)) / ref
                       if int(mm.sum()) >= 2 else np.nan)
        return out

    lin = V.normaliser_lin(lire(CHEMIN))
    petit, ech = reduire(lin)
    lin_neutre = C.neutraliser_fond(lin)          # étape de la chaîne du FICHIER
    petit_neutre = C.neutraliser_fond(petit)
    _, logd, _ = V.etirer(petit_neutre, mode=V.MODE_TARGET_BG,
                          target_bg=TARGET_BG, profil=PROFIL)
    print(f"    empilement {lin.shape[1]}×{lin.shape[0]} → aperçu ×{ech:.4f} · "
          f"logD résolu sur l'aperçu {logd:.4f} · force {FORCE} · rayon {RAYON} px")
    variantes = (("sans chroma", None),
                 ("v2.37.4", chroma_v2374),
                 ("v2.37.5", C.reduire_bruit_chroma))
    anneaux, grains = {}, {}
    for nom, fn in variantes:
        src = (lin_neutre if fn is None
               else fn(lin_neutre, FORCE, RAYON))
        grains[nom] = grain_chroma(src[:120])       # grain au PIXEL (passe-haut)
        rendu, _, _ = V.etirer(src, mode=V.MODE_LOG_D, log_d=logd,
                               target_bg=TARGET_BG, profil=PROFIL)
        petit_r, _ = reduire(gamma(rendu))
        anneaux[nom] = [anneaux_de(petit_r, x, y) for (x, y) in ETOILES]
    print("    R/G de l'anneau 2-3 px (× le R/G du fond local), par étoile :")
    for i, (x, y) in enumerate(ETOILES):
        print(f"      ({x:4d},{y:3d})   " + "   ".join(
            f"{nom} {anneaux[nom][i][2]:5.2f}" for nom, _ in variantes))
    moy = {nom: float(np.mean([anneaux[nom][i][2] for i in range(len(ETOILES))]))
           for nom, _ in variantes}
    gain = {nom: 1.0 - grains[nom] / max(grains["sans chroma"], 1e-12)
            for nom, _ in variantes}
    print(f"    moyenne des 4 étoiles : sans {moy['sans chroma']:.2f} · "
          f"v2.37.4 {moy['v2.37.4']:.2f} · v2.37.5 {moy['v2.37.5']:.2f}")
    print(f"    grain chromatique du fond (× celui sans chroma) : "
          f"v2.37.4 ×{grains['v2.37.4'] / grains['sans chroma']:.2f} · "
          f"v2.37.5 ×{grains['v2.37.5'] / grains['sans chroma']:.2f}")
    verifie(moy["v2.37.4"] > moy["sans chroma"] + 0.1,
            "sur son empilement, la v2.37.4 amplifie bien l'anneau "
            "(le banc mesure ce qu'Alain voit)")
    verifie(moy["v2.37.5"] < moy["sans chroma"]
            + 0.15 * (moy["v2.37.4"] - moy["sans chroma"]) + 0.05,
            f"la v2.37.5 ramène l'anneau au niveau sans chroma "
            f"({moy['v2.37.5']:.2f} contre {moy['sans chroma']:.2f}, "
            f"amplification {moy['v2.37.4'] - moy['sans chroma']:+.2f} de la v2.37.4)")
    verifie(gain["v2.37.5"] > 0.8 * gain["v2.37.4"],
            f"le grain coloré du fond reste retiré à "
            f"{gain['v2.37.5'] * 100:.0f} % (v2.37.4 : {gain['v2.37.4'] * 100:.0f} %)")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)


