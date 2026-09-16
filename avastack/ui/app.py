# -*- coding: utf-8 -*-
"""Fenêtre principale AVAStack (Tkinter) : interface, thread d'acquisition,
orchestration calibration → alignement → empilement → affichage, et traitement
externe sur instantané."""

import os
import time
import queue
import shutil
import subprocess
import tempfile
import threading

import numpy as np
import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from ..compat import IS_WINDOWS
from ..config import CONFIG, sauver_config
from ..images import CFA_MODE, load_image, save_image, find_output, auto_unflip
from ..cameras import (SOURCES, SimulatedCamera, OpenCVCamera, ZWOASICamera,
                       FolderCamera, QHYCamera, PlayerOneCamera,
                       TouptekCamera, SVBonyCamera)
from ..processing import Calibrator, StarAligner, LiveStacker, DisplayProcessor
from ..external import live as gx_live
from ..processing import veralux as veralux_moteur
from ..external.detection import (
    DEFAULT_CMD_GRAXPERT, DEFAULT_CMD_BXT,
    commande_par_defaut_graxpert, commande_par_defaut_bxt)


class App:
    W_IMG, H_IMG, W_HIST, H_HIST = 840, 560, 840, 110

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
        self.bad_frames = 0
        self.fps = 0.0
        self.show_stack = None       # dernier aperçu linéaire de l'empilement
        self.last_show = None       # image linéaire actuellement affichée
        self._session = 0           # anti-mélange entre sessions

        # --- état du zoom / pan (affichage)
        self.zoom = 1.0                # 1.0 = image ajustée à la fenêtre
        self.view_cx = self.view_cy = None   # centre de vue (coords image), None = centre
        self._last_disp = None         # dernière image déjà étirée (pour re-rendu)
        self._drag = None              # point de départ du glisser-déplacer

        # --- traitement externe (instantané de l'empilement)
        self.ext_request = False        # demande en attente (lue par le worker)
        self.ext_busy = False           # un traitement externe tourne
        self.ext_job = None             # (graxpert?, cmd_gx, bxt?, cmd_bxt)
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
        if c.get("process_existing") is False:
            self.var_process_existing.set(False)
        # Traitement externe : ne pas écraser une commande persistée par un
        # défaut re-détecté qui aurait changé ; si la commande au démarrage
        # était un chemin (détection) devenu inexistant, re-détecter.
        for cle, var in (("cmd_graxpert", self.var_cmd_graxpert),
                         ("cmd_bxt", self.var_cmd_bxt)):
            enreg = c.get(cle)
            if enreg:
                var.set(enreg)
            else:
                # commande détectée automatiquement → vérifier que l'exe existe
                premier = var.get().strip().split('"')[1] \
                    if var.get().strip().startswith('"') else None
                if premier and not os.path.isfile(premier):
                    var.set(commande_par_defaut_graxpert() if cle == "cmd_graxpert"
                            else commande_par_defaut_bxt())
        if c.get("ext_graxpert"):
            self.var_ext_graxpert.set(True)
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
        c["process_existing"] = self.var_process_existing.get()
        # Les commandes ne sont persistées que si utilisées au moins une fois
        # ou modifiées par l'utilisateur — sinon on laisse la détection se
        # rejouer au prochain lancement (installation déplacée, etc.).
        if self.var_cmd_graxpert.get().strip():
            c["cmd_graxpert"] = self.var_cmd_graxpert.get().strip()
        if self.var_cmd_bxt.get().strip():
            c["cmd_bxt"] = self.var_cmd_bxt.get().strip()
        if self.var_ext_graxpert.get():
            c["ext_graxpert"] = True
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
        c["moteur"] = self.var_moteur.get()
        c["vl_mode_res"] = self.var_vl_mode_res.get()
        c["vl_target"] = self.var_vl_target.get()
        c["vl_logd"] = self.var_vl_logd.get()
        c["vl_profil"] = self.var_vl_profil.get()
        c["vl_graxpert"] = bool(self.var_vl_graxpert.get())
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
        self.lbl_stats = ttk.Label(box, text="Frames : 0\nPixels rejetés (σ) : 0\nFrames non alignées : 0")
        self.lbl_stats.pack(anchor="w", pady=(0, 3))
        rowf = ttk.Frame(box)
        rowf.pack(fill="x", pady=2)
        ttk.Button(rowf, text="Réinitialiser l'empilement",
                   command=lambda: setattr(self, "reset_request", True)
                   ).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(rowf, text="Réf. = empilement",
                   command=lambda: setattr(self, "ref_request", True)
                   ).pack(side="left", expand=True, fill="x", padx=1)
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
        self.var_ext_bxt = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="2. BlurXTerminator — netteté",
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
                           "l'exécutable, options conservées.",
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

    def _on_view(self):
        """Bascule empilement ↔ résultat traité (stats d'étirement réinitialisées :
        les niveaux après GraXpert/BXT ne sont pas les mêmes)."""
        self.disp.reset()
        self._sync_vl_graxpert_vue()
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

    def _make_camera(self, key):
        if key.startswith("Simulée"):
            return SimulatedCamera()
        if key.startswith("Dossier"):
            folder = self.var_folder.get().strip()
            if not folder:
                raise RuntimeError("Choisissez d'abord le dossier à surveiller (bouton …)")
            return FolderCamera(folder, process_existing=self.var_process_existing.get())
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

    def _pick_folder(self):
        d = filedialog.askdirectory(title="Dossier où arrivent les brutes")
        if d:
            self.var_folder.set(d)

    def _start(self):
        if self.running:
            return
        try:
            cam = self._make_camera(self.var_source.get())
            cam.open()
            cam.apply_settings(self.var_expo.get(), self.var_gain.get())
        except Exception as e:
            messagebox.showerror("Caméra", str(e))
            return
        self.camera = cam
        self.aligner = StarAligner()
        self.stacker = None
        self.disp.reset()                      # stats d'affichage repartent de zéro
        self._vl_frames = None                 # le 1er empilement relancera le solveur
        self.bad_frames, self.fps = 0, 0.0
        self.show_stack = None
        self.last_show = None
        self._session += 1                     # invalide tout traitement externe en vol
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
        l'image a déjà subi le traitement externe) → étirement STF/manuel ou
        VeraLux → gamma/saturation. Le bouton d'enregistrement LINÉAIRE
        reste inchangé. Le rendu (plusieurs secondes possibles) part dans un
        thread dédié via _worker — comme un traitement externe."""
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
            vl_graxpert=d.vl_graxpert, vl_graxpert_cmd=d.vl_graxpert_cmd)
        self.save_asseen_request = (path, vue, reglages)

    def _save_asseen_thread(self, path, vue, source, reglages, session):
        """Thread de sauvegarde « tel que vu » (jalon 5) : GraXpert live si
        activé (vue « empilement » uniquement), puis rendu pleine résolution
        identique à l'affichage, puis écriture du fichier. AUCUN appel Tk
        ici : le résultat est consommé par _tick (messagebox thread-safe)."""
        try:
            if vue == "pile" and reglages.get("vl_graxpert"):
                gx, err = gx_live.appliquer(source, reglages["vl_graxpert_cmd"])
                if err:
                    # On ne sauvegarde PAS une image « presque comme vue » :
                    # échec GraXpert = échec de la sauvegarde (message clair).
                    self.asseen_result = f"ERREUR: GraXpert live : {err}"
                    return
                source = gx
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
        if not (self.var_ext_graxpert.get() or self.var_ext_bxt.get()):
            messagebox.showinfo("Traitement externe",
                                "Cochez au moins GraXpert ou BlurXTerminator.")
            return
        # Capture des réglages ici (thread principal) : le thread externe ne
        # touchera pas aux variables Tkinter.
        self.ext_job = (self.var_ext_graxpert.get(),
                        self.var_cmd_graxpert.get().strip(),
                        self.var_ext_bxt.get(),
                        self.var_cmd_bxt.get().strip())
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
            use_gx, cmd_gx, use_bxt, cmd_bxt = self.ext_job
            steps = []
            if use_gx:
                steps.append(("GraXpert", cmd_gx))
            if use_bxt:
                steps.append(("BlurXTerminator", cmd_bxt))
            for name, cmd in steps:
                if "{input}" not in cmd or ("{output}" not in cmd and "{outbase}" not in cmd):
                    self._set_ext_msg(f"Commande {name} incomplète : il manque "
                                      "{{input}} ou {output}/{outbase}.", state="error")
                    return
            tmp = tempfile.mkdtemp(prefix="avastack_")
            cur = os.path.join(tmp, "stack.fits")
            save_image(cur, stack)

            def run_step(name, cmd_tpl, src, outbase):
                cmd = (cmd_tpl.replace("{input}", src)
                              .replace("{output}", outbase + ".fits")
                              .replace("{outbase}", outbase))
                self._set_ext_msg(f"{name} en cours… ({n_frames} frames)", state="busy")
                r = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=1800)
                if r.returncode != 0:
                    lines = (r.stderr or r.stdout or "").strip().splitlines()
                    detail = lines[-1] if lines else "aucun message"
                    self._set_ext_msg(f"Erreur {name} (code {r.returncode}) : {detail}",
                                      state="error")
                    return None
                res = find_output(src, outbase)      # extension/suffixe quelconques
                if res is None:
                    self._set_ext_msg(f"Erreur {name} : fichier de sortie introuvable "
                                      "(l'outil n'a rien écrit)", state="error")
                    return None
                return res

            for i, (name, cmd_tpl) in enumerate(steps):
                outbase = os.path.join(tmp, f"step{i}")
                res = run_step(name, cmd_tpl, cur, outbase)
                if res is None:
                    return
                cur = res

            img = load_image(cur)
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

            frame = self.camera.read()
            if frame is None:
                time.sleep(0.005)
                continue
            frame = self.calib.apply(frame)

            # (re)création de l'empilement / nouvelle référence
            if self.reset_request or self.stacker is None or self.stacker.shape != frame.shape:
                self.reset_request = False
                self.stacker = LiveStacker(frame.shape, k=self.kappa,
                                           method=self.rejet_methode,
                                           window=self.rejet_fenetre)
                self.aligner.reset()
                self.aligner.set_reference(frame)
                self.disp.reset()          # stats d'affichage repartent de zéro

            M, ok = self.aligner.compute(frame)
            if ok:
                aligned = cv2.warpAffine(frame, M, (frame.shape[1], frame.shape[0]),
                                         flags=cv2.INTER_LINEAR)
                self.stacker.add(aligned)
                last_good = aligned
            else:
                self.bad_frames += 1

            stack = self.stacker.mean()

            if self.ref_request and stack is not None:
                self.ref_request = False
                self.aligner.set_reference(stack)   # utile en longue session (rotation de champ)

            show = stack if stack is not None else (last_good if last_good is not None else frame)

            # Aperçu allégé pour l'UI : réactif même en 16 Mpx ; l'étirement est
            # recalculé côté interface → curseurs réactifs entre deux frames.
            h, w = show.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                show = cv2.resize(show, None, fx=scale, fy=scale,
                                  interpolation=cv2.INTER_AREA)
            hist = self._compute_hist(show)

            dt = time.perf_counter() - t0
            inst = 1.0 / max(dt, 1e-4)
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
            st = dict(frames=self.stacker.n, rejets=self.stacker.rejected_total,
                      bad=self.bad_frames, fps=self.fps, cam=self.camera.name,
                      file=getattr(self.camera, "last_file", ""),
                      pending=len(getattr(self.camera, "_pending", [])),
                      failed=getattr(self.camera, "failed", 0))
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
        # Jalon 5 : GraXpert live = vue « empilement » uniquement (synchro
        # permanente : la case peut être cochée même en vue « traitée »)
        self._sync_vl_graxpert_vue()
        if self.disp.vl_new:      # résultat du solveur VeraLux (thread dédié)
            self.disp.vl_new = False
            if self.var_moteur.get() == "VeraLux":
                self._refresh_preview()
                if self.disp.vl_error:
                    self.lbl_vl.config(text=self.disp.vl_error,
                                       foreground="#d04040")
                elif self.disp.vl_diagnostics is not None:
                    d = self.disp.vl_diagnostics
                    prefixe = "GX ✓ · " if self.disp.vl_graxpert else ""
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
        self.lbl_stats.config(text=(f"Frames : {st['frames']}\n"
                                    f"Pixels rejetés (σ) : {st['rejets']}\n"
                                    f"Frames non alignées : {st['bad']}"))
        extra = ""
        if st.get("pending"):
            extra += f"   |  en attente : {st['pending']}"
        if st.get("failed"):
            extra += f"   |  illisibles : {st['failed']}"
        self.lbl_last.config(text="Dernier fichier : "
                             f"{os.path.basename(st.get('file', '')) or '—'}{extra}")
        self.lbl_status.config(
            text=f"{st['cam']}  |  {st['fps']:.1f} fps  |  "
                 f"{st['frames']} frames empilées (intégration cumulée)")


def main():
    """Point d'entrée : ouvre la fenêtre principale."""
    root = tk.Tk()
    App(root)
    root.mainloop()


