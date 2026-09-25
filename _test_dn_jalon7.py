# -*- coding: utf-8 -*-
"""Test des jalons 7/8 (remis le 16/09/2026) — débruitage dans le traitement
externe : GraXpert IA (subprocess) OU algorithmes locaux (en mémoire).

Vérifie sur la fenêtre RÉELLE (Tkinter), SANS toucher au vrai config.json
(sauver_config est intercepté, CONFIG est simulé) :
  - commandes par défaut : -cmd denoising avec -strength (PAS -smoothing) ;
  - commande_avec_strength : remplacement / ajout / casse / clamp [0,1] ;
  - UI : case « 2. Débruitage » + combobox de méthode (3 méthodes) + force ;
    BlurXTerminator renuméroté « 3. » ;
  - _request_ext : ext_job 8-tuple, force injectée dans la commande
    GraXpert, mode + force transportés pour les méthodes locales ;
  - _run_external RÉEL : chaîne gradient → débruitage local → BXT ;
  - persistance + restauration tolérante (jamais de popup au démarrage).

Nécessite un affichage. Exécution : python _test_dn_jalon7.py
"""
import os
import sys
import tempfile
import tkinter as tk
import types
from tkinter import ttk as _ttk

import numpy as np

import avastack.ui.app as ui
from avastack.external.detection import (
    DEFAULT_CMD_GRAXPERT, DEFAULT_CMD_GRAXPERT_DN, commande_avec_strength)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Outil externe SIMULÉ : copie l'entrée vers la sortie (fidèle à un vrai
# outil) et consigne son étiquette (argv[4]) dans un journal, pour vérifier
# l'ORDRE des étapes subprocess.
FAKE_TOOL = r"""
import sys
import numpy as np
from astropy.io import fits
d = fits.getdata(sys.argv[1])
fits.PrimaryHDU(np.asarray(d, dtype=np.float32)).writeto(sys.argv[2],
                                                         overwrite=True)
if len(sys.argv) > 4:
    with open(sys.argv[3], "a", encoding="utf-8") as f:
        f.write(sys.argv[4] + "\n")
"""

print("[1] Commandes par défaut (detection.py)")
verifie("-cmd denoising" in DEFAULT_CMD_GRAXPERT_DN,
        "commande débruitage par défaut : -cmd denoising")
verifie("-strength 0.5" in DEFAULT_CMD_GRAXPERT_DN
        and "-smoothing" not in DEFAULT_CMD_GRAXPERT_DN,
        "commande débruitage : -strength 0.5, PAS de -smoothing")
verifie("{input}" in DEFAULT_CMD_GRAXPERT_DN
        and "{outbase}" in DEFAULT_CMD_GRAXPERT_DN,
        "commande débruitage : placeholders {input}/{outbase} présents")
verifie(DEFAULT_CMD_GRAXPERT_DN.split(' "')[0]
        == DEFAULT_CMD_GRAXPERT.split(' "')[0],
        "même exécutable que le retrait de gradient (détection partagée)")

print("[2] commande_avec_strength (injection de la force)")
c0 = ('"exe.exe" "{input}" -cli -cmd denoising -strength 0.5 '
      '-output "{outbase}"')
verifie(commande_avec_strength(c0, 0.4)
        == c0.replace("-strength 0.5", "-strength 0.4"),
        "-strength existant REMPLACÉ (0.5 → 0.4)")
verifie(commande_avec_strength('"exe.exe" "{input}" -cmd denoising', 0.3)
        .endswith("-strength 0.3"),
        "-strength absent → AJOUTÉ en fin de commande")
verifie("-strength 0.4" in commande_avec_strength(
    '"e.exe" "{input}" -STRENGTH 0.9', 0.4).lower(),
    "remplacement insensible à la casse (-STRENGTH)")
verifie("-strength 1 " in commande_avec_strength(c0, 2.5) + " "
        and "-strength 0 " in commande_avec_strength(c0, -0.2) + " ",
        "clamp aux bornes [0, 1] (jamais d'argument invalide)")

print("[3] UI : case « 2. Débruitage », méthode, force ; BXT « 3. »")
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))  # jamais le vrai
ui.CONFIG = {}
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()


def tous_widgets(w):
    for enfant in w.winfo_children():
        yield enfant
        yield from tous_widgets(enfant)


textes = [str(w.cget("text")) for w in tous_widgets(root)
          if isinstance(w, _ttk.Checkbutton)]
verifie("1. GraXpert — retrait de gradient" in textes, "case 1 (gradient)")
verifie("2. Débruitage :" in textes, "case 2 (débruitage)")
verifie("3. BlurXTerminator — netteté" in textes, "case 3 (BXT) renumérotée")
verifie(len(app.cb_dn_methode["values"]) == 3,
        "combobox méthode externe : 3 méthodes (GraXpert IA, ondelettes, NLM)")
verifie(abs(app.var_dn_force.get() - 0.5) < 1e-9,
        "force externe par défaut 0.5")

