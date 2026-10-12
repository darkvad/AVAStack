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


def _globals_app():
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    Écho du correctif du jalon 105a : les bancs remplacent
    `avastack.ui.app.CONFIG` / `.sauver_config` pour intercepter le vrai
    config.json. Lire ces globals au MOMENT DE L'APPEL préserve cette
    interception ; en production c'est le MÊME objet que
    `avastack.config.CONFIG` / `avastack.config.sauver_config`."""
    from .. import app as _app              # import TARDIF (évite le cycle)
    return _app


class PanneauSortie:
    """Mixin : panneau « Sortie » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_sortie: tk.Frame
    btn_save_traite_lin: ttk.Button
    btn_save_asseen: ttk.Button
    # Jalon 121 : case « Fiche de rendu » (JSON compagnon).
    var_fiche_rendu: tk.Variable

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
        # Jalon 121 (demande d'Alain, 11/10/2026) : FICHE DE RENDU — un JSON
        # compagnon `<image>.ava.json` écrit à côté de CHAQUE image enregistrée,
        # pour que « le fichier dise ce qu'on lui a fait » (fini de deviner un
        # réglage depuis config.json ou par une empreinte). Case COCHÉE par
        # défaut (décision validée) ; le petit fichier porte, entre autres, la
        # chaîne DANS L'ORDRE et l'état APPLIQUÉ à côté de l'état AFFICHÉ.
        self.var_fiche_rendu = tk.BooleanVar(
            value=bool(_globals_app().CONFIG.get("fiche_rendu", True)))
        ttk.Checkbutton(
            box, text="Fiche de rendu (.ava.json) à côté de l'image",
            variable=self.var_fiche_rendu,
            command=self._on_fiche_rendu).pack(anchor="w", pady=(4, 0))

    def _on_fiche_rendu(self):
        """Persistance IMMÉDIATE de la case « Fiche de rendu » (jalon 121),
        comme les autres cases : un booléen EXPLICITE (une case décochée ne doit
        pas hériter d'un True) et le fichier de config réécrit tout de suite."""
        _app = _globals_app()
        _app.CONFIG["fiche_rendu"] = bool(self.var_fiche_rendu.get())
        _app.sauver_config(_app.CONFIG)
