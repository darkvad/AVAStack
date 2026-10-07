# -*- coding: utf-8 -*-
"""Panneau « Cadence d'empilement » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105a du chantier de refactoring :
- `_poser_panneau_cadence` construit la section pliable « Cadence
  d'empilement » (jalon 47 : UN SEUL cadre, partagé par « Dossier surveillé »
  et « Composition multi-filtres ») ;
- `_creer_cadence` pose la ligne « Empiler les brutes » (combobox + étiquette
  d'état) ;
- `_maj_lbl_cadence` entretient cette étiquette EN DIRECT.

Les méthodes sont reprises VERBATIM : `App` hérite de `PanneauCadence`, donc
`self` reste l'instance `App` et le comportement est inchangé AU BIT.

Les attributs d'interface (constantes, variables Tk, widgets, état, méthodes de
l'hôte) sont DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class PanneauCadence:
    """Mixin : panneau « Cadence d'empilement » (cf. docstring du module)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    CADENCES: tuple[tuple[str, int], ...]

    _lf_cadence: tk.Frame
    frm_rafale: ttk.Frame
    var_cadence: tk.Variable
    cb_cadence: ttk.Combobox
    lbl_cadence: ttk.Label
    _cadence_cbs: list[ttk.Combobox]
    _cadence_lbls: list[ttk.Label]
    _cadence_lbl_txt: str | None

    camera: Any
    cadence_lecture: int
    _prochaine_lecture: float

    _creer_section_pliable: Callable[..., Any]
    _on_cadence: Callable[..., Any]
    _cadence_dossier: Callable[..., Any]
    _brutes_en_attente: Callable[..., Any]

    # --- Jalon 105a : construction du panneau « Cadence d'empilement » -------
    def _poser_panneau_cadence(self, parent: tk.Misc) -> None:
        """Section « Cadence d'empilement » (jalon 47 : UN SEUL cadre,
        visible uniquement pour les sources dossier / composition, cf.
        `_maj_visibilite_cadres`).

        Le réglage de RAFALE (« Empiler les brutes », jalons 42/45) sort des
        cadres « Dossier surveillé » et « Composition multi-filtres » où il
        était DUPLIQUÉ.
        """
        # NOTE jalon 95 : self.frm_rafale = contenu interne (compat widgets),
        # self._lf_cadence = LabelFrame externe (pour pack/before).
        self._lf_cadence, self.frm_rafale, _, _ = self._creer_section_pliable(
            parent, "cadence")
        self._creer_cadence(self.frm_rafale)

    def _creer_cadence(self, parent):
        """Ligne « Empiler les brutes » (jalon 42 ; jalon 47 : UN SEUL
        exemplaire, dans le cadre dédié « Cadence d'empilement » — fini la
        duplication du jalon 45 dans les cadres dossier ET composition ; le
        choix reste commun, la cadence s'applique aux DEUX sources dossier
        car le worker la porte). L'étiquette (jalon 44) montre l'état du
        throttling en direct : « prochaine rafale dans Xs · N brute(s) en
        attente » (fenêtre armée), « rafale en cours » (drain), « — » (dès
        réception ou pas encore de source)."""
        if not hasattr(self, "var_cadence"):
            self.var_cadence = tk.StringVar(value="dès réception")
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(3, 0))
        ttk.Label(row, text="Empiler les brutes :").pack(side="left")
        cb = ttk.Combobox(row, textvariable=self.var_cadence,
                          state="readonly", width=16,
                          values=[lib for lib, _ in self.CADENCES])
        cb.pack(side="left", padx=(4, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_cadence())
        self._cadence_cbs.append(cb)
        if not hasattr(self, "cb_cadence"):
            self.cb_cadence = cb            # compatibilité (première créée)
        lbl = ttk.Label(parent, text="—")
        lbl.pack(anchor="w")
        self._cadence_lbls.append(lbl)
        if not hasattr(self, "lbl_cadence"):
            self.lbl_cadence = lbl          # compatibilité (première créée)

    def _maj_lbl_cadence(self):
        """État de la cadence affiché EN DIRECT (jalon 44) : pendant la
        fenêtre d'attente, « prochaine rafale dans Xs · N brute(s) en
        attente » (ambre) — la preuve visible que le throttling retient les
        brutes ; à l'échéance, « rafale en cours · N » (vert) pendant le
        drain ; « — » = dès réception OU pas encore de source connectée
        (jalon 45 : ne plus afficher « sans objet » avant la connexion —
        constat d'Alain) ; cadence posée sur une source non dossier →
        « sans objet ». Thread UI seul (appelé par _tick)."""
        if self.camera is None:
            txt, coul = "—", "#888888"      # pas encore de source : au repos
        elif self.cadence_lecture > 0 and self._cadence_dossier():
            attente = self._brutes_en_attente()
            reste = self._prochaine_lecture - time.monotonic()
            if reste > 0:
                txt = (f"prochaine rafale dans {reste:.0f} s · "
                       f"{attente} brute(s) en attente")
                coul = "#c98a00"
            else:
                txt = f"rafale en cours · {attente} brute(s) en attente"
                coul = "#1d7f1d"
        elif self.cadence_lecture > 0:
            txt = "cadence : sans objet (source non dossier)"
            coul = "#888888"
        else:
            txt, coul = "—", "#888888"
        if txt != self._cadence_lbl_txt:
            self._cadence_lbl_txt = txt
            for lbl in self._cadence_lbls:
                lbl.config(text=txt, foreground=coul)
