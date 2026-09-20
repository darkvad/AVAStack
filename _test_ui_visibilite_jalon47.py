# -*- coding: utf-8 -*-
"""Test UI du jalon 47 — visibilité des cadres selon la source choisie.

Demande d'ergonomie d'Alain : « la partie droite de l'écran est surchargée
inutilement » — la colonne de réglages ne doit montrer que les cadres utiles
au choix courant :
  - source caméra (simulée, OpenCV, SDK) → contrôles caméra seuls ;
  - « Dossier surveillé » → cadre dossier + « Cadence d'empilement » ;
  - « Composition multi-dossiers » → cadre composition + cadence ;
  - le réglage de rafale (« Empiler les brutes ») sort des cadres dossier et
    composition où il était dupliqué (jalon 45) : UN SEUL cadre partagé ;
  - masquer ≠ détruire : les valeurs saisies survivent aux allers-retours ;
  - l'ordre des cadres de la colonne ne change jamais (ancre Calibration).

Nécessite un affichage. Exécution : python _test_ui_visibilite_jalon47.py
"""
import sys
import tkinter as tk
from tkinter import ttk

import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def est_packe(w):
    """True si le widget est réellement affiché (masqué = pack_info lève)."""
    try:
        w.pack_info()
        return True
    except tk.TclError:
        return False


def ordre_colonne(app):
    """Cadres LabelFrame visibles de la colonne, dans l'ordre d'affichage."""
    colonne = app.frm_calibration.master   # le frame défilable « left »
    return [w for w in colonne.winfo_children()
            if isinstance(w, ttk.LabelFrame) and est_packe(w)]


ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()

# ==================================== [1] état initial (source par défaut)
print("[1] état initial (Simulée = source caméra)")
verifie(f"AVAStack v{ui.AVASTACK_VERSION}" in root.title(),
        f"la barre de titre affiche la version du package "
        f"(« {root.title()} », jalon 48)")
verifie(est_packe(app.frm_ctrl_cam),
        "source caméra : contrôles caméra visibles (exposition, gain…)")
verifie(est_packe(app.cb_source.master),
        "la combobox de source + Démarrer/Arrêter restent visibles")
verifie(not est_packe(app.frm_dossier), "cadre « Dossier surveillé » caché")
verifie(not est_packe(app.frm_compo), "cadre « Composition multi-filtres » caché")
verifie(not est_packe(app.frm_rafale),
        "cadre « Cadence d'empilement » caché (sans objet pour une caméra)")

# ==================================== [2] source dossier surveillé
print("[2] source « Dossier surveillé »")
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app._on_source_choisie()
root.update_idletasks()
verifie(not est_packe(app.frm_ctrl_cam), "contrôles caméra cachés (inutiles ici)")
verifie(est_packe(app.frm_dossier), "cadre « Dossier surveillé » visible")
verifie(not est_packe(app.frm_compo), "cadre « Composition » caché")
verifie(est_packe(app.frm_rafale), "cadre « Cadence d'empilement » visible (RAFALE)")
verifie(app.lbl_last.master is app.frm_dossier
        and est_packe(app.lbl_last),
        "« Dernier fichier » reste dans le cadre dossier")
verifie(app._cadence_lbls[0].master is app.frm_rafale
        and app._cadence_cbs[0].master.master is app.frm_rafale,
        "la combobox « Empiler les brutes » vit dans le cadre de cadence")

# ==================================== [3] source composition multi-dossiers
print("[3] source « Composition multi-dossiers »")
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._on_source_choisie()
root.update_idletasks()
verifie(not est_packe(app.frm_ctrl_cam), "contrôles caméra cachés")
verifie(not est_packe(app.frm_dossier), "cadre « Dossier surveillé » caché")
verifie(est_packe(app.frm_compo), "cadre « Composition » visible")
verifie(est_packe(app.frm_rafale),
        "cadre « Cadence d'empilement » visible DANS LES DEUX CAS (jalon 45)")
verifie(len(app._cadence_cbs) == 1 and len(app._cadence_lbls) == 1,
        "UN SEUL couple combobox + étiquette (fini la duplication du jalon 45)")

# ==================================== [4] retour caméra SDK
print("[4] retour source caméra (ZWO ASI SDK)")
app.var_source.set("ZWO ASI (SDK)")
app._on_source_choisie()
root.update_idletasks()
verifie(est_packe(app.frm_ctrl_cam), "contrôles caméra de retour")
verifie(not est_packe(app.frm_dossier)
        and not est_packe(app.frm_compo)
        and not est_packe(app.frm_rafale),
        "dossier, composition et cadence cachés")

# ==================================== [5] valeurs conservées + ordre stable
print("[5] allers-retours : valeurs conservées, ordre de la colonne stable")
ordre_avant = ordre_colonne(app)
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app._on_source_choisie()
app.var_folder.set("C:/brutes_test_jalon47")     # valeur saisie en mode dossier
app.var_compo_gains["G"].set("1.7")              # valeur saisie en mode compo
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._on_source_choisie()
root.update_idletasks()
verifie(app.var_folder.get() == "C:/brutes_test_jalon47",
        "le chemin de dossier saisi survit au passage en composition (on "
        "cache, on ne détruit pas)")
verifie(app.var_compo_gains["G"].get() == "1.7",
        "les gains de composition saisis survivent au passage en dossier")
app.var_source.set("Simulée (démo)")
app._on_source_choisie()
root.update_idletasks()
ordre_apres = ordre_colonne(app)
verifie(ordre_avant == ordre_apres
        and ordre_apres[0].cget("text") == "Caméra"
        and ordre_apres[1].cget("text") == "Calibration",
        "l'ordre des cadres visibles est inchangé après les allers-retours "
        f"({[c.cget('text') for c in ordre_apres]})")

# ==================================== [6] cadence : choix commun inchangé
print("[6] cadence unique : la combobox pilote toujours le moteur (42/45)")
app.var_cadence.set("toutes les 15 s")
app._on_cadence()
verifie(app.cadence_lecture == 15,
        "« toutes les 15 s » → miroir worker = 15 (via l'unique combobox)")
app.var_cadence.set("dès réception")
app._on_cadence()
verifie(app.cadence_lecture == 0, "retour « dès réception » → 0")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)