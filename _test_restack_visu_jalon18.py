# -*- coding: utf-8 -*-
"""Test du jalon 18 — rendre le re-stack VISIBLE (UX).

Enchaînement décidé par Alain après son retour réel sur le jalon 16
(« on est ok, pas simple de voir le restack ») : chantier COMPLET — ligne
d'état dédiée colorée + horodatage + GAIN + historique de session +
compteur dans les stats. Ce test vérifie :

  [1] état initial : ligne dédiée grise « Re-stack : — », aucun état ;
  [2] _noter_restack (succès) : couleur verte, horodatage, gain (frames +
      Δ score), compteur de session, historique en tête ;
  [3] _noter_restack (échec) : couleur ambre, compteur INCHANGÉ ;
  [4] plafond de l'historique (RESTACK_HIST_MAX) ;
  [5] _do_restack réel : état dédié vert + gain cohérent, message
      d'alignement INCHANGÉ (compat jalon 16) ;
  [6] échec de re-stack (archive illisible) → ambre, pas de compteur ;
      archive vide → rien fait, état conservé ;
  [7] _update_status : compteur dans les stats, ligne dédiée mise à jour,
      compat dicts SANS clés « restack » (anciens appels) ;
  [8] intégration worker : un re-stack AUTO remplit l'état dédié.

Nécessite un affichage. Exécution : python _test_restack_visu_jalon18.py
"""
import re
import sys
import threading
import time
import tkinter as tk

import numpy as np
import cv2

import avastack.ui.app as ui
from avastack.processing.stacking import LiveStacker
from avastack.images import load_image

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def decale(img, dx, dy):
    """warpAffine d'une translation (sens OpenCV)."""
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_LINEAR)


# Même champ à positions FIXES que le test jalon 16 : A = TRÈS défocalisée
# (σ 8 → score effondré), B/C/D = nettes décalées (dithering).
rng0 = np.random.default_rng(3)
POS = [(float(rng0.integers(30, 370)), float(rng0.integers(30, 270)),
        float(rng0.uniform(0.15, 0.7))) for _ in range(20)]


def champ_fixe(shape, sigma_px=1.5, bruit=0.004, fond=0.02, graine=1):
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for x, y, a in POS:
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += np.random.default_rng(graine).normal(0, bruit, img.shape).astype(
        np.float32)
    return img


SHAPE = (300, 400)
A = champ_fixe(SHAPE, sigma_px=8.0, graine=11)
B = decale(champ_fixe(SHAPE, graine=12), 6.0, 3.0)
C = decale(champ_fixe(SHAPE, graine=13), 12.0, 6.0)
D = decale(champ_fixe(SHAPE, graine=14), 18.0, 9.0)

root = tk.Tk()
root.withdraw()
app = ui.App(root)

VERT, AMBRE, GRIS = "#1d7f1d", "#c98a00", "#888888"

print("[1] état initial : ligne dédiée grise, aucun re-stack")
verifie(app.restack_info == "" and app.restack_total == 0
        and app.restack_hist == [] and app.restack_couleur == GRIS,
        "état initial vierge (info, compteur, historique, couleur)")
# PIÈGE (Tk 9 / Python 3.14) : ttk.Label.cget("foreground") renvoie un
# Tcl_Obj (non comparable à une chaîne) → str() obligatoire.
verifie(app.lbl_restack.cget("text") == "Re-stack : —"
        and str(app.lbl_restack.cget("foreground")) == GRIS,
        "ligne dédiée affichée d'office : « Re-stack : — » en gris")

print("[2] _noter_restack succès : couleur, horodatage, gain, compteur")
app._noter_restack(10, 7, 12, 150, 100, "auto")
i1 = app.restack_info
verifie(app.restack_couleur == VERT, "succès → couleur VERTE")
verifie(bool(re.match(r"^\d{2}:\d{2}:\d{2} ", i1)),
        f"horodatage HH:MM:SS en tête (« {i1[:8]} »)")
verifie("+3" in i1 and "vs avant" in i1,
        "gain de frames affiché (« +3 vs avant »)")
verifie("×1.50" in i1 and "100 → 150" in i1,
        "gain de score affiché (« ×1.50 (100 → 150 étoiles) »)")
verifie("#1" in i1 and app.restack_total == 1,
        "numéro de re-stack de session (« #1 »)")
verifie(len(app.restack_hist) == 1 and app.restack_hist[0] == i1,
        "historique : 1 entrée = l'état affiché")

print("[3] _noter_restack échec : ambre, compteur inchangé")
app._noter_restack(0, 0, 0, 0, None, "re-stack impossible (test)", echec=True)
verifie(app.restack_couleur == AMBRE, "échec → couleur AMBRE")
verifie(app.restack_total == 1, "compteur de session INCHANGÉ sur échec")
verifie("impossible" in app.restack_info, "motif d'échec affiché")
verifie(app.restack_hist[0] == app.restack_info and len(app.restack_hist) == 2,
        "l'échec figure aussi dans l'historique")

print("[4] plafond de l'historique (RESTACK_HIST_MAX)")
for _ in range(ui.RESTACK_HIST_MAX + 3):
    app._noter_restack(1, 0, 1, 5, 4, "test")
