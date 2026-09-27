# -*- coding: utf-8 -*-
"""Banc v2.36.0 — NORMALISATION COMMUNE DES CANAUX (option, décision d'Alain
du 25/09/2026).

Ce que la mesure sur son empilement M31 a montré (et que ce banc reproduit sur
une scène synthétique) :

  • `composer()` normalise par défaut CHAQUE rôle par SES percentiles
    (p0,25/p99,7). Le percentile bas est toujours ~2,8 σ sous le ciel : le
    NIVEAU du fond du composite est donc PROPORTIONNEL AU BRUIT du canal.
    Conséquence : empiler plus fait baisser le fond et le grain dans la même
    proportion, l'étirement compense, et **le grain du fond ne s'améliore
    jamais** (mesuré : fond/σ = 2,88 à 28 frames, 2,50 à 111 frames, alors que
    le grain diminuait bien en 1/√n). Le grain est aussi COLORÉ, chaque canal
    étant divisé par SA dynamique.
  • Avec des bornes COMMUNES (celles du rôle qui alimente le canal VERT), le
    fond garde son niveau physique : seul le bruit baisse (≈1/√n) → **le grain
    du fond s'améliore enfin avec l'intégration**, et il redevient gris.

Vérifie :
  [1] composer(normalisation_commune=True) : mêmes bornes pour les 3 rôles, les
      rapports de fond PHYSIQUES sont conservés (par rôle : égalisés) ;
  [2] LA propriété décisive : à 30 puis 120 frames synthétiques (bruit en
      1/√n), le rapport grain/fond — par rôle reste ~constant, en commun
      s'améliore d'environ 2× ;
  [3] équilibre du grain : par rôle COLORÉ (B/G ≈ 1,4), en commun GRIS (≈1) ;
  [4] UI : case décochée par défaut, posée sur l'empilement, persistée en
      config, et annoncée dans l'en-tête FITS (AVACOMPO).

Exécution : python bancs/_test_norm_commune_jalon61.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import tempfile
import tkinter as tk

import numpy as np

from avastack.processing.composition import (CompositeStacker, composer,
                                             bornes_normalisation, normaliser)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

H = W = 192
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- scène synthétique « M31 » : ciel, galaxie jaune (B faible), bruit -------
# Les AMPLITUDES diffèrent par canal (M31 est jaune : peu de signal bleu) → les
# dynamiques (spans p99,7−p0,25) diffèrent → c'est CE déséquilibre qui rend le
# grain coloré sous normalisation par rôle.
CIEL = {"R": 0.030, "G": 0.045, "B": 0.020}
OBJ = {"R": 1.00, "G": 1.20, "B": 0.45}
BRUIT1 = {"R": 0.0030, "G": 0.0028, "B": 0.0026}      # σ par frame (quasi égal)


def couche(canal, frames, graine):
    """Couche synthétique : ciel + galaxie (profil gaussien) + bruit en 1/√n.
    σ par canal quasi ÉGAL (comme les couches réelles mesurées chez Alain :
    0,000498 / 0,000557 / 0,000526 → grain équilibré AVANT la composition)."""
    rng = np.random.default_rng(graine)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt((x - W / 2.0) ** 2 + (y - H / 2.0) ** 2)
    noyau = (0.9 * np.exp(-(r / 18.0) ** 2) + 0.25 * np.exp(-(r / 30.0) ** 2))
    img = CIEL[canal] + OBJ[canal] * noyau
    img += rng.normal(0.0, BRUIT1[canal] / np.sqrt(frames), img.shape)
    return img.astype(np.float32)


def scene(frames, graine=1):
    return {c: couche(c, frames, graine + i)
            for i, c in enumerate(("R", "G", "B"))}


_MASQUE_CIEL = None


def grain_et_fond(img):
    """(σ, fond) par canal sur la COURONNE EXTERNE (r > 66 px) : ciel PUR de la
    scène synthétique (galaxie centrée) — ni halo ni gradient, donc c'est bien
    le GRAIN qu'on mesure, pas une structure."""
    global _MASQUE_CIEL
    if _MASQUE_CIEL is None:
        y, x = np.mgrid[0:H, 0:W]
        _MASQUE_CIEL = (np.sqrt((x - W / 2.0) ** 2
                                + (y - H / 2.0) ** 2) > 66)
    a = np.asarray(img, np.float32)[_MASQUE_CIEL]
    sig, fond = [], []
    for c in range(3):
        v = a[:, c]
        m = float(np.median(v))
        fond.append(m)
        sig.append(1.4826 * float(np.median(np.abs(v - m))))
    return sig, fond


