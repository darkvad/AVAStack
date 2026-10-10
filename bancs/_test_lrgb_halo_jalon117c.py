# -*- coding: utf-8 -*-
"""Test du jalon 117c (v2.70.0) — LE COMBINE LRGB N'ÉPAISSIT PLUS LES HALOS.

Défaut MESURÉ le 09/10/2026 sur le jeu réel M31 LRGB (L du 13/09 + R/G/B du
22-23/09, deux nuits à 176,2°) : `rgb *= L/luma` AMPLIFIE les AILES des étoiles
parce que la PSF de L est plus LARGE que celle de la luminance RGB. Le rapport
L/luma vaut 1,00 au cœur mais ~3 dans les ailes (r ≈ 4-5 px) → chaque étoile
brillante prend un ANNEAU coloré (rapport anneau/cœur 0,124 en RGB seul → 0,347
avec L = halo ×2,8). Ni l'alignement (résidu ramené à ~0,2 px au 117b) ni
l'optique (FWHM identiques par filtre, R/G = 1,039) ne sont en cause.

Correctif : LISSER le rapport L/luma à l'ÉCHELLE DES ÉTOILES (σ = 1,7 × FWHM
mesurée) pour que la luminance n'apporte plus que le GRAND ÉCHELLE — c'est le
réglage qui ramène le rapport anneau/cœur au niveau du RGB seul (un σ de
0,5-1 px ne suffisait pas).

Ce banc vérifie :
  [1] `sigma_l_auto` est PROPORTIONNEL à la FWHM mesurée des étoiles (et borné) ;
  [2] LE défaut : sur notre montage synthétique (L à PSF plus large), l'ANCIEN
      combine (σ = 0) produit un halo, le NOUVEAU (auto) le DIVISE PAR ≥ 2 et
      revient au niveau du RGB seul ;
  [3] non-régression : σ = 0 rend EXACTEMENT l'ancien combine ; champs plats et
      mode « L synthétisé » INCHANGÉS ; un composite RGB ignore `sigma_l` ;
  [4] garde-fous : image minuscule / sans étoile → σ de repli borné, jamais
      d'exception.

Exécution : python bancs/_test_lrgb_halo_jalon117c.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np

from avastack.processing.composition import (SIGMA_L_MAX, SIGMA_L_MIN,
                                             SIGMA_L_PAR_FWHM, composer,
                                             sigma_l_auto)
from avastack.processing import stars as stars_mod

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def _luma(rgb):
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1]
            + 0.114 * rgb[..., 2])


def _rapport_anneau_coeur(comp, r_min=3.5, r_max=4.5):
    """Rapport (luminance MOYENNE de l'anneau r∈[r_min,r_max]) / (luminance du
    cœur) autour du CENTRE de l'image — la métrique du diagnostic 117c."""
    lum = _luma(comp) if comp.ndim == 3 else comp
    h, w = lum.shape
    cy, cx = h // 2, w // 2
    coeur = float(lum[cy, cx])
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    anneau = (r >= r_min) & (r <= r_max)
    return (float(lum[anneau].mean()) / coeur) if coeur > 0 else float("nan")


def _champ(forme, nb=15, sigma=1.2, fond=0.01, bruit=0.002, graine=1, marge=20):
    """Champ synthétique mono : `nb` étoiles gaussiennes (σ en px) + bruit."""
    rng = np.random.default_rng(graine)
    h, w = forme
    img = (fond + rng.normal(0.0, bruit, (h, w))).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(nb):
        y = marge + (h - 2 * marge) * rng.random()
        x = marge + (w - 2 * marge) * rng.random()
        a = 0.4 + 0.6 * rng.random()
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma * sigma))).astype(np.float32)
    return img


