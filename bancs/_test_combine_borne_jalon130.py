# -*- coding: utf-8 -*-
"""Banc du JALON 130 (v2.82.0) — LE COMBINE LRGB EST BORNÉ (halos et points colorés).

Défaut MESURÉ le 16/10/2026 sur la sortie réelle (M33, composition LRGB+Ha,
441 frames, v2.81.0) : « anneaux sombres autour des étoiles », « points colorés
partout ». Cause NOMMÉE par rejeu de 4 VRAIES COUCHES EMPILÉES
(`_diag_combine_bornes_130`, hors dépôt) : `composer()` faisait
`rgb *= L/luma` avec une garde ABSOLUE de 1e-6, sans borne — le rapport allait
de **−41,8 à 15 278** et 0,257 % des pixels étaient NÉGATIFS. Trois causes
STRUCTURELLES (elles ne dépendent pas du nombre de frames) :
  ① `normaliser()` prend p0,25 pour POINT NOIR et ne clippe pas → 0,25 % des
     pixels de CHAQUE rôle sont négatifs (L négatif ⇒ point NOIR ; `lum`
     négative ⇒ l'ancienne garde rendait 1,0, soit un point 2,5× trop CLAIR au
     ciel, où le rapport vaut ~0,4) ;
  ② `lum` frôlant zéro (bord de recalage) ⇒ rapport jusqu'à 15 278 ;
  ③ aucune borne haute (p99,9 mesuré = 4,66).

Ce banc vérifie :
  [1] LE DÉFAUT est REPRODUIT à l'ÉCHELLE RÉELLE (ciel 0,2 de l'amplitude /
      cœur ~25 / rapport de ciel ~0,4 — l'échelle mesurée sur M33 ; la scène
      « banc 67 » ne reproduit ni le halo ni les extrêmes) ;
  [2] LES BORNES tiennent : le rapport rendu par `_ratio_combine()` ne sort
      jamais de [RATIO_L_MIN, RATIO_L_MAX], et le composite reste sous
      RATIO_L_MAX × les canaux d'entrée ;
  [3] LES TROIS PIÈGES (lum ≈ 0, L < 0, lum < 0) : plus un seul « point » —
      le pixel prend la moyenne LOCALE de son voisinage ;
  [4] CAS NOMINAL INCHANGÉ AU BIT : sans pixel hors domaine ni rapport hors
      bornes, `composer()` est EXACTEMENT la formule d'avant ;
  [5] LE PLANCHER EST RELATIF (× 10⁴ sur toute la scène → même domaine) ;
  [6] NON-RÉGRESSION du 117c : le halo d'étoile reste traité par le lissage,
      et le plafond ne touche PAS le halo légitime (~3) ;
  [7] GARDE-FOUS : image minuscule, scène plate, zone entièrement hors domaine
      (bord noir), canal vide, L synthétisé, composite sans luminance.

Exécution : python bancs/_test_combine_borne_jalon130.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing import composition as compo
from avastack.processing.composition import (PLANCHER_RATIO_FRAC,
                                             RATIO_L_MAX, RATIO_L_MIN,
                                             _amplitude, _luma,
                                             _ratio_combine, composer)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


ROLES = ("L", "R", "G", "B")
SIGMA_BRUIT = 0.002
# 5 étoiles de flux décroissant (positions fixes, identiques dans les 4 rôles) :
# le pic est le MÊME dans L et dans le RGB, seule la PSF diffère (σ 1,6 / 1,3).
ETOILES = ((128, 128, 0.80), (40, 50, 0.80), (90, 180, 0.55),
           (200, 60, 0.65), (150, 200, 0.35), (220, 230, 0.28))
# Les trois PIÈGES du défaut (coordonnées fixes, loin des étoiles).
PIEGE_A = (128, 40)     # `lum` ≈ 2e-4 (trou dans le RGB) → ancien rapport 1000
PIEGE_B = (128, 90)     # L < 0 (sous son point noir) → rapport NÉGATIF
PIEGE_C = (128, 150)    # `lum` < 0 → l'ancienne garde rendait 1,0
BORD = (2, 8)           # BORD de recalage : `lum` = 1,1e-6 → ancien rapport 1e5


def scene(forme=(256, 256), graine=7, bord=True):
    """Scène LRGB à l'ÉCHELLE RÉELLE, celle MESURÉE le 16/10/2026 sur
    l'empilement M33 (`_diag_echelle_130`, hors dépôt) :
      · bruit σ = 0,002 · nébulosité basse fréquence de pic 8 σ (c'est elle qui
        fixe p99,7 : la structure LARGE atteint 1,5 × le ciel, comme le disque
        de M33) ⇒ amplitude (p99,7 − p0,25) ≈ 10,5 σ, donc le point noir p0,25
        tombe à 2,8 σ sous le ciel et ~0,25 % des pixels sont NÉGATIFS (c'est
        le défaut STRUCTUREL) ;
      · ciel RGB 0,20 · ciel L 0,08 : le RAPPORT L/luma au ciel vaut donc
        ~0,4 (mesuré : 0,406) — c'est ce qui rend le repli différent de 1,0 ;
      · étoiles de pic ~0,8 (≈ 28 × l'amplitude, comme les cœurs mesurés), PSF
        plus LARGE dans L (σ 1,6 contre 1,3) = le mismatch du jalon 117c.
    Une scène « banc 67 » (ciel 0,03 / cœur 0,5) ne reproduit RIEN de tout cela.
    Plus 12 pixels de BORD (posés dans l'espace NORMALISÉ, cf. `couches()`) :
    le rapport y montait à ~7e4 avec l'ancienne garde absolue."""
    rng = np.random.default_rng(graine)
    h, w = forme
    yy, xx = np.mgrid[0:h, 0:w]
    g = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 18.0)
    base = (0.016 * g / max(float(g.max()), 1e-9)).astype(np.float32)
    canaux = {}
    for role in ROLES:
        ciel = 0.08 if role == "L" else 0.20
        sigma = 1.6 if role == "L" else 1.3
        img = (ciel + base
               + rng.normal(0.0, SIGMA_BRUIT, (h, w))).astype(np.float32)
        for (y, x, a) in ETOILES:
            img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                               / (2.0 * sigma ** 2))).astype(np.float32)
        canaux[role] = img
    return canaux


