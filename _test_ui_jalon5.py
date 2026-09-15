# -*- coding: utf-8 -*-
"""Test UI du jalon 5 (retours d'Alain sur la 1re passe).

Vérifie sur la fenêtre RÉELLE (Tkinter) :
  - les réglages STF sont MASQUÉS en mode VeraLux (et remis en mode STF) ;
  - gamma/saturation restent visibles dans les deux modes ;
  - la combobox « Profil capteur » existe et alimente disp.vl_profil ;
  - GraXpert live ne s'applique qu'en vue « empilement » : passer en vue
    « traitée » désactive le passage GX live (sinon DEUXIÈME traitement),
    et il revient automatiquement en vue « empilement ».

Nécessite un affichage. Exécution : python _test_ui_jalon5.py
"""
import sys
import tkinter as tk

import avastack.ui.app as ui
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def est_packe(w):
    try:
        w.pack_info()
        return True
    except tk.TclError:
        return False


root = tk.Tk()
app = ui.App(root)
root.update_idletasks()

print("[1] État initial (moteur STF)")
verifie(est_packe(app.frm_stf), "réglages STF visibles")
verifie(not est_packe(app.frm_veralux), "cadre VeraLux caché")
verifie(est_packe(app.frm_communs), "gamma/saturation visibles")

print("[2] Mode VeraLux → STF masqué")
app.var_moteur.set("VeraLux")
app._on_moteur()
root.update_idletasks()
verifie(app.disp.stretch == "veralux", "moteur sélectionné = veralux")
verifie(not est_packe(app.frm_stf), "réglages STF masqués (plus de case cochée à l'écran)")
verifie(est_packe(app.frm_veralux), "cadre VeraLux visible")
verifie(est_packe(app.frm_communs), "gamma/saturation toujours visibles")
verifie(len(app.cb_vl_profil["values"]) > 0 and vl.moteur_disponible(),
        f"combobox profil capteur remplie ({len(app.cb_vl_profil['values'])} profils)")
if len(app.cb_vl_profil["values"]) > 1:
    profil = app.cb_vl_profil["values"][1]
    app.var_vl_profil.set(profil)
    app._on_vl_profil()
    verifie(app.disp.vl_profil == profil, f"profil capteur appliqué ({profil})")

print("[3] Retour STF → réglages remis à leur place")
app.var_moteur.set("STF")
app._on_moteur()
root.update_idletasks()
verifie(app.disp.stretch == "stf", "moteur sélectionné = stf")
verifie(est_packe(app.frm_stf) and not est_packe(app.frm_veralux),
        "réglages STF revenus, cadre VeraLux caché")

print("[4] GraXpert live : vue « empilement » seulement")
app.var_cmd_graxpert.set(f'"{__import__("sys").executable}" '
                         f'"{{input}}" -o "{{output}}"')
app.var_vl_graxpert.set(True)
app._on_vl_graxpert()
verifie(app.disp.vl_graxpert is True, "vue empilement : GX live actif")
app.var_view.set("traitée")
app._on_view()
root.update_idletasks()
verifie(app.disp.vl_graxpert is False,
        "vue traitée : GX live DÉSACTIVÉ (pas de 2e traitement)")
app.var_view.set("pile")
app._on_view()
root.update_idletasks()
verifie(app.disp.vl_graxpert is True, "retour vue empilement : GX live réactivé")
app.var_vl_graxpert.set(False)
app._on_vl_graxpert()
verifie(app.disp.vl_graxpert is False, "case décochée : GX live inactif")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
