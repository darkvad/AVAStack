# -*- coding: utf-8 -*-
"""Test UI du jalon 120 (v2.72.1) — un réglage RESTAURÉ doit être AFFICHÉ.

Bug corrigé : `_add_slider` créait le `ttk.Scale` SANS `variable=` et n'écrivait
l'étiquette de valeur que dans `cmd()`, que Tk n'appelle JAMAIS sur un
`var.set()` programmatique (même en liant `variable=var`, seul le bouton suit).
Un réglage relu de config.json était donc APPLIQUÉ (les recopies de la
restauration posaient `disp.*` à partir des variables) mais NON AFFICHÉ :
l'étiquette ET le bouton restaient au défaut. MESURÉ sur M33 le 11/10/2026 —
`sat_b = 3,0` partait dans le rendu pendant que l'écran affichait 1,00.

Depuis, toute pose de valeur passe par `_poser_curseur` (chemin d'un geste :
`s.set(v)` → `cmd` → variable + étiquette + callback). Ce banc vérifie, sur la
fenêtre RÉELLE, POUR CHAQUE curseur restauré :
    étiquette == bouton (ttk.Scale) == variable == valeur de config
    (et `disp.*` quand ce curseur en pilote un).
Puis : une valeur HORS BORNES laisse le DÉFAUT, étiquette comprise.

Sans toucher au vrai config.json (sauver_config intercepté, CONFIG simulé).
Nécessite un affichage.
Exécution : python bancs/_test_restauration_curseurs_jalon120.py
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
from tkinter import ttk

import avastack.ui.app as ui
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Le VRAI config.json ne doit jamais être touché par les tests :
ui.sauver_config = lambda *a, **k: None


def valeur_affichee(app, var):
    """Texte du widget de valeur du curseur lié à `var` : `_add_slider` range
    [libellé, valeur] dans une « tête », la ligne [-, curseur, +] au-dessous —
    on lit donc le DERNIER widget de la tête (Entry en mode saisie, sinon
    Label)."""
    s = app._curseurs[str(var)]
    tete = s._row.winfo_children()[0]
    w = tete.winfo_children()[-1]
    return w.get() if isinstance(w, ttk.Entry) else w.cget("text")


def nombre(txt):
    return float(str(txt).replace(",", ".").strip())


def controle(app, nom, var, attendu, lire_disp=None):
    """Un curseur restauré : étiquette == bouton == variable (== disp)."""
    cur = app._curseurs[str(var)]
    ecarts = []
    txt = valeur_affichee(app, var)
    if abs(nombre(txt) - attendu) > 1e-6:
        ecarts.append(f"étiquette {txt!r} ≠ {attendu:g}")
    if abs(float(cur.get()) - attendu) > 1e-6:
        ecarts.append(f"bouton {float(cur.get()):g} ≠ {attendu:g}")
    if abs(float(var.get()) - attendu) > 1e-6:
        ecarts.append(f"variable {float(var.get()):g} ≠ {attendu:g}")
    if lire_disp is not None:
        d = float(lire_disp(app))
        if abs(d - attendu) > 1e-6:
            ecarts.append(f"disp {d:g} ≠ {attendu:g}")
    verifie(not ecarts,
            f"{nom} : tout suit la config ({attendu:g})"
            if not ecarts else f"{nom} : ÉCART → " + " · ".join(ecarts))


CONFIG = {
    # --- Affichage / STF : le cœur du bug du 11/10/2026 --------------------
    "sigk": 3.4, "target": 0.31, "gamma": 1.20, "saturation": 1.05,
    "sat_r": 1.50, "sat_g": 0.40, "sat_b": 2.50,
    # --- « Couleur » -------------------------------------------------------
    "vl_scnr_force": 0.60, "vl_demagenta_force": 0.40, "vl_boost_force": 2.0,
    # --- VeraLux / fond et grain / netteté ---------------------------------
    "vl_target": 0.31, "vl_logd": 2.40, "vl_chroma": True,
    "vl_chroma_force": 0.75, "vl_chroma_rayon_ref": 2.0,
    "vl_denoise_force": 0.80, "vl_sharp_iterations": 4,
    # --- Empilement / traitement externe -----------------------------------
    "wb_force": 0.50, "dn_force": 0.40,
}


print("[1] Restauration : étiquette == bouton == variable == config, "
      "POUR CHAQUE curseur")
ui.CONFIG = dict(CONFIG)
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()

controle(app, "Coupure du bruit (sigk)", app.var_sigk, 3.4,
         lambda a: a.disp.sigma_k)
controle(app, "Luminosité du fond (target)", app.var_target, 0.31,
         lambda a: a.disp.target)
controle(app, "Gamma", app.var_gamma, 1.20, lambda a: a.disp.gamma)
controle(app, "Saturation (globale)", app.var_saturation, 1.05,
         lambda a: a.disp.saturation)
controle(app, "Saturation rouge", app.var_sat_r, 1.50,
         lambda a: a.disp.sat_canaux[0])
controle(app, "Saturation verte", app.var_sat_g, 0.40,
         lambda a: a.disp.sat_canaux[1])
controle(app, "Saturation bleue", app.var_sat_b, 2.50,
         lambda a: a.disp.sat_canaux[2])
controle(app, "Force du SCNR", app.var_vl_scnr_force, 0.60,
         lambda a: a.disp.vl_scnr_force)
controle(app, "Force du démagenta", app.var_vl_demagenta_force, 0.40,
         lambda a: a.disp.vl_demagenta_force)
controle(app, "Force du boost (rouge)", app.var_vl_boost_force, 2.0,
         lambda a: a.disp.vl_boost_force)
controle(app, "Fond visé (VeraLux)", app.var_vl_target, 0.31,
         lambda a: a.disp.vl_target_bg)
controle(app, "logD forcé", app.var_vl_logd, 2.40,
         lambda a: a.disp.vl_log_d)
controle(app, "Force du bruit chromatique", app.var_vl_chroma_force, 0.75,
         lambda a: a.disp.vl_chroma_force)
controle(app, "Rayon de référence (chroma)", app.var_vl_chroma_rayon, 2.0)
controle(app, "Force du débruitage (live)", app.var_vl_dn_force, 0.80,
         lambda a: a.disp.vl_denoise_force)
controle(app, "Itérations (netteté)", app.var_vl_sharp_iter, 4,
         lambda a: a.disp.vl_sharp_iterations)
controle(app, "Force de l'équilibrage", app.var_wb_force, 0.50)
controle(app, "Force du débruitage (externe)", app.var_dn_force, 0.40)
root.destroy()

print("[2] Le cas MESURÉ du 11/10/2026 : sat_b = 3,00 (bug « appliqué non "
      "affiché »)")
ui.CONFIG = {"sat_b": 3.0}
root2 = tk.Tk()
app2 = ui.App(root2)
root2.update_idletasks()
txt = valeur_affichee(app2, app2.var_sat_b)
verifie(nombre(txt) == 3.0,
        f"« Saturation bleue » AFFICHE 3,00 (obtenu {txt!r}) — plus de mensonge")
verifie(abs(float(app2._curseurs[str(app2.var_sat_b)].get()) - 3.0) < 1e-9,
        "le bouton du curseur est bien à 3,00")
verifie(app2.disp.sat_canaux == (1.0, 1.0, 3.0),
        f"le rendu part avec {app2.disp.sat_canaux} (identique à l'écran)")
root2.destroy()

print("[3] Valeur HORS BORNES : le défaut est conservé, étiquette comprise")
hors = {"sigk": 99.0, "gamma": -5.0, "sat_b": 42.0, "vl_target": 9.9,
        "vl_logd": -1.0, "vl_chroma_force": 7.0, "wb_force": -3.0}
ui.CONFIG = dict(hors)
root3 = tk.Tk()
app3 = ui.App(root3)
root3.update_idletasks()
for nom, var, defaut in (
        ("sigk", app3.var_sigk, 2.8),
        ("gamma", app3.var_gamma, 1.0),
        ("Saturation bleue", app3.var_sat_b, 1.0),
        ("Fond visé (VeraLux)", app3.var_vl_target, vl.TARGET_BG_PAR_DEFAUT),
        ("logD forcé", app3.var_vl_logd, vl.LOG_D_PAR_DEFAUT),
        ("Force du bruit chromatique", app3.var_vl_chroma_force, 0.5),
        ("Force de l'équilibrage", app3.var_wb_force, 1.0)):
    txt = valeur_affichee(app3, var)
    verifie(abs(nombre(txt) - defaut) < 1e-6
            and abs(float(var.get()) - defaut) < 1e-6,
            f"{nom} hors bornes → défaut {defaut:g} conservé "
            f"(affiché {txt!r})")
root3.destroy()

print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
