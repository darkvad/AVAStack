# -*- coding: utf-8 -*-
"""Test du jalon 128 — garder l'image VeraLux pendant un recalcul + indicateur.

Demande d'Alain (12/10/2026) : en étirement VeraLux, à chaque NOUVEAU calcul,
l'image « sautait » brutalement vers l'aperçu STF pendant la résolution. On
garde désormais à l'écran le DERNIER résultat VeraLux (périmé de quelques
dixièmes de seconde) et l'UI superpose un indicateur « ⏳ Calcul VeraLux… »
(arc tournant, coin haut-gauche).

Vérifie :

  [0] le worker PUBLIE le moteur de son résultat (`_vl_result_moteur` :
      « veralux » en étirement VeraLux, « stf » dans la chaîne pré-étirement
      STF/manuel) ;
  [1] en VeraLux, un recalcul EN COURS conserve EXACTEMENT l'image VeraLux
      précédente (identité d'objet) — et ce n'est PAS le repli STF ;
  [2] garde-fou moteur : un résultat issu de la branche STF n'est JAMAIS
      conservé (après un passage STF → VeraLux, `_vl_result` est l'image
      PRÉ-ÉTIRÉE : la garder afficherait une image sombre) ;
  [3] garde-fou forme : un résultat précédent d'une AUTRE taille n'est pas
      conservé (repli STF) ;
  [4] hors calcul (`_vl_pending` False), rien n'est conservé (repli STF) ;
  [5] bout-en-bout `process()` : le rendu à l'écran est STRICTEMENT identique
      avant et pendant le recalcul (l'utilisateur ne voit que l'overlay) ;
  [6] UI : `_spinner_vl_actif()` est vrai SEULEMENT en VeraLux + calcul en
      cours, et `_dessiner_spinner_vl()` crée/retire l'item canvas « vl_spin » ;
  [7] UI : `_maj_lbl_vl()` (tick) fait TOURNER l'arc (angle avancé) et le
      retire à la fin du calcul.

Exécution : python bancs/_test_conservation_veralux_jalon128.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing.display import DisplayProcessor
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée != console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    print(("  OK  " if cond else "  ECHEC ") + msg)
    ok = bool(ok and cond)


rng = np.random.default_rng(128)
y, x = np.mgrid[0:400, 0:600]
img = np.clip(rng.normal(0.008, 0.004, (400, 600)).astype(np.float32), 0, None)
img += (0.8 * np.exp(-((y - 200) ** 2 + (x - 300) ** 2) / 8.0)).astype(np.float32)
img = np.clip(img, 0.0, 1.0)


def attendre(d, max_s=8.0):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < max_s:
        if d._vl_result is not None and not d._vl_pending:
            return True
        time.sleep(0.05)
    return False


def repli_stf(d):
    """Repli STF/auto tel que le produit `_process_chaine` en VeraLux (image
    d'attente) — calculé à l'identique pour comparer."""
    lo, hi, m = d._auto_params(img, live=False)
    return d._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)


# ============================================================ [0] le worker
print("[0] Le worker publie le MOTEUR de son résultat")
d0 = DisplayProcessor()
d0.stretch = "veralux"
d0.vl_mode_res = vl.MODE_LOG_D
d0.vl_log_d = 2.0
d0.process(img)                        # soumet le job VeraLux
verifie(attendre(d0), "résolution VeraLux terminée")
verifie(d0._vl_result_moteur == "veralux",
        f"moteur « veralux » publié ({d0._vl_result_moteur!r})")

d0b = DisplayProcessor()
d0b.stretch = "stf"
d0b.vl_chroma = True                   # force un job de la chaîne pré-étirement
d0b.process(img)
verifie(attendre(d0b), "chaîne pré-étirement STF terminée")
verifie(d0b._vl_result_moteur == "stf",
        f"moteur « stf » publié dans la branche pré-étirement ({d0b._vl_result_moteur!r})")

# ====================== [1] conservation de l'image VeraLux pendant le calcul
print("[1] Recalcul en cours : l'image VeraLux précédente est CONSERVÉE")
d = DisplayProcessor()
d.stretch = "veralux"
d.vl_mode_res = vl.MODE_LOG_D
d.vl_log_d = 2.0
key = d._vl_params() + (img.shape,)
d._vl_key = key                        # pas de resoumission pendant le test
fake = np.full_like(img, 0.42, dtype=np.float32)   # image VeraLux « précédente »
d._vl_result = (("CLE_ANCIENNE",), fake)           # clé ≠ courante → pas de cache
d._vl_result_moteur = "veralux"
d._vl_pending = True
out = d._process_chaine(img, live=False)
verifie(out is fake, "l'image VeraLux précédente est rendue à l'IDENTIQUE")
verifie(not np.array_equal(out, repli_stf(d)),
        "et ce n'est PAS le repli STF (l'image ne « saute » plus)")

# ============================ [2] garde-fou moteur : pas de résultat « stf »
print("[2] Garde-fou moteur : un résultat de la branche STF n'est pas conservé")
d._vl_result_moteur = "stf"
out2 = d._process_chaine(img, live=False)
verifie(out2 is not fake, "l'image pré-étirée (sombre) n'est PAS conservée")
verifie(np.array_equal(out2, repli_stf(d)), "repli STF appliqué à la place")

# ================================ [3] garde-fou forme : forme différente
print("[3] Garde-fou forme : un résultat d'une AUTRE taille n'est pas conservé")
d._vl_result_moteur = "veralux"
d._vl_result = (("CLE_ANCIENNE",), np.zeros((10, 10), np.float32))
out3 = d._process_chaine(img, live=False)
verifie(not np.array_equal(out3, fake), "forme incompatible → repli STF")
verifie(np.array_equal(out3, repli_stf(d)), "repli STF exact")

# ============================== [4] hors calcul : rien à conserver
print("[4] Hors calcul : repli STF (aucune conservation)")
d._vl_pending = False
d._vl_result = (("CLE_ANCIENNE",), fake)
d._vl_result_moteur = "veralux"
out4 = d._process_chaine(img, live=False)
verifie(np.array_equal(out4, repli_stf(d)),
        "sans calcul en cours, le repli STF reste la règle")

# ====================== [5] bout-en-bout process() : écran IDENTIQUE
print("[5] process() : rendu STRICTEMENT identique avant et pendant le recalcul")
d.gamma, d.saturation = 1.0, 1.0
d.bar_noir, d.bar_median, d.bar_blanc = 0.0, 0.5, 1.0
d._vl_pending = False
d._vl_result = (key, fake)
d._vl_result_moteur = "veralux"
ref = d.process(img, live=False)       # résultat à jour (cache)
d._vl_result = (("CLE_ANCIENNE",), fake)   # nouveau calcul en cours
d._vl_pending = True
pend = d.process(img, live=False)
verifie(np.array_equal(ref, pend),
        "pendant le recalcul, l'écran garde EXACTEMENT le rendu VeraLux")

# ==================================================== [6] UI : l'indicateur
print("[6] UI : indicateur superposé (arc « vl_spin »)")
import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui

ui.CONFIG = {}
ui.sauver_config = lambda a: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
dd = app.disp

# état initial : aucun calcul → pas d'overlay
dd._vl_pending = False
dd.stretch = "stf"
app._dessiner_spinner_vl()
verifie(not app._spinner_vl_actif()
        and len(app.cv_img.find_withtag("vl_spin")) == 0,
        "au repos : aucun indicateur superposé")

# VeraLux + calcul en cours → overlay présent
dd.stretch = "veralux"
app.var_moteur.set("VeraLux")
dd._vl_pending = True
dd.vl_stage = "étirement"
app._dessiner_spinner_vl()
verifie(app._spinner_vl_actif()
        and len(app.cv_img.find_withtag("vl_spin")) > 0,
        "calcul VeraLux : arc + libellé affichés (tag « vl_spin »)")

# STF + calcul en cours → PAS d'overlay (étirement instantané)
dd.stretch = "stf"
app.var_moteur.set("STF")
app._dessiner_spinner_vl()
verifie(not app._spinner_vl_actif()
        and len(app.cv_img.find_withtag("vl_spin")) == 0,
        "STF : pas d'indicateur (le worker tourne mais l'étirement est instantané)")

# =========================== [7] UI : l'arc tourne (tick) et disparaît à la fin
print("[7] UI : le tick fait tourner l'arc puis le retire")
dd.stretch = "veralux"
app.var_moteur.set("VeraLux")
dd._vl_pending = True
dd.vl_stage = "netteté"
dd.vl_new = False
app._refresh_preview = lambda *a, **k: None     # éviter un vrai job pendant le test
app._vl_spin_angle = 0.0
app._maj_lbl_vl()
a1 = app._vl_spin_angle
app._maj_lbl_vl()
a2 = app._vl_spin_angle
verifie(a2 != a1 and len(app.cv_img.find_withtag("vl_spin")) > 0,
        f"l'angle de l'arc avance à chaque tick ({a1:.0f}° → {a2:.0f}°)")
dd._vl_pending = False
dd.vl_stage = ""
app._maj_lbl_vl()
verifie(len(app.cv_img.find_withtag("vl_spin")) == 0,
        "calcul terminé : l'indicateur est retiré")

root.destroy()

print("\n===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)