def _canaux_lrgb(forme=(160, 160), sigma_rgb=1.3, sigma_l=1.5, fond=0.002,
                 bruit=0.0005, amps=(1.0, 0.7, 0.5), graine=5):
    """Dict LRGB synthétique : MÊME étoile au CENTRE dans R/G/B (PSF étroite,
    colorée par les amplitudes) et dans L (PSF PLUS LARGE, amplitude calée pour
    que le rapport L/luma vaille 1,00 au cœur) — c'est le mismatch réel."""
    h, w = forme
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h // 2, w // 2
    d2 = (yy - cy) ** 2 + (xx - cx) ** 2
    rng = np.random.default_rng(graine)
    b = bruit * rng.normal(0.0, 1.0, (h, w)).astype(np.float32)
    canaux = {}
    lum_amp = 0.0
    for role, amp in zip(("R", "G", "B"), amps):
        canaux[role] = (fond + b
                        + amp * np.exp(-d2 / (2.0 * sigma_rgb ** 2))
                        ).astype(np.float32)
        lum_amp += {"R": 0.299, "G": 0.587, "B": 0.114}[role] * amp
    canaux["L"] = (fond + b
                   + lum_amp * np.exp(-d2 / (2.0 * sigma_l ** 2))
                   ).astype(np.float32)
    return canaux


B01 = {r: (0.0, 1.0) for r in ("L", "R", "G", "B")}

# ==================================================== [1] σ auto ∝ FWHM ========
print("[1] sigma_l_auto : σ PROPORTIONNEL à la FWHM mesurée des étoiles")
ch = _champ((256, 256), nb=15, sigma=1.2, graine=1)
mes, _msg = stars_mod.mesurer_seeing(ch)
fwhm_vraie = stars_mod.fwhm_depuis_sigma(1.2)
fwhm_mes = float(mes.get("fwhm") or 0.0)
s_auto = sigma_l_auto(ch)
print(f"    FWHM vraie {fwhm_vraie:.2f} px · mesurée {fwhm_mes:.2f} px · "
      f"σ auto {s_auto:.2f} px (attendu ≈ {SIGMA_L_PAR_FWHM * fwhm_vraie:.2f})")
verifie(abs(fwhm_mes - fwhm_vraie) / fwhm_vraie < 0.15,
        f"la FWHM mesurée colle à la vraie ({fwhm_mes:.2f} vs {fwhm_vraie:.2f})")
verifie(abs(s_auto - SIGMA_L_PAR_FWHM * fwhm_vraie)
        / (SIGMA_L_PAR_FWHM * fwhm_vraie) < 0.20,
        f"σ auto = {SIGMA_L_PAR_FWHM} × FWHM (±20 %)")
ch_fin = _champ((256, 256), nb=12, sigma=0.9, graine=2)
ch_gros = _champ((256, 256), nb=12, sigma=2.4, graine=3)
verifie(sigma_l_auto(ch_gros) > 1.5 * sigma_l_auto(ch_fin),
        f"σ auto SUIT la taille des étoiles : {sigma_l_auto(ch_fin):.2f} px "
        f"(σ étoile 0,9) < {sigma_l_auto(ch_gros):.2f} px (σ étoile 2,4)")
verifie(SIGMA_L_MIN <= sigma_l_auto(ch) <= SIGMA_L_MAX,
        f"σ auto borné à [{SIGMA_L_MIN} ; {SIGMA_L_MAX}]")

# ========================================== [2] le halo est DIVISÉ par ≥ 2 ====
print("[2] Halo du combine LRGB : σ = 0 (ancien) contre σ auto (nouveau)")
canaux = _canaux_lrgb()
rgb_seul = composer({"R": canaux["R"], "G": canaux["G"], "B": canaux["B"]},
                    "RGB", bornes=B01)
ancien = composer(canaux, "LRGB", bornes=B01, sigma_l=0)
nouveau = composer(canaux, "LRGB", bornes=B01)                  # auto (défaut)
impose = composer(canaux, "LRGB", bornes=B01, sigma_l=4.0)
r_rgb = _rapport_anneau_coeur(rgb_seul)
r_anc = _rapport_anneau_coeur(ancien)
r_nouv = _rapport_anneau_coeur(nouveau)
r_imp = _rapport_anneau_coeur(impose)
print(f"    rapport anneau/cœur : RGB seul {r_rgb:.3f} · ancien {r_anc:.3f} · "
      f"σ auto {r_nouv:.3f} · σ=4 {r_imp:.3f}")
