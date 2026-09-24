# -*- coding: utf-8 -*-
"""Test du jalon 20 — RE-STACK MULTI-CANAL (mode composition).

Le re-stack « à la Siril » (jalon 16, mono) est étendu au mode composition
multi-filtres (jalon 19) : chaque couche (rôle) a son archive, ses mauvaises
frames ou ses meilleures au fil du stack. Vérifie :

  [1] _meilleure_archive_compo : argmax des scores TOUS RÔLES confondus
      (mesure identique : canal extrait de chaque rôle), cohérence avec
      _vider_archive ;
  [2] _veut_restack (compo) : marge 1,5× sur la meilleure brute de N'IMPORTE
      QUELLE couche, exclusion de l'ancre courante (rôle + index) ;
  [3] _do_restack direct : NOUVELLE façade CompositeStacker, réglages
      conservés (composition, gains, mode L, WB, méthode/fenêtre de rejet),
      TOUTES les couches recalculées depuis les archives PAR RÔLE (canal
      ré-extrait), ancre (rôle, index, score), ligne dédiée verte avec le
      détail PAR CANAL ;
  [4] intégration worker : déclencheur AUTO (constantes patchées) sur une
      ancre médiocre (1re brute Ha très défocalisée) — MultiFolderCamera
      Ha/O3 réelle ; pas de boucle ensuite (l'ancre est la meilleure).

Le chemin mono (jalon 16/18) ne change pas : _test_restack_jalon16.py et
_test_restack_visu_jalon18.py restent verts.
Nécessite un affichage. Exécution : python _test_restack_compo_jalon20.py
"""
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
images.CFA_MODE = "Non"              # brutes mono dans ce test
from avastack.cameras.multifolder import MultiFolderCamera
import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)
from avastack.processing.composition import (CompositeStacker,
                                             composition_pour_roles)
from avastack.processing.framestore import ArchiveFrames
from avastack.images import load_image, save_image

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERT = "#1d7f1d"
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def decale(img, dx, dy):
    """warpAffine d'une translation (sens OpenCV)."""
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_LINEAR)


# Même principe que le test jalon 16 : P = TRÈS défocalisée (score effondré),
# B/C/D = nettes décalées (dithering). Positions d'étoiles FIXES.
rng0 = np.random.default_rng(3)
POS = [(float(rng0.integers(20, 240)), float(rng0.integers(20, 180)),
        float(rng0.uniform(0.15, 0.7))) for _ in range(25)]


def champ_fixe(shape, sigma_px=1.5, bruit=0.004, fond=0.02, graine=1):
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for x, y, a in POS:
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += np.random.default_rng(graine).normal(0, bruit, img.shape).astype(
        np.float32)
    return img


H, W = 200, 260
SHAPE = (H, W)
P = champ_fixe(SHAPE, sigma_px=8.0, graine=11)          # ancre médiocre
B = decale(champ_fixe(SHAPE, graine=12), 5.0, 2.0)
C = decale(champ_fixe(SHAPE, graine=13), 10.0, 4.0)
D = decale(champ_fixe(SHAPE, graine=14), 15.0, 6.0)

root = tk.Tk()
root.withdraw()
app = ui.App(root)
app._mode_compo = True
app._compo_nom = "HOO"


class ArchiveRapide(ArchiveFrames):
    """Archive sans limite de débit (test)."""

    def __init__(self, *a, **k):
        k.setdefault("intervalle_s", 0.0)
        super().__init__(*a, **k)


def archiver(role, frames):
    """Archive `frames` pour `role` et remplit les scores PAR RÔLE (même
    mesure que le worker : _score_frame sur la frame lue)."""
    arch = app.archives.setdefault(role, ArchiveRapide())
    for f in frames:
        arch.ajouter(f)
    app._scores_par_role[role] = [app._score_frame(load_image(c))
                                  for c in arch.chemins]


# ==================================== [1] _meilleure_archive_compo
print("[1] _meilleure_archive_compo : argmax TOUS RÔLES confondus")
app._vider_archive()
verifie(app._meilleure_archive_compo() == (None, None, None, None),
        "archives vides → (None, None, None, None)")
