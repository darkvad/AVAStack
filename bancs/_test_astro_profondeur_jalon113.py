# -*- coding: utf-8 -*-
"""Banc du jalon 113 — ② PROFONDEUR MINIMALE PAR RÔLE POUR L'ASTROMÉTRIE.

DÉFAUT CORRIGÉ : la politique d'astrométrie comparait `stacker.n` — en mode
COMPOSITION c'est la SOMME des rôles. En LRGB, 1 frame par rôle donnait donc
`n = 4 ≥ ASTRO_MIN_FRAMES (3)` et le solveur tentait sa résolution sur une image
DÉJÀ INSOLUBLE (« image constante », mesuré : 2 frames/rôle = échec ; 3 = 24
appariements) : l'essai était BRÛLÉ et le backoff (20→300 s) éloignait les
suivants — l'empilement n'atteignait jamais la profondeur où l'astrométrie
fonctionne. La profondeur qui compte est la profondeur MINIMALE parmi les rôles
NON VIDES (chaque canal entre dans le composite).

Vérifie :
  [1] `CompositeStacker.profondeur_min()` : min des rôles non vides (`n`, lui,
      reste la SOMME) ;
  [2] `App._profondeur_astro()` : en composition → `profondeur_min()`, sinon
      `stacker.n` ;
  [3] `SuiviAstrometrie.peut_essayer` : LRGB à 1 frame/rôle → REFUS (insoluble) ;
      3 frames/rôle → accord ;
  [4] `App._astro_tour` (intégration, suivi bouchonné) : la profondeur transmise
      à `peut_essayer` ET `resoudre_sur(n_frames=…)` est celle PAR RÔLE ;
  [5] `App._astro_aveugle` : ASTAP n'est PAS sollicité tant que la profondeur
      par rôle est insuffisante (le balayage est cher).
  [6] JALON 115 — `App._photo_tour` et `App._spcc_tour` : MÊME règle que
      l'astrométrie (`_profondeur_astro`). Ils comparaient encore `stacker.n` (la
      SOMME des rôles) : en LRGB, 1 frame par rôle (n = 4) suffisait à lancer la
      mesure pendant que l'astrométrie en exigeait trois. Sans effet aujourd'hui
      (les deux mesurent après un WCS résolu) mais deux règles pour une même
      décision : plus aucun seuil de profondeur ne doit dériver de l'autre.

Exécution : python bancs/_test_astro_profondeur_jalon113.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV/OpenCL au teardown sinon

import avastack.ui.app as ui
from avastack.processing import astrometrie as astro
from avastack.processing.composition import CompositeStacker
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


H, W = 24, 32


def compo(nom, roles_frames):
    """CompositeStacker peuplé de `roles_frames[r]` frames par rôle."""
    st = CompositeStacker(nom, k=None)
    for role, n in roles_frames.items():
        for i in range(n):
            st.add(np.full((H, W), 0.05 + 0.01 * i, np.float32), role=role)
    return st


# ================================================ [1] profondeur_min()
print("[1] CompositeStacker.profondeur_min() : min des rôles NON VIDES")
st_lrgb = compo("LRGB", {"L": 5, "R": 4, "G": 3, "B": 2})
verifie(st_lrgb.n == 14,
        f"n reste la SOMME des rôles (14 — reçu {st_lrgb.n})")
verifie(st_lrgb.profondeur_min() == 2,
        f"LRGB(5/4/3/2) → 2 (reçu {st_lrgb.profondeur_min()})")

st_opt = compo("LRGB", {"R": 4, "G": 3, "B": 2})     # L optionnel VIDE
verifie(st_opt.profondeur_min() == 2,
        f"rôle L vide → 2, jamais bloquant (reçu {st_opt.profondeur_min()})")

st_seul = compo("LRGB", {"L": 7})
verifie(st_seul.profondeur_min() == 7,
        f"un seul rôle rempli → sa profondeur (reçu {st_seul.profondeur_min()})")

verifie(CompositeStacker("LRGB", k=None).profondeur_min() == 0,
        "aucun rôle rempli → 0")

st_1 = compo("LRGB", {"L": 1, "R": 1, "G": 1, "B": 1})
verifie(st_1.n == 4 and st_1.profondeur_min() == 1,
        "1 frame/rôle → n = 4 MAIS profondeur réelle = 1 (le piège corrigé)")

st_3 = compo("LRGB", {"L": 3, "R": 3, "G": 3, "B": 3})
verifie(st_3.n == 12 and st_3.profondeur_min() == 3,
        "3 frames/rôle → n = 12, profondeur réelle = 3 (le seuil atteint)")


# ============================================ [2] App._profondeur_astro()
print("[2] App._profondeur_astro() : par rôle en composition, n sinon")
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)

app._mode_compo = True
app.stacker = st_lrgb
verifie(app._profondeur_astro(st_lrgb) == 2,
        f"composition → profondeur_min (reçu {app._profondeur_astro(st_lrgb)})")

app._mode_compo = False
mono = LiveStacker((H, W), k=None)
for _ in range(5):
    mono.add(np.full((H, W), 0.05, np.float32))
verifie(app._profondeur_astro(mono) == 5,
        f"hors composition (mono) → n (reçu {app._profondeur_astro(mono)})")
app._mode_compo = True


# ============================ [3] politique : peut_essayer par profondeur
print("[3] SuiviAstrometrie.peut_essayer : refus à 1 frame/rôle (insoluble)")
suivi = astro.SuiviAstrometrie()
suivi.indice(10.683333, 41.268611, 2.63665)
verifie(suivi.pret and not suivi.resolu, "indices posés, WCS pas encore résolu")
verifie(suivi.peut_essayer(st_1.n) is True,
        f"ANCIEN gate (somme n={st_1.n}) : essai autorisé — l'essai brûlé")
verifie(suivi.peut_essayer(app._profondeur_astro(st_1)) is False,
        "NOUVEAU gate (profondeur par rôle = 1) : essai REFUSÉ")
verifie(suivi.peut_essayer(app._profondeur_astro(st_3)) is True,
        "3 frames par rôle : essai autorisé (la mesure dit : RÉSOLU)")


# ============================ [4] intégration : _astro_tour transmet la profondeur
print("[4] App._astro_tour : profondeur PAR RÔLE transmise au suivi")


class SuiviBouchon:
    """Suivi d'astrométrie de test : enregistre ce que le worker lui transmet."""

    def __init__(self):
        self.resolu = False
        self.pret = True
        self.essais = 0
        self.derniere_erreur = ""
        self.appels = []   # profondeurs reçues par peut_essayer
        self.solves = []   # n_frames reçus par resoudre_sur

    def indice(self, *a):
        return False

    def peut_essayer(self, n, maintenant=None):
        self.appels.append(int(n))
        return int(n) >= astro.ASTRO_MIN_FRAMES

    def raison_attente(self):
        return "en attente d'un empilement plus profond"

    def resoudre_sur(self, img, n_frames=None):
        self.solves.append(int(n_frames))
        return False, "bouchon"


