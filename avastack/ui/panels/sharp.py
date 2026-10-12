# -*- coding: utf-8 -*-
"""Panneau « Netteté live » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105b du chantier de refactoring. La
méthode `_poser_panneau_nette` est reprise VERBATIM : `App` hérite de
`PanneauNette`, donc `self` reste l'instance `App` et le comportement (case
« Netteté live » + curseur d'itérations + libellé d'état, indépendant du moteur
d'étirement) est inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte) sont
DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...processing import sharpness as nettete_live


class PanneauNette:
    """Mixin : panneau « Netteté live » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_nette: tk.Frame
    frm_sharp: ttk.Frame
    var_vl_sharp: tk.Variable
    var_vl_sharp_iter: tk.Variable
    scl_sharp: ttk.Scale
    lbl_sharp: ttk.Label
    # JALON 125 (VOLET A) : cases de la CHAÎNE PRÉ-ÉTIREMENT (GraXpert +
    # débruitage live) — DÉPLACÉES ici depuis le cadre VeraLux (visibles dans
    # les deux modes).
    var_vl_graxpert: tk.Variable
    var_vl_dn: tk.Variable
    var_vl_dn_methode: tk.Variable
    cb_vl_dn_methode: ttk.Combobox
    var_vl_dn_force: tk.Variable
    VL_DN_LABELS: Any
    VL_DN_METHODES: Any

    _creer_section_pliable: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _on_vl_sharp: Callable[..., Any]
    _on_vl_graxpert: Callable[..., Any]
    _on_vl_denoise: Callable[..., Any]

    # --- Jalon 105b : construction du panneau « Netteté live » ---------------
    def _poser_panneau_nette(self, parent: tk.Misc) -> None:
        """Cadre « Chaîne AVANT étirement » : GraXpert live (retrait de
        gradient) → débruitage live → netteté live (Richardson-Lucy) — la
        CHAÎNE PRÉ-ÉTIREMENT, COMMUNE aux deux moteurs (jalon 125, VOLET A).

        Ce cadre s'appelait « Netteté live » seule. Les cases GraXpert +
        débruitage y ont été DÉPLACÉES depuis le cadre VeraLux (décision
        d'Alain du 11/10/2026 : « le fichier = l'écran ») : elles s'appliquent
        désormais aussi en STF/manuel, donc elles doivent être visibles dans
        les DEUX modes — masquées dans le cadre VeraLux (caché en STF), elles
        restaient actives à la sauvegarde sans que rien ne le montre."""
        # --- Netteté live (jalon 12) : cadre INDÉPENDANT du moteur
        # d'étirement (demande d'Alain) — Richardson-Lucy s'applique AVANT
        # l'étirement, en STF/manuel comme en VeraLux. Position dans la
        # chaîne : après le débruitage (on lisse d'abord, on restaure
        # ensuite), avant l'étirement. PSF = seeing mesuré (jalon 10) ; la
        # netteté est calculée dans le thread de la CHAÎNE PRÉ-ÉTIREMENT,
        # jamais dans l'UI (jalon 125 : plus de thread dédié).
        # v2.48.0 (jalon 85) : ce cadre a été REMONTÉ ici, avant « Affichage » —
        # son titre dit « avant étirement » depuis le jalon 12, mais il était
        # affiché APRÈS le cadre qui porte l'étirement (demande d'Alain : « l'UI
        # doit respecter l'ordre des traitements »). Aucun comportement ne
        # change : seule la place dans la colonne.
        # NOTE jalon 95 : self.frm_sharp reste le CONTENU INTERNE (pour les
        # widgets enfants). Le LabelFrame externe est self._lf_nette.
        self._lf_nette, self.frm_sharp, _, _ = self._creer_section_pliable(
            parent, "nette")
        # --- JALON 125 (VOLET A) : CHAÎNE PRÉ-ÉTIREMENT (GraXpert + débruitage)
        # COMMUNE aux deux moteurs — cases DÉPLACÉES ici depuis le cadre VeraLux
        # (visibles dans les deux modes ; cf. la docstring).
        # GraXpert « live » : appliqué AVANT l'étirement, dans le thread de la
        # chaîne pré-étirement, à chaque nouvel empilement (opt-in). Le BXT
        # reste manuel (bouton ⚡ de la section Traitement externe).
        self.var_vl_graxpert = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_sharp,
                        text="GraXpert live (avant étirement)",
                        variable=self.var_vl_graxpert,
                        command=self._on_vl_graxpert).pack(anchor="w")
        # Débruitage local AVANT l'étirement — algorithmes rapides numpy/OpenCV
        # (aucun subprocess), vue « empilement » uniquement (cf.
        # `_sync_vl_denoise_vue`). Force 0..1 : seuil k-sigma (ondelettes) / h
        # (NLM) auto-adaptés au bruit réel de chaque empilement.
        rowdn = ttk.Frame(self.frm_sharp)
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
        self._add_slider(self.frm_sharp, "Force du débruitage (live)",
                         self.var_vl_dn_force, 0.0, 1.0, 0.05,
                         self._on_vl_denoise, "{:.2f}")
        ttk.Separator(self.frm_sharp).pack(fill="x", pady=4)
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
