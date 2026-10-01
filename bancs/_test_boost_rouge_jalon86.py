# -*- coding: utf-8 -*-
"""Banc jalon 86 (v2.48.0) — BOOST DU ROUGE (SII) MASQUÉ À L'OBJET.

Constat d'Alain (30/09/2026, capture v2.48.0 en chantier) : avec la préservation
de L* du jalon 85 la nébuleuse SHO n'est plus ÉTEINTE, mais elle reste VERTE —
« il manque le doré ». Le doré est physique (le rouge vient du SII, faible :
MESURÉ sur ses brutes, SII/Ha = 0,219) et les deux leviers essayés sont mesurés
et écartés : le « Linear Fit » gain + offset se cale sur le quart CENTRAL de
l'image (60,6 % d'objet ici), choisit un gain rouge au plafond (×4,0), colore le
fond (saturation 0,08 → 0,34 sur ses captures) et délaye la nébuleuse
(0,72 → 0,31) ; un gain R global teinte le ciel (97 % des pixels de fond en
R > V à ×2,5). Le levier retenu pèse son gain par la LUMINANCE — 0 dans le fond,
1 sur l'objet. Ce banc vérifie :

  [1] `couleurs.boost_rouge` : identité AU BIT à force 1,00 (le réglage peut
      rester en place), mono inchangé, entrée jamais modifiée, force illisible →
      défaut, force au-delà du maximum → PLAFONNÉE ;
  [2] le MASQUE : sur une scène synthétique, le fond ressort identique AU BIT et
      l'objet reçoit le gain — c'est la propriété qui distingue ce levier d'un
      gain global (fond teinté) et du Linear Fit (fond coloré, objet délavé) ;
  [3] l'OBJECTIF : à 3,00 le R:G de l'objet rejoint celui du Linear Fit, la
      saturation de l'objet est CONSERVÉE (le Linear Fit la fait tomber) et
      l'objet ne perd pas de lumière ; avec préservation de L*, il garde
      exactement celle d'avant ;
  [4] la CHAÎNE (`display.couleur_apres_etirement`) : tout décoché = identité au
      bit ; le boost est appliqué EN DERNIER (donc il n'est pas repris par le
      SCNR) et le SCNR garde son effet quand le boost est actif ;
  [5] les centiles du masque : le sous-échantillonnage /2 du calcul ne déplace
      pas les bornes (la revendication du docstring, vérifiée) ;
  [6] l'INTERFACE : case + curseur présents dans « Couleur de l'objet (APRÈS
      étirement) », défauts (décochée, 3,00), clé des réglages du solveur qui
      change, bornes appliquées, réglages de « tel que vu » transportés, config
      aller-retour, vue « traitée » inactive ;
  [7] coût : négligeable devant l'étirement, à l'échelle de l'aperçu.

Exécution : python bancs/_test_boost_rouge_jalon86.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time
import tkinter as tk
from tkinter import ttk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing import couleurs as coul
from avastack.processing import display as dsp

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def scene_sho(n=192, force_fond=0.04, graine=7):
    """Scène SHO RÉALISTE (mécanisme des jalons 85/86) : un fond faible, un halo
    vert (Ha) large et un cœur plus brillant, avec du bruit. Le VERT domine
    partout — c'est ce fond vert que le boost ne doit PAS toucher."""
    rng = np.random.default_rng(graine)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    r2 = ((yy - n / 2.0) ** 2 + (xx - n / 2.0) ** 2) / (n * 0.30) ** 2
    halo, coeur = np.exp(-r2), np.exp(-r2 * 9.0)
    base = force_fond + rng.normal(0.0, 0.004, (n, n)).astype(np.float32)
    im = np.empty((n, n, 3), np.float32)
    im[..., 0] = base + 0.16 * halo + 0.30 * coeur      # SII (rouge) : 0,22 × Ha
    im[..., 1] = base + 0.72 * halo + 0.85 * coeur      # Ha (vert) : la donnée
    im[..., 2] = base + 0.22 * halo + 0.35 * coeur      # OIII (bleu)
    return np.clip(im, 0.0, 1.0).astype(np.float32)


def masque_objet(im, pct=80.0):
    lum = im.mean(axis=2)
    return lum > np.percentile(lum, pct)


def masque_fond(im):
    lum = im.mean(axis=2)
    return lum < np.percentile(lum, 25)


def rv_objet(im, m=None):
    """(G:R, B:R) de l'objet et part de pixels R > V — le « doré »."""
    m = masque_objet(im) if m is None else m
    rgb = np.clip(im, 0.0, 1.0)[m].mean(axis=0)
    return (float(rgb[1] / max(rgb[0], 1e-9)), float(rgb[2] / max(rgb[0], 1e-9)),
            100.0 * float((im[..., 0][m] > im[..., 1][m]).mean()))


