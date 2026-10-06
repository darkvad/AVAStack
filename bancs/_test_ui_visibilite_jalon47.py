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
  - l'ordre des cadres de la colonne ne change jamais (ancre Caméra depuis
    le jalon 98 — elle fut Calibration puis le LabelFrame « Fichiers », qui
    coupait cette section en deux et plantait le changement de source si
    elle était repliée) ;
  - [5bis] v2.48.0 : cet ordre SUIT la chaîne des traitements — « Fond et grain
    (AVANT étirement) » et « Netteté live » précèdent « Affichage (temps réel) »,
    qui précède « Couleur de l'objet (APRÈS étirement) » (demande d'Alain :
    « l'UI doit respecter l'ordre des traitements »), et chaque étape porte SES
    cases (la neutralisation et le bruit chromatique ont quitté le cadre couleur).
  - [8] v2.56.1 (jalon 98) : avec les sections PLIABLES (jalon 95b), vérifie
    l'ordre VRAI du pack (boutons d'en-tête + LabelFrame) : « Fichiers de
    travail et journal » n'est jamais coupé de son contenu, changer de source
    ne lève JAMAIS « TclError: isn't packed » même Fichiers replié, et une
    section repliée par l'utilisateur RESTE repliée (flèche ▶ cohérente).

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
    """Sections visibles de la colonne, dans l'ordre d'affichage — leurs
    conteneurs externes (« porteurs » encadrés, jalon 99), identifiés par
    leur attribut `_btn_header`."""
    colonne = app._lf_fichiers_travail.master   # le frame défilable « left »
    return [w for w in colonne.pack_slaves()
            if hasattr(w, "_btn_header") and est_packe(w)]


def _titre_cadre(section):
    """Titre d'une section pliable : sur son bouton d'en-tête (attribut
    `_btn_header`, posé par `_creer_section_pliable`)."""
    btn = getattr(section, "_btn_header", None)
    if btn is not None:
        return str(btn.cget("text"))
    return section.cget("text")


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

# ============ [8] jalon 98 : ordre du pack avec sections PLIABLES (jalon 95b)
# Retour d'Alain (06/10/2026) : en mode Dossier, la section « Fichiers de
# travail et journal » était COUPÉE EN DEUX par le replacement (en-tête en
# haut, contenu orphelin sous « Dossier surveillé » — elle PARAISSAIT
# repliée) ; et si elle était réellement repliée, le changement de source
# levait « TclError: window … isn't packed » et AVORTAIT tout le reste
# (déconnexion caméra, détection SDK, « Démarrer »). Une section repliée
# réapparaissait en outre dépliée (flèche ▶ menteuse) au changement de
# source. La séquence ci-dessous rejoue TROIS scénarios réels.
print("[8] jalon 98 : ordre du pack, plis respectés, jamais de TclError")
DOSSIER = "Dossier surveillé (brutes FITS/PNG/TIFF…)"
COMPO = "Composition multi-dossiers (RGB/HOO/SHO/LRGB)"
SIMULEE = "Simulée (démo)"
colonne = app._lf_fichiers_travail.master   # le frame défilable « left »


def seq_pack():
    """Séquence packée de la colonne : (classe, texte) — boutons d'en-tête
    ET conteneurs (l'ordre VRAI de l'affichage, pas seulement les cadres)."""
    out = []
    for w in colonne.pack_slaves():
        try:
            t = str(w.cget("text"))
        except tk.TclError:
            t = ""
        if not t and w.winfo_class() in ("TLabelframe", "Labelframe", "Frame"):
            t = "<contenu>"
        out.append((w.winfo_class(), t))
    return out


def rang(seq, texte):
    """Position d'un BOUTON D'EN-TÊTE dans la séquence (ttk ou Tk classique,
    jalon 99) — -1 si absent."""
    for i, (cls, t) in enumerate(seq):
        if cls in ("TButton", "Button") and t.endswith(texte):
            return i
    return -1


def visible_et_fleche(lf):
    """(visible, flèche) d'une section pliable (jalon 95b)."""
    try:
        lf.pack_info()
        visible = True
    except tk.TclError:
        visible = False
    return visible, str(lf._btn_header.cget("text"))[:1]


# [8a] mode Dossier : « Fichiers » COMPLET (contenu juste après son bouton),
#      puis Cadence, Dossier, puis Caméra — l'ordre général est intact.
app.var_source.set(DOSSIER)
app._on_source_choisie()
root.update()
s = seq_pack()
i_fic = rang(s, "Fichiers de travail et journal")
verifie(i_fic >= 0 and s[i_fic + 1][1] == "<contenu>",
        "mode Dossier : le contenu de « Fichiers de travail et journal » "
        "suit IMMÉDIATEMENT son en-tête (section complète, pas coupée)")
