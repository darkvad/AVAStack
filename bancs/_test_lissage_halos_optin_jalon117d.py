# -*- coding: utf-8 -*-
"""Banc v2.71.0 (jalon 117d) — LISSAGE DU COMBINE LRGB : OPT-IN + σ RÉGLABLE.

Contexte (décision d'Alain, 10/10/2026) : le correctif du 117c (lisser le rapport
L/luma à l'échelle des étoiles, dans un masque d'étoiles brillantes) a été
VALIDÉ en réel, MAIS son seuil de masque (20σ) est un réglage EMPIRIQUE, calé
sur le jeu d'essai (le disque d'une galaxie gonfle la MAD) : sa validité sur une
autre image n'était pas garantie, et il s'appliquait PARTOUT, sans choix. On en
fait donc une OPTION visible.

Ce banc vérifie :
  [1] OPT-OUT (défaut) : case DÉCOCHÉE → σ = 0 → composite BIT-IDENTIQUE au
      combine d'avant le 117c (halos visibles) ;
  [2] OPT-IN : case COCHÉE → le halo d'étoile est bien réduit (rapport
      anneau/cœur) et le composite DIFFÈRE de l'opt-out ;
  [3] σ RÉGLABLE : le seuil du masque AGIT (seuil très haut → aucune étoile
      masquée → composite = opt-out ; seuil bas → masque actif → composite ≠) ;
  [4] MÉMOÏSATION : changer lissage/seuil INVALIDE le cache du composite ;
  [5] TRANSPORT live : `params_lissage_halos` (déballage TOLÉRANT des jobs d'avant
      le 117d : absent/6/7 éléments → inactif) ;
  [6] UI : case présente et DÉCOCHÉE par défaut, champ σ, posée sur l'empilement,
      persistée en config, annoncée dans l'en-tête FITS (AVACOMPO) ;
  [7] garde-fous : σ clampé, composite RGB / L synthétisé IGNORE le réglage,
      `composer()` garde ses défauts (rétro-compatibilité du 117c).

Exécution : python bancs/_test_lissage_halos_optin_jalon117d.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import tkinter as tk
from tkinter import ttk

import numpy as np

from avastack.processing.composition import (SEUIL_MASQUE_MAX, SEUIL_MASQUE_MIN,
                                             SEUIL_MASQUE_SIGMA,
                                             CompositeStacker, composer)
from avastack.processing import display as dp_mod

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
    cœur) autour du CENTRE de l'image — la métrique du diagnostic 117c/117d."""
    lum = _luma(comp) if comp.ndim == 3 else comp
    h, w = lum.shape
    cy, cx = h // 2, w // 2
    coeur = float(lum[cy, cx])
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    anneau = (r >= r_min) & (r <= r_max)
    return (float(lum[anneau].mean()) / coeur) if coeur > 0 else float("nan")


def _canaux_lrgb(forme=(160, 160), sigma_rgb=1.3, sigma_l=1.5, fond=0.002,
                 bruit=0.0005, graine=5):
    """Dict LRGB synthétique : une étoile BRILLANTE au CENTRE (même position dans
    R/G/B, PSF étroite ; dans L, PSF PLUS LARGE — le mismatch réel du 117c) et
    quelques étoiles FAIBLES dispersées, pour que le SEUIL du masque ait un effet
    observable (10σ n'en masque pas le même nombre que 80σ)."""
    h, w = forme
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h // 2, w // 2
    d2 = (yy - cy) ** 2 + (xx - cx) ** 2
    rng = np.random.default_rng(graine)
    b = bruit * rng.normal(0.0, 1.0, (h, w)).astype(np.float32)
    faibles = [(30, 40, 0.30), (120, 45, 0.15), (40, 125, 0.08),
               (128, 118, 0.05)]
    canaux = {}
    lum_amp = 0.0
    for role, poids in (("R", 0.299), ("G", 0.587), ("B", 0.114)):
        img = fond + b + poids * np.exp(-d2 / (2.0 * sigma_rgb ** 2))
        for (fy, fx, a) in faibles:
            img = img + poids * a * np.exp(
                -(((yy - fy) ** 2 + (xx - fx) ** 2) / (2.0 * sigma_rgb ** 2)))
        canaux[role] = img.astype(np.float32)
        lum_amp += poids * 1.0
    img_l = fond + b + lum_amp * np.exp(-d2 / (2.0 * sigma_l ** 2))
    for (fy, fx, a) in faibles:
        img_l = img_l + lum_amp * a * np.exp(
            -(((yy - fy) ** 2 + (xx - fx) ** 2) / (2.0 * sigma_l ** 2)))
    canaux["L"] = img_l.astype(np.float32)
    return canaux


B01 = {r: (0.0, 1.0) for r in ("L", "R", "G", "B")}
CANAUX = _canaux_lrgb()