print("[4] _request_ext : ext_job 14-tuple, force injectée")
app.running = True                     # worker non lancé : aucun thread
app.stacker = types.SimpleNamespace(n=5)
app.var_dn_methode.set("Non-local means")
app.var_dn_force.set(0.4)
app.var_ext_dn.set(True)
app._request_ext()
j = app.ext_job
# v2.37.1 : 14-tuple — les 11 premiers éléments sont les jalons 22/23, puis la
# neutralisation du fond, le bruit chromatique et la force de ce dernier.
verifie(app.ext_request is True and isinstance(j, tuple) and len(j) == 14
        and j[8] is False and j[9] is False and j[10] is False
        and j[11] is True and j[12] is False and 0.0 <= j[13] <= 1.0,
        "ext_job est un 14-tuple (gx, cmd, dn, cmd_dn, bxt, cmd_bxt, mode, "
        "force, scnr, scnr_doux, demagenta, neutre_fond, chroma, force_chroma) "
        "— jalons 22/23 + v2.37.1")
verifie(j[2] is True and j[6] == "nlm" and abs(j[7] - 0.4) < 1e-9
        and j[3] == "",
        "mode local (nlm) + force transportés, commande vide (étape en mémoire)")
app.ext_request = False
app.ext_busy = False
app.var_dn_methode.set("GraXpert (IA, lent)")
app._request_ext()
j = app.ext_job
verifie(j[6] == "graxpert" and "-cmd denoising" in j[3]
        and "-strength 0.4" in j[3],
        "force réglée (0.4) injectée dans la commande débruitage GraXpert")
app.ext_request = False
app.ext_busy = False

print("[5] _run_external RÉEL : chaîne gradient → débruitage local → BXT")
tmp = tempfile.mkdtemp(prefix="avastack_test_dn_")
outil = os.path.join(tmp, "outil_simule.py")
journal = os.path.join(tmp, "ordre.log")
with open(outil, "w", encoding="utf-8") as f:
    f.write(FAKE_TOOL)
cmd_tpl = (f'"{sys.executable}" "{outil}" "{{input}}" "{{output}}" '
           f'"{journal}"')
rng = np.random.default_rng(7)
stack = (np.full((64, 48), 0.001, dtype=np.float32)
         + rng.normal(0.0, 0.002, (64, 48)).astype(np.float32))
app.ext_job = (True, cmd_tpl + " GX_GRADIENT",
               True, "",                      # étape locale : pas de commande
               True, cmd_tpl + " BXT",
               "nlm", 0.5)
app._session = 0
app._run_external(stack, 10, 0)          # appel direct : le test EST le thread
root.update_idletasks()
ordre = [l.strip() for l in open(journal, encoding="utf-8") if l.strip()]
verifie(ordre == ["GX_GRADIENT", "BXT"],
        f"ordre des subprocess = gradient → (local en mémoire) → BXT ({ordre})")
verifie(app.proc_full is not None and app.proc_full.shape == stack.shape,
        "résultat traité pleine résolution produit")
verifie("Traité à" in app.ext_msg and app.ext_state == "ok",
        "message de succès (ext_state='ok')")
verifie(app.ext_busy is False, "ext_busy repassé à False")
sigma_avant = float(np.std(stack))
sigma_apres = float(np.std(app.proc_full))
verifie(sigma_apres < sigma_avant,
        f"image débruitée en mémoire (σ {sigma_avant:.4f} → {sigma_apres:.4f})")

print("[6] Persistance : sauvegarde")
app.var_dn_methode.set("Ondelettes à trous")
app.var_dn_force.set(0.7)
app._sauver_config_app()
c = sauvegardes[-1]
verifie(c.get("ext_dn") is True and c.get("dn_methode") == "ondelettes"
        and abs(c.get("dn_force", 0) - 0.7) < 1e-9,
        "ext_dn (True explicite) + dn_methode + dn_force persistés")
verifie("denoising" in (c.get("cmd_graxpert_dn") or ""),
        "cmd_graxpert_dn persistée")
root.destroy()

# --- Restauration tolérante (nouvelles sessions) ---------------------------
ui.CONFIG = {"ext_dn": True, "dn_methode": "graxpert", "dn_force": 2.5,
             "cmd_graxpert_dn": "graxpert sans_placeholder"}   # corrompu
root2 = tk.Tk()
app2 = ui.App(root2)
root2.update_idletasks()
verifie(app2.var_ext_dn.get() is False,
        "méthode graxpert + commande sans placeholders → case PAS restaurée")
verifie(abs(app2.var_dn_force.get() - 0.5) < 1e-9,
        "dn_force 2.5 (hors [0,1]) → défaut 0.5")
root2.destroy()

ui.CONFIG = {"ext_dn": True, "dn_methode": "nlm", "dn_force": 0.3,
             "cmd_graxpert_dn": '"exe.exe" "{input}" -cmd denoising '
                                '-strength 0.9 -output "{outbase}"'}
root3 = tk.Tk()
app3 = ui.App(root3)
root3.update_idletasks()
verifie(app3.var_ext_dn.get() is True
        and app3.var_dn_methode.get() == "Non-local means"
        and abs(app3.var_dn_force.get() - 0.3) < 1e-9,
        "méthode nlm : case restaurée SANS condition de commande")
verifie("-strength 0.9" in app3.var_cmd_graxpert_dn.get(),
        "commande débruitage persistée restaurée telle quelle")
root3.destroy()

ui.CONFIG = {"ext_dn": True, "dn_methode": "inconnu", "dn_force": 0.8}
root4 = tk.Tk()
app4 = ui.App(root4)
root4.update_idletasks()
verifie(app4.var_dn_methode.get() == "GraXpert (IA, lent)",
        "méthode inconnue → défaut graxpert (label)")
root4.destroy()

print()
print("JALONS 7/8 : " + ("TOUS LES TESTS PASSENT" if ok
                         else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)
