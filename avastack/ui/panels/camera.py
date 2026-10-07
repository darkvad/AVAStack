# -*- coding: utf-8 -*-
"""Panneau « Caméra » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105a du chantier de refactoring. La
méthode `_poser_panneau_camera` est reprise VERBATIM : `App` hérite de
`PanneauCamera`, donc `self` reste l'instance `App` et le comportement (ordre de
pose — choix de source + Démarrer/Arrêter AVANT les contrôles caméra,
exposition, gain / offset, roue à filtres, TEC, détection SDK, déconnexion) est
inchangé AU BIT.

Le formateur `_fmt_expo` (exposition lisible µs/ms/s) est le compagnon de ce
panneau : il est DÉPLACÉ ici et RÉ-IMPORTÉ par `app.py` (dont les méthodes
d'exposition `_maj_expo` / `_valider_expo` continuent de l'utiliser). Le
ré-import préserve `avastack.ui.app._fmt_expo` (usage des bancs).

Les attributs d'interface (variables Tk, widgets, état, méthodes de l'hôte) sont
DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...cameras import SOURCES
from ...cameras.base import FILTRES_ROUE


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


class PanneauCamera:
    """Mixin : panneau « Caméra » (cf. docstring du module)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    # Widgets et état créés par ce panneau.
    _lf_camera: tk.Frame
    frm_ctrl_cam: ttk.Frame
    cb_source: ttk.Combobox
    btn_start: ttk.Button
    btn_stop: ttk.Button
    entry_expo: ttk.Entry
    lbl_expo: ttk.Label
    s_expo: ttk.Scale
    chk_expo_longue: ttk.Checkbutton
    sl_gain: ttk.Scale
    sl_offset: ttk.Scale
    cb_filtre: ttk.Combobox
    lbl_filtre: ttk.Label
    lbl_tec_lib: ttk.Label
    btn_tec_on: ttk.Button
    btn_tec_off: ttk.Button
    lbl_tec: ttk.Label
    lbl_detect: ttk.Label
    btn_deconnect: ttk.Button

    # Variables Tk.
    var_source: tk.Variable
    var_expo: tk.Variable
    var_gain: tk.Variable
    var_offset: tk.Variable
    var_expo_longue: tk.Variable
    var_tec_consigne: tk.Variable
    var_filtre: tk.Variable
    var_expo_saisie: tk.Variable

    # État consommé par le thread d'acquisition (`_tick`).
    _tec_dernier: Any
    _tec_demande: Any
    _tec_info: Any
    _filtre_demande: Any
    _filtre_info: Any
    _roue_ok: bool

    # Méthodes de l'hôte appelées par ce panneau.
    _creer_section_pliable: Callable[..., Any]
    _on_source_choisie: Callable[..., Any]
    _start: Callable[..., Any]
    _stop: Callable[..., Any]
    _valider_expo: Callable[..., Any]
    _on_pas_expo: Callable[..., Any]
    _pos_depuis_expo: Callable[..., Any]
    _on_curseur_expo: Callable[..., Any]
    _on_echelle_expo: Callable[..., Any]
    _maj_libelle_expo_longue: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _push_settings: Callable[..., Any]
    _on_filtre_choisi: Callable[..., Any]
    _on_consigne_tec: Callable[..., Any]
    _on_arret_tec: Callable[..., Any]
    _detecter_camera: Callable[..., Any]
    _deconnecter_camera: Callable[..., Any]

    # --- Jalon 105a : construction du panneau « Caméra » ---------------------
    def _poser_panneau_camera(self, parent: tk.Misc) -> None:
        """Panneau « Caméra » : la SOURCE + Démarrer/Arrêter sont TOUJOURS
        visibles ; les contrôles propres à la caméra (exposition, gain, roue,
        TEC, détection SDK…) vont dans `frm_ctrl_cam`, qui n'apparaît QUE pour
        une source caméra (jalon 47 — en dossier/composition, la colonne ne
        montre que ce qui sert au choix en cours, cf. `_maj_visibilite_cadres`).
        """
        self._lf_camera, box, _, _ = self._creer_section_pliable(parent, "camera")
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
