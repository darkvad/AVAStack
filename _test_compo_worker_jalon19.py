# -*- coding: utf-8 -*-
"""Test du jalon 19 PHASE 2 — worker en mode « composition multi-filtres ».

Vérifie :
  [1] CompositeStacker seul : un stacker par rôle, mean() → composite,
      cadre commun (note_alignement global), reset, k/set_rejet répercutés,
      etat() « Ha: n · O3: m », composition_pour_roles (exact + sous-ensemble) ;
  [2] worker réel (app._worker dans un thread) avec MultiFolderCamera sur
      deux dossiers temporaires de FITS mono : façade posée, stackers par
      rôle, état par canal dans les stats, composite (H, W, 3), archive
      PAR RÔLE (l'archive mono reste vide), scores PAR RÔLE (jalon 20) ;
  [3] sauvegarde LINÉAIRE : le fichier écrit = le composite BRUT de la façade
      (v2.35.0 : `mean(corrections=False)` — aucune correction de couleur).

Le chemin mono-flux ne doit PAS changer : les 25 autres _test_*.py restent
verts (régression vérifiée à part).
"""

import os
import re
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
from avastack.cameras.multifolder import MultiFolderCamera
from avastack.processing.composition import (CompositeStacker,
                                             composition_pour_roles)
from avastack.processing.framestore import ArchiveFrames
from avastack.images import load_image, save_image

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFA_MODE_AVANT = images.CFA_MODE
images.CFA_MODE = "Non"                  # brutes mono dans ce test

H, W = 200, 260
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK  " if cond else "  ÉCHEC ") + msg)


# --- champ d'étoiles synthétique (positions fixes, translation appliquée) ---
_ETOILES = None


def champ(dx=0.0, dy=0.0, fond=0.05, graine=0):
    """Carte float32 (H, W) : fond BRUITÉ + étoiles gaussiennes translatées.
    Jalon 21 : le bruit de fond est INDISPENSABLE — sans lui, la détection
    d'étoiles (médiane-MAD) renvoie « image constante » (0 étoile) et le
    chemin TRIANGLES, imposé en HOO/SHO depuis le jalon 21, n'a rien à
    appareiller (en vrai ciel, il y a toujours du bruit de lecture/pose)."""
    global _ETOILES
    rng = np.random.default_rng(7)
    if _ETOILES is None:
        _ETOILES = [(rng.uniform(15, W - 15), rng.uniform(15, H - 15),
                     rng.uniform(0.4, 0.9)) for _ in range(30)]
    img = np.full((H, W), fond, np.float32)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    for (sx, sy, f) in _ETOILES:
        xx, yy = sx + dx, sy + dy
        img += f * np.exp(-((x - xx) ** 2 + (y - yy) ** 2)
                          / (2.0 * 1.2 ** 2)).astype(np.float32)
    img += np.random.default_rng(100 + graine).normal(
        0, 0.004, img.shape).astype(np.float32)
    return img


# =========================================================== [1] façade seule
print("[1] CompositeStacker seul")
verifie(composition_pour_roles(("Ha", "O3")) == "HOO"
        and composition_pour_roles(("S2", "Ha", "O3")) == "SHO"
        and composition_pour_roles(("R", "G", "B")) == "RGB"
        and composition_pour_roles(("L", "R", "G", "B")) == "LRGB"
        and composition_pour_roles(("L",)) == "Mono"
        and composition_pour_roles(("Ha",)) == "HOO"      # sous-ensemble
        and composition_pour_roles(("L", "R", "G")) == "LRGB"
        and composition_pour_roles(()) is None,
        "composition_pour_roles : exact + sous-ensembles + vide")

fa = CompositeStacker("HOO", k=None)
fa.role_courant = "Ha"
fa.add(champ())
fa.role_courant = "O3"
fa.add(champ(2, 5))
verifie(set(fa.stackers) == {"Ha", "O3"} and fa.n == 2,
        "un stacker PAR RÔLE, n = total des rôles")
verifie(fa.mean() is not None and fa.mean().shape == (H, W, 3)
        and fa.mean().dtype == np.float32,
        "mean() → composite (H, W, 3) float32 (HOO)")
verifie(fa.mean(recadre=False).shape == (H, W, 3),
        "mean(recadre=False) → composite sans recadrage (référence)")
verifie(set(fa.moyennes()) == {"Ha", "O3"}
        and all(m.shape == (H, W) for m in fa.moyennes().values()),
        "moyennes() → dict rôle → carte 2D, formes identiques")
verifie(fa.etat() == "Ha: 1 · O3: 1",
        "etat() → « Ha: 1 · O3: 1 » (ordre de la composition)")