verifie(r_anc > 1.8 * r_rgb,
        f"LE DÉFAUT est reproduit : le combine brut donne un halo "
        f"({r_anc:.3f} vs {r_rgb:.3f} en RGB seul, ×{r_anc / r_rgb:.2f})")
verifie(r_anc / r_nouv >= 2.0,
        f"LE CORRECTIF divise le halo par ≥ 2 (×{r_anc / r_nouv:.2f})")
verifie(r_nouv <= 1.35 * r_rgb,
        f"σ auto revient au niveau du RGB seul ({r_nouv:.3f} vs {r_rgb:.3f})")
verifie(r_imp <= 1.35 * r_rgb,
        f"σ imposé = 4 px revient au niveau du RGB seul ({r_imp:.3f})")
verifie(np.array_equal(
    composer({"R": canaux["R"], "G": canaux["G"], "B": canaux["B"]}, "RGB",
             bornes=B01, sigma_l=0),
    composer({"R": canaux["R"], "G": canaux["G"], "B": canaux["B"]}, "RGB",
             bornes=B01, sigma_l=8.0)),
    "un composite RGB (sans luminance) IGNORE sigma_l : RGB seul inchangé")

# ================================= [3] non-régression & chemins historiques ===
print("[3] Non-régression : σ = 0 = ancien combine ; chemins historiques")
# σ = 0 doit rendre EXACTEMENT le calcul d'avant le 117c : rgb *= L/luma.
lum = _luma(np.stack([canaux["R"], canaux["G"], canaux["B"]], axis=-1))
ratio = np.where(lum > 1e-6, canaux["L"] / np.maximum(lum, 1e-6), 1.0)
attendu = (np.stack([canaux["R"], canaux["G"], canaux["B"]], axis=-1)
           * ratio[..., None]).astype(np.float32)
verifie(np.allclose(ancien, attendu),
        "σ = 0 reproduit AU BIT l'ancien combine `rgb *= L/luma`")
verifie(not np.allclose(ancien, nouveau),
        "σ auto DIFFÈRE de l'ancien (le correctif agit bien)")
# Champ plat → ratio constant → INCHANGÉ, quel que soit σ.
plat = {r: np.full((16, 16), v, np.float32) for r, v in
        (("R", 0.1), ("G", 0.2), ("B", 0.3), ("L", 0.1815))}
verifie(np.allclose(composer(plat, "LRGB", bornes=B01),
                    composer(plat, "LRGB", bornes=B01, sigma_l=6.0)),
        "champs plats : ratio constant → le lissage ne change RIEN")
# L synthétisé (dossier L vide) = luminance du composite → identité (RGB pur).
synth = composer({k: v for k, v in canaux.items() if k != "L"}, "LRGB",
                 bornes=B01, mode_l="synthetise")
synth_ecrase = composer({k: v for k, v in canaux.items() if k != "L"}, "LRGB",
                        bornes=B01, mode_l="synthetise", sigma_l=6.0)
verifie(np.allclose(synth, synth_ecrase),
        "mode « L synthétisé » : identité, le lissage n'est PAS appliqué")

# ==================== [3b] le MASQUE préserve le détail de la nébuleuse =======
print("[3b] Masque : détail de la nébuleuse préservé (le global le détruisait)")
import cv2 as _cv2                                            # noqa: E402


