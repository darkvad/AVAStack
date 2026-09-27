# -*- coding: utf-8 -*-
"""Test du jalon 12 — netteté live CÂBLÉE (Richardson-Lucy en direct).

Vérifie :
  [1] display.py : attributs par défaut, clé des réglages (VeraLux et netteté),
      reset() vide le résultat mémorisé ;
  [2] modes STF/manuel : solveur de netteté DÉDIÉ (thread réel) — image
      d'attente NON nette tant que le calcul n'est pas prêt, puis image nette
      conforme au module, cache par OBJET image (aucun recalcul au tick
      suivant), recalcul sur nouvel empilement ou nouveau réglage, REFUS
      mémorisé (aucune boucle de resoumissions — un solveur qui resoumettrait
      un job refusé 30 fois par seconde saturerait le CPU) ;
  [3] mode VeraLux : la netteté est la DERNIÈRE étape du solveur existant, donc
      bien APRÈS GraXpert/débruitage (gradient → débruitage → netteté →
      étirement) ; échec = repli + message, jamais d'image perdue ;
  [4] UI (fenêtre réelle) : cadre INDÉPENDANT du moteur d'étirement (visible en
      STF ET en VeraLux), case + curseur 1-10, vue « traitée » = netteté
      ignorée, étiquette qui dit l'état réel, persistance + restauration
      tolérante ;
  [5] sauvegarde « tel que vu » : netteté reproduite en PLEINE RÉSOLUTION (PSF
      mesurée sur le FICHIER, pas celle de l'aperçu), fichier DIFFÉRENT de la
      version sans netteté, et échec = sauvegarde abandonnée (jamais un
      fichier « presque comme vu »).

Nécessite un affichage. Exécution : python bancs/_test_sharp_live_jalon12.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import tempfile
import time
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
import avastack.processing.display as dp
import avastack.processing.sharpness as sh
import avastack.processing.denoise as dn
import avastack.processing.veralux as veralux
import avastack.external.live as gx_live

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def est_packe(w):
    """True si le widget est réellement affiché (masqué = pack_info lève)."""
    try:
        w.pack_info()
        return True
    except tk.TclError:
        return False


def champ(shape=(256, 256), sigma_px=1.5, nb=25, bruit=0.004, fond=0.002,
          amp=(0.05, 0.5), graine=3, marge=20):
    """Champ synthétique : nb étoiles gaussiennes de σ connu + bruit.

    σ = 1,5 px → FWHM ≈ 3,5 px : dans les bornes de stars.SIGMA_MIN/MAX, donc
    la netteté s'applique (mêmes conventions que _test_rl_jalon11.py, mais on
    ne vérifie ici QUE le câblage : la conformité de la formule RL et ses
    mesures sont le périmètre du test du jalon 11)."""
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(nb):
        y = int(rng.integers(marge, h - marge))
        x = int(rng.integers(marge, w - marge))
        a = float(rng.uniform(*amp))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    return np.clip(img, 0.0, 1.0)


def attendre_sh(d, timeout=20.0):
    """Attend la fin du calcul de netteté dédié (polling, 20 ms).

    DEUX conditions : le job soumis a été PRIS par le worker (`_sh_job` vidé)
    et plus aucun calcul en cours (`_sh_pending`) — un résultat mémorisé doit
    alors exister."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with d._sh_lock:
            if d._sh_job is None and not d._sh_pending:
                return d._sh_result is not None
        time.sleep(0.02)
    return False


