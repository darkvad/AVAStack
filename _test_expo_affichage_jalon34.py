# -*- coding: utf-8 -*-
"""Test de l'affichage de l'exposition (jalon 34).

Retours RÉELS d'Alain, 20/09/2026 (setup 2, item 2d) — points 1 et 2 :
  [1] la case « Échelle longue » portait le « 900 s » CODÉ EN DUR → libellé
      GÉNÉRÉ ;
  [2] au-delà de 1000 s, l'affichage passait en notation scientifique
      (« 2e+03 s ») → désormais notation décimale (« 2 000 s », « 20 000 s »).
CORRECTIONS d'Alain après retests réels :
  - la case ne doit JAMAIS être masquée (v2.20.1) ;
  - coupure à 5 S pour TOUTES les caméras (v2.20.3) : DÉCOCHÉE le curseur
    va du min à 5 s, COCHÉE de 5 s au max réel (5 s = pivot commun, le
    libellé affiche « 5 s – borne max réelle »).
Vérifications headless (format) + fenêtre Tk réelle (libellé, bornes du
curseur selon l'état de la case, bascules auto à la saisie). Jeter après
usage."""
import sys

import tkinter as tk

sys.path.insert(0, r"c:\Astro\AstroLiveStack")
import avastack.ui.app as ui
from avastack.cameras.capacites import Capacites

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


print("[1] _fmt_expo : notation décimale lisible (jamais de « e+03 »)")
verifie(ui._fmt_expo(100.0) == "100 ms", "100 ms → « 100 ms »")
verifie(ui._fmt_expo(0.036) == "36 µs", "0,036 ms → « 36 µs »")
verifie(ui._fmt_expo(2000.0) == "2 s", "2 000 ms → « 2 s »")
verifie(ui._fmt_expo(5000.0) == "5 s", "5 000 ms → « 5 s »")
verifie(ui._fmt_expo(900000.0) == "900 s", "900 000 ms → « 900 s »")
v = ui._fmt_expo(2_000_000.0)          # la borne réelle POA/SVB : 2000 s
verifie(v == "2\u202f000 s", f"2 000 000 ms → « 2\u202f000 s » (obtenu « {v} »)")
verifie("e" not in v and "+" not in v, "aucune notation scientifique")
v = ui._fmt_expo(3_600_000.0)
verifie(v == "3\u202f600 s", f"3 600 000 ms → « 3\u202f600 s » (obtenu « {v} »)")
v = ui._fmt_expo(20_000_000.0)
verifie(v == "20\u202f000 s", f"20 000 000 ms → « 20\u202f000 s » (obtenu « {v} »)")

print("[2] Case « Échelle longue » : coupure à 5 s, toutes caméras (Alain)")
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
txt0 = app.chk_expo_longue.cget("text")
verifie(txt0 == "Échelle longue (5 s – 900 s)",
        f"défaut : « {txt0} » (libellé généré, coupure 5 s)")
verifie(app._expo_bornes() == (0.011, 5000.0),
        "case décochée : curseur min → 5 s (11 µs → 5 s)")
app.var_expo_longue.set(True)
verifie(app._expo_bornes() == (5000.0, 900000.0),
        "case cochée : curseur 5 s → 900 s")
app.var_expo_longue.set(False)
cap = Capacites("Player One", modele="Uranus-C Pro", couleur=True,
                bits=16, max_l=3856, max_h=2180, pixel_um=2.9)
cap.expo_us = (10.0, 2_000_000_000.0)   # relevé réel : 10 µs → 2000 s
app._adapter_ui_capacites(cap)
root.update_idletasks()
txt1 = app.chk_expo_longue.cget("text")
verifie(app.chk_expo_longue.winfo_manager() != "",
        "case TOUJOURS visible avec des bornes natives (retour d'Alain)")
verifie(txt1 == "Échelle longue (5 s – 2\u202f000 s)",
        f"libellé = coupure 5 s + borne max RÉELLE (« {txt1} »)")
verifie(app._expo_bornes() == (0.01, 5000.0),
        "case décochée : plage native min → 5 s (10 µs → 5 s)")
app.var_expo_longue.set(True)
verifie(app._expo_bornes() == (5000.0, 2_000_000.0),
        "case cochée : 5 s → 2000 s (longues poses, réglage fin)")
app._maj_expo(2_500_000.0)              # saisie 2500 s hors échelle courte
verifie(app.var_expo_longue.get() and abs(app.var_expo.get() - 2_000_000.0) < 1e-9,
        "saisie 2500 s avec case cochée : reste en longue, clampée 2000 s")
app.var_expo_saisie.set("500 ms")
app._valider_expo()
verifie(not app.var_expo_longue.get(),
        "saisie 500 ms : décoche automatiquement (retour min → 5 s)")
app.var_expo_saisie.set("30 s")
app._valider_expo()
verifie(app.var_expo_longue.get(),
        "saisie 30 s : coche automatiquement (côté 5 s → max)")
cap_fine = Capacites("QHY", modele="?")
cap_fine.expo_us = (1.0, 4000.0)        # plage native ENTIÈREMENT sous 5 s
app._adapter_ui_capacites(cap_fine)
root.update_idletasks()
verifie(app._expo_bornes() == (0.001, 4.0) and not app.var_expo_longue.get(),
        "plage native toute entière sous 5 s : la case reste sans effet")
app._deconnecter_camera()
root.update_idletasks()
verifie(app.chk_expo_longue.winfo_manager() != "",
        "déconnexion → case toujours visible")
txt2 = app.chk_expo_longue.cget("text")
verifie(txt2 == txt0, f"libellé régénéré au défaut (« {txt2} »)")

print("[3] Sans sonde : la case garde le libellé des échelles fixes")
app._adapter_ui_capacites(Capacites("SVBONY", modele="?"))   # sonde muette
root.update_idletasks()
verifie(app.chk_expo_longue.winfo_manager() != "" and
        app.chk_expo_longue.cget("text") == txt0,
        "caméra sans plage expo → case inchangée et visible")

root.destroy()
print("BILAN :", "TOUTES LES VERIFICATIONS PASSENT" if ok else "ÉCHECS")
sys.exit(0 if ok else 1)