def couches(pieges=True):
    """Couches NORMALISÉES par rôle (bornes auto) — l'état dans lequel
    `composer()` les utilise. p0,25 y vaut 0 PAR CONSTRUCTION : les négatifs
    STRUCTURELS du réel (0,25 % des pixels de chaque rôle) sont donc présents
    sans être posés. Les trois PIÈGES sont posés DANS cet espace normalisé, à
    des valeurs qu'un pixel aberrent atteint vraiment (cf. mesures du 16/10)."""
    n = normes(scene())
    if pieges:
        # A) trou dans le RGB (G et B négatifs) → `lum` = 2e-4, 4 ordres sous le
        #    ciel, avec R = 0,5 : l'ancien rapport valait 1000 (point ×6250).
        n["R"][PIEGE_A], n["G"][PIEGE_A], n["B"][PIEGE_A] = 0.5, -0.24, -0.074
        n["L"][PIEGE_A] = 0.20
        n["L"][PIEGE_B] = -0.02        # B) L sous son point noir
        n["G"][PIEGE_C] = -0.30        # C) `lum` devient NÉGATIVE
        for role in ("R", "G", "B"):   # D) BORD de recalage : `lum` frôle zéro
            n[role][BORD[0], BORD[1]:BORD[1] + 12] = 1.1e-6
    return n


def ratio_ancien(L, lum):
    """La formule d'AVANT le 117c/jalon 130 : `rgb *= L/luma`, garde ABSOLUE."""
    return np.where(lum > 1e-6, L / np.maximum(lum, 1e-6), 1.0)


