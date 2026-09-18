# -*- coding: utf-8 -*-
"""Fenêtre principale AVAStack (Tkinter) : interface, thread d'acquisition,
orchestration calibration → alignement → empilement → affichage, et traitement
externe sur instantané."""

import os
import time
import queue
import shutil
import tempfile
import threading

import numpy as np
import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from ..compat import IS_WINDOWS
from ..config import CONFIG, sauver_config
from ..images import (CFA_MODE, lire_filtre_fits, load_image, save_image,
                      find_output, auto_unflip)
from ..cameras import (SOURCES, SimulatedCamera, OpenCVCamera, ZWOASICamera,
                       FolderCamera, MultiFolderCamera, QHYCamera,
                       PlayerOneCamera, TouptekCamera, SVBonyCamera)
from ..processing import Calibrator, StarAligner, LiveStacker, DisplayProcessor
from ..processing import alignment as align_mod
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
from ..processing import stars as seeing_live
from ..processing import sharpness as nettete_live
from ..external import live as gx_live
from ..processing import veralux as veralux_moteur
from ..external.detection import (
    DEFAULT_CMD_GRAXPERT, DEFAULT_CMD_GRAXPERT_DN, DEFAULT_CMD_BXT,
    commande_avec_strength, commande_par_defaut_graxpert,
    commande_par_defaut_graxpert_dn, commande_par_defaut_bxt)


