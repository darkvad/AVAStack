# -*- coding: utf-8 -*-
"""Banc v2.88.0 — JALON J2 : FUSION DU Ha AU ROUGE (chantier LRGB+Ha).

Le rôle Ha de « RGB+Ha » et « LRGB+Ha » n'alimente AUCUN canal (`canaux_rgb`
ne le cite pas) : il s'empile, s'aligne (voie A du 129b)… et le composite
l'IGNORAIT. Le J2 livre le premier des cinq modes de fusion — « ajout au
rouge », DÉFAUT des 13 arbitrages d'Alain du 15/10/2026 — plus son cadre
d'interface. Formule, appliquée APRÈS le combine L dans l'espace normalisé de
`composer()` :

    R' = R + poids × (Ha − fond(Ha))

Vérifie :
  [1] les DÉFAUTS FIGÉS (mode, poids 1,0 borné [0 ; 10], alpha 0,5 et Q 0,80
      réservés à J3/J4) et la validation de `fusion_ha_effectif()` : None hors
      RGB+Ha/LRGB+Ha, mode inconnu → défaut, poids hors bornes → borné,
      valeur illisible → défaut ;
  [2] la FORMULE exacte, AU BIT : R décalé de `poids × (Ha − médiane(Ha))`,
      G et B INCHANGÉS ;
  [2b] le CONTINUUM (actif par défaut) : R ramené à la bande du Ha
      (`Q × 7/100 × (R − fond(R)) / échelle(Ha)`), signal ÉCRÊTÉ [0 ; 1],
      sans couche R → aucun retrait ;
  [3] le RECENTRAGE : le fond du ciel ne bouge PAS (même quand le Ha a un
      fond à 1,0, cas de la normalisation commune) ; sans recentrage il
      bouge de `poids × fond(Ha)` — c'est le défaut qu'on évite ;
  [4] les NO-OPS rendent le MÊME objet (poids 0, Ha absent, forme
      incompatible) — aucun coût, aucune copie inutile ;
  [5] `composer()` : poids 0 = composite INCHANGÉ AU BIT ; avec poids, SEUL R
      change et l'écart vaut exactement le calcul ; HOO/SHO ne fusionnent
      JAMAIS ; RGB+Ha fusionne aussi (sans L) ;
  [6] la CLÉ DE MÉMOÏSATION du `CompositeStacker` porte le réglage : bouger le
      poids (ou le recentrage) refait le composite au lieu de resservir le
      cache — même piège que le lissage du 117d ;
  [7] l'INTERFACE (App réelle, Tk) : cadre « Fusion Ha » visible SEULEMENT en
      RGB+Ha/LRGB+Ha, poids borné à la saisie, réglage poussé sur le stacker,
      persistance relue ;
  [8] la FICHE DE RENDU dit la fusion (mode, poids, recentrage) et rien hors
      des compositions à Ha fusionné.

Exécution : python bancs/_test_fusion_ha_jalon2.py
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
from avastack.processing.composition import (ALPHA_HA_DEFAUT, BW_HA_NM,
                                             BW_RGB_NM, CONTINUUM_HA_DEFAUT,
                                             CompositeStacker,
                                             FUSION_HA_DEFAUT,
                                             METHODE_CONTINUUM_DEFAUT,
                                             MODES_FUSION_HA, POIDS_HA_DEFAUT,
                                             POIDS_HA_MAX, POIDS_HA_MIN,
                                             Q_HA_DEFAUT, Q_HA_MAX, Q_HA_MIN,
                                             RECENTRER_HA_DEFAUT, composer,
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
    """Scène LRGB+Ha synthétique : ciel + bruit dans chaque rôle, une
    nébulosité COMPACTE (≈3 % de l'image), et un Ha dont le FOND est
    FRANCHEMENT plus haut (0,30) que celui du RGB — c'est ce fond qui rend le
    recentrage observable, et c'est exactement le cas « normalisation
    commune » (où il vaut ~1) qui inonderait le rouge sans lui. La nébulosité
    est compacte À DESSEIN : le fond estimé est une MÉDIANE, qui ne vaut le
    ciel que si l'objet couvre moins de la moitié de l'image."""
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
    rgb[..., 0] += 0.15          # un peu de signal dans R
    return rgb


# ========================================================== [1] défauts figés
print("[1] défauts figés et validation de `fusion_ha_effectif`")
verifie(MODES_FUSION_HA == ("ajout_rouge", "fondu_rouge", "ecran_rouge",
                            "eclaircir_rouge", "ha_luminance")
        and FUSION_HA_DEFAUT == MODES_FUSION_HA[0],
        f"cinq modes, `ajout_rouge` en TÊTE et par défaut : {MODES_FUSION_HA}"
        " (volet mis à jour VOLONTAIREMENT au J3 — il n'y en avait qu'un au J2)")
verifie(FUSION_HA_DEFAUT == "ajout_rouge" and POIDS_HA_DEFAUT == 1.0
        and (POIDS_HA_MIN, POIDS_HA_MAX) == (0.0, 10.0),
        "défauts figés : ajout_rouge, poids 1,0 borné [0 ; 10]")
verifie(ALPHA_HA_DEFAUT == 0.5 and Q_HA_DEFAUT == 0.80
        and RECENTRER_HA_DEFAUT is True,
        "α 0,5 (J3), Q 0,80 (J4) et recentrage COCHÉ déjà définis")
d = fusion_ha_effectif("LRGB+Ha", None)
attendu_defauts = {"mode": "ajout_rouge", "poids": 1.0, "alpha": ALPHA_HA_DEFAUT,
                   "recentrer": True, "continuum": True, "q": 0.80,
                   "methode_continuum": "bandes_passantes", "bw_ha": 7.0}
verifie(d == attendu_defauts,
        f"LRGB+Ha sans réglage → défauts complets : {d}")
verifie(BW_HA_NM == 7.0 and BW_RGB_NM == 100.0
        and CONTINUUM_HA_DEFAUT is True
        and METHODE_CONTINUUM_DEFAUT == "bandes_passantes",
        "continuum : bandes passantes Ha 7 nm / R 100 nm, ACTIF par défaut")
verifie(fusion_ha_effectif("RGB+Ha", {}) == d,
        "RGB+Ha : mêmes défauts")
verifie(fusion_ha_effectif("HOO", {"poids": 3.0}) is None
        and fusion_ha_effectif("SHO", {"poids": 3.0}) is None
        and fusion_ha_effectif("LRGB", {"poids": 3.0}) is None
        and fusion_ha_effectif("RGB", {"poids": 3.0}) is None,
        "HOO/SHO (Ha = canal), LRGB et RGB : AUCUNE fusion")
verifie(fusion_ha_effectif("LRGB+Ha", {"mode": "inconnu"})["mode"]
        == "ajout_rouge"
        and fusion_ha_effectif("LRGB+Ha",
                               {"methode_continuum": "inconnue"}
                               )["methode_continuum"]
        == "bandes_passantes",
        "mode/méthode inconnus → DÉFAUTS (jamais une exception)")
verifie(fusion_ha_effectif("LRGB+Ha", {"poids": 99})["poids"] == POIDS_HA_MAX
        and fusion_ha_effectif("LRGB+Ha", {"poids": -3})["poids"] == 0.0,
        "poids hors bornes → borné (99 → 10, −3 → 0)")
verifie(fusion_ha_effectif("LRGB+Ha", {"q": 9})["q"] == Q_HA_MAX
        and fusion_ha_effectif("LRGB+Ha", {"q": 0.01})["q"] == Q_HA_MIN,
        f"Q hors bornes → borné (9 → {Q_HA_MAX}, 0,01 → {Q_HA_MIN})")
verifie(fusion_ha_effectif("LRGB+Ha", {"poids": "illisible"})["poids"]
        == POIDS_HA_DEFAUT,
        "poids illisible → défaut 1,0 (jamais 0, qui passerait pour « sans "
        "effet »)")
verifie(fusion_ha_effectif("LRGB+Ha", {"recentrer": False})["recentrer"]
        is False
        and fusion_ha_effectif("LRGB+Ha", {"continuum": False})["continuum"]
        is False,
        "recentrage et continuum sont RÉGLABLES (cases du J2/J4)")

# ========================================================= [2] formule au bit
print("[2] formule exacte : R + poids × (Ha − fond), G et B au bit")
rgb = composite_rgb()
ha = scene()["Ha"]
attendu = rgb.copy()
attendu[..., 0] += (ha - np.float32(np.median(ha)))
out = fusionner_ha(rgb, ha)                      # défauts : ajout, 1,0
verifie(np.array_equal(out, attendu),
        "poids 1,0 : R' == R + (Ha − médiane(Ha)) AU BIT")
verifie(np.array_equal(out[..., 1:], rgb[..., 1:]),
        "G et B INCHANGÉS au bit (la fusion ne touche QUE le rouge)")
attendu25 = rgb.copy()
attendu25[..., 0] += 2.5 * (ha - np.float32(np.median(ha)))
verifie(np.allclose(fusionner_ha(rgb, ha, poids=2.5), attendu25, atol=1e-6,
                    rtol=0),
        "poids 2,5 : l'ajout est bien PROPORTIONNEL au poids")
verifie(np.array_equal(fusionner_ha(rgb, ha, mode="inconnu"), out),
        "mode inconnu → même résultat que le mode par défaut")

# ================================================= [2b] continuum (formule)
print("[2b] continuum : R ramené à la bande du Ha, écrêté [0 ; 1]")
r_raw = scene()["R"]
ECH = 0.5          # échelle arbitraire du volet (unités du Ha normalisé)
k = np.float32(Q_HA_DEFAUT * (BW_HA_NM / BW_RGB_NM) / ECH)
sig = ((ha - np.float32(np.median(ha)))
       - k * (r_raw - np.float32(np.median(r_raw))))
sig = np.clip(sig, 0.0, 1.0)
att_cont = rgb.copy()
att_cont[..., 0] += sig
out_cont = fusionner_ha(rgb, ha, continuum=True, q=Q_HA_DEFAUT,
                        r_reference=r_raw, echelle_ha=ECH)
verifie(np.array_equal(out_cont, att_cont),
        "R' = R + [Ha − fond − Q×(7/100)×(R − fond(R))/échelle] AU BIT")
verifie(np.array_equal(out_cont[..., 1:], rgb[..., 1:]),
        "continuum : G et B toujours INCHANGÉS")
verifie(np.all(out_cont[..., 0] >= rgb[..., 0]),
        "le signal est ÉCRÊTÉ à [0 ; 1] : le continuum ne fait que RETIRER "
        "(aucun rouge négatif)")
verifie(np.array_equal(fusionner_ha(rgb, ha, continuum=True, r_reference=None),
                       fusionner_ha(rgb, ha, continuum=False)),
        "continuum demandé SANS couche R → aucun retrait (jamais d'exception)")

# ============================================================ [3] recentrage
print("[3] recentrage : le fond du ciel ne bouge pas")
# On mesure le FOND sur le CIEL (tous les pixels loin de la nébulosité) : une
# médiane GLOBALE ne conviendrait pas, `médiane(R + δ)` n'étant pas
# `médiane(R) + médiane(δ)`, et un seul coin est trop bruité.
_h, _w = ha.shape
_yy, _xx = np.mgrid[0:_h, 0:_w]
CIEL = np.hypot(_yy - _h / 2.0, _xx - _w / 2.0) > (_h * 0.35)


def fond_ciel(img):
    return float(np.mean(img[..., 0][CIEL]))


fond0 = fond_ciel(rgb)
recent = fusionner_ha(rgb, ha, poids=1.0, recentrer=True)
brut = fusionner_ha(rgb, ha, poids=1.0, recentrer=False)
verifie(abs(fond_ciel(recent) - fond0) < 0.01,
        f"recentré : le FOND du rouge bouge de "
        f"{fond_ciel(recent) - fond0:+.5f} (négligeable)")
verifie(fond_ciel(brut) - fond0 > 0.2,
        f"sans recentrage : le fond monterait de "
        f"{fond_ciel(brut) - fond0:+.5f} (tout le fond du Ha) — défaut évité")
ha_fond_un = (ha + np.float32(0.70)).astype(np.float32)   # cas « norm. commune »
r_un = fusionner_ha(rgb, ha_fond_un, poids=3.0, recentrer=True)
verifie(abs(fond_ciel(r_un) - fond0) < 0.03,
        f"Ha à fond 1,0 (normalisation commune), poids 3 : le fond reste "
        f"immobile ({fond_ciel(r_un) - fond0:+.5f}, contre +3,0 sans "
        "recentrage) — c'est pourquoi il est le défaut du J2")

# ================================================================= [4] no-ops
print("[4] no-ops : MÊME objet rendu (aucun coût)")
verifie(fusionner_ha(rgb, ha, poids=0.0) is rgb,
        "poids 0 → composite rendu TEL QUEL (pas même une copie)")
verifie(fusionner_ha(rgb, None) is rgb,
        "Ha absent (aucune frame) → composite inchangé")
verifie(fusionner_ha(rgb, ha[:10, :10]) is rgb,
        "forme incompatible → composite inchangé (jamais une exception)")
verifie(fusionner_ha(None, ha) is None and fusionner_ha(rgb, ha[None]) is rgb,
        "entrées dégénérées : aucune exception")

# ========================================================= [5] composer()
print("[5] `composer()` : poids 0 au bit, poids > 0 sur le SEUL rouge")
canaux = scene()
bornes = {r: compo.bornes_normalisation(a) for r, a in canaux.items()}
base = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                fusion_ha={"poids": 0.0})       # référence SANS fusion
norm_ha = normaliser(canaux["Ha"], *bornes["Ha"])
med_ha = np.float32(np.median(norm_ha))
ECH_HA = float(bornes["Ha"][1] - bornes["Ha"][0])
# --- ajout PUR (continuum coupé) : la formule du [2]
pur = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
               fusion_ha={"poids": 1.0, "continuum": False})
verifie(np.allclose(pur[..., 0], base[..., 0] + (norm_ha - med_ha),
                    atol=1e-6, rtol=0),
        "continuum COUPÉ : rouge = R + (Ha normalisé − son fond), au bit près")
verifie(np.array_equal(pur[..., 1:], base[..., 1:]),
        "continuum COUPÉ : G et B INCHANGÉS au bit")
# --- DÉFAUTS : continuum ACTIF (demande d'Alain du 18/10)
defaut = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0)
verifie(not np.array_equal(defaut[..., 0], pur[..., 0]),
        "les DÉFAUTS soustraient le continuum : le rouge diffère de l'ajout pur")
k = np.float32(Q_HA_DEFAUT * (BW_HA_NM / BW_RGB_NM) / ECH_HA)
sig = ((norm_ha - med_ha)
       - k * (canaux["R"] - np.float32(np.median(canaux["R"]))))
sig = np.clip(sig, 0.0, 1.0)
att_cont = base[..., 0] + sig
verifie(np.allclose(defaut[..., 0], att_cont, atol=1e-6, rtol=0),
        "continuum par défaut : rouge = R + [Ha − fond − Q×(7/100)×R/échelle] "
        "écrêté, exactement")
verifie(np.array_equal(defaut[..., 1:], base[..., 1:]),
        "continuum actif : G et B INCHANGÉS au bit")
explicite = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                     fusion_ha={"mode": "ajout_rouge", "poids": 1.0,
                                "recentrer": True, "continuum": True,
                                "q": Q_HA_DEFAUT})
verifie(np.array_equal(defaut, explicite),
        "aucun réglage → MÊMES défauts complets (dont le continuum)")
p2 = composer(canaux, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
              fusion_ha={"mode": "ajout_rouge", "poids": 2.0,
                         "continuum": False})
verifie(np.array_equal(p2[..., 1:], base[..., 1:]),
        "poids 2,0 (continuum coupé) : G et B du composite INCHANGÉS au bit")
verifie(not np.array_equal(p2[..., 0], base[..., 0]),
        "poids 2,0 : le rouge, lui, change bien")
att = base[..., 0] + 2.0 * (norm_ha - med_ha)
verifie(np.allclose(p2[..., 0], att, atol=1e-6, rtol=0),
        "poids 2,0 : le rouge vaut EXACTEMENT R + 2 × (Ha normalisé − son fond)")
sansR = {r: a for r, a in canaux.items() if r != "R"}
s0 = composer(sansR, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
              fusion_ha={"poids": 1.0, "continuum": False})
s1 = composer(sansR, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
              fusion_ha={"poids": 1.0, "continuum": True})
verifie(np.array_equal(s0, s1),
        "aucune couche R : le continuum reste SANS EFFET (composite au bit)")
hoo0 = composer(canaux, "HOO", bornes=bornes, sigma_l=0.0)
hoo1 = composer(canaux, "HOO", bornes=bornes, sigma_l=0.0,
                fusion_ha={"poids": 5.0})
verifie(np.array_equal(hoo0, hoo1),
        "HOO : la fusion n'a AUCUN effet (le Ha y est déjà le canal vert)")
rgbha0 = composer(canaux, "RGB+Ha", bornes=bornes)          # défauts
rgbha1 = composer(canaux, "RGB+Ha", bornes=bornes,
                  fusion_ha={"poids": 0.0})
verifie(not np.array_equal(rgbha0[..., 0], rgbha1[..., 0])
        and np.array_equal(rgbha0[..., 1:], rgbha1[..., 1:]),
        "RGB+Ha (sans L) : la fusion agit aussi, sur le seul rouge")
sans_ha = {r: a for r, a in canaux.items() if r != "Ha"}
sans0 = composer(sans_ha, "LRGB+Ha", bornes=bornes, sigma_l=0.0)
sans1 = composer(sans_ha, "LRGB+Ha", bornes=bornes, sigma_l=0.0,
                 fusion_ha={"poids": 3.0})
verifie(np.array_equal(sans0, sans1),
        "aucune frame Ha : fusion sans objet → composite INCHANGÉ au bit")

# ==================================================== [6] clé de mémoïsation
print("[6] mémoïsation : le réglage de fusion fait partie de la CLÉ")


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
st.fusion_ha = {"mode": "ajout_rouge", "poids": 2.0, "continuum": False}
a3 = st.mean()
verifie(a3 is not a1 and not np.array_equal(a3[..., 0], a1[..., 0])
        and np.array_equal(a3[..., 1:], a1[..., 1:]),
        "poids changé → composite REFAIT, seul le rouge diffère")
st.fusion_ha = {"mode": "ajout_rouge", "poids": 2.0, "recentrer": False,
                "continuum": False}
a4 = st.mean()
decal = fond_ciel(a4) - fond_ciel(a3)
verifie(a4 is not a3 and 0.005 < decal < 0.2,
        f"recentrage décoché → composite REFAIT, le fond monte de {decal:.4f} "
        "(le recentrage est bien dans la clé)")
st.fusion_ha = {"poids": 0.0}
a5 = st.mean()
verifie(np.array_equal(a5, a1),
        "retour à poids 0 → composite identique à SANS fusion, AU BIT")
st.fusion_ha = None                       # None = DÉFAUTS (poids 1,0)
a6 = st.mean()
verifie(a6 is not a5 and not np.array_equal(a6[..., 0], a5[..., 0]),
        "None = DÉFAUTS ACTIFS : le Ha s'ajoute (poids 1,0) dès qu'une couche "
        "Ha existe")
# Le CONTINUUM est dans la clé : l'activer, puis changer Q, refait le composite.
st.fusion_ha = {"poids": 2.0, "continuum": True}
a7 = st.mean()
st.fusion_ha = {"poids": 2.0, "continuum": True, "q": 1.9}
a8 = st.mean()
verifie(a8 is not a7 and not np.array_equal(a8, a7),
        "Q du continuum dans la clé : changer Q REFAIT le composite")
st.fusion_ha = {"poids": 2.0, "continuum": False}
a9 = st.mean()
verifie(np.array_equal(a9, a3),
        "couper le continuum redonne EXACTEMENT l'ajout pur (Q sans effet)")

# ============================================================ [7] interface
print("[7] interface : cadre « Fusion Ha » visible SEULEMENT avec un Ha fusionné")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui               # noqa: E402
ui.CONFIG = {}                             # jamais toucher à la vraie config
captures: list[dict] = []
ui.sauver_config = lambda d: captures.append(dict(d))
ui.App._avertir = lambda self, titre, message: None   # aucune boîte modale
app = ui.App(root)
app._mode_compo = False

verifie(app.frm_fusion_ha.winfo_manager() == "",
        "composition par défaut (HOO) : cadre « Fusion Ha » MASQUÉ")
app.var_compo.set("RGB+Ha")
app._on_compo()
verifie(app.frm_fusion_ha.winfo_manager() == "pack",
        "RGB+Ha : cadre VISIBLE")
app.var_compo.set("LRGB+Ha")
app._on_compo()
verifie(app.frm_fusion_ha.winfo_manager() == "pack",
        "LRGB+Ha : cadre VISIBLE")
app.var_compo.set("RGB")
app._on_compo()
verifie(app.frm_fusion_ha.winfo_manager() == "",
        "RGB : cadre MASQUÉ (le Ha n'y existe pas)")
app.var_compo.set("SHO")
app._on_compo()
verifie(app.frm_fusion_ha.winfo_manager() == "",
        "SHO : cadre MASQUÉ (le Ha y est un CANAL, pas une fusion)")

app.var_compo.set("LRGB+Ha")
app._on_compo()
# --- CONTINUUM : sans dossier R, la case est DÉSACTIVÉE et le réglage
# effectif vaut False (il n'y a rien pour estimer le continuum).
app.var_fusion_ha_continuum.set(True)
app._maj_fusion_ha()
verifie(str(app.chk_fusion_ha_continuum.cget("state")) == "disabled"
        and app._lire_fusion_ha()["continuum"] is False,
        "aucun dossier R : case continuum DÉSACTIVÉE, réglage forcé à False")
ligne_r = next(i for i in range(compo.NB_LIGNES_COMPO)
               if app.var_compo_roles[i].get() == "R")
app.var_compo_dossiers[ligne_r].set("C:/brutes/R")
app._maj_fusion_ha()
verifie(str(app.chk_fusion_ha_continuum.cget("state")) == "normal"
        and app._lire_fusion_ha()["continuum"] is True,
        "dossier R renseigné : case continuum ACTIVE et prise en compte")
app.var_fusion_ha_q.set(9.0)
verifie(app._lire_fusion_ha()["q"] == Q_HA_MAX,
        f"saisie Q 9 → borné à {Q_HA_MAX}")
app.var_fusion_ha_q.set(0.65)
app.var_fusion_ha_poids.set(99.0)
verifie(app._lire_fusion_ha()["poids"] == POIDS_HA_MAX,
        "saisie 99 → poids BORNÉ à 10 à la lecture")
app.var_fusion_ha_poids.set(-4.0)
verifie(app._lire_fusion_ha()["poids"] == POIDS_HA_MIN,
        "saisie −4 → poids BORNÉ à 0")
app.var_fusion_ha_poids.set(2.5)
app.stacker = CompositeStacker("LRGB+Ha")
app._on_fusion_ha()
sth = app.stacker.fusion_ha
verifie(sth["mode"] == "ajout_rouge" and sth["poids"] == 2.5
        and sth["continuum"] is True and sth["q"] == 0.65
        and sth["recentrer"] is True,
        f"réglage poussé sur le STACKER : {sth}")
verifie(app._compo_fusion_ha == sth,
        "instantané `_compo_fusion_ha` posé pour le worker")

app._sauver_config_app()
c = captures[-1]
verifie(c.get("fusion_ha_mode") == "ajout_rouge"
        and float(c.get("fusion_ha_poids", -1.0)) == 2.5
        and c.get("fusion_ha_continuum") is True
        and float(c.get("fusion_ha_q", -1.0)) == 0.65,
        f"persisté : mode={c.get('fusion_ha_mode')} "
        f"poids={c.get('fusion_ha_poids')} "
        f"continuum={c.get('fusion_ha_continuum')} q={c.get('fusion_ha_q')}")
ui.CONFIG = c
app.var_fusion_ha_poids.set(1.0)           # on casse les valeurs…
app.var_fusion_ha_q.set(0.80)
app.var_fusion_ha_continuum.set(False)
app._restaurer_config()                    # … puis on relit la config
verifie(float(app.var_fusion_ha_poids.get()) == 2.5
        and float(app.var_fusion_ha_q.get()) == 0.65
        and bool(app.var_fusion_ha_continuum.get()) is True,
        "config relue : poids, Q et continuum RESTAURÉS")

# ======================================================== [8] fiche de rendu
print("[8] fiche de rendu : la fusion est DITE, et seulement quand elle agit")
app.var_compo.set("LRGB+Ha")
app._on_compo()
app.var_fusion_ha_poids.set(2.5)
app.var_fusion_ha_q.set(Q_HA_DEFAUT)
app.var_fusion_ha_continuum.set(True)
app._maj_fusion_ha()
app.stacker = CompositeStacker("LRGB+Ha")
app.stacker.stackers = {"Ha": _FauxStacker(canaux["Ha"]),
                        "R": _FauxStacker(canaux["R"])}   # Ha ET R non vides
app._on_fusion_ha()
reg = app._reglages_rendu()
attendu = {"mode": "ajout_rouge", "poids": 2.5, "alpha": ALPHA_HA_DEFAUT,
           "recentrer": True, "continuum": True, "q": Q_HA_DEFAUT,
           "methode_continuum": "bandes_passantes", "bw_ha": 7.0}
verifie(reg.get("compo_fusion") == attendu,
        f"réglages capturés : {reg.get('compo_fusion')}")
chaine = app._fiche_chaine(reg, "empilement", False)
noms = [e["etape"] for e in chaine]
verifie("fusion Ha" in noms,
        "la chaîne porte une étape « fusion Ha »")
if "fusion Ha" in noms:
    etape = chaine[noms.index("fusion Ha")]
    verifie(etape.get("mode") == "ajout_rouge"
            and float(etape.get("poids", -1.0)) == 2.5
            and etape.get("recentrer") is True
            and etape.get("continuum") is True
            and float(etape.get("q", -1.0)) == Q_HA_DEFAUT,
            f"l'étape nomme mode, poids, recentrage, continuum et Q : {etape}")
    verifie(noms.index("fusion Ha")
            == noms.index("combine LRGB (rapport L/luma borne)") + 1,
            "elle vient JUSTE APRÈS le combine L (ordre du plan)")
else:
    verifie(False, "étape « fusion Ha » absente alors que la compo en a une")

app.stacker = CompositeStacker("HOO")
reg2 = app._reglages_rendu()
verifie(reg2.get("compo_fusion") is None,
        "HOO : aucune fusion dans les réglages")
noms2 = [e["etape"] for e in app._fiche_chaine(reg2, "empilement", False)]
verifie("fusion Ha" not in noms2,
        "HOO : aucune étape « fusion Ha » dans la fiche")

# Composition à Ha FUSIONNÉ mais AUCUNE frame Ha : la fiche ne doit pas
# prétendre avoir fusionné quoi que ce soit.
app.stacker = CompositeStacker("LRGB+Ha")
reg3 = app._reglages_rendu()
verifie(reg3.get("compo_fusion") is None,
        "compo à Ha mais couche Ha VIDE : rien à fusionner, la fiche se tait")
noms3 = [e["etape"] for e in app._fiche_chaine(reg3, "empilement", False)]
verifie("fusion Ha" not in noms3,
        "et aucune étape « fusion Ha » n'est écrite")

# Ha empilé mais AUCUNE couche R : le continuum n'a rien pu retirer, la fiche
# doit le déclarer FAUX (sinon elle mentirait sur un réglage sans effet).
app.stacker = CompositeStacker("LRGB+Ha")
app.stacker.stackers = {"Ha": _FauxStacker(canaux["Ha"])}
reg4 = app._reglages_rendu()
verifie((reg4.get("compo_fusion") or {}).get("continuum") is False,
        "couche R absente : la fiche DÉCLARE le continuum inactif")

root.destroy()
print()
print("VERDICT :", "TOUS LES VOLETS VERTS" if ok else "ÉCHEC")
sys.exit(0 if ok else 1)
