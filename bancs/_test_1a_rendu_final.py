# -*- coding: utf-8 -*-
"""Banc étape 1a (branche `OptimisationUI`) — NE PLUS RENDRE DEUX FOIS.

LE DÉFAUT MESURÉ (Phase 0, `perf-3.json`, 13 min, 5 canaux M33) : `rendus` = 132
pour 71 frames — un rendu COMPLET de la pile brute à l'arrivée de la frame, puis
un SECOND rendu complet sur `vl_new` (`_maj_lbl_vl` → `_refresh_preview`), soit
127 s de fil Tk pour 61 rendus dont l'image était identique quand aucune case de
la chaîne n'était cochée (`vl_actif` faux).

CE QUE CE BANC VERROUILLE
  [1] jauge `vl_actif` : lue sur les CASES Tk, jamais sur `disp.vl_*` (le piège
      historique : `vl_neutre_gains` est un RÉSULTAT persistant) ;
  [2] AUCUNE case cochée : UN rendu par frame, et un `vl_new` ne rend PLUS
      (compteur `rendus_evites` incrémenté) ;
  [3] CHAÎNE ACTIVE : aucun rendu de la pile brute — la chaîne est SOLLICITÉE
      sans rendu (`demander_chaine`), puis le `vl_new` rend l'image FINALE ;
  [4] FILET anti-écran figé : chaîne MUETTE (aucun `vl_new`) ⇒ l'image arrive
      quand même après un délai borné (`rendus_filet`, puis plus rien) ;
  [5] RATTRAPAGE : plusieurs frames empilées pendant un calcul ⇒ UN SEUL rendu
      final (pas un par frame) ;
  [6] RAFALE DE DOSSIER (jalon 80) : le déclenchement de la chaîne y est déjà
      différé ⇒ la frame est rendue IMMÉDIATEMENT, comportement inchangé ;
  [7] VRAIE CHAÎNE (`DisplayProcessor`) : `demander_chaine()` soumet le job
      SANS rendre, et l'image affichée par le chemin différé est IDENTIQUE AU
      BIT à la référence `process()`.

Exécution : python bancs/_test_1a_rendu_final.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tempfile
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui
from avastack import perf
from avastack.cameras import FolderCamera
from avastack.processing.display import DisplayProcessor

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ============================================================ outillage Tk
ui.CONFIG = {}
ui.sauver_config = lambda d: None

root = tk.Tk()
root.withdraw()
app = ui.App(root)
# 1b (20/10/2026) : ce banc compare l'image JUSTE après l'avoir demandée (et
# compte les rendus) → rendu IMMÉDIAT, comme avant 1b. Le fil de rendu ne sert
# qu'en production ; le banc 1b (`_test_render_worker_bit_exact.py`) le teste.
app.rendu.immediat = True
app.var_view.set("pile")             # le banc teste le rendu de la vue « pile »


class _CameraMuette:
    """Source sans fichier : `_cadence_dossier()` est FAUX (comportement caméra)."""
    pending = 0
    last_file = ""


app.camera = _CameraMuette()


def pomper(secondes):
    """Fait vivre `_tick` (chaîne `after(30, _tick)`) pendant `secondes`."""
    t0 = time.time()
    while time.time() - t0 < secondes:
        root.update()
        time.sleep(0.005)


def attendre(cond, limite=30.0):
    """Pompe Tk jusqu'à ce que `cond()` soit vraie (worker en fond)."""
    t0 = time.time()
    while time.time() - t0 < limite:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def message(frames, image=None):
    """Message de la file du worker : `(image affichable, état)` — MÊMES clés
    que le vrai worker (`_update_status` les lit toutes)."""
    if image is None:
        image = np.zeros((16, 20), np.float32)
    st = dict(frames=frames, rejets=0, bad=0, floues=0, fps=1.0, cam="banc",
              file="", pending=0, failed=0, align="—", seeing=None,
              seeing_msg="", archive=0, archive_err="", compo=None,
              restack="", restack_n=0, astro="", photo="", spcc="")
    return (image, st)


# Mouchards : `rendus` reçoit ce que l'interface AFFICHE réellement (un appel à
# `_rendre_et_afficher` = un rendu complet, celui que `perf` compte) ; `demandes`
# reçoit les piles confiées à la chaîne SANS rendu.
vrai_rendu = app._rendre_et_afficher
rendus = []


