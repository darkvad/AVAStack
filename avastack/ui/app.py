# -*- coding: utf-8 -*-
"""Fenêtre principale AVAStack (Tkinter) : interface, thread d'acquisition,
orchestration calibration → alignement → empilement → affichage, et traitement
externe sur instantané."""

import os
import re
import time
import math
import queue
import shutil
import threading
import traceback

import numpy as np
import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from ..compat import IS_MACOS, IS_WINDOWS
from .. import AVASTACK_VERSION
from .. import delais
from .. import journal
from .. import ressources
from .. import travail
from ..config import CONFIG, sauver_config
from ..images import (borner_lineaire, lire_filtre_fits,
                      load_image, save_image, find_output, auto_unflip)
# Jalon 105a : `CFA_MODE` n'est plus utilisé DANS `app.py` (le panneau « Dossier
# surveillé » vit désormais dans `ui/panels/folder.py`) mais reste RÉ-EXPORTÉ
# ici pour ne pas rompre la surface publique figée (banc garde-fou).
from ..images import CFA_MODE                            # noqa: F401 (ré-export)
from ..cameras import (SimulatedCamera, OpenCVCamera, ZWOASICamera,
                       FolderCamera, MultiFolderCamera, QHYCamera,
                       PlayerOneCamera, TouptekCamera, SVBonyCamera)
# Jalon 105a : `SOURCES` n'est plus utilisé DANS `app.py` (le panneau
# « Caméra » vit désormais dans `ui/panels/camera.py`) mais reste RÉ-EXPORTÉ
# ici (surface publique figée).
from ..cameras import SOURCES                            # noqa: F401 (ré-export)
from ..cameras.base import FILTRES_ROUE
from ..cameras.qhy import lister_via_sous_processus, tracer_evt
from ..processing import Calibrator, StarAligner, LiveStacker, DisplayProcessor
from ..processing import alignment as align_mod
# Jalon 103 : `display_mod` n'est plus utilisé DANS `app.py` (le tracé de
# l'histogramme a migré vers `ui/widgets/histogram.py`) mais reste RÉ-EXPORTÉ
# ici pour ne pas rompre la surface publique figée de `app.py` (surveillée par
# le banc garde-fou, qui compte les noms importés du paquet `avastack`).
from ..processing import display as display_mod           # noqa: F401 (ré-export)
from ..processing.composition import (COMPOSITIONS, CompositeStacker,
                                      extraire_canal, composition_pour_roles,
                                      role_de_filtre, roles_de)
# Jalon 105b : `ROLES` n'est plus utilisé DANS `app.py` (le panneau
# « Composition multi-filtres » vit désormais dans `ui/panels/compo.py`) mais
# reste RÉ-EXPORTÉ ici pour ne pas rompre la surface publique figée de `app.py`
# (banc garde-fou, qui compte les noms importés du paquet `avastack`).
from ..processing.composition import ROLES               # noqa: F401 (ré-export)
# Jalon 104 : `MODES_L` n'est plus utilisé DANS `app.py` (restauration de la
# composition migrée vers `ui/config_ui.py`) mais reste RÉ-EXPORTÉ ici pour ne
# pas rompre la surface publique figée de `app.py` (banc garde-fou).
from ..processing.composition import MODES_L              # noqa: F401 (ré-export)
from ..processing.framestore import ArchiveFrames

# Jalon 102 (chantier de refactoring) : les CONSTANTES de l'interface (seuils,
# palettes, listes de choix) vivent désormais dans `avastack/ui/constants.py`
# (module TYPÉ). Deux modes de ré-exposition, pour que la surface publique de
# `app.py` reste INCHANGÉE :
#   - les constantes de MODULE ci-dessous sont ré-exportées ici (leur nom reste
#     offert directement par `avastack.ui.app.<NOM>`) ;
#   - les constantes de CLASSE de `App` sont, elles, ré-exposées plus bas en
#     attributs de classe alimentés par l'alias privé `_const` (cf. `class App`).
from . import constants as _const
from .constants import (CAMERAS_PILOTEES, FLU_MIN_REF, FLU_NB_FRAC,
                        FWHM_ABS_MIN, FWHM_MARGE,
                        RESTACK_HIST_MAX, RESTACK_MARGE, SCORE_MAX_ETOILES,
                        # Jalon 106a : `RESTACK_CADENCE`/`RESTACK_MIN_FRAMES` ne
                        # sont plus utilisés DANS `app.py` (la boucle du worker a
                        # migré vers `avastack/core/worker.py`, qui les lit par
                        # RÉSOLUTION TARDIVE `_globals_app()`) mais restent
                        # RÉ-EXPORTÉS ici pour ne pas rompre la surface publique
                        # figée (banc garde-fou).
                        RESTACK_CADENCE, RESTACK_MIN_FRAMES)  # noqa: F401

# (Caméras « pilotées » — jalon 35 — et filtre anti-brutes très défocalisées —
# jalon 17 — : leurs constantes vivent désormais dans `constants.py` et sont
# ré-exportées via l'import ci-dessus.)

# Jalon 103 (chantier de refactoring) : les WIDGETS de l'interface (sections
# pliables ; panneau d'histogramme + niveaux + saturation) vivent désormais dans
# `avastack/ui/widgets/` (modules TYPÉS), sous forme de « mixins » dont `App`
# HÉRITE. Les méthodes sont reprises VERBATIM de `app.py` : `self` reste
# l'instance `App`, donc `App.<méthode>` et `self.<méthode>` restent valides et
# le comportement (rendu) est inchangé AU BIT. Alias PRIVÉS (`_`) : les mixins
# ne comptent PAS dans la surface publique de `app.py` (motif du jalon 102).
from .widgets.collapsible import SectionsPliables as _SectionsPliables
from .widgets.histogram import PanneauHistogramme as _PanneauHistogramme

# Jalon 104 (chantier de refactoring) : la PERSISTANCE de la config de l'UI
# (charger/restaurer + sauver) vit dans `avastack/ui/config_ui.py` (TYPÉ), mixin
# dont `App` hérite — méthodes VERBATIM, alias PRIVÉ `_` (hors surface publique).
from .config_ui import ConfigUI as _ConfigUI

# Jalon 105a (chantier de refactoring) : les PANNEAUX « sources » de la colonne
# gauche (fichiers de travail, caméra, cadence, dossier surveillé) vivent
# désormais dans `avastack/ui/panels/` (modules TYPÉS), sous forme de mixins
# dont `App` HÉRITE — méthodes VERBATIM, alias PRIVÉS `_` (hors surface
# publique de `app.py`, motif des jalons 102/103/104). `_fmt_expo` (formateur
# d'exposition µs/ms/s, compagnon du panneau Caméra) est déplacé dans
# `panels/camera.py` et RÉ-IMPORTÉ ici : les méthodes d'exposition de `app.py`
# (`_maj_expo`, `_valider_expo`…) continuent de l'utiliser, et
# `avastack.ui.app._fmt_expo` reste résolvable (usage des bancs).
from .panels.files import PanneauFichiers as _PanneauFichiers
from .panels.camera import PanneauCamera as _PanneauCamera, _fmt_expo
from .panels.cadence import PanneauCadence as _PanneauCadence
from .panels.folder import PanneauDossierSurveille as _PanneauDossierSurveille

# Jalon 105b (chantier de refactoring) : la 2e vague de PANNEAUX de la
# colonne gauche — les panneaux « traitement » — vit aussi dans
# `avastack/ui/panels/` (modules TYPÉS, mixins dont `App` HÉRITE, méthodes
# VERBATIM). `stack.py` lit `CONFIG` par résolution TARDIVE (`_globals_app`)
# pour préserver l'interception des bancs (`ui.CONFIG`), comme le correctif
# du jalon 105a dans `ui/widgets/collapsible.py`.
from .panels.compo import PanneauComposition as _PanneauComposition
from .panels.calib import PanneauCalibration as _PanneauCalibration
from .panels.stack import PanneauEmpilement as _PanneauEmpilement
from .panels.bgnoise import PanneauFondGrain as _PanneauFondGrain
from .panels.sharp import PanneauNette as _PanneauNette

# Jalon 105c (chantier de refactoring) : la 3e vague de PANNEAUX de la
# colonne gauche — les panneaux « sortie » — vit aussi dans
# `avastack/ui/panels/` (modules TYPÉS, mixins dont `App` HÉRITE,
# méthodes reprises VERBATIM).
from .panels.display import PanneauAffichage as _PanneauAffichage
from .panels.color import PanneauCouleur as _PanneauCouleur
from .panels.state import PanneauEtatCalculs as _PanneauEtatCalculs
from .panels.external import PanneauTraitementExterne as _PanneauTraitementExterne
from .panels.output import PanneauSortie as _PanneauSortie

from ..processing import denoise as denoiser_local

# Jalon 106a (chantier de refactoring) : le THREAD D'ACQUISITION (méthode
# `_worker`) vit désormais dans `avastack/core/worker.py` (module TYPÉ),
# sous forme de mixin dont `App` HÉRITE — méthode reprise VERBATIM, alias
# PRIVÉ `_` (hors surface publique de `app.py`).
from ..core.worker import AcquisitionWorker as _AcquisitionWorker
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
# Jalon 96 (étapes 5-6) : annotation temps-réel de l'image AFFICHÉE — overlay
# OpenCV (objets célèbres + étoiles Gaia) sur une COPIE du buffer, jamais sur
# les données brutes ni dans les FITS (linéarité photométrique préservée).
from ..processing import annotations as annoter_mod
# Jalon 70 : CATALOGUES (dossier par OS, présence du catalogue astro, et
# téléchargement Gaia DR3) — l'astrométrie interne en dépend, et son absence
# doit être DITE (constat Linux du 27/09/2026 : échec silencieux).
from .. import catalogues as cat_mod
# Jalon 84 : GUET DE GEL du fil d'interface — « les boutons ne répondent pas »
# devient MESURABLE (durée + pile du fil retenu). Voir ui/reactivite.py.
from . import reactivite as reactivite_mod
# Jalon 56 (étape 4) : photométrie — zéro-point instrumental PAR BANDE via le
# WCS (appariement mutuel des étoiles de l'empilement au catalogue Gaia). On
# MESURE ici ; l'application aux gains du stacker est l'étape 5.
from ..processing import photometrie as photo_mod
from ..processing import spcc as spcc_mod
# Jalon 105c : `DEFAULT_CMD_GRAXPERT`, `DEFAULT_CMD_GRAXPERT_DN` et
# `DEFAULT_CMD_BXT` ne sont plus utilisés DANS `app.py` (le panneau
# « Traitement externe » vit désormais dans `ui/panels/external.py`) mais
# restent RÉ-EXPORTÉS ici pour ne pas rompre la surface publique figée de
# `app.py` (banc garde-fou).
from ..external.detection import (
    DEFAULT_CMD_GRAXPERT, DEFAULT_CMD_GRAXPERT_DN, DEFAULT_CMD_BXT,  # noqa: F401
    commande_avec_strength, detecter_outils)


