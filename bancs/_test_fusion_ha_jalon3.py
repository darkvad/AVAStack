# -*- coding: utf-8 -*-
"""Banc v2.90.0 — JALON J3bis : LES QUATRE MODES DANS L'ESPACE DE R.

Le J2 (v2.88.0) a livré `ajout_rouge` et le cadre « Fusion Ha » ; il est VALIDÉ
EN RÉEL (Alain, 19/10/2026) et sa formule ne change PAS — il est purement
ADDITIF, donc hors du piège d'échelle. Le J3 (v2.89.0) a livré les quatre autres
modes, mais ses formules comparaient `R` et `s` DIRECTEMENT : condamnées en réel
sur M33 et remplacées par le J3bis (option A, 19/10/2026).

MESURE QUI A TRANCHÉ (couches M33 réelles, `_diag_fusion_ha_echelles.py`) : avec
la « normalisation commune » le rouge du composite vit entre 2,86 et 5,71 alors
que `s` est écrêté dans [0 ; 1] ⇒ `1 − R < 0` partout (l'écran SOUSTRAIT),
`max(0, s − R) = 0` partout (éclaircir INERTE), le fondu retirait la moitié du
rouge du fond, et la luminance blanchissait.

DEPUIS J3bis, les quatre modes travaillent dans l'ESPACE DE R — « 0 au fond du
ciel, ≈ 1 au p99,7 » pour les DEUX grandeurs :

    fond_R = médiane de R sur le fond (s ≤ sa médiane)
    A_R    = p99,7(R) − fond_R
    R̃ = (R − fond_R)/A_R        s̃ = s/p99,7(s)

    · fondu      : R̃' = R̃ + α·(s̃ − R̃)
    · écran      : R̃' = R̃ + s̃·max(0, 1 − min(R̃, 1))
    · éclaircir  : R̃' = R̃ + max(0, s̃ − R̃)
    · luminance  : R' = R × (1 + s̃·porte), porte = rampe 0,05 → 0,25 sur s̃
                  (le Ha éclaire le ROUGE seulement là où il est FRANC ; sous
                  0,05 le rouge est INCHANGÉ AU BIT ; V/B intacts)

puis retour au composite, pour les TROIS modes « R̃ » :
`R' = max(0, fond_R + A_R·R̃')` et `sortie_R = R + poids × (R' − R)`.

VERDICT RÉEL DU 19/10 : `fondu`, `écran` et `éclaircir` sont OK ; `ha_luminance`
BLANCHISSAIT — il multipliait les TROIS canaux, donc aussi le CIEL de G et B
(saturation des zones Ha 0,19 → 0,12, cœur 0,09 → 0,04). Après comparaison
d'aperçus, Alain a retenu la variante « PORTE douce » : le gain multiplicatif
porte sur le ROUGE, mais seulement là où le Ha est FRANC (rampe 0,05 → 0,25) —
la bande diffuse reste intacte (0 % de pixels touchés) et V/B ne bougent pas.

Le MÊME signal préparé et le MÊME rôle du POIDS qu'au J2/J3 :

    s = (Ha − fond(Ha)) − continuum      (écrêté [0 ; 1] si continuum actif)
    sortie = composite + poids × (opérateur(composite, s) − composite)

Vérifie :
  [1] les CINQ modes (ordre, défaut inchangé), α 0,5 borné [0 ; 1], le dict
      complet de `fusion_ha_effectif` qui porte α, HOO/SHO toujours exclus ;
  [2] CHAQUE FORMULE, dans l'espace de R, à poids 1 et continuum coupé :
      fondu/écran/éclaircir/luminance via R̃ et s̃ ; `ajout_rouge` reste AU BIT
      (J2) ; V et B au bit pour les CINQ modes ;
  [2b] α : 0 → rouge inchangé, 1 → rouge = s̃ ramené au composite, α n'agit QUE
      sur le fondu, valeur illisible → 0,5 ;
  [3] le POIDS comme force globale pour les CINQ modes : 0 rend le MÊME objet,
      0,5 est à mi-chemin, 2 extrapole ;
  [4] le CONTINUUM alimente les quatre modes avec le MÊME signal écrêté, et
      sans couche R il reste SANS EFFET quel que soit le mode ;
  [5] `composer()` : poids 0 au bit pour chaque mode, formules retrouvées sur le
      composite réel, HOO inchangé, mode inconnu = `ajout_rouge` ;
  [5b] COMPOSITE HORS [0 ; 1] (R ≈ 2,9-5,7, comme la session M33) : aucun mode
      ne baisse le rouge du FOND, écran n'abaisse JAMAIS, éclaircir AGIT,
      le fondu ne retire plus le Ha, luminance : gain ×(1 + s̃·porte) qui laisse
      la bande diffuse INTACTE et ne touche que le rouge franc (V/B au bit) ;
  [6] la CLÉ de mémoïsation suit α et le MODE (sinon réglage « sans effet ») ;
  [7] l'INTERFACE (App réelle) : champ α DÉSACTIVÉ hors fondu, borné, persisté
      et restauré, réglage poussé sur le stacker ;
  [8] la FICHE DE RENDU nomme le mode et α.

Exécution : python bancs/_test_fusion_ha_jalon3.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing import composition as compo
from avastack.processing.composition import (ALPHA_HA_DEFAUT, ALPHA_HA_MAX,
                                             ALPHA_HA_MIN, BW_HA_NM, BW_RGB_NM,
                                             CLIP_HA_MAX, CLIP_HA_MIN,
                                             CompositeStacker, FUSION_HA_DEFAUT,
                                             MODES_FUSION_HA, POIDS_HA_DEFAUT,
                                             PORTE_HA_DEBUT, PORTE_HA_FIN,
                                             Q_HA_DEFAUT, composer,
                                             fusion_ha_effectif, fusionner_ha,
                                             normaliser)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def scene(forme=(64, 64), graine=3, fond_ha=0.30, signal_ha=0.50):
    """Scène LRGB+Ha synthétique (même construction qu'au banc J2) : ciel +
    bruit par rôle, nébulosité COMPACTE, Ha à fond franc (0,30)."""
    rng = np.random.default_rng(graine)
    h, w = forme
    yy, xx = np.mgrid[0:h, 0:w]
    neb = np.exp(-(((yy - h / 2.0) ** 2 + (xx - w / 2.0) ** 2)
                   / (2.0 * (h / 12.0) ** 2))).astype(np.float32)
    canaux = {}
    for role in ("L", "R", "G", "B"):
        canaux[role] = (0.02 + 0.10 * neb
                        + rng.normal(0.0, 0.002, (h, w))).astype(np.float32)
    canaux["Ha"] = (fond_ha + signal_ha * neb
                    + rng.normal(0.0, 0.002, (h, w))).astype(np.float32)
    return canaux


def composite_rgb():
    """Composite (H, W, 3) déjà dans l'espace normalisé (valeurs ~0..1)."""
    rng = np.random.default_rng(11)
    rgb = rng.normal(0.25, 0.02, (64, 64, 3)).astype(np.float32)
    rgb[..., 0] += 0.15
    return rgb


def rouge(base, delta):
    """Composite attendu : SEUL le rouge reçoit `delta`."""
    out = base.copy()
    out[..., 0] = base[..., 0] + delta
    return out


def reperes(base, sig):
    """Repères de l'ESPACE DE R, calculés ICI (référence INDÉPENDANTE).

    Mêmes définitions que la spec J3bis : `fond_R` = médiane du rouge sur le
    fond (`s` ≤ sa médiane), `A_R` = p99,7(R) − fond_R, `p_s` = p99,7(s).
    """
    fond = sig <= np.percentile(sig, 50.0)
    r0 = np.asarray(base[..., 0], dtype=np.float64)
    fond_r = float(np.median(r0[fond]))
    return (fond_r, float(np.percentile(r0, 99.7)) - fond_r,
            float(np.percentile(sig, 99.7)))


def mode_espace_r(base, sig, mode, alpha=0.5, poids=1.0):
    """Rejoue l'opérateur J3bis (option A) tel que la SPEC l'écrit.

    Écrit VOLONTAIREMENT à part de `fusionner_ha` : c'est la référence du banc.
    Calculs en float64 ⇒ comparaison avec une TOLÉRANCE (l'aller-retour par R̃
    coûte quelques ulp en float32). Seul `ajout_rouge` reste comparé AU BIT.

    Depuis le 19/10 (verdict réel), `ha_luminance` est un opérateur de ROUGE
    comme les autres : `R' = R × (1 + p·s̃·porte)`, la porte n'ouvrant le gain
    que là où le Ha est franc (rampe 0,05 → 0,25 sur s̃). Le ciel n'est pas
    multiplié sous 0,05 et V/B ne sont PAS touchés.
    """
    r0 = np.asarray(base[..., 0], dtype=np.float64)
    fond_r, amp_r, amp_s = reperes(base, sig)
    st = np.asarray(sig, dtype=np.float64) / amp_s  # s̃
    if mode == "ha_luminance":
        porte = np.clip((st - PORTE_HA_DEBUT)
                        / (PORTE_HA_FIN - PORTE_HA_DEBUT), 0.0, 1.0)
        r_mode = np.maximum(r0 * (1.0 + st * porte), 0.0)
    else:
        rt = (r0 - fond_r) / amp_r                  # R̃
        if mode == "fondu_rouge":
            rt = rt + alpha * (st - rt)
        elif mode == "ecran_rouge":
            rt = rt + st * np.maximum(0.0, 1.0 - np.minimum(rt, 1.0))
        elif mode == "eclaircir_rouge":
            rt = rt + np.maximum(st - rt, 0.0)
        else:
            raise AssertionError(f"{mode} n'est pas un mode de rouge")
        r_mode = np.maximum(fond_r + amp_r * rt, 0.0)   # retour au composite
    out = np.asarray(base, dtype=np.float64).copy()
    out[..., 0] = r0 + poids * (r_mode - r0)        # force GLOBALE
    return out


# ============================================== [1] cinq modes, défauts, bornes
print("[1] cinq modes, défauts et bornes de α")
verifie(MODES_FUSION_HA == ("ajout_rouge", "fondu_rouge", "ecran_rouge",
                            "eclaircir_rouge", "ha_luminance"),
        f"cinq modes, dans l'ordre du plan : {MODES_FUSION_HA}")
verifie(FUSION_HA_DEFAUT == "ajout_rouge" and POIDS_HA_DEFAUT == 1.0,
        "le défaut reste `ajout_rouge` / poids 1,0 (VALIDÉ EN RÉEL au J2)")
verifie(ALPHA_HA_DEFAUT == 0.5
        and (ALPHA_HA_MIN, ALPHA_HA_MAX) == (0.0, 1.0),
        f"α du fondu : défaut {ALPHA_HA_DEFAUT}, bornes "
        f"[{ALPHA_HA_MIN} ; {ALPHA_HA_MAX}]")
f = fusion_ha_effectif("LRGB+Ha", None)
verifie(set(f) == {"mode", "poids", "alpha", "recentrer", "continuum", "q",
                   "methode_continuum"} and f["alpha"] == ALPHA_HA_DEFAUT,
        f"le dict COMPLET porte α : {sorted(f)}")
verifie(fusion_ha_effectif("LRGB+Ha", {"alpha": 9})["alpha"] == ALPHA_HA_MAX
        and fusion_ha_effectif("LRGB+Ha", {"alpha": -1})["alpha"] == ALPHA_HA_MIN,
        "α hors bornes → borné (9 → 1, −1 → 0)")
verifie(fusion_ha_effectif("LRGB+Ha", {"alpha": "illisible"})["alpha"]
        == ALPHA_HA_DEFAUT,
        "α illisible → défaut 0,5 (jamais 0, qui passerait pour « sans effet »)")
verifie(fusion_ha_effectif("LRGB+Ha", {"mode": "inconnu"})["mode"]
        == FUSION_HA_DEFAUT,
        "mode inconnu → DÉFAUT (jamais une exception)")
verifie(fusion_ha_effectif("HOO", {"mode": "fondu_rouge"}) is None
        and fusion_ha_effectif("SHO", {"mode": "ecran_rouge"}) is None
        and fusion_ha_effectif("LRGB", {"mode": "eclaircir_rouge"}) is None,
        "HOO/SHO (Ha = canal) et LRGB : aucun mode ne s'invite")

# ================================ [2] chaque formule, dans l'ESPACE DE R (poids 1)
print("[2] formules J3bis à poids 1, continuum coupé : les repères de R sont respectés")
rgb = composite_rgb()
ha = scene()["Ha"]
r0 = rgb[..., 0].copy()
s = (ha - np.float32(np.median(ha)))          # signal préparé (sans continuum)
fond_r, amp_r, amp_s = reperes(rgb, s)
print(f"    repères : fond_R={fond_r:.4f}  A_R={amp_r:.4f}  p99,7(s)={amp_s:.4f}")
verifie(amp_r > 1e-6 and amp_s > 1e-6,
        "les repères existent (ni canal plat, ni signal vide)")

out = fusionner_ha(rgb, ha, mode="ajout_rouge", poids=1.0, continuum=False)
verifie(np.array_equal(out, rouge(rgb, s)),
        "ajout_rouge : R' = R + s AU BIT — formule du J2 INCHANGÉE")

out_fondu = fusionner_ha(rgb, ha, mode="fondu_rouge", alpha=0.5, poids=1.0,
                         continuum=False)
verifie(np.allclose(out_fondu,
                    mode_espace_r(rgb, s, "fondu_rouge", alpha=0.5),
                    atol=1e-6, rtol=1e-6),
        "fondu_rouge : R̃' = R̃ + α×(s̃ − R̃), puis retour au composite")
verifie(np.array_equal(out_fondu[..., 1:], rgb[..., 1:]),
        "fondu : VERT et BLEU INCHANGÉS au bit")
ancien = rouge(rgb, np.float32(0.5) * (s - r0))
verifie(float(np.max(np.abs(out_fondu[..., 0] - ancien[..., 0]))) > 1e-3,
        "le fondu ne fait PLUS R + α×(s − R) : l'espace de R est bien appliqué "
        "(l'ancienne formule est abandonnée)")

out = fusionner_ha(rgb, ha, mode="ecran_rouge", poids=1.0, continuum=False)
verifie(np.allclose(out, mode_espace_r(rgb, s, "ecran_rouge"),
                    atol=1e-6, rtol=1e-6),
        "ecran_rouge : R̃' = R̃ + s̃ × max(0, 1 − min(R̃, 1)) [l'écran BORNE]")
verifie(np.array_equal(out[..., 1:], rgb[..., 1:]),
        "écran : VERT et BLEU INCHANGÉS au bit")

out = fusionner_ha(rgb, ha, mode="eclaircir_rouge", poids=1.0,
                   continuum=False)
verifie(np.allclose(out, mode_espace_r(rgb, s, "eclaircir_rouge"),
                    atol=1e-6, rtol=1e-6),
        "eclaircir_rouge : R̃' = R̃ + max(0, s̃ − R̃) [max(R̃, s̃)]")
verifie(np.all(out[..., 0] >= r0 - 1e-6),
        "éclaircir ne fait que MONTER le rouge (jamais de baisse)")
verifie(np.array_equal(out[..., 1:], rgb[..., 1:]),
        "éclaircir : VERT et BLEU INCHANGÉS au bit")

out = fusionner_ha(rgb, ha, mode="ha_luminance", poids=1.0, continuum=False)
verifie(np.allclose(out, mode_espace_r(rgb, s, "ha_luminance"),
                    atol=1e-6, rtol=1e-6),
        "ha_luminance : R' = R × (1 + s̃·porte) — le gain n'ouvre que sur le Ha franc")
verifie(np.array_equal(out[..., 1:], rgb[..., 1:]),
        "luminance : VERT et BLEU INCHANGÉS au bit (les 5 modes ne touchent que R)")

# ================================================================ [2b] α du fondu
print("[2b] α : 0 = rouge inchangé, 1 = rouge = s̃, n'agit QUE sur le fondu")
out0 = fusionner_ha(rgb, ha, mode="fondu_rouge", alpha=0.0, poids=1.0,
                    continuum=False)
verifie(np.allclose(out0[..., 0], r0, atol=1e-6, rtol=0)
        and np.array_equal(out0[..., 1:], rgb[..., 1:]),
        "α 0 : le rouge revient à R (à l'aller-retour par R̃ près), V/B au bit")
out1 = fusionner_ha(rgb, ha, mode="fondu_rouge", alpha=1.0, poids=1.0,
                    continuum=False)
att1 = np.maximum(fond_r + amp_r * (s.astype(np.float64) / amp_s), 0.0)
verifie(np.allclose(out1[..., 0], att1, atol=1e-6, rtol=1e-6),
        "α 1 : le rouge prend s̃ (fond_R + A_R·s̃), plus le signal brut")
a_alpha0 = fusionner_ha(rgb, ha, mode="ajout_rouge", alpha=0.0, poids=1.0,
                        continuum=False)
a_alpha1 = fusionner_ha(rgb, ha, mode="ajout_rouge", alpha=1.0, poids=1.0,
                        continuum=False)
verifie(np.array_equal(a_alpha0, a_alpha1),
        "α n'agit QUE sur le fondu (ajout identique à α 0 et α 1)")

# ================================================ [3] le poids, force globale
print("[3] le POIDS est une force globale, pour les CINQ modes")
for mode in MODES_FUSION_HA:
    base = fusionner_ha(rgb, ha, mode=mode, poids=0.0)
    verifie(base is rgb,
            f"{mode} : poids 0 rend LE MÊME objet (composite du J1, "
            "aucune copie)")
pleine = {m: fusionner_ha(rgb, ha, mode=m, poids=1.0, continuum=False)
          for m in MODES_FUSION_HA}
for mode in MODES_FUSION_HA:
    moitie = fusionner_ha(rgb, ha, mode=mode, poids=0.5, continuum=False)
    verifie(np.allclose(moitie, rgb + 0.5 * (pleine[mode] - rgb),
                        atol=1e-6, rtol=0),
            f"{mode} : poids 0,5 = EXACTEMENT à mi-chemin du composite et du "
            "mode")
double = fusionner_ha(rgb, ha, mode="ecran_rouge", poids=2.0, continuum=False)
verifie(np.allclose(double, rgb + 2.0 * (pleine["ecran_rouge"] - rgb),
                    atol=1e-6, rtol=0),
        "poids 2,0 EXTRAPOLE (2 × l'écart du mode), il n'est pas plafonné à 1")

# ====================================================== [4] continuum partagé
print("[4] continuum : le MÊME signal écrêté pour les quatre modes")
r_raw = scene()["R"]
ECH = 0.5                       # échelle arbitraire du volet (unités du Ha)
kk = np.float32(Q_HA_DEFAUT * (BW_HA_NM / BW_RGB_NM) / ECH)
sig = np.clip(s - kk * (r_raw - np.float32(np.median(r_raw))),
              CLIP_HA_MIN, CLIP_HA_MAX)
CONT = {"continuum": True, "q": Q_HA_DEFAUT, "r_reference": r_raw,
        "echelle_ha": ECH}
out = fusionner_ha(rgb, ha, mode="fondu_rouge", alpha=0.5, poids=1.0, **CONT)
verifie(np.allclose(out, mode_espace_r(rgb, sig, "fondu_rouge"),
                    atol=1e-6, rtol=1e-6),
        "fondu + continuum : même opérateur, sur s_écrêté")
out = fusionner_ha(rgb, ha, mode="ecran_rouge", poids=1.0, **CONT)
verifie(np.allclose(out, mode_espace_r(rgb, sig, "ecran_rouge"),
                    atol=1e-6, rtol=1e-6),
        "écran + continuum : même opérateur, sur s_écrêté")
out = fusionner_ha(rgb, ha, mode="eclaircir_rouge", poids=1.0, **CONT)
verifie(np.allclose(out, mode_espace_r(rgb, sig, "eclaircir_rouge"),
                    atol=1e-6, rtol=1e-6),
        "éclaircir + continuum : même opérateur, sur s_écrêté")
out = fusionner_ha(rgb, ha, mode="ha_luminance", poids=1.0, **CONT)
verifie(np.allclose(out, mode_espace_r(rgb, sig, "ha_luminance"),
                    atol=1e-6, rtol=1e-6),
        "luminance + continuum : même opérateur, sur s_écrêté")
for mode in ("fondu_rouge", "ecran_rouge", "eclaircir_rouge", "ha_luminance"):
    sans_r = fusionner_ha(rgb, ha, mode=mode, continuum=True,
                          r_reference=None)
    coupe = fusionner_ha(rgb, ha, mode=mode, continuum=False)
    verifie(np.array_equal(sans_r, coupe),
            f"{mode} : SANS couche R le continuum est sans effet (aucun "
            "retrait, jamais d'exception)")

# ============================================================== [5] composer()
print("[5] `composer()` : poids 0 au bit, chaque mode retrouvé, HOO intact")
canaux = scene()
bornes = {r: compo.bornes_normalisation(a) for r, a in canaux.items()}
base = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                fusion_ha={"poids": 0.0})       # référence SANS fusion
norm_ha = normaliser(canaux["Ha"], *bornes["Ha"])
sc = norm_ha - np.float32(np.median(norm_ha))
ATTENDUS = {
    "ajout_rouge": lambda: rouge(base, sc),
    "fondu_rouge": lambda: mode_espace_r(base, sc, "fondu_rouge",
                                         alpha=ALPHA_HA_DEFAUT),
    "ecran_rouge": lambda: mode_espace_r(base, sc, "ecran_rouge"),
    "eclaircir_rouge": lambda: mode_espace_r(base, sc, "eclaircir_rouge"),
    "ha_luminance": lambda: mode_espace_r(base, sc, "ha_luminance"),
}
for mode in MODES_FUSION_HA:
    c0 = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                  fusion_ha={"mode": mode, "poids": 0.0})
    verifie(np.array_equal(c0, base),
            f"{mode} : poids 0 → composite INCHANGÉ AU BIT (sortie d'urgence)")
    c1 = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                  fusion_ha={"mode": mode, "poids": 1.0, "continuum": False})
    if mode == "ajout_rouge":
        verifie(np.array_equal(c1, ATTENDUS[mode]()),
                f"{mode} : formule EXACTE retrouvée sur le composite réel (AU BIT)")
    else:
        verifie(np.allclose(c1, ATTENDUS[mode](), atol=1e-6, rtol=1e-6),
                f"{mode} : formule EXACTE retrouvée sur le composite réel "
                "(espace de R)")