def _compte_rendu(lineaire, live=True, hist=True, motif="rendu"):
    rendus.append(lineaire)


app._rendre_et_afficher = _compte_rendu
demandes = []


def _demande_chaine(img):
    demandes.append(img)


app.disp.demander_chaine = _demande_chaine

# Le premier tour de `_tick` peut déclencher un rendu (gains de composition,
# jalon 55) : on le laisse passer avant de compter.
pomper(0.3)
rendus.clear()
demandes.clear()
perf.activer()
perf.reinitialiser()

# ============================================================================
# [1] JAUGE `vl_actif` : les CASES, jamais les attributs de résultat
# ============================================================================
print("[1] Jauge `vl_actif` : les cases Tk, pas `disp.vl_*`")
app.disp.vl_neutre_gains = (1.0123, 1.0, 0.9544)     # RÉSULTAT persistant (piège)
app._maj_lbl_vl()
verifie(perf.instantane()["jauges"].get("vl_actif") is False,
        "aucune étape de chaîne + gains mesurés ⇒ `vl_actif` = False (piège corrigé)")
verifie(perf.instantane()["jauges"].get("vl_couleurs") is True,
        "la neutralisation cochée PAR DÉFAUT est vue comme « couleur », "
        "pas comme « chaîne » (sinon la jauge serait toujours vraie)")
_jauges = perf.instantane()["jauges"]
verifie(_jauges.get("vl_etapes") == "" and _jauges.get("moteur") == "STF",
        "les jauges disent POURQUOI : aucune étape active, moteur STF")
app.var_vl_chroma.set(True)
app._sync_vl_chroma_vue()
app._maj_lbl_vl()
verifie(perf.instantane()["jauges"].get("vl_actif") is True,
        "une étape de la chaîne cochée ⇒ `vl_actif` = True")
verifie(perf.instantane()["jauges"].get("vl_etapes") == "CH",
        "…et `vl_etapes` nomme l'étape active (« CH »)")
app.var_vl_chroma.set(False)
app._sync_vl_chroma_vue()
app._maj_lbl_vl()
verifie(perf.instantane()["jauges"].get("vl_actif") is False,
        "case décochée ⇒ retour à False")
app.disp.vl_neutre_gains = None      # ne pas polluer les volets suivants

# ============================================================================
# [2] AUCUNE CASE : un rendu par frame, `vl_new` ne rend PLUS
# ============================================================================
print("[2] Aucune case : 1 rendu par frame, aucun rendu sur `vl_new`")
rendus.clear()
demandes.clear()
perf.reinitialiser()
for f in (1, 2, 3):
    app.q.put_nowait(message(f))
    pomper(0.06)
verifie(len(rendus) == 3,
        f"3 frames ⇒ 3 rendus (obtenu : {len(rendus)})")
verifie(not demandes,
        "aucune case cochée ⇒ la chaîne n'est jamais sollicitée")
app.disp.vl_new = True
app._maj_lbl_vl()
verifie(len(rendus) == 3,
        f"un `vl_new` sans case cochée ne rend PAS (rendus : {len(rendus)})")
verifie(perf.instantane()["compteurs"].get("rendus_evites", 0) == 1,
        "le rendu évité est COMPTÉ (`rendus_evites`)")

# ============================================================================
# [3] CHAÎNE ACTIVE : aucun rendu de la pile brute, un rendu sur `vl_new`
# ============================================================================
print("[3] Chaîne active : la frame est confiée à la chaîne, `vl_new` rend l'image finale")
app.var_vl_chroma.set(True)
app.disp.vl_chroma = True
rendus.clear()
demandes.clear()
perf.reinitialiser()
app._rendu_attente = None
app.q.put_nowait(message(4))
pomper(0.12)
verifie(len(rendus) == 0,
        f"chaîne active ⇒ AUCUN rendu de la pile brute (rendus : {len(rendus)})")
verifie(len(demandes) == 1,
        f"la chaîne est SOLLICITÉE sans rendu (demandes : {len(demandes)})")
verifie(app._rendu_attente is not None,
        "la frame est gardée EN ATTENTE de l'image finale")
