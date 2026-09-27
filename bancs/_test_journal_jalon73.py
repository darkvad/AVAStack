# -*- coding: utf-8 -*-
"""Banc du jalon 73 : SI L'APPLICATION NE DÉMARRE PAS, ELLE LE DIT.

Constat déclencheur (Alain, 27/09/2026, v2.38.6, machine Linux) :
« l'appli ne se lance pas sous linux (elle se lance sous windows) », puis,
relancé par l'entrée de menu : « rien du tout : aucune fenêtre, aucun
message ». L'application n'avait ni journal ni autre canal que `stderr` —
invisible pour un lancement par le menu (`.desktop`, `Terminal=false`).

Ce banc vérifie, SANS aucune fenêtre à fermer :
  [1] `journal` : écriture horodatée, ROTATION, repli quand le dossier est
      inaccessible, `trace_env()` (versions, exécutable, Tk, dossier de travail
      et son espace), `erreur()` (traceback COMPLET conservé + texte court avec
      fichier et ligne) ;
  [2] `montrer()` : boîte de dialogue Tk si un affichage existe, repli `stderr`
      sinon, et `AVASTACK_SANS_DIALOGUE=1` qui force le repli ;
  [3] `travail.ouvrir_chemin` : ouvre un FICHIER comme un dossier (le bouton
      « Journal » emprunte le même chemin que « Ouvrir ») ;
  [4] FILET DE DÉMARRAGE : `AVAStack.py` ouvert par chemin — les étapes sont
      journalisées, un `main` qui échoue est journalisé + MONTRÉ, et un
      SOUS-PROCESSUS RÉEL dont l'import de l'interface est cassé rend le code 1
      en laissant le traceback dans `journal.txt` (l'erreur que personne ne
      voyait) ;
  [5] UI réelle : les étapes du démarrage sont au journal, un bouton « Journal »
      existe et ouvre `journal.txt`, et une erreur de RAPPEL Tk
      (`report_callback_exception`) finit dans le journal.

Exécution : python bancs/_test_journal_jalon73.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

import avastack
from avastack import config as config_mod
from avastack import journal
from avastack import travail

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="banc73_")
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_PREVU = os.path.join(TMP, "journal.txt")

# Journal, configuration et dossier de travail DANS le bac à sable : le banc ne
# touche pas aux vrais fichiers (même règle que les bancs d'interface).
_CONFIG_PREVU = config_mod.CONFIG
_SAUVE_DOSSIER_CONFIG = config_mod.dossier_config
config_mod.dossier_config = lambda: TMP
config_mod.CONFIG = {}
_DOSSIER_JOURNAL = journal.dossier_journal
journal.dossier_journal = lambda: TMP


def lire_journal():
    """Contenu du journal du banc ("" s'il n'existe pas encore)."""
    try:
        with open(JOURNAL_PREVU, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def purger_journal():
    for chemin in (JOURNAL_PREVU, JOURNAL_PREVU + ".1"):
        try:
            os.remove(chemin)
        except OSError:
            pass


# ==================================== [1] journal : notes, rotation, erreurs
print("[1] journal : où, quand, quoi — et jamais d'exception")
purger_journal()
verifie(journal.chemin_journal() == JOURNAL_PREVU,
        "chemin du journal dans le dossier de configuration : %s"
        % journal.chemin_journal())
ecrit = journal.note("test", "ligne du banc")
contenu = lire_journal()
verifie(ecrit and "test — ligne du banc" in contenu
        and contenu.startswith(time.strftime("%Y-%m-%d")),
        "note horodatée écrite (« %s… »)" % contenu.strip()[:44])

# Rotation : au-delà de la taille maximale, le journal courant devient .1.
_de_max = journal.TAILLE_MAX
journal.TAILLE_MAX = 200
for _i in range(6):
    journal.note("gonflage", "x" * 40)
journal.TAILLE_MAX = _de_max
journal.note("après-rotation", "nouvelle écriture")
ancien = ""
try:
    with open(JOURNAL_PREVU + ".1", encoding="utf-8", errors="replace") as f:
        ancien = f.read()
except OSError:
    pass
verifie("ligne du banc" in ancien and "gonflage" in ancien
        and "après-rotation" in lire_journal()
        and "ligne du banc" not in lire_journal(),
        "rotation : les notes anciennes partent dans journal.txt.1, "
        "le courant repart de zéro")

env = journal.trace_env()
verifie("AVAStack " in env and "exe=" in env and "Tk " in env
        and "travail=" in env and "libres" in env,
        "trace_env() : %s…" % env[:76])
verifie(env.startswith("AVAStack " + avastack.AVASTACK_VERSION),
        "trace_env() commence par la version d'AVAStack (%s)"
        % avastack.AVASTACK_VERSION)


def _exception_test():
    """Exception dans une fonction dédiée : le traceback doit la nommer."""
    raise ValueError("panne simulée du banc")


try:
    _exception_test()
except ValueError as e:
    court = journal.erreur("démarrage", e)
verifie(court.startswith("ERREUR démarrage : ValueError: panne simulée du banc")
        and "ligne" in court,
        "erreur() : texte court « %s »" % court)
après = lire_journal()
verifie("Traceback (most recent call last)" in après
        and "_exception_test" in après,
        "erreur() : traceback COMPLET conservé (nom de la fonction compris)")

# Dossier inaccessible : journaliser ne doit JAMAIS lever (service, pas
# dépendance) — le banc force l'échec d'écriture plutôt que de le supposer.
_sauvé_dossier = journal.chemin_journal
journal.chemin_journal = lambda: os.path.join(TMP, "interdit", "journal.txt")
os.makedirs(os.path.join(TMP, "interdit"))
os.chmod(os.path.join(TMP, "interdit"), 0o500)
reussite = journal.note("interdit", "ne doit pas lever")
os.chmod(os.path.join(TMP, "interdit"), 0o700)
journal.chemin_journal = _sauvé_dossier
verifie(reussite in (True, False),
        "note() sur dossier inaccessible : aucune exception (→ %s)" % reussite)


# ================================================== [2] montrer() : visible
# AUCUNE fenêtre ne doit s'ouvrir pendant le banc : on force le repli écrit
# (`AVASTACK_SANS_DIALOGUE`), et on ne teste la boîte que si un affichage
# existe VRAIMENT (sans écran, Tk refuse — c'est le cas à couvrir, pas un
# défaut).
print("[2] montrer() : boîte de dialogue si un affichage existe, sinon stderr")
os.environ["AVASTACK_SANS_DIALOGUE"] = "1"
try:
    import tkinter as _tk_test
    _r = _tk_test.Tk()
    _r.withdraw()
    _r.destroy()
    affichage = True
except Exception:
    affichage = False
verifie(True, "affichage graphique : %s" % ("présent" if affichage else "absent"))

if affichage:
    from tkinter import messagebox
    vus = []
    _sauve_showerror = messagebox.showerror
    messagebox.showerror = lambda titre, txt, **k: vus.append((titre, txt))
    _sauve_var = os.environ.pop("AVASTACK_SANS_DIALOGUE")   # on teste la boîte
    try:
        mode = journal.montrer("Titre du banc", "message du banc")
    finally:
        os.environ["AVASTACK_SANS_DIALOGUE"] = "1"
        messagebox.showerror = _sauve_showerror
    verifie(mode == "boite" and vus and vus[0][0] == "Titre du banc"
            and JOURNAL_PREVU in vus[0][1],
            "montrer() : boîte affichée, avec le chemin du journal")

# Repli forcé (celui d'un lancement sans personne devant l'écran).
_err = io.StringIO()
_sauve_stderr = sys.stderr
sys.stderr = _err
try:
    mode = journal.montrer("Titre du banc", "repli écrit du banc")
finally:
    sys.stderr = _sauve_stderr
verifie(mode == "stderr" and "repli écrit du banc" in _err.getvalue(),
        "montrer() : repli stderr (AVASTACK_SANS_DIALOGUE)")

# Tk indisponible (« tkinter manquant » = la panne Linux à diagnostiquer).
def _tk_ko(*_a, **_k):
    raise RuntimeError("pas d'affichage (banc)")
_sauve_Tk_module = _tk_test.Tk
_tk_test.Tk = _tk_ko
_err = io.StringIO()
_sauve_stderr = sys.stderr
sys.stderr = _err
try:
    mode = journal.montrer("Titre du banc", "Tk cassé")
finally:
    sys.stderr = _sauve_stderr
    _tk_test.Tk = _sauve_Tk_module
verifie(mode == "stderr" and "Tk cassé" in _err.getvalue(),
        "montrer() : Tk en échec → repli stderr")
# NB : `AVASTACK_SANS_DIALOGUE` reste posé pour la suite du banc (aucune boîte
# ne doit s'ouvrir) ; on le retire à la toute fin (cf. `restaure()`).


# ==================================== [3] ouvrir_chemin : un FICHIER s'ouvre
print("[3] ouvrir_chemin : fichier comme dossier (même bouton, même route)")
fichier = os.path.join(TMP, "element.txt")
with open(fichier, "w", encoding="utf-8") as f:
    f.write("banc\n")
appels = []
_sauve_startfile = getattr(os, "startfile", None)
_sauve_popen = subprocess.Popen
os.startfile = lambda c: appels.append(c)          # Windows (créé au besoin)
subprocess.Popen = lambda cmd, *a, **k: appels.append(cmd)
try:
    err_fichier = travail.ouvrir_chemin(fichier)
    err_dossier = travail.ouvrir_dossier(TMP)
finally:
    subprocess.Popen = _sauve_popen
    if _sauve_startfile is None:
        del os.startfile
    else:
        os.startfile = _sauve_startfile
verifie(err_fichier == "" and err_dossier == "" and appels
        and appels[0] == fichier,
        "ouvrir_chemin(FICHIER) et ouvrir_dossier(dossier) → outil de l'OS")


# ============================================ [4] filet de démarrage (A→Z)
print("[4] filet de démarrage : AVAStack.py journalise PUIS montre l'échec")
from avastack.ui import app as ui      # noqa: E402  (lourd : import volontaire ici)
from tkinter import ttk                # noqa: E402

_sauve_montrer = journal.montrer
montres = []
journal.montrer = lambda titre, msg: (montres.append((titre, msg)), "banc")[1]

# Le script d'entrée est chargé SANS exécuter son bloc `__main__` (le nom du
# module n'est pas "__main__") : on appelle donc ses deux fonctions, comme le
# ferait l'exécution réelle.
_spec = importlib.util.spec_from_file_location(
    "avastack_entree_banc", os.path.join(RACINE, "AVAStack.py"))
entree = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(entree)
verifie(entree.journal is journal,
        "AVAStack.py charge le journal AVANT le reste de l'application")

purger_journal()
appels_main = []
_sauve_main = ui.main
ui.main = lambda: appels_main.append("main")
try:
    code = entree._demarrer()
finally:
    ui.main = _sauve_main
contenu = lire_journal()
verifie(appels_main == ["main"] and code is None,
        "_demarrer() ouvre l'interface (%d appel de main)" % len(appels_main))
verifie("interface importée" in contenu and "arrêt" in contenu
        and "travail=" in contenu and "Tk " in contenu,
        "étapes ET environnement journalisés (dossier de travail compris)")


def _main_ko():
    """Panne simulée d'import d'interface : celle qui était muette sous Linux."""
    raise ImportError("dépendance simulée absente du venv")


purger_journal()
ui.main = _main_ko
code = None
try:
    entree._demarrer()
except BaseException as e:                 # ce que fait le bloc __main__
    code = entree._echec(e)
finally:
    ui.main = _sauve_main
contenu = lire_journal()
verifie(code == 1 and "ERREUR démarrage" in contenu
        and "ImportError: dépendance simulée absente du venv" in contenu
        and "Traceback" in contenu,
        "_échec() : code 1, traceback COMPLET dans le journal")
verifie(montres and "ne peut pas démarrer" in montres[-1][0]
        and journal.chemin_journal() in montres[-1][1],
        "l'échec est MONTRÉ (titre « %s ») et renvoie au journal"
        % (montres[-1][0] if montres else "—"))

# --- Sous-processus RÉEL : import de l'interface cassé, comme le 27/09/2026
# Il n'y a pas de meilleure mesure qu'une vraie exécution : la copie de
# l'application est cassée dans le bac à sable, et on regarde ce que L'UTILIS-
# ATEUR verrait (code de sortie, message, journal écrit sur disque).
bac = os.path.join(TMP, "app_cassee")
shutil.copytree(os.path.join(RACINE, "avastack"), os.path.join(bac, "avastack"),
                ignore=shutil.ignore_patterns("__pycache__"))
shutil.copy2(os.path.join(RACINE, "AVAStack.py"),
             os.path.join(bac, "AVAStack.py"))
with open(os.path.join(bac, "avastack", "ui", "app.py"), "w",
          encoding="utf-8") as f:
    f.write("raise ImportError('dépendance simulée absente du venv')\n")
conf = os.path.join(bac, "conf")
env = dict(os.environ)
env.update({"AVASTACK_SANS_DIALOGUE": "1", "XDG_CONFIG_HOME": conf,
            "APPDATA": conf, "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1"})
proc = subprocess.run([sys.executable, "AVAStack.py"], cwd=bac, env=env,
                      capture_output=True, encoding="utf-8", errors="replace",
                      timeout=300)
journal_cassee = os.path.join(conf, "AVAStack", "journal.txt")
try:
    with open(journal_cassee, encoding="utf-8", errors="replace") as f:
        trace = f.read()
except OSError:
    trace = ""
verifie(proc.returncode == 1,
        "sous-processus : code de sortie 1 (→ %s)" % proc.returncode)
verifie("Traceback" in trace and "ImportError" in trace
        and "dépendance simulée absente du venv" in trace,
        "sous-processus : le traceback est ÉCRIT dans journal.txt")
verifie("ne peut pas démarrer" in (proc.stderr or ""),
        "sous-processus : stderr dit l'échec (repli sans dialogue)")


# ================================ [5] UI réelle : journal, bouton, rappels Tk
print("[5] UI réelle : étapes au journal, bouton « Journal », rappel fautif")
_sauve_ui_config = ui.CONFIG
_sauve_sauver = ui.sauver_config
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None


class _RacineFactice:
    """Racine Tk factice : on vérifie le CÂBLAGE de `main()` sans ouvrir de
    fenêtre (aucune boîte de dialogue ne doit attendre le banc)."""
    def __init__(self):
        self.report_callback_exception = None
        self.tours = []

    def mainloop(self):
        self.tours.append("mainloop")


faux = _RacineFactice()
_sauve_Tk_ui = ui.tk.Tk
_sauve_App = ui.App
ui.tk.Tk = lambda: faux
ui.App = lambda racine: racine
try:
    ui.main()
finally:
    ui.tk.Tk = _sauve_Tk_ui
    ui.App = _sauve_App
verifie(faux.report_callback_exception is journal.rapport_callback
        and faux.tours == ["mainloop"],
        "main() : `report_callback_exception` branché sur la racine Tk")

import tkinter as tk       # noqa: E402

root = tk.Tk()
root.withdraw()
root.report_callback_exception = journal.rapport_callback   # ce que fait main()
purger_journal()
ui.CONFIG = {}
application = ui.App(root)                                  # noqa: F841
contenu = lire_journal()
verifie("construction de l'interface" in contenu
        and "restauration de la configuration" in contenu
        and "prêt" in contenu,
        "démarrage de l'interface : étapes journalisées")

boutons = []


def _chercher_journal(widget):
    for enfant in widget.winfo_children():
        if isinstance(enfant, ttk.Button) and enfant.cget("text") == "Journal":
            boutons.append(enfant)
        _chercher_journal(enfant)


_chercher_journal(root)
ouvert = []
_sauve_ouvrir = journal.ouvrir
journal.ouvrir = lambda: (ouvert.append(1), "")[1]
try:
    if boutons:
        boutons[0].invoke()
finally:
    journal.ouvrir = _sauve_ouvrir
verifie(len(boutons) == 1 and ouvert == [1],
        "bouton « Journal » présent et branché (%d bouton trouvé)"
        % len(boutons))

# Erreur dans un RAPPEL Tk (clic, curseur, touche) : Tk l'engloutissait sur
# stderr — elle doit maintenant laisser une trace dans le journal.
purger_journal()


def _rappel_ko():
    """Rappel fautif : exactement ce que fait un clic dont le code casse."""
    raise ZeroDivisionError("rappel fautif du banc")


root.after(0, _rappel_ko)
time.sleep(0.2)
root.update()
contenu = lire_journal()
verifie("rappel d'interface" in contenu and "ZeroDivisionError" in contenu,
        "erreur de rappel Tk : journalisée")

root.destroy()

# --- fin du banc : tout est remis en place
journal.montrer = _sauve_montrer
journal.dossier_journal = _DOSSIER_JOURNAL
ui.CONFIG = _sauve_ui_config
ui.sauver_config = _sauve_sauver
config_mod.CONFIG = _CONFIG_PREVU
config_mod.dossier_config = _SAUVE_DOSSIER_CONFIG
os.environ.pop("AVASTACK_SANS_DIALOGUE", None)
shutil.rmtree(TMP, ignore_errors=True)

print("\nBANC JALON 73 (journal et filet de démarrage) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)