def saturation(im, m):
    hsv = cv2.cvtColor(np.clip(im, 0.0, 1.0), cv2.COLOR_RGB2HSV)
    return float(hsv[..., 1][m].mean())


def luminosite(im, m):
    return float(cv2.cvtColor(np.clip(im, 0.0, 1.0),
                              cv2.COLOR_RGB2LAB)[..., 0][m].mean())


# ============================================ [1] la fonction, ses garde-fous
print("[1] boost_rouge : identité au bit, mono, entrée intacte, force plafonnée")
sc = scene_sho()
copie = sc.copy()
verifie(np.array_equal(coul.boost_rouge(sc, force=1.0), sc),
        "force 1,00 → identité AU BIT près (le réglage peut rester en place "
        "sans rien changer)")
verifie(np.array_equal(coul.boost_rouge(sc, force=0.0), sc),
        "force 0,00 (saisie aberrante) → identité au bit")
mono = sc[..., 1].copy()
verifie(np.array_equal(coul.boost_rouge(mono, force=4.0), mono),
        "composite MONOCHROME → copie inchangée (pas de rouge à dorer)")
verifie(np.array_equal(coul.boost_rouge(sc, force=4.0),
                       coul.boost_rouge(sc, force=99.0)),
        "force au-delà du maximum → PLAFONNÉE à 4,00 (une config erronée ne "
        "doit jamais amplifier sans borne)")
verifie(np.allclose(coul.boost_rouge(sc, force="illisible"),
                    coul.boost_rouge(sc, force=coul.BOOST_ROUGE_DEFAUT)),
        f"force illisible → défaut du module ({coul.BOOST_ROUGE_DEFAUT:.2f})")
verifie(np.array_equal(sc, copie), "l'entrée n'est JAMAIS modifiée")
y = coul.boost_rouge(sc, force=3.0)
verifie(y.dtype == np.float32 and y.shape == sc.shape,
        "→ float32 de mêmes dimensions")

# ================================================== [2] le masque (le fond)
print("[2] le MASQUE : le fond est INTACT — c'est tout l'intérêt du levier")
fond, obj = masque_fond(sc), masque_objet(sc)
for force in (1.5, 3.0, 4.0):
    y = coul.boost_rouge(sc, force=force)
    ec_fond = float(np.abs(y - sc).max(axis=2)[fond].max())
    gain_obj = float((y[..., 0] - sc[..., 0])[obj].mean())
    verifie(ec_fond == 0.0 and gain_obj > 0.01,
            f"force {force:.2f} : fond inchangé AU BIT (écart max {ec_fond:.1e}) "
            f"et rouge de l'objet +{gain_obj:.3f} en moyenne")
lum = 0.2126 * sc[..., 0] + 0.7152 * sc[..., 1] + 0.0722 * sc[..., 2]
bas = float(np.percentile(lum, coul.BOOST_ROUGE_CENTILE_BAS))
verifie(float(lum[fond].max()) <= bas,
        f"tous les pixels de fond sont SOUS le "
        f"{coul.BOOST_ROUGE_CENTILE_BAS:.0f}e centile de luminance (poids "
        f"exactement nul)")

# ===================================================== [3] l'objectif (doré)
print("[3] l'OBJECTIF : du doré sur l'objet, sans délavage ni perte de lumière")
g0, b0, dore0 = rv_objet(sc, obj)
s0, l0 = saturation(sc, obj), luminosite(sc, obj)
print(f"    référence (aucun boost) : G:R {g0:.2f} · B:R {b0:.2f} · "
      f"R>V {dore0:4.1f} % · sat {s0:.2f} · L* {l0:.2f}")
for force in (2.0, 3.0, 4.0):
    y = coul.boost_rouge(sc, force=force)
    g1, b1, dore = rv_objet(y, obj)
    verifie(g1 < g0 - 0.10 and dore >= dore0,
            f"force {force:.2f} : G:R {g0:.2f} → {g1:.2f} (R>V {dore0:.1f} → "
            f"{dore:.1f} %) : l'objet part vers le doré")
    verifie(saturation(y, obj) > 0.75 * s0,
            f"        la saturation de l'objet est CONSERVÉE "
            f"({saturation(y, obj):.2f} contre {s0:.2f}) : le Linear Fit la "
            f"faisait tomber à 0,31 pour 0,72")
