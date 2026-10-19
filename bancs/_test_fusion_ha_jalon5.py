# -*- coding: utf-8 -*-
"""Banc v2.92.0 — JALON J5 : L'ANCRE PARTAGÉE NE PEUT PAS ÊTRE LE Ha FUSIONNÉ.

Décision d'Alain (19/10/2026) : dans une composition BROADBAND+Ha (RGB+Ha,
LRGB+Ha), le rôle Ha est FUSIONNÉ au composite et s'aligne sur LUI-MÊME (voie A,
jalon 129b) : il ne se sert JAMAIS de l'aligneur partagé. Le choisir comme ancre
partagée ne lui apporte donc RIEN, alors que les couches large bande paieraient
un repère venu d'une bande de 7 nm.

QUATRE chemins posent l'ancre partagée (relevé du 19/10/2026) :
  ① repli après refus répétés       : déjà fermé par un `if voie_a` explicite ;
  ② création de l'empilement        : FERMÉ ici (on attend une brute LARGE BANDE) ;
  ③ re-ancrage « meilleure brute »  : FERMÉ ici (le Ha n'est plus candidat) ;
  ④ rafraîchissement auto / manuel  : fermé PAR CONSTRUCTION dès que ② l'est (la
    référence vient de la couche qui alimente le VERT, le Ha est en dernier).
Ce banc vérifie les QUATRE — y compris celles déjà fermées : un refactoring peut
emporter un `if` sans bruit.

POURQUOI PAS « le Ha a peu d'étoiles » : MESURÉ sur les canaux M33 réels, le Ha
détecte PLUS d'étoiles que G et B (4 391 contre 3 932 et 3 594) et il est la
couche la PLUS FINE (FWHM 2,46 px, contre 3,45 px pour L). Le score qui tranche
est un NOMBRE D'ÉTOILES (des flux), pas une qualité : il ne doit pas décider de
l'ancre partagée.

Vérifie :
  [1] `_meilleure_archive_compo` EXCLUT le Ha fusionné (+Ha), le GARDE en
      HOO/SHO, et `_veut_restack` ne peut plus être déclenché par le Ha ;
  [2] session +Ha : une 1re frame Ha ne crée RIEN (message d'attente, frame
      ARCHIVÉE) ; la 1re frame large bande crée l'empilement, devient l'ancre
      et REJOUE la frame Ha dans son propre repère ;
  [3] assertion ① : une série de refus Ha ne repose JAMAIS l'ancre partagée ;
  [4] assertion ④ : la référence de rafraîchissement est une couche large
      bande (celle du vert, puis L/R/B — le Ha est en dernier) ;
  [5] NON-RÉGRESSION : HOO attend toujours sa première Ha et ancre sur elle.

Exécution : python bancs/_test_fusion_ha_jalon5.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
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
import avastack.ui.app as ui
from avastack.processing.composition import CompositeStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

images.CFA_MODE = "Non"                  # brutes mono dans ce test
H, W = 160, 200
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- champ d'étoiles commun (la géométrie est la même pour tous les rôles) ---
def _etoiles(graine, n=40):
    rng = np.random.default_rng(graine)
    return [(rng.uniform(15, W - 15), rng.uniform(15, H - 15),
             rng.uniform(0.4, 0.9)) for _ in range(n)]


_ETOILES = _etoiles(7)


def champ(dx=0.0, dy=0.0, fond=0.05, graine=0, bruit=0.004):
    """Carte float32 (H, W) : fond BRUITÉ + étoiles gaussiennes translatées."""
    img = np.full((H, W), fond, np.float32)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    for (sx, sy, f) in _ETOILES:
        img += f * np.exp(-((x - (sx + dx)) ** 2 + (y - (sy + dy)) ** 2)
                          / (2.0 * 1.2 ** 2)).astype(np.float32)
    img += np.random.default_rng(1000 + graine).normal(
        0, bruit, img.shape).astype(np.float32)
    return img


class _Archive:
    """Archive FACTICE : `_meilleure_archive_compo` ne lit que `chemins`."""

    def __init__(self, n):
        self.chemins = [f"f{i}.fit" for i in range(n)]


class _Val:
    """Bouchon de variable Tk (le worker lit var_wb au moment de créer)."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


# `_dire()` est une boîte MODALE : elle bloquerait le banc indéfiniment.
ui.App._dire = lambda self, *a, **k: None

