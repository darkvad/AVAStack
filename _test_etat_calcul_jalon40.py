# -*- coding: utf-8 -*-
"""Test du jalon 40 — état du calcul VeraLux matérialisé à l'écran.

Demande d'Alain : « matérialiser qu'on applique le traitement et que c'est
terminé — un curseur de calcul qui revient normal quand c'est fait ou la
ligne d'état qui indique GX, net, logd… ».

Vérifie :

  [1] le thread solveur écrit l'étape COURANTE (vl_stage) à chaque maillon
      de la chaîne — GraXpert → débruitage → netteté → étirement (l'étape
      « préparation » court avant le premier outil : rien ne l'enregistre)
      — via des outils/modules factices, et la remet à "" à la fin
      (vl_en_cours() False) ;
  [2] l'UI : pendant un calcul, lbl_vl = « ⏳ calcul : <étape>… » (ambre) et
      le curseur pb_vl EST affiché ; à la fin, ligne de résultat avec les ✓
      des étapes actives (GX/DN/NET/COUL) + logD + fond, curseur retiré ;
      erreur → texte en rouge ; en mode STF, rien ne s'affiche.

Nécessite un affichage. Exécution : python _test_etat_calcul_jalon40.py
"""
import sys
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui
from avastack.processing import display as dp
from avastack.processing import veralux as vl
from avastack.external import live as gx_live
from avastack.processing import denoise as dn
from avastack.processing import sharpness as sharp

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


rng = np.random.default_rng(40)
H, W = 60, 80


def image_test():
    img = np.empty((H, W, 3), np.float32)
    img[..., 0] = 0.08
    img[..., 1] = 0.16 + rng.normal(0, 0.01, (H, W)).astype(np.float32)
    img[..., 2] = 0.08
    img[20:28, 10:18] = (0.25, 0.05, 0.25)
    return np.clip(img, 0.0, 1.0)


# ==================================== [1] étapes écrites par le solveur
print("[1] solveur : vl_stage posé à chaque étape, remis à zéro à la fin")
d = dp.DisplayProcessor()
d.stretch = "veralux"
d.vl_mode_res = vl.MODE_LOG_D
d.vl_log_d = 2.0
d.vl_profil = vl.PROFIL_PAR_DEFAUT
d.vl_graxpert = True
d.vl_graxpert_cmd = "gx"             # factice ci-dessous : jamais exécutée
d.vl_denoise = True
d.vl_sharp = True
etapes = []

_gx_reel = gx_live.appliquer
_dn_reel = dn.denoiser
_sh_reel = sharp.deconvoluer
_vl_reel = vl.etirer


def _faire_gx(img, cmd, *a, **k):
    etapes.append(d.vl_stage)
    return img, ""


def _faire_dn(img, methode, force, *a, **k):
    etapes.append(d.vl_stage)
    return img, ""


def _faire_sh(img, iterations=5, mesure=None, *a, **k):
    etapes.append(d.vl_stage)
    return img, ""


def _faire_vl(img, **params):
    etapes.append(d.vl_stage)
    return _vl_reel(img, **params)


gx_live.appliquer = _faire_gx
dn.denoiser = _faire_dn
sharp.deconvoluer = _faire_sh
vl.etirer = _faire_vl
try:
    img = image_test()
    d.process(img)                   # soumission (image d'attente rendue)
    verifie(d.vl_en_cours(), "calcul soumis : vl_en_cours() True")
    t0 = time.time()
    while (d._vl_pending or d._vl_job is not None) and time.time() - t0 < 60:
        time.sleep(0.01)
    verifie(etapes == ["GraXpert", "débruitage", "netteté", "étirement"],
            f"étapes dans l'ordre de la chaîne ({etapes})")
    verifie(d.vl_en_cours() is False and d.vl_stage == "",
            "fin du calcul : vl_en_cours() False, vl_stage remis à \"\"")
finally:
    gx_live.appliquer = _gx_reel
    dn.denoiser = _dn_reel
    sharp.deconvoluer = _sh_reel
    vl.etirer = _vl_reel