def attendre_vl(d, timeout=60.0):
    """Attend la fin du job solveur VeraLux en cours (polling, 20 ms)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with d._vl_lock:
            if (d._vl_job is None and not d._vl_pending
                    and d._vl_result is not None):
                return True
        time.sleep(0.02)
    return False


IMG = champ()
IMG2 = champ(graine=7)
PSF = {"fwhm": 3.5, "nb": 25}      # PSF « du seeing » (mesure du jalon 10)

print("[1] display.py — attributs, clés de réglages, reset()")
d = dp.DisplayProcessor()
verifie(d.vl_sharp is False
        and d.vl_sharp_iterations == sh.ITERATIONS_DEFAUT
        and d.vl_seeing is None and d.sh_msg == "" and d._sh_result is None,
        "défauts : netteté désactivée, 5 itérations (réglage utile), aucune PSF")
k0 = d._vl_params()
d.vl_sharp = True
verifie(d._vl_params() != k0, "vl_sharp fait partie de la clé VeraLux")
k1 = d._vl_params()
d.vl_sharp_iterations = 3
verifie(d._vl_params() != k1, "les itérations font partie de la clé VeraLux")
verifie(d._sh_key() == (3, None), f"clé de netteté : itérations + PSF ({d._sh_key()})")
d.vl_seeing = dict(PSF)
verifie(d._sh_key() == (3, 3.5), "la PSF du seeing entre dans la clé de netteté")
d._sh_result = ((3, 3.5), IMG, IMG)
d._sh_soumis = (IMG, (3, 3.5))
d.reset()
verifie(d._sh_result is None and d._sh_soumis is None,
        "reset() vide le résultat et la soumission de la netteté")

print("[2] Modes STF/manuel : solveur de netteté DÉDIÉ (thread réel)")
appels = {"n": 0}
_reel = sh.deconvoluer


def compte(img, **kw):
    appels["n"] += 1
    return _reel(img, **kw)


sh.deconvoluer = compte
try:
    d = dp.DisplayProcessor()
    d.vl_sharp = True
    d.vl_sharp_iterations = 3
    d.vl_seeing = dict(PSF)
    out1 = d._process_nettete(IMG)
    verifie(out1 is IMG,
            "1er appel : image d'attente NON nette (le calcul vient d'être soumis)")
    verifie(attendre_sh(d), "calcul de netteté terminé (thread dédié)")
    out2 = d._process_nettete(IMG)
    attendu, err = _reel(IMG, iterations=3, mesure=d.vl_seeing)
    verifie(err == "" and float(np.max(np.abs(out2 - attendu))) < 1e-6,
            "image nette conforme au module (3 it, PSF du seeing mesuré)")
    verifie(not np.allclose(out2, IMG),
            "le résultat est bien MODIFIÉ (un repli silencieux ne passerait pas)")
    verifie(appels["n"] == 1, f"calcul fait UNE fois (appels={appels['n']})")
    verifie(d._process_nettete(IMG) is out2 and appels["n"] == 1,
            "même image + mêmes réglages : résultat mémorisé, aucun recalcul")

    out3 = d._process_nettete(IMG2)
    verifie(out3 is IMG2,
            "nouvel empilement : image d'attente (jamais l'image nette de l'autre)")
    verifie(attendre_sh(d) and appels["n"] == 2, "nouvelle image → recalcul")
    verifie(not np.allclose(d._process_nettete(IMG2), IMG2),
            "…et le nouvel empilement est bien netté")

    d.vl_sharp_iterations = 5
    verifie(d._process_nettete(IMG2) is IMG2 and attendre_sh(d)
            and appels["n"] == 3, "itérations changées → recalcul")
    attendu5, _ = _reel(IMG2, iterations=5, mesure=d.vl_seeing)
    verifie(float(np.max(np.abs(d._process_nettete(IMG2) - attendu5))) < 1e-6,
            "le nouveau réglage (5 it) est bien celui appliqué")

    sans = np.full((128, 128), 0.002, dtype=np.float32)
    d.vl_seeing = {"nb": 0, "fwhm": None}
    n_avant = appels["n"]
    verifie(d._process_nettete(sans) is sans and attendre_sh(d),
            "PSF inutilisable : netteté refusée (image d'entrée rendue)")
    verifie("inactive" in d.sh_msg and d.sh_new,
            f"raison explicite remontée à l'UI (« {d.sh_msg} »)")
    verifie(np.array_equal(d._process_nettete(sans), sans),
            "refus MÉMORISÉ : image d'entrée rendue telle quelle (copie de travail)")
    verifie(appels["n"] == n_avant + 1,
            "…sans resoumettre : le refus ne boucle pas")
    for _ in range(5):
        d._process_nettete(sans)
    verifie(appels["n"] == n_avant + 1, "5 ticks d'UI de plus : toujours aucun recalcul")

    d.vl_sharp = False
    d.vl_seeing = dict(PSF)
    verifie(d._process_nettete(IMG2) is IMG2 and appels["n"] == n_avant + 1,
            "case décochée : la netteté n'est plus appelée du tout")

    # process() : la netteté est appliquée en STF/manuel, PAS en VeraLux (où
    # c'est le solveur VeraLux qui s'en charge — jamais deux fois).
    appels_pn = {"n": 0}
    reel_pn = d._process_nettete

    def pn(img):
        appels_pn["n"] += 1
        return reel_pn(img)

    d._process_nettete = pn
    d.vl_sharp = True
    d.process(IMG2)
    verifie(appels_pn["n"] == 1, "process() applique la netteté en mode STF")
    if veralux.moteur_disponible():
        d.stretch = "veralux"
        d.process(IMG2)
        verifie(appels_pn["n"] == 1,
                "process() NE la réapplique PAS en mode VeraLux (le solveur l'a fait)")
        d.stretch = "stf"
    else:
        print("  (moteur VeraLux absent : vérification du mode VeraLux sautée)")
    d.vl_sharp = False
    d.process(IMG2)
    verifie(appels_pn["n"] == 1, "case décochée : process() ne l'appelle pas")
    d._process_nettete = reel_pn

    # EXCEPTION du module : le solveur DÉDIÉ doit rester VIVANT — un thread
    # mort figerait l'aperçu sur l'image d'attente pour toujours.
    def sh_leve(img, **kw):
        raise RuntimeError("panne dédiée simulée")


    sh.deconvoluer = sh_leve
    d.vl_sharp = True
    d.vl_seeing = dict(PSF)
    IMG3 = champ(graine=11)
    verifie(d._process_nettete(IMG3) is IMG3 and attendre_sh(d, timeout=20.0),
            "exception du module : le solveur dédié est TOUJOURS VIVANT")
    verifie("panne dédiée simulée" in d.sh_msg,
            f"exception signalée à l'UI, jamais avalée ({d.sh_msg!r})")
    verifie(np.array_equal(d._process_nettete(IMG3), IMG3),
            "…et l'image d'attente est rendue telle quelle (repli sûr)")
    d.vl_sharp = False
finally:
    sh.deconvoluer = _reel

print("[3] Mode VeraLux : netteté = DERNIÈRE étape du solveur existant")
d2 = dp.DisplayProcessor()
d2.stretch = "veralux"
d2.vl_mode_res = veralux.MODE_LOG_D
d2.vl_log_d = 1.2
d2.vl_seeing = dict(PSF)
params2 = dict(mode=d2.vl_mode_res, target_bg=d2.vl_target_bg,
               log_d=d2.vl_log_d, profil=d2.vl_profil)
d2._vl_job = (IMG.copy(), params2, "k1", (False, ""), (False, "nlm", 0.5),
              (True, 3))
d2._vl_pending = True
d2._vl_wake.set()
verifie(attendre_vl(d2), "job solveur VeraLux terminé")
net, err_net = _reel(IMG, iterations=3, mesure=d2.vl_seeing)
attendu, _, _ = veralux.etirer(net, **params2)
verifie(err_net == "" and float(np.max(np.abs(d2._vl_result[1] - attendu))) < 1e-6,
        "netteté appliquée AVANT l'étirement, résultat conforme")
verifie(d2.sh_msg == "", f"aucun message en cas de succès ({d2.sh_msg!r})")

# ORDRE de la chaîne : GraXpert live (simulé) PUIS débruitage PUIS netteté.
_gx_reel = gx_live.appliquer
gx_live.appliquer = lambda img, cmd, timeout=gx_live.TIMEOUT_S: \
    (np.flipud(img), "")
try:
    d2._vl_job = (IMG.copy(), params2, "k2", (True, "fake"),
                  (True, "ondelettes", 0.5), (True, 3))
    d2._vl_pending = True
    d2._vl_wake.set()
    verifie(attendre_vl(d2), "job GraXpert + débruitage + netteté terminé")
    src2 = dn.denoiser(np.flipud(IMG), "ondelettes", 0.5)[0]
    net2, _ = _reel(src2, iterations=3, mesure=d2.vl_seeing)
    attendu2, _, _ = veralux.etirer(net2, **params2)
    verifie(float(np.max(np.abs(d2._vl_result[1] - attendu2))) < 1e-6,
            "ordre de la chaîne : gradient → débruitage → NETTETÉ → étirement")
    verifie(d2.vl_error == "", f"aucune erreur signalée ({d2.vl_error!r})")
finally:
    gx_live.appliquer = _gx_reel


# Échec de la netteté : repli (l'image est étirée quand même), message clair.
def net_plante(img, **kw):
    return np.asarray(img), "boom"


sh.deconvoluer = net_plante
try:
    d2._vl_job = (IMG.copy(), params2, "k3", (False, ""), (False, "nlm", 0.5),
                  (True, 3))
    d2._vl_pending = True
    d2._vl_wake.set()
    verifie(attendre_vl(d2), "job terminé malgré l'échec de la netteté")
    verifie(d2.vl_error.startswith("Netteté live :"),
            f"erreur signalée à l'UI ({d2.vl_error!r})")
    verifie(d2.sh_msg == "boom", "message de la netteté remonté au cadre dédié")
    ref, _, _ = veralux.etirer(IMG, **params2)
    verifie(float(np.max(np.abs(d2._vl_result[1] - ref))) < 1e-6,
            "repli : l'image EST étirée, jamais figée sur une erreur")
    # La netteté est inactive si le module ne l'applique pas : le job suivant
    # avec la CASE DÉCOCHÉE ne doit même pas appeler le module.
    appels3 = {"n": 0}


    def compte3(img, **kw):
        appels3["n"] += 1
        return _reel(img, **kw)


    sh.deconvoluer = compte3
    d2._vl_job = (IMG.copy(), params2, "k4", (False, ""), (False, "nlm", 0.5),
                  (False, 3))
    d2._vl_pending = True
    d2._vl_wake.set()
    verifie(attendre_vl(d2) and appels3["n"] == 0,
            "case décochée : le solveur VeraLux ne calcule AUCUNE netteté")

    # EXCEPTION du module : le solveur VeraLux doit rester VIVANT (un thread
    # mort figerait l'aperçu VeraLux pour toujours).
    def net_leve(img, **kw):
        raise RuntimeError("panne VeraLux simulée")


    sh.deconvoluer = net_leve
    d2._vl_job = (IMG.copy(), params2, "k5", (False, ""), (False, "nlm", 0.5),
                  (True, 3))
    d2._vl_pending = True
    d2._vl_wake.set()
    verifie(attendre_vl(d2, timeout=20.0),
            "exception du module : le solveur VeraLux est TOUJOURS VIVANT")
    verifie("panne VeraLux simulée" in d2.vl_error,
            f"exception signalée, jamais avalée ({d2.vl_error!r})")
    ref5, _, _ = veralux.etirer(IMG, **params2)
    verifie(float(np.max(np.abs(d2._vl_result[1] - ref5))) < 1e-6,
            "…et l'image est quand même étirée (repli sûr)")
finally:
    sh.deconvoluer = _reel

print("[4] UI (fenêtre réelle) : cadre indépendant, case, curseur, vue « traitée »")
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))   # jamais le vrai
ui.CONFIG = {}
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
verifie(est_packe(app.frm_sharp), "cadre « Netteté live » visible dès le départ")
verifie(app.var_vl_sharp.get() is False and app.disp.vl_sharp is False,
        "netteté live désactivée par défaut")
verifie(app.disp.vl_sharp_iterations == sh.ITERATIONS_DEFAUT == 5
        and abs(app.var_vl_sharp_iter.get() - 5) < 1e-9,
        "itérations par défaut : 5 (3-5 = réglage utile)")
verifie("désactivée" in app.lbl_sharp.cget("text"),
        f"étiquette initiale ({app.lbl_sharp.cget('text')!r})")
app.var_moteur.set("VeraLux")
app._on_moteur()
root.update_idletasks()
verifie(est_packe(app.frm_veralux) and est_packe(app.frm_sharp),
        "cadre netteté visible AUSSI en mode VeraLux (indépendant du moteur)")
app.var_moteur.set("STF")
app._on_moteur()
root.update_idletasks()
verifie(est_packe(app.frm_stf) and est_packe(app.frm_sharp),
        "…et en mode STF : la netteté n'est plus enfermée dans le cadre VeraLux")
app.var_vl_sharp.set(True)
app._on_vl_sharp()
verifie(app.disp.vl_sharp is True, "case cochée : netteté active (vue « empilement »)")
app.var_vl_sharp_iter.set(3)
app._on_vl_sharp()
verifie(app.disp.vl_sharp_iterations == 3, "curseur : itérations propagées au solveur")
verifie("3 it" in app.lbl_sharp.cget("text"),
        f"étiquette d'état ({app.lbl_sharp.cget('text')!r})")
app.var_view.set("traitée")
app._on_view()
verifie(app.disp.vl_sharp is False,
        "vue « traitée » : netteté DÉSACTIVÉE (pas de 2e traitement)")
verifie("traitée" in app.lbl_sharp.cget("text"),
        "étiquette : netteté ignorée en vue « traitée »")
app.var_view.set("pile")
app._on_view()
verifie(app.disp.vl_sharp is True, "retour vue empilement : réactivée")
app.var_vl_sharp_iter.set(99)      # hors bornes : jamais appliqué en silence
app._on_vl_sharp()
verifie(app.disp.vl_sharp_iterations == sh.ITERATIONS_MAX
        and abs(app.var_vl_sharp_iter.get() - sh.ITERATIONS_MAX) < 1e-9,
        f"itérations hors bornes ramenées au plafond dur ({sh.ITERATIONS_MAX})")
app.var_vl_sharp_iter.set(3)
app._on_vl_sharp()
app._sauver_config_app()
derniere = sauvegardes[-1]
verifie(derniere.get("vl_sharp") is True
        and derniere.get("vl_sharp_iterations") == 3,
        "clés vl_sharp / vl_sharp_iterations écrites dans config.json")

print("[5] Sauvegarde « tel que vu » : netteté reproduite en pleine résolution")
tmp = tempfile.mkdtemp(prefix="avastack_test_sh12_")
f_net = os.path.join(tmp, "avec_nettete.fits")
f_brut = os.path.join(tmp, "sans_nettete.fits")
reglages = dict(stretch="stf", auto=True, sigma_k=2.8, target=0.25,
                black=0.0, white=1.0, gamma=1.0, saturation=1.0,
                vl_sharp=True, vl_sharp_iterations=3)
app.asseen_busy = True
app._save_asseen_thread(f_net, "pile", IMG.copy(), reglages, app._session)
verifie(app.asseen_result == f_net and os.path.exists(f_net),
        "sauvegarde « tel que vu » AVEC netteté OK (PSF mesurée sur le fichier)")
reglages.pop("vl_sharp")
app.asseen_busy = True
app._save_asseen_thread(f_brut, "pile", IMG.copy(), reglages, app._session)
verifie(app.asseen_result == f_brut and os.path.exists(f_brut),
        "sauvegarde « tel que vu » SANS netteté OK")
from avastack.images import load_image
a, b = load_image(f_net), load_image(f_brut)
verifie(a.shape == b.shape and not np.allclose(a, b, atol=1e-6),
        "le fichier avec netteté DIFFÈRE bien de la version brute")
verifie(a.shape[:2] == IMG.shape,
        "mêmes dimensions : le fichier est en pleine résolution")

sh.deconvoluer = net_plante          # échec = sauvegarde abandonnée
try:
    reglages["vl_sharp"] = True
    app.asseen_busy = True
    f_echec = os.path.join(tmp, "echec.fits")
    app._save_asseen_thread(f_echec, "pile", IMG.copy(), reglages, app._session)
    verifie(app.asseen_result.startswith("ERREUR: Netteté live"),
            f"échec de la netteté → sauvegarde abandonnée ({app.asseen_result!r})")
    verifie(not os.path.exists(f_echec),
            "…et AUCUN fichier écrit (jamais une image « presque comme vue »)")
finally:
    sh.deconvoluer = _reel
root.destroy()

print("[6] Persistance : restauration (tolérante, jamais de surprise)")
ui.CONFIG = {"vl_sharp": True, "vl_sharp_iterations": 3}
root = tk.Tk()
app2 = ui.App(root)
root.update_idletasks()
verifie(app2.var_vl_sharp.get() is True and app2.disp.vl_sharp is True
        and app2.disp.vl_sharp_iterations == 3
        and abs(app2.var_vl_sharp_iter.get() - 3) < 1e-9,
        "restauration complète (case, itérations, curseur)")
root.destroy()

ui.CONFIG = {"vl_sharp": True, "vl_sharp_iterations": 99}    # aberrante
root = tk.Tk()
app3 = ui.App(root)
root.update_idletasks()
verifie(app3.var_vl_sharp.get() is True
        and app3.disp.vl_sharp_iterations == sh.ITERATIONS_DEFAUT
        and abs(app3.var_vl_sharp_iter.get() - sh.ITERATIONS_DEFAUT) < 1e-9,
        "restauration tolérante : 99 (hors bornes) → défaut 5, case restaurée")
root.destroy()

ui.CONFIG = {}
root = tk.Tk()
app4 = ui.App(root)
root.update_idletasks()
verifie(app4.var_vl_sharp.get() is False and app4.disp.vl_sharp is False,
        "clé absente → netteté désactivée (jamais de surprise)")
root.destroy()

print()
print("JALON 12 : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)
