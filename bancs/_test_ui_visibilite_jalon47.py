# -*- coding: utf-8 -*-
"""Test UI du jalon 47 — visibilité des cadres selon la source choisie.

Demande d'ergonomie d'Alain : « la partie droite de l'écran est surchargée
inutilement » — la colonne de réglages ne doit montrer que les cadres utiles
au choix courant :
  - source caméra (simulée, OpenCV, SDK) → contrôles caméra seuls ;
  - « Dossier surveillé » → cadre dossier + « Cadence d'empilement » ;
  - « Composition multi-dossiers » → cadre composition + cadence ;
  - le réglage de rafale (« Empiler les brutes ») sort des cadres dossier et
    composition où il était dupliqué (jalon 45) : UN SEUL cadre partagé ;
  - masquer ≠ détruire : les valeurs saisies survivent aux allers-retours ;
  - l'ordre des cadres de la colonne ne change jamais (ancre Calibration) ;
  - [5bis] v2.48.0 : cet ordre SUIT la chaîne des traitements — « Fond et grain
    (AVANT étirement) » et « Netteté live » précèdent « Affichage (temps réel) »,
    qui précède « Couleur de l'objet (APRÈS étirement) » (demande d'Alain :
    « l'UI doit respecter l'ordre des traitements »), et chaque étape porte SES
    cases (la neutralisation et le bruit chromatique ont quitté le cadre couleur).

Nécessite un affichage. Exécution : python bancs/_test_ui_visibilite_jalon47.py
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

import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def est_packe(w):
    """True si le widget est réellement affiché (masqué = pack_info lève)."""
    try:
        w.pack_info()
        return True
    except tk.TclError:
        return False


def section_visible(app, nom):
    """Jalon 95 : teste si la section pliable NOMMÉE est visible.
    Cherche via l'attribut `_lf_<nom>` créé par `_creer_section_pliable`.

    Mapping entre noms de clés SECTIONS_NOM_MAP et attributs `_lf_*`."""
    mapping = {
        "dossier": "_lf_dossier_surveille",
        "dossier_surveille": "_lf_dossier_surveille",
        "compo": "_lf_composition",
        "composition": "_lf_composition",
        "rafale": "_lf_cadence",
        "cadence": "_lf_cadence",
        "fond": "_lf_fond_grain",
        "fond_grain": "_lf_fond_grain",
        "nette": "_lf_nette",
        "etat": "_lf_etat_calculs",
        "etat_calculs": "_lf_etat_calculs",
        "ext": "_lf_traitement_externe",
        "traitement_externe": "_lf_traitement_externe",
        "camera": "_lf_camera",
        "calibration": "_lf_calibration",
        "empilement": "_lf_empilement",
        "affichage": "_lf_affichage",
        "couleur": "_lf_couleur",
        "sortie": "_lf_sortie",
        "fichiers": "_lf_fichiers_travail",
        "fichiers_travail": "_lf_fichiers_travail",
    }
    attr = mapping.get(nom, f"_lf_{nom}")
    lf = getattr(app, attr, None)
    if lf is None:
        return False
    try:
        lf.pack_info()
        return True
    except tk.TclError:
        return False


def ordre_colonne(app):
    """Cadres LabelFrame visibles de la colonne, dans l'ordre d'affichage."""
    colonne = app.frm_calibration.master   # le frame défilable « left »
    return [w for w in colonne.winfo_children()
            if isinstance(w, ttk.LabelFrame) and est_packe(w)]


def _titre_cadre(lf):
    """Récupère le titre d'un LabelFrame, qu'il soit en `text=` (legacy) ou
    dans le labelwidget (pliable, jalon 95) ou dans un bouton d'en-tête séparé (nouveau jalon 95b)."""
    # 1. Cas legacy : text= sur le LabelFrame
    txt = lf.cget("text")
    if txt:
        return txt
    # 2. Cas jalon 95 : labelwidget sur le LabelFrame (bouton intégré)
    lw_name = lf.cget("labelwidget")
    if lw_name:
        try:
            lw = lf.nametowidget(lw_name)
            return lw.cget("text")
        except (tk.TclError, KeyError):
            pass
    # 3. Nouveau cas jalon 95b : le bouton d'en-tête est un widget FRÈRE dans le parent,
    # packé AVANT le LabelFrame. On cherche dans le parent le bouton qui précède.
    try:
        parent = lf.master
        if parent:
            # Chercher le bouton qui a ce LabelFrame comme "after" ou qui est juste avant
            for w in parent.winfo_children():
                if isinstance(w, ttk.Button):
                    # Le bouton a le titre avec préfixe ▼/▶
                    btn_text = w.cget("text")
                    # Vérifier que ce bouton contrôle ce LabelFrame (pack after=btn)
                    # Astuce : le bouton est packé AVANT le LF
                    pass
        # Fallback : chercher par proximité de pack
        # Le bouton d'en-tête est le widget immédiatement avant le LF dans parent
        children = list(parent.winfo_children())
        idx = children.index(lf)
        if idx > 0:
            prev = children[idx - 1]
            if isinstance(prev, ttk.Button):
                return prev.cget("text")
    except (tk.TclError, ValueError, AttributeError):
        pass
    return ""


ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()

