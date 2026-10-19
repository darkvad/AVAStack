# -*- coding: utf-8 -*-
"""Panneau « Fond et grain » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105b du chantier de refactoring. La
méthode `_poser_panneau_fond_grain` est reprise VERBATIM : `App` hérite de
`PanneauFondGrain`, donc `self` reste l'instance `App` et le comportement
(neutralisation de la couleur du fond, réduction du bruit chromatique + rayon de
référence) est inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte) sont
DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...processing import couleurs as couleurs_mod


class PanneauFondGrain:
    """Mixin : panneau « Fond et grain » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_fond_grain: tk.Frame
    frm_fond: ttk.Frame
    var_vl_chroma: tk.Variable
    var_vl_chroma_force: tk.Variable
    var_vl_chroma_rayon: tk.Variable

    _creer_section_pliable: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _aide: Callable[..., Any]
    _on_vl_chroma: Callable[..., Any]
    _on_vl_chroma_rayon: Callable[..., Any]

    # --- Jalon 105b : construction du panneau « Fond et grain » --------------
    def _poser_panneau_fond_grain(self, parent: tk.Misc) -> None:
        """Cadre « Fond et grain » (AVANT étirement) : réduction du bruit
        chromatique (opt-in). La NEUTRALISATION de la couleur du fond a QUITTÉ
        ce cadre (jalon 124) : elle s'applique APRÈS l'étirement et vit
        désormais dans « Couleur de l'objet (APRÈS étirement) »."""
        # --- v2.48.0 (jalon 85) : L'ORDRE DES CADRES SUIT L'ORDRE DES TRAITEMENTS
        # (demande d'Alain : « l'UI doit respecter l'ordre des traitements »).
        # Le cadre couleur du jalon 22 MÉLANGEAIT deux étapes de la chaîne : la
        # correction AVANT l'étirement (réduction du bruit chromatique, appliquée
        # juste avant l'étirement, cf. display.py) et celles APRÈS (SCNR, SCNR
        # doux, démagenta, préservation de L*). Il est donc SCINDÉ, et la colonne
        # suit désormais la chaîne réelle :
        #   Fond et grain (AVANT étirement) → bruit chromatique ;
        #   Netteté live (AVANT étirement)  → Richardson-Lucy ;
        #   Affichage (temps réel)          → l'étirement lui-même + gamma/saturation ;
        #   Couleur de l'objet (APRÈS)      → SCNR / SCNR doux / démagenta (L*, R*).
        # Aucun réglage, aucune clé de configuration et aucun comportement ne
        # changent : seuls les PARENTS de ces widgets (donc leur place à l'écran)
        # changent, et l'ordre affiché devient l'ordre appliqué.
        # NOTE jalon 95 : self.frm_fond reste le CONTENU INTERNE (pour les
        # widgets enfants). Le LabelFrame externe est self._lf_fond_grain.
        self._lf_fond_grain, self.frm_fond, _, _ = self._creer_section_pliable(
            parent, "fond_grain")
        # --- jalons 123/124 : la NEUTRALISATION de la couleur du fond a QUITTÉ
        # ce cadre — elle s'applique APRÈS l'étirement, donc sa case vit
        # désormais dans « Couleur de l'objet (APRÈS étirement) »
        # (`panels/color.py`), juste avant gamma/saturation. Le jalon 123
        # l'avait déjà sortie de l'étage PRÉ-étirement (elle FABRIQUAIT le
        # magenta) ; le jalon 124 achève le déplacement CÔTÉ UI (constat
        # d'Alain : la garder ici la montrait comme un traitement AVANT
        # l'étirement). Seul le BRUIT CHROMATIQUE reste pré-étirement ici.

        # --- v2.37.0 : RÉDUCTION DU BRUIT CHROMATIQUE (opt-in, DÉCOCHÉE par
        # défaut — choix d'Alain, 25/09/2026 : « oui pour la réduction de bruit
        # chromatique (j'allais te demander un équivalent de SCNR pour le bleu de
        # toute façon) et case décochée par défaut »). Justification MESURÉE sur
        # ses empilements M31 (41 et 115 frames) : le grain du fond est équilibré
        # en R/G (0,90) mais B/G reste à ~1,17 — la SPCC applique K_B/K_G = 1,32,
        # et un gain multiplicatif amplifie le bruit du canal qu'il monte. Elle
        # lisse la CHROMA (YCrCb) en laissant la LUMINANCE intacte : ni le niveau
        # ni le contraste du fond ne bougent, seulement le grain coloré.
        self.var_vl_chroma = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_fond,
                        text="Réduire le bruit chromatique (live)",
                        variable=self.var_vl_chroma,
                        command=self._on_vl_chroma).pack(anchor="w")
        self.var_vl_chroma_force = tk.DoubleVar(value=0.5)
        self._add_slider(self.frm_fond, "Force du bruit chromatique",
                         self.var_vl_chroma_force, 0.0, 1.0, 0.05,
                         self._on_vl_chroma, "{:.2f}")
        # Lot 3 / P4 : texte d'aide → infobulle « ⓘ » (option « Aides en texte »).
        self._aide(self.frm_fond,
                   "Lisse la COULEUR du grain (YCrCb) sans toucher à la "
                   "luminance : un gain par canal (SPCC en tête) amplifie le "
                   "bruit du canal qu'il monte — mesuré : B/G 1,17 → ~1,00. "
                   "Force = part du bruit chromatique retirée.")
        # --- v2.37.4 : RAYON DE RÉFÉRENCE du flou de chroma (demande d'Alain,
        # 26/09/2026 : « pour la visu live, mets à disposition le réglage du rayon
        # de référence pour pouvoir faire des tests »). Exprimé en pixels PLEINE
        # RÉSOLUTION : l'aperçu de l'appli le ramène à sa propre échelle
        # (`couleurs.rayon_chroma_apercu`) pour rester fidèle aux fichiers, et la
        # chaîne EXTERNE comme la sauvegarde « tel que vu » l'utilisent tel quel.
        self.var_vl_chroma_rayon = tk.DoubleVar(value=couleurs_mod.RAYON_CHROMA_DEFAUT)
        self._add_slider(self.frm_fond, "Rayon de référence (px pleine rés.)",
                         self.var_vl_chroma_rayon, 0.5, 8.0, 0.25,
                         self._on_vl_chroma_rayon, "{:.2f}")
        self._aide(self.frm_fond,
                   "Rayon du flou qui lisse la couleur : plus grand = grain "
                   "coloré mieux retiré, mais couleur des étoiles plus "
                   "étalée (halo de couleur). L'aperçu applique ce rayon à "
                   "SON échelle, les fichiers à la pleine résolution — "
                   "l'écran reste fidèle au fichier.")
