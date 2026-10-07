# -*- coding: utf-8 -*-
"""Panneau « Sortie » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105c du chantier de refactoring.
La méthode `_poser_panneau_sortie` est reprise VERBATIM (seul le parent de la colonne
passe de `left` à `parent`, comme aux jalons 105a/105b) : `App` hérite de
`PanneauSortie`, donc `self` reste l'instance `App` et le comportement est
inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte)
sont DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur,
aucune logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class PanneauSortie:
    """Mixin : panneau « Sortie » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_sortie: tk.Frame
    btn_save_traite_lin: ttk.Button
    btn_save_asseen: ttk.Button

    _creer_section_pliable: Callable[..., Any]
    _save: Callable[..., Any]
    _save_traite_lineaire: Callable[..., Any]
    _save_asseen: Callable[..., Any]
    _save_canaux: Callable[..., Any]

    # --- Jalon 105c : construction du panneau « Sortie »
    def _poser_panneau_sortie(self, parent: tk.Misc) -> None:
        # Corps repris VERBATIM de `app.py` (jalon 105c).
        # --- Sortie
        self._lf_sortie, box, _, _ = self._creer_section_pliable(parent, "sortie")
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
