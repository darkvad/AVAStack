# -*- coding: utf-8 -*-
"""Panneau « Couleur de l'objet (APRÈS étirement) » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105c du chantier de refactoring.
La méthode `_poser_panneau_couleur` est reprise VERBATIM (seul le parent de la colonne
passe de `left` à `parent`, comme aux jalons 105a/105b) : `App` hérite de
`PanneauCouleur`, donc `self` reste l'instance `App` et le comportement est
inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte)
sont DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur,
aucune logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...processing import couleurs as couleurs_mod


class PanneauCouleur:
    """Mixin : panneau « Couleur de l'objet (APRÈS étirement) » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_couleur: tk.Frame
    frm_couleur: ttk.Frame
    var_vl_preserve: tk.Variable
    var_vl_scnr: tk.Variable
    var_vl_scnr_force: tk.Variable
    var_vl_scnr_doux: tk.Variable
    var_vl_demagenta: tk.Variable
    var_vl_demagenta_force: tk.Variable
    var_vl_boost: tk.Variable
    var_vl_boost_force: tk.Variable

    _creer_section_pliable: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _on_vl_preserve: Callable[..., Any]
    _on_vl_scnr: Callable[..., Any]
    _on_vl_scnr_force: Callable[..., Any]
    _on_vl_scnr_doux: Callable[..., Any]
    _on_vl_demagenta: Callable[..., Any]
    _on_vl_demagenta_force: Callable[..., Any]
    _on_vl_boost: Callable[..., Any]
    _on_vl_boost_force: Callable[..., Any]

    # --- Jalon 105c : construction du panneau « Couleur de l'objet (APRÈS étirement) »
    def _poser_panneau_couleur(self, parent: tk.Misc) -> None:
        # Corps repris VERBATIM de `app.py` (jalon 105c).
        # --- Couleur de l'objet (v2.48.0, jalon 85) : cadre INDÉPENDANT du
        # moteur d'étirement, appliqué APRÈS l'étirement par le solveur VeraLux
        # (jalon 22/23, déplacé ici au jalon 85) ET par le moteur STF/manuel
        # (`display.process()`) ; no-op sur un composite monochrome (Mono).
        # S'applique aux DEUX VUES (v2.48.1) : elle n'est plus dans la chaîne
        # externe, donc la vue « traitée » la porte enfin comme le live.
        # POURQUOI APRÈS l'étirement : la
        # préservation de la luminosité (case ci-dessous, cochée par défaut)
        # est une grandeur PERCEPTUELLE, et la sortie LINÉAIRE sauvegardée ne
        # doit plus être écrêtée en vert (elle l'était — MESURÉ sur l'empilement
        # M31 d'Alain : excès de vert max 5,9·10⁻⁸ contre 1,6·10⁻¹ sur
        # l'empilement d'origine).
        # NOTE jalon 95 : self.frm_couleur reste le CONTENU INTERNE
        # (compatibilité avec tout le code qui crée des widgets dedans).
        # Le LabelFrame externe est accessible via self._lf_couleur.
        self._lf_couleur, self.frm_couleur, _, _ = self._creer_section_pliable(
            parent, "couleur")
        self.var_vl_preserve = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.frm_couleur,
                        text="Préserver la luminosité (L*) — comme Siril",
                        variable=self.var_vl_preserve,
                        command=self._on_vl_preserve).pack(anchor="w",
                                                           pady=(2, 0))
        ttk.Label(self.frm_couleur,
                  text="Sans elle, retirer du vert RETIRE DE LA LUMIÈRE : "
                       "mesuré sur ton empilement SHO NGC 2237, la nébuleuse "
                       "passe de L* 56,5 à 25,8 (elle s'éteint — « manque de "
                       "doré ») ; avec elle, 56,4. Seuls les pixels corrigés "
                       "changent.",
                  foreground="#888888", wraplength=310).pack(anchor="w")
        self.var_vl_scnr = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur, text="SCNR — retrait du vert",
                        variable=self.var_vl_scnr,
                        command=self._on_vl_scnr).pack(anchor="w", pady=(4, 0))
        self.var_vl_scnr_force = tk.DoubleVar(value=1.0)
        self._add_slider(self.frm_couleur, "Force du SCNR (1,00 = retrait total)",
                         self.var_vl_scnr_force, 0.0, 1.0, 0.05,
                         self._on_vl_scnr_force, "{:.2f}")
        # Jalon 23 : SCNR doux borné par le bruit — ne retire que le
        # grésillement vert (excès de vert ≤ 3σ), préserve la structure
        # (nébuleuses) : pensé pour les palettes narrowband où le vert est
        # de la DONNÉE (HOO : O3 ; SHO sans S : Ha). MESURÉ (banc jalon 85 [6]) :
        # après un SCNR à force 1,00 l'excès est ≤ 0 partout, donc cette case ne
        # retire plus rien — elle ne redevient active qu'avec une force < 1,00.
        self.var_vl_scnr_doux = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur,
                        text="SCNR doux — bruit seul (actif si force < 1,00)",
                        variable=self.var_vl_scnr_doux,
                        command=self._on_vl_scnr_doux).pack(anchor="w")
        self.var_vl_demagenta = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur,
                        text="Démagenta — négatif + SCNR",
                        variable=self.var_vl_demagenta,
                        command=self._on_vl_demagenta).pack(anchor="w")
        self.var_vl_demagenta_force = tk.DoubleVar(value=1.0)
        self._add_slider(self.frm_couleur, "Force du démagenta",
                         self.var_vl_demagenta_force, 0.0, 1.0, 0.05,
                         self._on_vl_demagenta_force, "{:.2f}")
        ttk.Label(self.frm_couleur,
                  text="Les deux cases sont INDÉPENDANTES (en SHO la teinte "
                       "magenta coexiste avec l'excès de vert) : l'ordre est "
                       "SCNR → SCNR doux → démagenta, et chacun garde sa force.",
                  foreground="#888888", wraplength=310).pack(anchor="w")

        # --- v2.48.0 (jalon 86) : BOOST DU ROUGE (SII) MASQUÉ À L'OBJET -------
        # Décision d'Alain après la mesure de son empilement SHO NGC 2237 :
        # « la préservation de L* marche (la nébuleuse n'est plus éteinte), mais
        # elle reste verte — il manque le doré ». Le doré EST physique : en SHO
        # le rouge vient du SII, faible (MESURÉ sur ses brutes : SII/Ha = 0,22,
        # soit 4,6× moins de flux que Ha), et les deux autres leviers essayés
        # sont MESURÉS et écartés — le « Linear Fit » gain + offset se cale sur
        # le quart central de l'image (60,6 % d'OBJET ici), choisit un gain rouge
        # au plafond (×4,0) et colore le fond (saturation 0,08 → 0,34) tout en
        # délavant la nébuleuse (0,72 → 0,31) ; un gain R global teinte le ciel
        # (97 % des pixels de fond en R > V à ×2,5). Ce boost-ci pèse son gain
        # par la LUMINANCE (0 dans le fond, 1 sur l'objet) : le fond reste
        # identique AU PIXEL près (vérifié : les quatre mesures de fond ne
        # bougent pas de ×1,5 à ×4,0).
        ttk.Separator(self.frm_couleur).pack(fill="x", pady=4)
        self.var_vl_boost = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_couleur,
                        text="Boost du rouge (SII) — masqué à l'objet",
                        variable=self.var_vl_boost,
                        command=self._on_vl_boost).pack(anchor="w")
        self.var_vl_boost_force = tk.DoubleVar(
            value=float(couleurs_mod.BOOST_ROUGE_DEFAUT))
        self._add_slider(self.frm_couleur,
                         "Force du boost (3,00 = doré mesuré)",
                         self.var_vl_boost_force,
                         float(couleurs_mod.BOOST_ROUGE_MIN),
                         float(couleurs_mod.BOOST_ROUGE_MAX), 0.05,
                         self._on_vl_boost_force, "{:.2f}")
        ttk.Label(self.frm_couleur,
                  text="À 3,00 la nébuleuse atteint le R:G du Linear Fit "
                       "(mesuré 1,07 contre 1,05) en gardant sa saturation "
                       "(0,70 contre 0,31) ; à 4,00 le doré est franc. Appliqué "
                       "EN DERNIER (après le SCNR) pour que les deux se cumulent "
                       "au lieu de se combattre. 1,00 = aucun effet.",
                  foreground="#888888", wraplength=310).pack(anchor="w")
