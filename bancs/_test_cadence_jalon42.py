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
      fenêtre ARMÉE → REFUS, MÊME sans brute détectée (jalon 43 : sinon
      le read() interne des caméras dossier court-circuitait la fenêtre —
      constat réel d'Alain en composition) ; fenêtre écoulée → autorisé ;
  [2] armement : _armer_cadence() ne pose la fenêtre QUE si toutes les
      brutes détectées sont lues ;
  [3] portée : sources NON-dossier (caméra SDK muette) jamais throttlées ;
  [4] composition : `pending` du MultiFolderCamera = total des dossiers ;
      scanner() tourne sans lire ;
  [5] persistance : clé `cadence_lecture` écrite ; restauration tolérante
      (valeur inconnue → « dès réception »).

Nécessite un affichage. Exécution : python bancs/_test_cadence_jalon42.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
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
app._prochaine_lecture = time.monotonic() + 30.0
# Jalon 43 (bug du jalon 42) : la fenêtre armée bloque TOUTE lecture, MÊME
# sans brute détectée — sinon le scan INTERNE de read() renvoyait la brute
# à l'instant où elle devenait complète (cadence inopérante en composition).
verifie(not app._autoriser_lecture(),
        "fenêtre armée, AUCUNE brute détectée : lecture REFUSÉE (sinon le "
        "read() interne court-circuitait la fenêtre)")
app.camera._pending.append("a.fits")     # une brute détectée, non lue
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
# Jalon 46 : plafond de rafale — dossiers déjà REMPLIS (acquisitions
# d'autres soirées) : le drain ne doit pas vider TOUT le backlog d'un coup.
app.camera._pending.append("d.fits")     # encore des brutes en attente
app._rafale_reste = 0                    # budget de la rafale épuisé
app._armer_cadence()
verifie(app._prochaine_lecture > time.monotonic() + 29.0
        and app._rafale_reste == app.RAFALE_MAX,
        "budget de rafale épuisé : fenêtre armée MÊME avec des brutes en "
        f"attente (plafond {app.RAFALE_MAX}), budget rechargé")

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
# Jalon 43 : en composition aussi, la fenêtre armée bloque TOUTE lecture
# (même sans brute détectée) — c'était le bug constaté par Alain.
verifie(not app._autoriser_lecture(),
        "composition : fenêtre armée, backlog vide → lecture REFUSÉE")
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
verifie(app2._rafale_reste == app2.RAFALE_MAX,
        "une App neuve démarre avec un budget de rafale complet "
        f"({app2.RAFALE_MAX})")
ui.CONFIG = {"cadence_lecture": "inconnu"}
app3 = ui.App(root)
verifie(app3.cadence_lecture == 0 and app3.var_cadence.get() == "dès réception",
        "restauration tolérante : valeur invalide → « dès réception »")
# ==================================== [6] état de la cadence affiché en direct
print("[6] étiquette d'état de la cadence (jalon 44)")
app.camera = FolderCamera(tmp1)
app._mode_compo = False
app.var_cadence.set("toutes les 30 s")
app._on_cadence()
app.camera._pending.append("x.fits")
app._prochaine_lecture = time.monotonic() + 12.0
app._maj_lbl_cadence()
coul_cd = str(app.lbl_cadence.cget("foreground"))
verifie("prochaine rafale dans" in app.lbl_cadence.cget("text")
        and "12" in app.lbl_cadence.cget("text")
        and "1 brute(s) en attente" in app.lbl_cadence.cget("text")
        and "#c98a00" in coul_cd,
        f"fenêtre armée : « {app.lbl_cadence.cget('text')} » (compte à "
        f"rebours visible)")
app.camera._pending.clear()
app._prochaine_lecture = time.monotonic() - 1.0
app._maj_lbl_cadence()
verifie("rafale en cours" in app.lbl_cadence.cget("text")
        and "#1d7f1d" in str(app.lbl_cadence.cget("foreground")),
        "fenêtre écoulée : « rafale en cours » (drain, en vert)")
app.var_cadence.set("dès réception")
app._on_cadence()
app._maj_lbl_cadence()
verifie(app.lbl_cadence.cget("text") == "—",
        "dès réception : étiquette au repos (« — »)")
app.var_cadence.set("toutes les 30 s")
app._on_cadence()
app.camera = _Muette()
app._maj_lbl_cadence()
verifie("sans objet" in app.lbl_cadence.cget("text"),
        "cadence posée sur une source non dossier : « sans objet »")
app.camera = None
app._maj_lbl_cadence()
verifie(app.lbl_cadence.cget("text") == "—",
        "aucune source connectée : étiquette au repos (« — », jalon 45 — "
        "ne plus afficher « sans objet » avant la connexion)")

# ==================================== [7] cadence commune aux deux modes
print("[7] jalon 47 : UN SEUL cadre « Cadence d'empilement » partagé")
verifie(len(app._cadence_cbs) == 1 and len(app._cadence_lbls) == 1,
        "une combobox + une étiquette (la duplication du jalon 45 est levée)")
verifie(app._cadence_cbs[0] is app.cb_cadence,
        "l'unique combobox reste exposée comme cb_cadence (compatibilité)")
verifie(app._cadence_lbls[0].master.cget("text") == "Cadence d'empilement",
        "l'unique couple vit dans le cadre « Cadence d'empilement »")
app.var_cadence.set("toutes les 5 min")
app._maj_lbl_cadence()
verifie("5 min" in app._cadence_cbs[0].get(),
        "le choix de cadence reste piloté par l'unique combobox")
app.var_cadence.set("dès réception")
app._on_cadence()

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