# cadre commun : une translation d'alignement réduit l'intersection GLOBALE
fa2 = CompositeStacker("HOO", k=None)
fa2.role_courant = "Ha"
fa2.add(champ())
fa2.note_alignement(np.array([[1.0, 0.0, 10.0], [0.0, 1.0, 0.0]]))
avant = fa2.cadre
fa2.role_courant = "O3"
fa2.note_alignement(np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 5.0]]))
verifie(fa2.cadre is not None and avant is not None
        and fa2.cadre[0] >= avant[0] and fa2.cadre[1] >= avant[1]
        and fa2.cadre[2] <= avant[2] and fa2.cadre[3] <= avant[3],
        "note_alignement : intersection GLOBALE (cadre commun rétrécit)")
if fa2.cadre is not None:
    y0, x0, y1, x1 = fa2.cadre
    formes = {r: m.shape for r, m in fa2.moyennes().items()}
    verifie(all(f == (y1 - y0, x1 - x0) for f in formes.values()),
            "toutes les moyennes recadrées à la TAILLE du cadre commun")

fa2.reset()
verifie(fa2.stackers == {} and fa2.cadre is None and fa2.n == 0,
        "reset() → tout vide (tous rôles + cadre)")

fa.k = 3.0
fa.set_rejet(method="winsorized", window=5)
verifie(all(s.k == 3.0 and s.method == "winsorized" and s.window == 5
            for s in fa.stackers.values()),
        "k / set_rejet répercutés sur TOUS les stackers de rôle")

# ============================================ [2] worker réel (intégration)
print("[2] worker réel + MultiFolderCamera (dossiers temporaires Ha/O3)")


class ArchiveRapide(ArchiveFrames):
    """Archive sans limite de débit (test)."""

    def __init__(self, *a, **k):
        k.setdefault("intervalle_s", 0.0)
        super().__init__(*a, **k)


import avastack.ui.app as ui
ui.ArchiveFrames = ArchiveRapide
# Config HERMÉTIQUE (règle du projet, cf. AVANCEMENT) : jamais le vrai
# config.json du poste. Depuis le jalon 56, celui d'Alain contient la case
# « Astrométrie » cochée et ses indices : le worker lancerait alors une VRAIE
# résolution astrométrique (lecture du catalogue Gaia, plusieurs centaines de
# ms à quelques secondes) pendant que ce banc mesure sa cadence — la stat de la
# dernière frame n'arriverait plus dans les temps.
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None

racine = tempfile.mkdtemp(prefix="avastack_jalon19_")
d_ha = os.path.join(racine, "Ha")
d_o3 = os.path.join(racine, "O3")
os.makedirs(d_ha)
os.makedirs(d_o3)
decalages = {"Ha": [(0.0, 0.0), (3.0, 1.0), (6.0, 2.0)],
             "O3": [(2.0, 5.0), (5.0, 8.0), (8.0, 3.0)]}
for role, doss in (("Ha", d_ha), ("O3", d_o3)):
    for i, (dx, dy) in enumerate(decalages[role]):
        save_image(os.path.join(doss, f"{role}_{i:02d}.fits"),
                   champ(dx, dy, fond=0.05 if role == "Ha" else 0.07,
                         graine=i if role == "Ha" else 50 + i))
time.sleep(1.3)                      # taille stable + mtime > 0,5 s (folder)

root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.rejeter_flou = False             # test déterministe (pas de filtre)
app.ref_refresh = 0                  # pas de rafraîchissement de référence


