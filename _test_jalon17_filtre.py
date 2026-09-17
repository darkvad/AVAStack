# -*- coding: utf-8 -*-
"""Test du jalon 17 — filtre anti-brutes TRÈS défocalisées (avant empilement).

Constat réel d'Alain après le jalon 15 (« ça a l'air OK sauf sur des brutes
très défocalisées ») — elles passent l'alignement (les triangles s'y
retrouvent) mais dégradent l'empilement. DÉCISION d'Alain : rejet
AUTOMATIQUE d'office + case « Rejeter les frames floues (auto) » pour
désactiver. Ce test vérifie :

  [1] _score_qualite : (fwhm, nb) réalistes sur un champ net, (None, 0) sur
      une image plate ;
  [2] _filtre_floue — garde-fous : < 3 frames gardées → rien n'est rejeté ;
      case décochée → rien n'est rejeté ;
  [3] rejet FWHM : > 2× la médiane (et > 3 px) → rejeté ; 1,25× → gardé ;
  [4] rejet score étoiles : effondré + FWHM dégradée → rejeté ; effondré
      SEUL (autre champ, FWHM identique) → gardé (dossier mixé) ;
  [5] défocalisation poussée (nb 0, FWHM non mesurable) : rejetée dès que
      les gardées ont des étoiles ; nébulosité pure → jamais rejetée ;
  [6] intégration worker : la frame très défocalisée n'est NI empilée NI
      archivée, le compteur s'incrémente, la suite continue de s'empiler ;
  [7] config round-trip (`rejeter_flou`, booléen explicite) + restauration.

Nécessite un affichage (sections [6]/[7]). Exécution :
python _test_jalon17_filtre.py
"""
import sys
import threading
import time
import tkinter as tk

import numpy as np
import cv2

import avastack.ui.app as ui
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def decale(img, dx, dy):
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_LINEAR)


# 20 étoiles à positions FIXES : on peut fabriquer net / flou / très flou.
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
NET = champ_fixe(SHAPE, graine=21)              # σ 1,5 → FWHM ≈ 3,5 px
NET2 = decale(champ_fixe(SHAPE, graine=22), 5.0, 2.0)
NET3 = decale(champ_fixe(SHAPE, graine=23), 9.0, 5.0)
LEGER = decale(champ_fixe(SHAPE, sigma_px=2.4, graine=24), 4.0, 1.0)
# TRES : σ 8 → étoiles hors critères de forme (nb 0) — le cas réel d'Alain.
TRES = champ_fixe(SHAPE, sigma_px=8.0, graine=25)
# MOYEN : σ 3,4 → FWHM ≈ 8 px (≈ 2,3× la nette) mais encore mesurable.
MOYEN = champ_fixe(SHAPE, sigma_px=3.4, graine=26)
PLAT = np.full(SHAPE, 0.02, np.float32)         # aucun signal


class _MesureForcee:
    """Délegue à une app en FORÇANT le résultat de _score_qualite : permet
    de tester les critères (nb effondré, FWHM identique/dégradée) sans
    fabriquer des images irréalistes."""

    def __init__(self, base, mes):
        self.base, self.mes = base, mes

    def _score_qualite(self, img):
        return self.mes

    def __getattr__(self, nom):
        return getattr(self.base, nom)


root = tk.Tk()
root.withdraw()
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
ui.CONFIG = {}
app = ui.App(root)

print("[1] _score_qualite : (fwhm, nb) réalistes ; (None, 0) sans étoiles")
f_net, n_net = app._score_qualite(NET)
f_plat, n_plat = app._score_qualite(PLAT)
verifie(f_net is not None and 2.0 < f_net < 6.0 and n_net >= 10,
        f"champ net σ1,5 → FWHM {f_net:.2f} px, {n_net} étoiles")
verifie(f_plat is None and n_plat == 0,
        f"image plate → ({f_plat}, {n_plat}) : mesure impossible")

print("[2] _filtre_floue : garde-fous (pas assez de référence, case OFF)")
app.rejeter_flou = True
app._fwhm_hist = []
verifie(app._filtre_floue(NET) == "" and app._filtre_floue(NET2) == ""
        and app._filtre_floue(TRES) == "",
        "0, 1, 2 frames gardées → RIEN n'est rejeté (pas de référence)")
app._fwhm_hist = [(f_net, n_net), (f_net, n_net), (f_net, n_net)]
verifie(app._filtre_floue(TRES) != "",
        "référence en place → la très floue (nb 0) serait rejetée")
verifie(app._fwhm_hist == [(f_net, n_net)] * 3,
        "une frame rejetée n'alimente PAS les médianes de référence")
app.rejeter_flou = False
verifie(app._filtre_floue(TRES) == "" and app._fwhm_hist
        == [(f_net, n_net)] * 3,
        "case décochée → aucun rejet, aucune mesure ajoutée")
app.rejeter_flou = True
app._fwhm_hist = []

print("[3] rejet FWHM : > 2× la médiane (et > 3 px) → rejeté ; 1,6× → gardé")
for f in (NET, NET2, NET3):               # 3 gardées σ1,5 (FWHM ≈ 3,5)
    app._filtre_floue(f)
verifie(app._filtre_floue(LEGER) == "",
        "frame légèrement floue (σ2,4 ≈ 1,6×) → GARDÉE (pas d'excès)")