app._astro_actif = True
app._astro_indices = (10.68, 41.27, 2.64)
app._astro_wcs_secours = None

b1 = SuiviBouchon()
app.suivi_astro = b1
app.stacker = st_1                    # 1 frame/rôle : n = 4, profondeur = 1
app._astro_tour(st_1)
verifie(b1.appels == [1],
        f"1 frame/rôle : peut_essayer reçoit 1 — reçu {b1.appels}")
verifie(b1.solves == [],
        f"1 frame/rôle : AUCUNE résolution tentée — reçu {b1.solves}")

b2 = SuiviBouchon()
app.suivi_astro = b2
app.stacker = st_3
app._astro_tour(st_3)
verifie(b2.appels == [3] and b2.solves == [3],
        f"3 frames/rôle : peut_essayer ET resoudre_sur reçoivent 3 — "
        f"reçu {b2.appels} / {b2.solves}")


# ============================ [5] repli ASTAP : pas de balayage trop tôt
print("[5] App._astro_aveugle : ASTAP non sollicité sous la profondeur requise")
appels_astap = []


def _astap_bouchon(img, fov_deg=None):
    appels_astap.append(fov_deg)
    return None, None, None, None, "bouchon"


_astap_origine = astro.resoudre_aveugle_astap
astro.resoudre_aveugle_astap = _astap_bouchon

