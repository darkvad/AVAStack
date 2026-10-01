# -*- coding: utf-8 -*-
"""Banc du jalon 87 (v2.48.1) — LA BOUCLE D'INTERFACE NE PEUT PLUS GELER.

DÉCLENCHEUR (retour RÉEL du testeur macOS, 30/09/2026, v2.47.0) : son journal se
termine par

    ERREUR rappel d'interface : TclError: invalid command name
    ".!panedwindow.!frame.!canvas.!frame.!labelframe7.!label11"
    File "app.py", line 8779, in _tick
        self._maj_libelle_fit()

`_tick` se replanifiait en DERNIÈRE ligne (`after(30, _tick)`) : la moindre
exception tuait la boucle POUR DE BON — et l'interface restait GELÉE (c'est le
« les boutons ne répondent plus » du testeur). Ce banc vérifie la conception
neuve :

  [1] `_widget_vivant` : True sur un widget vivant, False sur un widget DÉTRUIT
      (SANS exception) et sur None — la SEULE interrogation sûre pour savoir si
      un rafraîchissement a encore un sens ;
  [2] `_maj_libelle_fit` sur un `lbl_fit` DÉTRUIT : ne lève PLUS (il se tait) —
      c'est EXACTEMENT le cas du journal macOS ;
  [3] `_tick` : une exception du corps est ÉCRITE au journal (une fois par
      épisode, pas 33 fois par seconde) MAIS la boucle est REPLANIFIÉE — et
      jamais deux fois par tour (sinon le travail doublerait à chaque tick) ;
  [4] `_on_close` : la replanification en attente est ANNULÉE avant la
      destruction de la fenêtre — plus d'`after` orphelin (« invalid command
      name » à la fermeture).

Nécessite un affichage. Exécution : python bancs/_test_ui_robuste_jalon87.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import tkinter as tk
from tkinter import ttk

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


import avastack.ui.app as ui                                        # noqa: E402


# --- journal de test : n'écrit JAMAIS dans le vrai journal.txt --------------
_vrai_journal = ui.journal


class _JournalDeTest:
    """Doublure de `journal` : le banc ne doit pas polluer le journal réel."""

    def __init__(self):
        self.erreurs = []
        self.notes = []

    def note(self, etape, detail=""):
        self.notes.append((etape, detail))
        return True

    def etape(self, nom, detail=""):
        self.notes.append((nom, detail))
        return True

    def erreur(self, contexte="", exc=None):
        self.erreurs.append(contexte)
        return ""


faux = _JournalDeTest()
ui.journal = faux                    # app.py lit `journal` au niveau MODULE
ui.CONFIG = {}                       # jamais le vrai config.json du poste
ui.sauver_config = lambda d: None
os.environ["AVASTACK_SANS_GUET"] = "1"     # pas de guet dans un banc

# ======================================================= [1] _widget_vivant
print("[1] _widget_vivant : la seule interrogation SÛRE d'un widget")
root = tk.Tk()
root.withdraw()
lab = ttk.Label(root, text="vivant")
lab.pack()
root.update_idletasks()
verifie(ui.App._widget_vivant(lab) is True, "widget VIVANT → True")
lab.destroy()
root.update_idletasks()
verifie(ui.App._widget_vivant(lab) is False,
        "widget DÉTRUIT → False, SANS exception (winfo exists)")
verifie(ui.App._widget_vivant(None) is False, "None → False")

# ================================================== [2] _maj_libelle_fit
print("[2] _maj_libelle_fit : se TAIT sur un widget détruit (cas du journal)")
app = ui.App(root)
root.update_idletasks()
app.stacker = None
app._maj_libelle_fit()
verifie(True, "libellé vivant : aucun bruit")
app.lbl_fit.destroy()
root.update_idletasks()
leve = False
try:
    app._maj_libelle_fit()
except Exception:
    leve = True
verifie(not leve,
        "lbl_fit DÉTRUIT : `_maj_libelle_fit` ne lève PLUS (il se tait) — "
        "c'est l'exception « invalid command name » du testeur macOS")

# ============================== [3] _tick : une exception ne tue plus la boucle
print("[3] _tick : une exception du corps NE TUE PLUS la boucle")
planifs = []
vrai_plan = app._planifier_tick


def compte_plan(delai=30):
    planifs.append(delai)
    return vrai_plan(delai)


app._planifier_tick = compte_plan
# Le corps RÉEL ferait tourner les sondes de disque différées (un fil qui peut
# écrire au journal) : on l'isole — ce banc teste la PROTECTION de `_tick`, pas
# le corps lui-même.
app._demander_mesures = lambda *a, **k: None
etat = {"n": 0}


def corps_qui_casse():
    etat["n"] += 1
    if etat["n"] == 1:
        raise tk.TclError('invalid command name ".!faux.!label"')


app._tick_corps = corps_qui_casse
app._tick()                          # 1er tour : le corps CASSE
verifie(len(planifs) == 1,
        "corps en exception → la boucle est REPLANIFIÉE (une fois quand même)")
verifie(len(faux.erreurs) == 1, "l'erreur est écrite UNE fois au journal")
verifie(app._tick_err_sig is not None, "l'épisode d'erreur est mémorisé")
app._tick()                          # 2e tour : le corps RÉUSSIT
verifie(len(planifs) == 2,
        "une seule replanification par tour (jamais deux — le travail ne "
        "double pas)")
verifie(app._tick_err_sig is None and len(faux.erreurs) == 1,
        "épisode clos : signature oubliée, rien de nouveau écrit")

# ================================= [4] _on_close : plus d'`after` orphelin
print("[4] _on_close : la replanification en attente est ANNULÉE")
r2 = tk.Tk()
r2.withdraw()
app2 = ui.App(r2)
r2.update_idletasks()
verifie(app2._tick_id is not None,
        "au démarrage de la fenêtre, une replanification est en attente")
app2.running = False
app2._on_close()
verifie(app2._tick_id is None,
        "fermeture : la replanification est ANNULÉE (plus d'`after` orphelin "
        "qui lèverait « invalid command name » après la destruction)")
try:
    detruite = not r2.winfo_exists()
except tk.TclError:                  # racine détruite : winfo peut lever
    detruite = True
verifie(detruite, "la fenêtre est bien détruite (la fermeture aboutit)")

# --------------------------------------------------------------------- ménage
ui.journal = _vrai_journal
os.environ.pop("AVASTACK_SANS_GUET", None)

print()
print("BANC JALON 87 (interface robuste) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

