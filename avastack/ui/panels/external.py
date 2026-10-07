# -*- coding: utf-8 -*-
"""Panneau « Traitement externe » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105c du chantier de refactoring.
La méthode `_poser_panneau_traitement_externe` est reprise VERBATIM (seul le parent de la colonne
passe de `left` à `parent`, comme aux jalons 105a/105b) : `App` hérite de
`PanneauTraitementExterne`, donc `self` reste l'instance `App` et le comportement est
inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte)
sont DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur,
aucune logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...external.detection import (
    DEFAULT_CMD_GRAXPERT, DEFAULT_CMD_GRAXPERT_DN,
    DEFAULT_CMD_BXT)


class PanneauTraitementExterne:
    """Mixin : panneau « Traitement externe » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_traitement_externe: tk.Frame
    var_ext_graxpert: tk.Variable
    var_cmd_graxpert: tk.Variable
    lbl_etat_graxpert: ttk.Label
    var_ext_dn: tk.Variable
    var_dn_methode: tk.Variable
    cb_dn_methode: ttk.Combobox
    var_cmd_graxpert_dn: tk.Variable
    lbl_etat_gx_dn: ttk.Label
    var_dn_force: tk.Variable
    var_ext_bxt: tk.Variable
    var_cmd_bxt: tk.Variable
    lbl_etat_bxt: ttk.Label
    var_ext_neutre: tk.Variable
    var_ext_chroma: tk.Variable
    var_view: tk.Variable
    btn_ext: ttk.Button
    btn_save_proc: ttk.Button
    lbl_ext: ttk.Label
    DN_EXT_METHODES: Any
    DN_EXT_LABELS: Any

    _creer_section_pliable: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _pick_exe: Callable[..., Any]
    _maj_etat_outils: Callable[..., Any]
    _on_view: Callable[..., Any]
    _request_ext: Callable[..., Any]
    _save_proc: Callable[..., Any]

    # --- Jalon 105c : construction du panneau « Traitement externe »
    def _poser_panneau_traitement_externe(self, parent: tk.Misc) -> None:
        # Corps repris VERBATIM de `app.py` (jalon 105c).
        # --- Traitement externe (long : plusieurs minutes — cf. docstring
        # de _run_external ; le « live » reste réservé aux étapes rapides)
        self._lf_traitement_externe, box, _, _ = self._creer_section_pliable(
            parent, "traitement_externe")
        # NB (v2.38.9) : la ligne « dossier de travail » et ses boutons étaient
        # ICI, en premières lignes du cadre. Constat d'Alain (27/09/2026) :
        # « pas de chemin pour temp et pas de bouton journal » — et la mesure lui
        # a donné raison sur les deux points : le bouton « Journal » n'était
        # JAMAIS affiché (`winfo_ismapped()=0`, cadre de 318 px trop étroit pour
        # trois boutons) et la ligne était sous le pli (y≈2421 px sur 3218 px de
        # colonne défilante). Ils vivent maintenant EN HAUT de la colonne, dans
        # le cadre « Fichiers de travail et journal » (cf. plus haut).
        self.var_ext_graxpert = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="1. GraXpert — retrait de gradient",
                        variable=self.var_ext_graxpert).pack(anchor="w")
        rowgx = ttk.Frame(box)
        rowgx.pack(fill="x")
        self.var_cmd_graxpert = tk.StringVar(value=DEFAULT_CMD_GRAXPERT)
        ttk.Entry(rowgx, textvariable=self.var_cmd_graxpert).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowgx, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_graxpert)
                   ).pack(side="left", padx=(4, 0))
        # v2.38.5 : état de la détection, TOUJOURS visible (chemin trouvé, ou
        # outil introuvable) — cf. _maj_etat_outils.
        self.lbl_etat_graxpert = ttk.Label(box, text="—", foreground="#888888",
                                           wraplength=310)
        self.lbl_etat_graxpert.pack(anchor="w")
        # Jalon 8 (remis le 16/09/2026) : débruitage du traitement externe —
        # méthode au choix : GraXpert IA (lent, subprocess) OU algorithmes
        # locaux rapides (ondelettes/NLM, en mémoire) ; force commune 0..1.
        # -strength (GraXpert) / k-sigma·h (local, auto-adaptés au bruit).
        rowd = ttk.Frame(box)
        rowd.pack(anchor="w")
        self.var_ext_dn = tk.BooleanVar(value=False)
        ttk.Checkbutton(rowd, text="2. Débruitage :",
                        variable=self.var_ext_dn).pack(side="left")
        self.var_dn_methode = tk.StringVar(
            value=self.DN_EXT_LABELS["graxpert"])
        self.cb_dn_methode = ttk.Combobox(
            rowd, textvariable=self.var_dn_methode, state="readonly",
            width=17, values=[lib for _, lib in self.DN_EXT_METHODES])
        self.cb_dn_methode.pack(side="left", padx=(4, 0))
        rowdn = ttk.Frame(box)
        rowdn.pack(fill="x")
        self.var_cmd_graxpert_dn = tk.StringVar(value=DEFAULT_CMD_GRAXPERT_DN)
        ttk.Entry(rowdn, textvariable=self.var_cmd_graxpert_dn).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowdn, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_graxpert_dn)
                   ).pack(side="left", padx=(4, 0))
        # v2.38.5 : même état que ci-dessus pour le débruitage GraXpert.
        self.lbl_etat_gx_dn = ttk.Label(box, text="—", foreground="#888888",
                                        wraplength=310)
        self.lbl_etat_gx_dn.pack(anchor="w")
        self.var_dn_force = tk.DoubleVar(value=0.5)
        self._add_slider(box, "Force du débruitage (0-1)", self.var_dn_force,
                         0.0, 1.0, 0.05, None, "{:.2f}")
        self.var_ext_bxt = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="3. BlurXTerminator — netteté",
                        variable=self.var_ext_bxt).pack(anchor="w")
        rowbx = ttk.Frame(box)
        rowbx.pack(fill="x")
        self.var_cmd_bxt = tk.StringVar(value=DEFAULT_CMD_BXT)
        ttk.Entry(rowbx, textvariable=self.var_cmd_bxt).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowbx, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_bxt)
                   ).pack(side="left", padx=(4, 0))
        # v2.38.5 : état de la détection pour BlurXTerminator (rc-astro).
        self.lbl_etat_bxt = ttk.Label(box, text="—", foreground="#888888",
                                      wraplength=310)
        self.lbl_etat_bxt.pack(anchor="w")
        # Un changement de commande (saisie, bouton « … », re-détection) met à
        # jour l'état affiché : c'est le seul retour dont dispose l'utilisateur.
        for _v in (self.var_cmd_graxpert, self.var_cmd_graxpert_dn,
                   self.var_cmd_bxt):
            _v.trace_add("write", self._maj_etat_outils)
        # v2.48.0 (jalon 85) : les trois cases couleur qui vivaient ICI
        # (« 4. SCNR », « 5. SCNR doux », « 6. Démagenta ») ont été RETIRÉES.
        # POURQUOI : la chaîne couleur suit désormais l'ÉTIREMENT (préservation
        # de la luminosité + sortie linéaire non écrêtée) — elle ne peut donc
        # plus faire partie d'une chaîne qui produit un fichier LINÉAIRE. Elle
        # est réglée par la section « Couleur de l'objet (après étirement) » et
        # s'applique à l'affichage du résultat ⚡ comme à sa sauvegarde
        # « tel que vu ». Les clés de configuration `ext_scnr`, `ext_scnr_doux`
        # et `ext_demagenta` ne sont plus écrites ni relues (sans effet).
        ttk.Label(box, text="4-6. Couleur (SCNR / SCNR doux / démagenta) et boost "
                            "du rouge (SII) : réglés par la section « Couleur de "
                            "l'objet (après étirement) » — appliqués APRÈS "
                            "l'étirement, à l'écran comme dans le fichier.",
                  foreground="#888888",
                  wraplength=310).pack(anchor="w", pady=(4, 0))
        # v2.37.1 — DEMANDE D'ALAIN (25/09/2026) : « intégrer les derniers ajouts
        # (SPCC, neutralisation, bruit chroma) dans la chaîne de traitement
        # externe pour que je puisse sortir une belle image à la fin du stack ».
        # La SPCC y était DÉJÀ (les corrections de couleur — gains effectifs
        # SPCC/Gaia/manuels, équilibrage, recalage « Linear Fit » — s'appliquent
        # au composite dans les deux chemins : `mean()` corrigé en mono,
        # `corrections_couleur` après recomposition en composition, cf.
        # _run_external_compo). Les DEUX corrections pré-étirement de la chaîne
        # live rejoignent donc la chaîne externe, au même rang qu'elle (… →
        # démagenta → neutralisation du fond → réduction du bruit chromatique,
        # juste avant l'étirement d'affichage) : c'est l'image que l'œil voit
        # sous l'ancre de VeraLux, et c'est elle que l'utilisateur exporte.
        self.var_ext_neutre = tk.BooleanVar(value=True)   # défaut COCHÉE, comme
                                                          # la case live (défaut
                                                          # de rendu, pas un
                                                          # choix esthétique)
        ttk.Checkbutton(box, text="7. Neutraliser la couleur du fond",
                        variable=self.var_ext_neutre).pack(anchor="w")
        self.var_ext_chroma = tk.BooleanVar(value=False)  # OPT-IN (choix d'Alain)
        ttk.Checkbutton(box,
                        text="8. Réduire le bruit chromatique (force = curseur "
                             "« Couleur live »)",
                        variable=self.var_ext_chroma).pack(anchor="w")
        ttk.Label(box, text="Placeholders : {input} · {output} (.fits complet) · "
                           "{outbase} (sans extension, GraXpert). « … » : choisir "
                           "l'exécutable, options conservées. Le débruitage "
                           "Ondelettes/NLM n'utilise aucune commande (traité "
                           "en mémoire).",
                  foreground="#888888", wraplength=310).pack(anchor="w")
        rowv = ttk.Frame(box)
        rowv.pack(fill="x", pady=2)
        self.var_view = tk.StringVar(value="pile")
        ttk.Radiobutton(rowv, text="Vue : empilement", variable=self.var_view, value="pile",
                        command=self._on_view).pack(side="left")
        ttk.Radiobutton(rowv, text="vue traitée", variable=self.var_view, value="traitée",
                        command=self._on_view).pack(side="left")
        self.btn_ext = ttk.Button(box, text="⚡ Traiter l'empilement courant",
                                  command=self._request_ext)
        self.btn_ext.pack(fill="x", pady=2)
        self.btn_save_proc = ttk.Button(box, text="💾 Enregistrer le résultat traité (linéaire)…",
                                        command=self._save_proc, state="disabled")
        self.btn_save_proc.pack(fill="x")
        self.lbl_ext = ttk.Label(box, text="—", foreground="#888888", wraplength=310)
        self.lbl_ext.pack(anchor="w")
