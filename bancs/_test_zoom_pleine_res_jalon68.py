# -*- coding: utf-8 -*-
"""Banc v2.38.0 — ZOOM SUR L'IMAGE PLEINE RÉSOLUTION (l'écran = le fichier).

DEMANDE D'ALAIN (26/09/2026, en réponse au correctif de l'anneau) : « sur l'écran,
je veux pouvoir zoomer sur l'image pleine résolution ». L'écran agrandissait
jusqu'ici l'APERÇU 1600 px (le zoom ×32 ne rendait que de l'interpolation), et
surtout la chaîne non linéaire y tournait à une AUTRE échelle que pour le fichier
(mesuré au jalon 66 : écart moyen 0,015-0,023, max 0,37-0,49 aux cœurs) — l'anneau
de couleur des étoiles n'existe QUE dans les fichiers, pour cette raison.

Vérifie :
  [1] l'option existe, est DÉCOCHÉE par défaut, se PERSISTE
      (`vl_pleine_res_ecran`) et se relit ; décocher LIBÈRE la copie (25 Mo) ;
  [2] la source de rendu (`_src_rendu`) : l'aperçu quand l'option est décochée
      (comportement d'origine préservé), l'empilement COMPLET quand elle est
      cochée, repli sur l'aperçu si aucun empilement complet n'existe ;
  [3] L'ÉCRAN = LE FICHIER (règle du projet) : nourri de l'image COMPLÈTE,
      `DisplayProcessor.process()` (chemin d'affichage) rend EXACTEMENT ce que
      `rendu_pleine_resolution()` (chemin de sauvegarde) écrirait ;
  [4] le ZOOM recadre de VRAIS pixels : à l'échelle 1:1, la géométrie de
      `App._render` rend les pixels de la source AU BIT PRÈS — alors que
      l'aperçu grossi au même cadrage, lui, INVENTE (moins de détail) ;
  [5] le libellé du zoom annonce l'échelle réelle et la mention PLEINE RÉSOLUTION.

Nécessite un affichage. Exécution : python bancs/_test_zoom_pleine_res_jalon68.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import inspect
import sys
import time
import tkinter as tk

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.ui.app as ui
from avastack.processing.display import DisplayProcessor
from avastack.processing import veralux as veralux
from avastack.processing import couleurs as couleurs

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def attendre_vl(d, timeout=60.0):
    """Attend la fin du job du solveur VeraLux (polling, 20 ms)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with d._vl_lock:
            if (d._vl_job is None and not d._vl_pending
                    and d._vl_result is not None):
                return True
        time.sleep(0.02)
    return False


def recadrage(img, zoom, cw=200, ch=120, cx=None, cy=None):
    """COPIE de la géométrie de `App._render` : rend (affiché, fenêtre, échelle).

    `zoom` = 1.0 → image ajustée à la fenêtre ; au-delà, recadrage centré sur
    (cx, cy) et agrandissement — exactement les calculs de l'application."""
    ih, iw = img.shape[:2]
    fit = min(cw / iw, ch / ih)
    scale = fit * zoom
    if zoom <= 1.0001:
        return (cv2.resize(img, (max(1, int(iw * scale)), max(1, int(ih * scale))),
                           interpolation=cv2.INTER_AREA if scale < 1.0
                           else cv2.INTER_LINEAR), img, scale)
    vx = cx if cx is not None else iw / 2.0
    vy = cy if cy is not None else ih / 2.0
    x0, x1 = vx - cw / (2 * scale), vx + cw / (2 * scale)
    y0, y1 = vy - ch / (2 * scale), vy + ch / (2 * scale)
    xi0, yi0 = max(0, int(np.floor(x0))), max(0, int(np.floor(y0)))
    xi1, yi1 = min(iw, int(np.ceil(x1))), min(ih, int(np.ceil(y1)))
    fen = img[yi0:yi1, xi0:xi1]
    interp = cv2.INTER_NEAREST if zoom >= 2.0 else cv2.INTER_LINEAR
    return (cv2.resize(fen, (max(1, int(round((xi1 - xi0) * scale))),
                             max(1, int(round((yi1 - yi0) * scale)))),
                       interpolation=interp), fen, scale)


