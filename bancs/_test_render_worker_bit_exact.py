# -*- coding: utf-8 -*-
"""Banc étape 1b (branche `OptimisationUI`) — RENDU HORS FIL Tk.

LE DÉFAUT MESURÉ (Phase 0 puis `perf-4.json`, 637 s, 48 frames) : après 1a il
ne restait plus qu'UN rendu par frame, mais ce rendu pesait **102 s sur le fil
Tk** (51 rendus × ~2 000 ms à pleine résolution) — `ui_tick` restait à 48 % du
temps mural et la fenêtre était immobile deux secondes à chaque image.

CE QUE CE BANC VERROUILLE
  [1] le FIL existe, il tourne, il est DÉMON, et le mode normal est
      asynchrone (`immediat` faux) ;
  [2] image finale **IDENTIQUE AU BIT** à la référence `process()`, et les
      DEUX jeux de bacs identiques à ceux de `_histogrammes_purs` ;
  [3] **UN SEUL ÉCRIVAIN de l'EMA du STF** : espion sur `_auto_params` — les
      appels viennent TOUS du fil de rendu, jamais du fil d'interface, et les
      stats lissées après 3 frames sont les mêmes que la référence
      synchrone (au bit) ;
  [4] le fil Tk NE BLOQUE PLUS : `process()` lent (60 ms) × 20 frames ⇒ aucun
      tour de `_tick_corps` long, et l'image finale reste exacte ;
  [5] « LE DERNIER GAGNE » : les demandes en trop sont ÉCRASÉES (compteur) et
      c'est bien la DERNIÈRE image qui s'affiche, au bit ;
  [6] PURGE (`_vider_ecran`, session neuve) : un résultat calculé AVANT le
      reset ne repeint jamais l'écran (génération) ;
  [7] `hist=False` : aucun recalcul d'histogramme (les bacs en place restent) ;
  [8] fil ARRÊTÉ (fermeture) : repli sur place, image identique au bit ;
  [9] `_on_close` ARRÊTE le fil de rendu (chemin réel de fermeture de la
      fenêtre, vérifié sur une seconde application).

Exécution : python bancs/_test_render_worker_bit_exact.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import threading
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui
from avastack import perf
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


def attendre(cond, limite=20.0):
    """Pompe Tk jusqu'à ce que `cond()` soit vraie (fil de rendu en fond)."""
    t0 = time.time()
    while time.time() - t0 < limite:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def image_essai(graine=0, decalage=0.0):
    """Petite image couleur LINÉAIRE (>0 partout : pas de bord noir suspect)."""
    rng = np.random.default_rng(graine)
    img = np.clip(rng.normal(0.12, 0.02, (48, 64, 3)).astype(np.float32), 0, 1)
    img[20:28, 24:32] = (0.55 + decalage, 0.25 + decalage, 0.35 + decalage)
    return img


def meme_hist(a, b):
    """Deux jeux de bacs identiques (comptes au bit + même axe)."""
    if a is None or b is None:
        return a is b
    if len(a[0]) != len(b[0]) or abs(float(a[1]) - float(b[1])) > 1e-12:
        return False
    return all(np.array_equal(x, y) for x, y in zip(a[0], b[0]))


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


def nouveau_moteur(auto=True):
    """Moteur d'affichage PROPRE (aucune stats, aucun cache hérité)."""
    d = DisplayProcessor()
    d.stretch = "stf"
    d.auto = bool(auto)
    if not auto:
        d.black, d.white = 0.0, 1.0
    return d


# ============================================================================
# [1] LE FIL EXISTE ET TOURNE
# ============================================================================
print("[1] Le fil de rendu existe, il tourne, il est DÉMON")
verifie(getattr(app, "rendu", None) is not None,
        "`App` crée le fil de rendu dans son constructeur (`app.rendu`)")
verifie(app.rendu.vivant(), "le fil de rendu est VIVANT")
verifie(app.rendu._fil.daemon,
        "le fil est DÉMON (il ne retient jamais la fermeture de l'application)")
