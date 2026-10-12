# -*- coding: utf-8 -*-
"""Banc du jalon 127 (v2.79.0) — LA CHROMA AGIT POUR LES DEUX MOTEURS.

Décision d'Alain (12/10/2026) : la case « Réduire le bruit chromatique » (cadre
« Fond et grain ») était VISIBLE mais INERTE en STF — elle vivait dans la branche
VeraLux du worker. Arbitrage : on ne la masque pas, on l'OUVRE aux DEUX moteurs
(comme GraXpert et le débruitage au jalon 125), par la règle « le fichier =
l'écran ». La chroma entre donc dans la chaîne PRÉ-ÉTIREMENT COMMUNE
(`_vl_worker`, APRÈS la netteté), et la sauvegarde « tel que vu » n'est plus
gardée par `stretch == "veralux"`.

Vérifie :
  [1] STF, ÉCRAN : la sortie de la chaîne pré-étirement = chroma(entrée)
      (comparaison image à image) — la case n'est plus inerte ;
  [2] STF, ÉCRAN : `process()` route par la chaîne quand la chroma est active,
      donc cocher la case CHANGE le rendu ;
  [3] STF, FICHIER : la sauvegarde « tel que vu » applique la chroma quel que
      soit le moteur (plus de gate `stretch == "veralux"`) — écran == fichier ;
  [4] VERA LUX : comportement INCHANGÉ (chroma appliquée JUSTE AVANT
      l'étirement) ;
  [5] le MOTEUR et la chroma restent dans la clé des réglages.

Exécution : python bancs/_test_chroma_stf_jalon127.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time
import inspect

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)          # parade du projet : crash OpenCV 5/OpenCL au
                                     # teardown quand on enchaîne les bancs Tk

import avastack.processing.display as dp                          # noqa: E402
from avastack.processing import couleurs as C                     # noqa: E402
from avastack.processing import veralux as V                      # noqa: E402
import avastack.ui.saver as saver_mod                            # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def attendre(d_, timeout=60.0):
    """Attend la fin du job de la chaîne (sans exiger la clé : une seule
    soumission par cas)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with d_._vl_lock:
            if (d_._vl_job is None and not d_._vl_pending
                    and d_._vl_result is not None):
                return True
        time.sleep(0.02)
    return False


def resultat(d_):
    with d_._vl_lock:
        return (None if d_._vl_result is None
                else np.asarray(d_._vl_result[1], np.float32))


# Scène COULEUR : fond teinté + GRAIN COLORÉ (la chroma n'agit que sur la
# couleur) + une tache colorée (sa LUMINANCE ne doit pas bouger).
rng = np.random.default_rng(127)
H, W = 96, 128
IMG = np.empty((H, W, 3), np.float32)
IMG[..., 0] = 0.06 + rng.normal(0, 0.010, (H, W)).astype(np.float32)
IMG[..., 1] = 0.07 + rng.normal(0, 0.010, (H, W)).astype(np.float32)
IMG[..., 2] = 0.09 + rng.normal(0, 0.010, (H, W)).astype(np.float32)
IMG[30:40, 50:60] = (0.25, 0.05, 0.20)
np.clip(IMG, 0.0, 1.0, out=IMG)

# =========================================== [1] STF : la chaîne l'applique
print("[1] STF : la chroma entre dans la sortie de la chaîne pré-étirement")
d = dp.DisplayProcessor()
d.stretch = "stf"
d.vl_chroma = True
d.vl_chroma_force = 0.6
d.notify_new_stack()
d._process_chaine(IMG, live=False)
verifie(attendre(d), "chaîne pré-étirement terminée (STF)")
attendu = C.reduire_bruit_chroma(IMG, force=0.6, rayon=d.vl_chroma_rayon)
ecart = float(np.max(np.abs(resultat(d) - attendu)))
verifie(ecart < 1e-6,
        f"en STF, sortie de chaîne = chroma(entrée) — écart max {ecart:.2e}")
verifie(not np.allclose(resultat(d), IMG),
        "…et la sortie DIFFÈRE de l'entrée (la chroma a bien tourné)")

# =========================================== [2] STF : effet à l'ÉCRAN
print("[2] STF : process() route par la chaîne quand la chroma est active")
# ÉTREINTE MANUELLE (points fixes) : le rendu ne dépend QUE de la chroma, pas
# des stats EMA du STF qui évoluent d'un appel à l'autre.
d.auto = False
d.black = 0.0
d.white = 0.30
d.vl_chroma = False
d.notify_new_stack()
out_off = d.process(IMG).copy()
d.vl_chroma = True
d.notify_new_stack()
d.process(IMG)                       # 1er appel : soumet la chaîne
verifie(attendre(d), "chaîne pré-étirement terminée (2e cas)")
out_on = d.process(IMG).copy()       # 2e appel : la sortie de chaîne est prête
verifie(out_off.dtype == np.uint8 and out_on.shape == out_off.shape,
        "les deux rendus STF ont la même forme (8 bits)")
verifie(not np.array_equal(out_off, out_on),
        "cocher la chroma CHANGE le rendu STF (elle n'est plus inerte)")

# =========================================== [3] FICHIER == ÉCRAN (STF)
print("[3] FICHIER (STF) : la sauvegarde applique la chroma, sans gate moteur")
_src = inspect.getsource(saver_mod.Saver._save_asseen_thread)
verifie("reduire_bruit_chroma" in _src
        and 'reglages.get("vl_chroma")' in _src,
        "la sauvegarde « tel que vu » applique la chroma (case `vl_chroma`)")
verifie('reglages.get("stretch") == "veralux"' not in _src,
        "…sans la réserver à VeraLux (elle vaut AUSSI en STF — jalon 127)")

# =========================================== [4] VERA LUX : inchangé
print("[4] VeraLux : la chroma est appliquée JUSTE AVANT l'étirement (inchangé)")
if not V.moteur_disponible():
    print("  IGNORÉ (moteur VeraLux indisponible)")
else:
    d2 = dp.DisplayProcessor()
    d2.stretch = "veralux"
    d2.vl_chroma = True
    d2.vl_chroma_force = 0.5
    d2.vl_chroma_rayon = 1.5
    params = dict(mode=d2.vl_mode_res, target_bg=d2.vl_target_bg,
                  log_d=d2.vl_log_d, profil=d2.vl_profil)
    d2.notify_new_stack()
    d2._process_chaine(IMG, live=False)
    verifie(attendre(d2), "chaîne VeraLux terminée")
    attendu2 = np.asarray(
        V.etirer(C.reduire_bruit_chroma(IMG, force=0.5, rayon=1.5), **params)[0],
        np.float32)
    ecart2 = float(np.max(np.abs(resultat(d2) - attendu2)))
    verifie(ecart2 < 1e-6,
            f"VeraLux : sortie = chroma PUIS étirement — écart max {ecart2:.2e}")

# =========================================== [5] clé des réglages
print("[5] la chroma ET le moteur restent dans la clé des réglages")
d3 = dp.DisplayProcessor()
d3.stretch = "stf"
k0 = d3._vl_params()
d3.vl_chroma = True
verifie(d3._vl_params() != k0, "cocher la chroma change la clé (re-résolution)")
d3.vl_chroma = False
d3.stretch = "veralux"
verifie(d3._vl_params() != k0, "changer de moteur change la clé")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