# ==================================== [1] état initial (source par défaut)
print("[1] état initial (Simulée = source caméra)")
verifie(f"AVAStack v{ui.AVASTACK_VERSION}" in root.title(),
        f"la barre de titre affiche la version du package "
        f"(« {root.title()} », jalon 48)")
verifie(est_packe(app.frm_ctrl_cam),
        "source caméra : contrôles caméra visibles (exposition, gain…)")
verifie(est_packe(app.cb_source.master),
        "la combobox de source + Démarrer/Arrêter restent visibles")
verifie(not section_visible(app, "dossier"), "cadre « Dossier surveillé » caché")
verifie(not section_visible(app, "compo"), "cadre « Composition multi-filtres » caché")
verifie(not section_visible(app, "rafale"),
        "cadre « Cadence d'empilement » caché (sans objet pour une caméra)")

# ==================================== [2] source dossier surveillé
print("[2] source « Dossier surveillé »")
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app._on_source_choisie()
root.update_idletasks()
verifie(not est_packe(app.frm_ctrl_cam), "contrôles caméra cachés (inutiles ici)")
verifie(section_visible(app, "dossier"), "cadre « Dossier surveillé » visible")
verifie(not section_visible(app, "compo"), "cadre « Composition » caché")
verifie(section_visible(app, "rafale"), "cadre « Cadence d'empilement » visible (RAFALE)")
verifie(app.lbl_last.master is app.frm_dossier
        and est_packe(app.lbl_last),
        "« Dernier fichier » reste dans le cadre dossier")
verifie(app._cadence_lbls[0].master is app.frm_rafale
        and app._cadence_cbs[0].master.master is app.frm_rafale,
        "la combobox « Empiler les brutes » vit dans le cadre de cadence")

# ==================================== [3] source composition multi-dossiers
print("[3] source « Composition multi-dossiers »")
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._on_source_choisie()
root.update_idletasks()
verifie(not est_packe(app.frm_ctrl_cam), "contrôles caméra cachés")
verifie(not section_visible(app, "dossier"), "cadre « Dossier surveillé » caché")
verifie(section_visible(app, "compo"), "cadre « Composition » visible")
verifie(section_visible(app, "rafale"),
        "cadre « Cadence d'empilement » visible DANS LES DEUX CAS (jalon 45)")
verifie(len(app._cadence_cbs) == 1 and len(app._cadence_lbls) == 1,
        "UN SEUL couple combobox + étiquette (fini la duplication du jalon 45)")

# ==================================== [4] retour caméra SDK
print("[4] retour source caméra (ZWO ASI SDK)")
app.var_source.set("ZWO ASI (SDK)")
app._on_source_choisie()
root.update_idletasks()
verifie(est_packe(app.frm_ctrl_cam), "contrôles caméra de retour")
verifie(not section_visible(app, "dossier")
        and not section_visible(app, "compo")
        and not section_visible(app, "rafale"),
        "dossier, composition et cadence cachés")

# ==================================== [5] valeurs conservées + ordre stable
print("[5] allers-retours : valeurs conservées, ordre de la colonne stable")
ordre_avant = ordre_colonne(app)
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app._on_source_choisie()
app.var_folder.set("C:/brutes_test_jalon47")     # valeur saisie en mode dossier
app.var_compo_gains["G"].set("1.7")              # valeur saisie en mode compo
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._on_source_choisie()
root.update_idletasks()
verifie(app.var_folder.get() == "C:/brutes_test_jalon47",
        "le chemin de dossier saisi survit au passage en composition (on "
        "cache, on ne détruit pas)")
verifie(app.var_compo_gains["G"].get() == "1.7",
        "les gains de composition saisis survivent au passage en dossier")
app.var_source.set("Simulée (démo)")
app._on_source_choisie()
root.update_idletasks()
ordre_apres = ordre_colonne(app)
# NB : le cadre « Fichiers de travail et journal » est EN HAUT de la colonne
# depuis la v2.38.9 (décision d'Alain : « ce qui répond à où est-ce écrit ? va
# en haut », leçon des jalons 72/74) — il précède donc Caméra, qui reste
# suivie de Calibration (ancre). Cette attente avait été oubliée par ce banc ;
# mesuré au jalon 75.
verifie(ordre_avant == ordre_apres
        and _titre_cadre(ordre_apres[0]) == "▼ Fichiers de travail et journal"
        and _titre_cadre(ordre_apres[1]) == "▼ Caméra"
        and _titre_cadre(ordre_apres[2]) == "▼ Calibration",
        "l'ordre des cadres visibles est inchangé après les allers-retours "
        f"({[_titre_cadre(c) for c in ordre_apres]})")