def hf_energie(img):
    """Énergie haute fréquence (netteté de détail) d'une image affichée."""
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    return float(np.std(g - cv2.GaussianBlur(g, (0, 0), sigmaX=1.5)))


print("=" * 78)
print("[1] l'option : présente, décochée par défaut, persistée, libère la copie")
print("=" * 78)
ui.CONFIG = {}
capture = {}
ui.sauver_config = lambda d: capture.update(d)
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()
verifie(hasattr(app, "var_vl_pleine_res"),
        "case « Rendu pleine résolution » présente dans l'interface")
verifie(app.var_vl_pleine_res.get() is False,
        "DÉCOCHÉE par défaut (le comportement d'origine — aperçu 1600 px — est "
        "préservé)")
app._sauver_config_app()
verifie(capture.get("vl_pleine_res_ecran") is False,
        "persistée à False quand elle est décochée (booléen explicite)")
app.var_vl_pleine_res.set(True)
app._on_vl_pleine_res()
verifie(app._pleine_res_activee(), "cochée → option ACTIVE (helper tolérant)")
verifie(getattr(app, "pleine_res_ecran", None) is True,
        "l'état est MIRÉ dans un attribut PYTHON — c'est lui, et non la variable "
        "Tk, que lisent les threads de travail (RuntimeError « main thread is not "
        "in main loop » sinon, constat réel)")
app._sauver_config_app()
verifie(capture.get("vl_pleine_res_ecran") is True,
        "persistée à True quand elle est cochée")
app._stack_pleine_res = np.zeros((10, 10, 3), np.float32)
app.pleine_res_ecran = False
app.var_vl_pleine_res.set(False)
app._on_vl_pleine_res()
verifie(app._stack_pleine_res is None,
        "décocher LIBÈRE la copie pleine résolution (mémoire rendue)")

print()
print("=" * 78)
print("[2] la source de rendu : aperçu par défaut, empilement complet si cochée")
print("=" * 78)
complet = np.full((380, 600, 3), 0.02, np.float32)
apercu = cv2.resize(complet, (250, 158), interpolation=cv2.INTER_AREA)
app.var_vl_pleine_res.set(False)
app._on_vl_pleine_res()                    # décochée : la copie est libérée…
app._stack_pleine_res = complet            # …on la repose pour comparer
verifie(app._src_rendu(apercu) is apercu,
        "option décochée : c'est l'APERÇU qui est rendu, même si une copie "
        "pleine résolution traîne (comportement d'origine)")
app.var_vl_pleine_res.set(True)
app._on_vl_pleine_res()
verifie(app._stack_pleine_res is complet, "cochée : la copie n'est pas libérée")
verifie(app._src_rendu(apercu) is complet,
        f"option cochée : l'EMPILEMENT COMPLET {complet.shape[:2]} est rendu "
        f"(au lieu de l'aperçu {apercu.shape[:2]})")
app._stack_pleine_res = None
verifie(app._src_rendu(apercu) is apercu,
        "aucun empilement complet (vue traitée, début de session) → repli sur "
        "l'aperçu, jamais d'écran vide")

print()
print("=" * 78)
print("[3] L'ÉCRAN = LE FICHIER : process() == rendu_pleine_resolution()")
print("=" * 78)
rng = np.random.default_rng(8038)
n = 320
yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
scene = np.full((n, n, 3), 0.02, np.float32)
for (cx, cy, coul, amp) in ((90.0, 80.0, (1.0, 0.72, 0.42), 0.6),
                            (230.0, 210.0, (0.42, 0.70, 1.0), 0.6),
                            (180.0, 60.0, (0.9, 0.95, 1.0), 0.08)):
    prof = amp / (1.0 + ((xx - cx) ** 2 + (yy - cy) ** 2) / 2.5 ** 2) ** 2.0
    scene += prof[..., None] * np.array(coul, np.float32).reshape(1, 1, 3)