def normes(canaux, bornes=None):
    """Les couches NORMALISÉES par rôle exactement comme `composer()` (bornes
    auto par défaut → les négatifs STRUCTURELS sous p0,25 sont là)."""
    n = {}
    for role in ROLES:
        lo, hi = (bornes or {}).get(role) or (None, None)
        n[role] = compo.normaliser(np.asarray(canaux[role], np.float32),
                                   lo, hi)
    return n


def compose(n, ratio):
    """Composite comme `composer()` : rgb × ratio."""
    rgb = np.stack([n["R"], n["G"], n["B"]], axis=-1)
    return (rgb * ratio[..., None]).astype(np.float32)


def voisinage(img, xy, r=4):
    """Médiane d'une fenêtre (2r+1)² autour de `xy`, SANS le centre — le niveau
    « normal » du pixel, c'est-à-dire ce qu'un « point » n'a pas."""
    y, x = xy
    h, w = img.shape[:2]
    y0, y1 = max(0, y - r), min(h, y + r + 1)
    x0, x1 = max(0, x - r), min(w, x + r + 1)
    fen = np.asarray(img[y0:y1, x0:x1], np.float32).copy()
    fen[y - y0, x - x0] = np.nan
    with np.errstate(invalid="ignore"):
        val = np.nanmedian(fen.reshape(-1, fen.shape[-1]), axis=0)
    return np.asarray(val, np.float64)


def ecart_au_voisinage(comp, xy):
    """Rapport du pixel à son voisinage, canal par canal : 1,0 = le pixel est
    NORMAL, 1e3 = un point 1000× trop clair, 0 = un point noir."""
    v = voisinage(comp, xy)
    p = np.asarray(comp[xy[0], xy[1]], np.float64)
    rap = p / np.maximum(np.abs(v), 1e-12)
    return float(np.nanmax(rap)), float(np.nanmin(rap))


def teinte(comp):
    """Luminance moyenne du composite (pour situer un « point »)."""
    return float(np.median(_luma(comp))) if comp.ndim == 3 else float(
        np.median(comp))


print("=" * 78)
print("[1] LE DÉFAUT, à l'ÉCHELLE RÉELLE (aucun piège posé : il vient du CIEL)")
brut = scene()
n_auto = normes(brut)
rgb_auto = np.stack([n_auto["R"], n_auto["G"], n_auto["B"]], axis=-1)
lum_auto = _luma(rgb_auto)
L_auto = n_auto["L"]
amp_lum, amp_L = _amplitude(lum_auto), _amplitude(L_auto)
seuil_lum = max(PLANCHER_RATIO_FRAC * amp_lum, 1e-6)
seuil_L = max(PLANCHER_RATIO_FRAC * amp_L, 1e-6)
hors = (lum_auto <= seuil_lum) | (L_auto <= seuil_L)
r_anc = ratio_ancien(L_auto, lum_auto)
c_anc = compose(n_auto, r_anc)
c_fix = np.asarray(composer(brut, "LRGB", sigma_l=0.0), np.float32)
ciel_lum = float(np.median(lum_auto))
ciel_L = float(np.median(L_auto))
bande = (lum_auto > 0.15) & (lum_auto < 0.25)
print(f"  ÉCHELLE : ciel(lum)={ciel_lum:.4f} · amp={amp_lum:.4f} = "
      f"{amp_lum / SIGMA_BRUIT:.1f} σ (réel 10,5) · ciel(L)={ciel_L:.4f} · "
      f"rapport au ciel={np.median(r_anc[bande]):.3f} (réel 0,406) · "
      f"cœur max={lum_auto.max():.1f} = "
      f"{lum_auto.max() / max(ciel_lum, 1e-9):.1f} × le ciel (réel 133)")
amp_brut = _amplitude(brut["G"])       # amplitude en VALEURS BRUTES (donc vs σ)
print(f"  rapport ANCIEN : min={r_anc.min():.4g} max={r_anc.max():.6g} · "
      f"NÉGATIFS={int((r_anc < 0).sum())} px "
      f"({100.0 * (r_anc < 0).mean():.4f} %) · hors domaine="
      f"{100.0 * hors.mean():.4f} %")