motif_f = app._filtre_floue(MOYEN)
verifie(motif_f != "" and "FWHM" in motif_f,
        f"frame σ3,4 (FWHM ≈ 2,3× la médiane) → REJETÉE (« {motif_f} »)")

print("[4] rejet score étoiles : effondré + FWHM dégradée → rejeté ; "
      "effondré SEUL → gardé (dossier mixé)")
app._fwhm_hist = []
for f in (NET, NET2, NET3):
    app._filtre_floue(f)
f_m, n_m = app._score_qualite(MOYEN)          # ~2,3× la FWHM, nb quasi plein
ref_n = [m[1] for m in app._fwhm_hist]
nb_bas = max(1, int(0.3 * float(np.median(ref_n))))
patche = _MesureForcee(app, (f_net, nb_bas))   # FWHM IDENTIQUE, nb effondré
# Méthode appelée NON LIÉE avec l'instance patchée (sinon self = base et la
# mesure forcée ne serait jamais consultée).
verifie(ui.App._filtre_floue(patche, NET) == "",
        "nb effondré mais FWHM IDENTIQUE → GARDÉ (autre champ, pas du flou)")
# FWHM dégradée mais SOUS la marge 2× (1,6×) : seul le critère « étoiles »
# peut rejeter — la FWHM à 2,3× (MOYEN) déclencherait le critère FWHM avant.
f_d = 1.6 * f_net
patche2 = _MesureForcee(app, (f_d, nb_bas))    # FWHM dégradée + nb effondré
motif_e = ui.App._filtre_floue(patche2, NET)
verifie(motif_e != "" and "étoiles" in motif_e,
        f"nb effondré + FWHM dégradée → REJETÉ (« {motif_e} »)")

print("[5] défocalisation poussée (nb 0) : rejetée si les gardées ont des "
      "étoiles ; nébulosité pure → jamais")
app._fwhm_hist = []
for f in (NET, NET2, NET3):
    app._filtre_floue(f)
motif_t = app._filtre_floue(TRES)
verifie(motif_t != "" and "étoiles" in motif_t,
        f"frame σ8 (nb 0, FWHM non mesurable) → REJETÉE (« {motif_t} »)")
app._fwhm_hist = [(None, 0), (None, 0), (None, 0)]
verifie(app._filtre_floue(TRES) == "" and app._filtre_floue(NET) == "",
        "gardées toutes sans étoiles (nébulosité) → RIEN n'est rejeté")

print("[6] intégration worker : TRES ni empilée ni archivée ; suite normale")
app2 = ui.App(root)
app2.archive.intervalle_s = 0.0
app2.stacker = LiveStacker(SHAPE, k=None)
app2._definir_reference(NET)                # référence = frame nette


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
    # TRES arrive après 3 nettes : le filtre a sa référence → il doit le
    # bloquer AVANT l'archivage, et la série doit reprendre normalement.
    app2.camera = CamFournit([NET, NET2, NET3, TRES, NET, NET2])
    app2.running = True
    th = threading.Thread(target=app2._worker, daemon=True)
    th.start()
    t0 = time.time()
    while time.time() - t0 < 30.0 and (app2.floues_rejetees < 1
                                       or app2.archive.n < 5):
        time.sleep(0.05)
    app2.running = False
    th.join(timeout=5.0)
    verifie(app2.floues_rejetees == 1,
            f"compteur : {app2.floues_rejetees} frame floue rejetée (attendu 1)")
    verifie(app2.archive.n == 5,
            f"archive : {app2.archive.n} frames (TRES NON archivée)")
    verifie(app2.stacker.n == 5,
            f"empilement : {app2.stacker.n} frames (TRES NON empilée)")
finally:
    app2.archive.vider()

print("[7] stats + config round-trip (`rejeter_flou`, booléen explicite)")
st_test = dict(frames=5, rejets=0, bad=0, floues=1, align="—", archive=5,
               cam="test", fps=0.0, file="", pending=0, failed=0,
               seeing=None, seeing_msg="")
app2._update_status(st_test)
verifie("Frames floues rejetées : 1" in app2.lbl_stats.cget("text"),
        "stats : ligne « Frames floues rejetées : 1 » affichée")
st_test["floues"] = 0
app2._update_status(st_test)
verifie("floues" not in app2.lbl_stats.cget("text"),
        "stats : pas de ligne « floues » quand rien n'est rejeté")

app3 = ui.App(root)
verifie(app3.var_rejeter_flou.get() is True and app3.rejeter_flou is True,
        "case « Rejeter les frames floues (auto) » cochée PAR DÉFAUT")
app3.var_rejeter_flou.set(False)
app3._on_rejeter_flou()
verifie(app3.rejeter_flou is False, "case décochée → filtre désactivé")
app3._sauver_config_app()
c = sauvegardes[-1]
verifie(c.get("rejeter_flou") is False,
        "config écrite : rejeter_flou = False (booléen explicite)")
ui.CONFIG = {"rejeter_flou": False}
app4 = ui.App(root)
verifie(app4.var_rejeter_flou.get() is False and app4.rejeter_flou is False,
        "config restaurée (case décochée comprise)")
ui.CONFIG = {"rejeter_flou": True}
app5 = ui.App(root)
verifie(app5.rejeter_flou is True, "config rejeter_flou = True restaurée")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
