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

    _creer_section_pliable: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _on_vl_sharp: Callable[..., Any]

    # --- Jalon 105b : construction du panneau « Netteté live » ---------------
    def _poser_panneau_nette(self, parent: tk.Misc) -> None:
        """Cadre « Netteté live » (AVANT étirement) : Richardson-Lucy (PSF =
        seeing mesuré), indépendant du moteur d'étirement."""
        # --- Netteté live (jalon 12) : cadre INDÉPENDANT du moteur
        # d'étirement (demande d'Alain) — Richardson-Lucy s'applique AVANT
        # l'étirement, en STF/manuel comme en VeraLux. Position dans la
        # chaîne : après le débruitage (on lisse d'abord, on restaure
        # ensuite), avant l'étirement. PSF = seeing mesuré (jalon 10) ; la
        # netteté est calculée dans un thread dédié, jamais dans l'UI.
        # v2.48.0 (jalon 85) : ce cadre a été REMONTÉ ici, avant « Affichage » —
        # son titre dit « avant étirement » depuis le jalon 12, mais il était
        # affiché APRÈS le cadre qui porte l'étirement (demande d'Alain : « l'UI
        # doit respecter l'ordre des traitements »). Aucun comportement ne
        # change : seule la place dans la colonne.
        # NOTE jalon 95 : self.frm_sharp reste le CONTENU INTERNE (pour les
        # widgets enfants). Le LabelFrame externe est self._lf_nette.
        self._lf_nette, self.frm_sharp, _, _ = self._creer_section_pliable(
            parent, "nette")
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
