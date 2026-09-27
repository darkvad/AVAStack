# -*- coding: utf-8 -*-
"""Tests jalon 19, Phase 1 — MultiFolderCamera (multi-dossiers, un par rôle).

Vérifie sur de VRAIS dossiers temporaires (fichiers PNG 16 bits écrits
via save_image, comme le ferait N.I.N.A.) :
  - read() → (image, rôle), rotation round-robin équitable ;
  - toutes les frames de tous les dossiers finissent par sortir ;
  - stats()/count/failed par rôle ;
  - process_existing=False ignore l'existant ;
  - un dossier inexistant → open() lève ET referme les déjà-ouverts ;
  - une frame qui arrive PENDANT la session est bien ramassée.

Exécution : python bancs/_test_multifolder_jalon19.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import tempfile
import time

import numpy as np

import avastack.images as images
from avastack.cameras.multifolder import MultiFolderCamera
from avastack.images import save_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True
_CFA_AVANT = images.CFA_MODE
images.CFA_MODE = "Non"            # brutes mono dans les tests (pas de CFA)


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def ecrire(dossier, nom, val, h=12, w=16):
    """Écrit une frame PNG 16 bits complète (mtime passé de 2 s : « ancien »)."""
    p = os.path.join(dossier, nom)
    save_image(p, np.full((h, w), val, np.float32))
    t = time.time() - 2.0
    os.utime(p, (t, t))            # complet = taille stable + mtime > 0,5 s
    return p


racine = tempfile.mkdtemp(prefix="avastack_mfc_")
d_ha = os.path.join(racine, "Ha")
d_o3 = os.path.join(racine, "O3")
os.makedirs(d_ha)
os.makedirs(d_o3)

print("[1] read() → (image, rôle), dans l'ordre, rotation round-robin")
ecrire(d_ha, "ha_1.png", 0.10)
ecrire(d_o3, "o3_1.png", 0.20)
cam = MultiFolderCamera([("Ha", d_ha), ("O3", d_o3)], poll=0.05)
verifie(cam.name == "Composition : Ha + O3", f"nom : {cam.name}")
cam.open()
r1 = cam.read(timeout=3.0)
verifie(r1 is not None and len(r1) == 2 and r1[1] == "Ha"
        and r1[0].shape == (12, 16) and abs(float(np.mean(r1[0])) - 0.10) < 1e-3,
        f"1re frame : rôle {r1[1] if r1 else '?'} (attendu Ha), contenu OK")
r2 = cam.read(timeout=3.0)
verifie(r2 is not None and r2[1] == "O3" and abs(float(np.mean(r2[0])) - 0.20) < 1e-6,
        f"2e frame : rôle {r2[1] if r2 else '?'} (attendu O3)")
t0 = time.time()
r3 = cam.read(timeout=0.6)
verifie(r3 is None and time.time() - t0 < 1.5,
        "plus rien à lire → None (et vite, pas bloqué par un dossier vide)")

print("[2] Équité : toutes les frames de tous les dossiers sortent")
for i in range(2, 5):                       # 3 nouvelles dans chaque dossier
    ecrire(d_ha, f"ha_{i}.png", 0.10 + i / 100)
    ecrire(d_o3, f"o3_{i}.png", 0.20 + i / 100)
roles, n_max = [], 20
while len(roles) < n_max:
    r = cam.read(timeout=1.5)
    if r is None:
        break
    roles.append(r[1])
verifie(sorted(roles) == ["Ha", "Ha", "Ha", "O3", "O3", "O3"],
        f"6 frames sorties, 3 par rôle ({sorted(roles)})")
st = cam.stats()
verifie(st["Ha"]["count"] == 4 and st["O3"]["count"] == 4
        and st["Ha"]["failed"] == 0 and st["O3"]["failed"] == 0,
        f"stats par rôle : {st}")
verifie(cam.count == 8 and cam.failed == 0,
        f"totaux agrégés : count={cam.count}, failed={cam.failed}")
verifie(cam.last_file.endswith(".png"), f"dernier fichier : {cam.last_file}")
cam.close()

print("[3] process_existing=False : l'existant est ignoré")
ecrire(d_ha, "avant.png", 0.5)
ecrire(d_o3, "avant.png", 0.5)
cam2 = MultiFolderCamera([("Ha", d_ha), ("O3", d_o3)],
                         process_existing=False, poll=0.05)
cam2.open()
verifie(cam2.read(timeout=0.6) is None,
        "aucune frame déjà présente n'est relue")
ecrire(d_ha, "pendant.png", 0.7)            # arrive APRÈS l'ouverture
r = cam2.read(timeout=3.0)
verifie(r is not None and r[1] == "Ha" and abs(float(np.mean(r[0])) - 0.7) < 1e-3,
        "une frame qui arrive PENDANT la session est bien ramassée")
cam2.close()

print("[4] Dossier inexistant → open() lève et referme les déjà-ouverts")
cam3 = MultiFolderCamera([("Ha", d_ha), ("O3", os.path.join(racine, "absent"))],
                         poll=0.05)
leve = False
try:
    cam3.open()
except RuntimeError:
    leve = True
verifie(leve, "RuntimeError levée (Dossier introuvable)")
verifie(cam3.read(timeout=0.1) is None and not cam3._running,
        "caméra inertie après l'échec (read → None, _running False)")

cam.close()
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
images.CFA_MODE = _CFA_AVANT
sys.exit(0 if ok else 1)