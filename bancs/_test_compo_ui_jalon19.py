# -*- coding: utf-8 -*-
"""Test du jalon 19 PHASE 3 — interface « Composition multi-filtres ».

Vérifie (App réelle, Tk) :
  [1] briques de phase 3 : FILTRES_USUELS / role_de_filtre et
      lire_filtre_fits (FITS avec/sans FILTER, PNG, fichier absent) ;
  [2] UI : cadre Composition (4 lignes rôle+dossier, radio L, gains),
      combobox composition → rôles, rôles remplis → composition déduite,
      gains bornés (virgule, hors bornes) ;
  [3] worker réel (MultiFolderCamera, dossiers temporaires Ha/O3) : gains
      appliqués au composite, état par canal dans les stats, sauvegarde
      PAR CANAL (un canal_<rôle>.fit par rôle) + message de la boucle UI.

Le chemin MONO ne doit PAS changer : les 26 autres _test_*.py restent verts.
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

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
from avastack.images import load_image, save_image, lire_filtre_fits
from avastack.cameras import SOURCES
from avastack.cameras.multifolder import MultiFolderCamera
from avastack.processing.composition import (FILTRES_USUELS, role_de_filtre,
                                             bornes_normalisation, normaliser)

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


def ecrire_fits(dossier, nom, img, filtre=None):
    """Écrit un FITS 2D, avec le mot-clé FILTER si `filtre` est fourni."""
    p = os.path.join(dossier, nom)
    if filtre is None:
        save_image(p, img)
    else:
        from astropy.io import fits
        hd = fits.Header()
        hd["FILTER"] = str(filtre)
        fits.PrimaryHDU(img.astype(np.float32), hd).writeto(p, overwrite=True)
    return p


# ========================================================= [1] briques filtres
print("[1] détection du filtre (FITS FILTER) : rôle + lecture en-tête")
verifie(FILTRES_USUELS.get("HA") == "Ha" and role_de_filtre("Ha") == "Ha",
        "FILTRES_USUELS : « Ha » → rôle Ha")
verifie(role_de_filtre("H-alpha") == "Ha" and role_de_filtre("h alpha") == "Ha",
        "graphies séparées (« H-alpha », « h alpha ») → Ha")
verifie(role_de_filtre("OIII") == "O3" and role_de_filtre("SII") == "S2"
        and role_de_filtre("Red") == "R" and role_de_filtre("Luminance") == "L",
        "OIII → O3 · SII → S2 · Red → R · Luminance → L")
verifie(role_de_filtre("Bleu Profond") is None
        and role_de_filtre(None) is None,
        "graphie inconnue / None → rôle None (pas de sur-étiquetage)")

racine = tempfile.mkdtemp(prefix="avastack_j19p3_")
d_f = os.path.join(racine, "filtre")
os.makedirs(d_f)
champ_img = champ()
p_f = ecrire_fits(d_f, "a.fit", champ_img, filtre="Ha")
verifie(lire_filtre_fits(p_f) == "Ha", "lire_filtre_fits : FILTER lu = « Ha »")
verifie(role_de_filtre(lire_filtre_fits(p_f)) == "Ha",
        "chaîne complète : FILTER « Ha » → rôle Ha")
p_sans = ecrire_fits(d_f, "sans.fit", champ_img)
verifie(lire_filtre_fits(p_sans) is None, "FITS sans mot-clé FILTER → None")
p_png = os.path.join(d_f, "img.png")
save_image(p_png, champ_img)
verifie(lire_filtre_fits(p_png) is None, "PNG → None (pas d'en-tête FITS)")
verifie(lire_filtre_fits(os.path.join(d_f, "absent.fit")) is None,
        "fichier absent → None (jamais d'exception)")

# =================================================================== [2] UI
print("[2] UI : cadre composition, combobox ↔ rôles, gains")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui
# Test HERMÉTIQUE (piège config.json — comme _test_ui_jalon5 / jalon12) : la
# vraie config d'Alain contient des lignes compo RÉELLES (LRGB, dossiers
# N.I.N.A.) ; _restaurer_config les rétablirait dans l'UI et fausserait le
# test du PRÉ-REMPLISSAGE (constaté le 19/09/2026 après une session réelle).
# Config vierge simulée + sauvegarde interceptée : jamais toucher au vrai
# fichier.
ui.CONFIG = {}
ui.sauver_config = lambda d: None
app = ui.App(root)

verifie("Composition multi-dossiers (RGB/HOO/SHO/LRGB)" in SOURCES,
        "SOURCES : la source « Composition multi-dossiers » existe")
verifie(len(app.var_compo_roles) == 4 and len(app.var_compo_dossiers) == 4,
        "4 lignes rôle + dossier (1 à 4 dossiers)")
verifie(tuple(v.get() for v in app.var_compo_roles) == ("Ha", "O3", "", ""),
        "défaut HOO → rôles pré-remplis (Ha, O3)")

app.var_compo.set("SHO")
app._on_compo()
verifie(tuple(v.get() for v in app.var_compo_roles) == ("S2", "Ha", "O3", ""),
        "choix SHO → rôles (S2, Ha, O3)")

# sens inverse : rôles remplis → composition déduite (LRGB ⇄ RGB, cas valide)
app.var_compo.set("LRGB")
app._on_compo()
verifie(tuple(v.get() for v in app.var_compo_roles) == ("L", "R", "G", "B"),
        "choix LRGB → rôles (L, R, G, B)")
app.var_compo_roles[0].set("")
app._on_compo_roles()
verifie(app.var_compo.get() == "RGB",
        "L retiré → composition RGB déduite (sens inverse)")
app.var_compo_roles[0].set("L")
app._on_compo_roles()
verifie(app.var_compo.get() == "LRGB",
        "rôle L revenu → composition LRGB redéduite")

app.var_compo.set("HOO")
app._on_compo()
verifie(app.rb_l_syn.instate(["disabled"])
        and app.rb_l_deg.instate(["disabled"]),
        "radio « Canal L » inactive hors LRGB")
app.var_compo.set("LRGB")
app._on_compo()
verifie(app.rb_l_syn.instate(["!disabled"])
        and app.rb_l_deg.instate(["!disabled"]),
        "radio « Canal L » active en LRGB")
app.var_compo.set("HOO")
app._on_compo()      # retour au scénario HOO pour la suite du test

app.var_compo_gains["R"].set("1,5")     # virgule décimale
app.var_compo_gains["G"].set("99")      # hors bornes
app.var_compo_gains["B"].set("abc")     # non numérique
g = app._lire_gains()
verifie(abs(g["R"] - 1.5) < 1e-9 and g["G"] == 10.0 and g["B"] == 1.0,
        "_lire_gains : virgule acceptée, bornes 0..10, défaut 1.0")
app.var_compo_gains["R"].set("1.0")
app.var_compo_gains["G"].set("1.0")
app.var_compo_gains["B"].set("1.0")

# erreurs claires de _lire_roles_dossiers
try:
    app._lire_roles_dossiers()
    verifie(False, "rôles sans dossiers → RuntimeError levée")
except RuntimeError:
    verifie(True, "rôles sans dossiers → RuntimeError levée")

d_ha = os.path.join(racine, "ha")
d_o3 = os.path.join(racine, "o3")
os.makedirs(d_ha)
os.makedirs(d_o3)
app.var_compo_dossiers[0].set(d_ha)
app.var_compo_dossiers[1].set(d_o3)
verifie(app._lire_roles_dossiers() == [("Ha", d_ha), ("O3", d_o3)],
        "_lire_roles_dossiers : couples (rôle, dossier) corrects")

# persistance config : SANS toucher au vrai config.json (comme jalon 6) —
# sauver_config intercepté, CONFIG simulé pour la nouvelle session.
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
app.var_compo_gains["R"].set("0.8")
app._sauver_config_app()
verifie(len(sauvegardes) == 1, "config écrite exactement une fois")
c_cfg = sauvegardes[0]
verifie(c_cfg.get("compo_role_0") == "Ha"
        and c_cfg.get("compo_dossier_0") == d_ha
        and abs(c_cfg.get("compo_gains", {}).get("R", 0.0) - 0.8) < 1e-9
        and c_cfg.get("compo_nom") == "HOO"
        and c_cfg.get("compo_mode_l") == "synthetise",
        "config : clés compo écrites (rôles, dossiers, gains, mode L)")
ui.CONFIG = dict(c_cfg)      # simule le config.json relu au démarrage
app2 = ui.App(root)
verifie(app2.var_compo_dossiers[0].get() == d_ha
        and app2.var_compo_roles[0].get() == "Ha",
        "config : dossiers et rôles restaurés")
verifie(abs(app2._lire_gains()["R"] - 0.8) < 1e-9, "config : gains restaurés")
root.destroy()

# ========================================================= [3] worker réel
print("[3] worker réel : gains + état par canal + sauvegarde par filtre")
root = tk.Tk()
root.withdraw()
app = ui.App(root)


class _Val:
    """Bouchon de variable Tk (get interdit hors thread principal)."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app.var_expo = _Val(0.0)
