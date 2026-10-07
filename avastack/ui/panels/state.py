# -*- coding: utf-8 -*-
"""Panneau « État des calculs » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105c du chantier de refactoring.
La méthode `_poser_panneau_etat_calculs` est reprise VERBATIM (seul le parent de la colonne
passe de `left` à `parent`, comme aux jalons 105a/105b) : `App` hérite de
`PanneauEtatCalculs`, donc `self` reste l'instance `App` et le comportement est
inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte)
sont DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur,
aucune logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class PanneauEtatCalculs:
    """Mixin : panneau « État des calculs » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_etat_calculs: tk.Frame
    frm_etat: ttk.Frame
    lbl_vl: ttk.Label
    pb_vl: ttk.Progressbar

    _creer_section_pliable: Callable[..., Any]

    # --- Jalon 105c : construction du panneau « État des calculs »
    def _poser_panneau_etat_calculs(self, parent: tk.Misc) -> None:
        # Corps repris VERBATIM de `app.py` (jalon 105c).
        # --- État des calculs (jalons 40/41) : cadre INDÉPENDANT du moteur —
        # visible en VeraLux (étapes du solveur : ⏳ préparation/composition/
        # GraXpert/débruitage/netteté/étirement, puis résultat GX/DN/NET/COUL
        # · logD · fond) ET en STF/manuel (⏳ netteté pendant la déconvolution
        # du solveur dédié jalon 12). Un seul écrivain : _maj_lbl_vl (thread
        # UI, appelée par _tick).
        # NOTE jalon 95 : self.frm_etat reste le CONTENU INTERNE (pour les
        # widgets enfants). Le LabelFrame externe est self._lf_etat_calculs.
        self._lf_etat_calculs, self.frm_etat, _, _ = self._creer_section_pliable(
            parent, "etat_calculs")
        self.lbl_vl = ttk.Label(self.frm_etat, text="—",
                                foreground="#888888", wraplength=310)
        self.lbl_vl.pack(anchor="w")
        self.pb_vl = ttk.Progressbar(self.frm_etat, mode="indeterminate",
                                     length=220)