def _stacker(lissage=False, seuil=SEUIL_MASQUE_SIGMA):
    """CompositeStacker LRGB alimenté des mêmes couches, avec les réglages voulus."""
    fa = CompositeStacker("LRGB")
    for role in ("L", "R", "G", "B"):
        fa.add(CANAUX[role], role)
    fa.lissage_halos = bool(lissage)
    fa.seuil_masque_halos = float(seuil)
    return fa


# ============================================= [1] opt-out = bit-identique 117c
print("[1] OPT-OUT (défaut) : case décochée → combine d'avant le 117c, AU BIT")
fa_off = _stacker(lissage=False)
verifie(fa_off.lissage_halos is False,
        "façade : lissage_halos DÉCOCHÉ par défaut")
off = fa_off.mean(corrections=False)
ref_off = composer(fa_off.moyennes(), "LRGB", sigma_l=0.0)
verifie(np.array_equal(off, ref_off),
        "case décochée = `composer(sigma_l=0)` AU BIT (aucun flou, pré-117c)")

# ==================================================== [2] opt-in réduit le halo
print("[2] OPT-IN : case cochée → le halo d'étoile est RÉDUIT, le composite change")
on = _stacker(lissage=True).mean(corrections=False)
r_off = _rapport_anneau_coeur(off)
r_on = _rapport_anneau_coeur(on)
verifie(not np.array_equal(off, on),
        "cochée : le composite DIFFÈRE de l'opt-out (le lissage agit)")
verifie(r_on < r_off,
        "le halo est réduit : rapport anneau/cœur %.4f → %.4f (÷ %.2f)"
        % (r_off, r_on, r_off / max(r_on, 1e-9)))

# ==================================================== [3] le seuil du masque agit
print("[3] σ RÉGLABLE : le seuil du masque AGIT")
bas = composer(CANAUX, "LRGB", bornes=B01, sigma_l=None, seuil_masque_sigma=3.0)
haut = composer(CANAUX, "LRGB", bornes=B01, sigma_l=None,
                seuil_masque_sigma=1.0e6)
ref_brut = composer(CANAUX, "LRGB", bornes=B01, sigma_l=0.0)
verifie(not np.allclose(bas, ref_brut),
        "seuil BAS (3σ) : masque actif → composite ≠ combine brut")
verifie(np.allclose(haut, ref_brut),
        "seuil TRÈS HAUT (1e6 σ) : AUCUNE étoile masquée → composite = combine brut")
verifie(not np.allclose(bas, haut),
        "deux seuils différents donnent DEUX composites différents")

# ============================================= [4] mémoïsation invalidée
print("[4] MÉMOÏSATION : changer le réglage INVALIDE le cache du composite")
fa_memo = _stacker(lissage=False)
a = fa_memo.mean(corrections=False)
b = fa_memo.mean(corrections=False)
verifie(np.array_equal(a, b),
        "mêmes réglages → composite mémoïsé (aucun changement)")
fa_memo.lissage_halos = True
c = fa_memo.mean(corrections=False)
verifie(not np.array_equal(a, c),
        "case cochée APRÈS coup → le composite est RECALCULÉ (cache invalidé)")
fa_memo.seuil_masque_halos = float(SEUIL_MASQUE_MAX)
d = fa_memo.mean(corrections=False)
verifie(not np.array_equal(c, d),
        "changer le SEUIL → recalcul aussi (seuil dans la clé du cache)")

# ==================================== [5] transport live : déballage tolérant
print("[5] TRANSPORT live : `params_lissage_halos` (jobs d'avant le 117d tolérés)")
verifie(dp_mod.params_lissage_halos(None) == (False, None),
        "compo None (mono) → lissage inactif")
verifie(dp_mod.params_lissage_halos((1, 2, 3, 4, 5, 6)) == (False, None),
        "job à 6 éléments (d'avant) → lissage inactif")
verifie(dp_mod.params_lissage_halos((1, 2, 3, 4, 5, 6, True)) == (False, None),
        "job à 7 éléments (v2.36.0) → lissage inactif")
verifie(dp_mod.params_lissage_halos((1, 2, 3, 4, 5, 6, True, (True, 15.0)))
        == (True, 15.0),
        "job à 8 éléments → (actif, seuil) lus")
verifie(dp_mod.params_lissage_halos((1, 2, 3, 4, 5, 6, True, (False, 15.0)))
        == (False, 15.0),
        "case décochée dans le job → lissage inactif (σ = 0 côté composer)")

# ============================================= [6] UI, config et en-tête FITS
print("[6] UI : case décochée par défaut, posée, persistée, en-tête (AVACOMPO)")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui               # noqa: E402
ui.CONFIG = {}                             # jamais toucher à la vraie config
vus = []                                   # intercepte ce que l'app écrit en config
ui.sauver_config = lambda d: vus.append(d)
app = ui.App(root)
verifie(hasattr(app, "var_lissage_halos")
        and bool(app.var_lissage_halos.get()) is False
        and bool(app._compo_lissage_halos) is False,
        "case « Lisser le combine LRGB » présente et DÉCOCHÉE par défaut")
