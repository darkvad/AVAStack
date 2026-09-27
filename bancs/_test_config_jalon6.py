# -*- coding: utf-8 -*-
"""Test UI du jalon 6 — persistance config.json (VeraLux + empilement).

Vérifie sur la fenêtre RÉELLE (Tkinter), SANS toucher au vrai config.json
(sauver_config est intercepté, CONFIG est simulé) :
  - la sauvegarde écrit toutes les clés jalon 6 : kappa, méthode + fenêtre
    de rejet, moteur, mode de résolution, fond visée, logD, profil
    capteur, GraXpert live ;
  - une nouvelle session restaure tout (variables UI ET état du
    DisplayProcessor), moteur VeraLux en dernier (réglages masqués/affichés) ;
  - des réglages invalides ou corrompus laissent les défauts, sans crash.

Nécessite un affichage. Exécution : python bancs/_test_config_jalon6.py
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

import avastack.ui.app as ui
from avastack.external import live as gx_live
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


FAKE_CMD = f'"{sys.executable}" "{{input}}" -o "{{output}}"'

# Le VRAI config.json ne doit jamais être touché par les tests :
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))

print("[1] Sauvegarde : toutes les clés jalon 6 sont écrites")
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
app.var_kappa.set("4σ"); app._on_kappa()
app.var_rejet.set("Winsorized (satellites)"); app._on_rejet()
app.var_fenetre.set("12"); app._on_rejet()
app.var_vl_target.set(0.31); app.disp.vl_target_bg = 0.31
app.var_vl_logd.set(2.4); app.disp.vl_log_d = 2.4
app.var_vl_mode_res.set("logD forcé"); app._sync_vl_mode()
profils = list(app.cb_vl_profil["values"])
profil = profils[1] if len(profils) > 1 else app.var_vl_profil.get()
app.var_vl_profil.set(profil); app._on_vl_profil()
app.var_cmd_graxpert.set(FAKE_CMD)
app.var_vl_graxpert.set(True); app._on_vl_graxpert()
app.var_moteur.set("VeraLux"); app._on_moteur()
app._sauver_config_app()
verifie(len(sauvegardes) == 1, "config écrite exactement une fois")
c = sauvegardes[0]
verifie(c.get("kappa") == 4.0 and c.get("rejet_methode") == "winsorized"
        and c.get("rejet_fenetre") == 12,
        "empilement persisté (kappa / méthode / fenêtre)")
verifie(c.get("moteur") == "VeraLux" and c.get("vl_mode_res") == "logD forcé"
        and c.get("vl_target") == 0.31 and c.get("vl_logd") == 2.4
        and c.get("vl_profil") == profil and c.get("vl_graxpert") is True,
        "VeraLux persisté (moteur / mode / fond / logD / profil / GX live)")
root.destroy()

print("[2] Restauration : une nouvelle session retrouve tout")
ui.CONFIG = dict(c)      # simule le config.json relu au démarrage
root2 = tk.Tk()
app2 = ui.App(root2)
root2.update_idletasks()
verifie(app2.kappa == 4.0 and app2.var_kappa.get() == "4σ", "kappa restauré")
verifie(app2.rejet_methode == "winsorized"
        and app2.var_rejet.get() == "Winsorized (satellites)"
        and app2.rejet_fenetre == 12 and app2.var_fenetre.get() == "12",
        "méthode + fenêtre de rejet restaurées")
verifie(str(app2.cb_fenetre.cget("state")) == "readonly",
        "fenêtre active (mode winsorized)")
verifie(app2.var_moteur.get() == "VeraLux", "moteur VeraLux restauré")
verifie(app2.var_vl_mode_res.get() == "logD forcé"
        and app2.disp.vl_mode_res == vl.MODE_LOG_D
        and abs(app2.disp.vl_log_d - 2.4) < 1e-9,
        "mode de résolution + logD restaurés (dans disp aussi)")
verifie(abs(app2.disp.vl_target_bg - 0.31) < 1e-9
        and abs(app2.var_vl_target.get() - 0.31) < 1e-9, "fond visée restauré")
verifie(app2.disp.vl_profil == profil and app2.var_vl_profil.get() == profil,
        "profil capteur restauré")
verifie(app2.var_vl_graxpert.get() is True
        and app2.disp.vl_graxpert_cmd == FAKE_CMD,
        "GraXpert live restauré (commande comprise)")
verifie(app2.disp.vl_graxpert is True,
        "GX live actif côté solveur (vue « empilement » au démarrage)")
root2.destroy()

print("[3] Réglages invalides/corrompus : défauts conservés, aucun crash")
ui.CONFIG = {"kappa": 7.0, "rejet_methode": "pivot", "rejet_fenetre": "abc",
             "moteur": "Photoshop", "vl_mode_res": "hasard",
             "vl_target": 99.0, "vl_logd": -3, "vl_profil": "inconnu",
             "vl_graxpert": True, "cmd_graxpert": ""}
root3 = tk.Tk()
app3 = ui.App(root3)
root3.update_idletasks()
verifie(app3.kappa == 3.0 and app3.var_kappa.get() == "3σ",
        "kappa invalide → défaut")
verifie(app3.rejet_methode == "kappa" and app3.rejet_fenetre == 8,
        "méthode / fenêtre invalides → défauts")
verifie(app3.var_moteur.get() == "STF", "moteur inconnu → STF")
verifie(app3.var_vl_mode_res.get() == "fond cible (auto)",
        "mode de résolution invalide → défaut")
verifie(abs(app3.var_vl_target.get() - vl.TARGET_BG_PAR_DEFAUT) < 1e-9
        and abs(app3.var_vl_logd.get() - vl.LOG_D_PAR_DEFAUT) < 1e-9,
        "curseurs hors bornes → défauts")
verifie(app3.var_vl_profil.get() == vl.PROFIL_PAR_DEFAUT,
        "profil inconnu → défaut")
cmd3 = app3.var_cmd_graxpert.get().strip()
verifie(app3.var_vl_graxpert.get() == gx_live.commande_valide(cmd3),
        "GX live restauré SEULEMENT si la commande est utilisable")
root3.destroy()

print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