verifie(len({ATTENDUS[m]().tobytes() for m in MODES_FUSION_HA}) == 5,
        "les cinq modes donnent bien CINQ composites DIFFÉRENTS (ajout et "
        "luminance agissent tous deux sur le rouge, mais pas de la même façon : "
        "ajout = +s constant, luminance = ×(1 + s̃·porte) sur le rouge franc)")
inconnu = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                   fusion_ha={"mode": "zzz", "poids": 1.0,
                              "continuum": False})
verifie(np.array_equal(inconnu, ATTENDUS["ajout_rouge"]()),
        "mode inconnu → `ajout_rouge` AU BIT (jamais une exception)")
for mode in MODES_FUSION_HA:
    hoo0 = composer(canaux, "HOO", bornes=bornes, sigma_l=0.0)
    hoo1 = composer(canaux, "HOO", bornes=bornes, sigma_l=0.0,
                    fusion_ha={"mode": mode, "poids": 5.0})
    verifie(np.array_equal(hoo0, hoo1),
            f"HOO + {mode} : AUCUN effet (le Ha y est déjà le canal vert)")

# ============================ [5b] composite HORS [0 ; 1] (le cas de la session)
print("[5b] composite HORS [0 ; 1] (R ≈ 2,9-5,7) : les défauts du 19/10 disparaissent")
# Scène CALQUÉE sur la mesure : continuum R large entre 2,86 et 5,71 (le rouge
# du composite en normalisation commune), Ha COMPACT et AILLEURS que le maximum
# de R (une émission Ha est bien plus concentrée que le continuum) — c'est
# exactement la configuration où le J3 soustrayait, blanchissait et n'agissait
# sur rien.
_n = 160
_yy, _xx = np.mgrid[0:_n, 0:_n].astype(np.float32)
_rng = np.random.default_rng(11)
_neb = np.exp(-(((_yy - 70.0) ** 2 + (_xx - 80.0) ** 2)
                / (2.0 * 40.0 ** 2))).astype(np.float32)