archiver("Ha", [P, B, C, D])
archiver("O3", [B, C])
role, idx, chemin, score = app._meilleure_archive_compo()
tous_scores = [s for v in app._scores_par_role.values() for s in v]
verifie(role in ("Ha", "O3") and score == max(tous_scores)
        and chemin == app.archives[role].chemins[idx]
        and score == app._scores_par_role[role][idx],
        f"meilleure brute = {role}#{idx} ({score} étoiles, tous rôles)")
app._vider_archive()
verifie(app._scores_par_role == {} and sum(a.n for a in
                                            app.archives.values()) == 0
        and app._meilleure_archive_compo() == (None, None, None, None),
        "_vider_archive : archives PAR RÔLE ET scores PAR RÔLE remis à zéro")

# ==================================== [2] _veut_restack (compo)
print("[2] _veut_restack compo : marge 1,5× toutes couches, ancre exclue")
app.archives = {"Ha": ArchiveRapide(), "O3": ArchiveRapide()}
app.archives["Ha"].chemins = ["a", "b"]     # factice : ne sont pas lus
app.archives["O3"].chemins = ["c"]
app._scores_par_role = {"Ha": [5, 40], "O3": [30]}
app._ref_score = 5
app._ancre_role = app._ancre_idx = None
verifie(app._veut_restack(),
        "meilleure brute (Ha, 40) ≥ 1,5 × référence (5) → re-stack voulu")
app._ancre_role, app._ancre_idx = "Ha", 1
verifie(not app._veut_restack(),
        "la meilleure brute EST l'ancre courante (rôle + index) → rien")
app._ancre_role, app._ancre_idx = "O3", 0
verifie(app._veut_restack(),
        "l'ancre est une AUTRE couche (O3) que la meilleure (Ha) → voulu")
app._ancre_role, app._ancre_idx = None, None
app._ref_score = 30
verifie(not app._veut_restack(),
        "40 < 1,5 × 30 → marge non atteinte, pas de re-stack")
app._ref_score = None
verifie(not app._veut_restack(), "référence non mesurée → pas de re-stack")

# ==================================== [3] _do_restack direct (compo)
print("[3] _do_restack direct : TOUTES les couches recalculées")
app._vider_archive()
archiver("Ha", [P, B, C, D])
archiver("O3", [B, C])
ancien = CompositeStacker("HOO", k=None, method="winsorized", window=6)
ancien.wb_auto = True
ancien.wb_force = 0.7
ancien.gains = {"R": 1.2, "G": 0.8, "B": 1.0}
ancien.mode_l = "degrade"
ancien.role_courant = "Ha"
ancien.add(P)
app.stacker = ancien
app._definir_reference(P)         # ancre initiale = la DÉFOCALISÉE (canal)
app._ancre_role = app._ancre_idx = None
app.restack_total = 0
app.restack_hist = []
info = app._do_restack("test")
verifie(info.startswith("re-stack"), f"message d'état (« {info[:60]}… »)")
verifie(app.stacker is not ancien
        and type(app.stacker).__name__ == "CompositeStacker",
        "NOUVELLE façade CompositeStacker posée")
verifie(app.stacker.composition == "HOO"
        and app.stacker.method == "winsorized" and app.stacker.window == 6
        and app.stacker.wb_auto and abs(app.stacker.wb_force - 0.7) < 1e-9
        and app.stacker.gains == {"R": 1.2, "G": 0.8, "B": 1.0}
        and app.stacker.mode_l == "degrade",
        "réglages conservés (composition, rejet, WB, gains, mode L)")
verifie(set(app.stacker.stackers) == {"Ha", "O3"}
        and app.stacker.stackers["Ha"].n >= 3
        and app.stacker.stackers["O3"].n >= 1,
        f"couches recalculées (Ha {app.stacker.stackers['Ha'].n}/4, "
        f"O3 {app.stacker.stackers['O3'].n}/2 au moins)")
role_m, idx_m, _c, score_m = app._meilleure_archive_compo()
verifie((app._ancre_role, app._ancre_idx, app._ancre_score)
        == (role_m, idx_m, score_m) and app._ref_score == score_m,
        f"référence = meilleure brute TOUS RÔLES ({role_m}#{idx_m}, "
        f"{score_m} étoiles)")
