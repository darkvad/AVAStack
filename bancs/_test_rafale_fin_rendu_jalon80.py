# -*- coding: utf-8 -*-
"""Test du jalon 80 (v2.44.0) — RENDU DÉCLENCHÉ EN FIN DE RAFALE.

Demande d'Alain (29/09/2026) : « je lance sur des dossiers avec 50 brutes par
couche : on en lit 10, on les stacke, et seulement là on lance un rendu ? ».
Diagnostic consigné : le déclenchement du solveur tombait sur la PREMIÈRE brute
de la rafale — une passe ENTIÈRE de la chaîne lourde (GraXpert live par couche,
~10 s chez lui, dont 92 % de GraXpert) calculée sur une pile à 1 brute, puis une
SECONDE passe sur la pile de fin de rafale : ~70 % de panneau occupé par cycle,
dont une passe entière perdue (et une image bruitée affichée pendant ce temps).

Correctif : en rafale de DOSSIER (et composition), le rendu est DIFFÉRÉ à la fin
de la rafale — il part quand plus aucun empilement n'est signalé pendant
`RAFALE_QUIET_S` (0,35 s), une seule fois, sur la pile la plus PROFONDE, avec
une BORNE (`RAFALE_MAX` brutes empilées depuis le dernier rendu) pour qu'un
dossier pré-rempli ne le retarde jamais indéfiniment. **Aucun pixel ne change** :
seule la DATE de déclenchement change (même chaîne, même pile).

Vérifie, d'abord sur la LOGIQUE de déclenchement (messages fabriqués, `_tick`
RÉELLEMENT pompé par `root.update()`), puis BOUT EN BOUT (vrai worker, vraies
brutes FITS sur disque) :

  [1] rafale de dossier : AUCUN rendu pendant la rafale, UN SEUL à la fin, sur
      la pile la plus profonde ;
  [2] borne : rafale plus longue que RAFALE_MAX → un rendu À LA BORNE (latence
      jamais illimitée) PUIS un rendu en fin de rafale (rien n'est perdu) ;
  [3] caméra / source non-dossier : STRICTEMENT inchangé (un rendu par
      empilement, sans attendre le silence) ;
  [4] messages rapprochés : le rendu différé part une seule fois, sur le
      DERNIER empilement (« dernier gagnant ») ;
  [5] remise à zéro (`_reinit_etat_session`) : aucun rendu fantôme de la rafale
      précédente ;
  [6] bout en bout, 6 brutes lues en rafale : UN SEUL déclenchement de rendu
      (avec `RAFALE_QUIET_S = 0`, l'ancien comportement, il y en avait un PAR
      brute).

Nécessite un affichage. Exécution :
    python bancs/_test_rafale_fin_rendu_jalon80.py
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
import time
import tkinter as tk
import traceback

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
from avastack.images import save_image
from avastack.cameras import FolderCamera
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


class _Val:
    """Bouchon de variable Tk : `var.get()` est INTERDIT hors thread principal
    (« main thread is not in main loop ») — le worker lit ces variables au moment
    de créer l'empilement (même bouchon que les bancs jalons 19/76)."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


def pomper(secondes):
    """Fait vivre `_tick` (la chaîne `after(30, _tick)` du App) pendant
    `secondes` : sans mainloop, `root.update()` sert les rappels dus."""
    t0 = time.time()
    while time.time() - t0 < secondes:
        root.update()
        time.sleep(0.005)


def attendre(cond, limite=60.0):
    """Pompe Tk jusqu'à ce que la condition soit vraie (worker en fond)."""
    t0 = time.time()
    while time.time() - t0 < limite:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def message(frames):
    """Message de la file du worker : `(image affichable, état)` — MÊMES clés que
    le vrai worker (`_update_status` lit `frames`, `rejets`, `bad`, `cam`, `fps`)."""
    montre = np.zeros((16, 20), np.float32)
    st = dict(frames=frames, rejets=0, bad=0, floues=0, fps=1.0, cam="banc",
              file="", pending=0, failed=0, align="—", seeing=None,
              seeing_msg="", archive=0, archive_err="", compo=None,
              restack="", restack_n=0, astro="", photo="", spcc="")
    return (montre, st)


