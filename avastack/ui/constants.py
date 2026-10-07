# -*- coding: utf-8 -*-
"""Constantes de l'interface (seuils, palettes, listes de choix) — jalon 102 du
chantier de refactoring.

Extraites de `avastack/ui/app.py` pour que l'UI (et les futures découpes
`ui/widgets/`, `ui/config_ui.py`, `ui/panels/`…) partagent une source UNIQUE et
TYPÉE. `app.py` les IMPORTE et les ré-expose à l'identique (surface publique
inchangée) : déplacer une valeur ici ne change RIEN au comportement observable.
"""

from ..cameras import (CameraBase, QHYCamera, PlayerOneCamera, SVBonyCamera,
                       ZWOASICamera, TouptekCamera)

# ──────────────────────────────────────────────────────────────────────────
# Géométrie de la fenêtre (hauteurs de référence)
# ──────────────────────────────────────────────────────────────────────────
# H_HIST reste la hauteur de RÉFÉRENCE du panneau d'histogramme ; depuis le
# jalon 75 la hauteur réellement utilisée est `_hauteur_hist()` (deux bandes,
# ou une seule — voir HIST_MODES).
W_IMG: int = 840
H_IMG: int = 560
W_HIST: int = 840
H_HIST: int = 110

# ──────────────────────────────────────────────────────────────────────────
# Panneau d'histogramme (jalon 75 : deux bandes + réglages des barres)
# ──────────────────────────────────────────────────────────────────────────
# Le panneau porte DEUX bandes — « Brut (linéaire) » (diagnostic : fond,
# clipping, dominante — c'est l'axe du GRAND histogramme de SharpCap) et
# « Sortie du moteur » (l'image telle que l'étirement la rend, AVANT les
# barres : c'est là que vivent les 3 barres Noir/Médian/Blanc, comme dans le
# MINI-histogramme de SharpCap, qui agit « on the display only »). Le sélecteur
# permet de n'afficher qu'une bande : l'image regagne alors la place, et une
# bande unique est plus confortable à régler.
HIST_MODES: tuple[tuple[str, str], ...] = (("Les deux", "les_deux"),
                                           ("Brut (linéaire)", "brut"),
                                           ("Sortie du moteur", "sortie"))
HIST_CODES: tuple[str, ...] = tuple(code for _, code in HIST_MODES)
HIST_LABELS: dict[str, str] = dict((code, lib) for lib, code in HIST_MODES)
HIST_POINTS: int = 400000    # échantillon des histogrammes : le COÛT ne dépend
                             # donc pas de la résolution (mesuré ~10 ms en
                             # aperçu comme en pleine résolution, contre ~55 ms
                             # pour l'ancien calcul sur toute l'image)
HIST_MARGE: int = 7          # marge de l'axe « sortie » (px) : une barre à
                             # 0 % ou 100 % reste attrapable à la souris
HIST_PRISE: int = 7          # rayon de prise d'une barre (px)
HIST_RANG_PX: int = 16       # pas vertical entre deux RANGS d'étiquettes —
                             # mesuré : le texte fait 15 px de haut, un pas de
                             # 11 px faisait donc chevaucher deux rangs voisins
                             # (défaut trouvé par le banc, pas à l'œil)

# ──────────────────────────────────────────────────────────────────────────
# SPCC couleur (jalon 58 bis / v2.40.0)
# ──────────────────────────────────────────────────────────────────────────
# Le TYPE de capteur est un choix EXPLICITE : en mono, trois filtres R/G/B ; en
# couleur, UN capteur OSC et son filtre (LPF). Constat d'Alain (28/09/2026) :
# « la case SPCC dit que c'est que pour du mono multibande, alors que SPCC
# fonctionne en images couleurs dans Siril — il faut juste lui dire que c'est
# un capteur couleur et le choisir ».
SPCC_TYPE_MONO: str = "Mono (filtres R/G/B)"
SPCC_TYPE_OSC: str = "Couleur (OSC)"

# ──────────────────────────────────────────────────────────────────────────
# Sections pliables de la colonne gauche (jalon 95, persistées)
# ──────────────────────────────────────────────────────────────────────────
# Clés CONFIG : "ui_section_<nom_normalisé>" → bool (True = ouvert)
SECTIONS_NOM_MAP: dict[str, str] = {
    "fichiers_travail": "Fichiers de travail et journal",
    "camera": "Caméra",
    "cadence": "Cadence d'empilement",
    "dossier_surveille": "Dossier surveillé",
    "composition": "Composition multi-filtres",
    "calibration": "Calibration",
    "empilement": "Empilement",
    "fond_grain": "Fond et grain (AVANT étirement)",
    "nette": "Netteté live (Richardson-Lucy)",
    "affichage": "Affichage (temps réel)",
    "couleur": "Couleur de l'objet (APRÈS étirement)",
    "etat_calculs": "État des calculs (live)",
    "traitement_externe": "Traitement externe (long)",
    "sortie": "Sortie",
}

