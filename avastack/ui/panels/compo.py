# -*- coding: utf-8 -*-
"""Panneau « Composition multi-filtres » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105b du chantier de refactoring. La
méthode `_poser_panneau_compo` est reprise VERBATIM : `App` hérite de
`PanneauComposition`, donc `self` reste l'instance `App` et le comportement
(1 à 4 lignes rôle + dossier, radio du canal L, gains R/G/B, détection des
filtres FITS, normalisation commune des canaux, pré-remplissage par
`_on_compo`) est inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte) sont
DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur, aucune
logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...processing.composition import COMPOSITIONS, ROLES


class PanneauComposition:
    """Mixin : panneau « Composition multi-filtres » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_composition: tk.Frame
    frm_compo: ttk.Frame
    var_compo: tk.Variable
    lbl_compo_info: ttk.Label
    rb_l_syn: ttk.Radiobutton
    rb_l_deg: ttk.Radiobutton
    var_compo_mode_l: tk.Variable
    var_norm_commune: tk.Variable
    var_compo_dossiers: list[tk.StringVar]
    var_compo_roles: list[tk.StringVar]
    var_compo_gains: dict[str, tk.StringVar]

    _creer_section_pliable: Callable[..., Any]
    _on_compo: Callable[..., Any]
    _on_compo_roles: Callable[..., Any]
    _pick_dossier_compo: Callable[..., Any]
    _detecter_filtres: Callable[..., Any]
    _on_norm_commune: Callable[..., Any]

    # --- Jalon 105b : construction du panneau « Composition multi-filtres » --
    def _poser_panneau_compo(self, parent: tk.Misc) -> None:
        """Cadre « Composition multi-filtres » (jalon 19) : 1 à 4 dossiers
        surveillés, un RÔLE (filtre) par dossier ; le composite temps réel
        combine les empilements par rôle selon la composition choisie."""
        # --- Composition multi-filtres (jalon 19) : 1 à 4 dossiers surveillés,
        # un RÔLE (filtre) par dossier ; le composite temps réel combine les
        # empilements par rôle selon la composition choisie.
        # NOTE jalon 95 : self.frm_compo = contenu interne (compat widgets),
        # self._lf_composition = LabelFrame externe (pour pack/before).
        self._lf_composition, self.frm_compo, _, _ = self._creer_section_pliable(
            parent, "composition")
        box = self.frm_compo
        row_c = ttk.Frame(self.frm_compo)
        row_c.pack(fill="x")
        ttk.Label(row_c, text="Composition :").pack(side="left")
        self.var_compo = tk.StringVar(value="HOO")
        cb_compo = ttk.Combobox(row_c, textvariable=self.var_compo,
                                state="readonly", width=8,
                                values=list(COMPOSITIONS))
        cb_compo.pack(side="left", padx=4)
        cb_compo.bind("<<ComboboxSelected>>", lambda e: self._on_compo())
        self.lbl_compo_info = ttk.Label(box, text="", foreground="#666666")
        self.lbl_compo_info.pack(anchor="w")
        # 4 lignes fixes : rôle (filtre) + dossier. Une ligne sans rôle = non
        # utilisée ; le remplissage des rôles CONTRAINT la composition
        # (cf. _on_compo_roles), la composition pré-remplit les rôles.
        self.var_compo_roles = [tk.StringVar(value="") for _ in range(4)]
        self.var_compo_dossiers = [tk.StringVar(value="") for _ in range(4)]
        for i in range(4):
            row = ttk.Frame(box)
            row.pack(fill="x", pady=1)
            cb_role = ttk.Combobox(row, textvariable=self.var_compo_roles[i],
                                   state="readonly", width=5,
                                   values=list(ROLES))
            cb_role.pack(side="left")
            cb_role.bind("<<ComboboxSelected>>", self._on_compo_roles)
            ttk.Entry(row, textvariable=self.var_compo_dossiers[i]).pack(
                side="left", fill="x", expand=True, padx=(4, 0))
            ttk.Button(row, text="…", width=3,
                       command=lambda i=i: self._pick_dossier_compo(i)
                       ).pack(side="left", padx=(4, 0))
        # Radio « Canal L » (utile en LRGB quand le dossier L est vide) :
        # L synthétisé = luminance du composite (combine identité) ;
        # dégradé = composite RGB pur (décisions d'Alain, 18/09/2026).
        row_l = ttk.Frame(box)
        row_l.pack(fill="x", pady=(4, 0))
        ttk.Label(row_l, text="Canal L (si dossier L vide) :").pack(side="left")
        self.var_compo_mode_l = tk.StringVar(value="synthetise")
        self.rb_l_syn = ttk.Radiobutton(row_l, text="Synthétisé",
                                        value="synthetise",
                                        variable=self.var_compo_mode_l)
        self.rb_l_deg = ttk.Radiobutton(row_l, text="Dégradé RGB",
                                        value="degrade",
                                        variable=self.var_compo_mode_l)
        self.rb_l_syn.pack(side="left", padx=(6, 0))
        self.rb_l_deg.pack(side="left", padx=(6, 0))
        # Gains R/G/B du composite : multiplicatifs APRÈS la normalisation
        # linéaire par canal — réglage à chaud de l'équilibre colorimétrique
        # (appliqués au composite dès la frame suivante, cf. _tick).
        row_g = ttk.Frame(box)
        row_g.pack(fill="x", pady=(4, 0))
        ttk.Label(row_g, text="Gains R/G/B :").pack(side="left")
        self.var_compo_gains = {canal: tk.StringVar(value="1.0")
                                for canal in ("R", "G", "B")}
        for canal in ("R", "G", "B"):
            ttk.Entry(row_g, textvariable=self.var_compo_gains[canal],
                      width=5).pack(side="left", padx=(4, 0))
        ttk.Button(box, text="🔎 Détecter les filtres (FITS FILTER)",
                   command=self._detecter_filtres).pack(fill="x", pady=(6, 0))
        # --- v2.36.0 : NORMALISATION COMMUNE DES CANAUX (option, décision
        # d'Alain du 25/09/2026). Décrivée en clair : c'est un changement de
        # comportement visible (fond et grain), pas un réglage cosmétique.
        self.var_norm_commune = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Normalisation commune des canaux",
                        variable=self.var_norm_commune,
                        command=self._on_norm_commune).pack(anchor="w",
                                                            pady=(6, 0))
        ttk.Label(box, text=(
            "Décoché : chaque canal est calé sur SES percentiles, avec SON point "
            "noir — le fond du composite suit alors son propre bruit : empiler "
            "plus ne réduit plus le grain du fond, et il reste coloré. "
            "Coché : les trois canaux partagent la MÊME ÉCHELLE (celle du vert) "
            "et aucun point noir n'est soustrait → le fond garde son niveau "
            "physique (son grain diminue enfin en 1/√n) et les coefficients SPCC "
            "s'appliquent sur la base où ils ont été mesurés. Le fond garde sa "
            "couleur physique (bleu-rouge) : la neutraliser avec l'équilibrage "
            "des canaux ou le recalage colorimétrique."),
            foreground="#888888", wraplength=310).pack(anchor="w")
        # Jalon 45/47 : le choix de cadence est COMMUN aux deux modes —
        # voir le cadre unique `frm_rafale` (plus de combobox ici).
        self._on_compo()    # pré-remplit les lignes de rôle de la compo par défaut
