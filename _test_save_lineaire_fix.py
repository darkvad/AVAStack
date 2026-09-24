# -*- coding: utf-8 -*-
"""Test headless de la correction v2.3.2 — sauvegarde linéaire sans frames.

Constat Alain (16/09/2026) : « 💾 Enregistrer l'empilement (linéaire)… » ne
faisait RIEN (aucun fichier, aucun message) dès que plus aucune brute
n'arrivait : la demande (save_request) n'était consommée par le thread
d'acquisition qu'APRÈS l'empilement d'une NOUVELLE frame.

Ce test reproduit le scénario : un worker dont la caméra ne renvoie plus
rien (dossier terminé) + un empilement existant + une demande de sauvegarde
posée → le fichier DOIT être écrit et saved_path renseigné, SANS nouvelles
frames. Vérifie aussi le cas d'erreur (chemin impossible) et que la demande
posée SANS empilement reste simplement en attente (comportement conservé).

Exécution : python _test_save_lineaire_fix.py
"""
import os
import sys
import tempfile
import threading
import time
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


class CameraMuette:
    """Caméra factice : ne renvoie PLUS aucune frame (dossier terminé)."""
    name = "muette"

    def read(self):
        return None


root = tk.Tk()
root.withdraw()
app = ui.App(root)

print("[1] Empilement existant, caméra muette, demande de sauvegarde")
app.camera = CameraMuette()
app.running = True
stacker = LiveStacker((48, 64), k=3, method="kappa", window=8)
stacker.add(np.full((48, 64), 0.25, np.float32))
app.stacker = stacker
app.save_request = None       # état propre

tmp = tempfile.mkdtemp(prefix="avastack_test_")
chemin = os.path.join(tmp, "pile.fits")
app.save_request = chemin

# UNE itération du worker : on ne lance pas la boucle while, on exécute
# son corps via un fil jusqu'à la 1re sauvegarde — plus simple : on lance
# le thread worker pour de vrai et on surveille saved_path.
th = threading.Thread(target=app._worker, daemon=True)
th.start()
t0 = time.time()
while time.time() - t0 < 5.0 and app.saved_path is None:
    time.sleep(0.05)
verifie(os.path.isfile(chemin), "fichier écrit SANS aucune nouvelle frame")
verifie(isinstance(app.saved_path, str)
        and not app.saved_path.startswith("ERREUR"),
        "saved_path renseigné (succès)")
verifie(app.save_request is None, "demande consommée (une seule fois)")
# le worker tourne en boucle : on l'arrête proprement
app.running = False
th.join(timeout=3.0)

print("[2] Chemin impossible → ERREUR signalée (et non silencieuse)")
app.running = True
app.stacker = stacker
app.saved_path = None
mauvais = os.path.join(tmp, "inexistant", "sous", "dossier.fits")
app.save_request = mauvais
th2 = threading.Thread(target=app._worker, daemon=True)
th2.start()
t0 = time.time()
while time.time() - t0 < 5.0 and app.saved_path is None:
    time.sleep(0.05)
verifie(isinstance(app.saved_path, str)
        and app.saved_path.startswith("ERREUR"),
        "échec d'écriture → saved_path = ERREUR (messagebox de _tick)")
app.running = False
th2.join(timeout=3.0)

print("[3] Demande posée sans empilement → reste en attente (inchangé)")
app.saved_path = None
app.stacker = None
app.save_request = os.path.join(tmp, "jamais.fits")
th3 = threading.Thread(target=app._worker, daemon=True)
th3.start()
time.sleep(0.6)
verifie(app.save_request is not None and app.saved_path is None,
        "sans empilement : demande conservée, rien d'écrit, rien de planté")
app.running = False
th3.join(timeout=3.0)

import shutil
shutil.rmtree(tmp, ignore_errors=True)
root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