i_cam = rang(s, "Caméra")
verifie(-1 < rang(s, "empilement") < rang(s, "Dossier surveillé")
        < i_cam,
        "ordre canonique rafale → dossier AVANT Caméra "
        f"(Cadence={rang(s, 'empilement')}, "
        f"Dossier={rang(s, 'Dossier surveillé')}, Caméra={i_cam})")

# [8b] une section REPLIÉE reste repliée au changement de source (flèche ▶
#      et contenu absent — plus de section « dépliée avec flèche ▶ »).
app._lf_cadence._btn_header.invoke()          # replier Cadence
root.update()
app.var_source.set(COMPO)
app._on_source_choisie()
root.update()
vis_cad, fleche_cad = visible_et_fleche(app._lf_cadence)
verifie(not vis_cad and fleche_cad == "▶",
        "Cadence repliée RESTE repliée (cachée, flèche ▶) après le passage "
        "en Composition")
verifie(section_visible(app, "compo"),
        "la section Composition, elle, est bien affichée")
s = seq_pack()
verifie(-1 < rang(s, "empilement") < rang(s, "multi-filtres")
        < rang(s, "Caméra"),
        "l'ordre canonique rafale → composition est conservé (Cadence "
        "repliée = son seul en-tête)")

# [8c] « Fichiers » replié + changement de source : AUCUNE exception et le
#      changement de source s'applique quand même ; au redépliage, tout
#      revient à sa place.
app._lf_fichiers_travail._btn_header.invoke()   # replier Fichiers
root.update()
erreur = None
try:
    app.var_source.set(DOSSIER)
    app._on_source_choisie()
    app.var_source.set(SIMULEE)
    app._on_source_choisie()
    root.update()
except tk.TclError as e:
    erreur = e
verifie(erreur is None,
        "Fichiers replié : changer de source ne lève PLUS « TclError: "
        f"window … isn't packed » ({erreur})")
vis_fic, _ = visible_et_fleche(app._lf_fichiers_travail)
verifie(not vis_fic, "Fichiers replié reste replié après les changements "
        "de source")
app._lf_fichiers_travail._btn_header.invoke()   # redéplier Fichiers
root.update()
s = seq_pack()
i_fic = rang(s, "Fichiers de travail et journal")
verifie(i_fic >= 0 and s[i_fic + 1][1] == "<contenu>",
        "au redépliage, le contenu de « Fichiers » retrouve sa place sous "
        "son en-tête")
verifie(not section_visible(app, "dossier")
        and not section_visible(app, "compo")
        and not section_visible(app, "rafale"),
        "retour en caméra : dossier, composition et cadence cachés")

# [8d] une section REPLIÉE qui devient INUTILE à la source : son en-tête
#      doit DISPARAÎTRE (avant le jalon 98bis, l'en-tête restait planté à
#      son ancienne position — flottant au milieu de la colonne — car la
#      branche « cacher » testait l'état du CONTENU, déjà dépacké par le
#      pli : le cas « repliée AU MOMENT où elle devient inutile » n'était
#      jamais couvert).
app.var_source.set(DOSSIER)
app._on_source_choisie()
root.update()
if not app._lf_cadence._var_etat.get():         # [8b] a laissé Cadence repliée
    app._lf_cadence._btn_header.invoke()        # repartir d'une section dépliée
app._lf_cadence._btn_header.invoke()            # replier Cadence (en dossier)
root.update()
app.var_source.set(SIMULEE)
app._on_source_choisie()
root.update()
s = seq_pack()
verifie(rang(s, "empilement") == -1,
        "section repliée devenue inutile : son EN-TÊTE disparaît aussi "
        "(plus d'en-tête orphelin flottant dans la colonne)")
app.var_source.set(DOSSIER)
app._on_source_choisie()
root.update()
s = seq_pack()
i_cad = rang(s, "empilement")
i_dos = rang(s, "Dossier surveillé")
vis_cad, fleche_cad = visible_et_fleche(app._lf_cadence)
verifie(0 <= i_cad < i_dos,
        f"au retour en Dossier, l'en-tête replié revient AVANT Dossier "
        f"(Cadence={i_cad}, Dossier={i_dos})")
verifie(not vis_cad and fleche_cad == "▶",
        "et il est TOUJOURS replié (contenu caché, flèche ▶)")
app._lf_cadence._btn_header.invoke()            # redéplier Cadence
root.update()
s = seq_pack()
i_cad = rang(s, "empilement")
verifie(0 <= i_cad and s[i_cad + 1][1] == "<contenu>" and i_cad < rang(s, "Dossier surveillé"),
        "au redépliage, le contenu de Cadence revient sous son en-tête, "
        "avant Dossier")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)