# -*- coding: utf-8 -*-
"""Test du jalon 9 (remis le 16/09/2026) — débruitage LIVE (algorithmes
locaux) dans le solveur VeraLux.

Vérifie :
  - display.py : attributs par défaut, clé des réglages (vl_denoise*),
    reset() vide le cache ;
  - thread solveur RÉEL : chaîne stack → GraXpert live (stub) → débruitage
    local → étirement VeraLux ; cache par (empreinte image, méthode, force) ;
    erreur non fatale (repli) ;
  - UI (fenêtre réelle, config.json simulé) : case + méthode + force ; vue
    « traitée » désactive le débruitage live ; force invalide tolérée ;
  - sauvegarde « tel que vu » : débruitage reproduit en pleine résolution ;
  - persistance : clés vl_denoise* écrites ; restauration tolérante.

Nécessite un affichage. Exécution : python _test_denoise_live_jalon9.py

NB (jalon 12, 16/09/2026) : le job du solveur VeraLux est passé de 5 à 6
éléments — les réglages de la NETTETÉ live (jalon 12) s'y ajoutent en
dernier : (image, params, clé, (gx…), (dn…), (netteté active, itérations)).
Ce test pilote le solveur avec la netteté INACTIVE, son périmètre (le
débruitage) est donc inchangé.
"""
import os
import sys
import tempfile
import time
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
import avastack.processing.display as dp
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


