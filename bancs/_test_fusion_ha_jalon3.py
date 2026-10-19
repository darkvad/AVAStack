# -*- coding: utf-8 -*-
"""Banc v2.89.0 — JALON J3 : LES QUATRE AUTRES MODES DE FUSION DU Ha.

Le J2 (v2.88.0) a livré `ajout_rouge` et le cadre « Fusion Ha » ; il est VALIDÉ
EN RÉEL (Alain, 19/10/2026) et sa formule ne change PAS. Le J3 livre les quatre
modes du plan figé, avec le MÊME signal préparé

    s = (Ha − fond(Ha)) − continuum      (écrêté [0 ; 1] si continuum actif)

et le MÊME rôle du POIDS — une FORCE GLOBALE qui interpole entre le composite
d'origine et le résultat du mode :

    sortie = composite + poids × (opérateur(composite, s) − composite)

À poids 1 : l'opérateur exact ; à poids 0 : le composite du J1 AU BIT (la
sortie d'urgence validée au J2 ne dépend donc pas du mode).

Vérifie :
  [1] les CINQ modes (ordre, défaut inchangé), α 0,5 borné [0 ; 1], le dict
      complet de `fusion_ha_effectif` qui porte α, HOO/SHO toujours exclus ;
  [2] CHAQUE FORMULE, AU BIT, à poids 1 et continuum coupé :
      fondu R + α×(s − R) · écran R + s×(1 − R) · éclaircir R + max(0, s − R)
      · luminance les TROIS canaux + s ; V/B au bit hors luminance ;
  [2b] α : 0 → rouge INCHANGÉ, 1 → rouge remplacé par le signal, α n'agit QUE
      sur le fondu, valeur illisible → 0,5 ;
  [3] le POIDS comme force globale pour les CINQ modes : 0 rend le MÊME objet,
      0,5 est à mi-chemin, 2 extrapole ;
  [4] le CONTINUUM alimente les quatre modes avec le MÊME signal écrêté, et
      sans couche R il reste SANS EFFET quel que soit le mode ;
  [5] `composer()` : poids 0 au bit pour chaque mode, formules retrouvées sur le
      composite réel, HOO inchangé, mode inconnu = `ajout_rouge` ;
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
                                             POIDS_HA_MAX, POIDS_HA_MIN,
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

# ================================= [2] chaque formule, AU BIT (poids 1, sans cont.)
print("[2] formules EXACTES à poids 1, continuum coupé")
rgb = composite_rgb()
ha = scene()["Ha"]
r0 = rgb[..., 0].copy()
s = (ha - np.float32(np.median(ha)))          # signal préparé (sans continuum)

out = fusionner_ha(rgb, ha, mode="ajout_rouge", poids=1.0, continuum=False)
verifie(np.array_equal(out, rouge(rgb, s)),
        "ajout_rouge : R' = R + s AU BIT — formule du J2 INCHANGÉE")

out = fusionner_ha(rgb, ha, mode="fondu_rouge", alpha=0.5, poids=1.0,
                   continuum=False)
verifie(np.array_equal(out, rouge(rgb, np.float32(0.5) * (s - r0))),
        "fondu_rouge α 0,5 : R' = R + 0,5 × (s − R) AU BIT")
verifie(np.array_equal(out[..., 1:], rgb[..., 1:]),
        "fondu : VERT et BLEU INCHANGÉS au bit")

out = fusionner_ha(rgb, ha, mode="ecran_rouge", poids=1.0, continuum=False)
verifie(np.array_equal(out, rouge(rgb, s * (np.float32(1.0) - r0))),
        "ecran_rouge : R' = R + s × (1 − R) AU BIT [écran 1−(1−R)(1−s)]")
verifie(np.array_equal(out[..., 1:], rgb[..., 1:]),
        "écran : VERT et BLEU INCHANGÉS au bit")

out = fusionner_ha(rgb, ha, mode="eclaircir_rouge", poids=1.0,
                   continuum=False)
verifie(np.array_equal(out, rouge(rgb,
                                  np.maximum(s - r0, np.float32(0.0)))),
        "eclaircir_rouge : R' = R + max(0, s − R) AU BIT [max(R, s)]")
verifie(np.all(out[..., 0] >= r0),
        "éclaircir ne fait que MONTER le rouge (jamais de baisse)")
verifie(np.array_equal(out[..., 1:], rgb[..., 1:]),
        "éclaircir : VERT et BLEU INCHANGÉS au bit")

out = fusionner_ha(rgb, ha, mode="ha_luminance", poids=1.0, continuum=False)
att = rgb + s[..., None]
verifie(np.array_equal(out, att),
        "ha_luminance : les TROIS canaux reçoivent + s, AU BIT")
verifie(not np.array_equal(out[..., 1:], rgb[..., 1:]),
        "luminance TOUCHE le vert et le bleu — c'est son objet (seule exception)")

# ================================================================ [2b] α du fondu
print("[2b] α : 0 = rouge inchangé, 1 = rouge remplacé, n'agit QUE sur le fondu")
out0 = fusionner_ha(rgb, ha, mode="fondu_rouge", alpha=0.0, poids=1.0,
                    continuum=False)
verifie(np.array_equal(out0[..., 0], r0)
        and np.array_equal(out0[..., 1:], rgb[..., 1:]),
        "α 0 : le rouge revient EXACTEMENT à R (aucun changement)")
out1 = fusionner_ha(rgb, ha, mode="fondu_rouge", alpha=1.0, poids=1.0,
                    continuum=False)
verifie(np.allclose(out1[..., 0], s, atol=1e-6, rtol=0),
        "α 1 : R' = s (le rouge est REMPLACÉ par le signal, au bit près)")
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
verifie(np.array_equal(out, rouge(rgb, np.float32(0.5) * (sig - r0))),
        "fondu + continuum : R + 0,5 × (s_écrêté − R), AU BIT")
out = fusionner_ha(rgb, ha, mode="ecran_rouge", poids=1.0, **CONT)
verifie(np.array_equal(out, rouge(rgb, sig * (np.float32(1.0) - r0))),
        "écran + continuum : R + s_écrêté × (1 − R), AU BIT")
out = fusionner_ha(rgb, ha, mode="eclaircir_rouge", poids=1.0, **CONT)
verifie(np.array_equal(out, rouge(rgb,
                                  np.maximum(sig - r0, np.float32(0.0)))),
        "éclaircir + continuum : max(R, s_écrêté), AU BIT")
out = fusionner_ha(rgb, ha, mode="ha_luminance", poids=1.0, **CONT)
verifie(np.array_equal(out, rgb + sig[..., None]),
        "luminance + continuum : les trois canaux reçoivent s_écrêté, AU BIT")
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
br = base[..., 0].copy()
ATTENDUS = {
    "ajout_rouge": lambda: rouge(base, sc),
    "fondu_rouge": lambda: rouge(base,
                                 np.float32(ALPHA_HA_DEFAUT) * (sc - br)),
    "ecran_rouge": lambda: rouge(base, sc * (np.float32(1.0) - br)),
    "eclaircir_rouge": lambda: rouge(base,
                                     np.maximum(sc - br, np.float32(0.0))),
    "ha_luminance": lambda: base + sc[..., None],
}
for mode in MODES_FUSION_HA:
    c0 = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                  fusion_ha={"mode": mode, "poids": 0.0})
    verifie(np.array_equal(c0, base),
            f"{mode} : poids 0 → composite INCHANGÉ AU BIT (sortie d'urgence)")
    c1 = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                  fusion_ha={"mode": mode, "poids": 1.0, "continuum": False})
    verifie(np.array_equal(c1, ATTENDUS[mode]()),
            f"{mode} : formule EXACTE retrouvée sur le composite réel")
verifie(len({ATTENDUS[m]().tobytes() for m in MODES_FUSION_HA}) == 5,
        "les cinq modes donnent bien CINQ composites DIFFÉRENTS (comparés sur "
        "les TROIS canaux : le rouge seul ne sépare pas ajout de luminance, "
        "qui agit aussi sur V et B)")
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
verifie(not np.array_equal(c1[..., 1:], a1[..., 1:]),
        "mode luminance : le composite mémoïsé TOUCHE aussi V et B")

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






