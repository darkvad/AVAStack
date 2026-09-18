# -*- coding: utf-8 -*-
"""Test du jalon 21 — NARROWBAND (HOO/SHO) : TRIANGLES D'ABORD + ancre Ha.

Décision d'Alain (19/09/2026) : en composition narrowband, l'alignement
commence SYSTÉMATIQUEMENT par les TRIANGLES (ORB écarté : il s'apparie mal
d'un filtre à l'autre), et la référence d'alignement initiale est TOUJOURS
une brute Ha — les frames des autres rôles qui arrivent avant la 1re Ha
sont archivées puis rejouées à l'ancrage. Ensuite (re-stack), comportement
normal (jalon 20). Jalon 21b (retour réel : 86 refus en début de session
SHO, les canaux narrowband montrant souvent moins de 6 étoiles communes) :
REPLI « étoiles » puis PHASE après l'échec des triangles — jamais ORB.

Vérifie :
  [1] StarAligner.triangles_seuls : méthode « triangles » imposée en premier
      (jamais ORB), champ pauvre (4 étoiles < minimum des triangles) → repli
      PHASE (jalon 21b, retour réel : 86 refus en début de session SHO),
      frame sans étoiles ni texture → refusée ;
  [2] App._narrowband_ha : HOO/SHO → True, RGB/LRGB/Mono → False ;
  [3] worker HOO réel : frames O3 AVANT la 1re Ha → attente (pas d'empilement),
      puis ancre sur la 1re Ha et REJEU des O3 archivées ; triangles_seuls
      activé pour la session.

Le mono et RGB ne changent pas (cascade ORB → triangles → étoiles → phase).
Nécessite un affichage. Exécution : python _test_narrowband_ha_jalon21.py
"""
import os
import sys
import threading
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"              # brutes mono dans ce test
import avastack.ui.app as ui
from avastack.processing.alignment import StarAligner

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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


# Champ d'étoiles à positions FIXES (même logique que les tests jalon 16/20) :
# mêmes POSITIONS pour tous les « filtres » (seuls le bruit et le fond varient
# — comme Ha et O3 du même ciel), dithering simulé par décalages.
rng0 = np.random.default_rng(5)
POS = [(float(rng0.integers(25, 235)), float(rng0.integers(25, 175)),
        float(rng0.uniform(0.2, 0.7))) for _ in range(22)]


def champ_fixe(shape, fond=0.03, bruit=0.005, graine=1):
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for x, y, a in POS:
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * 1.4 ** 2))).astype(np.float32)
    img += np.random.default_rng(graine).normal(0, bruit, img.shape).astype(
        np.float32)
    return img


SHAPE = (200, 260)
O3_A = champ_fixe(SHAPE, fond=0.05, graine=21)
O3_B = decale(champ_fixe(SHAPE, fond=0.05, graine=22), 6.0, 3.0)
HA_A = champ_fixe(SHAPE, fond=0.03, graine=23)
HA_B = decale(champ_fixe(SHAPE, fond=0.03, graine=24), 9.0, 4.0)
PLATE = np.full(SHAPE, 0.4, np.float32)          # aucun objet détectable

# ==================================== [1] TRIANGLES d'abord + repli
print("[1] triangles_seuls : triangles d'abord, repli phase, jamais ORB")
al = StarAligner()
al.set_reference(HA_A)
al.triangles_seuls = True
M, okk = al.compute(O3_B)
verifie(okk and M is not None and al.dernier["methode"] == "triangles",
        f"triangles_seuls : alignement OK par TRIANGLES "
        f"(méthode « {al.dernier['methode'] if al.dernier else '?'} »)")
if okk and M is not None:
    verifie(abs(float(M[0, 2]) + 6.0) < 1.5 and abs(float(M[1, 2]) + 3.0) < 1.5,
            f"translation retrouvée (Δ=({M[0, 2]:+.1f},{M[1, 2]:+.1f}) px)")

# Champ PAUVRE (4 étoiles < le minimum de 6 des triangles ET du chemin
# « étoiles ») : repli PHASE (jalon 21b, retour réel d'Alain — 86 refus en
# session SHO quand le canal narrowband montre peu d'étoiles).
POS4 = [(60.0, 50.0, 0.5), (120.0, 80.0, 0.6), (180.0, 120.0, 0.4),
        (150.0, 60.0, 0.45)]