scene += rng.normal(0.0, 0.0006, scene.shape).astype(np.float32)
scene = np.clip(scene, 0.0, None).astype(np.float32)
d = DisplayProcessor()
d.stretch = "veralux"
d.vl_profil = "Rec.709 (Recommended)"
d.vl_mode_res = veralux.MODE_TARGET_BG
d.vl_target_bg = 0.16
verifie(veralux.moteur_disponible(), "moteur VeraLux disponible")
_ = d.process(scene)                       # soumet le rendu (image d'attente)
verifie(attendre_vl(d), "solveur VeraLux : rendu terminé")
ecran = np.asarray(d.process(scene, live=False), np.uint8)
# CHEMIN DE SAUVEGARDE « tel que vu », répliqué ici comme le fait
# `_save_asseen_thread` : les étapes PRÉ-ÉTIREMENT d'abord (neutralisation du
# fond — ACTIVE par défaut, v2.36.1 — puis réduction du bruit chromatique), et
# l'étirement ensuite. Sans elles, la comparaison serait biaisée (mesuré : 18
# niveaux d'écart, exactement l'effet de la neutralisation oubliée).
source = couleurs.neutraliser_fond(scene) if d.vl_neutre_fond else scene
if d.vl_chroma:
    source = couleurs.reduire_bruit_chroma(source, force=d.vl_chroma_force,
                                           rayon=d.vl_chroma_rayon)
fichier = np.asarray((d.rendu_pleine_resolution(source) * 255.0).astype(np.uint8),
                     np.uint8)
pire = int(np.max(np.abs(ecran.astype(np.int16) - fichier.astype(np.int16))))
print(f"    écran {ecran.shape[:2]} · fichier {fichier.shape[:2]} · "
      f"écart max {pire} niveau(x) de 8 bits")
verifie(ecran.shape == fichier.shape and pire == 0,
        "l'écran montre EXACTEMENT ce que le fichier enregistré contiendra "
        "(écart 0)")

print()
print("=" * 78)
print("[4] le ZOOM recadre de VRAIS pixels (1:1) au lieu de grossir l'aperçu")
print("=" * 78)
ih, iw = ecran.shape[:2]
fit = min(200 / iw, 120 / ih)
zoom_1_1 = 1.0 / fit                       # zoom qui donne l'échelle 1:1
vue_pleine, fen_pleine, s_p = recadrage(ecran, zoom_1_1)
apercu_ecran = cv2.resize(ecran, None, fx=0.4168, fy=0.4168,
                          interpolation=cv2.INTER_AREA)   # l'écran d'avant
grossi = cv2.resize(apercu_ecran, (iw, ih), interpolation=cv2.INTER_LINEAR)
vue_apercu, _, s_a = recadrage(grossi, zoom_1_1)
print(f"    échelle 1:1 demandée au zoom ×{zoom_1_1:.2f} → "
      f"{s_p:.3f} px image / px écran · recadrage {vue_pleine.shape[:2]}")
verifie(abs(s_p - 1.0) < 0.02 and np.array_equal(vue_pleine, fen_pleine),
        "à 1:1, le recadrage rend les pixels de la SOURCE au BIT PRÈS "
        "(aucune interpolation)")
ecart = int(np.max(np.abs(vue_pleine.astype(np.int16)
                          - vue_apercu.astype(np.int16))))
hf_p, hf_a = hf_energie(vue_pleine), hf_energie(vue_apercu)
print(f"    même cadrage via l'aperçu grossi : écart max {ecart} niveaux · "
      f"détail fin {hf_p:.3f} (pleine résolution) contre {hf_a:.3f} (aperçu)")
verifie(ecart > 0 and hf_a < 0.9 * hf_p,
        "l'aperçu grossi ne rend PAS ces pixels (il invente du flou) : c'est "
        "exactement ce que la nouvelle option supprime")

print()
print("=" * 78)
print("[5] le libellé du zoom annonce l'échelle réelle")
print("=" * 78)
src = inspect.getsource(ui.App._render)
verifie("px image / px écran" in src,
        "l'échelle réelle (px image par px écran) est affichée")
verifie("PLEINE RÉSOLUTION" in src and "_pleine_res_activee" in src,
        "la mention PLEINE RÉSOLUTION apparaît quand l'option est active")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
try:
    root.destroy()
except tk.TclError:
    pass
raise SystemExit(0 if ok else 1)

