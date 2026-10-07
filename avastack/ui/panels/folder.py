# -*- coding: utf-8 -*-
"""Panneau « Dossier surveillé » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105a du chantier de refactoring. La
méthode `_poser_panneau_dossier_surveille` est reprise VERBATIM : `App` hérite
de `PanneauDossierSurveille`, donc `self` reste l'instance `App` et le
comportement (dossier à surveiller, option « images déjà présentes », motif CFA
des brutes capteur couleur, libellé « dernier fichier ») est inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte) sont
DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...images import CFA_MODE


class PanneauDossierSurveille:
    """Mixin : panneau « Dossier surveillé » (cf. docstring du module)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_dossier_surveille: tk.Frame
    frm_dossier: ttk.Frame
    var_folder: tk.Variable
    var_process_existing: tk.Variable
    var_cfa: tk.Variable
    lbl_last: ttk.Label

    _creer_section_pliable: Callable[..., Any]
    _pick_folder: Callable[..., Any]
    _on_cfa: Callable[..., Any]

    # --- Jalon 105a : construction du panneau « Dossier surveillé » ----------
    def _poser_panneau_dossier_surveille(self, parent: tk.Misc) -> None:
        """Panneau « Dossier surveillé » (visible uniquement pour cette source,
        jalon 47).

        NOTE jalon 95 : self.frm_dossier = contenu interne.
        """
        self._lf_dossier_surveille, self.frm_dossier, _, _ = self._creer_section_pliable(
            parent, "dossier_surveille")
        row = ttk.Frame(self.frm_dossier)
        row.pack(fill="x")
        self.var_folder = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.var_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=self._pick_folder).pack(side="left", padx=(4, 0))
        self.var_process_existing = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.frm_dossier,
                        text="Empiler aussi les images déjà présentes",
                        variable=self.var_process_existing).pack(anchor="w")
        rowc = ttk.Frame(self.frm_dossier)
        rowc.pack(fill="x", pady=(3, 0))
        ttk.Label(rowc, text="Brutes capteur couleur :").pack(side="left")
        self.var_cfa = tk.StringVar(value=CFA_MODE)
        ttk.Combobox(rowc, textvariable=self.var_cfa, state="readonly", width=6,
                     values=["Auto", "RGGB", "BGGR", "GRBG", "GBRG", "Non"]
                     ).pack(side="left", padx=(4, 0))
        self.var_cfa.trace_add("write", self._on_cfa)
        # Jalon 42/45 : la cadence d'empilement (« Empiler les brutes ») est
        # DÉPLACÉE hors de ce cadre (jalon 47) — un seul exemplaire partagé
        # par dossier surveillé et composition, cf. frm_rafale ci-dessus.
        self.lbl_last = ttk.Label(self.frm_dossier, text="Dernier fichier : —")
        self.lbl_last.pack(anchor="w")