ui.CONFIG = {}                       # banc HERMÉTIQUE : jamais le vrai config
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.rejeter_flou = False             # test déterministe (pas de filtre flou)
app.ref_refresh = 0                  # pas de rafraîchissement automatique
app._veut_restack = lambda: False    # re-stack AUTO neutralisé (déterminisme)
app.var_wb = _Val(False)
app.var_wb_force = _Val(1.0)


# ============================= [1] la liste des candidats (porte ③) =========
print("[1] re-ancrage : le Ha FUSIONNÉ n'est plus candidat")


def _meilleur(compo, scores):
    app._mode_compo = True
    app._compo_nom = compo
    app.archives = {r: _Archive(len(s)) for r, s in scores.items()}
    app._scores_par_role = {r: list(s) for r, s in scores.items()}
    return app._meilleure_archive_compo()


r = _meilleur("LRGB+Ha", {"L": [10], "G": [20], "Ha": [999]})
verifie(r[0] == "G" and r[3] == 20,
        f"LRGB+Ha : le Ha (999) est ÉCARTÉ → meilleure brute G (20) — reçu {r[0]}")
r = _meilleur("RGB+Ha", {"R": [3], "G": [2], "B": [1], "Ha": [999]})
verifie(r[0] == "R",
        f"RGB+Ha : le Ha est ÉCARTÉ → R (3) — reçu {r[0]}")
r = _meilleur("LRGB+Ha", {"Ha": [999]})
verifie(r[0] is None,
        "LRGB+Ha sans couche large bande : AUCUN candidat (pas de re-ancrage)")
r = _meilleur("HOO", {"Ha": [999], "O3": [10]})
verifie(r[0] == "Ha",
        "HOO : le Ha EST un canal → il reste candidat et gagne (999)")
r = _meilleur("SHO", {"S2": [5], "Ha": [999], "O3": [8]})
verifie(r[0] == "Ha",
        "SHO : le Ha alimente le VERT → il reste candidat et gagne (999)")
r = _meilleur("RGB", {"R": [10], "G": [20], "B": [5]})
verifie(r[0] == "G",
        "RGB (aucun Ha) : comportement inchangé → G (20)")

# Le déclencheur AUTO ne peut plus être armé par une frame Ha seule.
app._mode_compo = True
app._compo_nom = "LRGB+Ha"
app._ref_score = 10
app._ancre_idx = None
app._ancre_role = None
app.archives = {"Ha": _Archive(1)}
app._scores_par_role = {"Ha": [999]}
verifie(app._veut_restack() is False,
        "déclencheur AUTO : une frame Ha à 999 étoiles ne déclenche RIEN")


# ===================== [2] la 1re frame Ha ne crée pas l'empilement =========
print("[2] session +Ha : une 1re frame Ha attend une brute large bande")
app.archives = {}
app._scores_par_role = {}
app.stacker = None
app._mode_compo = True
app._compo_nom = "LRGB+Ha"
app.aligner.reset()
app.aligner_ha.reset()
app._ha_ref_posee = False
app._ha_ref_bad = 0
app._ref_bad = 0
app._ref_frames = 0
app.bad_frames = 0
app.bad_frames_par_role = {}
app._ancre_role = app._ancre_idx = app._ancre_score = None

_sauter, _lg, stack = app._worker_empiler_frame(champ(graine=1), "Ha", None,
                                                time.perf_counter())
verifie(not _sauter and stack is None and app.stacker is None,
        "1re frame Ha : AUCUN empilement créé (l'ancre ne peut pas être Ha)")
verifie("large bande" in app.align_info,
        f"message d'attente explicite — reçu {app.align_info!r}")
verifie(app.archives.get("Ha") is not None and app.archives["Ha"].n == 1,
        "la frame Ha est ARCHIVÉE (rien n'est perdu)")

_sauter, _lg, stack = app._worker_empiler_frame(champ(graine=2), "R", None,
                                                time.perf_counter())
verifie(app.stacker is not None and app.stacker.composition == "LRGB+Ha",
        "1re frame LARGE BANDE : l'empilement est créé")
verifie(app._ancre_role == "R",
        f"l'ancre est la brute LARGE BANDE (reçu {app._ancre_role})")
_prof = {r: s.n for r, s in app.stacker.stackers.items()} if app.stacker else {}
verifie(_prof.get("Ha") == 1,
        f"la frame Ha archivée est REJOUÉE dans son propre repère — états {_prof}")
verifie(_prof.get("R") == 1,
        f"la frame large bande est empilée (c'est l'ancre) — états {_prof}")