def attendre(disp, timeout=20.0):
    """Attend la fin du job solveur en cours (polling, 50 ms).

    TROIS conditions : le job soumis a été PRIS par le worker (`_vl_job`
    vidé — sinon le résultat du job PRÉCÉDENT ferait croire à une fin
    immédiate), plus aucun calcul en cours (`_vl_pending`) et un résultat
    disponible."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with disp._vl_lock:
            if (disp._vl_job is None and not disp._vl_pending
                    and disp._vl_result is not None):
                return True
        time.sleep(0.05)
    return False


# Image linéaire de test : fond bruité + étoiles gaussiennes (comme jalon 8).
rng = np.random.default_rng(42)
IMG = np.full((256, 256), 0.001, dtype=np.float32)
IMG += rng.normal(0.0, 0.002, IMG.shape).astype(np.float32)
yy, xx = np.mgrid[0:256, 0:256]
for (cy, cx, amp) in ((80, 100, 0.5), (150, 180, 0.3), (120, 60, 0.2)):
    IMG += (amp * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 6.0)
            ).astype(np.float32)
IMG = np.clip(IMG, 0.0, 1.0)

PARAMS = dict(mode=veralux.MODE_LOG_D, log_d=1.2, profil="Rec.709")

print("[1] display.py — attributs, clé des réglages, reset()")
disp = dp.DisplayProcessor()
verifie(disp.vl_denoise is False and disp.vl_denoise_methode == "nlm"
        and abs(disp.vl_denoise_force - 0.5) < 1e-9
        and disp._dn_cache is None,
        "défauts : débruitage live désactivé, nlm (le plus homogène), 0.5")
k0 = disp._vl_params()
disp.vl_denoise = True
verifie(disp._vl_params() != k0, "vl_denoise fait partie de la clé des réglages")
k1 = disp._vl_params()
disp.vl_denoise_methode = "ondelettes"
verifie(disp._vl_params() != k1, "la méthode fait partie de la clé")
disp.vl_denoise_methode = "nlm"
disp.vl_denoise_force = 0.8
verifie(disp._vl_params() != k1, "la force fait partie de la clé")
disp.vl_denoise_force = 0.5
disp._dn_cache = ("x", IMG)
disp.reset()
verifie(disp._dn_cache is None, "reset() vide le cache de débruitage live")

print("[2] Thread solveur RÉEL : chaîne + cache + repli")
verifie(veralux.moteur_disponible(), "moteur VeraLux disponible (test complet)")
appels = {"n": 0}
_denoiser_reel = dn.denoiser


def dn_compte(img, methode, force):
    appels["n"] += 1
    return _denoiser_reel(img, methode, force)


dn.denoiser = dn_compte

disp._vl_job = (IMG.copy(), PARAMS, "k1", (False, ""), (True, "ondelettes", 0.5),
                (False, 5))
disp._vl_pending = True
disp._vl_wake.set()
verifie(attendre(disp), "job solveur terminé")
res_dn = disp._vl_result[1]
attendu, _, _ = veralux.etirer(_denoiser_reel(IMG, "ondelettes", 0.5)[0],
                               **PARAMS)
verifie(float(np.max(np.abs(res_dn - attendu))) < 1e-6,
        "débruitage appliqué AVANT l'étirement (résultat conforme)")
verifie(appels["n"] == 1, f"débruitage calculé une fois (appels={appels['n']})")

# Cache : même image + mêmes réglages → PAS de recalcul. Le job IDENTIQUE
# est réellement resoumis (l'étirement VeraLux est donc recalculé) : seule
# la clé de cache (empreinte image, méthode, force) évite le débruitage.
disp._vl_job = (IMG.copy(), PARAMS, "k1", (False, ""),
                (True, "ondelettes", 0.5), (False, 5))
disp._vl_pending = True
disp._vl_wake.set()
verifie(attendre(disp), "2e job (identique) terminé")
verifie(appels["n"] == 1, "cache : même (image, méthode, force) → PAS de recalcul")

# Force changée → recalcul (le cache est indexé aussi sur la force).
disp._vl_job = (IMG.copy(), PARAMS, "k1", (False, ""), (True, "ondelettes", 0.6),
                (False, 5))
disp._vl_pending = True
disp._vl_wake.set()
verifie(attendre(disp) and appels["n"] == 2, "force changée → recalcul")

# ORDRE de la chaîne : GraXpert live (simulé) AVANT le débruitage.
_gx_reel = gx_live.appliquer
gx_live.appliquer = lambda img, cmd, timeout=gx_live.TIMEOUT_S: \
    (np.flipud(img), "")
try:
    disp._vl_job = (IMG.copy(), PARAMS, "k2", (True, "fake"),
                    (True, "ondelettes", 0.5), (False, 5))
    disp._vl_pending = True
    disp._vl_wake.set()
    verifie(attendre(disp), "job avec GraXpert live terminé")
    attendu2, _, _ = veralux.etirer(
        _denoiser_reel(np.flipud(IMG), "ondelettes", 0.5)[0], **PARAMS)
    verifie(float(np.max(np.abs(disp._vl_result[1] - attendu2))) < 1e-6,
            "ordre de la chaîne : GraXpert live AVANT le débruitage")
    verifie(disp.vl_error == "", "aucune erreur signalée (GX + DN)")
finally:
    gx_live.appliquer = _gx_reel


# Erreur non fatale : débruitage en échec → repli (image étirée quand même).
def dn_plante(img, methode, force):
    return np.asarray(img), "boom"


dn.denoiser = dn_plante
disp._vl_job = (IMG.copy(), PARAMS, "k3", (False, ""), (True, "nlm", 0.5),
                (False, 5))
disp._vl_pending = True
disp._vl_wake.set()
verifie(attendre(disp), "job terminé malgré l'erreur de débruitage")
verifie(disp.vl_error.startswith("Débruitage live :"),
        f"erreur signalée ({disp.vl_error!r})")
ref, _, _ = veralux.etirer(IMG, **PARAMS)
verifie(float(np.max(np.abs(disp._vl_result[1] - ref))) < 1e-6,
        "repli : l'image EST étirée (jamais figée)")
dn.denoiser = _denoiser_reel

print("[3] UI (fenêtre réelle) + vue « traitée » + force invalide")
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))  # jamais le vrai
ui.CONFIG = {}
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
verifie(app.var_vl_dn.get() is False and app.disp.vl_denoise is False,
        "débruitage live désactivé par défaut")
verifie(app.var_vl_dn_methode.get() == "Non-local means",
        "méthode par défaut : Non-local means (le plus homogène)")
app.var_moteur.set("VeraLux")
app._on_moteur()
root.update_idletasks()
app.var_vl_dn.set(True)
app._on_vl_denoise()
verifie(app.disp.vl_denoise is True,
        "case cochée : débruitage live actif (vue « empilement »)")
app.var_vl_dn_methode.set("Ondelettes à trous")
app._on_vl_denoise()
verifie(app.disp.vl_denoise_methode == "ondelettes",
        "méthode propagée au solveur")
app.var_vl_dn_force.set(0.8)
app._on_vl_denoise()
verifie(abs(app.disp.vl_denoise_force - 0.8) < 1e-9,
        "force propagée au solveur")
app.var_view.set("traitée")
app._on_view()
verifie(app.disp.vl_denoise is False,
        "vue « traitée » : débruitage live DÉSACTIVÉ (pas de 2e traitement)")
app.var_view.set("pile")
app._on_view()
verifie(app.disp.vl_denoise is True, "retour vue empilement : réactivé")
app.var_vl_dn_force.set("abc")           # saisie invalide : ne doit rien casser
root.update_idletasks()
verifie(abs(app.disp.vl_denoise_force - 0.8) < 1e-9,
        "saisie de force invalide ignorée (valeur conservée)")
app.var_vl_dn_force.set(0.5)
app._on_vl_denoise()

print("[4] Sauvegarde « tel que vu » : débruitage reproduit en pleine résolution")
tmp = tempfile.mkdtemp(prefix="avastack_test_dn9_")
grande = np.kron(IMG, np.ones((2, 2), dtype=np.float32))   # 512×512
f_dn = os.path.join(tmp, "avec_denoise.fits")
f_brut = os.path.join(tmp, "sans_denoise.fits")
reglages = dict(stretch="stf", auto=True, sigma_k=2.8, target=0.25,
                black=0.0, white=1.0, gamma=1.0, saturation=1.0,
                vl_denoise=True, vl_denoise_methode="ondelettes",
                vl_denoise_force=0.5)
app.asseen_busy = True
app._save_asseen_thread(f_dn, "pile", grande.copy(), reglages, app._session)
verifie(app.asseen_result == f_dn and os.path.exists(f_dn),
        "sauvegarde « tel que vu » avec débruitage live OK")
reglages.pop("vl_denoise")
app.asseen_busy = True
app._save_asseen_thread(f_brut, "pile", grande.copy(), reglages, app._session)
verifie(app.asseen_result == f_brut and os.path.exists(f_brut),
        "sauvegarde « tel que vu » sans débruitage OK")
from avastack.images import load_image
a, b = load_image(f_dn), load_image(f_brut)
verifie(a.shape == b.shape and not np.allclose(a, b, atol=1e-6),
        "le fichier avec débruitage DIFFÈRE bien de la version brute")

print("[5] Persistance + restauration tolérante")
app.var_vl_dn.set(True)
app.var_vl_dn_methode.set("Non-local means")
app._on_vl_denoise()
app.var_vl_dn_force.set(0.7)
app._on_vl_denoise()
app._sauver_config_app()
derniere = sauvegardes[-1]
verifie(derniere.get("vl_denoise") is True
        and derniere.get("vl_denoise_methode") == "nlm"
        and abs(derniere.get("vl_denoise_force", 0) - 0.7) < 1e-9,
        "clés vl_denoise / vl_denoise_methode / vl_denoise_force écrites")
root.destroy()

ui.CONFIG = {"vl_denoise": True, "vl_denoise_methode": "nlm",
             "vl_denoise_force": 0.7}
root = tk.Tk()
app2 = ui.App(root)
root.update_idletasks()
verifie(app2.var_vl_dn.get() is True and app2.disp.vl_denoise is True
        and app2.disp.vl_denoise_methode == "nlm"
        and abs(app2.disp.vl_denoise_force - 0.7) < 1e-9
        and app2.var_vl_dn_methode.get() == "Non-local means",
        "restauration complète (case, méthode, force)")
root.destroy()

ui.CONFIG = {"vl_denoise": True, "vl_denoise_methode": "inconnu",
             "vl_denoise_force": 5.0}
root = tk.Tk()
app3 = ui.App(root)
root.update_idletasks()
verifie(app3.var_vl_dn.get() is True
        and app3.disp.vl_denoise_methode == "nlm"
        and abs(app3.disp.vl_denoise_force - 0.5) < 1e-9,
        "restauration tolérante : méthode inconnue → nlm, force → 0.5")
root.destroy()

ui.CONFIG = {}
root = tk.Tk()
app4 = ui.App(root)
root.update_idletasks()
verifie(app4.var_vl_dn.get() is False and app4.disp.vl_denoise is False,
        "clé absente → débruitage live désactivé (jamais de surprise)")
root.destroy()

print()
print("JALON 9 : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)