comp = app.stacker.mean()
verifie(comp is not None and comp.ndim == 3 and np.isfinite(comp).all(),
        "composite du re-stack fini (H, W, 3)")
verifie(app.restack_total == 1 and app.restack_couleur == VERT
        and f"{role_m} " in app.restack_info
        and f"{'Ha' if role_m == 'O3' else 'O3'} " in app.restack_info,
        f"ligne dédiée verte avec détail PAR CANAL (« {app.restack_info} »)")
verifie(len(app.restack_hist) == 1 and app.restack_hist[0] == app.restack_info,
        "historique : 1 entrée = l'état affiché")

# ==================================== [4] intégration worker (AUTO)
print("[4] intégration worker : déclencheur AUTO (constantes patchées)")
ui.RESTACK_MIN_FRAMES = 2
ui.RESTACK_CADENCE = 1
racine = tempfile.mkdtemp(prefix="avastack_jalon20_")
d_ha = os.path.join(racine, "Ha")
d_o3 = os.path.join(racine, "O3")
os.makedirs(d_ha)
os.makedirs(d_o3)
save_image(os.path.join(d_ha, "ha_00.fits"), P)   # 1re lue = ANCRE médiocre
save_image(os.path.join(d_ha, "ha_01.fits"), B)
save_image(os.path.join(d_ha, "ha_02.fits"), C)
save_image(os.path.join(d_o3, "o3_00.fits"), B)
save_image(os.path.join(d_o3, "o3_01.fits"), C)
save_image(os.path.join(d_o3, "o3_02.fits"), D)
time.sleep(1.3)                      # taille stable + mtime > 0,5 s (folder)

app2 = ui.App(root)
app2.rejeter_flou = False            # test déterministe (pas de filtre)
app2.ref_refresh = 0                 # pas de rafraîchissement de référence


class _Val:
    """Bouchon de variable Tk : var.get() est INTERDIT hors thread principal."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app2.var_wb = _Val(False)
app2.var_wb_force = _Val(1.0)
ui.ArchiveFrames = ArchiveRapide
cam = MultiFolderCamera([("Ha", d_ha), ("O3", d_o3)])
cam.open()
app2.camera = cam
app2._mode_compo = True
app2._compo_nom = composition_pour_roles(cam.roles)

try:
    app2.running = True
    app2.empilement_on = True           # jalon 26 : le worker n'empile que si armé
    th = threading.Thread(target=app2._worker, daemon=True)
    th.start()
    t0 = time.time()
    # Jalon 21 : le 1er re-stack est l'ANCRE Ha du démarrage (ha_00 = P) ;
    # le 2e est le re-stack AUTO sur une meilleure brute (P est médiocre).
    while time.time() - t0 < 60.0 and (app2.restack_total < 2
                                       or sum(a.n for a in
                                              app2.archives.values()) < 6):
        time.sleep(0.05)
    app2.running = False
    th.join(timeout=5.0)
    verifie(app2._ancre_role in ("Ha", "O3"),
            f"déclencheur AUTO : re-stack sur {app2._ancre_role} "
            "(l'ancre initiale était médiocre)")
    verifie(app2.restack_total >= 2 and app2.restack_couleur == VERT,
            "ligne dédiée : ancre Ha au démarrage + re-stack réussi (vert)")
    tous = [s for v in app2._scores_par_role.values() for s in v]
    score_p = app2._scores_par_role["Ha"][0]     # score de l'ancre médiocre P
    verifie(app2._ancre_score >= ui.RESTACK_MARGE * score_p,
            f"référence re-ancrée nettement mieux que l'ancre médiocre "
            f"({app2._ancre_score} étoiles ≥ 1,5 × {score_p})")
    verifie(sum(a.n for a in app2.archives.values()) == 6,
            "archives PAR RÔLE complètes (6 frames)")
    verifie(type(app2.stacker).__name__ == "CompositeStacker"
            and app2.stacker.n >= 4,
            f"empilement reconstruit ({app2.stacker.n} frames)")
finally:
    app2.running = False
    for a in app2.archives.values():
        a.vider()
    shutil.rmtree(racine, ignore_errors=True)

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
