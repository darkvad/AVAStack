# -*- coding: utf-8 -*-
"""Banc du JALON 129 — compositions « RGB+Ha » et « LRGB+Ha » (VOLET 1/5 du
chantier Ha, 15/10/2026).

Vérifie :
  [1] TABLE : les deux compositions nouvelles (rôles, `optionnels`, `canaux_rgb`
      SANS le Ha, luminance), `COMPOSITIONS_HA`, `composition_avec_ha()`, et
      `NB_LIGNES_COMPO` == plus grand nombre de rôles (5) ;
  [2] `composition_pour_roles` : les cas nominaux EXACTS des deux +Ha, et la
      NON-RÉGRESSION du repli par sous-ensemble (« Ha » → HOO, « L,R,G » →
      LRGB, « L » → Mono) — les compositions +Ha sont testées EN DERNIER ;
  [3] FAÇADE : « LRGB+Ha » empile bien une couche Ha, et depuis le jalon J2
      (v2.88.0) cette couche ENTRE dans l'image — ajout au rouge PAR DÉFAUT
      (poids 1,0), le rouge SEUL changeant ; poids 0 restaure AU BIT le
      composite d'avant (volet 1). « LRGB+Ha » sans Ha reste identique à
      « LRGB » ;
  [4] UI réelle (Tk, config vierge simulée) : 5 lignes rôle+dossier,
      pré-remplissage des rôles de LRGB+Ha, ligne d'aide « + Ha fusionné au
      rouge », radio « Canal L » ACTIVE en LRGB+Ha, détection des filtres FITS
      sur la 5e ligne, persistance puis restauration de la 5e ligne ;
  [5] ANCRE : `_broadband_ha()` (LRGB+Ha, RGB+Ha) vs `_narrowband_ha()` (HOO,
      SHO) — sans cette séparation la session attendrait indéfiniment une brute
      Ha pour créer l'empilement.

PAS de session live à 5 dossiers ici (coûteuse et non déterministe) : elle est
couverte par le test réel. Ce banc verrouille la PLOMBERIE (table, UI, ancre).
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
import shutil
import sys
import tempfile
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
import avastack.ui.app as ui
from avastack.processing.composition import (COMPOSITIONS, COMPOSITIONS_HA,
                                             NB_LIGNES_COMPO,
                                             CompositeStacker,
                                             composition_avec_ha,
                                             composition_pour_roles,
                                             roles_de, roles_optionnels)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFA_MODE_AVANT = images.CFA_MODE
images.CFA_MODE = "Non"                  # brutes mono dans ce test

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK  " if cond else "  ÉCHEC ") + msg)


# `_detecter_filtres()` se TERMINE par `self._dire(...)` — une boîte de
# dialogue MODALE : elle bloquerait le banc indéfiniment (constaté). On
# neutralise `_dire` sur la CLASSE (toutes les instances, y compris la seconde
# session simulée) le temps du banc.
ui.App._dire = lambda self, *a, **k: None


def _roles_des_canaux(spec):
    """Ensemble des rôles CITÉS par le mapping canaux R/G/B d'une composition."""
    return {r for rs in spec["canaux_rgb"].values() for r in rs}


# ================================================== [1] table des compositions
print("[1] table : compositions +Ha, COMPOSITIONS_HA, NB_LIGNES_COMPO")
verifie(set(COMPOSITIONS) == {"Mono", "HOO", "SHO", "RGB", "LRGB",
                              "RGB+Ha", "LRGB+Ha"},
        "table : les 5 compositions d'origine + les 2 nouvelles")
verifie(COMPOSITIONS_HA == ("RGB+Ha", "LRGB+Ha")
        and composition_avec_ha("RGB+Ha") and composition_avec_ha("LRGB+Ha"),
        "COMPOSITIONS_HA / composition_avec_ha : les deux +Ha sont reconnues")
verifie(not composition_avec_ha("LRGB") and not composition_avec_ha("RGB")
        and not composition_avec_ha("HOO") and not composition_avec_ha("SHO")
        and not composition_avec_ha("Mono"),
        "composition_avec_ha : FAUX pour LRGB/RGB/HOO/SHO/Mono (le Ha y est un "
        "canal ou absent)")