# ==================================== [2] UI : ⏳ + curseur puis résultat
print("[2] UI : ⏳ + curseur pendant, résultat/erreur à la fin")
ui.CONFIG = {}
ui.sauver_config = lambda a: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
d2 = app.disp
app.var_moteur.set("VeraLux")        # lecture seule par _maj_lbl_vl
app.last_show = image_test()         # aperçu (pour le rendu du résultat)
app._maj_lbl_vl()                    # état initial : rien en cours
verifie(app.pb_vl.winfo_manager() == "",
        "état initial : curseur de calcul invisible")

# --- calcul en cours : ⏳ + étape + curseur visible
d2._vl_pending = True
d2.vl_stage = "débruitage"
app._maj_lbl_vl()
# NB Tk 9 : cget("foreground") renvoie un OBJET couleur, pas une str —
# comparaison tolérante via str() (fonctionne aussi sur les Tk anciens).
coul_lbl = str(app.lbl_vl.cget("foreground"))
verifie("⏳" in app.lbl_vl.cget("text") and "débruitage" in app.lbl_vl.cget("text")
        and "#c98a00" in coul_lbl,
        f"calcul en cours : « {app.lbl_vl.cget('text')} » en ambre")
verifie(app.pb_vl.winfo_manager() != "",
        "calcul en cours : curseur de calcul affiché")
verifie(app._vl_lbl_txt == app.lbl_vl.cget("text"),
        "mémo du texte cohérent (anti-spam)")
# étape suivante : le texte suit (puis ne bouge plus sans changement)
d2.vl_stage = "netteté"
app._maj_lbl_vl()
verifie("netteté" in app.lbl_vl.cget("text"), "l'étape affichée suit le worker")
txt_avant = app.lbl_vl.cget("text")
app._maj_lbl_vl()
verifie(app.lbl_vl.cget("text") == txt_avant,
        "tick sans changement : texte réécrit à l'identique (pas de clignotement)")

# --- fin du calcul : ligne de résultat, curseur retiré
d2._vl_pending = False
d2.vl_stage = ""
d2.vl_graxpert = True
d2.vl_denoise = True
d2.vl_sharp = True
d2.vl_scnr = True
d2.vl_log_d_resolu = 2.5
d2.vl_diagnostics = {"median_luminance_finale": 0.2}
d2.vl_error = ""
d2.vl_new = True
app._maj_lbl_vl()
coul_res = str(app.lbl_vl.cget("foreground"))
verifie(app.lbl_vl.cget("text")
        == "GX ✓ · DN ✓ · NET ✓ · COUL ✓ · logD 2.50 · fond 0.200"
        and "#1d7f1d" in coul_res,
        f"résultat : « {app.lbl_vl.cget('text')} » en vert (COUL ✓ inclus)")
verifie(app.pb_vl.winfo_manager() == "",
        "fin du calcul : curseur de calcul retiré (revient normal)")

# --- erreur : texte rouge
d2.vl_new = True
d2.vl_error = "boom test"
d2.vl_diagnostics = None
app._maj_lbl_vl()
coul_err = str(app.lbl_vl.cget("foreground"))
verifie(app.lbl_vl.cget("text") == "boom test"
        and "#d04040" in coul_err,
        "erreur : texte en rouge")

# --- mode STF (jalon 41 : le cadre d'état est visible dans les DEUX
# modes, mais un calcul VERA LUX en attente ne s'y affiche pas — le solveur
# VeraLux n'est pas utilisé en STF)
app.var_moteur.set("STF")
d2._vl_pending = True
d2.vl_stage = "étirement"
app._maj_lbl_vl()
verifie(app.pb_vl.winfo_manager() == ""
        and app.lbl_vl.cget("text") == "boom test",
        "mode STF : calcul VeraLux en attente ≠ indicateur, texte inchangé")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)

def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


rng = np.random.default_rng(40)
H, W = 60, 80


def image_test():
    img = np.empty((H, W, 3), np.float32)
    img[..., 0] = 0.08
    img[..., 1] = 0.16 + rng.normal(0, 0.01, (H, W)).astype(np.float32)
    img[..., 2] = 0.08
    img[20:28, 10:18] = (0.25, 0.05, 0.25)
    return np.clip(img, 0.0, 1.0)
