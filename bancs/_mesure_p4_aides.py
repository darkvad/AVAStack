# -*- coding: utf-8 -*-
"""Mesure P4 (lot 3) — combien de place la COLONNE GAUCHE récupère.

CONSTAT (Alain, 19/10/2026) : « la colonne de gauche est pleine de textes
d'aide gris, on ne voit plus les réglages » — les étiquettes `wraplength`
expliquent chaque case sur 2 à 8 lignes, et poussent les réglages sous le pli.
P4 remplace ces étiquettes par une INFOBULLE derrière un « ⓘ » (option
« Aides en texte dans la colonne » pour revenir à l'ancien affichage).

MÉTHODE : on construit la VRAIE interface (aucune image, aucun disque, le
`config.json` réel n'est jamais lu ni écrit), puis on mesure
  · le nombre d'étiquettes d'aide et leur hauteur REQUISE (px) ;
  · la hauteur des sections de la colonne (somme des porteurs + en-têtes) ;
  · la part des aides dans la colonne.
Le mode mesuré est celui de l'option (`--texte` ou `--bulles`) ; le JSON du
passage est conservé (`bancs/_mesure_p4_aides.json`) pour comparer avant /
après.

Exécution : python bancs/_mesure_p4_aides.py [--texte | --bulles] [--json]
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import json
import sys

import cv2

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

cv2.ocl.setUseOpenCL(False)

import tkinter as tk                       # noqa: E402
from tkinter import ttk                    # noqa: E402

import avastack.config as config_mod       # noqa: E402
import avastack.ui.app as app_mod          # noqa: E402

# Le VRAI config.json n'est ni lu ni écrit : les bancs de l'interface posent
# toujours un dict neuf (règle du projet).
config_mod.CONFIG.clear()
app_mod.CONFIG = config_mod.CONFIG
app_mod.sauver_config = lambda _d: None

GRIS = {"#888888", "#808080", "#777777", "#666666"}


def _mode(argv):
    if "--bulles" in argv:
        return "bulles"
    if "--texte" in argv:
        return "texte"
    return "defaut"


def _hauteur_ligne(widget):
    """Hauteur d'une ligne de texte de la police du widget (px)."""
    try:
        police = ttk.Style(widget).lookup("TLabel", "font") or "TkDefaultFont"
        return max(1, widget.tk.call("font", "metrics", police, "-linespace"))
    except tk.TclError:
        return 17


def _parcourir(widget, out):
    for enfant in widget.winfo_children():
        out.append(enfant)
        _parcourir(enfant, out)


def _colonne_gauche(ui):
    """Le cadre de la colonne gauche (celui posé DANS le canvas défilant)."""
    w = ui._lf_fichiers_travail
    while w is not None and not isinstance(w, tk.Canvas):
        w = w.master                      # porteur → LabelFrame → filet → canvas
    if w is None:
        raise RuntimeError("canvas de la colonne gauche introuvable")
    for item in w.find_all():
        if w.itemcget(item, "window"):
            return w.nametowidget(w.itemcget(item, "window"))
    raise RuntimeError("cadre de la colonne gauche introuvable")



def _lignes_etat(ui):
    """Widgets que l'application GARDE dans un attribut `lbl_*` (état vivant).

    Ce sont les lignes que le code REMPLIT en marche (« Photométrie : … »,
    « mesure en cours… ») : leur texte est long par moments, mais elles ne sont
    PAS des aides — on ne les compte jamais. Les aides sont, elles, créées
    anonymement (ou dans `_aides`, qui ne porte pas de nom `lbl_*`)."""
    vus = set()
    for nom in dir(ui):
        if nom.startswith("lbl_"):
            objet = getattr(ui, nom, None)
            if isinstance(objet, tk.Misc):
                vus.add(str(objet))
    return vus


def _pose_jusqu_a(widget, colonne):
    """Vrai si le widget et TOUS ses ancêtres sont gérés jusqu'à la colonne.

    `winfo_manager()` d'un widget dit seulement qu'il est packed DANS SON
    parent : le grand texte « Principe : le Ha… » vit dans le cadre « Fusion
    Ha », lui-même NON packé hors composition Ha — il ne prend donc aucune
    place à l'écran. On remonte la chaîne pour ne compter que le VISIBLE."""
    w = widget
    while w is not None and w is not colonne:
        try:
            if not w.winfo_manager():
                return False
        except tk.TclError:
            return False
        w = w.master
    return True