# ============================================ [1] deux modes, deux échelles
print("[1] composer : échelle COMMUNE (option) vs normalisation par rôle")
ch = scene(60, graine=11)
par_role = composer(ch, "RGB")
commun = composer(ch, "RGB", normalisation_commune=True)
echelle = bornes_normalisation(ch["G"])           # référence = rôle du VERT
span_g = echelle[1] - echelle[0]
verifie(np.allclose(commun[..., 1], normaliser(ch["G"], 0.0, span_g)),
        "le canal VERT donne l'ÉCHELLE de référence (aucun point noir retiré)")
verifie(np.allclose(commun[..., 0], normaliser(ch["R"], 0.0, span_g))
        and np.allclose(commun[..., 2], normaliser(ch["B"], 0.0, span_g)),
        "R et B partagent cette échelle (x / amplitude du vert)")
verifie(not np.allclose(par_role, commun)
        and float(commun.min()) >= 0.0,
        "les deux modes diffèrent, et le mode commun ne crée AUCUNE valeur "
        "négative (c'est pourquoi il n'y a pas de point noir commun)")
img_ch = np.stack([ch[c] for c in "RGB"], -1)
_, n_ch = grain_et_fond(img_ch)
_, n_par = grain_et_fond(par_role)
_, n_com = grain_et_fond(commun)
r_ch = (n_ch[0] / n_ch[1], n_ch[2] / n_ch[1])
r_par = (n_par[0] / n_par[1], n_par[2] / n_par[1])
r_com = (n_com[0] / n_com[1], n_com[2] / n_com[1])
verifie(abs(r_com[0] - r_ch[0]) < 0.02 and abs(r_com[1] - r_ch[1]) < 0.02,
        f"échelle commune : les rapports de fond sont ceux des COUCHES "
        f"(physiques) — {np.round(r_com, 3)} vs {np.round(r_ch, 3)}")
verifie(abs(r_par[0] - r_ch[0]) > 0.05 or abs(r_par[1] - r_ch[1]) > 0.05,
        f"normalisation par rôle : les rapports de fond ne sont PLUS ceux des "
        f"couches — {np.round(r_par, 3)} vs {np.round(r_ch, 3)} (chaque canal "
        f"est décalé par SON point noir)")

# ======================= [2] LA propriété décisive : le grain s'améliore en 1/√n
print("[2] le grain du FOND s'améliore enfin avec l'intégration (1/√n)")
res = {}
for mode, commun_ in (("par rôle", False), ("commun", True)):
    for frames in (30, 120):
        img = composer(scene(frames, graine=200), "RGB",
                       normalisation_commune=commun_)
        sig, nivo = grain_et_fond(img)
        res[(mode, frames)] = [sig[i] / max(abs(nivo[i]), 1e-9)
                               for i in range(3)]
for mode in ("par rôle", "commun"):
    g30, g120 = res[(mode, 30)][2], res[(mode, 120)][2]
    print(f"    {mode:<9} : grain/fond (B) {g30:.4f} à 30 frames → "
          f"{g120:.4f} à 120 frames  (facteur {g30 / g120:.2f}×)")
c30, c120 = res[("commun", 30)][2], res[("commun", 120)][2]
p30, p120 = res[("par rôle", 30)][2], res[("par rôle", 120)][2]
verifie(c30 / c120 > 1.6,
        f"échelle commune : le grain du fond s'améliore d'un facteur "
        f"{c30 / c120:.2f}× (théorie : 2,0×) quand on passe de 30 à 120 frames")