verifie(roles_de("RGB+Ha") == ("R", "G", "B", "Ha"),
        "RGB+Ha : rôles (R, G, B, Ha)")
verifie(roles_de("LRGB+Ha") == ("L", "R", "G", "B", "Ha"),
        "LRGB+Ha : rôles (L, R, G, B, Ha)")
verifie(COMPOSITIONS["RGB+Ha"]["canaux_rgb"]
        == {"R": ("R",), "G": ("G",), "B": ("B",)},
        "RGB+Ha : canaux R=R, G=G, B=B")
verifie(COMPOSITIONS["LRGB+Ha"]["canaux_rgb"]
        == {"R": ("R",), "G": ("G",), "B": ("B",)}
        and COMPOSITIONS["LRGB+Ha"].get("luminance") == ("L",),
        "LRGB+Ha : canaux R/G/B + luminance L")
verifie("Ha" not in _roles_des_canaux(COMPOSITIONS["RGB+Ha"])
        and "Ha" not in _roles_des_canaux(COMPOSITIONS["LRGB+Ha"]),
        "le Ha des compositions +Ha n'alimente AUCUN canal (il sera FUSIONNÉ)")
verifie(roles_optionnels("LRGB+Ha") == ("L",)
        and roles_optionnels("RGB+Ha") == (),
        "optionnels : L vide toléré en LRGB+Ha, AUCUN rôle optionnel en RGB+Ha")
verifie(NB_LIGNES_COMPO == 5
        and NB_LIGNES_COMPO == max(len(s["roles"]) for s in COMPOSITIONS.values()),
        f"NB_LIGNES_COMPO = {NB_LIGNES_COMPO} = plus grand nombre de rôles "
        "(LRGB+Ha)")

# ============================================== [2] déduction de la composition
print("[2] composition_pour_roles : cas nominaux + NON-RÉGRESSION du repli")
verifie(composition_pour_roles(("R", "G", "B", "Ha")) == "RGB+Ha"
        and composition_pour_roles(("L", "R", "G", "B", "Ha")) == "LRGB+Ha",
        "correspondance EXACTE des deux compositions +Ha")
verifie(composition_pour_roles(("Ha",)) == "HOO",
        "NON-RÉGRESSION : (« Ha »,) → HOO (et non LRGB+Ha, dont les rôles "
        "l'englobent)")
verifie(composition_pour_roles(("Ha", "O3")) == "HOO"
        and composition_pour_roles(("S2", "Ha", "O3")) == "SHO"
        and composition_pour_roles(("R", "G", "B")) == "RGB"
        and composition_pour_roles(("L", "R", "G", "B")) == "LRGB"
        and composition_pour_roles(("L",)) == "Mono",
        "NON-RÉGRESSION : HOO, SHO, RGB, LRGB, Mono inchangés")
verifie(composition_pour_roles(("L", "R", "G")) == "LRGB"
        and composition_pour_roles(("R", "G")) == "RGB",
        "NON-RÉGRESSION du repli par sous-ensemble (sans Ha)")
verifie(composition_pour_roles(("Ha", "R")) == "RGB+Ha"
        and composition_pour_roles(("L", "R", "G", "Ha")) == "LRGB+Ha",
        "repli des compositions +Ha pour les jeux PARTIELS (les canaux manquants "
        "restent vides)")
verifie(composition_pour_roles(()) is None,
        "jeu vide → None")

# =========================================== [3] le Ha n'entre pas dans l'image
print("[3] façade : la couche Ha est empilée et, depuis le J2, FUSIONNÉE")


def carte(graine, fond=0.05, h=48, w=64):
    """Carte 2D BRUITÉE (bornes de normalisation non dégénérées)."""
    rng = np.random.default_rng(graine)
    return (fond + rng.normal(0.0, 0.01, (h, w))).astype(np.float32)