_ha = (np.exp(-(((_yy - 50.0) ** 2 + (_xx - 55.0) ** 2)
                / (2.0 * 9.0 ** 2)))
       + np.exp(-(((_yy - 100.0) ** 2 + (_xx - 120.0) ** 2)
                  / (2.0 * 12.0 ** 2)))).astype(np.float32)
_R = (2.86 + 2.85 * _neb + _rng.normal(0.0, 0.02, (_n, _n))).astype(np.float32)
_V = (0.20 + 0.05 * _neb + _rng.normal(0.0, 0.01, (_n, _n))).astype(np.float32)
_B = (0.15 + 0.04 * _neb + _rng.normal(0.0, 0.01, (_n, _n))).astype(np.float32)
hors = np.stack([_R, _V, _B], axis=-1).astype(np.float32)
sig_hors = np.clip(_ha - float(np.median(_ha))
                   + _rng.normal(0.0, 0.01, (_n, _n)).astype(np.float32),
                   np.float32(0.0), np.float32(1.0)).astype(np.float32)
_p50, _p997 = (float(v) for v in np.percentile(_R, [50.0, 99.7]))
print(f"    rouge du composite : p50={_p50:.2f}  p99,7={_p997:.2f} "
      "(la mesure M33 : 2,86 / 5,71)")