print(f"  composite ANCIEN : max={c_anc.max():.5g} · éteints(≤0)="
      f"{100.0 * (c_anc <= 0).mean():.4f} %")
print(f"  composite BORNÉ  : max={c_fix.max():.5g} · éteints(≤0)="
      f"{100.0 * (c_fix <= 0).mean():.4f} %")
verifie(0.05 <= ciel_lum <= 0.5,
        f"échelle RÉELLE reproduite : le ciel est à {100 * ciel_lum:.1f} % de "
        "l'amplitude (réel 20-27 % — l'échelle du banc 67 n'a rien de tel)")
verifie(amp_brut / SIGMA_BRUIT <= 20.0,
        f"amplitude brute = {amp_brut / SIGMA_BRUIT:.1f} σ (réel 10,5) → p0,25 "
        "est un VRAI point noir, pas une convention")
verifie(abs(np.median(r_anc[bande]) - 0.4) < 0.15,
        f"le rapport L/luma au CIEL vaut {np.median(r_anc[bande]):.3f} (réel "
        "0,406) — c'est ce qui rend le repli différent de 1,0")
verifie(r_anc.min() < 0.0,
        f"le rapport ANCIEN passe NÉGATIF (min {r_anc.min():.3f})")
verifie((r_anc < 0).mean() > 5e-4,
        f"…et ce n'est pas un accident isolé : {100.0 * (r_anc < 0).mean():.3f} % "
        "des pixels (p0,25 de CHAQUE rôle est négatif par construction)")
verifie(r_anc.max() > 2.0 * RATIO_L_MAX,
        f"le rapport ANCIEN dépasse largement le plafond (max {r_anc.max():.4g} "
        f"pour un plafond de {RATIO_L_MAX} — jusqu'à 15 278 sur les couches "
        "réelles, marges de recalage comprises)")
verifie(c_fix.max() <= RATIO_L_MAX * float(rgb_auto.max()) * 1.001,
        f"le composite BORNÉ reste sous {RATIO_L_MAX} × les canaux d'entrée "
        f"(max {c_fix.max():.4g}, plafond "
        f"{RATIO_L_MAX * float(rgb_auto.max()):.4g})")
verifie((c_fix <= 0).mean() < (c_anc <= 0).mean(),
        f"moins de pixels ÉTEINTS : {100.0 * (c_fix <= 0).mean():.4f} % contre "
        f"{100.0 * (c_anc <= 0).mean():.4f} % (le combine n'en fabrique plus)")

print()
print("[2] LES BORNES : le rapport ne sort JAMAIS de "
      f"[{RATIO_L_MIN} ; {RATIO_L_MAX}]")
r_fix = _ratio_combine(L_auto, lum_auto)
print(f"  plancher={seuil_lum:.3e} (lum) / {seuil_L:.3e} (L) = "
      f"{PLANCHER_RATIO_FRAC:g} × l'amplitude du rôle · hors domaine="
      f"{100.0 * hors.mean():.4f} % ({int(hors.sum())} px)")
print(f"  rapport BORNÉ : min={r_fix.min():.6g} max={r_fix.max():.6g} · "
      f"au plafond={int((r_fix >= RATIO_L_MAX - 1e-6).sum())} px")
verifie(float(r_fix.min()) >= RATIO_L_MIN and float(r_fix.max()) <= RATIO_L_MAX,
        f"rapport dans [{RATIO_L_MIN} ; {RATIO_L_MAX}] "
        f"(min {r_fix.min():.3g}, max {r_fix.max():.3g})")
verifie(0 < hors.mean() < 0.05,
        f"le domaine est LARGE et la correction MARGINALE : "
        f"{100.0 * hors.mean():.3f} % des pixels hors domaine")
verifie(np.array_equal(compose(n_auto, r_fix),
                       np.asarray(composer(brut, "LRGB", sigma_l=0.0),
                                  np.float32)),
        "le composite du banc reproduit `composer()` AU BIT (le banc ne "
        "mesure pas autre chose que le code livré)")