# --- Habillage des sections pliables (jalon 99, choix d'Alain, variante « B+ »
# de la maquette du 06/10/2026 : titres en évidence + cadre « un peu plus
# marqué ») ----------------------------------------------------------------
# En-têtes en bouton Tk CLASSIQUE : le thème ttk « vista » de Windows ignore le
# fond des ttk.Button stylisés (constat réel sur la maquette : un texte blanc
# restait invisible sur fond ignoré) — un bouton classique rend exactement ce
# qui est demandé, sur les trois OS. Le cadre du contenu est un FILET posé par
# un porteur autour du LabelFrame (les couleurs ttk « bordercolor » ne sont pas
# honorées par le thème vista). AUCUN changement d'ordre ni de comportement.
SECTION_TITRE_BG: str = "#dde7f5"          # fond d'en-tête (bleu très clair)
SECTION_TITRE_FG: str = "#1f3b63"          # texte d'en-tête (bleu foncé)
SECTION_TITRE_BG_ACTIF: str = "#cddcef"    # fond d'en-tête pendant le clic
SECTION_CADRE: str = "#9fb6d4"             # filet du cadre de contenu (2 px)

# ──────────────────────────────────────────────────────────────────────────
# Débruitage live (jalon 9, remis le 16/09/2026)
# ──────────────────────────────────────────────────────────────────────────
# Libellés UI ↔ codes internes (module avastack/processing/denoise.py,
# algorithmes locaux sans IA). NLM en premier = défaut (tests réels d'Alain :
# plus homogène que les ondelettes). Le débruitage GraXpert IA reste en
# TRAITEMENT EXTERNE (plusieurs minutes par image — jamais en live).
VL_DN_METHODES: tuple[tuple[str, str], ...] = (("nlm", "Non-local means"),
                                               ("ondelettes", "Ondelettes à trous"))
VL_DN_LABELS: dict[str, str] = dict(VL_DN_METHODES)   # code → libellé (restauration)
VL_DN_CODES: dict[str, str] = {lib: code for code, lib in VL_DN_METHODES}

# ──────────────────────────────────────────────────────────────────────────
# Cadence d'empilement (jalon 42, demande d'Alain)
# ──────────────────────────────────────────────────────────────────────────
# En surveillance de dossier, à quelle fréquence les brutes sont lues/empilées.
# Les brutes qui arrivent pendant la fenêtre d'attente RESTENT sur le disque
# (aucune perte) puis sont drainées en rafale à l'échéance — le solveur VeraLux
# ne relance qu'une fois par rafale (dernier job gagnant) au lieu d'à CHAQUE
# brute : c'est ce qui évite le sablier permanent avec la chaîne lourde
# (gradient/débruitage live).
CADENCES: tuple[tuple[str, int], ...] = (("dès réception", 0), ("toutes les 5 s", 5),
                                         ("toutes les 15 s", 15), ("toutes les 30 s", 30),
                                         ("toutes les 1 min", 60), ("toutes les 5 min", 300))
CADENCE_CODES: dict[str, int] = dict(CADENCES)         # libellé → secondes
CADENCE_LABELS: dict[int, str] = {s: l for l, s in CADENCES}   # secondes → libellé

# --- Jalon 46 (retour d'Alain : dossiers déjà REMPLIS d'acquisitions d'autres
# soirées) : plafond de rafale. Sans lui, la première rafale devait vider TOUT
# le backlog d'un coup (des centaines de fichiers → sablier en continu pendant
# des minutes au démarrage). Avec le plafond, chaque rafale empile AU PLUS
# RAFALE_MAX brutes ; le reste attend les rafales suivantes (aucune perte — les
# fichiers restent sur le disque).
RAFALE_MAX: int = 10

