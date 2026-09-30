# -*- coding: utf-8 -*-
"""Banc du jalon 84 : DIALOGUES ATTACHÉS À LA FENÊTRE + MESURE DU GEL D'UI.

DÉCLENCHEUR (retour RÉEL d'un testeur sous macOS 27 « Golden Gate »,
30/09/2026) : « les boutons ne sont pas toujours cliquables, par exemple le
bouton "Dossier", mais qui le deviennent après que j'ai cliqué frénétiquement
dessus… le bouton permettant de choisir le dossier à surveiller ne répond pas ».
Diagnostic : TOUS les dialogues de l'application étaient ouverts SANS `parent=`.
Sur macOS, Tk ouvre alors un panneau ou une alerte APPLICATIVE LIBRE
(NSOpenPanel / NSAlert non attaché), qui peut rester DERRIÈRE la fenêtre
principale — laquelle attend la réponse (attente modale) : l'application paraît
insensible, et les clics ne produisent rien tant qu'ils n'atteignent pas la
boîte invisible. Avec `parent=`, Tk demande à macOS une FEUILLE ATTACHÉE, donc
toujours devant son parent.

Ce banc vérifie :
  [1] STATIQUE (analyse du source, pas de regex) : dans `avastack/ui/app.py`,
      AUCUN appel direct à `filedialog.*` / `messagebox.*` hors des six aides —
      un appel oublié ramènerait le défaut — et chacune des six aides demande
      le parent (`_kw_parent`) ;
  [2] les DIALOGUES FICHIER réels (dossier, ouverture, enregistrement) partent
      avec `parent` = la fenêtre, et les options historiques (titre, types de
      fichiers, extension) sont CONSERVÉES ;
  [3] les BOÎTES DE MESSAGE réelles (information, avertissement, erreur) partent
      avec `parent` = la fenêtre — vérifié sur des chemins de l'application, pas
      seulement sur les aides ;
  [4] racine détruite : aucun `parent=None` n'est envoyé (Tk le refuserait) ;
  [5] la boîte maison « unique / couche » est MAPPÉE avant son grab (elle doit
      être affichée avant de bloquer les clics) ;
  [6] le GUET DE GEL mesure vraiment : un fil d'interface retenu au-delà du
      seuil produit UN rapport (durée + PILE du fil fautif, qui nomme ce
      fichier), un seul par gel, et un épisode nouveau en produit un autre ;
  [7] `AVASTACK_SANS_GUET=1` débraye le guet (bancs et exécutions sans écran).

Exécution : python bancs/_test_dialogues_jalon84.py   (nécessite un affichage)
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import ast
import io
import os
import sys
import time
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
import avastack.ui.reactivite as reactivite_mod

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True
RACINE = _pl_banc.Path(__file__).resolve().parents[1]


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- faux journal : le guet ENVELOPPE le vrai code, il n'écrit pas dans le
# journal du développeur pendant un banc.
class FauxJournal:
    def __init__(self):
        self.notes = []

    def note(self, categorie, message):
        self.notes.append((categorie, str(message)))


faux_journal = FauxJournal()
_vrai_journal = reactivite_mod.journal
reactivite_mod.journal = faux_journal

# --- espions : on remplace les boîtes Tk (jamais de dialogue bloquant), et on
# NOTE les arguments reçus — c'est précisément ce qu'on veut verrouiller.
VUS = {"dossier": [], "fichier": [], "enregistrer": [],
       "info": [], "avertir": [], "erreur": []}
_SAUVE = {nom: getattr(ui.filedialog, nom) for nom in
          ("askdirectory", "askopenfilename", "asksaveasfilename")}
_SAUVE.update({nom: getattr(ui.messagebox, nom) for nom in
               ("showinfo", "showwarning", "showerror")})
ui.filedialog.askdirectory = lambda **k: (VUS["dossier"].append(k), "")[1]
ui.filedialog.askopenfilename = lambda **k: (VUS["fichier"].append(k), "")[1]
ui.filedialog.asksaveasfilename = lambda **k: (VUS["enregistrer"].append(k), "")[1]
ui.messagebox.showinfo = lambda t, m, **k: VUS["info"].append((t, m, k))
ui.messagebox.showwarning = lambda t, m, **k: VUS["avertir"].append((t, m, k))
ui.messagebox.showerror = lambda t, m, **k: VUS["erreur"].append((t, m, k))

ui.CONFIG = {}                       # jamais le vrai config.json
ui.sauver_config = lambda d: None

root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
app.guet.arreter()                   # le guet du banc est celui de [6]


# ================================================== [1] STATIQUE : le source
print("[1] Statique : aucun dialogue direct hors des six aides")
AIDES = ("_demander_dossier", "_demander_fichier", "_enregistrer_sous",
         "_dire", "_avertir", "_signaler")
source = io.open(os.path.join(RACINE, "avastack", "ui", "app.py"),
                 encoding="utf-8").read()
arbre = ast.parse(source)
coupables, demandent_parent = [], set()
for classe in [n for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)]:
    for f in [n for n in classe.body if isinstance(n, ast.FunctionDef)]:
        for appel in ast.walk(f):
            if (isinstance(appel, ast.Call)
                    and isinstance(appel.func, ast.Attribute)
                    and isinstance(appel.func.value, ast.Name)
                    and appel.func.value.id in ("filedialog", "messagebox")
                    and f.name not in AIDES):
                coupables.append("%s() ligne %d : %s.%s"
                                 % (f.name, appel.lineno, appel.func.value.id,
                                    appel.func.attr))
        if f.name in AIDES and "_kw_parent" in ast.dump(f):
            demandent_parent.add(f.name)
verifie(not coupables,
        "aucun `filedialog`/`messagebox` direct hors des aides%s"
        % ("" if not coupables else " — COUPABLES : " + " ; ".join(coupables)))
verifie(demandent_parent == set(AIDES),
        "les six aides demandent le parent (vues : %s)"
        % ", ".join(sorted(demandent_parent)))


# ================================== [2] DIALOGUES FICHIER : parent + options
print("[2] Dialogues fichier : parent posé, options historiques conservées")
app._pick_folder()                    # bouton « Dossier où arrivent les brutes »
k = VUS["dossier"][0] if VUS["dossier"] else {}
verifie(k.get("parent") is root,
        "📂 dossier surveillé : `parent` = la fenêtre principale")
verifie(k.get("title") == "Dossier où arrivent les brutes",
        "…et son titre est inchangé (« %s »)" % k.get("title"))

app._load_dark()                      # hors composition : aucun dialogue de rôle
k = VUS["fichier"][0] if VUS["fichier"] else {}
verifie(k.get("parent") is root,
        "🖼 « Charger un dark… » : `parent` = la fenêtre principale")
verifie(isinstance(k.get("filetypes"), list)
        and k["filetypes"][0][0] == "Images",
        "…et ses types de fichiers sont conservés")

app.proc_full = np.zeros((8, 8), np.float32)
app.proc_entete = {}
app._save_proc()                      # annulé par l'espion
k = VUS["enregistrer"][0] if VUS["enregistrer"] else {}
verifie(k.get("parent") is root,
        "💾 « enregistrer sous » : `parent` = la fenêtre principale")
verifie(k.get("defaultextension") == ".fits",
        "…et l'extension par défaut est conservée (.fits)")
app.proc_full = None

# Chemin RÉEL de la ligne « Dossier de travail » (choix annulé par l'espion).
app._choisir_dossier_travail()
k = VUS["dossier"][-1] if VUS["dossier"] else {}
verifie(k.get("parent") is root and "Dossier de travail" in k.get("title", ""),
        "📂 dossier de travail : `parent` posé aussi (titre « %s »)"
        % k.get("title"))


# ==================================== [3] BOÎTES DE MESSAGE : parent posé
print("[3] Boîtes de message : parent posé sur des chemins de l'application")
app._request_ext()                    # aucun empilement → information
verifie(bool(VUS["info"]) and VUS["info"][-1][2].get("parent") is root,
        "information : `parent` = la fenêtre principale")
verifie(bool(VUS["info"]) and VUS["info"][-1][1] == "Aucun empilement à traiter.",
        "…et le message est bien celui de l'application")

_vue = (app.disp.stretch, app.disp.vl_graxpert, app.disp.vl_graxpert_cmd)
app.disp.stretch, app.disp.vl_graxpert = "veralux", True
app.disp.vl_graxpert_cmd = "commande-incomplete-sans-placeholder"
autorise = app._gx_live_prete("banc 84")
verifie(autorise is False and bool(VUS["avertir"])
        and VUS["avertir"][-1][2].get("parent") is root,
        "avertissement (GraXpert incomplet) : `parent` = la fenêtre principale")
(app.disp.stretch, app.disp.vl_graxpert, app.disp.vl_graxpert_cmd) = _vue

app._signaler("Titre banc", "message d'erreur")
verifie(bool(VUS["erreur"]) and VUS["erreur"][-1][2].get("parent") is root,
        "erreur : `parent` = la fenêtre principale")


# ================================== [4] RACINE MORTE : jamais parent=None
print("[4] Racine détruite : aucun `parent=None` envoyé à Tk")


class _FauxRoot:
    def winfo_exists(self):
        return False


_vrai_root = app.root
app.root = _FauxRoot()
vide = app._kw_parent()
app._pick_folder()
k = VUS["dossier"][-1]
verifie(vide == {} and "parent" not in k,
        "fenêtre détruite : aucun `parent` envoyé — jamais `parent=None`, que "
        "Tk refuserait (options reçues : %s)" % sorted(k))
app.root = _vrai_root


# ================================= [5] BOÎTE MAISON : mappée avant le grab
print("[5] Boîte « unique / couche » : mappée AVANT le grab")
attrapes = []
_vrai_grab = tk.Toplevel.grab_set


def _grab(dlg):
    attrapes.append(bool(dlg.winfo_ismapped()))   # état AU MOMENT du grab
    return _vrai_grab(dlg)


def _repondre():
    app._dlg_var.set("unique")
    app._dlg_ok()


tk.Toplevel.grab_set = _grab
root.after(150, _repondre)
resultat = app._dialogue_cible("flat", ["Ha", "O3"])
tk.Toplevel.grab_set = _vrai_grab
verifie(resultat == "unique", "la boîte rend bien la cible choisie")
verifie(bool(attrapes) and all(attrapes),
        "la fenêtre est AFFICHÉE quand le grab est posé (macOS / X11)")


# ========================================= [6] LE GUET MESURE VRAIMENT
print("[6] Guet de gel : un rapport par gel, avec la PILE du fil fautif")
faux_journal.notes.clear()
root.update()                        # le guet exige une fenêtre AFFICHÉE
verifie(bool(root.winfo_viewable()),
        "fenêtre du banc affichée (prérequis du guet — un banc masqué n'a pas "
        "de clic perdu à expliquer)")
guet = reactivite_mod.Guet(root, seuil=0.3)
verifie(guet.demarrer() is True, "guet lancé (seuil de banc : 0,3 s)")
guet.battement()
time.sleep(0.15)                     # SOUS le seuil : rien à signaler
verifie(not guet.rapports, "un retard sous le seuil ne produit AUCUN rapport")

time.sleep(0.6)                      # gel volontaire du fil d'interface
verifie(len(guet.rapports) == 1,
        "gel d'environ 0,75 s → UN rapport (retard mesuré %.2f s)"
        % (guet.rapports[0][0] if guet.rapports else -1))
pile = guet.rapports[0][1] if guet.rapports else ""
verifie("_test_dialogues_jalon84" in pile,
        "…avec la PILE du fil retenu (elle nomme CE fichier)")
notes = [m for c, m in faux_journal.notes if c == "gel de l'interface"]
verifie(any("n'a pas rendu la main" in n for n in notes),
        "…et le journal est prévenu (catégorie « gel de l'interface »)")

time.sleep(0.6)                      # le MÊME gel continue : pas de doublon
verifie(len(guet.rapports) == 1, "le même gel ne produit qu'UN rapport")

guet.battement()                     # l'interface revient…
time.sleep(0.6)                      # …puis gèle de nouveau
verifie(len(guet.rapports) == 2,
        "après reprise, un NOUVEAU gel est rapporté (rien n'est perdu)")
guet.arreter()

n0 = app.guet.battements
app._tick()                          # la boucle d'interface pose son battement
verifie(app.guet.battements == n0 + 1,
        "la boucle d'interface (_tick) pose bien son battement")


# ============================================= [7] DÉBRAYAGE DU GUET
print("[7] `AVASTACK_SANS_GUET=1`, et une fenêtre MASQUÉE, débrayent le guet")
os.environ["AVASTACK_SANS_GUET"] = "1"
g2 = reactivite_mod.Guet(root, seuil=0.2)
verifie(g2.demarrer() is False, "AVASTACK_SANS_GUET=1 → guet NON lancé")
del os.environ["AVASTACK_SANS_GUET"]
g3 = reactivite_mod.Guet(root, seuil=0.2)
verifie(g3.demarrer() is True, "sans la variable, le guet repart")
g2.arreter()
g3.arreter()

# Fenêtre MASQUÉE (bancs, exécution sans écran) : rien à signaler, et surtout
# aucune perturbation des mesures de temps des bancs.
_cachee = tk.Toplevel(root)
_cachee.withdraw()
root.update()
g4 = reactivite_mod.Guet(_cachee, seuil=0.2)
verifie(g4.demarrer() is False and g4.fenetre_visible() is False,
        "fenêtre NON affichée → guet NON lancé (aucun clic perdu à expliquer)")
_cachee.destroy()


# ------------------------------------------------------------------ ménage
guet.arreter()
app.guet.arreter()
reactivite_mod.journal = _vrai_journal
for nom, f in _SAUVE.items():
    if nom in ("askdirectory", "askopenfilename", "asksaveasfilename"):
        setattr(ui.filedialog, nom, f)
    else:
        setattr(ui.messagebox, nom, f)
root.destroy()

print("BANC JALON 84 :", "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)


