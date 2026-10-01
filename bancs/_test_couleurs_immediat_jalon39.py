# -*- coding: utf-8 -*-
"""Test du jalon 39 — cases couleur live (SCNR / SCNR doux / démagenta)
réactives IMMÉDIATEMENT.

Constat réel d'Alain (20/09/2026) : cliquer ces cases ne changeait
l'affichage qu'à la prochaine frame empilée — ou pas du tout, jusqu'à
bouger par ex. le fond cible VeraLux. CAUSE : les callbacks des trois
cases mettaient à jour l'état du solveur (la clé changeait) mais
OUBLIAIENT d'appeler _refresh_preview() — la nouvelle chaîne n'était
soumise au solveur VeraLux qu'au prochain disp.process() (frame
suivante ou autre réglage).

Vérifie, SANS nouvel empilement ni autre réglage :

  [1] cocher SCNR → la chaîne est soumise au solveur VERA LUX par le
      callback lui-même, le résultat (clé = réglages courants) arrive
      et l'affichage le montre ;
  [2] décocher SCNR → idem (retour immédiat) ;
  [3] SCNR doux et démagenta → idem ;
  [4] _sync_vl_couleur_vue (appelée par _tick toutes les 30 ms) ne
      touche qu'à l'état : AUCUNE soumission en boucle, et elle suit la
      case dans les DEUX vues (« traitée » comme « pile » l'appliquent
      depuis la v2.48.1 : la chaîne couleur suit l'étirement).

Nécessite un affichage. Exécution : python bancs/_test_couleurs_immediat_jalon39.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"              # couleur d'essai composite, pas de CFA
import avastack.ui.app as ui
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Image COULEUR synthétique (fond vert excédentaire + tache magenta),
# comme le test du jalon 22 — la chaîne couleur y a un EFFET visible.
rng = np.random.default_rng(39)
H, W = 120, 160


def image_test():
    img = np.empty((H, W, 3), np.float32)
    img[..., 0] = 0.08
    img[..., 1] = 0.16 + rng.normal(0, 0.01, (H, W)).astype(np.float32)
    img[..., 2] = 0.08
    img[60:70, 20:30] = (0.25, 0.05, 0.25)
    return img


ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
d = app.disp
d.stretch = "veralux"                # moteur VeraLux (cases du panneau)
app.var_view.set("pile")             # vue « empilement » (cases actives)
app._sync_vl_couleur_vue()           # état de départ cohérent
verifie(not d.vl_scnr and not d.vl_scnr_doux and not d.vl_demagenta,
        "état de départ : les trois cases couleur sont désactivées")

img = image_test()
app.last_show = img                  # aperçu courant (comme en session)


def attendre_resultat(d_, img_, declencher=False):
    """Attend la fin du calcul, puis rend le résultat visible comme le fait
    le _tick réel (vl_new). `declencher=False` : le calcul a été soumis par
    le callback testé lui-même (c'est ce qu'on prouve — aucun process()
    additionnel AVANT l'attente) ; `declencher=True` : un process() est fait
    AVANT l'attente, comme le ferait un tick ou une frame entrante."""
    if declencher:
        d_.process(img_, live=False)
    t0 = time.time()
    while (d_._vl_pending or d_._vl_job is not None) and time.time() - t0 < 60:
        time.sleep(0.01)
    d_.process(img_, live=False)     # rendu du résultat terminé (comme _tick)
    app._refresh_preview()
    root.update_idletasks()
    if d_._vl_result is None or d_._vl_result[0] != d_._vl_params():
        return False
    # L'affichage montre bien le résultat : en test, gamma/saturation sont
    # neutres (1.0) — process() ne fait que clipper PUIS convertir en uint8
    # (cf. _gamma_saturation et la fin de process()).
    ref = (np.clip(d_._vl_result[1], 0.0, 1.0) * 255).astype(np.uint8)
    return bool(np.array_equal(app._last_disp, ref))


def case_immediat(var, attr, nom):
    """Coche la case, appelle SEULEMENT son callback : la résolution doit
    se faire sans frame ni autre réglage (c'était le bug du jalon 39),
    puis décoche et vérifie le retour immédiat."""
    rappel = {"vl_scnr": app._on_vl_scnr,
              "vl_scnr_doux": app._on_vl_scnr_doux,
              "vl_demagenta": app._on_vl_demagenta,
              "vl_neutre": app._on_vl_neutre}[attr]
    var.set(True)
    t0 = time.time()
    rappel()
    instant = time.time() - t0
    obtenu = attendre_resultat(d, img)
    verifie(obtenu and instant < 2.0,
            f"{nom} cochée : chaîne soumise immédiatement et résultat "
            f"affiché ({instant * 1000:.0f} ms au callback)")
    var.set(False)
    rappel()
    verifie(attendre_resultat(d, img),
            f"{nom} décochée : retour immédiat (sans frame ni réglage)")


# ==================================== [1..3] cases → résolution immédiate
print("[1] SCNR cochée → soumission immédiate au solveur VeraLux")
case_immediat(app.var_vl_scnr, "vl_scnr", "SCNR")
print("[2] SCNR doux → idem")
case_immediat(app.var_vl_scnr_doux, "vl_scnr_doux", "SCNR doux")
print("[3] démagenta → idem")
case_immediat(app.var_vl_demagenta, "vl_demagenta", "Démagenta")
print("[3bis] neutralisation du fond (v2.36.1) → idem")
# Constat d'Alain (25/09/2026) : « la case Neutraliser la couleur du fond ne
# provoque pas une visualisation immédiate quand on la coche et la décoche,
# contrairement aux autres corrections de couleur. Ça semble attendre une
# nouvelle frame. » — même bug que le jalon 39 (le callback n'appelait pas
# _refresh_preview), même correction, et ce banc le verrouille désormais.
case_immediat(app.var_vl_neutre, "vl_neutre", "Neutralisation du fond")

# ==================================== [4] _sync_vl_couleur_vue : état SEUL
print("[4] _sync_vl_couleur_vue : aucune soumission en boucle, suit la vue")
app.var_vl_scnr.set(True)
app._sync_vl_couleur_vue()
verifie(attendre_resultat(d, img, declencher=True),  # fige un résultat à clé courante
        "état posé : résultat résolu, clé à jour")
cle = d._vl_params()
for _ in range(50):                  # ce que ferait _tick pendant 1,5 s
    app._sync_vl_couleur_vue()
verifie(not d._vl_pending and d._vl_job is None
        and d._vl_result[0] == cle,
        "50 appels sans changement : aucun calcul relancé (état seul)")
# Changement d'état via la sync SEULE : l'état suit la case, mais AUCUN rendu
# ni soumission — c'est la case/la vue qui rafraîchit. v2.48.1 : la chaîne
# couleur suit l'étirement et vaut pour LES DEUX VUES — elle n'est donc plus
# coupée en vue « traitée ».
app.var_view.set("traitée")
app._sync_vl_couleur_vue()
verifie(d.vl_scnr is True and not d._vl_pending and d._vl_job is None,
        "vue « traitée » : SCNR ACTIF (chaîne couleur après étirement), sans "
        "calcul lancé ici")
app.var_view.set("pile")
app._sync_vl_couleur_vue()
verifie(d.vl_scnr is True and not d._vl_pending and d._vl_job is None,
        "vue « pile » : toujours actif, sans calcul lancé ici")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
