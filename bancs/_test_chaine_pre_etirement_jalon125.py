# -*- coding: utf-8 -*-
"""Test du jalon 125 (VOL. A) — chaîne pré-étirement COMMUNE aux deux moteurs.

Décision d'Alain (11/10/2026) : « le fichier = l'écran ». GraXpert + débruitage
étaient appliqués par la SAUVEGARDE mais PAS par l'écran en STF/manuel : leurs
cases vivaient dans le cadre VeraLux (masqué en STF) alors qu'elles restaient
actives à l'enregistrement. On corrige CÔTÉ ÉCRAN : la chaîne pré-étirement
(GraXpert → débruitage → netteté) est désormais UNIQUE (`_vl_worker`) et seule
la DERNIÈRE étape (l'étirement) dépend du moteur.

Vérifie :
  [1] UI : les cases GraXpert + débruitage ont QUITTÉ le cadre VeraLux et vivent
      dans « Chaîne avant étirement » (`frm_sharp`), VISIBLES dans les deux
      modes (le cadre VeraLux, lui, est masqué en STF) ;
  [2] STF/manuel : la chaîne tourne À L'ÉCRAN — la sortie du worker est l'image
      PRÉ-ÉTIRÉE (GraXpert PUIS débruitage), l'étirement STF étant appliqué par
      `process()` ;
  [3] ÉCRAN == FICHIER : la sortie de chaîne STF est exactement l'image que la
      sauvegarde « tel que vu » enchaîne AVANT l'étirement ;
  [4] le MOTEUR fait partie de la clé de la chaîne ; la chroma entre dans la
      sortie STF (chaîne pré-étirement COMMUNE depuis le jalon 127).

Nécessite un affichage. Exécution :
    python bancs/_test_chaine_pre_etirement_jalon125.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
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

import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui
import avastack.processing.display as dp
import avastack.processing.denoise as dn
import avastack.external.live as gx_live
from avastack.processing import couleurs as C

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def attendre_vl(d, timeout=60.0):
    """Attend la fin du job de la chaîne (polling, 20 ms)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with d._vl_lock:
            if (d._vl_job is None and not d._vl_pending
                    and d._vl_result is not None):
                return True
        time.sleep(0.02)
    return False


rng = np.random.default_rng(125)
IMG = (0.05 + rng.normal(0, 0.01, (128, 128))).astype(np.float32)
np.clip(IMG, 0.0, 1.0, out=IMG)

print("[1] UI : les cases GraXpert/débruitage quittent le cadre VeraLux")
ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()


def trouve(w, texte):
    """Premier descendant dont le texte contient `texte`, ou None."""
    for c in w.winfo_children():
        try:
            if texte in str(c.cget("text")):
                return c
        except tk.TclError:
            pass
        r = trouve(c, texte)
        if r is not None:
            return r
    return None


verifie(trouve(app.frm_sharp, "GraXpert live") is not None,
        "case GraXpert DANS « Chaîne avant étirement » (frm_sharp)")
verifie(trouve(app.frm_sharp, "Débruitage live") is not None,
        "case Débruitage DANS le cadre partagé")
verifie(trouve(app.frm_veralux, "GraXpert live") is None,
        "…et PLUS dans le cadre VeraLux")
verifie(trouve(app.frm_veralux, "Débruitage live") is None,
        "…ni le débruitage")
titre = str(getattr(app._lf_nette, "_btn_header").cget("text"))
verifie("Chaîne avant étirement" in titre, f"titre de section ({titre!r})")
app.var_moteur.set("STF")
app._on_moteur()
root.update_idletasks()
verifie(app._lf_nette.winfo_manager() != "" and app.frm_veralux.winfo_manager() == "",
        "STF : cadre partagé VISIBLE, cadre VeraLux caché")
app.var_moteur.set("VeraLux")
app._on_moteur()
root.update_idletasks()
verifie(app._lf_nette.winfo_manager() != "" and app.frm_veralux.winfo_manager() != "",
        "VeraLux : cadre partagé toujours visible (+ cadre VeraLux)")
