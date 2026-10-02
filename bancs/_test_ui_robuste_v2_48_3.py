# -*- coding: utf-8 -*-
"""Banc du jalon 95 (v2.48.3) -- _tick_corps TAIL LA ZONE
"TRAITEMENT EXTERNE" QUAND ELLE DISPARAIT.

Declencheur (retour macOS du 01/10/2026, v2.48.1 et v2.48.2) : le journal du
testeur se terminait par

    ERREUR boucle d'interface (widget detruit ?) : TclError: invalid command
    name ".!panedwindow.!frame.!canvas.!frame.!labelframe13.!button"
    File "app.py", line 8884, in _tick
        self._tick_corps()
    File "app.py", line 9254, in _tick_corps
        self.btn_ext.config(state="disabled"

_tick_corps touchait btn_save_proc.config, lbl_ext.config (x2) et
btn_ext.config SANS protection _widget_vivant. _journal_erreur_tick filtre
par episode (_tick_err_sig) : une seule ligne dans le journal meme si
l'exception revient 33 fois par seconde, et la boucle survit mais TOUS les
rafraichissements d'interface meurent (les boutons ne repondent plus, les
combobox ne s'ouvrent plus, le statut ne se met plus a jour). Le filet pose
au jalon 87 ne couvrait QUE _maj_libelle_fit ; cette zone (Traitement externe)
avait ete oubliee.

Ce banc verifie la conception neuve -- il cible LA ZONE qui etait non gardee
(btn_save_proc, lbl_ext, btn_ext dans le cadre "Traitement externe"). Le
reste de _tick_corps n'est PAS couvert par le correctif (le scope du jalon est
precis, voir AVANCEMENT.md / CLAUDE.md) :

  [1] STATIQUE -- analyse du source _tick_corps : les .config( de la zone
      ciblee sont desormais TOUS precedes d'un _widget_vivant(.
  [2] DYNAMIQUE -- detruire btn_ext / lbl_ext / btn_save_proc puis appeler
      _tick_corps ne leve PLUS TclError et _journal_erreur_tick n'ecrit plus.
  [3] DYNAMIQUE -- les widgets EN VIE ne sont PAS affectes par les gardes.

Necessite un affichage. Execution : python bancs/_test_ui_robuste_v2_48_3.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import ast
import os
import sys
import time as _t
import tkinter as tk
from tkinter import ttk

if hasattr(sys.stdout, "reconfigure"):     # sortie pipee != console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ECHEC ") + msg)


import avastack.ui.app as ui                                        # noqa: E402


# --- journal de test : n'ecrit JAMAIS dans le vrai journal.txt --------------
_vrai_journal = ui.journal


class _JournalDeTest:
    """Doublure de journal : le banc ne doit pas polluer le journal reel."""

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
ui.journal = faux                    # app.py lit journal au niveau MODULE
ui.CONFIG = {}                       # jamais le vrai config.json du poste
ui.sauver_config = lambda d: None
# ========================================== [1] STATIQUE -- analyse de source
print("[1] _tick_corps : la zone 'Traitement externe' est gardee")
SRC = ui.__file__
with open(SRC, "r", encoding="utf-8") as f:
    src_text = f.read()
arbre = ast.parse(src_text)


def corps_de_tick_corps(arbre):
    """Repere le corps de def _tick_corps(self) et rend le noeud."""
    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef) and n.name == "_tick_corps":
            return n
    return None


noeud = corps_de_tick_corps(arbre)
if noeud is None:
    verifie(False, "_tick_corps introuvable dans le source")
else:
    # Bloc de _tick_corps : depuis sa 1re ligne jusqu'a la 1re ligne de
    # niveau 0 (autre def).
    lignes_src = src_text.splitlines()
    deb = noeud.body[0].lineno
    fin = deb
    for lno in range(deb, len(lignes_src)):
        txt = lignes_src[lno - 1]
        if txt.strip() and not (txt.startswith("    ") or txt.startswith("\t")):
            break
        fin = lno
    bloc = [(idx + 1, lignes_src[idx - 1])
            for idx in range(deb - 1, fin)]
    # Cibles du jalon : uniquement les .config( de la zone
    # "Traitement externe" -- btn_save_proc, lbl_ext, btn_ext.
    cibles = {"btn_save_proc", "lbl_ext", "btn_ext"}
    fenetre = 15
    nb_vues = 0
    for i, (ln, txt) in enumerate(bloc):
        code = txt.split("#", 1)[0]
        if ".config(" not in code:
            continue
        # On ne regarde que les widgets cibles du jalon.
        cible_trouvee = None
        for c in cibles:
            if f"self.{c}.config(" in code:
                cible_trouvee = c
                break
        if cible_trouvee is None:
            continue
        nb_vues += 1
        precedent_code = "\n".join(
            l.split("#", 1)[0] for _, l in bloc[max(0, i - fenetre):i + 1])
        # La garde doit etre on _widget_vivant(getattr(self, CIBLE, None)).
        # On accepte la cible OU le label du meme LabelFrame (lbl_ext peut
        # etre garde par lui-meme OU par btn_ext, le label de zone etant
        # partage). On accepte donc tout _widget_vivant(getattr(self, C, ))
        # ou C est l'un des widgets cibles.
        garde = False
        for c in cibles:
            if f'_widget_vivant(getattr(self, "{c}"' in precedent_code:
                garde = True
                break
        verifie(garde,
                f"ligne {ln} : {cible_trouvee}.config garde par _widget_vivant ?")
    if nb_vues == 0:
        verifie(False, "aucun .config( cible trouve -- scope du jalon modifie ?")
os.environ["AVASTACK_SANS_GUET"] = "1"     # pas de guet dans un banc
# ===================================== [2] DYNAMIQUE -- widget detruit, _tick_corps
print()
print("[2] _tick_corps : un widget detruit TAIT toute la zone, sans exception")
r3 = tk.Tk()
r3.withdraw()
app3 = ui.App(r3)
r3.update_idletasks()
# Cas EXACT du journal macOS : btn_ext est dans le cadre "Traitement externe".
app3.btn_ext.destroy()
r3.update_idletasks()
app3.journal = faux
leve = False
try:
    app3._tick_corps()
except tk.TclError as exc:
    leve = True
    print(f"    >> _tick_corps LEVE ENCORE : {exc}")
verifie(not leve,
        "_tick_corps sur btn_ext detruit : ne leve PLUS (la garde l'arrete)")
verifie(len(faux.erreurs) == 0,
        "_tick_corps sur btn_ext detruit : AUCUNE ligne d'erreur journalisee")

print()
print("[2b] _tick_corps : lbl_ext detruit -> meme silence")
r3b = tk.Tk()
r3b.withdraw()
appb = ui.App(r3b)
r3b.update_idletasks()
faux_b = _JournalDeTest()
appb.journal = faux_b
appb.lbl_ext.destroy()
r3b.update_idletasks()
appb.ext_msg = "TEST jalon 95"
appb._ext_shown = ""
appb.ext_busy = True
appb.ext_t0 = _t.time() - 1.0
leve = False
try:
    appb._tick_corps()
except tk.TclError as exc:
    leve = True
    print(f"    >> _tick_corps LEVE ENCORE sur lbl_ext : {exc}")
verifie(not leve,
        "_tick_corps sur lbl_ext detruit : ne leve PLUS")
verifie(len(faux_b.erreurs) == 0,
        "_tick_corps sur lbl_ext detruit : AUCUNE ligne d'erreur journalisee")

print()
print("[2c] _tick_corps : btn_save_proc detruit -> meme silence")
r3c = tk.Tk()
r3c.withdraw()
appc = ui.App(r3c)
r3c.update_idletasks()
faux_c = _JournalDeTest()
appc.journal = faux_c
appc.btn_save_proc.destroy()
r3c.update_idletasks()
# Forcer proc_new pour entrer dans le bloc btn_save_proc
appc.proc_new = True
leve = False
try:
    appc._tick_corps()
except tk.TclError as exc:
    leve = True
    print(f"    >> _tick_corps LEVE ENCORE sur btn_save_proc : {exc}")
appc.proc_new = False
verifie(not leve,
        "_tick_corps sur btn_save_proc detruit : ne leve PLUS")
verifie(len(faux_c.erreurs) == 0,
        "_tick_corps sur btn_save_proc detruit : AUCUNE ligne d'erreur journalisee")

# ================================ [3] DYNAMIQUE -- widgets EN VIE, aucun effet
print()
print("[3] _tick_corps : widgets EN VIE -> gardes True, execution normale")
r4 = tk.Tk()
r4.withdraw()
app4 = ui.App(r4)
r4.update_idletasks()
faux_4 = _JournalDeTest()
app4.journal = faux_4
leve = False
try:
    app4._tick_corps()
except Exception as exc:
    leve = True
    print(f"    >> _tick_corps LEVE sur widgets en vie : {exc!r}")
verifie(not leve,
        "_tick_corps sur widgets en vie : Aucun changement de comportement")
verifie(app4._widget_vivant(app4.btn_ext) is True,
        "_widget_vivant(btn_ext) rend True sur widget vivant (sanity check)")
verifie(app4._widget_vivant(app4.lbl_ext) is True,
        "_widget_vivant(lbl_ext) rend True sur widget vivant (sanity check)")
verifie(app4._widget_vivant(app4.btn_save_proc) is True,
        "_widget_vivant(btn_save_proc) rend True sur widget vivant (sanity check)")

# --------------------------------------------------------------------- menage
ui.journal = _vrai_journal
os.environ.pop("AVASTACK_SANS_GUET", None)

print()
print("BANC JALON 95 (zone << Traitement externe >> gardee) :",
      "TOUT AU VERT " if ok else "ECHECS ")
sys.exit(0 if ok else 1)