_LAYERS = (("L", 1), ("R", 2), ("G", 3), ("B", 4))
fa = CompositeStacker("LRGB+Ha", k=None)
for _role, _g in _LAYERS:
    fa.add(carte(_g), role=_role)
comp_sans_ha = fa.mean(recadre=False)
canaux_sans_ha = fa.moyennes(recadre=False)
verifie(comp_sans_ha is not None and comp_sans_ha.shape == (48, 64, 3),
        "LRGB+Ha (sans Ha) rend un composite couleur "
        f"{getattr(comp_sans_ha, 'shape', None)}")
verifie("Ha" not in canaux_sans_ha,
        "tant qu'aucune brute Ha n'arrive, la couche Ha n'existe pas")

fa.add(carte(5, fond=0.90), role="Ha")     # Ha TRÈS différent : lisible si fuite
comp_avec_ha = fa.mean(recadre=False)
canaux_avec_ha = fa.moyennes(recadre=False)
verifie("Ha" in canaux_avec_ha and canaux_avec_ha["Ha"] is not None,
        "après une brute Ha, la couche Ha EST empilée (moyennes())")
verifie(fa.n == 5 and fa.profondeur_min() == 1,
        f"compteurs : n = {fa.n} (somme des rôles), profondeur_min = "
        f"{fa.profondeur_min()}")
verifie(not np.array_equal(comp_avec_ha[..., 0], comp_sans_ha[..., 0])
        and np.array_equal(comp_avec_ha[..., 1:], comp_sans_ha[..., 1:]),
        "J2 (v2.88.0) : la couche Ha ENTRE dans l'image — ajout au rouge par "
        "DÉFAUT (poids 1,0), et le ROUGE seul change")
fa.fusion_ha = {"mode": "ajout_rouge", "poids": 0.0}
verifie(np.array_equal(fa.mean(recadre=False), comp_sans_ha),
        "poids 0 → composite IDENTIQUE AU BIT avec et sans Ha (le comportement "
        "du volet 1 reste accessible)")
fa.fusion_ha = None
verifie(np.array_equal(fa.mean(recadre=False), comp_avec_ha),
        "retour aux défauts → le composite fusionné revient (le réglage entre "
        "bien dans la clé de mémoïsation)")

fa_lrgb = CompositeStacker("LRGB", k=None)
for _role, _g in _LAYERS:
    fa_lrgb.add(carte(_g), role=_role)
verifie(np.array_equal(fa_lrgb.mean(recadre=False), comp_sans_ha),
        "LRGB+Ha (sans Ha) == LRGB au bit : la composition nouvelle ne change "
        "RIEN aux compositions existantes")

# ===================================================================== [4] UI
print("[4] UI réelle : 5 lignes, aide, radio L, détection, persistance")
racine = tempfile.mkdtemp(prefix="avastack_j129_")
dossiers = []
for _i in range(5):
    _d = os.path.join(racine, f"d{_i}")
    os.makedirs(_d)
    dossiers.append(_d)

root = tk.Tk()
root.withdraw()
# Banc HERMÉTIQUE (piège config.json, comme _test_compo_ui_jalon19) : config
# vierge simulée + sauvegarde interceptée → jamais toucher au vrai fichier.
ui.CONFIG = {}
ui.sauver_config = lambda d: None
app = ui.App(root)

verifie(len(app.var_compo_roles) == NB_LIGNES_COMPO
        and len(app.var_compo_dossiers) == NB_LIGNES_COMPO,
        f"panneau : {NB_LIGNES_COMPO} lignes rôle + dossier")
app.var_compo.set("LRGB+Ha")
app._on_compo()
verifie(tuple(v.get() for v in app.var_compo_roles)
        == ("L", "R", "G", "B", "Ha"),
        "choix LRGB+Ha → rôles pré-remplis (L, R, G, B, Ha)")
verifie("Ha fusionné au rouge" in app.lbl_compo_info.cget("text"),
        f"ligne d'aide : « {app.lbl_compo_info.cget('text')} »")
verifie(app.rb_l_syn.instate(["!disabled"])
        and app.rb_l_deg.instate(["!disabled"]),
        "radio « Canal L » ACTIVE en LRGB+Ha (il y a une luminance L)")
