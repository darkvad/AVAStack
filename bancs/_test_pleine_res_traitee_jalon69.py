# -*- coding: utf-8 -*-
"""Banc v2.38.1 — RENDU PLEINE RÉSOLUTION EN VUE « TRAITÉE ».

DEMANDE D'ALAIN (27/09/2026) : « ok pour le rendu pleine résolution en vue
traitée, je pensais que c'était évident de le faire ». La v2.38.0 ne livrait
l'option que pour la vue « empilement » — et PIRE, `_src_rendu` rendait
l'EMPILEMENT complet dès que l'option était cochée, SANS regarder la vue : en vue
« traitée » (l'écran doit montrer le résultat du ⚡ traitement externe), l'écran
montrait donc l'empilement, et le zoom « fidèle » ne portait pas sur l'image
annoncée.

Vérifie :
  [1] la source pleine résolution SUIT LA VUE (`_src_pleine_res`) : empilement
      complet en vue « empilement », RÉSULTAT EXTERNE (`proc_full`) en vue
      « traitée » — avec un TÉMOIN ré-écrivant la formule de la v2.38.0, qui
      prouve que l'assertion DISCRIMINE (sans la correction, ce serait
      l'empilement qui serait rendu) ;
  [2] les replis : option décochée (aucune bascule), image complète absente de
      la vue courante (début de session, avant le premier ⚡) → aperçu, jamais
      d'écran vide ; décocher LIBÈRE la copie de l'empilement mais laisse
      `proc_full` intact (il sert aux sauvegardes) ;
  [3] L'ÉCRAN = LE FICHIER en vue « traitée » : le rendu affiché (chemin
      `process()`, alimenté par `_src_rendu`) et le fichier écrit par la VRAIE
      chaîne de sauvegarde « tel que vu » (`_save_asseen_thread`, vue
      « traitée ») sont identiques — ÉGALITÉ exigée, pas une tolérance (leçon du
      jalon 68) ; le fichier est relu par un lecteur INDÉPENDANT (astropy brut) ;
  [4] le libellé d'aide de la case annonce les DEUX vues (empilement ou résultat
      traité).

Nécessite un affichage. Exécution : python bancs/_test_pleine_res_traitee_jalon69.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from astropy.io import fits

import avastack.ui.app as ui
from avastack.processing import veralux as veralux

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


def scene_synthetique(n=256, fond=0.02, seed=8039):
    """Ciel factice : fond + étoiles + nébulosité + grain (linéaire [0..1]).

    Cœur des étoiles ~0,45 (JAMAIS écrêté : une étoile blanche à 1,0 n'aurait
    aucune couleur à déposer — leçon du jalon 67) et PSF fine.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    img = np.full((n, n, 3), fond, np.float32)
    neb = 0.05 * np.exp(-((yy - n * 0.35) ** 2 + (xx - n * 0.5) ** 2)
                        / (n * n / 24.0))
    img += neb[..., None].astype(np.float32)
    for (cx, cy, coul, amp) in ((90.0, 80.0, (1.0, 0.72, 0.42), 0.45),
                                (200.0, 190.0, (0.42, 0.70, 1.0), 0.45),
                                (150.0, 40.0, (0.9, 0.95, 1.0), 0.12)):
        prof = amp / (1.0 + ((xx - cx) ** 2 + (yy - cy) ** 2) / 1.8 ** 2) ** 2.0
        img += prof[..., None].astype(np.float32) * np.array(
            coul, np.float32).reshape(1, 1, 3)
    img += rng.normal(0.0, 0.0006, img.shape).astype(np.float32)
    return np.clip(img, 0.0, None).astype(np.float32)


print("=" * 78)
print("[1] la source pleine résolution SUIT LA VUE")
print("=" * 78)
ui.CONFIG = {}
capture = {}
ui.sauver_config = lambda d: capture.update(d)
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()

# L'empilement complet et le résultat du ⚡ traitement externe : MÊME taille (le
# résultat externe dérive de l'empilement) mais fonds différents → une erreur de
# source se VOIT (fond 0,02 contre 0,06).
stack = np.full((300, 300, 3), 0.02, np.float32)
stack[100:200, 100:200] = 0.35               # un objet, pour que ce ne soit pas plat
traite = np.full((300, 300, 3), 0.06, np.float32)
traite[100:200, 100:200] = 0.50
apercu_stack = cv2.resize(stack, (150, 150), interpolation=cv2.INTER_AREA)
apercu_traite = cv2.resize(traite, (150, 150), interpolation=cv2.INTER_AREA)

app._stack_pleine_res = stack
app.proc_full = traite
app.proc_show = apercu_traite
app.var_vl_pleine_res.set(True)
app._on_vl_pleine_res()
verifie(app._pleine_res_activee(), "option « Rendu pleine résolution » cochée")

app.var_view.set("pile")
verifie(app._src_pleine_res() is stack,
        "vue « empilement » : source = l'EMPILEMENT complet")
verifie(app._src_rendu(apercu_stack) is stack,
        "vue « empilement » : `_src_rendu` rend l'empilement complet "
        "(comportement de la v2.38.0 préservé)")

app.var_view.set("traitée")
verifie(app._src_pleine_res() is traite,
        "vue « traitée » : source = le RÉSULTAT EXTERNE (`proc_full`)")
verifie(app._src_rendu(apercu_traite) is traite
        and app._src_rendu(apercu_traite) is not stack,
        "vue « traitée » : `_src_rendu` rend `proc_full` — et NON l'empilement "
        "(c'est le défaut corrigé)")