y4 = coul.boost_rouge(sc, force=4.0)
g4, b4, dore4 = rv_objet(y4, obj)
verifie(dore4 > dore0 + 2.0,
        f"à 4,00 le doré est FRANC : R > V sur {dore4:.1f} % des pixels de "
        f"l'objet, G:R {g4:.2f} (sur l'empilement RÉEL d'Alain, le diagnostic a "
        f"mesuré 6,2 % → 55,6 % à cette force)")
g3 = coul.boost_rouge(sc, force=3.0)
verifie(luminosite(g3, obj) >= l0 - 1e-9,
        f"        l'objet ne perd pas de lumière (L* {l0:.2f} → "
        f"{luminosite(g3, obj):.2f} : le rouge est AJOUTÉ)")
gp = coul.boost_rouge(sc, force=3.0, preserve_luminance=True)
ecp = abs(luminosite(gp, obj) - l0) / max(l0, 1e-9)
verifie(ecp < 0.02,
        f"        variante « L* gardée » : la lumière reste celle d'avant "
        f"(L* {luminosite(gp, obj):.2f}, écart {ecp * 100:.2f} %)")
# ============================================== [4] la chaîne (ordre et garde)
print("[4] la CHAÎNE après étirement : ordre respecté, identité quand tout est "
      "décoché")
verifie(np.array_equal(dsp.couleur_apres_etirement(sc), sc),
        "toutes les cases décochées → identité AU BIT (aucune régression)")
ref = coul.boost_rouge(coul.scnr(sc, amount=0.35, preserve_luminance=True),
                       force=3.0)
chaine = dsp.couleur_apres_etirement(
    sc, (True, False, False), force_scnr=0.35, preserve_luminance=True,
    boost_rouge=True, force_boost=3.0)
verifie(np.array_equal(chaine, ref),
        "le boost est appliqué EN DERNIER (après le SCNR) — l'ordre de la "
        "chaîne est celui du docstring, au bit près")
sans_boost = dsp.couleur_apres_etirement(
    sc, (True, False, False), force_scnr=0.35, preserve_luminance=True,
    boost_rouge=False)
exces_avant = np.maximum(sc[..., 1] - 0.5 * (sc[..., 0] + sc[..., 2]), 0.0)
exces_apres = np.maximum(chaine[..., 1] - 0.5 * (chaine[..., 0] + chaine[..., 2]),
                         0.0)
verifie(float(exces_apres[obj].mean()) < float(exces_avant[obj].mean()),
        "le SCNR garde son effet quand le boost est actif (le vert de l'objet "
        "a bien été réduit : les deux réglages s'AJOUTENT)")
gain = float((chaine[..., 0] - sans_boost[..., 0])[obj].mean())
verifie(gain > 0.01 and float(np.abs(chaine - sans_boost).max(axis=2)[fond].max())
        == 0.0,
        f"avec le boost : rouge de l'objet +{gain:.3f} et FOND inchangé au bit")
verifie(np.array_equal(dsp.couleur_apres_etirement(sc, boost_rouge=True,
                                                   force_boost=1.0), sc),
        "case cochée mais force 1,00 → identité au bit (les deux réglages sont "
        "sans danger)")

# =========================================== [5] centiles : sous-échantillon
print("[5] les centiles du masque : sous-échantillonner ne déplace pas les bornes")
grand = scene_sho(n=256, graine=11)
lm = 0.2126 * grand[..., 0] + 0.7152 * grand[..., 1] + 0.0722 * grand[..., 2]
bas_p = float(np.percentile(lm, coul.BOOST_ROUGE_CENTILE_BAS))
haut_p = float(np.percentile(lm, coul.BOOST_ROUGE_CENTILE_HAUT))
bas_e = float(np.percentile(lm[::2, ::2], coul.BOOST_ROUGE_CENTILE_BAS))
haut_e = float(np.percentile(lm[::2, ::2], coul.BOOST_ROUGE_CENTILE_HAUT))
verifie(abs(bas_p - bas_e) < 1e-3 and abs(haut_p - haut_e) < 1e-3,
        f"bornes : bas {bas_p:.5f} / {bas_e:.5f} · haut {haut_p:.5f} / "
        f"{haut_e:.5f} (écart < 10⁻³)")
poids = np.clip((lm - bas_p) / max(1e-6, haut_p - bas_p), 0.0, 1.0)
ref = np.array(grand, np.float32)
ref[..., 0] = np.clip(grand[..., 0] * (1.0 + 2.0 * poids), 0.0, 1.0)
ec = float(np.abs(coul.boost_rouge(grand, force=3.0) - ref).max())
verifie(ec < 0.01,
        f"image obtenue : écart max {ec:.2e} avec la formule à centiles pleins "
        f"(le sous-échantillonnage est invisible)")


