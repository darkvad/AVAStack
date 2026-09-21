# -*- coding: utf-8 -*-
"""Test de régression — jalon 52 : ergonomie du cadre « Caméra » (v2.21.10).

Deux demandes d'Alain (21/09/2026) :
  1. le choix de la source (caméra/dossier/…) doit être EN HAUT du cadre
     DÈS LE LANCEMENT — avant, il était sous les contrôles caméra et sa
     place dépendait de l'histoire de la session (choisir « Dossier » puis
     revenir à « Caméra » le laissait en haut, choix initial = en bas) ;
  2. « ⏏ Déconnecter » doit être visible en TOUTES circonstances — avant,
     side="right" de la ligne Détecter le poussait hors de la colonne dès
     qu'un long libellé de caméra détectée arrivait (il fallait élargir la
     colonne à la main). Corrigé : SA PROPRE ligne.

La vérification porte sur l'ordre de packing RÉEL de Tk (pack_slaves()),
pas sur des détails d'implémentation : si un jour le montage change,
l'ordre - ce que voit l'œil - reste le contrat.
"""
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, r"c:\Astro\AstroLiveStack")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import avastack.ui.app as ui

ECHECS = []


def verifie(cond, texte):
    print(("  OK    " if cond else "  ÉCHEC ") + texte)
    if not cond:
        ECHECS.append(texte)


root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()

print("[1] au lancement : choix de source EN HAUT du cadre « Caméra »")
ordre0 = app.cb_source.master.pack_slaves()
verifie(ordre0.index(app.cb_source) < ordre0.index(app.frm_ctrl_cam),
        "cb_source packé AVANT frm_ctrl_cam (ordre réel de Tk)")

print("[2] « ⏏ Déconnecter » sur sa propre ligne (toujours visible)")
verifie(getattr(app.btn_deconnect, "_ligne_propre", True)
        or app.btn_deconnect.master is not None,
        "btn_deconnect existe")
# la ligne « 🔎 Détecter » est un sous-cadre (bouton + libellé) ;
# btn_deconnect ne doit plus y vivre (avant : side="right" de cette
# ligne → poussé hors colonne par un long libellé)
freres = [w for w in app.frm_ctrl_cam.pack_slaves()]
idx = freres.index(app.btn_deconnect)
ligne_detect = freres[idx - 1] if idx > 0 else None
verifie(isinstance(ligne_detect, ttk.Frame)
        and app.btn_deconnect not in ligne_detect.pack_slaves()
        and app.lbl_detect.master is ligne_detect,
        "btn_deconnect SUR SA PROPRE ligne (pas à droite de « Détecter »)")
verifie(app.btn_deconnect in app.frm_ctrl_cam.pack_slaves(),
        "btn_deconnect est un enfant direct du cadre Caméra (ligne dédiée)")

print("[3] va-et-vient Dossier → Caméra : l'ordre NE BOUGE PAS")
val_dossier = [v for v in app.cb_source.cget("values")
               if v.startswith("Dossier")]
app.var_source.set(val_dossier[0] if val_dossier
                   else app.cb_source.cget("values")[-1])
app._maj_visibilite_cadres()
root.update_idletasks()
verifie(app.frm_ctrl_cam.winfo_manager() == "",
        "mode Dossier : contrôles caméra cachés (comportement inchangé)")
app.var_source.set(app.cb_source.cget("values")[0])
app._maj_visibilite_cadres()
root.update_idletasks()
ordre1 = app.cb_source.master.pack_slaves()
verifie(ordre1.index(app.cb_source) < ordre1.index(app.frm_ctrl_cam),
        "retour Caméra : le choix RESTE en haut, contrôles dessous")

root.destroy()
print()
if ECHECS:
    print(f"BILAN : {len(ECHECS)} ÉCHEC(S)")
    sys.exit(1)
print("JALON 52 : TOUT OK")