app.var_compo.set("RGB+Ha")
app._on_compo()
verifie(tuple(v.get() for v in app.var_compo_roles) == ("R", "G", "B", "Ha", ""),
        "choix RGB+Ha → rôles (R, G, B, Ha) + ligne libre")
verifie(app.rb_l_syn.instate(["disabled"]),
        "radio « Canal L » inactive en RGB+Ha (aucune luminance)")

# démarrage : 5 couples (rôle, dossier) acceptés
app.var_compo.set("LRGB+Ha")
app._on_compo()
for _i, _d in enumerate(dossiers):
    app.var_compo_dossiers[_i].set(_d)
couples = app._lire_roles_dossiers()
verifie(couples == [("L", dossiers[0]), ("R", dossiers[1]), ("G", dossiers[2]),
                    ("B", dossiers[3]), ("Ha", dossiers[4])],
        f"_lire_roles_dossiers : {len(couples)} couples lus (5 attendus)")

# détection des filtres FITS sur la 5e ligne (range(4) → range(5))
for _v in app.var_compo_roles:
    _v.set("")
from astropy.io import fits              # noqa: E402 (FITS à en-tête)
_hd = fits.Header()
_hd["FILTER"] = "Ha"
fits.PrimaryHDU(carte(9).astype(np.float32), _hd).writeto(
    os.path.join(dossiers[4], "ha.fit"), overwrite=True)
app._detecter_filtres()
verifie(app.var_compo_roles[4].get() == "Ha",
        "détection des filtres FITS : 5e ligne → rôle "
        f"« {app.var_compo_roles[4].get()} »")

# persistance / restauration de la 5e ligne
app.var_compo.set("LRGB+Ha")
app._on_compo()
for _i, _d in enumerate(dossiers):
    app.var_compo_dossiers[_i].set(_d)
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
app._sauver_config_app()
verifie(len(sauvegardes) == 1, "config écrite exactement une fois")
c_cfg = sauvegardes[0]
verifie(c_cfg.get("compo_role_4") == "Ha"
        and c_cfg.get("compo_dossier_4") == dossiers[4],
        "config : la 5e ligne (compo_role_4 / compo_dossier_4) est écrite")
ui.CONFIG = dict(c_cfg)                  # simule le config.json relu
app2 = ui.App(root)
verifie(app2.var_compo_roles[4].get() == "Ha"
        and app2.var_compo_dossiers[4].get() == dossiers[4],
        "config : la 5e ligne est restaurée")
verifie(app2.var_compo.get() == "LRGB+Ha",
        f"config : composition restaurée « {app2.var_compo.get()} »")

# ==================================================================== [5] ancre
print("[5] ancre : broadband+Ha ≠ narrowband Ha (sinon attente d'une brute Ha)")
app._mode_compo = True
app._compo_nom = "LRGB+Ha"
verifie(app._broadband_ha() and not app._narrowband_ha(),
        "LRGB+Ha : broadband+Ha (ancre broadband, PAS d'attente d'une brute Ha)")
app._compo_nom = "RGB+Ha"
verifie(app._broadband_ha() and not app._narrowband_ha(),
        "RGB+Ha : broadband+Ha (ancre broadband)")
app._compo_nom = "HOO"
verifie(app._narrowband_ha() and not app._broadband_ha(),
        "HOO : narrowband Ha INCHANGÉ (ancre = 1re brute Ha, triangles seuls)")
app._compo_nom = "SHO"
verifie(app._narrowband_ha() and not app._broadband_ha(),
        "SHO : narrowband Ha INCHANGÉ")
app._compo_nom = "LRGB"
verifie(not app._narrowband_ha() and not app._broadband_ha(),
        "LRGB : ni l'un ni l'autre (aucun Ha)")
app._mode_compo = False
verifie(not app._broadband_ha() and not app._narrowband_ha(),
        "hors mode composition : les deux prédicats sont FAUX")

root.destroy()
shutil.rmtree(racine, ignore_errors=True)
images.CFA_MODE = CFA_MODE_AVANT
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