def _mesure(ui, mode):
    gauche = _colonne_gauche(ui)
    widgets = []
    _parcourir(gauche, widgets)
    etat = _lignes_etat(ui)
    aides, infos = [], []
    for w in widgets:
        if not isinstance(w, ttk.Label):
            continue
        try:
            texte = str(w.cget("text"))
            fg = str(w.cget("foreground")).lower()
            wrap = int(float(w.cget("wraplength") or 0))
        except (tk.TclError, ValueError):
            continue
        if str(w) in etat:
            continue
        if texte.strip() == "ⓘ":
            if _pose_jusqu_a(w, gauche):
                infos.append(int(w.winfo_reqheight()))
            continue
        if fg not in GRIS or wrap == 0 or len(texte) < 25:
            continue
        if not _pose_jusqu_a(w, gauche):
            continue
        aides.append({
            "texte": texte[:60].replace("\n", " "),
            "caracteres": len(texte),
            "hauteur": int(w.winfo_reqheight()),
            "visible": True,
        })
    # Hauteur des SECTIONS de la colonne (porteurs + en-têtes), toutes ouvertes :
    # indépendante de la source choisie, donc comparable d'un passage à l'autre.
    sections = 0
    n_sections = 0
    for nom in dir(ui):
        if not nom.startswith("_lf_"):
            continue
        porteur = getattr(ui, nom, None)
        if not isinstance(porteur, tk.Misc):
            continue
        try:
            sections += int(porteur.winfo_reqheight())
            entete = getattr(porteur, "_btn_header", None)
            if isinstance(entete, tk.Misc):
                sections += int(entete.winfo_reqheight())
            n_sections += 1
        except tk.TclError:
            pass
    ligne = _hauteur_ligne(ui.root)
    total_aides = sum(a["hauteur"] for a in aides)
    total_infos = sum(infos)
    occupe = total_aides + total_infos
    return {
        "mode": mode,
        "nb_aides": len(aides),
        "nb_infos": len(infos),
        "hauteur_aides_px": total_aides,
        "hauteur_infos_px": total_infos,
        "ligne_px": ligne,
        "lignes_equivalentes": round(total_aides / ligne, 1),
        "colonne_px": sections,
        "nb_sections": n_sections,
        "part_pourcent": round(100.0 * occupe / sections, 1) if sections else 0.0,
        "detail": aides,
    }


def _tout_afficher(ui):
    """Rend TOUTES les sections visibles le temps de la mesure.

    L'application masque les cadres inutiles à la source choisie (jalon 47) :
    mesure faite sur la source par défaut, la composition et le traitement
    externe seraient invisibles et leurs aides ne compteraient pas — le gain
    mesuré serait sous-estimé. On repose donc chaque porteur non géré (l'ordre
    n'a aucune importance : on mesure des HAUTEURS)."""
    for nom in dir(ui):
        if not nom.startswith("_lf_"):
            continue
        porteur = getattr(ui, nom, None)
        if not isinstance(porteur, tk.Misc):
            continue
        try:
            if not porteur.winfo_manager():
                porteur.pack(fill="x")
        except tk.TclError:
            pass


def main(argv):
    mode = _mode(argv)
    if mode == "bulles":
        config_mod.CONFIG["aides_texte"] = False
    elif mode == "texte":
        config_mod.CONFIG["aides_texte"] = True
    root = tk.Tk()
    root.withdraw()
    ui = app_mod.App(root)
    root.update_idletasks()
    _tout_afficher(ui)
    root.update_idletasks()
    res = _mesure(ui, mode)
    root.destroy()

    print("Mode                     : %s" % res["mode"])
    print("Étiquettes d'aide        : %d (hauteur %d px = %.1f lignes)"
          % (res["nb_aides"], res["hauteur_aides_px"],
             res["lignes_equivalentes"]))
    print("Infobulles ⓘ visibles    : %d (hauteur %d px)"
          % (res["nb_infos"], res["hauteur_infos_px"]))
    print("Colonne gauche           : %d sections, %d px"
          % (res["nb_sections"], res["colonne_px"]))
    print("Part des aides           : %.1f %% de la colonne"
          % res["part_pourcent"])
    print()
    print("Détail des aides (px requis) :")
    for a in res["detail"]:
        print("  %4d px · %4d car. · %s" % (a["hauteur"], a["caracteres"],
                                             a["texte"]))

    if "--json" in argv:
        chemin = _pl_banc.Path(__file__).with_name("_mesure_p4_aides.json")
        ancien = {}
        if chemin.is_file():
            try:
                ancien = json.loads(chemin.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                ancien = {}
        ancien[res["mode"]] = res
        chemin.write_text(json.dumps(ancien, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        print("\nJSON : %s" % chemin)
        avant_m, apres_m = ancien.get("texte"), ancien.get("bulles")
        if avant_m and apres_m:
            gain = avant_m["colonne_px"] - apres_m["colonne_px"]
            print("GAIN MESURÉ : %d px repris sur la colonne (%.1f lignes de "
                  "texte), soit %.1f %%"
                  % (gain, gain / max(1, avant_m["ligne_px"]), 100.0 * gain
                     / max(1, avant_m["colonne_px"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