app.var_gain = _Val(0.0)
app.var_wb = _Val(False)
app.var_wb_force = _Val(1.0)
app._compo_gains = {"R": 1.0, "G": 2.0, "B": 1.0}   # gain vert ×2 (visible)
app._compo_mode_l = "synthetise"
cam = MultiFolderCamera([("Ha", d_ha), ("O3", d_o3)])
cam.open()
app.camera = cam
app._mode_compo = True
app._compo_nom = "HOO"
app.running = True
app.empilement_on = True             # jalon 26 : le worker n'empile que si armé
th = threading.Thread(target=app._worker, daemon=True)
th.start()

# déposer les frames APRÈS l'ouverture (comme N.I.N.A. pendant la session)
for i, (dx, dy) in enumerate([(0.0, 0.0), (2.0, 0.0), (4.0, 0.0)]):
    save_image(os.path.join(d_ha, f"ha_{i}.fit"),
               champ(dx, dy, fond=0.05, graine=i))
    save_image(os.path.join(d_o3, f"o3_{i}.fit"),
               champ(dx, dy, fond=0.07, graine=50 + i))
t0 = time.time()
st = None
while time.time() - t0 < 60:
    if app.stacker is not None and app.stacker.n >= 6:
        break
    try:
        _show, _hist, st = app.q.get(timeout=0.5)
    except Exception:
        pass