app.disp.vl_new = True
app._maj_lbl_vl()
verifie(len(rendus) == 1,
        f"le `vl_new` rend l'image FINALE, une seule fois (rendus : {len(rendus)})")
verifie(app._rendu_attente is None,
        "l'attente est vidée après le rendu final")
verifie(bool(rendus) and rendus[0] is app.last_show,
        "c'est bien la dernière pile qui est rendue")
verifie(perf.instantane()["compteurs"].get("rendus_differe", 0) == 1,
        "le rendu différé est COMPTÉ (`rendus_differe`)")

# ============================================================================
# [4] FILET : chaîne MUETTE ⇒ l'image arrive quand même (jamais d'écran figé)
# ============================================================================
print("[4] Filet anti-écran figé : chaîne muette ⇒ rendu forcé après le délai")
_app_var_chroma = True
app.var_vl_chroma.set(True)
app.disp.vl_chroma = True
rendus.clear()
demandes.clear()
perf.reinitialiser()
app._rendu_attente = None
_delai_reel = app.RENDU_FINAL_DELAI_S
app.RENDU_FINAL_DELAI_S = 0.05        # délai court : le banc ne dort pas 15 s
app.q.put_nowait(message(5))
pomper(0.4)
verifie(len(rendus) == 1,
        f"aucun `vl_new` ⇒ UN rendu de secours (rendus : {len(rendus)})")
verifie(app._rendu_attente is None,
        "l'attente est vidée : le filet ne rend pas en boucle")
verifie(perf.instantane()["compteurs"].get("rendus_filet", 0) == 1,
        "le rendu de secours est COMPTÉ (`rendus_filet`)")
app.RENDU_FINAL_DELAI_S = _delai_reel

# ============================================================================
# [5] RATTRAPAGE : N frames pendant un calcul ⇒ UN SEUL rendu final
# ============================================================================
print("[5] Plusieurs frames pendant un calcul ⇒ un seul rendu final")
rendus.clear()
demandes.clear()
app._rendu_attente = None
for f in (6, 7, 8):
    app.q.put_nowait(message(f))
    pomper(0.05)
verifie(len(rendus) == 0,
        f"aucune des 3 frames n'est rendue brute (rendus : {len(rendus)})")
verifie(len(demandes) == 3,
        f"les 3 piles sont confiées à la chaîne (demandes : {len(demandes)})")
app.disp.vl_new = True
app._maj_lbl_vl()
verifie(len(rendus) == 1,
        f"un seul `vl_new` ⇒ UN rendu final pour 3 frames (rendus : {len(rendus)})")

# ============================================================================
# [6] RAFALE DE DOSSIER + CHAÎNE : aucun rendu de frame, un rendu final
# ============================================================================
print("[6] Rafale de dossier : aucun rendu pendant, la chaîne part à la fin")
_vide = tempfile.mkdtemp(prefix="avastack_banc1a_vide_")
app.camera = FolderCamera(_vide)      # `_cadence_dossier()` vrai
app.var_vl_chroma.set(True)
app.disp.vl_chroma = True
app._vl_frames = None
app._rendu_differ = None
rendus.clear()
demandes.clear()
app._rendu_attente = None
app.q.put_nowait(message(9))
pomper(0.12)
verifie(len(rendus) == 0,
        f"rafale + chaîne : AUCUN rendu de frame (rendus : {len(rendus)})")
verifie(app._rendu_attente is not None,
        "la pile de la rafale est gardée EN ATTENTE")
verifie(not demandes,
        "la chaîne n'est pas sollicitée avant la fin de rafale (jalon 80)")
pomper(app.RAFALE_QUIET_S + 0.2)
verifie(len(demandes) == 1,
        f"fin de rafale : la chaîne est sollicitée SANS rendu (demandes : {len(demandes)})")
app.disp.vl_new = True
app._maj_lbl_vl()
verifie(len(rendus) == 1,
        f"puis UN SEUL rendu : l'image finale (rendus : {len(rendus)})")

# Sans chaîne active : la rafale rend chaque frame, comportement inchangé.
print("[6b] Rafale SANS chaîne : rendu immédiat inchangé")
app.var_vl_chroma.set(False)
app.disp.vl_chroma = False
app._vl_frames = None
app._rendu_differ = None
rendus.clear()
demandes.clear()
app._rendu_attente = None
app.q.put_nowait(message(10))
pomper(0.12)
verifie(len(rendus) == 1,
        f"aucune chaîne : la frame est rendue tout de suite (rendus : {len(rendus)})")