verifie(_p50 > 2.0 and _p997 > 4.0,
        "le composite est bien HORS [0 ; 1] — le cas qui a condamné le J3")
fond_h = sig_hors <= np.percentile(sig_hors, 50.0)
coeur_h = sig_hors >= np.percentile(sig_hors, 99.0)
_fond_h_ref, _amp_h, _amp_h_s = reperes(hors, sig_hors)  # échelle du test
CONT5 = {"continuum": False, "recentrer": False}

o = fusionner_ha(hors, sig_hors, mode="ajout_rouge", poids=1.0, **CONT5)
verifie(np.array_equal(o, hors + sig_hors[..., None]
                       * np.float32([1.0, 0.0, 0.0])),
        "ajout_rouge reste PUREMENT ADDITIF hors [0 ; 1] — le J2 est intact")

degrad = {}
for mode in ("fondu_rouge", "ecran_rouge", "eclaircir_rouge"):
    o = fusionner_ha(hors, sig_hors, mode=mode, poids=1.0, alpha=0.5, **CONT5)
    d = o[..., 0] - _R
    degrad[mode] = (o, d)
    verifie(abs(float(np.median(d[fond_h]))) < 0.01 * _amp_h,
            f"{mode} : le rouge du FOND ne bouge plus "
            f"({100.0 * float(np.median(d[fond_h])) / _amp_h:+.2f} % de A_R) "
            "— plus d'image bleuie")
    if mode != "fondu_rouge":
        verifie(float(d.min()) >= -1e-6,
                f"{mode} : le rouge ne BAISSE JAMAIS (min {float(d.min()):+.6f}) "
                "— plus de cyan")
    verifie(np.array_equal(o[..., 1:], hors[..., 1:]),
            f"{mode} : VERT et BLEU INCHANGÉS au bit")

