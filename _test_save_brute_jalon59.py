# -*- coding: utf-8 -*-
"""Banc du chantier v2.35.0 — SAUVEGARDE LINÉAIRE BRUTE + CORRECTIONS DE COULEUR
DANS LA CHAÎNE DE SORTIE (décisions d'Alain, 24/09/2026 ; étapes ①→⑦ du plan).

Vérifie, de bout en bout :
  [1] composer() ne porte plus AUCUN gain (empilement brut) ; appliquer_gains()
      le fait, APRÈS la composition (chaîne de sortie) ;
  [2] CompositeStacker : mean(corrections=False) = EMPILEMENT BRUT (identique à
      composer() seul), mean(corrections=True) = brut + corrections ; les
      COUCHES (moyennes()) ne sont jamais modifiées ;
  [3] corrections_couleur() : ordre exact gains → équilibrage → recalage,
      diag du fit, no-op en mono ;
  [4] PREUVE DE « BRUT » (le cœur du chantier) : le FICHIER LINÉAIRE est
      IDENTIQUE au pixel près avec et sans SPCC / gains Gaia / équilibrage /
      Linear Fit cochés, alors que l'AFFICHAGE (mean()) change ; en-têtes
      « mesure » (AVASPCC/AVAGAIA) vs « appliqué » (AVAAPPLI, AVAWB, AVAFIT) ;
  [5] solveur live (display._vl_worker) : l'équilibrage est transporté dans le
      job (6e élément) et appliqué APRÈS la recomposition — la vue « traitée »
      suit la vue « empilement » ;
  [6] RÉEL (worker) : la 3e sortie « 💾 Enregistrer l'empilement traité
      (linéaire)… » écrit un fichier AVEC les corrections, SANS étirement, avec
      un en-tête AUTO-DESCRIPTIF (AVAVUE/AVAAPPLI).

Exécution : python _test_save_brute_jalon59.py
"""
import os
import sys
import tempfile
import threading
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.ui.app as ui
ui.CONFIG = {}                            # bac à sable : JAMAIS le vrai
ui.sauver_config = lambda *a, **k: None   # config.json (règle du projet)

from astropy.io import fits                                  # noqa: E402
from avastack.images import load_image                       # noqa: E402
from avastack.processing.composition import (                # noqa: E402
    CompositeStacker, appliquer_equilibrage, appliquer_gains,
    composer, corrections_couleur)
from avastack.processing.stacking import aligner_canaux      # noqa: E402

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

H, W = 96, 128
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def champ(fond=0.05, graine=0):
    """Carte float32 (H, W) : fond BRUITÉ + quelques taches gaussiennes —
    de quoi donner du signal aux trois canaux (sinon tout est plat et les
    corrections n'ont rien à mesurer)."""
    rng = np.random.default_rng(1000 + graine)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.full((H, W), fond, np.float32)
    for (sx, sy, f) in ((20, 30, 0.6), (70, 40, 0.9), (50, 75, 0.4)):
        img += f * np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (2 * 2.0 ** 2))
    return (img + rng.normal(0, 0.004, img.shape)).astype(np.float32)


def canaux_fixes():
    """Couches Ha/O3 déterministes, avec des FONDS INÉGAUX (pour que
    l'équilibrage des canaux ait réellement quelque chose à corriger)."""
    return {"Ha": champ(0.02, 1), "O3": champ(0.10, 2)}


# ======================================================= [1] composer brut
print("[1] composer() ne porte plus aucun gain ; appliquer_gains() le fait")
canaux = canaux_fixes()
brut = composer(canaux, "HOO")
gains = {"R": 1.5, "B": 2.0}
corr = appliquer_gains(brut, gains)
verifie(np.allclose(corr[..., 0], brut[..., 0] * 1.5)
        and np.allclose(corr[..., 1], brut[..., 1])
        and np.allclose(corr[..., 2], brut[..., 2] * 2.0),
        "appliquer_gains : R ×1.5 et B ×2.0, G inchangé (canal par canal)")
