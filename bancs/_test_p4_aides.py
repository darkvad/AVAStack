# -*- coding: utf-8 -*-
"""Banc P4 (lot 3, v2.95.0) — les AIDES de la colonne passent en infobulles.

CONSTAT DÉCLENCHEUR (Alain, 19/10/2026) : « la colonne de gauche est pleine de
textes d'aide gris, on ne voit plus les réglages ». Mesuré sur la VRAIE
interface (`bancs/_mesure_p4_aides.py`) : les textes d'aide prenaient
**702 px de plus que les « ⓘ »** qui les remplacent (46,8 lignes, 13 % de la
colonne) — et davantage encore avec les cadres « Fusion Ha » / « Affichage »
dépliés.

Ce banc vérifie, SANS toucher au vrai config.json :
  [1] `Bulle` — création PARESSEUSE, délai de 400 ms, UNE seule bulle à la
      fois, fermeture (sortie, clic, Échap), position DANS l'écran ;
  [2] `astuce` — souris ET clavier (survol, focus, Échap), destruction ;
  [3] `App._aide` — mode TEXTE (`aides_texte`) : étiquette grise posée, « ⓘ »
      absent ; mode BULLES (défaut) : l'inverse, et la bulle porte le texte ;
  [4] les 13 aides sont TOUTES passées par `_aide` (aucun texte gris orphelin
      dans la colonne) et la place est réellement reprise (mesure) ;
  [5] la case « Aides en texte dans la colonne » bascule À CHAUD et persiste
      la clé (sauver_config intercepté) ;
  [6] géométrie : aucun « ⓘ » écrasé (pack l'abandonne en silence quand la
      place manque — leçon du jalon 72).

Exécution : python bancs/_test_p4_aides.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time

import cv2

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

cv2.ocl.setUseOpenCL(False)

import tkinter as tk                       # noqa: E402
from tkinter import ttk                    # noqa: E402

import avastack.config as config_mod       # noqa: E402
import avastack.ui.app as app_mod          # noqa: E402
from avastack.ui import bulles             # noqa: E402

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def pomper(root, secondes):
    """Fait tourner la boucle Tk `secondes` (les `after` doivent s'exécuter)."""
    fin = time.time() + secondes
    while time.time() < fin:
        root.update()
        time.sleep(0.01)


# --- [1]/[2] La bulle et sa liaison, sur une fenêtre nue --------------------
print("[1] Bulle : paresse, délai, unicité, fermeture, position")
root = tk.Tk()
root.geometry("300x200+40+40")
root.update()
cible = ttk.Label(root, text="ⓘ", takefocus=True)
cible.pack()
root.update()

b = bulles.astuce(cible, "Texte d'aide de contrôle")
verifie(b._fenetre is None, "création PARESSEUSE (aucune fenêtre avant le survol)")
cible.event_generate("<Enter>")
root.update()
verifie(b.visible() is False, "rien avant 400 ms (délai de la spec P4)")
pomper(root, 0.55)
verifie(b.visible() is True, "affichée après le délai : %s" % b.visible())
verifie(b._fenetre is not None and b._fenetre.winfo_exists(),
        "fenêtre réellement créée")
_libelle = [w for w in b._fenetre.winfo_children()[0].winfo_children()
            if isinstance(w, tk.Label)]
verifie(bool(_libelle) and _libelle[0].cget("text") == "Texte d'aide de contrôle",
        "la bulle PORTE le texte de l'aide")
_x, _y = b._fenetre.winfo_rootx(), b._fenetre.winfo_rooty()
verifie(0 <= _x < root.winfo_screenwidth()
        and 0 <= _y < root.winfo_screenheight(),
        "position DANS l'écran (%d, %d)" % (_x, _y))
verifie(b._fenetre.overrideredirect(), "pas de décoration (overrideredirect)")
cible.event_generate("<Leave>")
root.update()
verifie(b.visible() is False, "la sortie de la souris referme")

# Échap est une touche : Tk la livre au widget qui a le FOCUS (un
# `event_generate` sans focus part ailleurs) — on force donc le focus AVANT
# de pomper, pour que la bulle soit ouverte par le clavier lui-même.
cible.focus_force()
pomper(root, 0.55)
verifie(b.visible() is True, "le CLAVIER l'ouvre aussi (FocusIn)")
cible.event_generate("<Escape>")
root.update()
verifie(b.visible() is False, "Échap la referme")

b2 = bulles.astuce(cible, "Deuxième aide")
b.montrer()
root.update()
b2.montrer()
root.update()
verifie(b.visible() is False and b2.visible() is True,
        "UNE SEULE bulle à la fois (la précédente se referme)")
b2.cacher()
verifie(b2.visible() is False, "cacher() referme")

# Destruction du widget → la bulle ne survit pas (aucune fenêtre orpheline).
cible.destroy()
verifie(b._fenetre is None and b2._fenetre is None,
        "détruire le widget détruit ses bulles")
root.destroy()
print()

# --- [3]/[4]/[5]/[6] L'application RÉELLE ----------------------------------
print("[3] App._aide : 14 aides (13 de P4 + celle du panneau Stacks), mode BULLES par défaut")
config_mod.CONFIG.clear()
app_mod.CONFIG = config_mod.CONFIG          # jamais le vrai config.json
_intercepte = {}
app_mod.sauver_config = lambda d: _intercepte.update(d)
root = tk.Tk()
root.withdraw()
ui = app_mod.App(root)
root.update_idletasks()

aides = getattr(ui, "_aides", [])
# P6 (lot 5) : le panneau « Stacks (fichiers FITS) » porte une 14e aide. Elle
# suit la MÊME règle que les 13 autres (un point de passage unique `_aide`) :
# son texte n'apparaît donc PAS en gris dans la colonne.
verifie(len(aides) == 14, "14 aides déclarées (mesuré : %d)" % len(aides))
verifie(all(a.texte.winfo_manager() == "" for a in aides),
        "mode BULLES (défaut) : AUCUNE étiquette de texte posée")
verifie(all(a.info.winfo_manager() == "pack" for a in aides),
        "les 14 « ⓘ » sont posés")
verifie(all(a.info.cget("text") == "ⓘ" for a in aides),
        "chaque aide porte bien le caractère ⓘ")
verifie(all(a.info.cget("takefocus") in ("1", 1, True) for a in aides),
        "les « ⓘ » sont atteignables au CLAVIER (takefocus)")
verifie(config_mod.CONFIG.get("aides_texte") is None,
        "défaut NON : la clé n'est pas fabriquée par la construction")

print()
print("[4] Les 14 textes ont TOUS migré (aucun texte gris orphelin)")


def _parcourir(w, out):
    for e in w.winfo_children():
        out.append(e)
        _parcourir(e, out)


def _colonne(ui):
    w = ui._lf_fichiers_travail
    while w is not None and not isinstance(w, tk.Canvas):
        w = w.master
    for item in w.find_all():
        if w.itemcget(item, "window"):
            return w.nametowidget(w.itemcget(item, "window"))
    return None


def _sections(ui):
    total = 0
    for nom in dir(ui):
        if not nom.startswith("_lf_"):
            continue
        porteur = getattr(ui, nom, None)
        if not isinstance(porteur, tk.Misc):
            continue
        total += int(porteur.winfo_reqheight())
        entete = getattr(porteur, "_btn_header", None)
        if isinstance(entete, tk.Misc):
            total += int(entete.winfo_reqheight())
    return total


def _tout_afficher(ui):
    for nom in dir(ui):
        if nom.startswith("_lf_"):
            porteur = getattr(ui, nom, None)
            if isinstance(porteur, tk.Misc) and not porteur.winfo_manager():
                porteur.pack(fill="x")


_tout_afficher(ui)
root.update_idletasks()
gauche = _colonne(ui)
_widgets = []
_parcourir(gauche, _widgets)
# Comparaison par IDENTITÉ de widget (jamais par texte : deux aides peuvent
# commencer par la même phrase).
_connus = {str(a.texte) for a in aides}
_etat = set()
for nom in dir(ui):
    if nom.startswith("lbl_"):
        objet = getattr(ui, nom, None)
        if isinstance(objet, tk.Misc):
            _etat.add(str(objet))
_orphelins = []
for w in _widgets:
    if not isinstance(w, ttk.Label) or str(w) in _etat:
        continue
    try:
        texte = str(w.cget("text"))
        fg = str(w.cget("foreground")).lower()
        wrap = int(float(w.cget("wraplength") or 0))
    except (tk.TclError, ValueError):
        continue
    if fg == "#888888" and wrap > 0 and len(texte) >= 25 \
            and str(w) not in _connus:
        _orphelins.append(texte[:40])
verifie(not _orphelins,
        "aucune étiquette d'aide NON migrée dans la colonne : %s" % _orphelins)

_hauteur_bulles = _sections(ui)
verifie(_hauteur_bulles > 0, "colonne mesurée en mode bulles : %d px"
        % _hauteur_bulles)
print()


print("[5] Option « Aides en texte dans la colonne » : bascule + persistance")
verifie(bool(ui.var_aides_texte.get()) is False,
        "la case démarre DÉCOCHÉE (défaut = bulles)")
ui.var_aides_texte.set(True)
ui._on_aides_texte()
root.update_idletasks()
verifie(all(a.texte.winfo_manager() == "pack" for a in aides),
        "bascule À CHAUD vers le texte : les 14 étiquettes sont posées")
verifie(all(a.info.winfo_manager() == "" for a in aides),
        "… et les « ⓘ » ont disparu")
verifie(config_mod.CONFIG.get("aides_texte") is True,
        "clé `aides_texte` = True dans la configuration")
verifie(_intercepte.get("aides_texte") is True,
        "sauver_config a bien été appelé (choix persistant)")
_hauteur_texte = _sections(ui)
verifie(_hauteur_texte > _hauteur_bulles,
        "le mode texte REPREND de la place : %d px contre %d px"
        % (_hauteur_texte, _hauteur_bulles))
verifie(_hauteur_texte - _hauteur_bulles >= 500,
        "gain mesuré >= 500 px (mesuré : %d px)"
        % (_hauteur_texte - _hauteur_bulles))
# Retour aux bulles : le gain DOIT revenir (aucun widget laissé en place).
ui.var_aides_texte.set(False)
ui._on_aides_texte()
root.update_idletasks()
verifie(all(a.info.winfo_manager() == "pack" for a in aides)
        and all(a.texte.winfo_manager() == "" for a in aides),
        "retour aux bulles : état identique au départ")
verifie(_sections(ui) == _hauteur_bulles,
        "la colonne retrouve exactement sa hauteur en bulles (%d px)"
        % _hauteur_bulles)
verifie(config_mod.CONFIG.get("aides_texte") is False,
        "la clé redevient False (aucun héritage d'un True)")
print()

print("[6] Géométrie : aucun « ⓘ » écrasé, bulle du bon texte")
ui.root.deiconify()
root.update()
# `winfo_ismapped()` est TROMPEUR ici : la colonne défile, et tout ce qui est
# sous le pli n'est pas « mappé » alors qu'il est parfaitement posé (leçon du
# jalon 72). On vérifie donc ce qui définit un widget ÉCRASÉ par `pack` : il
# est GÉRÉ dans son parent mais reçoit une largeur nulle. Les aides dont un
# CADRE PARENT est fermé (Fusion Ha hors composition Ha, VeraLux en STF) sont
# hors jeu : elles ne sont pas visibles, ce n'est pas un écrasement.


def _chaine_posee(widget):
    w = widget
    while w is not None and w is not gauche:
        if not w.winfo_manager():
            return False
        w = w.master
    return True


_ecrases = [a.info for a in aides
            if _chaine_posee(a.info)
            and (a.info.winfo_manager() != "pack" or a.info.winfo_width() <= 1)]
_cachees = [a for a in aides if not _chaine_posee(a.info)]
verifie(not _ecrases, "les « ⓘ » posés ont une largeur réelle (écrasés : %d, "
        "cachés par un cadre fermé : %d)" % (len(_ecrases), len(_cachees)))
_lignes = sorted({str(a.ligne) for a in aides if a.ligne is not None})
verifie(len(_lignes) >= 1,
        "des « ⓘ » vivent SUR une ligne de réglage (aucune ligne en plus) : %d"
        % len(_lignes))
# La bulle d'une aide porte EXACTEMENT le texte de cette aide.
_a0 = aides[0]
_b = bulles.astuce(_a0.info, str(_a0.texte.cget("text")))
_b.montrer()
root.update()
_lbl = [w for w in _b._fenetre.winfo_children()[0].winfo_children()
        if isinstance(w, tk.Label)]
verifie(bool(_lbl) and _lbl[0].cget("text") == _a0.texte.cget("text"),
        "la bulle affiche le texte de SON aide")
_b.cacher()
root.destroy()

print()
print("RÉSULTAT :", "VERT" if ok else "ÉCHEC")
sys.exit(0 if ok else 1)

