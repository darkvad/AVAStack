# -*- coding: utf-8 -*-
"""Banc v2.72.0 (jalon 119) — TEMPS DE POSE & INTÉGRATION PAR COUCHE.

Chantier : la barre d'état affiche, à côté du nombre de frames, le TEMPS DE
POSE unitaire et la DURÉE D'INTÉGRATION (par couche en composition + total).
Source : les en-têtes FITS (EXPTIME/EXPOSURE) pour les sources « dossier », la
consigne appliquée pour les caméras SDK.

Ce banc vérifie :
  [1] `images` : `load_image(..., avec_expo=True)` renvoie (image, expo) —
      RÉTRO-COMPATIBLE (défaut = image seule), `lire_exptime_fits`, mots-clés
      variés (EXPTIME/EXPOSURE/XPOSURE), unités (s / ms / µs), valeur absente ;
  [2] `LiveStacker` : `exposure_times`, `expo_unitaire`, `expo_min_max`,
      `integration_totale`, remise à zéro du `reset`, et NON-INTERFÉRENCE avec
      les mathématiques (add avec/sans exposure → rendu identique) ;
  [3] `CompositeStacker` : `expo_par_role`, `integration_totale`, `etat_expo`
      (chaque rôle a SON empileur → poses différentes par couche) ;
  [4] formatage : `_fmt_duree` (60s→1min, 3600s→1h), `_fmt_expo`,
      `_fmt_expo_plage` (« 30-60s ») et `App._texte_expo` (mono + composition) ;
  [5] `ArchiveFrames` : le temps de pose est mémorisé AVEC la frame, et
      `vider()` le réinitialise (matière du re-stack) ;
  [6] caméras : `exposure_time_sec` — None par défaut, consigne appliquée pour
      la caméra simulée, en-tête FITS pour `FolderCamera`.

Exécution : python bancs/_test_expo_integration_jalon119.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
import sys
import tempfile
import time

import numpy as np
import cv2

from avastack import images
from avastack.images import load_image, lire_exptime_fits
from avastack.processing.stacking import LiveStacker
from avastack.processing.composition import CompositeStacker
from avastack.processing.framestore import ArchiveFrames
from avastack.cameras.base import CameraBase
from avastack.cameras.simulated import SimulatedCamera
from avastack.cameras.folder import FolderCamera
from avastack.ui.app import App, _fmt_duree, _fmt_pose, _fmt_pose_plage

if hasattr(sys.stdout, "reconfigure"):   # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="avastack_banc119_")


def _fits(path, arr, entete=None):
    from astropy.io import fits
    fits.PrimaryHDU(np.asarray(arr), header=fits.Header(entete or {})
                    ).writeto(path, overwrite=True)
    return path


# ============================================================================
print("[1] images : lecture de l'en-tête FITS (avec_expo, mots-clés, unités)")
if not images.FITS_OK:
    print("  SAUTÉ  astropy indisponible — lecture FITS non testable")
else:
    p = _fits(os.path.join(TMP, "expo60.fit"),
              np.full((6, 8), 0.25, np.float32), {"EXPTIME": 60.0})
    lu = load_image(p, avec_expo=True)
    verifie(isinstance(lu, tuple) and len(lu) == 2,
            "avec_expo=True renvoie (image, expo)")
    verifie(abs(lu[1] - 60.0) < 1e-9, "EXPTIME=60 → expo 60 s")
    verifie(isinstance(lu[0], np.ndarray) and lu[0].shape == (6, 8),
            "l'image est inchangée (float32 (6, 8))")
    seul = load_image(p)
    verifie(isinstance(seul, np.ndarray) and seul.shape == (6, 8),
            "défaut RÉTRO-COMPATIBLE : load_image() renvoie l'IMAGE seule")
    verifie(np.array_equal(seul, lu[0]), "et c'est bien la même image")

    verifie(lire_exptime_fits(p) == 60.0, "lire_exptime_fits → 60.0")

    p2 = _fits(os.path.join(TMP, "expo_exposure.fit"),
               np.zeros((4, 4), np.uint16), {"EXPOSURE": 15})
    verifie(lire_exptime_fits(p2) == 15.0, "mot-clé EXPOSURE=15 s reconnu")

    p3 = _fits(os.path.join(TMP, "expo_xposure.fit"),
               np.zeros((4, 4), np.uint16), {"XPOSURE": 5})
    verifie(lire_exptime_fits(p3) == 5.0, "mot-clé XPOSURE=5 s reconnu")

    p4 = _fits(os.path.join(TMP, "expo_ms.fit"),
               np.zeros((4, 4), np.uint16),
               {"TIMEUNIT": "ms", "EXPTIME": 60000})
    verifie(lire_exptime_fits(p4) == 60.0,
            "unités ms (TIMEUNIT=ms, EXPTIME=60000) → 60 s")

    p5 = _fits(os.path.join(TMP, "expo_us.fit"),
               np.zeros((4, 4), np.uint16),
               {"BUNIT": "us", "EXPTIME": 500000})
    verifie(lire_exptime_fits(p5) == 0.5,
            "unités µs (BUNIT=us, EXPTIME=500000) → 0.5 s")

    p6 = _fits(os.path.join(TMP, "expo_absent.fit"),
               np.zeros((4, 4), np.uint16))
    verifie(lire_exptime_fits(p6) is None, "mot-clé absent → None")

    p7 = _fits(os.path.join(TMP, "expo_zero.fit"),
               np.zeros((4, 4), np.uint16), {"EXPTIME": 0.0})
    verifie(lire_exptime_fits(p7) is None,
            "EXPTIME=0 → None (jamais de pose nulle)")

    png = os.path.join(TMP, "image.png")
    cv2.imwrite(png, np.zeros((4, 4, 3), np.uint8))
    verifie(lire_exptime_fits(png) is None, "PNG → None (pas d'en-tête FITS)")
    lu_png = load_image(png, avec_expo=True)
    verifie(isinstance(lu_png, tuple) and lu_png[1] is None,
            "load_image(avec_expo=True) sur PNG → expo None")

# ============================================================================
print("[2] LiveStacker : temps de pose et intégration")
rng = np.random.default_rng(119)
fr = rng.normal(0.2, 0.02, (24, 32)).astype(np.float32)

st = LiveStacker((24, 32), k=3.0)
for _ in range(4):
    st.add(fr, exposure=60.0)
verifie(st.expo_unitaire() == 60.0, "pose constante 60 s → expo_unitaire = 60")
verifie(st.expo_min_max() == (60.0, 60.0), "min/max = (60, 60)")
verifie(abs(st.integration_totale() - 240.0) < 1e-9,
        "4 × 60 s → intégration 240 s")

st_var = LiveStacker((24, 32), k=3.0)
for e in (30.0, 60.0, 60.0):
    st_var.add(fr, exposure=e)
verifie(st_var.expo_unitaire() is None, "pose VARIABLE → expo_unitaire None")
verifie(st_var.expo_min_max() == (30.0, 60.0),
        "min/max = (30, 60) → « 30-60s »")
verifie(abs(st_var.integration_totale() - 150.0) < 1e-9,
        "30 + 60 + 60 → intégration 150 s")

st_nu = LiveStacker((24, 32), k=3.0)
for _ in range(3):
    st_nu.add(fr)
verifie(st_nu.expo_min_max() is None and st_nu.integration_totale() == 0.0,
        "aucune pose connue → None / 0 s (repli sur le compteur de frames)")

st_math = LiveStacker((24, 32), k=3.0)
st_math2 = LiveStacker((24, 32), k=3.0)
for _ in range(6):
    st_math.add(fr)
    st_math2.add(fr, exposure=42.0)
verifie(np.array_equal(st_math.mean(), st_math2.mean()),
        "add(exposure=…) NE change PAS le rendu (mathématiques intactes)")

st.reset()
verifie(st.exposure_times == [] and st.integration_totale() == 0.0,
        "reset() vide les temps de pose")

# ============================================================================
print("[3] CompositeStacker : temps de pose PAR COUCHE")
cp = CompositeStacker("LRGB", k=3.0)
for _ in range(2):
    cp.add(fr, role="L", exposure=60.0)
cp.add(fr, role="R", exposure=30.0)
cp.add(fr, role="G", exposure=60.0)
cp.add(fr, role="B", exposure=30.0)
etat = cp.expo_par_role()
verifie(set(etat) == {"L", "R", "G", "B"}, "4 rôles exposés")
verifie(etat["L"]["n"] == 2 and etat["L"]["unitaire"] == 60.0, "L : 2 × 60 s")
verifie(etat["R"]["unitaire"] == 30.0, "R : pose 30 s")
verifie(abs(cp.integration_totale() - (120 + 30 + 60 + 30)) < 1e-9,
        "intégration totale = 240 s (somme des rôles)")
ee = cp.etat_expo()
verifie(set(ee) == {"roles", "total"} and abs(ee["total"] - 240.0) < 1e-9,
        "etat_expo() → {'roles', 'total'}")

cp_var = CompositeStacker("HOO", k=3.0)
cp_var.add(fr, role="Ha", exposure=300.0)
cp_var.add(fr, role="Ha", exposure=60.0)
ev = cp_var.expo_par_role()["Ha"]
verifie(ev["unitaire"] is None and ev["min"] == 60.0 and ev["max"] == 300.0,
        "pose variable dans une couche → unitaire None, min/max renseignés")

# ============================================================================
print("[4] formatage (app) : durées, poses et ligne d'état")
verifie(_fmt_duree(30) == "30s", "_fmt_duree(30) = 30s")
verifie(_fmt_duree(60) == "1min", "_fmt_duree(60) = 1min")
verifie(_fmt_duree(20 * 60) == "20min", "_fmt_duree(1200) = 20min")
verifie(_fmt_duree(3600) == "1h", "_fmt_duree(3600) = 1h")
verifie(_fmt_duree(5400) == "1.5h", "_fmt_duree(5400) = 1.5h")
verifie(_fmt_pose(60) == "60s", "_fmt_pose(60) = 60s (langage d'une pose)")
verifie(_fmt_pose(0.5) == "0.5s", "_fmt_pose(0.5) = 0.5s")
verifie(_fmt_pose_plage(60, 60, 60) == "60s", "plage constante → 60s")
verifie(_fmt_pose_plage(None, 30, 60) == "30-60s", "plage variable → 30-60s")

st_mono = {"frames": 20,
           "expo": {"roles": {}, "unitaire": 60.0, "min": 60.0, "max": 60.0,
                    "total": 1200.0}}
txt_mono = App._texte_expo(None, st_mono)
verifie(txt_mono == "20×60s = 20min (intégration)",
        "ligne mono = « %s »" % txt_mono)

st_compo = {"frames": 22,
            "expo": {"roles": {"L": {"n": 12, "unitaire": 60.0, "min": 60.0,
                                     "max": 60.0, "integration": 720.0},
                               "R": {"n": 10, "unitaire": 30.0, "min": 30.0,
                                     "max": 30.0, "integration": 300.0}},
                     "total": 1020.0}}
txt_compo = App._texte_expo(None, st_compo)
verifie(txt_compo == "L: 12×60s=12min · R: 10×30s=5min  |  Total: 17min",
        "ligne compo = « %s »" % txt_compo)

st_vide = {"frames": 7, "expo": {"roles": {}, "unitaire": None, "min": None,
                                 "max": None, "total": 0.0}}
verifie(App._texte_expo(None, st_vide)
        == "7 frames empilées (intégration cumulée)",
        "sans pose connue → repli sur le compteur de frames")
verifie(App._texte_expo(None, {"frames": 3})
        == "3 frames empilées (intégration cumulée)",
        "état d'avant le 119 (pas de clé « expo ») → pas de plantage")

# ============================================================================
print("[5] ArchiveFrames : le temps de pose suit la frame archivée")
arch = ArchiveFrames(intervalle_s=0.0)
c1 = arch.ajouter(fr, exposition=60.0)
c2 = arch.ajouter(fr)                      # sans temps de pose
verifie(c1 is not None and c2 is not None, "deux frames archivées")
verifie(arch.expositions == [60.0, None],
        "expositions = [60.0, None] (parallèle à chemins)")
arch.vider()
verifie(arch.expositions == [] and arch.chemins == [],
        "vider() réinitialise aussi les expositions")

# ============================================================================
print("[6] caméras : exposure_time_sec")
verifie(CameraBase().exposure_time_sec is None,
        "CameraBase : None par défaut (jamais de pose inventée)")
sim = SimulatedCamera(w=32, h=24, n_stars=5)
sim.apply_settings(250.0, 1.0)
verifie(sim.exposure_time_sec == 0.25,
        "caméra SDK : consigne 250 ms → 0.25 s")

if images.FITS_OK:
    d = tempfile.mkdtemp(prefix="avastack_banc119_dir_")
    fp = _fits(os.path.join(d, "brute.fit"),
               np.full((10, 12), 0.1, np.float32),
               {"EXPTIME": 45.0, "FILTER": "L"})
    t = time.time() - 10.0
    os.utime(fp, (t, t))                   # fichier « complet » (mtime ancien)
    cam = FolderCamera(d, process_existing=True, poll=0.1)
    cam.open()
    img = None
    for _ in range(40):                     # laisse le scan confirmer la taille
        img = cam.read(timeout=0.5)
        if img is not None:
            break
    cam.close()
    verifie(img is not None and img.shape == (10, 12),
            "FolderCamera lit bien la brute")
    verifie(cam.exposure_time_sec == 45.0,
            "FolderCamera : expo 45 s lue dans l'en-tête (sans relecture)")

# ============================================================================
print()
print("RÉSULTAT : " + ("TOUT VERT" if ok else "ÉCHECS"))
sys.exit(0 if ok else 1)