def compter_rendus(app, detail=None):
    """Installe un compteur de déclenchements de rendu (c'est LUI qui lance la
    chaîne lourde). Rend la liste des `_vl_frames` vus à chaque déclenchement ;
    `detail` (liste) reçoit l'origine de chaque appel (diagnostic)."""
    vus = []
    vrai = app.disp.notify_new_stack

    def _compte():
        vus.append(app._vl_frames)
        if detail is not None:
            detail.append(" ← ".join(l.strip() for l in
                                     traceback.format_stack()[-4:-1]))
        vrai()

    app.disp.notify_new_stack = _compte
    return vus


def champ(dx=0.0, dy=0.0, graine=0):
    """Brute mono synthétique : MÊME champ d'étoiles translaté, bruit par frame."""
    global _ETOILES
    h, w = 120, 160
    if _ETOILES is None:
        rng = np.random.default_rng(11)
        _ETOILES = [(rng.uniform(20, w - 20), rng.uniform(20, h - 20),
                     rng.uniform(0.4, 0.9)) for _ in range(12)]
    img = np.full((h, w), 0.05, np.float32)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    for (sx, sy, f) in _ETOILES:
        xx, yy = sx + dx, sy + dy
        img += (f * np.exp(-((x - xx) ** 2 + (y - yy) ** 2)
                           / (2.0 * 1.2 ** 2))).astype(np.float32)
    img += np.random.default_rng(200 + graine).normal(
        0, 0.004, img.shape).astype(np.float32)
    return img


_ETOILES = None
images.CFA_MODE = "Non"               # brutes mono

ui.CONFIG = {}
ui.sauver_config = lambda d: None

root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.var_view.set("traitée")           # pas de rendu d'aperçu ici : ce banc teste
                                      # le DÉCLENCHEMENT, pas l'affichage
vides = []
vides.append(tempfile.mkdtemp(prefix="avastack_banc80_vide_"))
app.camera = FolderCamera(vides[0])   # source dossier → `_cadence_dossier()` vrai
origine = []                          # diagnostic : d'où vient chaque rendu
rendus = compter_rendus(app, origine)
pomper(0.3)                           # le 1er `_tick` déclenche UN rendu (gains de
                                      # composition, jalon 55) : hors sujet du banc
rendus.clear()
origine.clear()

# ==================================== [1] rafale de dossier
print("[1] rafale de dossier : aucun rendu pendant, UN SEUL en fin de rafale")
for f in (1, 2, 3, 4, 5, 6):          # 6 brutes « lues en rafale » (40 ms d'écart)
    app.q.put_nowait(message(f))
    pomper(0.04)
verifie(rendus == [],
        "aucun rendu pendant la rafale (6 empilements annoncés, 0 déclenchement "
        "— origine : %s)" % (origine or ["aucun rendu"]))
pomper(app.RAFALE_QUIET_S + 0.3)
verifie(rendus == [6],
        "UN SEUL rendu, après le silence, sur la pile la plus PROFONDE "
        "(déclenché sur %s frames)" % (rendus or ["aucun"]))

# ==================================== [2] borne de rafale
print("[2] rafale plus longue que RAFALE_MAX : borne PUIS fin de rafale")
rendus.clear()
app._vl_frames = None
app._rendu_differ = None
for f in range(1, app.RAFALE_MAX + 5):    # 14 brutes d'affilée
    app.q.put_nowait(message(f))
    pomper(0.04)
verifie(rendus == [app.RAFALE_MAX],
        "rendu À LA BORNE (%d brutes empilées depuis le dernier rendu) : la "
        "latence d'affichage reste bornée (déclenché sur %s)"
        % (app.RAFALE_MAX, rendus or ["aucun"]))
pomper(app.RAFALE_QUIET_S + 0.3)
verifie(rendus == [app.RAFALE_MAX, app.RAFALE_MAX + 4],
        "PUIS un rendu en fin de rafale, sur la pile complète : rien n'est perdu "
        "(%s)" % rendus)


# ==================================== [3] caméra : inchangé
print("[3] source non-dossier (caméra) : un rendu par empilement, inchangé")


class _CameraMuette:
    pending = 0


rendus.clear()
app._vl_frames = None
app._rendu_differ = None
app.camera = _CameraMuette()
for f in (1, 2, 3):
    app.q.put_nowait(message(f))
    pomper(0.04)
verifie(rendus == [1, 2, 3],
        "caméra : un déclenchement PAR empilement, sans attendre le silence (%s)"
        % rendus)

