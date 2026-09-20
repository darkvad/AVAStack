# -*- coding: utf-8 -*-
"""Test du jalon 41 — UI indépendante du moteur : couleur live ET état des
calculs visibles dans les DEUX modes (STF/manuel et VeraLux).

Décision d'Alain : « rendre visible tout ce qui s'applique aussi en STF ».
La chaîne couleur (SCNR / SCNR doux / démagenta) est appliquée par le
solveur VeraLux ET par le moteur STF/manuel (process(), testé au jalon 22) :
ses cases sortent du cadre VeraLux → cadre « Couleur live » indépendant.
L'étiquette + le curseur d'état des calculs sortent aussi (cadre « État des
calculs ») : en STF ils signalent le solveur de netteté dédié (jalon 12).

Vérifie :

  [1] cadres indépendants : frm_couleur et frm_etat sont packés AUSSI en
      mode VeraLux (et restent packés en STF, contrairement à frm_veralux) ;
  [2] cases couleur effectives EN STF : coche SCNR → dominance verte
      réduite par le moteur STF/manuel (pas seulement en VeraLux) ;
  [3] état des calculs en STF : solveur de netteté occupé → « ⏳ calcul :
      netteté… » + curseur ; fini → retour au repos (« — », curseur retiré) ;
      en VeraLux, le solveur de netteté dédié (inutilisé) ne déclenche
      RIEN.

Nécessite un affichage. Exécution : python _test_ui_moteur_jalon41.py
"""
import sys
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


rng = np.random.default_rng(41)
H, W = 120, 160


def image_test():
    img = np.empty((H, W, 3), np.float32)
    img[..., 0] = 0.08
    img[..., 1] = 0.16 + rng.normal(0, 0.01, (H, W)).astype(np.float32)
    img[..., 2] = 0.08
    img[60:70, 20:30] = (0.25, 0.05, 0.25)
    return np.clip(img, 0.0, 1.0)


ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
d = app.disp

# ==================================== [1] cadres indépendants des deux modes
print("[1] cadres « Couleur live » et « État des calculs » visibles partout")
verifie(app.frm_couleur.winfo_manager() != "" and app.frm_etat.winfo_manager() != "",
        "état initial (STF) : « Couleur live » et « État des calculs » visibles")
verifie(app.lbl_vl.master is app.frm_etat
        and app.pb_vl.master is app.frm_etat,
        "étiquette + curseur d'état DANS le cadre indépendant (plus VeraLux)")
app.var_moteur.set("VeraLux")
app._on_moteur()
root.update_idletasks()
verifie(app.frm_couleur.winfo_manager() != "" and app.frm_etat.winfo_manager() != ""
        and app.frm_veralux.winfo_manager() != "",
        "mode VeraLux : les deux cadres restent visibles (+ cadre VeraLux)")
app.var_moteur.set("STF")
app._on_moteur()
root.update_idletasks()
verifie(app.frm_couleur.winfo_manager() != "" and app.frm_etat.winfo_manager() != ""
        and app.frm_veralux.winfo_manager() == "",
        "retour STF : les deux cadres restent, cadre VeraLux caché")

# ==================================== [2] cases couleur effectives EN STF
print("[2] case SCNR appliquée par le moteur STF/manuel")
app.var_view.set("pile")
app._sync_vl_couleur_vue()
d.auto = False                     # fixes : la relation G' ≤ (R'+B')/2 est
d.black, d.white = 0.02, 0.40      # linéaire et exacte après étirement
d.gamma, d.saturation = 1.0, 1.0
img = image_test()
d.vl_scnr = False
out_sans = d.process(img).astype(np.float32) / 255.0
app.var_vl_scnr.set(True)
app._on_vl_scnr()                  # la case (hors cadre VeraLux) agit
verifie(d.vl_scnr is True, "case cochée EN STF : état propagé au solveur")
out_avec = d.process(img).astype(np.float32) / 255.0
ec_sans = float(np.mean(out_sans[..., 1] - 0.5 * (out_sans[..., 0]
                                                  + out_sans[..., 2])))
ec_avec = float(np.mean(out_avec[..., 1] - 0.5 * (out_avec[..., 0]
                                                  + out_avec[..., 2])))
verifie(ec_avec < ec_sans,
        f"STF : dominance verte réduite par la case (G−(R+B)/2 : "
        f"{ec_sans:.4f} → {ec_avec:.4f})")
app.var_vl_scnr.set(False)
app._on_vl_scnr()

# ==================================== [3] état des calculs en STF = netteté
print("[3] en STF, l'indicateur suit le solveur de netteté dédié (jalon 12)")
app.var_moteur.set("STF")
d._sh_pending = True
app._maj_lbl_vl()
txt = app.lbl_vl.cget("text")
verifie("⏳" in txt and "netteté" in txt
        and "#c98a00" in str(app.lbl_vl.cget("foreground"))
        and app.pb_vl.winfo_manager() != "",
        f"STF netteté en cours : « {txt} » + curseur visible")
d._sh_pending = False
app._maj_lbl_vl()
verifie(app.lbl_vl.cget("text") == "—" and app.pb_vl.winfo_manager() == "",
        "STF netteté terminée : retour au repos (« — », curseur retiré)")
# en VeraLux, le solveur de netteté DÉDIÉ est inutilisé : il ne déclenche rien
app.var_moteur.set("VeraLux")
d._sh_pending = True
app._maj_lbl_vl()
verifie(app.lbl_vl.cget("text") == "—" and app.pb_vl.winfo_manager() == "",
        "VeraLux : netteté DÉDIÉE (STF) ignorée par l'indicateur")
d._sh_pending = False
app._maj_lbl_vl()

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)