# ================== [5bis] v2.48.0 : l'ORDRE SUIT LA CHAÎNE DES TRAITEMENTS
# Demande d'Alain (30/09/2026) : « l'UI doit respecter l'ordre des traitements ».
# Le cadre couleur du jalon 22 mélangeait deux ÉTAPES de la chaîne (neutralisation
# du fond et bruit chromatique sont appliqués AVANT l'étirement, SCNR/démagenta
# APRÈS) ; il est scindé, et « Netteté live » (qui dit « avant étirement » depuis
# le jalon 12) n'est plus affiché APRÈS le cadre qui porte l'étirement.
print("[5bis] l'ordre des cadres suit l'ordre des traitements (jalon 85)")
_titres_bruts = [_titre_cadre(c) for c in ordre_apres]
# j99 : les titres portent un préfixe "▼ " / "▶ " quand la section est pliée
_titres = [t.replace("▼ ", "").replace("▶ ", "") for t in _titres_bruts]
_attendus = ["Fond et grain (AVANT étirement)",
             "Netteté live (Richardson-Lucy)",
             "Affichage (temps réel)",
             "Couleur de l'objet (APRÈS étirement)"]
verifie(all(t in _titres for t in _attendus),
        f"les quatre cadres de la chaîne sont présents ({_titres})")
verifie([_titres.index(t) for t in _attendus] ==
        sorted(_titres.index(t) for t in _attendus),
        "« Fond et grain » → « Netteté live » → « Affichage » → « Couleur de "
        "l'objet » : l'ordre affiché EST l'ordre appliqué")


def _cases(cadre):
    """Libellés des cases à cocher d'un cadre (ses enfants directs)."""
    return [w.cget("text") for w in cadre.winfo_children()
            if isinstance(w, ttk.Checkbutton)]


_c_fond, _c_coul = _cases(app.frm_fond), _cases(app.frm_couleur)
verifie(any("Neutraliser la couleur du fond" in t for t in _c_fond)
        and any("Réduire le bruit chromatique" in t for t in _c_fond),
        f"« Fond et grain (AVANT étirement) » porte la neutralisation ET le "
        f"bruit chromatique ({_c_fond})")
verifie(any("SCNR — retrait du vert" in t for t in _c_coul)
        and any("Démagenta" in t for t in _c_coul)
        and any("Préserver la luminosité" in t for t in _c_coul),
        f"« Couleur de l'objet (APRÈS étirement) » porte la L*, le SCNR et le "
        f"démagenta ({_c_coul})")

# ==================================== [6] cadence : choix commun inchangé
print("[6] cadence unique : la combobox pilote toujours le moteur (42/45)")
app.var_cadence.set("toutes les 15 s")
app._on_cadence()
verifie(app.cadence_lecture == 15,
        "« toutes les 15 s » → miroir worker = 15 (via l'unique combobox)")
app.var_cadence.set("dès réception")
app._on_cadence()
verifie(app.cadence_lecture == 0, "retour « dès réception » → 0")

# ======================= [7] MOLETTE : ne change JAMAIS la valeur d'une liste
# Constat RÉEL d'Alain (25/09/2026) : en défilant les réglages à la molette, si
# le curseur passait sur (ou près de) une LISTE DÉROULANTE, la molette changeait
# sa valeur TOUTE SEULE (profil SPCC, méthode du recalage…) — des tests ont pu
# être faussés. La liaison de CLASSE Tk (`ttk::combobox::Scroll`) est supprimée
# au démarrage : pour changer une valeur, il faut OUVRIR la liste.
print("[7] molette : aucun changement de valeur des listes déroulantes")
liste = getattr(app, "cb_fit_methode", None)
verifie(liste is not None, "combobox de la méthode de recalage présente")
if liste is not None:
    verifie(liste.bind_class("TCombobox", "<MouseWheel>") == "",
            "liaison de CLASSE Tk de la molette supprimée "
            "(ttk::combobox::Scroll)")
    avant = app.var_fit_methode.get()
    for _ in range(3):                       # 3 crans vers le bas
        liste.event_generate("<MouseWheel>", delta=-120,
                             x=liste.winfo_width() // 2,
                             y=liste.winfo_height() // 2)
    root.update()
    verifie(app.var_fit_methode.get() == avant,
            f"3 crans de molette sur la liste : valeur INCHANGÉE "
            f"(« {avant} » → « {app.var_fit_methode.get()} »)")
    liste.event_generate("<MouseWheel>", delta=120,
                         x=liste.winfo_width() // 2,
                         y=liste.winfo_height() // 2)
    root.update()
    verifie(app.var_fit_methode.get() == avant,
            "un cran vers le haut non plus : toujours inchangée")
    # la liste reste utilisable normalement (choix explicite → code interne) :
    # `_code_fit_methode` est LA fonction qui traduit le libellé choisi pour le
    # stacker et l'instantané du worker.
    app.var_fit_methode.set("Gain + offset")
    app._on_linear_fit()
    verifie(app._code_fit_methode() == "gain_offset"
            and app.var_fit_methode.get() == "Gain + offset",
            "la liste fonctionne toujours normalement (choix explicite "
            "« Gain + offset » → gain_offset)")
    app.var_fit_methode.set(avant)
    app._on_linear_fit()
    verifie(app._code_fit_methode() == "offset",
            "retour à « Offset seul (fond) » → offset")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)