app._astro_aveugles = 0
app._astro_balayage = True
app._astro_bases = "aucune"
app._astro_champ_seul = 1.5
app._astro_dernier_aveugle = 0.0

app._astro_fov_essayes = set()
app._astro_aveugle(st_1)              # profondeur 1 < 3 → rien à balayer
verifie(appels_astap == [] and app._astro_fov_essayes == set(),
        f"profondeur 1 : ASTAP NE balaie PAS — reçu {appels_astap}")

app._astro_fov_essayes = set()
app._astro_aveugle(st_3)              # profondeur 3 → balayage autorisé
verifie(appels_astap == [1.5],
        f"profondeur 3 : ASTAP balaie UNE fois — reçu {appels_astap}")

# ============== [6] jalon 115 : photo et SPCC sur la MÊME profondeur par rôle
print("[6] _photo_tour / _spcc_tour : profondeur PAR RÔLE (fin de l'écart)")
appels_mesure = []


def _canaux_bouchon(stacker):
    """Compte l'appel et arrête le tour juste APRÈS le seuil : c'est le seuil
    qui est mesuré ici, pas la mesure elle-même."""
    appels_mesure.append(stacker)
    return {}, None, None


class SuiviPhotoBouchon:
    """Suivi minimal des deux mesures : WCS « résolu » (leur seul prérequis),
    la grille n'étant jamais atteinte grâce au bouchon ci-dessus."""

    resolu = True

    def wcs_grille(self, cadre, forme=None):
        return None, "bouchon"


class PhotoBouchon:
    valide = False
    derniere_erreur = "bouchon"


app._photo_canaux = _canaux_bouchon
app.suivi_astro = SuiviPhotoBouchon()
app._photo_actif = True
app.photometrie = PhotoBouchon()
app._photo_essais, app._photo_dernier = 0, 0.0
app._spcc_actif = True
app._spcc_dispo = True
app._spcc_essais, app._spcc_dernier = 0, 0.0
app._mode_compo = True

# L'ANCIEN gate (la somme) laissait passer dès 1 frame par rôle : c'est
# exactement l'incohérence que le jalon 115 supprime.
verifie(st_1.n >= astro.ASTRO_MIN_FRAMES,
        f"ANCIEN gate (somme n={st_1.n}) : photo et SPCC mesuraient — l'écart")
appels_mesure.clear()
app._photo_tour(st_1)
verifie(appels_mesure == [],
        f"1 frame/rôle : la PHOTOMÉTRIE ne mesure pas (appels "
        f"{len(appels_mesure)})")
appels_mesure.clear()
app._spcc_tour(st_1)
verifie(appels_mesure == [],
        f"1 frame/rôle : la SPCC ne mesure pas (appels {len(appels_mesure)})")

appels_mesure.clear()
app._photo_tour(st_3)
verifie(len(appels_mesure) == 1,
        f"3 frames/rôle : la PHOTOMÉTRIE mesure (appels {len(appels_mesure)})")
appels_mesure.clear()
app._spcc_tour(st_3)
verifie(len(appels_mesure) == 1,
        f"3 frames/rôle : la SPCC mesure (appels {len(appels_mesure)})")

# Hors composition, la règle reste le nombre de frames empilées.
appels_mesure.clear()
app._mode_compo = False
app._photo_tour(mono)
verifie(len(appels_mesure) == 1,
        f"mono 5 frames : la PHOTOMÉTRIE mesure (appels {len(appels_mesure)})")
app._mode_compo = True

astro.resoudre_aveugle_astap = _astap_origine
root.destroy()
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
