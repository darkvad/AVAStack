# -*- coding: utf-8 -*-
"""Panneau « Stacks (fichiers FITS) » (colonne gauche) — mixin TYPÉ.

P6 (lot 5 des améliorations d'usage, 19/10/2026) : source d'empilements DÉJÀ
FAITS, choisis FICHIER par FICHIER (pas un dossier — un stack peut venir de
Siril, PixInsight, ASTAP… et vivre n'importe où).

Le panneau ne DECIDE rien : il pose `NB_LIGNES_COMPO` lignes « rôle → fichier »
(les mêmes rôles que la composition multi-dossiers) et laisse `app.py` valider,
déduire la composition et construire la caméra `StackFilesCamera`. Le RÔLE est
celui que l'utilisateur choisit : rien n'est deviné à partir du nom du fichier
ni de son en-tête (un `FILTER` contradictoire n'est qu'un avertissement).

`App` hérite de ce mixin : `self` reste l'instance `App`, donc la pose des
widgets et le comportement suivent les autres panneaux. Les attributs
d'interface sont DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...processing.composition import NB_LIGNES_COMPO, ROLES


class PanneauStacks:
    """Mixin : panneau « Stacks (fichiers FITS) » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_stacks: tk.Frame
    frm_stacks: ttk.Frame
    var_stacks_roles: list[tk.StringVar]
    var_stacks_fichiers: list[tk.StringVar]
    lbl_stacks_info: ttk.Label

    _creer_section_pliable: Callable[..., Any]
    _aide: Callable[..., Any]
    _on_stacks_roles: Callable[..., Any]
    _pick_fichier_stacks: Callable[..., Any]

    # --- P6 : construction du panneau « Stacks (fichiers FITS) » -------------
    def _poser_panneau_stacks(self, parent: tk.Misc) -> None:
        """Panneau « Stacks (fichiers FITS) », visible UNIQUEMENT pour cette
        source (même mécanique que « Dossier surveillé » / « Composition »).

        NOTE jalon 95 : `self._lf_stacks` = porteur externe (pack/before),
        `self.frm_stacks` = contenu interne (compatibilité des widgets).
        """
        self._lf_stacks, self.frm_stacks, _, _ = self._creer_section_pliable(
            parent, "stacks")
        box = self.frm_stacks
        # Même nombre de lignes que la composition multi-dossiers (SOURCE
        # UNIQUE `NB_LIGNES_COMPO` : jamais un `range(5)` recopié).
        self.var_stacks_roles = [tk.StringVar(value="")
                                 for _ in range(NB_LIGNES_COMPO)]
        self.var_stacks_fichiers = [tk.StringVar(value="")
                                    for _ in range(NB_LIGNES_COMPO)]
        for i in range(NB_LIGNES_COMPO):
            row = ttk.Frame(box)
            row.pack(fill="x", pady=1)
            cb_role = ttk.Combobox(row, textvariable=self.var_stacks_roles[i],
                                   state="readonly", width=5,
                                   values=list(ROLES))
            cb_role.pack(side="left")
            cb_role.bind("<<ComboboxSelected>>", self._on_stacks_roles)
            ttk.Entry(row, textvariable=self.var_stacks_fichiers[i]).pack(
                side="left", fill="x", expand=True, padx=(4, 0))
            ttk.Button(row, text="…", width=3,
                       command=lambda i=i: self._pick_fichier_stacks(i)
                       ).pack(side="left", padx=(4, 0))
        # Ligne d'ÉTAT du panneau : composition DÉDUITE des rôles indiqués +
        # avertissements (FILTER contradictoire, fichier absent). Remplie par
        # `App._maj_stacks_info` — jamais par ce panneau.
        self.lbl_stacks_info = ttk.Label(box, text="", foreground="#666666",
                                         wraplength=310)
        self.lbl_stacks_info.pack(anchor="w", pady=(4, 0))
        self._aide(
            box,
            "Source d'EMPILEMENTS DÉJÀ FAITS : un fichier par filtre voulu "
            "(FITS, où qu'il soit — Siril, PixInsight, ASTAP, AVAStack…). Le "
            "RÔLE est celui que VOUS indiquez : il n'est jamais déduit du nom "
            "du fichier ni de l'en-tête (un mot-clé FILTER contradictoire est "
            "seulement signalé, votre choix fait foi). Chaque fichier est lu "
            "UNE fois par session, sans calibration (un empilement n'a plus de "
            "signal brut à corriger) ; un seul fichier = empilement direct, "
            "plusieurs = composition déduite des rôles (comme le mode "
            "« Composition multi-dossiers »). La profondeur (nombre de brutes "
            "derrière le stack) n'est PAS lue : les mesures partent dès qu'un "
            "fichier par rôle est là, et l'état dit « empilement fourni "
            "(profondeur non vérifiée) ». Un fichier DÉJÀ ÉTIRÉ est refusé si "
            "son en-tête AVAStack le dit ; sinon il est accepté avec un "
            "avertissement mesuré.")
        self._on_stacks_roles()      # ligne d'aide juste dès l'ouverture