verifie(np.allclose(composer(canaux, "HOO"), brut),
        "composer() est DÉTERMINISTE et SANS gain (empilement brut)")
verifie(np.allclose(appliquer_gains(brut, {}), brut)
        and appliquer_gains(brut, None) is brut,
        "appliquer_gains : gains vides/None → aucune modification")
mono = np.full((4, 5), 0.3, np.float32)
verifie(appliquer_gains(mono, gains) is mono,
        "appliquer_gains : no-op sur une image non couleur (H, W)")
verifie(np.asarray(canaux["Ha"]).shape == (H, W)
        and abs(float(np.median(canaux["O3"])) - 0.10) < 0.02,
        "les COUCHES d'entrée ne sont jamais modifiées par composer()")

# =================================================== [2] façade CompositeStacker
print("[2] CompositeStacker : corrections=True (affichage) / False (brut)")
fa = CompositeStacker("HOO", k=None)
fa.role_courant = "Ha"
fa.add(canaux["Ha"])
fa.role_courant = "O3"
fa.add(canaux["O3"])
fa.gains = {"R": 1.4}
fa.gains_roles = {"O3": 1.3}            # gain photométrique sur O3 (→ G et B)
fa.wb_auto = True
fa.linear_fit = True
fa.linear_fit_mode = "gain_offset"
couches_avant = {r: m.copy() for r, m in fa.moyennes().items()}
m_brut = fa.mean(corrections=False)
m_aff = fa.mean(corrections=True)
verifie(m_brut is not None and m_aff is not None
        and m_brut.shape == m_aff.shape == (H, W, 3),
        "les deux chemins rendent un composite (H, W, 3)")
verifie(np.allclose(m_brut, composer(fa.moyennes(), "HOO")),
        "mean(corrections=False) = EXACTEMENT composer() seul (BRUT)")
verifie(not np.allclose(m_brut, m_aff),
        "mean(corrections=True) DIFFÈRE du brut : les corrections agissent "
        "sur l'affichage")
attendu, _diag = corrections_couleur(
    m_brut, gains=fa.gains_effectifs(), wb_auto=True, wb_force=1.0,
    cadre=fa.cadre, linear_fit=True, linear_fit_mode="gain_offset")
verifie(np.allclose(m_aff, attendu, rtol=1e-5, atol=1e-6),
        "mean(corrections=True) = corrections_couleur(brut) — même chaîne "
        "que le solveur live")
verifie(all(np.array_equal(fa.moyennes()[r], couches_avant[r])
            for r in couches_avant),
        "les COUCHES restent BRUTES : mean() ne les modifie jamais "
        "(contrat jalon 54)")
verifie(fa._wb_cache_comp is not None and fa.fit_diag is not None,
        "caches des corrections alimentés (équilibrage + diagnostic du fit)")

# ============================================ [3] corrections_couleur (ordre)
print("[3] corrections_couleur : ORDRE gains → équilibrage → recalage")
etape1 = appliquer_gains(brut, {"R": 1.5, "G": 1.0, "B": 0.7})
etape2 = appliquer_equilibrage(etape1, fa.cadre, 1.0)
etape3, diag3 = aligner_canaux(etape2, mode="offset")
out, diag = corrections_couleur(brut, gains={"R": 1.5, "G": 1.0, "B": 0.7},
                                wb_auto=True, wb_force=1.0, cadre=fa.cadre,
                                linear_fit=True, linear_fit_mode="offset")
verifie(np.allclose(out, etape3, rtol=1e-6) and diag is not None
        and diag3 is not None and diag["mode"] == "offset",
        "l'ordre appliqué EST gains → équilibrage → recalage (calcul manuel "
        "identique), diag du recalage remonté")
out_sans, diag_sans = corrections_couleur(brut)
verifie(np.allclose(out_sans, brut) and diag_sans is None,
        "aucun réglage actif → image inchangée, diag None")
out_mono, _ = corrections_couleur(np.full((H, W), 0.4, np.float32),
                                  gains={"R": 2.0}, wb_auto=True,
                                  linear_fit=True)