time.sleep(0.5)
try:
    while True:
        _show, _hist, st = app.q.get_nowait()
except Exception:
    pass

verifie(app.stacker is not None
        and type(app.stacker).__name__ == "CompositeStacker",
        "worker : façade CompositeStacker posée en mode compo")
verifie(app.stacker.gains == {"R": 1.0, "G": 2.0, "B": 1.0},
        "gains de session appliqués à la façade (vert ×2)")
verifie(app.stacker.mode_l == "synthetise", "mode L posé (défaut)")

# le gain vert ×2 multiplie le canal G du composite (HOO : G = O3)
comp = app.stacker.mean()
o3 = app.stacker.moyennes()["O3"]
if comp is not None:
    lo, hi = bornes_normalisation(o3)
    verifie(float(np.max(np.abs(
        comp[..., 1] - normaliser(o3, lo, hi) * 2.0))) < 2e-3,
        "composite : canal G = O3 normalisé × gain (2.0)")
else:
    verifie(False, "composite produit (impossible de vérifier le gain)")

if st is not None:
    verifie(isinstance(st.get("compo"), str)
            and re.fullmatch(r"Ha: [1-9]\d* · O3: [1-9]\d*",
                             st["compo"]) is not None,
            f"stats : état par canal (« {st.get('compo')} »)")
else:
    verifie(False, "stats : aucune stat reçue de la file")

# sauvegarde PAR CANAL : un fichier par rôle, contenu = moyenne du rôle
d_can = os.path.join(racine, "canaux")
os.makedirs(d_can)
app.save_canaux_request = d_can
t0 = time.time()
while app.saved_path is None and time.time() - t0 < 10:
    time.sleep(0.05)
verifie(app.saved_path == d_can and os.path.isdir(d_can),
        "sauvegarde par canal consommée par le worker")
moy = app.stacker.moyennes()
for role in ("Ha", "O3"):
    p = os.path.join(d_can, f"canal_{role}.fit")
    lu = load_image(p) if os.path.exists(p) else None
    verifie(lu is not None
            and lu.shape == moy[role].shape
            and np.allclose(lu, moy[role], rtol=1e-5, atol=1e-6),
            f"canal_{role}.fit écrit = moyenne du rôle (recadrée)")
# v2.34.6 : le fichier DIT ce qu'il contient (question d'Alain du 24/09/2026 :
# « la sauvegarde linéaire, elle sauvegarde quoi au juste ? »).
from astropy.io import fits      # noqa: E402
h_can = fits.open(os.path.join(d_can, "canal_Ha.fit"))[0].header
verifie("BRUTE" in str(h_can.get("AVALAYER", "")),
        f"canal_*.fit : en-tête AVALAYER = « {h_can.get('AVALAYER')} » "
        f"(couche brute : ni normalisation, ni gain)")
verifie(int(h_can.get("AVAFRAME", 0)) > 0,
        f"canal_*.fit : AVAFRAME = {h_can.get('AVAFRAME')} (frames empilées)")
h_compo = fits.open(os.path.join(d_can, "canal_O3.fit"))[0].header
verifie(str(h_compo.get("FILTER", "")) == "O3",
        "canal_*.fit : FILTER = rôle du canal (déjà en place)")

# sauvegarde de l'EMPILEMENT (composite) : mêmes renseignements + composition
d_stack = os.path.join(racine, "empilement.fits")
app.save_request = d_stack
t0 = time.time()
while app.saved_path != d_stack and time.time() - t0 < 10:
    time.sleep(0.05)
ok_stack = os.path.exists(d_stack)
verifie(ok_stack and app.saved_path == d_stack,
        "sauvegarde de l'empilement (linéaire) consommée par le worker")
if ok_stack:
    h_s = fits.open(d_stack)[0].header
    verifie(str(h_s.get("AVACOMPO", "")).startswith("HOO")
            and "normalisation" in str(h_s.get("AVACOMPO", "")),
            f"empilement : AVACOMPO = « {h_s.get('AVACOMPO')} » (ce qui est "
            f"appliqué est écrit dans le fichier)")
    verifie("AVASPCC" not in h_s and "AVAGAIA" not in h_s,
            "empilement : aucun gain de couleur signalé quand aucune case "
            "n'est cochée (le fichier ne ment pas)")

app.running = False
th.join(timeout=5)
cam.close()
root.destroy()

shutil.rmtree(racine, ignore_errors=True)
images.CFA_MODE = CFA_MODE_AVANT
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
