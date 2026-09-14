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
        self.kappa = 3.0
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

        # --- Affichage
        box = ttk.LabelFrame(left, text="Affichage (temps réel)", padding=6)
        box.pack(fill="x", pady=3)
        # Moteur d'étirement : STF intégré (défaut, inchangé) ou VeraLux
        # (moteur tiers, opt-in). Le calcul VeraLux part dans un thread
        # dédié côté DisplayProcessor : l'interface n'est jamais bloquée.
        rowm = ttk.Frame(box)
        rowm.pack(fill="x", pady=(0, 2))
        ttk.Label(rowm, text="Moteur d'étirement :").pack(side="left")
        self.var_moteur = tk.StringVar(value="STF")
        self.cb_moteur = ttk.Combobox(rowm, textvariable=self.var_moteur,
                                      state="readonly", width=9,
                                      values=["STF", "VeraLux"])
        self.cb_moteur.pack(side="left", padx=4)
        self.cb_moteur.bind("<<ComboboxSelected>>", lambda e: self._on_moteur())
        self.var_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Auto-stretch STF (fond calé sur la cible)",
                        variable=self.var_auto, command=self._on_auto).pack(anchor="w")
        self.var_sigk = tk.DoubleVar(value=2.8)
        self._add_slider(box, "Coupure du bruit (k·σ sous le fond)",
                         self.var_sigk, 0.5, 5.0, 0.1,
                         lambda: (setattr(self.disp, "sigma_k", self.var_sigk.get()),
                                  self._refresh_preview()), "{:.1f}")
        self.var_target = tk.DoubleVar(value=0.25)
        self._add_slider(box, "Luminosité du fond du ciel",
                         self.var_target, 0.10, 0.45, 0.01,
                         lambda: (setattr(self.disp, "target", self.var_target.get()),
                                  self._refresh_preview()), "{:.2f}")
        ttk.Separator(box).pack(fill="x", pady=4)
        ttk.Label(box, text="Manuel (si auto décoché) :").pack(anchor="w")
        self.var_black = tk.DoubleVar(value=0.0)
        self.var_white = tk.DoubleVar(value=1.0)
        self.scl_black = self._add_slider(box, "Black point", self.var_black, 0.0, 1.0, 0.005,
                                          lambda: (setattr(self.disp, "black", self.var_black.get()),
                                                   self._refresh_preview()), "{:.3f}")
        self.scl_white = self._add_slider(box, "White point", self.var_white, 0.0, 2.0, 0.005,
                                          lambda: (setattr(self.disp, "white", self.var_white.get()),
                                                                                                      self._refresh_preview()), "{:.3f}")
        vg = tk.DoubleVar(value=1.0)
        self.var_gamma = vg
        self._add_slider(box, "Gamma (les 2 modes)", vg, 0.2, 4.0, 0.05,
                         lambda: (setattr(self.disp, "gamma", vg.get()),
                                  self._refresh_preview()), "{:.2f}")
        vs = tk.DoubleVar(value=1.0)
        self.var_saturation = vs
        self._add_slider(box, "Saturation", vs, 0.0, 3.0, 0.05,
                         lambda: (setattr(self.disp, "saturation", vs.get()),
                                  self._refresh_preview()), "{:.2f}")

        # --- VeraLux (moteur tiers) — caché tant que « STF » est sélectionné
        self.frm_veralux = ttk.Frame(box)
        ttk.Label(self.frm_veralux, text="Résolution du logD :").pack(anchor="w")
        self.var_vl_mode_res = tk.StringVar(value="logD forcé")
        # jalon 3 ajoutera « fond cible (target_bg) » à cette liste
        ttk.Combobox(self.frm_veralux, textvariable=self.var_vl_mode_res,
                     state="readonly", width=14, values=["logD forcé"]).pack(anchor="w")
        self.var_vl_logd = tk.DoubleVar(value=veralux_moteur.LOG_D_PAR_DEFAUT)
        self._add_slider(self.frm_veralux, "logD forcé",
                         self.var_vl_logd, 0.0, 7.0, 0.05,
                         lambda: (setattr(self.disp, "vl_log_d", self.var_vl_logd.get()),
                                  self._refresh_preview()), "{:.2f}")
        self.lbl_vl = ttk.Label(self.frm_veralux, text="—",
                                foreground="#888888", wraplength=310)
        self.lbl_vl.pack(anchor="w")

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
        self.btn_save_proc = ttk.Button(box, text="💾 Enregistrer le résultat traité…",
                                        command=self._save_proc, state="disabled")
        self.btn_save_proc.pack(fill="x")
        self.lbl_ext = ttk.Label(box, text="—", foreground="#888888", wraplength=310)
        self.lbl_ext.pack(anchor="w")

        # --- Sortie
        box = ttk.LabelFrame(left, text="Sortie", padding=6)
        box.pack(fill="x", pady=3)
        ttk.Button(box, text="💾 Enregistrer l'empilement…", command=self._save).pack(fill="x")

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

        s = ttk.Scale(row, from_=frm, to=to, value=var.get(), command=cmd)
        s.pack(fill="x")
        return s

    # ------------------------------------------------------------ callbacks UI
    def _on_kappa(self):
        self.kappa = {"Off": None, "2σ": 2.0, "3σ": 3.0, "4σ": 4.0, "5σ": 5.0}[self.var_kappa.get()]
        if self.stacker:
            self.stacker.k = self.kappa

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
            self.frm_veralux.pack(fill="x", pady=(4, 0))
            self.disp.vl_log_d = self.var_vl_logd.get()
            self.lbl_vl.config(text="Calcul en cours…", foreground="#c98a00")
        else:
            self.frm_veralux.pack_forget()
            self.lbl_vl.config(text="—", foreground="#888888")
        self._refresh_preview()

    def _on_view(self):
        """Bascule empilement ↔ résultat traité (stats d'étirement réinitialisées :
        les niveaux après GraXpert/BXT ne sont pas les mêmes)."""
        self.disp.reset()
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
        self.bad_frames, self.fps = 0, 0.0
        self.show_stack = None
        self.last_show = None
        self._session += 1                     # invalide tout traitement externe en vol
        self.proc_show = self.proc_full = None
        self.proc_new = False
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

            frame = self.camera.read()
            if frame is None:
                time.sleep(0.005)
                continue
            frame = self.calib.apply(frame)

            # (re)création de l'empilement / nouvelle référence
            if self.reset_request or self.stacker is None or self.stacker.shape != frame.shape:
                self.reset_request = False
                self.stacker = LiveStacker(frame.shape, k=self.kappa)
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

            if self.save_request is not None and stack is not None:
                path, self.save_request = self.save_request, None
                try:
                    save_image(path, stack)
                    self.saved_path = path
                except Exception as e:
                    self.saved_path = f"ERREUR: {e}"

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
                self._update_status(st)
                self._draw_hist(hist)
                if self.var_view.get() == "pile":     # la vue traitée garde son instantané
                    self.last_show = show
                    self._show_image(self.disp.process(show))
        except queue.Empty:
            pass
        if self.disp.vl_new:      # résultat du solveur VeraLux (thread dédié)
            self.disp.vl_new = False
            if self.var_moteur.get() == "VeraLux":
                self._refresh_preview()
                if self.disp.vl_error:
                    self.lbl_vl.config(text=self.disp.vl_error,
                                       foreground="#d04040")
                elif self.disp.vl_diagnostics is not None:
                    d = self.disp.vl_diagnostics
                    self.lbl_vl.config(
                        text=f"logD {self.disp.vl_log_d_resolu:.2f} · "
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


