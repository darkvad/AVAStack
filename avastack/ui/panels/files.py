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


def _globals_app():
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    Écho du motif des jalons 104/105a : les bancs remplacent
    `avastack.ui.app.CONFIG` / `.sauver_config` pour intercepter le VRAI
    config.json. Lire ces globals au MOMENT DE L'APPEL préserve cette
    interception ; en production c'est le MÊME objet.
    (Import TARDIF : `avastack.ui.app` importe ce module.)"""
    from .. import app as _app
    return _app


class PanneauFichiers:
    """Mixin : panneau « Fichiers de travail et journal » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    var_debug: tk.Variable
    var_aides_texte: tk.Variable
    lbl_travail: ttk.Label
    _lf_fichiers_travail: tk.Frame

    _creer_section_pliable: Callable[..., Any]
    _choisir_dossier_travail: Callable[..., Any]
    _ouvrir_dossier_travail: Callable[..., Any]
    _ouvrir_journal: Callable[..., Any]
    _on_aides_texte: Callable[..., Any]

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
        # --- Lot 3 / P4 (v2.95.0) : OPTION « Aides en texte dans la colonne ».
        # Les explications de la colonne sont des INFOBULLES derrière un « ⓘ »
        # (défaut) : mesuré, les 13 textes d'aide prenaient 1 267 px — 84,5
        # lignes, 23,5 % de la colonne — et poussaient les réglages sous le
        # pli. Cette case rétablit l'ancien affichage (lire les aides d'un
        # coup, capture d'écran) ; la bascule est IMMÉDIATE et persistée
        # (`aides_texte`). Ligne DÉDIÉE : la ligne du dessus est déjà pleine
        # (trois boutons + Debug — leçon du jalon 72).
        self.var_aides_texte = tk.BooleanVar(
            value=bool(_globals_app().CONFIG.get("aides_texte", False)))
        ttk.Checkbutton(box, text="Aides en texte dans la colonne",
                        variable=self.var_aides_texte,
                        command=self._on_aides_texte).pack(anchor="w",
                                                           pady=(3, 0))
