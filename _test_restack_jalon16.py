# -*- coding: utf-8 -*-
"""Test du jalon 16 — re-stack sur la meilleure référence (étape 3 « à la
Siril »).

Enchaînement décidé par Alain après le 1er test réel du jalon 15 (« ça a
l'air OK sauf sur des brutes très défocalisées » — le filtre défocalisation
est NOTÉ à faire dans AVANCEMENT.md, on enchaîne le point 3). Ce test
vérifie :

  [1] _score_frame : nb d'étoiles du champ riche, 0 sur image plate ;
  [2] _definir_reference : la référence reçoit bien son score ;
  [3] _meilleure_archive : argmax des scores, cohérence avec _vider_archive ;
  [4] _veut_restack : marge 1,5×, exclusion de l'ancre courante ;
  [5] _do_restack direct : re-ancre sur la meilleure brute ET recalcule tout
      l'empilement depuis l'archive (réglages conservés) ;
  [6] intégration worker : déclencheur AUTO (patch des constantes) — la
      meilleure brute devient la référence et l'empilement est reconstruit.

Nécessite un affichage (sections [5]/[6]). Exécution :
python _test_restack_jalon16.py
"""
import os
import sys
import threading
import time
import tkinter as tk

import numpy as np
import cv2

import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)
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
    """warpAffine d'une translation (sens OpenCV : contenu déplacé de (dx,dy))."""
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_LINEAR)


# 20 étoiles à positions FIXES (même champ pour toutes les frames) : on peut
# ainsi fabriquer une version DÉFOCALISÉE (sigma 8) et des versions nettes.
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
# A : TRÈS défocalisée (σ ≈ 8 → étoiles rejetées par les critères de forme
# de stars.py → score effondré) ; B/C/D : nettes, décalées (dithering).
A = champ_fixe(SHAPE, sigma_px=8.0, graine=11)
B = decale(champ_fixe(SHAPE, graine=12), 6.0, 3.0)
C = decale(champ_fixe(SHAPE, graine=13), 12.0, 6.0)
D = decale(champ_fixe(SHAPE, graine=14), 18.0, 9.0)

root = tk.Tk()
root.withdraw()
app = ui.App(root)

print("[1] _score_frame : nb d'étoiles (canal vert), 0 sur image plate")
s_riche = app._score_frame(B)
s_defoc = app._score_frame(A)
s_plat = app._score_frame(np.full((300, 400), 0.02, np.float32))
verifie(s_riche >= 10,
        f"champ net de 20 étoiles → score {s_riche} (≥ 10)")
verifie(s_defoc <= max(2, s_riche // 4),
        f"champ TRÈS défocalisé → score effondré ({s_defoc} ≪ {s_riche})")
verifie(s_plat == 0, "image plate → score 0")

print("[2] _definir_reference : la référence reçoit son score")
app._definir_reference(B)
verifie(app._ref_score == s_riche,
        f"_ref_score = {app._ref_score} (score de la référence)")

print("[3] _meilleure_archive : argmax des scores, cohérence _vider_archive")
verifie(app._meilleure_archive() == (None, None, None),
        "archive vide → (None, None, None)")
app.archive.intervalle_s = 0.0
for f in (A, B, C, D):
    app.archive.ajouter(f)
app._scores = [app._score_frame(load_image(c)) for c in app.archive.chemins]
idx, chemin, score = app._meilleure_archive()
verifie(idx == int(np.argmax(app._scores)) and chemin == app.archive.chemins[idx]
        and score == max(app._scores),
        f"meilleure brute = #{idx} ({score} étoiles)")
app._vider_archive()
verifie(app.archive.n == 0 and app._scores == [],
        "_vider_archive : fichiers ET scores remis à zéro")

print("[4] _veut_restack : marge 1,5×, exclusion de l'ancre courante")
app.archive.chemins = ["a", "b"]          # factice : _veut_restack ne lit pas
app._scores = [5, 40]
app._ref_score = 5
app._ancre_idx = None
verifie(app._veut_restack(),
        "meilleure brute (40) ≥ 1,5 × référence (5) → re-stack voulu")
app._ancre_idx = 1
verifie(not app._veut_restack(),
        "la meilleure brute EST l'ancre courante → pas de re-stack")
app._ancre_idx = None
app._ref_score = 30
verifie(not app._veut_restack(),
        "40 < 1,5 × 30 → marge non atteinte, pas de re-stack")

print("[5] _do_restack direct : re-ancre + recalcule TOUT depuis l'archive")
app.archive.vider()
app.archive.intervalle_s = 0.0
for f in (A, B, C, D):
    app.archive.ajouter(f)
app._scores = [app._score_frame(load_image(c)) for c in app.archive.chemins]
ancien = LiveStacker(SHAPE, k=None, method="winsorized", window=6)
ancien.wb_auto = True
ancien.wb_force = 0.7
app.stacker = ancien
app._definir_reference(A)                 # ancre initiale = la DÉFOCALISÉE
app._ancre_idx = None
info = app._do_restack("test")
verifie(info.startswith("re-stack"), f"message d'état (« {info} »)")
verifie(app.stacker is not ancien and app.stacker.method == "winsorized"
        and app.stacker.window == 6 and app.stacker.wb_auto
        and abs(app.stacker.wb_force - 0.7) < 1e-9,
        "NOUVEAU stacker, réglages conservés (méthode, fenêtre, équilibrage)")
verifie(app._ancre_idx == int(np.argmax(app._scores))
        and app._ref_score == max(app._scores),
        f"référence = meilleure brute (#{app._ancre_idx}, "
        f"{app._ref_score} étoiles)")
verifie(app.stacker.n >= 3,
        f"empilement recalculé : {app.stacker.n}/4 frames au moins "
        f"(B, C, D ré-alignées ; A défocalisée alignée ou refusée)")
m = app.stacker.mean()
verifie(m is not None and np.isfinite(m).all(),
        "moyenne du re-stack finie")

print("[6] intégration worker : déclencheur AUTO (constantes patchées)")
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
    app2.empilement_on = True           # jalon 26 : le worker n'empile que si armé
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
    verifie(app2._ancre_score == max(app2._scores)
            and app2._ref_score == max(app2._scores),
            f"référence re-ancrée sur la meilleure brute "
            f"({app2._ancre_score} étoiles)")
    verifie(app2.stacker.n >= 3,
            f"empilement reconstruit ({app2.stacker.n} frames)")
    verifie(app2.archive.n == 4,
            f"archive complète ({app2.archive.n} frames)")
finally:
    app2.archive.vider()

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)