print()
print("[3] LES TROIS PIÈGES (la queue pathologique du défaut) : aucun « point »")
n_p = couches(pieges=True)
rgb_p = np.stack([n_p["R"], n_p["G"], n_p["B"]], axis=-1)
lum_p = _luma(rgb_p)
c_anc_p = compose(n_p, ratio_ancien(n_p["L"], lum_p))
c_fix_p = compose(n_p, _ratio_combine(n_p["L"], lum_p))
print(f"  (le ciel du composite vaut {teinte(c_fix_p):.4f} — un « point » est un "
      "pixel qui s'en écarte de plus de quelques fois)")
for nom, xy in (("A) `lum` ≈ 2e-4 (trou RGB)", PIEGE_A),
                ("B) L < 0 (sous le point noir)", PIEGE_B),
                ("C) `lum` < 0 (négative)", PIEGE_C)):
    a = ecart_au_voisinage(c_anc_p, xy)
    f = ecart_au_voisinage(c_fix_p, xy)
    print(f"  {nom:32s} pixel / voisinage : ANCIEN max={a[0]:10.3f} "
          f"min={a[1]:8.3f}  ·  BORNÉ max={f[0]:6.3f} min={f[1]:6.3f}")
m_a_anc, m_a_fix = ecart_au_voisinage(c_anc_p, PIEGE_A), ecart_au_voisinage(c_fix_p, PIEGE_A)
verifie(m_a_anc[0] > 100.0,
        f"A) l'ancien combine fabrique un point ÉNORME "
        f"(×{m_a_anc[0]:.0f} son voisinage)")
verifie(m_a_fix[0] < 5.0,
        f"A) borné : le pixel prend le niveau de son voisinage "
        f"(×{m_a_fix[0]:.2f})")
m_b_anc, m_b_fix = ecart_au_voisinage(c_anc_p, PIEGE_B), ecart_au_voisinage(c_fix_p, PIEGE_B)
verifie(m_b_anc[1] < 0.05,
        f"B) l'ancien combine fabrique un point NÉGATIF (×{m_b_anc[1]:.3f}), "
        "c'est-à-dire NOIR après écrêtage")
verifie(m_b_fix[0] < 5.0 and m_b_fix[1] > 0.2,
        f"B) borné : le pixel est AU NIVEAU de son voisinage "
        f"(×{m_b_fix[0]:.2f} / ×{m_b_fix[1]:.2f} — la dispersion résiduelle est "
        "le bruit LOCAL du rapport, ~50 % au ciel, pas un point)")
m_c_anc, m_c_fix = ecart_au_voisinage(c_anc_p, PIEGE_C), ecart_au_voisinage(c_fix_p, PIEGE_C)
verifie(m_c_anc[0] > 2.0,
        f"C) l'ancienne garde (`lum > 1e-6` → 1,0) donnait un point "
        f"×{m_c_anc[0]:.2f} plus CLAIR que son voisinage")
verifie(m_c_fix[0] < 5.0,
        f"C) borné : ×{m_c_fix[0]:.2f} — plus de point clair (le canal G reste "
        "négatif : c'est la donnée du pixel, pas le combine)")
verifie(np.array_equal(np.asarray(composer(couches(pieges=True), "LRGB",
                                           normaliser_canal=False, sigma_l=0.0),
                                  np.float32), c_fix_p),
        "avec pièges : `composer()` = le composite du banc, AU BIT")
# D) le BORD de recalage : le RAPPORT partait à ~1e5 (cause ② du défaut) — il
# prend désormais la moyenne locale (le pixel lui-même ne changeait pas : le
# composite valait déjà « L », donc la preuve est sur le RAPPORT).
r_bord_anc = ratio_ancien(n_p["L"], lum_p)[BORD[0], BORD[1]]
r_bord_fix = _ratio_combine(n_p["L"], lum_p)[BORD[0], BORD[1]]
print(f"  D) BORD (`lum` = 1,1e-6)          rapport : ANCIEN={r_bord_anc:.6g} "
      f"· BORNÉ={r_bord_fix:.4f}")
