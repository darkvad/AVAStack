# -*- coding: utf-8 -*-
"""Banc v2.98.8 — BASCULE VeraLux → STF : « IMAGE BLANCHE » (21/10/2026).

DÉFAUT SIGNALÉ PAR ALAIN (test complet du 21/10, SEUL point qui bloquait la
fusion vers `master`) : après avoir joué en fin d'empilement avec « un peu tous
les paramètres » EN ÉTIREMENT VERALUX, basculer sur l'étirement STF donnait une
IMAGE BLANCHE.

CAUSE MESURÉE (banc `bancs/_diag_bascule_stf_blanc.py`, avant toute correction) :
la mémoire d'étirement du STF (`DisplayProcessor._stats`, un lissage TEMPOREL de
l'empilement) était POSÉE pendant la phase VeraLux — une simple image d'attente
suffit : le STF y calcule ses stats sur la pile du moment — puis JAMAIS
rafraîchie, parce que depuis l'étape 1a le rendu de frame n'existe plus quand la
chaîne est attendue. À la bascule, `_moteur_stf(live=False)` RÉUTILISAIT cette
mémoire (`_auto_params` la garde dès qu'elle existe) : l'image d'aujourd'hui
était étirée avec le point noir d'hier.
MESURÉ sur la séquence réelle : mémoire `(0,000882, 0,000345, 0,001972)` — la
première pile de la session — contre un empilement à 0,048 ⇒ `lo` −0,000084,
`hi` 0,004335, soit **`hi` 11 fois SOUS le fond** ⇒ tout écrête à 1 :
**médiane 255, 100 % des pixels ≥ 250, écart 180,3 niveaux avec le STF sain**.

QUAND LE NIVEAU CHANGE (c'est le cas réel) : un maître dark/flat chargé ou
retiré (test v2.98.7), un dossier qui mélange plusieurs nuits ou filtres, la
Lune qui se couche… Le STF reçoit alors une image dont le fond est plusieurs
fois au-dessus du `hi` mémorisé : l'écrêtage est TOTAL.

CE QUE CE BANC VERROUILLE
  [1] TÉMOIN INVERSÉ — la même séquence AVEC le garde-fou neutralisé rend bien
      une image BLANCHE (médiane ≥ 250) : la reproduction est la bonne, et elle
      échouerait si le défaut disparaissait de la séquence ;
  [2] LE CORRECTIF — la bascule rend l'image du STF SAIN, IDENTIQUE AU BIT à la
      référence (vraie `DisplayProcessor` neuve, mêmes réglages, aucune
      mémoire) ;
  [3] NON-RÉGRESSION — bascule à niveau STABLE : image identique à la référence
      (écart ≤ 1 niveau), jamais blanche ;
  [4] la mémoire du STF AVANCE au rendu d'une NOUVELLE pile (`live=True`), au
      lieu de rester figée sur la première pile de la session ;
  [5] l'INTERFACE passe bien `live=True` à ce rendu-là (`_maj_lbl_vl`).

Exécution (interpréteur du venv) :
    python bancs/_test_bascule_stf_blanc.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import time

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing import veralux as V
from avastack.processing.display import DisplayProcessor

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def attendre_vl(d, timeout=60.0, avant=None):
    """Attend la fin d'un job de la chaîne (polling, 20 ms).

    `avant` : image du résultat PRÉCÉDENT — on attend alors un résultat
    DIFFÉRENT (sinon on repartirait aussitôt sur l'ancien, déjà publié)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with d._vl_lock:
            res = d._vl_result
            if (d._vl_job is None and not d._vl_pending and res is not None
                    and (avant is None or res[1] is not avant)):
                return True
        time.sleep(0.02)
    return False


# ==================================================== piles linéaires d'essai
# Le FOND est le paramètre qui compte : c'est lui qui change entre deux périodes
# de calibration (maître dark/flat chargé ou retiré — test v2.98.7 —, autre nuit
# ou filtre dans un dossier mixte, Lune qui se couche…). Mono : le défaut est
# dans la MÉMOIRE du STF, aucune couleur n'est nécessaire pour le montrer.
H, W = 64, 80
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_rr = np.sqrt((_xx - W / 2.0) ** 2 + (_yy - H / 2.0) ** 2)
_noyau = 0.8 * np.exp(-(_rr / 8.0) ** 2) + 0.25 * np.exp(-(_rr / 26.0) ** 2)


def pile(fond, frames, graine):
    rng = np.random.default_rng(graine)
    img = fond * (1.0 + 0.9 * _noyau)
    img = img + rng.normal(0.0, 0.0006 / np.sqrt(max(1.0, float(frames))),
                           img.shape)
    return np.clip(img, 0.0, 1.0).astype(np.float32)


FOND_SOMBRE = 0.008           # période « calibration appliquée » (fond retiré)
FOND_CLAIR = 0.048            # période suivante : 6× le fond mémorisé
PILE_DEBUT = pile(FOND_SOMBRE, 1, 1)      # 1re pile : la mémoire du STF naît là
PILE_MILIEU = pile(FOND_CLAIR, 12, 12)
PILE_FIN = pile(FOND_CLAIR, 60, 60)       # l'empilement de la bascule


def _processor_veralux():
    """Vraie `DisplayProcessor` en VeraLux, logD forcé (déterministe et rapide)."""
    d = DisplayProcessor()
    d.stretch = "veralux"
    d.vl_mode_res = V.MODE_LOG_D
    d.vl_log_d = 2.0
    return d


def session_veralux(d, piles):
    """Joue « une session en VeraLux » : la MÉMOIRE du STF est posée par l'image
    d'attente de la première pile (un GESTE ou le FILET rend pendant que la
    chaîne calcule — c'est le seul endroit où le STF voit encore l'empilement),
    puis VeraLux rend chaque pile et le STF ne rend plus rien."""
    prec = None
    for i, p in enumerate(piles):
        with d._vl_lock:
            prec = d._vl_result[1] if d._vl_result is not None else None
        d.notify_new_stack()
        if i == 0:
            # Rendu SANS résultat disponible → image d'attente : le STF y
            # mesure ses stats sur la pile DU MOMENT (et soumet la chaîne).
            d.process(p, live=True)
        else:
            d.demander_chaine(p)
        if not attendre_vl(d, avant=prec):
            return False
        d.process(p, live=False)          # rendu du RÉSULTAT VeraLux
    return True


def reference_stf(img):
    """Le STF SAIN de référence : `DisplayProcessor` NEUVE (aucune mémoire),
    mêmes réglages (défauts) — c'est l'image que la bascule DOIT produire."""
    r = DisplayProcessor()
    r.stretch = "stf"
    return r.process(img, live=False)


def est_blanche(img8):
    """(médiane, part de pixels ≥ 250) d'une image affichée."""
    a = np.asarray(img8)
    return float(np.median(a)), float(np.mean(a >= 250))


if not V.moteur_disponible():
    print("Moteur VeraLux indisponible — banc sauté (le défaut n'existe qu'APRÈS "
          "une période VeraLux).")
    raise SystemExit(0)

# ============================================================================
# [2] LE CORRECTIF — bascule VeraLux → STF SANS nouvelle frame
# ============================================================================
print("=" * 78)
print("[2] BASCULE VeraLux → STF SANS nouvelle frame : image du STF SAIN")
print("=" * 78)
d = _processor_veralux()
verifie(session_veralux(d, (PILE_DEBUT, PILE_MILIEU, PILE_FIN)),
        "session VeraLux jouée (3 piles, la chaîne a rendu chaque fois)")
_memo = d._stats
print("    mémoire du STF après la phase VeraLux : "
      + (f"{tuple(round(v, 6) for v in _memo)}" if _memo is not None else "None")
      + f" · fond de l'empilement à la bascule : {float(np.median(PILE_FIN)):.5f}")
verifie(_memo is not None
        and _memo[0] < 0.25 * float(np.median(PILE_FIN)),
        "la mémoire du STF est POSÉE puis FIGÉE : elle décrit la 1re pile, six "
        "fois sous le fond de la bascule (la condition du défaut)")

d.stretch = "stf"                       # la bascule (`_on_moteur`), RIEN d'autre
out = d.process(PILE_FIN, live=False)   # le rendu de `_refresh_preview`
ref = reference_stf(PILE_FIN)
_med, _sat = est_blanche(out)
print(f"    bascule : médiane {_med:.1f} · pixels ≥250 {100.0 * _sat:.1f} % "
      f"· référence : médiane {float(np.median(ref)):.1f}")
verifie(np.array_equal(out, ref),
        "l'image de la bascule est IDENTIQUE AU BIT au STF de référence")
verifie(_med < 128.0, f"l'image n'est pas blanche (médiane {_med:.1f} < 128)")

# ============================================================================
# [1] TÉMOIN INVERSÉ — la MÊME séquence, garde-fou neutralisé : IMAGE BLANCHE
# ============================================================================
print()
print("=" * 78)
print("[1] TÉMOIN INVERSÉ : sans le garde-fou, la même bascule BLANCHIT")
print("=" * 78)
d2 = _processor_veralux()
verifie(session_veralux(d2, (PILE_DEBUT, PILE_MILIEU, PILE_FIN)),
        "2e session VeraLux jouée (témoin inversé)")
d2.oublier_memoire_stf = lambda: None   # garde-fou NEUTRALISÉ (sans correctif)
d2.stretch = "stf"
out2 = d2.process(PILE_FIN, live=False)
_med2, _sat2 = est_blanche(out2)
verifie(_med2 >= 250.0 and _sat2 > 0.9,
        f"TÉMOIN INVERSÉ : sans le garde-fou, la bascule rend l'image BLANCHE "
        f"(médiane {_med2:.1f}, {100.0 * _sat2:.1f} % des pixels ≥ 250)")
verifie(not np.array_equal(out2, ref),
        "…et cette image DIFFÈRE du STF de référence (le défaut est bien celui-là)")

# ============================================================================
# [3] NON-RÉGRESSION — bascule à niveau STABLE (aucun changement de niveau)
# ============================================================================
print()
print("=" * 78)
print("[3] NON-RÉGRESSION : bascule à niveau STABLE")
print("=" * 78)
d3 = _processor_veralux()
verifie(session_veralux(d3, (PILE_FIN, PILE_FIN, PILE_FIN)),
        "session VeraLux à niveau stable")
d3.stretch = "stf"
out3 = d3.process(PILE_FIN, live=False)
ref3 = reference_stf(PILE_FIN)
_ecart3 = float(np.mean(np.abs(np.asarray(out3, np.float32)
                               - np.asarray(ref3, np.float32))))
_med3, _ = est_blanche(out3)
verifie(_ecart3 <= 1.0,
        f"image identique à la référence (écart moyen {_ecart3:.2f} niveau ≤ 1)")
verifie(_med3 < 128.0, f"jamais blanche (médiane {_med3:.1f})")

# ============================================================================
# [4] LA MÉMOIRE AVANCE au rendu d'une NOUVELLE pile (`live=True`)
# ============================================================================
print()
print("=" * 78)
print("[4] La mémoire du STF AVANCE au rendu d'une NOUVELLE pile")
print("=" * 78)
d4 = DisplayProcessor()
d4.stretch = "stf"
d4.process(PILE_DEBUT, live=True)       # 1re pile : la mémoire naît ici
_memo_avant = d4._stats
d4.process(PILE_FIN, live=True)         # NOUVELLE pile : elle doit suivre
_memo_apres = d4._stats
verifie(_memo_apres is not None and _memo_avant is not None
        and _memo_apres != _memo_avant and _memo_apres[0] > _memo_avant[0],
        f"la mémoire SUIT l'empilement (fond mémorisé {_memo_avant[0]:.5f} → "
        f"{_memo_apres[0]:.5f})")
d4.process(PILE_FIN, live=False)        # un GESTE ne fait pas avancer le lissage
verifie(d4._stats == _memo_apres,
        "un geste (`live=False`) ne modifie PAS la mémoire (jalon 79 intact)")

# ============================================================================
# [5] L'INTERFACE passe `live=True` au rendu de l'image FINALE d'une pile
# ============================================================================
print()
print("=" * 78)
print("[5] L'interface fait AVANCER la mémoire au rendu d'une nouvelle pile")
print("=" * 78)
import tkinter as tk                                    # noqa: E402
import avastack.ui.app as ui                            # noqa: E402

ui.CONFIG = {}
ui.sauver_config = lambda d: None
_root = tk.Tk()
_root.withdraw()
_app = ui.App(_root)
_app.rendu.immediat = True
_app.var_view.set("pile")
_vus = []


def _espion(lineaire, live=True, hist=True, motif="rendu"):
    _vus.append(bool(live))


_app._rendre_et_afficher = _espion
_app.last_show = PILE_FIN
_app._rendu_attente = PILE_FIN      # une pile confiée à la chaîne attend son image
_app._vl_frames = 7
_app._rendu_fait_frames = None
_app.disp.vl_new = True             # le `vl_new` de cette pile arrive
_app._maj_lbl_vl()
verifie(_vus == [True],
        f"le rendu du `vl_new` d'une nouvelle pile est `live=True` (vus : {_vus})")
_vus.clear()
_app._refresh_preview(hist=False)   # un geste ordinaire, lui, ne lisse pas
verifie(_vus == [False],
        f"un geste ordinaire reste `live=False` (vus : {_vus})")
_root.destroy()

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