for _role, _g in (("G", 3), ("B", 4)):
    app._worker_empiler_frame(champ(graine=_g), _role, None, time.perf_counter())
_prof = {r: s.n for r, s in app.stacker.stackers.items()}
verifie(_prof.get("G") == 1 and _prof.get("B") == 1,
        f"les autres couches large bande s'empilent normalement — états {_prof}")
verifie(app._ancre_role == "R",
        f"l'ancre reste la 1re large bande (jamais le Ha) — reçu {app._ancre_role}")


# ================= [3] assertion ① : le repli Ha ne touche pas l'ancre =======
print("[3] assertion ① : un refus Ha ne repose JAMAIS l'ancre partagée")
_appels = {"n": 0}
_appels_ha = {"n": 0}
_orig_def = app._definir_reference
_orig_def_ha = app._definir_reference_ha


def _spy_def(img, motif="", role_source=None):
    _appels["n"] += 1
    return _orig_def(img, motif=motif, role_source=role_source)


def _spy_def_ha(img):
    _appels_ha["n"] += 1
    return _orig_def_ha(img)


app._definir_reference = _spy_def
app._definir_reference_ha = _spy_def_ha
app._ref_bad = 0
app._ha_ref_bad = 0
app.aligner_ha.compute = lambda f: (None, False)     # refus Ha FORCÉS
for _i in range(3):
    app._worker_empiler_frame(champ(graine=10 + _i), "Ha", None,
                              time.perf_counter())
verifie(_appels["n"] == 0,
        "refus Ha ×3 : l'ancre PARTAGÉE n'est pas reposée (0 appel)")
verifie(app._ref_bad == 0 and _appels_ha["n"] >= 1,
        f"le repli existe mais il est PROPRE au Ha (ref_bad={app._ref_bad}, "
        f"repli Ha={_appels_ha['n']}) — et il remet son compteur à zéro")
app._definir_reference = _orig_def
app._definir_reference_ha = _orig_def_ha


# ================= [4] assertion ④ : le rafraîchissement prend du broadband ==
print("[4] assertion ④ : le rafraîchissement prend une couche LARGE BANDE")
app._mode_compo = True
_st4 = CompositeStacker("LRGB+Ha", k=None)
_st4.add(champ(graine=20), role="L")        # la couche du VERT est VIDE
_img, _role = app._image_reference_et_role_de(_st4)
verifie(_role == "L", f"vert vide → repli sur L (jamais Ha) — reçu {_role}")
_st4b = CompositeStacker("LRGB+Ha", k=None)
_st4b.add(champ(graine=21), role="G")
_st4b.add(champ(graine=22), role="Ha")
_img, _role = app._image_reference_et_role_de(_st4b)
verifie(_role == "G", f"vert présent → G — reçu {_role}")


# ==================== [5] NON-RÉGRESSION : HOO ancre toujours sur le Ha =====
print("[5] non-régression : HOO attend sa première Ha et ancre sur elle")
app.archives = {}
app._scores_par_role = {}
app.stacker = None
app._mode_compo = True
app._compo_nom = "HOO"
app.aligner.reset()
app._ref_bad = 0
app._ref_frames = 0
app.bad_frames = 0
app.bad_frames_par_role = {}
app._ancre_role = app._ancre_idx = None
_sauter, _lg, stack = app._worker_empiler_frame(champ(graine=30), "O3", None,
                                                time.perf_counter())
verifie(app.stacker is None and "en attente d'une brute Ha" in app.align_info,
        f"HOO : attend toujours sa première Ha — reçu {app.align_info!r}")
_sauter, _lg, stack = app._worker_empiler_frame(champ(graine=31), "Ha", None,
                                                time.perf_counter())
verifie(app.stacker is not None and app._ancre_role == "Ha",
        f"HOO : la 1re Ha crée l'empilement et devient l'ancre — "
        f"reçu {app._ancre_role}")
verifie("en attente d'une brute large bande" not in app.align_info,
        "HOO : le message « large bande » ne fuit pas dans une composition "
        "narrowband")


# ------------------------------------------------------------------ ménage --
for _a in list(app.archives.values()):
    try:
        _a.vider()
    except Exception:
        pass
app.archives = {}
root.destroy()

print()
print("BANC J5 : " + ("VERT — toutes les vérifications passent" if ok
                      else "ROUGE — au moins une vérification a échoué"))
sys.exit(0 if ok else 1)