verifie(out_mono.shape == (H, W) and np.allclose(out_mono, 0.4),
        "image MONO (2D) : les corrections de couleur sont un no-op")


# ================================================ [4] PREUVE DE « BRUT » réel
print("[4] FICHIER LINÉAIRE identique avec/sans les cases de couleur cochées")


class _Val:
    """Bouchon de variable Tk (get interdit hors thread principal)."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


class _SpccFactice:
    """Mesure SPCC factice (la mesure elle-même n'est pas l'objet du banc :
    on vérifie le TRANSPORT des gains et la SÉMANTIQUE des en-têtes).
    gains() rend des gains de RÔLE, comme la vraie SessionSpcc."""

    valide = True
    coefficients = np.array([0.90, 1.00, 1.10])

    def gains(self):
        return {"Ha": 1.2, "O3": 0.9}


class CameraMuette:
    """Caméra factice : ne renvoie plus aucune frame (dossier terminé)."""

    name = "muette"

    def read(self):
        return None


root = tk.Tk()
root.withdraw()
app = ui.App(root)
tmp = tempfile.mkdtemp(prefix="avastack_brut59_")
app.camera = CameraMuette()
app.running = True
app._mode_compo = True
app._compo_nom = "HOO"
app._compo_gains = {}
app._compo_mode_l = "synthetise"
app._fit_actif = False
app._fit_mode = "offset"
app._photo_gains_actif = False
app._spcc_actif = False
app.spcc = _SpccFactice()
app.stacker = fa                 # façade déjà empilée (2 frames)
app.save_request = None
app.saved_path = None
th = threading.Thread(target=app._worker, daemon=True)
th.start()
time.sleep(0.6)                  # le worker pose les réglages sur la façade

# --- état 1 : AUCUNE case de couleur (référence)
p_brut1 = os.path.join(tmp, "brut_sans_cases.fits")
app.saved_path = None
app.save_request = p_brut1
t0 = time.time()
while app.saved_path is None and time.time() - t0 < 20:
    time.sleep(0.05)
verifie(app.saved_path == p_brut1 and os.path.exists(p_brut1),
        "sauvegarde LINÉAIRE consommée (toutes les cases décochées)")
aff_sans = fa.mean()             # ce que l'AFFICHAGE montre, état 1
v_brut1 = load_image(p_brut1)
h_brut1 = fits.open(p_brut1)[0].header

# --- état 2 : TOUTES les corrections activées (SPCC + manuels + équilibrage
#     + recalage) — l'affichage doit changer, le FICHIER BRUT non.
app._compo_gains = {"R": 1.4, "G": 1.0, "B": 0.8}
app._fit_actif = True
app._spcc_actif = True
fa.wb_auto = True
fa.wb_force = 1.0
time.sleep(0.6)                  # le worker repose les réglages
p_brut2 = os.path.join(tmp, "brut_avec_cases.fits")
app.saved_path = None
app.save_request = p_brut2
t0 = time.time()
while app.saved_path is None and time.time() - t0 < 20:
    time.sleep(0.05)
verifie(app.saved_path == p_brut2 and os.path.exists(p_brut2),
        "sauvegarde LINÉAIRE consommée (SPCC + manuels + équilibrage + fit)")
aff_avec = fa.mean()             # ce que l'AFFICHAGE montre, état 2
v_brut2 = load_image(p_brut2)
h_brut2 = fits.open(p_brut2)[0].header

verifie(np.array_equal(v_brut1, v_brut2),
        "LE FICHIER LINÉAIRE EST IDENTIQUE AU PIXEL PRÈS avec et sans les "
        "cases de couleur — preuve de « BRUT » (une seule passe de moyennes "
        "temporelle + normalisation par rôle)")
verifie(h_brut1.get("AVASPCC") in (None, "") and h_brut2.get("AVASPCC"),
        f"AVASPCC = MESURE : absent sans mesure, présent avec "
        f"(« {h_brut2.get('AVASPCC')} »)")
verifie(str(h_brut1.get("AVAAPPLI")) == "aucune (empilement BRUT)"
        and str(h_brut2.get("AVAAPPLI")) == "aucune (empilement BRUT)",
        f"AVAAPPLI = « aucune (empilement BRUT) » dans les DEUX fichiers — "
        f"le fichier ne ment pas sur ce qu'il contient "
        f"(« {h_brut2.get('AVAAPPLI')} »)")
verifie(h_brut1.get("AVAWB") is None and h_brut1.get("AVAFIT") is None
        and h_brut2.get("AVAWB") is None and h_brut2.get("AVAFIT") is None,
        "AVAWB/AVAFIT absents d'un fichier BRUT (ils ne décrivent qu'une "
        "chose appliquée)")
verifie(str(h_brut1.get("AVAVUE", "")).startswith("empilement BRUT")
        and str(h_brut2.get("AVAVUE", "")).startswith("empilement BRUT"),
        f"AVAVUE décrit la vue enregistrée (« {h_brut2.get('AVAVUE')} »)")
verifie(not np.allclose(aff_sans, aff_avec),
        "l'AFFICHAGE, lui, CHANGE bien entre les deux états (les corrections "
        "vivent dans la chaîne de sortie)")


# ================================================= [5] solveur live (job à 6)
print("[5] solveur live : équilibrage transporté et appliqué APRÈS la "
      "recomposition")
import avastack.processing.display as dp                            # noqa: E402

canaux_s = {"Ha": champ(0.02, 1), "O3": champ(0.10, 2)}
CARRE = (4, 6, H - 4, W - 6)          # cadre de mesure du fond (transporté)
G = {"R": 1.4, "O3": 0.9}


def corrections_attendues(gains, wb, fit=None):
    """Ce que la vue « traitée » DOIT valoir (étirement court-circuité) :
    recomposition des couches traitées puis chaîne des corrections."""
    comp = composer(canaux_s, "HOO")
    out, _diag = corrections_couleur(
        comp, gains=gains, wb_auto=bool(wb[0]), wb_force=float(wb[1]),
        cadre=wb[2], linear_fit=bool(fit[0]) if fit else False,
        linear_fit_mode=fit[1] if fit else "offset")
    return np.asarray(out, np.float32)


d = dp.DisplayProcessor()             # le thread solveur démarre à l'init
d.stretch = "veralux"
d.vl_log_d = 2.0
# Outils remplacés par des IDENTITÉS : on mesure la chaîne de RECOMPOSITION +
# CORRECTIONS, pas GraXpert ni l'étirement (déjà couverts par leurs bancs).
dp._gx_live.appliquer = lambda img, cmd: (np.asarray(img, np.float32).copy(), "")
dp._veralux.etirer = lambda img, **kw: (img, 2.0, {})
params = dict(mode=d.vl_mode_res, target_bg=0.25, log_d=2.0, profil=d.vl_profil)
gx = (True, 'copy /Y "{input}" "{output}"')      # gx actif → chemin PAR COUCHE


def _soumet(key, compo):
    d._vl_result = None
    d._vl_job = (composer(canaux_s, "HOO").copy(), params, key, gx,
                 (False, "nlm", 0.5), (False, 3), (), compo)
    d._vl_wake.set()
    for _ in range(400):
        if d._vl_result is not None and d._vl_result[0] == key:
            return d._vl_result[1]
        time.sleep(0.02)
    return None


base = (canaux_s, "HOO", G, "synthetise")
r4 = _soumet("k59a", base)                                  # job jalon 24
r6_off = _soumet("k59b", base + (None, (False, 1.0, CARRE)))
r6_on = _soumet("k59c", base + (None, (True, 1.0, CARRE)))
r6_fit = _soumet("k59d", base + ((True, "offset"), (True, 1.0, CARRE)))
verifie(r4 is not None and r6_off is not None and r6_on is not None
        and r6_fit is not None,
        "solveur : jobs à 4, 5 et 6 éléments déballés (tolérance), vues "
        "« traitées » produites")
verifie(r6_off is not None and np.allclose(r6_off, r4, rtol=1e-5, atol=1e-6),
        "équilibrage INACTIF transporté : résultat identique au job jalon 24")
verifie(r6_on is not None and r6_off is not None
        and not np.allclose(r6_on, r6_off),
        "équilibrage ACTIF : la vue « traitée » change (il est bien appliqué "
        "par le solveur, pas seulement par la façade)")
attendu_on = corrections_attendues(G, (True, 1.0, CARRE))
verifie(r6_on is not None and np.allclose(r6_on, attendu_on,
                                          rtol=1e-5, atol=1e-6),
        "la vue « traitée » = corrections_couleur(recomposition) — MÊME "
        "chaîne que la vue « empilement » (ordre (c) respecté)")
attendu_fit = corrections_attendues(G, (True, 1.0, CARRE), (True, "offset"))
verifie(r6_fit is not None and np.allclose(r6_fit, attendu_fit,
                                           rtol=1e-5, atol=1e-6)
        and not np.allclose(r6_fit, r6_on),
        "recalage Linear Fit (5e élément) : appliqué APRÈS l'équilibrage")

# ================================ [6] 3e sortie linéaire (bouton dédié, réel)
print("[6] « empilement traité (linéaire) » : corrections SANS étirement")
app.asseen_result = None
app.asseen_busy = False
p_traite = os.path.join(tmp, "empilement_traite_lineaire.fits")
app.save_asseen_request = (p_traite, "pile", app._reglages_rendu(), True)
t0 = time.time()
while app.asseen_result is None and time.time() - t0 < 30:
    time.sleep(0.05)
verifie(app.asseen_result == p_traite and os.path.exists(p_traite),
        f"3e sortie écrite par le worker (« {app.asseen_result} »)")
v_traite = load_image(p_traite)
h_traite = fits.open(p_traite)[0].header
attendu_traite, _ = corrections_couleur(
    fa.mean(corrections=False), gains=fa.gains_effectifs(), wb_auto=fa.wb_auto,
    wb_force=fa.wb_force, cadre=fa.cadre, linear_fit=fa.linear_fit,
    linear_fit_mode=fa.linear_fit_mode)
ech = max(float(attendu_traite.max()), 1.0)
verifie(np.allclose(v_traite, attendu_traite / ech, rtol=1e-5, atol=1e-5),
        "contenu = empilement BRUT + corrections (aucun étirement appliqué)")
verifie(str(h_traite.get("AVAVUE", "")).startswith("empilement TRAITE")
        and "sans etirement" in str(h_traite.get("AVAVUE", "")),
        f"en-tête AVAVUE (« {h_traite.get('AVAVUE')} »)")
verifie("SPCC" in str(h_traite.get("AVAAPPLI", ""))
        and "equilibrage canaux" in str(h_traite.get("AVAAPPLI", ""))
        and "recalage colorimetrique" in str(h_traite.get("AVAAPPLI", "")),
        f"en-tête AVAAPPLI = corrections RÉELLEMENT appliquées "
        f"(« {h_traite.get('AVAAPPLI')} »)")
verifie(h_traite.get("AVAWB") is not None and h_traite.get("AVAFIT") is not None
        and str(h_traite.get("AVASPCC", "")).startswith("K="),
        "AVAWB/AVAFIT/AVASPCC présents (équilibrage et recalage appliqués, "
        "coefficients MESURÉS)")
verifie(os.path.exists(p_brut2) and not np.allclose(
            load_image(p_brut2), v_traite),
        "le fichier TRAITÉ diffère bien du fichier BRUT (mêmes frames)")
verifie(float(np.nanmax(v_traite)) <= 1.0 + 1e-6,
        f"fichier borné [0,1] (max {float(np.nanmax(v_traite)):.5f})")

app.running = False
th.join(timeout=5)
root.destroy()
import shutil                                                        # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