o_f, d_f = degrad["fondu_rouge"]
verifie(float(np.median(d_f[coeur_h])) > 0.1,
        f"fondu : le Ha MONTE au cœur ({float(np.median(d_f[coeur_h])):+.3f}) "
        "— il n'est plus retiré du rouge")
o_e, d_e = degrad["eclaircir_rouge"]
monte = float(np.mean(d_e[coeur_h] > 1e-6))
verifie(monte > 0.80,
        f"éclaircir AGIT au cœur Ha : {100.0 * monte:.1f} % des pixels montent "
        "(il était strictement INERTE)")
o_e2 = fusionner_ha(hors, sig_hors, mode="eclaircir_rouge", poids=2.0,
                    continuum=False, recentrer=False)
verifie(float(np.max(np.abs(o_e2 - o_e))) > 1e-3,
        "éclaircir : le POIDS n'est plus sans effet (poids 2 ≠ poids 1)")
o_s, d_s = degrad["ecran_rouge"]
verifie(float(np.median(d_s[coeur_h])) > 0.1,
        f"écran : il AJOUTE au cœur Ha ({float(np.median(d_s[coeur_h])):+.3f}) "
        "— le poids n'est plus multiplié par un (1 − R) négatif")

o_l = fusionner_ha(hors, sig_hors, mode="ha_luminance", poids=1.0, **CONT5)
d_l = o_l[..., 0] - _R
verifie(abs(float(np.median(d_l[fond_h]))) < 0.01 * _amp_h,
        f"ha_luminance : le CIEL garde son niveau "
        f"({100.0 * float(np.median(d_l[fond_h])) / _amp_h:+.2f} % de A_R) "
        "— plus de bruit rouge dans le fond")