def champ_pauvre(dx=0.0, dy=0.0, graine=1):
    h, w = SHAPE
    img = np.full((h, w), 0.03, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for x, y, a in POS4:
        img += (a * np.exp(-((yy - (y + dy)) ** 2 + (xx - (x + dx)) ** 2)
                           / (2.0 * 1.4 ** 2))).astype(np.float32)
    img += np.random.default_rng(graine).normal(0, 0.004, img.shape).astype(
        np.float32)
    return img


REF4 = champ_pauvre(0.0, 0.0, graine=31)
al2 = StarAligner()
al2.set_reference(REF4)
al2.triangles_seuls = True
M3, ok3 = al2.compute(champ_pauvre(6.0, 3.0, graine=32))
verifie(ok3 and al2.dernier["methode"] == "phase",
        f"champ pauvre (4 étoiles) : triangles refusent → REPLI PHASE "
        f"(méthode « {al2.dernier['methode'] if al2.dernier else '?'} »)")
M4, ok4 = al2.compute(PLATE)
verifie(not ok4 and (al2.dernier is None
                     or al2.dernier["methode"] != "ORB"),
        "frame sans étoiles ni texture → refusée (repli épuisé, sans ORB)")

# ==================================== [2] _narrowband_ha
print("[2] _narrowband_ha : HOO/SHO → True ; RGB/LRGB/Mono → False")
root = tk.Tk()
root.withdraw()
app = ui.App(root)
app._mode_compo = True
for nom, attendu in (("HOO", True), ("SHO", True), ("RGB", False),
                     ("LRGB", False), ("Mono", False)):
    app._compo_nom = nom
    verifie(app._narrowband_ha() == attendu,
            f"composition {nom} → narrowband Ha : {attendu}")

# ==================================== [3] worker HOO : attente Ha + rejeu
print("[3] worker HOO réel : O3 d'abord → attente, puis ancre Ha + rejeu")


class ArchiveRapide(ui.ArchiveFrames):
    """Archive sans limite de débit (test)."""

    def __init__(self, *a, **k):
        k.setdefault("intervalle_s", 0.0)
        super().__init__(*a, **k)


class CamRoles:
    """Source de test : liste figée de (image, rôle), comme MultiFolderCamera."""

    name = "test"

    def __init__(self, items):
        self.items = items
        self.i = 0

    def read(self):
        self.i += 1
        return None if self.i > len(self.items) else self.items[self.i - 1]


class _Val:
    """Bouchon de variable Tk : var.get() est INTERDIT hors thread principal."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


ui.ArchiveFrames = ArchiveRapide
app2 = ui.App(root)
app2.rejeter_flou = False            # test déterministe (pas de filtre)
app2.ref_refresh = 0                 # pas de rafraîchissement de référence
app2.var_wb = _Val(False)
app2.var_wb_force = _Val(1.0)
app2.camera = CamRoles([(O3_A, "O3"), (O3_B, "O3"),
                        (HA_A, "Ha"), (HA_B, "Ha")])
app2._mode_compo = True
app2._compo_nom = "HOO"

try:
    app2.running = True
    th = threading.Thread(target=app2._worker, daemon=True)
    th.start()
    t0 = time.time()
    while time.time() - t0 < 30.0 and (app2._ancre_role != "Ha"
                                       or app2.stacker is None
                                       or app2.stacker.n < 4):
        time.sleep(0.05)
    app2.running = False
    th.join(timeout=5.0)
    verifie(app2._ancre_role == "Ha" and app2.restack_total >= 1,
            "ancre initiale posée sur la 1re brute Ha (rejeu = 1er re-stack)")
    verifie(app2.aligner.triangles_seuls is True,
            "session HOO : mode « triangles d'abord, sans ORB » activé")
    verifie(app2.stacker is not None
            and set(app2.stacker.stackers) == {"Ha", "O3"}
            and app2.stacker.stackers["O3"].n >= 2
            and app2.stacker.stackers["Ha"].n >= 1,
            f"les O3 arrivées AVANT la 1re Ha sont rejouées "
            f"(Ha {app2.stacker.stackers['Ha'].n}, "
            f"O3 {app2.stacker.stackers['O3'].n})")
    verifie(sum(a.n for a in app2.archives.values()) == 4,
            "archives PAR RÔLE complètes (4 frames)")
finally:
    app2.running = False
    for a in app2.archives.values():
        a.vider()

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