# --- Jalon 80 (demande d'Alain, 29/09/2026) : rendu déclenché en FIN de rafale,
# pas sur sa PREMIÈRE brute. `RAFALE_QUIET_S` = silence à partir duquel la
# rafale est considérée terminée : une rafale de dossier lit ses brutes en
# continu (le temps d'aligner et d'empiler entre deux fichiers, jamais un creux
# de plusieurs dixièmes de seconde), puis le worker repart au scan ou à la
# fenêtre de cadence. 0,35 s couvre le pas de `_tick` (30 ms) sans retarder
# perceptiblement une session à une brute par minute.
RAFALE_QUIET_S: float = 0.35

# ──────────────────────────────────────────────────────────────────────────
# Débruitage du TRAITEMENT EXTERNE (jalon 8, remis le 16/09/2026)
# ──────────────────────────────────────────────────────────────────────────
# Mêmes algorithmes locaux que le live (ondelettes/NLM) ET le débruitage
# GraXpert IA (lent) — au choix, force commune 0..1. En externe, les
# algorithmes locaux tournent EN MÉMOIRE entre les étapes subprocess.
DN_EXT_METHODES: tuple[tuple[str, str], ...] = (("graxpert", "GraXpert (IA, lent)"),
                                                ("ondelettes", "Ondelettes à trous"),
                                                ("nlm", "Non-local means"))
DN_EXT_LABELS: dict[str, str] = dict(DN_EXT_METHODES)  # code → libellé (restauration)
DN_EXT_CODES: dict[str, str] = {lib: code for code, lib in DN_EXT_METHODES}

# ──────────────────────────────────────────────────────────────────────────
# Re-stack sur la meilleure référence (jalon 16, esprit Siril)
# ──────────────────────────────────────────────────────────────────────────
# Chaque brute archivée reçoit un score qualité (nb d'étoiles détectées sur le
# canal vert). Si une brute bat nettement la référence courante, on ré-ancre
# dessus et on RECALCULE tout l'empilement depuis l'archive ; le bouton
# « ⟳ Re-stacker (meilleure brute) » force le recalcul.
SCORE_MAX_ETOILES: int = 200       # plafond de détection pour le score qualité
RESTACK_MARGE: float = 1.5         # une brute doit battre la référence de ce facteur
RESTACK_MIN_FRAMES: int = 5        # pas de re-stack auto avant ce nb de frames archivées
RESTACK_CADENCE: int = 10          # nb de frames archivées entre deux re-stacks auto
RESTACK_HIST_MAX: int = 12         # entrées conservées dans l'historique de session (jalon 18)

# ──────────────────────────────────────────────────────────────────────────
# Caméras « pilotées » (jalon 35 : sondage roue/TEC, demandes de consigne)
# ──────────────────────────────────────────────────────────────────────────
# TOUTES les caméras SDK, pas seulement QHY (correctif du point 3 de l'item 2d,
# retour réel d'Alain du 20/09/2026, setup 2 : sur la POA Uranus-C Pro les
# contrôles TEC s'affichaient — bornes de consigne détectées — mais les boutons
# ❄ restaient GRISÉS). Cause : `cam_pilotee` était resté QHY-only depuis le
# jalon 25, donc le sondage lire_refroidissement() du worker n'était JAMAIS
# lancé pour les autres marques — les implémentations du jalon 33 étaient
# saines mais jamais appelées. Les no-ops de CameraBase garantissent qu'une
# marque sans roue/TEC (ZWO, Touptek) reste sans effet : sondage → None →
# boutons ❄ grisés, combobox filtre désactivée.
CAMERAS_PILOTEES: tuple[type[CameraBase], ...] = (
    QHYCamera, PlayerOneCamera, SVBonyCamera, ZWOASICamera, TouptekCamera)

# ──────────────────────────────────────────────────────────────────────────
# Filtre anti-brutes TRÈS défocalisées (jalon 17, AVANT l'empilement)
# ──────────────────────────────────────────────────────────────────────────
# Constat réel d'Alain (17/09/2026, après le jalon 15) : « ça a l'air OK sauf
# sur des brutes très défocalisées » — elles passent l'alignement (les
# triangles s'y retrouvent) mais dégradent l'empilement. Rejet AUTOMATIQUE
# d'office, case « Rejeter les frames floues (auto) » pour désactiver (décision
# d'Alain). Critères RELATIFS à la médiane des frames gardées.
FLU_MIN_REF: int = 3         # ≥ 3 frames gardées avant le 1er rejet possible
FLU_NB_FRAC: float = 0.5     # score étoiles < 0,5× la médiane → « effondré »
FWHM_MARGE: float = 2.0      # FWHM > 2× la médiane → frame très floue
FWHM_ABS_MIN: float = 3.0    # …et soi-même > 3 px (rien à rejeter en très courte focale)