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

from ...processing.composition import (ALPHA_HA_DEFAUT, ALPHA_HA_MAX,
                                       ALPHA_HA_MIN, COMPOSITIONS,
                                       CONTINUUM_HA_DEFAUT, FUSION_HA_DEFAUT,
                                       MODES_FUSION_HA, NB_LIGNES_COMPO,
                                       POIDS_HA_DEFAUT, POIDS_HA_MAX,
                                       POIDS_HA_MIN, Q_HA_DEFAUT, Q_HA_MAX,
                                       Q_HA_MIN, ROLES, SEUIL_MASQUE_MAX,
                                       SEUIL_MASQUE_MIN, SEUIL_MASQUE_SIGMA)


class PanneauComposition:
    """Mixin : panneau « Composition multi-filtres » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_composition: tk.Frame
    frm_compo: ttk.Frame
    var_compo: tk.Variable
    lbl_compo_info: ttk.Label
    lbl_compo_session: ttk.Label
    rb_l_syn: ttk.Radiobutton
    rb_l_deg: ttk.Radiobutton
    var_compo_mode_l: tk.Variable
    var_norm_commune: tk.Variable
    var_lissage_halos: tk.Variable
    var_lissage_halos_sigma: tk.Variable
    # Jalon J2 (v2.88.0) : cadre « Fusion Ha » — mode + poids du Ha ajouté au
    # rouge des compositions RGB+Ha / LRGB+Ha.
    frm_fusion_ha: ttk.LabelFrame
    var_fusion_ha_mode: tk.Variable
    var_fusion_ha_poids: tk.Variable
    var_fusion_ha_alpha: tk.Variable
    var_fusion_ha_continuum: tk.Variable
    var_fusion_ha_q: tk.Variable
    chk_fusion_ha_continuum: ttk.Checkbutton
    sp_fusion_ha_alpha: ttk.Spinbox
    sp_fusion_ha_q: ttk.Spinbox
    var_compo_dossiers: list[tk.StringVar]
    var_compo_roles: list[tk.StringVar]
    var_compo_gains: dict[str, tk.StringVar]

    _creer_section_pliable: Callable[..., Any]
    _on_compo: Callable[..., Any]
    _on_compo_roles: Callable[..., Any]
    _pick_dossier_compo: Callable[..., Any]
    _detecter_filtres: Callable[..., Any]
    _on_norm_commune: Callable[..., Any]
    _on_lissage_halos: Callable[..., Any]
    _on_fusion_ha: Callable[..., Any]

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
        # Jalon 141-B (décision d'Alain du 18/10/2026 — option B : PRÉVENIR).
        # Le menu ci-dessus dit ce que l'on CHOISIT ; il ne dit pas ce que la
        # SESSION en cours empile réellement. Changer la composition en cours de
        # route laissait donc l'interface afficher « RGB » pendant que le
        # composite (et l'en-tête AVACOMPO du fichier) restaient en LRGB+Ha : le
        # fichier était juste, l'écran mentait en silence. Ce bandeau le dit, en
        # orange, tant que l'écart dure ; il est vide le reste du temps.
        self.lbl_compo_session = ttk.Label(box, text="", foreground="#c98a00",
                                           wraplength=310)
        self.lbl_compo_session.pack(anchor="w")
        # NB_LIGNES_COMPO lignes fixes : rôle (filtre) + dossier. Une ligne sans
        # rôle = non utilisée ; le remplissage des rôles CONTRAINT la composition
        # (cf. _on_compo_roles), la composition pré-remplit les rôles.
        # Jalon 129 : 5 lignes — le maximum de rôles d'une composition est celui
        # de LRGB+Ha (L, R, G, B, Ha) ; la constante est partagée avec `app.py`
        # et `config_ui.py` (jamais un `range(4)` recopié).
        self.var_compo_roles = [tk.StringVar(value="")
                                for _ in range(NB_LIGNES_COMPO)]
        self.var_compo_dossiers = [tk.StringVar(value="")
                                   for _ in range(NB_LIGNES_COMPO)]
        for i in range(NB_LIGNES_COMPO):
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
        # --- Jalon 117d : LISSAGE DU COMBINE LRGB (halos d'étoiles), OPT-IN.
        # Décision d'Alain du 10/10/2026 : le rapport L/luma est lissé à l'échelle
        # des étoiles pour éteindre les halos colorés, mais SEULEMENT autour des
        # étoiles brillantes (masque). Le seuil du masque est EMPIRIQUE (il dépend
        # du fond) : il est réglable ici. Case DÉCOCHÉE = combine d'avant le 117c.
        self.var_lissage_halos = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Lisser le combine LRGB (halos d'étoiles)",
                        variable=self.var_lissage_halos,
                        command=self._on_lissage_halos).pack(anchor="w",
                                                             pady=(6, 0))
        row_lh = ttk.Frame(box)
        row_lh.pack(fill="x", pady=(2, 0))
        ttk.Label(row_lh, text="σ du masque (étoiles) :").pack(side="left")
        self.var_lissage_halos_sigma = tk.DoubleVar(
            value=float(SEUIL_MASQUE_SIGMA))
        self.sp_lissage_halos = ttk.Spinbox(
            row_lh, from_=float(SEUIL_MASQUE_MIN), to=float(SEUIL_MASQUE_MAX),
            increment=1.0, width=5, textvariable=self.var_lissage_halos_sigma,
            command=self._on_lissage_halos)
        self.sp_lissage_halos.pack(side="left", padx=(4, 0))
        # La saisie au clavier (Entrée ou perte de focus) applique aussi — la
        # flèche du Spinbox ne suffit pas.
        self.sp_lissage_halos.bind("<Return>",
                                   lambda e: self._on_lissage_halos())
        self.sp_lissage_halos.bind("<FocusOut>",
                                   lambda e: self._on_lissage_halos())
        ttk.Label(box, text=(
            "Coché : le rapport L/luma est lissé à l'échelle des ÉTOILES pour "
            "éteindre leur halo coloré, mais SEULEMENT dans le masque d'étoiles "
            "brillantes — la nébuleuse garde tout le détail de L. Le seuil du "
            "masque est un multiple de σ au-dessus du fond : 10-20 masque les "
            "étoiles brillantes sans toucher la nébulosité ; l'AUGMENTER (plus "
            "sélectif) si trop de détail part, le BAISSER si un halo survit. "
            "Décoché (défaut) : combine d'avant le jalon 117c (halos visibles). "
            "Ne s'applique qu'en LRGB, avec un dossier L non vide."),
            foreground="#888888", wraplength=310).pack(anchor="w")
        # Jalon 45/47 : le choix de cadence est COMMUN aux deux modes —
        # voir le cadre unique `frm_rafale` (plus de combobox ici).
        # --- Jalon J2 (v2.88.0) : CADRE « FUSION Ha » -------------------------
        # Le rôle Ha de RGB+Ha / LRGB+Ha n'alimente AUCUN canal : il est AJOUTÉ
        # au ROUGE du composite, après le combine L. Le cadre est MONTRÉ
        # SEULEMENT quand la composition contient un Ha fusionné (arbitrage figé
        # du 15/10/2026) — c'est `_maj_fusion_ha()` (app.py) qui le pack/forget,
        # ici il est construit mais PAS packé. Le J3 ajoutera les autres modes
        # (fondu, écran, éclaircir, luminance) et le J4 le continuum : la liste
        # des modes est lue dans `MODES_FUSION_HA`, jamais recopiée.
        self.frm_fusion_ha = ttk.LabelFrame(box, text="Fusion Ha")
        row_fm = ttk.Frame(self.frm_fusion_ha)
        row_fm.pack(fill="x", padx=4, pady=(2, 0))
        ttk.Label(row_fm, text="Mode :").pack(side="left")
        self.var_fusion_ha_mode = tk.StringVar(value=FUSION_HA_DEFAUT)
        self.cb_fusion_ha = ttk.Combobox(row_fm,
                                         textvariable=self.var_fusion_ha_mode,
                                         state="readonly", width=14,
                                         values=list(MODES_FUSION_HA))
        self.cb_fusion_ha.pack(side="left", padx=(4, 0))
        self.cb_fusion_ha.bind("<<ComboboxSelected>>",
                               lambda e: self._on_fusion_ha())
        # --- J3 (v2.89.0) : profondeur du FONDU (α). N'agit que sur le mode
        # `fondu_rouge` ; le Spinbox est DÉSACTIVÉ pour les autres modes
        # (`_maj_fusion_ha()`), mais sa valeur est TOUJOURS lue et persistée :
        # changer de mode ne doit pas perdre le réglage.
        row_fa = ttk.Frame(self.frm_fusion_ha)
        row_fa.pack(fill="x", padx=4, pady=(2, 0))
        ttk.Label(row_fa, text="Fondu α (mode fondu) :").pack(side="left")
        self.var_fusion_ha_alpha = tk.DoubleVar(value=ALPHA_HA_DEFAUT)
        self.sp_fusion_ha_alpha = ttk.Spinbox(
            row_fa, from_=ALPHA_HA_MIN, to=ALPHA_HA_MAX, increment=0.05,
            width=6, textvariable=self.var_fusion_ha_alpha,
            command=self._on_fusion_ha)
        self.sp_fusion_ha_alpha.pack(side="left", padx=(4, 0))
        self.sp_fusion_ha_alpha.bind("<Return>", lambda e: self._on_fusion_ha())
        self.sp_fusion_ha_alpha.bind("<FocusOut>",
                                     lambda e: self._on_fusion_ha())
        row_fp = ttk.Frame(self.frm_fusion_ha)
        row_fp.pack(fill="x", padx=4, pady=(2, 0))
        ttk.Label(row_fp, text="Poids du Ha :").pack(side="left")
        self.var_fusion_ha_poids = tk.DoubleVar(value=POIDS_HA_DEFAUT)
        self.sp_fusion_ha_poids = ttk.Spinbox(
            row_fp, from_=POIDS_HA_MIN, to=POIDS_HA_MAX, increment=0.1,
            width=6, textvariable=self.var_fusion_ha_poids,
            command=self._on_fusion_ha)
        self.sp_fusion_ha_poids.pack(side="left", padx=(4, 0))
        # La saisie au clavier (Entrée ou perte de focus) applique aussi — la
        # flèche du Spinbox ne suffit pas (même règle qu'au lissage LRGB).
        self.sp_fusion_ha_poids.bind("<Return>",
                                     lambda e: self._on_fusion_ha())
        self.sp_fusion_ha_poids.bind("<FocusOut>",
                                     lambda e: self._on_fusion_ha())
        # --- CONTINUUM (J2, demande d'Alain du 18/10 : pouvoir l'ACTIVER ou le
        # COUPER dès maintenant, pour juger AVEC et SANS — et ne pas attribuer
        # au Ha un défaut qui n'est que du continuum non soustrait). Référence
        # = couche R (jamais L), bandes passantes Ha 7 nm / R 100 nm, force Q.
        # DÉSACTIVÉ quand aucun dossier R n'est renseigné (il n'y a alors rien
        # pour estimer le continuum) — `_maj_fusion_ha()`.
        self.var_fusion_ha_continuum = tk.BooleanVar(
            value=CONTINUUM_HA_DEFAUT)
        self.chk_fusion_ha_continuum = ttk.Checkbutton(
            self.frm_fusion_ha, text="Soustraire le continuum (référence R)",
            variable=self.var_fusion_ha_continuum,
            command=self._on_fusion_ha)
        self.chk_fusion_ha_continuum.pack(anchor="w", padx=4, pady=(4, 0))
        row_fq = ttk.Frame(self.frm_fusion_ha)
        row_fq.pack(fill="x", padx=4, pady=(2, 0))
        ttk.Label(row_fq, text="Force Q du continuum :").pack(side="left")
        self.var_fusion_ha_q = tk.DoubleVar(value=Q_HA_DEFAUT)
        self.sp_fusion_ha_q = ttk.Spinbox(
            row_fq, from_=Q_HA_MIN, to=Q_HA_MAX, increment=0.05,
            width=6, textvariable=self.var_fusion_ha_q,
            command=self._on_fusion_ha)
        self.sp_fusion_ha_q.pack(side="left", padx=(4, 0))
        self.sp_fusion_ha_q.bind("<Return>", lambda e: self._on_fusion_ha())
        self.sp_fusion_ha_q.bind("<FocusOut>", lambda e: self._on_fusion_ha())
        ttk.Label(self.frm_fusion_ha, text=(
            "Principe : le Ha est FUSIONNÉ au composite — "
            "résultat = composite + poids × (mode − composite). Poids 1 = le "
            "mode tel quel, 0 = aucun effet, au-delà de 1 on le renforce. "
            "MODES : ajout_rouge (ajout pur au rouge), fondu_rouge (mélange "
            "rouge ↔ Ha réglé par α), ecran_rouge (écran : monte sans écraser), "
            "eclaircir_rouge (garde le plus clair de R et du Ha), "
            "ha_luminance (le Ha éclaire le ROUGE de l'objet, à proportion de "
            "son signal — le fond du ciel garde son niveau). Le Ha est recentré "
            "sur son propre fond, donc le fond du ciel ne dérive pas ; les CINQ "
            "modes laissent VERT et BLEU intacts. "
            "CONTINUUM : un filtre Ha de 7 nm laisse passer "
            "aussi la lumière blanche de l'objet et du ciel ; la case le "
            "retranche (estimé sur R, ramené par 7 nm / 100 nm, réglé par Q, "
            "puis écrêté à [0 ; 1]) — la COUPER permet de comparer, mais un "
            "défaut vu sans elle peut n'être que du continuum non soustrait. "
            "Elle se désactive si aucun dossier R n'est renseigné. "
            "S'applique aux compositions RGB+Ha et LRGB+Ha."),
            foreground="#888888", wraplength=300).pack(anchor="w", padx=4,
                                                       pady=(2, 4))
        self._on_compo()    # pré-remplit les lignes de rôle de la compo par défaut