class App:
    W_IMG, H_IMG, W_HIST, H_HIST = 840, 560, 840, 110

    # Débruitage live (jalon 9, remis le 16/09/2026) : libellés UI ↔ codes
    # internes (module avastack/processing/denoise.py, algorithmes locaux
    # sans IA). NLM en premier = défaut (tests réels d'Alain : plus homogène
    # que les ondelettes). Le débruitage GraXpert IA reste en TRAITEMENT
    # EXTERNE (plusieurs minutes par image — jamais en live).
    VL_DN_METHODES = (("nlm", "Non-local means"),
                      ("ondelettes", "Ondelettes à trous"))
    VL_DN_LABELS = dict(VL_DN_METHODES)    # code → libellé (restauration)
    VL_DN_CODES = {lib: code for code, lib in VL_DN_METHODES}

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
        root.title("AVAStack — live stacking (empilement temps réel)")
        root.geometry("1300x820")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.camera = self.thread = None
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
        self.reset_request = self.ref_request = False
        self.save_request = self.saved_path = None
        self.save_canaux_request = None  # jalon 19 : dossier des canaux (compo)
        self.bad_frames = 0
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
        self._compo_mode_l = "synthetise"
        self.archives = {}              # rôle → ArchiveFrames (mode compo)
        # Jalon 16 : re-stack sur la meilleure référence — score qualité
        # (nb d'étoiles) parallèle à archive.chemins, ancre courante, et
        # déclencheurs (auto : marge en étoiles ; manuel : bouton).
        self._scores = []            # score par frame archivée (même ordre)
        self.restack_request = False # bouton « ⟳ Re-stacker (meilleure brute) »
        self._ref_score = None       # score de la référence courante
        self._ancre_idx = None       # index d'archive de la brute servant d'ancre
        self._ancre_score = None     # son score
        self._restack_depuis = 0     # frames archivées depuis le dernier re-stack
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
        self._drag = None              # point de départ du glisser-déplacer

        # --- traitement externe (instantané de l'empilement)
        self.ext_request = False        # demande en attente (lue par le worker)
        self.ext_busy = False           # un traitement externe tourne
        self.ext_job = None             # (gx?, cmd_gx, dn?, cmd_dn, bxt?,
                                        # cmd_bxt, mode_dn, force_dn)
                                        # dn = débruitage : GraXpert IA
                                        # (subprocess) OU ondelettes/nlm
                                        # (local, en mémoire)
        self.proc_show = None           # aperçu traité (réduit, pour affichage)
        self.proc_full = None           # résultat traité pleine résolution (sauvegarde)
        self.proc_new = False           # un nouveau résultat vient d'arriver
        self.save_asseen_request = None  # (chemin, vue, réglages) — jalon 5, capté côté UI
        self.asseen_busy = False        # sauvegarde « tel que vu » en cours (thread dédié)
        self.asseen_result = None       # chemin ou "ERREUR: …" — écrit par le thread, lu par _tick
        self.ext_msg = "—"              # message d'état (écrit par le thread, lu par _tick)
        self._ext_shown = None
        self.ext_state = "idle"         # idle | busy | ok | error
        self.ext_t0 = None              # début du traitement en cours (chrono)
        self._ext_popup = False        # erreur à signaler par popup

        self._build_ui()
        self._restaurer_config()
        self.root.after(30, self._tick)

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
        self._on_compo_roles()   # composition recollée aux rôles restaurés
        if c.get("process_existing") is False:
            self.var_process_existing.set(False)
        # Traitement externe : ne pas écraser une commande persistée par un
        # défaut re-détecté qui aurait changé ; si la commande au démarrage
        # était un chemin (détection) devenu inexistant, re-détecter.
        for cle, var in (("cmd_graxpert", self.var_cmd_graxpert),
                         ("cmd_graxpert_dn", self.var_cmd_graxpert_dn),
                         ("cmd_bxt", self.var_cmd_bxt)):
            enreg = c.get(cle)
            if enreg:
                var.set(enreg)
            else:
                # commande détectée automatiquement → vérifier que l'exe existe
                premier = var.get().strip().split('"')[1] \
                    if var.get().strip().startswith('"') else None
                if premier and not os.path.isfile(premier):
                    var.set(commande_par_defaut_graxpert()
                            if cle == "cmd_graxpert" else
                            commande_par_defaut_graxpert_dn()
                            if cle == "cmd_graxpert_dn" else
                            commande_par_defaut_bxt())
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
        for cle, var, mini, maxi in (
                ("sigk", self.var_sigk, 0.5, 5.0),
                ("target", self.var_target, 0.10, 0.45),
                ("gamma", self.var_gamma, 0.2, 4.0),
                ("saturation", self.var_saturation, 0.0, 3.0)):
            v = c.get(cle)
            if isinstance(v, (int, float)) and mini <= v <= maxi:
                var.set(float(v))
        self.disp.sigma_k = self.var_sigk.get()
        self.disp.target = self.var_target.get()
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
        self._on_rejeter_flou()
        self._on_wb()
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
        self._maj_lbl_sharp()        # étiquette juste dès le démarrage
        # Moteur d'étirement en DERNIER : la bascule VeraLux masque les
        # réglages STF et affiche le cadre VeraLux avec les valeurs ci-dessus.
        # (moteur indisponible → STF conservé, sans popup)
        if c.get("moteur") == "VeraLux" and veralux_moteur.moteur_disponible():
            self.var_moteur.set("VeraLux")
            self._on_moteur()

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
        c["process_existing"] = self.var_process_existing.get()
        # Les commandes ne sont persistées que si utilisées au moins une fois
        # ou modifiées par l'utilisateur — sinon on laisse la détection se
        # rejouer au prochain lancement (installation déplacée, etc.).
        if self.var_cmd_graxpert.get().strip():
            c["cmd_graxpert"] = self.var_cmd_graxpert.get().strip()
        if self.var_cmd_graxpert_dn.get().strip():
            c["cmd_graxpert_dn"] = self.var_cmd_graxpert_dn.get().strip()
        if self.var_cmd_bxt.get().strip():
            c["cmd_bxt"] = self.var_cmd_bxt.get().strip()
        if self.var_ext_graxpert.get():
            c["ext_graxpert"] = True
        if self.var_ext_dn.get():
            c["ext_dn"] = True
        c["dn_methode"] = self.DN_EXT_CODES.get(self.var_dn_methode.get(),
                                                "graxpert")
        c["dn_force"] = self.var_dn_force.get()   # force débruitage externe
        if self.var_ext_bxt.get():
            c["ext_bxt"] = True
        c["sigk"] = self.var_sigk.get()
        c["target"] = self.var_target.get()
        c["gamma"] = self.var_gamma.get()
        c["saturation"] = self.var_saturation.get()
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

        # --- Caméra
        box = ttk.LabelFrame(left, text="Caméra", padding=6)
        box.pack(fill="x", pady=3)
        self.var_source = tk.StringVar(value=SOURCES[0])
        ttk.Combobox(box, textvariable=self.var_source, values=SOURCES,
                     state="readonly", width=28).pack(fill="x", pady=2)
        rowbtn = ttk.Frame(box)
        rowbtn.pack(fill="x", pady=1)
        self.btn_start = ttk.Button(rowbtn, text="▶ Démarrer", command=self._start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=1)
        self.btn_stop = ttk.Button(rowbtn, text="■ Arrêter", command=self._stop,
                                   state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=1)
        self.var_expo = tk.DoubleVar(value=100.0)
        self.var_gain = tk.DoubleVar(value=1.0)
        self._add_slider(box, "Exposition (ms)", self.var_expo, 5, 1000, 5,
                         self._push_settings, "{:.0f}")
        self._add_slider(box, "Gain", self.var_gain, 0.5, 8.0, 0.1,
                         self._push_settings, "{:.1f}")

        # --- Dossier surveillé
        box = ttk.LabelFrame(left, text="Dossier surveillé", padding=6)
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
        self.lbl_last = ttk.Label(box, text="Dernier fichier : —")
        self.lbl_last.pack(anchor="w")

        # --- Composition multi-filtres (jalon 19) : 1 à 4 dossiers surveillés,
        # un RÔLE (filtre) par dossier ; le composite temps réel combine les
        # empilements par rôle selon la composition choisie.
        box = ttk.LabelFrame(left, text="Composition multi-filtres", padding=6)
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
        self._on_compo()    # pré-remplit les lignes de rôle de la compo par défaut

        # --- Calibration
        box = ttk.LabelFrame(left, text="Calibration", padding=6)
        box.pack(fill="x", pady=3)
        ttk.Button(box, text="Charger un dark…", command=self._load_dark).pack(fill="x", pady=1)
        ttk.Button(box, text="Charger un flat…", command=self._load_flat).pack(fill="x", pady=1)
        ttk.Button(box, text="Effacer calibration",
                   command=self._clear_calib).pack(fill="x", pady=1)
        self.lbl_dark = ttk.Label(box, text="Dark : —", foreground="#888888")
        self.lbl_dark.pack(anchor="w")
        self.lbl_flat = ttk.Label(box, text="Flat : —", foreground="#888888")
        self.lbl_flat.pack(anchor="w")

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
        ttk.Button(rowf, text="Réinitialiser l'empilement",
                   command=lambda: setattr(self, "reset_request", True)
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
        self.lbl_restack = ttk.Label(row_rs, text="Re-stack : —",
                                     foreground="#888888")
        self.lbl_restack.pack(side="left", fill="x", expand=True)
        ttk.Button(row_rs, text="ⓘ", width=3,
                   command=self._montrer_restack_hist).pack(side="left",
                                                            padx=(4, 0))
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
                         lambda: (setattr(self.disp, "target", self.var_target.get()),
                                  self._refresh_preview()), "{:.2f}")
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
        self.frm_communs = ttk.Frame(box)
        self.frm_communs.pack(fill="x")
        vg = tk.DoubleVar(value=1.0)
        self.var_gamma = vg
        self._add_slider(self.frm_communs, "Gamma (les 2 moteurs)", vg, 0.2, 4.0, 0.05,
                         lambda: (setattr(self.disp, "gamma", vg.get()),
                                  self._refresh_preview()), "{:.2f}")
        vs = tk.DoubleVar(value=1.0)
        self.var_saturation = vs
        self._add_slider(self.frm_communs, "Saturation", vs, 0.0, 3.0, 0.05,
                         lambda: (setattr(self.disp, "saturation", vs.get()),
                                  self._refresh_preview()), "{:.2f}")

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
                         lambda: (setattr(self.disp, "vl_target_bg",
                                          self.var_vl_target.get()),
                                  self._refresh_preview()), "{:.2f}")
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
        self.lbl_vl = ttk.Label(self.frm_veralux, text="—",
                                foreground="#888888", wraplength=310)
        self.lbl_vl.pack(anchor="w")
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

        # --- Traitement externe (instantané de l'empilement)
        box = ttk.LabelFrame(left, text="Traitement externe (instantané)", padding=6)
        box.pack(fill="x", pady=3)
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
        self.cv_hist = tk.Canvas(right, width=self.W_HIST, height=self.H_HIST,
                                 bg="#101010", highlightthickness=0)
        self.cv_hist.pack(fill="x")
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

    def _add_slider(self, parent, label, var, frm, to, res, onchange=None, fmt="{:g}"):
        """Curseur + étiquette de valeur + boutons « - »/« + » (demande
        d'Alain, jalon 6) : réglage FIN sans devoir viser à la souris.
        Un clic = ±1 pas (res), aligné sur la grille du curseur ; clic
        MAINTENU = répétition (400 ms puis toutes les 80 ms) pour parcourir
        une grande plage sans cliquer 200 fois. Clamps aux bornes frm/to."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        head = ttk.Frame(row)
        head.pack(fill="x")
        ttk.Label(head, text=label).pack(side="left")
        lab_val = ttk.Label(head, text=fmt.format(var.get()))
        lab_val.pack(side="right")

        def cmd(v):
            var.set(float(v))
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
        self._refresh_preview()

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
            self.lbl_vl.config(text="Calcul en cours…", foreground="#c98a00")
        else:
            self.frm_veralux.pack_forget()
            self.frm_stf.pack(fill="x", after=self.rowm)  # position d'origine
            self.lbl_vl.config(text="—", foreground="#888888")
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
        si la commande GraXpert n'est pas utilisable (placeholders)."""
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
            self.disp.vl_graxpert_cmd = cmd
            self.lbl_vl.config(text="GraXpert live activé — calcul en cours…",
                               foreground="#c98a00")
        self._sync_vl_graxpert_vue()
        if actif and self.var_view.get() == "traitée":
            self.lbl_vl.config(
                text="Vue « traitée » : GraXpert live ignoré — l'image a déjà "
                     "été traitée (il s'appliquera en vue « empilement »).",
                foreground="#c98a00")
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

    def _on_view(self):
        """Bascule empilement ↔ résultat traité (stats d'étirement réinitialisées :
        les niveaux après GraXpert/BXT ne sont pas les mêmes)."""
        self.disp.reset()
        self._sync_vl_graxpert_vue()
        self._sync_vl_denoise_vue()
        self._sync_vl_sharp_vue()
        self._maj_lbl_sharp()
        if self.var_view.get() == "traitée":
            if self.proc_show is not None:
                self.last_show = self.proc_show
                self._show_image(self.disp.process(self.last_show, live=False))
            else:
                self._set_ext_msg("Aucun résultat traité — cliquez « ⚡ Traiter » d'abord.")
        else:
            if self.show_stack is not None:
                self.last_show = self.show_stack
                self._show_image(self.disp.process(self.last_show, live=False))

    def _refresh_preview(self):
        """Re-rend l'aperçu immédiatement après un réglage (indispensable en mode
        dossier : pas de frame régulière pour rafraîchir l'écran).
        live=False : ne fait pas avancer le lissage temporel des stats."""
        if self.last_show is not None:
            self._show_image(self.disp.process(self.last_show, live=False))

    def _push_settings(self):
        if self.camera is not None:
            self.pending_settings = (self.var_expo.get(), self.var_gain.get())

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
            return QHYCamera()
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
        if self.running:
            return
        try:
            cam = self._make_camera(self.var_source.get())
            if isinstance(cam, MultiFolderCamera) and \
                    composition_pour_roles(cam.roles) is None:
                raise RuntimeError(
                    "Rôles de dossiers sans composition connue : "
                    + ", ".join(cam.roles))
            cam.open()
            cam.apply_settings(self.var_expo.get(), self.var_gain.get())
        except Exception as e:
            messagebox.showerror("Caméra", str(e))
            return
        self.camera = cam
        # Jalon 19 : mode composition si la source est multi-dossiers — la
        # composition est déduite des rôles configurés (choix UI en phase 3).
        self._mode_compo = isinstance(cam, MultiFolderCamera)
        self._compo_nom = (composition_pour_roles(cam.roles)
                           if self._mode_compo else None)
        # Jalon 19 phase 3 : gains + radio « Canal L » instantanés POUR LE
        # THREAD (le worker n'a jamais le droit de lire les variables Tk).
        self._compo_gains = self._lire_gains()
        self._compo_mode_l = self.var_compo_mode_l.get()
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
        self._restack_depuis = 0
        self.restack_info = ""            # jalon 18 : état dédié de session neuve
        self.restack_couleur = "#888888"
        self.restack_total = 0
        self.restack_hist = []
        self.proc_show = self.proc_full = None
        self.proc_new = False
        self.save_asseen_request = None       # sauvegarde « tel que vu » annulée
        self.asseen_busy = False
        self.asseen_result = None
        self.ext_request = False
        self.ext_busy = False
        self.ext_state = "idle"
        self.ext_t0 = None
        self._ext_popup = False
        self.btn_save_proc.config(state="disabled")
        self.zoom, self.view_cx, self.view_cy = 1.0, None, None
        self._last_disp = None
        self.q = queue.Queue(maxsize=2)
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

    def _stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
            self.thread = None
        if self.camera:
            self.camera.close()
            self.camera = None
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="Arrêté.")

    def _on_close(self):
        self._sauver_config_app()
        self._stop()
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
        if (self.disp.stretch == "veralux" and self.disp.vl_graxpert
                and not gx_live.commande_valide(self.disp.vl_graxpert_cmd)):
            messagebox.showwarning(
                "GraXpert live",
                "Commande GraXpert absente ou incomplète — impossible de "
                "reproduire la chaîne live.\nVérifiez la commande dans "
                "« Traitement externe ».")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"),
                       ("PNG 16 bits", "*.png")])
        if not path:
            return
        # Capture des réglages ICI (thread principal) : le thread de
        # sauvegarde ne lira jamais les variables Tkinter, et l'état de disp
        # (curseurs, solveur) continue de vivre pendant le rendu.
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
            vl_sharp=d.vl_sharp, vl_sharp_iterations=d.vl_sharp_iterations)
        self.save_asseen_request = (path, vue, reglages)

    def _save_asseen_thread(self, path, vue, source, reglages, session):
        """Thread de sauvegarde « tel que vu » (jalon 5) : GraXpert live si
        activé (vue « empilement » uniquement), puis débruitage/netteté live,
        puis rendu pleine résolution identique à l'affichage, puis écriture du
        fichier. AUCUN appel Tk ici : le résultat est consommé par _tick
        (messagebox thread-safe)."""
        try:
            if vue == "pile" and reglages.get("vl_graxpert"):
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
            if vue == "pile" and reglages.get("vl_denoise"):
                img_dn, err = denoiser_local.denoiser(
                    source, reglages.get("vl_denoise_methode", "nlm"),
                    reglages.get("vl_denoise_force", 0.5))
                if err:
                    self.asseen_result = f"ERREUR: Débruitage live : {err}"
                    return
                source = img_dn
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
            rendu = self.disp.rendu_pleine_resolution(source, reglages)
            if session != self._session:    # session relancée entre-temps
                return
            save_image(path, rendu)
            self.asseen_result = path
        except Exception as e:
            self.asseen_result = f"ERREUR: {e}"
        finally:
            self.asseen_busy = False

    def _load_dark(self):
        p = filedialog.askopenfilename(filetypes=[
            ("Images", "*.fits *.fit *.fts *.png *.tif *.tiff *.jpg *.jpeg"), ("Tous", "*.*")])
        if p:
            try:
                self.calib.load_dark(p)
                h, w = self.calib.dark.shape[:2]
                self.lbl_dark.config(text=f"Dark : {os.path.basename(p)}  ({h}×{w})",
                                     foreground="#1d7f1d")
                msg = f"Dark chargé : {p}"
                if self.running:
                    msg += "  —  pensez à « Réinitialiser l'empilement » pour que tout soit calibré pareil"
                self.lbl_status.config(text=msg)
            except Exception as e:
                messagebox.showerror("Dark", str(e))

    def _load_flat(self):
        p = filedialog.askopenfilename(filetypes=[
            ("Images", "*.fits *.fit *.fts *.png *.tif *.tiff *.jpg *.jpeg"), ("Tous", "*.*")])
        if p:
            try:
                self.calib.load_flat(p)
                h, w = self.calib.flat.shape[:2]
                self.lbl_flat.config(text=f"Flat : {os.path.basename(p)}  ({h}×{w})",
                                     foreground="#1d7f1d")
                msg = f"Flat chargé : {p}"
                if self.running:
                    msg += "  —  pensez à « Réinitialiser l'empilement » pour que tout soit calibré pareil"
                self.lbl_status.config(text=msg)
            except Exception as e:
                messagebox.showerror("Flat", str(e))

    def _clear_calib(self):
        self.calib.clear()
        self.lbl_dark.config(text="Dark : —", foreground="#888888")
        self.lbl_flat.config(text="Flat : —", foreground="#888888")

    # ------------------------------------------------------------ traitement externe
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
                or self.var_ext_bxt.get()):
            messagebox.showinfo("Traitement externe",
                                "Cochez au moins un traitement.")
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
                        self.var_dn_force.get())
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
                save_image(path, self.proc_full)
                messagebox.showinfo("Enregistrer", f"Résultat traité sauvegardé :\n{path}")
            except Exception as e:
                messagebox.showerror("Enregistrer", str(e))

    def _run_external(self, stack, n_frames, session):
        """Chaîne les outils externes (GraXpert → BlurXTerminator) sur un
        instantané de l'empilement. Tourne en thread séparé : l'acquisition
        continue pendant ce temps. Le résultat n'affecte QUE l'affichage (vue
        « traitée ») et la sauvegarde dédiée — l'empilement accumulé reste
        linéaire et intact.

        Placeholders des commandes :
          {input}   → fichier FITS d'entrée (instantané de l'empilement, float 32F)
          {output}  → chemin de sortie complet, extension .fits
          {outbase} → chemin de sortie SANS extension (GraXpert : -output)
        Le fichier réellement produit est retrouvé automatiquement (_find_output),
        quelle que soit son extension ou son suffixe (-bxt, _GraXpert…), et un
        éventuel miroir vertical est corrigé (_auto_unflip)."""
        tmp = None
        try:
            (use_gx, cmd_gx, use_dn, cmd_dn, use_bxt, cmd_bxt,
             mode_dn, force_dn) = self.ext_job
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
            tmp = tempfile.mkdtemp(prefix="avastack_")
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
            if session != self._session:             # session relancée entre-temps
                return
            self.proc_full = img                     # pleine résolution (sauvegarde)
            h, w = img.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                img = cv2.resize(img, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            self.proc_show = img                     # version allégée (affichage)
            self.proc_new = True
            self._set_ext_msg(f"Traité à {time.strftime('%H:%M:%S')} "
                              f"({n_frames} frames)", state="ok")
        except Exception as e:
            self._set_ext_msg(f"Erreur : {e}", state="error")
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
            if session == self._session:
                self.ext_busy = False

    # ----------------------- jalon 17 : filtre anti-brutes défocalisées
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
        for arch in self.archives.values():
            arch.vider()

    def _meilleure_archive(self):
        """→ (idx, chemin, score) de la meilleure brute archivée, ou
        (None, None, None) si l'archive est vide ou incohérente."""
        if not self._scores or len(self._scores) != len(self.archive.chemins):
            return None, None, None
        idx = int(np.argmax(self._scores))
        return idx, self.archive.chemins[idx], int(self._scores[idx])

    def _veut_restack(self):
        """Déclencheur AUTO (esprit Siril) : la meilleure brute archivée bat
        nettement la référence courante (marge RESTACK_MARGE en étoiles).
        Surtout utile quand l'ANCRE initiale était médiocre ; une fois la
        référence rafraîchie sur l'EMPILEMENT (qui détecte plus d'étoiles
        qu'une brute isolée), la marge n'est presque plus atteinte —
        comportement voulu, le re-stack auto reste exceptionnel."""
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
        self._definir_reference(ref)
        st = LiveStacker(ancien.shape, k=ancien.k, method=ancien.method,
                         window=ancien.window)
        st.wb_auto = ancien.wb_auto
        st.wb_force = ancien.wb_force
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
    def _worker(self):
        last_good = None
        while self.running:
            t0 = time.perf_counter()

            if self.pending_settings is not None:
                self.camera.apply_settings(*self.pending_settings)
                self.pending_settings = None

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
            if (self.save_asseen_request is not None and self.stacker is not None
                    and self.stacker.n > 0 and not self.asseen_busy):
                path, vue, reglages = self.save_asseen_request
                self.save_asseen_request = None
                if vue == "traitée" and self.proc_full is None:
                    self.asseen_result = ("ERREUR: aucun résultat traité à "
                                          "enregistrer")
                else:
                    if vue == "traitée":
                        # copie défensive : proc_full peut être remplacé
                        source = self.proc_full.astype(np.float32).copy()
                    else:
                        source = self.stacker.mean()  # pleine résolution, linéaire
                    self.asseen_busy = True
                    threading.Thread(
                        target=self._save_asseen_thread,
                        args=(path, vue, source, reglages, self._session),
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
                    save_image(path, self.stacker.mean())
                    self.saved_path = path
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
                        save_image(os.path.join(
                            d_canaux, f"canal_{role}.fit"), carte)
                    self.saved_path = d_canaux
                except Exception as e:
                    self.saved_path = f"ERREUR: {e}"

            lu = self.camera.read()
            if lu is None:
                time.sleep(0.005)
                continue
            # Jalon 19 : source « composition » → read() renvoie (img, rôle).
            if self._mode_compo:
                frame, role = lu
            else:
                frame, role = lu, None
            frame = self.calib.apply(frame)

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
            if self._mode_compo:          # archive PAR RÔLE (futur re-stack v2)
                chemin_archive = self.archives.setdefault(
                    role, ArchiveFrames()).ajouter(frame)
            else:
                chemin_archive = self.archive.ajouter(frame)
            if chemin_archive is not None and not self._mode_compo:
                # Jalon 16 : score qualité (nb d'étoiles détectées, canal
                # vert) de chaque brute archivée — matière du choix de
                # référence à la Siril (meilleure référence + re-stack).
                # (Mode compo : re-stack DÉSACTIVÉ — reporté v2.)
                self._scores.append(self._score_frame(frame))
                self._restack_depuis += 1

            # (re)création de l'empilement / nouvelle référence — SEULEMENT
            # si la frame a passé le filtre jalon 17 (une brute très floue ne
            # doit jamais devenir la référence d'alignement ni créer
            # l'empilement — c'est le défaut que le filtre élimine).
            if (self.reset_request or self.stacker is None
                    or self.stacker.shape != img_travail.shape):
                self.reset_request = False
                if self._mode_compo:       # façade multi-rôles : un stacker
                    self.stacker = CompositeStacker(   # par rôle, mean() =
                        self._compo_nom,   # composite (cadre commun)
                        k=self.kappa, method=self.rejet_methode,
                        window=self.rejet_fenetre)
                    # Jalon 19 phase 3 : gains + canal L posés dès la
                    # création (instantanés tenus à jour par _tick).
                    self.stacker.gains = dict(self._compo_gains or {})
                    self.stacker.mode_l = self._compo_mode_l
                else:
                    self.stacker = LiveStacker(img_travail.shape, k=self.kappa,
                                               method=self.rejet_methode,
                                               window=self.rejet_fenetre)
                self.stacker.wb_auto = bool(self.var_wb.get())
                self.stacker.wb_force = float(self.var_wb_force.get())
                self.aligner.reset()
                self._definir_reference(img_travail)
                self.disp.reset()          # stats d'affichage repartent de zéro

            M, ok = self.aligner.compute(img_travail)
            if ok:
                aligned = cv2.warpAffine(img_travail, M,
                                         (img_travail.shape[1],
                                          img_travail.shape[0]),
                                         flags=cv2.INTER_LINEAR)
                if self._mode_compo:       # routage vers le stacker du rôle
                    self.stacker.role_courant = role
                self.stacker.add(aligned)
                self.stacker.note_alignement(M)   # intersection des zones couvertes
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
            # Jalon 19 : re-stack DÉSACTIVÉ en mode compo (reporté v2 —
            # l'archive par rôle est en place pour l'accueillir).
            if (not self._mode_compo and self.stacker is not None and (
                    self.restack_request
                    or (self.archive.n >= RESTACK_MIN_FRAMES
                        and self._restack_depuis >= RESTACK_CADENCE
                        and self._veut_restack()))):
                raison = "bouton" if self.restack_request else "auto"
                self.restack_request = False
                info = self._do_restack(raison)
                if info:
                    self.align_info = info
                    stack = self.stacker.mean()   # affichage immédiat

            show = stack if stack is not None else (last_good if last_good is not None else frame)

            # Aperçu allégé pour l'UI : réactif même en 16 Mpx ; l'étirement est
            # recalculé côté interface → curseurs réactifs entre deux frames.
            h, w = show.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                show = cv2.resize(show, None, fx=scale, fy=scale,
                                  interpolation=cv2.INTER_AREA)
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
            hist = self._compute_hist(show)

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
            st = dict(frames=self.stacker.n, rejets=self.stacker.rejected_total,
                      bad=self.bad_frames, floues=self.floues_rejetees,
                      fps=self.fps, cam=self.camera.name,
                      file=getattr(self.camera, "last_file", ""),
                      pending=pend,
                      failed=getattr(self.camera, "failed", 0),
                      align=self.align_info,
                      seeing=self.seeing, seeing_msg=self.seeing_msg,
                      archive=n_arch, archive_err=err_arch,
                      compo=(self.stacker.etat()
                             if self._mode_compo and self.stacker is not None
                             else None),
                      restack=self.restack_info, restack_n=self.restack_total)
            if self.stacker.cadre is not None:      # recadrage d'intersection
                y0, x0, y1, x1 = self.stacker.cadre
                st["crop_w"], st["crop_h"] = x1 - x0, y1 - y0
            try:
                self.q.put_nowait((show, hist, st))
            except queue.Full:
                pass
            time.sleep(max(0.0, 1.0 / 20.0 - (time.perf_counter() - t0)))

    @staticmethod
    def _compute_hist(img):
        hi = float(np.percentile(img, 99.9)) * 1.15 + 1e-6
        chans = [img] if img.ndim == 2 else [img[..., i] for i in range(3)]
        return [np.histogram(c, bins=256, range=(0.0, hi))[0].astype(np.float64) for c in chans]

    # ------------------------------------------------------------ rafraîchissement UI
    def _tick(self):
        # Jalon 19 : réglages de composition (gains R/G/B, radio « Canal L »)
        # lus CÔTÉ THREAD PRINCIPAL (variables Tk interdites dans le worker,
        # cf. piège) et poussés vers la façade si modifiés → appliqués au
        # composite dès la prochaine frame, sans redémarrer la session.
        gains = self._lire_gains()
        mode_l = self.var_compo_mode_l.get()
        if gains != self._compo_gains or mode_l != self._compo_mode_l:
            self._compo_gains = gains
            self._compo_mode_l = mode_l
        try:
            while True:
                show, hist, st = self.q.get_nowait()
                self.show_stack = show
                if st["frames"] != self._vl_frames:
                    # Jalon 3 : un NOUVEL empilement vient d'être produit —
                    # le solveur VeraLux relance la résolution (le rythme des
                    # frames est le cooldown ; aucun calcul entre deux frames,
                    # et le solveur ne garde que le DERNIER empilement).
                    self._vl_frames = st["frames"]
                    self.disp.notify_new_stack()
                self._update_status(st)
                self._draw_hist(hist)
                if self.var_view.get() == "pile":     # la vue traitée garde son instantané
                    self.last_show = show
                    self._show_image(self.disp.process(show))
        except queue.Empty:
            pass
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
        self._sync_vl_sharp_vue()
        if self.disp.sh_new:      # netteté live : message du solveur (jalon 12)
            self.disp.sh_new = False
            self._maj_lbl_sharp()
        if self.disp.vl_new:      # résultat du solveur VeraLux (thread dédié)
            self.disp.vl_new = False
            if self.var_moteur.get() == "VeraLux":
                self._refresh_preview()
                if self.disp.vl_error:
                    self.lbl_vl.config(text=self.disp.vl_error,
                                       foreground="#d04040")
                elif self.disp.vl_diagnostics is not None:
                    d = self.disp.vl_diagnostics
                    prefixe = ("GX ✓ · " if self.disp.vl_graxpert else "") \
                        + ("DN ✓ · " if self.disp.vl_denoise else "") \
                        + ("NET ✓ · " if self.disp.vl_sharp else "")
                    self.lbl_vl.config(
                        text=f"{prefixe}logD {self.disp.vl_log_d_resolu:.2f} · "
                             f"fond {d['median_luminance_finale']:.3f}",
                        foreground="#1d7f1d")
        if self.proc_new:
            self.proc_new = False
            self.btn_save_proc.config(state="normal")
            if self.var_view.get() == "traitée" and self.proc_show is not None:
                self.last_show = self.proc_show
                self._show_image(self.disp.process(self.proc_show, live=False))
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
                messagebox.showinfo("Enregistrer", f"Empilement sauvegardé :\n{p}")
        # Jalon 5 : état de la sauvegarde « tel que vu » (thread dédié)
        self.btn_save_asseen.config(
            state="disabled"
            if (self.asseen_busy or self.save_asseen_request is not None)
            else "normal")
        if self.asseen_result:
            p, self.asseen_result = self.asseen_result, None
            if p.startswith("ERREUR"):
                messagebox.showerror("Enregistrer tel que vu", p)
            else:
                messagebox.showinfo("Enregistrer tel que vu",
                                    f"Image « tel que vu » sauvegardée :\n{p}")
        self.root.after(30, self._tick)

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
            self.cv_img.create_text(8, 8, anchor="nw", fill="#ffd75e",
                                    text=f"zoom ×{self.zoom:.1f}   (double-clic : ajuster)")

    def _draw_hist(self, chans):
        self.cv_hist.delete("all")
        w = self.cv_hist.winfo_width() or self.W_HIST
        h = self.cv_hist.winfo_height() or self.H_HIST
        colors = ["#ff5555", "#55ff55", "#5599ff"] if len(chans) == 3 else ["#bbbbbb"]
        mx = max(float(c.max()) for c in chans) or 1.0
        for arr, col in zip(chans, colors):
            pts = []
            for i in range(256):
                v = float(np.log1p(arr[i]) / np.log1p(mx))
                pts += [i / 255.0 * w, h - v * (h - 4) - 2]
            self.cv_hist.create_line(*pts, fill=col, width=1)

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
    """Point d'entrée : ouvre la fenêtre principale."""
    root = tk.Tk()
    App(root)
    root.mainloop()