root.destroy()

print("[2]/[3] STF/manuel : chaîne à l'écran == chaîne de la sauvegarde")
_reel_gx = gx_live.appliquer
gx_live.appliquer = lambda img, cmd, timeout=gx_live.TIMEOUT_S: \
    (np.flipud(img), "")          # GraXpert factice : copie retournée
try:
    d = dp.DisplayProcessor()
    d.stretch = "stf"
    d.vl_graxpert = True
    d.vl_graxpert_cmd = "faux {input} {output}"   # jamais exécutée (surchargé)
    d.vl_denoise = True
    d.vl_denoise_methode = "nlm"
    d.vl_denoise_force = 0.5
    d.notify_new_stack()
    d.process(IMG)
    verifie(d.vl_en_cours() or d._vl_job is not None,
            "chaîne pré-étirement SOUMISE en STF (GraXpert + débruitage actifs)")
    verifie(attendre_vl(d), "chaîne pré-étirement terminée")
    # [3] Ce que la SAUVEGARDE enchaîne AVANT l'étirement (saver) :
    #     GraXpert PUIS débruitage — l'écran doit produire la MÊME image.
    src = np.flipud(IMG)
    attendu, err = dn.denoiser(src, "nlm", 0.5)
    verifie(err == "", f"débruitage de référence sans erreur ({err!r})")
    verifie(float(np.max(np.abs(d._vl_result[1] - attendu))) < 1e-6,
            "sortie STF = GraXpert PUIS débruitage (ordre de la chaîne)")
    verifie(not np.allclose(d._vl_result[1], IMG),
            "la sortie DIFFÈRE de l'entrée (la chaîne a bien tourné)")
    # L'étirement est appliqué PAR-DESSUS par process() : sa sortie est bien
    # une image 8 bits étirée, pas la sortie de chaîne linéaire.
    out = d.process(IMG)
    verifie(out.dtype == np.uint8 and out.shape == IMG.shape,
            "process() étire la sortie de chaîne (8 bits, mêmes dimensions)")
    # [4] JALON 127 : la chroma n'est PLUS réservée à VeraLux — l'activer entre
    # DANS la sortie STF (chaîne pré-étirement commune, APRÈS la netteté).
    # Image COULEUR : sur une image MONOCHROME la chroma est un NO-OP (elle ne
    # lisserait que Cr/Cb), elle ne serait donc pas observable ici.
    IMG_C = np.stack([IMG, IMG * 0.85, IMG * 1.20], axis=-1).astype(np.float32)
    d.vl_chroma = True
    d.vl_chroma_force = 0.8
    d.notify_new_stack()
    d.process(IMG_C)
    verifie(attendre_vl(d), "2e passage terminé (image couleur)")
    attendu_c, _e_c = dn.denoiser(np.flipud(IMG_C), "nlm", 0.5)
    attendu_chroma = C.reduire_bruit_chroma(attendu_c, force=0.8,
                                            rayon=d.vl_chroma_rayon)
    verifie(float(np.max(np.abs(d._vl_result[1] - attendu_chroma))) < 1e-6,
            "chroma ACTIVE dans la sortie STF (chaîne pré-étirement commune)")
    verifie(not np.allclose(d._vl_result[1], attendu_c),
            "…et la sortie DIFFÈRE bien de celle sans chroma")
finally:
    gx_live.appliquer = _reel_gx

print("[4] le MOTEUR fait partie de la clé de la chaîne")
d2 = dp.DisplayProcessor()
d2.stretch = "stf"
k_stf = d2._vl_params()
d2.stretch = "veralux"
verifie(d2._vl_params() != k_stf,
        "changer de moteur change la clé (la chaîne est relancée)")
verifie(d2.sh_en_cours() is False,
        "plus de solveur de netteté dédié (netteté dans la chaîne unique)")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
