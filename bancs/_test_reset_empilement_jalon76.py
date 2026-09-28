# -*- coding: utf-8 -*-
"""Test du jalon 76 (v2.41.0) — « Réinitialiser l'empilement » et la source de
FICHIERS qui suit l'interface.

Constat réel d'Alain (28/09/2026) : « quand j'ai fini avec une cible, je ne peux
pas enchaîner avec une autre en choisissant 1 ou des nouveaux dossiers et en
cliquant sur Réinitialiser l'empilement… quand je clique sur Démarrer ça empile
toujours la cible précédente », « il faudrait que le bouton réinitialiser
réinitialise vraiment » et « Démarrer, quand c'est accessible — ce qui n'est pas
toujours le cas ».

Vérifie, avec le VRAI worker et de VRAIES brutes FITS sur disque :

  [1] session « cible A » : les brutes du dossier sont empilées, et « ▶ Démarrer »
      ne lance qu'UN SEUL worker (un second démarrage inconditionnel en lançait
      DEUX : deux threads lisaient la même source et écrivaient le même
      empilement) ;
  [2] « ■ Arrêter » puis « Réinitialiser l'empilement » sur une NOUVELLE cible :
      remise à zéro immédiate côté interface (écran vidé, empilement vidé,
      boutons justes, source de fichiers refermée), et le worker consomme sa
      demande MÊME EN PAUSE — témoin : le compteur de session avance de 2
      (interface puis worker) sans que l'empilement reparte ;
  [3] « ▶ Démarrer » après la remise à zéro : c'est le dossier CHOISI ENSUITE
      qui est lu, et l'empilement ne contient que ses brutes (c'est LE défaut
      constaté : la caméra gardait son dossier et la mémoire des brutes déjà
      lues, donc « Démarrer » rejouait — ou n'empilait plus rien de — la cible
      précédente) ;
  [4] la PAUSE d'une source dossier ne consomme plus les brutes qui arrivent :
      elles restent sur le disque (« en attente ») et sont empilées à la
      reprise — avant, elles étaient lues puis jetées, marquées « traitées » ;
  [5] une caméra (source live) n'est JAMAIS refermée par la réinitialisation ;
  [6] changement de source : « ▶ Démarrer » redevient accessible (il restait
      grisé pour toute source sans connexion automatique) ;
  [7] `_source_fichiers_obsolete` : comparaison NORMALISÉE (barres obliques,
      barre finale, majuscules sous Windows) et détection des vrais changements
      (dossier, rôle, option « images déjà présentes »).

Nécessite un affichage. Exécution :
    python bancs/_test_reset_empilement_jalon76.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
from avastack.images import save_image
from avastack.cameras import FolderCamera, MultiFolderCamera, SimulatedCamera
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


_ETOILES = None


def champ(dx=0.0, dy=0.0, graine=0):
    """Brute mono synthétique : MÊME champ d'étoiles translaté (des frames
    sans rapport entre elles ne s'alignent pas — l'empilement resterait
    partiel), plus un bruit de fond par frame."""
    global _ETOILES
    h, w = 120, 160
    rng = np.random.default_rng(7)
    if _ETOILES is None:
        _ETOILES = [(rng.uniform(20, w - 20), rng.uniform(20, h - 20),
                     rng.uniform(0.4, 0.9)) for _ in range(12)]
    img = np.full((h, w), 0.05, np.float32)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    for (sx, sy, f) in _ETOILES:
        xx, yy = sx + dx, sy + dy
        img += (f * np.exp(-((x - xx) ** 2 + (y - yy) ** 2)
                           / (2.0 * 1.2 ** 2))).astype(np.float32)
    img += np.random.default_rng(100 + graine).normal(
        0, 0.004, img.shape).astype(np.float32)
    return img


def ecrire(dossier, nom, dx):
    chemin = os.path.join(dossier, nom)
    save_image(chemin, champ(dx, dx * 0.5, graine=int(dx)))
    return chemin


def attendre(cond, limite, quoi):
    """Attend qu'une condition devienne vraie (le worker travaille en fond)."""
    t0 = time.time()
    while time.time() - t0 < limite:
        if cond():
            return True
        time.sleep(0.05)
    return False


def threads_worker(app):
    """Threads (encore vivants) qui exécutent App._worker de CETTE App."""
    n = 0
    for th in threading.enumerate():
        cible = getattr(th, "_target", None)
        if (cible is not None
                and getattr(cible, "__name__", "") == "_worker"
                and getattr(cible, "__self__", None) is app):
            n += 1
    return n


ui.CONFIG = {}
ui.sauver_config = lambda d: None
ui.messagebox.showerror = lambda *a, **k: None      # jamais de dialogue bloquant
ui.messagebox.showinfo = lambda *a, **k: None

racine = tempfile.mkdtemp(prefix="avastack_banc76_")
dir_a = os.path.join(racine, "cible_A")
dir_b = os.path.join(racine, "cible_B")
os.makedirs(dir_a)
os.makedirs(dir_b)
for i in range(3):                    # cible A : 3 brutes du MÊME champ
    ecrire(dir_a, "a_%02d.fits" % i, float(i))