class App(_SectionsPliables, _PanneauHistogramme, _ConfigUI,
          _PanneauFichiers, _PanneauCamera, _PanneauCadence,
          _PanneauDossierSurveille, _PanneauComposition,
          _PanneauCalibration, _PanneauEmpilement, _PanneauFondGrain,
          _PanneauNette, _PanneauAffichage, _PanneauCouleur,
          _PanneauEtatCalculs, _PanneauTraitementExterne, _PanneauSortie,
          _AcquisitionWorker):
    # Jalon 105a (chantier de refactoring) : `App` hérite AUSSI des mixins des
    # PANNEAUX « sources » extraits de cet objet vers `avastack/ui/panels/`
    # (fichiers de travail, caméra, cadence, dossier surveillé). `self` reste
    # l'instance `App` : l'ordre de pose des widgets et le comportement sont
    # inchangés AU BIT.
    # Jalon 105b (chantier de refactoring) : `App` hérite EN PLUS des mixins des
    # PANNEAUX « traitement » extraits vers `avastack/ui/panels/` (composition,
    # calibration, empilement, fond et grain, netteté live). Mêmes garanties :
    # `self` reste l'instance `App`, pose et comportement inchangés AU BIT.
    # Jalon 102 (chantier de refactoring) : les constantes de l'interface ont
    # été EXTRAITES dans `avastack/ui/constants.py` (typé). On ne conserve ici
    # que des RÉ-EXPOSITIONS en attributs de classe, pour que `App.<NOM>` et
    # `self.<NOM>` restent valides (API inchangée, comportement identique).
    W_IMG, H_IMG, W_HIST, H_HIST = (_const.W_IMG, _const.H_IMG,
                                    _const.W_HIST, _const.H_HIST)

    HIST_MODES = _const.HIST_MODES
    HIST_CODES = _const.HIST_CODES
    HIST_LABELS = _const.HIST_LABELS
    HIST_POINTS = _const.HIST_POINTS
    HIST_MARGE = _const.HIST_MARGE
    HIST_PRISE = _const.HIST_PRISE
    HIST_RANG_PX = _const.HIST_RANG_PX

    SPCC_TYPE_MONO = _const.SPCC_TYPE_MONO
    SPCC_TYPE_OSC = _const.SPCC_TYPE_OSC

    SECTIONS_NOM_MAP = _const.SECTIONS_NOM_MAP

    SECTION_TITRE_BG = _const.SECTION_TITRE_BG
    SECTION_TITRE_FG = _const.SECTION_TITRE_FG
    SECTION_TITRE_BG_ACTIF = _const.SECTION_TITRE_BG_ACTIF
    SECTION_CADRE = _const.SECTION_CADRE

    VL_DN_METHODES = _const.VL_DN_METHODES
    VL_DN_LABELS = _const.VL_DN_LABELS
    VL_DN_CODES = _const.VL_DN_CODES

    CADENCES = _const.CADENCES
    CADENCE_CODES = _const.CADENCE_CODES
    CADENCE_LABELS = _const.CADENCE_LABELS

    RAFALE_MAX = _const.RAFALE_MAX
    RAFALE_QUIET_S = _const.RAFALE_QUIET_S

    DN_EXT_METHODES = _const.DN_EXT_METHODES
    DN_EXT_LABELS = _const.DN_EXT_LABELS
    DN_EXT_CODES = _const.DN_EXT_CODES

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
        self._astro_name_proposed = False  # popup déjà proposée pour ce nom
        # Jalon 96 (étapes 5-6) : annotation temps-réel de l'image AFFICHÉE
        # (objets célèbres + étoiles brillantes). Les listes de ciel (objets,
        # étoiles) sont mises en CACHE par (centre, champ, seuil) : la lecture
        # du catalogue Gaia (≈ 1 Go) est trop lourde pour être refaite à
        # chaque rendu, et a fortiori sous le zoom. Le WCS, lui, est recalculé
        # à chaque rendu (une composition de matrice : négligeable).
        self._annote_cache = None         # (clé, objets, etoiles) du champ
        self._annote_rendu = None         # cache mono-slot de l'overlay dessiné
        self.var_debug = tk.BooleanVar(value=False)  # case « Debug général »
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
        # Jalon 80 : rendu DIFFÉRÉ en fin de rafale (sources dossier /
        # composition SEULEMENT — cf. `_cadence_dossier`). `_rendu_differ` =
        # nombre de frames du dernier empilement non encore rendu (None = rien
        # en attente), `_rendu_differ_t` = instant de cet empilement. Le rendu
        # part quand la rafale se tait (`RAFALE_QUIET_S`) ou que `RAFALE_MAX`
        # brutes se sont empilées depuis le dernier rendu.
        self._rendu_differ = None
        self._rendu_differ_t = 0.0
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
        # v2.48.1 (retour macOS du 30/09/2026) : identifiant de la
        # replanification de `_tick` (ANNULABLE à la fermeture — un `after` en
        # attente qui se déclenche APRÈS `root.destroy()` lève « invalid command
        # name .!… » : la fenêtre est détruite, le rappel ne doit plus courir)
        # et signature de la dernière erreur de la boucle (écriture UNE fois par
        # épisode : un widget durablement détruit ne doit pas noyer le journal).
        self._tick_id = None
        self._tick_err_sig = None
        # Variable pour le nom de cible manuel (utilisée dans panneaux Empilement et Astrométrie)
        self.var_nom_cible_manual = tk.StringVar(value="")
        # Suivi du dernier camera.last_file vu pour ne lire l'en-tête FITS qu'au changement
        self._dernier_last_file = ""
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
        # Jalon 84 : le GUET DE GEL est ARMÉ après la mise en route (1 s) —
        # il ne doit pas compter la construction de la fenêtre. Il écrit au
        # journal dès que le fil d'interface dépasse `SEUIL_S` sans rendre la
        # main, avec la PILE de ce fil (retour réel macOS 27 : « les boutons ne
        # sont pas toujours cliquables »).
        self.guet = reactivite_mod.Guet(self.root)
        self.root.after(1000, self.guet.demarrer)
        journal.note("démarrage", "prêt (mesures de disque différées, bornées)")
        self._planifier_tick(30)
        self.root.after(150, self._premieres_mesures)

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

        # --- Fichiers de travail et journal : EN HAUT de la colonne (v2.38.9 —
        # panneau extrait au jalon 105a dans `avastack/ui/panels/files.py`, qui
        # porte le « pourquoi ce placement »).
        self._poser_panneau_fichiers_travail(left)

        # --- Caméra : panneau extrait au jalon 105a (`avastack/ui/panels/
        # camera.py`). La SOURCE + Démarrer/Arrêter restent TOUJOURS visibles ;
        # les contrôles caméra vivent dans frm_ctrl_cam (visible seulement pour
        # une source caméra, jalon 47 — cf. `_maj_visibilite_cadres`).
        self._poser_panneau_camera(left)

        # --- Cadence d'empilement (panneau extrait au jalon 105a dans
        # `avastack/ui/panels/cadence.py` ; jalon 47 : UN SEUL cadre, partagé
        # par « Dossier surveillé » et « Composition multi-filtres »).
        self._poser_panneau_cadence(left)

        # --- Dossier surveillé (panneau extrait au jalon 105a dans
        # `avastack/ui/panels/folder.py` ; visible uniquement pour cette
        # source, jalon 47).
        self._poser_panneau_dossier_surveille(left)

        # --- Composition multi-filtres (panneau extrait au jalon 105b dans
        # `avastack/ui/panels/compo.py` ; jalon 19).
        self._poser_panneau_compo(left)

        # --- Calibration (panneau extrait au jalon 105b dans
        # `avastack/ui/panels/calib.py` ; ancre STABLE des cadres commutables
        # du jalon 47).
        self._poser_panneau_calibration(left)

        # --- Empilement (panneau extrait au jalon 105b dans
        # `avastack/ui/panels/stack.py` : stats, seeing, re-stack, astrométrie
        # + annotation, catalogues & données SPCC, photométrie, SPCC, rejet,
        # équilibrage des canaux, Linear Fit, filtre flou).
        self._poser_panneau_empilement(left)

        # --- Fond et grain (panneau extrait au jalon 105b dans
        # `avastack/ui/panels/bgnoise.py` ; AVANT étirement).
        self._poser_panneau_fond_grain(left)

        # --- Netteté live (panneau extrait au jalon 105b dans
        # `avastack/ui/panels/sharp.py` ; AVANT étirement, indépendant du
        # moteur d'étirement).
        self._poser_panneau_nette(left)

        # --- Affichage (panneau extrait au jalon 105c dans
        # `avastack/ui/panels/display.py` : moteur d'étirement STF/VeraLux,
        # réglages STF et communs, cadre VeraLux, rendu pleine résolution).
        self._poser_panneau_affichage(left)

        # --- Couleur de l'objet (panneau extrait au jalon 105c dans
        # `avastack/ui/panels/color.py` ; APRÈS étirement : SCNR, SCNR doux,
        # démagenta, boost du rouge SII).
        self._poser_panneau_couleur(left)

        # --- État des calculs (panneau extrait au jalon 105c dans
        # `avastack/ui/panels/state.py` : étapes du solveur + barre).
        self._poser_panneau_etat_calculs(left)

        # --- Traitement externe (panneau extrait au jalon 105c dans
        # `avastack/ui/panels/external.py` : GraXpert, débruitage,
        # BlurXTerminator, vue empilement/traitée, ⚡ et sorties liées).
        self._poser_panneau_traitement_externe(left)

        # --- Sortie (panneau extrait au jalon 105c dans
        # `avastack/ui/panels/output.py` : enregistrements linéaire, traité
        # (linéaire), tel que vu et par filtre).
        self._poser_panneau_sortie(left)


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

    # ------------------------------------------------- dialogues (jalon 84)
    # POURQUOI (retour RÉEL d'un testeur sous macOS 27 « Golden Gate »,
    # 30/09/2026) : « les boutons ne sont pas toujours cliquables… le bouton
    # permettant de choisir le dossier à surveiller ne répond pas ». TOUS les
    # dialogues de l'application étaient ouverts SANS `parent=` : macOS ouvre
    # alors un panneau ou une alerte APPLICATIVE LIBRE (NSOpenPanel / NSAlert
    # non attaché), qui peut se retrouver DERRIÈRE la fenêtre principale —
    # laquelle, elle, ATTEND la réponse (attente modale). L'application paraît
    # insensible : les clics ne produisent rien tant qu'ils n'atteignent pas la
    # boîte invisible. Avec `parent=`, Tk demande à macOS une FEUILLE ATTACHÉE
    # à la fenêtre : elle est toujours devant son parent, quel que soit l'état
    # du gestionnaire de fenêtres (et sur Windows/Linux, cela ne change rien
    # d'observable : la boîte reste modale).
    # Tous les dialogues passent par les aides ci-dessous — le banc
    # `_test_dialogues_jalon84.py` REFUSE tout appel direct résiduel : un seul
    # appel oublié ramènerait le défaut.
    def _parent_dlg(self):
        """Fenêtre parente des dialogues, ou None si la racine n'existe plus."""
        try:
            if self.root.winfo_exists():
                return self.root
        except Exception:                  # racine détruite (fermeture)
            pass
        return None

    def _kw_parent(self):
        """`{"parent": …}`, ou vide si la fenêtre n'existe plus.

        Jamais `parent=None` : Tk refuserait alors l'appel (chaîne vide reçue
        comme un nom de fenêtre)."""
        parent = self._parent_dlg()
        return {"parent": parent} if parent is not None else {}

    def _demander_dossier(self, titre, depart=None):
        """Boîte « choisir un dossier », ATTACHÉE à la fenêtre (cf. plus haut)."""
        opts = dict(title=titre)
        opts.update(self._kw_parent())
        if depart:
            opts["initialdir"] = depart
        return filedialog.askdirectory(**opts)

    def _demander_fichier(self, titre=None, filetypes=None, initialdir=None):
        """Boîte « ouvrir un fichier », ATTACHÉE à la fenêtre (cf. plus haut)."""
        opts = dict(self._kw_parent())
        if titre:
            opts["title"] = titre
        if filetypes:
            opts["filetypes"] = filetypes
        if initialdir:
            opts["initialdir"] = initialdir
        return filedialog.askopenfilename(**opts)

    def _enregistrer_sous(self, titre=None, defaultextension=None,
                          filetypes=None, initialfile=None):
        """Boîte « enregistrer sous », ATTACHÉE à la fenêtre (cf. plus haut)."""
        opts = dict(self._kw_parent())
        if titre:
            opts["title"] = titre
        if defaultextension:
            opts["defaultextension"] = defaultextension
        if filetypes:
            opts["filetypes"] = filetypes
        if initialfile:
            opts["initialfile"] = initialfile
        return filedialog.asksaveasfilename(**opts)

    def _proposer_nom_cible(self, suffixe="", extension="fits"):
        r"""Nom de fichier initial suggéré pour les boîtes d'enregistrement,
        à partir du mot-clé FITS OBJECT (ou OBJNAME/TARGNAME/TARGET) de la
        DERNIÈRE brute lue — sans cette clé, l'utilisateur tape un nom à la
        main, comme avant.

        RÈGLES (jalon « nom de cible auto ») :
          • opt-in via `CONFIG["nom_cible_auto"]` (True par défaut) ;
          • si le nom est absent du header, ou si la lecture échoue, on
            retourne None (la boîte reste sans nom pré-rempli) ;
          • le nom est SANITISÉ pour Windows/macOS/Linux : caractères de
            contrôle, séparateurs (`/\:*?"<>|`), blancs aux extrémités ;
            les espaces internes sont conservés (un nom « M 31 » reste
            lisible), les espaces multiples sont collapsés ;
          • le suffixe (p.ex. « _traite », « _tel_que_vu ») et l'extension
            (sans point) sont ajoutés si fournis.

        → str terminée par l'extension SANS point, ou None si rien à proposer."""
        if not bool(CONFIG.get("nom_cible_auto", True)):
            return None
        chemin = ""
        try:
            chemin = getattr(self.camera, "last_file", "") or ""
        except Exception:
            chemin = ""
        if not chemin:
            return None
        try:
            nom = astro_mod.nom_objet_entete_fits(chemin) or ""
        except Exception:
            return None
        if not nom:
            return None
        # Sanitisation : on retire tout caractère qui poserait problème sur
        # Windows (\ / : * ? " < > |) ou les caractères de contrôle ; les
        # espaces en trop sont collapsés, ceux du début/fin retirés.
        nom = re.sub(r"[\\/:\"*?|<>]", "_", nom)
        nom = re.sub(r"[\x00-\x1f]", "", nom)
        nom = re.sub(r"\s+", " ", nom).strip(" .")
        if not nom:
            return None
        base = nom + (suffixe or "")
        if extension:
            return f"{base}.{extension.lstrip('.')}"
        return base

    @staticmethod
    def _sanitize_nom(nom: str) -> str:
        """Nettoie un nom de fichier pour être valide sur Win/Linux/macOS."""
        import re
        nom = re.sub(r"[\\\\/:\\\"*?|<>]", "_", nom)
        nom = re.sub(r"[\x00-\x1f]", "", nom)
        nom = re.sub(r"\s+", " ", nom).strip(" .")
        return nom

    def _objets_celestes_resolus(self) -> list | None:
        """Objets célèbres trouvés par l'astrométrie (WCS résolu), DÉDUPLIQUÉS
        par position : NGC 224 et M31 sont le même objet aux mêmes coordonnées —
        un seul représentant par groupe, avec le MEILLEUR nom (Messier d'abord,
        « M31 » plus reconnaissable que « 224 » ou « Great Nebula in … » tronqué).
        → liste triée (Messier d'abord, puis distance/éclat), ou None si aucun
        match ou astrométrie non résolue."""
        if self.suivi_astro is None or not getattr(self.suivi_astro, "resolu", False):
            return None
        ra = getattr(self.suivi_astro, "ra0", None)
        dec = getattr(self.suivi_astro, "dec0", None)
        if ra is None or dec is None:
            return None
        try:
            from avastack.catalogues import (cherche_celebres,
                                             deduplique_celebres)

            objets = cherche_celebres(ra, dec, rayon_deg=0.5)
            if self.var_debug.get():
                if objets:
                    details = [(o.designation, o.type_obj, o.mag_v, o.size_arcmin) for o in objets[:6]]
                    journal.note("DEBUG", f"_objets_celestes_resolus: cherche_celebres({ra:.4f}, {dec:.4f}, 0.5°) -> {len(objets)} objets: {details}")
                else:
                    journal.note("DEBUG", f"_objets_celestes_resolus: cherche_celebres({ra:.4f}, {dec:.4f}, 0.5°) -> AUCUN objet trouvé")
            if not objets:
                return None

            # Déduplication par position (~0,01°) PARTAGÉE avec l'annotation
            # (`catalogues.celebres.deduplique_celebres`) : une seule source
            # de vérité — le meilleur nom (Messier d'abord), tri distance/éclat.
            reps = deduplique_celebres(objets, ra, dec)
            return reps
        except Exception as e:
            if self.var_debug.get():
                journal.note("DEBUG", f"_objets_celestes_resolus: exception: {e}")
            return None

    def _nom_cible_astro_only(self) -> str | None:
        """Retourne le nom détecté par l'astrométrie (match céleste UNIQUEMENT).
        N'utilise PAS la priorité manuel, NI le fallback FITS — sert pour le popup
        de confirmation : « L'astrométrie a résolu la cible : M31 »."""
        objets = self._objets_celestes_resolus()
        if not objets:
            if self.var_debug.get():
                journal.note("DEBUG", "_nom_cible_astro_only: aucun match céleste")
            return None
        nom = self._sanitize_nom(objets[0].designation)
        if self.var_debug.get():
            journal.note("DEBUG", f"_nom_cible_astro_only: céleste={nom!r}")
        return nom

    def _nom_cible_pour_sauvegarde(self) -> str | None:
        """Retourne le nom de base à proposer dans les boîtes « Enregistrer ».
        Priorité stricte :
        1. Nom saisi manuellement (var_nom_cible_manual)
        2. Match céleste (WCS résolu + catalogue célèbres)
        3. En-tête FITS de la dernière brute (OBJECT/OBJNAME/TARGNAME/TARGET)
        4. None
        """
        # 1. Manuel
        manuel = self.var_nom_cible_manual.get().strip()
        if manuel:
            if self.var_debug.get():
                journal.note("DEBUG", f"_nom_cible_pour_sauvegarde: manuel={manuel!r}")
            return self._sanitize_nom(manuel)
        # 2. Match céleste
        if self.suivi_astro and getattr(self.suivi_astro, "resolu", False):
            ra = getattr(self.suivi_astro, "ra0", None)
            dec = getattr(self.suivi_astro, "dec0", None)
            if ra is not None and dec is not None:
                try:
                    from avastack.catalogues import cherche_celebres
                    objets = cherche_celebres(ra, dec, rayon_deg=0.5)
                    if objets:
                        nom = self._sanitize_nom(objets[0].designation)
                        if self.var_debug.get():
                            journal.note("DEBUG", f"_nom_cible_pour_sauvegarde: céleste={nom!r}")
                        return nom
                except Exception:
                    pass
        # 3. FITS header
        chemin = getattr(self.camera, "last_file", "") or ""
        if chemin:
            try:
                nom = astro_mod.nom_objet_entete_fits(chemin)
                if nom:
                    nom = self._sanitize_nom(nom)
                    if self.var_debug.get():
                        journal.note("DEBUG", f"_nom_cible_pour_sauvegarde: FITS={nom!r}")
                    return nom
            except Exception:
                pass
        # 4. Rien
        if self.var_debug.get():
            journal.note("DEBUG", "_nom_cible_pour_sauvegarde: aucun nom trouvé")
        return None

    def _dire(self, titre, message):
        """Information ATTACHÉE à la fenêtre (jamais derrière elle)."""
        messagebox.showinfo(titre, message, **self._kw_parent())

    def _avertir(self, titre, message):
        """Avertissement ATTACHÉ à la fenêtre (jamais derrière elle)."""
        messagebox.showwarning(titre, message, **self._kw_parent())

    def _signaler(self, titre, message):
        """Erreur ATTACHÉE à la fenêtre (jamais derrière elle)."""
        messagebox.showerror(titre, message, **self._kw_parent())

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
        # Jalon 84 : la boîte doit être MAPPÉE avant le grab (sur macOS comme
        # sous X11, un grab posé sur une fenêtre pas encore affichée est au
        # mieux sans effet, au pire bloquant), puis placée DEVANT la fenêtre
        # principale : c'est le pendant, pour cette boîte maison, du `parent=`
        # des boîtes Tk standard (cf. les aides de dialogue ci-dessus).
        dlg.update_idletasks()
        try:
            dlg.lift()
            dlg.focus_force()
            if IS_MACOS:
                dlg.attributes("-topmost", True)
        except Exception:
            pass
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
        # Réinitialiser la proposition de nom quand l'astrométrie est désactivée
        if not self._astro_actif:
            self._astro_name_proposed = False
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
                # Nouveaux indices → nouvelle proposition de nom possible
                self._astro_name_proposed = False
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

    # ------------------------------------ jalon 96 : annotation temps-réel
    def _seuil_mag(self):
        """Seuil de magnitude des étoiles annotées (jalon 96), lu TOLÉRANT
        (saisie invalide = valeur de config) et BORNÉ (0 à 20 : un seuil
        aberrant ne doit pas noyer l'image d'étiquettes)."""
        try:
            v = float(str(self.var_seuil_mag_etoiles.get()).replace(",", "."))
        except (tk.TclError, TypeError, ValueError):
            v = float(CONFIG.get("seuil_mag_etoiles", 8.0))
        return min(20.0, max(0.0, v))

    def _on_annoter(self):
        """Cases « Annoter objets célèbres » / « Étoiles brillantes » / seuil
        de magnitude / PNG compagnon (jalon 96, étapes 5-6) : persistance
        IMMÉDIATE (comme les autres cases), cache des listes de ciel INVALIDÉ
        (un seuil changé doit relire le catalogue) et rendu immédiat."""
        CONFIG["annoter_objets"] = bool(self.var_annoter_objets.get())
        CONFIG["annoter_etoiles"] = bool(self.var_annoter_etoiles.get())
        CONFIG["annoter_visibles"] = bool(self.var_annoter_visibles.get())
        CONFIG["annoter_sauvegarde"] = bool(self.var_annoter_sauvegarde.get())
        CONFIG["seuil_mag_etoiles"] = self._seuil_mag()
        sauver_config(CONFIG)
        self._annote_cache = None
        self._annote_rendu = None
        self._refresh_preview()

    def _forme_pleine(self, disp=None):
        """Forme (h, w) PLEINE RÉSOLUTION de la grille recadrée affichée, ou
        None. `stacker.cadre` = (y0, x0, y1, x1) du recadrage d'intersection :
        la grille affichée en est le recadrage. Sans cadre, la copie pleine
        résolution de l'empilement fait foi ; à défaut, l'aperçu RÉDUIT d'un
        facteur uniforme `_echelle_apercu` (posé par le worker) est remonté.
        → None si aucune de ces sources n'est disponible : JAMAIS de forme
        devinée (l'annotation serait décalée)."""
        st = self.stacker
        if st is None:
            return None
        cadre = getattr(st, "cadre", None)
        if cadre:
            try:
                y0, x0, y1, x1 = (int(v) for v in cadre)
            except (TypeError, ValueError):
                return None
            if y1 - y0 > 0 and x1 - x0 > 0:
                return (y1 - y0, x1 - x0)
            return None
        plein = getattr(self, "_stack_pleine_res", None)
        if plein is not None:
            h, w = plein.shape[:2]
            return (int(h), int(w))
        if disp is not None and not self._pleine_res_activee():
            s = float(getattr(self, "_echelle_apercu", 1.0) or 1.0)
            if 0.0 < s < 1.0:
                h, w = disp.shape[:2]
                return (int(round(h / s)), int(round(w / s)))
        return None

    def _wcs_affichage(self, disp):
        """WCS du buffer AFFICHÉ, ou None (astrométrie non résolue, pas de
        forme). Le WCS rendu est celui de la grille recadrée PLEINE
        résolution, ENVELOPPÉ dans `WcsEchelle` : l'aperçu est une réduction
        uniforme de cette grille, multiplier les coordonnées suffit."""
        sa = self.suivi_astro
        if sa is None or not getattr(sa, "resolu", False):
            return None
        if disp is None:
            return None
        st = self.stacker
        cadre = getattr(st, "cadre", None) if st is not None else None
        wcs, msg = sa.wcs_grille(cadre=cadre)
        if wcs is None:
            return None
        forme = self._forme_pleine(disp)
        if forme is None:
            return None
        ech = float(disp.shape[1]) / float(forme[1])
        return annoter_mod.WcsEchelle(wcs, ech)

    def _donnees_annotation(self, wcs, disp):
        """Listes de ciel de l'annotation (objets célèbres + étoiles Gaia du
        champ), mises en CACHE par (centre, champ, seuil) : la lecture du
        catalogue Gaia (≈ 1 Go) est trop lourde pour un rendu par image, et a
        fortiori sous le zoom. → (objets, etoiles) ; (None, None) si rien
        d'exploitable (catalogue absent, champ vide)."""
        sa = self.suivi_astro
        ra = getattr(sa, "ra0", None)
        dec = getattr(sa, "dec0", None)
        if ra is None or dec is None:
            return None, None
        champ = getattr(sa, "champ", None)
        seuil = self._seuil_mag()
        objets_act = bool(self.var_annoter_objets.get())
        etoiles_act = bool(self.var_annoter_etoiles.get())
        rayon = max(0.5, float(champ)) if champ else 0.5
        cle = (round(float(ra), 4), round(float(dec), 4), round(rayon, 3),
               round(seuil, 2), objets_act, etoiles_act)
        c = self._annote_cache
        if c is not None and c[0] == cle:
            return c[1], c[2]
        objets = etoiles = None
        if objets_act:
            try:
                objets = cat_mod.celebres.cherche_celebres(
                    ra, dec, rayon) or None
                if objets:
                    # DÉDUPLICATION PARTAGÉE : le catalogue brut renvoie M31 +
                    # NGC 224 + « 224 » aux MÊMES coordonnées — les doublons
                    # empilaient leurs textes au même endroit, illisibles
                    # (constat Alain sur M31, 04/10/2026).
                    objets = (cat_mod.celebres.deduplique_celebres(
                        objets, ra, dec) or None)
            except Exception:
                objets = None
        if etoiles_act:
            forme = self._forme_pleine(disp)
            if forme is not None:
                try:
                    etoiles, _msg = photo_mod.etoiles_catalogue(
                        wcs, forme, limmag=seuil)
                    etoiles = etoiles or None
                except Exception:
                    etoiles = None
        self._annote_cache = (cle, objets, etoiles)
        return objets, etoiles

    def _annoter_image(self, disp, echelle_police=1.0):
        """Copie de l'image affichée AVEC l'annotation (objets + étoiles), ou
        l'image telle quelle si rien à dessiner. `_last_disp` reste SANS
        annotation : le PNG compagnon et le zoom repartent de la version
        propre, jamais d'une image déjà annotée (double étiquette).
        `echelle_police` (v2.55.3) : taille des étiquettes pour une TAILLE À
        L'ÉCRAN constante (pleine résolution ≠ aperçu).
        Cache MONO-SLOT : à pleine résolution l'overlay recopie ~69 Mo — le
        glissement de vue (pan) re-rend en continu, le cache l'évite. La clé
        retient le buffer (id + référence, donc pas d'id recyclé), l'échelle
        et l'état des deux cases."""
        if disp is None:
            return disp
        try:
            objets_act = bool(self.var_annoter_objets.get())
            etoiles_act = bool(self.var_annoter_etoiles.get())
            visibles_act = bool(self.var_annoter_visibles.get())
        except (tk.TclError, AttributeError):
            return disp
        if not (objets_act or etoiles_act):
            return disp
        cle_cache = (id(disp), round(float(echelle_police), 3),
                     objets_act, etoiles_act, visibles_act)
        c = getattr(self, "_annote_rendu", None)
        if c is not None and c[0] == cle_cache:
            return c[1]
        wcs = self._wcs_affichage(disp)
        if wcs is None:
            return disp
        objets, etoiles = self._donnees_annotation(wcs, disp)
        if objets is None and etoiles is None:
            return disp
        img = np.ascontiguousarray(disp)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        img_ann = annoter_mod.generer_image_annotee(
            img, wcs, objets, etoiles, self._seuil_mag(),
            annoter_objets=objets_act, annoter_etoiles=etoiles_act,
            echelle_police=echelle_police, seulement_visibles=visibles_act)
        if img_ann is None:
            return disp
        self._annote_rendu = (cle_cache, img_ann, disp)
        return img_ann

    def _sauver_png_annote(self, chemin):
        """PNG annoté COMPAGNON à côté du FITS (jalon 96, étape 6) : copie du
        buffer d'affichage courant (PROPRE) + étiquettes. → (chemin écrit,
        message d'erreur) ; (None, "") si rien à écrire. AUCUNE exception
        propagée : un PNG compagnon ne doit jamais faire échouer la
        sauvegarde du FITS (linéarité photométrique préservée)."""
        try:
            if not (bool(CONFIG.get("annoter_sauvegarde", True))
                    and self.var_annoter_sauvegarde.get()):
                return None, ""
            objets_act = bool(self.var_annoter_objets.get())
            etoiles_act = bool(self.var_annoter_etoiles.get())
            visibles_act = bool(self.var_annoter_visibles.get())
        except (tk.TclError, AttributeError):
            return None, ""
        if not (objets_act or etoiles_act):
            return None, ""
        disp = getattr(self, "_last_disp", None)
        if disp is None:
            return None, ""
        wcs = self._wcs_affichage(disp)
        if wcs is None:
            return None, ""
        objets, etoiles = self._donnees_annotation(wcs, disp)
        if objets is None and etoiles is None:
            return None, ""
        img = np.ascontiguousarray(disp)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        # Même échelle que le DERNIER rendu à l'écran (le PNG doit ressembler
        # à l'écran) ; jamais rendu → repli sur la taille de l'image.
        echelle = getattr(self, "_echelle_police_annot", None)
        if not echelle or echelle < 1.0:
            ih, iw = img.shape[:2]
            echelle = min(12.0, max(1.0, max(ih, iw) / 1600.0))
        img_ann = annoter_mod.generer_image_annotee(
            img, wcs, objets, etoiles, self._seuil_mag(),
            annoter_objets=objets_act, annoter_etoiles=etoiles_act,
            echelle_police=echelle, seulement_visibles=visibles_act)
        if img_ann is None:
            return None, ""
        sortie = os.path.splitext(chemin)[0] + "_annote.png"
        try:
            save_image(sortie, img_ann.astype(np.float32) / 255.0)
        except Exception as exc:
            return None, str(exc)
        return sortie, ""

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
                            getattr(self, "btn_celebres_dl", None),
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
        d = self._demander_dossier(
            "Dossier de la base SPCC",
            depart or os.path.expanduser("~"))
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
        d = self._demander_dossier("Dossier des catalogues (Gaia/Siril)",
                                   depart)
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

    def _telecharger_celebres(self):
        """Télécharge le catalogue d'objets célèbres (Messier, NGC, IC, Sh2, Barnard, LDN)
        dans le dossier des catalogues — thread DÉDIÉ : reprise après coupure et sha256
        vérifié par le téléchargeur ; l'interface ne reçoit que des messages par file
        (jamais d'appel Tk depuis ce thread)."""
        try:
            dossier = cat_mod.dossier_catalogues()
        except Exception as exc:
            self.lbl_cat_etat.config(
                text=f"célèbres : dossier des catalogues illisible ({exc})",
                foreground="#d04040")
            return

        def fin(res):
            chemin, telecharge = res
            if telecharge:
                return f"catalogue d'objets célèbres téléchargé : {os.path.basename(chemin)}"
            return f"catalogue d'objets célèbres déjà présent : {os.path.basename(chemin)}"

        self._lancer_telechargement(
            "celebres", dossier,
            lambda d, prog: cat_mod.telecharger_catalogue_celebres(d, prog),
            "du catalogue d'objets célèbres (≈ quelques Mo)", fin)

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
        # v2.48.1 : « existe ENCORE » (créé ET pas détruit) plutôt que « a été
        # créé » — un widget détruit par une boîte de dialogue native macOS
        # doit faire taire le libellé, pas lever « invalid command name .!… »
        # à chaque tick (le symptôme du journal du testeur macOS).
        if not self._widget_vivant(getattr(self, "lbl_fit", None)):
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
            self._signaler(
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
                self._avertir(
                    "GraXpert live",
                    "Commande GraXpert absente ou incomplète.\n"
                    "Vérifiez la commande dans « Traitement externe » "
                    "(elle doit contenir {input} et {output} ou {outbase}).")
                return
            manque = gx_live.outil_manquant(cmd)
            if manque:
                self.var_vl_graxpert.set(False)
                self._avertir(
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
        réglages change → re-résolution. Vaut pour LES DEUX VUES (v2.48.1) : la
        chaîne couleur suit l'étirement et n'est plus dans la chaîne externe.
        Jalon 39 : relance le rendu IMMÉDIATEMENT (comme GraXpert live,
        le débruitage et la netteté) — sans ce rafraîchissement, la
        nouvelle chaîne n'était soumise au solveur qu'à la prochaine
        frame empilée ou au prochain réglage appelant _refresh_preview
        (constat réel d'Alain : les cases couleur semblaient inertes
        jusqu'à l'un des deux, par ex. bouger le fond cible)."""
        self._sync_vl_scnr_vue()
        self._refresh_preview()

    def _sync_vl_scnr_vue(self):
        """État SEUL (sans rendu) de la case SCNR — appelé par la case ET
        par _tick/_on_view.

        v2.48.1 (constat d'Alain, 01/10/2026 : « les corrections de couleurs
        ne sont plus dans le traitement externe et celles du live ne sont pas
        appliquées sur l'affichage de la vue traitée ») : la chaîne couleur
        SUIT l'étirement (jalon 85) et n'appartient PLUS à la chaîne externe —
        elle doit donc s'appliquer DANS LES DEUX VUES, y compris « traitée »
        (qui passe par le même étirement que le live). Avant, elle était
        coupée en vue « traitée » pour éviter un DEUXIÈME traitement, parce que
        le résultat ⚡ LINÉAIRE la portait déjà : ce n'est plus le cas, et la
        vue « traitée » restait VERTE. Les corrections PRÉ-étirement (fond,
        chroma) restent, elles, coupées — elles SONT dans la chaîne externe."""
        actif = bool(self.var_vl_scnr.get())
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
        """Vue « empilement » uniquement : la neutralisation du fond est une
        correction PRÉ-étirement qui RESTE dans la chaîne externe ⚡ (indice 8
        du job) — le résultat ⚡ la porte déjà, la refaire à l'affichage ferait
        un DEUXIÈME traitement. (Contraste avec les corrections APRÈS
        étirement, qui valent pour les deux vues depuis la v2.48.1.)"""
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
        vue « empilement » uniquement : comme la neutralisation du fond, cette
        correction PRÉ-étirement RESTE dans la chaîne externe ⚡ (indice 9 du
        job) ; la refaire à l'affichage doublerait le traitement."""
        actif = bool(self.var_vl_chroma.get()) \
            and self.var_view.get() != "traitée"
        if actif != self.disp.vl_chroma:
            self.disp.vl_chroma = actif      # la clé change → re-résolution

    def _on_vl_preserve(self):
        """Case « Préserver la luminosité (L*) » (v2.48.0, jalon 85) : lue par la
        chaîne couleur APRÈS étirement — la clé des réglages change (solveur
        VeraLux relancé) et les modes STF/manuel sont refaits. Rendu IMMÉDIAT
        (leçon du jalon 39, revécue à chaque case couleur). N'agit QUE sur les
        pixels réellement corrigés : sur une image sans excès de vert, cocher ou
        décocher ne change rien (identité au bit)."""
        self.disp.vl_preserve_luminance = bool(self.var_vl_preserve.get())
        self._refresh_preview()

    def _on_vl_scnr_force(self):
        """Curseur « Force du SCNR » (v2.48.0) : 1,00 = formule historique des
        jalons 22/23 (AU BIT PRÈS), 0,00 = aucun effet. Entre les deux, une part
        de l'excès de vert est conservée — c'est à force < 1,00 que le « SCNR
        doux » redevient actif derrière lui (MESURÉ : à force 1,00 l'excès est
        ≤ 0 partout, écart 2,98·10⁻⁸ — banc jalon 85 [6])."""
        try:
            self.disp.vl_scnr_force = min(
                1.0, max(0.0, float(self.var_vl_scnr_force.get())))
        except (tk.TclError, TypeError, ValueError):
            pass                            # saisie invalide : on garde
        self._refresh_preview()

    def _on_vl_demagenta_force(self):
        """Curseur « Force du démagenta » (v2.48.0) : part du magenta retirée
        (1,00 = formule historique des jalons 22/23, AU BIT PRÈS)."""
        try:
            self.disp.vl_demagenta_force = min(
                1.0, max(0.0, float(self.var_vl_demagenta_force.get())))
        except (tk.TclError, TypeError, ValueError):
            pass
        self._refresh_preview()

    def _on_vl_boost(self):
        """Case « Boost du rouge (SII) — masqué à l'objet » (v2.48.0, jalon 86) :
        rendu IMMÉDIAT (leçon des cases couleur, jalon 39). La case entre dans la
        clé des réglages du solveur VeraLux (donc re-résolution) et dans les
        réglages du rendu pleine résolution : le fichier « tel que vu » suit
        l'écran."""
        self._sync_vl_boost_vue()
        self._refresh_preview()

    def _sync_vl_boost_vue(self):
        """État SEUL (sans rendu) du boost du rouge. v2.48.1 : comme les autres
        corrections de couleur (elles suivent l'étirement, cf.
        `_sync_vl_scnr_vue`), le boost s'applique DANS LES DEUX VUES — la vue
        « traitée » l'applique sur l'image externe comme le live l'applique sur
        l'empilement."""
        actif = bool(self.var_vl_boost.get())
        if actif != self.disp.vl_boost_rouge:
            self.disp.vl_boost_rouge = actif    # la clé change → re-résolution

    def _on_vl_boost_force(self):
        """Curseur « Force du boost » (v2.48.0, jalon 86) : 1,00 = identité AU BIT
        PRÈS (aucun pixel touché : le réglage peut rester en place sans rien
        changer), 3,00 = le doré mesuré sur l'empilement d'Alain, 4,00 = le
        maximum. Une saisie invalide laisse la valeur précédente."""
        try:
            self.disp.vl_boost_force = min(
                float(couleurs_mod.BOOST_ROUGE_MAX),
                max(float(couleurs_mod.BOOST_ROUGE_MIN),
                    float(self.var_vl_boost_force.get())))
        except (tk.TclError, TypeError, ValueError):
            pass                            # saisie invalide : on garde
        self._refresh_preview()

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
        """État SEUL (sans rendu) de la case démagenta. v2.48.1 : s'applique
        DANS LES DEUX VUES, comme les autres corrections de couleur qui suivent
        l'étirement (`_sync_vl_scnr_vue`)."""
        actif = bool(self.var_vl_demagenta.get())
        if actif != self.disp.vl_demagenta:
            self.disp.vl_demagenta = actif  # la clé change → re-résolution

    def _on_vl_scnr_doux(self):
        """Case SCNR doux (jalon 23) : idem SCNR — bruit seul, structure
        préservée (pensé pour les palettes narrowband). Jalon 39 : rendu
        immédiat."""
        self._sync_vl_scnr_doux_vue()
        self._refresh_preview()

    def _sync_vl_scnr_doux_vue(self):
        """État SEUL (sans rendu) de la case SCNR doux. v2.48.1 : s'applique
        DANS LES DEUX VUES, comme les autres corrections de couleur qui suivent
        l'étirement (`_sync_vl_scnr_vue`)."""
        actif = bool(self.var_vl_scnr_doux.get())
        if actif != self.disp.vl_scnr_doux:
            self.disp.vl_scnr_doux = actif  # la clé change → re-résolution

    def _sync_vl_couleur_vue(self):
        """Chaîne couleur APRÈS étirement (jalon 22/23, déplacée après
        l'étirement au jalon 85 : SCNR, SCNR doux, démagenta, boost du rouge)
        ET corrections PRÉ-étirement (neutralisation du fond, bruit
        chromatique). Appelée par _tick TOUTES les 30 ms : elle ne touche qu'à
        l'ÉTAT (les _sync_*), JAMAIS au rendu — les _on_* (avec
        _refresh_preview) ne sont appelés que par les cases elles-mêmes
        (jalon 39 : un rendu ici serait déclenché 3× par tick).

        v2.48.1 : les synchros ne partagent plus la même règle de vue. Celles
        qui suivent l'ÉTIREMENT (SCNR, SCNR doux, démagenta, boost du rouge)
        valent pour LES DEUX VUES ; celles qui restent dans la chaîne EXTERNE
        (neutralisation du fond, bruit chromatique) restent coupées en vue
        « traitée » — le résultat ⚡ les porte déjà (double traitement sinon)."""
        self._sync_vl_scnr_vue()
        self._sync_vl_scnr_doux_vue()
        self._sync_vl_demagenta_vue()
        self._sync_vl_boost_vue()           # v2.48.0 (jalon 86) : boost du rouge
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

    # `_creer_cadence` et `_maj_lbl_cadence` ont été EXTRAITS au jalon 105a du
    # chantier de refactoring vers `avastack/ui/panels/cadence.py` (mixin
    # `PanneauCadence`, dont `App` hérite) — code repris VERBATIM.

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
        d = self._demander_dossier(
            "Dossier des brutes « "
            + (self.var_compo_roles[i].get() or "rôle ?") + " »")
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
            self._dire("Détection des filtres", "\n".join(rapports))
        else:
            self._dire("Détection des filtres",
                       "Aucun dossier rempli dans la composition.")

    def _save_canaux(self):
        """Sauvegarde des empilements PAR CANAL (jalon 19) : un fichier
        « canal_<rôle>.fit » (linéaire, recadré au cadre commun) par rôle
        empilé. Consommée par le thread d'acquisition (comme save_request)."""
        if not (self._mode_compo and self.stacker is not None
                and self.stacker.n > 0):
            self._dire(
                "Canaux", "Rien à enregistrer : démarrez une session en mode "
                          "composition et attendez au moins une frame.")
            return
        d = self._demander_dossier(
            "Dossier où enregistrer les empilements par canal")
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
        dossier → composition) JUSTE AVANT le cadre Caméra — son bouton
        d'en-tête est TOUJOURS packé (la combobox de source et
        Démarrer/Arrêter restent visibles en toutes circonstances) — :
        l'ordre général de la colonne ne bouge jamais. Thread UI seul
        (construction, _restaurer_config, _on_source_choisie).

        Jalon 98 (retour d'Alain, 06/10/2026) — DEUX défauts de la v2.51.1
        (jalon 95b) réparés ici :
        ① l'ancienne ancre était le LabelFrame « Fichiers de travail »,
        packé APRÈS son propre bouton d'en-tête : `pack(before=ancre)`
        insérait donc Cadence/Dossier ENTRE ce bouton et son contenu,
        coupant la section en deux (en-tête seul en haut, contenu orphelin
        sous « Dossier surveillé » — elle PARAISSAIT repliée) ; pire, si la
        section Fichiers était réellement repliée, l'ancre n'était plus
        gérée et Tk levait « TclError: window … isn't packed », ABORTANT
        tout le changement de source (pas de déconnexion caméra, pas de
        détection SDK, « Démarrer » non réactivé). L'ancre est désormais le
        bouton d'en-tête de Caméra, toujours géré — garde-fou : repli sur
        un pack simple s'il ne l'était plus.
        ② une section REPLIÉE par l'utilisateur (Cadence, Dossier ou
        Composition) réapparaissait avec son contenu au simple changement
        de source, avec sa flèche ▶ menteuse : l'état replié est maintenant
        RESPECTÉ (`lf._var_etat`, posé par _creer_section_pliable) — la
        visibilité de l'ENSEMBLE (bouton + contenu) suit la source, le pli
        reste un choix de l'utilisateur.

        Note jalon 95 : `_lf_*` pointe vers le LabelFrame externe (utilisé
        pour pack/before). `frm_*` est le contenu interne (compat widgets)."""
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
        visibles = ([self._lf_cadence, self._lf_dossier_surveille] if est_dossier else
                    [self._lf_cadence, self._lf_composition] if est_compo else [])
        # Ancre stable (jalon 98) : le bouton d'en-tête de Caméra — TOUJOURS
        # packé (la source et Démarrer/Arrêter restent visibles en toutes
        # circonstances, jalon 47). Les cadres de la source s'insèrent AVANT
        # lui : « Fichiers de travail » reste complet et, replié ou non, la
        # ligne suivante ne lève JAMAIS « TclError: isn't packed ».
        ancre = self._lf_camera._btn_header
        for cadre in (self._lf_cadence, self._lf_dossier_surveille, self._lf_composition):
            btn = getattr(cadre, "_btn_header", None)
            if cadre in visibles:
                # Afficher le bouton d'en-tête AVANT le LabelFrame
                # IMPORTANT : packer le bouton D'ABORD, puis le LF après (after=btn)
                if btn:
                    if ancre.winfo_manager():
                        btn.pack(fill="x", pady=(3, 0), before=ancre)
                    else:
                        btn.pack(fill="x", pady=(3, 0))
                # pack() replace le cadre (déjà géré ou non) à la même place
                # relative — appelé dans l'ordre canonique ci-dessus. Jalon 98 :
                # le contenu n'est re-packé que si la section est DÉPLIÉE —
                # une section repliée par l'utilisateur reste repliée (bouton
                # ▶ seul, sans contenu) au lieu de réapparaître dépliée.
                var_etat = getattr(cadre, "_var_etat", None)
                if var_etat is None or bool(var_etat.get()):
                    cadre.pack(fill="x", pady=(0, 3), after=btn if btn else ancre)
                elif cadre.winfo_manager():
                    cadre.pack_forget()
            elif cadre.winfo_manager() or (btn and btn.winfo_manager()):
                # Jalon 98bis : cacher l'EN-TÊTE même si le contenu est déjà
                # dépacké — une section REPLIÉE qui devient inutile à la
                # source gardait sinon son en-tête planté à son ancienne
                # position (winfo_manager() du porteur vide → branche jamais
                # prise), flottant au milieu de la colonne jusqu'au prochain
                # changement de source. Le constat d'Alain (« positionnement
                # bizarre des sections selon les zones cliquées »).
                if cadre.winfo_manager():
                    cadre.pack_forget()
                if btn:
                    btn.pack_forget()
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
                self._dire(
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
            self._dire(
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
        d = self._demander_dossier("Dossier où arrivent les brutes")
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
            self._signaler("Caméra", str(e))
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
        self._rendu_differ = None              # jalon 80 : aucun rendu en attente
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
        # Jalon 84 : le guet de gel s'arrête AVANT la destruction de la fenêtre
        # (il est démon, donc sans danger, mais un instrument de mesure doit se
        # taire quand ce qu'il surveille disparaît).
        guet = getattr(self, "guet", None)
        if guet is not None:
            guet.arreter()
        # v2.48.1 : ANNULER la replanification de `_tick` AVANT de détruire la
        # fenêtre. Sans cela, un rappel `after` déjà en file se déclenche sur
        # l'arbre détruit et lève « invalid command name .!… » (constat du
        # journal macOS) — au mieux une erreur de journal, au pire une
        # fermeture qui n'aboutit pas (l'application reste « ouverte » sans
        # fenêtre). `after_cancel` sur un identifiant déjà consommé est sans
        # effet, et l'échec éventuel est avalé : la fermeture ne doit JAMAIS
        # dépendre de ce nettoyage.
        tick_id = getattr(self, "_tick_id", None)
        if tick_id is not None:
            try:
                self.root.after_cancel(tick_id)
            except Exception:
                pass
            self._tick_id = None
        self.root.destroy()

    def _save(self):
        if not self.running or self.stacker is None or self.stacker.n == 0:
            self._dire("Enregistrer", "Aucun empilement à enregistrer.")
            return
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
        if path:
            self.save_request = path  # la sauvegarde est faite par le thread d'acquisition
            # Jalon 96 (étape 6) : PNG annoté COMPAGNON, écrit à côté (le FITS
            # linéaire, lui, part par le thread — deux fichiers indépendants).
            _png, _msg = self._sauver_png_annote(path)

    def _gx_live_prete(self, titre):
        """Contrôle AVANT toute sauvegarde pleine résolution : si le retrait de
        gradient live est actif et que sa commande est incomplète, la chaîne ne
        peut pas être reproduite — message clair et abandon (jamais de fichier
        « presque comme vu »). → True si l'on peut continuer."""
        if (self.disp.stretch == "veralux" and self.disp.vl_graxpert
                and not gx_live.commande_valide(self.disp.vl_graxpert_cmd)):
            self._avertir(
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
            # v2.48.0 (jalon 85) : force des deux outils et préservation de la
            # luminosité — la chaîne couleur suit l'étirement, donc le rendu
            # pleine résolution doit les recevoir pour rester identique à
            # l'écran (règle du projet : le fichier = l'écran).
            vl_scnr_force=float(d.vl_scnr_force),
            vl_demagenta_force=float(d.vl_demagenta_force),
            vl_preserve_luminance=bool(d.vl_preserve_luminance),
            # v2.48.0 (jalon 86) : boost du rouge (SII) masqué à l'objet — la
            # sauvegarde « tel que vu » doit être l'écran au pixel près.
            vl_boost_rouge=bool(d.vl_boost_rouge),
            vl_boost_force=float(d.vl_boost_force),
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
            self._dire("Enregistrer tel que vu",
                       "Un enregistrement est déjà en cours — patientez.")
            return
        if not self.running or self.stacker is None or self.stacker.n == 0:
            self._dire("Enregistrer tel que vu",
                       "Aucun empilement à enregistrer.")
            return
        vue = self.var_view.get()
        if vue == "traitée" and self.proc_full is None:
            self._dire(
                "Enregistrer tel que vu",
                "Aucun résultat traité — cliquez d'abord « ⚡ Traiter "
                "l'empilement courant ».")
            return
        if not self._gx_live_prete("tel que vu"):
            return
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"),
                       ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
        if not path:
            return
        self.asseen_titre = "Enregistrer tel que vu"
        # Jalon 96 (étape 6) : PNG annoté COMPAGNON, écrit à côté du FITS.
        _png, _msg = self._sauver_png_annote(path)
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
            self._dire(titre, "Un enregistrement est déjà en cours — "
                              "patientez.")
            return
        if not self.running or self.stacker is None or self.stacker.n == 0:
            self._dire(titre, "Aucun empilement à enregistrer.")
            return
        if not self._gx_live_prete(titre):
            return
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"),
                       ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
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
        couches = {role: np.asarray(couche, dtype=np.float32)
                   for role, couche in canaux.items()}
        # --- ① GRADIENT par couche, EN PARALLÈLE (jalon 81) : à l'export, TOUS
        # les appels sont à faire — c'est là que le gain est maximal (chaque
        # appel paie ~2,8 s fixes de démarrage + chargement du modèle de 217 Mo,
        # et les trois couches sont indépendantes : cf. `appliquer_lot`).
        if reglages.get("vl_graxpert"):
            a_lancer = []                    # (role, image)
            for role, c in couches.items():
                if float(np.max(np.abs(c))) < 1e-9:
                    msgs.append(f"GraXpert live ({role}) : couche vide — "
                                "ignorée")
                else:
                    a_lancer.append((role, c))
            if a_lancer:
                lot = gx_live.appliquer_lot(
                    [(role, c, reglages["vl_graxpert_cmd"])
                     for role, c in a_lancer])
                for role, _c in a_lancer:
                    c2, err = lot.get(role, (None, "appel non exécuté"))
                    if err or c2 is None:
                        msgs.append(f"GraXpert live ({role}) : "
                                    f"{err or 'aucun résultat'}")
                    else:
                        couches[role] = c2
        # --- ② DÉBRUITAGE par couche : même ordre qu'avant, inchangé.
        if reglages.get("vl_denoise"):
            for role, c in couches.items():
                c2, err = denoiser_local.denoiser(
                    c, reglages.get("vl_denoise_methode", "nlm"),
                    reglages.get("vl_denoise_force", 0.5))
                if err:
                    msgs.append(f"Débruitage live ({role}) : {err}")
                else:
                    couches[role] = c2
        traites = couches
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
            # v2.48.0 (jalon 85) : la chaîne couleur n'est PLUS appliquée ici.
            # Elle suit désormais l'ÉTIREMENT, donc elle vit dans
            # `rendu_pleine_resolution` (appelé plus bas), exactement comme à
            # l'écran — « le fichier correspond à l'écran » reste vrai.
            # CONSÉQUENCE VOULUE : la 3e sortie LINÉAIRE ci-dessous n'est plus
            # écrêtée en vert (elle était la SEULE à porter le SCNR des jalons
            # 22/23 — MESURÉ sur son empilement M31 : excès de vert max 5,9·10⁻⁸
            # contre 1,6·10⁻¹ sur l'empilement d'origine).
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
        p = self._demander_fichier(filetypes=[
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
                self._signaler("Dark", str(e))

    def _load_flat(self):
        # Jalon 53 : cible INDÉPENDANTE de celle des darks (ex. flat par
        # filtre et dark unique, ou l'inverse).
        cible = self._choisir_cible("flat")
        if cible is None:
            return
        p = self._demander_fichier(filetypes=[
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
                self._signaler("Flat", str(e))

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
        d = self._demander_dossier(
            "Dossier de travail (fichiers temporaires lourds)", depart)
        if not d:
            return
        CONFIG["dossier_travail"] = d
        sauver_config(dict(CONFIG))
        self._maj_travail_vue()
        libre = travail.espace_libre(d)
        self._dire(
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
            self._avertir("Dossier de travail",
                          f"Impossible d'ouvrir « {d} » :\n{err}")

    def _ouvrir_journal(self):
        """Ouvre le JOURNAL de l'application (v2.38.7) : démarrages, erreurs
        d'interface, échecs journalisés — c'est LE fichier à regarder (et à
        envoyer) quand quelque chose ne va pas, en particulier quand la fenêtre
        ne s'ouvre pas du tout."""
        chemin = journal.chemin_journal()
        err = journal.ouvrir()
        if err:                              # aucun outil associé : le dire
            self._avertir(
                "Journal",
                f"Impossible d'ouvrir le journal :\n{err}\n\nLe fichier est :\n"
                f"{chemin}")

    def _pick_exe(self, var):
        """Sélectionne l'exécutable d'un outil externe et le place en tête de
        la commande — les options déjà saisies ({input}, {output}…) sont
                conservées telles quelles."""
        p = self._demander_fichier(
            "Exécutable de l'outil",
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
            self._dire("Traitement externe", "Aucun empilement à traiter.")
            return
        if self.ext_busy:
            self._dire("Traitement externe",
                       "Un traitement est déjà en cours — patientez.")
            return
        if not (self.var_ext_graxpert.get() or self.var_ext_dn.get()
                or self.var_ext_bxt.get()
                or self.var_ext_neutre.get()            # v2.37.1
                or self.var_ext_chroma.get()):          # v2.37.1
            self._dire("Traitement externe",
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
            self._avertir(
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
                        # v2.48.0 (jalon 85) : la chaîne couleur
                        # (SCNR / SCNR doux / démagenta) N'EST PLUS dans ce job
                        # — elle suit l'étirement et est réglée par la section
                        # « Couleur de l'objet (après étirement) ». Le résultat
                        # ⚡ reste LINÉAIRE, non écrêté en vert.
                        # v2.37.1 : corrections PRÉ-ÉTIREMENT de la chaîne live
                        # (9e/10e éléments + la force en 11e) — déballage
                        # tolérant côté thread de traitement. La force est
                        # CAPTURÉE ici (curseur « Couleur live ») : le thread
                        # externe ne lit jamais une variable Tk.
                        self.var_ext_neutre.get(),
                        self.var_ext_chroma.get(),
                        float(self.disp.vl_chroma_force),
                        # v2.37.4 : RAYON DE RÉFÉRENCE du flou de chroma
                        # (12e élément), en pixels PLEINE RÉSOLUTION — la chaîne
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
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
        if path:
            try:
                # v2.27.1 : même garantie d'échelle que la sauvegarde de
                # l'empilement linéaire (un résultat d'outil externe peut
                # lui aussi dépasser 1 : le borner évite un fichier que les
                # lecteurs supposant [0,1] afficheraient « saturé »).
                img, entete = borner_lineaire(self.proc_full,
                                              dict(self.proc_entete or {}))
                save_image(path, img, entete=entete)
                # Jalon 96 (étape 6) : PNG annoté COMPAGNON, écrit à côté du
                # FITS (jamais dans le fichier : linéarité préservée).
                _png, _msg = self._sauver_png_annote(path)
                self._dire("Enregistrer", f"Résultat traité sauvegardé :\n{path}")
            except Exception as e:
                self._signaler("Enregistrer", str(e))

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
            # v2.48.0 (jalon 85) : la chaîne couleur (SCNR / SCNR doux /
            # démagenta) NE FAIT PLUS PARTIE DE CETTE CHAÎNE — elle suit
            # l'étirement, donc elle est appliquée par l'AFFICHAGE et par la
            # sauvegarde « tel que vu » (`display.couleur_apres_etirement`).
            # Le résultat ⚡ reste ainsi LINÉAIRE et non écrêté en vert :
            # réutilisable tel quel.
            # v2.37.1 : corrections pré-étirement de la chaîne LIVE (9e, 10e et
            # 11e éléments du job — déballage tolérant : les jobs antérieurs n'en
            # ont pas → inactives) : neutralisation du fond → réduction du bruit
            # chromatique, juste avant l'étirement d'affichage.
            nf_ext = bool(self.ext_job[8]) if len(self.ext_job) > 8 else False
            chroma_ext = bool(self.ext_job[9]) if len(self.ext_job) > 9 \
                else False
            force_chroma_ext = (float(self.ext_job[10])
                                if len(self.ext_job) > 10 else 0.5)
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma (12e élément —
            # déballage tolérant : les jobs antérieurs n'en ont pas → rayon de
            # référence, soit le comportement de la v2.37.3).
            rayon_chroma_ext = (float(self.ext_job[11])
                                if len(self.ext_job) > 11
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
            # v2.48.0 (jalon 85) : la chaîne couleur a QUITTÉ la chaîne externe
            # (elle suit l'étirement : `display.couleur_apres_etirement`,
            # appliquée à l'affichage du résultat et à « tel que vu ») — le
            # résultat ⚡ est donc LINÉAIRE et non écrêté en vert.
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
            # v2.48.0 (jalon 85) : plus de chaîne couleur ici (elle suit
            # l'étirement, cf. `display.couleur_apres_etirement`) — seules les
            # corrections PRÉ-étirement restent dans cette chaîne.
            nf_ext = bool(self.ext_job[8]) if len(self.ext_job) > 8 else False
            chroma_ext = bool(self.ext_job[9]) if len(self.ext_job) > 9 \
                else False
            force_chroma_ext = (float(self.ext_job[10])
                                if len(self.ext_job) > 10 else 0.5)
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma (12e élément —
            # déballage tolérant, comme la chaîne mono).
            rayon_chroma_ext = (float(self.ext_job[11])
                                if len(self.ext_job) > 11
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
            # v2.48.0 (jalon 85) : la chaîne couleur a QUITTÉ la chaîne externe
            # (composition comprise) — elle suit l'étirement et est appliquée à
            # l'affichage / « tel que vu » (`display.couleur_apres_etirement`).
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
        """Chaîne PAR COUCHE du traitement externe (jalon 24), avec le GRADIENT
        EN UN SEUL LOT (jalon 83) et le DÉBRUITAGE couche par couche.

        POURQUOI le lot POUR LE GRADIENT SEUL : les couches sont INDÉPENDANTES et
        chaque appel GraXpert paie un démarrage FIXE (~3,4 s, identiques sur
        iGPU, RTX 4070 et RTX 4060 Ti) — les lancer ensemble recouvre ces temps
        morts : **+57 à +60 % sur les trois machines**, sorties identiques AU BIT
        (banc `_test_gx_lot_externe_jalon83`). Le DÉBRUITAGE reste en SÉRIE : sur
        ces mêmes trois machines son lot ne rapporte rien (un appel sature déjà
        le GPU : −13 % sur iGPU, +12,9 % sur 4070, +1,2 % sur 4060 Ti) et il
        coûte 2,2 à 3,7 Go de VRAM par appel.

        → dict rôle → couche traitée, ou None (échec TOTAL du gradient, ou échec
        d'un subprocess de débruitage : message posé, chaîne arrêtée — même
        politique que la chaîne mono ; un échec PARTIEL du gradient conserve la
        couche brute, le signale, et la chaîne continue)."""
        traites = {}
        i_etape = 0
        couches = {role: np.asarray(couche, dtype=np.float32)
                   for role, couche in canaux.items()}
        # --- ① GRADIENT : UN SEUL LOT pour toutes les couches (jalon 83).
        # Validation du GABARIT et de l'exécutable AVANT tout lancement — mêmes
        # messages que la chaîne mono (leçon du jalon 24 : après substitution les
        # placeholders n'existent plus, on ne peut plus les vérifier).
        if use_gx:
            if ("{input}" not in cmd_gx
                    or ("{output}" not in cmd_gx
                        and "{outbase}" not in cmd_gx)):
                self._set_ext_msg("Commande GraXpert gradient incomplète : il "
                                  "manque {input} ou {output}/{outbase}.",
                                  state="error")
                return None
            manque = gx_live.outil_manquant(cmd_gx)
            if manque:
                self._set_ext_msg(
                    f"GraXpert gradient : {manque} — désignez l'exécutable avec "
                    "le bouton « … » du cadre « Traitement externe (long) ».",
                    state="error")
                return None
            a_lancer = []                    # (rôle, couche) à envoyer à l'outil
            for role, c in couches.items():
                if float(np.max(np.abs(c))) < 1e-9:
                    msgs.append(f"GraXpert ({role}) : couche vide — ignorée")
                else:
                    a_lancer.append((role, c))
            if a_lancer:
                i_etape += len(a_lancer)
                self._set_ext_msg(
                    f"GraXpert gradient : {len(a_lancer)} couche(s) en "
                    f"parallèle… ({n_frames} frames)", state="busy")
                lot = gx_live.appliquer_lot(
                    [(role, c, cmd_gx) for role, c in a_lancer])
                echecs = 0
                for role, _c in a_lancer:
                    c2, err = lot.get(role, (None, "appel non exécuté"))
                    if err or c2 is None:
                        echecs += 1
                        msgs.append(f"GraXpert ({role}) : "
                                    f"{err or 'aucun résultat'}")
                    else:
                        couches[role] = c2.astype(np.float32)
                if echecs == len(a_lancer):
                    # ÉCHEC TOTAL : on ARRÊTE et on le dit — continuer
                    # produirait une image « traitée » qui ne l'est pas.
                    self._set_ext_msg(
                        "Erreur GraXpert gradient : "
                        + (msgs[-1] if msgs else "aucun résultat"),
                        state="error")
                    return None
        # --- ② DÉBRUITAGE par couche : SÉRIE (mesuré : le lot n'apporte rien).
        # L'entrée du subprocess est la couche APRÈS gradient, écrite ici dans le
        # dossier de la chaîne (le gradient travaille, lui, dans le sien).
        for role, c in list(couches.items()):
            if use_dn:
                if mode_dn == "graxpert":
                    src = os.path.join(tmp, f"dn_in_{role}.fits")
                    gx_live._ecrire_entree(src, c)
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
        # Détecter la transition "non résolu → résolu" pour réinitialiser la proposition
        precedent = getattr(self, "_astro_was_resolved", False)
        maintenant = self.suivi_astro.resolu
        if maintenant and not precedent:
            # Nouvelle résolution : on réinitialise le flag pour permettre une nouvelle popup
            self._astro_name_proposed = False
        self._astro_was_resolved = maintenant
        
        if maintenant:
            self.astro_couleur = "#1d7f1d"
            # Gestion du nom de cible à chaque résolution (pas seulement la première)
            if not self._astro_name_proposed:
                # Objets célèbres DÉDUPLIQUÉS trouvés par l'astrométrie
                # (SANS la priorité manuel ni le fallback FITS)
                objets = self._objets_celestes_resolus()
                current = self.var_nom_cible_manual.get().strip()
                auto_nom = (self._sanitize_nom(objets[0].designation)
                            if objets else None)
                if self.var_debug.get():
                    journal.note("DEBUG", f"auto_nom(astro)={auto_nom!r} "
                                 f"n_objets={len(objets) if objets else 0} "
                                 f"current={current!r} proposed={self._astro_name_proposed}")
                if auto_nom:
                    if not current:
                        # Champ vide → on adopte le meilleur nom de l'astrométrie
                        if self.var_debug.get():
                            journal.note("DEBUG", "Champ vide → adoption auto_nom")
                        self.var_nom_cible_manual.set(auto_nom)
                    elif current != auto_nom:
                        # Nom différent → popup avec radio-boutons : tous les
                        # objets trouvés + « garder l'actuel »
                        if self.var_debug.get():
                            journal.note("DEBUG", "Nom différent → popup radio-boutons")
                        try:
                            choix = self._demander_nom_cible(objets, current)
                            if choix:
                                self.var_nom_cible_manual.set(choix)
                                if self.var_debug.get():
                                    journal.note("DEBUG", f"Utilisateur a choisi « {choix} »")
                            else:
                                if self.var_debug.get():
                                    journal.note("DEBUG", "Utilisateur a refusé le remplacement")
                        except Exception as e:
                            if self.var_debug.get():
                                journal.note("DEBUG", f"Exception popup: {e}")
                self._astro_name_proposed = True

    def _demander_nom_cible(self, objets, current: str) -> str | None:
        """Dialogue « Nom de cible détecté » : radio-boutons listant les objets
        célèbres trouvés par l'astrométrie (meilleur présélectionné) + l'option
        « garder l'actuel » quand le champ est déjà rempli. Retourne le nom
        choisi, l'actuel si gardé, ou None (annulé)."""
        import tkinter as tk

        def libelle(o) -> str:
            nom = self._sanitize_nom(o.designation)
            bouts = [nom, o.type_obj]
            if o.mag_v is not None:
                bouts.append(f"mag {o.mag_v:.1f}".replace(".", ","))
            if o.size_arcmin:
                bouts.append(f"{o.size_arcmin:.0f}′")
            return " — ".join(bouts)

        noms = [libelle(o) for o in objets[:6]]
        # Valeur par défaut : le meilleur objet, sauf si l'utilisateur garde l'actuel
        garder = bool(current)
        choix_initial = libelle(objets[0]) if not garder else current
        var = tk.StringVar(value=choix_initial)

        dlg = tk.Toplevel(self.root)
        dlg.title("Nom de cible détecté")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        tk.Label(dlg, text="L'astrométrie a résolu le champ. Choisissez le nom "
                           "de la cible :", justify="left").pack(
            anchor="w", padx=12, pady=(12, 6))

        cadre = tk.Frame(dlg)
        cadre.pack(fill="both", expand=True, padx=12)
        for nom_lib in noms:
            tk.Radiobutton(cadre, text=nom_lib, value=nom_lib,
                           variable=var, justify="left").pack(anchor="w")
        if garder:
            tk.Radiobutton(cadre, text=f"Garder « {current} »",
                           value=current, variable=var,
                           justify="left").pack(anchor="w")

        resultat = {"nom": None}

        def valider():
            resultat["nom"] = var.get()
            dlg.destroy()

        boutons = tk.Frame(dlg)
        boutons.pack(fill="x", padx=12, pady=(6, 12))
        tk.Button(boutons, text="OK", width=8, command=valider).pack(side="right")
        tk.Button(boutons, text="Annuler", width=8,
                  command=dlg.destroy).pack(side="right", padx=(0, 6))

        dlg.wait_window()
        nom = resultat["nom"]
        # « Garder l'actuel » choisi → retourner l'actuel (pas de changement)
        if garder and nom == current:
            return current
        return nom

    # -------------------------------- jalon 56 (étape 4) : photométrie
    def _mettre_a_jour_nom_depuis_fits(self):
        """Si le champ « Nom cible » est vide, tente de le remplir depuis
        l'en-tête FITS de la dernière brute (camera.last_file).
        Appelée seulement quand camera.last_file change (nouvelle brute)."""
        if self.var_nom_cible_manual.get().strip():
            return  # l'utilisateur a déjà saisi un nom
        chemin = getattr(self.camera, "last_file", "") or ""
        if not chemin:
            return
        try:
            nom = astro_mod.nom_objet_entete_fits(chemin)
            if self.var_debug.get():
                journal.note("DEBUG", f"FITS nom_objet_entete_fits={nom!r} chemin={chemin!r}")
            if nom:
                self.var_nom_cible_manual.set(self._sanitize_nom(nom))
                if self.var_debug.get():
                    journal.note("DEBUG", f"Nom mis à jour depuis FITS -> {self.var_nom_cible_manual.get()!r}")
        except Exception as e:
            if self.var_debug.get():
                journal.note("DEBUG", f"Exception lecture FITS: {e}")
            pass

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
        # v2.48.0 (jalon 85) : la chaîne couleur (SCNR / SCNR doux / démagenta)
        # NE FAIT PLUS PARTIE de la chaîne externe — elle suit l'étirement et
        # est appliquée à l'affichage comme à « tel que vu »
        # (`display.couleur_apres_etirement`). Le fichier ⚡ ne porte donc que
        # les corrections PRÉ-étirement, ce que dit AVAAPPLI.
        for actif, nom in ((val(8), "fond neutre"), (val(9), "chroma")):
            if actif:
                preet.append(nom)
        if val(9):
            preet.append("chroma force %.2f rayon %.1fpx"
                         % (float(val(10, 0.5)), float(val(11, 3.0))))
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
        self._dire(
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

    # Jalon 106a : la boucle du thread d'acquisition (`_worker`) vit
    # désormais dans `avastack/core/worker.py` (mixin `AcquisitionWorker`,
    # dont `App` hérite — méthode reprise VERBATIM). Jalon 106b : la partie
    # « boucle » (acquisition + reset / re-stack) est découpée en sous-méthodes
    # (`_worker_empiler_frame`, `_worker_reinitialiser`, `_worker_restack`).
    # Jalon 106c : la partie « pilotage » est découpée à son tour
    # (`_worker_pilotage`, `_worker_cadence_dossier`). Le jalon 106d découpera
    # « mesures ».

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
    def _planifier_tick(self, delai=30):
        """Replanifie la boucle d'interface en MÉMORISANT l'identifiant `after`
        (v2.48.1).

        Deux raisons, toutes deux mesurées sur le retour macOS du 30/09/2026 :
        ① `_on_close` peut ANNULER ce rappel avant `root.destroy()` — sinon un
        `after` en attente se déclenche sur un arbre de widgets détruit et lève
        « invalid command name .!… » ; ② une fenêtre DÉJÀ détruite (fermeture en
        cours) n'a plus rien à replanifier — l'erreur est simplement ignorée."""
        try:
            self._tick_id = self.root.after(delai, self._tick)
        except tk.TclError:
            self._tick_id = None            # fenêtre détruite : rien à faire

    @staticmethod
    def _widget_vivant(w):
        """True si `w` est un widget Tk encore VALIDE (v2.48.1).

        `winfo exists` est la SEULE interrogation qui ne lève pas sur un widget
        détruit (elle rend 0) : c'est ce qui permet aux rafraîchissements
        d'interface de se TAISIR au lieu d'échouer quand un widget a disparu
        (constat macOS : « invalid command name .!… »)."""
        if w is None:
            return False
        try:
            return bool(w.winfo_exists())
        except tk.TclError:
            return False

    def _tick(self):
        """Boucle d'interface : rafraîchissements + consommation des files.

        v2.48.1 (retour macOS du 30/09/2026) : le CORPS est protégé et la
        REPLANIFICATION est faite dans un `finally`. Avant, `_tick` se
        replanifiait en DERNIÈRE ligne : la moindre exception (un widget détruit
        pendant une boîte de dialogue native macOS, « invalid command name
        .!… ») tuait la boucle POUR DE BON et l'interface restait GELÉE — c'est
        exactement ce que montrait le journal du testeur. Désormais une erreur
        est ÉCRITE au journal (une fois par épisode, jamais 33 fois par seconde)
        et la boucle CONTINUE : un rafraîchissement raté n'est plus un gel."""
        try:
            self._tick_corps()
            self._tick_err_sig = None          # épisode clos
        except tk.TclError:
            self._journal_erreur_tick("boucle d'interface (widget détruit ?)")
        except Exception:
            self._journal_erreur_tick("boucle d'interface")
        finally:
            self._planifier_tick(30)

    def _journal_erreur_tick(self, titre):
        """Écrit l'erreur de la boucle d'interface UNE fois par épisode.

        Un widget durablement détruit ferait 33 exceptions par seconde : sans
        ce garde-fou, le journal deviendrait illisible et masquerait la CAUSE.
        """
        sig = traceback.format_exc()
        if sig == self._tick_err_sig:
            return
        self._tick_err_sig = sig
        journal.erreur(titre)

    def _tick_corps(self):
        # Jalon 84 : BATTEMENT pour le guet de gel — la PREUVE que le fil
        # d'interface rend la main (deux affectations, aucun coût mesurable).
        guet = getattr(self, "guet", None)
        if guet is not None:
            guet.battement()
        # Mise à jour automatique du nom de cible depuis l'en-tête FITS
        # Seulement si camera.last_file a changé (nouvelle brute reçue)
        chemin = getattr(self.camera, "last_file", "") or ""
        if chemin != self._dernier_last_file:
            self._dernier_last_file = chemin
            self._mettre_a_jour_nom_depuis_fits()
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
            quoi = msg[-1] if len(msg) >= 3 and msg[-1] in ("spectres", "spcc", "celebres") \
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
                if quoi == "celebres":
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
                    return
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
                    # JALON 80 (demande d'Alain, 29/09/2026) : EN RAFALE DE
                    # DOSSIER ce déclenchement tombait sur la PREMIÈRE brute —
                    # une passe ENTIÈRE de la chaîne lourde (GraXpert live par
                    # couche, ~10 s chez lui) calculée sur une pile à 1 brute,
                    # puis une SECONDE passe sur la pile de fin de rafale : le
                    # panneau restait occupé ~70 % du temps, dont une passe
                    # entière perdue. Le rendu est donc DIFFÉRÉ à la fin de la
                    # rafale (aucun empilement nouveau pendant `RAFALE_QUIET_S`,
                    # contrôle ci-dessous), avec une BORNE (`RAFALE_MAX` brutes
                    # empilées depuis le dernier rendu) pour qu'un dossier
                    # pré-rempli ne le retarde jamais indéfiniment. Les sources
                    # NON-dossier (caméras, webcam, simulée) ne changent pas :
                    # leur file ne s'accumule pas et le rythme des frames y est
                    # déjà le cooldown.
                    if not self._cadence_dossier():
                        self._vl_frames = st["frames"]
                        self._rendu_differ = None
                        self.disp.notify_new_stack()
                    # `_vl_frames` peut être None (aucun rendu encore dans cette
                    # session) : la borne compte alors depuis le début de session.
                    elif (self._rendu_differ is None
                          or st["frames"] - (self._vl_frames or 0)
                          < self.RAFALE_MAX):
                        self._rendu_differ = st["frames"]    # dernier gagnant
                        self._rendu_differ_t = time.perf_counter()
                    else:
                        self._vl_frames = st["frames"]       # borne atteinte
                        self._rendu_differ = None
                        self.disp.notify_new_stack()
                self._update_status(st)
                if self.var_view.get() == "pile":     # la vue traitée garde son instantané
                    self.last_show = show
                    self._rendre_et_afficher(show)
        except queue.Empty:
            pass
        # Jalon 80 : la rafale s'est TUE (plus aucun empilement depuis
        # `RAFALE_QUIET_S`) → le rendu différé part MAINTENANT, une seule fois,
        # sur la pile la plus PROFONDE. Ce contrôle est ICI (et pas seulement à
        # la réception d'un empilement) pour qu'un rendu différé ne puisse
        # JAMAIS être perdu : la dernière brute de la rafale peut être suivie
        # d'un long silence (fenêtre de cadence, scan) sans nouveau message.
        if (self._rendu_differ is not None
                and time.perf_counter() - self._rendu_differ_t
                >= self.RAFALE_QUIET_S):
            self._vl_frames = self._rendu_differ
            self._rendu_differ = None
            self.disp.notify_new_stack()
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
            # v2.48.3 (jalon 95, retour macOS du 01/10/2026) : la zone
            # « Traitement externe » peut disparaître sur Tcl/Tk 8.6.12 / macOS
            # (invalid command name sur btn_ext.config) — la garde suivante
            # TAIT toute la zone (3 widgets : btn_save_proc, lbl_ext, btn_ext)
            # et laisse `_tick` se replanifier normalement. _maj_libelle_fit
            # l'avait déjà, posée au jalon 87 ; cette zone avait été oubliée
            # (cf. CLAUDE.md « leçon du jalon 95 »).
            if not self._widget_vivant(getattr(self, "btn_save_proc", None)):
                return
            self.btn_save_proc.config(state="normal")
            if self.var_view.get() == "traitée" and self.proc_show is not None:
                self.last_show = self.proc_show
                self._show_image(self.disp.process(
                    self._src_rendu(self.proc_show), live=False))
        if self.ext_msg != self._ext_shown:
            self._ext_shown = self.ext_msg
            if not self._widget_vivant(getattr(self, "lbl_ext", None)):
                return
            self.lbl_ext.config(
                text=self.ext_msg,
                foreground={"busy": "#c98a00", "ok": "#1d7f1d",
                            "error": "#d04040"}.get(self.ext_state, "#888888"))
        if self.ext_busy:                      # chrono pendant le traitement
            if not self._widget_vivant(getattr(self, "lbl_ext", None)):
                return
            self.lbl_ext.config(text=f"{self.ext_msg}  "
                                      f"({time.time() - (self.ext_t0 or time.time()):.0f} s)")
        if not self._widget_vivant(getattr(self, "btn_ext", None)):
            return
        self.btn_ext.config(state="disabled"
                            if (self.ext_busy or self.ext_request) else "normal")
        if self._ext_popup:
            self._ext_popup = False
            self._signaler("Traitement externe", self.ext_msg)
        if self.saved_path:
            p, self.saved_path = self.saved_path, None
            if p.startswith("ERREUR"):
                self._signaler("Enregistrer", p)
            elif os.path.isdir(p):
                self._dire("Enregistrer",
                           f"Canaux sauvegardés dans :\n{p}")
            else:
                corr = self.dernier_applicatif
                self.dernier_applicatif = None
                self._dire(
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
                self._signaler(titre, p)
            else:
                self._dire(
                    titre, f"Image sauvegardée :\n{p}"
                    + (f"\n\nCorrections écrites dans le fichier (AVAAPPLI) :"
                       f"\n{corr}" if corr else "")
                    + (f"\n\nOutils : {outils}" if outils else ""))
        # v2.48.1 : la replanification de la boucle est faite par `_tick`, dans
        # un `finally` — elle ne doit PAS être répétée ici (sinon la boucle
        # serait planifiée DEUX fois, et le travail doublerait à chaque tour).

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
        disp_src = self._last_disp
        if disp_src is None:
            return
        # v2.55.3 : l'échelle d'affichage est calculée AVANT l'annotation —
        # les étiquettes gardent une TAILLE À L'ÉCRAN constante quel que soit
        # le buffer (aperçu 1600 px OU rendu pleine résolution) : à pleine
        # résolution elles étaient dessinées à ~11 px DANS le buffer (6000 px)
        # puis réduites à ~2 px à l'écran, illisibles (constat d'Alain).
        # Jamais < 1 (le zoom avant ne rapetisse pas les textes) ; plafonnée
        # à 12 pour un canvas minuscule.
        ih, iw = disp_src.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        fit = min(cw / iw, ch / ih)                    # échelle « ajuster »
        scale = fit * self.zoom
        echelle_police = min(12.0, max(1.0, 1.0 / max(scale, 1e-9)))
        self._echelle_police_annot = echelle_police
        # Jalon 96 (étape 5) : annotation temps-réel — overlay dessiné sur une
        # COPIE du buffer, UNIQUE point de passage (tous les rendus : nouvelle
        # image, réglage, zoom). `_last_disp` reste PROPRE : le PNG compagnon
        # repart de la version sans annotation.
        disp = self._annoter_image(disp_src, echelle_police)
        ih, iw = disp.shape[:2]
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


def activer_fenetre(root):
    """macOS : met la fenêtre AU PREMIER PLAN et lui donne le focus (jalon 84).

    POURQUOI (retour RÉEL d'un testeur sous macOS 27 « Golden Gate »,
    30/09/2026 : « les boutons ne sont pas toujours cliquables, mais qui le
    deviennent après que j'ai cliqué frénétiquement dessus ») : une application
    Tk lancée par un lanceur ou depuis un terminal n'est pas « activée » par
    macOS à l'ouverture ; sa fenêtre peut rester DERRIÈRE, et les premiers clics
    servent alors à activer l'application au lieu d'atteindre le widget — d'où
    l'impression qu'il faut insister. `lift` + `-topmost` bref + `focus_force`
    est la séquence qui force cette activation. Elle n'est faite QUE sur macOS :
    ailleurs, `focus_force` volerait le focus à ce que fait l'utilisateur, ce
    que l'application n'a jamais fait. → True si l'activation a été tentée.
    (Le pendant pour les boîtes de dialogue est le `parent=` des aides
    `_dire`/`_signaler`/`_demander_*` de `App`.)"""
    if not IS_MACOS:
        return False
    try:
        root.lift()
        root.attributes("-topmost", True)
        root.focus_force()
        # `-topmost` retiré aussitôt : la fenêtre passe devant au moment de
        # l'ouverture, puis redevient une fenêtre ordinaire (elle n'écrase pas
        # celles que l'utilisateur ouvre ensuite).
        root.after(250, lambda: root.attributes("-topmost", False))
    except Exception:
        return False
    return True


def main():
    """Point d'entrée : ouvre la fenêtre principale.

    v2.38.7 : `report_callback_exception` est remplacé par le journal — une
    erreur dans un rappel d'interface (clic, curseur, touche) était écrite sur
    `stderr` et nulle part ailleurs, donc invisible pour une application
    lancée par le menu (constat d'Alain, 27/09/2026).

    Jalon 84 : la version de Tcl/Tk est JOURNALISÉE (le retour macOS 27 a
    relancé la piste d'un Tk trop ancien : elle doit être lisible dans le
    journal sans avoir à la demander à l'utilisateur), et la fenêtre est mise
    au premier plan sur macOS (`activer_fenetre`)."""
    root = tk.Tk()
    ressources.poser_icone_fenetre(root)   # barre de titres + barre des tâches
    root.report_callback_exception = journal.rapport_callback
    try:
        journal.note("démarrage",
                     "Tcl/Tk %s" % root.tk.call("info", "patchlevel"))
    except Exception:
        pass
    App(root)
    activer_fenetre(root)
    root.mainloop()


