# -*- coding: utf-8 -*-
"""Test UI du jalon 6 — boutons « - »/« + » des curseurs (demande d'Alain).

Vérifie sur la fenêtre RÉELLE (Tkinter) :
  - chaque curseur a ses deux boutons ;
  - un clic « + » / « - » avance/recule d'UN pas du curseur (res) ;
  - le callback du curseur est bien appelé (disp.black suit, etc.) ;
  - les bornes frm/to sont respectées (clamp) ;
  - une valeur hors grille (glissée à la souris) est recalée sur la grille ;
  - le clic Tk RÉEL (event_generate) déclenche le pas, et la répétition
    s'annule au relâchement du bouton.

Nécessite un affichage. Exécution : python _test_sliders_jalon6.py
"""
import sys
import time
import tkinter as tk

import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


root = tk.Tk()
app = ui.App(root)
root.update_idletasks()

print("[1] Chaque curseur a ses boutons « - » et « + »")
curseurs = [app.scl_black, app.scl_white, app.scl_vl_logd]
verifie(all(hasattr(c, "_pas") and len(c._boutons) == 2
            and c._boutons[0].winfo_exists() and c._boutons[1].winfo_exists()
            for c in curseurs),
        "boutons présents et vivants sur les curseurs testés")

print("[2] Un clic « + » avance d'un pas et appelle le callback")
app.var_black.set(0.40)
app.scl_black.set(0.40)
avant = app.var_black.get()
app.scl_black._pas(1)
verifie(abs(app.var_black.get() - (avant + 0.005)) < 1e-9,
        f"black point : {avant} → {app.var_black.get()} (pas 0.005)")
verifie(abs(app.disp.black - app.var_black.get()) < 1e-9,
        "callback appliqué (disp.black suit)")

print("[3] Le bouton « - » recule d'un pas")
app.scl_black._pas(-1)
verifie(abs(app.var_black.get() - avant) < 1e-9, "retour à la valeur initiale")

print("[4] Valeur hors grille (glissée à la souris) recalée sur la grille")
app.var_black.set(0.4037)
app.scl_black._pas(-1)
verifie(abs(app.var_black.get() - 0.400) < 1e-9,
        f"0.4037 - 0.005 → {app.var_black.get()} (grille 0.005)")

print("[5] Bornes respectées (clamp au min et au max)")
for _ in range(1000):
    app.scl_black._pas(1)
verifie(app.var_black.get() == 1.0,
        f"plafond = 1.0 (obtenu {app.var_black.get()})")
for _ in range(3000):
    app.scl_black._pas(-1)
verifie(app.var_black.get() == 0.0,
        f"plancher = 0.0 (obtenu {app.var_black.get()})")

print("[6] Clic Tk RÉEL + annulation de la répétition au relâchement")
app.var_vl_logd.set(2.0)
app.scl_vl_logd.set(2.0)
b_plus = app.scl_vl_logd._boutons[1]
b_plus.event_generate("<ButtonPress-1>")
root.update_idletasks()
verifie(abs(app.var_vl_logd.get() - 2.05) < 1e-9,
        f"clic réel : logD 2.00 → {app.var_vl_logd.get():.2f} (pas 0.05)")
b_plus.event_generate("<ButtonRelease-1>")
t0 = time.perf_counter()
while time.perf_counter() - t0 < 0.6:    # laisse filer le délai (400/80 ms)
    root.update()
verifie(abs(app.var_vl_logd.get() - 2.05) < 1e-9,
        "répétition bien annulée au relâchement (valeur inchangée après 0.6 s)")

root.destroy()
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)