def _canaux_detail(forme=(240, 240), graine=21):
    """Nébuleuse à GRANDE échelle + texture FINE, plus une étoile BRILLANTE au
    centre (pour activer le masque) ; L a sa PROPRE texture, comme dans le réel."""
    rng = np.random.default_rng(graine)
    h, w = forme
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h // 2, w // 2
    d2 = (yy - cy) ** 2 + (xx - cx) ** 2
    g = _cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 18)
    d = {}
    for role in "RGB":
        t = _cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.0)
        d[role] = (0.05 + 0.25 * g + 0.12 * t
                   + 3.0 * np.exp(-d2 / (2 * 1.4 ** 2))).astype(np.float32)
    tL = _cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.0)
    d["L"] = (0.05 + 0.25 * g + 0.12 * tL
              + 3.0 * np.exp(-d2 / (2 * 1.6 ** 2))).astype(np.float32)
    return d


_cd = _canaux_detail()
_h, _w = _cd["L"].shape
_yy, _xx = np.mgrid[0:_h, 0:_w]
_R = np.sqrt((_yy - _h // 2) ** 2 + (_xx - _w // 2) ** 2)
_ZONE = _R > 25                       # nébuleuse, HORS de l'étoile centrale


def _de(L):
    return float(np.std((L - _cv2.GaussianBlur(L, (0, 0), 1.5))[_ZONE]))


_c0 = np.maximum(composer(_cd, "LRGB", bornes=B01, sigma_l=0), 0)
_cm = np.maximum(composer(_cd, "LRGB", bornes=B01), 0)          # masqué (défaut)
# lissage GLOBAL de référence : MÊME combine, mais ratio lissé PARTOUT
# (bornes B01 = identité → la normalisation de composer est neutre ici).
_rgbn = np.stack([_cd["R"], _cd["G"], _cd["B"]], -1)
_luma_rgb = _luma(_rgbn)
from avastack.processing.composition import (_lisser_ratio,       # noqa: E402
                                             sigma_l_auto)
_ratio = np.where(_luma_rgb > 1e-6, _cd["L"] / np.maximum(_luma_rgb, 1e-6), 1.0)
_cg = np.maximum(_rgbn * _lisser_ratio(
    _ratio, sigma_l_auto(_luma_rgb))[..., None], 0)            # lissage GLOBAL
_d0, _dm, _dg = _de(_luma(_c0)), _de(_luma(_cm)), _de(_luma(_cg))
print(f"    détail nébuleuse : σ=0 {_d0:.5f} · masqué {_dm:.5f} · "
      f"global {_dg:.5f}")
verifie(_dm / _d0 > 0.97,
        f"le masque PRÉSERVE le détail fin ({_dm / _d0:.3f} de σ=0, "
        f"attendu > 0,97)")
verifie(_dg / _d0 < 0.95,
        f"le lissage GLOBAL détruit du détail ({_dg / _d0:.3f} de σ=0)")
verifie(_dm / _d0 > _dg / _d0 + 0.03,
        "le masque fait CLAIREMENT mieux que le global "
        f"({_dm / _d0:.3f} vs {_dg / _d0:.3f})")

# ==================================================== [4] garde-fous ==========
print("[4] Garde-fous : image minuscule / sans étoile → repli borné, sans erreur")
s_mini = sigma_l_auto(np.zeros((4, 4), np.float32))
s_plat = sigma_l_auto(np.full((64, 64), 0.02, np.float32))
verifie(SIGMA_L_MIN <= s_mini <= SIGMA_L_MAX and SIGMA_L_MIN <= s_plat
        <= SIGMA_L_MAX,
        f"repli borné [{SIGMA_L_MIN} ; {SIGMA_L_MAX}] : 4×4 → {s_mini:.2f} px, "
        f"plat 64×64 → {s_plat:.2f} px")
verifie(np.isfinite(sigma_l_auto(np.zeros(8, np.float32))),
        "tableau 1D : σ fini (aucune exception)")
comp_mini = composer({r: np.zeros((4, 4), np.float32) for r in "LRGB"},
                     "LRGB", bornes=B01)
verifie(comp_mini is not None and comp_mini.shape == (4, 4, 3),
        "image 4×4 : composer ne plante pas et rend un composite")

print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