for i in range(2):                    # cible B : 2 brutes du même champ
    ecrire(dir_b, "b_%02d.fits" % i, float(i))
time.sleep(1.2)                       # taille stable + mtime > 0,5 s (dossier)

CFA_AVANT = images.CFA_MODE
images.CFA_MODE = "Non"               # brutes mono

root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.rejeter_flou = False              # test déterministe (pas de filtre flou)
app.ref_refresh = 0                   # pas de rafraîchissement de référence


class _Val:
    """Bouchon de variable Tk : `var.get()` est INTERDIT hors thread principal
    (« main thread is not in main loop ») — le worker lit var_wb/var_wb_force
    au moment de créer l'empilement (même bouchon que le banc jalon 19)."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app.var_wb = _Val(False)
app.var_wb_force = _Val(1.0)
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app._on_source_choisie()
app.var_folder.set(dir_a)
print("source : %s → %s" % (app.var_source.get(), app.var_folder.get()))

# ==================================== [1] session sur la cible A
print("[1] session « cible A » : les 3 brutes sont empilées par le worker")
app._start()
verifie(attendre(lambda: app.stacker is not None and app.stacker.n >= 3, 90,
                 "3 brutes de cible A"),
        "les 3 brutes de « cible A » sont empilées (n = %s)"
        % (app.stacker.n if app.stacker is not None else 0))
verifie(threads_worker(app) == 1,
        "UN SEUL worker lancé par « ▶ Démarrer » (compté : %d — le second "
        "démarrage inconditionnel en lançait DEUX, qui lisaient la même "
        "source et écrivaient le même empilement)" % threads_worker(app))
dossier_lu = os.path.dirname(app.camera.last_file or "")
verifie(dossier_lu == dir_a,
        "la brute lue vient de « cible A » (%s)" % dossier_lu)

# ==================================== [2] « ■ Arrêter » + « Réinitialiser »
print("[2] nouvelle cible choisie puis « Réinitialiser l'empilement »")
app._stop()
verifie(not app.empilement_on, "« ■ Arrêter » : empilement en pause")
app.var_folder.set(dir_b)                 # la NOUVELLE cible…
verifie(app._source_fichiers_obsolete(),
        "« cible B » choisie APRÈS la connexion → source jugée obsolète")
session_avant = app._session
app._reset_empilement()
verifie(app.stacker is None and app.reset_request,
        "remise à zéro IMMÉDIATE côté interface (empilement vidé + demande "
        "posée au worker)")
verifie(not app.empilement_on,
        "l'empilement reste en PAUSE (ce bouton ne démarre pas)")
verifie(app.btn_start.instate(["!disabled"])
        and not app.btn_stop.instate(["!disabled"]),
        "« ▶ Démarrer » redevient accessible, « ■ Arrêter » grisé")
verifie(app.camera is None and not app.btn_deconnect.instate(["!disabled"]),
        "la source de fichiers a été REFERMÉE (le dossier suivant sera "
        "vraiment ouvert au démarrage)")
verifie(app._last_disp is None and app.show_stack is None,
        "l'écran ne montre plus l'image de « cible A »")
verifie("cible_B" in app.lbl_status.cget("text"),
        "la ligne d'état annonce ce qui sera lu (« %s »)"
        % app.lbl_status.cget("text"))
verifie(attendre(lambda: not app.reset_request, 10, "worker"),
        "le WORKER consomme la remise à zéro MÊME EN PAUSE (avant, ce drapeau "
        "n'était lu qu'en traitant une frame : à l'arrêt, il ne réinitialisait "
        "RIEN)")
verifie(app._session >= session_avant + 2,
        "témoin de la DOUBLE remise à zéro (interface PUIS worker) : session "
        "%d → %d" % (session_avant, app._session))
verifie(not app.empilement_on,
        "après le passage du worker, l'empilement est toujours en pause")

# ==================================== [3] « ▶ Démarrer » sur la nouvelle cible
print("[3] « ▶ Démarrer » → c'est « cible B » qui est lue (et plus A)")
app._start()
verifie(attendre(lambda: app.stacker is not None and app.stacker.n >= 2, 90,
                 "2 brutes de cible B"),
        "les 2 brutes de « cible B » sont empilées (n = %s)"
        % (app.stacker.n if app.stacker is not None else 0))
verifie(app.stacker is not None and app.stacker.n == 2,
        "l'empilement ne contient QUE les brutes de la nouvelle cible "
        "(n = %d — avant le correctif, la caméra gardait son dossier et la "
        "mémoire des brutes déjà lues : rien de neuf n'était empilé)"
        % (app.stacker.n if app.stacker is not None else -1))
dossier_lu = os.path.dirname(app.camera.last_file or "")
verifie(dossier_lu == dir_b,
        "la brute lue vient de « cible B » (%s)" % dossier_lu)
verifie(threads_worker(app) == 1,
        "toujours UN SEUL worker après un second « ▶ Démarrer » (compté : %d)"
        % threads_worker(app))

# ==================================== [4] pause : aucune brute consommée
print("[4] pause sur une source dossier : les brutes restent sur le disque")
app._stop()
count_avant = app.camera.count
nouveau = ecrire(dir_b, "b_pause.fits", 3.0)
time.sleep(1.6)                     # le worker tourne (en pause) pendant ce temps
base = os.path.basename(nouveau)
verifie(base not in app.camera._processed,
        "la brute arrivée PENDANT la pause n'a pas été marquée « traitée » "
        "(elle reste empilable)")
verifie(app.camera.count == count_avant,
        "aucune lecture pendant la pause (compteur de la source resté à %d)"
        % app.camera.count)
verifie(app._brutes_en_attente() >= 1,
        "elle est vue « en attente » sur le disque (%d) — l'état affiché reste "
        "juste pendant la pause" % app._brutes_en_attente())
app._start()                        # reprise
verifie(attendre(lambda: app.stacker is not None and app.stacker.n >= 1, 90,
                 "brute de la pause"),
        "à la reprise, la brute de la pause EST empilée (n = %s)"
        % (app.stacker.n if app.stacker is not None else 0))
verifie(os.path.basename(app.camera.last_file or "") == base,
        "c'est bien elle qui a été lue (%s)" % base)

# ==================================== [5] caméra live : jamais refermée
print("[5] une caméra (source live) n'est jamais refermée par la remise à zéro")
app.running = False                 # le worker s'arrête : contrôle sans lui
if app.thread is not None and app.thread.is_alive():
    app.thread.join(timeout=3.0)
cam_sim = SimulatedCamera()
app.camera = cam_sim
app.cam_pilotee = None
app.empilement_on = True
app._reset_empilement()
verifie(app.camera is cam_sim,
        "la caméra reste connectée (le SDK interdit une réouverture dans le "
        "même process)")
verifie("reste connectée" in app.lbl_status.cget("text"),
        "la ligne d'état le DIT (« %s »)" % app.lbl_status.cget("text"))
verifie(app.btn_start.instate(["!disabled"]),
        "« ▶ Démarrer » est accessible après la remise à zéro")

# ==================================== [6] changement de source : bouton rendu
print("[6] changement de source : « ▶ Démarrer » redevient accessible")
app.camera = FolderCamera(dir_a)
app.btn_start.config(state="disabled")     # état laissé par une déconnexion
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._on_source_choisie()
verifie(app.camera is None,
        "la caméra de la source précédente a été déconnectée")
verifie(app.btn_start.instate(["!disabled"]),
        "« ▶ Démarrer » est réactivé (avant, pour toute source SANS connexion "
        "automatique, il restait grisé jusqu'à la fin de la session — constat "
        "d'Alain : « quand c'est accessible, ce qui n'est pas toujours le "
        "cas »)")

# ==================================== [7] comparaison des sources de fichiers
print("[7] _source_fichiers_obsolete : comparaison normalisée ou vrai changement")
app.camera = FolderCamera(dir_a)
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app.var_folder.set(dir_a)
app.var_process_existing.set(True)
verifie(not app._source_fichiers_obsolete(), "état initial → pas obsolète")
app.var_folder.set(dir_a.replace("\\", "/") + "/")
verifie(not app._source_fichiers_obsolete(),
        "même dossier écrit autrement (barres obliques, barre finale) → PAS "
        "obsolète (sinon une simple retouche du texte relancerait la lecture "
        "de tout le dossier)")
if os.name == "nt":                 # normalisation de casse (Windows)
    app.var_folder.set(dir_a.upper())
    verifie(not app._source_fichiers_obsolete(),
            "même dossier en MAJUSCULES → PAS obsolète")
app.var_folder.set(dir_b)
verifie(app._source_fichiers_obsolete(), "un AUTRE dossier → obsolète")
app.var_folder.set(dir_a)
app.var_process_existing.set(False)
verifie(app._source_fichiers_obsolete(),
        "option « images déjà présentes » changée → obsolète")
app.var_process_existing.set(True)
verifie(not app._source_fichiers_obsolete(), "retour à l'état initial → OK")
app.camera = MultiFolderCamera([("Ha", dir_a), ("O3", dir_b)])
for i in range(4):                  # lignes de rôle remplies comme à l'écran
    app.var_compo_roles[i].set("Ha" if i == 0 else "O3" if i == 1 else "")
    app.var_compo_dossiers[i].set(dir_a if i == 0 else dir_b if i == 1 else "")
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
verifie(not app._source_fichiers_obsolete(),
        "composition identique → pas obsolète")
app.var_compo_dossiers[1].set(dir_a)
verifie(app._source_fichiers_obsolete(),
        "un dossier de composition change → obsolète")

# ============================================================ fin
app.running = False
app.empilement_on = False
if app.thread is not None and app.thread.is_alive():
    app.thread.join(timeout=3.0)
app.archive.vider()
images.CFA_MODE = CFA_AVANT
root.destroy()
shutil.rmtree(racine, ignore_errors=True)
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
