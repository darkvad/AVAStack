# -*- coding: utf-8 -*-
"""Fenêtre principale AVAStack (Tkinter) : interface, thread d'acquisition,
orchestration calibration → alignement → empilement → affichage, et traitement
externe sur instantané."""

import os
import time
import math
import queue
import shutil
import threading

import numpy as np
import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from ..compat import IS_WINDOWS
from .. import AVASTACK_VERSION
from .. import delais
from .. import journal
from .. import travail
from ..config import CONFIG, sauver_config
from ..images import (CFA_MODE, borner_lineaire, lire_filtre_fits,
                      load_image, save_image, find_output, auto_unflip)
from ..cameras import (SOURCES, SimulatedCamera, OpenCVCamera, ZWOASICamera,
                       FolderCamera, MultiFolderCamera, QHYCamera,
                       PlayerOneCamera, TouptekCamera, SVBonyCamera)
from ..cameras.base import FILTRES_ROUE
from ..cameras.qhy import lister_via_sous_processus, tracer_evt
from ..processing import Calibrator, StarAligner, LiveStacker, DisplayProcessor
from ..processing import alignment as align_mod
# Jalon 75 : étage de « niveaux » de l'écran (barres Noir/Médian/Blanc de
# l'histogramme) et saturation par couleur — fonctions pures du module
# d'affichage, appelées par l'UI pour le tracé et la validation des saisies.
from ..processing import display as display_mod
from ..processing.composition import (COMPOSITIONS, MODES_L, ROLES,
                                      CompositeStacker, extraire_canal,
                                      composition_pour_roles, role_de_filtre,
                                      roles_de)
from ..processing.framestore import ArchiveFrames

# --- Jalon 16 : re-stack sur la meilleure référence (esprit Siril) ----------
# Chaque brute archivée reçoit un score qualité (nb d'étoiles détectées sur
# le canal vert). Si une brute bat nettement la référence courante, on
# ré-ancre dessus et on RECALCULE tout l'empilement depuis l'archive ;
# le bouton « ⟳ Re-stacker (meilleure brute) » force le recalcul.
SCORE_MAX_ETOILES = 200    # plafond de détection pour le score qualité
RESTACK_MARGE = 1.5        # une brute doit battre la référence de ce facteur
RESTACK_MIN_FRAMES = 5     # pas de re-stack auto avant ce nb de frames archivées
RESTACK_CADENCE = 10       # nb de frames archivées entre deux re-stacks auto
RESTACK_HIST_MAX = 12      # entrées conservées dans l'historique de session (jalon 18)

# --- Jalon 35 : caméras « pilotées » (sondage roue/TEC, demandes de consigne)
# TOUTES les caméras SDK, pas seulement QHY (correctif du point 3 de l'item
# 2d, retour réel d'Alain du 20/09/2026, setup 2 : sur la POA Uranus-C Pro
# les contrôles TEC s'affichaient — bornes de consigne détectées — mais les
# boutons ❄ restaient GRISÉS). Cause : `cam_pilotee` était resté QHY-only
# depuis le jalon 25, donc le sondage lire_refroidissement() du worker
# n'était JAMAIS lancé pour les autres marques — les implémentations du
# jalon 33 étaient saines mais jamais appelées. Les no-ops de CameraBase
# garantissent qu'une marque sans roue/TEC (ZWO, Touptek) reste sans effet :
# sondage → None → boutons ❄ grisés, combobox filtre désactivée.
CAMERAS_PILOTEES = (QHYCamera, PlayerOneCamera, SVBonyCamera,
                    ZWOASICamera, TouptekCamera)


def _fmt_expo(ms):
    """Format d'affichage d'une exposition en ms : µs / ms / s selon l'ordre
    de grandeur (le curseur log couvre 11 µs → 3600 s selon la caméra).

    Jamais de notation scientifique (retour réel d'Alain, 20/09/2026 :
    « 2e+03 s » illisible) : au-delà de 10 s la valeur est arrondie à
    l'entier — le pas réel de la caméra est ≥ 1 ms, le dixième de seconde
    n'a plus de sens — et les milliers sont séparés par une espace fine
    insécable (« 2 000 s », « 20 000 s »)."""
    ms = float(ms)
    if ms < 1.0:
        return f"{ms * 1000.0:.0f} µs"
    if ms < 1000.0:
        return f"{ms:.1f} ms" if ms < 100.0 else f"{ms:.0f} ms"
    s = ms / 1000.0
    if s < 10.0:
        return f"{s:.2f}".rstrip("0").rstrip(".") + " s"
    return f"{round(s):_}".replace("_", "\u202f") + " s"

# --- Jalon 17 : filtre anti-brutes TRÈS défocalisées (AVANT l'empilement) ---
# Constat réel d'Alain (17/09/2026, après le jalon 15) : « ça a l'air OK sauf
# sur des brutes très défocalisées » — elles passent l'alignement (les
# triangles s'y retrouvent) mais dégradent l'empilement. Rejet AUTOMATIQUE
# d'office, case « Rejeter les frames floues (auto) » pour désactiver
# (décision d'Alain). Critères RELATIFS à la médiane des frames gardées.
FLU_MIN_REF = 3      # ≥ 3 frames gardées avant le 1er rejet possible
FLU_NB_FRAC = 0.5    # score étoiles < 0,5× la médiane → « effondré »
FWHM_MARGE = 2.0     # FWHM > 2× la médiane → frame très floue
FWHM_ABS_MIN = 3.0   # …et soi-même > 3 px (rien à rejeter en très courte focale)
from ..processing import denoise as denoiser_local
from ..processing import couleurs as couleurs_mod
from ..processing import composition as composition_mod
from ..processing import stars as seeing_live
from ..processing import sharpness as nettete_live
from ..external import live as gx_live
from ..processing import veralux as veralux_moteur
# Jalon 56 (branchement du solveur) : astrométrie de l'empilement — module de
# GLUE (résolution UNIQUE du WCS sur la grille complète, puis PROPAGATION à
# chaque réempilement). Le worker ne touche jamais au catalogue lui-même
# (processing → catalogues, jamais l'inverse : pas de cycle d'import).
from ..processing import astrometrie as astro_mod
# Jalon 70 : CATALOGUES (dossier par OS, présence du catalogue astro, et
# téléchargement Gaia DR3) — l'astrométrie interne en dépend, et son absence
# doit être DITE (constat Linux du 27/09/2026 : échec silencieux).
from .. import catalogues as cat_mod
# Jalon 56 (étape 4) : photométrie — zéro-point instrumental PAR BANDE via le
# WCS (appariement mutuel des étoiles de l'empilement au catalogue Gaia). On
# MESURE ici ; l'application aux gains du stacker est l'étape 5.
from ..processing import photometrie as photo_mod
from ..processing import spcc as spcc_mod
from ..external.detection import (
    DEFAULT_CMD_GRAXPERT, DEFAULT_CMD_GRAXPERT_DN, DEFAULT_CMD_BXT,
    commande_avec_strength, detecter_outils)


class App:
    # H_HIST reste la hauteur de RÉFÉRENCE du panneau d'histogramme ; depuis le
    # jalon 75 la hauteur réellement utilisée est `_hauteur_hist()` (deux
    # bandes, ou une seule — voir HIST_MODES).
    W_IMG, H_IMG, W_HIST, H_HIST = 840, 560, 840, 110

    # Jalon 75 : le panneau d'histogramme porte désormais DEUX bandes —
    # « Brut (linéaire) » (diagnostic : fond, clipping, dominante — c'est
    # l'axe du GRAND histogramme de SharpCap) et « Sortie du moteur » (l'image
    # telle que l'étirement la rend, AVANT les barres : c'est là que vivent
    # les 3 barres Noir/Médian/Blanc, comme dans le MINI-histogramme de
    # SharpCap, qui agit « on the display only »). Le sélecteur permet de
    # n'afficher qu'une bande : l'image regagne alors la place, et une bande
    # unique est plus confortable à régler.
    HIST_MODES = (("Les deux", "les_deux"),
                  ("Brut (linéaire)", "brut"),
                  ("Sortie du moteur", "sortie"))
    HIST_CODES = tuple(code for _, code in HIST_MODES)
    HIST_LABELS = dict((code, lib) for lib, code in HIST_MODES)
    HIST_POINTS = 400000     # échantillon des histogrammes : le COÛT ne dépend
                             # donc pas de la résolution (mesuré ~10 ms en
                             # aperçu comme en pleine résolution, contre ~55 ms
                             # pour l'ancien calcul sur toute l'image)
    HIST_MARGE = 7           # marge de l'axe « sortie » (px) : une barre à
                             # 0 % ou 100 % reste attrapable à la souris
    HIST_PRISE = 7           # rayon de prise d'une barre (px)
    HIST_RANG_PX = 16        # pas vertical entre deux RANGS d'étiquettes —
                             # mesuré : le texte fait 15 px de haut, un pas de
                             # 11 px faisait donc chevaucher deux rangs voisins
                             # (défaut trouvé par le banc, pas à l'œil)

    # Jalon 58 bis (v2.40.0) : SPCC COULEUR (capteur OSC). Le TYPE de capteur
    # est un choix EXPLICITE : en mono, trois filtres R/G/B ; en couleur, UN
    # capteur OSC et son filtre (LPF). Constat d'Alain (28/09/2026) : « la
    # case SPCC dit que c'est que pour du mono multibande, alors que SPCC
    # fonctionne en images couleurs dans Siril — il faut juste lui dire que
    # c'est un capteur couleur et le choisir ».
    SPCC_TYPE_MONO = "Mono (filtres R/G/B)"
    SPCC_TYPE_OSC = "Couleur (OSC)"

    # Débruitage live (jalon 9, remis le 16/09/2026) : libellés UI ↔ codes
    # internes (module avastack/processing/denoise.py, algorithmes locaux
    # sans IA). NLM en premier = défaut (tests réels d'Alain : plus homogène
    # que les ondelettes). Le débruitage GraXpert IA reste en TRAITEMENT
    # EXTERNE (plusieurs minutes par image — jamais en live).
    VL_DN_METHODES = (("nlm", "Non-local means"),
                      ("ondelettes", "Ondelettes à trous"))
    VL_DN_LABELS = dict(VL_DN_METHODES)    # code → libellé (restauration)
    VL_DN_CODES = {lib: code for code, lib in VL_DN_METHODES}

    # Cadence d'empilement (jalon 42, demande d'Alain) : en surveillance de
    # dossier, à quelle fréquence les brutes sont lues/empilées. Les brutes
    # qui arrivent pendant la fenêtre d'attente RESTENT sur le disque (aucune
    # perte) puis sont drainées en rafale à l'échéance — le solveur VeraLux
    # ne relance qu'une fois par rafale (dernier job gagnant) au lieu d'à
    # CHAQUE brute : c'est ce qui évite le sablier permanent avec la chaîne
    # lourde (gradient/débruitage live).
    CADENCES = (("dès réception", 0), ("toutes les 5 s", 5),
                ("toutes les 15 s", 15), ("toutes les 30 s", 30),
                ("toutes les 1 min", 60), ("toutes les 5 min", 300))
    CADENCE_CODES = dict(CADENCES)         # libellé → secondes
    CADENCE_LABELS = {s: l for l, s in CADENCES}   # secondes → libellé

    # Jalon 46 (retour d'Alain : dossiers déjà REMPLIS d'acquisitions
    # d'autres soirées) : plafond de rafale. Sans lui, la première rafale
    # devait vider TOUT le backlog d'un coup (des centaines de fichiers →
    # sablier en continu pendant des minutes au démarrage). Avec le plafond,
    # chaque rafale empile AU PLUS RAFALE_MAX brutes ; le reste attend les
    # rafales suivantes (aucune perte — les fichiers restent sur le disque).
    RAFALE_MAX = 10

    # Débruitage du TRAITEMENT EXTERNE (jalon 8, remis le 16/09/2026) :
    # mêmes algorithmes locaux que le live (ondelettes/NLM) ET le débruitage
    # GraXpert IA (lent) — au choix, force commune 0..1. En externe, les
    # algorithmes locaux tournent EN MÉMOIRE entre les étapes subprocess.
    DN_EXT_METHODES = (("graxpert", "GraXpert (IA, lent)"),
                       ("ondelettes", "Ondelettes à trous"),
                       ("nlm", "Non-local means"))
    DN_EXT_LABELS = dict(DN_EXT_METHODES)  # code → libellé (restauration)
    DN_EXT_CODES = {lib: code for code, lib in DN_EXT_METHODES}

    def __init__(self, root):
        self.root = root
        root.title(f"AVAStack v{AVASTACK_VERSION} — "
                   "live stacking (empilement temps réel)")
        root.geometry("1300x820")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.camera = self.thread = None
        self.cam_pilotee = None          # jalon 25 : caméra QHY pilotée (TEC/roue)
        # Jalon 26 (demande d'Alain) : la caméra est CONNECTÉE dès la
        # détection — les contrôles (roue, refroidissement, réglages) sont
        # utilisables AVANT l'empilement (p.ex. attendre la bonne
        # température) ; « ▶ Démarrer » ne lance plus que l'EMPILEMENT.
        self.empilement_on = False       # empilement en cours (pause sinon)
        self.empilement_start_request = False   # reset de session (worker)
        self._connexion_busy = False     # une connexion (toute marque) en cours
        self._connexion_result = None    # QHY : (cam|None, err|None) → _tick
        # Jalon 32 : résultat de connexion des AUTRES marques SDK (Player
        # One, SVBONY, ZWO, Touptek) → (source, cam|None, err|None) → _tick.
        self._connexion_sdk_result = None
        self._tec_dernier_t0 = 0.0       # cadence de relecture TEC (2 s)
        # Jalon 32 : DÉCISION D'ALAIN (20/09/2026) — la déconnexion est la
        # version SIMPLE (« ⏏ Déconnecter » referme la caméra directement
        # depuis le thread Tk) : c'est celle du 19/09 qui fonctionne en réel
        # ; la version threadée du jalon 26b (demande exécutée par le
        # worker + confirmation) est supprimée (elle restait sans effet).
        self._controles_sondes = False
        self._roue_ok = False            # roue détectée (worker → _tick)
        self._tec_ok = False             # refroidissement détecté (idem)
        # Jalon 31 : capacités détectées À LA CONNEXION → l'UI s'adapte
        # (plages expo/gain/offset/TEC réelles, roue aux slots réels).
        # None = sonde absente ou muette → valeurs par défaut conservées.
        self.capacites = None
        self._EXPO_DYN = None            # (min_ms, max_ms) réels, sinon None
        self.tec_plage = None            # (min, max) °C réels, sinon None
        self._filtres_dispo = FILTRES_ROUE
        self.filtre_courant = None       # nom du filtre en place (FITS FILTER)
        self.running = False
        self.q = queue.Queue(maxsize=2)
        self.stacker = None
        self.aligner = StarAligner()
        self.calib = Calibrator()
        self.disp = DisplayProcessor()
        self._vl_frames = None        # nb de frames du dernier empilement affiché
        self.kappa = 3.0
        self.rejet_methode = "kappa"     # "kappa" ou "winsorized" (satellites)
        self.rejet_fenetre = 8           # frames de la fenêtre glissante
        self.pending_settings = None
        self.expo_ms = 100.0             # instantanés thread-safe (jalon 25)
        self.gain_val = 30.0
        self.pending_offset = None       # jalon 27 : offset demandé (10-255)
        self.reset_request = self.ref_request = False
        self.save_request = self.saved_path = None
        self.save_canaux_request = None  # jalon 19 : dossier des canaux (compo)
        self.bad_frames = 0
        # Détection des sources SDK (correctif du 19/09/2026 : le choix
        # « QHY (SDK) » n'affichait rien et le 1er « Démarrer » mourait en
        # crash natif). Le scan QHY est isolé en SOUS-PROCESSUS (un segfault
        # du SDK au scan ne doit jamais tuer l'application).
        self._qhy_id = ""             # id de caméra détecté → QHYCamera
        self._sdk_ids = None          # dernier scan réussi (liste d'ids)
        self._detect_busy = False     # un scan est en cours (thread)
        self._detect_result = None    # (source, ids|None, erreur|None) → _tick
        # Jalon 13 : alignement — info de la dernière frame (ligne d'état) et
        # rafraîchissement automatique de la référence (fréquence + compteurs).
        self.align_info = "—"
        self.ref_refresh = 20            # frames (0 = « jamais »)
        self._ref_frames = 0             # frames depuis le dernier rafraîchissement
        self._ref_bad = 0                # frames refusées depuis le dernier
        self.fps = 0.0
        # --- Jalon 10 : seeing live (FWHM + nombre d'étoiles), mesuré par le
        # thread d'acquisition sur l'aperçu (≤ 1600 px, même résolution que
        # celle où travaillera la netteté live) toutes les `seeing_periode`
        # secondes — la détection coûte quelques ms, inutile de la refaire à
        # chaque frame. Sert aussi de PRÉREQUIS à la netteté (PSF).
        self.seeing = None             # dernière mesure (dict) ou None
        self.seeing_msg = ""           # message associé (étoiles insuffisantes…)
        self.seeing_periode = 3.0      # secondes entre deux mesures
        self._seeing_t0 = 0.0          # horodatage de la dernière mesure
        self.show_stack = None       # dernier aperçu linéaire de l'empilement
        self.last_show = None       # image linéaire actuellement affichée
        # v2.37.4 : rayon du flou de chroma, en pixels PLEINE RÉSOLUTION (le
        # curseur « Rayon de référence ») — l'aperçu le ramène à SON échelle via
        # `_poser_rayon_chroma`, les fichiers l'utilisent tel quel.
        self.rayon_chroma_ref = 3.0
        self._echelle_apercu = 1.0   # dernier facteur de réduction de l'aperçu
        # v2.38.0 : empilement PLEINE RÉSOLUTION (copie défensive) pour l'option
        # « Rendu pleine résolution » de l'écran — posé en fin de boucle
        # d'acquisition, SEUL endroit qui a l'image complète sous la main.
        self._stack_pleine_res = None
        # …et son état, en attribut PYTHON (lisible par les threads de travail,
        # contrairement à une variable Tk : cf. `_pleine_res_activee`).
        self.pleine_res_ecran = False
        self._session = 0           # anti-mélange entre sessions
        # Jalon 15 : archive temporaire des frames calibrées (fondation du
        # re-stack « à la Siril » : recalcul de l'empilement sur une meilleure
        # référence). Dossier temp de session, vidé au démarrage/fermeture.
        self.archive = ArchiveFrames()
        # Jalon 19 (mode composition) : drapeau de mode + composition déduite
        # des rôles des dossiers (choix UI explicite en phase 3). En mode
        # compo, self.stacker est une FAÇADE CompositeStacker (un LiveStacker
        # par rôle, mean() → composite) et l'archive est tenue PAR RÔLE.
        self._mode_compo = False
        self._compo_nom = None
        # Jalon 19 phase 3 : instantanés pour le thread worker (jamais de
        # lecture de variables Tk hors du thread principal — cf. pièges).
        self._compo_gains = None         # dict R/G/B → facteur
        self._norm_commune = False       # v2.36.0 : normalisation commune (opt-in)
        self._compo_mode_l = "synthetise"
        # Jalon 55 : un réglage compo/fit changé SANS nouvelle brute (mode
        # dossier consommé) doit quand même rafraîchir le rendu — le worker
        # recalcule et repousse UNE fois (sinon affichage figé jusqu'à la
        # prochaine frame, constat Alain : « bouger un gain ne change rien »).
        self._rafraichir_rendu = False
        self._dernier_st = None          # dernier dict d'état poussé (réutilisé)
        # Jalon 54 : instantanés du recalage « Linear Fit » pour le worker —
        # le worker n'a JAMAIS le droit de lire les variables Tk (piège
        # « main thread is not in main loop », cf. régression constatée).
        self._fit_actif = False
        self._fit_mode = "offset"
        self.archives = {}              # rôle → ArchiveFrames (mode compo)
        # Jalon 16 : re-stack sur la meilleure référence — score qualité
        # (nb d'étoiles) parallèle à archive.chemins, ancre courante, et
        # déclencheurs (auto : marge en étoiles ; manuel : bouton).
        self._scores = []            # score par frame archivée (même ordre)
        self.restack_request = False # bouton « ⟳ Re-stacker (meilleure brute) »
        self._ref_score = None       # score de la référence courante
        self._ancre_idx = None       # index d'archive de la brute servant d'ancre
        self._ancre_role = None      # jalon 20 : rôle de cette brute (compo)
        self._ancre_score = None     # son score
        self._restack_depuis = 0     # frames archivées depuis le dernier re-stack
        self._scores_par_role = {}   # jalon 20 : rôle → scores (ordre de l'archive)
        # Jalon 18 : rendre le re-stack VISIBLE (retour réel d'Alain sur le
        # jalon 16 : « pas simple de voir le restack »). Ligne d'état DÉDIÉE
        # (toujours affichée, jamais écrasée par les messages de frames),
        # horodatage, GAIN, compteur de session et historique (bouton « ⓘ »).
        # Écrit par le worker (attributs simples), lu par _update_status
        # dans le thread Tk.
        self.restack_info = ""           # texte de la ligne dédiée ("" = rien)
        self.restack_couleur = "#888888" # gris (rien) / vert (succès) / ambre (échec)
        self.restack_total = 0           # re-stacks RÉUSSIS de la session
        self.restack_hist = []           # historique horodaté (récent en tête)
        # Jalon 56 (branchement du solveur) : astrométrie de l'empilement.
        # L'objet SuiviAstrometrie vit dans le WORKER (résolution UNIQUE sur la
        # grille complète puis PROPAGATION à chaque réempilement) ; l'UI ne lit
        # que des attributs simples (astro_info), comme la ligne de re-stack.
        # Les INDICES de la cible arrivent par INSTANTANÉ (jamais lus dans les
        # widgets par le worker, cf. piège « main thread is not in main loop »).
        self.suivi_astro = astro_mod.SuiviAstrometrie()
        self.astro_info = ""             # texte de la ligne dédiée ("" = rien)
        self.astro_couleur = "#888888"   # gris / vert (résolu) / ambre (souci)
        self._astro_actif = False        # case « Astrométrie » (instantané Tk)
        self._astro_indices = None       # (ra, dec, champ) validés (instantané)
        # Champ SEUL (sans coordonnées) : saisi par l'utilisateur qui connaît sa
        # focale mais pas ses coordonnées — sert de `fov` indicatif au balayage
        # ASTAP (CONSTAT RÉEL du 23/09/2026 : sans ordre de grandeur de champ,
        # le balayage complet d'ASTAP échoue sur M31 ; avec, il résout en 0,2 s).
        self._astro_champ_seul = None
        self._astro_fov_essayes = set()  # valeurs de fov DÉJÀ tentées (1 essai
                                         # par valeur : un balayage identique
                                         # redonnerait le même échec)
        self._astro_balayage = None      # base de balayage ASTAP ? (sonde UNE
                                         # fois par session — listdir coûteux)
        self._astro_bases = ""           # familles de bases installées (état)
        # Jalon 56 (étape 4) : photométrie — zéro-point PAR BANDE mesuré sur
        # l'empilement via le WCS résolu (appariement mutuel au catalogue Gaia).
        # Mesure SEULE (aucun effet sur l'image) : l'application aux gains du
        # stacker est l'étape 5. Le catalogue est lu UNE fois par mesure.
        self.photometrie = photo_mod.Photometrie()
        self.photo_info = ""             # texte de la ligne dédiée ("" = rien)
        self.photo_couleur = "#888888"
        self._photo_actif = False        # case « Photométrie » (instantané Tk)
        # v2.37.0 : DEMANDE explicite de mesure (décochage/recochage de la case).
        # Le worker la sert même quand AUCUNE frame n'est lisible — constat
        # d'Alain du 25/09/2026 : « en fin de stack, décocher et recocher la
        # SPCC ne met rien à jour : le libellé reste gris avec les anciennes
        # valeurs ». Sans ce service, la mesure n'était tentée qu'à la prochaine
        # frame, qui n'arrive jamais en fin de source (cf.
        # _servir_demandes_sans_frame).
        self._photo_demande = False
        # Jalon 58 : SPCC ABSOLUE (calibration spectrophotométrique « à la
        # Siril ») — mesure SÉPARÉE, qui a besoin des profils CAPTEUR/FILTRES de
        # la base Siril et des spectres Gaia. Elle remplace les gains Gaia
        # RELATIFS du jalon 56 quand sa case est cochée (elle est juste par
        # construction : elle compare les RATIOS de couleur de l'image aux
        # ratios PRÉDITS par les spectres, pas une magnitude G trop large).
        self.spcc = spcc_mod.SessionSpcc()
        self.spcc_info = ""
        self.spcc_couleur = "#888888"
        self._spcc_actif = False         # case « SPCC » (instantané Tk)
        self._spcc_essais = 0            # tentatives de mesure (session)
        self._spcc_dernier = 0.0         # instant de la dernière tentative
        self._spcc_demande = False       # v2.37.0 : mesure redemandée par la case
        # Jalon 56 (étape 5) : CASE À PART, DÉCOCHÉE PAR DÉFAUT (opt-in demandé
        # par Alain, 23/09/2026) — c'est elle, et elle seule, qui fait écrire
        # les gains photométriques dans le stacker (donc qui CHANGE l'image).
        self._photo_gains_actif = False
        self._photo_gains_pose = {}      # derniers gains posés (suivi de rendu)
        self._photo_essais = 0           # tentatives de mesure (session)
        self._photo_dernier = 0.0        # monotonic du dernier essai
        self._astro_msg_indices = ""     # raison d'un refus des indices saisis
        self._astro_source = ""          # « saisie », « image <fichier> », « ASTAP »…
        # Repli ASTAP « aveugle » (décision d'Alain, 23/09/2026) : tenté quand
        # AUCUN indice n'est disponible (caméra live sans en-tête FITS). Le WCS
        # rendu par ASTAP est gardé ici pour servir de repli si le solveur
        # interne refuse ensuite ; compteur borné (un balayage est LENT).
        self._astro_wcs_secours = None
        self._astro_aveugles = 0
        self._astro_dernier_aveugle = 0.0
        # Jalon 17 : filtre anti-brutes très défocalisées (rejet d'office,
        # case pour désactiver — décision d'Alain). Mesure par frame à
        # l'arrivée (fwhm, nb d'étoiles) ; le filtre compare à la médiane des
        # frames gardées (≥ 3 avant tout rejet, jamais de rejet sur mesure
        # impossible) ; compteur exposé dans les stats d'empilement.
        self.rejeter_flou = True     # état lu par le thread worker (case UI)
        self.floues_rejetees = 0     # frames rejetées par le filtre (session)
        self._fwhm_hist = []         # (fwhm, nb) des frames gardées — médianes
        self._fwhm_par_role = {}     # jalon 19 : historique PAR RÔLE en mode
                                     # compo (un filtre étroit ne montre pas
                                     # le même champ qu'un autre)

        # --- état du zoom / pan (affichage)
        self.zoom = 1.0                # 1.0 = image ajustée à la fenêtre
        self.view_cx = self.view_cy = None   # centre de vue (coords image), None = centre
        self._last_disp = None         # dernière image déjà étirée (pour re-rendu)
        # --- Jalon 75 : histogramme à deux bandes et barres de niveaux ------
        self.hist_mode = "les_deux"     # « Histogramme » : les_deux/brut/sortie
        # Échelle VERTICALE de la bande BASSE uniquement (décision d'Alain,
        # 28/09/2026) : False = logarithmique (défaut historique — la queue
        # des valeurs brillantes reste lisible), True = LINÉAIRE (le fond
        # devient un vrai PIC). La bande HAUTE garde toujours le log : mesurée
        # en linéaire, elle tombait à 10 bacs visibles sur 256 (une aiguille
        # sans usage). Voir `_courbes_pts`.
        self.hist_lineaire = False
        self._hist_brut = None          # (canaux, axe_max) des données linéaires
        self._hist_sortie = None        # canaux de la SORTIE DU MOTEUR
        self._hist_drag = None          # barre en cours de glissement
        self._vl_mode_avant_fige = None  # mode logD avant ⏹ (VeraLux)
        self._drag = None              # point de départ du glisser-déplacer

        # --- traitement externe (instantané de l'empilement)
        self.ext_request = False        # demande en attente (lue par le worker)
        self.ext_busy = False           # un traitement externe tourne
        self.ext_job = None             # (gx?, cmd_gx, dn?, cmd_dn, bxt?,
                                        # cmd_bxt, mode_dn, force_dn,
                                        # scnr?, scnr_doux?, demagenta?)
                                        # dn = débruitage : GraXpert IA
                                        # (subprocess) OU ondelettes/nlm
                                        # (local, en mémoire)
        self.proc_show = None           # aperçu traité (réduit, pour affichage)
        self.proc_full = None           # résultat traité pleine résolution (sauvegarde)
        self.proc_entete = None         # en-tête FITS de ce résultat (v2.38.3)
        self.proc_new = False           # un nouveau résultat vient d'arriver
        self.save_asseen_request = None  # (chemin, vue, réglages, lineaire)
        self.asseen_busy = False        # sauvegarde « tel que vu » en cours (thread dédié)
        self.asseen_result = None       # chemin ou "ERREUR: …" — écrit par le thread, lu par _tick
        self.asseen_titre = None        # titre du dialogue (les 2 boutons partagent le thread)
        self.msg_outils = None          # erreurs d'outil non bloquantes (chaîne par couche)
        self.dernier_applicatif = None  # AVAAPPLI du dernier fichier écrit (dialogue)
        self.ext_msg = "—"              # message d'état (écrit par le thread, lu par _tick)
        self._ext_shown = None
        self._vl_lbl_txt = "—"          # mémo du texte affiché dans lbl_vl
                                        # (jalon 40 : anti-spam du ⏳ à 30 ms)
        self._vl_pb_active = False      # curseur de calcul actuellement visible
        # Jalon 42 : cadence d'empilement (sources dossier). `cadence_lecture`
        # = miroir thread-sûr (int écrit côté UI, lu par le worker) ;
        # `_prochaine_lecture`/`_prochain_scan` = état du worker seul ;
        # `_a_lu_une_frame` = drapeau « une brute vient d'être lue » (le
        # worker arme la fenêtre quand TOUTES les brutes détectées sont lues).
        self.cadence_lecture = 0
        self._prochaine_lecture = 0.0
        self._prochain_scan = 0.0
        self._a_lu_une_frame = False
        self._rafale_reste = self.RAFALE_MAX   # jalon 46 : budget de la
                                               # rafale en cours (décrémenté
                                               # à chaque brute lue)
        self._cadence_lbl_txt = None    # mémo du texte affiché dans lbl_cadence
        self._cadence_cbs = []          # combobox « Empiler les brutes » —
        self._cadence_lbls = []         # jalon 47 : UN SEUL exemplaire (cadre
                                        # « Cadence d'empilement », partagé)
        self.ext_state = "idle"         # idle | busy | ok | error
        self.ext_t0 = None              # début du traitement en cours (chrono)
        self._ext_popup = False        # erreur à signaler par popup

        # v2.38.7 : chaque étape du démarrage est JOURNALISÉE (`journal.txt`) —
        # c'est ce qui rend un démarrage raté diagnosticable quand la fenêtre
        # n'apparaît jamais (constat d'Alain, 27/09/2026 : « l'appli ne se
        # lance pas sous linux », sans aucun message).
        # File des mesures de disque DIFFÉRÉES (v2.38.11) — créée AVANT
        # l'interface : `_restaurer_config` (appelée juste après la construction)
        # peut déjà en demander une, et elle doit rester BORNÉE.
        self._mesures = queue.Queue()
        self._mesure_en_cours = False
        journal.note("démarrage", "construction de l'interface")
        self._build_ui()
        journal.note("démarrage", "restauration de la configuration")
        self._restaurer_config()
        # v2.38.11 : LES MESURES DE DISQUE SONT DIFFÉRÉES ET BORNÉES. La fenêtre
        # s'ouvre D'ABORD ; le nettoyage des résidus, l'état des outils, le
        # dossier de travail et les catalogues sont sondés dans un fil DÉMON
        # (5 s par mesure), et l'interface le dit. Constat RÉEL du 27/09/2026 : un
        # dossier de couches R/G/B sur un NAS filtré par `nftables` bloquait ces
        # sondes faites AVANT l'affichage → l'application ne s'ouvrait pas, sans
        # AUCUN message ni ligne de journal (la mesure de l'environnement, qui
        # précédait la première ligne, se bloquait aussi).
        self._travail_recycle = (0, 0)
        journal.note("démarrage", "prêt (mesures de disque différées, bornées)")
        self.root.after(30, self._tick)
        self.root.after(150, self._premieres_mesures)

    # ------------------------------------------------------------ persistance config
    def _restaurer_config(self):
        """Restaure les réglages persistés (dossier surveillé, CFA, traitement
        externe, étirement) après la construction de l'UI. Les commandes des
        outils externes ont déjà été restaurées au niveau module
        (DEFAULT_CMD_*). Si une commande détectée automatiquement (pas
        persistée) n'existe plus sur cette machine, elle est re-détectée."""
        c = CONFIG
        if c.get("dossier"):
            self.var_folder.set(c["dossier"])
        if c.get("cfa") in ("Auto", "RGGB", "BGGR", "GRBG", "GBRG", "Non"):
            self.var_cfa.set(c["cfa"])
        # --- Jalon 19 : composition multi-filtres (rôles + dossiers des 4
        # lignes, gains, radio « Canal L ») — restauration TOLÉRANTE :
        # format inconnu / rôle hors liste → ligne ignorée (défauts).
        for i in range(4):
            entree = c.get(f"compo_dossier_{i}")
            if isinstance(entree, str) and entree:
                self.var_compo_dossiers[i].set(entree)
        for i in range(4):
            v = c.get(f"compo_role_{i}")
            if isinstance(v, str) and v in ROLES:
                self.var_compo_roles[i].set(v)
        if c.get("compo_nom") in COMPOSITIONS:
            self.var_compo.set(c["compo_nom"])
        gains = c.get("compo_gains")
        if isinstance(gains, dict):
            for canal in ("R", "G", "B"):
                v = gains.get(canal)
                if isinstance(v, (int, float)) and not isinstance(v, bool) \
                        and 0.0 <= float(v) <= 10.0:
                    self.var_compo_gains[canal].set(str(float(v)))
        if c.get("compo_mode_l") in MODES_L:
            self.var_compo_mode_l.set(c["compo_mode_l"])
        # v2.36.0 : normalisation commune des canaux (option). L'instantané est
        # posé ici aussi : le stacker le recevra à sa création.
        if "norm_commune" in c:
            self.var_norm_commune.set(bool(c.get("norm_commune")))
            self._norm_commune = bool(self.var_norm_commune.get())
        self._on_compo_roles()   # composition recollée aux rôles restaurés
        if c.get("process_existing") is False:
            self.var_process_existing.set(False)
        # Traitement externe : ne pas écraser une commande persistée par un
        # défaut re-détecté qui aurait changé — SAUF si son exécutable est
        # INTROUVABLE (v2.38.5). POURQUOI : l'ancienne version ne testait
        # l'existence du binaire QUE lorsqu'aucune commande n'était persistée ;
        # or la commande de REPLI (binaire nu « graxpert … », écrite par une
        # session où la détection avait échoué — cas Linux d'Alain,
        # 27/09/2026) est une chaîne non vide : elle se retrouvait donc figée
        # dans config.json à vie, invisible, et aucune correction de la
        # détection ne pouvait plus la déloger.
        # v2.38.11 : AUCUNE SONDE DISQUE ICI. On restaure les commandes
        # PERSISTÉES (texte), on ANNONCE que la mesure est en cours, et c'est le
        # fil de mesures (borné, APRÈS l'affichage) qui détecte les outils,
        # re-détecte un binaire disparu et sonde le dossier de travail.
        # POURQUOI : ces sondes (`which`, `isfile`, `glob`, `disk_usage`)
        # ATTENDENT indéfiniment sur un montage réseau injoignable — le
        # 27/09/2026, un dossier de couches R/G/B sur le NAS (filtré par
        # `nftables`) empêchait ainsi l'application de s'ouvrir, sans un mot.
        for cle, var in (("cmd_graxpert", self.var_cmd_graxpert),
                         ("cmd_graxpert_dn", self.var_cmd_graxpert_dn),
                         ("cmd_bxt", self.var_cmd_bxt)):
            enreg = (c.get(cle) or "").strip()
            if enreg:
                var.set(enreg)
        self._annoncer_mesures()
        if c.get("ext_graxpert"):
            self.var_ext_graxpert.set(True)
        # Jalons 7/8 (remis le 16/09/2026) — débruitage du traitement
        # externe : méthode au choix (GraXpert IA / ondelettes / NLM) +
        # force commune. La case n'est restaurée que si la méthode est
        # utilisable : ondelettes/NLM (aucun outil requis) ou GraXpert
        # avec commande complète (jamais de popup au démarrage).
        methode_ext = c.get("dn_methode")
        if methode_ext in self.DN_EXT_LABELS:
            self.var_dn_methode.set(self.DN_EXT_LABELS[methode_ext])
        v = c.get("dn_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_dn_force.set(float(v))
        if c.get("ext_dn") and (self.DN_EXT_CODES.get(
                self.var_dn_methode.get(), "graxpert") != "graxpert"
                or gx_live.commande_valide(
                    self.var_cmd_graxpert_dn.get().strip())):
            self.var_ext_dn.set(True)
        if c.get("ext_bxt"):
            self.var_ext_bxt.set(True)
        # Jalon 22 : SCNR + démagenta du traitement externe (booléens
        # explicites — aucun outil requis, numpy seul).
        if c.get("ext_scnr"):
            self.var_ext_scnr.set(True)
        if c.get("ext_scnr_doux"):
            self.var_ext_scnr_doux.set(True)
        if c.get("ext_demagenta"):
            self.var_ext_demagenta.set(True)
        # v2.37.1 : corrections pré-étirement de la chaîne externe. La
        # neutralisation est COCHÉE par défaut → on ne la modifie que si la
        # config porte la clé ET une valeur (même règle que vl_neutre_fond) ;
        # le bruit chromatique, OPT-IN, n'est activé que s'il est demandé.
        if "ext_neutre_fond" in c:
            self.var_ext_neutre.set(bool(c.get("ext_neutre_fond")))
        if c.get("ext_chroma"):
            self.var_ext_chroma.set(True)
        for cle, var, mini, maxi in (
                ("sigk", self.var_sigk, 0.5, 5.0),
                ("target", self.var_target, 0.10, 0.45),
                ("gamma", self.var_gamma, 0.2, 4.0),
                ("saturation", self.var_saturation, 0.0, 3.0),
                # Jalon 75 : saturation par couleur (R/V/B).
                ("sat_r", self.var_sat_r, 0.0, 3.0),
                ("sat_g", self.var_sat_g, 0.0, 3.0),
                ("sat_b", self.var_sat_b, 0.0, 3.0)):
            v = c.get(cle)
            if isinstance(v, (int, float)) and mini <= v <= maxi:
                var.set(float(v))
        self.disp.sigma_k = self.var_sigk.get()
        self.disp.target = self.var_target.get()
        # Jalon 75 : saturation par couleur + bandes d'histogramme affichées.
        # Les BARRES de niveaux et l'état « figé », eux, ne sont pas restaurés
        # (comme `auto` et black/white) : ils appartiennent à la session.
        self._on_sat_canaux()
        if c.get("hist_mode") in self.HIST_CODES:
            self.hist_mode = c.get("hist_mode")
            self.var_hist_mode.set(self.HIST_LABELS[self.hist_mode])
            self.cv_hist.config(height=self._hauteur_hist())
        # Jalon 75 (échelle y, décision d'Alain du 28/09/2026) : case persistée,
        # DÉFAUT = logarithmique — une config.json d'avant la case n'a pas la
        # clé et garde donc exactement le rendu d'avant.
        if "hist_lineaire" in c:
            self.hist_lineaire = bool(c.get("hist_lineaire"))
            self.var_hist_lineaire.set(self.hist_lineaire)
        # --- Jalon 6 : réglages d'empilement (kappa, méthode/fenêtre rejet)
        if "kappa" in c:
            v = c.get("kappa")
            v = None if v is None else round(float(v), 1)
            etiquette = {None: "Off", 2.0: "2σ", 3.0: "3σ",
                         4.0: "4σ", 5.0: "5σ"}.get(v)
            if etiquette:
                self.var_kappa.set(etiquette)
                self.kappa = None if etiquette == "Off" else float(v)
        methode = c.get("rejet_methode")
        if methode in ("kappa", "winsorized"):
            self.rejet_methode = methode
            self.var_rejet.set("Winsorized (satellites)"
                               if methode == "winsorized"
                               else "kappa-sigma (rapide)")
            self.cb_fenetre.configure(
                state="readonly" if methode == "winsorized" else "disabled")
        fen = c.get("rejet_fenetre")
        if isinstance(fen, int) and not isinstance(fen, bool) \
                and str(fen) in self.cb_fenetre["values"]:
            self.rejet_fenetre = fen
            self.var_fenetre.set(str(fen))
        # --- Jalon 13 : rafraîchissement auto de la référence + équilibrage
        # des canaux (booléen EXPLICITE : une case décochée ne doit pas
        # hériter d'un True d'une session précédente ; clé absente → défauts).
        v = c.get("ref_refresh")
        if isinstance(v, int) and not isinstance(v, bool) \
                and str(v) in self.cb_ref_refresh["values"]:
            self.var_ref_refresh.set(str(v))
        self._on_ref_refresh()
        if "wb_auto" in c:
            self.var_wb.set(bool(c.get("wb_auto")))
        v = c.get("wb_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_wb_force.set(float(v))
        # --- Jalon 17 : filtre anti-brutes très défocalisées — booléen
        # explicite (une case décochée ne doit pas hériter d'un True) ;
        # clé absente → défaut (rejet d'office).
        if "rejeter_flou" in c:
            self.var_rejeter_flou.set(bool(c.get("rejeter_flou")))
        # --- Jalon 54 : recalage colorimétrique « Linear Fit » — booléen
        # explicite (même convention : la clé absente garde le défaut) ;
        # jalon 54b : méthode (« offset » / « gain_offset »).
        if "linear_fit" in c:
            self.var_fit.set(bool(c.get("linear_fit")))
        code_fit = c.get("linear_fit_mode")
        for lib, code in getattr(self, "FIT_METHODES", ()):
            if code == code_fit:
                self.var_fit_methode.set(lib)
                break
        self._on_rejeter_flou()
        self._on_wb()
        # --- Jalon 56 : astrométrie (case + indices de la cible) — chaînes
        # relues par le parseur à l'activation ; case persistée comme les
        # autres (booléen EXPLICITE : décochée doit rester décochée).
        for cle, var in (("astro_ra", self.var_astro_ra),
                         ("astro_dec", self.var_astro_dec),
                         ("astro_champ", self.var_astro_champ)):
            v = c.get(cle)
            if isinstance(v, str):
                var.set(v.strip())
        if "astro_actif" in c:
            self.var_astro.set(bool(c.get("astro_actif")))
        self._on_astro()
        # --- Jalon 56 (étape 4) : photométrie (zéro-point Gaia) — booléen
        # EXPLICITE, comme les autres cases.
        if "photo_actif" in c:
            self.var_photo.set(bool(c.get("photo_actif")))
        self._on_photo()
        # --- Jalon 56 (étape 5) : application des gains photométriques — OPT-IN
        # (case décochée par défaut : clé absente = décochée).
        if "photo_gains_actif" in c:
            self.var_photo_gains.set(bool(c.get("photo_gains_actif")))
        self._on_photo_gains()
        # --- Jalon 58 : SPCC absolue — case OPT-IN (clé absente = décochée) et
        # profils retenus (capteur, filtres R/G/B, référence de blanc). Un nom
        # qui ne figure PLUS dans la base est IGNORÉ (on garde le défaut) :
        # un profil disparu ne doit pas lancer une SPCC impossible.
        categorie = {"spcc_capteur": "capteur", "spcc_fr": "filtres",
                     "spcc_fg": "filtres", "spcc_fb": "filtres",
                     "spcc_blanc": "blancs"}
        # v2.40.0 : le TYPE de capteur (mono / couleur OSC) se restaure AVANT
        # les profils — c'est lui qui décide de LA LISTE dans laquelle ils
        # doivent exister (un capteur OSC n'est pas dans la liste mono, et
        # réciproquement). Valeur inconnue : type d'usage (mono) conservé.
        if c.get("spcc_type") in (self.SPCC_TYPE_MONO, self.SPCC_TYPE_OSC):
            self.var_spcc_type.set(c.get("spcc_type"))
            self._on_spcc_type()     # repeuple capteurs/filtres + libellés
        for cle, var in (("spcc_capteur", self._spcc_vars.get("capteur")),
                         ("spcc_fr", self._spcc_vars.get("fr")),
                         ("spcc_fg", self._spcc_vars.get("fg")),
                         ("spcc_fb", self._spcc_vars.get("fb")),
                         ("spcc_blanc", self._spcc_vars.get("blanc"))):
            v = c.get(cle)
            if var is None or not isinstance(v, str) or not v.strip():
                continue
            liste = self._spcc_noms.get(categorie[cle], ())
            if not liste or v.strip() in liste:
                var.set(v.strip())
        if "spcc_actif" in c:
            self.var_spcc.set(bool(c.get("spcc_actif")))
        self._on_spcc()
        # --- Jalon 6 : réglages VeraLux (moteur tiers opt-in)
        mode_res = c.get("vl_mode_res")
        if mode_res in ("fond cible (auto)", "logD forcé"):
            self.var_vl_mode_res.set(mode_res)
            self._sync_vl_mode()   # répercute dans disp + libellé bouton 🔒
        v = c.get("vl_target")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.10 <= float(v) <= 0.45:
            self.var_vl_target.set(float(v))
            self.disp.vl_target_bg = float(v)
        v = c.get("vl_logd")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 7.0:
            self.var_vl_logd.set(float(v))
            self.disp.vl_log_d = float(v)
        profil = c.get("vl_profil")
        if profil and profil in self.cb_vl_profil["values"]:
            self.var_vl_profil.set(profil)
            self.disp.vl_profil = profil
        if c.get("vl_graxpert") and gx_live.commande_valide(
                self.var_cmd_graxpert.get().strip()):
            self.var_vl_graxpert.set(True)
            self._on_vl_graxpert()   # sans popup : commande validée avant
        # --- Jalon 9 (remis le 16/09/2026) : débruitage live (méthode +
        # force tolérantes : méthode inconnue → nlm, force hors [0,1] → 0.5)
        methode_dn = c.get("vl_denoise_methode")
        if methode_dn in self.VL_DN_LABELS:
            self.var_vl_dn_methode.set(self.VL_DN_LABELS[methode_dn])
        v = c.get("vl_denoise_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_vl_dn_force.set(float(v))
        self.disp.vl_denoise_methode = self.VL_DN_CODES.get(
            self.var_vl_dn_methode.get(), "nlm")
        self.disp.vl_denoise_force = self.var_vl_dn_force.get()
        if c.get("vl_denoise"):
            self.var_vl_dn.set(True)
            self._on_vl_denoise()    # sans popup : aucun outil externe requis
        # --- Jalon 12 : netteté live (cadre INDÉPENDANT du moteur
        # d'étirement : elle s'applique en STF/manuel comme en VeraLux).
        # Itérations restaurées seulement si elles sont dans les bornes du
        # module : une valeur aberrante (99) n'est pas « rabattue »
        # silencieusement, le défaut (5) reste. scl_sharp.set() → passe par le
        # callback du curseur (valeur + étiquette + disp, une seule voie).
        v = c.get("vl_sharp_iterations")
        if isinstance(v, int) and not isinstance(v, bool) \
                and 1 <= v <= nettete_live.ITERATIONS_MAX:
            self.scl_sharp.set(float(v))
        self.disp.vl_sharp_iterations = int(round(self.var_vl_sharp_iter.get()))
        if c.get("vl_sharp"):
            self.var_vl_sharp.set(True)
            self._on_vl_sharp()      # sans popup : aucun outil externe requis
        # --- Jalon 22 : SCNR + démagenta live (booléens explicites, aucun
        # outil externe requis — appliqués après composition, avant étirement).
        if c.get("vl_scnr"):
            self.var_vl_scnr.set(True)
            self._on_vl_scnr()
        if c.get("vl_scnr_doux"):
            self.var_vl_scnr_doux.set(True)
            self._on_vl_scnr_doux()
        if c.get("vl_demagenta"):
            self.var_vl_demagenta.set(True)
            self._on_vl_demagenta()
        # v2.36.1 : neutralisation de la couleur du fond — DÉFAUT COCHÉE, donc on
        # ne l'active que si la config la demande ET qu'une valeur est présente
        # (une config antérieure ne doit pas changer le défaut).
        if "vl_neutre_fond" in c:
            self.var_vl_neutre.set(bool(c.get("vl_neutre_fond")))
            self._on_vl_neutre()
        # v2.37.0 : réduction du bruit chromatique — DÉFAUT DÉCOCHÉE, donc une
        # config antérieure (sans la clé) la laisse décochée ; la FORCE est
        # restaurée de façon TOLÉRANTE (valeur hors [0,1] ou illisible :
        # IGNORÉE, la valeur d'usage reste — comme le débruitage live).
        v = c.get("vl_chroma_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_vl_chroma_force.set(float(v))
        self.disp.vl_chroma_force = float(self.var_vl_chroma_force.get())
        # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma, en pixels PLEINE
        # RÉSOLUTION — restauré TOLÉRANT (hors [0,5 ; 8] ou illisible : IGNORÉ, la
        # valeur d'usage reste le défaut du module) et immédiatement reposé à
        # l'échelle de l'aperçu (`_poser_rayon_chroma`), comme le fait le worker à
        # chaque aperçu.
        r = c.get("vl_chroma_rayon_ref")
        if isinstance(r, (int, float)) and not isinstance(r, bool) \
                and 0.5 <= float(r) <= 8.0:
            self.rayon_chroma_ref = float(r)
            self.var_vl_chroma_rayon.set(float(r))
        self._poser_rayon_chroma(self._echelle_apercu)
        if c.get("vl_chroma"):
            self.var_vl_chroma.set(True)
            self._on_vl_chroma()
        # v2.38.0 : RENDU PLEINE RÉSOLUTION de l'écran — booléen EXPLICITE ; clé
        # absente (config antérieure) → DÉCOCHÉE, le comportement d'origine
        # (aperçu 1600 px) est préservé.
        if c.get("vl_pleine_res_ecran"):
            self.var_vl_pleine_res.set(True)
            self._on_vl_pleine_res()
        # Jalon 42 : cadence d'empilement — restauration TOLÉRANTE (valeur
        # absente/inconnue → « dès réception », jamais de surprise).
        cad = c.get("cadence_lecture")
        if isinstance(cad, (int, float)) and int(cad) in self.CADENCE_LABELS:
            self.var_cadence.set(self.CADENCE_LABELS[int(cad)])
            self._on_cadence()
        self._maj_lbl_sharp()        # étiquette juste dès le démarrage
        # Moteur d'étirement en DERNIER : la bascule VeraLux masque les
        # réglages STF et affiche le cadre VeraLux avec les valeurs ci-dessus.
        # (moteur indisponible → STF conservé, sans popup)
        if c.get("moteur") == "VeraLux" and veralux_moteur.moteur_disponible():
            self.var_moteur.set("VeraLux")
            self._on_moteur()
        # Jalon 47 : source connue → montrer uniquement les cadres utiles
        # (no-op si la source n'a pas changé depuis la construction).
        self._maj_visibilite_cadres()

    def _sauver_config_app(self):
        """Persiste les réglages de l'interface dans config.json (appelé à la
        fermeture). Ne touche pas aux entrées inconnues (extensibilité)."""
        c = dict(CONFIG)          # conserve les clés futures/éventuelles
        if self.var_folder.get().strip():
            c["dossier"] = self.var_folder.get().strip()
        c["cfa"] = self.var_cfa.get()
        # Jalon 19 : réglages de la composition (rôles + dossiers des 4
        # lignes, gains, radio « Canal L ») — relus au démarrage suivant.
        for i in range(4):
            c[f"compo_role_{i}"] = self.var_compo_roles[i].get()
            c[f"compo_dossier_{i}"] = self.var_compo_dossiers[i].get().strip()
        c["compo_nom"] = self.var_compo.get()
        c["compo_gains"] = {canal: self._lire_gains()[canal]
                            for canal in ("R", "G", "B")}
        c["compo_mode_l"] = self.var_compo_mode_l.get()
        # v2.36.0 : normalisation commune des canaux (option, booléen explicite
        # comme les autres cases : une case décochée ne doit pas hériter d'un True).
        c["norm_commune"] = bool(self.var_norm_commune.get())
        c["process_existing"] = self.var_process_existing.get()
        # Les commandes ne sont persistées que si leur OUTIL EXISTE (v2.38.5) :
        # une commande de repli (« graxpert … », binaire nu) figée dans
        # config.json empêchait la détection de rejouer au lancement suivant —
        # l'utilisateur installait GraXpert après coup sans que rien ne change.
        # Une commande sans outil est donc RETIRÉE de la config (la détection
        # rejouera), la valeur restant affichée dans le champ de l'interface.
        for cle, var in (("cmd_graxpert", self.var_cmd_graxpert),
                         ("cmd_graxpert_dn", self.var_cmd_graxpert_dn),
                         ("cmd_bxt", self.var_cmd_bxt)):
            txt = var.get().strip()
            if txt and not gx_live.outil_manquant(txt):
                c[cle] = txt
            else:
                c.pop(cle, None)
        if self.var_ext_graxpert.get():
            c["ext_graxpert"] = True
        if self.var_ext_dn.get():
            c["ext_dn"] = True
        c["dn_methode"] = self.DN_EXT_CODES.get(self.var_dn_methode.get(),
                                                "graxpert")
        c["dn_force"] = self.var_dn_force.get()   # force débruitage externe
        if self.var_ext_bxt.get():
            c["ext_bxt"] = True
        # Jalon 22/23 : chaîne couleur (live et externe) — booléens
        # EXPLICITES (True comme False, cf. convention ci-dessous).
        c["vl_scnr"] = bool(self.var_vl_scnr.get())
        c["vl_scnr_doux"] = bool(self.var_vl_scnr_doux.get())
        c["vl_demagenta"] = bool(self.var_vl_demagenta.get())
        # v2.36.1 : neutralisation de la couleur du fond — booléen EXPLICITE
        # (comme les autres cases : si Alain la décoche, elle reste décochée).
        c["vl_neutre_fond"] = bool(self.var_vl_neutre.get())
        # v2.37.0 : réduction du bruit chromatique — booléen EXPLICITE (comme
        # les autres cases) + force dans [0, 1].
        c["vl_chroma"] = bool(self.var_vl_chroma.get())
        c["vl_chroma_force"] = float(self.var_vl_chroma_force.get())
        # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma, en pixels PLEINE
        # RÉSOLUTION (curseur « Rayon de référence »).
        c["vl_chroma_rayon_ref"] = float(self.rayon_chroma_ref)
        # v2.38.0 : rendu pleine résolution de l'écran (booléen EXPLICITE, comme
        # les autres cases : décoché, il reste décoché).
        c["vl_pleine_res_ecran"] = bool(self.var_vl_pleine_res.get())
        c["ext_scnr"] = bool(self.var_ext_scnr.get())
        c["ext_scnr_doux"] = bool(self.var_ext_scnr_doux.get())
        c["ext_demagenta"] = bool(self.var_ext_demagenta.get())
        # v2.37.1 : corrections pré-étirement de la chaîne externe (booléens
        # EXPLICITES, comme toutes les autres cases).
        c["ext_neutre_fond"] = bool(self.var_ext_neutre.get())
        c["ext_chroma"] = bool(self.var_ext_chroma.get())
        c["sigk"] = self.var_sigk.get()
        # Jalon 42 : cadence d'empilement (mode dossier), en secondes.
        c["cadence_lecture"] = int(self.cadence_lecture)
        c["target"] = self.var_target.get()
        c["gamma"] = self.var_gamma.get()
        c["saturation"] = self.var_saturation.get()
        # Jalon 75 : saturation par couleur (R/V/B) et bandes d'histogramme
        # affichées. Les barres de niveaux et l'état figé ne sont PAS persistés.
        c["sat_r"] = float(self.var_sat_r.get())
        c["sat_g"] = float(self.var_sat_g.get())
        c["sat_b"] = float(self.var_sat_b.get())
        c["hist_mode"] = self.hist_mode
        # Jalon 75 : échelle y de la bande basse (log par défaut) — c'est un
        # réglage de LECTURE, pas de session : il se retrouve au lancement.
        c["hist_lineaire"] = bool(getattr(self, "hist_lineaire", False))
        # Jalon 6 : réglages d'empilement et VeraLux. Les booléens sont
        # stockés EXPLICITEMENT (True comme False) : une case décochée ne
        # doit pas hériter d'un True d'une session précédente.
        c["kappa"] = self.kappa                  # None → null JSON (« Off »)
        c["rejet_methode"] = self.rejet_methode
        c["rejet_fenetre"] = int(self.rejet_fenetre)
        # Jalon 13 : alignement (référence auto) + équilibrage des canaux —
        # booléen explicite (comme les autres cases).
        c["ref_refresh"] = int(self.ref_refresh)
        c["wb_auto"] = bool(self.var_wb.get())
        c["wb_force"] = float(self.var_wb_force.get())
        # Jalon 17 : filtre défocalisation — booléen explicite (comme les
        # autres cases : une case décochée ne doit pas hériter d'un True).
        c["rejeter_flou"] = bool(self.var_rejeter_flou.get())
        # Jalon 54 : recalage colorimétrique « Linear Fit » — booléen
        # explicite (comme les autres cases : False doit être persisté) ;
        # jalon 54b : méthode persistée (offset seul par défaut, retour du
        # test réel d'Alain).
        c["linear_fit"] = bool(self.var_fit.get())
        c["linear_fit_mode"] = self._code_fit_methode()
        # Jalon 56 : astrométrie — case d'activation (booléen explicite) et
        # indices de la cible, persistés TELS QUE SAISIS (le parseur les relit
        # à l'activation ; une chaîne non interprétable est refusée à ce
        # moment-là, jamais silencieusement convertie).
        c["astro_actif"] = bool(self.var_astro.get())
        c["astro_ra"] = self.var_astro_ra.get().strip()
        c["astro_dec"] = self.var_astro_dec.get().strip()
        c["astro_champ"] = self.var_astro_champ.get().strip()
        # Jalon 56 (étape 4) : photométrie — case d'activation (booléen
        # explicite : la mesure n'a aucun effet sur l'image, mais son état doit
        # survivre à la session).
        c["photo_actif"] = bool(self.var_photo.get())
        # Jalon 56 (étape 5) : OPT-IN — la case qui écrit les gains dans le
        # stacker. Persistée comme les autres (une case cochée le reste).
        c["photo_gains_actif"] = bool(self.var_photo_gains.get())
        # Jalon 58 : SPCC absolue — case OPT-IN (décochée par défaut : une
        # calibration écrite dans l'image ne doit jamais être activée par
        # surprise) + profils choisis, persistés pour la prochaine session.
        c["spcc_type"] = self.var_spcc_type.get()
        c["spcc_actif"] = bool(self.var_spcc.get())
        for cle, var in (("spcc_capteur", self._spcc_vars.get("capteur")),
                         ("spcc_fr", self._spcc_vars.get("fr")),
                         ("spcc_fg", self._spcc_vars.get("fg")),
                         ("spcc_fb", self._spcc_vars.get("fb")),
                         ("spcc_blanc", self._spcc_vars.get("blanc"))):
            if var is not None:
                c[cle] = var.get()
        c["moteur"] = self.var_moteur.get()
        c["vl_mode_res"] = self.var_vl_mode_res.get()
        c["vl_target"] = self.var_vl_target.get()
        c["vl_logd"] = self.var_vl_logd.get()
        c["vl_profil"] = self.var_vl_profil.get()
        c["vl_graxpert"] = bool(self.var_vl_graxpert.get())
        # Jalon 9 : débruitage live — booléen explicite (comme vl_graxpert),
        # méthode en code interne ("nlm"/"ondelettes"), force dans [0, 1].
        c["vl_denoise"] = bool(self.var_vl_dn.get())
        c["vl_denoise_methode"] = self.VL_DN_CODES.get(
            self.var_vl_dn_methode.get(), "nlm")
        c["vl_denoise_force"] = self.var_vl_dn_force.get()
        # Jalon 12 : netteté live — booléen explicite (comme vl_graxpert/
        # vl_denoise) et itérations en ENTIER borné par le module. La PSF n'est
        # pas persistée : elle vient de la mesure de seeing de la session.
        c["vl_sharp"] = bool(self.var_vl_sharp.get())
        c["vl_sharp_iterations"] = int(self.disp.vl_sharp_iterations)
        sauver_config(c)

    # ------------------------------------------------------------ construction UI
    # Contrôles caméra QHY (jalon 25, demandes d'Alain du 19/09/2026) :
    # exposition en curseur LOGARITHMIQUE à deux échelles — un curseur
    # linéaire ne peut pas couvrir un rapport de 80 millions : en log, le
    # pas est multiplicatif et le réglage reste fin partout. `var_expo`
    # reste TOUJOURS en ms réelles (contrat apply_settings + tests).
    # Coupure à 5 S (demande d'Alain, 20/09/2026, v2.20.3 — vaut pour
    # TOUTES les caméras, bornes natives ou échelles fixes) : case
    # DÉCOCHÉE = min → 5 s ; COCHÉE = 5 s → exposition max.
    _EXPO_COURT = (0.011, 5000.0)      # ms : 11 µs → 5 s
    _EXPO_LONG = (5000.0, 900000.0)    # ms : 5 s → 900 s

    # ------------------------------------------------------ case « Échelle longue »
    # Jalon 34, CORRECTION d'Alain (20/09/2026, retour réel Player One) : la
    # case reste TOUJOURS VISIBLE — la masquer (première mouture) n'était
    # pas ce qui était demandé. Elle redevient même UTILE avec des bornes
    # natives : cochée, le curseur log se concentre sur la longue portée
    # (1 s → exposition max) pour un réglage fin des longues poses ;
    # décochée, il couvre toute la plage (µs → max). Son libellé affiche la
    # borne max RÉELLE (2000 s sur Uranus-C Pro) au lieu du « 900 s » codé
    # en dur (point 1 du relevé d'Alain).
    def _maj_libelle_expo_longue(self):
        """Libellé « Échelle longue (5 s – max) » : max = borne RÉELLE de la
        caméra si détectée, sinon 900 s (échelle fixe d'origine)."""
        hi = (self._EXPO_DYN[1] if self._EXPO_DYN is not None
              else self._EXPO_LONG[1])
        self.chk_expo_longue.config(
            text=f"Échelle longue ({_fmt_expo(self._EXPO_LONG[0])} – "
                 f"{_fmt_expo(max(hi, self._EXPO_LONG[0]))})")

    def _expo_bornes(self):
        """Bornes actives du curseur log, coupure à 5 s (Alain, 20/09/2026) :
        case DÉCOCHÉE = min → 5 s, COCHÉE = 5 s → max — identique pour
        TOUTES les caméras (bornes natives ou échelles fixes d'origine)."""
        if self._EXPO_DYN is not None:
            lo, hi = self._EXPO_DYN
            pivot = self._EXPO_LONG[0]          # 5 s
            if lo < pivot < hi:
                # La plage native chevauche la coupure : la case est utile.
                return ((pivot, hi) if self.var_expo_longue.get()
                        else (lo, pivot))
            return (lo, hi)   # plage native d'un seul côté de 5 s : sans effet
        return self._EXPO_LONG if self.var_expo_longue.get() else self._EXPO_COURT

    def _expo_depuis_pos(self, p):
        """Curseur 0..1000 → ms (échelle logarithmique de l'échelle active)."""
        lo, hi = self._expo_bornes()
        p = min(max(float(p), 0.0), 1000.0)
        return lo * (hi / lo) ** (p / 1000.0)

    def _pos_depuis_expo(self, ms):
        """ms → curseur 0..1000 (inverse du mapping ci-dessus, borné)."""
        lo, hi = self._expo_bornes()
        ms = min(max(float(ms), lo), hi)
        return 1000.0 * math.log(ms / lo) / math.log(hi / lo)

    def _maj_expo(self, ms, replacer=True):
        """Pose l'exposition réelle (ms bornées), l'affichage et la demande."""
        lo, hi = self._expo_bornes()
        ms = min(max(float(ms), lo), hi)
        self.var_expo.set(ms)
        self.lbl_expo.config(text=_fmt_expo(ms))
        self.var_expo_saisie.set(_fmt_expo(ms))
        if replacer:
            self.s_expo.set(self._pos_depuis_expo(ms))
        self._push_settings()

    def _valider_expo(self, _e=None):
        """Saisie directe de l'exposition (jalon 27) : accepte « 100 »,
        « 0,5 », « 12 ms », « 2 s », « 11 µs » — borne à l'échelle courante
        et BASCULE automatiquement d'échelle si la valeur déborde."""
        t = self.var_expo_saisie.get().strip().lower().replace(",", ".")
        t = t.replace(" ", "")
        facteur = 1.0
        if t.endswith("ms"):
            t = t[:-2]
        elif t.endswith(("µs", "us")):
            t = t[:-2]
            facteur = 0.001
        elif t.endswith("s"):
            t = t[:-1]
            facteur = 1000.0
        try:
            ms = float(t) * facteur
        except ValueError:
            self.var_expo_saisie.set(_fmt_expo(self.var_expo.get()))
            return
        # Bascule automatique d'échelle à la coupure 5 s (toutes caméras) :
        # saisie > 5 s → case cochée ; saisie < 5 s → case décochée.
        if ms > self._EXPO_LONG[0] and not self.var_expo_longue.get():
            self.var_expo_longue.set(True)
        elif ms < self._EXPO_LONG[0] and self.var_expo_longue.get():
            self.var_expo_longue.set(False)
        self._maj_expo(ms)

    def _on_echelle_expo(self):
        """Case « échelle longue » : garde la valeur réelle si elle reste
        dans la nouvelle échelle, sinon la ramène à la borne la plus proche
        (les deux échelles se touchent au pivot 5 s : aucune valeur ne saute,
        et 5 s est le PIVOT commun — atteignable des deux côtés)."""
        self._maj_expo(self.var_expo.get())

    def _on_curseur_expo(self, v):
        self._maj_expo(self._expo_depuis_pos(v), replacer=False)

    def _on_pas_expo(self, facteur):
        self._maj_expo(self.var_expo.get() * facteur)

    def _build_ui(self):
        main = ttk.PanedWindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True)

        # ------- Colonne gauche : zone défilable (canvas + scrollbar)
        container = ttk.Frame(main)
        main.add(container, weight=0)
        canvas = tk.Canvas(container, width=350, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        left = ttk.Frame(canvas, padding=8)
        win_id = canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=max(330, e.width)))

        def _wheel(event):
            w = self.root.winfo_containing(event.x_root, event.y_root)
            if w is None or not (w is canvas or str(w).startswith(str(left))):
                return                                  # molette hors du panneau → ignorer
            if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0:
                canvas.yview_scroll(-2, "units")
            elif getattr(event, "num", 0) == 5 or getattr(event, "delta", 0) < 0:
                canvas.yview_scroll(2, "units")
        canvas.bind_all("<MouseWheel>", _wheel)   # Windows / macOS
        canvas.bind_all("<Button-4>", _wheel)     # Linux
        canvas.bind_all("<Button-5>", _wheel)

        # --- PIÈGE MAJEUR D'ERGONOMIE (constat d'Alain, 25/09/2026) -----------
        # Tk associe la MOLETTE aux listes déroulantes par une liaison de CLASSE
        # (`ttk::combobox::Scroll`) : en défilant les réglages, si le curseur
        # passait sur une liste (ou juste à côté), la molette CHANGEait sa
        # valeur TOUTE SEULE — profil de capteur/filtre de la SPCC, méthode du
        # recalage colorimétrique, référence de blanc… Des réglages ont ainsi pu
        # changer sans que l'utilisateur l'ait voulu, ce qui a faussé des tests.
        # On SUPPRIME ces liaisons de classe : la molette ne modifie plus aucune
        # liste, elle continue de faire défiler le panneau (handler `bind_all`
        # ci-dessus). Pour changer une valeur, il faut désormais OUVRIR la liste.
        for _classe in ("TCombobox", "TSpinbox", "Spinbox"):
            for _ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    self.root.unbind_class(_classe, _ev)
                except tk.TclError:
                    pass

        # --- Fichiers de travail et journal (v2.38.9) : EN HAUT de la colonne.
        # POURQUOI CE DÉPLACEMENT : cette ligne est un indicateur GLOBAL (où vont
        # les fichiers lourds — frames archivées, FITS des outils — et combien
        # d'espace reste) et le POINT D'ENTRÉE du diagnostic (journal). Elle vivait
        # en premières lignes du cadre « Traitement externe (long) », donc à 75 %
        # de la hauteur d'une colonne DÉFILANTE (y≈2421 px sur 3218 px de
        # contenu) : constat RÉEL d'Alain (27/09/2026) « pas de chemin pour temp
        # et pas de bouton journal ». Mesure : les trois boutons ne tenaient pas
        # sur une ligne (cadre 318 px = texte 243 + « Ouvrir » 43 + « 📂 » 28) et
        # le troisième — « Journal » — n'était même pas AFFICHÉ
        # (`winfo_ismapped()` = 0). D'où DEUX lignes : le texte, puis les boutons.
        box = ttk.LabelFrame(left, text="Fichiers de travail et journal",
                             padding=6)
        box.pack(fill="x", pady=3)
        self.lbl_travail = ttk.Label(box, text="—", foreground="#888888",
                                     wraplength=300)
        self.lbl_travail.pack(anchor="w", fill="x")
        rowtr = ttk.Frame(box)
        rowtr.pack(fill="x", pady=(3, 0))
        ttk.Button(rowtr, text="📂 Dossier", width=12,
                   command=self._choisir_dossier_travail).pack(side="left")
        ttk.Button(rowtr, text="Ouvrir", width=8,
                   command=self._ouvrir_dossier_travail
                   ).pack(side="left", padx=(4, 0))
        ttk.Button(rowtr, text="Journal", width=8,
                   command=self._ouvrir_journal).pack(side="left", padx=(4, 0))

        # --- Caméra : la SOURCE + Démarrer/Arrêter sont TOUJOURS visibles ;
        # les contrôles propres à la caméra (exposition, gain, roue, TEC,
        # détection SDK…) vont dans un sous-cadre qui n'apparaît QUE pour une
        # source caméra (jalon 47 : en dossier/composition, la colonne ne
        # montre que ce qui sert au choix en cours — cf.
        # _maj_visibilite_cadres).
        box = ttk.LabelFrame(left, text="Caméra", padding=6)
        box.pack(fill="x", pady=3)
        self.frm_ctrl_cam = ttk.Frame(box)
        # Jalon 52 (demande d'Alain, 21/09/2026) : le CHOIX DE SOURCE doit
        # être EN HAUT DU CADRE DÈS LE LANCEMENT. Avant, frm_ctrl_cam était
        # packé en premier : le choix était SOUS les contrôles ; choisir
        # « Dossier » (frm_ctrl_cam caché) le faisait remonter — mieux — et
        # au retour caméra il RESTAIT en haut (le re-pack de
        # _maj_visibilite_cadres réappend frm_ctrl_cam à la fin) : la place
        # du choix dépendait de l'histoire de la session. En packant le choix
        # et Démarrer/Arrêter AVANT frm_ctrl_cam (pack différé ci-dessous),
        # l'ordre est stable et identique quel que soit le va-et-vient.
        self.var_source = tk.StringVar(value=SOURCES[0])
        self.cb_source = ttk.Combobox(box, textvariable=self.var_source,
                                      values=SOURCES, state="readonly",
                                      width=28)
        self.cb_source.pack(fill="x", pady=2)
        self.cb_source.bind("<<ComboboxSelected>>", self._on_source_choisie)
        rowbtn = ttk.Frame(box)
        rowbtn.pack(fill="x", pady=1)
        self.btn_start = ttk.Button(rowbtn, text="▶ Démarrer", command=self._start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=1)
        self.btn_stop = ttk.Button(rowbtn, text="■ Arrêter", command=self._stop,
                                   state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=1)
        # Jalon 52 : les contrôles caméra APRÈS le choix + Démarrer/Arrêter
        # (le pack_forget/pack de _maj_visibilite_cadres réappend frm_ctrl_cam
        # en fin d'ordre : sa place ne bouge donc jamais).
        self.frm_ctrl_cam.pack(fill="x")
        self.var_expo = tk.DoubleVar(value=100.0)
        self.var_gain = tk.DoubleVar(value=30.0)
        self.var_offset = tk.DoubleVar(value=10.0)
        # Contrôles caméra QHY (jalon 25 — demandes d'Alain du 19/09/2026) :
        # exposition log 11 µs → 5 s (case → 1 s à 900 s) ; gain 0 → 175
        # (unités SDK QHY) ; refroidissement (consigne, lecture, arrêt) ;
        # roue à filtres intégrée (0 = cran noir « Dark », puis LRGBSHO).
        self.var_expo_longue = tk.BooleanVar(value=False)
        self.var_tec_consigne = tk.StringVar(value="-10")
        self.var_filtre = tk.StringVar(value=FILTRES_ROUE[0])
        self._tec_dernier = None          # (temp, pwm, consigne) → _tick
        self._tec_demande = None          # ("consigne", °C) | ("stop", None)
        self._tec_info = None             # texte d'état TEC (thread → _tick)
        self._filtre_demande = None       # index de position 0..N-1
        self._filtre_info = None          # texte d'état roue (thread → _tick)
        self._roue_ok = False             # roue détectée (worker → _tick)
        # --- Exposition : curseur log dédié (11 µs – 5 s / 1 s – 900 s) ---
        # Jalon 27 (demande d'Alain) : zone de saisie en PLUS du curseur
        # (formats acceptés : « 100 », « 0,5 », « 12 ms », « 2 s », « 11 µs »).
        rowe = ttk.Frame(self.frm_ctrl_cam)
        rowe.pack(fill="x", pady=1)
        heade = ttk.Frame(rowe)
        heade.pack(fill="x")
        ttk.Label(heade, text="Exposition").pack(side="left")
        self.var_expo_saisie = tk.StringVar(value=_fmt_expo(100.0))
        self.entry_expo = ttk.Entry(heade, textvariable=self.var_expo_saisie,
                                    width=10, justify="right")
        self.entry_expo.pack(side="right", padx=(0, 4))
        self.entry_expo.bind("<Return>", self._valider_expo)
        self.entry_expo.bind("<FocusOut>", self._valider_expo)
        self.lbl_expo = ttk.Label(heade, text="")
        self.lbl_expo.pack(side="right")
        lignee = ttk.Frame(rowe)
        lignee.pack(fill="x")
        b_em = ttk.Button(lignee, text="-", width=3, takefocus=False,
                          command=lambda: self._on_pas_expo(1 / 1.25))
        b_em.pack(side="left")
        self.s_expo = ttk.Scale(lignee, from_=0, to=1000,
                                value=self._pos_depuis_expo(100.0),
                                command=self._on_curseur_expo)
        self.s_expo.pack(side="left", fill="x", expand=True, padx=3)
        b_ep = ttk.Button(lignee, text="+", width=3, takefocus=False,
                          command=lambda: self._on_pas_expo(1.25))
        b_ep.pack(side="left")
        self.chk_expo_longue = ttk.Checkbutton(
            self.frm_ctrl_cam, text="", variable=self.var_expo_longue,
            command=self._on_echelle_expo)
        self._maj_libelle_expo_longue()   # libellé = bornes réelles (jalon 34)
        self.chk_expo_longue.pack(anchor="w")
        self.sl_gain = self._add_slider(
            self.frm_ctrl_cam, "Gain (0 – 175)", self.var_gain, 0.0, 175.0, 1.0,
            self._push_settings, "{:.0f}", saisie=True)
        self.sl_offset = self._add_slider(
            self.frm_ctrl_cam, "Offset (0 – 255)", self.var_offset, 0.0, 255.0, 1.0,
            self._push_settings, "{:.0f}", saisie=True)
        # --- Roue à filtres intégrée (active si la roue répond, cf. worker)
        rowf = ttk.Frame(self.frm_ctrl_cam)
        rowf.pack(fill="x", pady=(2, 0))
        ttk.Label(rowf, text="Filtre :").pack(side="left")
        self.cb_filtre = ttk.Combobox(rowf, textvariable=self.var_filtre,
                                      state="disabled", width=7,
                                      values=list(FILTRES_ROUE))
        self.cb_filtre.pack(side="left", padx=4)
        self.cb_filtre.bind("<<ComboboxSelected>>", self._on_filtre_choisi)
        self.lbl_filtre = ttk.Label(rowf, text="", foreground="#888888")
        self.lbl_filtre.pack(side="left", padx=(2, 0))
        # --- Refroidissement TEC (consigne + lectures + arrêt) -----------
        rowt = ttk.Frame(self.frm_ctrl_cam)
        rowt.pack(fill="x", pady=(2, 0))
        self.lbl_tec_lib = ttk.Label(rowt, text="Consigne °C :")
        self.lbl_tec_lib.pack(side="left")
        ttk.Entry(rowt, textvariable=self.var_tec_consigne, width=5
                  ).pack(side="left", padx=(4, 4))
        self.btn_tec_on = ttk.Button(rowt, text="❄ Réguler",
                                     command=self._on_consigne_tec,
                                     state="disabled")
        self.btn_tec_on.pack(side="left", padx=(0, 2))
        self.btn_tec_off = ttk.Button(rowt, text="⏹ Arrêter",
                                      command=self._on_arret_tec,
                                      state="disabled")
        self.btn_tec_off.pack(side="left")
        self.lbl_tec = ttk.Label(self.frm_ctrl_cam, text="Capteur : — · TEC : —",
                                 foreground="#888888")
        self.lbl_tec.pack(anchor="w")
        # Détection des caméras « SDK constructeur » (correctif du
        # 19/09/2026 : aucune info au choix de la source). Le scan QHY
        # tourne dans un SOUS-PROCESSUS isolé : un segfault du SDK ne tue
        # jamais l'application (message clair à la place).
        rowd = ttk.Frame(self.frm_ctrl_cam)
        rowd.pack(fill="x", pady=(2, 0))
        ttk.Button(rowd, text="🔎 Détecter", width=12,
                   command=self._detecter_camera).pack(side="left")
        self.lbl_detect = ttk.Label(rowd, text="", foreground="#666666")
        self.lbl_detect.pack(side="left", padx=(6, 0))
        # Jalon 52 (demande d'Alain, 21/09/2026) : « ⏏ Déconnecter » sur SA
        # PROPRE ligne, sous « 🔎 Détecter ». Sur la même ligne (side="right"),
        # un long libellé de caméra détectée (« Touptek : connectée (…) ») le
        # poussait hors de la colonne : il fallait élargir la colonne pour
        # l'atteindre. Une ligne dédiée le rend toujours visible.
        self.btn_deconnect = ttk.Button(self.frm_ctrl_cam,
                                        text="⏏ Déconnecter", width=12,
                                        command=self._deconnecter_camera,
                                        state="disabled")
        self.btn_deconnect.pack(anchor="w", pady=(2, 0))

        # --- Jalon 47 : le réglage de RAFALE (« Empiler les brutes »,
        # jalons 42/45) sort des cadres « Dossier surveillé » et
        # « Composition multi-filtres » où il était DUPLIQUÉ : UN SEUL cadre
        # « Cadence d'empilement », visible uniquement pour ces deux sources
        # (sans objet pour une vraie caméra) — cf. _maj_visibilite_cadres.
        self.frm_rafale = ttk.LabelFrame(left, text="Cadence d'empilement",
                                         padding=6)
        self._creer_cadence(self.frm_rafale)

        # --- Dossier surveillé (visible uniquement pour cette source, jalon 47)
        self.frm_dossier = ttk.LabelFrame(left, text="Dossier surveillé",
                                          padding=6)
        box = self.frm_dossier
        box.pack(fill="x", pady=3)
        row = ttk.Frame(box)
        row.pack(fill="x")
        self.var_folder = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.var_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=self._pick_folder).pack(side="left", padx=(4, 0))
        self.var_process_existing = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Empiler aussi les images déjà présentes",
                        variable=self.var_process_existing).pack(anchor="w")
        rowc = ttk.Frame(box)
        rowc.pack(fill="x", pady=(3, 0))
        ttk.Label(rowc, text="Brutes capteur couleur :").pack(side="left")
        self.var_cfa = tk.StringVar(value=CFA_MODE)
        ttk.Combobox(rowc, textvariable=self.var_cfa, state="readonly", width=6,
                     values=["Auto", "RGGB", "BGGR", "GRBG", "GBRG", "Non"]
                     ).pack(side="left", padx=(4, 0))
        self.var_cfa.trace_add("write", self._on_cfa)
        # Jalon 42/45 : la cadence d'empilement (« Empiler les brutes ») est
        # DÉPLACÉE hors de ce cadre (jalon 47) — un seul exemplaire partagé
        # par dossier surveillé et composition, cf. frm_rafale ci-dessus.
        self.lbl_last = ttk.Label(box, text="Dernier fichier : —")
        self.lbl_last.pack(anchor="w")

        # --- Composition multi-filtres (jalon 19) : 1 à 4 dossiers surveillés,
        # un RÔLE (filtre) par dossier ; le composite temps réel combine les
        # empilements par rôle selon la composition choisie.
        self.frm_compo = ttk.LabelFrame(left, text="Composition multi-filtres",
                                        padding=6)
        box = self.frm_compo
        box.pack(fill="x", pady=3)
        row_c = ttk.Frame(box)
        row_c.pack(fill="x")
        ttk.Label(row_c, text="Composition :").pack(side="left")
        self.var_compo = tk.StringVar(value="HOO")
        cb_compo = ttk.Combobox(row_c, textvariable=self.var_compo,
                                state="readonly", width=8,
                                values=list(COMPOSITIONS))
        cb_compo.pack(side="left", padx=4)
        cb_compo.bind("<<ComboboxSelected>>", lambda e: self._on_compo())
        self.lbl_compo_info = ttk.Label(box, text="", foreground="#666666")
        self.lbl_compo_info.pack(anchor="w")
        # 4 lignes fixes : rôle (filtre) + dossier. Une ligne sans rôle = non
        # utilisée ; le remplissage des rôles CONTRAINT la composition
        # (cf. _on_compo_roles), la composition pré-remplit les rôles.
        self.var_compo_roles = [tk.StringVar(value="") for _ in range(4)]
        self.var_compo_dossiers = [tk.StringVar(value="") for _ in range(4)]
        for i in range(4):
            row = ttk.Frame(box)
            row.pack(fill="x", pady=1)
            cb_role = ttk.Combobox(row, textvariable=self.var_compo_roles[i],
                                   state="readonly", width=5,
                                   values=list(ROLES))
            cb_role.pack(side="left")
            cb_role.bind("<<ComboboxSelected>>", self._on_compo_roles)
            ttk.Entry(row, textvariable=self.var_compo_dossiers[i]).pack(
                side="left", fill="x", expand=True, padx=(4, 0))
            ttk.Button(row, text="…", width=3,
                       command=lambda i=i: self._pick_dossier_compo(i)
                       ).pack(side="left", padx=(4, 0))
        # Radio « Canal L » (utile en LRGB quand le dossier L est vide) :
        # L synthétisé = luminance du composite (combine identité) ;
        # dégradé = composite RGB pur (décisions d'Alain, 18/09/2026).
        row_l = ttk.Frame(box)
        row_l.pack(fill="x", pady=(4, 0))
        ttk.Label(row_l, text="Canal L (si dossier L vide) :").pack(side="left")
        self.var_compo_mode_l = tk.StringVar(value="synthetise")
        self.rb_l_syn = ttk.Radiobutton(row_l, text="Synthétisé",
                                        value="synthetise",
                                        variable=self.var_compo_mode_l)
        self.rb_l_deg = ttk.Radiobutton(row_l, text="Dégradé RGB",
                                        value="degrade",
                                        variable=self.var_compo_mode_l)
        self.rb_l_syn.pack(side="left", padx=(6, 0))
        self.rb_l_deg.pack(side="left", padx=(6, 0))
        # Gains R/G/B du composite : multiplicatifs APRÈS la normalisation
        # linéaire par canal — réglage à chaud de l'équilibre colorimétrique
        # (appliqués au composite dès la frame suivante, cf. _tick).
        row_g = ttk.Frame(box)
        row_g.pack(fill="x", pady=(4, 0))
        ttk.Label(row_g, text="Gains R/G/B :").pack(side="left")
        self.var_compo_gains = {canal: tk.StringVar(value="1.0")
                                for canal in ("R", "G", "B")}
        for canal in ("R", "G", "B"):
            ttk.Entry(row_g, textvariable=self.var_compo_gains[canal],
                      width=5).pack(side="left", padx=(4, 0))
        ttk.Button(box, text="🔎 Détecter les filtres (FITS FILTER)",
                   command=self._detecter_filtres).pack(fill="x", pady=(6, 0))
        # --- v2.36.0 : NORMALISATION COMMUNE DES CANAUX (option, décision
        # d'Alain du 25/09/2026). Décrivée en clair : c'est un changement de
        # comportement visible (fond et grain), pas un réglage cosmétique.
        self.var_norm_commune = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Normalisation commune des canaux",
                        variable=self.var_norm_commune,
                        command=self._on_norm_commune).pack(anchor="w",
                                                            pady=(6, 0))
        ttk.Label(box, text=(
            "Décoché : chaque canal est calé sur SES percentiles, avec SON point "
            "noir — le fond du composite suit alors son propre bruit : empiler "
            "plus ne réduit plus le grain du fond, et il reste coloré. "
            "Coché : les trois canaux partagent la MÊME ÉCHELLE (celle du vert) "
            "et aucun point noir n'est soustrait → le fond garde son niveau "
            "physique (son grain diminue enfin en 1/√n) et les coefficients SPCC "
            "s'appliquent sur la base où ils ont été mesurés. Le fond garde sa "
            "couleur physique (bleu-rouge) : la neutraliser avec l'équilibrage "
            "des canaux ou le recalage colorimétrique."),
            foreground="#888888", wraplength=310).pack(anchor="w")
        # Jalon 45/47 : le choix de cadence est COMMUN aux deux modes —
        # voir le cadre unique `frm_rafale` (plus de combobox ici).
        self._on_compo()    # pré-remplit les lignes de rôle de la compo par défaut

        # --- Calibration (ancre STABLE : les cadres commutables jalon 47 se
        # replacent toujours juste avant elle — l'ordre des cadres ne bouge
        # jamais, quel que soit le nombre d'allers-retours de source)
        box = ttk.LabelFrame(left, text="Calibration", padding=6)
        self.frm_calibration = box
        box.pack(fill="x", pady=3)
        ttk.Button(box, text="Charger un dark…", command=self._load_dark).pack(fill="x", pady=1)
        ttk.Button(box, text="Charger un flat…", command=self._load_flat).pack(fill="x", pady=1)
        ttk.Button(box, text="Effacer calibration",
                   command=self._clear_calib).pack(fill="x", pady=1)
        self.lbl_dark = ttk.Label(box, text="Dark : —", foreground="#888888")
        self.lbl_dark.pack(anchor="w")
        self.lbl_flat = ttk.Label(box, text="Flat : —", foreground="#888888")
        self.lbl_flat.pack(anchor="w")
        # Jalon 53 : chaque dark et chaque flat peut viser UN rôle (filtre)
        # du cadre Composition — le choix se fait AU CLIC sur « Charger un
        # dark/flat… » (boîte « ce dark s'applique à : »), jamais avant
        # (retour d'Alain : plus intuitif). Les libellés détaillent TOUT ce
        # qui est chargé : l'unique PUIS chaque couche active (— si le
        # master de cette couche manque), cf. _maj_libelles_calib.

        # --- Empilement
        box = ttk.LabelFrame(left, text="Empilement", padding=6)
        box.pack(fill="x", pady=3)
        self.lbl_stats = ttk.Label(box, text="Frames : 0\nPixels rejetés (σ) : 0"
                                             "\nFrames non alignées : 0\nAlign. : —")
        self.lbl_stats.pack(anchor="w", pady=(0, 3))
        # Jalon 10 : seeing live (FWHM médiane + nombre d'étoiles) — mesure
        # faite par le thread d'acquisition sur l'aperçu, toutes les 3 s.
        self.lbl_seeing = ttk.Label(box, text="Seeing (FWHM) : —",
                                    foreground="#888888")
        self.lbl_seeing.pack(anchor="w", pady=(0, 3))
        rowf = ttk.Frame(box)
        rowf.pack(fill="x", pady=2)
        # v2.41.0 : ce bouton fait une VRAIE remise à zéro (cf.
        # _reset_empilement) — il ne se contente plus de poser un drapeau que
        # le worker ne lisait qu'en TRAITANT une frame (constat d'Alain,
        # 28/09/2026 : « il faudrait que le bouton réinitialiser réinitialise
        # vraiment »).
        ttk.Button(rowf, text="Réinitialiser l'empilement",
                   command=self._reset_empilement
                   ).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(rowf, text="Réf. = empilement",
                   command=lambda: setattr(self, "ref_request", True)
                   ).pack(side="left", expand=True, fill="x", padx=1)
        # Jalon 13 : rafraîchissement AUTOMATIQUE de la référence
        # d'alignement — la dérive lente (flexure, erreur périodique)
        # éloigne les frames de la référence initiale et l'appariement
        # dégénère ; une référence jeune (l'empilement courant) suit.
        # « jamais » = ancien comportement (référence figée).
        rowr = ttk.Frame(box)
        rowr.pack(fill="x", pady=2)
        ttk.Label(rowr, text="Rafraîchir la référence (frames) :").pack(side="left")
        self.var_ref_refresh = tk.StringVar(value="20")
        self.cb_ref_refresh = ttk.Combobox(
            rowr, textvariable=self.var_ref_refresh, state="readonly", width=6,
            values=["jamais", "10", "20", "30", "50"])
        self.cb_ref_refresh.pack(side="left", padx=4)
        self.cb_ref_refresh.bind("<<ComboboxSelected>>",
                                 lambda e: self._on_ref_refresh())
        # Jalon 16 : re-stack « à la Siril » — re-ancre l'alignement sur la
        # meilleure brute archivée (score = nb d'étoiles) et RECALCULE tout
        # l'empilement depuis l'archive. Déclencheur auto : une brute bat
        # nettement la référence courante ; ce bouton force le recalcul.
        ttk.Button(box, text="⟳ Re-stacker (meilleure brute)",
                   command=lambda: setattr(self, "restack_request", True)
                   ).pack(fill="x", pady=2)
        # Jalon 18 : ligne d'état DÉDIÉE au re-stack (retour réel d'Alain :
        # « pas simple de voir le restack » — le message de la ligne
        # d'alignement est écrasé par la frame suivante) + bouton « ⓘ » =
        # historique horodaté des re-stacks de la session. Gris = rien,
        # vert = re-stack réussi, ambre = échec.
        row_rs = ttk.Frame(box)
        row_rs.pack(fill="x", pady=(2, 0))
        # v2.38.10 : le bouton « ⓘ » est posé EN PREMIER (`side="right"`) et le
        # texte prend ce qui reste. POURQUOI : `pack` alloue dans l'ordre de
        # pose et ABANDONNE le widget qui ne trouve plus de place — mesuré sur
        # cette ligne, un message de re-stack long (≈110 caractères) faisait
        # disparaître le bouton ⓘ (requête 28 px, allocation 0). Posé en
        # premier, il ne peut plus être sacrifié ; le texte, lui, est rogné.
        ttk.Button(row_rs, text="ⓘ", width=3,
                   command=self._montrer_restack_hist).pack(side="right",
                                                            padx=(4, 0))
        self.lbl_restack = ttk.Label(row_rs, text="Re-stack : —",
                                     foreground="#888888", wraplength=250)
        self.lbl_restack.pack(side="left", fill="x", expand=True)
        # Jalon 56 : ASTROMÉTRIE de l'empilement — case + indices de la cible.
        # Le solveur interne résout l'astrométrie UNE fois sur l'empilement
        # (ces indices l'y aident), puis le WCS est PROPAGÉ à chaque
        # réempilement. En mode dossier, les champs peuvent rester VIDES : des
        # indices sont alors lus dans l'en-tête des brutes (OBJCTRA/OBJCTDEC).
        # Interprétation : « 0h42m44s » ou « 00 42 44 » = HEURES (« 0.7123h »
        # aussi) ; un décimal nu (« 10.68333 ») = DEGRÉS. La ligne d'état
        # rappelle les indices retenus — aucune interprétation silencieuse.
        # v2.38.10 : TROIS lignes au lieu d'une. Mesure (constat d'Alain,
        # 27/09/2026 : « le champ et le bouton pour récupérer les coordonnées
        # depuis les brutes ne sont pas visibles sans agrandir la colonne ») :
        # les huit widgets de cette ligne demandaient ≈490 px pour 318 px
        # disponibles → `pack` ABANDONNAIT les deux derniers, le champ
        # « champ° » et le bouton 📷, sans aucun message. Une ligne de contrôles
        # à taille FIXE ne sait pas se replier : elle se répartit sur plusieurs
        # lignes (la case d'abord, puis AD/Dec, puis champ° + le bouton 📷).
        row_a = ttk.Frame(box)
        row_a.pack(fill="x", pady=(4, 0))
        self.var_astro = tk.BooleanVar(value=False)
        ttk.Checkbutton(row_a, text="Astrométrie", variable=self.var_astro,
                        command=self._on_astro).pack(side="left")
        row_ad = ttk.Frame(box)
        row_ad.pack(fill="x", pady=(2, 0))
        ttk.Label(row_ad, text="AD :").pack(side="left", padx=(6, 0))
        self.var_astro_ra = tk.StringVar(value="")
        e_ra = ttk.Entry(row_ad, textvariable=self.var_astro_ra, width=11)
        e_ra.pack(side="left", padx=(2, 0))
        ttk.Label(row_ad, text="Dec :").pack(side="left", padx=(4, 0))
        self.var_astro_dec = tk.StringVar(value="")
        e_dec = ttk.Entry(row_ad, textvariable=self.var_astro_dec, width=11)
        e_dec.pack(side="left", padx=(2, 0))
        row_ch = ttk.Frame(box)
        row_ch.pack(fill="x", pady=(2, 0))
        ttk.Label(row_ch, text="champ° :").pack(side="left", padx=(6, 0))
        self.var_astro_champ = tk.StringVar(value="")
        e_ch = ttk.Entry(row_ch, textvariable=self.var_astro_champ, width=6)
        e_ch.pack(side="left", padx=(2, 0))
        # Bouton : lire AD/Dec/champ depuis l'image courante (dernière brute
        # reçue ou dernier empilement sauvegardé) — remplit les trois champs.
        ttk.Button(row_ch, text="📷", width=3,
                   command=self._lire_indices_image).pack(side="left",
                                                          padx=(6, 0))
        # Les champs sont relus à la VALIDATION (Entrée / sortie du champ) —
        # pas à chaque frappe : un indice à moitié tapé serait refusé pour rien.
        for e in (e_ra, e_dec, e_ch):
            e.bind("<Return>", lambda ev: self._on_astro())
            e.bind("<FocusOut>", lambda ev: self._on_astro())
        self.lbl_astro = ttk.Label(box, text="Astrométrie : —",
                                   foreground="#888888", wraplength=310)
        self.lbl_astro.pack(anchor="w", pady=(2, 0))
        # Jalon 70 — DONNÉES de l'astrométrie : l'application DIT où elle
        # cherche le catalogue Gaia DR3 de Siril, laisse choisir un autre
        # dossier (config `chemin_catalogues`), et le télécharge (1,1 Go,
        # reprise + sha256 vérifié). Sans catalogue, l'astrométrie interne ne
        # peut pas aboutir : le dire ici évite l'échec silencieux constaté
        # sous Linux le 27/09/2026.
        # v2.38.10 : DEUX lignes (le chemin, puis les boutons). MESURE : le
        # libellé du chemin, insécable (un chemin n'a pas d'espace, donc
        # `wraplength` ne le replie PAS), prenait toute la ligne → avec un chemin
        # long comme `~/.local/share/siril`, `pack` ABANDONNAIT 📂 et « ⬇ Gaia ».
        # Le texte est en plus BORNÉ en caractères (`width`), ce qui garantit
        # qu'il ne peut plus manger la ligne.
        row_cat = ttk.Frame(box)
        row_cat.pack(fill="x", pady=(2, 0))
        self.lbl_cat_dossier = ttk.Label(row_cat, text="Catalogues : —",
                                         foreground="#888888", width=44,
                                         anchor="w")
        self.lbl_cat_dossier.pack(side="left")
        row_cat_b = ttk.Frame(box)
        row_cat_b.pack(fill="x", pady=(2, 0))
        ttk.Button(row_cat_b, text="📂 Dossier", width=12,
                   command=self._choisir_dossier_catalogues).pack(side="left",
                                                                  padx=(6, 0))
        self.btn_cat_dl = ttk.Button(row_cat_b, text="⬇ Gaia", width=9,
                                     command=self._telecharger_catalogue)
        self.btn_cat_dl.pack(side="left", padx=(4, 0))
        self.lbl_cat_etat = ttk.Label(box, text="", foreground="#888888",
                                      wraplength=310)
        self.lbl_cat_etat.pack(anchor="w")
        # Jalon 77 — LES DONNÉES DE LA SPCC SANS SIRIL. Mesure d'un besoin : il
        # manquait DEUX jeux de données (les 48 morceaux de spectres Gaia XP,
        # dont la fonction de téléchargement n'était branchée nulle part, et la
        # base de profils de capteurs/filtres, qui n'était LUE que chez Siril) :
        # sans eux, la SPCC exigeait Siril installé. Chacun a SA ligne, avec
        # DEUX boutons au plus (règle de mise en page v2.38.9 : `pack` abandonne
        # silencieusement le widget qui ne tient plus) et un état qui DIT ce qui
        # est présent — jamais de bouton muet.
        row_sp = ttk.Frame(box)
        row_sp.pack(fill="x", pady=(4, 0))
        self.btn_spectres = ttk.Button(row_sp, text="⬇ Spectres (champ)",
                                       width=17,
                                       command=self._telecharger_spectres)
        self.btn_spectres.pack(side="left", padx=(6, 0))
        self.btn_spectres_tous = ttk.Button(row_sp, text="⬇ les 48", width=9,
                                            command=self._telecharger_spectres_tous)
        self.btn_spectres_tous.pack(side="left", padx=(4, 0))
        row_sp2 = ttk.Frame(box)
        row_sp2.pack(fill="x", pady=(2, 0))
        self.btn_spcc_base = ttk.Button(row_sp2, text="⬇ Base SPCC", width=13,
                                        command=self._telecharger_base_spcc)
        self.btn_spcc_base.pack(side="left", padx=(6, 0))
        self.btn_spcc_dos = ttk.Button(row_sp2, text="📂 Dossier SPCC", width=15,
                                       command=self._choisir_dossier_spcc)
        self.btn_spcc_dos.pack(side="left", padx=(4, 0))
        self.lbl_base_spcc = ttk.Label(box, text="", foreground="#888888",
                                       wraplength=310)
        self.lbl_base_spcc.pack(anchor="w")
        # File de la conversation réseau → UI (le thread de téléchargement n'a
        # PAS le droit de toucher un widget : il ne pose que des messages ici).
        self._cat_q = queue.Queue()
        self._cat_dl_actif = False
        # v2.38.11 : la ligne « Catalogues » (dossier + présence du catalogue)
        # demande des `listdir`/`glob` sur des dossiers qui peuvent être sur un
        # NAS : plus de sonde ICI (avant l'affichage). Le fil de mesures la
        # remplit APRÈS l'ouverture, borné ; l'appel direct reste pour un geste
        # de l'utilisateur (bouton 📂, téléchargement terminé).
        # Jalon 56 (étape 4) : PHOTOMÉTRIE — zéro-point instrumental par BANDE,
        # mesuré sur l'empilement via le WCS (appariement mutuel des étoiles au
        # catalogue Gaia de Siril). Case SÉPARÉE et cochée par défaut : la
        # mesure n'a AUCUN effet sur l'image (l'application aux gains est
        # l'étape 5) — la décocher arrête simplement la mesure et son état.
        row_p = ttk.Frame(box)
        row_p.pack(fill="x", pady=(2, 0))
        self.var_photo = tk.BooleanVar(value=True)
        ttk.Checkbutton(row_p, text="Photométrie (zéro-point Gaia)",
                        variable=self.var_photo,
                        command=self._on_photo).pack(side="left")
        self.lbl_photo = ttk.Label(box, text="Photométrie : —",
                                   foreground="#888888", wraplength=310)
        self.lbl_photo.pack(anchor="w", pady=(2, 0))
        # Jalon 56 (étape 5) : APPLICATION des gains photométriques au
        # composite — case SÉPARÉE, DÉCOCHÉE PAR DÉFAUT (opt-in d'Alain) : la
        # mesure ci-dessus n'a aucun effet tant que celle-ci n'est pas cochée.
        # Elle n'agit qu'en COMPOSITION (un gain global en mono n'a pas de sens
        # et déréglerait VeraLux, qui travaille en valeurs absolues).
        row_pg = ttk.Frame(box)
        row_pg.pack(fill="x", pady=(2, 0))
        self.var_photo_gains = tk.BooleanVar(value=False)
        ttk.Checkbutton(row_pg, text="Gains photométriques (Gaia)",
                        variable=self.var_photo_gains,
                        command=self._on_photo_gains).pack(side="left")
        self.lbl_photo_gains = ttk.Label(box, text="", foreground="#888888")
        self.lbl_photo_gains.pack(anchor="w")
        # Jalon 58 : SPCC ABSOLUE « à la Siril » — case SÉPARÉE, DÉCOCHÉE PAR
        # DÉFAUT (opt-in, même choix qu'Alain pour les gains Gaia) : elle
        # remplace les gains Gaia par des coefficients calculés à partir des
        # SPECTRES Gaia et des PROFILS capteur/filtres de la base Siril. Sans
        # cette base (non installée), la case est désactivée et le dit — jamais
        # une valeur inventée.
        row_sx = ttk.Frame(box)
        row_sx.pack(fill="x", pady=(4, 0))
        # Jalon 77 : la base de profils peut vivre AILLEURS que chez Siril (copie
        # d'AVAStack téléchargée, dossier choisi) — et ce dossier peut être sur
        # un NAS. La lecture qui remplit les sélecteurs est donc BORNÉE
        # (v2.38.11 : aucune mesure de disque ne doit retenir l'ouverture) ; la
        # sonde différée `_sonder_spcc_base` corrige l'affichage quand elle a
        # répondu, et la fin d'un téléchargement relit tout.
        self._spcc_dispo, self._spcc_noms, _mesure = self._spcc_base_bornee()
        self.var_spcc = tk.BooleanVar(value=False)
        self.chk_spcc = ttk.Checkbutton(
            row_sx, text="SPCC (couleurs absolues)",
            variable=self.var_spcc, command=self._on_spcc)
        self.chk_spcc.pack(side="left")
        if not self._spcc_dispo:
            self.chk_spcc.state(["disabled"])
        self._spcc_vars = {}
        self._spcc_lbls = {}
        self._spcc_cbs = {}
        # v2.40.0 : TYPE de capteur — la SPCC n'est PAS réservée au mono
        # multi-bandes (constat d'Alain, 28/09/2026 : « la case SPCC dit que
        # c'est que pour du mono multibande, alors que SPCC fonctionne en
        # couleurs dans Siril — il faut juste lui dire que c'est un capteur
        # couleur et le choisir »). Ligne AJOUTÉE au-dessus des cinq autres :
        # aucune ligne ne disparaît (règle de mise en page v2.38.9).
        ligne_t = ttk.Frame(box)
        ligne_t.pack(fill="x")
        ttk.Label(ligne_t, text="Type de capteur :", width=19).pack(side="left")
        self.var_spcc_type = tk.StringVar(value=self.SPCC_TYPE_MONO)
        cbt = ttk.Combobox(ligne_t, textvariable=self.var_spcc_type,
                           state="readonly", width=26,
                           values=[self.SPCC_TYPE_MONO, self.SPCC_TYPE_OSC])
        cbt.pack(side="left", fill="x", expand=True)
        cbt.bind("<<ComboboxSelected>>", lambda e: self._on_spcc_type())
        for cle, etiquette, defaut, largeur in (
                ("capteur", "Capteur", "Sony IMX585", 26),
                ("fr", "Filtre R", "QHYCCD MiniCam8M Red", 26),
                ("fg", "Filtre G", "QHYCCD MiniCam8M Green", 26),
                ("fb", "Filtre B", "QHYCCD MiniCam8M Blue", 26),
                ("blanc", "Référence de blanc", "Average Spiral Galaxy", 30)):
            ligne = ttk.Frame(box)
            ligne.pack(fill="x")
            lbl = ttk.Label(ligne, text=f"{etiquette} :", width=19)
            lbl.pack(side="left")
            self._spcc_lbls[cle] = lbl
            valeurs = self._spcc_noms.get(
                {"capteur": "capteur", "fr": "filtres", "fg": "filtres",
                 "fb": "filtres", "blanc": "blancs"}[cle], [])
            v = tk.StringVar(value=defaut)
            cb = ttk.Combobox(ligne, textvariable=v, state="readonly",
                              width=largeur, values=valeurs or [defaut])
            cb.pack(side="left", fill="x", expand=True)
            cb.bind("<<ComboboxSelected>>", lambda e: self._on_spcc())
            if not valeurs:
                cb.state(["disabled"])
            self._spcc_vars[cle] = v
            self._spcc_cbs[cle] = cb
        self.lbl_spcc = ttk.Label(box, text="", foreground="#888888",
                                  wraplength=330, justify="left")
        self.lbl_spcc.pack(anchor="w")
        ttk.Label(box, text="Rejet kappa-sigma :").pack(anchor="w")
        self.var_kappa = tk.StringVar(value="3σ")
        cb = ttk.Combobox(box, textvariable=self.var_kappa, state="readonly", width=8,
                          values=["Off", "2σ", "3σ", "4σ", "5σ"])
        cb.pack(anchor="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_kappa())
        # Méthode de rejet : kappa-sigma séquentiel (rapide, historique) ou
        # Winsorized (adaptation live du Winsorized Sigma Clipping de
        # PixInsight) — médiane/MAD d'une fenêtre glissante de frames
        # alignées, robuste aux traînées de satellites/météores.
        ttk.Label(box, text="Méthode de rejet :").pack(anchor="w")
        self.var_rejet = tk.StringVar(value="kappa-sigma (rapide)")
        self.cb_rejet = ttk.Combobox(box, textvariable=self.var_rejet, state="readonly",
                                     width=24,
                                     values=["kappa-sigma (rapide)",
                                             "Winsorized (satellites)"])
        self.cb_rejet.pack(anchor="w")
        self.cb_rejet.bind("<<ComboboxSelected>>", lambda e: self._on_rejet())
        rowwin = ttk.Frame(box)
        rowwin.pack(fill="x", pady=2)
        ttk.Label(rowwin, text="Fenêtre de référence (frames) :").pack(side="left")
        self.var_fenetre = tk.StringVar(value=str(self.rejet_fenetre))
        self.cb_fenetre = ttk.Combobox(rowwin, textvariable=self.var_fenetre,
                                       state="disabled", width=3,
                                       values=["4", "6", "8", "12", "16"])
        self.cb_fenetre.pack(side="left", padx=4)
        self.cb_fenetre.bind("<<ComboboxSelected>>", lambda e: self._on_rejet())
        # Jalon 13 : équilibrage des canaux (auto) — les capteurs couleur ont
        # 2 sites verts sur 4 (matrice de Bayer) et une réponse spectrale
        # déséquilibrée : l'empilement brut domine dans le vert (constat réel
        # NGC7023). Gains LINÉAIRES par canal égalisant le FOND du ciel (la
        # couleur des objets est préservée) ; tout ce qui sort de
        # l'empilement est équilibré (affichage, histogramme, sauvegardes,
        # traitements externes).
        self.var_wb = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Équilibrage des canaux (auto)",
                        variable=self.var_wb, command=self._on_wb
                        ).pack(anchor="w", pady=(2, 0))
        self.var_wb_force = tk.DoubleVar(value=1.0)
        self._add_slider(box, "Force de l'équilibrage",
                         self.var_wb_force, 0.0, 1.0, 0.05, self._on_wb, "{:.2f}")
        # Jalon 54 : recalage colorimétrique « Linear Fit » — R et B alignés
        # sur le VERT par une droite Gain + Offset (mesurée sur le composite
        # linéaire, réf. = vert). Neutralise le masque coloré (fond bleu dans
        # les poussières de M31, constat réel d'Alain) qui surgit à
        # l'étirement quand les fonds des filtres diffèrent. Appliqué au
        # composite (visu ET sauvegardes — le fichier linéaire reste un
        # float32 simple). DÉCOCHÉE par défaut (décision d'Alain) ; le
        # libellé montre les gains/offsets MESURÉS (règle : le réglage relu
        # n'est pas le réglage appliqué — seul l'effet physique prouve).
        self.var_fit = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Recalage colorimétrique (Linear Fit)",
                        variable=self.var_fit,
                        command=self._on_linear_fit).pack(anchor="w")
        # Jalon 54b (retour du test réel d'Alain) : le GAIN fondé sur le
        # rapport des bruits amplifie halos/bruit du canal bleu d'une image
        # OSC déjà équilibrée → aspect flou/décalé à l'étirement. DÉFAUT =
        # OFFSET SEUL (le fond) ; le gain reste disponible (palettes
        # narrowband, équivalent du Linear Fit d'APP).
        self.FIT_METHODES = (("Offset seul (fond)", "offset"),
                             ("Gain + offset", "gain_offset"))
        row_fm = ttk.Frame(box)
        row_fm.pack(fill="x")
        ttk.Label(row_fm, text="Méthode :").pack(side="left")
        self.var_fit_methode = tk.StringVar(value="Offset seul (fond)")
        self.cb_fit_methode = ttk.Combobox(
            row_fm, textvariable=self.var_fit_methode, state="readonly",
            width=17, values=[lib for lib, _ in self.FIT_METHODES])
        self.cb_fit_methode.pack(side="left", padx=4)
        self.cb_fit_methode.bind("<<ComboboxSelected>>",
                                 lambda e: self._on_linear_fit())
        self.lbl_fit = ttk.Label(box, text="", foreground="#888888")
        self.lbl_fit.pack(anchor="w")
        self._on_linear_fit()
        # Jalon 17 : filtre anti-brutes TRÈS défocalisées — rejet d'office
        # (décision d'Alain), cette case le désactive (les frames passent
        # comme avant le jalon 17 ; le compteur de rejets reste affiché).
        self.var_rejeter_flou = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Rejeter les frames floues (auto)",
                        variable=self.var_rejeter_flou,
                        command=self._on_rejeter_flou).pack(anchor="w")

        # --- Affichage
        box = ttk.LabelFrame(left, text="Affichage (temps réel)", padding=6)
        box.pack(fill="x", pady=3)
        # Moteur d'étirement : STF intégré (défaut, inchangé) ou VeraLux
        # (moteur tiers, opt-in). Le calcul VeraLux part dans un thread
        # dédié côté DisplayProcessor : l'interface n'est jamais bloquée.
        rowm = self.rowm = ttk.Frame(box)
        rowm.pack(fill="x", pady=(0, 2))
        ttk.Label(rowm, text="Moteur d'étirement :").pack(side="left")
        self.var_moteur = tk.StringVar(value="STF")
        self.cb_moteur = ttk.Combobox(rowm, textvariable=self.var_moteur,
                                      state="readonly", width=9,
                                      values=["STF", "VeraLux"])
        self.cb_moteur.pack(side="left", padx=4)
        self.cb_moteur.bind("<<ComboboxSelected>>", lambda e: self._on_moteur())
        # Réglages propres au STF — regroupés pour être MASQUÉS en mode
        # VeraLux (sinon ils restent visibles et laissés « cochés », sans
        # aucun effet sur l'image : source de confusion).
        self.frm_stf = ttk.Frame(box)
        self.frm_stf.pack(fill="x")
        self.var_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.frm_stf, text="Auto-stretch STF (fond calé sur la cible)",
                        variable=self.var_auto, command=self._on_auto).pack(anchor="w")
        self.var_sigk = tk.DoubleVar(value=2.8)
        self._add_slider(self.frm_stf, "Coupure du bruit (k·σ sous le fond)",
                         self.var_sigk, 0.5, 5.0, 0.1,
                         lambda: (setattr(self.disp, "sigma_k", self.var_sigk.get()),
                                  self._refresh_preview()), "{:.1f}")
        self.var_target = tk.DoubleVar(value=0.25)
        self._add_slider(self.frm_stf, "Luminosité du fond du ciel",
                         self.var_target, 0.10, 0.45, 0.01,
                         self._on_target_auto, "{:.2f}")
        ttk.Separator(self.frm_stf).pack(fill="x", pady=4)
        ttk.Label(self.frm_stf, text="Manuel (si auto décoché) :").pack(anchor="w")
        self.var_black = tk.DoubleVar(value=0.0)
        self.var_white = tk.DoubleVar(value=1.0)
        self.scl_black = self._add_slider(self.frm_stf, "Black point", self.var_black, 0.0, 1.0, 0.005,
                                          lambda: (setattr(self.disp, "black", self.var_black.get()),
                                                   self._refresh_preview()), "{:.3f}")
        self.scl_white = self._add_slider(self.frm_stf, "White point", self.var_white, 0.0, 2.0, 0.005,
                                          lambda: (setattr(self.disp, "white", self.var_white.get()),
                                                                                                      self._refresh_preview()), "{:.3f}")
        # Gamma / saturation : COMMUNS aux deux moteurs (toujours visibles,
        # appliqués après l'étirement quel que soit le mode).
        # NON REDONDANT AVEC LA BARRE « MÉDIAN » de l'histogramme — décision
        # d'Alain, 28/09/2026 : « on laisse comme c'est, à savoir les deux ».
        # À NE PAS « NETTOYER » : la barre médian place le gris moyen PAR LA MTF
        # (MTF(m, m) = 0,5 : la valeur de la barre DEVIENT le gris moyen, c'est
        # elle qui découpe l'histogramme à l'écran), le gamma est une courbe de
        # PUISSANCE appliquée APRÈS l'étage de niveaux — deux courbes
        # différentes : à m = 0,25 la MTF envoie 0,5 sur 0,75, là où γ = 4
        # l'envoie sur 0,06.
        self.frm_communs = ttk.Frame(box)
        self.frm_communs.pack(fill="x")
        vg = tk.DoubleVar(value=1.0)
        self.var_gamma = vg
        # Jalon 79 — `hist=False` sur gamma ET saturation (même règle que les
        # barres de niveaux depuis le jalon 75) : les DEUX bandes de
        # l'histogramme sont calculées AVANT ces étages — bande « brut » =
        # source linéaire, bande « sortie » = sortie du moteur d'étirement —
        # donc un geste sur ces curseurs ne change AUCUNE des deux courbes.
        # Sans cela, chaque pixel de souris payait en plus les deux
        # histogrammes (34 ms mesurés sur l'aperçu couleur) pour un tracé
        # identique. Le moteur d'étirement lui-même n'est plus recalculé non
        # plus (mémoire `DisplayProcessor._moteur_stf`, même jalon).
        self._add_slider(self.frm_communs, "Gamma (les 2 moteurs)", vg, 0.2, 4.0, 0.05,
                         lambda: (setattr(self.disp, "gamma", vg.get()),
                                  self._refresh_preview(hist=False)), "{:.2f}")
        vs = tk.DoubleVar(value=1.0)
        self.var_saturation = vs
        self._add_slider(self.frm_communs, "Saturation (globale)", vs, 0.0, 3.0,
                         0.05,
                         lambda: (setattr(self.disp, "saturation", vs.get()),
                                  self._refresh_preview(hist=False)), "{:.2f}")
        # --- Jalon 75 : saturation PAR COULEUR (R/V/B), demande d'Alain du
        # 28/09/2026 (les colonnes de couleur du grand histogramme de SharpCap).
        # Précision VÉRIFIÉE dans la doc et chez l'auteur : chez SharpCap ces
        # colonnes sont une BALANCE DES CANAUX appliquée AVANT l'étirement
        # (« colour adjustments happen before the stretch ») — or cette
        # correction existe DÉJÀ chez nous, et à sa place photométrique (gains
        # SPCC/Gaia, équilibrage des canaux, Linear Fit) : la rejouer à
        # l'affichage la dupliquerait. Ici c'est donc une VRAIE saturation par
        # couleur : le secteur de TEINTE visé seulement (poids triangulaires
        # sur R/V/B, cf. display.saturation_canaux), après la saturation
        # globale, 1,00 = neutre. La 1re écriture (« c_c = Y + k_c·(c − Y) »)
        # a été REJETÉE après l'essai réel d'Alain : elle changeait le canal
        # partout, si bien que pousser « rouge » verdissait les pixels verts
        # (constat : « quand je pousse l'un, c'est l'autre couleur qui semble
        # se renforcer »).
        self.var_sat_r = tk.DoubleVar(value=1.0)
        self.var_sat_g = tk.DoubleVar(value=1.0)
        self.var_sat_b = tk.DoubleVar(value=1.0)
        for lib, var in (("Saturation rouge", self.var_sat_r),
                         ("Saturation verte", self.var_sat_g),
                         ("Saturation bleue", self.var_sat_b)):
            self._add_slider(self.frm_communs, lib, var, 0.0, 3.0, 0.05,
                             self._on_sat_canaux, "{:.2f}")

        # --- VeraLux (moteur tiers) — caché tant que « STF » est sélectionné
        self.frm_veralux = ttk.Frame(box)
        ttk.Label(self.frm_veralux, text="Résolution du logD :").pack(anchor="w")
        self.var_vl_mode_res = tk.StringVar(value="fond cible (auto)")
        # Jalon 3 : « fond cible (auto) » = le moteur résout lui-même le logD
        # pour amener le fond à la cible, à CHAQUE nouvel empilement (le
        # rythme des frames est le cooldown) ; « logD forcé » = déterministe
        # et réactif (curseur ou bouton 🔒).
        self.cb_vl_mode = ttk.Combobox(self.frm_veralux,
                                       textvariable=self.var_vl_mode_res,
                                       state="readonly", width=16,
                                       values=["fond cible (auto)", "logD forcé"])
        self.cb_vl_mode.pack(anchor="w")
        self.cb_vl_mode.bind("<<ComboboxSelected>>",
                             lambda e: self._on_vl_mode())
        self.var_vl_target = tk.DoubleVar(value=veralux_moteur.TARGET_BG_PAR_DEFAUT)
        self._add_slider(self.frm_veralux, "Luminosité du fond visée (VeraLux)",
                         self.var_vl_target, 0.10, 0.45, 0.01,
                         self._on_vl_target, "{:.2f}")
        self.var_vl_logd = tk.DoubleVar(value=veralux_moteur.LOG_D_PAR_DEFAUT)
        self.scl_vl_logd = self._add_slider(
            self.frm_veralux, "logD forcé",
            self.var_vl_logd, 0.0, 7.0, 0.05,
            lambda: (setattr(self.disp, "vl_log_d", self.var_vl_logd.get()),
                     self._refresh_preview()), "{:.2f}")
        self.btn_vl_lock = ttk.Button(self.frm_veralux,
                                      text="🔒 Verrouiller le logD résolu",
                                      command=self._on_vl_lock)
        self.btn_vl_lock.pack(anchor="w", pady=(2, 0))
        # Jalon 4 : GraXpert « live » — appliqué AVANT l'étirement VeraLux,
        # dans le thread solveur, à chaque nouvel empilement (opt-in). Le BXT
        # reste manuel (bouton ⚡ de la section Traitement externe).
        self.var_vl_graxpert = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_veralux,
                        text="GraXpert live (avant étirement)",
                        variable=self.var_vl_graxpert,
                        command=self._on_vl_graxpert).pack(anchor="w",
                                                           pady=(2, 0))
        # Jalon 9 (remis le 16/09/2026) : débruitage local AVANT l'étirement
        # — algorithmes rapides numpy/OpenCV (aucun subprocess), opère en
        # vue « empilement » uniquement (cf. _sync_vl_denoise_vue). Force en
        # 0..1 : seuil k-sigma (ondelettes) / h (NLM) auto-adaptés au bruit
        # réel de chaque empilement.
        rowdn = ttk.Frame(self.frm_veralux)
        rowdn.pack(fill="x", pady=(2, 0))
        self.var_vl_dn = tk.BooleanVar(value=False)
        ttk.Checkbutton(rowdn, text="Débruitage live (avant étirement)",
                        variable=self.var_vl_dn,
                        command=self._on_vl_denoise).pack(side="left")
        self.var_vl_dn_methode = tk.StringVar(value=self.VL_DN_LABELS["nlm"])
        self.cb_vl_dn_methode = ttk.Combobox(
            rowdn, textvariable=self.var_vl_dn_methode, state="readonly",
            width=15, values=[lib for _, lib in self.VL_DN_METHODES])
        self.cb_vl_dn_methode.pack(side="left", padx=(4, 0))
        self.cb_vl_dn_methode.bind("<<ComboboxSelected>>",
                                   lambda e: self._on_vl_denoise())
        self.var_vl_dn_force = tk.DoubleVar(value=0.5)
        self._add_slider(self.frm_veralux, "Force du débruitage (live)",
                         self.var_vl_dn_force, 0.0, 1.0, 0.05,
                         self._on_vl_denoise, "{:.2f}")
        # Jalon 22 (décision d'Alain) : SCNR + démagenta — APRÈS composition
        # (image COULEUR du composite) et JUSTE AVANT l'étirement ; no-op sur
        # un composite monochrome (Mono). Vue « empilement » uniquement (en
        # vue « traitée », l'image a déjà subi le traitement externe).
        # Jalon 41 (décision d'Alain) : les CASES couleur sont sorties du
        # cadre VeraLux (cadre « Couleur live » indépendant, plus bas) — la
        # chaîne couleur est appliquée par le solveur VeraLux ET par le
        # moteur STF/manuel (process(), testé au jalon 22). L'étiquette et le
        # curseur d'état des calculs sont sortis AUSSI (cadre « État des
        # calculs », visible dans les DEUX modes).

        # Jalon 5 : profil capteur du moteur VeraLux (réponse couleur du
        # capteur — Rec.709 par défaut). Fait partie de la clé des réglages :
        # changer de profil relance la résolution au prochain rendu.
        ttk.Label(self.frm_veralux, text="Profil capteur :").pack(anchor="w")
        self.var_vl_profil = tk.StringVar(value=veralux_moteur.PROFIL_PAR_DEFAUT)
        self.cb_vl_profil = ttk.Combobox(self.frm_veralux,
                                         textvariable=self.var_vl_profil,
                                         state="readonly",
                                         values=list(veralux_moteur.profils_disponibles()))
        self.cb_vl_profil.pack(anchor="w")
        self.cb_vl_profil.bind("<<ComboboxSelected>>",
                               lambda e: self._on_vl_profil())

        # --- v2.38.0 : RENDU PLEINE RÉSOLUTION pour l'écran (demande d'Alain,
        # 26/09/2026 : « sur l'écran, je veux pouvoir zoomer sur l'image pleine
        # résolution »). Coché : la chaîne d'affichage (GraXpert/débruitage/
        # netteté/couleurs/étirement) tourne sur l'empilement COMPLET — l'écran
        # montre alors EXACTEMENT ce que le fichier contiendra, et le zoom
        # recadre de VRAIS pixels au lieu de grossir l'aperçu 1600 px (mesuré au
        # jalon 66 : l'anneau de couleur des étoiles, invisible sur l'aperçu,
        # n'apparaît que dans les fichiers). Coût mesuré ×4,3 (~7-8 s par
        # recalcul complet contre ~1,7 s) : décoché par défaut.
        # v2.38.1 (demande d'Alain, 27/09/2026 : « ok pour le rendu pleine
        # résolution en vue traitée ») : l'option vaut pour les DEUX vues — en
        # vue « traitée » la source est le résultat du ⚡ traitement externe
        # (`proc_full`, déjà mémorisé pour les sauvegardes : aucune copie en
        # plus), cf. `_src_pleine_res`.
        self.var_vl_pleine_res = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_veralux,
                        text="Rendu pleine résolution (zoom fidèle)",
                        variable=self.var_vl_pleine_res,
                        command=self._on_vl_pleine_res).pack(anchor="w",
                                                             pady=(6, 0))
        ttk.Label(self.frm_veralux,
                  text="L'écran étire l'image COMPLÈTE — empilement, ou résultat "
                       "traité en vue « traitée » : le zoom montre de vrais "
                       "pixels, identiques au fichier enregistré. Plus lent "
                       "(~7-8 s par rendu, contre ~2 s pour l'aperçu).",
                  foreground="#888888", wraplength=310).pack(anchor="w")

        # --- Netteté live (jalon 12) : cadre INDÉPENDANT du moteur
        # d'étirement (demande d'Alain) — Richardson-Lucy s'applique AVANT
        # l'étirement, en STF/manuel comme en VeraLux. Position dans la
        # chaîne : après le débruitage (on lisse d'abord, on restaure
        # ensuite), avant l'étirement. PSF = seeing mesuré (jalon 10) ; la
        # netteté est calculée dans un thread dédié, jamais dans l'UI.
        self.frm_sharp = ttk.LabelFrame(left, text="Netteté live (Richardson-Lucy)",
                                        padding=6)
        self.frm_sharp.pack(fill="x", pady=3)
        self.var_vl_sharp = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_sharp, text="Netteté live (avant étirement)",
                        variable=self.var_vl_sharp,
                        command=self._on_vl_sharp).pack(anchor="w")
        self.var_vl_sharp_iter = tk.DoubleVar(
            value=float(nettete_live.ITERATIONS_DEFAUT))
        self.scl_sharp = self._add_slider(
            self.frm_sharp, "Itérations (3-5 = réglage utile)",
            self.var_vl_sharp_iter, 1.0,
            float(nettete_live.ITERATIONS_MAX), 1.0,
            self._on_vl_sharp, "{:.0f}")
        self.lbl_sharp = ttk.Label(self.frm_sharp, text="Netteté désactivée",
                                   foreground="#888888", wraplength=310)
        self.lbl_sharp.pack(anchor="w", pady=(2, 0))

        # --- Couleur live (jalon 41, décision d'Alain) : cadre INDÉPENDANT
        # du moteur d'étirement — SCNR / SCNR doux / démagenta sont appliqués
        # par le solveur VeraLux (jalons 22/23) ET par le moteur STF/manuel
        # (process(), testé au jalon 22). Jalon 22 (décision d'Alain) :
        # APRÈS composition (image COULEUR du composite) et JUSTE AVANT
        # l'étirement ; no-op sur un composite monochrome (Mono). Vue
        # « empilement » uniquement (en vue « traitée », l'image a déjà subi
        # le traitement externe).
        self.frm_couleur = ttk.LabelFrame(
            left, text="Couleur live (SCNR / démagenta)", padding=6)
        self.frm_couleur.pack(fill="x", pady=3)
        self.var_vl_scnr = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur, text="SCNR — retrait du vert (live)",
                        variable=self.var_vl_scnr,
                        command=self._on_vl_scnr).pack(anchor="w", pady=(2, 0))
        # Jalon 23 : SCNR doux borné par le bruit — ne retire que le
        # grésillement vert (excès de vert ≤ 3σ), préserve la structure
        # (nébuleuses) : pensé pour les palettes narrowband où le vert est
        # de la DONNÉE (HOO : O3 ; SHO sans S : Ha).
        self.var_vl_scnr_doux = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur,
                        text="SCNR doux — bruit seul (live)",
                        variable=self.var_vl_scnr_doux,
                        command=self._on_vl_scnr_doux).pack(anchor="w")
        self.var_vl_demagenta = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur,
                        text="Démagenta — négatif + SCNR (live)",
                        variable=self.var_vl_demagenta,
                        command=self._on_vl_demagenta).pack(anchor="w")
        # --- v2.36.1 : NEUTRALISATION DE LA COULEUR DU FOND avant étirement ---
        # Constat d'Alain (25/09/2026) : le fond restait bleu à l'écran (et le
        # PNG était franchement bleu, pour une autre raison : canaux permutés).
        # COCHÉE PAR DÉFAUT : ce n'est pas un choix esthétique mais la
        # correction d'un défaut de rendu (l'ancre de VeraLux transforme
        # quelques pour cent d'écart de ciel en facteur ~2,4 de couleur de
        # fond). Décocher = ancien rendu.
        self.var_vl_neutre = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.frm_couleur,
                        text="Neutraliser la couleur du fond (live)",
                        variable=self.var_vl_neutre,
                        command=self._on_vl_neutre).pack(anchor="w", pady=(4, 0))
        ttk.Label(self.frm_couleur,
                  text="Égalise les 3 canaux sur la MÉDIANE DE LA MOITIÉ SOMBRE "
                       "(gains ~2 %) juste avant l'étirement : l'ancre de "
                       "VeraLux transformait 2 % d'écart de ciel en un fond "
                       "bleu (mesuré R/G 0,36 · B/G 1,61 → 1,02 · 1,00).",
                  foreground="#888888", wraplength=310).pack(anchor="w")

        # --- v2.37.0 : RÉDUCTION DU BRUIT CHROMATIQUE (opt-in, DÉCOCHÉE par
        # défaut — choix d'Alain, 25/09/2026 : « oui pour la réduction de bruit
        # chromatique (j'allais te demander un équivalent de SCNR pour le bleu de
        # toute façon) et case décochée par défaut »). Justification MESURÉE sur
        # ses empilements M31 (41 et 115 frames) : le grain du fond est équilibré
        # en R/G (0,90) mais B/G reste à ~1,17 — la SPCC applique K_B/K_G = 1,32,
        # et un gain multiplicatif amplifie le bruit du canal qu'il monte. Elle
        # lisse la CHROMA (YCrCb) en laissant la LUMINANCE intacte : ni le niveau
        # ni le contraste du fond ne bougent, seulement le grain coloré.
        self.var_vl_chroma = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur,
                        text="Réduire le bruit chromatique (live)",
                        variable=self.var_vl_chroma,
                        command=self._on_vl_chroma).pack(anchor="w", pady=(4, 0))
        self.var_vl_chroma_force = tk.DoubleVar(value=0.5)
        self._add_slider(self.frm_couleur, "Force du bruit chromatique",
                         self.var_vl_chroma_force, 0.0, 1.0, 0.05,
                         self._on_vl_chroma, "{:.2f}")
        ttk.Label(self.frm_couleur,
                  text="Lisse la COULEUR du grain (YCrCb) sans toucher à la "
                       "luminance : un gain par canal (SPCC en tête) amplifie le "
                       "bruit du canal qu'il monte — mesuré : B/G 1,17 → ~1,00. "
                       "Force = part du bruit chromatique retirée.",
                  foreground="#888888", wraplength=310).pack(anchor="w")
        # --- v2.37.4 : RAYON DE RÉFÉRENCE du flou de chroma (demande d'Alain,
        # 26/09/2026 : « pour la visu live, mets à disposition le réglage du rayon
        # de référence pour pouvoir faire des tests »). Exprimé en pixels PLEINE
        # RÉSOLUTION : l'aperçu de l'appli le ramène à sa propre échelle
        # (`couleurs.rayon_chroma_apercu`) pour rester fidèle aux fichiers, et la
        # chaîne EXTERNE comme la sauvegarde « tel que vu » l'utilisent tel quel.
        self.var_vl_chroma_rayon = tk.DoubleVar(value=couleurs_mod.RAYON_CHROMA_DEFAUT)
        self._add_slider(self.frm_couleur, "Rayon de référence (px pleine rés.)",
                         self.var_vl_chroma_rayon, 0.5, 8.0, 0.25,
                         self._on_vl_chroma_rayon, "{:.2f}")
        ttk.Label(self.frm_couleur,
                  text="Rayon du flou qui lisse la couleur : plus grand = grain "
                       "coloré mieux retiré, mais couleur des étoiles plus "
                       "étalée (halo de couleur). L'aperçu applique ce rayon à "
                       "SON échelle, les fichiers à la pleine résolution — "
                       "l'écran reste fidèle au fichier.",
                  foreground="#888888", wraplength=310).pack(anchor="w")

        # --- État des calculs (jalons 40/41) : cadre INDÉPENDANT du moteur —
        # visible en VeraLux (étapes du solveur : ⏳ préparation/composition/
        # GraXpert/débruitage/netteté/étirement, puis résultat GX/DN/NET/COUL
        # · logD · fond) ET en STF/manuel (⏳ netteté pendant la déconvolution
        # du solveur dédié jalon 12). Un seul écrivain : _maj_lbl_vl (thread
        # UI, appelée par _tick).
        self.frm_etat = ttk.LabelFrame(left, text="État des calculs (live)",
                                       padding=6)
        self.frm_etat.pack(fill="x", pady=3)
        self.lbl_vl = ttk.Label(self.frm_etat, text="—",
                                foreground="#888888", wraplength=310)
        self.lbl_vl.pack(anchor="w")
        self.pb_vl = ttk.Progressbar(self.frm_etat, mode="indeterminate",
                                     length=220)

        # --- Traitement externe (long : plusieurs minutes — cf. docstring
        # de _run_external ; le « live » reste réservé aux étapes rapides)
        box = ttk.LabelFrame(left, text="Traitement externe (long)", padding=6)
        box.pack(fill="x", pady=3)
        # NB (v2.38.9) : la ligne « dossier de travail » et ses boutons étaient
        # ICI, en premières lignes du cadre. Constat d'Alain (27/09/2026) :
        # « pas de chemin pour temp et pas de bouton journal » — et la mesure lui
        # a donné raison sur les deux points : le bouton « Journal » n'était
        # JAMAIS affiché (`winfo_ismapped()=0`, cadre de 318 px trop étroit pour
        # trois boutons) et la ligne était sous le pli (y≈2421 px sur 3218 px de
        # colonne défilante). Ils vivent maintenant EN HAUT de la colonne, dans
        # le cadre « Fichiers de travail et journal » (cf. plus haut).
        self.var_ext_graxpert = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="1. GraXpert — retrait de gradient",
                        variable=self.var_ext_graxpert).pack(anchor="w")
        rowgx = ttk.Frame(box)
        rowgx.pack(fill="x")
        self.var_cmd_graxpert = tk.StringVar(value=DEFAULT_CMD_GRAXPERT)
        ttk.Entry(rowgx, textvariable=self.var_cmd_graxpert).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowgx, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_graxpert)
                   ).pack(side="left", padx=(4, 0))
        # v2.38.5 : état de la détection, TOUJOURS visible (chemin trouvé, ou
        # outil introuvable) — cf. _maj_etat_outils.
        self.lbl_etat_graxpert = ttk.Label(box, text="—", foreground="#888888",
                                           wraplength=310)
        self.lbl_etat_graxpert.pack(anchor="w")
        # Jalon 8 (remis le 16/09/2026) : débruitage du traitement externe —
        # méthode au choix : GraXpert IA (lent, subprocess) OU algorithmes
        # locaux rapides (ondelettes/NLM, en mémoire) ; force commune 0..1.
        # -strength (GraXpert) / k-sigma·h (local, auto-adaptés au bruit).
        rowd = ttk.Frame(box)
        rowd.pack(anchor="w")
        self.var_ext_dn = tk.BooleanVar(value=False)
        ttk.Checkbutton(rowd, text="2. Débruitage :",
                        variable=self.var_ext_dn).pack(side="left")
        self.var_dn_methode = tk.StringVar(
            value=self.DN_EXT_LABELS["graxpert"])
        self.cb_dn_methode = ttk.Combobox(
            rowd, textvariable=self.var_dn_methode, state="readonly",
            width=17, values=[lib for _, lib in self.DN_EXT_METHODES])
        self.cb_dn_methode.pack(side="left", padx=(4, 0))
        rowdn = ttk.Frame(box)
        rowdn.pack(fill="x")
        self.var_cmd_graxpert_dn = tk.StringVar(value=DEFAULT_CMD_GRAXPERT_DN)
        ttk.Entry(rowdn, textvariable=self.var_cmd_graxpert_dn).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowdn, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_graxpert_dn)
                   ).pack(side="left", padx=(4, 0))
        # v2.38.5 : même état que ci-dessus pour le débruitage GraXpert.
        self.lbl_etat_gx_dn = ttk.Label(box, text="—", foreground="#888888",
                                        wraplength=310)
        self.lbl_etat_gx_dn.pack(anchor="w")
        self.var_dn_force = tk.DoubleVar(value=0.5)
        self._add_slider(box, "Force du débruitage (0-1)", self.var_dn_force,
                         0.0, 1.0, 0.05, None, "{:.2f}")
        self.var_ext_bxt = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="3. BlurXTerminator — netteté",
                        variable=self.var_ext_bxt).pack(anchor="w")
        rowbx = ttk.Frame(box)
        rowbx.pack(fill="x")
        self.var_cmd_bxt = tk.StringVar(value=DEFAULT_CMD_BXT)
        ttk.Entry(rowbx, textvariable=self.var_cmd_bxt).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowbx, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_bxt)
                   ).pack(side="left", padx=(4, 0))
        # v2.38.5 : état de la détection pour BlurXTerminator (rc-astro).
        self.lbl_etat_bxt = ttk.Label(box, text="—", foreground="#888888",
                                      wraplength=310)
        self.lbl_etat_bxt.pack(anchor="w")
        # Un changement de commande (saisie, bouton « … », re-détection) met à
        # jour l'état affiché : c'est le seul retour dont dispose l'utilisateur.
        for _v in (self.var_cmd_graxpert, self.var_cmd_graxpert_dn,
                   self.var_cmd_bxt):
            _v.trace_add("write", self._maj_etat_outils)
        # Jalon 22/23 (décision d'Alain) : chaîne couleur en fin de traitement
        # externe — SCNR classique, puis SCNR doux (bruit seul, jalon 23 :
        # pensé pour les palettes narrowband), puis démagenta — sur l'image
        # COULEUR du résultat (no-op si mono), juste avant l'étirement
        # d'affichage. Équivalent des cases live du cadre VeraLux.
        self.var_ext_scnr = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="4. SCNR — retrait du vert",
                        variable=self.var_ext_scnr).pack(anchor="w")
        self.var_ext_scnr_doux = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="5. SCNR doux — bruit seul",
                        variable=self.var_ext_scnr_doux).pack(anchor="w")
        self.var_ext_demagenta = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="6. Démagenta (négatif + SCNR)",
                        variable=self.var_ext_demagenta).pack(anchor="w")
        # v2.37.1 — DEMANDE D'ALAIN (25/09/2026) : « intégrer les derniers ajouts
        # (SPCC, neutralisation, bruit chroma) dans la chaîne de traitement
        # externe pour que je puisse sortir une belle image à la fin du stack ».
        # La SPCC y était DÉJÀ (les corrections de couleur — gains effectifs
        # SPCC/Gaia/manuels, équilibrage, recalage « Linear Fit » — s'appliquent
        # au composite dans les deux chemins : `mean()` corrigé en mono,
        # `corrections_couleur` après recomposition en composition, cf.
        # _run_external_compo). Les DEUX corrections pré-étirement de la chaîne
        # live rejoignent donc la chaîne externe, au même rang qu'elle (… →
        # démagenta → neutralisation du fond → réduction du bruit chromatique,
        # juste avant l'étirement d'affichage) : c'est l'image que l'œil voit
        # sous l'ancre de VeraLux, et c'est elle que l'utilisateur exporte.
        self.var_ext_neutre = tk.BooleanVar(value=True)   # défaut COCHÉE, comme
                                                          # la case live (défaut
                                                          # de rendu, pas un
                                                          # choix esthétique)
        ttk.Checkbutton(box, text="7. Neutraliser la couleur du fond",
                        variable=self.var_ext_neutre).pack(anchor="w")
        self.var_ext_chroma = tk.BooleanVar(value=False)  # OPT-IN (choix d'Alain)
        ttk.Checkbutton(box,
                        text="8. Réduire le bruit chromatique (force = curseur "
                             "« Couleur live »)",
                        variable=self.var_ext_chroma).pack(anchor="w")
        ttk.Label(box, text="Placeholders : {input} · {output} (.fits complet) · "
                           "{outbase} (sans extension, GraXpert). « … » : choisir "
                           "l'exécutable, options conservées. Le débruitage "
                           "Ondelettes/NLM n'utilise aucune commande (traité "
                           "en mémoire).",
                  foreground="#888888", wraplength=310).pack(anchor="w")
        rowv = ttk.Frame(box)
        rowv.pack(fill="x", pady=2)
        self.var_view = tk.StringVar(value="pile")
        ttk.Radiobutton(rowv, text="Vue : empilement", variable=self.var_view, value="pile",
                        command=self._on_view).pack(side="left")
        ttk.Radiobutton(rowv, text="vue traitée", variable=self.var_view, value="traitée",
                        command=self._on_view).pack(side="left")
        self.btn_ext = ttk.Button(box, text="⚡ Traiter l'empilement courant",
                                  command=self._request_ext)
        self.btn_ext.pack(fill="x", pady=2)
        self.btn_save_proc = ttk.Button(box, text="💾 Enregistrer le résultat traité (linéaire)…",
                                        command=self._save_proc, state="disabled")
        self.btn_save_proc.pack(fill="x")
        self.lbl_ext = ttk.Label(box, text="—", foreground="#888888", wraplength=310)
        self.lbl_ext.pack(anchor="w")

        # --- Sortie
        box = ttk.LabelFrame(left, text="Sortie", padding=6)
        box.pack(fill="x", pady=3)
        ttk.Button(box, text="💾 Enregistrer l'empilement (linéaire)…",
                   command=self._save).pack(fill="x")
        # Chantier 24/09/2026 (décision (a) d'Alain) : 3e sortie LINÉAIRE —
        # « empilement TRAITÉ » = gradient retiré + débruitage + corrections de
        # couleur, SANS étirement (intermédiaire entre « brut » et « tel que
        # vu »). Bouton DÉDIÉ, distinct de « Enregistrer le résultat traité
        # (linéaire)… » du cadre « Traitement externe », qui reste lié au ⚡
        # manuel (GraXpert/BXT à la demande, sur un instantané).
        self.btn_save_traite_lin = ttk.Button(
            box, text="💾 Enregistrer l'empilement traité (linéaire)…",
            command=self._save_traite_lineaire)
        self.btn_save_traite_lin.pack(fill="x")
        # Jalon 5 : sauvegarde « tel que vu » — la vue courante rendue comme
        # à l'écran (étirement + gamma/saturation), en PLEINE résolution.
        # Les autres boutons d'enregistrement restent LINÉAIRES (inchangés).
        self.btn_save_asseen = ttk.Button(
            box, text="💾 Enregistrer tel que vu (étiré)…",
            command=self._save_asseen)
        self.btn_save_asseen.pack(fill="x")
        # Jalon 19 : en mode composition, un fichier par canal (rôle) —
        # l'empilement « standard » reste le COMPOSITE linéaire (bouton du haut).
        ttk.Button(box, text="💾 Enregistrer les canaux (par filtre)…",
                   command=self._save_canaux).pack(fill="x")

        # --- Panneau droit
        right = ttk.Frame(main)
        main.add(right, weight=1)
        self.cv_img = tk.Canvas(right, width=self.W_IMG, height=self.H_IMG,
                                bg="black", highlightthickness=0)
        self.cv_img.pack(fill="both", expand=True)
        # --- Jalon 75 : histogramme (2 bandes) + barres Noir/Médian/Blanc ----
        self.cv_hist = tk.Canvas(right, width=self.W_HIST,
                                 height=self._hauteur_hist(),
                                 bg="#101010", highlightthickness=0)
        self.cv_hist.pack(fill="x")
        self.cv_hist.bind("<Button-1>", self._hist_press)
        self.cv_hist.bind("<B1-Motion>", self._hist_drag_move)
        self.cv_hist.bind("<ButtonRelease-1>", self._hist_release)
        self.cv_hist.bind("<Double-Button-1>", self._hist_dblclick)
        self.cv_hist.bind("<Motion>", self._hist_survol)
        self._poser_panneau_hist(right)
        self.lbl_status = ttk.Label(right, text="Prêt. Choisissez une source puis cliquez Démarrer.\n"
                                               "Molette sur l'image : zoom · glisser : déplacer · "
                                               "double-clic : ajuster",
                                    anchor="w")
        self.lbl_status.pack(fill="x")

        # Zoom / pan sur l'image
        self.cv_img.bind("<MouseWheel>", self._on_wheel_zoom)   # Windows / macOS
        self.cv_img.bind("<Button-4>", self._on_wheel_zoom)    # Linux
        self.cv_img.bind("<Button-5>", self._on_wheel_zoom)
        self.cv_img.bind("<Button-1>", self._on_img_press)
        self.cv_img.bind("<B1-Motion>", self._on_img_drag)
        self.cv_img.bind("<ButtonRelease-1>", self._on_img_release)
        self.cv_img.bind("<Double-Button-1>", self._on_img_dblclick)
        self.cv_img.bind("<Configure>", lambda e: self._render())

        # Jalon 47 : état initial de la visibilité (source par défaut) —
        # _restaurer_config la réappliquera si la config change quelque chose.
        self._maj_visibilite_cadres()

    # --- Jalon 53 : dark/flat par couche (mode composition) ------------------

    def _source_est_compo(self):
        """True si la source choisie est la composition multi-dossiers —
        le ciblage dark/flat par rôle n'a de sens que là."""
        return self.var_source.get().startswith("Composition")

    def _roles_actifs(self):
        """Rôles remplis du cadre Composition (ordre des lignes, dédoublés)."""
        roles, vus = [], set()
        for v in self.var_compo_roles:
            r = v.get().strip()
            if r and r not in vus:
                vus.add(r)
                roles.append(r)
        return roles

    def _choisir_cible(self, famille):
        """Cible d'un chargement de master (`famille` = « dark »/« flat ») :
        → None si l'utilisateur annule ;
        → "unique" hors composition (pas de dialogue : aucun choix possible) ;
        → "unique" ou le rôle choisi via la boîte modale sinon.
        Jalon 53 (retour d'Alain pendant le test) : la couche se choisit AU
        MOMENT du clic sur « Charger un dark/flat… », pas par une sélection
        préalable dans un menu déroulant."""
        if not self._source_est_compo():
            return "unique"
        roles = self._roles_actifs()
        if not roles:
            return "unique"
        return self._dialogue_cible(famille, roles)

    def _dialogue_cible(self, famille, roles):
        """Boîte modale « ce dark/flat s'applique à : » — Unique + les
        rôles actifs de la composition. → None si annulé (croix, Annuler),
        sinon "unique" ou le rôle choisi. Thread UI seul (wait_window) ;
        widgets exposés (`_dlg_var`/`_dlg_ok`/`_dlg`) pour le test
        automatisé."""
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Charger un {famille}…")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        ttk.Label(dlg, text=f"Ce {famille} s'applique à :", padding=(10, 8)
                  ).pack(anchor="w")
        var = tk.StringVar(value="unique")
        ttk.Radiobutton(dlg, text="Unique (toutes les couches)",
                        value="unique", variable=var
                        ).pack(anchor="w", padx=14)
        for r in roles:
            ttk.Radiobutton(dlg, text=f"la couche « {r} »", value=r,
                            variable=var).pack(anchor="w", padx=14)
        choix = []

        def _valider():
            choix.append(var.get())
            dlg.destroy()

        row = ttk.Frame(dlg, padding=(10, 8))
        row.pack(fill="x")
        ttk.Button(row, text="OK", width=10, command=_valider
                   ).pack(side="left", expand=True, padx=3)
        ttk.Button(row, text="Annuler", width=10, command=dlg.destroy
                   ).pack(side="left", expand=True, padx=3)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.grab_set()
        self._dlg = dlg                     # exposés pour le test automatisé
        self._dlg_var = var
        self._dlg_ok = _valider
        try:
            self.root.wait_window(dlg)      # boucle locale : boîte modale
        finally:
            self._dlg = self._dlg_var = self._dlg_ok = None
        return choix[0] if choix else None

    def _maj_libelles_calib(self):
        """Détail COMPLET des masters chargés (jalon 53, retour d'Alain :
        « voir tous les darks chargés pour chaque couche et unique ») :
        l'unique PUIS chaque couche active de la composition (« — » si le
        master de cette couche manque). Vert dès qu'un master de la famille
        existe, gris sinon. Thread UI seul (événements Tk)."""
        # Garde-fou de construction : _on_compo est appelée par _build_ui
        # AVANT que le cadre Calibration (libellés) n'existe.
        if not hasattr(self, "lbl_dark"):
            return
        roles = self._roles_actifs() if self._source_est_compo() else []

        def _lignes(titre, img, source, dico, sources):
            if img is not None:
                h, w = img.shape[:2]
                nom = os.path.basename(source) if source else "?"
                lignes = [f"{titre} unique : {nom} ({h}×{w})"]
            else:
                lignes = [f"{titre} unique : —"]
            for r in roles:
                m = dico.get(r)
                if m is not None:
                    h, w = m.shape[:2]
                    nom = os.path.basename(sources.get(r) or "?")
                    lignes.append(f"{titre} {r} : {nom} ({h}×{w})")
                else:
                    lignes.append(f"{titre} {r} : —")
            return lignes

        ld = _lignes("Dark", self.calib.dark, self.calib.dark_source,
                     self.calib.darks, self.calib.darks_sources)
        lf = _lignes("Flat", self.calib.flat, self.calib.flat_source,
                     self.calib.flats, self.calib.flats_sources)
        coul_d = "#1d7f1d" if (self.calib.dark is not None
                               or self.calib.darks) else "#888888"
        coul_f = "#1d7f1d" if (self.calib.flat is not None
                               or self.calib.flats) else "#888888"
        self.lbl_dark.config(text="\n".join(ld), foreground=coul_d)
        self.lbl_flat.config(text="\n".join(lf), foreground=coul_f)

    def _add_slider(self, parent, label, var, frm, to, res, onchange=None,
                    fmt="{:g}", saisie=False):
        """Curseur + étiquette de valeur + boutons « - »/« + » (demande
        d'Alain, jalon 6) : réglage FIN sans devoir viser à la souris.
        Un clic = ±1 pas (res), aligné sur la grille du curseur ; clic
        MAINTENU = répétition (400 ms puis toutes les 80 ms) pour parcourir
        une grande plage sans cliquer 200 fois. Clamps aux bornes frm/to.
        saisie=True (jalon 27, demande d'Alain) : le label de valeur devient
        une ZONE DE SAISIE (nombre acceptant la virgule ; Return ou sortie
        de champ applique et borne ; le curseur suit)."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        head = ttk.Frame(row)
        head.pack(fill="x")
        ttk.Label(head, text=label).pack(side="left")
        var_txt = tk.StringVar(value=fmt.format(var.get()))
        if saisie:
            lab_val = ttk.Entry(head, textvariable=var_txt, width=8,
                                justify="right")
            lab_val.pack(side="right")

            def valider(_e=None):
                try:
                    v = float(var_txt.get().strip().replace(",", "."))
                except ValueError:
                    var_txt.set(fmt.format(var.get()))
                    return
                v = min(max(v, frm), to)
                v = frm + round((v - frm) / res) * res
                s.set(round(v, 6))   # rappelle cmd() → var + texte + onchange
                var_txt.set(fmt.format(var.get()))

            lab_val.bind("<Return>", valider)
            lab_val.bind("<FocusOut>", valider)
        else:
            lab_val = ttk.Label(head, text=fmt.format(var.get()))
            lab_val.pack(side="right")

        def cmd(v):
            var.set(float(v))
            if saisie:
                var_txt.set(fmt.format(float(v)))   # Entry (StringVar)
            else:
                lab_val.config(text=fmt.format(float(v)))
            if onchange:
                onchange()

        ligne = ttk.Frame(row)
        ligne.pack(fill="x")
        job = [None]                     # after() de la répétition en cours

        def pas(delta):
            v = var.get() + delta * res
            v = min(max(v, frm), to)                 # bornes
            v = frm + round((v - frm) / res) * res   # grille du curseur
            s.set(round(v, 6))   # s.set rappelle cmd() → var + label + onchange

        def repeter(delta):
            try:
                pas(delta)
                job[0] = ligne.after(80, lambda: repeter(delta))
            except tk.TclError:      # fenêtre détruite pendant l'appui
                job[0] = None

        def appui(delta):
            pas(delta)
            job[0] = ligne.after(400, lambda: repeter(delta))

        def relache(_e=None):
            if job[0] is not None:
                try:
                    ligne.after_cancel(job[0])
                except tk.TclError:
                    pass
                job[0] = None

        b_moins = ttk.Button(ligne, text="-", width=3, takefocus=False)
        b_moins.pack(side="left")
        s = ttk.Scale(ligne, from_=frm, to=to, value=var.get(), command=cmd)
        s.pack(side="left", fill="x", expand=True, padx=3)
        b_plus = ttk.Button(ligne, text="+", width=3, takefocus=False)
        b_plus.pack(side="left")
        for bouton, delta in ((b_moins, -1.0), (b_plus, 1.0)):
            bouton.bind("<ButtonPress-1>", lambda _e, d=delta: appui(d))
            bouton.bind("<ButtonRelease-1>", relache)
            bouton.bind("<Leave>", relache)
        s._pas = pas                 # accès pour les tests
        s._boutons = (b_moins, b_plus)
        s._row = row                 # reconstruction dynamique (jalon 31)
        s._lbl_txt = label           # texte d'origine (idem)
        return s

    # ------------------------------------------------------------ callbacks UI
    def _on_kappa(self):
        self.kappa = {"Off": None, "2σ": 2.0, "3σ": 3.0, "4σ": 4.0, "5σ": 5.0}[self.var_kappa.get()]
        if self.stacker:
            self.stacker.k = self.kappa

    def _on_rejet(self):
        """Bascule de la méthode de rejet (kappa-sigma / Winsorized) et de
        la taille de la fenêtre de référence. Appliqué à chaud au stacker
        (l'accumulation en cours est préservée, seule la fenêtre est vidée)."""
        self.rejet_methode = ("winsorized" if "Winsorized" in self.var_rejet.get()
                              else "kappa")
        try:
            self.rejet_fenetre = int(self.var_fenetre.get())
        except ValueError:
            self.rejet_fenetre = 8
        # La fenêtre glissante n'a de sens qu'en mode Winsorized : grisée sinon.
        self.cb_fenetre.configure(
            state="readonly" if self.rejet_methode == "winsorized" else "disabled")
        if self.stacker:
            self.stacker.set_rejet(method=self.rejet_methode,
                                   window=self.rejet_fenetre)

    def _on_ref_refresh(self):
        """Jalon 13 : fréquence (en frames) du rafraîchissement auto de la
        référence d'alignement ; « jamais » = 0 (ancien comportement)."""
        v = self.var_ref_refresh.get()
        try:
            self.ref_refresh = 0 if v == "jamais" else int(v)
        except ValueError:
            self.ref_refresh = 20
        self._ref_frames = self._ref_bad = 0

    def _on_wb(self):
        """Jalon 13 : équilibrage des canaux (auto) de l'empilement —
        répercuté sur l'empilement courant s'il existe."""
        if self.stacker:
            self.stacker.wb_auto = bool(self.var_wb.get())
            self.stacker.wb_force = float(self.var_wb_force.get())
        self._on_linear_fit()
        self._refresh_preview()

    def _code_fit_methode(self):
        """Libellé du menu « Méthode » → code interne du Linear Fit
        (thread principal uniquement ; le worker lit l'instantané)."""
        for lib, code in getattr(self, "FIT_METHODES", ()):
            if lib == self.var_fit_methode.get():
                return code
        return "offset"                        # inconnu → le plus doux

    def _on_astro(self):
        """Jalon 56 : case « Astrométrie » + indices de la cible (AD, Dec,
        champ) — relus dans le thread Tk et transmis au worker par INSTANTANÉ
        (`_astro_indices`) : le worker n'a JAMAIS le droit de lire les
        variables Tk. Ne touche QU'À L'ÉTAT (la ligne d'état suit ensuite par
        _update_status, qui l'affiche pour tous les états).

        Une saisie refusée (valeur illisible, champ hors bornes) est signalée
        TELLE QUELLE : rien n'est deviné, et le suivi reste sans indices —
        l'astrométrie ne se lancera pas sur une valeur à moitié comprise."""
        self._astro_actif = bool(self.var_astro.get())
        ra, dec, champ, msg = astro_mod.analyser_indices(
            self.var_astro_ra.get().strip(),
            self.var_astro_dec.get().strip(),
            self.var_astro_champ.get().strip())
        self._astro_msg_indices = msg
        self._astro_source = ""
        # Champ SEUL (indépendamment des coordonnées) : c'est lui qui guidera un
        # éventuel balayage ASTAP si les coordonnées manquent.
        self._astro_champ_seul, _ = astro_mod.analyser_champ(
            self.var_astro_champ.get().strip())
        if msg:
            self._astro_indices = None
        else:
            self._astro_indices = (ra, dec, champ)
            self._astro_source = "saisie"
            if self.suivi_astro is not None \
                    and self.suivi_astro.indice(ra, dec, champ):
                # Indices DIFFÉRENTS : le WCS déjà résolu ne décrit plus la
                # même cible/le même champ → oublié (indice() s'en charge) et
                # l'affichage repart de zéro.
                self.astro_info = ""
                self.astro_couleur = "#888888"
        if not self._astro_actif and self.suivi_astro is not None:
            self.suivi_astro.reset()
        self._rafraichir_rendu = True     # la ligne d'état suit SANS brute
        self._maj_astro_vue()
        # v2.38.11 : la ligne « Catalogues » demande des `listdir` sur des
        # dossiers qui peuvent être sur un NAS → sonde DIFFÉRÉE et bornée.
        # POURQUOI ICI PRÉCISÉMENT : `_on_astro` est appelée par
        # `_restaurer_config`, donc AVANT l'affichage ; mesuré au faulthandler le
        # 27/09/2026, cette sonde synchrone faisait attendre le MONTAGE NAS et
        # l'application ne s'ouvrait pas (30 s de blocage observés sur la sonde
        # simulée du banc jalon 74).
        self._demander_mesures()

    def _spcc_osc(self):
        """Le TYPE choisi désigne-t-il un capteur COULEUR (OSC) ?"""
        try:
            return self.var_spcc_type.get() == self.SPCC_TYPE_OSC
        except Exception:
            return False

    @staticmethod
    def _spcc_defaut(cle, liste, osc):
        """Valeur posée quand la liste des profils change.

        En OSC, JAMAIS un filtre « au hasard » : le premier nom de la liste est
        un VRAI LPF (« Antlia Quad Band Anti-Light Pollution Filter »…) et
        l'appliquer en silence à une brute sans filtre fausserait toute la
        couleur — on préfère donc la référence « sans filtre » de la base
        (« No filter », « Full spectrum (no filter) »), et seulement à défaut le
        premier nom. Pour les capteurs, rien à choisir : « Sony IMX585 » est
        dans les deux listes, la sélection suit le type (v2.40.0)."""
        if osc and cle == "fr":
            for n in liste:                     # la référence elle-même d'abord
                if str(n).strip().lower() in ("no filter", "sans filtre"):
                    return n
            for n in liste:
                b = str(n).lower()
                if "no filter" in b or "sans filtre" in b or "full spectrum" in b:
                    return n
        return liste[0] if liste else ""

    def _on_spcc_type(self):
        """Jalon 58 bis : le type de capteur change (mono ↔ couleur OSC).

        Les listes déroulantes suivent (capteurs, filtres) et — en OSC — c'est
        UN SEUL filtre qui couvre les trois bandes : les lignes « Filtre G » et
        « Filtre B » RESTENT (règle de mise en page v2.38.9 : on ne retire pas
        de ligne, le pack abandonnerait silencieusement ce qui suit), mais elles
        sont grisées et leur libellé le dit. Toute mesure en cours est
        invalidée : des coefficients calculés pour d'autres bandes seraient
        faux."""
        osc = self._spcc_osc()
        noms = getattr(self, "_spcc_noms", {}) or {}
        vars_, cbs = getattr(self, "_spcc_vars", {}), getattr(self, "_spcc_cbs", {})
        if not vars_ or not cbs:
            return
        for cle, categorie, cle_noms in (("capteur", "capteur", "osc_capteurs"),
                                         ("fr", "filtres", "osc_filtres")):
            liste = ((noms.get(cle_noms) if osc else noms.get(categorie)) or [""])
            cbs[cle].config(values=liste)
            cbs[cle].state(["!disabled"])
            if vars_[cle].get() not in liste:
                vars_[cle].set(self._spcc_defaut(cle, liste, osc))
        for cle, b in (("fg", "G"), ("fb", "B")):
            self._spcc_lbls[cle].config(
                text=("Filtre (OSC) :" if osc else f"Filtre {b} :"))
            if osc:
                vars_[cle].set(vars_["fr"].get())
                cbs[cle].state(["disabled"])
            else:
                cbs[cle].state(["!disabled"])
                if not noms.get("filtres"):
                    cbs[cle].state(["disabled"])
        self._spcc_lbls["fr"].config(
            text=("Filtre (OSC) :" if osc else "Filtre R :"))
        self._spcc_lbls["capteur"].config(
            text=("Capteur OSC :" if osc else "Capteur :"))
        self._on_spcc()          # invalide la mesure et remet la vue à jour

    def _on_spcc(self):
        """Jalon 58 : case « SPCC (couleurs absolues) » — OPT-IN, décochée par
        défaut comme celle des gains Gaia. Cochée, elle fait ÉCRIRE dans le
        composite les coefficients spectrophotométriques (calculés par le
        worker sur l'empilement courant) À LA PLACE des gains Gaia relatifs ;
        décochée, elle remet tout à zéro et le dit. Changer un profil
        (capteur/filtre/blanc) invalide la mesure : un coefficient calculé pour
        d'autres bandes serait faux."""
        self._spcc_actif = bool(self.var_spcc.get())
        self._spcc_demande = self._spcc_actif     # v2.37.0 : mesure à (re)faire
        if not self._spcc_actif:
            if self.spcc is not None:
                self.spcc.reset()
            self.spcc_info = "SPCC : désactivée"
            self.spcc_couleur = "#888888"
        else:
            self.spcc_info = "SPCC : mesure demandée…"
            self.spcc_couleur = "#c98a00"
            self._spcc_essais = 0        # nouvelle mesure autorisée
            self._spcc_dernier = 0.0
            if self.spcc is not None and self.spcc.valide:
                self._maj_spcc_etat()
        self._rafraichir_rendu = True
        self._maj_spcc_vue()

    def _spcc_profils(self):
        """Profils choisis dans l'UI → (capteur, {"R","G","B"}, blanc)."""
        v = getattr(self, "_spcc_vars", {})
        try:
            return (v["capteur"].get(), {"R": v["fr"].get(), "G": v["fg"].get(),
                                         "B": v["fb"].get()}, v["blanc"].get())
        except Exception:
            return "", {}, ""

    def _maj_spcc_vue(self):
        """Libellé sous la case SPCC : dit ce qui est appliqué, ou pourquoi
        rien ne l'est — jamais muet quand la case est cochée."""
        if getattr(self, "lbl_spcc", None) is None:
            return
        if not self._spcc_actif:
            self.lbl_spcc.config(text="", foreground="#888888")
            return
        if not self._spcc_dispo:
            self.lbl_spcc.config(
                text=("SPCC : base de profils (capteurs/filtres) introuvable — "
                      "le bouton « ⬇ Base SPCC » la télécharge (quelques Mo), "
                      "ou « 📂 Dossier SPCC » désigne une base existante"),
                foreground="#c98a00")
            return
        if not (self._mode_compo or self._source_rgb(getattr(self, "stacker", None))):
            # v2.37.1 : au LANCEMENT, aucune source n'est encore choisie —
            # annoncer « sans effet en MONO » était FAUX (constat d'Alain du
            # 25/09/2026 : il rouvre l'appli, ses profils sont bons, la case est
            # cochée, et le libellé lui dit que ça ne sert à rien alors que
            # l'appli ne SAIT PAS encore ce que sera la source).
            # v2.40.0 : la SPCC n'est PLUS réservée à la composition R/G/B —
            # une source COULEUR (capteur OSC) suffit, comme dans Siril.
            besoin = ("il faut une image COULEUR (capteur OSC) ou une "
                      "composition multi-dossiers R/G/B")
            if self.camera is None:
                self.lbl_spcc.config(
                    text=f"SPCC : en attente de la source ({besoin})",
                    foreground="#c98a00")
                return
            self.lbl_spcc.config(
                text=f"SPCC : sans effet sur cette source ({besoin})",
                foreground="#c98a00")
            return
        # Contrôle IMMÉDIAT des profils choisis (constat réel : « Filtre R =
        # … Luminance ») : un profil de luminance ou deux filtres identiques
        # donneraient des coefficients faux — on le dit AVANT toute mesure.
        # En OSC, c'est `coherence_osc` qui juge (UN filtre couvre les trois
        # bandes : exiger trois filtres distincts n'aurait aucun sens).
        _, filtres, _ = self._spcc_profils()
        if self._spcc_osc():
            avis = spcc_mod.coherence_osc(
                self._spcc_vars["capteur"].get(),
                filtres.get("R"))
        else:
            avis = spcc_mod.coherence_bandes([filtres.get("R"),
                                              filtres.get("G"),
                                              filtres.get("B")])
        if avis:
            self.lbl_spcc.config(text="SPCC : ⚠ " + " ; ".join(avis),
                                 foreground="#d04040")
            return
        if self.spcc is not None and self.spcc.valide:
            txt = self.spcc.texte_resume()
            self.spcc_info = txt
            self.spcc_couleur = ("#c98a00" if self.spcc.diag.get("avertissement")
                                 else "#1d7f1d")
            self.lbl_spcc.config(text=txt, foreground=self.spcc_couleur)
            self._maj_photo_gains_vue()    # dit que les gains Gaia sont remplacés
            return
        self.lbl_spcc.config(text="SPCC : en attente de la mesure",
                             foreground="#c98a00")

    def _maj_spcc_etat(self):
        """Recopie la mesure SPCC dans la ligne dédiée (si le texte change)."""
        if self.spcc is None:
            return
        txt = self.spcc.texte_resume()
        if txt and txt != self.spcc_info:
            self.spcc_info = txt
        if self.spcc.valide:
            self.spcc_couleur = ("#c98a00" if self.spcc.diag.get("avertissement")
                                 else "#1d7f1d")

    def _on_photo_gains(self):
        """Jalon 56 (étape 5) : case « Gains photométriques (Gaia) » — OPT-IN
        (décochée par défaut, choix d'Alain du 23/09/2026). C'est le SEUL
        réglage qui écrit les facteurs mesurés dans le stacker, donc qui change
        l'image : cochée SANS mesure, elle n'applique rien et l'annonce."""
        self._photo_gains_actif = bool(self.var_photo_gains.get())
        self._rafraichir_rendu = True
        self._maj_photo_vue()

    def _maj_photo_gains_vue(self):
        """Libellé SOUS la case des gains : dit ce qui est appliqué (ou
        pourquoi rien ne l'est) — jamais muet quand la case est cochée."""
        if getattr(self, "lbl_photo_gains", None) is None:
            return
        if not self._photo_gains_actif:
            self.lbl_photo_gains.config(text="", foreground="#888888")
            return
        if not self._mode_compo:
            self.lbl_photo_gains.config(
                text=("Gains photométriques : sans effet en MONO (un gain "
                      "global ne se voit pas et déréglerait VeraLux)"),
                foreground="#c98a00")
            return
        if self.photometrie is None or not self.photometrie.valide:
            self.lbl_photo_gains.config(
                text="Gains photométriques : en attente de la mesure",
                foreground="#c98a00")
            return
        gains = ", ".join(f"{b} ×{g:.4f}"
                          for b, g in sorted(self.photometrie.gains.items()))
        # Jalon 58 : si la SPCC est active, ce sont SES coefficients qui sont
        # écrits (elle prime) — le dire évite de croire à une double correction.
        if self._spcc_actif and self.spcc is not None and self.spcc.valide:
            self.lbl_photo_gains.config(
                text=(f"Gains photométriques (Gaia) mesurés : {gains} — "
                      "REMPLACÉS par la SPCC (couleurs absolues)"),
                foreground="#c98a00")
            return
        self.lbl_photo_gains.config(
            text=f"Gains photométriques appliqués : {gains}",
            foreground="#1d7f1d")

    def _on_photo(self):
        """Jalon 56 (étape 4) : case « Photométrie » — instantané pour le
        worker (jamais de lecture Tk hors du thread principal). Décocher remet
        la mesure à zéro et l'ANNONCE ; recocher relance une mesure (le worker
        la tentera au prochain tour, sur l'empilement courant)."""
        self._photo_actif = bool(self.var_photo.get())
        self._photo_demande = self._photo_actif   # v2.37.0 : mesure à (re)faire
        if not self._photo_actif:
            if self.photometrie is not None:
                self.photometrie.reset()
            self.photo_info = "Photométrie : désactivée"
            self.photo_couleur = "#888888"
        else:
            # Recochée : la mesure repart de zéro (le worker la retentera — au
            # prochain tour, et MÊME sans nouvelle frame en fin de stack :
            # cf. _servir_demandes_sans_frame — aucun zéro-point d'une session
            # révolue ne doit rester affiché).
            self.photo_info = "Photométrie : mesure demandée…"
            self.photo_couleur = "#c98a00"
        self._rafraichir_rendu = True
        self._maj_photo_vue()

    def _maj_photo_vue(self):
        """Affiche l'état de la photométrie CONNU CÔTÉ UI : soit la mesure
        (zéro-points par bande), soit la RAISON de son absence — jamais muet."""
        if getattr(self, "lbl_photo", None) is None:
            return
        if not self._photo_actif:
            txt, col = "Photométrie : désactivée", "#888888"
        elif self.photo_info:
            txt, col = self.photo_info, self.photo_couleur
        elif self.suivi_astro is None or not self.suivi_astro.resolu:
            txt = "Photométrie : en attente de l'astrométrie (WCS)"
            col = "#c98a00"
        else:
            txt, col = ("Photométrie : en attente d'un empilement "
                        "suffisant"), "#888888"
        self.lbl_photo.config(text=txt, foreground=col)
        self._maj_photo_gains_vue()      # le libellé des gains suit l'état

    def _maj_astro_vue(self):
        """Affiche l'état de l'astrométrie CONNU CÔTÉ UI (avant toute
        tentative) : la ligne reflète la saisie ; la mesure (étoiles, rms,
        ″/px, chemin du solveur) arrive ensuite du worker par `astro_info`.
        Jamais de ligne muette : soit une mesure, soit la raison de son
        absence."""
        if getattr(self, "lbl_astro", None) is None:
            return
        if not self._astro_actif:
            txt, col = "Astrométrie : désactivée", "#888888"
        elif self._astro_msg_indices:
            txt = f"Astrométrie : indices refusés — {self._astro_msg_indices}"
            col = "#c98a00"
        elif self.astro_info:
            txt, col = self.astro_info, self.astro_couleur
        elif self._astro_indices:
            txt = ("Astrométrie : indices posés (%s) — résolution au 1er "
                   "empilement" % (self._astro_source or "saisie"))
            col = "#888888"
        else:
            txt, col = "Astrométrie : en attente d'indices", "#c98a00"
        self.lbl_astro.config(text=txt, foreground=col)

    def _sonder_catalogues(self):
        """SONDE le dossier des catalogues (accès disque) → `(dossier, état, err)`.

        Séparée de l'affichage (v2.38.11) : elle fait des `listdir`/`glob` sur des
        dossiers qui peuvent être sur un NAS — donc potentiellement bloqués — et
        doit pouvoir tourner HORS du fil d'interface, bornée.
        → `("", None, message)` si la sonde échoue : l'affichage le dit."""
        try:
            d = cat_mod.dossier_catalogues()
        except Exception as exc:                     # dossier illisible
            return ("", None, str(exc))
        try:
            return (d, cat_mod.etat_local(d), "")
        except Exception as exc:
            return (d, None, str(exc))

    def _maj_cat_vue(self):
        """Ligne « Catalogues » (jalon 70) : dossier RÉELLEMENT utilisé par
        l'application, présence du catalogue astrométrique, nombre de chunks
        spectro (informatif : la SPCC et la photométrie s'en servent). Jamais de
        ligne muette — c'est ce silence qui a coûté la soirée du 27/09/2026.

        v2.38.11 : sonde ET affiche — appelée par un GESTE de l'utilisateur (📂,
        fin de téléchargement) ; au démarrage, la sonde est différée et bornée."""
        d, etat, err = self._sonder_catalogues()
        self._appliquer_cat_vue(d, etat, err)

    def _appliquer_cat_vue(self, d, etat, err=""):
        """Affiche la ligne « Catalogues » (fil d'interface).

        `d` vide (ou `etat` None) = sonde NON aboutie : on le DIT au lieu de
        laisser un ancien texte (accès disque bloqué — montage réseau NAS ?)."""
        if getattr(self, "lbl_cat_dossier", None) is None:
            return
        if not d:
            self.lbl_cat_dossier.config(
                text="Catalogues : NON MESURÉ — un accès disque bloque "
                     "(montage réseau NAS ?)", foreground="#d04040")
            self.lbl_cat_etat.config(
                text=f"catalogues : inspection impossible ({err or 'délai dépassé'}) "
                     "— montage réseau NAS injoignable, ou pare-feu ?",
                foreground="#d04040")
            return
        # v2.38.10 : texte BORNÉ (44 caractères : la largeur du libellé) et
        # préfixe DANS le texte. POURQUOI : un chemin n'a pas d'espace, donc
        # `wraplength` ne le replie PAS — un libellé insécable trop long mange
        # la ligne où il vit (mesuré : avec `~/.local/share/siril`, les boutons
        # 📂 et ⬇ Gaia étaient abandonnés par `pack`). La QUEUE du chemin est
        # conservée : c'est elle qui nomme le dossier.
        self.lbl_cat_dossier.config(
            text="Catalogues : " + (d if len(d) <= 30 else "…" + d[-29:]),
            foreground="#888888")
        if self._cat_dl_actif:
            return                     # la ligne de progression fait foi
        if etat is None:
            self.lbl_cat_etat.config(
                text=f"catalogues : état NON MESURÉ ({err or 'délai dépassé'}) "
                     "— accès disque bloqué ?", foreground="#c98a00")
            return
        astro = etat.get("astro")
        n_ch = len(etat.get("chunks") or {})
        if astro:
            txt = f"catalogue astro : présent ({os.path.basename(astro)})"
            col = "#1d7f1d"
        else:
            txt = ("catalogue astro : ABSENT — l'astrométrie interne ne peut "
                   "pas aboutir (bouton ⬇ Gaia, ou déposer le fichier ici)")
            col = "#c98a00"
        self.lbl_cat_etat.config(
            text=f"{txt} — spectres Gaia : {n_ch}/{cat_mod.TOTAL_CHUNKS} morceaux",
            foreground=col)

    # ----------------------------------------------------------------- base SPCC
    def _spcc_base_bornee(self):
        """Lecture de la base SPCC pour construire les sélecteurs (jalon 58),
        BORNÉE (v2.38.11) → (dispo, noms, mesuré).

        `mesuré` = False quand le délai a été dépassé : l'affichage le dit et la
        sonde différée tranchera, au lieu de faire croire à une base absente."""
        vide = {"capteur": [], "filtres": [], "blancs": [],
                "osc_capteurs": [], "osc_filtres": []}

        def _lire():
            return (bool(spcc_mod.base_presente()), spcc_mod.noms_base(), True)

        dispo, noms, mesure = delais.borne(_lire, (False, vide, False),
                                           delais.DELAI_DEFAUT)[0] \
            or (False, vide, False)
        return bool(dispo), (noms or vide), bool(mesure)

    def _sonder_spcc_base(self):
        """SONDE la base de profils SPCC (accès disque) → (dossier, noms, dispo).
        Séparée de l'affichage pour tourner HORS du fil d'interface, bornée
        comme les autres sondes de disque."""
        try:
            base = cat_mod.spcc_db.dossier_base()
            return (base or "", spcc_mod.noms_base(), bool(spcc_mod.base_presente()))
        except Exception:
            return ("", None, False)

    def _maj_base_spcc_vue(self):
        """Sonde ET affiche (geste de l'utilisateur : fin de téléchargement)."""
        self._appliquer_spcc_base_vue(*self._sonder_spcc_base())

    def _appliquer_spcc_base_vue(self, dossier, noms, dispo):
        """Ligne « Base SPCC » + SÉLECTEURS de la SPCC : dit où sont les profils
        et ce qu'ils contiennent, et (re)remplit les listes.

        RENFORT MESURÉ (jalon 77) : une base arrivée APRÈS le démarrage (elle
        vient d'être téléchargée) doit rendre sa case cochable et ses listes
        utilisables SANS redémarrer l'application — sinon le téléchargement
        n'aurait servi à rien dans la session où on le fait."""
        if getattr(self, "lbl_base_spcc", None) is not None:
            if not dossier:
                self.lbl_base_spcc.config(
                    text=("Base SPCC : ABSENTE — la SPCC ne peut pas aboutir "
                          "(⬇ Base SPCC la télécharge, quelques Mo)"),
                    foreground="#c98a00")
            else:
                court = dossier if len(dossier) <= 30 else "…" + dossier[-29:]
                n = cat_mod.etat_base_spcc(dossier)
                detail = ", ".join(f"{k.split('_')[0]} {v}"
                                   for k, v in n.items() if v)
                self.lbl_base_spcc.config(
                    text=(f"Base SPCC : {court} — {detail}"
                          if detail else f"Base SPCC : {court} — vide"),
                    foreground="#1d7f1d" if dispo else "#c98a00")
        nouveau = bool(dispo) and not self._spcc_dispo
        if dispo:
            self._spcc_dispo = True
            self.chk_spcc.state(["!disabled"])
        elif not noms:
            self._spcc_dispo = False
        if noms:
            self._spcc_noms = noms
            # Peuplement des cinq listes, puis application du TYPE choisi (qui
            # pose les valeurs par défaut et remet la vue à jour).
            for cle, cle_noms in (("capteur", "osc_capteurs"),
                                  ("fr", "osc_filtres"),
                                  ("fg", "filtres"),
                                  ("fb", "filtres"),
                                  ("blanc", "blancs")):
                cb = self._spcc_cbs.get(cle)
                valeurs = self._spcc_noms.get(cle_noms) or []
                if cb is None or not valeurs:
                    continue
                cb.config(values=valeurs)
        if nouveau:
            self._on_spcc_type()
        else:
            self._maj_spcc_vue()

    # --------------------------------------------- téléchargements (réseau)
    def _boutons_dl(self):
        """Les boutons de TÉLÉCHARGEMENT : un SEUL transfert à la fois, donc
        tous neutralisés ensemble puis rendus ensemble (un bouton qui resterait
        gris, ou actif pendant un transfert, mentirait sur l'état réel)."""
        return [b for b in (getattr(self, "btn_cat_dl", None),
                            getattr(self, "btn_spectres", None),
                            getattr(self, "btn_spectres_tous", None),
                            getattr(self, "btn_spcc_base", None))
                if b is not None]

    def _regler_boutons_dl(self, actif):
        for b in self._boutons_dl():
            b.state(["disabled"] if actif else ["!disabled"])

    def _lancer_telechargement(self, quoi, dossier, fonction, quoi_texte,
                               fin_texte):
        """Lance un transfert dans un THREAD dédié, suivi par la file `_cat_q`
        (le fil réseau ne touche JAMAIS un widget).

        `quoi` : « spectres » ou « spcc » — l'astrométrie garde son chemin
        historique `_telecharger_catalogue`. `fonction(dossier, progression)`
        fait le travail ; `quoi_texte` nomme le transfert (affiché pendant) ;
        `fin_texte(resultat)` compose la phrase finale — appelé DANS LE FIL
        RÉSEAU, donc sans le moindre accès à un widget."""
        if self._cat_dl_actif:
            return
        try:
            os.makedirs(dossier, exist_ok=True)
        except OSError as exc:
            self.lbl_cat_etat.config(text=f"téléchargement impossible : {exc}",
                                     foreground="#d04040")
            return
        self._cat_dl_actif = True
        self._regler_boutons_dl(True)
        self.lbl_cat_etat.config(text=f"téléchargement {quoi_texte}…",
                                 foreground="#c98a00")

        def travail():
            try:
                res = fonction(dossier, lambda nom, frac: self._cat_q.put(
                    ("progres", nom, float(frac), quoi)))
                self._cat_q.put(("fini", fin_texte(res), quoi))
            except Exception as exc:          # réseau, disque, sha256…
                self._cat_q.put(("erreur", str(exc), quoi))

        threading.Thread(target=travail, daemon=True).start()

    def _champ_spectres(self):
        """Champ visé pour les spectres : les TROIS indices de la cible, tels
        qu'ils sont SAISIS (mêmes règles que l'astrométrie : rien n'est deviné).
        → (ra, dec, rayon_deg, message) ; rayon = demi-diagonale MAJORÉE
        (0,8 × champ) pour couvrir un capteur non carré et l'orientation — la
        sélection ajoute déjà une marge d'un pixel."""
        ra, dec, champ, msg = astro_mod.analyser_indices(
            self.var_astro_ra.get().strip(),
            self.var_astro_dec.get().strip(),
            self.var_astro_champ.get().strip())
        if msg:
            return None, None, None, msg
        return ra, dec, 0.8 * float(champ), ""

    def _telecharger_spectres(self):
        """⬇ Spectres (champ) : seulement les morceaux du catalogue Gaia XP qui
        couvrent le champ visé (100–300 Mo au lieu de 10,6 Go)."""
        ra, dec, rayon, msg = self._champ_spectres()
        if msg:
            self.lbl_cat_etat.config(
                text=("spectres : AD/Dec/champ nécessaires pour ne prendre que "
                      f"les morceaux du champ ({msg}) — ou « ⬇ les 48 » pour "
                      "tout le ciel (≈ 10,6 Go)"),
                foreground="#c98a00")
            return
        chunks = cat_mod.chunks_du_champ(ra, dec, rayon)
        if not chunks:
            self.lbl_cat_etat.config(
                text="spectres : aucun morceau trouvé pour ce champ (champ trop "
                     "petit ?)", foreground="#d04040")
            return
        try:
            dossier = cat_mod.dossier_catalogues()
        except Exception as exc:
            self.lbl_cat_etat.config(
                text=f"spectres : dossier des catalogues illisible ({exc})",
                foreground="#d04040")
            return
        texte = (f"spectres Gaia XP du champ (AD {ra:.3f}°, Dec {dec:+.3f}°, "
                 f"rayon {rayon:.2f}°) : morceau(x) "
                 f"{', '.join(str(c) for c in chunks)} — les 343 flux "
                 f"336-1020 nm de la SPCC dans {dossier}")

        def fin(res):
            n = sum(1 for _c, _p, tele in res if tele)
            return (f"spectres téléchargés : {len(res)} morceau(x) du champ "
                    f"({n} transféré(s)) — « ⬇ les 48 » aurait pris ≈ 10,6 Go")

        self._lancer_telechargement(
            "spectres", dossier,
            lambda d, prog: cat_mod.telecharger_chunks(d, chunks, prog),
            texte, fin)

    def _telecharger_spectres_tous(self):
        """⬇ les 48 : tout le catalogue spectral (≈ 10,6 Go) — pour un usage
        itinérant, sans savoir à l'avance ce qu'on visera."""
        try:
            dossier = cat_mod.dossier_catalogues()
        except Exception as exc:
            self.lbl_cat_etat.config(
                text=f"spectres : dossier des catalogues illisible ({exc})",
                foreground="#d04040")
            return

        def fin(res):
            n = sum(1 for _c, _p, tele in res if tele)
            return (f"spectres : {len(res)}/48 morceaux présents dans {dossier} "
                    f"({n} transféré(s)) — la SPCC peut travailler sur tout le "
                    "ciel")

        self._lancer_telechargement(
            "spectres", dossier,
            lambda d, prog: cat_mod.telecharger_tous_les_chunks(d, prog),
            "les 48 morceaux de spectres Gaia XP (≈ 10,6 Go — la reprise est "
            "automatique)", fin)

    def _choisir_dossier_spcc(self):
        """📂 Dossier SPCC : choisit et PERSISTE (config `chemin_spcc`) le dossier
        de la base de profils (capteurs, filtres, références de blanc)."""
        depart = delais.borne(cat_mod.spcc_db.dossier_ecriture,
                              os.path.expanduser("~"), delais.DELAI_DEFAUT)[0]
        d = filedialog.askdirectory(title="Dossier de la base SPCC",
                                    initialdir=depart or os.path.expanduser("~"))
        if not d:
            return
        CONFIG[cat_mod.spcc_db.CLE_CONFIG] = d
        sauver_config(dict(CONFIG))
        # La mesure est BORNÉE : le dossier choisi peut être sur un NAS.
        self._appliquer_spcc_base_vue(*delais.borne(
            self._sonder_spcc_base, ("", None, False), delais.DELAI_DEFAUT)[0])

    def _telecharger_base_spcc(self):
        """⬇ Base SPCC : télécharge la base de profils du dépôt GitLab
        `siril-spcc-database` (quelques Mo, GPLv3) et l'installe dans le dossier
        SPCC — la SPCC n'exige alors plus ni Siril ni une calibration faite
        dans Siril."""
        try:
            dossier = cat_mod.spcc_db.dossier_ecriture()
        except Exception as exc:
            self.lbl_base_spcc.config(
                text=f"Base SPCC : dossier inutilisable ({exc})",
                foreground="#d04040")
            return
        if not dossier:
            self.lbl_base_spcc.config(
                text="Base SPCC : aucun dossier utilisable — en choisir un (📂)",
                foreground="#d04040")
            return
        texte = ("la base de profils SPCC (capteurs, filtres, références de "
                 f"blanc) dans {dossier}")

        def fin(res):
            _d, n, tele = res
            if not tele:
                return (f"base SPCC : déjà complète dans {dossier} — rien à "
                        "télécharger")
            return (f"base SPCC téléchargée : {n} fichiers dans {dossier} — la "
                    "SPCC fonctionne désormais sans Siril")

        self._lancer_telechargement(
            "spcc", dossier,
            lambda d, prog: cat_mod.telecharger_base_spcc(d, prog),
            texte, fin)

    def _choisir_dossier_catalogues(self):
        """Choisit le dossier des catalogues et le PERSISTE (config
        `chemin_catalogues`). Un dossier VIDE est accepté : c'est là que le
        bouton ⬇ écrira."""
        # v2.38.11 : la sonde d'aperçu est BORNÉE (le dossier peut être sur un
        # NAS injoignable) — la boîte de dialogue s'ouvre quoi qu'il arrive.
        depart = delais.borne(cat_mod.dossier_catalogues,
                              os.path.expanduser("~"),
                              delais.DELAI_DEFAUT)[0]
        d = filedialog.askdirectory(title="Dossier des catalogues (Gaia/Siril)",
                                    initialdir=depart)
        if not d:
            return
        CONFIG["chemin_catalogues"] = d
        sauver_config(dict(CONFIG))
        # Un catalogue peut déjà être là (ou arriver par le réseau) : on rouvre
        # les essais et on efface un éventuel « DONNÉES MANQUANTES » affiché.
        self.astro_info = ""
        self._rafraichir_rendu = True
        self._maj_astro_vue()
        # Rafraîchissement DIFFÉRÉ (borné) : la ligne « Catalogues » se remplit
        # dans la seconde, sans risquer d'attendre le NAS.
        self._demander_mesures()

    def _telecharger_catalogue(self):
        """Télécharge le catalogue astrométrique Gaia DR3 de Siril (≈ 1,1 Go
        compressé) dans le dossier des catalogues — thread DÉDIÉ : reprise
        après coupure et sha256 vérifié par le téléchargeur ; l'interface ne
        reçoit que des messages par file (jamais d'appel Tk depuis ce thread)."""
        if self._cat_dl_actif:
            return
        try:
            d = cat_mod.dossier_catalogues()
            os.makedirs(d, exist_ok=True)
        except OSError as exc:
            self.lbl_cat_etat.config(text=f"téléchargement impossible : {exc}",
                                     foreground="#d04040")
            return
        self._cat_dl_actif = True
        self._regler_boutons_dl(True)
        self.lbl_cat_etat.config(
            text=f"téléchargement du catalogue Gaia (≈ 1,1 Go) dans {d}…",
            foreground="#c98a00")

        def travail():
            try:
                from ..catalogues import telechargeur as dl

                chemin, telecharge = dl.telecharger_catalogue_astro(
                    d, lambda nom, frac: self._cat_q.put(
                        ("progres", nom, float(frac))))
                self._cat_q.put(("fini", chemin, bool(telecharge)))
            except Exception as exc:          # réseau, disque, sha256…
                self._cat_q.put(("erreur", str(exc)))

        threading.Thread(target=travail, daemon=True).start()

    def _lire_indices_image(self):
        """Jalon 56 : lit AD/Dec/champ depuis l'image COURANTE (dernière brute
        reçue ou dernier empilement linéaire sauvegardé) et pré-remplit les
        trois champs — l'utilisateur n'a plus qu'à valider (Entrée / FocusOut).
        Priorité : 1) `camera.last_file` (brute reçue), 2) `save_request` chemin
        demandé, 3) dernier FITS dans le dossier d'empilement, 4) empilement
        courant sauvegardé via `images.save_image` (le worker connaît le chemin).
        La lecture est STRICTE (OBJCTRA/OBJCTDEC + FOCALLEN/XPIXSZ) — si le
        header n'a pas les mots-clés, rien n'est rempli et le libellé l'annonce.
        """
        chemin = None
        # 1) dernière brute lue par la caméra (mode live / dossier)
        chemin = getattr(self.camera, "last_file", "") or ""
        # 2) dernier empilement linéaire sauvé par le worker (chemin mémorisé)
        if not chemin:
            chemin = getattr(self, "saved_path", "") or ""
            if chemin and chemin.startswith("ERREUR"):
                chemin = ""
        # 3) si on est en mode dossier, regarder les dossiers de la composition
        if not chemin and self._mode_compo:
            try:
                stats = self.camera.stats() or {}
                cands = [v.get("last_file") or "" for v in stats.values()]
                cands = [c for c in cands if c]
                if cands:
                    chemin = max(cands, key=lambda p: os.path.getmtime(p))
            except Exception:
                pass
        if not chemin or not os.path.isfile(chemin):
            self._astro_msg_indices = "aucune image disponible (dernière brute ou empilement)"
            self._maj_astro_vue()
            return
        ra, dec, champ, msg = astro_mod.indices_entete_fits(chemin)
        if ra is None or dec is None or champ is None:
            self._astro_msg_indices = f"lecture {os.path.basename(chemin)} : {msg}"
            self._maj_astro_vue()
            return
        # Remplit les champs avec les VALEURS ANALYSÉES (format décimal degrés)
        self.var_astro_ra.set(f"{ra:.6f}")
        self.var_astro_dec.set(f"{dec:+.6f}")
        self.var_astro_champ.set(f"{champ:.5f}")
        self._astro_msg_indices = ""
        self._on_astro()        # valide et transmet au worker
        # …PUIS l'origine : _on_astro() vient de la marquer « saisie » (les
        # valeurs sont désormais dans les champs) — la vraie provenance de
        # ces indices est l'image, et c'est ce que l'utilisateur doit lire.
        self._astro_source = f"image {os.path.basename(chemin)}"
        self._maj_astro_vue()

    def _on_linear_fit(self):
        """Jalon 54 : case « Recalage colorimétrique (Linear Fit) » + menu
        « Méthode » — posés sur l'empilement COURANT (mono LiveStacker ou
        façade CompositeStacker, attributs communs) et appliqués au
        composite dès le prochain rendu. Défaut : OFFSET SEUL (retour du
        test réel d'Alain, 21/09/2026 : le gain fondé sur le rapport des
        bruits amplifie halos/bruit bleus d'une image OSC équilibrée)."""
        if self.stacker is not None and hasattr(self.stacker, "linear_fit"):
            self.stacker.linear_fit = bool(self.var_fit.get())
            self.stacker.linear_fit_mode = self._code_fit_methode()
        self._maj_libelle_fit()
        # Jalon 55 : le rendu suit sans attendre la prochaine brute (mode
        # dossier consommé) ; la résolution VeraLux est forcée aussi.
        self._rafraichir_rendu = True
        if getattr(self, "disp", None) is not None:
            self.disp.notify_new_stack()

    def _maj_libelle_fit(self):
        """Libellé des gains/offsets MESURÉS par le recalage (effectif sur
        le dernier mean() : R et B seulement, le vert est la référence)."""
        if not hasattr(self, "lbl_fit"):
            return
        d = (self.stacker.fit_diag if self.stacker is not None else None)
        if not getattr(self, "var_fit", None) or not self.var_fit.get():
            self.lbl_fit.config(text="", foreground="#888888")
            return
        if d is None:
            self.lbl_fit.config(text="Linear Fit : en attente de données…",
                                foreground="#888888")
            return
        gr, ob = d["gains"][0], d["offsets"][0]
        gb, obb = d["gains"][2], d["offsets"][2]
        self.lbl_fit.config(
            text=f"Fit R ×{gr:.3f}{ob:+.4f} · B ×{gb:.3f}{obb:+.4f}",
            foreground="#1d7f1d")

    def _on_rejeter_flou(self):
        """Jalon 17 : active/désactive le filtre anti-brutes très défocalisées.
        Miroir thread-sûr (booléen Python écrit côté UI, lu par le thread
        d'acquisition) : jamais d'accès Tk depuis le worker."""
        self.rejeter_flou = bool(self.var_rejeter_flou.get())

    def _on_cfa(self, *args):
        import avastack.images as _images
        _images.CFA_MODE = self.var_cfa.get()

    def _on_auto(self):
        self.disp.auto = self.var_auto.get()
        if not self.disp.auto:  # fige les réglages sur les points calculés par l'auto
            self.var_black.set(round(self.disp.last_lo, 4))
            self.var_white.set(round(self.disp.last_hi, 4))
            self.scl_black.set(self.var_black.get())
            self.scl_white.set(self.var_white.get())
        self._refresh_preview()

    def _on_target_auto(self):
        """Cible de fond du STF : miroir thread-sûr + aperçu + ligne d'état.

        La cible est ÉCRITE dans le panneau d'histogramme (« cible du fond
        25 % ») : bouger le curseur doit donc mettre la ligne à jour, sinon
        l'état mentirait sur ce que le moteur vise (constat à l'écran du
        28/09/2026)."""
        self.disp.target = float(self.var_target.get())
        if hasattr(self, "lbl_hist_etat"):
            self._maj_niveaux_vue()
        self._refresh_preview()

    def _on_vl_target(self):
        """Fond visé de VeraLux : même logique que `_on_target_auto` (c'est le
        réglage d'Alain, 0,16 sur son M31 — il doit être celui qui s'affiche)."""
        self.disp.vl_target_bg = float(self.var_vl_target.get())
        if hasattr(self, "lbl_hist_etat"):
            self._maj_niveaux_vue()
        self._refresh_preview()

    def _on_moteur(self):
        """Bascule du moteur d'étirement : STF intégré ou VeraLux (tiers).
        VeraLux est opt-in et n'écrit JAMAIS dans black/white/gamma : il
        produit sa propre image étirée, gamma/saturation s'appliquent après
        comme pour le STF."""
        if self.var_moteur.get() == "VeraLux" \
                and not veralux_moteur.moteur_disponible():
            messagebox.showerror(
                "VeraLux",
                "Moteur veralux_core_headless.py introuvable à la racine du "
                "projet — le STF est conservé.")
            self.var_moteur.set("STF")
        veralux_actif = self.var_moteur.get() == "VeraLux"
        self.disp.stretch = "veralux" if veralux_actif else "stf"
        if veralux_actif:
            self.frm_stf.pack_forget()                    # réglages STF masqués
            self.frm_veralux.pack(fill="x", pady=(4, 0), after=self.rowm)
            self._sync_vl_mode()
            self._lbl_vl_texte("Calcul en cours…", "#c98a00")
        else:
            self.frm_veralux.pack_forget()
            self.frm_stf.pack(fill="x", after=self.rowm)  # position d'origine
            self._lbl_vl_texte("—", "#888888")
        # Jalon 75 : la ligne d'état des niveaux nomme le moteur — elle doit
        # suivre le changement de moteur (le panneau d'histogramme n'existe pas
        # encore au tout début de la construction de la fenêtre).
        if hasattr(self, "lbl_hist_etat"):
            self._maj_niveaux_vue()
        self._refresh_preview()

    def _sync_vl_mode(self):
        """Répercute la combobox « Résolution du logD » (jalon 3) dans le
        DisplayProcessor et ajuste le libellé du bouton de verrouillage."""
        forcer = self.var_vl_mode_res.get() == "logD forcé"
        self.disp.vl_mode_res = (veralux_moteur.MODE_LOG_D if forcer
                                 else veralux_moteur.MODE_TARGET_BG)
        self.disp.vl_log_d = self.var_vl_logd.get()
        self.btn_vl_lock.config(text="🔓 Déverrouiller (fond cible)" if forcer
                                     else "🔒 Verrouiller le logD résolu")

    def _on_vl_mode(self):
        """Changement de mode de résolution du logD (jalon 3) : « fond cible
        (auto) » = le moteur résout le logD à chaque nouvel empilement ;
        « logD forcé » = calcul direct déterministe et réactif."""
        self._sync_vl_mode()
        self._refresh_preview()

    def _on_vl_lock(self):
        """Bouton 🔒 (jalon 3) : capte le dernier logD résolu par le mode
        « fond cible » et bascule en « logD forcé » — déterministe et réactif
        (plus de résolution itérative). 🔓 : retour à la résolution auto."""
        if self.var_vl_mode_res.get() == "logD forcé":
            self.var_vl_mode_res.set("fond cible (auto)")
            self._sync_vl_mode()
            self._refresh_preview()
            return
        if self.disp.vl_log_d_resolu is None:
            self.lbl_vl.config(text="Aucun logD résolu pour l'instant — "
                                    "attendez le premier calcul.",
                               foreground="#c98a00")
            return
        # Le curseur met à jour la variable, le label de valeur ET
        # disp.vl_log_d via son callback (_add_slider) :
        self.scl_vl_logd.set(round(self.disp.vl_log_d_resolu, 3))
        self.var_vl_mode_res.set("logD forcé")
        self._sync_vl_mode()
        self._refresh_preview()

    def _on_vl_graxpert(self):
        """Case « GraXpert live » (jalon 4) : enchaîne stack → GraXpert →
        VeraLux dans le thread solveur, à chaque nouvel empilement. Refusé
        si la commande GraXpert n'est pas utilisable (placeholders) ou si son
        exécutable est INTROUVABLE (v2.38.5 : le shell répondait « command
        not found » à chaque empilement, dans un message d'erreur illisible)."""
        actif = self.var_vl_graxpert.get()
        if actif:
            cmd = self.var_cmd_graxpert.get().strip()
            if not gx_live.commande_valide(cmd):
                self.var_vl_graxpert.set(False)
                messagebox.showwarning(
                    "GraXpert live",
                    "Commande GraXpert absente ou incomplète.\n"
                    "Vérifiez la commande dans « Traitement externe » "
                    "(elle doit contenir {input} et {output} ou {outbase}).")
                return
            manque = gx_live.outil_manquant(cmd)
            if manque:
                self.var_vl_graxpert.set(False)
                messagebox.showwarning(
                    "GraXpert live",
                    f"{manque}.\n\n"
                    "Désignez l'exécutable avec le bouton « … » du cadre "
                    "« Traitement externe (long) » (sous Linux, le binaire "
                    "s'appelle GraXpert-linux), ou installez GraXpert.")
                return
            self.disp.vl_graxpert_cmd = cmd
            self._lbl_vl_texte("GraXpert live activé — calcul en cours…",
                               "#c98a00")
        self._sync_vl_graxpert_vue()
        if actif and self.var_view.get() == "traitée":
            self._lbl_vl_texte(
                "Vue « traitée » : GraXpert live ignoré — l'image a déjà "
                "été traitée (il s'appliquera en vue « empilement »).",
                "#c98a00")
        self._refresh_preview()

    def _on_vl_profil(self):
        """Changement du profil capteur VeraLux : fait partie de la clé des
        réglages → le solveur relance la résolution au prochain rendu."""
        self.disp.vl_profil = self.var_vl_profil.get()
        self._refresh_preview()

    def _sync_vl_graxpert_vue(self):
        """GraXpert live ne s'applique QUE sur la vue « empilement » : en vue
        « traitée », l'image a déjà subi le traitement externe (GraXpert/BXT
        manuels via ⚡) — le relancer ferait un DEUXIÈME traitement. La case
        reste cochée : c'est l'état passé au solveur (disp.vl_graxpert) qui
        suit la vue (retour à la case au retour en vue « empilement »)."""
        actif = self.var_vl_graxpert.get() and self.var_view.get() != "traitée"
        if actif != self.disp.vl_graxpert:
            self.disp.vl_graxpert = actif   # la clé change → re-résolution

    def _on_vl_denoise(self):
        """Case/combobox/curseur du débruitage live : répercute méthode et
        force dans le solveur, puis re-résolution. Tolérant : une force
        saisie invalide (texte) est ignorée, la valeur précédente reste."""
        self.disp.vl_denoise_methode = self.VL_DN_CODES.get(
            self.var_vl_dn_methode.get(), "nlm")
        try:
            self.disp.vl_denoise_force = min(
                1.0, max(0.0, float(self.var_vl_dn_force.get())))
        except (tk.TclError, TypeError, ValueError):
            pass                            # saisie invalide : on garde
        self._sync_vl_denoise_vue()
        self._refresh_preview()

    def _sync_vl_denoise_vue(self):
        """Débruitage live = vue « empilement » uniquement (même règle que
        GraXpert live) : en vue « traitée », l'image a déjà subi le
        traitement externe — re-débruiter ferait un DEUXIÈME traitement.
        La case reste cochée : c'est disp.vl_denoise qui suit la vue."""
        actif = self.var_vl_dn.get() and self.var_view.get() != "traitée"
        if actif != self.disp.vl_denoise:
            self.disp.vl_denoise = actif    # la clé change → re-résolution

    def _on_vl_scnr(self):
        """Case SCNR (jalon 22) : répercute dans le solveur — la clé des
        réglages change → re-résolution. Vue « empilement » uniquement
        (en vue « traitée », l'image a déjà subi le traitement externe).
        Jalon 39 : relance le rendu IMMÉDIATEMENT (comme GraXpert live,
        le débruitage et la netteté) — sans ce rafraîchissement, la
        nouvelle chaîne n'était soumise au solveur qu'à la prochaine
        frame empilée ou au prochain réglage appelant _refresh_preview
        (constat réel d'Alain : les cases couleur semblaient inertes
        jusqu'à l'un des deux, par ex. bouger le fond cible)."""
        self._sync_vl_scnr_vue()
        self._refresh_preview()

    def _sync_vl_scnr_vue(self):
        """État SEUL (sans rendu) de la case SCNR : appelé par la case ET
        par _tick/_on_view (la chaîne couleur suit la vue)."""
        actif = self.var_vl_scnr.get() and self.var_view.get() != "traitée"
        if actif != self.disp.vl_scnr:
            self.disp.vl_scnr = actif       # la clé change → re-résolution

    def _on_vl_neutre(self):
        """Case « Neutraliser la couleur du fond » (v2.36.1) : le solveur
        VeraLux applique les gains AVANT l'étirement (le direct aussi :
        `disp.vl_neutre_fond` entre dans la clé des réglages → re-résolution).
        Rend le rendu IMMÉDIATEMENT, comme les autres cases couleur : sans ce
        `_refresh_preview()`, cocher/décocher la case n'avait AUCUN effet visible
        avant la frame suivante — c'est exactement le bug du jalon 39, constaté de
        nouveau par Alain le 25/09/2026 (« ne provoque pas une visualisation
        immédiate… ça semble attendre une nouvelle frame »)."""
        self._sync_vl_neutre_vue()
        self._refresh_preview()

    def _sync_vl_neutre_vue(self):
        """Vue « empilement » uniquement (même règle que SCNR/débruitage : en vue
        « traitée », l'image vient du traitement externe, sans étirement live)."""
        actif = bool(self.var_vl_neutre.get()) \
            and self.var_view.get() != "traitée"
        if actif != self.disp.vl_neutre_fond:
            self.disp.vl_neutre_fond = actif    # la clé change → re-résolution

    def _on_vl_chroma(self):
        """Case/curseur « Réduire le bruit chromatique » (v2.37.0) : force lue
        (tolérante — une saisie invalide laisse la valeur précédente) et
        transportée au solveur VeraLux (10e/11e éléments du job), qui l'applique
        juste avant l'étirement. Rendu IMMÉDIAT, comme les autres cases couleur :
        c'est la leçon du jalon 39, revécue avec la neutralisation du fond
        (constat d'Alain du 25/09/2026 : une case couleur qui n'appelle pas
        `_refresh_preview()` semble inerte jusqu'à la frame suivante)."""
        try:
            self.disp.vl_chroma_force = min(
                1.0, max(0.0, float(self.var_vl_chroma_force.get())))
        except (tk.TclError, TypeError, ValueError):
            pass                            # saisie invalide : on garde
        self._sync_vl_chroma_vue()
        self._refresh_preview()

    def _sync_vl_chroma_vue(self):
        """État SEUL (sans rendu) de la case « Réduire le bruit chromatique » —
        vue « empilement » uniquement, comme les autres corrections de couleur."""
        actif = bool(self.var_vl_chroma.get()) \
            and self.var_view.get() != "traitée"
        if actif != self.disp.vl_chroma:
            self.disp.vl_chroma = actif      # la clé change → re-résolution

    def _poser_rayon_chroma(self, scale):
        """Pose le rayon EFFECTIF du flou de chroma pour une image d'échelle
        `scale` (v2.37.4). Le réglage utilisateur (`self.rayon_chroma_ref`) est
        exprimé en pixels PLEINE RÉSOLUTION ; l'aperçu travaille, lui, sur une
        image RÉDUITE — le rayon doit suivre la résolution, sinon l'écran étale la
        couleur des étoiles plus loin que les fichiers (constat du 26/09/2026 :
        3 px d'aperçu = 7,2 px pleine résolution sur son image de 3838 px, soit
        un halo 2,4 fois plus large à l'écran). Appelé par le worker qui construit
        l'aperçu ET par le curseur de rayon."""
        self._echelle_apercu = float(scale)
        self.disp.vl_chroma_rayon = couleurs_mod.rayon_chroma_apercu(
            scale, self.rayon_chroma_ref)

    def _on_vl_chroma_rayon(self):
        """Curseur « Rayon de référence » du flou de chroma (v2.37.4, demande
        d'Alain) : rayon lu (tolérant — une saisie invalide laisse la valeur
        précédente), rayon effectif de l'aperçu reposé à SON échelle, et rendu
        IMMÉDIAT (même leçon que les autres cases couleur, jalon 39)."""
        try:
            v = float(self.var_vl_chroma_rayon.get())
        except (tk.TclError, TypeError, ValueError):
            v = self.rayon_chroma_ref         # saisie invalide : on garde
        self.rayon_chroma_ref = min(8.0, max(0.5, v))
        self._poser_rayon_chroma(self._echelle_apercu)
        self._refresh_preview()

    def _pleine_res_activee(self):
        """True si l'option « Rendu pleine résolution » de l'écran est cochée
        (v2.38.0).

        ATTENTION THREADS : l'état vit dans `self.pleine_res_ecran`, un simple
        attribut Python — la boucle d'acquisition et `_pousser_rendu` (threads de
        travail) l'interrogent pour mémoriser l'empilement COMPLET. Une variable
        Tk ne peut PAS être lue hors du thread d'interface
        (`RuntimeError: main thread is not in main loop`, constat réel du banc
        jalon 59 : la sauvegarde n'était plus produite), d'où ce miroir posé
        UNIQUEMENT par l'interface (`_on_vl_pleine_res`, restauration de config)."""
        return bool(getattr(self, "pleine_res_ecran", False))

    def _on_vl_pleine_res(self):
        """Case « Rendu pleine résolution (zoom fidèle) » (v2.38.0, demande
        d'Alain du 26/09/2026 : « sur l'écran, je veux pouvoir zoomer sur l'image
        pleine résolution »).

        Trois effets, et rien d'autre :
          - l'état est MIRÉ dans un attribut Python (`self.pleine_res_ecran`),
            seul lisible par les threads de travail (cf. `_pleine_res_activee`) ;
          - décochée : la copie pleine résolution de l'EMPILEMENT (25 Mo) est
            LIBÉRÉE. `proc_full` (résultat du ⚡ traitement externe) n'est PAS
            touché : il sert aux sauvegardes « résultat traité (linéaire) » et
            « tel que vu » en vue traitée, indépendamment de cette option ;
          - `notify_new_stack()` force un nouveau rendu — le cache du solveur
            VeraLux n'a pour clé que les RÉGLAGES, pas la résolution : sans ce
            drapeau, l'ancien rendu d'aperçu resservirait.
        Pendant le calcul (7 à 8 s), l'écran garde la dernière image."""
        v = getattr(self, "var_vl_pleine_res", None)
        self.pleine_res_ecran = bool(v.get()) if v is not None else False
        if not self.pleine_res_ecran:
            self._stack_pleine_res = None
        self.disp.notify_new_stack()
        self._refresh_preview()

    def _on_vl_demagenta(self):
        """Case démagenta (jalon 22) : idem SCNR (jalon 39 : rendu immédiat)."""
        self._sync_vl_demagenta_vue()
        self._refresh_preview()

    def _sync_vl_demagenta_vue(self):
        """État SEUL (sans rendu) de la case démagenta."""
        actif = self.var_vl_demagenta.get() and self.var_view.get() != "traitée"
        if actif != self.disp.vl_demagenta:
            self.disp.vl_demagenta = actif  # la clé change → re-résolution

    def _on_vl_scnr_doux(self):
        """Case SCNR doux (jalon 23) : idem SCNR — bruit seul, structure
        préservée (pensé pour les palettes narrowband). Jalon 39 : rendu
        immédiat."""
        self._sync_vl_scnr_doux_vue()
        self._refresh_preview()

    def _sync_vl_scnr_doux_vue(self):
        """État SEUL (sans rendu) de la case SCNR doux."""
        actif = self.var_vl_scnr_doux.get() \
            and self.var_view.get() != "traitée"
        if actif != self.disp.vl_scnr_doux:
            self.disp.vl_scnr_doux = actif  # la clé change → re-résolution

    def _sync_vl_couleur_vue(self):
        """Chaîne couleur live (jalon 22/23 : SCNR, SCNR doux, démagenta) =
        vue « empilement » uniquement (même règle que le débruitage live) :
        suit le changement de vue. Appelée par _tick TOUTES les 30 ms :
        elle ne touche qu'à l'ÉTAT (les _sync_*), JAMAIS au rendu — les
        _on_* (avec _refresh_preview) ne sont appelés que par les cases
        elles-mêmes (jalon 39 : un rendu ici serait déclenché 3× par tick)."""
        self._sync_vl_scnr_vue()
        self._sync_vl_scnr_doux_vue()
        self._sync_vl_demagenta_vue()
        self._sync_vl_neutre_vue()          # v2.36.1 : fond neutre avant étirement
        self._sync_vl_chroma_vue()          # v2.37.0 : bruit chromatique

    def _on_vl_sharp(self):
        """Case/curseur de la netteté live (jalon 12) : répercute les
        itérations dans le solveur (bornées par le module, plafond dur
        ITERATIONS_MAX), puis relance le rendu. Tolérant : une valeur
        illisible (texte) est ignorée, la valeur précédente reste."""
        try:
            it = int(round(float(self.var_vl_sharp_iter.get())))
        except (tk.TclError, TypeError, ValueError):
            it = nettete_live.ITERATIONS_DEFAUT
        self.disp.vl_sharp_iterations = min(max(it, 1),
                                            nettete_live.ITERATIONS_MAX)
        if it != self.disp.vl_sharp_iterations:
            # Valeur hors bornes (programmée, config restaurée…) : ramenée ICI,
            # jamais appliquée en silence. On passe par le CURSEUR pour que sa
            # position et son étiquette suivent ; le rappel qu'il déclenche
            # s'arrête de lui-même (la valeur est alors dans les bornes, la
            # condition ci-dessus est fausse) — pas de récursion sans fin.
            self.scl_sharp.set(float(self.disp.vl_sharp_iterations))
        self.disp.sh_msg = ""           # message de l'essai précédent périmé
        self._sync_vl_sharp_vue()
        self._maj_lbl_sharp()
        self._refresh_preview()

    def _sync_vl_sharp_vue(self):
        """Netteté live = vue « empilement » uniquement (même règle que
        GraXpert/débruitage live) : en vue « traitée », l'image a déjà subi le
        traitement externe — la reteinter ferait un DEUXIÈME traitement. La
        case reste cochée : c'est disp.vl_sharp qui suit la vue."""
        actif = self.var_vl_sharp.get() and self.var_view.get() != "traitée"
        if actif != self.disp.vl_sharp:
            self.disp.vl_sharp = actif      # la clé change → re-résolution

    def _maj_lbl_sharp(self):
        """Étiquette du cadre « Netteté live » : dit l'état RÉEL, jamais une
        promesse — désactivée, ignorée en vue « traitée », refusée (raison
        donnée par le module) ou active (itérations + provenance de la PSF)."""
        if not self.var_vl_sharp.get():
            txt, coul = "Netteté désactivée", "#888888"
        elif self.var_view.get() == "traitée":
            txt = "Vue « traitée » : netteté live ignorée"
            coul = "#c98a00"
        elif self.disp.sh_msg:
            txt, coul = self.disp.sh_msg, "#d04040"
        else:
            psf = ("PSF du seeing mesuré" if self.disp.vl_seeing
                   else "PSF mesurée sur l'image")
            txt = (f"Netteté active · {self.disp.vl_sharp_iterations} it · "
                   f"{psf}")
            coul = "#1d7f1d"
        self.lbl_sharp.config(text=txt, foreground=coul)

    def _lbl_vl_texte(self, txt, coul):
        """Écrit l'étiquette d'état VeraLux ET son mémo (jalon 40 : le ⏳
        de _maj_lbl_vl ne doit pas être reconfiguré 30 fois par seconde —
        tout autre écrivain de lbl_vl passe par ici pour garder le mémo
        cohérent). Thread UI seul."""
        self._vl_lbl_txt = txt
        self.lbl_vl.config(text=txt, foreground=coul)

    def _maj_lbl_vl(self):
        """État des calculs live à l'écran (jalons 40/41, demande d'Alain :
        matérialiser qu'un calcul tourne et qu'il est terminé). Le cadre
        « État des calculs » est INDÉPENDANT du moteur (jalon 41) :
        - VeraLux : PENDANT un calcul, curseur animé (pb_vl) + étape
          courante du worker (⏳ préparation / composition / GraXpert /
          débruitage / netteté / étirement) ; À LA FIN, ligne de RÉSULTAT —
          ✓ des étapes actives (GX / DN / NET / COUL), logD utilisé, fond
          mesuré — ou erreur en rouge ;
        - STF/manuel : ⏳ netteté pendant la déconvolution du solveur
          dédié (jalon 12), retour au repos ensuite.
        Un seul écrivain : le thread UI (lecture thread-sûre des attributs
        du solveur, jamais d'appel Tk depuis les threads)."""
        veralux = self.var_moteur.get() == "VeraLux"
        en_cours_vl = veralux and self.disp.vl_en_cours()
        en_cours_sh = (not veralux) and self.disp.sh_en_cours()
        en_cours = en_cours_vl or en_cours_sh
        # Curseur de calcul : apparaît au DÉBUT d'un job, disparaît à la FIN
        # (transitions seulement — pas de reconfiguration à chaque tick).
        if en_cours != self._vl_pb_active:
            self._vl_pb_active = en_cours
            if en_cours:
                self.pb_vl.pack(anchor="w", pady=(2, 0))
                self.pb_vl.start(12)
            else:
                self.pb_vl.stop()
                self.pb_vl.pack_forget()
        if self.disp.vl_new:          # un calcul VeraLux vient de se TERMINER
            self.disp.vl_new = False
            if veralux:
                self._refresh_preview()
                if self.disp.vl_error:
                    self._lbl_vl_texte(self.disp.vl_error, "#d04040")
                elif self.disp.vl_diagnostics is not None:
                    d = self.disp.vl_diagnostics
                    prefixe = ("GX ✓ · " if self.disp.vl_graxpert else "") \
                        + ("DN ✓ · " if self.disp.vl_denoise else "") \
                        + ("NET ✓ · " if self.disp.vl_sharp else "") \
                        + ("COUL ✓ · " if (self.disp.vl_scnr
                                           or self.disp.vl_scnr_doux
                                           or self.disp.vl_demagenta) else "") \
                        + ("FOND ✓ · " if self.disp.vl_neutre_gains
                           is not None else "") \
                        + ("CHR ✓ · " if self.disp.vl_chroma else "")
                    texte = (f"{prefixe}logD "
                             f"{self.disp.vl_log_d_resolu:.2f} · "
                             f"fond {d['median_luminance_finale']:.3f}")
                    # v2.36.1 : ANNONCE les gains de neutralisation du fond (sans
                    # quoi l'utilisateur ne peut pas savoir ce qui a été corrigé).
                    if self.disp.vl_neutre_gains is not None:
                        g = self.disp.vl_neutre_gains
                        texte += (f" · fond neutralisé (R {g[0]:.4f} / "
                                  f"G {g[1]:.4f} / B {g[2]:.4f})")
                    self._lbl_vl_texte(texte, "#1d7f1d")
        if en_cours_vl:               # solveur VeraLux : l'étape courante
            txt = f"⏳ calcul : {self.disp.vl_stage or 'préparation'}…"
            if txt != self._vl_lbl_txt:
                self._lbl_vl_texte(txt, "#c98a00")
        elif en_cours_sh:             # solveur de netteté STF/manuel (jalon 12)
            txt = "⏳ calcul : netteté…"
            if txt != self._vl_lbl_txt:
                self._lbl_vl_texte(txt, "#c98a00")
        elif (not veralux) and self._vl_lbl_txt.startswith("⏳"):
            self._lbl_vl_texte("—", "#888888")   # calcul STF fini : repos

    def _on_view(self):
        """Bascule empilement ↔ résultat traité (stats d'étirement réinitialisées :
        les niveaux après GraXpert/BXT ne sont pas les mêmes)."""
        self.disp.reset()
        self._sync_vl_graxpert_vue()
        self._sync_vl_denoise_vue()
        self._sync_vl_couleur_vue()
        self._sync_vl_sharp_vue()
        self._maj_lbl_sharp()
        if self.var_view.get() == "traitée":
            if self.proc_show is not None:
                self.last_show = self.proc_show
                self._rendre_et_afficher(self.last_show, live=False)
            else:
                self._set_ext_msg("Aucun résultat traité — cliquez « ⚡ Traiter » d'abord.")
        else:
            if self.show_stack is not None:
                self.last_show = self.show_stack
                self._rendre_et_afficher(self.last_show, live=False)

    def _rendre_et_afficher(self, lineaire, live=True, hist=True):
        """Chaîne d'affichage COMPLÈTE et UNIQUE (jalon 75) : source linéaire →
        étirement (STF / manuel / VeraLux) → étage de niveaux → gamma et
        saturations → écran, ET mise à jour des deux histogrammes.

        Un seul point de passage pour les endroits qui affichaient une image :
        c'est ce qui garantit que l'histogramme décrit toujours ce qui est à
        l'écran (avant le jalon 75 le calcul vivait dans le thread
        d'acquisition, sur l'aperçu de l'empilement — donc jamais sur l'image
        d'une vue « traitée », et à ~55 ms par frame de CPU).
        """
        src = self._src_rendu(lineaire)
        img8 = self.disp.process(src, live=live)
        if hist:
            self._maj_histogrammes(src,
                                   getattr(self.disp, "dernier_brut_niveaux",
                                           None))
        self._show_image(img8)

    def _refresh_preview(self, hist=True):
        """Re-rend l'aperçu immédiatement après un réglage (indispensable en mode
        dossier : pas de frame régulière pour rafraîchir l'écran).
        live=False : ne fait pas avancer le lissage temporel des stats.
        hist=False : le glissement d'une BARRE DE NIVEAUX ne recalcule pas
        l'histogramme (la donnée du moteur ne change pas — seules les barres
        bougent) : sans cela, chaque pixel de souris coûterait un histogramme."""
        if self.last_show is not None:
            self._rendre_et_afficher(self.last_show, live=False, hist=hist)

    def _push_settings(self):
        # Instantanés « thread-safe » (attributs simples lus par le worker) :
        # le worker n'a JAMAIS le droit de lire une variable Tk.
        self.expo_ms = float(self.var_expo.get())
        self.gain_val = float(self.var_gain.get())
        if self.camera is not None:
            self.pending_settings = (self.expo_ms, self.gain_val)
            self.pending_offset = float(self.var_offset.get())

    # --- cadence d'empilement (jalon 42, demande d'Alain) -------------------
    def _brutes_en_attente(self):
        """Brutes détectées sur le disque mais pas encore lues (jalon 42) —
        sources dossier/composition uniquement ; 0 pour les autres."""
        cam = self.camera
        if cam is None:
            return 0
        if self._mode_compo:
            return int(getattr(cam, "pending", 0))
        return len(getattr(cam, "_pending", []))

    def _cadence_dossier(self):
        """True si la cadence s'applique à la source courante (jalon 42) :
        dossier surveillé / composition multi-dossiers SEULEMENT — les
        files des caméras SDK ne doivent jamais s'accumuler (mémoire)."""
        return isinstance(self.camera, (FolderCamera, MultiFolderCamera))

    def _autoriser_lecture(self):
        """Décision de cadence (jalon 42) : True = le worker peut lire une
        brute maintenant. En surveillance de dossier, les brutes qui
        arrivent pendant la fenêtre d'attente RESTENT sur le disque (aucune
        perte) puis sont drainées en rafale à l'échéance — le solveur
        VeraLux ne relance alors qu'une fois par rafale (dernier job
        gagnant) au lieu d'à CHAQUE brute : c'est ce qui évite le sablier
        permanent avec la chaîne lourde (gradient/débruitage live).
        cadence 0 = « dès réception » (comportement inchangé).
        JALON 43 (bug du jalon 42, constat réel d'Alain en composition) :
        la fenêtre armée bloque TOUTE lecture, MÊME sans brute détectée —
        sinon le scan interne des caméras dossier (à l'intérieur de
        read()) détectait la brute à l'instant où elle devenait complète
        et la renvoyait immédiatement, court-circuitant la fenêtre : la
        cadence ne ralentissait RIEN pour des arrivées plus espacées que
        la fenêtre (le premier fichier de chaque « rafale » partait toujours
        tout de suite). Pendant la fenêtre, le worker ne fait que scanner
        (0,4 s) et attendre — la détection se fait par scanner(), la lecture
        attend l'échéance."""
        if self.cadence_lecture <= 0 or not self._cadence_dossier():
            return True
        return time.monotonic() >= self._prochaine_lecture

    def _armer_cadence(self):
        """(Ré)arme la fenêtre de cadence (jalon 42/46) — appelé par le
        worker quand une brute vient d'être lue. La rafale SE TERMINE quand
        soit TOUTES les brutes détectées ont été lues (jalon 42), soit le
        budget de rafale est épuisé (jalon 46 : RAFALE_MAX brutes — avec un
        dossier déjà REMPLI d'acquisitions antérieures, le drain pouvait
        durer des minutes d'affilée ; le plafond borne chaque rafale et le
        reste des fichiers attend les rafales suivantes, aucune perte)."""
        if self.cadence_lecture > 0 and (self._rafale_reste <= 0
                                         or self._brutes_en_attente() == 0):
            self._prochaine_lecture = time.monotonic() + self.cadence_lecture
            self._rafale_reste = self.RAFALE_MAX

    def _on_cadence(self):
        """Combobox « Empiler les brutes » (jalon 42) : répercute la cadence
        dans le worker (miroir thread-sûr : int écrit côté UI, lu par le
        worker — jamais d'accès Tk depuis le thread de travail)."""
        self.cadence_lecture = self.CADENCE_CODES.get(
            self.var_cadence.get(), 0)
        if self.cadence_lecture <= 0:
            self._prochaine_lecture = 0.0   # « dès réception » : plus de fenêtre

    def _creer_cadence(self, parent):
        """Ligne « Empiler les brutes » (jalon 42 ; jalon 47 : UN SEUL
        exemplaire, dans le cadre dédié « Cadence d'empilement » — fini la
        duplication du jalon 45 dans les cadres dossier ET composition ; le
        choix reste commun, la cadence s'applique aux DEUX sources dossier
        car le worker la porte). L'étiquette (jalon 44) montre l'état du
        throttling en direct : « prochaine rafale dans Xs · N brute(s) en
        attente » (fenêtre armée), « rafale en cours » (drain), « — » (dès
        réception ou pas encore de source)."""
        if not hasattr(self, "var_cadence"):
            self.var_cadence = tk.StringVar(value="dès réception")
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(3, 0))
        ttk.Label(row, text="Empiler les brutes :").pack(side="left")
        cb = ttk.Combobox(row, textvariable=self.var_cadence,
                          state="readonly", width=16,
                          values=[lib for lib, _ in self.CADENCES])
        cb.pack(side="left", padx=(4, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_cadence())
        self._cadence_cbs.append(cb)
        if not hasattr(self, "cb_cadence"):
            self.cb_cadence = cb            # compatibilité (première créée)
        lbl = ttk.Label(parent, text="—")
        lbl.pack(anchor="w")
        self._cadence_lbls.append(lbl)
        if not hasattr(self, "lbl_cadence"):
            self.lbl_cadence = lbl          # compatibilité (première créée)

    def _maj_lbl_cadence(self):
        """État de la cadence affiché EN DIRECT (jalon 44) : pendant la
        fenêtre d'attente, « prochaine rafale dans Xs · N brute(s) en
        attente » (ambre) — la preuve visible que le throttling retient les
        brutes ; à l'échéance, « rafale en cours · N » (vert) pendant le
        drain ; « — » = dès réception OU pas encore de source connectée
        (jalon 45 : ne plus afficher « sans objet » avant la connexion —
        constat d'Alain) ; cadence posée sur une source non dossier →
        « sans objet ». Thread UI seul (appelé par _tick)."""
        if self.camera is None:
            txt, coul = "—", "#888888"      # pas encore de source : au repos
        elif self.cadence_lecture > 0 and self._cadence_dossier():
            attente = self._brutes_en_attente()
            reste = self._prochaine_lecture - time.monotonic()
            if reste > 0:
                txt = (f"prochaine rafale dans {reste:.0f} s · "
                       f"{attente} brute(s) en attente")
                coul = "#c98a00"
            else:
                txt = f"rafale en cours · {attente} brute(s) en attente"
                coul = "#1d7f1d"
        elif self.cadence_lecture > 0:
            txt = "cadence : sans objet (source non dossier)"
            coul = "#888888"
        else:
            txt, coul = "—", "#888888"
        if txt != self._cadence_lbl_txt:
            self._cadence_lbl_txt = txt
            for lbl in self._cadence_lbls:
                lbl.config(text=txt, foreground=coul)

    # --- contrôles caméra QHY (jalon 25) : demandes posées ICI (thread Tk),
    # consommées par le thread de travail — jamais d'appel SDK depuis Tk.
    def _adapter_ui_capacites(self, cap):
        """Jalon 31 — DEMANDE D'ALAIN (20/09/2026) : à la connexion d'une
        caméra (toute marque), l'UI est reconstruite avec les bornes RÉELLES
        détectées par le SDK — RIEN n'est câblé en dur. `cap` = objet
        Capacites (peut être None : on ne touche alors à rien).

        Curseurs : reconstruits par DESTRUCTION/REMPLACEMENT (grid+pack
        interdits dans le même conteneur — leçon des bancs), valeurs
        courantes conservées si elles restent dans les nouvelles plages.
        Exposition : plages log dynamiques (bornes natives en ms) ; TEC :
        consigne bornée à la plage native (arrondie au pas) ; roue :
        combobox limitée aux SLOTS réels ; étiquettes : bornes lues."""
        if cap is None:
            return
        # --- exposition (µs natif → ms interne) : bornes log dynamiques ---
        if getattr(cap, "expo_us", None):
            lo_ms = max(float(cap.expo_us[0]) / 1000.0, 0.001)
            hi_ms = float(cap.expo_us[1]) / 1000.0
            if hi_ms > lo_ms:
                self._EXPO_DYN = (lo_ms, hi_ms)
                # Jalon 34 (Alain) : coupure à 5 s — si la plage native est
                # ENTIÈREMENT d'un côté du pivot, la case n'a aucun effet :
                # on la décoche pour ne pas afficher un réglage factice.
                if not (lo_ms < 5000.0 < hi_ms):
                    self.var_expo_longue.set(False)
                maj = getattr(self, "_maj_expo", None)
                if maj is not None:
                    maj(self.var_expo.get())
                # Le libellé de la case suit la borne max réelle.
                maj_case = getattr(self, "_maj_libelle_expo_longue", None)
                if maj_case is not None:
                    maj_case()
        # --- gain / offset : reconstruction de la ligne complète ---------
        # Jalon 32 : cid résolu PAR MARQUE via cap.plage(rôle) — les ids
        # diffèrent entre les SDK (« 6 » = gain QHY, mais balance des blancs
        # B chez Player One, « Flip » chez SVBONY) : interroger un cid
        # littéral produirait des curseurs aux bornes FAUSSES.
        for nom_attr, role, var in (("sl_gain", "gain", self.var_gain),
                                    ("sl_offset", "offset", self.var_offset)):
            ancien = getattr(self, nom_attr, None)
            if ancien is None or getattr(ancien, "_row", None) is None:
                continue
            p = cap.plage(role)
            if p is None:
                continue
            mn, mx, st = p
            base = getattr(ancien, "_lbl_txt", nom_attr).split(" (")[0]
            try:
                ancien._row.destroy()
            except tk.TclError:
                pass
            var.set(min(max(var.get(), mn), mx))     # valeur dans la plage
            # Jalon 51 (demande d'Alain : « offset lu plutôt que 10 par
            # défaut, règle valable pour toutes les caméras ») : si la sonde
            # a LU la valeur courante de ce rôle sur la caméra, l'appli
            # l'ADOPTE — elle n'impose pas la sienne. Un offset de capteur
            # écrasé silencieusement fausse les brutes (et les darks/flats
            # associés). Aucune valeur lue (marque muette) → comportement
            # d'origine : la valeur de l'UI est seulement ramenée dans la
            # plage détectée.
            actuel = cap.valeur_actuelle(role)
            if actuel is not None:
                var.set(min(max(actuel, mn), mx))
            parent = ancien._row.master   # le parent de la LIGNE détruite
            setattr(self, nom_attr, self._add_slider(
                parent, f"{base} ({mn:g} – {mx:g})", var,
                mn, mx, st, self._push_settings, "{:.0f}", saisie=True))
        # --- TEC : plage de consigne réelle ------------------------------
        if getattr(cap, "tec_consigne", None) and cap.tec:
            t = cap.tec_consigne
            if t[0] < t[1]:
                self.tec_plage = (float(t[0]), float(t[1]))
        # --- roue : slots réels détectés ----------------------------------
        n = getattr(cap, "roue_slots", None)
        if n and n > 0:
            self._filtres_dispo = (FILTRES_ROUE[:int(n)]
                                   if int(n) < len(FILTRES_ROUE)
                                   else FILTRES_ROUE)
            self._roue_ok = True     # la roue a été vue par la sonde native
        # --- partie Tk directe (méthode appelée depuis le thread UI) ------
        # roue : valeurs = slots réels (Dark, L, R… jusqu'à n)
        try:
            self.cb_filtre.config(values=list(self._filtres_dispo))
        except tk.TclError:
            pass
        if self.var_filtre.get() not in self._filtres_dispo:
            self.var_filtre.set(self._filtres_dispo[0])
        # consigne TEC : clamp à la plage réelle + bornes affichées
        t = self.tec_plage
        if t is not None:
            try:
                v = float(self.var_tec_consigne.get().replace(",", "."))
                self.var_tec_consigne.set(f"{min(max(v, t[0]), t[1]):g}")
            except ValueError:
                pass
            self.lbl_tec_lib.config(
                text=f"Consigne °C ({t[0]:g} à {t[1]:g}) :")

    def _on_filtre_choisi(self, _e=None):
        try:
            n = FILTRES_ROUE.index(self.var_filtre.get())
        except ValueError:
            return
        self._filtre_demande = n

    def _on_consigne_tec(self):
        try:
            t = float(self.var_tec_consigne.get().replace(",", "."))
        except ValueError:
            self._tec_info = ("Consigne TEC : nombre invalide", "#d04040")
            return
        # Jalon 31 : clamp à la plage RÉELLE de la caméra (plage native si
        # détectée, bornes prudentes d'origine sinon).
        plage = self.tec_plage or (-30.0, 45.0)
        self._tec_demande = ("consigne", min(max(t, plage[0]), plage[1]))

    def _on_arret_tec(self):
        self._tec_demande = ("stop", None)

    def _pick_dossier_compo(self, i):
        d = filedialog.askdirectory(
            title=("Dossier des brutes « "
                   + (self.var_compo_roles[i].get() or "rôle ?") + " »"))
        if d:
            self.var_compo_dossiers[i].set(d)

    def _detecter_filtres(self):
        """Auto-détection (jalon 19) : pour chaque dossier rempli, lit le
        mot-clé FILTER du FITS le plus récent et applique le rôle
        correspondant. Override manuel ensuite : les menus déroulants
        restent modifiables à la main."""
        rapports = []
        for i in range(4):
            d = self.var_compo_dossiers[i].get().strip()
            if not d or not os.path.isdir(d):
                continue
            filtre = None
            try:
                candidats = [os.path.join(d, f) for f in os.listdir(d)
                             if f.lower().endswith((".fits", ".fit", ".fts"))]
                if candidats:
                    recent = max(candidats, key=os.path.getmtime)
                    filtre = lire_filtre_fits(recent)
            except Exception:
                filtre = None
            role = role_de_filtre(filtre)
            if role:
                self.var_compo_roles[i].set(role)
                rapports.append(f"Ligne {i + 1} : FILTER = « {filtre} » "
                                f"→ rôle {role}")
            elif filtre:
                rapports.append(
                    f"Ligne {i + 1} : FILTER = « {filtre} » non reconnu "
                    f"(rôle inchangé : {self.var_compo_roles[i].get() or '—'})")
            else:
                rapports.append(f"Ligne {i + 1} : aucun mot-clé FILTER trouvé")
        self._on_compo_roles()   # la composition se recolle aux rôles détectés
        if rapports:
            messagebox.showinfo("Détection des filtres", "\n".join(rapports))
        else:
            messagebox.showinfo("Détection des filtres",
                                "Aucun dossier rempli dans la composition.")

    def _save_canaux(self):
        """Sauvegarde des empilements PAR CANAL (jalon 19) : un fichier
        « canal_<rôle>.fit » (linéaire, recadré au cadre commun) par rôle
        empilé. Consommée par le thread d'acquisition (comme save_request)."""
        if not (self._mode_compo and self.stacker is not None
                and self.stacker.n > 0):
            messagebox.showinfo(
                "Canaux", "Rien à enregistrer : démarrez une session en mode "
                          "composition et attendez au moins une frame.")
            return
        d = filedialog.askdirectory(
            title="Dossier où enregistrer les empilements par canal")
        if d:
            self.save_canaux_request = d

    # --- Détection des caméras SDK (correctif du 19/09/2026) -----------------
    _SOURCES_SDK = ("QHY", "ZWO", "Player One", "Touptek", "SVBONY")

    # --- Jalon 47 : visibilité des cadres selon la source --------------------
    def _maj_visibilite_cadres(self):
        """N'afficher que les cadres UTILES à la source choisie (demande
        d'ergonomie d'Alain, jalon 47 : « la partie droite est surchargée » —
        la colonne de réglages à gauche de l'image) :
          - source caméra (simulée, OpenCV, SDK) → contrôles caméra seuls ;
          - « Dossier surveillé » → cadre dossier + cadence d'empilement ;
          - « Composition multi-dossiers » → cadre composition + cadence.
        Le réglage de rafale (« Empiler les brutes », jalons 42/45) est un
        cadre UNIQUE (`frm_rafale`) partagé par les deux modes dossier — il
        n'apparaît plus pour une vraie caméra (sans objet). On CACHE
        (pack_forget), on ne détruit RIEN : les valeurs saisies (dossier,
        rôles, gains…) sont conservées et la persistance ne change pas. Les
        cadres visibles sont replacés dans l'ordre canonique (rafale →
        dossier → composition) juste avant l'ancre stable `frm_calibration` :
        l'ordre général de la colonne ne bouge jamais. Thread UI seul
        (construction, _restaurer_config, _on_source_choisie)."""
        source = self.var_source.get()
        est_dossier = source.startswith("Dossier")
        est_compo = source.startswith("Composition")
        # Contrôles caméra : toute source qui n'est NI dossier NI composition
        # (simulée, webcams OpenCV, SDK constructeur). La combobox de source
        # et Démarrer/Arrêter restent visibles en toutes circonstances.
        if est_dossier or est_compo:
            self.frm_ctrl_cam.pack_forget()
        elif self.frm_ctrl_cam.winfo_manager() == "":
            self.frm_ctrl_cam.pack(fill="x")
        visibles = ([self.frm_rafale, self.frm_dossier] if est_dossier else
                    [self.frm_rafale, self.frm_compo] if est_compo else [])
        for cadre in (self.frm_rafale, self.frm_dossier, self.frm_compo):
            if cadre in visibles:
                # pack(before=) replace le cadre (déjà géré ou non) à la même
                # place relative — appelé dans l'ordre canonique ci-dessus.
                cadre.pack(fill="x", pady=3, before=self.frm_calibration)
            elif cadre.winfo_manager():
                cadre.pack_forget()
        # Jalon 53 : les libellés dark/flat suivent la source (détail par
        # couche en composition, libellé simple hors composition).
        if hasattr(self, "lbl_dark"):
            self._maj_libelles_calib()

    def _on_source_choisie(self, *_):
        """Sélection d'une source : auto-détection si source « SDK ».
        Une caméra connectée est d'abord déconnectée (jalon 26 : la
        connexion appartient à la source ; pour une QHY, la reconnexion
        dans le même process est impossible — l'utilisateur est prévenu et
        la re-détection automatique est évitée, elle échouerait)."""
        # Jalon 47 : les cadres suivent la source AVANT toute autre action
        # (y compris si la suite retourne tôt — cas de la déconnexion QHY).
        self._maj_visibilite_cadres()
        if self.camera is not None:
            qhy = isinstance(self.camera, QHYCamera)
            self._deconnecter_camera()
            t0 = time.monotonic()
            while (self.camera is not None and self.thread is not None
                   and self.thread.is_alive()
                   and time.monotonic() - t0 < 8.0):
                try:
                    self.root.update()     # _tick consomme la confirmation
                except tk.TclError:
                    break
                time.sleep(0.05)
            if qhy:
                messagebox.showinfo(
                    "Changement de source",
                    "La caméra QHY a été déconnectée.\n\nAprès une "
                    "déconnexion, relancez l'application pour reconnecter "
                    "une caméra QHY (le SDK ne peut pas être réinitialisé "
                    "dans le même process).")
                self.lbl_detect.config(
                    text="QHY déconnectée — relancez l'application pour "
                         "reconnecter (le SDK QHY ne peut pas être "
                         "réinitialisé dans ce process).",
                    foreground="#B06000")
                return
        if self.var_source.get().startswith(self._SOURCES_SDK):
            self._detecter_camera()
        else:
            self.lbl_detect.config(text="")
            # v2.41.0 : « ▶ Démarrer » doit redevenir ACCESSIBLE. La
            # déconnexion ci-dessus le grise ; pour ces sources-là (simulée,
            # dossier, composition), aucune connexion automatique ne viendra le
            # réactiver — il restait grisé jusqu'à la fin de la session
            # (constat d'Alain, 28/09/2026 : « quand c'est accessible, ce qui
            # n'est pas toujours le cas »). Le worker, lui, démarre s'il ne
            # tourne plus, au moment du « ▶ Démarrer ».
            self.btn_start.config(state="normal")

    def _detecter_camera(self):
        """Lance la détection (thread : ne jamais bloquer l'UI)."""
        if self.camera is not None:
            messagebox.showinfo(
                "Détection",
                "Une caméra est déjà connectée — déconnectez-la d'abord "
                "(⏏) pour en changer.")
            return
        if self._detect_busy or self._connexion_busy:
            return
        source = self.var_source.get()
        if source.startswith("QHY"):
            self._detect_busy = True
            self.lbl_detect.config(text="QHY : scan en cours…")
            threading.Thread(target=self._detect_qhy, daemon=True).start()
        elif source.startswith(self._SOURCES_SDK):
            self._detect_busy = True
            self.lbl_detect.config(text="Scan en cours…")
            threading.Thread(target=self._detect_sdk_local,
                             args=(source,), daemon=True).start()

    def _detect_qhy(self):
        """Scan QHY DANS UN SOUS-PROCESSUS isolé (le résultat est consommé
        par _tick côté thread UI ; aucun appel Tk depuis ce thread)."""
        ids, err = lister_via_sous_processus()
        self._detect_result = ("QHY", ids, err)

    def _detect_sdk_local(self, source):
        """Scan des autres marques, in-process (sans DLL → RuntimeError
        propre ; lister() des modules attrape déjà les exceptions)."""
        cls = (PlayerOneCamera if source.startswith("Player One")
               else TouptekCamera if source.startswith("Touptek")
               else SVBonyCamera if source.startswith("SVBONY")
               else ZWOASICamera)
        fn = getattr(cls, "lister", None)
        if fn is None:
            self._detect_result = (source, None,
                                   "détection non disponible (SDK/paquet absent)")
            return
        try:
            self._detect_result = (source, list(fn()), None)
        except Exception as e:
            self._detect_result = (source, None, str(e))

    def _connecter_qhy(self):
        """CONNEXION de la caméra QHY (jalon 26, thread dédié) : ouverture
        SANS empilement — le sondage des contrôles (roue/TEC), l'application
        des réglages et le refroidissement deviennent possibles AVANT le
        « ▶ Démarrer » (qui ne lance plus que l'empilement).

        PIÈGE (constat réel du 19/09/2026 : « connexion de la caméra… »
        figée pour toujours) : ce thread n'a PAS le droit de toucher aux
        variables Tkinter — `var_expo.get()` depuis un thread secondaire
        bloque sur le verrou Tcl (jamais de retour, jamais d'exception).
        Les instantanés `expo_ms`/`gain_val` (tenus à jour par
        _push_settings côté thread Tk) sont les seuls accès sûrs ; les
        réglages sont de toute façon (re)posés par le worker
        (pending_settings) une fois la connexion consommée.
        """
        try:
            if self._qhy_id and not self._qhy_id.startswith("<"):
                cam = QHYCamera(camera_id=self._qhy_id)
            elif self._sdk_ids:
                cam = QHYCamera(camera_id=str(self._sdk_ids[0]))
            else:
                cam = QHYCamera()
            cam.open()
            self._connexion_result = (cam, None)
        except Exception as e:
            self._connexion_result = (None, str(e))

    def _connecter_sdk(self, source):
        """CONNEXION des caméras SDK NON-QHY (jalon 32, thread dédié — le
        même modèle que QHY, jalon 26) : ouverture SANS empilement ; le
        résultat (source, cam, err) est consommé par _tick, qui détecte les
        capacités puis construit l'UI aux bornes réelles.

        PIÈGE (cf. _connecter_qhy) : ce thread ne touche à AUCUNE variable
        Tk — la classe est instanciée SANS arguments (aucun réglage lu ici) ;
        les réglages sont de toute façon (re)posés par le worker
        (pending_settings) une fois la connexion consommée."""
        cls = (PlayerOneCamera if source.startswith("Player One")
               else TouptekCamera if source.startswith("Touptek")
               else SVBonyCamera if source.startswith("SVBONY")
               else ZWOASICamera)
        try:
            cam = cls()
            cam.open()
            self._connexion_sdk_result = (source, cam, None)
        except Exception as e:
            self._connexion_sdk_result = (source, None, str(e))

    def _installer_camera_connectee(self, cam, source):
        """Après une CONNEXION RÉUSSIE (thread Tk seul) : pose la caméra,
        détecte les capacités (curseurs aux bornes réelles, roue aux slots
        réels, TEC borné — jalon 31 pour QHY, jalon 32 pour les autres),
        réarme les réglages et les boutons, démarre le worker permanent
        (pilotage des contrôles). Utilisé par le chemin QHY (jalon 26/31)
        ET par les autres marques (jalon 32) : une seule définition, zéro
        duplication. `source` : libellé de marque pour les messages
        (« QHY », « Player One (SDK) »…)."""
        self.camera = cam
        self.cam_pilotee = cam if isinstance(cam, CAMERAS_PILOTEES) else None
        self._controles_sondes = False
        self._roue_ok = self._tec_ok = False
        # Jalon 31 : détection des capacités puis ADAPTATION de l'UI
        # (curseurs aux plages réelles, roue aux slots réels, TEC borné) —
        # demandé par Alain : « quand tu connectes une caméra tu fais ce
        # travail de détection et ensuite tu construis l'UI », pour toutes
        # les marques. La caméra est ouverte : detecter_capacites traduit
        # le relevé fait à l'ouverture (aucun appel SDK bloquant).
        try:
            self.capacites = cam.detecter_capacites()
        except Exception:
            self.capacites = None
        self._adapter_ui_capacites(self.capacites)
        self.pending_settings = (self.expo_ms, self.gain_val)
        self.pending_offset = float(self.var_offset.get())
        self.var_filtre.set(FILTRES_ROUE[0])
        self.cb_filtre.config(state="disabled")
        self.lbl_filtre.config(text="", foreground="#888888")
        self.btn_tec_on.config(state="disabled")
        self.btn_tec_off.config(state="disabled")
        self.lbl_tec.config(text="Capteur : — · TEC : —",
                            foreground="#888888")
        self.btn_start.config(state="normal")
        self.btn_deconnect.config(state="normal")
        self.lbl_detect.config(text=f"{source} : connectée ({cam.name})",
                               foreground="#1d7f1d")
        self.lbl_status.config(
            text="Caméra connectée — réglez (température, filtre, "
                 "gain…) puis « ▶ Démarrer » pour empiler.")
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._worker,
                                           daemon=True)
            self.thread.start()

    def _connexion_terminee(self, etat, cam, err):
        """Consommation du résultat de connexion (thread Tk seul) : état
        des lignes de contrôles + message d'état. Un échec réactive le
        bouton (on peut resscanner) ; un succès active « ▶ Démarrer » et
        « ⏏ Déconnecter »."""
        self._connexion_busy = False
        if etat == "erreur":
            self._detect_busy = False
            self.lbl_detect.config(text=f"QHY : connexion impossible — {err}",
                                   foreground="#d04040")
            return
        self.camera = cam
        self.cam_pilotee = cam if isinstance(cam, CAMERAS_PILOTEES) else None
        self._controles_sondes = False
        self._roue_ok = self._tec_ok = False
        self.btn_start.config(state="normal")
        self.btn_deconnect.config(state="normal")
        self._detect_busy = False
        self.lbl_detect.config(text=f"QHY : connectée ({cam.name})",
                               foreground="#1d7f1d")
        self.lbl_status.config(
            text="Caméra connectée — réglez (filtre, refroidissement, "
                 "gain…) puis « ▶ Démarrer » pour empiler.")

    def _make_camera(self, key):
        if key.startswith("Simulée"):
            return SimulatedCamera()
        if key.startswith("Dossier"):
            folder = self.var_folder.get().strip()
            if not folder:
                raise RuntimeError("Choisissez d'abord le dossier à surveiller (bouton …)")
            return FolderCamera(folder, process_existing=self.var_process_existing.get())
        if key.startswith("Composition"):
            # Jalon 19 phase 3 : 1 à 4 dossiers surveillés, un rôle par ligne
            # (les erreurs de remplissage sortent avec un message clair).
            return MultiFolderCamera(self._lire_roles_dossiers(),
                                     process_existing=self.var_process_existing.get())
        if key.startswith("OpenCV"):
                        return OpenCVCamera(int(key.split()[-1]))
        if key.startswith("QHY"):
            return QHYCamera(camera_id=self._qhy_id)
        if key.startswith("Player One"):
            return PlayerOneCamera()
        if key.startswith("Touptek"):
            return TouptekCamera()
        if key.startswith("SVBONY"):
            return SVBonyCamera()
        return ZWOASICamera()

    # --- Jalon 19 phase 3 : composition multi-filtres ------------------------
    def _on_compo(self):
        """Choix de la composition → pré-remplit les rôles des 4 lignes."""
        roles = roles_de(self.var_compo.get())
        for i in range(4):
            self.var_compo_roles[i].set(roles[i] if i < len(roles) else "")
        self._maj_compo_info()

    def _on_compo_roles(self, *_):
        """Changement manuel d'un rôle (override de la détection) → la
        composition se DÉDUIT des rôles remplis (sens inverse : les
        dossiers contraignent la composition). Pas de correspondance
        connue → la composition affichée reste en place, l'erreur exacte
        sera levée au démarrage (garde-fou déjà en place)."""
        remplis = tuple(v.get() for v in self.var_compo_roles if v.get())
        comp = composition_pour_roles(remplis)
        if comp and comp != self.var_compo.get():
            self.var_compo.set(comp)
        self._maj_compo_info()

    def _maj_compo_info(self):
        """Ligne d'aide : mapping de la composition ; la radio « Canal L »
        n'est active qu'en LRGB (inutile ailleurs)."""
        nom = self.var_compo.get()
        spec = COMPOSITIONS.get(nom)
        if spec is None:
            self.lbl_compo_info.config(text="—")
            return
        if "canaux_rgb" not in spec:
            txt = "Mono : un seul dossier, composite monochrome."
        else:
            txt = " · ".join(f"{canal}={'+'.join(roles)}"
                             for canal, roles in spec["canaux_rgb"].items())
            if "luminance" in spec:
                txt += " + luminance L (optionnelle)"
        self.lbl_compo_info.config(text=txt)
        etat = "normal" if nom == "LRGB" else "disabled"
        self.rb_l_syn.config(state=etat)
        self.rb_l_deg.config(state=etat)
        self._maj_libelles_calib()   # jalon 53 : le détail suit les rôles

    def _pick_folder(self):
        d = filedialog.askdirectory(title="Dossier où arrivent les brutes")
        if d:
            self.var_folder.set(d)

    def _lire_roles_dossiers(self):
        """Couples (rôle, dossier) des lignes remplies (au démarrage).
        Lève une erreur claire sur un remplissage incohérent : rôle sans
        dossier, rôle en double, dossier sans rôle, tout vide."""
        pairs, vus = [], {}
        for i in range(4):
            role = self.var_compo_roles[i].get().strip()
            doss = self.var_compo_dossiers[i].get().strip()
            if not role:
                if doss:
                    raise RuntimeError(
                        f"Ligne {i + 1} : dossier rempli mais aucun rôle "
                        "choisi (menu déroulant de la ligne)")
                continue
            if not doss:
                raise RuntimeError(
                    f"Rôle {role} : choisissez le dossier à surveiller (…)")
            if role in vus:
                raise RuntimeError(
                    f"Rôle {role} présent sur les lignes {vus[role] + 1} "
                    f"et {i + 1} — un rôle = un seul dossier")
            vus[role] = i
            pairs.append((role, doss))
        if not pairs:
            raise RuntimeError("Composition : remplissez au moins une ligne "
                               "(rôle + dossier)")
        return pairs

    def _on_norm_commune(self):
        """v2.36.0 — case « Normalisation commune des canaux » (option, décision
        d'Alain du 25/09/2026). Posée sur l'empilement courant et appliquée dès
        le prochain rendu ; l'instantané `_norm_commune` est celui que lit le
        worker (jamais de variable Tk hors du thread principal)."""
        self._norm_commune = bool(self.var_norm_commune.get())
        if self.stacker is not None and hasattr(self.stacker,
                                                "normalisation_commune"):
            self.stacker.normalisation_commune = self._norm_commune
        self._rafraichir_rendu = True
        self._refresh_preview()
        self.disp.notify_new_stack()

    def _lire_gains(self):
        """Gains R/G/B saisis (texte → float, virgule acceptée, défaut 1.0,
        borné 0..10). Appelé côté THREAD PRINCIPAL seulement (variables Tk) ;
        le thread worker consomme l'instantané `_compo_gains`."""
        gains = {}
        for canal in ("R", "G", "B"):
            try:
                v = float(self.var_compo_gains[canal].get().replace(",", "."))
            except (ValueError, AttributeError):
                v = 1.0
            gains[canal] = min(10.0, max(0.0, v))
        return gains

    def _start(self):
        """« ▶ Démarrer » = lancer l'EMPILEMENT (jalon 26).

        La caméra est déjà connectée (dès la détection) : ce bouton ne fait
        plus qu'armer une NOUVELLE session d'empilement — le reset complet
        est exécuté par le worker (`empilement_start_request`), qui reprend
        ensuite la lecture du flux. Les réglages pris AVANT (température,
        filtre, gain…) sont conservés."""
        if self.empilement_on:
            return
        # v2.41.0 : la source de FICHIERS suit l'INTERFACE — un dossier (ou une
        # composition) modifié APRÈS la connexion n'était jamais ouvert : la
        # caméra garde son dossier ET la mémoire des brutes déjà lues, d'où
        # « ▶ Démarrer » qui empilait encore la CIBLE PRÉCÉDENTE (constat
        # d'Alain, 28/09/2026). Elle est refermée AVANT de choisir la source,
        # puis rouverte juste après, sur la configuration AFFICHÉE — et, la
        # CIBLE changeant, les indices d'astrométrie de l'ancienne sont effacés
        # (ils feraient échouer la résolution de la nouvelle).
        if self._source_fichiers_obsolete():
            self._effacer_indices_astro()
            self._refermer_source_fichiers()
        try:
            if self.camera is None:
                cam = self._make_camera(self.var_source.get())
                if isinstance(cam, MultiFolderCamera) and \
                        composition_pour_roles(cam.roles) is None:
                    raise RuntimeError(
                        "Rôles de dossiers sans composition connue : "
                        + ", ".join(cam.roles))
                cam.open()
                # Jalon 32 (chemin de REPLI — la connexion automatique à la
                # détection n'a pas eu lieu) : mêmes capacités + UI aux
                # bornes réelles que les autres marques. open() est déjà
                # exécuté dans ce thread (comportement d'origine) ; la
                # détection est protégée (sonde muette → défauts, jamais
                # d'erreur).
                try:
                    self.capacites = cam.detecter_capacites()
                except Exception:
                    self.capacites = None
                self._adapter_ui_capacites(self.capacites)
                self.pending_settings = (self.expo_ms, self.gain_val)
                self.pending_offset = float(self.var_offset.get())
            else:
                cam = self.camera
        except Exception as e:
            messagebox.showerror("Caméra", str(e))
            return
        self.camera = cam
        self.cam_pilotee = cam if isinstance(cam, CAMERAS_PILOTEES) else None
        self.btn_deconnect.config(state="normal")
        # Jalon 19 : mode composition si la source est multi-dossiers — la
        # composition est déduite des rôles configurés (choix UI en phase 3).
        self._mode_compo = isinstance(cam, MultiFolderCamera)
        self._compo_nom = (composition_pour_roles(cam.roles)
                           if self._mode_compo else None)
        # Jalon 19 phase 3 : gains + radio « Canal L » instantanés POUR LE
        # THREAD (le worker n'a jamais le droit de lire les variables Tk).
        self._compo_gains = self._lire_gains()
        self._compo_mode_l = self.var_compo_mode_l.get()
        self._norm_commune = bool(self.var_norm_commune.get())   # v2.36.0
        # Jalon 54 : instantané du recalage Linear Fit pour le thread.
        self._fit_actif = bool(self.var_fit.get())
        self._fit_mode = self._code_fit_methode()
        # v2.41.0 : les remises à zéro de SESSION vivent désormais dans UNE
        # méthode (`_reinit_etat_session`), partagée avec « Réinitialiser
        # l'empilement », et elles sont posées AVANT d'armer la demande au
        # worker (`empilement_start_request`) : c'est la DEMANDE qui fait foi
        # (le worker les refait, dans son thread, sur les objets vivants).
        # Avant, l'UI les reposait APRÈS le démarrage du worker : elle pouvait
        # vider une archive que le worker venait d'écrire (archivage déclaré en
        # erreur pour toute la session).
        self._reinit_etat_session()
        self.empilement_on = False
        self.empilement_start_request = True          # reset + purge (worker)
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        # Jalon 19 : mode composition si la source est multi-dossiers — la
        # composition est déduite des rôles configurés (choix UI en phase 3).
        self._mode_compo = isinstance(cam, MultiFolderCamera)
        self._compo_nom = (composition_pour_roles(cam.roles)
                           if self._mode_compo else None)
        # Jalon 19 phase 3 : gains + radio « Canal L » instantanés POUR LE
        # THREAD (le worker n'a jamais le droit de lire les variables Tk).
        self._compo_gains = self._lire_gains()
        self._compo_mode_l = self.var_compo_mode_l.get()
        self._norm_commune = bool(self.var_norm_commune.get())   # v2.36.0
        self._fit_actif = bool(self.var_fit.get())   # jalon 54 (thread)
        self._fit_mode = self._code_fit_methode()    # jalon 54b (méthode)
        # v2.41.0 : les remises à zéro de session viennent d'être faites par
        # `_reinit_etat_session()` (avant l'armement de la demande au worker),
        # et le worker les refait de son côté : plus AUCUNE ici.
        # Ce qui vivait à cet endroit — `self.running = True` + un
        # `Thread(_worker).start()` INCONDITIONNEL — lançait un SECOND worker à
        # CHAQUE « ▶ Démarrer » : deux threads lisaient la même source et
        # écrivaient le même empilement. « ■ Arrêter » ne fait que mettre
        # l'empilement en pause (le worker reste en vie, c'est lui qui pilote la
        # caméra) ; la relance légitime est déjà assurée par le bloc
        # `if self.thread is None or not self.thread.is_alive()` ci-dessus.
        self.btn_save_proc.config(state="disabled")
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

    def _stop(self):
        """« ■ Arrêter » = PAUSE de l'empilement (jalon 26) : le worker
        reste actif (il continue de piloter la caméra — TEC, filtre,
        réglages) mais n'empile plus ; la caméra reste connectée et le
        refroidissement continue (on peut repartir au « ▶ Démarrer » sans
        rebrancher). Rappel limite SDK : le flux QHY ne redémarre pas dans
        le même process — relancer l'application si plus aucune frame."""
        self.empilement_on = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_deconnect.config(state="normal")
        self.lbl_status.config(
            text="Empilement arrêté — caméra connectée, refroidissement "
                 "maintenu.")

    def _reinit_etat_session(self):
        """Remises à zéro d'une SESSION NEUVE — communes à « ▶ Démarrer » et à
        « Réinitialiser l'empilement » (v2.41.0 : extraites de `_start`).

        Appelée depuis le thread Tk : elle ne touche NI la source (caméra), NI
        les réglages (exposition, filtre, TEC, indices d'astrométrie saisis),
        NI les variables Tk de l'empilement. Elle incrémente `_session` (ce qui
        invalide tout traitement externe en vol) et vide l'archive de session.

        Les MÊMES remises à zéro sont refaites dans le thread du worker (bloc
        `empilement_start_request`/`reset_request` de `_worker`) : ici, elles
        sont VISIBLES immédiatement, même si le worker ne tourne pas (source
        fermée, thread arrêté) — c'est ce qu'exige un bouton « Réinitialiser ».
        """
        self.aligner = StarAligner()
        self.stacker = None
        self.disp.reset()                      # stats d'affichage repartent de zéro
        self._vl_frames = None                 # le 1er empilement relancera le solveur
        self.bad_frames, self.fps = 0, 0.0
        self.floues_rejetees = 0              # jalon 17 : compteur de session
        self._fwhm_hist = []                  # jalon 17 : mesures de session neuve
        self._fwhm_par_role = {}              # jalon 19 : idem, PAR RÔLE (compo)
        self.seeing, self.seeing_msg = None, ""   # jalon 10 : nouvelle mesure
        self._seeing_t0 = 0.0                     # → dès la 1re frame
        self.disp.vl_seeing = None                # jalon 12 : PSF de la
                                                  # nouvelle session (aucune
                                                  # mesure héritée)
        self.show_stack = None
        self.last_show = None
        self._session += 1                     # invalide tout traitement externe en vol
        self._vider_archive()                  # jalon 15/16 : archive + scores de session neuve
        self.restack_request = False
        self._ref_score = self._ancre_score = None
        self._ancre_idx = None
        self._ancre_role = None
        self._restack_depuis = 0
        self.restack_info = ""            # jalon 18 : état dédié de session neuve
        self.restack_couleur = "#888888"
        self.restack_total = 0
        self.restack_hist = []
        # Jalon 56 : astrométrie de session neuve — les INDICES de la cible
        # (saisis ou lus) restent posés, le WCS résolu ne vaut plus rien.
        self.suivi_astro.reset()
        self.astro_info = ""
        self.astro_couleur = "#888888"
        self._astro_source = ""
        self._astro_wcs_secours = None       # repli ASTAP de l'ancienne session
        self._astro_aveugles = 0
        self._astro_dernier_aveugle = 0.0
        self._astro_fov_essayes = set()
        self._astro_balayage = None          # sonde des bases ASTAP refaite
        # Jalon 56 (étape 4) : photométrie de session neuve (les zéro-points
        # d'une autre cible/session n'ont aucun sens).
        self.photometrie.reset()
        self.photo_info = ""
        self.photo_couleur = "#888888"
        self._photo_essais = 0
        # Jalon 58 : même chose pour la SPCC absolue (coefficients d'une autre
        # cible ou d'une autre session = faux par construction).
        if getattr(self, "spcc", None) is not None:
            self.spcc.reset()
        self.spcc_info = ""
        self.spcc_couleur = "#888888"
        self._spcc_essais = 0
        self._spcc_dernier = 0.0
        self._photo_dernier = 0.0
        self._photo_gains_pose = {}
        self._maj_photo_vue()
        self._maj_astro_vue()
        self.proc_show = self.proc_full = None
        self.proc_entete = None               # v2.38.3
        self.proc_new = False
        self.save_asseen_request = None       # sauvegarde « tel que vu » annulée
        self.asseen_busy = False
        self.asseen_result = None
        self.asseen_titre = None
        self.msg_outils = None
        self.ext_request = False
        self.ext_busy = False
        self.ext_state = "idle"
        self.ext_t0 = None
        self._ext_popup = False
        # Jalon 26 : les contrôles caméra (filtre, TEC) vivent avec la
        # CONNEXION — ils ne sont PAS réinitialisés au démarrage de
        # l'empilement (on a pu refroidir et choisir le filtre avant).
        self.btn_save_proc.config(state="disabled")
        self.zoom, self.view_cx, self.view_cy = 1.0, None, None
        self._last_disp = None
        self.q = queue.Queue(maxsize=2)
        # Jalon 42/46 : une session neuve lit sa PREMIÈRE rafale tout de suite
        # (fenêtre de cadence réarmée) — sinon, après une remise à zéro tombée
        # au milieu d'une fenêtre, il faudrait attendre la cadence choisie
        # avant de voir la première brute de la nouvelle cible.
        self._prochaine_lecture = 0.0
        self._rafale_reste = self.RAFALE_MAX

    def _effacer_indices_astro(self):
        """Efface les INDICES d'astrométrie (AD, Dec, champ°) — décision d'Alain
        du 28/09/2026 : quand la source de FICHIERS change de CIBLE (autre
        dossier, autres rôles), les coordonnées de l'ancienne cible sont de
        FAUX indices et FONT ÉCHOUER la résolution de la nouvelle (le solveur
        cherche à l'ancien endroit du ciel).

        La saisie repart donc VIDE — ce qui rouvre au passage les deux chemins
        prévus : les indices lus dans l'en-tête des brutes du nouveau dossier
        (`_astro_indices_entete`), puis le repli ASTAP aveugle s'il est
        disponible. La ligne d'état DIT l'effacement : une saisie qui disparaît
        en silence serait un défaut de plus.
        """
        self.var_astro_ra.set("")
        self.var_astro_dec.set("")
        self.var_astro_champ.set("")
        suivi = getattr(self, "suivi_astro", None)
        if suivi is not None:
            suivi.effacer_indices()      # indices ET WCS de l'ancienne cible
        self._on_astro()                 # instantané (vide) + lignes d'état
        # `_on_astro` vient de poser « indices refusés — AD : … » : ce n'est pas
        # un refus de SAISIE mais un EFFACEMENT volontaire, on le dit ainsi.
        self._astro_msg_indices = ""
        self.astro_info = ("Astrométrie : indices effacés (nouvelle cible) — à "
                           "saisir, lus dans les brutes du dossier, ou repli "
                           "ASTAP")
        self.astro_couleur = "#888888"
        self._maj_astro_vue()

    def _reset_empilement(self):
        """« Réinitialiser l'empilement » — remise à zéro RÉELLE (v2.41.0).

        Constat réel d'Alain (28/09/2026) : « quand j'ai fini avec une cible, je
        ne peux pas enchaîner avec une autre en choisissant 1 ou des nouveaux
        dossiers et en cliquant sur Réinitialiser l'empilement… quand je clique
        sur Démarrer ça empile toujours la cible précédente » et « il faudrait
        que le bouton réinitialiser réinitialise vraiment ». Trois causes, les
        trois traitées ici :
          ① le drapeau de remise à zéro n'était lu par le worker qu'en
             TRAITANT une frame : à l'arrêt (empilement en pause, aucune brute
             qui arrive), cliquer ne réinitialisait RIEN. Il est désormais
             servi en TÊTE de boucle du worker, donc MÊME en pause ; et la
             remise à zéro visible est faite ici, dans le thread Tk, donc elle
             a lieu même si le worker ne tourne pas (source fermée, thread
             arrêté) ;
          ② la SOURCE de fichiers gardait son dossier ET la mémoire des brutes
             déjà lues : le dossier choisi ensuite n'était jamais ouvert, d'où
             une session suivante qui « empile encore la cible précédente ».
             Elle est refermée ici → « ▶ Démarrer » la rouvre sur la
             configuration AFFICHÉE (cf. `_refermer_source_fichiers`) ;
          ③ rien ne disait ce qui venait d'être fait et l'écran restait sur
             l'image de l'ancienne cible : l'écran est vidé (avec un message)
             et la ligne d'état annonce la suite ;
          ④ et, si le DOSSIER de la cible a changé, les INDICES d'astrométrie de
             l'ancienne sont EFFACÉS (décision d'Alain du 28/09/2026) : ils
             feraient chercher le solveur à l'ancien endroit du ciel. Même
             dossier = même cible : les indices sont GARDÉS.

        C'est une REMISE À ZÉRO, pas un démarrage : l'empilement reste en pause
        et « ▶ Démarrer » redevient accessible.
        """
        self.empilement_on = False             # plus rien ne s'ajoute
        self._reinit_etat_session()            # remises à zéro (thread Tk)
        self.reset_request = True              # …et les mêmes, côté worker
        # La CIBLE change-t-elle de dossier ? À évaluer AVANT de refermer la
        # source (après, il n'y a plus rien à comparer) : les indices
        # d'astrométrie de l'ancienne cible sont alors EFFACÉS — décision
        # d'Alain du 28/09/2026 — car ils feraient chercher le solveur à
        # l'ancien endroit du ciel. Même dossier = même cible : on les GARDE.
        cible_changee = self._source_fichiers_obsolete()
        if cible_changee:
            self._effacer_indices_astro()
        self._refermer_source_fichiers()       # la source suivra l'interface
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._vider_ecran("Empilement réinitialisé —\n« ▶ Démarrer » pour "
                          "repartir sur la cible choisie.")
        if self.camera is None:
            texte = ("Empilement réinitialisé — la source de fichiers a été "
                     "refermée : « ▶ Démarrer » la rouvrira "
                     + self._resume_source_fichiers() + ".")
        else:
            texte = ("Empilement réinitialisé — cliquez « ▶ Démarrer » pour "
                     "une session neuve (la caméra reste connectée).")
        if cible_changee:
            # Dit ICI aussi (et pas seulement sur la ligne d'astrométrie) : le
            # worker remet cette ligne-là à zéro au tour suivant, en consommant
            # sa demande — l'utilisateur doit le voir DURABLEMENT. Message court
            # (le libellé n'a pas de `wraplength` : une phrase à rallonge ferait
            # élargir la fenêtre).
            texte += "\nIndices d'astrométrie effacés (nouvelle cible)."
        self.lbl_status.config(text=texte)

    def _resume_source_fichiers(self):
        """Décrit, pour la ligne d'état, la source de FICHIERS qui sera ouverte
        au prochain « ▶ Démarrer » — jamais un silence sur ce qui sera lu
        (leçon du jalon 70 : une donnée absente ou une décision implicite doit
        être DITE). « le dossier « X » » (avec le rappel de l'option « images
        déjà présentes » quand elle est décochée), « les N dossiers (« Ha »,
        « O3 ») », ou la source telle quelle pour une caméra."""
        src = self.var_source.get()
        if src.startswith("Composition"):
            try:
                paires = self._lire_roles_dossiers()
            except RuntimeError:
                return "sur les dossiers des lignes de composition"
            return ("sur les %d dossiers (« %s »)"
                    % (len(paires), " », « ".join(r for r, _ in paires)))
        if src.startswith("Dossier"):
            d = self.var_folder.get().strip()
            if not d:
                return "sur le dossier à choisir (bouton « … »)"
            txt = ("sur le dossier « %s »"
                   % (os.path.basename(d.rstrip("/\\")) or d))
            if not self.var_process_existing.get():
                txt += (" — les brutes DÉJÀ présentes ne seront pas reprises "
                        "(case « Empiler aussi les images déjà présentes » "
                        "décochée)")
            return txt
        return "sur la source « %s »" % src

    def _source_fichiers_obsolete(self):
        """True si la source de FICHIERS connectée ne correspond PLUS à ce que
        montre l'interface (v2.41.0) : d'autres dossier(s), un autre rôle, ou
        l'option « Empiler aussi les images déjà présentes » qui a changé.

        POURQUOI COMPARER au lieu de refermer à chaque démarrage : la caméra
        d'un dossier garde la mémoire des brutes déjà vues (`_processed`) et de
        celles qui attendent ; la refermer la ferait repartir de ZÉRO (tout le
        dossier serait relu et re-empilé). On ne la referme donc que si la
        configuration a changé — c'est exactement le cas « nouvelle cible » —
        ou si elle est devenue invalide (l'erreur claire sortira alors du
        démarrage, au lieu d'être ignorée).
        """
        cam = self.camera
        if not isinstance(cam, (FolderCamera, MultiFolderCamera)):
            return False                       # caméra SDK : jamais touchée
        attendu = bool(self.var_process_existing.get())
        if isinstance(cam, MultiFolderCamera):
            try:
                paires = self._lire_roles_dossiers()
            except RuntimeError:
                return True                    # lignes incomplètes : à refaire
            if len(paires) != len(cam.cams):
                return True
            for (role, dossier), role_cam, sous in zip(paires, cam.roles,
                                                       cam.cams):
                if (role != role_cam
                        or not self._meme_dossier(dossier, sous.folder)
                        or bool(sous.process_existing) != attendu):
                    return True
            return False
        return (not self.var_source.get().startswith("Dossier")
                or not self._meme_dossier(self.var_folder.get().strip(),
                                          cam.folder)
                or bool(cam.process_existing) != attendu)

    @staticmethod
    def _meme_dossier(a, b):
        """Deux textes désignent-ils le même dossier ? Comparaison ABSOLUE et
        normalisée pour la casse : « C:\\brutes\\cible1 », « c:/brutes/cible1 »
        et « C:\\brutes\\cible1\\ » sont bien le même dossier — sans cela, une
        simple retouche du texte relancerait la lecture de tout le dossier."""
        if not a or not b:
            return False
        ka = os.path.normcase(os.path.abspath(os.path.expanduser(a)))
        kb = os.path.normcase(os.path.abspath(os.path.expanduser(b)))
        return ka == kb

    def _refermer_source_fichiers(self):
        """Referme la source de FICHIERS connectée (« Dossier surveillé » ou
        « Composition ») — v2.41.0. Le prochain « ▶ Démarrer » la rouvrira avec
        la configuration AFFICHÉE (nouveau dossier compris).

        Une caméra SDK n'est JAMAIS touchée : elle reste connectée (sa
        réouverture est impossible dans le même process — limite SDK connue,
        cf. QHY). → True si une source de fichiers a été refermée.
        """
        if not isinstance(self.camera, (FolderCamera, MultiFolderCamera)):
            return False
        try:
            self.camera.close()
        except Exception:
            pass                  # source déjà fermée / disparue : rien à faire
        self.camera = None
        self.cam_pilotee = None
        self._mode_compo = False
        self._compo_nom = None
        self.btn_deconnect.config(state="disabled")
        self.btn_start.config(state="normal")
        self.lbl_detect.config(text="")
        return True

    def _vider_ecran(self, texte=""):
        """Efface l'image affichée (v2.41.0) : après une remise à zéro, l'écran
        ne doit plus montrer l'empilement de la cible précédente. `texte` est
        posé au centre (jamais un écran muet — leçon des jalons 72/74)."""
        self._last_disp = None
        try:
            self.cv_img.delete("all")
            cw = self.cv_img.winfo_width() or self.W_IMG
            ch = self.cv_img.winfo_height() or self.H_IMG
            if texte:
                self.cv_img.create_text(cw // 2, ch // 2, text=texte,
                                        fill="#888888",
                                        width=max(80, cw - 40))
        except tk.TclError:           # fenêtre en cours de destruction
            pass

    def _deconnecter_camera(self):
        """« ⏏ Déconnecter » (jalon 26) : referme la caméra — le TEC est
        coupé avant (un refroidissement laissé en régulation continue de
        consommer du courant et de givrer)."""
        if self.running:
            self._stop()
        cam = self.cam_pilotee or (self.camera
                                   if isinstance(self.camera, QHYCamera)
                                   else None)
        if cam is not None:
            try:
                cam.arreter_refroidissement()
            except Exception:
                pass        # caméra déjà fermée / TEC absent : rien à faire
        self.cam_pilotee = None
        if self.camera:
            self.camera.close()
            self.camera = None
        self.btn_start.config(state="disabled")
        self.btn_deconnect.config(state="disabled")
        self.cb_filtre.config(state="disabled")
        self.btn_tec_on.config(state="disabled")
        self.btn_tec_off.config(state="disabled")
        # Jalon 31 : retour aux valeurs par défaut (la prochaine connexion
        # relancera la détection et reconstruira les bornes réelles).
        self.capacites = None
        self._EXPO_DYN = None
        self.tec_plage = None
        # Jalon 34 : le libellé de la case revient à l'échelle fixe (900 s).
        self._maj_libelle_expo_longue()
        self._filtres_dispo = FILTRES_ROUE
        self.cb_filtre.config(values=list(FILTRES_ROUE))
        self.lbl_tec_lib.config(text="Consigne °C :")
        self.lbl_tec.config(text="Capteur : — · TEC : —", foreground="#888888")
        self.lbl_detect.config(text="")
        self._qhy_id = ""
        self.lbl_status.config(text="Caméra déconnectée.")

    def _on_close(self):
        self._sauver_config_app()
        # Déconnexion SIMPLE (version du 19/09, décision d'Alain du
        # 20/09/2026) : le worker est arrêté D'ABORD (running=False, jonction
        # bornée) pour qu'aucun appel natif ne soit concurrent au close ;
        # la caméra est refermée ici même (arrêt du TEC d'abord — un
        # refroidissement laissé en régulation givre le capteur). Le seul
        # échec possible est SDK-spécifique (QHY : l'état du process reste
        # occupé, mais l'application se ferme et l'OS libère le handle USB).
        self.empilement_on = False
        self.running = False
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        cam = self.cam_pilotee or self.camera
        if cam is not None:
            try:
                cam.arreter_refroidissement()
            except Exception:
                pass
            try:
                cam.close()
            except Exception:
                pass
        self.archive.vider()      # jalon 15 : dossier temp des frames supprimé
        self.root.destroy()

    def _save(self):
        if not self.running or self.stacker is None or self.stacker.n == 0:
            messagebox.showinfo("Enregistrer", "Aucun empilement à enregistrer.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")])
        if path:
            self.save_request = path  # la sauvegarde est faite par le thread d'acquisition

    def _gx_live_prete(self, titre):
        """Contrôle AVANT toute sauvegarde pleine résolution : si le retrait de
        gradient live est actif et que sa commande est incomplète, la chaîne ne
        peut pas être reproduite — message clair et abandon (jamais de fichier
        « presque comme vu »). → True si l'on peut continuer."""
        if (self.disp.stretch == "veralux" and self.disp.vl_graxpert
                and not gx_live.commande_valide(self.disp.vl_graxpert_cmd)):
            messagebox.showwarning(
                "GraXpert live",
                "Commande GraXpert absente ou incomplète — impossible de "
                "reproduire la chaîne live.\nVérifiez la commande dans "
                "« Traitement externe ».")
            return False
        return True

    def _reglages_rendu(self):
        """Capture des réglages de la chaîne de sortie DANS le thread principal
        (jalon 5) : le thread de sauvegarde ne lira JAMAIS les variables
        Tkinter, et l'état de `disp` (curseurs, solveur) continue de vivre
        pendant le rendu. Inclut, depuis le chantier du 24/09/2026, les
        CORRECTIONS DE COULEUR (`corr_*`) appliquées en pleine résolution."""
        d = self.disp
        reglages = dict(
            stretch=d.stretch, auto=d.auto, sigma_k=d.sigma_k, target=d.target,
            black=d.black, white=d.white, gamma=d.gamma, saturation=d.saturation,
            vl_mode_res=d.vl_mode_res, vl_target_bg=d.vl_target_bg,
            vl_log_d=d.vl_log_d, vl_profil=d.vl_profil,
            vl_log_d_resolu=d.vl_log_d_resolu,
            vl_graxpert=d.vl_graxpert, vl_graxpert_cmd=d.vl_graxpert_cmd,
            vl_denoise=d.vl_denoise, vl_denoise_methode=d.vl_denoise_methode,
            vl_denoise_force=d.vl_denoise_force,
            vl_scnr=d.vl_scnr, vl_demagenta=d.vl_demagenta,
            vl_scnr_doux=d.vl_scnr_doux,
            vl_neutre_fond=bool(d.vl_neutre_fond),   # v2.36.1
            # v2.37.0 : réduction du bruit chromatique (case + force).
            vl_chroma=bool(d.vl_chroma),
            vl_chroma_force=float(d.vl_chroma_force),
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma, en pixels PLEINE
            # RÉSOLUTION — le rendu pleine résolution l'utilise TEL QUEL (l'écran,
            # lui, le ramène à l'échelle de l'aperçu : `_poser_rayon_chroma`).
            vl_chroma_rayon_ref=float(self.rayon_chroma_ref),
            vl_sharp=d.vl_sharp, vl_sharp_iterations=d.vl_sharp_iterations,
            # Jalon 75 : étage de niveaux (barres de l'histogramme) et
            # saturation par couleur — SANS ces clés, « tel que vu » ne serait
            # pas ce qui est à l'écran (règle du projet : le fichier = l'écran).
            bar_noir=float(d.bar_noir), bar_median=float(d.bar_median),
            bar_blanc=float(d.bar_blanc),
            sat_canaux=tuple(float(v) for v in d.sat_canaux),
            # Étirement GELÉ (⏹) : le rendu pleine résolution recalcule les
            # stats sur l'image complète — il doit utiliser les MÊMES stats
            # gelées que l'affichage, sinon le fichier dériverait de l'écran.
            stats_gelees=(d._stats if d.fige else None))
        st = self.stacker
        if st is not None:
            # NB : en MONO, l'empilement porte AUSSI des corrections (équilibrage
            # et recalage s'appliquent à une image couleur d'un dossier OSC) —
            # on les transporte donc quelle que soit la classe de stacker, pour
            # que « empilement traité (linéaire) » corresponde à l'affichage.
            reglages.update(
                corr_gains=(dict(st.gains_effectifs())
                            if hasattr(st, "gains_effectifs") else None),
                corr_wb=bool(getattr(st, "wb_auto", False)),
                corr_wb_force=float(getattr(st, "wb_force", 1.0)),
                corr_cadre=getattr(st, "cadre", None),
                corr_fit=bool(getattr(st, "linear_fit", False)),
                corr_fit_mode=getattr(st, "linear_fit_mode", "offset"))
        return reglages

    def _save_asseen(self):
        """Jalon 5 — « 💾 Enregistrer tel que vu (étiré) » : sauvegarde la vue
        courante (empilement ou traitée) RENDUE comme à l'écran, en PLEINE
        résolution (jamais l'aperçu 1600 px) : chaîne complète stack →
        GraXpert live si activé (vue « empilement » ; en vue « traitée »,
        l'image a déjà subi le traitement externe) → débruitage live si
        activé (jalon 9) → netteté live si activée (jalon 12) → étirement
        STF/manuel ou VeraLux → gamma/saturation. Le bouton d'enregistrement
        LINÉAIRE reste inchangé. Le rendu (plusieurs secondes possibles) part
        dans un thread dédié via _worker — comme un traitement externe."""
        if self.asseen_busy or self.save_asseen_request is not None:
            messagebox.showinfo("Enregistrer tel que vu",
                                "Un enregistrement est déjà en cours — patientez.")
            return
        if not self.running or self.stacker is None or self.stacker.n == 0:
            messagebox.showinfo("Enregistrer tel que vu",
                                "Aucun empilement à enregistrer.")
            return
        vue = self.var_view.get()
        if vue == "traitée" and self.proc_full is None:
            messagebox.showinfo(
                "Enregistrer tel que vu",
                "Aucun résultat traité — cliquez d'abord « ⚡ Traiter "
                "l'empilement courant ».")
            return
        if not self._gx_live_prete("tel que vu"):
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"),
                       ("PNG 16 bits", "*.png")])
        if not path:
            return
        self.asseen_titre = "Enregistrer tel que vu"
        self.save_asseen_request = (path, vue, self._reglages_rendu(), False)

    def _save_traite_lineaire(self):
        """Chantier 24/09/2026 (décision (a) d'Alain) — « 💾 Enregistrer
        l'empilement traité (linéaire)… » : 3e sortie LINÉAIRE. Elle contient ce
        que la vue « empilement » a subi AVANT l'étirement : empilement BRUT →
        GraXpert live (gradient) si activé → débruitage live si activé →
        CORRECTIONS DE COULEUR (gains SPCC/Gaia/manuels, équilibrage des
        canaux, recalage Linear Fit) → netteté live si activée → chaîne couleur
        (SCNR…). C'est le fichier « prêt à traiter » dans un logiciel externe,
        intermédiaire entre l'empilement brut et l'image « tel que vu » (aucun
        étirement, aucun gamma/saturation). Réglages capturés dans le thread
        principal ; le rendu part dans le thread de sauvegarde, comme « tel que
        vu » (l'acquisition continue)."""
        titre = "Enregistrer l'empilement traité (linéaire)"
        if self.asseen_busy or self.save_asseen_request is not None:
            messagebox.showinfo(titre, "Un enregistrement est déjà en cours — "
                                       "patientez.")
            return
        if not self.running or self.stacker is None or self.stacker.n == 0:
            messagebox.showinfo(titre, "Aucun empilement à enregistrer.")
            return
        if not self._gx_live_prete(titre):
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"),
                       ("PNG 16 bits", "*.png")])
        if not path:
            return
        self.asseen_titre = titre
        self.save_asseen_request = (path, "pile", self._reglages_rendu(), True)

    def _couches_brutes(self):
        """Couches BRUTES recadrées (dict rôle → carte 2D) pour la chaîne par
        couche, ou None hors composition (mono : une seule image)."""
        st = self.stacker
        if st is None or not hasattr(st, "moyennes"):
            return None
        try:
            return st.moyennes()
        except Exception:
            return None

    def _couches_pleine_resolution(self, canaux, reglages):
        """Chaîne PAR COUCHE en pleine résolution — identique à celle du
        solveur live (jalon 24) : GraXpert live puis débruitage live sur CHAQUE
        couche 2D, puis recomposition (composer) et CORRECTIONS de couleur.

        POURQUOI par couche : GraXpert live et le débruitage live sont
        contractés pour des images de [0..1] (cf. `external.live.appliquer` et
        `denoise`) — les COUCHES le sont, le COMPOSITE non : la normalisation
        par rôle laisse un cœur d'étoile monter bien au-dessus de 1 (mesuré :
        17,94 sur l'empilement M31 d'Alain, 165 frames). Appliquer ces outils au
        composite le rescalait (GraXpert normalise sa sortie) et l'ÉCRÊTAIT (le
        NLM fait `clip(0, 1)` : 96 % des pixels > 1 perdus à la mesure) : le
        fichier n'était plus linéaire. Par couche, tout reste ≤ 1 et le
        composite recomposé garde son échelle.

        → (composite corrigé, message) ; jamais d'exception (les erreurs d'outil
        sont remontées en message et l'appelant décide)."""
        traites, msgs = {}, []
        for role, couche in canaux.items():
            c = np.asarray(couche, dtype=np.float32)
            if reglages.get("vl_graxpert"):
                if float(np.max(np.abs(c))) < 1e-9:
                    msgs.append(f"GraXpert live ({role}) : couche vide — "
                                "ignorée")
                else:
                    c2, err = gx_live.appliquer(c, reglages["vl_graxpert_cmd"])
                    if err:
                        msgs.append(f"GraXpert live ({role}) : {err}")
                    else:
                        c = c2
            if reglages.get("vl_denoise"):
                c2, err = denoiser_local.denoiser(
                    c, reglages.get("vl_denoise_methode", "nlm"),
                    reglages.get("vl_denoise_force", 0.5))
                if err:
                    msgs.append(f"Débruitage live ({role}) : {err}")
                else:
                    c = c2
            traites[role] = c
        try:
            comp = composition_mod.composer(
                traites, self.stacker.composition,
                mode_l=self.stacker.mode_l,
                normalisation_commune=bool(getattr(
                    self.stacker, "normalisation_commune", False)))
        except Exception as exc:
            return None, f"Recomposition impossible : {exc}"
        if comp is None:
            return None, "Recomposition impossible (aucune couche exploitable)"
        comp, _diag = composition_mod.corrections_couleur(
            comp,
            gains=reglages.get("corr_gains"),
            wb_auto=bool(reglages.get("corr_wb", False)),
            wb_force=float(reglages.get("corr_wb_force", 1.0)),
            cadre=reglages.get("corr_cadre"),
            linear_fit=bool(reglages.get("corr_fit", False)),
            linear_fit_mode=reglages.get("corr_fit_mode", "offset"))
        return comp, " ; ".join(msgs)

    def _save_asseen_thread(self, path, vue, source, reglages, session,
                            lineaire=False, canaux=None):
        """Thread de sauvegarde « tel que vu » (jalon 5) : GraXpert live si
        activé (vue « empilement » uniquement), puis débruitage/netteté live,
        puis rendu pleine résolution identique à l'affichage, puis écriture du
        fichier. AUCUN appel Tk ici : le résultat est consommé par _tick
        (messagebox thread-safe).

        `lineaire=True` (chantier 24/09/2026) : MÊME chaîne, mais elle s'arrête
        AVANT l'étirement et écrit l'image LINÉAIRE (bornée [0,1], en-tête FITS
        AUTO-DESCRIPTIF) — c'est la 3e sortie « empilement traité (linéaire) ».

        `canaux` (couches BRUTES) : en COMPOSITION et vue « empilement », la
        chaîne GraXpert/débruitage est faite PAR COUCHE (cf.
        `_couches_pleine_resolution`) — sans quoi le composite (> 1) serait
        rescalé et écrêté par des outils contractés pour [0..1]. Le composite
        est alors déjà corrigé : les corrections ne sont pas réappliquées."""
        corrige = False
        try:
            if (vue == "pile" and canaux
                    and (reglages.get("vl_graxpert")
                         or reglages.get("vl_denoise"))):
                comp, msg = self._couches_pleine_resolution(canaux, reglages)
                if comp is None:
                    self.asseen_result = f"ERREUR: {msg}"
                    return
                if msg:
                    self.msg_outils = msg     # erreurs d'outil non bloquantes
                source = comp
                corrige = True
            if not corrige and vue == "pile" and reglages.get("vl_graxpert"):
                gx, err = gx_live.appliquer(source, reglages["vl_graxpert_cmd"])
                if err:
                    # On ne sauvegarde PAS une image « presque comme vue » :
                    # échec GraXpert = échec de la sauvegarde (message clair).
                    self.asseen_result = f"ERREUR: GraXpert live : {err}"
                    return
                source = gx
            # Jalon 9 : le débruitage live fait partie de la chaîne affichée
            # (stack → GX → débruitage → étirement) — reproduit ici en pleine
            # résolution pour que le fichier corresponde à l'écran.
            if not corrige and vue == "pile" and reglages.get("vl_denoise"):
                img_dn, err = denoiser_local.denoiser(
                    source, reglages.get("vl_denoise_methode", "nlm"),
                    reglages.get("vl_denoise_force", 0.5))
                if err:
                    self.asseen_result = f"ERREUR: Débruitage live : {err}"
                    return
                source = img_dn
            # --- CHANTIER 24/09/2026 (décision (c) d'Alain) : les CORRECTIONS
            # DE COULEUR s'appliquent ICI, après le débruitage et AVANT la
            # netteté — c'est l'ordre de la chaîne de sortie. Seule la 3e sortie
            # LINÉAIRE en a besoin, et seulement si la chaîne par couche ne les
            # a pas déjà appliquées (elle finit par `corrections_couleur`).
            if lineaire and not corrige:
                source, _diag = composition_mod.corrections_couleur(
                    source,
                    gains=reglages.get("corr_gains"),
                    wb_auto=bool(reglages.get("corr_wb", False)),
                    wb_force=float(reglages.get("corr_wb_force", 1.0)),
                    cadre=reglages.get("corr_cadre"),
                    linear_fit=bool(reglages.get("corr_fit", False)),
                    linear_fit_mode=reglages.get("corr_fit_mode", "offset"))
            # Jalon 12 : la netteté live fait aussi partie de la chaîne
            # affichée (stack → GX → débruitage → netteté → étirement).
            # ⚠️ La PSF est MESURÉE ici, en pleine résolution (aucun `mesure=`
            # transmis) : celle du live est exprimée en pixels de l'APERÇU,
            # réduit sur les gros capteurs — l'utiliser telle quelle fausserait
            # la déconvolution du fichier.
            if vue == "pile" and reglages.get("vl_sharp"):
                img_net, err = nettete_live.deconvoluer(
                    source,
                    iterations=reglages.get("vl_sharp_iterations",
                                            nettete_live.ITERATIONS_DEFAUT))
                if err:
                    self.asseen_result = f"ERREUR: Netteté live : {err}"
                    return
                source = img_net
            # Jalon 22/23 : la chaîne couleur fait aussi partie de la chaîne
            # affichée (… → netteté → SCNR → SCNR doux → démagenta →
            # étirement).
            if vue == "pile" and reglages.get("vl_scnr"):
                source = couleurs_mod.scnr(source)
            if vue == "pile" and reglages.get("vl_scnr_doux"):
                source = couleurs_mod.scnr_doux(source)
            if vue == "pile" and reglages.get("vl_demagenta"):
                source = couleurs_mod.demagenta(source)
            if lineaire:
                # 3e sortie LINÉAIRE (« empilement traité ») : on écrit l'image
                # telle quelle, bornée [0,1] comme la sauvegarde brute, AVEC
                # l'en-tête auto-descriptif de la chaîne de sortie — aucun
                # étirement, aucun gamma/saturation.
                if session != self._session:   # session relancée entre-temps
                    return
                entete = self._astro_entete_sauvegarde(
                    {"FILTER": self.filtre_courant} if self.filtre_courant
                    else None, source.shape[:2] if source is not None else None)
                entete.update(self._entete_reglages(applique=True))
                entete["AVAVUE"] = ("empilement TRAITE (lineaire, sans "
                                    "etirement)")
                img, entete = borner_lineaire(source, entete)
                save_image(path, img, entete=entete)
                self.dernier_applicatif = entete.get("AVAAPPLI")
                self.asseen_result = path
                return
            # v2.36.1 : neutralisation de la couleur du fond, JUSTE AVANT
            # l'étirement — UNIQUEMENT pour un étirement VeraLux (c'est son
            # ANCRE qui amplifie la couleur du fond ; le STF étire avec une
            # seule transformation sur la luminance, donc n'est pas concerné) et
            # JAMAIS pour la 3e sortie LINÉAIRE ci-dessus, qui doit rester
            # « empilement + corrections » (verrouillé par le banc jalon 59 [6]).
            # Même ordre que dans le solveur live : le fichier « tel que vu » est
            # identique à l'écran.
            if (vue == "pile" and reglages.get("vl_neutre_fond")
                    and reglages.get("stretch") == "veralux"):
                source = couleurs_mod.neutraliser_fond(source)
            # v2.37.0 : réduction du bruit chromatique — APRÈS la neutralisation
            # (un gain par canal) et juste AVANT l'étirement, comme dans le
            # solveur live ; elle aussi réservée à l'étirement VeraLux (en STF,
            # l'aperçu ne l'applique pas : le fichier doit être identique à
            # l'écran) et JAMAIS dans la 3e sortie linéaire ci-dessus.
            if (vue == "pile" and reglages.get("vl_chroma")
                    and reglages.get("stretch") == "veralux"):
                source = couleurs_mod.reduire_bruit_chroma(
                    source, force=float(reglages.get("vl_chroma_force") or 0.5),
                    # v2.37.4 : rayon de RÉFÉRENCE, pleine résolution (l'image
                    # rendue ici est en pleine résolution — l'aperçu, lui, est
                    # ramené à son échelle par `_poser_rayon_chroma`).
                    rayon=float(reglages.get("vl_chroma_rayon_ref")
                                or couleurs_mod.RAYON_CHROMA_DEFAUT))
            rendu = self.disp.rendu_pleine_resolution(source, reglages)
            if session != self._session:    # session relancée entre-temps
                return
            # v2.38.3 : en vue « traitée », cette image VIENT de la chaîne
            # externe (c'était le SEUL fichier sans aucune traçabilité).
            entete = None
            if vue == "traitée":
                entete = self._entete_externe()
                entete["AVAVUE"] = ("resultat traite externe, tel que vu "
                                    "(ETIRE)")
            save_image(path, rendu, entete=entete)
            self.asseen_result = path
        except Exception as e:
            self.asseen_result = f"ERREUR: {e}"
        finally:
            self.asseen_busy = False

    def _load_dark(self):
        # Jalon 53 : la couche se choisit AU CLIC (boîte « ce dark
        # s'applique à : ») — hors composition, cible unique directe.
        cible = self._choisir_cible("dark")
        if cible is None:
            return
        p = filedialog.askopenfilename(filetypes=[
            ("Images", "*.fits *.fit *.fts *.png *.tif *.tiff *.jpg *.jpeg"), ("Tous", "*.*")])
        if p:
            try:
                role = None if cible == "unique" else cible
                self.calib.load_dark(p, role=role)
                self._maj_libelles_calib()
                msg = (f"Dark{' pour « ' + role + ' »' if role else ''} "
                       f"chargé : {p}")
                if self.running:
                    msg += "  —  pensez à « Réinitialiser l'empilement » pour que tout soit calibré pareil"
                self.lbl_status.config(text=msg)
            except Exception as e:
                messagebox.showerror("Dark", str(e))

    def _load_flat(self):
        # Jalon 53 : cible INDÉPENDANTE de celle des darks (ex. flat par
        # filtre et dark unique, ou l'inverse).
        cible = self._choisir_cible("flat")
        if cible is None:
            return
        p = filedialog.askopenfilename(filetypes=[
            ("Images", "*.fits *.fit *.fts *.png *.tif *.tiff *.jpg *.jpeg"), ("Tous", "*.*")])
        if p:
            try:
                role = None if cible == "unique" else cible
                self.calib.load_flat(p, role=role)
                self._maj_libelles_calib()
                msg = (f"Flat{' pour « ' + role + ' »' if role else ''} "
                       f"chargé : {p}")
                if self.running:
                    msg += "  —  pensez à « Réinitialiser l'empilement » pour que tout soit calibré pareil"
                self.lbl_status.config(text=msg)
            except Exception as e:
                messagebox.showerror("Flat", str(e))

    def _clear_calib(self):
        self.calib.clear()
        self._maj_libelles_calib()

    # ------------------------------------------------------------ traitement externe
    def _champs_outils(self):
        """Les trois (variable Tk, libellé, nom) du cadre « Traitement externe »."""
        return ((self.var_cmd_graxpert, self.lbl_etat_graxpert, "GraXpert"),
                (self.var_cmd_graxpert_dn, self.lbl_etat_gx_dn,
                 "GraXpert (débruitage)"),
                (self.var_cmd_bxt, self.lbl_etat_bxt, "BlurXTerminator"))

    def _sonder_outils(self, commandes):
        """SONDE les trois outils (accès disque) → [(nom, manque, binaire)].

        `commandes` est un instantané [(nom, texte)] pris côté Tk (v2.38.11) :
        la sonde peut ainsi tourner HORS du thread d'interface (thread de mesures,
        borné) — c'est elle qui balaie le PATH et des dossiers, donc elle qui
        pouvait se bloquer sur un NAS injoignable."""
        etats = []
        for nom, cmd in commandes:
            manque = gx_live.outil_manquant(cmd)
            etats.append((nom, manque, "" if manque else gx_live.binaire_de(cmd)))
        return etats

    def _maj_etat_outils(self, *_a):
        """Affiche l'état de DÉTECTION des outils externes (v2.38.5).

        Constat d'Alain (27/09/2026, installateur Linux) : « la détection de
        l'emplacement de GraXpert ne s'est pas faite » — et personne ne
        pouvait le voir : la commande de repli (« graxpert … », binaire nu,
        aucune détection réussie) contient les placeholders attendus, donc
        elle passait pour bonne, et l'échec n'apparaissait qu'à l'exécution
        (« command not found » du shell, noyé dans la sortie de l'outil).
        Chaque ligne dit maintenant OÙ est l'outil, ou qu'il est introuvable.

        v2.38.11 : appelée sur un GESTE de l'utilisateur (champ modifié) — elle
        sonde donc ici ; au démarrage, la sonde est faite par le thread de
        mesures borné et l'affichage passe par `_appliquer_etats_outils`."""
        commandes = [(nom, var.get().strip())
                     for var, _lbl, nom in self._champs_outils()]
        self._appliquer_etats_outils(self._sonder_outils(commandes))

    def _appliquer_etats_outils(self, etats):
        """Affiche [(nom, manque, binaire)] — thread d'interface seulement."""
        for (_var, lbl, nom), (_n, manque, binaire) in zip(self._champs_outils(),
                                                           etats):
            if manque:
                lbl.config(text=f"⚠ {nom} : {manque} — bouton « … » pour le "
                                "désigner", foreground="#c98a00")
            else:
                lbl.config(text=f"✔ {nom} : {binaire}", foreground="#1d7f1d")

    # ------------------------------------ mesures de disque DIFFÉRÉES (v2.38.11)
    def _annoncer_mesures(self):
        """Pose les libellés « mesure en cours… » AVANT les sondes différées.

        L'utilisateur voit ainsi que l'application regarde — et si une sonde ne
        répond pas (montage réseau NAS), la ligne reste HONNÊTE au lieu de
        garder un ancien texte qui mentirait."""
        for _var, lbl, nom in self._champs_outils():
            lbl.config(text=f"{nom} : mesure en cours…", foreground="#888888")
        if getattr(self, "lbl_travail", None) is not None:
            self.lbl_travail.config(text="dossier de travail : mesure en cours…",
                                    foreground="#888888")
        if getattr(self, "lbl_cat_dossier", None) is not None:
            self.lbl_cat_dossier.config(text="Catalogues : mesure en cours…",
                                        foreground="#888888")

    def _commandes_outils(self):
        """Instantané [(nom, texte)] des trois commandes, pris CÔTÉ TK."""
        return [(nom, var.get().strip())
                for var, _lbl, nom in self._champs_outils()]

    def _premieres_mesures(self):
        """Mesures de disque du démarrage, HORS du fil d'interface (v2.38.11)."""
        self._demander_mesures(nettoyage=True)

    def _demander_mesures(self, nettoyage=False):
        """Lance les sondes de disque dans un FIL DÉMON, chacune bornée à 5 s.

        POURQUOI (constat RÉEL du 27/09/2026) : une sonde sur un dossier monté
        par le réseau (NAS) ATTEND indéfiniment quand ce réseau est filtré — elle
        ne doit donc ni empêcher l'ouverture (les sondes sont différées APRÈS
        l'affichage), ni figer l'interface (fil démon + délai). Les résultats
        passent par `self._mesures` et sont appliqués par `_tick`, dans le fil
        d'interface. Une seule salve à la fois."""
        if getattr(self, "_mesure_en_cours", False):
            return
        self._mesure_en_cours = True
        commandes = self._commandes_outils()

        def _fond():
            msg = {}
            try:
                if nettoyage:
                    journal.etape("nettoyage des résidus de session")
                    msg["recyclage"] = delais.borne(
                        travail.nettoyer_orphelins, (0, 0), delais.DELAI_DEFAUT)[0]
                journal.etape("dossier de travail")
                msg["travail"] = delais.borne(self._sonder_travail,
                                              ("", -1, False), delais.DELAI_DEFAUT)[0]
                # Outils : DÉTECTION puis re-détection d'un binaire disparu
                # (v2.38.5 : binaire repris, OPTIONS conservées), et seulement
                # ensuite la sonde d'état — pour que l'affichage corresponde aux
                # commandes réellement en place.
                journal.etape("détection des outils externes")
                detectes = delais.borne(detecter_outils, None, delais.DELAI_DEFAUT)[0]
                if detectes:
                    # La re-détection sonde ELLE AUSSI le disque (`outil_manquant`
                    # par commande) : elle est donc bornée comme le reste.
                    msg["commandes"] = delais.borne(
                        lambda: self._commandes_rafraichies(commandes, detectes),
                        {}, delais.DELAI_DEFAUT)[0]
                else:
                    msg["commandes"] = {}
                journal.etape("état des outils externes")
                a_sonder = [(nom, (msg["commandes"].get(cle) or txt).strip())
                            for cle, nom, txt in (
                                ("cmd_graxpert", "GraXpert", commandes[0][1]),
                                ("cmd_graxpert_dn", "GraXpert (débruitage)",
                                 commandes[1][1]),
                                ("cmd_bxt", "BlurXTerminator", commandes[2][1]))]
                msg["outils"] = delais.borne(
                    lambda: self._sonder_outils(a_sonder), None, delais.DELAI_DEFAUT)[0]
                journal.etape("dossiers des catalogues")
                msg["catalogues"] = delais.borne(self._sonder_catalogues,
                                                 ("", None, ""), delais.DELAI_DEFAUT)[0]
                # Jalon 77 : la base de profils SPCC suit le même chemin (elle
                # peut être dans la configuration d'AVAStack, dans un dossier
                # choisi — donc sur un NAS — ou chez Siril).
                journal.etape("base de profils SPCC")
                msg["spcc"] = delais.borne(self._sonder_spcc_base,
                                           ("", None, False),
                                           delais.DELAI_DEFAUT)[0]
            except Exception:
                journal.erreur("mesures de démarrage")
            finally:
                self._mesures.put(msg)

        threading.Thread(target=_fond, daemon=True,
                         name="mesures-disque").start()

    def _commandes_rafraichies(self, commandes, detectes):
        """Re-détection (v2.38.5, déplacée ici en v2.38.11) : une commande dont
        l'EXÉCUTABLE a disparu est corrigée — le binaire est repris de la
        détection, les OPTIONS de l'utilisateur sont CONSERVÉES
        (`remplacer_binaire`), donc installer GraXpert après coup suffit sans
        perdre -correction/-smoothing/-strength.

        PURE : `commandes` = [(nom, texte)] persisté, `detectes` = {clé: texte}
        calculé par `detecter_outils()` dans le fil de mesures borné.
        → {clé: texte corrigé} (vide si rien ne change, pour ne rien écraser)."""
        cles = ("cmd_graxpert", "cmd_graxpert_dn", "cmd_bxt")
        out = {}
        for (nom, txt), cle in zip(commandes, cles):
            det = (detectes.get(cle) or "").strip()
            txt = (txt or "").strip()
            if txt and det and gx_live.outil_manquant(txt):
                out[cle] = gx_live.remplacer_binaire(txt, det)
        return out

    def _appliquer_mesures(self, msg):
        """Applique les résultats d'une salve de mesures (fil d'interface)."""
        self._mesure_en_cours = False
        # Commandes corrigées par la re-détection (binaire retrouvé/disparu) :
        # posées AVANT l'affichage des états, qui les reflète.
        for cle, txt in (msg.get("commandes") or {}).items():
            var = {"cmd_graxpert": getattr(self, "var_cmd_graxpert", None),
                   "cmd_graxpert_dn": getattr(self, "var_cmd_graxpert_dn", None),
                   "cmd_bxt": getattr(self, "var_cmd_bxt", None)}.get(cle)
            if var is not None and txt:
                var.set(txt)
        recy = msg.get("recyclage")
        if recy and recy[0]:
            self._travail_recycle = recy
            journal.note("démarrage", "%d dossier(s) de travail recyclés (%s)"
                         % (recy[0], travail.texte_octets(recy[1])))
        travail_info = msg.get("travail")
        if travail_info:
            self._appliquer_travail_vue(*travail_info)
        if msg.get("outils"):
            self._appliquer_etats_outils(msg["outils"])
        cat = msg.get("catalogues")
        if cat:
            self._appliquer_cat_vue(*cat)
        spcc_base = msg.get("spcc")
        if spcc_base:
            self._appliquer_spcc_base_vue(*spcc_base)

    def _sonder_travail(self):
        """SONDE le dossier de travail (accès disque) → (dossier, libre, ram).

        Séparée de l'affichage pour pouvoir tourner HORS du thread d'interface,
        bornée (v2.38.11) : si le dossier est sur un NAS injoignable, cette sonde
        attend indéfiniment — elle ne doit donc pas retenir la fenêtre.
        → `("", -1, False)` si le dossier est illisible."""
        try:
            d = travail.dossier_travail()
        except Exception:
            return ("", -1, False)
        return (d, travail.espace_libre(d), travail.est_tmpfs(d))

    def _maj_travail_vue(self):
        """Ligne « dossier de travail » (v2.38.6) : le dossier RÉELLEMENT utilisé
        pour les fichiers lourds (frames archivées, FITS des outils), son espace
        libre, et l'alerte « en RAM » s'il s'agit d'un tmpfs.

        Constat du 27/09/2026 : `/tmp` (tmpfs 4,6 Go) s'est rempli pendant une
        chaîne BlurX → écriture partielle d'un FITS → « 24962352 requested and
        10902832 written », message incompréhensible et AUCUNE indication du
        dossier utilisé. Cette ligne est la réponse : ce que l'application écrit,
        où elle l'écrit, et combien d'espace il reste.

        v2.38.11 : sonde ET affiche — appelée par un GESTE (bouton 📂) ; au
        démarrage c'est le thread de mesures borné qui sonde."""
        d, libre, ram = self._sonder_travail()
        self._appliquer_travail_vue(d, libre, ram)

    def _appliquer_travail_vue(self, d, libre, ram):
        """Affiche la ligne (thread d'interface). `libre = -1` : espace NON mesuré
        (accès disque bloqué — montage réseau NAS ?) : on le DIT."""
        if getattr(self, "lbl_travail", None) is None:
            return
        if not d:
            self.lbl_travail.config(
                text="dossier de travail : ILLISIBLE / non mesuré — un accès "
                     "disque bloque (montage réseau NAS ?)",
                foreground="#d04040")
            return
        txt = f"dossier de travail : {d}"
        if libre > 0:
            txt += f" — {travail.texte_octets(libre)} libres"
        elif libre < 0:
            txt += " — espace NON MESURÉ (accès disque bloqué ?)"
        if ram:
            txt += " ⚠ en RAM (tmpfs) : préférez un disque"
            col = "#c98a00"
        elif libre > 0 and libre < (1 << 30):
            txt += " ⚠ presque plein"
            col = "#c98a00"
        else:
            col = "#888888"
        recy = getattr(self, "_travail_recycle", None)
        if recy and recy[0]:
            txt += (f" · {recy[0]} dossier(s) recyclés "
                    f"({travail.texte_octets(recy[1])})")
        self.lbl_travail.config(text=txt, foreground=col)

    def _choisir_dossier_travail(self):
        """Choisit le dossier de travail et le PERSISTE (config
        `dossier_travail`) : c'est là que vont les frames archivées et les FITS
        des outils externes. Le volume choisi peut être un disque de données."""
        # v2.38.11 : aperçu de départ BORNÉ (le dossier de travail peut être sur
        # un NAS injoignable) — la boîte de dialogue s'ouvre quoi qu'il arrive.
        depart = delais.borne(travail.dossier_travail,
                              os.path.expanduser("~"),
                              delais.DELAI_DEFAUT)[0]
        d = filedialog.askdirectory(
            title="Dossier de travail (fichiers temporaires lourds)",
            initialdir=depart)
        if not d:
            return
        CONFIG["dossier_travail"] = d
        sauver_config(dict(CONFIG))
        self._maj_travail_vue()
        libre = travail.espace_libre(d)
        messagebox.showinfo(
            "Dossier de travail",
            "Les fichiers de travail (frames archivées, FITS des étapes "
            f"d'outils) seront écrits dans :\n{d}\n\n"
            f"Espace libre : {travail.texte_octets(libre)}"
            + ("\n\n⚠ Ce dossier est sur un volume de RAM (tmpfs) : il peut "
               "saturer en pleine session — un disque vaut mieux."
               if travail.est_tmpfs(d) else ""))

    def _ouvrir_dossier_travail(self):
        """Ouvre le dossier de travail dans le gestionnaire de fichiers : c'est
        là que se trouvent les fichiers CONSERVÉS après l'échec d'une chaîne
        externe (FITS d'entrée, sorties d'étape, journal `outils_sortie.txt`
        de l'outil) — de quoi comprendre ce qui s'est passé."""
        d = travail.dossier_travail()
        err = travail.ouvrir_dossier(d)
        if err:
            messagebox.showwarning("Dossier de travail",
                                   f"Impossible d'ouvrir « {d} » :\n{err}")

    def _ouvrir_journal(self):
        """Ouvre le JOURNAL de l'application (v2.38.7) : démarrages, erreurs
        d'interface, échecs journalisés — c'est LE fichier à regarder (et à
        envoyer) quand quelque chose ne va pas, en particulier quand la fenêtre
        ne s'ouvre pas du tout."""
        chemin = journal.chemin_journal()
        err = journal.ouvrir()
        if err:                              # aucun outil associé : le dire
            messagebox.showwarning(
                "Journal",
                f"Impossible d'ouvrir le journal :\n{err}\n\nLe fichier est :\n"
                f"{chemin}")

    def _pick_exe(self, var):
        """Sélectionne l'exécutable d'un outil externe et le place en tête de
        la commande — les options déjà saisies ({input}, {output}…) sont
                conservées telles quelles."""
        p = filedialog.askopenfilename(
            title="Exécutable de l'outil",
            filetypes=[("Exécutables", "*.exe *.bat *.cmd *.py" if IS_WINDOWS
                        else "*.py *.sh *.AppImage"),
                       ("Tous les fichiers", "*.*")])
        if not p:
            return
        cmd = var.get().strip()
        rest = ""                                  # options existantes à conserver
        if cmd.startswith('"'):
            end = cmd.find('"', 1)
            if end != -1:
                rest = cmd[end + 1:].strip()
        elif cmd:
            parts = cmd.split(None, 1)
            rest = parts[1] if len(parts) > 1 else ""
        var.set(f'"{p}"' + (f" {rest}" if rest else ""))

    def _request_ext(self):
        """Demande un traitement externe sur l'empilement courant (lancé par le worker)."""
        if not self.running or self.stacker is None or self.stacker.n == 0:
            messagebox.showinfo("Traitement externe", "Aucun empilement à traiter.")
            return
        if self.ext_busy:
            messagebox.showinfo("Traitement externe",
                                "Un traitement est déjà en cours — patientez.")
            return
        if not (self.var_ext_graxpert.get() or self.var_ext_dn.get()
                or self.var_ext_bxt.get() or self.var_ext_scnr.get()
                or self.var_ext_scnr_doux.get()
                or self.var_ext_demagenta.get()
                or self.var_ext_neutre.get()            # v2.37.1
                or self.var_ext_chroma.get()):          # v2.37.1
            messagebox.showinfo("Traitement externe",
                                "Cochez au moins un traitement.")
            return
        # v2.38.5 : dire AVANT de lancer (des minutes de calcul) qu'un outil
        # est introuvable — l'échec n'arrivait jusque-là qu'à SON étape, sous
        # la forme d'un « command not found » noyé dans la sortie de l'outil.
        manques = []
        for actif, var, nom in (
                (self.var_ext_graxpert.get(), self.var_cmd_graxpert,
                 "GraXpert (gradient)"),
                (self.var_ext_dn.get() and self.DN_EXT_CODES.get(
                    self.var_dn_methode.get(), "graxpert") == "graxpert",
                 self.var_cmd_graxpert_dn, "GraXpert (débruitage)"),
                (self.var_ext_bxt.get(), self.var_cmd_bxt,
                 "BlurXTerminator")):
            if not actif:
                continue
            m = gx_live.outil_manquant(var.get().strip())
            if m:
                manques.append(f"• {nom} : {m}")
        if manques:
            messagebox.showwarning(
                "Traitement externe",
                "Outil externe introuvable — le traitement échouerait :\n\n"
                + "\n".join(manques)
                + "\n\nRéglez le chemin avec le bouton « … » du cadre "
                  "« Traitement externe (long) ».")
            return
        # Capture des réglages ici (thread principal) : le thread externe ne
        # touchera pas aux variables Tkinter. Méthode de débruitage : la
        # force est injectée DANS la commande GraXpert (source de vérité =
        # curseur, l'Entry n'est jamais modifiée) ; pour ondelettes/NLM la
        # force est transportée telle quelle (étape locale, en mémoire).
        mode_dn = self.DN_EXT_CODES.get(self.var_dn_methode.get(), "graxpert")
        cmd_dn = (commande_avec_strength(self.var_cmd_graxpert_dn.get().strip(),
                                         self.var_dn_force.get())
                  if mode_dn == "graxpert" else "")
        self.ext_job = (self.var_ext_graxpert.get(),
                        self.var_cmd_graxpert.get().strip(),
                        self.var_ext_dn.get(),
                        cmd_dn,
                        self.var_ext_bxt.get(),
                        self.var_cmd_bxt.get().strip(),
                        mode_dn,
                        self.var_dn_force.get(),
                        # Jalon 22/23 : chaîne couleur EN FIN de chaîne,
                        # dans l'ordre d'application — SCNR classique,
                        # SCNR doux (bruit seul), démagenta.
                        self.var_ext_scnr.get(),
                        self.var_ext_scnr_doux.get(),
                        self.var_ext_demagenta.get(),
                        # v2.37.1 : corrections PRÉ-ÉTIREMENT de la chaîne live
                        # (12e/13e éléments + la force en 14e) — déballage
                        # tolérant côté thread de traitement. La force est
                        # CAPTURÉE ici (curseur « Couleur live ») : le thread
                        # externe ne lit jamais une variable Tk.
                        self.var_ext_neutre.get(),
                        self.var_ext_chroma.get(),
                        float(self.disp.vl_chroma_force),
                        # v2.37.4 : RAYON DE RÉFÉRENCE du flou de chroma
                        # (15e élément), en pixels PLEINE RÉSOLUTION — la chaîne
                        # externe travaille à cette résolution, elle l'utilise
                        # tel quel. Capturé ici : le thread de traitement ne lit
                        # JAMAIS une variable Tk.
                        float(self.rayon_chroma_ref))
        self.ext_request = True
        self._set_ext_msg("Traitement demandé…", state="busy")
        self.btn_ext.config(state="disabled")

    def _set_ext_msg(self, txt, state=None):
        """Message d'état du traitement externe (thread-safe : simple attribut
        relu par _tick, jamais un widget directement depuis un thread).
        state : 'busy' (en cours), 'ok' (terminé), 'error' (échec → popup)."""
        self.ext_msg = txt
        if state:
            self.ext_state = state
            if state == "busy":
                self.ext_t0 = time.time()
            if state == "error":
                self._ext_popup = True

    def _save_proc(self):
        if self.proc_full is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")])
        if path:
            try:
                # v2.27.1 : même garantie d'échelle que la sauvegarde de
                # l'empilement linéaire (un résultat d'outil externe peut
                # lui aussi dépasser 1 : le borner évite un fichier que les
                # lecteurs supposant [0,1] afficheraient « saturé »).
                img, entete = borner_lineaire(self.proc_full,
                                              dict(self.proc_entete or {}))
                save_image(path, img, entete=entete)
                messagebox.showinfo("Enregistrer", f"Résultat traité sauvegardé :\n{path}")
            except Exception as e:
                messagebox.showerror("Enregistrer", str(e))

    def _run_external(self, stack, n_frames, session):
        """Chaîne les outils externes (GraXpert → BlurXTerminator) sur un
        instantané de l'empilement. Tourne en thread séparé : l'acquisition
        continue pendant ce temps. Le résultat n'affecte QUE l'affichage (vue
        « traitée ») et la sauvegarde dédiée — l'empilement accumulé reste
        linéaire et intact.

        Jalon 24 (décision d'Alain, 19/09/2026) : en mode COMPOSITION, le
        gradient et le débruitage sont faits PAR COUCHE (la pollution
        lumineuse et la lune ne frappent pas pareil selon le filtre ; le
        modèle de fond de GraXpert ne doit voir que des couches mono 2D —
        élimine aussi le canal-mort SHO sans S, cf. jalon 23b) ; BXT et la
        chaîne couleur restent sur le composite. Voir _run_external_compo.

        Placeholders des commandes :
          {input}   → fichier FITS d'entrée (instantané de l'empilement, float 32F)
          {output}  → chemin de sortie complet, extension .fits
          {outbase} → chemin de sortie SANS extension (GraXpert : -output)
        Le fichier réellement produit est retrouvé automatiquement (_find_output),
        quelle que soit son extension ou son suffixe (-bxt, _GraXpert…), et un
        éventuel miroir vertical est corrigé (_auto_unflip)."""
        tmp = None
        try:
            # Jalon 24 : en composition, chaîne PAR COUCHE (gradient +
            # débruitage sur chaque couche 2D, recomposition, puis BXT +
            # chaîne couleur sur le composite).
            if self._mode_compo and hasattr(self.stacker,
                                            "mean_avec_canaux") \
                    and len(self.ext_job) > 11 \
                    and (self.ext_job[0] or self.ext_job[2]):
                comp, canaux = self.stacker.mean_avec_canaux()
                if comp is not None and canaux:
                    self._run_external_compo(comp, canaux, n_frames, session)
                    return
            (use_gx, cmd_gx, use_dn, cmd_dn, use_bxt, cmd_bxt,
             mode_dn, force_dn) = self.ext_job[:8]
            # Jalon 22/23 : chaîne couleur transportée dans le job (9e, 10e
            # et 11e éléments — ordre d'application). Déballage TOLÉRANT
            # (8 éléments = tout False) pour compatibilité des tests qui
            # fabriquent des jobs 8-tuple (jalons 7/14).
            scnr_actif = bool(self.ext_job[8]) if len(self.ext_job) > 8 \
                else False
            sd_actif = bool(self.ext_job[9]) if len(self.ext_job) > 9 \
                else False
            dm_actif = bool(self.ext_job[10]) if len(self.ext_job) > 10 \
                else False
            # v2.37.1 : corrections pré-étirement de la chaîne LIVE (12e, 13e et
            # 14e éléments du job — déballage tolérant : les jobs antérieurs n'en
            # ont pas → inactives). Ordre d'application identique au live :
            # … → démagenta → neutralisation du fond → réduction du bruit
            # chromatique, juste avant l'étirement d'affichage.
            nf_ext = bool(self.ext_job[11]) if len(self.ext_job) > 11 else False
            chroma_ext = bool(self.ext_job[12]) if len(self.ext_job) > 12 \
                else False
            force_chroma_ext = (float(self.ext_job[13])
                                if len(self.ext_job) > 13 else 0.5)
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma (15e élément —
            # déballage tolérant : les jobs antérieurs n'en ont pas → rayon de
            # référence, soit le comportement de la v2.37.3).
            rayon_chroma_ext = (float(self.ext_job[14])
                                if len(self.ext_job) > 14
                                else couleurs_mod.RAYON_CHROMA_DEFAUT)
            steps = []
            if use_gx:
                steps.append(("GraXpert gradient", "cmd", cmd_gx))
            if use_dn:
                if mode_dn == "graxpert":
                    # Débruitage GraXpert IA (jalon 7, remis le 16/09/2026) :
                    # étape SUBPROCESS comme les autres, LONGUE (minutes).
                    steps.append(("GraXpert débruitage", "cmd", cmd_dn))
                else:
                    # Jalon 8 : débruitage LOCAL (ondelettes à trous ou
                    # Non-local means) en numpy/OpenCV, quelques secondes —
                    # étape EN MÉMOIRE entre les étapes subprocess.
                    libelle = ("Ondelettes à trous" if mode_dn == "ondelettes"
                               else "Non-local means")
                    steps.append((f"Débruitage local ({libelle})",
                                  "dn_local", None))
            if use_bxt:
                steps.append(("BlurXTerminator", "cmd", cmd_bxt))
            for name, kind, cmd in steps:
                if kind == "cmd" and ("{input}" not in cmd
                                      or ("{output}" not in cmd
                                          and "{outbase}" not in cmd)):
                    self._set_ext_msg(f"Commande {name} incomplète : il manque "
                                      "{{input}} ou {output}/{outbase}.", state="error")
                    return
            tmp = travail.creer_dossier("avastack_")
            # v2.38.6 : la chaîne écrit PLUSIEURS FITS de la taille de l'image
            # (entrée + une par étape). On vérifie l'espace AVANT d'écrire et on
            # REFUSE en une phrase chiffrée, plutôt que de remplir le volume à la
            # 3e étape après plusieurs minutes de calcul (constat du 27/09/2026 :
            # « 24962352 requested and 10902832 written » sur un /tmp plein).
            ok_esp, msg_esp = travail.verifier_espace(
                tmp, int(np.asarray(stack).nbytes) * (len(steps) + 2),
                f"la chaîne externe ({len(steps)} étape(s) + fichiers de "
                "travail)")
            if not ok_esp:
                self._set_ext_msg(msg_esp, state="error")
                return
            cur = os.path.join(tmp, "stack.fits")
            # Jalon 14 : les outils externes (GraXpert, et BXT côté PixInsight)
            # lisent le FITS avec les CANAUX sur NAXIS3 ((C, H, W) côté
            # astropy). Le save_image standard ((H, W, C) → NAXIS1=3) est MAL
            # LU et fait planter GraXpert dans cv2.resize
            # (« !dsize.empty() », boîte modale cx_Freeze) — constat réel
            # d'Alain le 17/09/2026 sur empilement RGB (Uranus-C Pro). Parade
            # déjà éprouvée du chemin live (external/live.py) : écrire
            # canaux-en-tête. Le mono 2D n'est pas concerné.
            gx_live._ecrire_entree(cur, stack)
            journal = os.path.join(tmp, "outils_sortie.txt")

            def run_step(name, cmd_tpl, src, outbase):
                cmd = (cmd_tpl.replace("{input}", src)
                              .replace("{output}", outbase + ".fits")
                              .replace("{outbase}", outbase))
                self._set_ext_msg(f"{name} en cours… ({n_frames} frames)", state="busy")
                # Jalon 14 : lanceur « survivable » (piège documenté du
                # 14/09/2026) — sorties dans un FICHIER et kill de
                # l'ARBORESCENCE au délai : un outil qui plante affiche sa
                # boîte modale puis meurt, au lieu de bloquer
                # subprocess.run(capture_output) pour toujours (le kill ne
                # touchait que cmd.exe, pas GraXpert).
                code, err = gx_live._run_bloquant_survivable(cmd, tmp, 1800)
                if err:
                    self._set_ext_msg(f"Erreur {name} : {err}", state="error")
                    return None
                if code != 0:
                    lignes = []
                    try:
                        with open(journal, encoding="utf-8",
                                  errors="replace") as f:
                            lignes = [l for l in f.read().splitlines() if l.strip()]
                    except OSError:
                        pass
                    detail = lignes[-1] if lignes else "aucun message"
                    self._set_ext_msg(f"Erreur {name} (code {code}) : {detail}",
                                      state="error")
                    return None
                res = find_output(src, outbase)      # extension/suffixe quelconques
                if res is None:
                    self._set_ext_msg(f"Erreur {name} : fichier de sortie introuvable "
                                      "(l'outil n'a rien écrit)", state="error")
                    return None
                return res

            for i, (name, kind, cmd_tpl) in enumerate(steps):
                outbase = os.path.join(tmp, f"step{i}")
                if kind == "dn_local":
                    # Jalon 8 : étape locale EN MÉMOIRE (pas de subprocess) —
                    # l'image courante est relue, débruitée (numpy/OpenCV)
                    # puis réécrite pour l'outil suivant de la chaîne.
                    self._set_ext_msg(f"{name} en cours… ({n_frames} frames)",
                                      state="busy")
                    # Jalon 14 : lecture normalisée ((3,H,W) → (H,W,3)) pour
                    # le débruiteur, réécriture canaux-en-tête pour l'outil
                    # suivant (cf. convention FITS des outils externes).
                    img_cur = gx_live._lire_sortie(cur)
                    img_dn, err = denoiser_local.denoiser(img_cur, mode_dn,
                                                          force_dn)
                    if err:
                        self._set_ext_msg(f"Erreur {name} : {err}",
                                          state="error")
                        return
                    cur = outbase + ".fits"
                    gx_live._ecrire_entree(cur, img_dn)
                    continue
                res = run_step(name, cmd_tpl, cur, outbase)
                if res is None:
                    return
                # Jalon 14 : normalise la sortie de l'outil ((3, H, W) →
                # (H, W, 3) le cas échéant) puis la réécrit canaux-en-tête
                # pour l'étape SUIVANTE — chaque outil reçoit la même
                # convention, quelle que soit celle de son prédécesseur.
                img_out = gx_live._lire_sortie(res)
                cur = outbase + "_conv.fits"
                gx_live._ecrire_entree(cur, img_out)

            img = gx_live._lire_sortie(cur)
            img = auto_unflip(img, stack)     # corrige un éventuel miroir vertical
            # Jalon 23b : sortie d'outil DÉGÉNÉRÉE (pixels non finis, image
            # vide — cf. le « plus d'image » en SHO sans S) → erreur claire
            # au lieu d'un résultat noir en visu / sauvegardé.
            if (not np.isfinite(img).all()
                    or float(np.max(np.abs(img))) < 1e-9):
                self._set_ext_msg("Erreur : sortie dégénérée de l'outil "
                                  "(pixels non finis ou image vide)",
                                  state="error")
                return
            # Jalon 22/23 : chaîne couleur (opt-in) — EN FIN de chaîne
            # externe, sur l'image COULEUR du résultat (no-op si mono),
            # juste avant l'étirement d'affichage (décision d'Alain).
            # Ordre : SCNR classique → SCNR doux (bruit seul) → démagenta.
            if scnr_actif:
                img = couleurs_mod.scnr(img)
            if sd_actif:
                img = couleurs_mod.scnr_doux(img)
            if dm_actif:
                img = couleurs_mod.demagenta(img)
            # v2.37.1 : NEUTRALISATION DU FOND puis RÉDUCTION DU BRUIT
            # CHROMATIQUE — les deux corrections pré-étirement de la chaîne live,
            # au même rang qu'elle (elles corrigent ce que l'ANCRE de VeraLux
            # amplifie ensuite : sa soustraction transforme 2 % d'écart de ciel
            # en un fond franc bleu, et les gains multiplicatifs — SPCC en tête —
            # amplifient le grain du canal qu'ils montent). Gains ANNONCÉS dans
            # le message final, comme dans « État des calculs » du live.
            gains_fond_ext = None
            if nf_ext:
                gains_fond_ext = couleurs_mod.gains_fond(img)
                if gains_fond_ext is not None \
                        and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                    img = couleurs_mod.neutraliser_fond(img)
            if chroma_ext:
                img = couleurs_mod.reduire_bruit_chroma(
                    img, force=force_chroma_ext, rayon=rayon_chroma_ext)
            if session != self._session:             # session relancée entre-temps
                return
            self.proc_full = img                     # pleine résolution (sauvegarde)
            # v2.38.3 : la chaîne QUI A PRODUIT ce résultat (outils et leurs
            # paramètres) est consignée dans l'en-tête du fichier enregistré.
            self.proc_entete = self._entete_externe(n_frames)
            h, w = img.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                img = cv2.resize(img, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            self.proc_show = img                     # version allégée (affichage)
            self.proc_new = True
            detail_fond = ""
            if gains_fond_ext is not None \
                    and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                detail_fond = (" · fond neutralisé (R %.4f / G %.4f / B %.4f)"
                               % gains_fond_ext)
            self._set_ext_msg(f"Traité à {time.strftime('%H:%M:%S')} "
                              f"({n_frames} frames){detail_fond}", state="ok")
        except Exception as e:
            self._set_ext_msg(f"Erreur : {e}", state="error")
        finally:
            self._fin_ext_tmp(tmp, session)

    def _fin_ext_tmp(self, tmp, session):
        """Fin de chaîne externe : nettoyage du dossier de travail — SAUF en cas
        d'échec, où il est CONSERVÉ et annoncé (v2.38.6).

        POURQUOI : le dossier était supprimé quoi qu'il arrive, donc le journal
        de l'outil (`outils_sortie.txt`), les FITS d'entrée et les sorties
        d'étape disparaissaient avec l'erreur — le « requested and written » du
        27/09/2026 était indiagnosticable. Un dossier VIDÉ (échec avant toute
        écriture) est supprimé comme avant (rien à conserver)."""
        try:
            if tmp is None:
                pass
            elif self.ext_state == "error":
                vide = True
                try:
                    vide = not os.listdir(tmp)
                except OSError:
                    vide = True
                if vide:
                    shutil.rmtree(tmp, ignore_errors=True)
                else:
                    self.ext_msg = (f"{self.ext_msg} — fichiers de travail "
                                    f"conservés : {tmp}")
            else:
                shutil.rmtree(tmp, ignore_errors=True)
        finally:
            if session == self._session:
                self.ext_busy = False

    def _run_external_compo(self, comp, canaux, n_frames, session):
        """Chaîne externe PAR COUCHE (jalon 24, décision d'Alain du 19/09/2026) :
        sur un instantané de la composition — GraXpert gradient et débruitage
        exécutés sur CHAQUE couche 2D (FITS mono — plus de piège RGB jalon 14),
        composite re-fait depuis les couches traitées, PUIS BXT et la chaîne
        couleur (SCNR…) sur le composite, comme la chaîne mono. Échec d'une
        étape sur une couche = la couche brute passe à la suite, message
        signalé — jamais de blocage, jamais d'image perdue. Même contrat de
        thread que _run_external (ext_busy géré par son finally)."""
        tmp = None
        try:
            (use_gx, cmd_gx, use_dn, cmd_dn, use_bxt, cmd_bxt,
             mode_dn, force_dn) = self.ext_job[:8]
            scnr_actif = bool(self.ext_job[8]) if len(self.ext_job) > 8 \
                else False
            sd_actif = bool(self.ext_job[9]) if len(self.ext_job) > 9 \
                else False
            dm_actif = bool(self.ext_job[10]) if len(self.ext_job) > 10 \
                else False
            # v2.37.1 : corrections pré-étirement de la chaîne live (12e/13e/14e
            # éléments — voir _run_external ; déballage tolérant).
            nf_ext = bool(self.ext_job[11]) if len(self.ext_job) > 11 else False
            chroma_ext = bool(self.ext_job[12]) if len(self.ext_job) > 12 \
                else False
            force_chroma_ext = (float(self.ext_job[13])
                                if len(self.ext_job) > 13 else 0.5)
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma (15e élément —
            # déballage tolérant, comme la chaîne mono).
            rayon_chroma_ext = (float(self.ext_job[14])
                                if len(self.ext_job) > 14
                                else couleurs_mod.RAYON_CHROMA_DEFAUT)
            tmp = travail.creer_dossier("avastack_compo_")
            journal = os.path.join(tmp, "outils_sortie.txt")
            n_etapes = ((len(canaux) if use_gx else 0)
                        + (len(canaux) if use_dn and mode_dn == "graxpert"
                           else 0))
            # v2.38.6 : espace vérifié AVANT d'écrire (entrée + une sortie par
            # étape) — refus chiffré et immédiat plutôt qu'un volume saturé en
            # pleine chaîne. Placé APRÈS `n_etapes` (piège attrapé par le banc
            # jalon 24 : un `NameError` ici était avalé par le `except` et
            # l'échec apparaissait… en silence).
            ok_esp, msg_esp = travail.verifier_espace(
                tmp, int(np.asarray(comp).nbytes) * (n_etapes + 2),
                f"la chaîne externe par couche ({n_etapes} étape(s))")
            if not ok_esp:
                self._set_ext_msg(msg_esp, state="error")
                return
            i_etape, msgs = 0, []
            traites = self._compo_couches_traitees(
                canaux, use_gx, cmd_gx, use_dn, cmd_dn, mode_dn, force_dn,
                tmp, journal, n_frames, n_etapes, msgs)
            if traites is None:
                return                      # erreur déjà posée par _ext_run_cmd
            comp_traite = composition_mod.composer(
                traites, self.stacker.composition,
                mode_l=self.stacker.mode_l,
                # v2.36.0 : même normalisation que la vue live — sinon la sortie
                # traitée ne serait pas au même niveau que l'écran.
                normalisation_commune=bool(getattr(
                    self.stacker, "normalisation_commune", False)))
            if comp_traite is None:
                self._set_ext_msg("Erreur : recomposition impossible après "
                                  "traitement par couche", state="error")
                return
            comp_traite = np.asarray(comp_traite, dtype=np.float32)
            # Chantier 24/09/2026 (décision (b)) : les CORRECTIONS DE COULEUR de
            # la chaîne de sortie s'appliquent ICI, sur le composite re-fait
            # depuis les couches traitées — exactement comme le solveur live.
            # Les couches, elles, restent BRUTES (contrat jalon 54).
            gains_ext = (self.stacker.gains_effectifs()
                         if hasattr(self.stacker, "gains_effectifs")
                         else self.stacker.gains)
            comp_traite, _d = composition_mod.corrections_couleur(
                comp_traite,
                gains=gains_ext,
                wb_auto=bool(getattr(self.stacker, "wb_auto", False)),
                wb_force=float(getattr(self.stacker, "wb_force", 1.0)),
                cadre=getattr(self.stacker, "cadre", None),
                linear_fit=bool(getattr(self.stacker, "linear_fit", False)),
                linear_fit_mode=getattr(self.stacker, "linear_fit_mode",
                                        "offset"))
            # --- Suite de la chaîne SUR LE COMPOSITE : BXT et chaîne couleur
            # — identique à la fin de la chaîne mono.
            cur = os.path.join(tmp, "comp_traite.fits")
            gx_live._ecrire_entree(cur, comp_traite)
            if use_bxt:
                outbase = os.path.join(tmp, "bxt")
                res = self._ext_run_cmd("BlurXTerminator", cmd_bxt, cur,
                                        outbase, tmp, journal, n_frames)
                if res is None:
                    return
                cur = res
            img = gx_live._lire_sortie(cur)
            img = auto_unflip(img, comp)
            if (not np.isfinite(img).all()
                    or float(np.max(np.abs(img))) < 1e-9):
                self._set_ext_msg("Erreur : sortie dégénérée de l'outil "
                                  "(pixels non finis ou image vide)",
                                  state="error")
                return
            if scnr_actif:
                img = couleurs_mod.scnr(img)
            if sd_actif:
                img = couleurs_mod.scnr_doux(img)
            if dm_actif:
                img = couleurs_mod.demagenta(img)
            # v2.37.1 : neutralisation du fond puis réduction du bruit
            # chromatique (chaîne live) — sur le COMPOSITE re-fait, comme les
            # SCNR ; les couches restent brutes (contrat jalon 54).
            gains_fond_ext = None
            if nf_ext:
                gains_fond_ext = couleurs_mod.gains_fond(img)
                if gains_fond_ext is not None \
                        and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                    img = couleurs_mod.neutraliser_fond(img)
            if chroma_ext:
                img = couleurs_mod.reduire_bruit_chroma(
                    img, force=force_chroma_ext, rayon=rayon_chroma_ext)
            if session != self._session:      # session relancée entre-temps
                return
            self.proc_full = img
            self.proc_entete = self._entete_externe(n_frames)   # v2.38.3
            h, w = img.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                img = cv2.resize(img, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            self.proc_show = img
            self.proc_new = True
            if gains_fond_ext is not None \
                    and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                msgs.append("fond neutralisé (R %.4f / G %.4f / B %.4f)"
                            % gains_fond_ext)
            detail = (" ; ".join(msgs) + " — ") if msgs else ""
            self._set_ext_msg(f"{detail}Traité par couche à "
                              f"{time.strftime('%H:%M:%S')} ({n_frames} "
                              "frames)", state="ok" if not msgs else "busy")
        except Exception as e:
            self._set_ext_msg(f"Erreur : {e}", state="error")
        finally:
            self._fin_ext_tmp(tmp, None)

    def _compo_couches_traitees(self, canaux, use_gx, cmd_gx, use_dn, cmd_dn,
                                mode_dn, force_dn, tmp, journal, n_frames,
                                n_etapes, msgs):
        """Boucle PAR COUCHE du traitement externe (jalon 24) : gradient
        (subprocess) puis débruitage (subprocess GraXpert IA, ou local en
        mémoire numpy/OpenCV) sur chaque couche 2D du dossier temporaire.
        → dict rôle → couche traitée, ou None (erreur d'un subprocess :
        message déjà posé, chaîne arrêtée — même politique que la chaîne
        mono ; les échecs SANS subprocess dégénèrent en couche brute +
        message et la chaîne continue)."""
        traites = {}
        i_etape = 0
        for role, couche in canaux.items():
            c = np.asarray(couche, dtype=np.float32)
            src = os.path.join(tmp, f"in_{role}.fits")
            gx_live._ecrire_entree(src, c)
            if use_gx:
                if float(np.max(np.abs(c))) < 1e-9:
                    msgs.append(f"GraXpert ({role}) : couche vide — ignorée")
                else:
                    i_etape += 1
                    outbase = os.path.join(tmp, f"gx_{role}")
                    res = self._ext_run_cmd(
                        f"GraXpert gradient {role}", cmd_gx, src, outbase,
                        tmp, journal, n_frames, f" ({i_etape}/{n_etapes})")
                    if res is None:
                        return None
                    c2 = auto_unflip(gx_live._lire_sortie(res), c)
                    if (not np.isfinite(c2).all()
                            or float(np.max(np.abs(c2))) < 1e-9):
                        msgs.append(f"GraXpert ({role}) : sortie dégénérée — "
                                    "couche brute conservée")
                    else:
                        c = c2.astype(np.float32)
                        src = os.path.join(tmp, f"in2_{role}.fits")
                        gx_live._ecrire_entree(src, c)
            if use_dn:
                if mode_dn == "graxpert":
                    i_etape += 1
                    outbase = os.path.join(tmp, f"dn_{role}")
                    res = self._ext_run_cmd(
                        f"GraXpert débruitage {role}", cmd_dn, src, outbase,
                        tmp, journal, n_frames, f" ({i_etape}/{n_etapes})")
                    if res is None:
                        return None
                    c2 = auto_unflip(gx_live._lire_sortie(res), c)
                    if (not np.isfinite(c2).all()
                            or float(np.max(np.abs(c2))) < 1e-9):
                        msgs.append(f"Débruitage ({role}) : sortie dégénérée "
                                    "— couche brute conservée")
                    else:
                        c = c2.astype(np.float32)
                else:
                    c2, err = denoiser_local.denoiser(c, mode_dn, force_dn)
                    if err:
                        msgs.append(f"Débruitage ({role}) : {err}")
                    else:
                        c = c2
            traites[role] = c
        return traites

    def _ext_run_cmd(self, name, cmd_tpl, src, outbase, tmp, journal,
                     n_frames, progression=""):
        """Une étape SUBPROCESS de la chaîne externe (jalon 24) : lanceur
        « survivable » partagé avec la chaîne mono, progression par étape.
        → chemin du fichier de sortie, ou None (message d'erreur déjà posé)."""
        # Validation du GABARIT AVANT substitution (après, les placeholders
        # n'existent plus — leçon du débogage du jalon 24).
        if ("{input}" not in cmd_tpl or ("{output}" not in cmd_tpl
                                         and "{outbase}" not in cmd_tpl)):
            self._set_ext_msg(f"Commande {name} incomplète : il manque "
                              "{{input}} ou {output}/{outbase}.", state="error")
            return None
        # v2.38.5 : outil introuvable = échec ANNONCÉ (au lieu d'un « command
        # not found » du shell, noyé dans la sortie de l'outil et illisible).
        manque = gx_live.outil_manquant(cmd_tpl)
        if manque:
            self._set_ext_msg(
                f"{name} : {manque} — désignez l'exécutable avec le bouton "
                "« … » du cadre « Traitement externe (long) ».",
                state="error")
            return None
        cmd = (cmd_tpl.replace("{input}", src)
                      .replace("{output}", outbase + ".fits")
                      .replace("{outbase}", outbase))
        self._set_ext_msg(f"{name} en cours…{progression} ({n_frames} frames)",
                          state="busy")
        code, err = gx_live._run_bloquant_survivable(cmd, tmp, 1800)
        if err:
            self._set_ext_msg(f"Erreur {name} : {err}", state="error")
            return None
        if code != 0:
            lignes = []
            try:
                with open(journal, encoding="utf-8", errors="replace") as f:
                    lignes = [l for l in f.read().splitlines() if l.strip()]
            except OSError:
                pass
            detail = lignes[-1] if lignes else "aucun message"
            self._set_ext_msg(f"Erreur {name} (code {code}) : {detail}",
                              state="error")
            return None
        res = find_output(src, outbase)
        if res is None:
            self._set_ext_msg(f"Erreur {name} : fichier de sortie introuvable "
                              "(l'outil n'a rien écrit)", state="error")
            return None
        return res

    def _score_qualite(self, img):
        """Mesure qualité d'une brute pour le filtre jalon 17 :
        (fwhm, nb) — FWHM médiane (px) et nombre d'étoiles exploitables de
        `stars.mesurer_seeing` (jalon 10, ~15 ms ; la couleur est traitée par
        sa luminance interne). (None, 0) = aucune étoile exploitable (mesure
        impossible, champ sans étoile ou défocalisation poussée) : la
        DÉCISION reste à `_filtre_floue` (jamais de rejet sur la seule erreur
        de mesure). Jamais d'exception propagée (convention du module
        stars)."""
        try:
            mes, _msg = seeing_live.mesurer_seeing(img)
        except Exception:
            return None, 0
        if not isinstance(mes, dict):
            return None, 0
        fwhm = mes.get("fwhm")
        if not isinstance(fwhm, (int, float)) or not np.isfinite(fwhm) \
                or fwhm <= 0:
            fwhm = None
        return (float(fwhm) if fwhm is not None else None), \
            int(mes.get("nb") or 0)

    def _filtre_floue(self, frame, role=None):
        """Décision du filtre jalon 17 pour la frame calibrée `frame` :
        → message de rejet ("" si la frame est gardée ou filtre désactivé).
        En mode composition (jalon 19, `role` fourni), la médiane de
        référence est tenue PAR RÔLE : un filtre étroit (Ha) ne montre pas
        le même nombre d'étoiles ni la même FWHM qu'un autre (O3).
        Rejet si : FWHM > FWHM_MARGE × médiane des frames gardées (et
        soi-même > FWHM_ABS_MIN px — ne rien rejeter en très courte focale où
        une FWHM de 3 px est un seeing honnête), OU score étoiles effondré
        (< FLU_NB_FRAC × médiane des gardées) : la défocalisation poussée
        fait sortir les étoiles des critères de forme de stars.py (nb 0, FWHM
        non mesurable). SEUL, un score bas pourrait refléter un simple
        changement de champ (dossier mixé) → il ne rejette que si la FWHM est
        dégradée (> 1,25× la médiane) ou non mesurable. Il faut ≥ FLU_MIN_REF
        frames gardées pour décider ; si AUCUNE frame gardée n'a d'étoiles
        (nébulosité, champ pauvre…), rien n'est jamais rejeté. La frame
        gardée alimente les médianes de référence."""
        if not self.rejeter_flou:
            return ""
        fwhm, nb = self._score_qualite(frame)
        hist = (self._fwhm_par_role.setdefault(role, [])
                if role is not None else self._fwhm_hist)
        ref_f = [m[0] for m in hist if m[0] is not None]
        ref_n = [m[1] for m in hist]
        assez_n = len(ref_n) >= FLU_MIN_REF
        med_n = float(np.median(ref_n)) if assez_n else 0.0
        med_f = float(np.median(ref_f)) if len(ref_f) >= FLU_MIN_REF else None
        if nb == 0 and (not assez_n or med_n <= 0):
            return ""             # aucune étoile nulle part : pas de critère
        rejeter = ""
        if med_f is not None and fwhm is not None \
                and fwhm > FWHM_ABS_MIN and fwhm > FWHM_MARGE * med_f:
            rejeter = (f"frame très floue rejetée "
                       f"(FWHM {fwhm:.1f} px ≫ médiane {med_f:.1f} px)")
        if not rejeter and assez_n and nb < FLU_NB_FRAC * med_n:
            # Effondrement du nb d'étoiles : signature d'une défocalisation
            # plus poussée que les critères de forme de stars.py. SEUL il peut
            # refléter un simple changement de champ (dossier mixé) → il ne
            # rejette que si la FWHM est dégradée ou non mesurable.
            degrade = (fwhm is not None and med_f is not None
                       and fwhm > 1.25 * med_f)
            if degrade or fwhm is None:
                rejeter = (f"frame très défocalisée rejetée (score étoiles "
                           f"{nb} ≪ médiane {med_n:.0f})")
        if not rejeter and fwhm is not None:
            hist.append((fwhm, nb))
        return rejeter

    # -------------------------------------- jalon 16 : re-stack (Siril)
    def _score_frame(self, img):
        """Score qualité d'une brute (esprit Siril) : nombre d'étoiles
        détectées sur le canal vert. Une brute très défocalisée en détecte
        peu (les étoiles larges sortent des critères de forme de stars.py) —
        le score pénalise donc déjà partiellement la défocalisation pour le
        choix de la référence (un VRAI filtre qualité FWHM reste à faire,
        cf. AVANCEMENT.md). Jamais d'exception propagée."""
        try:
            pos, _msg = seeing_live.detecter_positions(
                align_mod.canal_alignement(img), max_etoiles=SCORE_MAX_ETOILES)
            return int(len(pos))
        except Exception:
            return 0

    # ------------------------------------ jalon 56 : astrométrie de l'empilement
    def _astro_tour(self, stacker):
        """Appelé par le worker APRÈS le re-stack (la grille est alors celle
        qui sera affichée et sauvegardée) : indices → RÉSOLUTION UNIQUE → état.

        - WCS déjà résolu : rien à faire, la ligne rappelle la mesure (et le
          nombre de propagations) ;
        - case décochée / indices manquants : la ligne DIT pourquoi (jamais de
          silence) ; en mode dossier, une lecture des indices dans l'en-tête
          de la brute courante est tentée AVANT de renoncer ;
        - sinon `peut_essayer` décide (frames empilées, délai, plafond) : une
          résolution coûte du temps d'acquisition, elle n'est tentée que sur
          un empilement déjà consistant, et au plus une fois par délai."""
        if self.suivi_astro is None or stacker is None or stacker.n <= 0:
            return
        if self.suivi_astro.resolu:
            self._maj_astro_etat()
            return
        if not self._astro_actif:
            self.astro_info = "Astrométrie : désactivée"
            self.astro_couleur = "#888888"
            return
        if self._astro_indices is None:
            self._astro_indices_entete()
        if self._astro_indices is None:
            # Jalon 56 : ni saisie ni en-tête de brute (caméra live sans
            # en-tête FITS) → REPLI ASTAP « aveugle » : c'est LUI qui fournit
            # les indices (son centre), puis le solveur interne reprend la main
            # sur un champ indicé fiable (chemin validé par _diag_solve_reel).
            self._astro_aveugle(stacker)
        if self._astro_indices is None:
            self.astro_info = ("Astrométrie : " + (self._astro_msg_indices
                               or "indices de la cible manquants"))
            self.astro_couleur = "#c98a00"
            return
        if not self.suivi_astro.pret:
            self.suivi_astro.indice(*self._astro_indices)
        if not self.suivi_astro.peut_essayer(stacker.n):
            raison = self.suivi_astro.raison_attente()
            if raison:
                self.astro_info = f"Astrométrie : {raison}"
                self.astro_couleur = "#c98a00"
            return
        img = stacker.mean(recadre=False)
        if img is None:
            return
        # Message posé AVANT le calcul : le thread Tk le lit PENDANT la
        # résolution (le worker, lui, est occupé) — l'utilisateur voit ainsi
        # d'où vient la pause d'acquisition d'une frame environ.
        self.astro_info = (f"Astrométrie : résolution en cours "
                           f"({stacker.n} frames)…")
        self.astro_couleur = "#888888"
        okk, msg = self.suivi_astro.resoudre_sur(img, n_frames=stacker.n)
        if okk:
            self._maj_astro_etat()
            return
        # Jalon 56 : le solveur INTERNE a refusé — si ASTAP avait résolu en
        # aveugle, son WCS devient le WCS de la session (repli prévu par la
        # décision d'Alain : « ASTAP = référence indépendante/repli »).
        if self._astro_wcs_secours is not None:
            ok2, msg2 = self.suivi_astro.adopter(self._astro_wcs_secours,
                                                 img.shape[:2])
            if ok2:
                self._astro_wcs_secours = None     # adopté : plus de secours
                self._astro_source = "ASTAP (repli)"
                self._maj_astro_etat()
                return
            msg = f"{msg} — repli ASTAP refusé ({msg2})"
        essais = self.suivi_astro.essais
        self.astro_couleur = ("#c98a00" if essais < astro_mod.ASTRO_MAX_ESSAIS
                              else "#d04040")
        suite = ("réessai automatique dès que l'empilement double"
                 if essais < astro_mod.ASTRO_MAX_ESSAIS else "plafond atteint")
        self.astro_info = (f"Astrométrie : échec — {msg} "
                           f"({essais}/{astro_mod.ASTRO_MAX_ESSAIS} essais, "
                           f"{suite})")

    def _astro_aveugle(self, stacker):
        """Jalon 56 — REPLI ASTAP : quand AUCUN indice n'est disponible (ni
        saisie, ni en-tête de brute), ASTAP balaie le ciel seul (`fov` auto) et
        son centre sert d'indice au solveur interne. Le WCS rendu est GARDÉ
        (`_astro_wcs_secours`) : si le solveur interne refuse ensuite, il est
        adopté tel quel (repli) au lieu de laisser la session sans astrométrie.

        Appel LENT (balayage complet : plusieurs secondes à une minute) → au
        plus `ASTRO_MAX_AVEUGLES` fois par session, espacées du même délai que
        les essais internes, et jamais pendant qu'un empilement est trop court.
        Sans astap_cli installé, l'échec est immédiat et parfaitement clair."""
        if self._astro_aveugles >= astro_mod.ASTRO_MAX_AVEUGLES:
            self._astro_msg_indices = (f"aucun indice (ASTAP aveugle : plafond "
                                       f"de {astro_mod.ASTRO_MAX_AVEUGLES} "
                                       f"tentatives atteint)")
            return
        # SONDE des bases ASTAP, UNE fois par session (listdir d'un dossier de
        # plus de 1000 fichiers) : sans base de BALAYAGE (G18/H18…), ASTAP ne
        # peut PAS chercher sans position — inutile de bloquer l'acquisition
        # pour un échec certain (constat réel du 23/09/2026 : avec la seule
        # base D80, tout balayage échoue en ~0,4 s). On le DIT à l'utilisateur.
        if self._astro_balayage is None:
            self._astro_balayage = astro_mod.balayage_possible()
            self._astro_bases = (", ".join(sorted(astro_mod.bases_installees()))
                                 or "aucune")
        if not self._astro_balayage:
            self._astro_msg_indices = (
                f"aucun indice (ASTAP : bases installées = {self._astro_bases}; "
                f"PAS de base de BALAYAGE — saisir AD/Dec approximatifs, ou "
                f"installer une base G18/H18)")
            return
        if stacker.n < astro_mod.ASTRO_MIN_FRAMES:
            return
        # Un seul essai PAR VALEUR de champ : rebalayer à l'identique redonne
        # exactement le même échec (« No solution found! », constat réel).
        fov = float(self._astro_champ_seul or 0.0)
        if fov in self._astro_fov_essayes:
            self._astro_msg_indices = (
                f"aucun indice (ASTAP déjà tenté avec un champ de "
                f"{fov:.3f}° : balayage NON répété — saisir AD/Dec, ou "
                f"corriger le champ)")
            return
        self._astro_fov_essayes.add(fov)
        t = time.monotonic()
        if (self._astro_aveugles
                and t - self._astro_dernier_aveugle
                < astro_mod.ASTRO_ESSAI_DELAI_S):
            return
        img = stacker.mean(recadre=False)
        if img is None:
            return
        self._astro_aveugles += 1
        self._astro_dernier_aveugle = t
        self.astro_info = (
            "Astrométrie : aucun indice — balayage ASTAP en cours"
            + (f" (champ indicatif {fov:.3f}°)…" if fov
               else " (sans champ indicatif : LENT)…"))
        self.astro_couleur = "#c98a00"
        try:
            wcs, ra, dec, champ, msg = astro_mod.resoudre_aveugle_astap(
                img, fov_deg=fov)
        except Exception as exc:       # un outil externe ne tue jamais le worker
            wcs, ra, dec, champ = None, None, None, None
            msg = f"exception ASTAP ({exc})"
        if wcs is None or ra is None:
            self._astro_msg_indices = f"ASTAP aveugle : {msg}"
            self.astro_info = f"Astrométrie : {self._astro_msg_indices}"
            self.astro_couleur = "#c98a00"
            return
        self._astro_wcs_secours = wcs
        self._astro_indices = (ra, dec, champ)
        self._astro_msg_indices = ""
        self._astro_source = "ASTAP (aveugle)"
        self.suivi_astro.indice(ra, dec, champ)
        self.astro_info = (f"Astrométrie : indices d'ASTAP — {msg}"
                           f" → solve interne…")
        self.astro_couleur = "#888888"

    def _maj_astro_etat(self):
        """Recopie l'état du suivi (étoiles, rms, ″/px, propagations) dans la
        ligne dédiée — seulement si le texte change : Tk relit `astro_info`
        ~20×/s, inutile de réécrire la même chaîne."""
        if self.suivi_astro is None:
            return
        txt = self.suivi_astro.texte_resume()
        if txt and txt != self.astro_info:
            self.astro_info = txt
        if self.suivi_astro.resolu:
            self.astro_couleur = "#1d7f1d"

    # -------------------------------- jalon 56 (étape 4) : photométrie
    def _photo_tour(self, stacker):
        """Mesure le zéro-point PAR BANDE quand l'astrométrie est RÉSOLUE (le
        WCS est indispensable : c'est lui qui relie les étoiles de l'image au
        catalogue Gaia), l'empilement assez profond et la case cochée.

        Mesure UNE fois par session (réessais espacés, plafonnés) et SANS AUCUN
        effet sur l'image : l'application de ces gains au stacker est l'étape 5.
        Le catalogue (1,1 Go) n'est lu QUE par une mesure — d'où le plafond."""
        if self.photometrie is None or stacker is None or stacker.n <= 0:
            return
        if self.photometrie.valide:
            return                     # déjà mesuré : rien à refaire
        if not self._photo_actif:
            return
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return                     # sans WCS : aucune photométrie possible
        if stacker.n < astro_mod.ASTRO_MIN_FRAMES:
            return
        if self._photo_essais >= photo_mod.MAX_ESSAIS:
            self.photo_info = (f"Photométrie : {self.photometrie.derniere_erreur}"
                               f" — {self._photo_essais} essais, plafond atteint")
            self.photo_couleur = "#d04040"
            return
        t = time.monotonic()
        if (self._photo_essais
                and t - self._photo_dernier < photo_mod.DELAI_ESSAI_S):
            return
        canaux, wcs, forme = self._photo_canaux(stacker)
        if not canaux or wcs is None:
            return
        self._photo_essais += 1
        self._photo_dernier = t
        self.photo_info = ("Photométrie : mesure du zéro-point en cours "
                           f"({stacker.n} frames, "
                           f"{len(canaux)} bande(s))…")
        self.photo_couleur = "#888888"
        try:
            res, msg = self.photometrie.mesurer(canaux, wcs, forme=forme)
        except Exception as exc:       # une mesure ne tue jamais le worker
            res, msg = None, f"exception ({exc})"
        if res is None:
            self.photo_info = f"Photométrie : {msg}"
            self.photo_couleur = ("#c98a00"
                                  if self._photo_essais < photo_mod.MAX_ESSAIS
                                  else "#d04040")
            return
        self._maj_photo_etat()

    @staticmethod
    def _source_rgb(stacker):
        """L'empilement porte-t-il les trois canaux R/G/B ? VRAI en composition
        multi-rôles (le composite est recoloré) ET pour une source COULEUR
        (capteur OSC en mode dossier) ; FAUX en mono. Purement géométrique (la
        forme d'UNE frame), donc GRATUIT : aucune image à moyenner pour le
        savoir — la SPCC a besoin des trois canaux, et le dire vaut mieux que
        d'échouer."""
        shp = getattr(stacker, "shape", None) or getattr(stacker, "_shape", None)
        try:
            return shp is not None and len(tuple(shp)) == 3
        except TypeError:
            return False

    def _photo_canaux(self, stacker):
        """Canaux (bandes) + WCS de la MÊME grille pour la photométrie.

        Grille RECADRÉE (celle de la vue et des sauvegardes) — en composition,
        les cartes PAR RÔLE (`moyennes`) sont les bandes ; pour une source
        COULEUR (capteur OSC en mode dossier), les trois canaux R/G/B de
        l'empilement BRUT (`corrections=False`) sont les bandes — c'est sur
        cette image-là que la SPCC doit mesurer : un équilibrage ou un
        recalage déjà appliqué fausserait les ratios de couleur (et les gains
        se cumuleraient). En mono, une seule bande « L ». Le WCS est celui de
        cette grille exacte (recadrage d'intersection inclus) : les deux
        DOIVENT décrire la même grille, sinon l'appariement au catalogue
        serait faux. → (canaux, WCS, forme)."""
        cadre = getattr(stacker, "cadre", None)
        try:
            if hasattr(stacker, "moyennes"):
                canaux = stacker.moyennes(recadre=True) or {}
            else:
                img = stacker.mean(corrections=False)
                if img is None:
                    canaux = {}
                elif getattr(img, "ndim", 2) == 3:
                    a = (img if img.shape[-1] == 3
                         else np.transpose(img, (1, 2, 0)))
                    canaux = {"R": a[..., 0], "G": a[..., 1], "B": a[..., 2]}
                else:
                    canaux = {"L": img}
        except Exception as exc:
            self.photo_info = f"Photométrie : canaux indisponibles ({exc})"
            self.photo_couleur = "#c98a00"
            return {}, None, None
        canaux = {b: v for b, v in canaux.items() if v is not None}
        if not canaux:
            return {}, None, None
        forme = tuple(np.asarray(next(iter(canaux.values()))).shape[:2])
        wcs, msg = self.suivi_astro.wcs_grille(cadre, forme=forme)
        if wcs is None:
            self.photo_info = f"Photométrie : WCS indisponible ({msg})"
            self.photo_couleur = "#c98a00"
            return {}, None, None
        return canaux, wcs, forme

    def _maj_photo_etat(self):
        """Recopie la mesure (zéro-points par bande) dans la ligne dédiée —
        seulement si le texte change."""
        if self.photometrie is None:
            return
        txt = self.photometrie.texte_resume()
        if txt and txt != self.photo_info:
            self.photo_info = txt
        if self.photometrie.valide:
            self.photo_couleur = "#1d7f1d"
            # Jalon 56 (étape 5) : si la case opt-in est cochée, les gains
            # viennent d'apparaître → le rendu doit suivre SANS attendre une
            # nouvelle brute (le stacker les recevra au prochain tour).
            if self._photo_gains_actif and self._mode_compo:
                self._rafraichir_rendu = True

    # -------------------------------- jalon 58 : SPCC absolue
    def _spcc_tour(self, stacker):
        """Calcule les coefficients SPCC de la session (une fois, réessais
        espacés). Mêmes prérequis que la photométrie (WCS résolu, empilement
        assez profond) PLUS les trois canaux R/G/B et la base de profils."""
        if self.spcc is None or stacker is None or stacker.n <= 0:
            return
        if self.spcc.valide:
            return                     # déjà calibré : rien à refaire
        if not self._spcc_actif or not getattr(self, "_spcc_dispo", False):
            return
        if not (self._mode_compo or self._source_rgb(stacker)):
            return                     # il faut une image COULEUR (R, G et B)
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return
        if stacker.n < astro_mod.ASTRO_MIN_FRAMES:
            return
        if self._spcc_essais >= spcc_mod.MAX_ESSAIS:
            self.spcc_info = (f"SPCC : {self.spcc.derniere_erreur}"
                              f" — {self._spcc_essais} essais, plafond atteint")
            self.spcc_couleur = "#d04040"
            return
        t = time.monotonic()
        if (self._spcc_essais
                and t - self._spcc_dernier < spcc_mod.DELAI_ESSAI_S):
            return
        canaux, wcs, forme = self._photo_canaux(stacker)
        if not canaux or wcs is None:
            return
        capteur, filtres, blanc = self._spcc_profils()
        self._spcc_essais += 1
        self._spcc_dernier = t
        self.spcc_info = ("SPCC : calibration en cours (spectres Gaia × profils "
                          f"capteur/filtres, {stacker.n} frames)…")
        self.spcc_couleur = "#888888"
        try:
            res, msg = self.spcc.mesurer(canaux, wcs, capteur, filtres, blanc,
                                         forme=forme,
                                         mode=("osc" if self._spcc_osc()
                                               else "mono"))
        except Exception as exc:       # une mesure ne tue jamais le worker
            res, msg = None, f"exception ({exc})"
        if res is None:
            self.spcc_info = f"SPCC : {msg}"
            self.spcc_couleur = ("#c98a00"
                                 if self._spcc_essais < spcc_mod.MAX_ESSAIS
                                 else "#d04040")
            self._maj_spcc_vue()
            return
        # Sur COMBIEN de frames la mesure a été faite : la mesure SPCC est faite
        # UNE fois par session (SessionSpcc) — le dire évite de croire que la
        # case ne « rafraîchit » plus rien (constat d'Alain, 25/09/2026).
        if isinstance(self.spcc.diag, dict):
            self.spcc.diag.setdefault("frames", int(stacker.n))
        self._maj_spcc_etat()
        self._maj_spcc_vue()

    def _astro_indices_entete(self):
        """Indices de la cible déduits de l'en-tête de la brute courante
        (source DOSSIER) quand la saisie est vide — lecture STRICTE
        (OBJCTRA/OBJCTDEC + FOCALLEN/XPIXSZ), jamais de supposition : sans
        mots-clés explicites, rien n'est inventé et le message le dit."""
        chemin = getattr(self.camera, "last_file", "") or ""
        if not chemin:
            try:      # composition : dernier fichier du rôle le plus récent
                stats = self.camera.stats() or {}
                cands = [v.get("last_file") or "" for v in stats.values()]
                cands = [c for c in cands if c]
                if cands:
                    chemin = max(cands, key=os.path.getmtime)
            except Exception:
                chemin = ""
        if not chemin:
            return
        ra, dec, champ, msg = astro_mod.indices_entete_fits(chemin)
        if ra is None or champ is None:
            self._astro_msg_indices = msg
            return
        self._astro_indices = (ra, dec, champ)
        self._astro_msg_indices = ""
        self._astro_source = f"en-tête {os.path.basename(chemin)}"
        self.suivi_astro.indice(ra, dec, champ)

    def _astro_propager_restack(self, ancien, ref):
        """Jalon 56 : le RÉEMPILEMENT change la référence d'alignement, donc la
        GRILLE de l'empilement — le WCS est PROPAGÉ (aucun re-solve, aucun
        accès au catalogue : décision d'Alain du 22/09/2026).

        `M10` (nouvelle grille → ANCIENNE grille) est mesuré par un aligneur
        PRIVÉ : référence = l'ancien empilement COMPLET (`mean(recadre=False)`
        — le même repère que toutes les frames alignées, contrat du jalon 13),
        source = la nouvelle référence. C'est exactement le chemin confronté au
        StarAligner réel par le banc du jalon 56 (étape 3) ; l'aligneur de la
        SESSION n'est pas touché (il est sur le point d'être re-référencé).

        Échec (appariement refusé, WCS absent) : SANS EFFET sur l'empilement,
        message exposé sur la ligne dédiée — un WCS d'ancienne grille est
        signalé, jamais présenté comme valable."""
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return
        try:
            base = ancien.mean(recadre=False)
        except Exception:
            base = None
        if base is None:
            return
        al = StarAligner()
        al.triangles_seuls = bool(self.aligner.triangles_seuls)  # HOO/SHO
        try:
            al.set_reference(base)
            M, okk = al.compute(ref)
        except Exception as exc:
            self.astro_couleur = "#c98a00"
            self.astro_info = f"Astrométrie : propagation impossible ({exc})"
            return
        if not okk or M is None:
            self.astro_couleur = "#c98a00"
            self.astro_info = ("Astrométrie : propagation refusée (nouvelle "
                               "référence ↔ ancien empilement) — le WCS reste "
                               "celui de l'ancienne grille")
            return
        ok2, msg = self.suivi_astro.propager(M)
        if ok2:
            self._maj_astro_etat()
        else:
            self.astro_couleur = "#c98a00"
            self.astro_info = f"Astrométrie : propagation refusée — {msg}"

    def _entete_reglages(self, applique=True):
        """Mots-clés FITS décrivant une sauvegarde LINÉAIRE — question d'Alain
        (24/09/2026) : « la sauvegarde empilement linéaire, elle sauvegarde quoi
        au juste ? ». Le fichier devient AUTO-DESCRIPTIF.

        Chantier du 24/09/2026 — MESURE vs APPLICATION (étape ⑥ du plan) :
        depuis que la sauvegarde linéaire est BRUTE, AVASPCC et AVAGAIA
        décrivent une MESURE (ce que la session a mesuré), pas ce que le
        fichier contient. La clé AVAAPPLI dit, elle, ce qui est RÉELLEMENT
        appliqué à l'image écrite : « aucune (empilement BRUT) » pour le
        fichier brut, la liste des corrections pour la sortie traitée. Sans
        cette distinction, un fichier brut portant AVASPCC=K=… laisserait
        croire que la SPCC y est appliquée : il mentirait.

        ASCII uniquement (convention FITS) et clés courtes (≤ 8 caractères) :
        AVACOMPO (composition), AVAAPPLI (corrections appliquées au fichier),
        AVAWB (équilibrage auto et sa force — si appliqué), AVAFIT (recalage
        colorimétrique — si appliqué), AVASPCC (coefficients SPCC MESURÉS),
        AVAGAIA (gains Gaia MESURÉS), AVAFRAME (frames empilées), AVALAYER
        (sauvegarde d'une COUCHE brute, posée par l'appelant)."""
        st = self.stacker
        ent = {}
        n = int(getattr(st, "n", 0) or 0)
        if n:
            ent["AVAFRAME"] = n
        # NB : ces mots-clés ne dépendent PAS de l'existence du stacker (les
        # réglages sont connus même sans empilement) — seule la description de
        # l'empilement lui-même en dépend (getattr défensifs).
        spcc_ok = (self._spcc_actif and self.spcc is not None
                   and self.spcc.valide)
        gaia_ok = (self._photo_gains_actif and self.photometrie is not None
                   and self.photometrie.valide)
        if self._mode_compo:
            # v2.36.0 : le fichier DIT quelle normalisation a servi (c'est un
            # choix visible : le fond et le grain en dépendent).
            norm = ("normalisation COMMUNE des canaux (amplitude du vert)"
                    if bool(getattr(st, "normalisation_commune", False))
                    else "normalisation par role (percentiles)")
            ent["AVACOMPO"] = f"{getattr(st, 'composition', '?')}, {norm}"
        # MESURES de la session (indépendantes de ce qui est appliqué).
        if spcc_ok:
            k = self.spcc.coefficients
            ent["AVASPCC"] = f"K={k[0]:.4f}/{k[1]:.4f}/{k[2]:.4f}"
        elif self._spcc_actif:
            # Case cochée SANS mesure exploitable : le dire, sinon on croit que
            # la SPCC est entrée dans le fichier alors que rien n'a été appliqué
            # (constat d'Alain, 25/09/2026 : fichiers écrits avant que la mesure
            # ne soit disponible, en-tête muet).
            ent["AVASPCC"] = ("non appliquee (case cochee, mesure "
                              "indisponible)")
        if gaia_ok:
            ent["AVAGAIA"] = " ".join(
                f"{b}={g:.4f}" for b, g in sorted(self.photometrie.gains.items()))
        elif self._photo_gains_actif:
            ent["AVAGAIA"] = ("non appliques (case cochee, mesure "
                              "indisponible)")
        # CE QUI EST APPLIQUÉ à l'image écrite (étape ⑥).
        if not applique:
            ent["AVAAPPLI"] = "aucune (empilement BRUT)"
            return ent
        parts = []
        if spcc_ok:
            parts.append("SPCC")
        elif gaia_ok:
            parts.append("gains Gaia")
        gains_ui = {c: float(g) for c, g in (self._compo_gains or {}).items()
                    if abs(float(g) - 1.0) > 1e-9}
        if gains_ui:
            parts.append("gains manuels")
        if bool(getattr(st, "wb_auto", False)):
            parts.append("equilibrage canaux")
            ent["AVAWB"] = (f"equilibrage canaux auto, force "
                            f"{getattr(st, 'wb_force', 1.0):.2f}")
        if bool(getattr(st, "linear_fit", False)):
            parts.append("recalage colorimetrique")
            ent["AVAFIT"] = (f"recalage colorimetrique "
                             f"{getattr(st, 'linear_fit_mode', 'offset')}")
        ent["AVAAPPLI"] = " + ".join(parts) if parts else "aucune"
        return ent

    def _entete_externe(self, n_frames=None):
        """En-tête FITS du RÉSULTAT du ⚡ traitement externe (v2.38.3).

        POURQUOI (constat d'Alain, 27/09/2026) : les commandes des outils — donc
        leurs PARAMÈTRES — n'étaient écrites NULLE PART. `AVAAPPLI` ne décrivait
        que les corrections de couleur, et les « tel que vu » n'avaient aucun
        en-tête : un fichier ne disait pas de quelle chaîne il venait, alors que
        le réglage des outils change la texture fine (mesuré : moucheté chroma
        2-8 px ×0,37 entre `--sn 0,50` — le défaut du CLI non passé — et 0,3).

        Les commandes RÉELLEMENT utilisées par le ⚡ sont consignées telles
        quelles (elles portent leurs options : `--ash`, `--sn`, `-strength`…) ;
        l'en-tête est construit au moment du traitement, depuis `ext_job` (lu par
        le thread de travail, jamais une variable Tk). Déballage TOLÉRANT : un
        job à 8 éléments (formats antérieurs) reste accepté."""
        j = tuple(self.ext_job or ())

        def val(i, defaut=None):
            return j[i] if len(j) > i else defaut

        outils = []
        if val(0):
            outils.append("GraXpert gradient")
        if val(2):
            methode = val(6) or "?"
            outils.append("debruitage "
                          + ("GraXpert" if methode == "graxpert" else methode))
        if val(4):
            outils.append("BXT")
        preet = []
        for actif, nom in ((val(8), "SCNR"), (val(9), "SCNR doux"),
                           (val(10), "demagenta"), (val(11), "fond neutre"),
                           (val(12), "chroma")):
            if actif:
                preet.append(nom)
        if val(12):
            preet.append("chroma force %.2f rayon %.1fpx"
                         % (float(val(13, 0.5)), float(val(14, 3.0))))
        ent = {"AVAOUTIL": " + ".join(outils) if outils else "aucun",
               "AVAAPPLI": " + ".join(preet) if preet else "aucune",
               "AVAVUE": ("resultat du traitement externe (LINEAIRE, "
                          "avant etirement)")}
        if val(1):
            ent["AVACMDGX"] = str(val(1))
        if val(3):
            ent["AVACMDDN"] = str(val(3))
        if val(5):
            ent["AVACMDBX"] = str(val(5))
        if n_frames:
            ent["AVAFRAME"] = int(n_frames)
        return ent

    def _astro_entete_sauvegarde(self, entete=None, forme=None):
        """Jalon 56 : complète un en-tête de sauvegarde avec les mots-clés WCS
        de la grille ACTUELLE (recadrage d'intersection inclus) — le FITS écrit
        devient localisable par Siril, astropy, PixInsight… Sans astrométrie
        résolue : en-tête INCHANGÉ (jamais de mot-clé faux dans un fichier)."""
        entete = dict(entete or {})
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return entete
        cadre = None
        if self.stacker is not None:
            cadre = getattr(self.stacker, "cadre", None)
        mc, msg = self.suivi_astro.mots_cles(cadre, forme=forme)
        if not mc:
            if msg:
                self.astro_info = f"Astrométrie : en-tête WCS indisponible — {msg}"
                self.astro_couleur = "#c98a00"
            return entete
        entete.update(mc)
        return entete

    def _definir_reference(self, img):
        """Remplace la référence d'alignement ET mesure son score (le score
        de la référence sert de seuil au déclencheur auto du re-stack)."""
        self.aligner.set_reference(img)
        self._ref_score = self._score_frame(img)

    def _vider_archive(self):
        """Vide l'archive temporaire ET le score parallèle (les deux listes
        doivent toujours avoir le même ordre — jalon 16). En mode compo
        (jalon 19), vide aussi les archives PAR RÔLE."""
        self.archive.vider()
        self._scores = []
        self._scores_par_role = {}   # jalon 20 : scores PAR RÔLE (compo)
        for arch in self.archives.values():
            arch.vider()

    def _meilleure_archive(self):
        """→ (idx, chemin, score) de la meilleure brute archivée, ou
        (None, None, None) si l'archive est vide ou incohérente."""
        if not self._scores or len(self._scores) != len(self.archive.chemins):
            return None, None, None
        idx = int(np.argmax(self._scores))
        return idx, self.archive.chemins[idx], int(self._scores[idx])

    def _meilleure_archive_compo(self):
        """Jalon 20 (mode compo) → (rôle, idx, chemin, score) de la meilleure
        brute archivée, TOUS RÔLES confondus — les scores sont mesurés sur le
        CANAL EXTRAIT de chaque rôle (la même mesure que l'alignement), donc
        comparables d'une couche à l'autre. → (None,)*4 si vide ou incohérent
        (une liste de scores ne collant plus à son archive est ignorée)."""
        meilleur = (None, None, None, None)
        for role, scores in self._scores_par_role.items():
            arch = self.archives.get(role)
            if arch is None or len(scores) != len(arch.chemins):
                continue
            idx = int(np.argmax(scores))
            if meilleur[3] is None or scores[idx] > meilleur[3]:
                meilleur = (role, idx, arch.chemins[idx], int(scores[idx]))
        return meilleur

    def _veut_restack(self):
        """Déclencheur AUTO (esprit Siril) : la meilleure brute archivée bat
        nettement la référence courante (marge RESTACK_MARGE en étoiles).
        Surtout utile quand l'ANCRE initiale était médiocre ; une fois la
        référence rafraîchie sur l'EMPILEMENT (qui détecte plus d'étoiles
        qu'une brute isolée), la marge n'est presque plus atteinte —
        comportement voulu, le re-stack auto reste exceptionnel.
        Jalon 20 : en mode compo, même logique TOUS RÔLES confondus (la
        référence d'alignement est partagée, une meilleure brute d'une
        couche quelconque re-ancre tout)."""
        if self._mode_compo:
            role, idx, _chemin, score = self._meilleure_archive_compo()
            if role is None or self._ref_score is None:
                return False
            if (self._ancre_idx is not None and self._ancre_role == role
                    and idx == self._ancre_idx):
                return False
            return score >= RESTACK_MARGE * self._ref_score
        idx, _chemin, score = self._meilleure_archive()
        if idx is None or self._ref_score is None:
            return False
        if self._ancre_idx is not None and idx == self._ancre_idx:
            return False
        return score >= RESTACK_MARGE * self._ref_score

    def _do_restack(self, raison):
        """Re-ancre l'alignement sur la MEILLEURE brute archivée et recalcule
        TOUT l'empilement depuis l'archive (équivalent live du choix de
        référence de Siril). S'exécute dans le thread worker (quelques
        secondes à ~1 min selon le nb de frames) ; les frames qui arrivent
        pendant ce temps sont traitées juste après. Le re-stack est SIGNALÉ
        sur une ligne d'état DÉDIÉE (jalon 18) : horodatage + gain +
        historique. → message d'état, ou "" si rien fait (archive vide,
        lecture impossible, forme différente)."""
        if self.stacker is None:
            return ""
        if self._mode_compo:          # jalon 20 : re-stack multi-canal
            return self._do_restack_compo(raison)
        idx, chemin, score = self._meilleure_archive()
        if idx is None:
            return ""
        try:
            ref = load_image(chemin)
        except Exception as exc:
            self._noter_restack(0, 0, 0, 0, None,
                                f"re-stack impossible (lecture archive : "
                                f"{exc})", echec=True)
            return f"re-stack impossible (lecture archive : {exc})"
        ancien = self.stacker
        if tuple(ref.shape) != tuple(ancien.shape):
            self._noter_restack(0, 0, 0, 0, None,
                                "re-stack impossible (forme d'archive "
                                "différente)", echec=True)
            return "re-stack impossible (forme d'archive différente)"
        # Jalon 18 : état « en cours » visible immédiatement (le recalcul
        # peut prendre de quelques secondes à ~1 min).
        self.restack_couleur = "#888888"
        self.restack_info = f"{time.strftime('%H:%M:%S')} · re-stack en " \
                            f"cours ({raison})…"
        # Jalon 18 : mémoriser l'état AVANT le recalcul pour afficher le GAIN.
        n_avant = ancien.n
        ref_score_avant = self._ref_score
        # Jalon 56 : la référence d'alignement change → la GRILLE change. Le
        # WCS (résolu sur l'ancienne grille) est PROPAGÉ depuis l'ancien
        # empilement complet, AVANT que la référence de la session ne soit
        # remplacée (l'aligneur privé de la propagation a besoin de l'ancien).
        self._astro_propager_restack(ancien, ref)
        self._definir_reference(ref)
        st = LiveStacker(ancien.shape, k=ancien.k, method=ancien.method,
                         window=ancien.window)
        st.wb_auto = ancien.wb_auto
        st.wb_force = ancien.wb_force
        # v2.40.0 : les gains de canaux (SPCC d'une source COULEUR) survivent au
        # re-stack — le worker les repose de toute façon, mais l'empilement ne
        # doit pas repasser une frame en couleurs fausses.
        st.gains = (dict(ancien.gains) if getattr(ancien, "gains", None)
                    else None)
        # Jalon 54 : le recalage « Linear Fit » survit au re-stack.
        st.linear_fit = ancien.linear_fit
        st.linear_fit_mode = ancien.linear_fit_mode
        self.stacker = st
        n_ok = 0
        ident = np.eye(2, 3)
        for j, c in enumerate(self.archive.chemins):
            try:
                img = load_image(c)
            except Exception:
                continue                    # fichier illisible → on le saute
            if tuple(img.shape) != tuple(st.shape):
                continue
            if j == idx:
                st.add(img)                 # l'ancre : alignement trivial
                st.note_alignement(ident)
                n_ok += 1
                continue
            M, ok = self.aligner.compute(img)
            if ok:
                st.add(cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                                      flags=cv2.INTER_LINEAR))
                st.note_alignement(M)
                n_ok += 1
        self._ref_frames = self._ref_bad = 0
        self._restack_depuis = 0
        self._ancre_idx = idx
        self._ancre_score = score
        # Jalon 18 : signaler le re-stack (ligne dédiée horodatée + gain,
        # compteur de session, historique) — le message sur la ligne
        # d'alignement reste inchangé (test jalon 16).
        self._noter_restack(n_ok, n_avant, self.archive.n, score,
                            ref_score_avant, raison)
        return (f"re-stack {n_ok}/{self.archive.n} frames · réf. = brute "
                f"#{idx} ({score} étoiles, {raison})")

    def _narrowband_ha(self):
        """Jalon 21 (décision d'Alain) : composition narrowband contenant le
        rôle Ha (HOO, SHO). Dans ce mode : l'ancre initiale est TOUJOURS une
        brute Ha, et l'alignement se fait par TRIANGLES seuls (ORB s'apparie
        mal d'un filtre à l'autre)."""
        return bool(self._mode_compo and self._compo_nom
                    and "Ha" in roles_de(self._compo_nom))

    def _do_restack_compo(self, raison, ancre_role=None, ancre_idx=None):
        """Jalon 20 — re-stack en mode COMPOSITION multi-filtres. La
        meilleure brute archivée, TOUS RÔLES confondus, devient la
        référence de l'aligneur PARTAGÉ (même repère pour toutes les
        couches, décision du 18/09/2026) et TOUTES les couches sont
        recalculées depuis leur archive PAR RÔLE : chaque couche a ses
        mauvaises frames (refusées à l'alignement ou dégradées avec
        l'ancienne référence) — elles repartent de zéro et ont une
        seconde chance. Le canal du rôle est ré-extrait de chaque brute
        archivée (les archives gardent les brutes complètes, calibrées).
        Jalon 21 : ancre FORCÉE (ancre_role, ancre_idx) au démarrage
        HOO/SHO — la 1re brute Ha devient l'ancre et les frames archivées
        entre-temps sont rejouées.
        S'exécute dans le thread worker ; → message d'état, ou "" si
        rien fait (archive vide, lecture impossible, forme différente)."""
        if ancre_role is not None:
            arch = self.archives.get(ancre_role)
            if (arch is None or ancre_idx is None
                    or not (0 <= ancre_idx < len(arch.chemins))):
                return ""
            role_ref = ancre_role
            idx = ancre_idx
            chemin = arch.chemins[idx]
            scores = self._scores_par_role.get(ancre_role) or []
            score = scores[idx] if idx < len(scores) else None
        else:
            role_ref, idx, chemin, score = self._meilleure_archive_compo()
            if role_ref is None:
                return ""
        try:
            ref = load_image(chemin)
            canal_ref = extraire_canal(ref, role_ref)
        except Exception as exc:
            self._noter_restack(0, 0, 0, 0, None,
                                f"re-stack impossible (lecture archive : "
                                f"{exc})", echec=True)
            return f"re-stack impossible (lecture archive : {exc})"
        ancien = self.stacker
        if (ancien.shape is not None
                and tuple(canal_ref.shape) != tuple(ancien.shape)):
            self._noter_restack(0, 0, 0, 0, None,
                                "re-stack impossible (forme d'archive "
                                "différente)", echec=True)
            return "re-stack impossible (forme d'archive différente)"
        # Jalon 18 : état « en cours » visible immédiatement.
        self.restack_couleur = "#888888"
        self.restack_info = f"{time.strftime('%H:%M:%S')} · re-stack en " \
                            f"cours ({raison})…"
        n_avant = ancien.n
        ref_score_avant = self._ref_score
        n_arch = sum(a.n for a in self.archives.values())
        # Référence de l'aligneur PARTAGÉ = canal extrait de la meilleure
        # brute (même mesure que les scores — cf. _meilleure_archive_compo).
        # Jalon 56 : propagation du WCS AVANT le remplacement (nouvelle
        # référence = une brute dans SON repère pixel, donc nouvelle grille).
        self._astro_propager_restack(ancien, canal_ref)
        self._definir_reference(canal_ref)
        st = CompositeStacker(ancien.composition, k=ancien.k,
                              method=ancien.method, window=ancien.window)
        st.gains = dict(ancien.gains) if ancien.gains else None
        st.mode_l = ancien.mode_l
        st.wb_auto = ancien.wb_auto
        st.wb_force = ancien.wb_force
        # Jalon 54 : le recalage « Linear Fit » survit au re-stack compo.
        st.linear_fit = ancien.linear_fit
        st.linear_fit_mode = ancien.linear_fit_mode
        # v2.36.0 : la normalisation commune (option) aussi.
        st.normalisation_commune = bool(getattr(ancien, "normalisation_commune",
                                                False))
        self.stacker = st
        # Rejouer les archives : rôles dans l'ordre de la composition, puis
        # les éventuels rôles supplémentaires (même ordre que etat()).
        roles = [r for r in roles_de(ancien.composition) if r in self.archives]
        roles += [r for r in self.archives if r not in roles]
        n_ok_par_role = {}
        ident = np.eye(2, 3)
        for role in roles:
            arch = self.archives[role]
            n_ok_role = 0
            for j, c in enumerate(arch.chemins):
                try:
                    img = load_image(c)
                    canal = extraire_canal(img, role)
                except Exception:
                    continue            # fichier illisible → on le saute
                if (ancien.shape is not None
                        and tuple(canal.shape) != tuple(ancien.shape)):
                    continue
                if role == role_ref and j == idx:
                    st.add(canal, role=role)      # l'ancre : trivial
                    st.note_alignement(ident)
                    n_ok_role += 1
                    continue
                M, ok = self.aligner.compute(canal)
                if ok:
                    st.add(cv2.warpAffine(canal, M, (canal.shape[1],
                                                     canal.shape[0]),
                                          flags=cv2.INTER_LINEAR), role=role)
                    st.note_alignement(M)
                    n_ok_role += 1
            n_ok_par_role[role] = n_ok_role
        n_ok = sum(n_ok_par_role.values())
        self._ref_frames = self._ref_bad = 0
        self._restack_depuis = 0
        self._ancre_role, self._ancre_idx, self._ancre_score = \
            role_ref, idx, score
        # Jalon 18 : signaler (ligne dédiée + gain + historique) — le détail
        # PAR CANAL (« Ha 9/9 · O3 8/9 ») permet de voir quelle couche a
        # récupéré (ou perdu) des frames avec la nouvelle référence.
        detail = raison
        detail += " · " + " · ".join(
            f"{r} {n_ok_par_role.get(r, 0)}/{self.archives[r].n}"
            for r in roles if self.archives[r].n > 0)
        self._noter_restack(n_ok, n_avant, n_arch, score,
                            ref_score_avant, detail)
        return (f"re-stack {n_ok}/{n_arch} frames (compo) · réf. = brute "
                f"{role_ref}#{idx} ({score} étoiles, {raison})")

    # ------------------------------------ jalon 18 : re-stack VISIBLE (UX)
    def _noter_restack(self, n_ok, n_avant, n_arch, score, ref_score_avant,
                       detail, echec=False):
        """Signale un re-stack (jalon 18 — retour réel d'Alain sur le jalon 16 :
        « pas simple de voir le restack ») : ligne d'état DÉDIÉE horodatée
        avec le GAIN (frames récupérées vs l'ancien empilement, rapport du
        score de la nouvelle référence à l'ancien), compteur de session et
        historique (bouton « ⓘ »). Appelé depuis le thread worker : ne
        modifie que des attributs simples ; l'affichage est fait par
        _update_status dans le thread Tk. Un ÉCHEC est signalé (ambre) mais
        ne compte PAS dans le compteur ni n'est un « re-stack »."""
        if not echec:
            self.restack_total += 1
        hhmm = time.strftime("%H:%M:%S")
        if echec:
            self.restack_couleur = "#c98a00"
            self.restack_info = f"{hhmm} · {detail}"
        else:
            gain_n = int(n_ok) - int(n_avant)
            gain_n_txt = f"+{gain_n}" if gain_n > 0 else str(gain_n)
            if ref_score_avant is None or ref_score_avant <= 0:
                gain_s_txt = "réf. précédente non mesurée"
            else:
                rapport = float(score) / float(ref_score_avant)
                gain_s_txt = (f"score réf. ×{rapport:.2f} "
                              f"({int(ref_score_avant)} → {int(score)} étoiles)")
            self.restack_couleur = "#1d7f1d"
            self.restack_info = (f"{hhmm} · re-stack #{self.restack_total} "
                                 f"({detail}) : {int(n_ok)}/{int(n_arch)} "
                                 f"frames ({gain_n_txt} vs avant) · "
                                 f"{gain_s_txt}")
        self.restack_hist.insert(0, self.restack_info)
        del self.restack_hist[RESTACK_HIST_MAX:]

    def _montrer_restack_hist(self):
        """Bouton « ⓘ » : historique horodaté des re-stacks de la session
        (fenêtre modale, la plus récente en premier)."""
        lignes = self.restack_hist or ["(aucun re-stack cette session)"]
        messagebox.showinfo(
            "Historique des re-stacks",
            f"Re-stacks de la session : {self.restack_total}\n\n"
            + "\n".join(f"• {l}" for l in lignes))

    # ------------------------------------------------------------ thread d'acquisition
    # --- contrôles caméra QHY (jalon 25) : appelés UNIQUEMENT depuis le
    # thread de travail (les appels SDK ne sont jamais faits côté Tk).
    def _appliquer_filtre_demande(self):
        """Change le filtre si une demande est en attente. Protocole de la
        décision d'Alain (le changement ARRÊTE puis REPREND l'acquisition) :
        stop_live → déplacement + attente de fin (≤ 25 s) → begin_live →
        PURGE des frames arrivées pendant la rotation (aucune frame d'un
        autre filtre ne doit entrer dans l'empilement). L'erreur est tracée
        et signalée, mais NE tue PAS l'acquisition (nouvel essai possible)."""
        n = self._filtre_demande
        if n is None or self.camera is None or self.cam_pilotee is None:
            return
        if not hasattr(self.cam_pilotee, "stop_live"):
            return      # roue : seul QHYCamera expose stop_live/begin_live
        self._filtre_demande = None
        nom = FILTRES_ROUE[n] if 0 <= n < len(FILTRES_ROUE) else f"?{n}"
        try:
            self.cam_pilotee.stop_live()
            self.cam_pilotee.choisir_filtre(n)
            self.cam_pilotee.begin_live()
            # PURGE TEMPORISÉE (piège : en flux live, read() ne renvoie
            # JAMAIS None — la caméra émet en continu, une boucle « jusqu'à
            # None » ne se terminerait jamais) : on jette les frames d'une
            # fenêtre ~2,5 expositions (≥ 1 s, ≤ 5 s) après la reprise.
            delai = min(5.0, max(1.0, 2.5 * getattr(self, "expo_ms",
                                                    100.0) / 1000.0))
            t_purge = time.monotonic()
            while self.running and time.monotonic() - t_purge < delai:
                self.camera.read()
                time.sleep(0.01)
            self._filtre_info = (f"Filtre {nom} (position {n})", "#1d7f1d")
            self.filtre_courant = nom
        except Exception as e:
            try:
                self.cam_pilotee.begin_live()   # repartir, même en échec
            except Exception:
                pass
            self._filtre_info = (f"Filtre {nom} : {e}", "#d04040")

    def _appliquer_demande_tec(self):
        """Consigne de régulation ou arrêt du TEC — demande posée par le
        thread Tk, exécutée ICI (thread de travail), résultat → _tick."""
        dem = self._tec_demande
        if dem is None or self.cam_pilotee is None:
            return
        self._tec_demande = None
        try:
            if dem[0] == "consigne":
                self.cam_pilotee.consigne_refroidissement(dem[1])
                self._tec_info = (f"Consigne TEC : {dem[1]:.0f} °C", "#1d7f1d")
            else:
                self.cam_pilotee.arreter_refroidissement()
                self._tec_info = ("Refroidissement arrêté", "#c98a00")
        except Exception as e:
            self._tec_info = (f"TEC : {e}", "#d04040")

    def _sonder_controles(self):
        """Sondage des contrôles (roue à filtres / refroidissement) après
        la CONNEXION — plus besoin d'attendre une frame (jalon 26 : on doit
        pouvoir refroidir et choisir le filtre AVANT d'empiler). Toutes les
        lectures SDK sont protégées (try/except), comme tout appel de
        contrôle : un échec = fonction absente, jamais un crash. Le
        résultat est consommé par _tick (thread Tk seul)."""
        if self.cam_pilotee is not None:
            try:
                self._roue_ok = self.cam_pilotee.roue_disponible()
            except Exception:
                self._roue_ok = False
            try:
                if self.cam_pilotee.lire_refroidissement() is not None:
                    self._tec_ok = True
            except Exception:
                pass

    def _worker(self):
        last_good = None
        self._controles_sondes = False
        # Jalon 26 : le thread est PERMANENT — tant que la caméra est
        # connectée, il continue de piloter les contrôles (roue, TEC,
        # réglages) même quand l'EMPILEMENT est en pause (« ■ Arrêter ») ;
        # c'est ce qui permet de régler/refroidir AVANT puis ENTRE les
        # sessions d'empilement.
        while self.running:
            t0 = time.perf_counter()

            # Sondage des contrôles une fois, dès la connexion (la caméra
            # est ouverte : les contrôles répondent sans attendre une frame).
            if not self._controles_sondes and self.cam_pilotee is not None:
                self._controles_sondes = True
                try:
                    self._sonder_controles()
                except Exception:
                    pass

            # Demandes filtre / refroidissement posées côté Tk — traitées
            # ICI (thread de travail, jamais d'appel SDK depuis le thread Tk).
            try:
                self._appliquer_filtre_demande()
                self._appliquer_demande_tec()
            except Exception:
                pass

            # Relecture TEC (temp/PWM/consigne) toutes les 2 s — display
            # permanent, empilement démarré ou non.
            if (self.cam_pilotee is not None
                    and time.monotonic() - self._tec_dernier_t0 >= 2.0):
                self._tec_dernier_t0 = time.monotonic()
                try:
                    self._tec_dernier = self.cam_pilotee.lire_refroidissement()
                except Exception:
                    pass

            if self.pending_settings is not None:
                self.camera.apply_settings(*self.pending_settings)
                self.pending_settings = None

            # Jalon 27 : OFFSET (contrôle 7, SDK QHY) — demande posée par
            # le thread Tk, exécutée ICI ; no-op silencieux pour les sources
            # qui n'ont pas d'offset (base no-op).
            if self.pending_offset is not None:
                off, self.pending_offset = self.pending_offset, None
                try:
                    self.camera.definir_offset(off)
                except Exception:
                    pass

            # (Le mécanisme « déconnexion demandée au worker » du jalon 26b
            # a été SUPPRIMÉ (décision d'Alain, 20/09/2026 : la version
            # simple côté thread Tk fonctionne) — le worker ne ferme plus
            # jamais la caméra lui-même.)

            # Jalon 26 : « ▶ Démarrer » (empilement_start_request) → RESET
            # COMPLET de session exécuté ICI (thread de travail) — l'UI ne
            # touche jamais aux objets vivants du worker. Purge d'abord des
            # frames restées dans la file du SDK (sessions précédentes /
            # attente caméra connectée).
            # v2.41.0 : « Réinitialiser l'empilement » (reset_request) emprunte
            # EXACTEMENT le même chemin — et il est servi ICI, en TÊTE de
            # boucle, donc MÊME EMPILEMENT EN PAUSE. Avant, ce drapeau n'était lu
            # qu'en TRAITANT une frame : cliquer « Réinitialiser » à l'arrêt ne
            # réinitialisait RIEN (constat d'Alain, 28/09/2026 : « il faudrait
            # que le bouton réinitialiser réinitialise vraiment ») et la session
            # suivante repartait sur l'empilement de la cible précédente. Seule
            # différence entre les deux : « Réinitialiser » ne RELANCE pas
            # l'empilement (il reste en pause).
            if self.empilement_start_request or self.reset_request:
                demarrer = bool(self.empilement_start_request)
                self.empilement_start_request = self.reset_request = False
                self.empilement_on = False
                self.aligner = StarAligner()
                self.stacker = None
                self.disp.reset()          # stats d'affichage repartent de zéro
                self._vl_frames = None     # le 1er empilement relancera le solveur
                self.bad_frames, self.fps = 0, 0.0
                self.floues_rejetees = 0   # jalon 17 : compteur de session
                self._fwhm_hist = []       # jalon 17 : mesures de session neuve
                self._fwhm_par_role = {}   # jalon 19 : idem, PAR RÔLE (compo)
                self.seeing, self.seeing_msg = None, ""   # jalon 10
                self._seeing_t0 = 0.0      # → dès la 1re frame
                self.disp.vl_seeing = None   # jalon 12 : PSF de session neuve
                self.show_stack = None
                self.last_show = None
                self._session += 1         # invalide tout traitement externe en vol
                self._vider_archive()      # jalon 15/16 : archive de session neuve
                self.restack_request = False
                self._ref_score = self._ancre_score = None
                self._ancre_idx = None
                self._ancre_role = None
                self._restack_depuis = 0
                self.restack_info = ""     # jalon 18 : état dédié de session neuve
                self.restack_couleur = "#888888"
                self.restack_total = 0
                self.restack_hist = []
                # Jalon 56 : astrométrie de session neuve — indices conservés
                # (ils viennent de l'UI/instantané), WCS oublié.
                self.suivi_astro.reset()
                self.astro_info = ""
                self.astro_couleur = "#888888"
                self._astro_wcs_secours = None
                self._astro_aveugles = 0
                self._astro_dernier_aveugle = 0.0
                self._astro_fov_essayes = set()
                self._astro_balayage = None
                self._astro_source = ""
                # Jalon 56 (étape 4) : photométrie de session neuve.
                self.photometrie.reset()
                self.photo_info = ""
                self.photo_couleur = "#888888"
                self._photo_essais = 0
                self._photo_dernier = 0.0
                self._photo_gains_pose = {}
                # Jalon 58 : SPCC de session neuve (mêmes raisons).
                if getattr(self, "spcc", None) is not None:
                    self.spcc.reset()
                self.spcc_info = ""
                self.spcc_couleur = "#888888"
                self._spcc_essais = 0
                self._spcc_dernier = 0.0
                self.proc_show = self.proc_full = None
                self.proc_entete = None           # v2.38.3
                self.proc_new = False
                self.save_asseen_request = None   # sauvegarde « tel que vu » annulée
                self.asseen_busy = False
                self.asseen_result = None
                self.ext_request = False
                self.ext_busy = False
                self.ext_state = "idle"
                self.ext_t0 = None
                self._ext_popup = False
                self.zoom, self.view_cx, self.view_cy = 1.0, None, None
                self._last_disp = None
                self.q = queue.Queue(maxsize=2)
                if isinstance(self.camera, QHYCamera):
                    # Purge de la file du SDK UNIQUEMENT pour un flux live
                    # (les sources « dossier » consommeraient de VRAIES
                    # frames — jamais jetées).
                    t_purge = time.monotonic()
                    while time.monotonic() - t_purge < 0.3:
                        self.camera.read()
                self.empilement_on = demarrer   # « Réinitialiser » ne démarre pas

            # v2.41.0 : la SOURCE peut avoir été REFERMÉE par l'interface
            # (« Réinitialiser l'empilement » sur une source de fichiers,
            # « ⏏ Déconnecter ») : le worker SURVIT au lieu de mourir sur un
            # `None.read()` (une exception dans un thread tue le thread EN
            # SILENCE — plus aucune frame n'arrivait ensuite, et rien ne le
            # disait). Il attend ici la prochaine source ; c'est « ▶ Démarrer »
            # qui la crée, et qui le relance s'il s'était arrêté.
            if self.camera is None:
                self._servir_demandes_sans_frame()
                time.sleep(0.02)
                continue

            # Traitement externe demandé → thread dédié, l'acquisition continue.
            # Placé AVANT la lecture d'une frame : doit fonctionner même si
            # aucune brute n'arrive (acquisition en pause, dossier silencieux…).
            if self.ext_request and self.stacker is not None and not self.ext_busy:
                stack_now = self.stacker.mean()
                if stack_now is not None:
                    self.ext_request = False
                    self.ext_busy = True
                    threading.Thread(target=self._run_external,
                                     args=(stack_now, self.stacker.n, self._session),
                                     daemon=True).start()

            # Sauvegarde « tel que vu » (jalon 5) → thread dédié, l'acquisition
            # continue : le rendu pleine résolution (GraXpert live + étirement)
            # peut prendre plusieurs secondes.
            # Chantier 24/09/2026 : 4e élément `lineaire` — la 3e sortie
            # « empilement traité (linéaire) » emprunte la MÊME chaîne mais
            # part de l'empilement BRUT (mean(corrections=False)) et s'arrête
            # avant l'étirement.
            if (self.save_asseen_request is not None and self.stacker is not None
                    and self.stacker.n > 0 and not self.asseen_busy):
                req = self.save_asseen_request
                self.save_asseen_request = None
                path, vue, reglages = req[:3]
                lineaire = bool(req[3]) if len(req) > 3 else False
                if vue == "traitée" and self.proc_full is None:
                    self.asseen_result = ("ERREUR: aucun résultat traité à "
                                          "enregistrer")
                else:
                    if vue == "traitée":
                        # copie défensive : proc_full peut être remplacé
                        source = self.proc_full.astype(np.float32).copy()
                        canaux = None
                    else:
                        # Pleine résolution. « tel que vu » : le composite de la
                        # chaîne affichée (corrections comprises) ; 3e sortie
                        # linéaire : l'empilement BRUT — les corrections sont
                        # appliquées plus loin, après le débruitage (décision (c)).
                        source = self.stacker.mean(corrections=not lineaire)
                        # Couches BRUTES : en COMPOSITION, la chaîne
                        # GraXpert/débruitage du fichier est faite PAR COUCHE
                        # (comme le solveur live) — le composite dépasse 1 et
                        # serait rescale/écrêté (cf. _couches_pleine_resolution).
                        canaux = self._couches_brutes()
                    self.asseen_busy = True
                    threading.Thread(
                        target=self._save_asseen_thread,
                        args=(path, vue, source, reglages, self._session,
                              lineaire, canaux),
                        daemon=True).start()

            # Sauvegarde LINÉAIRE de l'empilement : consommation de la demande
            # AVANT la lecture d'une frame — doit fonctionner même si aucune
            # brute n'arrive (dossier surveillé terminé, caméra en pause…).
            # Historiquement placé APRÈS l'empilement d'une nouvelle frame :
            # sans nouvelles frames, le worker ne l'atteignait JAMAIS
            # (demande silencieusement ignorée — constat Alain, 16/09/2026).
            if (self.save_request is not None and self.stacker is not None
                    and self.stacker.n > 0):
                path, self.save_request = self.save_request, None
                try:
                    # Jalon 25 : mot-clé FILTER (roue à filtres QHY) — utile
                    # pour les dossiers N.I.N.A. et la détection des rôles.
                    # v2.27.1 : l'empilement est BORNÉ à [0,1] avant écriture
                    # (borner_lineaire) — le composite d'une composition
                    # multi-dossiers dépasse largement 1 (cœur de galaxie
                    # normalisé par percentiles) : écrit tel quel, le fichier
                    # n'était PAS résolvable par ASTAP (« Only 0 stars found
                    # in image ») et paraissait saturé partout ailleurs
                    # (retour réel d'Alain, 22/09/2026, M31 RGB en mode
                    # dossiers). Mono : no-op (l'empilement est déjà ≤ 1).
                    img = self.stacker.mean(corrections=False)
                    # Jalon 56 : mots-clés WCS de la grille RÉELLEMENT écrite
                    # (recadrage d'intersection inclus) — le FITS devient
                    # localisable par Siril/astropy/PixInsight. Sans
                    # astrométrie résolue : en-tête inchangé (jamais de
                    # mot-clé faux dans un fichier).
                    entete = self._astro_entete_sauvegarde(
                        {"FILTER": self.filtre_courant}
                        if self.filtre_courant else None,
                        img.shape[:2] if img is not None else None)
                    # Question d'Alain (« la sauvegarde linéaire, elle sauvegarde
                    # quoi au juste ? ») : le fichier DÉCRIT ce qu'il contient.
                    # Chantier 24/09/2026 : plus AUCUNE correction de couleur
                    # ici (`applique=False`) — AVASPCC/AVAGAIA restent la MESURE
                    # (ce qui a été mesuré), AVAAPPLI dit ce qui est APPLIQUÉ au
                    # fichier (« aucune (empilement BRUT) »).
                    entete.update(self._entete_reglages(applique=False))
                    entete["AVAVUE"] = ("empilement BRUT (lineaire, sans "
                                        "etirement)")
                    img, entete = borner_lineaire(img, entete)
                    save_image(path, img, entete=entete)
                    self.saved_path = path
                    # Ce qui est ÉCRIT dans le fichier, montré à l'utilisateur
                    # (constat du 25/09/2026 : on ne savait pas, à la lecture du
                    # dialogue, si la SPCC était entrée dans le fichier ou non).
                    self.dernier_applicatif = entete.get("AVAAPPLI")
                except Exception as e:
                    self.saved_path = f"ERREUR: {e}"

            # Jalon 19 : sauvegarde des empilements PAR CANAL (mode compo) —
            # un fichier « canal_<rôle>.fit » par rôle empilé, linéaire et
            # recadré au cadre commun (composite = bouton « Enregistrer »).
            if (self.save_canaux_request is not None and self._mode_compo
                    and self.stacker is not None and self.stacker.n > 0):
                d_canaux, self.save_canaux_request = \
                    self.save_canaux_request, None
                try:
                    for role, carte in self.stacker.moyennes().items():
                        # v2.27.1 : même garantie d'échelle que la sauvegarde
                        # du composite (no-op ici en pratique : une moyenne de
                        # rôles reste ≤ 1).
                        # Jalon 56 : les couches sont empilées sur la MÊME
                        # grille que le composite → mêmes mots-clés WCS que
                        # la sauvegarde de l'empilement (recadrage inclus).
                        bordee, entete = borner_lineaire(
                            carte,
                            self._astro_entete_sauvegarde(
                                {"FILTER": role}, carte.shape[:2]))
                        # Ces fichiers sont les COUCHES BRUTES (moyenne par rôle,
                        # sans normalisation par canal ni gain) : la SPCC et la
                        # photométrie MESURENT sur ces mêmes valeurs — le dire
                        # dans l'en-tête évite toute confusion.
                        entete["AVALAYER"] = "couche BRUTE (ni normalisation, ni gain)"
                        # Aucune correction de couleur n'est appliquée à une
                        # couche (elle est BRUTE par construction) : le dire
                        # explicitement (étape ⑥).
                        entete.update(self._entete_reglages(applique=False))
                        save_image(os.path.join(
                            d_canaux, f"canal_{role}.fit"), bordee,
                            entete=entete)
                    self.saved_path = d_canaux
                except Exception as e:
                    self.saved_path = f"ERREUR: {e}"

            # Jalon 55 : réglages saisis en cours de session (gains compo,
            # canal L, Linear Fit) — resynchronisés sur le stacker À CHAQUE
            # tour. AVANT : posés à la création SEULEMENT (jalon 19) — un
            # gain changé en cours de session n'avait AUCUN effet sur la
            # vue « empilement » ni sur les sauvegardes (constat Alain :
            # « bouger un gain ne change rien »).
            if self.stacker is not None:
                if self._mode_compo:
                    self.stacker.gains = dict(self._compo_gains or {})
                    self.stacker.mode_l = self._compo_mode_l
                    # v2.36.0 : normalisation commune (option) — resynchronisée
                    # à chaque tour, comme les gains et le canal L.
                    if hasattr(self.stacker, "normalisation_commune"):
                        self.stacker.normalisation_commune = bool(
                            self._norm_commune)
                self.stacker.linear_fit = bool(self._fit_actif)
                self.stacker.linear_fit_mode = self._fit_mode
                # Jalon 56 (étape 5) : gains PHOTOMÉTRIQUES par rôle — écrits
                # dans le stacker SEULEMENT si la case opt-in est cochée, qu'une
                # mesure existe et qu'on est en COMPOSITION (un gain global en
                # mono n'a pas de sens). Comparé à ce qui est déjà posé : tout
                # changement force le rafraîchissement du rendu sans attendre
                # une nouvelle brute (leçon du jalon 55).
                if self._mode_compo and hasattr(self.stacker, "gains_roles"):
                    # Jalon 58 : la SPCC ABSOLUE prime sur les gains Gaia
                    # RELATIFS (elle compare des RATIOS de couleur prédits par
                    # les spectres, au lieu d'une magnitude G trop large) —
                    # chacune n'agit que si SA case est cochée.
                    if (self._spcc_actif and self.spcc is not None
                            and self.spcc.valide):
                        nouveaux = dict(self.spcc.gains())
                    elif (self._photo_gains_actif
                            and self.photometrie is not None
                            and self.photometrie.valide):
                        nouveaux = dict(self.photometrie.gains)
                    else:
                        nouveaux = {}
                    if nouveaux != (self.stacker.gains_roles or {}):
                        self.stacker.gains_roles = nouveaux
                        self._photo_gains_pose = dict(nouveaux)
                        self._rafraichir_rendu = True
                elif (self._source_rgb(self.stacker)
                      and hasattr(self.stacker, "gains")):
                    # v2.40.0 : source COULEUR (capteur OSC en mode dossier) —
                    # la SPCC y corrige DIRECTEMENT les canaux R/G/B de
                    # l'empilement (`LiveStacker.gains`, appliqués avant
                    # l'équilibrage et le recalage, comme la chaîne de sortie).
                    # Les gains Gaia RELATIFS restent, eux, réservés à la
                    # composition : ils sont mesurés par RÔLE, et une source
                    # couleur simple n'a pas de rôles.
                    nouveaux = (dict(self.spcc.gains())
                                if (self._spcc_actif and self.spcc is not None
                                    and self.spcc.valide) else {})
                    if nouveaux != (self.stacker.gains or {}):
                        self.stacker.gains = nouveaux
                        self._photo_gains_pose = dict(nouveaux)
                        self._rafraichir_rendu = True
                # Aucune brute à lire (mode dossier consommé, pause…) : si
                # un réglage vient de changer, le rendu est recalculé et
                # repoussé UNE fois — sinon l'affichage reste figé sur les
                # réglages du démarrage jusqu'à la prochaine brute.
                if self._rafraichir_rendu:
                    self._rafraichir_rendu = False
                    if self.stacker.n > 0 and self._dernier_st is not None:
                        self._pousser_rendu()

            # v2.41.0 : empilement EN PAUSE sur une source FICHIERS → on ne lit
            # RIEN. Pourquoi : une brute lue pendant la pause était marquée
            # « traitée » puis JETÉE (le `if not self.empilement_on` ci-dessous
            # ne gardait que la lecture d'une caméra live) — elle ne pouvait
            # plus JAMAIS être empilée, ni à la reprise, ni après une nouvelle
            # remise à zéro. C'est exactement la fenêtre « je finis une cible,
            # je prépare la suivante » (constat d'Alain, 28/09/2026). Le dossier
            # est seulement SCANNÉ, pour que l'état « brutes en attente » reste
            # juste ; les fichiers attendent sur le disque.
            if not self.empilement_on and self._cadence_dossier():
                maintenant = time.monotonic()
                if maintenant >= self._prochain_scan:   # au plus toutes les 0,4 s
                    try:
                        self.camera.scanner()
                    except Exception:
                        pass
                    self._prochain_scan = maintenant + 0.4
                self._servir_demandes_sans_frame()
                time.sleep(0.05)
                continue

            # Jalon 42 : cadence d'empilement (sources dossier, cf.
            # _autoriser_lecture). Le scan SANS lecture ne tourne que si une
            # cadence est posée, au plus toutes les 0,4 s — il permet de
            # connaître les brutes EN ATTENTE SUR LE DISQUE avant de décider
            # de lire (sinon la décision ne porterait que sur ce qui a déjà
            # été détecté, et chaque brute isolée serait lue immédiatement).
            if self.cadence_lecture > 0 and self._cadence_dossier():
                maintenant = time.monotonic()
                if maintenant >= self._prochain_scan:
                    try:
                        self.camera.scanner()
                    except Exception:
                        pass
                    self._prochain_scan = maintenant + 0.4
            lu = None
            if self._autoriser_lecture():
                try:
                    lu = self.camera.read()
                except AttributeError:
                    # v2.41.0 : la source vient d'être refermée par
                    # l'interface (réinitialisation d'une source de fichiers) —
                    # le tour suivant la verra absente et attendra proprement,
                    # au lieu de tuer ce thread en silence.
                    continue
            if lu is None:
                # v2.37.0 : aucune frame à lire (fin de source, lecture en
                # pause) — les demandes qui ne dépendent PAS d'une frame sont
                # servies ICI (SPCC/photométrie redemandées par leur case).
                self._servir_demandes_sans_frame()
                time.sleep(0.005)
                continue
            # Jalon 26 : empilement en pause (« ■ Arrêter ») sur une CAMÉRA →
            # on maintient la lecture du flux (la caméra reste connectée, la
            # file du SDK se vide : elle s'accumulerait sinon en mémoire) mais
            # on n'empile rien. (Les sources FICHIERS, elles, ne sont plus
            # lues du tout en pause — cf. le garde ci-dessus.)
            if not self.empilement_on:
                self._servir_demandes_sans_frame()   # idem : mesures sans frame
                time.sleep(0.05)
                continue
            # Jalon 19 : source « composition » → read() renvoie (img, rôle).
            if self._mode_compo:
                frame, role = lu
            else:
                frame, role = lu, None
            frame = self.calib.apply(frame, role=role)
            self._a_lu_une_frame = True   # jalon 42 : une brute vient d'être lue
            self._rafale_reste -= 1       # jalon 46 : budget de rafale consommé

            # Jalon 17 : filtre anti-brutes TRÈS DÉFOCALISÉES — AVANT tout le
            # reste (une frame rejetée n'est ni archivée ni empilable, donc
            # jamais ramenée par un re-stack). Rejet d'office, case pour
            # désactiver (décision d'Alain). La mesure (~15 ms) est presque
            # rien devant une pose de 120 s. La frame rejetée est comptée,
            # signalée sur la ligne d'alignement, et le worker respire (au
            # plus 20 analyses/s) sans empiler ni déclencher de re-calage.
            verdict = self._filtre_floue(frame, role=role)
            if verdict:
                self.floues_rejetees += 1
                self.align_info = verdict
                time.sleep(max(0.0, 1.0 / 20.0 - (time.perf_counter() - t0)))
                continue

            # Jalon 15 : chaque frame calibrée est archivée (dossier temp de
            # session, garde-fous débit/taille) — matière du futur re-stack
            # « à la Siril » (recalcul sur une meilleure référence). Aucun
            # échec d'archivage n'interrompt l'empilement (erreur exposée).
            # Jalon 19 : extraction du CANAL du rôle (mono → tel quel ; CFA
            # débayerisé → canal dominant du rôle, CANAUX_CFA). Tout le reste
            # du flux (référence, alignement, empilement) travaille sur ce
            # canal 2D — le repère reste COMMUN (aligneur unique, décision
            # tranchée du 18/09/2026).
            img_travail = (extraire_canal(frame, role)
                           if self._mode_compo else frame)
            if self.stacker is not None \
                    and self.stacker.shape != img_travail.shape:
                # changement de géométrie : les frames archivées (autre
                # taille) ne sont plus ré-empilables → archive neuve
                self._vider_archive()
            if self._mode_compo:          # archive PAR RÔLE (re-stack jalon 20)
                chemin_archive = self.archives.setdefault(
                    role, ArchiveFrames()).ajouter(frame)
            else:
                chemin_archive = self.archive.ajouter(frame)
            if chemin_archive is not None:
                if self._mode_compo:
                    # Jalon 20 : score qualité PAR RÔLE — mesuré sur le CANAL
                    # EXTRAIT (img_travail, la même image que l'alignement),
                    # donc comparable d'une couche à l'autre pour choisir la
                    # meilleure brute TOUS RÔLES confondus.
                    self._scores_par_role.setdefault(role, []).append(
                        self._score_frame(img_travail))
                    self._restack_depuis += 1
                else:
                    # Jalon 16 : score qualité (nb d'étoiles détectées, canal
                    # vert) de chaque brute archivée — matière du choix de
                    # référence à la Siril (meilleure référence + re-stack).
                    self._scores.append(self._score_frame(frame))
                    self._restack_depuis += 1

            # (re)création de l'empilement / nouvelle référence — SEULEMENT
            # si la frame a passé le filtre jalon 17 (une brute très floue ne
            # doit jamais devenir la référence d'alignement ni créer
            # l'empilement — c'est le défaut que le filtre élimine).
            # Jalon 21 (décision d'Alain) : HOO/SHO — l'ancre initiale est
            # TOUJOURS une brute Ha. Tant qu'aucune brute Ha n'est arrivée,
            # les frames des autres rôles (déjà archivées) ne créent PAS
            # l'empilement ; à la 1re Ha, l'ancre est posée sur elle et les
            # frames archivées entre-temps sont rejouées (via
            # _do_restack_compo, exactement comme un re-stack).
            deja_rejoue = False
            if (self._mode_compo and self._narrowband_ha()
                    and self.stacker is None and role != "Ha"):
                self.align_info = ("en attente d'une brute Ha "
                                   "(référence d'alignement)…")
            # v2.41.0 : `reset_request` n'est PLUS lu ici — la remise à zéro
            # complète est servie en TÊTE de boucle (donc même en pause) ; la
            # laisser ici la consommerait sans refaire le reste (archive,
            # compteurs, mesures). Ne reste donc que le vrai changement de
            # géométrie.
            elif (self.stacker is None
                    or self.stacker.shape != img_travail.shape):
                etait_vide = self.stacker is None
                if self._mode_compo:       # façade multi-rôles : un stacker
                    self.stacker = CompositeStacker(   # par rôle, mean() =
                        self._compo_nom,   # composite (cadre commun)
                        k=self.kappa, method=self.rejet_methode,
                        window=self.rejet_fenetre)
                    # Jalon 19 phase 3 : gains + canal L posés dès la
                    # création (instantanés tenus à jour par _tick).
                    self.stacker.gains = dict(self._compo_gains or {})
                    self.stacker.mode_l = self._compo_mode_l
                    self.stacker.normalisation_commune = bool(
                        self._norm_commune)          # v2.36.0 (option)
                else:
                    self.stacker = LiveStacker(img_travail.shape, k=self.kappa,
                                               method=self.rejet_methode,
                                               window=self.rejet_fenetre)
                self.stacker.wb_auto = bool(self.var_wb.get())
                self.stacker.wb_force = float(self.var_wb_force.get())
                # Jalon 54 : recalage « Linear Fit » posé dès la création —
                # via l'INSTANTANÉ (le worker n'a jamais le droit de lire
                # les variables Tk) ; les changements de la case passent
                # par _on_linear_fit (thread principal).
                self.stacker.linear_fit = bool(self._fit_actif)
                self.stacker.linear_fit_mode = self._fit_mode
                self.aligner.reset()
                # Jalon 21 : HOO/SHO → TRIANGLES seuls pour toute la session.
                self.aligner.triangles_seuls = self._narrowband_ha()
                self._definir_reference(img_travail)
                self.disp.reset()          # stats d'affichage repartent de zéro
                # Jalon 21 : 1re brute Ha → ancre + rejeu des frames
                # archivées entre-temps (les autres rôles arrivés avant).
                if (etait_vide and self._mode_compo and self._narrowband_ha()
                        and role == "Ha"
                        and self.archives.get(role, ArchiveFrames()).n > 0):
                    idx_ancre = len(self.archives[role].chemins) - 1
                    self._ancre_role, self._ancre_idx = role, idx_ancre
                    info = self._do_restack_compo(
                        f"ancre {role} (démarrage)", ancre_role=role,
                        ancre_idx=idx_ancre)
                    if info:
                        self.align_info = info
                    deja_rejoue = True

            stack = None
            canaux = None
            if self.stacker is not None and not deja_rejoue:
                M, ok = self.aligner.compute(img_travail)
                if ok:
                    aligned = cv2.warpAffine(img_travail, M,
                                             (img_travail.shape[1],
                                              img_travail.shape[0]),
                                             flags=cv2.INTER_LINEAR)
                    if self._mode_compo:       # routage vers le stacker du rôle
                        self.stacker.role_courant = role
                    self.stacker.add(aligned)
                    self.stacker.note_alignement(M)   # intersection des zones
                    last_good = aligned
                    self._ref_bad = 0
                else:
                    self.bad_frames += 1
                    self._ref_bad += 1
                    # Jalon 13 : dossier MIXÉ (brutes de plusieurs nuits, p.ex.
                    # TargetSchedulerSequence de NINA) — si TOUT refuse alors que
                    # l'empilement est quasi vide (≤ 2 frames), la référence
                    # (1re frame, autre nuit — ou une ancre faussée) ne convient
                    # à rien : on la recale sur la frame courante. Sûr : ≤ 2
                    # frames d'ancien repère dans l'accumulation seront rejetées
                    # ensuite par la médiane Winsorized (dilution). (Jalon 17 :
                    # la frame courante a déjà passé le filtre défocalisation.)
                    if self.stacker.n <= 2 and self._ref_bad >= 3:
                        self._definir_reference(frame)
                        self._ref_frames = self._ref_bad = 0
                self._ref_frames += 1
                # Jalon 13 : ligne d'état de l'alignement (Δ, θ, méthode ou refus).
                if ok and self.aligner.dernier:
                    d = self.aligner.dernier
                    self.align_info = (f"Δ=({d['dx']:+.1f},{d['dy']:+.1f}) px · "
                                       f"θ {d['angle']:+.2f}° · {d['methode']}")
                elif not ok:
                    self.align_info = "refus (frame non empilée)"

                stack = self.stacker.mean()

            # Jalon 13 : rafraîchissement AUTOMATIQUE de la référence — la
            # dérive lente éloigne les frames de la référence initiale et
            # l'appariement dégénère ; une référence JEUNE (l'empilement,
            # SANS recadrage → même repère que les frames alignées) suit.
            # Déclencheurs : toutes les N frames, ou ≥ 50 % de frames
            # refusées (et ≥ 3) depuis le dernier — sinon on ne se remet
            # jamais d'une série d'échecs (la prédiction reste bloquée).
            if stack is not None and self.ref_refresh > 0 and (
                    self._ref_frames >= self.ref_refresh
                    or (self._ref_bad >= 3
                        and 2 * self._ref_bad >= self._ref_frames)):
                self._definir_reference(self.stacker.mean(recadre=False))
                self._ref_frames = self._ref_bad = 0

            if self.ref_request and stack is not None:
                self.ref_request = False
                # jalon 13 : SANS recadrage (même repère que les frames —
                # l'ancien code passait l'empilement RECADRÉ : chaque clic
                # décalait silencieusement tout l'empilement de (y0, x0))
                self._definir_reference(self.stacker.mean(recadre=False))

            # Jalon 16 : re-stack sur la MEILLEURE brute archivée (choix de
            # référence à la Siril) — auto si une brute bat nettement la
            # référence courante (marge en étoiles), ou sur bouton. Le
            # recalcul rejoue TOUTES les frames archivées : celles qui
            # avaient refusé avec l'ancienne référence ont une seconde chance.
            # Jalon 20 : le re-stack s'applique AUSSI au mode compo — la
            # meilleure brute, TOUS RÔLES confondus, re-ancre l'aligneur
            # PARTAGÉ et toutes les couches sont recalculées depuis les
            # archives PAR RÔLE (chaque couche a ses mauvaises frames).
            n_arch = (sum(a.n for a in self.archives.values())
                      if self._mode_compo else self.archive.n)
            if (self.stacker is not None and (
                    self.restack_request
                    or (n_arch >= RESTACK_MIN_FRAMES
                        and self._restack_depuis >= RESTACK_CADENCE
                        and self._veut_restack()))):
                raison = "bouton" if self.restack_request else "auto"
                self.restack_request = False
                info = self._do_restack(raison)
                if info:
                    self.align_info = info
                    stack = self.stacker.mean()   # affichage immédiat

            # Jalon 56 : astrométrie de l'empilement — APRÈS le re-stack (le
            # WCS doit décrire la grille COURANTE : la propagation vient d'y
            # pourvoir), AVANT la construction de l'état poussé à l'UI (la
            # ligne d'état part alors avec le bon texte).
            if self.stacker is not None and self.stacker.n > 0:
                self._astro_tour(self.stacker)
                # Jalon 56 (étape 4) : photométrie — APRÈS l'astrométrie (elle
                # a besoin du WCS résolu) ; mesure SANS effet sur l'image.
                self._photo_tour(self.stacker)
                # Jalon 58 : SPCC absolue — APRÈS la photométrie (mêmes
                # prérequis) ; elle PRIORISE ses coefficients sur les gains
                # Gaia relatifs quand sa case est cochée.
                self._spcc_tour(self.stacker)

            show = stack if stack is not None else (last_good if last_good is not None else frame)

            # Jalon 24 : couches de la composition (même passe que le
            # composite — ni double calcul, ni incohérence entre les deux).
            if stack is not None and self._mode_compo \
                    and hasattr(self.stacker, "mean_avec_canaux"):
                comp, canaux = self.stacker.mean_avec_canaux()
                if comp is not None:
                    stack = comp
            # Aperçu allégé pour l'UI : réactif même en 16 Mpx ; l'étirement est
            # recalculé côté interface → curseurs réactifs entre deux frames.
            h, w = show.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                show = cv2.resize(show, None, fx=scale, fy=scale,
                                  interpolation=cv2.INTER_AREA)
            # v2.38.0 : garde l'empilement COMPLET sous la main pour l'option
            # « Rendu pleine résolution » (copie défensive : le stacker réécrit
            # son tampon à la frame suivante).
            if self._pleine_res_activee():
                self._stack_pleine_res = np.asarray(
                    stack if stack is not None else show, np.float32).copy()
            # v2.37.3/v2.37.4 : le rayon du flou de chroma suit la RÉSOLUTION —
            # l'aperçu est réduit d'un facteur `scale`, les ÉTOILES aussi : à
            # rayon constant en pixels, leur couleur s'étalerait 1/scale fois plus
            # loin à l'écran que dans les fichiers (halo 2,4 fois plus large à
            # 3838 px). Le réglage est le curseur « Rayon de référence » (pleine
            # résolution) : cf. `_poser_rayon_chroma`.
            self._poser_rayon_chroma(scale)
            # Jalon 10 : seeing live (FWHM médiane + nombre d'étoiles) sur
            # l'APERÇU — c'est la résolution sur laquelle la netteté live
            # travaillera, la PSF mesurée y est donc directement exploitable.
            # Mesure au plus toutes les `seeing_periode` s (quelques ms, mais
            # inutile 20 fois par seconde : le seeing ne change pas si vite).
            if time.perf_counter() - self._seeing_t0 >= self.seeing_periode:
                self._seeing_t0 = time.perf_counter()
                self.seeing, self.seeing_msg = seeing_live.mesurer_seeing(show)
                # Jalon 12 : la netteté live consomme cette mesure comme PSF —
                # elle est faite sur l'APERÇU, exactement la résolution où la
                # netteté travaille, et évite une 2e détection d'étoiles dans
                # le solveur. (Affectation atomique : le solveur lit la
                # référence, il ne la modifie jamais.)
                self.disp.vl_seeing = self.seeing
            # Jalon 75 : plus d'histogramme ici — il est calculé par le thread
            # d'affichage, sur l'image réellement montrée (l'aperçu 1600 px
            # d'ici ne décrit pas forcément ce qui est à l'écran : vue
            # « traitée », rendu pleine résolution).

            # Jalon 24 : couches + paramètres de recomposition poussés vers le
            # solveur live (remplacement ENTIER de la référence — jamais de
            # mutation en place, le solveur lit toujours un dict cohérent).
            # Gains/mode_l recopiés des valeurs lues côté thread principal en
            # tête de _tick (le worker n'a jamais le droit de lire les Tk).
            if self._mode_compo and canaux:
                # Jalon 56 (étape 5) puis chantier 24/09/2026 : le solveur live
                # re-compose depuis les couches BRUTES — il doit donc recevoir
                # TOUTES les corrections de couleur, exactement celles que la
                # façade applique à la vue « empilement » (sinon les deux vues
                # divergeraient dès qu'une case est cochée) : gains EFFECTIFS
                # (manuels × SPCC/Gaia), recalage « Linear Fit » et équilibrage
                # des canaux (avec son cadre, pour le fond mesuré).
                gains_eff = (self.stacker.gains_effectifs()
                             if hasattr(self.stacker, "gains_effectifs")
                             else self._compo_gains)
                self.disp.vl_compo = (dict(canaux), self.stacker.composition,
                                      gains_eff, self._compo_mode_l,
                                      # 5e élément (jalon 54) : recalage
                                      # « Linear Fit » — ré-appliqué à la
                                      # recomposition des couches traitées.
                                      (bool(self.stacker.linear_fit),
                                       self.stacker.linear_fit_mode),
                                      # 6e élément (chantier 24/09/2026) :
                                      # équilibrage des canaux (actif, force,
                                      # cadre) — déballage tolérant côté
                                      # display.
                                      (bool(self.stacker.wb_auto),
                                       float(self.stacker.wb_force),
                                       self.stacker.cadre),
                                      # 7e élément (v2.36.0) : normalisation
                                      # COMMUNE des canaux (option d'Alain) —
                                      # la vue « traitée » doit recomposer
                                      # comme la vue « empilement ».
                                      bool(getattr(self.stacker,
                                                   "normalisation_commune",
                                                   False)))
            else:
                self.disp.vl_compo = None

            dt = time.perf_counter() - t0
            inst = 1.0 / max(dt, 1e-4)
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
            # Jalon 19 : en mode compo, `pending` est une propriété (somme
            # des dossiers) et l'archive est tenue PAR RÔLE — totaux pour
            # l'état ; `compo` = état par canal (« Ha: 12 · O3: 9 »).
            if self._mode_compo:
                pend = getattr(self.camera, "pending", 0)
                n_arch = sum(a.n for a in self.archives.values())
                err_arch = "; ".join(a.erreur for a in self.archives.values()
                                     if a.erreur)
            else:
                pend = len(getattr(self.camera, "_pending", []))
                n_arch, err_arch = self.archive.n, self.archive.erreur
            st = dict(frames=(self.stacker.n if self.stacker is not None
                              else 0),
                      rejets=(self.stacker.rejected_total
                              if self.stacker is not None else 0),
                      bad=self.bad_frames, floues=self.floues_rejetees,
                      fps=self.fps, cam=getattr(self.camera, "name", "—"),
                      file=getattr(self.camera, "last_file", ""),
                      pending=pend,
                      failed=getattr(self.camera, "failed", 0),
                      align=self.align_info,
                      seeing=self.seeing, seeing_msg=self.seeing_msg,
                      archive=n_arch, archive_err=err_arch,
                      compo=(self.stacker.etat()
                             if self._mode_compo and self.stacker is not None
                             else None),
                      restack=self.restack_info, restack_n=self.restack_total,
                      astro=self.astro_info, photo=self.photo_info,
                      spcc=self.spcc_info)
            if self.stacker is not None and self.stacker.cadre is not None:
                y0, x0, y1, x1 = self.stacker.cadre
                st["crop_w"], st["crop_h"] = x1 - x0, y1 - y0
            self._dernier_st = st           # jalon 55 : réutilisé par
            try:                            # _pousser_rendu (sans brute)
                self.q.put_nowait((show, st))
            except queue.Full:
                pass
            # Jalon 42 : quand TOUTES les brutes détectées ont été lues, la
            # fenêtre de cadence est (ré)armée — la prochaine rafale n'aura
            # lieu qu'à l'échéance (les brutes qui arrivent entre-temps
            # attendent sur le disque, aucune perte).
            if self._a_lu_une_frame:
                self._armer_cadence()
                self._a_lu_une_frame = False
            time.sleep(max(0.0, 1.0 / 20.0 - (time.perf_counter() - t0)))

    def _pousser_rendu(self):
        """Jalon 55 : recalcule le composite/empilement courant (un réglage
        a changé SANS nouvelle brute — mode dossier consommé) et le pousse à
        l'UI : même chaîne que la fin de boucle (recadrage/fit inclus dans
        mean(), aperçu réduit, couches vers le solveur), SANS l'alignement
        ni la mesure de seeing (rien n'a changé pour eux). Le dict d'état
        du dernier rendu est réutilisé : les compteurs n'ont pas bougé —
        SAUF les lignes de MESURE (astro/photométrie/SPCC/re-stack), qui
        peuvent avoir été réécrites depuis (v2.37.0 : une mesure servie sans
        nouvelle frame ne poussait pas son texte → le libellé restait sur
        l'ancienne valeur, cf. constat d'Alain du 25/09/2026)."""
        canaux = None
        if self._mode_compo and hasattr(self.stacker, "mean_avec_canaux"):
            stack, canaux = self.stacker.mean_avec_canaux()
        else:
            stack = self.stacker.mean()
        if stack is None:
            return
        h, w = stack.shape[:2]
        scale = min(1.0, 1600.0 / float(max(h, w)))
        show = (cv2.resize(stack, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_AREA) if scale < 1.0
                else stack)
        # v2.38.0 : même mémorisation que la boucle d'acquisition, pour l'option
        # « Rendu pleine résolution » de l'écran.
        if self._pleine_res_activee():
            self._stack_pleine_res = np.asarray(stack, np.float32).copy()
        # v2.37.3/v2.37.4 : le rayon du flou de chroma suit la RÉSOLUTION (même
        # règle qu'à la fin de la boucle d'acquisition : l'aperçu est réduit, les
        # étoiles aussi → cf. `_poser_rayon_chroma`).
        self._poser_rayon_chroma(scale)
        if self._mode_compo and canaux:
            gains_eff2 = (self.stacker.gains_effectifs()
                          if hasattr(self.stacker, "gains_effectifs")
                          else self._compo_gains)
            self.disp.vl_compo = (dict(canaux), self.stacker.composition,
                                  gains_eff2, self._compo_mode_l,
                                  (bool(self.stacker.linear_fit),
                                   self.stacker.linear_fit_mode),
                                  (bool(self.stacker.wb_auto),
                                   float(self.stacker.wb_force),
                                   self.stacker.cadre),
                                  bool(getattr(self.stacker,
                                               "normalisation_commune", False)))
        else:
            self.disp.vl_compo = None
        # v2.37.0 : les lignes de MESURE du dict réutilisé sont RAFRAÎCHIES
        # (voir la docstring) — les compteurs, eux, n'ont pas bougé.
        if isinstance(getattr(self, "_dernier_st", None), dict):
            self._dernier_st.update(astro=self.astro_info, photo=self.photo_info,
                                    spcc=self.spcc_info,
                                    restack=self.restack_info)
        try:
            self.q.put_nowait((show, self._dernier_st))
        except queue.Full:
            pass

    def _servir_demandes_sans_frame(self):
        """v2.37.0 — demandes de l'utilisateur qui NE dépendent PAS d'une
        nouvelle brute, servies par le worker même quand aucune frame n'est
        lisible ou que l'empilement est en pause.

        Constat d'Alain (25/09/2026) : « je voulais refaire calculer la SPCC mais
        étant en fin de stack, ben ça le fait pas en décochant et recochant et ça
        ne met donc rien à jour (le libellé dessous ne passe pas au vert et reste
        gris avec les anciennes valeurs) ». Cause : en fin de source (dossier
        épuisé) ou après « ■ Arrêter », le worker sortait par « lu is None » ou
        « not empilement_on » AVANT les tours de mesure (_astro_tour /
        _photo_tour / _spcc_tour) : la mesure n'était donc tentée qu'à la
        PROCHAINE frame, qui n'arrive jamais. Les mesures ne dépendent que de
        l'EMPILEMENT COURANT : les servir ici ne coûte rien (elles gardent leurs
        propres délais/plafonds et ne repartent que sur demande explicite d'une
        case — jamais en boucle)."""
        if self.stacker is None or self.stacker.n <= 0:
            self._spcc_demande = self._photo_demande = False
            return
        servi = False
        if self._spcc_demande:
            self._spcc_demande = False
            self._spcc_tour(self.stacker)      # garde-fous internes (valide,
            servi = True                       # actif, essais, WCS, frames)
        if self._photo_demande:
            self._photo_demande = False
            self._photo_tour(self.stacker)
            servi = True
        if servi:
            self._pousser_rendu()              # le texte de mesure part à l'UI

    @staticmethod
    def _histogrammes(img, plage=None):
        """(conservé pour les bancs et les diagnostics) Histogrammes R/V/B
        d'une image — relais de `App._hist_canaux`, jalon 75."""
        return App._hist_canaux(img, plage)

    # ------------------------------------------------------------ rafraîchissement UI
    def _tick(self):
        # v2.38.11 : résultats des MESURES DE DISQUE différées (fil démon borné ;
        # le fil ne touche AUCUN widget — il ne pose qu'un dictionnaire ici).
        while getattr(self, "_mesures", None) is not None:
            try:
                msg = self._mesures.get_nowait()
            except queue.Empty:
                break
            self._appliquer_mesures(msg)
        # Jalon 70 : messages du TÉLÉCHARGEMENT des catalogues (thread → UI).
        # Le thread réseau ne touche AUCUN widget : il ne pose que des messages
        # ici, et c'est ce thread Tk qui les traduit en texte.
        while getattr(self, "_cat_q", None) is not None:
            try:
                msg = self._cat_q.get_nowait()
            except queue.Empty:
                break
            genre = msg[0]
            # Jalon 77 : les transferts des spectres et de la base SPCC passent
            # par la MÊME file ; leur nature est le DERNIER élément (les
            # messages de l'astrométrie, historiques, n'en ont pas).
            quoi = msg[-1] if len(msg) >= 3 and msg[-1] in ("spectres", "spcc") \
                else "astro"
            if genre == "progres":
                _, nom, frac = msg[0], msg[1], msg[2]
                self.lbl_cat_etat.config(
                    text=(f"téléchargement {nom} : {frac * 100:.0f} % "
                          "(la reprise est automatique si la connexion coupe)"),
                    foreground="#c98a00")
            elif genre == "fini":
                self._cat_dl_actif = False
                self._regler_boutons_dl(False)
                if quoi == "spcc":
                    self._maj_base_spcc_vue()
                    self.lbl_cat_etat.config(text=msg[1], foreground="#1d7f1d")
                    continue
                _, chemin, telecharge = msg[0], msg[1], msg[2]
                self.astro_info = ""        # les essais d'astrométrie repartent
                self._rafraichir_rendu = True
                self._maj_cat_vue()
                if quoi == "spectres":
                    self.lbl_cat_etat.config(text=msg[1], foreground="#1d7f1d")
                    continue
                self._maj_astro_vue()
                self.lbl_cat_etat.config(
                    text=(("catalogue astro téléchargé : " if telecharge
                           else "catalogue astro déjà présent : ")
                          + os.path.basename(chemin)),
                    foreground="#1d7f1d")
            else:
                self._cat_dl_actif = False
                self._regler_boutons_dl(False)
                if quoi == "spcc":
                    self._maj_base_spcc_vue()
                else:
                    self._maj_cat_vue()
                self.lbl_cat_etat.config(
                    text=(f"téléchargement : ÉCHEC — {msg[1]} "
                          "(le fichier .part reste : relancer reprend où on "
                          "s'est arrêté)"),
                    foreground="#d04040")
        # Détection SDK (thread → UI) : consommation du résultat — les
        # variables/labels Tk ne sont touchés QUE depuis ce thread principal.
        if self._detect_result is not None:
            source, ids, err = self._detect_result
            self._detect_result = None
            self._detect_busy = False
            if err is not None:
                self.lbl_detect.config(text=f"{source} : {err}",
                                       foreground="#B06000")
            elif not ids:
                self.lbl_detect.config(
                    text=f"{source} : aucune caméra détectée",
                    foreground="#B06000")
            else:
                self._sdk_ids = list(ids)
                if source == "QHY":
                    self._qhy_id = str(ids[0])
                    # Jalon 26 : la détection CONNECTE la caméra (thread
                    # dédié — le constructeur qhyccd.Camera ouvre le
                    # handle USB et peut prendre quelques secondes ; ne
                    # jamais bloquer le thread Tk).
                    if self.camera is None and not self._connexion_busy:
                        self._connexion_busy = True
                        self.lbl_detect.config(
                            text="QHY : connexion de la caméra…",
                            foreground="#c98a00")
                        threading.Thread(target=self._connecter_qhy,
                                         daemon=True).start()
                    else:
                        self.lbl_detect.config(
                            text=f"{source} : {' — '.join(map(str, ids))}",
                            foreground="#1d7f1d")
                else:
                    self.lbl_detect.config(
                        text=f"{source} : {' — '.join(map(str, ids))}",
                        foreground="#1d7f1d")
                    # Jalon 32 : comme QHY (jalon 26), la caméra détectée
                    # est CONNECTÉE AUTOMATIQUEMENT (thread dédié — open()
                    # peut prendre des secondes, jamais dans le thread Tk) ;
                    # le résultat est consommé plus bas (détection des
                    # capacités puis UI aux bornes réelles). Une seule
                    # connexion à la fois (_connexion_busy partagé avec QHY),
                    # « ▶ Démarrer » neutralisé pendant ce temps.
                    if self.camera is None and not self._connexion_busy:
                        self._connexion_busy = True
                        self.btn_start.config(state="disabled")
                        self.lbl_detect.config(
                            text=f"{source} : connexion de la caméra…",
                            foreground="#c98a00")
                        threading.Thread(target=self._connecter_sdk,
                                         args=(source,),
                                         daemon=True).start()
        # Jalon 26 : consommation du résultat de CONNEXION QHY (thread →
        # thread Tk). Succès : réglages posés, contrôles bientôt sondés
        # (worker), « ▶ Démarrer » et « ⏏ Déconnecter » actifs.
        if self._connexion_result is not None:
            cam, err = self._connexion_result
            self._connexion_result = None
            self._connexion_busy = False
            if err is not None:
                self.lbl_detect.config(
                    text=f"QHY : connexion impossible — {err}",
                    foreground="#d04040")
            else:
                # Jalon 32 : facteur commun (caméra posée + capacités + UI
                # aux bornes réelles + worker) partagé avec les AUTRES
                # marques SDK — une seule définition, zéro duplication.
                self._installer_camera_connectee(cam, "QHY")
        # Jalon 32 : consommation du résultat de CONNEXION des AUTRES marques
        # SDK (thread → thread Tk) : mêmes conséquences que QHY — détection
        # des capacités, UI construite aux bornes réelles, worker lancé.
        if self._connexion_sdk_result is not None:
            source, cam, err = self._connexion_sdk_result
            self._connexion_sdk_result = None
            self._connexion_busy = False
            if err is not None or cam is None:
                self.btn_start.config(state="normal")
                self.lbl_detect.config(
                    text=f"{source} : connexion impossible — "
                         f"{err or 'caméra introuvable'}",
                    foreground="#d04040")
            elif not self.var_source.get().startswith(source):
                # La source a changé pendant l'ouverture (l'utilisateur a
                # repris la main) : on n'installe PAS une caméra qui ne
                # correspond plus au choix — on la referme proprement.
                try:
                    cam.close()
                except Exception:
                    pass
                self.btn_start.config(state="normal")
                self.lbl_detect.config(
                    text=f"{source} : connexion annulée (source changée)",
                    foreground="#888888")
            else:
                self._installer_camera_connectee(cam, source)
        # (Le bloc « confirmation de DÉCONNEXION » du jalon 26b est supprimé
        # avec le mécanisme threadé — la version simple du 19/09 met à jour
        # l'état des boutons elle-même.)
        # Jalon 19 : réglages de composition (gains R/G/B, radio « Canal L »)
        # lus CÔTÉ THREAD PRINCIPAL (variables Tk interdites dans le worker,
        # cf. piège) et poussés vers la façade si modifiés → appliqués au
        # composite dès la prochaine frame, sans redémarrer la session.
        gains = self._lire_gains()
        mode_l = self.var_compo_mode_l.get()
        if gains != self._compo_gains or mode_l != self._compo_mode_l:
            self._compo_gains = gains
            self._compo_mode_l = mode_l
            # Jalon 55 : le rendu suit SANS attendre la prochaine brute
            # (le worker resynchronise et recalcule), et la résolution
            # VeraLux est forcée — les gains ne font pas partie de sa clé,
            # elle ne se rendrait jamais compte seule.
            self._rafraichir_rendu = True
            if getattr(self, "disp", None) is not None:
                self.disp.notify_new_stack()
        # Jalon 54 : instantané du recalage Linear Fit pour le worker
        # (jamais de lecture de variable Tk hors du thread principal) +
        # libellé des gains/offsets MESURÉS (écrits par le worker au dernier
        # mean() — lecture d'attributs simples, jamais de variables Tk).
        self._fit_actif = bool(self.var_fit.get())
        self._fit_mode = self._code_fit_methode()   # jalon 54b (méthode)
        self._maj_libelle_fit()
        # Jalon 25/26 : lecture de la température/PWM du TEC (attributs
        # simples écrits par le thread de travail — jamais de variable Tk
        # dans le worker) + activer les lignes Filtre/TEC quand le sondage
        # a répondu — DÈS LA CONNEXION (pas besoin d'une session).
        if self.camera is not None:
            dernier = self._tec_dernier
            if dernier is not None:
                self._tec_dernier = None
                t, pwm, cons = dernier
                # Jalon 51 : toutes les marques n'exposent pas les MÊMES
                # données — Touptek donne la température et la consigne mais
                # AUCUNE puissance de refroidissement (pas d'option dans son
                # SDK) → None s'affiche « — », jamais un « 0 % » qui
                # laisserait croire que le TEC ne travaille pas.
                txt = (f"Capteur : {t:.1f} °C" if t is not None
                       else "Capteur : —")
                if pwm is None:
                    txt += " · TEC : —"
                else:
                    pct = max(0, min(255, int(round(pwm)))) * 100 // 255
                    txt += f" · TEC : {pct} % ({int(pwm)}/255)"
                if cons:
                    txt += f" · consigne {cons:.0f} °C"
                self.lbl_tec.config(text=txt, foreground="#1d7f1d")
            if self._tec_ok:
                self._tec_ok = False
                self.btn_tec_on.config(state="normal")
                self.btn_tec_off.config(state="normal")
                try:
                    self._tec_defaut = float(
                        self.var_tec_consigne.get().replace(",", "."))
                except ValueError:
                    return self.root.after(30, self._tick)
                self._tec_demande = ("consigne", self._tec_defaut)
            if self._roue_ok:
                self._roue_ok = False
                self.cb_filtre.config(state="readonly")
                self.lbl_filtre.config(text="roue détectée", foreground="#1d7f1d")
            if self._filtre_info is not None:
                txt, coul = self._filtre_info
                self._filtre_info = None
                self.lbl_filtre.config(text=txt, foreground=coul)
            if self._tec_info is not None:
                txt, coul = self._tec_info
                self._tec_info = None
                self.lbl_tec.config(text=txt, foreground=coul)
        try:
            while True:
                # Jalon 75 : le tuple ne porte plus d'histogramme — il est
                # calculé dans le thread d'affichage, sur ce qui est
                # RÉELLEMENT affiché (vue « empilement » comme vue « traitée »).
                show, st = self.q.get_nowait()
                self.show_stack = show
                if st["frames"] != self._vl_frames:
                    # Jalon 3 : un NOUVEL empilement vient d'être produit —
                    # le solveur VeraLux relance la résolution (le rythme des
                    # frames est le cooldown ; aucun calcul entre deux frames,
                    # et le solveur ne garde que le DERNIER empilement).
                    self._vl_frames = st["frames"]
                    self.disp.notify_new_stack()
                self._update_status(st)
                if self.var_view.get() == "pile":     # la vue traitée garde son instantané
                    self.last_show = show
                    self._rendre_et_afficher(show)
        except queue.Empty:
            pass
        # Jalon 75 : une remise à zéro de l'affichage (nouvelle session) a pu
        # avoir lieu dans le worker — les barres doivent revenir à l'auto À
        # L'ÉCRAN aussi (sinon l'utilisateur croirait son réglage conservé).
        if getattr(self.disp, "niveaux_new", False):
            self.disp.niveaux_new = False
            self._maj_niveaux_vue()
            # …ET le tracé : une réinitialisation peut tomber sans aucune frame
            # en cours, auquel cas le panneau resterait sur les barres de la
            # session précédente (même défaut que le glissement, cf.
            # `_hist_drag_move`).
            self._draw_hist()
            if not self.disp.fige:
                self.btn_figer.config(text="⏹ Figer l'auto")
        if self.disp.vl_graxpert:      # jalon 4 : la commande GraXpert peut
                                       # être éditée pendant la session →
                                       # synchro permanente (thread UI seul)
            cmd = self.var_cmd_graxpert.get().strip()
            if cmd != self.disp.vl_graxpert_cmd:
                self.disp.vl_graxpert_cmd = cmd
        # Jalon 5/9/12 : GraXpert, débruitage ET netteté live = vue
        # « empilement » uniquement (synchro permanente : les cases peuvent
        # être cochées même en vue « traitée »)
        self._sync_vl_graxpert_vue()
        self._sync_vl_denoise_vue()
        self._sync_vl_couleur_vue()
        self._sync_vl_sharp_vue()
        self._maj_lbl_cadence()   # jalon 44 : état de la cadence en direct
        # v2.38.6 : espace du dossier de travail, rafraîchi toutes les 10 s —
        # la saturation devient VISIBLE pendant la session au lieu d'être
        # découverte par un échec en pleine chaîne.
        # v2.38.11 : la sonde part dans le fil de mesures BORNÉ (jamais dans le
        # fil d'interface : un dossier de travail sur un NAS injoignable figerait
        # la fenêtre à chaque rafraîchissement).
        if time.time() - getattr(self, "_travail_t0", 0.0) > 10.0:
            self._travail_t0 = time.time()
            self._demander_mesures()
        if self.disp.sh_new:      # netteté live : message du solveur (jalon 12)
            self.disp.sh_new = False
            self._maj_lbl_sharp()
        self._maj_lbl_vl()        # état du solveur VeraLux (jalon 40) :
                                  # ⏳ étape courante + curseur, puis résultat
        if self.proc_new:
            self.proc_new = False
            self.btn_save_proc.config(state="normal")
            if self.var_view.get() == "traitée" and self.proc_show is not None:
                self.last_show = self.proc_show
                self._show_image(self.disp.process(
                    self._src_rendu(self.proc_show), live=False))
        if self.ext_msg != self._ext_shown:
            self._ext_shown = self.ext_msg
            self.lbl_ext.config(
                text=self.ext_msg,
                foreground={"busy": "#c98a00", "ok": "#1d7f1d",
                            "error": "#d04040"}.get(self.ext_state, "#888888"))
        if self.ext_busy:                      # chrono pendant le traitement
            self.lbl_ext.config(text=f"{self.ext_msg}  "
                                      f"({time.time() - (self.ext_t0 or time.time()):.0f} s)")
        self.btn_ext.config(state="disabled"
                            if (self.ext_busy or self.ext_request) else "normal")
        if self._ext_popup:
            self._ext_popup = False
            messagebox.showerror("Traitement externe", self.ext_msg)
        if self.saved_path:
            p, self.saved_path = self.saved_path, None
            if p.startswith("ERREUR"):
                messagebox.showerror("Enregistrer", p)
            elif os.path.isdir(p):
                messagebox.showinfo("Enregistrer",
                                    f"Canaux sauvegardés dans :\n{p}")
            else:
                corr = self.dernier_applicatif
                self.dernier_applicatif = None
                messagebox.showinfo(
                    "Enregistrer", f"Empilement sauvegardé :\n{p}"
                    + (f"\n\nCorrections écrites dans le fichier (AVAAPPLI) :"
                       f"\n{corr}" if corr else ""))
        # Jalon 5 : état de la sauvegarde « tel que vu » (thread dédié)
        self.btn_save_asseen.config(
            state="disabled"
            if (self.asseen_busy or self.save_asseen_request is not None)
            else "normal")
        if self.asseen_result:
            p, self.asseen_result = self.asseen_result, None
            titre = self.asseen_titre or "Enregistrer tel que vu"
            self.asseen_titre = None
            outils = self.msg_outils        # erreurs d'outil (couche par couche)
            self.msg_outils = None
            corr = self.dernier_applicatif
            self.dernier_applicatif = None
            if p.startswith("ERREUR"):
                messagebox.showerror(titre, p)
            else:
                messagebox.showinfo(
                    titre, f"Image sauvegardée :\n{p}"
                    + (f"\n\nCorrections écrites dans le fichier (AVAAPPLI) :"
                       f"\n{corr}" if corr else "")
                    + (f"\n\nOutils : {outils}" if outils else ""))
        self.root.after(30, self._tick)

    def _src_pleine_res(self):
        """Image LINÉAIRE pleine résolution de la VUE COURANTE (v2.38.1), ou
        None si elle n'existe pas encore.

        Vue « empilement » → `self._stack_pleine_res`, la copie de l'empilement
        COMPLET posée par la boucle d'acquisition (seul endroit du code qui a
        l'image entière sous la main).
        Vue « traitée » → `self.proc_full`, le résultat du ⚡ traitement externe :
        il est DÉJÀ mémorisé (sauvegardes « résultat traité (linéaire) » et
        « tel que vu » en vue traitée, cf. `_save_proc` / `_save_asseen`), donc
        l'écran peut s'en servir SANS copie supplémentaire — et il montre alors
        le même instantané que celui que le fichier contiendra.

        ⚠️ THREADS : `self.var_view` (variable Tk) ne se lit QUE depuis le thread
        d'interface ; cette méthode n'est appelée que par `_src_rendu`, lui-même
        réservé à l'UI (`_tick`, `_on_view`, `_refresh_preview`) — jamais par la
        boucle d'acquisition ni par un thread de travail."""
        if self.var_view.get() == "traitée":
            return self.proc_full
        return self._stack_pleine_res

    def _src_rendu(self, lineaire):
        """Image LINÉAIRE donnée à la chaîne d'affichage (v2.38.0 ; pleine
        résolution en vue « traitée » depuis la v2.38.1).

        Par défaut : `lineaire`, l'aperçu 1600 px — rapide (~1,7 s), mais la
        chaîne non linéaire (GraXpert, débruitage, netteté, couleurs, chroma,
        étirement) n'est alors PAS appliquée à la même échelle que pour le
        fichier : mesuré au jalon 66, écart moyen 0,015-0,023 et jusqu'à 0,49 aux
        cœurs d'étoiles — l'anneau de couleur des étoiles, lui, n'existe QUE dans
        les fichiers (l'aperçu l'écrase).

        Option « Rendu pleine résolution » COCHÉE (et image complète disponible
        pour la vue courante) : la MÊME chaîne est appliquée à l'image COMPLÈTE →
        l'écran montre exactement ce que le fichier contiendra, et le zoom
        recadre de VRAIS pixels. Coût mesuré : 7,2-8,3 s par recalcul complet
        (×4,3).

        v2.38.1 — la source suit la VUE (`_src_pleine_res`) : en vue « traitée »
        c'est le RÉSULTAT EXTERNE pleine résolution qui est rendu. Avant, la
        méthode rendait l'empilement complet quel que soit l'état de la vue : en
        vue « traitée », l'écran montrait donc l'EMPILEMENT au lieu du résultat
        du ⚡ (et le zoom « fidèle » ne portait pas sur l'image annoncée).

        Repli sur l'aperçu quand l'image complète de la vue n'existe pas encore :
        avant le premier empilement d'une session, ou en vue « traitée » avant le
        premier ⚡ traitement."""
        if self._pleine_res_activee():
            src = self._src_pleine_res()
            if src is not None:
                return src
        return lineaire

    def _show_image(self, disp):
        """Mémorise la dernière image étirée puis la dessine (zoom/pan conservés)."""
        self._last_disp = disp
        self._render()

    # ------------------------------------------------------------ zoom / pan
    def _on_wheel_zoom(self, e):
        d = getattr(e, "delta", 0)
        if d:
            factor = 1.25 if d > 0 else 0.8
        else:
            factor = 1.25 if getattr(e, "num", 0) == 4 else 0.8
        self._zoom_at(e.x, e.y, factor)
        return "break"                 # ne pas faire défiler le panneau gauche

    def _zoom_at(self, mx, my, factor):
        """Zoom centré sur le curseur : le point de l'image sous la souris
        reste sous la souris après le zoom."""
        if self._last_disp is None:
            return
        ih, iw = self._last_disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        fit = min(cw / iw, ch / ih)                    # échelle « ajuster »
        scale = fit * self.zoom
        vx = self.view_cx if self.view_cx is not None else iw / 2.0
        vy = self.view_cy if self.view_cy is not None else ih / 2.0
        ix = vx + (mx - cw / 2.0) / scale              # point sous le curseur
        iy = vy + (my - ch / 2.0) / scale
        new_zoom = min(32.0, max(1.0, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-9:
            return
        self.view_cx = min(max(ix - (ix - vx) * (self.zoom / new_zoom), 0.0), float(iw))
        self.view_cy = min(max(iy - (iy - vy) * (self.zoom / new_zoom), 0.0), float(ih))
        self.zoom = new_zoom
        self._render()

    def _on_img_press(self, e):
        self._drag = (e.x, e.y)

    def _on_img_drag(self, e):
        if self._drag is None or self._last_disp is None or self.zoom <= 1.0001:
            return
        px, py = self._drag
        self._drag = (e.x, e.y)
        ih, iw = self._last_disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        scale = min(cw / iw, ch / ih) * self.zoom
        if self.view_cx is None:
            self.view_cx = iw / 2.0
        if self.view_cy is None:
            self.view_cy = ih / 2.0
        self.view_cx = min(max(self.view_cx - (e.x - px) / scale, 0.0), float(iw))
        self.view_cy = min(max(self.view_cy - (e.y - py) / scale, 0.0), float(ih))
        self._render()

    def _on_img_release(self, e):
        self._drag = None

    def _on_img_dblclick(self, e):
        self.zoom, self.view_cx, self.view_cy = 1.0, None, None
        self._render()

    def _render(self):
        """Dessine self._last_disp en tenant compte du zoom et du pan."""
        disp = self._last_disp
        if disp is None:
            return
        ih, iw = disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        fit = min(cw / iw, ch / ih)                    # échelle « ajuster »
        scale = fit * self.zoom
        if self.zoom <= 1.0001:                        # vue ajustée, pas de recadrage
            crop, interp = disp, (cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        else:
            vx = self.view_cx if self.view_cx is not None else iw / 2.0
            vy = self.view_cy if self.view_cy is not None else ih / 2.0
            x0, x1 = vx - cw / (2 * scale), vx + cw / (2 * scale)
            y0, y1 = vy - ch / (2 * scale), vy + ch / (2 * scale)
            # recadrage borné aux limites de l'image
            if x1 - x0 >= iw:
                x0, x1 = 0.0, float(iw)
            elif x0 < 0:
                x1 -= x0; x0 = 0.0
            elif x1 > iw:
                x0 -= x1 - iw; x1 = float(iw)
            if y1 - y0 >= ih:
                y0, y1 = 0.0, float(ih)
            elif y0 < 0:
                y1 -= y0; y0 = 0.0
            elif y1 > ih:
                y0 -= y1 - ih; y1 = float(ih)
            xi0, yi0 = int(np.floor(x0)), int(np.floor(y0))
            xi1, yi1 = min(iw, int(np.ceil(x1))), min(ih, int(np.ceil(y1)))
            if xi1 - xi0 < 1 or yi1 - yi0 < 1:
                return
            crop = disp[yi0:yi1, xi0:xi1]
            nw = max(1, int(round((xi1 - xi0) * scale)))
            nh = max(1, int(round((yi1 - yi0) * scale)))
            interp = cv2.INTER_NEAREST if self.zoom >= 2.0 else cv2.INTER_LINEAR
        img = cv2.resize(crop, (nw, nh), interpolation=interp)
        self._photo = ImageTk.PhotoImage(Image.fromarray(img))
        self.cv_img.delete("all")
        self.cv_img.create_image(cw // 2, ch // 2, image=self._photo)
        if self.zoom > 1.01:
            # v2.38.0 : l'échelle RÉELLE (px image par px écran) est affichée —
            # 1,00 signifie que l'écran montre les pixels du fichier sans
            # interpolation ; avec le rendu pleine résolution, ces pixels sont
            # ceux que le fichier contiendra.
            info = f"{scale:.2f} px image / px écran" \
                + (", 1:1" if abs(scale - 1.0) < 0.02 else "")
            if self._pleine_res_activee():
                info += " · PLEINE RÉSOLUTION"
            self.cv_img.create_text(8, 8, anchor="nw", fill="#ffd75e",
                                    text=f"zoom ×{self.zoom:.1f}   ({info})   "
                                         f"double-clic : ajuster")

    def _hist_taille(self):
        """(largeur, hauteur) à utiliser pour le tracé et les gestes : les
        dimensions RÉELLES du Canvas, avec repli sur les dimensions demandées
        tant que la fenêtre n'est pas encore dessinée — `winfo_width()` rend 1
        pour un widget non affiché, et un histogramme tracé sur 1 px ne serait
        pas « approximatif » mais INVISIBLE (constat du banc : les gestes et le
        tracé étaient tous décalés au démarrage)."""
        w = self.cv_hist.winfo_width()
        h = self.cv_hist.winfo_height()
        return (w if w >= 40 else self.W_HIST,
                h if h >= 40 else self._hauteur_hist())

    # ============================= jalon 75 : histogramme 2 bandes + niveaux
    def _hauteur_hist(self):
        """Hauteur du Canvas d'histogramme : deux bandes, ou une seule (plus
        haute) — l'image regagne alors 58 px, utile sur une fenêtre réduite."""
        return 176 if self.hist_mode == "les_deux" else 118

    def _poser_panneau_hist(self, parent):
        """Panneau du jalon 75 sous l'histogramme : choix des bandes, les trois
        niveaux en CHAMPS DE SAISIE (motif du jalon 27 : on doit pouvoir viser
        une valeur précise), ⏹ Figer / ▶ Reprendre et « ↺ Auto », plus la ligne
        d'état qui dit TOUJOURS dans quel mode on est — un étirement figé sans
        avertissement serait une chute silencieuse, et c'est le seul vrai
        danger de cette fonction.

        La barre MÉDIAN est CONSERVÉE en même temps que le curseur « Gamma »
        (décision d'Alain, 28/09/2026 : les deux restent) — cf. le commentaire
        du curseur Gamma : deux courbes différentes, aucun doublon à retirer."""
        row = ttk.Frame(parent)
        row.pack(fill="x")
        ttk.Label(row, text="Histogramme :").pack(side="left")
        self.var_hist_mode = tk.StringVar(
            value=self.HIST_LABELS.get(self.hist_mode, "Les deux"))
        self.cb_hist_mode = ttk.Combobox(
            row, textvariable=self.var_hist_mode, state="readonly", width=16,
            values=[lib for lib, _ in self.HIST_MODES])
        self.cb_hist_mode.pack(side="left", padx=(2, 8))
        self.cb_hist_mode.bind("<<ComboboxSelected>>",
                               lambda e: self._on_hist_mode())
        self.btn_figer = ttk.Button(row, text="⏹ Figer l'auto",
                                    command=self._on_figer)
        self.btn_figer.pack(side="left", padx=2)
        ttk.Button(row, text="↺ Auto", command=self._on_niveaux_auto).pack(
            side="left", padx=2)
        self.lbl_hist_etat = ttk.Label(row, text="", foreground="#888888",
                                       wraplength=250)
        self.lbl_hist_etat.pack(side="left", padx=6)

        row2 = ttk.Frame(parent)
        row2.pack(fill="x")
        self.var_bar_noir = tk.DoubleVar(value=0.0)
        self.var_bar_median = tk.DoubleVar(value=0.5)
        self.var_bar_blanc = tk.DoubleVar(value=1.0)
        self.ent_bar = {}
        for cle, lib, var in (("noir", "Noir %", self.var_bar_noir),
                              ("median", "Médian %", self.var_bar_median),
                              ("blanc", "Blanc %", self.var_bar_blanc)):
            ttk.Label(row2, text=lib).pack(side="left", padx=(6, 2))
            ent = ttk.Entry(row2, textvariable=var, width=7, justify="right")
            ent.pack(side="left")
            ent.bind("<Return>", lambda e: self._on_niveaux_saisie())
            ent.bind("<FocusOut>", lambda e: self._on_niveaux_saisie())
            self.ent_bar[cle] = ent
        # Échelle VERTICALE de la bande basse (décision d'Alain, 28/09/2026 :
        # « linéaire » sur la SEULE bande basse — celle où l'on pose les
        # barres —, la bande haute gardant son log). Posée ICI et pas dans la
        # ligne du dessus : cette ligne-ci restait plus étroite que la
        # précédente, donc la géométrie de la fenêtre ne bouge pas (leçon du
        # jalon 72 : `pack` abandonne SILENCIEUSEMENT un widget qui ne tient
        # plus).
        self.var_hist_lineaire = tk.BooleanVar(value=bool(self.hist_lineaire))
        self.chk_hist_lineaire = ttk.Checkbutton(
            row2, text="Échelle y linéaire (bande basse)",
            variable=self.var_hist_lineaire, command=self._on_hist_lineaire)
        self.chk_hist_lineaire.pack(side="left", padx=(12, 4))
        ttk.Label(row2, text="(barres = bande basse « sortie du moteur » · "
                             "double-clic = défaut)",
                  foreground="#888888").pack(side="left", padx=8)
        self._maj_niveaux_vue()

    def _maj_niveaux_vue(self):
        """Resynchronise les champs de saisie et la ligne d'état sur l'état
        RÉEL de l'affichage (barres et gel) — appelée après tout changement venu
        de l'affichage lui-même (glissement d'une barre, ↺, nouvelle session) :
        une seule source de vérité, jamais deux affichages qui divergent."""
        d = self.disp
        for var, val in ((self.var_bar_noir, d.bar_noir),
                         (self.var_bar_median, d.bar_median),
                         (self.var_bar_blanc, d.bar_blanc)):
            if abs(float(var.get()) - float(val) * 100.0) > 0.05:
                var.set(round(float(val) * 100.0, 1))
        texte, coul = self._texte_etat_niveaux()
        self.lbl_hist_etat.config(text=texte, foreground=coul)

    def _texte_etat_niveaux(self):
        """Phrase d'état des niveaux + couleur : dit ce qui AGIT — l'auto du
        moteur (les barres sont un décalage PAR-DESSUS) ou l'utilisateur seul
        (étirement figé) — ET la cible de fond du moteur, parce que c'est elle
        qui décide où tombe la « colline » de la bande basse (demande d'Alain,
        28/09/2026 : « c'est quoi les 25 % ? » — c'est le défaut du STF ; en
        VeraLux c'est SON curseur, 0,16 sur son M31)."""
        d = self.disp
        av = self.var_moteur.get() if hasattr(self, "var_moteur") else "STF"
        if av == "VeraLux":
            cible = "fond visé %.0f %%" % (100 * float(d.vl_target_bg))
            # Tant que le solveur n'a pas rendu son résultat, l'écran (et donc
            # la bande basse, et donc la marque « fond ») montre l'image
            # d'ATTENTE du STF : la ligne doit le dire, sinon elle annonce un
            # fond visé que la marque ne peut pas encore refléter.
            if d.vl_en_cours():
                cible += ", calcul en cours"
        else:
            cible = "cible du fond %.0f %%" % (100 * float(d.target))
        if d.fige:
            texte, coul = ("auto FIGÉ (%s, %s) — tes barres seules agissent"
                           % (av, cible), "#c98a00")
        else:
            texte, coul = ("Niveaux : décalage sur l'auto (%s, %s, le moteur "
                           "continue)" % (av, cible), "#888888")
        # Échelle de la bande basse : DITE ici, parce qu'une échelle muette est
        # un piège (la même courbe ne raconte pas la même chose en log et en
        # linéaire — mesuré : le fond fait 66 % de l'axe en log, 10,5 % en
        # linéaire). Elle ne concerne QUE cette bande.
        if getattr(self, "hist_lineaire", False):
            texte += " · échelle y LINÉAIRE (bande basse)"
        return texte, coul


    def _niveaux_pose(self):
        """Reporte les 3 valeurs dans l'intervalle licite et dans l'ordre
        attendu (noir < médian < blanc, écart mini) : des barres croisées
        donnent un rendu absurde, on ne le laisse pas faire."""
        d = self.disp
        noir = min(max(float(d.bar_noir), 0.0), 0.98)
        blanc = min(max(float(d.bar_blanc), noir + 0.02), 1.0)
        median = min(max(float(d.bar_median), noir + 0.01), blanc - 0.01)
        d.bar_noir, d.bar_median, d.bar_blanc = noir, median, blanc

    def _on_hist_lineaire(self):
        """Case « Échelle y linéaire (bande basse) » — décision d'Alain du
        28/09/2026, prise sur MESURE (ses frames, 20 moyennées, STF auto) :
        la largeur à mi-hauteur du fond passe de **170 bacs (66 % de l'axe)**
        à **27 bacs (10,5 %)** — la « colline » devient un vrai PIC — au prix
        de la queue, qui tombe de 34 px à 0,65 px (p99 des pixels) : les
        étoiles et la nébuleuse quittent alors la courbe. La bande HAUTE n'est
        PAS concernée : en linéaire elle ne montrait plus que 10 bacs sur 256.

        Ni rendu d'image (l'échelle ne touche QUE le tracé) ni recalcul
        d'histogramme (les bacs sont déjà en mémoire) : tracé immédiat, règle
        du défaut ③ du 28/09/2026."""
        self.hist_lineaire = bool(self.var_hist_lineaire.get())
        self._maj_niveaux_vue()   # l'échelle est DITE dans la ligne d'état
        self._draw_hist()

    def _on_hist_mode(self):
        """Choix des bandes affichées (les deux / brut / sortie)."""
        lib = self.var_hist_mode.get()
        for etiquette, code in self.HIST_MODES:
            if etiquette == lib:
                self.hist_mode = code
                break
        self.cv_hist.config(height=self._hauteur_hist())
        self._draw_hist()

    def _on_niveaux_saisie(self, *_a):
        """Saisie chiffrée d'un niveau, en % de l'axe de sortie : borne,
        ordonne, applique et redessine immédiatement."""
        d = self.disp
        for cle, attr in (("noir", "bar_noir"), ("median", "bar_median"),
                          ("blanc", "bar_blanc")):
            try:
                v = float(self.ent_bar[cle].get().replace(",", ".")) / 100.0
            except (ValueError, tk.TclError):
                v = getattr(d, attr)
            setattr(d, attr, v)
        self._niveaux_pose()
        self._maj_niveaux_vue()
        # Règle des barres (défaut du 28/09/2026) : le tracé suit IMMÉDIATEMENT,
        # et sans recalcul — une barre ne change pas la courbe (elle est tracée
        # sur la sortie du moteur, AVANT l'étage de niveaux).
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _on_niveaux_auto(self):
        """« ↺ Auto » : les trois barres reviennent à l'identité
        (0 / 50 / 100 %), c'est-à-dire au rendu du moteur — sans rien figer ni
        défiger (le gel est un autre bouton)."""
        d = self.disp
        d.bar_noir, d.bar_median, d.bar_blanc = 0.0, 0.5, 1.0
        self._maj_niveaux_vue()
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _on_figer(self):
        """⏹ Figer / ▶ Reprendre l'étirement AUTOMATIQUE du moteur (jalon 75).

        STF : les stats lissées sont gelées (elles ne se recalculent plus ET
        n'avancent plus) → l'image ne bouge plus toute seule et les barres
        deviennent le seul levier.
        VeraLux : le moteur n'a pas de stats mais un logD RÉSOLU — le gel le
        VERROUILLE (mode « logD forcé », mécanisme du jalon 3), et Reprendre
        rend la main au fond cible. C'est ce qui rend la fonction disponible
        DANS LES DEUX MOTEURS (demande d'Alain, 28/09/2026)."""
        d = self.disp
        gel = not d.fige
        d.fige = gel
        veralux = self.var_moteur.get() == "VeraLux"
        if veralux and gel:
            self._vl_mode_avant_fige = self.var_vl_mode_res.get()
            resolu = d.vl_log_d_resolu
            if resolu is not None:
                self.var_vl_logd.set(round(float(resolu), 4))
            self.var_vl_mode_res.set("logD forcé")
            self._sync_vl_mode()
        elif veralux and not gel:
            self.var_vl_mode_res.set(self._vl_mode_avant_fige
                                     or "fond cible (auto)")
            self._sync_vl_mode()
        elif not gel:
            d.reprendre_auto()          # STF : stats oubliées → recalage net
        self.btn_figer.config(text=("▶ Reprendre l'auto" if gel
                                    else "⏹ Figer l'auto"))
        self._maj_niveaux_vue()
        self._refresh_preview()

    def _on_sat_canaux(self):
        """Saturation par couleur (R/V/B) : les trois gains sont posés
        ENSEMBLE, en un tuple (jamais muté en place — le solveur live lit une
        référence cohérente), puis l'aperçu est re-rendu.

        Jalon 79 : `hist=False` (même règle que gamma, saturation globale et
        barres de niveaux) — la saturation par couleur s'applique APRÈS la
        sortie du moteur d'étirement, donc AUCUNE des deux bandes de
        l'histogramme ne change : la recalculer coûtait les deux histogrammes
        (34 ms sur l'aperçu couleur) pour un tracé identique."""
        self.disp.sat_canaux = (float(self.var_sat_r.get()),
                                float(self.var_sat_g.get()),
                                float(self.var_sat_b.get()))
        self._refresh_preview(hist=False)


    # --- calcul des histogrammes ---------------------------------------------
    @staticmethod
    def _hist_canaux(img, plage=None, bins=256, points=None):
        """Histogrammes PAR CANAL d'une image, ÉCHANTILLONNÉE pour que le coût
        ne dépende pas de la résolution (jalon 75 : le calcul quitte le thread
        d'acquisition — où il coûtait ~55 ms par frame sur 1600 px, et jusqu'à
        ~60 ms en pleine résolution — pour le thread d'affichage).

        plage : (lo, hi) imposé — bande « sortie du moteur », 0..1 ; None =
        axe AUTOMATIQUE sur p99,9 × 1,15, comme depuis toujours (bande « brut »,
        c'est le seul choix qui rende un empilement linéaire lisible : mesuré
        sur NGC 7331, le fond tombe à 52 % de cet axe, les p99/p99,9 à 57/87 %).
        Retourne (liste des 256 comptes, valeur haute de l'axe).
        """
        img = np.asarray(img, np.float32)
        pas = max(1, int(round(math.sqrt(
            img.shape[0] * img.shape[1] / float(points or App.HIST_POINTS)))))
        ech = img[::pas, ::pas]
        chans = [ech] if ech.ndim == 2 else [ech[..., i] for i in range(3)]
        if plage is None:
            lo, hi = 0.0, float(np.percentile(ech, 99.9)) * 1.15 + 1e-6
        else:
            lo, hi = float(plage[0]), float(plage[1])
        return ([np.histogram(c, bins=bins, range=(lo, hi))[0].astype(np.float64)
                 for c in chans], hi)

    def _maj_histogrammes(self, src_lin, brut=None):
        """Recalcule les DEUX bandes et redessine : « Brut (linéaire) » (la
        source donnée à la chaîne d'affichage) et « Sortie du moteur » (l'image
        AVANT les barres — c'est elle que les barres découpent).

        Un échec ici ne doit JAMAIS emporter la boucle d'interface (un
        historique de panne muette dans ce projet) : il est journalisé et se
        voit à l'écran.
        """
        try:
            self._hist_brut = (None if src_lin is None
                               else self._hist_canaux(src_lin))
            self._hist_sortie = (None if brut is None
                                 else self._hist_canaux(brut, plage=(0.0, 1.0)))
            self._hist_erreur = ""
        except Exception as exc:                    # noqa: BLE001 (journalisé)
            self._hist_brut = self._hist_sortie = None
            self._hist_erreur = str(exc)
            journal.erreur("histogramme", exc)
        self._draw_hist()

    # --- barres : glisser / double-clic --------------------------------------
    def _hist_zone_sortie(self):
        """(y0, y1) de la bande « Sortie du moteur », ou None si elle n'est
        pas affichée (le mode « brut » ne porte pas les barres)."""
        h = self._hist_taille()[1]
        if self.hist_mode == "brut":
            return None
        if self.hist_mode == "sortie":
            return (4, h - 18)
        haut = (h - 30) // 2
        return (h - haut - 18, h - 18)

    def _hist_x(self, valeur, w=None):
        """Position en pixels d'une valeur [0..1] sur l'axe de sortie."""
        w = w or self._hist_taille()[0]
        m = self.HIST_MARGE
        return m + float(valeur) * (w - 2 * m)

    def _hist_valeur(self, x, w=None):
        """Valeur [0..1] sous une abscisse de l'axe de sortie."""
        w = w or self._hist_taille()[0]
        m = self.HIST_MARGE
        return min(max((x - m) / float(max(w - 2 * m, 1)), 0.0), 1.0)

    def _hist_hit(self, x, w=None):
        """Barre sous le curseur ('noir' / 'median' / 'blanc') ou None."""
        if self._hist_zone_sortie() is None:
            return None
        best, dmin = None, self.HIST_PRISE + 1
        for cle, val in (("noir", self.disp.bar_noir),
                         ("median", self.disp.bar_median),
                         ("blanc", self.disp.bar_blanc)):
            d = abs(self._hist_x(val, w) - x)
            if d < dmin:
                best, dmin = cle, d
        return best

    def _hist_press(self, e):
        self._hist_drag = self._hist_hit(e.x)
        if self._hist_drag:
            self.cv_hist.config(cursor="sb_h_double_arrow")

    def _hist_drag_move(self, e):
        """Glissement : la valeur suit le doigt, le TRACÉ aussi, puis le RENDU.

        `_draw_hist()` est appelé ICI, et il ne RECALCULE rien : il ne fait que
        retracer les canaux DÉJÀ en mémoire (`_hist_brut` / `_hist_sortie`) —
        c'est légitime, la donnée du moteur ne change pas quand une barre bouge,
        seule la découpe change (la bande basse est la sortie du moteur AVANT
        les barres). L'oublier était un DÉFAUT RÉEL (constat d'Alain après son
        essai du 28/09/2026) : « quand l'empilement est fini, si on touche aux
        barres, l'image change alors que la position de la barre ne change pas,
        ou pas complètement, comme si le bas n'était pas rafraîchi ». Exactement
        cela : sans frame qui arrive, plus rien n'appelait `_draw_hist()` (il ne
        vivait que dans `_maj_histogrammes`), donc le panneau restait figé sur
        la position de DÉPART ; et à 0,2 fps une frame venait le rattraper par
        sauts, d'où la barre « à moitié » déplacée. Le tracé est posé AVANT le
        rendu (il est ~20 fois moins cher, quelques ms contre ~80) pour que la
        poignée suive le doigt sans attendre la fin de l'image."""
        if not self._hist_drag:
            return
        v = self._hist_valeur(e.x)
        d = self.disp
        if self._hist_drag == "noir":
            d.bar_noir = min(v, d.bar_blanc - 0.02)
        elif self._hist_drag == "blanc":
            d.bar_blanc = max(v, d.bar_noir + 0.02)
        else:
            d.bar_median = v
        self._niveaux_pose()
        self._maj_niveaux_vue()
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _hist_release(self, _e=None):
        self._hist_drag = None
        self.cv_hist.config(cursor="")
        # Le DERNIER mouvement peut manquer (relâchement hors du Canvas, ou
        # évènement perdu) : on retrace une fois pour que le panneau montre la
        # valeur RÉELLEMENT appliquée et non l'avant-dernière (même défaut que
        # celui corrigé dans `_hist_drag_move`).
        self._draw_hist()

    def _hist_dblclick(self, e):
        """Double-clic sur une barre : elle revient à sa valeur d'origine
        (0 / 50 / 100 %), c'est-à-dire au rendu du moteur."""
        cle = self._hist_hit(e.x)
        if not cle:
            return
        setattr(self.disp, "bar_" + cle,
                {"noir": 0.0, "median": 0.5, "blanc": 1.0}[cle])
        self._niveaux_pose()
        self._maj_niveaux_vue()
        # Même règle que le glissement : le tracé suit tout de suite, et
        # `hist=False` parce qu'une barre ne change PAS la courbe (elle est
        # tracée sur la sortie du moteur, avant l'étage de niveaux).
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _hist_survol(self, e):
        """Curseur « ⇔ » au survol d'une barre : elle est attrapable."""
        if self._hist_drag:
            return
        self.cv_hist.config(cursor=("sb_h_double_arrow"
                                    if self._hist_hit(e.x) else ""))


    def _draw_hist(self):
        """Trace l'histogramme (jalon 75) : deux bandes possibles —
        « Brut (linéaire) » (diagnostic : fond, piqué, clipping, dominante) et
        « Sortie du moteur » (l'image étirée AVANT les barres, que les trois
        barres Noir/Médian/Blanc découpent)."""
        self.cv_hist.delete("all")
        w, h = self._hist_taille()
        if getattr(self, "_hist_erreur", ""):
            self.cv_hist.create_text(w / 2.0, h / 2.0, fill="#d04040",
                                     text="histogramme indisponible : %s"
                                          % self._hist_erreur)
            return
        if self.hist_mode == "les_deux":
            haut = max(40, (h - 26) // 2 - 6)
            self._bande_brut(w, 2, 2 + haut)
            # Séparateur fin entre les deux bandes : sans lui, la queue basse de
            # la bande « brut » et les étiquettes des barres se lisent comme un
            # seul fouillis (constat sur une capture réelle de NGC 7331).
            yb = h - haut - 14
            self.cv_hist.create_line(0, yb - 3, w, yb - 3, fill="#3a3a3a")
            self._bande_sortie(w, yb, h - 14)
        elif self.hist_mode == "brut":
            self._bande_brut(w, 2, h - 16)
        else:
            self._bande_sortie(w, 2, h - 16)

    @staticmethod
    def _courbes_pts(chans, w, y0, y1, lineaire=False):
        """Points des polylignes R/V/B d'une bande, ÉCHELLE LOGARITHMIQUE en y
        par défaut (les queues d'un empilement sont invisibles en linéaire) et
        NORMALISATION COMMUNE : le maximum est pris sur les TROIS canaux.

        Fonction PURE (le tracé s'en sert, et le banc vérifie ainsi la
        propriété qui compte) : avant le jalon 75 chaque courbe était ramenée à
        SON propre maximum, donc trois canaux très inégaux se dessinaient à la
        même hauteur — l'histogramme ne disait plus rien de l'équilibre des
        couleurs, ce qui est justement l'usage qu'en fait Alain.

        `lineaire=True` (jalon 75, case « Échelle y linéaire », bande BASSE
        seulement) : la hauteur d'un bac est PROPORTIONNELLE À SON NOMBRE DE
        PIXELS — le rapport des hauteurs de deux bacs est alors exactement le
        rapport de leurs comptes (mesuré au banc : ×100 pour des comptes
        1000 / 10, là où le log le compresse à ×2,9). C'est ce qui fait
        apparaître le fond comme un PIC au lieu d'une colline (mesuré sur les
        frames d'Alain : 170 bacs à mi-hauteur → 27), au prix de la queue.
        """
        if not chans:
            return []
        mx = max(float(c.max()) for c in chans) or 1.0
        lg = max(1.0, float(np.log1p(mx)))
        polylignes = []
        for arr in chans:
            n = len(arr)
            pts = []
            for i in range(n):
                if lineaire:
                    haut = float(arr[i]) / mx          # proportion DIRECTE
                else:
                    haut = float(np.log1p(arr[i])) / lg
                pts += [i / float(n - 1) * w,
                        y1 - haut * (y1 - y0) - 1]
            polylignes.append(pts)
        return polylignes

    @staticmethod
    def _rangs_etiquettes(xs, largs):
        """Rang d'affichage de chaque étiquette (0, 1, 2…) : le PREMIER rang où
        elle ne chevauche aucune étiquette déjà posée dans ce rang.

        Les étiquettes serrées (trois barres au même endroit, ou trois repères
        du moteur dans les 5 % de l'axe) montent alors d'un rang au lieu de se
        superposer — leçon des jalons 72/74 : un texte qui en cache un autre
        est un défaut, et il ne se réveille qu'avec des valeurs groupées.
        """
        rangs, places = [], []
        for x, larg in zip(xs, largs):
            boite = (x - larg / 2.0, x + larg / 2.0)
            choisi = None
            for i, occupe in enumerate(rangs):
                if all(boite[1] < a or b < boite[0] for a, b in occupe):
                    choisi = i
                    break
            if choisi is None:
                rangs.append([])
                choisi = len(rangs) - 1
            rangs[choisi].append(boite)
            places.append(choisi)
        return places

    def _courbes(self, w, y0, y1, chans, lineaire=False):
        """Trace les courbes R/V/B d'une bande (cf. `_courbes_pts`)."""
        if not chans:
            # Message d'attente EN BAS À GAUCHE : le haut de la bande porte les
            # barres et leurs étiquettes, le bas à droite la légende — à cet
            # endroit il ne peut chevaucher ni l'une ni l'autre.
            self.cv_hist.create_text(4, y1 - 1, anchor="sw", fill="#777777",
                                     text="en attente de données")
            return
        couleurs = (["#ff5555", "#55ff55", "#5599ff"] if len(chans) == 3
                    else ["#bbbbbb"])
        for pts, col in zip(self._courbes_pts(chans, w, y0, y1, lineaire),
                            couleurs):
            self.cv_hist.create_line(*pts, fill=col, width=1)

    def _bande_brut(self, w, y0, y1):
        """Bande HAUTE : les données LINÉAIRES — c'est l'axe du « GRAND »
        histogramme de SharpCap (valeurs brutes + repères du niveau de
        l'étirement). Les repères ne sont dessinés qu'en STF et en auto :
        VeraLux n'a NI point noir NI point blanc (ancre + logD), et en mode
        manuel il n'y a plus d'auto à montrer — on n'invente pas un repère."""
        chans, hi = (self._hist_brut or (None, 0.0))
        # TOUJOURS en log, ici : la case « Échelle y linéaire » ne concerne que
        # la bande basse. Mesuré sur les frames d'Alain : cette bande, en
        # linéaire, ne laissait plus que 10 bacs visibles sur 256 (une
        # aiguille) — elle perdait son rôle de diagnostic (piqué, clipping,
        # dominante), d'où la décision du 28/09/2026.
        self._courbes(w, y0, y1, chans)
        self.cv_hist.create_text(4, y0 + 1, anchor="nw", fill="#999999",
                                 text="Brut (linéaire) — axe 0 à %.5f" % hi)
        d = self.disp
        # Sans données, aucun repère : un repère de niveau posé sur une bande
        # vide n'apprend rien et irait se superposer au message d'attente.
        if not chans or self.var_moteur.get() != "STF" or not d.auto or hi <= 0:
            return
        if not (d.last_hi > d.last_lo > 0):
            return
        milieu = d.last_lo + float(getattr(d, "last_m", 0.5)) \
            * (d.last_hi - d.last_lo)
        repere = [(val, lib, col) for val, lib, col
                  in ((d.last_lo, "Noir", "#bbbbbb"),
                      (milieu, "Médian", "#ffd75e"),
                      (d.last_hi, "Blanc", "#ffffff"))
                  if 0.0 < val < hi]
        # Étiquettes courtes (« Noir 46,5 % » — l'axe est dans la légende) et
        # posées sur des rangs distincts : sur une vraie image les trois repères
        # vivent dans la moitié gauche de l'axe et se chevaucheraient.
        textes = ["%s %.1f %%" % (lib, 100.0 * val / hi)
                  for val, lib, _c in repere]
        xs = [val / hi * w for val, _lib, _c in repere]
        rangs = self._rangs_etiquettes(xs, [7.0 * len(t) + 4.0
                                            for t in textes])
        for (val, _lib, col), x, txt, rang in zip(repere, xs, textes, rangs):
            self.cv_hist.create_line(x, y0 + 11, x, y1, fill=col, dash=(3, 3))
            anc = "n" if 60 < x < w - 60 else ("nw" if x <= 60 else "ne")
            self.cv_hist.create_text(min(max(x, 3), w - 3),
                                     y1 - 13 - self.HIST_RANG_PX * rang,
                                     anchor=anc, fill=col, text=txt)

    def _bande_sortie(self, w, y0, y1):
        """Bande BASSE : l'image telle que LE MOTEUR l'étire, AVANT les barres.
        Les repères intrinsèques (0 / 50 / 100 % — les valeurs d'origine des
        barres) sont en pointillé ; la COURBE JAUNE est le transfert des niveaux
        (ce que chaque valeur de sortie devient après les barres), la même que
        chez SharpCap."""
        chans = (self._hist_sortie or (None,))[0]
        # Échelle y de CETTE bande : log par défaut, linéaire si la case est
        # cochée (décision du 28/09/2026) — les barres, les repères et la
        # courbe jaune, eux, sont en x et ne bougent donc pas d'un pixel.
        self._courbes(w, y0, y1, chans, lineaire=self.hist_lineaire)
        d = self.disp
        for v in (0.0, 0.5, 1.0):
            x = self._hist_x(v, w)
            self.cv_hist.create_line(x, y0 + 8, x, y1, fill="#4a4a4a",
                                     dash=(2, 3))
        pts = []
        for i in range(0, 101):
            v = i / 100.0
            y = float(display_mod.niveaux(np.float32(v), d.bar_noir,
                                          d.bar_median, d.bar_blanc))
            pts += [self._hist_x(v, w), y1 - y * (y1 - y0) - 1]
        self.cv_hist.create_line(*pts, fill="#8a7a20", width=1)
        # Repère du PIC DU FOND : c'est LA question que se pose l'œil devant
        # cette bande (« où est le pic ? »). Il est MESURÉ sur la somme des
        # trois canaux (la donnée affichée, pas une valeur supposée) — et il
        # n'a pas de poignée : il n'est pas déplaçable.
        pic = None
        if chans:
            cum = np.sum(chans, axis=0)
            if float(cum.max()) > 0.0:
                pic = (float(np.argmax(cum)) + 0.5) / float(len(cum))
        # Les trois barres : ligne + poignée (attrapable) + valeur, PLUS le
        # repère du pic. Les étiquettes sont posées sur le premier RANG libre
        # (largeur estimée à ~7 px par caractère) : quatre textes serrés
        # tiennent alors sur quatre rangs au lieu de se superposer — un texte
        # qui en chevauche un autre est un DÉFAUT (leçon des jalons 72/74).
        pos = sorted((("noir", d.bar_noir), ("median", d.bar_median),
                      ("blanc", d.bar_blanc)), key=lambda p: p[1])
        marques = [(x, {"noir": "#ffffff", "median": "#ffd75e",
                        "blanc": "#ffffff"}[cle],
                    "%s %.1f %%" % ({"noir": "Noir", "median": "Médian",
                                     "blanc": "Blanc"}[cle], val * 100), True)
                   for cle, val in pos
                   for x in [self._hist_x(val, w)]]
        if pic is not None:
            marques.append((self._hist_x(pic, w), "#7fb2d8",
                            "fond %.1f %%" % (100.0 * pic), False))
        marques.sort(key=lambda m: m[0])
        rangs = self._rangs_etiquettes([m[0] for m in marques],
                                       [7.0 * len(m[2]) + 4.0 for m in marques])
        for (x, col, lib, poignee), rang in zip(marques, rangs):
            if poignee:
                self.cv_hist.create_line(x, y0 + 8, x, y1, fill=col, width=2)
                self.cv_hist.create_rectangle(x - 4, y0 + 1, x + 4, y0 + 8,
                                              fill=col, outline="#101010")
            else:
                self.cv_hist.create_line(x, y0 + 8, x, y1, fill=col, width=1,
                                         dash=(4, 3))
            anc = "n" if 46 < x < w - 46 else ("nw" if x <= 46 else "ne")
            self.cv_hist.create_text(min(max(x, 3), w - 3),
                                     y0 + 10 + self.HIST_RANG_PX * rang,
                                     anchor=anc, fill=col, text=lib)
        # NB (constat sur capture réelle) : plus de légende DANS la bande basse
        # — celle-ci se posait sur la queue du tracé ; le sélecteur au-dessus et
        # la ligne d'état disent déjà ce que chaque bande contient.

    def _update_status(self, st):
        arc = f"Archive (re-stack) : {st.get('archive', 0)}"
        if st.get("archive_err"):
            arc += f" — {st['archive_err']}"
        # Jalon 17 : compteur des frames rejetées par le filtre défocalisation
        # (ligne seulement s'il y en a — zéro message superflu).
        lignes = [f"Frames : {st['frames']}",
                  f"Pixels rejetés (σ) : {st['rejets']}",
                  f"Frames non alignées : {st['bad']}"]
        if st.get("floues"):
            lignes.append(f"Frames floues rejetées : {st['floues']}")
        # Jalon 18 : compteur des re-stacks de la session (ligne seulement
        # s'il y en a — zéro message superflu).
        if st.get("restack_n"):
            lignes.append(f"Re-stacks (session) : {st['restack_n']}")
        lignes.append(f"Align. : {st.get('align', '—')}")
        if st.get("compo"):
            lignes.append(f"Canaux : {st['compo']}")
        lignes.append(arc)
        self.lbl_stats.config(text="\n".join(lignes))
        # Jalon 18 : ligne DÉDIÉE au re-stack — jamais écrasée par les
        # messages de frames (retour réel d'Alain : « pas simple de voir le
        # restack »). Gris = rien, vert = réussi, ambre = échec.
        detail_rs = st.get("restack", self.restack_info) or ""
        self.lbl_restack.config(text=detail_rs or "Re-stack : —",
                                foreground=self.restack_couleur)
        # Jalon 56 : ligne d'état de l'ASTROMÉTRIE — même logique que le
        # re-stack (jamais écrasée par les messages de frames) ; un dict
        # d'état d'ancien format (sans clé « astro ») laisse la ligne telle
        # quelle, et un état vide retombe sur le texte de SAISIE (côté UI).
        detail_as = st.get("astro", self.astro_info) or ""
        if detail_as:
            self.lbl_astro.config(text=detail_as,
                                  foreground=self.astro_couleur)
        else:
            self._maj_astro_vue()
        # Jalon 56 (étape 4) : ligne d'état de la PHOTOMÉTRIE (même logique).
        detail_ph = st.get("photo", self.photo_info) or ""
        if detail_ph:
            self.lbl_photo.config(text=detail_ph,
                                  foreground=self.photo_couleur)
        else:
            self._maj_photo_vue()
        self._maj_photo_gains_vue()      # étape 5 : ce qui est appliqué
        # Jalon 58 : ligne d'état de la SPCC absolue (même logique que la
        # photométrie : le texte du worker prime, sinon l'état connu côté UI).
        detail_sx = st.get("spcc", self.spcc_info) or ""
        if detail_sx:
            self.lbl_spcc.config(text=detail_sx,
                                 foreground=self.spcc_couleur)
        else:
            self._maj_spcc_vue()
        # Jalon 10 : seeing live (mesuré par le thread d'acquisition) —
        # jamais de silence : soit la mesure, soit la RAISON de son absence.
        s = st.get("seeing") or {}
        if s.get("nb"):
            fiable = s["nb"] >= seeing_live.MIN_ETOILES
            self.lbl_seeing.config(
                text=(f"Seeing (FWHM) : {s['fwhm']:.2f} px  ·  "
                      f"{s['nb']} étoiles"
                      + ("" if fiable else "  (peu fiable)")),
                foreground="#1d7f1d" if fiable else "#c98a00")
        elif st.get("seeing_msg"):
            self.lbl_seeing.config(text=f"Seeing : {st['seeing_msg']}",
                                   foreground="#c98a00")
        else:
            self.lbl_seeing.config(text="Seeing (FWHM) : —",
                                   foreground="#888888")
        extra = ""
        if st.get("pending"):
            extra += f"   |  en attente : {st['pending']}"
        if st.get("failed"):
            extra += f"   |  illisibles : {st['failed']}"
        self.lbl_last.config(text="Dernier fichier : "
                             f"{os.path.basename(st.get('file', '')) or '—'}{extra}")
        self.lbl_status.config(
            text=(f"{st['cam']}  |  {st['fps']:.1f} fps  |  "
                  f"{st['frames']} frames empilées (intégration cumulée)"
                  + (f"  |  recadrée {st['crop_w']}×{st['crop_h']}"
                     if st.get("crop_w") else "")))


def main():
    """Point d'entrée : ouvre la fenêtre principale.

    v2.38.7 : `report_callback_exception` est remplacé par le journal — une
    erreur dans un rappel d'interface (clic, curseur, touche) était écrite sur
    `stderr` et nulle part ailleurs, donc invisible pour une application
    lancée par le menu (constat d'Alain, 27/09/2026)."""
    root = tk.Tk()
    root.report_callback_exception = journal.rapport_callback
    App(root)
    root.mainloop()