verifie(app.rendu._fil.name == "rendu",
        "le fil porte un nom explicite (journal, pile du Guet)")
verifie(app.rendu.immediat is False,
        "en marche normale, le rendu n'est PAS immédiat (il part au fil)")
verifie(app.rendu.ident() is not None
        and app.rendu.ident() != threading.get_ident(),
        "le fil de rendu n'est pas le fil d'interface")

# ============================================================================
# [2] IMAGE FINALE AU BIT (et les deux jeux de bacs)
# ============================================================================
print("[2] Image finale IDENTIQUE AU BIT à la référence `process()`")
img = image_essai(1)
d1 = nouveau_moteur(auto=True)
ref = nouveau_moteur(auto=True)
attendu = ref.process(img, live=True)      # référence SYNCHRONE (même état)
app.disp = d1
app._last_disp = None
app._hist_brut = app._hist_sortie = None
app.rendu.purger()
app._rendre_et_afficher(img, live=True, motif="banc")
verifie(app._last_disp is None,
        "la demande ne dessine RIEN elle-même (le calcul part au fil)")
verifie(attendre(lambda: app._last_disp is not None, 20.0),
        "le résultat arrive au fil Tk (pris par `_tick`)")
verifie(app._last_disp is not None
        and app._last_disp.dtype == np.uint8
        and attendu.dtype == np.uint8,
        "l'image publiée est bien un uint8 (prête pour PhotoImage)")
verifie(app._last_disp is not None and np.array_equal(app._last_disp, attendu),
        "l'image du fil de rendu est IDENTIQUE AU BIT à `process()`")
# Les DEUX bandes de l'histogramme, calculées dans le même fil que `process()`
# (la bande « sortie du moteur » lit `dernier_brut_niveaux`, écrit par lui).
verifie(meme_hist(app._hist_brut, ui.App._hist_canaux(img)),
        "bande « brut (linéaire) » : bacs identiques au calcul de référence")
verifie(meme_hist(app._hist_sortie,
                  ui.App._hist_canaux(d1.dernier_brut_niveaux,
                                      plage=(0.0, 1.0))),
        "bande « sortie du moteur » : bacs identiques au calcul de référence")
verifie(app.rendu.en_attente() is False,
        "plus rien en attente après application")

# ============================================================================
# [3] UN SEUL ÉCRIVAIN DE L'EMA DU STF
# ============================================================================
print("[3] UN SEUL ÉCRIVAIN de l'EMA du STF (espion sur `_auto_params`)")
d2 = nouveau_moteur(auto=True)
ref2 = nouveau_moteur(auto=True)
vus = []
vrai_auto = d2._auto_params


def _espion(src, live=True, _v=vrai_auto):
    vus.append((threading.get_ident(), bool(live)))
    return _v(src, live=live)


d2._auto_params = _espion
app.disp = d2
app._last_disp = None
app.rendu.purger()
plein = image_essai(2)
attendu2 = None
for _ in range(3):
    app._rendre_et_afficher(plein, live=True, motif="banc")
    attendre(lambda: not app.rendu.en_attente(), 20.0)
    attendu2 = ref2.process(plein, live=True)
verifie(len(vus) == 3,
        f"3 frames ⇒ 3 passages dans `_auto_params` (obtenu : {len(vus)})")
verifie(vus and all(ident == app.rendu.ident() for ident, _ in vus),
        "TOUS les appels viennent du FIL DE RENDU")
verifie(not any(ident == threading.get_ident() for ident, _ in vus),
        "AUCUN appel depuis le fil d'interface (un seul écrivain)")
verifie(all(live for _, live in vus),
        "les frames font bien avancer le lissage temporel (`live=True`)")
verifie(d2._stats is not None and d2._stats == ref2._stats,
        "stats EMA lissées IDENTIQUES AU BIT à la référence synchrone")
verifie(app._last_disp is not None
        and attendu2 is not None and np.array_equal(app._last_disp, attendu2),
        "l'image après 3 frames est identique au bit à la référence")