verifie(abs(float(app.var_lissage_halos_sigma.get())
            - float(SEUIL_MASQUE_SIGMA)) < 1e-9,
        "champ « σ du masque » présent, défaut %g" % float(SEUIL_MASQUE_SIGMA))
textes = [str(w.cget("text")) for w in app.frm_compo.winfo_children()
          if isinstance(w, ttk.Checkbutton)]
verifie(any("Lisser le combine LRGB" in t for t in textes),
        "la case vit dans le cadre « Composition multi-filtres »")
app.var_lissage_halos_sigma.set(999.0)
verifie(abs(app._lire_seuil_halos() - SEUIL_MASQUE_MAX) < 1e-9,
        "σ saisi au-dessus de la borne → clampé à %g" % SEUIL_MASQUE_MAX)
app.var_lissage_halos_sigma.set(0.0)
verifie(abs(app._lire_seuil_halos() - SEUIL_MASQUE_MIN) < 1e-9,
        "σ saisi sous la borne → clampé à %g" % SEUIL_MASQUE_MIN)
app._mode_compo = True
st = CompositeStacker("LRGB")
app.stacker = st
app.var_lissage_halos.set(True)
app.var_lissage_halos_sigma.set(12.0)
app._on_lissage_halos()
verifie(bool(st.lissage_halos) is True
        and abs(float(st.seuil_masque_halos) - 12.0) < 1e-9,
        "cochée : le réglage est posé sur l'empilement courant (seuil 12)")
verifie(bool(app._compo_lissage_halos) is True
        and abs(float(app._compo_seuil_halos) - 12.0) < 1e-9,
        "les instantanés lus par le THREAD suivent la case (jamais de Tk)")
app._sauver_config_app()
verifie(bool(vus and vus[-1].get("lissage_halos")) is True
        and abs(float(vus[-1].get("lissage_halos_sigma", 0.0)) - 12.0) < 1e-9,
        "réglage persisté en config (lissage_halos / lissage_halos_sigma)")
ui.CONFIG = {"lissage_halos": True, "lissage_halos_sigma": 33.0}
app.var_lissage_halos.set(False)
app._compo_lissage_halos = False
app._restaurer_config()
verifie(bool(app.var_lissage_halos.get()) is True
        and bool(app._compo_lissage_halos) is True
        and abs(float(app.var_lissage_halos_sigma.get()) - 33.0) < 1e-9
        and abs(float(app._compo_seuil_halos) - 33.0) < 1e-9,
        "relus depuis la config : case, champ ET instantanés restaurés")
verifie("actif" in str(app._entete_reglages().get("AVACOMPO", "")),
        "l'en-tête FITS annonce le lissage ACTIF (AVACOMPO)")
app.var_lissage_halos.set(False)
app._on_lissage_halos()
h_def = str(app._entete_reglages().get("AVACOMPO", ""))
verifie("inactif" in h_def and "lissage combine LRGB" in h_def,
        f"case décochée : l'en-tête l'annonce INACTIF — « {h_def} »")
root.destroy()

# ==================================================== [7] garde-fous
print("[7] garde-fous : RGB/L synthétisé ignorent le réglage, défauts conservés")
rgb_off = composer({"R": CANAUX["R"], "G": CANAUX["G"], "B": CANAUX["B"]},
                   "RGB", bornes=B01, sigma_l=0.0)
rgb_on = composer({"R": CANAUX["R"], "G": CANAUX["G"], "B": CANAUX["B"]},
                  "RGB", bornes=B01, sigma_l=8.0, seuil_masque_sigma=5.0)
verifie(np.array_equal(rgb_off, rgb_on),
        "un composite RGB IGNORE le lissage et le seuil")
synth = composer({k: v for k, v in CANAUX.items() if k != "L"}, "LRGB",
                 bornes=B01, mode_l="synthetise")
synth_on = composer({k: v for k, v in CANAUX.items() if k != "L"}, "LRGB",
                    bornes=B01, mode_l="synthetise", sigma_l=None,
                    seuil_masque_sigma=3.0)
verifie(np.array_equal(synth, synth_on),
        "mode « L synthétisé » : identité, le réglage est IGNORÉ")
d_seuil = composer(CANAUX, "LRGB", bornes=B01, sigma_l=None,
                   seuil_masque_sigma=None)
d_def = composer(CANAUX, "LRGB", bornes=B01, sigma_l=None,
                 seuil_masque_sigma=SEUIL_MASQUE_SIGMA)
verifie(np.array_equal(d_seuil, d_def),
        "`seuil_masque_sigma=None` = SEUIL_MASQUE_SIGMA (défaut du 117c conservé)")


print()
print("RÉSULTAT :", "TOUT OK" if ok else "ÉCHECS À CORRIGER")
sys.exit(0 if ok else 1)