class _Val:
    """Bouchon de variable Tk : var.get() est INTERDIT hors thread principal
    (RuntimeError « main thread is not in main loop ») — le worker lit
    var_wb/var_wb_force au moment de créer l'empilement."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app.var_wb = _Val(False)
app.var_wb_force = _Val(1.0)
cam = MultiFolderCamera([("Ha", d_ha), ("O3", d_o3)])
cam.open()
app.camera = cam
# Comme _start le fera en phase 3 (pas d'UI « composition » encore) :
app._mode_compo = True
app._compo_nom = composition_pour_roles(cam.roles)
verifie(app._compo_nom == "HOO", "composition déduite des rôles → HOO")

app.running = True
app.empilement_on = True             # jalon 26 : le worker n'empile que si armé
th = threading.Thread(target=app._worker, daemon=True)
th.start()

t0 = time.time()
st = None
while time.time() - t0 < 60:
    if app.stacker is not None and app.stacker.n >= 6:
        break
    try:
        _show, _hist, st = app.q.get(timeout=0.5)
    except Exception:
        pass
time.sleep(0.5)                      # dernière itération du worker terminée
try:                                 # la stat la PLUS RÉCENTE de la file
    while True:
        _show, _hist, st = app.q.get_nowait()
except Exception:
    pass

verifie(app.stacker is not None
        and type(app.stacker).__name__ == "CompositeStacker",
        "worker : la façade CompositeStacker est posée")
verifie(set(app.stacker.stackers) == {"Ha", "O3"} and app.stacker.n == 6,
        "worker : 6 frames empilées, stackers Ha ET O3")
verifie(app.stacker.stackers["Ha"].n == 3
        and app.stacker.stackers["O3"].n == 3,
        "worker : 3 frames par rôle (round-robin respecté)")
comp = app.stacker.mean()
if app.stacker.cadre is not None:    # le composite sort RECADRÉ au cadre
    _y0, _x0, _y1, _x1 = app.stacker.cadre
    attendu = (_y1 - _y0, _x1 - _x0, 3)
else:
    attendu = (H, W, 3)
verifie(comp is not None and comp.shape == attendu,
        f"worker : composite {attendu} produit pour l'affichage "
        "(recadré au cadre commun)")
if st is not None:
    verifie(isinstance(st.get("compo"), str)
            and re.fullmatch(r"Ha: [1-9]\d* · O3: [1-9]\d*",
                             st["compo"]) is not None,
            f"stats : état par canal présent (« {st.get('compo')} »)")
    verifie(st.get("archive", 0) == 6,
            f"stats : archive = total des RÔLES (6) — reçu "
            f"{st.get('archive')!r} : {st}")
else:
    verifie(False, "stats : aucune stat reçue de la file")

# archive PAR RÔLE ; l'archive mono reste vide ; scores PAR RÔLE (jalon 20).
# Jalon 21 : la 1re brute Ha est l'ANCRE initiale (HOO) → rejeu des archives
# à l'ancre → _restack_depuis repart de 0 puis compte les frames suivantes.
verifie(sum(a.n for a in app.archives.values()) == 6
        and set(app.archives) == {"Ha", "O3"},
        "worker : archive PAR RÔLE (6 frames, rôles Ha/O3)")
verifie(app.archive.n == 0, "worker : archive MONO intacte (vide)")
verifie(app._restack_depuis == 5 and app._scores == []
        and set(app._scores_par_role) == {"Ha", "O3"}
        and all(len(v) == 3 for v in app._scores_par_role.values())
        and all(s >= 0 for v in app._scores_par_role.values() for s in v),
        "worker : scores PAR RÔLE (jalon 20) + ancre Ha au démarrage "
        "(jalon 21 : 1re Ha → rejeu, 5 frames comptées depuis)")
verifie(app._ancre_role == "Ha" and app.restack_total == 1,
        "worker : ancre initiale = la 1re brute Ha (jalon 21)")
if app.stacker.cadre is not None:
    y0, x0, y1, x1 = app.stacker.cadre
    formes = {r: m.shape for r, m in app.stacker.moyennes().items()}
    verifie(all(f == (y1 - y0, x1 - x0) for f in formes.values()),
            "worker : cadre commun appliqué (formes identiques)")

# ---------------------------------------------- [3] sauvegarde linéaire
print("[3] sauvegarde linéaire = composite de la façade")
p_save = os.path.join(racine, "composite.fits")
app.save_request = p_save
t0 = time.time()
while app.saved_path is None and time.time() - t0 < 10:
    time.sleep(0.05)
verifie(app.saved_path == p_save and os.path.exists(p_save),
        "sauvegarde consommée par le worker (façade transparente)")
if os.path.exists(p_save):
    lu = load_image(p_save)
    # v2.27.1 : le fichier écrit est le composite BORNÉ à [0,1] — contenu
    # identique à un facteur GLOBAL près (AVASCALE dans l'en-tête), ce qui
    # rend le fichier lisible par ASTAP et les lecteurs qui supposent [0,1]
    # (avant, un composite à max > 1 n'était pas résolvable — constat réel
    # d'Alain du 22/09/2026 sur son empilement M31).
    ech = max(float(comp.max()), 1.0)     # facteur retiré par borner_lineaire
    verifie(lu.shape == comp.shape
            and np.allclose(lu, comp / ech, rtol=1e-5, atol=1e-6),
            "fichier sauvegardé = composite courant (linéaire)")
    verifie(float(lu.max()) <= 1.0 + 1e-6,
            f"fichier borné à [0,1] (max {float(lu.max()):.5f})")

app.running = False
th.join(timeout=5)
cam.close()
root.destroy()

shutil.rmtree(racine, ignore_errors=True)
images.CFA_MODE = CFA_MODE_AVANT
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
