# -*- coding: utf-8 -*-
"""Banc v2.87.0 — INTERFACE 141-B : PRÉVENIR QUAND LA COMPOSITION CHANGE EN
SESSION (jalon 141, décision d'Alain du 18/10/2026 — option B).

Le défaut, constaté en réel : une session **LRGB+Ha** conduite avec le menu
« Composition » passé en « RGB » **pendant** l'empilement. Le fichier était
JUSTE (son en-tête `AVACOMPO` portait LRGB+Ha) mais l'écran affichait « RGB » :
la composition de la session ne se lisait plus nulle part sans ouvrir le FITS,
et l'écart était SILENCIEUX. Options écartées : A = documenter (l'écran
continuerait de mentir), C = invalider l'empilement (perd une session bonne).

Vérifie (App réelle, Tk, `_avertir` espionné — aucune boîte modale ouverte) :
  [1] aucune session armée → aucun écart, bandeau vide, aucune boîte ;
  [2] session LRGB+Ha puis menu passé en RGB → bandeau ORANGE nommant les DEUX
      compositions, UNE boîte, et la SESSION ne change pas ;
  [3] même écart rejoué → pas de seconde boîte (le bandeau reste), un AUTRE
      écart (SHO) → une nouvelle boîte ;
  [4] retour du menu sur la composition de la session → bandeau vidé ;
  [5] l'écart naît aussi par les RÔLES (`_on_compo_roles`), même alerte ;
  [6] LE FICHIER NE MENT PAS : `AVACOMPO` continue de dire la composition de la
      SESSION pendant que l'écran affiche l'autre ;
  [7] « ▶ Démarrer » réarme (`_armer_compo_session`) → bandeau vidé, alerte
      remise à zéro (un nouvel écart sera dit) ;
  [8] fin de session (`_deconnecter_camera`) → plus d'écart, et changer la
      composition hors session ne prévient plus.

Exécution : python bancs/_test_compo_session_jalon141.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tkinter as tk

import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing.composition import CompositeStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ============================================================== [1] construction
print("[1] aucune session armée : aucun écart à signaler")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui               # noqa: E402
ui.CONFIG = {}                             # jamais toucher à la vraie config
ui.sauver_config = lambda d: None
# Espion AVANT la construction : à l'écran `_avertir` est une boîte MODALE
# (elle bloquerait le banc), et `_on_compo` est appelée par `_build_ui`.
boites = []


def _espion_avertir(self, titre, message):
    boites.append((str(titre), str(message)))


ui.App._avertir = _espion_avertir
app = ui.App(root)
BANDEAU = app.lbl_compo_session

verifie(BANDEAU.winfo_exists() and BANDEAU.cget("text") == "",
        "bandeau « composition de la session » présent et VIDE au démarrage")
verifie(app._compo_session is None and app._compo_divergente() is None,
        "aucune session armée → aucun écart (`_compo_session` None)")
verifie(not boites,
        "aucune boîte à la construction de l'interface (le bandeau suffit)")

# ============================================ [2] l'écart naît par le MENU
print("[2] session LRGB+Ha + menu passé en RGB : le bandeau et UNE boîte")
app._mode_compo = True
app.var_compo.set("LRGB+Ha")              # la session part du menu LRGB+Ha
app._on_compo()
app._compo_nom = "LRGB+Ha"
app._armer_compo_session()
verifie(app._compo_session == "LRGB+Ha" and app._compo_divergente() is None,
        "« ▶ Démarrer » arme la composition de la SESSION (celle des rôles : "
        "LRGB+Ha)")
app.var_compo.set("RGB")
app._on_compo()
txt = str(BANDEAU.cget("text"))
verifie("LRGB+Ha" in txt and "RGB" in txt,
        f"bandeau : il nomme la SESSION et la composition AFFICHÉE — « {txt} »")
verifie("session suivante" in txt and "gardent" in txt,
        "bandeau : il dit que la session garde SA composition et que l'autre "
        "ne vaudra qu'à la suivante")
verifie(str(BANDEAU.cget("foreground")) == "#c98a00",
        "bandeau en ORANGE (couleur d'avertissement de l'interface)")
verifie(len(boites) == 1 and "LRGB+Ha" in boites[0][1]
        and "RGB" in boites[0][1],
        "UNE boîte d'avertissement, nommant les DEUX compositions")
verifie(app._compo_session == "LRGB+Ha",
        "la SESSION ne change pas : seule la composition AFFICHÉE a changé")
verifie(tuple(v.get() for v in app.var_compo_roles) == ("R", "G", "B", "", ""),
        "le choix RGB a bien pré-rempli les rôles (comportement du jalon 19 "
        "inchangé)")

# ================================= [3] une boîte par écart, pas par clic
print("[3] même écart rejoué → pas de seconde boîte ; autre écart → nouvelle boîte")
app.var_compo.set("RGB")
app._on_compo()
verifie(len(boites) == 1 and BANDEAU.cget("text") != "",
        "même écart : aucune boîte de plus (le bandeau est toujours là)")
app.var_compo.set("SHO")
app._on_compo()
verifie(len(boites) == 2 and "SHO" in boites[1][1],
        "un AUTRE écart est annoncé à son tour")
verifie("LRGB+Ha" in str(BANDEAU.cget("text"))
        and "SHO" in str(BANDEAU.cget("text")),
        "le bandeau suit le nouvel écart (session LRGB+Ha, affichée SHO)")

# ================================== [4] retour à la composition de la session
print("[4] retour du menu sur la composition de la session → bandeau vidé")
app.var_compo.set("LRGB+Ha")
app._on_compo()
verifie(app._compo_divergente() is None and BANDEAU.cget("text") == "",
        "plus d'écart : le bandeau est VIDÉ (cas normal, aucun bruit)")
verifie(len(boites) == 2,
        "le retour à la normale n'ouvre aucune boîte (rien à signaler)")

# ============================================= [5] l'écart naît par les RÔLES
print("[5] l'écart naît aussi par les RÔLES, avec la même alerte")
app.var_compo_roles[0].set("")            # L retiré → composition déduite
app._on_compo_roles()
verifie(app.var_compo.get() == "RGB+Ha",
        f"rôles (R,G,B,Ha) → composition déduite « {app.var_compo.get()} »")
verifie(app._compo_divergente() == "LRGB+Ha",
        "l'écart avec la session LRGB+Ha est bien détecté")
verifie(len(boites) == 3 and "RGB+Ha" in boites[2][1],
        "les rôles déclenchent la MÊME boîte que le menu")
verifie(BANDEAU.cget("text") != "", "…et le bandeau s'affiche")

# ============================ [6] le FICHIER ne ment pas : AVACOMPO dit la SESSION
print("[6] AVACOMPO continue de dire la composition de la SESSION")
app.stacker = CompositeStacker("LRGB+Ha")
app._mode_compo = True
ent = str(app._entete_reglages().get("AVACOMPO", ""))
verifie(ent.split(",")[0].strip() == "LRGB+Ha",
        f"en-tête FITS : « {ent} » — la composition écrite est celle de la "
        f"SESSION, pas celle affichée (« {app.var_compo.get()} »)")

# ========================== [7] nouvelle session : bandeau vidé, alerte réarmée
print("[7] « ▶ Démarrer » réarme sur la configuration affichée")
app.var_compo.set("RGB+Ha")               # ce que les rôles portent réellement
app._compo_nom = "RGB+Ha"
app._armer_compo_session()                # ce que fait la fin de `_start`
verifie(app._compo_session == "RGB+Ha" and app._compo_divergente() is None
        and BANDEAU.cget("text") == "",
        "session neuve : armée sur RGB+Ha, bandeau vidé")
verifie(app._compo_alerte is None,
        "l'alerte est remise à zéro : un nouvel écart sera DIT")
app.var_compo.set("SHO")
app._on_compo()
verifie(len(boites) == 4 and "RGB+Ha" in boites[3][1],
        "nouvel écart sur la nouvelle session → nouvelle boîte")

# ========================================== [8] fin de session (déconnexion)
print("[8] fin de session : plus d'écart à signaler")
app._deconnecter_camera()
verifie(app._compo_session is None and app._compo_divergente() is None
        and BANDEAU.cget("text") == "",
        "déconnexion : la session s'achève, le bandeau est vidé")
app.var_compo.set("HOO")
app._on_compo()
verifie(len(boites) == 4,
        "hors session, changer la composition ne prévient plus (rien à changer)")

root.destroy()

print()
print("RÉSULTAT :", "TOUT OK" if ok else "ÉCHECS À CORRIGER")
sys.exit(0 if ok else 1)
