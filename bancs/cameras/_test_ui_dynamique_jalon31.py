# -*- coding: utf-8 -*-
"""Test du câblage dynamique (jalon 31) : fenêtre réelle + Capacites
injectées (valeurs du RELEVÉ RÉEL MiniCam8M d'Alain du 20/09/2026) →
l'UI doit se reconstruire aux bornes détectées, puis revenir aux défauts
après déconnexion simulée. Jeter après usage."""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import tkinter as tk

import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)
from avastack.cameras.capacites import Capacites

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


root = tk.Tk()
app = ui.App(root)
root.update_idletasks()

print("[1] Défauts avant connexion")
verifie(app.tec_plage is None and app._EXPO_DYN is None, "état neutre")
verifie(app.var_gain.get() == 30.0, "gain par défaut 30")

print("[2] Capacites du relevé réel (MiniCam8M) → adaptation")
cap = Capacites("QHY", modele="QHYminiCam8M")
cap.expo_us = (1.0, 3.6e9)          # 1 µs → 3600 s (relevé)
cap.gain = (0.0, 230.0)
cap.offset = (0.0, 255.0)
cap.tec = True
cap.tec_consigne = (-50.0, 50.0)
cap.temperature_lisible = True
cap.roue_slots = 8
cap.extras = {"6": {"min": 0, "max": 230, "step": 1, "val": 30},
              "7": {"min": 0, "max": 255, "step": 1, "val": 30},
              "8": {"min": 1, "max": 3.6e9, "step": 1, "val": 20000}}
app._adapter_ui_capacites(cap)
root.update_idletasks()

verifie(app._EXPO_DYN == (0.001, 3600000.0),
        "bornes expo dynamiques (1 µs → 3600 s, en ms)")
verifie(app.tec_plage == (-50.0, 50.0), "plage TEC réelle (-50 → 50)")
verifie(app._roue_ok, "roue détectée via capacités")
verifie(list(app.cb_filtre.cget("values")) == list(FILTRES := app._filtres_dispo)
        and len(FILTRES) == 8, "combobox roue = 8 slots réels")
g = app.sl_gain
verifie(abs(g.cget("from") - 0.0) < 1e-9 and abs(g.cget("to") - 230.0) < 1e-9,
        "curseur gain reconstruit 0 → 230")
verifie("230" in g._lbl_txt, "étiquette gain affiche les bornes réelles")
o = app.sl_offset
verifie(abs(o.cget("to") - 255.0) < 1e-9, "curseur offset 0 → 255")
verifie(0.0 <= app.var_gain.get() <= 230.0, "valeur gain clampée dans la plage")
app.var_tec_consigne.set("-100")
app._on_consigne_tec()
verifie(app._tec_demande == ("consigne", -50.0),
        "consigne TEC clampée à la borne réelle (-50)")
app.var_expo_saisie.set("3600 s")
app._valider_expo()
verifie(abs(app.var_expo.get() - 3_600_000.0) < 0.5,
        "saisie expo 3600 s acceptée (= 3 600 000 ms, plage native)")
app.capacites = cap          # (c'est _tick qui le fait en réel)
verifie(app.capacites is not None and app.capacites.gain == (0.0, 230.0),
        "capacités mémorisées")

print("[3] Déconnexion → retour aux défauts")
app._deconnecter_camera()
root.update_idletasks()
verifie(app.capacites is None and app._EXPO_DYN is None
        and app.tec_plage is None, "capacités vidées")
verifie(app.lbl_tec_lib.cget("text") == "Consigne °C :",
        "label TEC revenu au défaut")
verifie(len(app.cb_filtre.cget("values")) == len(
    __import__("avastack.cameras.base", fromlist=["x"]).FILTRES_ROUE),
    "roue revenue au jeu complet")

root.destroy()
print("BILAN :", "TOUTES LES VERIFICATIONS PASSENT" if ok else "ÉCHECS")
sys.exit(0 if ok else 1)