verifie(np.array_equal(o_l[..., 1:], hors[..., 1:]),
        "ha_luminance : VERT et BLEU INCHANGÉS au bit — plus de blanchiment")
_st_h = sig_hors / np.float32(_amp_h_s)
_sous = _st_h < np.float32(PORTE_HA_DEBUT - 1e-3)
verifie(np.array_equal(o_l[..., 0][_sous], _R[_sous]),
        f"ha_luminance : sous la porte ({100.0 * float(np.mean(_sous)):.0f} % des "
        "pixels) le rouge est INCHANGÉ AU BIT — le bruit du ciel reste intact")
verifie(float(np.median(d_l[coeur_h])) > 0.1,
        f"ha_luminance ÉCLAIRE le ROUGE au cœur "
        f"({float(np.median(d_l[coeur_h])):+.3f})")
_gain = ((o_l[..., 0] - np.float32(_fond_h_ref))
         / np.maximum(_R - np.float32(_fond_h_ref), np.float32(1e-6)))
verifie(float(np.median(_gain[coeur_h])) > 1.2,
        f"au cœur, l'objet est multiplié ×{float(np.median(_gain[coeur_h])):.2f} "
        "(R × (1 + s̃), porte grande ouverte)")

# ==================================================== [6] clé de mémoïsation
print("[6] mémoïsation : la CLÉ suit le MODE et α")
REP = {"mode": "fondu_rouge", "poids": 1.0, "alpha": 0.5, "continuum": False}