# ==================================== [4] dernier gagnant
print("[4] rendu différé : « dernier gagnant », une seule fois")
app.camera = FolderCamera(vides[0])
rendus.clear()
app._vl_frames = None
app._rendu_differ = None
for f in (1, 2, 3):
    app.q.put_nowait(message(f))
    pomper(0.04)
app.q.put_nowait(message(4))
app.q.put_nowait(message(5))
pomper(app.RAFALE_QUIET_S + 0.3)
verifie(rendus == [5],
        "un seul rendu, sur le DERNIER empilement (5), pas un par empilement (%s)"
        % rendus)

# ==================================== [5] remise à zéro
print("[5] remise à zéro : aucun rendu fantôme")
rendus.clear()
for f in (1, 2, 3):
    app.q.put_nowait(message(f))
    pomper(0.04)
app._reinit_etat_session()
pomper(app.RAFALE_QUIET_S + 0.3)
verifie(rendus == [] and app._rendu_differ is None,
        "« nouvelle session » : le rendu différé de la rafale précédente est "
        "abandonné (aucun rendu fantôme, drapeau vidé)")

# ==================================== [6] bout en bout (vrai worker)
print("[6] bout en bout : 6 brutes lues en rafale → UN SEUL rendu")
root_ref = [root]


def scenario(quiet):
    """Vraies brutes FITS + vrai worker ; rend (déclenchements, frames empilées,
    rafale terminée)."""
    dossier = tempfile.mkdtemp(prefix="avastack_banc80_")
    vides.append(dossier)
    for i in range(6):
        save_image(os.path.join(dossier, "b_%02d.fits" % i),
                   champ(float(i), float(i) * 0.5, graine=i))
    time.sleep(1.2)                   # taille stable + mtime (dossier surveillé)
    r2 = tk.Tk()
    r2.withdraw()
    a2 = ui.App(r2)
    a2.var_view.set("traitée")
    a2.var_wb = _Val(False)
    a2.var_wb_force = _Val(1.0)
    a2.rejeter_flou = False           # pas de filtre flou : test déterministe
    a2.ref_refresh = 0
    a2.RAFALE_QUIET_S = quiet         # 0 → comportement d'AVANT le jalon 80
    a2.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
    a2._on_source_choisie()
    a2.var_folder.set(dossier)
    a2.var_cadence.set("toutes les 30 s")
    a2._on_cadence()
    vus = compter_rendus(a2)
    a2._start()
    globals()["root"] = r2            # `pomper`/`attendre` pompent CETTE App
    try:
        fini = attendre(lambda: a2.stacker is not None and a2.stacker.n >= 6,
                        120)
        pomper(a2.RAFALE_QUIET_S + 0.6)
    finally:
        globals()["root"] = root_ref[0]
    n = a2.stacker.n if a2.stacker is not None else 0
    a2._stop()
    time.sleep(0.2)
    r2.update()
    return (vus, n, fini)


def main():
    vus, n, fini = scenario(0.0)           # AVANT le jalon 80 (silence nul)
    verifie(fini and n == 6,
            "les 6 brutes de la rafale sont empilées (n = %d)" % n)
    verifie(len(vus) >= 3,
            "AVANT le jalon (RAFALE_QUIET_S = 0) : un rendu PAR brute "
            "(%d déclenchements pour 6 brutes : %s)" % (len(vus), vus))
    vus2, n2, fini2 = scenario(app.RAFALE_QUIET_S)
    verifie(fini2 and n2 == 6,
            "même rafale avec la fin de rafale (n = %d)" % n2)
    verifie(len(vus2) == 1 and vus2 == [6],
            "APRÈS le jalon : UN SEUL rendu, sur la pile complète "
            "(%d déclenchement(s) : %s)" % (len(vus2), vus2))
    verifie(len(vus2) < len(vus),
            "moins de rendus pour la MÊME pile (%d contre %d) — la chaîne lourde "
            "n'est plus calculée sur une pile à 1 brute" % (len(vus2), len(vus)))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        code = main()
    finally:
        for d in vides:
            shutil.rmtree(d, ignore_errors=True)
    print("\n" + ("BANC jalon 80 : OK" if ok else "BANC jalon 80 : ÉCHECS"))
    sys.exit(code)