verifie(len(app.restack_hist) == ui.RESTACK_HIST_MAX,
        f"historique plafonné à RESTACK_HIST_MAX = "
        f"{ui.RESTACK_HIST_MAX} entrées")
verifie("test" in app.restack_hist[0],
        "l'entrée la plus récente est en tête")

print("[5] _do_restack réel : état dédié vert + gain, message inchangé")
app._vider_archive()
app.archive.intervalle_s = 0.0
for f in (A, B, C, D):
    app.archive.ajouter(f)
app._scores = [app._score_frame(load_image(c)) for c in app.archive.chemins]
ancien = LiveStacker(SHAPE, k=None)
ancien.add(B)
app.stacker = ancien
app._definir_reference(B)      # référence = une brute nette (score riche)
app.restack_total = 0          # remise à zéro après les appels directs
app.restack_hist = []
s_ref = app._ref_score
s_best = max(app._scores)
info = app._do_restack("test")
verifie(info.startswith("re-stack") and "test" in info,
        f"message d'alignement INCHANGÉ (« {info} »)")
verifie(app.restack_couleur == VERT and app.restack_total == 1,
        "état dédié : re-stack réussi compté (vert, total 1)")
verifie(f"/{app.archive.n}" in app.restack_info
        and "vs avant" in app.restack_info,
        f"état dédié : N/M frames + gain (« {app.restack_info} »)")
rapport_attendu = f"×{s_best / s_ref:.2f}"
verifie(rapport_attendu in app.restack_info,
        f"gain de score cohérent ({rapport_attendu} : la meilleure brute "
        f"ÉTAIT la référence)")
verifie(app.restack_hist[0] == app.restack_info,
        "historique alimenté par _do_restack")
verifie(app.stacker.n >= 3 and app.stacker is not ancien,
        f"empilement recalculé ({app.stacker.n} frames, NOUVEAU stacker)")

print("[6] échec de re-stack (archive illisible) → ambre, pas de compteur")
app._vider_archive()
total_avant = app.restack_total
app.archive.chemins = ["inexistant_jalon18.fits"]   # illisible
app._scores = [10]
info = app._do_restack("test")
verifie("re-stack impossible" in info, f"message d'échec (« {info} »)")
verifie(app.restack_couleur == AMBRE and app.restack_total == total_avant,
        "échec d'archive : ligne AMBRE, compteur inchangé")
app._vider_archive()
info = app._do_restack("test")
verifie(info == "" and app.restack_couleur == AMBRE,
        "archive vide : rien fait, état précédent conservé")

print("[7] _update_status : compteur dans les stats, ligne dédiée, compat")
st = dict(frames=5, rejets=0, bad=0, floues=0, fps=2.0, cam="test", file="",
          pending=0, failed=0, align="—", seeing=None, seeing_msg="",
          archive=4, archive_err="", restack=app.restack_info,
          restack_n=app.restack_total)
app._update_status(st)
verifie(f"Re-stacks (session) : {app.restack_total}"
        in app.lbl_stats.cget("text"),
        "stats : compteur « Re-stacks (session) : N » affiché")
verifie(app.lbl_restack.cget("text") == app.restack_info
        and str(app.lbl_restack.cget("foreground")) == AMBRE,
        "ligne dédiée reflète l'état courant (ambre après l'échec)")
st_sans = dict(frames=1, rejets=0, bad=0, fps=1.0, cam="t", file="",
               pending=0, failed=0, seeing=None, seeing_msg="")
app._update_status(st_sans)
verifie("Re-stacks (session)" not in app.lbl_stats.cget("text"),
        "dict sans clés « restack » (anciens appels) : pas de compteur")
verifie(app.lbl_restack.cget("text") == app.restack_info,
        "ligne dédiée inchangée par un dict ancien format")

print("[8] intégration worker : déclencheur AUTO (constantes patchées)")
ui.RESTACK_MIN_FRAMES = 2
ui.RESTACK_CADENCE = 1
app2 = ui.App(root)
app2.archive.intervalle_s = 0.0
app2.stacker = LiveStacker(SHAPE, k=None)
app2._definir_reference(A)                # ancre médiocre (défocalisée)
app2.bad_frames = 0


class CamFournit:
    name = "test"

    def __init__(self, frames):
        self.frames = frames
        self.i = 0

    def read(self):
        self.i += 1
        if self.i > len(self.frames):
            return None
        return self.frames[self.i - 1]


try:
    app2.camera = CamFournit([A, B, C, D])
    app2.running = True
    th = threading.Thread(target=app2._worker, daemon=True)
    th.start()
    t0 = time.time()
    while time.time() - t0 < 30.0 and (app2._ancre_idx is None
                                       or app2.archive.n < 4):
        time.sleep(0.05)
    app2.running = False
    th.join(timeout=5.0)
    verifie(app2._ancre_idx is not None,
            "déclencheur AUTO : un re-stack a eu lieu dans le worker")
    verifie(app2.restack_total == 1 and app2.restack_couleur == VERT,
            "état dédié rempli par le worker (vert, total 1)")
    verifie(bool(app2.restack_hist)
            and app2.restack_hist[0] == app2.restack_info,
            "historique rempli par le worker")
finally:
    app2.archive.vider()

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)