# ============================================================================
# [4] LE FIL Tk NE BLOQUE PLUS (`process()` lent)
# ============================================================================
print("[4] Le fil Tk ne bloque plus pendant un calcul")
d3 = nouveau_moteur(auto=False)
vrai_proc = d3.process
durees = []
vrai_corps = app._tick_corps


def _corps_chrono():
    t = time.perf_counter()
    try:
        vrai_corps()
    finally:
        durees.append(time.perf_counter() - t)


app._tick_corps = _corps_chrono

# ---- 4a) RENDEZ-VOUS : un calcul BLOQUÉ ne bloque pas le fil d'interface.
# C'est la preuve sans ambiguïté (aucune mesure de temps) : si le rendu se
# faisait encore dans `_tick`, la fenêtre serait figée jusqu'au déblocage.
debut, fin = threading.Event(), threading.Event()


def _bloque(src, live=True, _v=vrai_proc):
    debut.set()
    fin.wait(5.0)                        # filet : le banc ne peut pas se figer
    return _v(src, live=live)


d3.process = _bloque
app.disp = d3
app._last_disp = None
app.rendu.purger()
app._rendre_et_afficher(image_essai(9), live=False, motif="banc")
verifie(debut.wait(5.0), "le fil de rendu a bien pris la demande")
ticks_avant = len(durees)
pomper(0.4)
verifie(len(durees) - ticks_avant >= 5,
        "…et le fil d'interface CONTINUE de tourner pendant le calcul "
        f"({len(durees) - ticks_avant} tours en 0,4 s)")
verifie(app._last_disp is None,
        "aucune image n'est publiée tant que le calcul n'est pas terminé")
fin.set()
verifie(attendre(lambda: app._last_disp is not None, 10.0),
        "l'image arrive dès que le calcul se termine")

# ---- 4b) 20 frames avec un rendu LENT (60 ms) : l'image finale reste exacte
def _lent(src, live=True, _v=vrai_proc):
    time.sleep(0.06)                     # simule ~2 s de rendu réel, en plus court
    return _v(src, live=live)


d3.process = _lent
app._last_disp = None
app.rendu.purger()
durees.clear()
derniere = None
for f in range(1, 21):
    derniere = image_essai(10 + f, decalage=0.001 * f)
    try:
        app.q.put_nowait(message(f, derniere))
    except Exception:                    # file pleine : la frame sera sautée
        pass
    pomper(0.02)
verifie(attendre(lambda: not app.rendu.en_attente(), 20.0),
        "les 20 frames ont toutes été traitées (fil vidé)")