app._rendu_differ = None
app._vl_frames = None
app.camera = _CameraMuette()

# ============================================================================
# [7] VRAIE CHAÎNE : `demander_chaine()` soumet sans rendre + image AU BIT
# ============================================================================
print("[7] Vraie chaîne : soumission sans rendu, image finale identique au bit")
rng = np.random.default_rng(1)
img = np.clip(rng.normal(0.12, 0.02, (48, 64, 3)).astype(np.float32), 0.0, 1.0)
img[20:28, 24:32] = (0.55, 0.25, 0.35)
app.var_vl_chroma.set(False)          # la VRAIE chaîne est pilotée par `d`
app.disp.vl_chroma = False

d = DisplayProcessor()
d.stretch = "stf"
d.vl_chroma = True                    # étape réelle, bon marché sur 48×64
d.notify_new_stack()
d.demander_chaine(img)
verifie(d.vl_en_cours() and d._vl_job is not None,
        "`demander_chaine()` SOUMET le job au worker (sans passer par un rendu)")
verifie(d._vl_force is False,
        "le drapeau `notify_new_stack` est consommé par la soumission")
verifie(attendre(lambda: d.vl_new and not d.vl_en_cours(), 30.0),
        "la chaîne a publié son résultat (`vl_new`)")

_ancien_disp = app.disp
app.disp = d
app.last_show = img
app._last_disp = None
app._rendu_attente = None
app._rendre_et_afficher = vrai_rendu     # le VRAI renderer pour ce volet
d.vl_new = False
d.notify_new_stack()                     # nouvelle pile → nouvelle soumission
_differe = app._differe_rendu_frame({"frames": 1}, img)
verifie(_differe, "la frame est confiée à la chaîne (rendu différé)")
verifie(app._last_disp is None,
        "aucun pixel n'est dessiné par la soumission elle-même")
verifie(attendre(lambda: not d.vl_en_cours() and app._rendu_attente is None,
                 30.0),
        "le `vl_new` a déclenché le rendu de l'image finale")
ref = d.process(img, live=False)         # référence : même clé, cache
verifie(app._last_disp is not None and np.array_equal(app._last_disp, ref),
        "l'image finale du chemin différé est IDENTIQUE AU BIT à la référence")
verifie(not d.vl_en_cours(),
        "le rendu n'a pas relancé un calcul inutile (cache de la clé)")

app.disp = _ancien_disp
app._rendre_et_afficher = _compte_rendu

# ============================================================================
# [8] IMAGE D'ATTENTE : jamais affichée si une image est déjà à l'écran
# ============================================================================
print("[8] Image d'attente (blanche/STF) : l'image précédente est CONSERVÉE")
d2 = DisplayProcessor()
d2.stretch = "stf"
d2.vl_chroma = True
d2._vl_key = d2._vl_params() + (img.shape,)   # clé à jour : aucune soumission
d2._vl_result = None                          # aucun résultat pour cette clé
d2._vl_pending = False                        # aucun calcul en cours
app.disp = d2
app._rendre_et_afficher = vrai_rendu
precedent = np.full((48, 64, 3), 0.3, np.float32)
app._last_disp = precedent
app.last_show = img
perf.reinitialiser()
app._rendre_et_afficher(img, live=False)
verifie(app._last_disp is precedent,
        "l'image d'attente NE remplace PAS l'image précédente")
verifie(perf.instantane()["compteurs"].get("rendus_gardes", 0) == 1,
        "le rendu gardé est COMPTÉ (`rendus_gardes`)")
# Au tout premier rendu (aucune image), l'attente s'affiche quand même.
app._last_disp = None
app._rendre_et_afficher(img, live=False)
verifie(app._last_disp is not None,
        "au tout premier rendu, l'attente s'affiche (écran jamais vide)")
app.disp = _ancien_disp
app._rendre_et_afficher = _compte_rendu

# ============================================================================
# CONCLUSION
# ============================================================================
perf.desactiver()
root.destroy()
print("\n===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)