def _src_rendu_v2380(app_):
    """TÉMOIN : la formule de la v2.38.0, ré-écrite ici exprès (elle rend
    l'EMPILEMENT dès que l'option est cochée, sans regarder la vue)."""
    if app_._pleine_res_activee() and app_._stack_pleine_res is not None:
        return app_._stack_pleine_res
    return app_.proc_show


verifie(_src_rendu_v2380(app) is stack,
        "TÉMOIN : la formule de la v2.38.0 rendrait l'EMPILEMENT en vue "
        "« traitée » → le banc DISCRIMINE bien (il échouait avant la v2.38.1)")

print()
print("=" * 78)
print("[2] replis : jamais d'écran vide, et `proc_full` préservé")
print("=" * 78)
app.var_view.set("traitée")
app.proc_full = None
verifie(app._src_rendu(apercu_traite) is apercu_traite,
        "vue « traitée » sans résultat (avant le premier ⚡) → repli sur l'aperçu")
app.proc_full = traite
app.var_view.set("pile")
app._stack_pleine_res = None
verifie(app._src_rendu(apercu_stack) is apercu_stack,
        "vue « empilement » avant le premier empilement → repli sur l'aperçu")
app._stack_pleine_res = stack

app.var_vl_pleine_res.set(False)
app._on_vl_pleine_res()
verifie(app._src_rendu(apercu_stack) is apercu_stack
        and app._src_rendu(apercu_traite) is apercu_traite,
        "option décochée : l'APERÇU dans les deux vues (comportement d'origine)")
verifie(app.proc_full is traite,
        "décocher ne libère PAS `proc_full` : il sert à « Enregistrer le "
        "résultat traité (linéaire) » et à « tel que vu » en vue traitée")
app.var_vl_pleine_res.set(True)
app._on_vl_pleine_res()

print()
print("=" * 78)
print("[3] L'ÉCRAN = LE FICHIER en vue « traitée » (écart 0 exigé)")
print("=" * 78)
d = app.disp
d.reset()
d.stretch = "veralux"
d.vl_profil = "Rec.709 (Recommended)"
d.vl_mode_res = veralux.MODE_TARGET_BG
d.vl_target_bg = 0.16
verifie(veralux.moteur_disponible(), "moteur VeraLux disponible")
scene = scene_synthetique()
# La VUE commande la chaîne : en vue « traitée » les corrections PRÉ-étirement
# restent coupées (neutralisation, chroma : déjà dans la chaîne externe), comme
# le débruitage et la netteté ; les corrections APRÈS étirement (SCNR…) valent
# pour les deux vues depuis la v2.48.1 — exactement ce que fait _tick.
app.var_view.set("traitée")
app._sync_vl_couleur_vue()
app._sync_vl_graxpert_vue()
app._sync_vl_denoise_vue()
app._sync_vl_sharp_vue()
app.proc_full = scene
app.proc_show = cv2.resize(scene, (128, 128), interpolation=cv2.INTER_AREA)
_src = app._src_rendu(app.proc_show)
verifie(_src is scene,
        "la chaîne d'affichage est nourrie du RÉSULTAT TRAITÉ complet")
ecran = np.asarray(d.process(_src, live=False), np.uint8)   # soumet le rendu
verifie(attendre_vl(d), "solveur VeraLux : rendu terminé")
ecran = np.asarray(d.process(_src, live=False), np.uint8)   # rendu définitif

tmp = tempfile.mkdtemp(prefix="avastack_j69_")
path = os.path.join(tmp, "tel_que_vu_traitee.fits")
reglages = app._reglages_rendu()
app.asseen_result = None
app.asseen_busy = True
app._save_asseen_thread(path, "traitée", scene.astype(np.float32).copy(),
                        reglages, app._session)
verifie(app.asseen_result == path and os.path.isfile(path),
        "la VRAIE chaîne de sauvegarde « tel que vu » (vue traitée) a écrit "
        "le fichier")
data = np.asarray(fits.getdata(path), np.float32)      # lecteur INDÉPENDANT
if data.ndim == 3 and data.shape[0] <= 4 and data.shape[-1] > 4:
    data = np.ascontiguousarray(np.transpose(data, (1, 2, 0)))
fichier = np.asarray((data * 255.0).astype(np.uint8), np.uint8)
pire = int(np.max(np.abs(ecran.astype(np.int16) - fichier.astype(np.int16))))
print(f"    écran {ecran.shape[:2]} · fichier {fichier.shape[:2]} · "
      f"écart max {pire} niveau(x) de 8 bits")
verifie(ecran.shape == fichier.shape and pire == 0,
        "l'écran montre EXACTEMENT le fichier écrit en vue « traitée » (écart 0)")

print()
print("=" * 78)
print("[4] le libellé d'aide annonce les deux vues")
print("=" * 78)
textes = [w.cget("text") for w in app.frm_veralux.winfo_children()
          if "text" in w.keys()]
aide = [t for t in textes if "COMPLÈTE" in t]
verifie(len(aide) == 1 and "empilement" in aide[0] and "traité" in aide[0],
        "le libellé de la case pleine résolution mentionne l'empilement ET le "
        "résultat traité")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
shutil.rmtree(tmp, ignore_errors=True)
try:
    root.destroy()
except tk.TclError:
    pass
raise SystemExit(0 if ok else 1)