pomper(0.2)
mesure = sorted(durees[3:] or durees)
mediane = mesure[len(mesure) // 2] if mesure else 0.0
verifie(bool(mesure) and mediane < 0.05,
        "le tour MÉDIAN de `_tick_corps` reste court "
        f"({mediane * 1000:.1f} ms ; le calcul est ailleurs)")
ref3 = nouveau_moteur(auto=False)
verifie(app._last_disp is not None and derniere is not None
        and np.array_equal(app._last_disp, ref3.process(derniere, live=False)),
        "l'image affichée est celle de la DERNIÈRE frame, au bit")


# ============================================================================
# [5] « LE DERNIER GAGNE » : demandes écrasées, dernière image affichée
# ============================================================================
print("[5] « Le dernier gagne » : les demandes en trop sont ÉCRASÉES")
perf.activer()
perf.reinitialiser()
app._last_disp = None
app.rendu.purger()
images = [image_essai(30 + k, decalage=0.002 * k) for k in range(5)]
for im in images:
    app._rendre_et_afficher(im, live=False, motif="banc")
verifie(perf.instantane()["compteurs"].get("rendus_ecrases", 0) >= 1,
        "des demandes ont été ÉCRASÉES (aucune file d'attente, "
        "aucune backpressure)")
attendre(lambda: not app.rendu.en_attente(), 20.0)
pomper(0.2)
ref4 = nouveau_moteur(auto=False)
verifie(app._last_disp is not None
        and np.array_equal(app._last_disp, ref4.process(images[-1], live=False)),
        "c'est bien la DERNIÈRE image qui est à l'écran, au bit")
verifie(perf.instantane()["compteurs"].get("rendus", 0) >= 1,
        "les rendus produits par le FIL sont comptés (`rendus`)")
verifie("fil_rendu" in perf.instantane().get("chronos", {}),
        "le temps du fil de rendu est mesuré (`fil_rendu`)")

# ============================================================================
# [6] PURGE : aucun résultat tardif ne repeint l'écran
# ============================================================================
print("[6] Purge (`_vider_ecran`) : un calcul d'AVANT ne réapparaît jamais")
app._rendre_et_afficher(image_essai(40), live=False, motif="banc")
time.sleep(0.02)                     # le calcul (60 ms) est EN VOL
app._vider_ecran("banc")             # purge : génération invalidée
verifie(attendre(lambda: not app.rendu.en_attente(), 20.0),
        "le calcul en vol s'est terminé (rien ne reste bloqué)")
verifie(app._last_disp is None,
        "aucune image n'est réapparue après l'effacement (génération)")
verifie(perf.instantane()["compteurs"].get("rendus_perimes", 0) >= 1,
        "le résultat périmé est COMPTÉ (`rendus_perimes`)")

# ============================================================================
# [7] `hist=False` : aucun recalcul d'histogramme
# ============================================================================
print("[7] `hist=False` : les bacs en place ne sont pas recalculés")
marqueur = ("bacs inchangés", 1.0)
app._hist_brut = marqueur
app._hist_sortie = marqueur
app._rendre_et_afficher(image_essai(50), live=False, hist=False, motif="banc")
attendre(lambda: not app.rendu.en_attente(), 20.0)
pomper(0.1)
verifie(app._hist_brut is marqueur and app._hist_sortie is marqueur,
        "aucun recalcul d'histogramme (les bacs posés sont restés)")
verifie(app._last_disp is not None, "l'image, elle, a bien été rendue")

# ============================================================================
# [8] FIL ARRÊTÉ (fermeture) : repli sur place, image identique au bit
# ============================================================================
print("[8] Fil arrêté : le rendu se fait sur place, image identique au bit")
app.rendu.arreter()
verifie(not app.rendu.vivant(), "le fil de rendu est ARRÊTÉ (`arreter()`)")
d5 = nouveau_moteur(auto=False)
ref5 = nouveau_moteur(auto=False)
app.disp = d5
img5 = image_essai(60)
app._last_disp = None
app._rendre_et_afficher(img5, live=False, motif="banc")
verifie(app._last_disp is not None,
        "sans fil, le rendu est fait SUR PLACE (aucune image perdue)")
verifie(app._last_disp is not None
        and np.array_equal(app._last_disp, ref5.process(img5, live=False)),
        "…et il est IDENTIQUE AU BIT au rendu du fil")

# ============================================================================
# [9] FERMETURE DE LA FENÊTRE : le fil est arrêté par `_on_close`
# ============================================================================
print("[9] Fermeture (`_on_close`) : le fil de rendu est arrêté")
root2 = tk.Tk()
root2.withdraw()
app2 = ui.App(root2)
verifie(app2.rendu.vivant(), "une seconde application démarre bien son fil")
_erreur_close = ""
try:
    app2._on_close()                     # chemin RÉEL de fermeture
except Exception as exc:                 # noqa: BLE001 (diagnostic du banc)
    _erreur_close = f"{type(exc).__name__}: {exc}"
verifie(not _erreur_close, f"`_on_close` s'exécute sans erreur ({_erreur_close})")
verifie(not app2.rendu.vivant(), "la fermeture ARRÊTE le fil de rendu")

# ============================================================================
# CONCLUSION
# ============================================================================
perf.desactiver()
root.destroy()
print("\n===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)