class _FauxStacker:
    """Stacker de rôle minimal : `moyennes()` ne lit que `.n` et `.mean()`."""

    def __init__(self, img):
        self.img = img
        self.n = 5

    def mean(self, recadre: bool = False):
        return self.img


st = CompositeStacker("LRGB+Ha")
st.stackers = {r: _FauxStacker(a) for r, a in canaux.items()}
st.cadre = None
st.fusion_ha = {"poids": 0.0}             # référence SANS fusion
a1 = st.mean()
a2 = st.mean()
verifie(a1 is a2,
        "deux appels sans changement : composite MÉMOÏSÉ (même objet)")
st.fusion_ha = dict(REP)
b1 = st.mean()
st.fusion_ha = dict(REP, alpha=0.9)
b2 = st.mean()
verifie(b2 is not b1 and not np.array_equal(b2, b1),
        "α changé → composite REFAIT (α est bien dans la clé)")
st.fusion_ha = dict(REP, alpha=0.9, mode="ecran_rouge")
b3 = st.mean()
verifie(b3 is not b2 and not np.array_equal(b3, b2),
        "mode changé → composite REFAIT (le mode est dans la clé)")
st.fusion_ha = {"mode": "ecran_rouge", "poids": 0.0}
b4 = st.mean()
verifie(np.array_equal(b4, a1),
        "retour à poids 0 → composite de RÉFÉRENCE, AU BIT (tous modes)")
st.fusion_ha = {"mode": "ha_luminance", "poids": 1.0, "continuum": False}
c1 = st.mean()
verifie(not np.array_equal(c1[..., 0], a1[..., 0])
        and np.array_equal(c1[..., 1:], a1[..., 1:]),
        "mode luminance : le composite mémoïsé touche le ROUGE, mais PAS V et B")

# ============================================================ [7] interface
print("[7] interface : champ α activé SEULEMENT en fondu, borné et persisté")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui               # noqa: E402
ui.CONFIG = {}                             # jamais toucher à la vraie config
captures: list[dict] = []
ui.sauver_config = lambda d: captures.append(dict(d))
ui.App._avertir = lambda self, titre, message: None   # aucune boîte modale
app = ui.App(root)
app._mode_compo = False
app.var_compo.set("LRGB+Ha")
app._on_compo()
verifie(app.frm_fusion_ha.winfo_manager() == "pack",
        "LRGB+Ha : cadre « Fusion Ha » VISIBLE")
app.var_fusion_ha_mode.set("ajout_rouge")
app._maj_fusion_ha()
verifie(str(app.sp_fusion_ha_alpha.cget("state")) == "disabled",
        "mode ajout_rouge : champ α DÉSACTIVÉ (il n'y sert à rien)")
app.var_fusion_ha_mode.set("fondu_rouge")
app._maj_fusion_ha()
verifie(str(app.sp_fusion_ha_alpha.cget("state")) == "normal",
        "mode fondu_rouge : champ α ACTIVÉ")
# ⚠ DÉFAUT RÉEL du 19/10 : le vrai chemin est `_on_fusion_ha` (Combobox), pas
# `_maj_fusion_ha()` appelée à la main — le banc précédent ne voyait donc pas
# que le champ α RESTAIT GRISÉ en passant en fondu. On rejoue le chemin réel.
app.var_fusion_ha_mode.set("ajout_rouge")
app._on_fusion_ha()
verifie(str(app.sp_fusion_ha_alpha.cget("state")) == "disabled",
        "chemin RÉEL (Combobox → _on_fusion_ha) : α désactivé en ajout")
