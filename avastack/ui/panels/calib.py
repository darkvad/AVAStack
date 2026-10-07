# -*- coding: utf-8 -*-
"""Panneau « Calibration » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105b du chantier de refactoring. La
méthode `_poser_panneau_calibration` est reprise VERBATIM : `App` hérite de
`PanneauCalibration`, donc `self` reste l'instance `App` et le comportement
(boutons charger dark/flat, effacer la calibration, lignes d'état Dark/Flat) est
inchangé AU BIT.

Les attributs d'interface (widgets, méthodes de l'hôte) sont DÉCLARÉS ici pour
le typage statique (`pyright`) — aucune valeur, aucune logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class PanneauCalibration:
    """Mixin : panneau « Calibration » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_calibration: tk.Frame
    frm_calibration: tk.Frame
    frm_calibration_interne: ttk.Frame
    lbl_dark: ttk.Label
    lbl_flat: ttk.Label

    _creer_section_pliable: Callable[..., Any]
    _load_dark: Callable[..., Any]
    _load_flat: Callable[..., Any]
    _clear_calib: Callable[..., Any]

    # --- Jalon 105b : construction du panneau « Calibration » ----------------
    def _poser_panneau_calibration(self, parent: tk.Misc) -> None:
        """Cadre « Calibration » (ancre STABLE : les cadres commutables du
        jalon 47 se replacent toujours juste avant lui — l'ordre ne bouge
        jamais). `self.frm_calibration` pointe vers le conteneur EXTERNE de la
        section (porteur encadré, jalon 99) — l'ancre de
        `_maj_visibilite_cadres`."""
        # --- Calibration (ancre STABLE : les cadres commutables jalon 47 se
        # replacent toujours juste avant elle — l'ordre des cadres ne bouge
        # jamais, quel que soit le nombre d'allers-retours de source)
        # NOTE : self.frm_calibration pointe vers le conteneur EXTERNE de la
        # section (porteur encadré, jalon 99) — l'ancre de _maj_visibilite_cadres.
        # Le contenu est directement dans `box` (alias frm_calibration_interne).
        self._lf_calibration, box, _, _ = self._creer_section_pliable(
            parent, "calibration")
        self.frm_calibration = self._lf_calibration
        self.frm_calibration_interne = box  # alias pratique pour les sous-widgets
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
