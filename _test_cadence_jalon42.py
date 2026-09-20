# -*- coding: utf-8 -*-
"""Test du jalon 42 — cadence d'empilement en surveillance de dossier.

Demande d'Alain : avec la chaîne lourde live (gradient, débruitage) en
mode surveillance (dossier / multi-dossiers), chaque brute relançait la
résolution — le sablier tournait en PERMANENCE. Réglage : combobox
« Empiler les brutes » (dès réception / 5 s / 15 s / 30 s / 1 min / 5 min).
Les brutes qui arrivent pendant la fenêtre d'attente restent sur le disque
(aucune perte) puis sont drainées en rafale — un seul recalcul par rafale.

Vérifie, SANS worker ni fichiers réels (deques remplis à la main) :

  [1] porte de lecture : cadence « dès réception » → toujours autorisé ;
      fenêtre armée + brutes en attente → REFUS ; brutes en attente et
      fenêtre écoulée → autorisé ; aucune brute en attente → autorisé ;
  [2] armement : _armer_cadence() ne pose la fenêtre QUE si toutes les
      brutes détectées sont lues ;
  [3] portée : sources NON-dossier (caméra SDK muette) jamais throttlées ;
  [4] composition : `pending` du MultiFolderCamera = total des dossiers ;
      scanner() tourne sans lire ;
  [5] persistance : clé `cadence_lecture` écrite ; restauration tolérante
      (valeur inconnue → « dès réception »).

Nécessite un affichage. Exécution : python _test_cadence_jalon42.py
"""
import sys
import tempfile
import time
import tkinter as tk

import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.cameras import FolderCamera, MultiFolderCamera
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
tmp1 = tempfile.mkdtemp(prefix="avastack_j42_")
tmp2 = tempfile.mkdtemp(prefix="avastack_j42_")
tmp3 = tempfile.mkdtemp(prefix="avastack_j42_")

# ==================================== [1] porte de lecture
print("[1] porte de lecture (_autoriser_lecture)")
verifie(app.cadence_lecture == 0 and app.var_cadence.get() == "dès réception",
        "défaut : « dès réception » (comportement inchangé)")
app.camera = FolderCamera(tmp1)      # source dossier, file vide
app._mode_compo = False
verifie(app._autoriser_lecture(), "dès réception : lecture toujours autorisée")
app.var_cadence.set("toutes les 30 s")
app._on_cadence()
verifie(app.cadence_lecture == 30,
        "combobox « toutes les 30 s » → miroir worker = 30")
verifie(app._autoriser_lecture(),
        "fenêtre armée mais AUCUNE brute en attente : lecture autorisée "
        "(read() attendra les nouvelles)")
app.camera._pending.append("a.fits")     # une brute détectée, non lue
app._prochaine_lecture = time.monotonic() + 30.0
verifie(not app._autoriser_lecture(),
        "brute en attente + fenêtre pas écoulée : lecture REFUSÉE (elle "
        "reste sur le disque)")
app._prochaine_lecture = time.monotonic() - 1.0
verifie(app._autoriser_lecture(),
        "fenêtre écoulée : lecture autorisée (drain en rafale)")

# ==================================== [2] armement
print("[2] armement (_armer_cadence)")
app._prochaine_lecture = 0.0
app.camera._pending.append("b.fits")     # 2 brutes en attente (a + b)
app._armer_cadence()
verifie(app._prochaine_lecture == 0.0,
        "brutes EN ATTENTE : pas d'armement (le drain continue)")
app.camera._pending.clear()              # toutes lues
app._armer_cadence()
verifie(app._prochaine_lecture > time.monotonic() + 29.0,
        "toutes les brutes lues : fenêtre armée à +30 s")
app.camera._pending.append("c.fits")     # une NOUVELLE brute arrive
verifie(not app._autoriser_lecture(),
        "nouvelle brute pendant la fenêtre : lecture refusée (groupée)")
app.camera._pending.clear()

# ==================================== [3] sources non-dossier : jamais throttlées
print("[3] sources non-dossier (SDK, webcam…) jamais throttlées")


class _Muette:
    name = "muette"


app.camera = _Muette()
app._prochaine_lecture = time.monotonic() + 30.0
verifie(app._autoriser_lecture(),
        "caméra SDK (muette) : lecture TOUJOURS autorisée (la file du SDK "
        "ne doit pas s'accumuler en mémoire)")

# ==================================== [4] composition multi-dossiers
print("[4] composition : pending = total des dossiers, scanner() sans lecture")
mfc = MultiFolderCamera([("Ha", tmp2), ("O3", tmp3)])
app.camera = mfc
app._mode_compo = True
verifie(app._cadence_dossier(),
        "composition : la cadence S'APPLIQUE (source multi-dossiers)")
verifie(app._brutes_en_attente() == 0, "aucune brute en attente au départ")
mfc.cams[0]._pending.append("ha_001.fits")
mfc.cams[1]._pending.append("o3_001.fits")
mfc.cams[1]._pending.append("o3_002.fits")
verifie(app._brutes_en_attente() == 3,
        "pending composition = total des dossiers (1 + 2 = 3)")
app._prochaine_lecture = time.monotonic() + 30.0
verifie(not app._autoriser_lecture(),
        "composition : brutes en attente + fenêtre → lecture refusée")
mfc.scanner()                        # scan SANS lecture : rien ne change
verifie(app._brutes_en_attente() == 3,
        "scanner() : scanne tous les dossiers sans rien lire")
mfc.cams[0]._pending.clear()
mfc.cams[1]._pending.clear()
app._armer_cadence()
verifie(app._prochaine_lecture > time.monotonic() + 29.0,
        "composition : armement dès que TOUTES les brutes sont lues")
app._mode_compo = False

# ==================================== [5] persistance
print("[5] persistance : écriture + restauration tolérante")
app.camera = None
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
app.var_cadence.set("toutes les 15 s")
app._on_cadence()
app._sauver_config_app()
verifie(bool(sauvegardes) and sauvegardes[-1].get("cadence_lecture") == 15,
        "config : clé `cadence_lecture` écrite (15)")
ui.CONFIG = dict(sauvegardes[-1])
app2 = ui.App(root)
verifie(app2.cadence_lecture == 15 and app2.var_cadence.get() == "toutes les 15 s",
        "restauration : cadence 15 s rendue (case + miroir worker)")
ui.CONFIG = {"cadence_lecture": "inconnu"}
app3 = ui.App(root)
verifie(app3.cadence_lecture == 0 and app3.var_cadence.get() == "dès réception",
        "restauration tolérante : valeur invalide → « dès réception »")
ui.CONFIG = {}
app3.camera = None

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