app.var_fusion_ha_mode.set("fondu_rouge")
app._on_fusion_ha()
verifie(str(app.sp_fusion_ha_alpha.cget("state")) == "normal",
        "chemin RÉEL (Combobox → _on_fusion_ha) : α ACTIVÉ en fondu — "
        "défaut du 19/10 corrigé")
app.var_fusion_ha_alpha.set(9.0)
verifie(app._lire_fusion_ha()["alpha"] == ALPHA_HA_MAX,
        f"saisie α 9 → borné à {ALPHA_HA_MAX}")
app.var_fusion_ha_alpha.set(-2.0)
verifie(app._lire_fusion_ha()["alpha"] == ALPHA_HA_MIN,
        f"saisie α −2 → borné à {ALPHA_HA_MIN}")
app.var_fusion_ha_alpha.set(0.35)
app.var_fusion_ha_poids.set(2.5)
ligne_r = next(i for i in range(compo.NB_LIGNES_COMPO)
               if app.var_compo_roles[i].get() == "R")
app.var_compo_dossiers[ligne_r].set("C:/brutes/R")
app.var_fusion_ha_continuum.set(True)
app._maj_fusion_ha()
app.stacker = CompositeStacker("LRGB+Ha")
app._on_fusion_ha()
sth = app.stacker.fusion_ha
verifie(sth["mode"] == "fondu_rouge" and sth["alpha"] == 0.35
        and sth["poids"] == 2.5 and sth["continuum"] is True,
        f"réglage poussé sur le STACKER : {sth}")
verifie(app._compo_fusion_ha == sth,
        "instantané `_compo_fusion_ha` posé pour le worker")

app._sauver_config_app()
c = captures[-1]
verifie(c.get("fusion_ha_mode") == "fondu_rouge"
        and float(c.get("fusion_ha_alpha", -1.0)) == 0.35,
        f"persisté : mode={c.get('fusion_ha_mode')} "
        f"alpha={c.get('fusion_ha_alpha')}")
ui.CONFIG = c
app.var_fusion_ha_alpha.set(0.5)           # on casse les valeurs…
app.var_fusion_ha_mode.set("ajout_rouge")
app._restaurer_config()                    # … puis on relit la config
verifie(float(app.var_fusion_ha_alpha.get()) == 0.35
        and app.var_fusion_ha_mode.get() == "fondu_rouge",
        "config relue : mode et α RESTAURÉS")

# ======================================================== [8] fiche de rendu
print("[8] fiche de rendu : le MODE et α sont dits")
app.var_compo.set("LRGB+Ha")
app._on_compo()
app.var_fusion_ha_mode.set("fondu_rouge")
app.var_fusion_ha_alpha.set(0.35)
app.var_fusion_ha_poids.set(2.5)
app.var_fusion_ha_continuum.set(True)
app._maj_fusion_ha()
app.stacker = CompositeStacker("LRGB+Ha")
app.stacker.stackers = {"Ha": _FauxStacker(canaux["Ha"]),
                        "R": _FauxStacker(canaux["R"])}   # Ha ET R non vides
app._on_fusion_ha()
reg = app._reglages_rendu()
att = {"mode": "fondu_rouge", "poids": 2.5, "alpha": 0.35,
       "recentrer": True, "continuum": True, "q": Q_HA_DEFAUT,
       "methode_continuum": "bandes_passantes"}
verifie(reg.get("compo_fusion") == att,
        f"réglages capturés : {reg.get('compo_fusion')}")
chaine = app._fiche_chaine(reg, "empilement", False)
noms = [e["etape"] for e in chaine]
verifie("fusion Ha" in noms,
        "la chaîne porte une étape « fusion Ha »")
if "fusion Ha" in noms:
    etape = chaine[noms.index("fusion Ha")]
    verifie(etape.get("mode") == "fondu_rouge"
            and float(etape.get("alpha", -1.0)) == 0.35
            and float(etape.get("poids", -1.0)) == 2.5,
            f"l'étape nomme le MODE et α : {etape}")
    verifie(noms.index("fusion Ha")
            == noms.index("combine LRGB (rapport L/luma borne)") + 1,
            "elle vient JUSTE APRÈS le combine L (ordre du plan)")
else:
    verifie(False, "étape « fusion Ha » absente alors que la compo en a une")

app.stacker = CompositeStacker("HOO")
reg2 = app._reglages_rendu()
verifie(reg2.get("compo_fusion") is None,
        "HOO : aucune fusion dans les réglages, même champ α rempli")
noms2 = [e["etape"] for e in app._fiche_chaine(reg2, "empilement", False)]
verifie("fusion Ha" not in noms2,
        "HOO : aucune étape « fusion Ha » dans la fiche")

root.destroy()
print()
print("VERDICT :", "TOUS LES VOLETS VERTS" if ok else "ÉCHEC")
sys.exit(0 if ok else 1)