verifie(r_bord_anc > 1000.0,
        f"D) l'ancien rapport explose sur un bord de recalage "
        f"({r_bord_anc:.3g} — mesuré 15 278 sur les vraies couches)")
verifie(r_bord_fix < 5.0,
        f"D) borné : {r_bord_fix:.3f} = la moyenne locale du voisinage")

print()
print("[4] CAS NOMINAL : aucune borne ne mord → INCHANGÉ AU BIT")
B01 = {r: (0.0, 1.0) for r in ROLES}
propre = scene(graine=11)              # ciel 0,2 : AUCUN pixel négatif ici
n_pro = normes(propre, B01)            # bornes figées → normalisation neutre
lum_pro = _luma(np.stack([n_pro["R"], n_pro["G"], n_pro["B"]], axis=-1))
r_anc_pro = ratio_ancien(n_pro["L"], lum_pro)
obtenu = np.asarray(composer(propre, "LRGB", bornes=B01, sigma_l=0.0),
                    np.float32)
print(f"  rapport ancien sur cette scène : min={r_anc_pro.min():.3f} "
      f"max={r_anc_pro.max():.3f} (plafond {RATIO_L_MAX}, plancher du domaine "
      f"{max(PLANCHER_RATIO_FRAC * _amplitude(lum_pro), 1e-6):.2e})")
verifie(float(r_anc_pro.min()) > 0.0 and float(r_anc_pro.max()) < RATIO_L_MAX,
        "scène PROPRE : aucun rapport hors bornes ni négatif")
verifie(np.array_equal(obtenu, compose(n_pro, r_anc_pro)),
        "AUCUN pixel hors domaine → `composer()` est EXACTEMENT la formule "
        "d'avant (division seule), au bit")
verifie(np.array_equal(obtenu, compose(n_pro, _ratio_combine(n_pro["L"], lum_pro))),
        "…et `_ratio_combine()` passe bien par le chemin nominal")

print()
print("[5] LE PLANCHER EST RELATIF À L'ÉCHELLE DU RÔLE (plus de garde 1e-6)")
n_grand = {r: (c * 1e4).astype(np.float32) for r, c in n_p.items()}
lum_grand = _luma(np.stack([n_grand["R"], n_grand["G"], n_grand["B"]], -1))
r1 = _ratio_combine(n_p["L"], lum_p)
r2 = _ratio_combine(n_grand["L"], lum_grand)
print(f"  échelle ×1 : rapport min={r1.min():.4g} max={r1.max():.4g} · "
      f"×10⁴ : min={r2.min():.4g} max={r2.max():.4g}")
verifie(np.allclose(r1, r2, rtol=1e-3, atol=1e-6),
        "toute la scène × 10⁴ → MÊME rapport (le plancher suit l'amplitude du "
        "rôle, là où la garde 1e-6 absolue changeait de comportement)")
nt = np.asarray([1e-3, 2e-3, -1e-4], np.float32)
lt = np.asarray([1e-3, 2e-5, 5e-5], np.float32)
r_1d = _ratio_combine(lt, nt)
verifie(np.all(np.isfinite(r_1d))
        and float(r_1d.min()) >= RATIO_L_MIN and float(r_1d.max()) <= RATIO_L_MAX,
        "entrée 1-D (hors image) : bornée et FINIE, aucune exception")

print()
print("[6] NON-RÉGRESSION DU 117c — le halo d'étoile reste traité par le lissage")