verifie(p30 / p120 < 1.35,
        f"normalisation par rôle : il reste quasiment CONSTANT "
        f"({p30 / p120:.2f}×) — c'est le constat réel d'Alain "
        f"(fond/σ 2,88 à 28 frames → 2,50 à 111 frames)")

# =========================================== [3] équilibre du grain (couleur)
print("[3] équilibre du grain : coloré par rôle, gris en échelle commune")
sig_par = grain_et_fond(par_role)[0]
sig_com = grain_et_fond(commun)[0]
sig_src = grain_et_fond(img_ch)[0]
print(f"    couches    : R/G {sig_src[0]/sig_src[1]:.3f} · "
      f"B/G {sig_src[2]/sig_src[1]:.3f}")
print(f"    par rôle   : R/G {sig_par[0]/sig_par[1]:.3f} · "
      f"B/G {sig_par[2]/sig_par[1]:.3f}")
print(f"    commun     : R/G {sig_com[0]/sig_com[1]:.3f} · "
      f"B/G {sig_com[2]/sig_com[1]:.3f}")
verifie(sig_par[2] / sig_par[1] > 1.25,
        f"par rôle : le grain est COLORÉ (B/G {sig_par[2]/sig_par[1]:.3f})")
verifie(abs(sig_com[2] / sig_com[1] - sig_src[2] / sig_src[1]) < 0.05,
        f"échelle commune : le grain garde l'équilibre des COUCHES "
        f"(B/G {sig_com[2]/sig_com[1]:.3f} ≈ {sig_src[2]/sig_src[1]:.3f})")


# ================================= [4] UI : option, transport, persistance, sortie
print("[4] UI : case décochée par défaut, posée sur l'empilement, persistée, en-tête")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui               # noqa: E402
ui.CONFIG = {}                             # jamais toucher à la vraie config
vus = []                                   # intercepte ce que l'app écrit en config
ui.sauver_config = lambda d: vus.append(d)
app = ui.App(root)
verifie(hasattr(app, "var_norm_commune")
        and bool(app.var_norm_commune.get()) is False
        and bool(app._norm_commune) is False,
        "case « Normalisation commune des canaux » présente et DÉCOCHÉE par défaut")
app._mode_compo = True                     # l'en-tête AVACOMPO n'existe qu'en compo
st = CompositeStacker("RGB")
app.stacker = st
app.var_norm_commune.set(True)
app._on_norm_commune()
verifie(bool(st.normalisation_commune) is True,
        "cochée : l'option est posée sur l'empilement courant (vue traitée comprise)")
verifie(bool(app._norm_commune) is True,
        "l'instantané lu par le THREAD worker suit la case (jamais de variable Tk)")
app._sauver_config_app()
verifie(bool(vus and vus[-1].get("norm_commune")) is True,
        "l'option est persistée en config (case cochée → True)")
ui.CONFIG = {"norm_commune": True}
app.var_norm_commune.set(False)
app._norm_commune = False
app._restaurer_config()
verifie(bool(app.var_norm_commune.get()) is True
        and bool(app._norm_commune) is True,
        "relue depuis la config : case ET instantané restaurés")
verifie("COMMUNE" in str(app._entete_reglages().get("AVACOMPO", "")),
        "l'en-tête FITS annonce la normalisation COMMUNE (AVACOMPO)")
app.var_norm_commune.set(False)
app._on_norm_commune()
h_def = str(app._entete_reglages().get("AVACOMPO", ""))
verifie("COMMUNE" not in h_def and "normalisation" in h_def,
        f"case décochée : l'en-tête revient au défaut — « {h_def} »")
root.destroy()

print()
print("RÉSULTAT :", "TOUT OK" if ok else "ÉCHECS À CORRIGER")
sys.exit(0 if ok else 1)
