# -*- coding: utf-8 -*-
"""Panneau « Fichiers de travail et journal » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105a du chantier de refactoring. La
méthode `_poser_panneau_fichiers_travail` est reprise VERBATIM : `App` hérite de
`PanneauFichiers`, donc `self` reste l'instance `App` et le comportement (ordre
de pose, indicateur d'espace, boutons 📂 Dossier / Ouvrir / Journal, case
Debug) est inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte) sont
DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur, aucune
logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class PanneauFichiers:
    """Mixin : panneau « Fichiers de travail et journal » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    var_debug: tk.Variable
    lbl_travail: ttk.Label
    _lf_fichiers_travail: tk.Frame

    _creer_section_pliable: Callable[..., Any]
    _choisir_dossier_travail: Callable[..., Any]
    _ouvrir_dossier_travail: Callable[..., Any]
    _ouvrir_journal: Callable[..., Any]

    # --- Jalon 105a : construction du panneau « Fichiers de travail » --------
    def _poser_panneau_fichiers_travail(self, parent: tk.Misc) -> None:
        """Panneau « Fichiers de travail et journal », EN HAUT de la colonne
        (v2.38.9).

        POURQUOI CE PLACEMENT : cette ligne est un indicateur GLOBAL (où vont
        les fichiers lourds — frames archivées, FITS des outils — et combien
        d'espace reste) et le POINT D'ENTRÉE du diagnostic (journal). Elle
        vivait en premières lignes du cadre « Traitement externe (long) », donc
        à 75 % de la hauteur d'une colonne DÉFILANTE (y≈2421 px sur 3218 px de
        contenu) : constat RÉEL d'Alain (27/09/2026) « pas de chemin pour temp
        et pas de bouton journal ». Mesure : les trois boutons ne tenaient pas
        sur une ligne (cadre 318 px = texte 243 + « Ouvrir » 43 + « 📂 » 28) et
        le troisième — « Journal » — n'était même pas AFFICHÉ
        (`winfo_ismapped()` = 0). D'où DEUX lignes : le texte, puis les
        boutons.
        """
        self._lf_fichiers_travail, box, _, _ = self._creer_section_pliable(
            parent, "fichiers_travail")
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
        # Case « Debug » (v2.54.1, demande d'Alain : déplacée du panneau
        # Astrométrie) — à côté du bouton « Journal », logique : les logs
        # DEBUG vont dans le journal, le réglage vit à côté de son bouton.
        ttk.Checkbutton(rowtr, text="Debug",
                        variable=self.var_debug).pack(side="left", padx=(8, 0))