def bande_anneau(comp, r_lo, r_hi):
    h, w = comp.shape[:2]
    m = _luma(comp)
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot(yy - h // 2, xx - w // 2)
    return m[(rr >= r_lo) & (rr <= r_hi)].mean()

def rapport_anneau_coeur(comp, r_min=3.5, r_max=4.5):
    """Rapport (anneau / cœur) de l'étoile CENTRALE — la métrique du banc 117c."""
    m = _luma(comp)
    coeur = float(m[m.shape[0] // 2, m.shape[1] // 2])
    return float(bande_anneau(comp, r_min, r_max) / coeur) if coeur > 0 else float("nan")

n_c = couches(pieges=False)
rgb_c = np.stack([n_c["R"], n_c["G"], n_c["B"]], axis=-1)
rgb_seul = np.asarray(composer({"R": n_c["R"], "G": n_c["G"], "B": n_c["B"]},
                               "RGB", normaliser_canal=False), np.float32)
brut_c = np.asarray(composer(n_c, "LRGB", normaliser_canal=False, sigma_l=0.0),
                    np.float32)
lisse_c = np.asarray(composer(n_c, "LRGB", normaliser_canal=False), np.float32)
r_rgb = rapport_anneau_coeur(rgb_seul)
r_brut = rapport_anneau_coeur(brut_c)
r_lisse = rapport_anneau_coeur(lisse_c)
print(f"  rapport anneau/cœur : RGB seul {r_rgb:.3f} · brut (σ=0) {r_brut:.3f} "
      f"· lissé (σ auto) {r_lisse:.3f}")
verifie(r_brut > 1.8 * r_rgb,
        f"le halo est TOUJOURS reproduit (×{r_brut / r_rgb:.2f} le RGB seul) — "
        "le correctif n'a pas désarmé le mécanisme")
verifie(r_brut / r_lisse >= 2.0,
        f"le lissage du 117c divise toujours le halo par ≥ 2 "
        f"(×{r_brut / r_lisse:.2f})")
# Le PLAFOND ne doit PAS mordre le halo légitime (~3) : comparer le composite
# borné au même composite avec un plafond inatteignable.
_garde = compo.RATIO_L_MAX
try:
    compo.RATIO_L_MAX = 1.0e9
    sans_plafond = np.asarray(composer(n_c, "LRGB", normaliser_canal=False,
                                       sigma_l=0.0), np.float32)
finally:
    compo.RATIO_L_MAX = _garde
r_max_brut = _ratio_combine(n_c["L"], _luma(rgb_c))
touche = int((brut_c != sans_plafond).any(axis=-1).sum())
au_plafond = int((r_max_brut >= RATIO_L_MAX - 1e-6).sum())
print(f"    plafond : {au_plafond} px au plafond ({100.0 * au_plafond / r_max_brut.size:.4f} %) "
      f"· {touche} px modifiés ({100.0 * touche / r_max_brut.size:.4f} %) · "
      f"métrique du halo inchangée : "
      f"{rapport_anneau_coeur(brut_c):.6f} vs "
      f"{rapport_anneau_coeur(sans_plafond):.6f}")
verifie(abs(rapport_anneau_coeur(brut_c)
            - rapport_anneau_coeur(sans_plafond)) < 1e-6,
        "le plafond ne change PAS la métrique du halo (anneau/cœur identique "
        "avec et sans plafond)")
verifie(au_plafond < 5e-4 * r_max_brut.size,
        f"…et il ne concerne qu'une QUEUE : {au_plafond} px sur "
        f"{r_max_brut.size} ({100.0 * au_plafond / r_max_brut.size:.4f} %) — "
        "mesuré 0,09 % sur les couches réelles")

print()
print("[7] GARDE-FOUS : jamais d'exception, jamais de valeur non finie")
for nom, canaux in (("4×4 minuscule", {r: np.full((4, 4), 0.2, np.float32)
                                       for r in ROLES}),
                    ("scène PLATE", {r: np.full((32, 32), 0.2, np.float32)
                                     for r in ROLES}),
                    ("canaux TOUS NULS", {r: np.zeros((32, 32), np.float32)
                                          for r in ROLES}),
                    ("L ×4 plus faint", dict(scene(), L=scene()["L"] * 4.0))):
    try:
        c = composer(canaux, "LRGB", sigma_l=0.0)
        bon = c is not None and bool(np.all(np.isfinite(c)))
    except Exception as exc:                       # aucune exception tolérée
        bon = False
        print(f"    exception sur « {nom} » : {type(exc).__name__}: {exc}")
    verifie(bon, f"{nom} : composite FINI, aucune exception")
# Bord NOIR (zone entièrement hors domaine) : le repli vaut 1,0, JAMAIS 0.
bord = scene(graine=13)
for role in ROLES:
    bord[role][:, :40] = 0.0
n_b = normes(bord)
r_b = _ratio_combine(n_b["L"], _luma(np.stack([n_b["R"], n_b["G"], n_b["B"]], -1)))
c_b = compose(n_b, r_b)
verifie(float(r_b[:, :30].max()) <= RATIO_L_MAX
        and float(r_b[:, :30].min()) >= RATIO_L_MIN,
        f"bord noir : rapport borné [{r_b.min():.3g} ; {r_b.max():.3g}]")
verifie(np.all(np.isfinite(c_b)) and teinte(c_b) > 0.0,
        "bord noir : composite fini, aucune zone morte fabriquée par le combine")
# Composite SANS luminance : le correctif n'a AUCUN effet.
rgb_only = composer({"R": n_c["R"], "G": n_c["G"], "B": n_c["B"]}, "RGB",
                    normaliser_canal=False, sigma_l=0.0)
verifie(np.array_equal(np.asarray(rgb_only, np.float32), rgb_seul),
        "composite RGB (sans L) : inchangé, le correctif ne le touche pas")
# L synthétisé = identité (le combine ne s'applique pas).
synth = composer({k: v for k, v in n_c.items() if k != "L"}, "LRGB",
                 normaliser_canal=False, mode_l="synthetise")
verifie(np.array_equal(np.asarray(synth, np.float32), rgb_seul),
        "L synthétisé : identité — le rapport n'est pas calculé")
# Les invariants des constantes sont ceux qui sont DOCUMENTÉS.
verifie(RATIO_L_MIN == 0.0 and RATIO_L_MAX > 3.0,
        f"invariants : RATIO_L_MIN={RATIO_L_MIN} (jamais négatif) et "
        f"RATIO_L_MAX={RATIO_L_MAX} > 3 (halo légitime du 117c)")
verifie(0.0 < PLANCHER_RATIO_FRAC <= 1e-3,
        f"invariants : PLANCHER_RATIO_FRAC={PLANCHER_RATIO_FRAC:g} reste TROIS "
        "ordres sous le niveau de ciel (~0,2 de l'amplitude)")

print()
print("[8] LA FICHE DE RENDU DIT CE QUI A ÉTÉ APPLIQUÉ (correctif du 16/10)")
from avastack.ui import saver as saver_mod               # noqa: E402
_etapes = saver_mod.Saver._fiche_chaine(
    None, {"compo_combine": True, "compo_lissage": True, "compo_seuil": 12.0,
           "corr_cadre": None}, "pile", False)
_compo = [e for e in _etapes if str(e.get("etape", "")).startswith("combine")]
_mono = [e for e in saver_mod.Saver._fiche_chaine(
    None, {"compo_combine": False}, "pile", False)
    if str(e.get("etape", "")).startswith("combine")]
print(f"  étape « {_compo[0]['etape'] if _compo else '—'} » : "
      f"{ {k: v for k, v in (_compo[0] if _compo else {}).items() if k != 'etape'} }")
verifie(len(_compo) == 1 and _compo[0]["actif"] is True
        and _compo[0]["lissage_halos"] is True
        and float(_compo[0]["seuil_masque_sigma"]) == 12.0
        and float(_compo[0]["plafond_ratio"]) == RATIO_L_MAX
        and float(_compo[0]["plancher_ratio_relatif"]) == PLANCHER_RATIO_FRAC,
        "fiche « tel que vu » : une étape « combine LRGB » portant les BORNES "
        "(plafond + plancher relatif) ET le lissage — le silence de la fiche "
        "du 16/10 ne peut plus se reproduire")
verifie(_etapes[0]["etape"].startswith("combine"),
        "cette étape est la PREMIÈRE (le combine fabrique le composite)")
verifie(len(_mono) == 1 and _mono[0]["actif"] is False,
        "hors composition à luminance : l'étape est annoncée INACTIVE")

print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)