# ================================================================ [6] interface
print("[6] INTERFACE : case + curseur dans « Couleur de l'objet (APRÈS étirement) »")
import avastack.ui.app as ui                                       # noqa: E402

ui.CONFIG = {}
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()

verifie(bool(app.var_vl_boost.get()) is False
        and abs(float(app.var_vl_boost_force.get())
                - coul.BOOST_ROUGE_DEFAUT) < 1e-9
        and app.disp.vl_boost_rouge is False,
        f"défauts : case DÉCOCHÉE, force {coul.BOOST_ROUGE_DEFAUT:.2f}, solveur "
        f"informé — un rendu par défaut reste inchangé au bit")
verifie(any(isinstance(w, ttk.Checkbutton) and "Boost du rouge" in w.cget("text")
            for w in app.frm_couleur.winfo_children()),
        "la case vit dans le cadre « Couleur de l'objet (APRÈS étirement) »")
cle1 = app.disp._vl_params()
app.var_vl_boost.set(True)
app._on_vl_boost()
verifie(app.disp.vl_boost_rouge is True and app.disp._vl_params() != cle1,
        "cocher la case change la clé des réglages du solveur (re-résolution)")
cle2 = app.disp._vl_params()
app.var_vl_boost_force.set(2.5)
app._on_vl_boost_force()
verifie(abs(app.disp.vl_boost_force - 2.5) < 1e-9
        and app.disp._vl_params() != cle2,
        "bouger le curseur change la clé ET la valeur lue par le solveur")
app.var_vl_boost_force.set(99.0)
app._on_vl_boost_force()
verifie(abs(app.disp.vl_boost_force - coul.BOOST_ROUGE_MAX) < 1e-9,
        f"valeur hors bornes → ramenée à {coul.BOOST_ROUGE_MAX:.2f} (jamais "
        f"appliquée en silence)")
app.var_vl_boost_force.set(float(coul.BOOST_ROUGE_DEFAUT))
app._on_vl_boost_force()
reglages = app._reglages_rendu()
verifie(reglages.get("vl_boost_rouge") is True
        and abs(float(reglages.get("vl_boost_force", 0.0))
                - coul.BOOST_ROUGE_DEFAUT) < 1e-9,
        "les réglages du rendu pleine résolution (fichier « tel que vu ») "
        "transportent la case ET la force")
app._sauver_config_app()
verifie(bool(sauvegardes) and sauvegardes[-1].get("vl_boost_rouge") is True
        and abs(float(sauvegardes[-1].get("vl_boost_force", 0.0))
                - coul.BOOST_ROUGE_DEFAUT) < 1e-9,
        "la configuration écrite porte les deux clés (booléen ET force)")
ui.CONFIG = {"vl_boost_rouge": True, "vl_boost_force": 2.0}
app.var_vl_boost.set(False)
app.var_vl_boost_force.set(float(coul.BOOST_ROUGE_DEFAUT))
app._restaurer_config()
verifie(bool(app.var_vl_boost.get()) is True
        and abs(app.disp.vl_boost_force - 2.0) < 1e-9,
        "config relue : case restaurée dans l'UI ET force dans le solveur")
ui.CONFIG = {"vl_boost_force": 42.0}           # hors bornes
app.var_vl_boost_force.set(float(coul.BOOST_ROUGE_DEFAUT))
app._restaurer_config()
verifie(abs(float(app.var_vl_boost_force.get())
            - coul.BOOST_ROUGE_DEFAUT) < 1e-9,
        "force hors bornes dans la config → défaut du module conservé")
app.var_view.set("traitée")
app._sync_vl_boost_vue()
verifie(app.disp.vl_boost_rouge is True,
        "vue « traitée » : boost ACTIF (v2.48.1 — la chaîne couleur suit "
        "l'étirement, elle vaut pour les deux vues)")
app.var_view.set("pile")
app._sync_vl_boost_vue()
verifie(app.disp.vl_boost_rouge is True, "vue « pile » : toujours actif")
root.destroy()

# ==================================================================== [7] coût
print("[7] coût : négligeable devant les autres étages de la chaîne live")
x = np.ascontiguousarray(np.tile(scene_sho(n=904), (1, 2, 1))[:, :1600])
t0 = time.perf_counter()
coul.boost_rouge(x, force=3.0)
t1 = time.perf_counter()
verifie(t1 - t0 < 0.25,
        f"aperçu 1600×904 : {t1 - t0:.3f} s (étirement VeraLux ~0,4 s, GraXpert "
        f"~4,5 s mesurés : cet étage est invisible)")

# ============================================================ récapitulatif
print()
print("BANC JALON 86 (boost du rouge SII masqué à l'objet) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)
