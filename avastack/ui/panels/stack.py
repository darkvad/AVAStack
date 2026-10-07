# -*- coding: utf-8 -*-
"""Panneau « Empilement » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105b du chantier de refactoring. La
méthode `_poser_panneau_empilement` est reprise VERBATIM : `App` hérite de
`PanneauEmpilement`, donc `self` reste l'instance `App` et le comportement
(stats, seeing, nom de cible, réinitialisation/re-stack/référence, astrométrie +
annotation des objets, catalogues & données SPCC, photométrie, SPCC, rejet
kappa-sigma/Winsorized, équilibrage des canaux, recalage colorimétrique Linear
Fit, filtre anti-brutes floues) est inchangé AU BIT.

PIÈGE ÉVITÉ : les cases d'annotation lisent `CONFIG`. Comme `ui/widgets/
collapsible.py` (correctif du jalon 105a), la lecture passe par
`_globals_app()` — résolution TARDIVE des globals de `avastack.ui.app` : les
mocks des bancs (`ui.CONFIG`) restent EFFECTIFS et le vrai `config.json` n'est
jamais écrit pendant un test. En production, c'est le MÊME objet que
`avastack.config.CONFIG` (comportement identique AU BIT).

Les attributs d'interface (variables Tk, widgets, état, méthodes de l'hôte) sont
DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import queue
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


def _globals_app():
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    Écho du correctif du jalon 105a (`ui/widgets/collapsible.py`) : les bancs
    remplacent `avastack.ui.app.CONFIG` pour intercepter le vrai config.json.
    Lire ce global au MOMENT DE L'APPEL préserve cette interception ; en
    production c'est le MÊME objet que `avastack.config.CONFIG`."""
    from .. import app as _app              # import TARDIF (évite le cycle)
    return _app


class PanneauEmpilement:
    """Mixin : panneau « Empilement » (cf. docstring du module)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    # Constantes de `App`.
    SPCC_TYPE_MONO: str
    SPCC_TYPE_OSC: str

    # État de l'hôte consommé par ce panneau.
    rejet_fenetre: int
    var_nom_cible_manual: tk.Variable
    FIT_METHODES: tuple[tuple[str, str], ...]

    # Widgets créés par ce panneau.
    _lf_empilement: tk.Frame
    lbl_stats: ttk.Label
    lbl_seeing: ttk.Label
    cb_ref_refresh: ttk.Combobox
    lbl_restack: ttk.Label
    lbl_astro: ttk.Label
    lbl_cat_dossier: ttk.Label
    btn_cat_dl: ttk.Button
    btn_celebres_dl: ttk.Button
    lbl_cat_etat: ttk.Label
    btn_spectres: ttk.Button
    btn_spectres_tous: ttk.Button
    btn_spcc_base: ttk.Button
    btn_spcc_dos: ttk.Button
    lbl_base_spcc: ttk.Label
    lbl_photo: ttk.Label
    lbl_photo_gains: ttk.Label
    chk_spcc: ttk.Checkbutton
    lbl_spcc: ttk.Label
    cb_rejet: ttk.Combobox
    cb_fenetre: ttk.Combobox
    cb_fit_methode: ttk.Combobox
    lbl_fit: ttk.Label

    # Variables Tk (déclarées larges : `Variable` couvre IntVar/StringVar/
    # DoubleVar/BooleanVar).
    var_ref_refresh: tk.Variable
    var_astro: tk.Variable
    var_astro_ra: tk.Variable
    var_astro_dec: tk.Variable
    var_astro_champ: tk.Variable
    var_annoter_objets: tk.Variable
    var_annoter_etoiles: tk.Variable
    var_seuil_mag_etoiles: tk.Variable
    var_annoter_visibles: tk.Variable
    var_annoter_sauvegarde: tk.Variable
    var_photo: tk.Variable
    var_photo_gains: tk.Variable
    var_spcc: tk.Variable
    var_spcc_type: tk.Variable
    var_kappa: tk.Variable
    var_rejet: tk.Variable
    var_fenetre: tk.Variable
    var_wb: tk.Variable
    var_wb_force: tk.Variable
    var_fit: tk.Variable
    var_fit_methode: tk.Variable
    var_rejeter_flou: tk.Variable

    # État interne et collectives.
    _cat_q: queue.Queue[Any]
    _cat_dl_actif: bool
    _spcc_dispo: bool
    _spcc_noms: dict[str, Any]
    _spcc_vars: dict[str, tk.Variable]
    _spcc_lbls: dict[str, ttk.Label]
    _spcc_cbs: dict[str, ttk.Combobox]

    # Méthodes de l'hôte appelées par ce panneau.
    _creer_section_pliable: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _reset_empilement: Callable[..., Any]
    _montrer_restack_hist: Callable[..., Any]
    _on_ref_refresh: Callable[..., Any]
    _on_astro: Callable[..., Any]
    _lire_indices_image: Callable[..., Any]
    _on_annoter: Callable[..., Any]
    _choisir_dossier_catalogues: Callable[..., Any]
    _telecharger_catalogue: Callable[..., Any]
    _telecharger_celebres: Callable[..., Any]
    _telecharger_spectres: Callable[..., Any]
    _telecharger_spectres_tous: Callable[..., Any]
    _telecharger_base_spcc: Callable[..., Any]
    _choisir_dossier_spcc: Callable[..., Any]
    _on_photo: Callable[..., Any]
    _on_photo_gains: Callable[..., Any]
    _spcc_base_bornee: Callable[..., Any]
    _on_spcc: Callable[..., Any]
    _on_spcc_type: Callable[..., Any]
    _on_kappa: Callable[..., Any]
    _on_rejet: Callable[..., Any]
    _on_wb: Callable[..., Any]
    _on_linear_fit: Callable[..., Any]
    _on_rejeter_flou: Callable[..., Any]

    # --- Jalon 105b : construction du panneau « Empilement » -----------------
    def _poser_panneau_empilement(self, parent: tk.Misc) -> None:
        """Cadre « Empilement » : stats, seeing, nom de cible, réinitialisation,
        re-stack, astrométrie + annotation, catalogues & données SPCC,
        photométrie, SPCC, rejet, équilibrage, Linear Fit, filtre flou."""
        # --- Empilement
        self._lf_empilement, box, _, _ = self._creer_section_pliable(
            parent, "empilement")
        self.lbl_stats = ttk.Label(box, text="Frames : 0\nPixels rejetés (σ) : 0"
                                             "\nFrames non alignées : 0\nAlign. : —")
        self.lbl_stats.pack(anchor="w", pady=(0, 3))
        # Jalon 10 : seeing live (FWHM médiane + nombre d'étoiles) — mesure
        # faite par le thread d'acquisition sur l'aperçu, toutes les 3 s.
        self.lbl_seeing = ttk.Label(box, text="Seeing (FWHM) : —",
                                    foreground="#888888")
        self.lbl_seeing.pack(anchor="w", pady=(0, 3))
        # Champ « Nom cible » (reprend la valeur saisissable du panneau Astrométrie)
        row_nom = ttk.Frame(box)
        row_nom.pack(fill="x", pady=(2, 0))
        ttk.Label(row_nom, text="Nom cible :").pack(side="left", padx=(6, 0))
        # self.var_nom_cible_manual existe déjà (créé dans le panneau Astrométrie)
        ttk.Entry(row_nom, textvariable=self.var_nom_cible_manual, width=30).pack(side="left", padx=(2, 0), fill="x", expand=True)
        rowf = ttk.Frame(box)
        rowf.pack(fill="x", pady=2)
        # v2.41.0 : ce bouton fait une VRAIE remise à zéro (cf.
        # _reset_empilement) — il ne se contente plus de poser un drapeau que
        # le worker ne lisait qu'en TRAITANT une frame (constat d'Alain,
        # 28/09/2026 : « il faudrait que le bouton réinitialiser réinitialise
        # vraiment »).
        ttk.Button(rowf, text="Réinitialiser l'empilement",
                   command=self._reset_empilement
                   ).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(rowf, text="Réf. = empilement",
                   command=lambda: setattr(self, "ref_request", True)
                   ).pack(side="left", expand=True, fill="x", padx=1)
        # Jalon 13 : rafraîchissement AUTOMATIQUE de la référence
        # d'alignement — la dérive lente (flexure, erreur périodique)
        # éloigne les frames de la référence initiale et l'appariement
        # dégénère ; une référence jeune (l'empilement courant) suit.
        # « jamais » = ancien comportement (référence figée).
        rowr = ttk.Frame(box)
        rowr.pack(fill="x", pady=2)
        ttk.Label(rowr, text="Rafraîchir la référence (frames) :").pack(side="left")
        self.var_ref_refresh = tk.StringVar(value="20")
        self.cb_ref_refresh = ttk.Combobox(
            rowr, textvariable=self.var_ref_refresh, state="readonly", width=6,
            values=["jamais", "10", "20", "30", "50"])
        self.cb_ref_refresh.pack(side="left", padx=4)
        self.cb_ref_refresh.bind("<<ComboboxSelected>>",
                                 lambda e: self._on_ref_refresh())
        # Jalon 16 : re-stack « à la Siril » — re-ancre l'alignement sur la
        # meilleure brute archivée (score = nb d'étoiles) et RECALCULE tout
        # l'empilement depuis l'archive. Déclencheur auto : une brute bat
        # nettement la référence courante ; ce bouton force le recalcul.
        ttk.Button(box, text="⟳ Re-stacker (meilleure brute)",
                   command=lambda: setattr(self, "restack_request", True)
                   ).pack(fill="x", pady=2)
        # Jalon 18 : ligne d'état DÉDIÉE au re-stack (retour réel d'Alain :
        # « pas simple de voir le restack » — le message de la ligne
        # d'alignement est écrasé par la frame suivante) + bouton « ⓘ » =
        # historique horodaté des re-stacks de la session. Gris = rien,
        # vert = re-stack réussi, ambre = échec.
        row_rs = ttk.Frame(box)
        row_rs.pack(fill="x", pady=(2, 0))
        # v2.38.10 : le bouton « ⓘ » est posé EN PREMIER (`side="right"`) et le
        # texte prend ce qui reste. POURQUOI : `pack` alloue dans l'ordre de
        # pose et ABANDONNE le widget qui ne trouve plus de place — mesuré sur
        # cette ligne, un message de re-stack long (≈110 caractères) faisait
        # disparaître le bouton ⓘ (requête 28 px, allocation 0). Posé en
        # premier, il ne peut plus être sacrifié ; le texte, lui, est rogné.
        ttk.Button(row_rs, text="ⓘ", width=3,
                   command=self._montrer_restack_hist).pack(side="right",
                                                            padx=(4, 0))
        self.lbl_restack = ttk.Label(row_rs, text="Re-stack : —",
                                     foreground="#888888", wraplength=250)
        self.lbl_restack.pack(side="left", fill="x", expand=True)
        # Jalon 56 : ASTROMÉTRIE de l'empilement — case + indices de la cible.
        # Le solveur interne résout l'astrométrie UNE fois sur l'empilement
        # (ces indices l'y aident), puis le WCS est PROPAGÉ à chaque
        # réempilement. En mode dossier, les champs peuvent rester VIDES : des
        # indices sont alors lus dans l'en-tête des brutes (OBJCTRA/OBJCTDEC).
        # Interprétation : « 0h42m44s » ou « 00 42 44 » = HEURES (« 0.7123h »
        # aussi) ; un décimal nu (« 10.68333 ») = DEGRÉS. La ligne d'état
        # rappelle les indices retenus — aucune interprétation silencieuse.
        # v2.38.10 : TROIS lignes au lieu d'une. Mesure (constat d'Alain,
        # 27/09/2026 : « le champ et le bouton pour récupérer les coordonnées
        # depuis les brutes ne sont pas visibles sans agrandir la colonne ») :
        # les huit widgets de cette ligne demandaient ≈490 px pour 318 px
        # disponibles → `pack` ABANDONNAIT les deux derniers, le champ
        # « champ° » et le bouton 📷, sans aucun message. Une ligne de contrôles
        # à taille FIXE ne sait pas se replier : elle se répartit sur plusieurs
        # lignes (la case d'abord, puis AD/Dec, puis champ° + le bouton 📷).
        row_a = ttk.Frame(box)
        row_a.pack(fill="x", pady=(4, 0))
        self.var_astro = tk.BooleanVar(value=False)
        ttk.Checkbutton(row_a, text="Astrométrie", variable=self.var_astro,
                        command=self._on_astro).pack(side="left")
        row_ad = ttk.Frame(box)
        row_ad.pack(fill="x", pady=(2, 0))
        ttk.Label(row_ad, text="AD :").pack(side="left", padx=(6, 0))
        self.var_astro_ra = tk.StringVar(value="")
        e_ra = ttk.Entry(row_ad, textvariable=self.var_astro_ra, width=11)
        e_ra.pack(side="left", padx=(2, 0))
        ttk.Label(row_ad, text="Dec :").pack(side="left", padx=(4, 0))
        self.var_astro_dec = tk.StringVar(value="")
        e_dec = ttk.Entry(row_ad, textvariable=self.var_astro_dec, width=11)
        e_dec.pack(side="left", padx=(2, 0))
        row_ch = ttk.Frame(box)
        row_ch.pack(fill="x", pady=(2, 0))
        ttk.Label(row_ch, text="champ° :").pack(side="left", padx=(6, 0))
        self.var_astro_champ = tk.StringVar(value="")
        e_ch = ttk.Entry(row_ch, textvariable=self.var_astro_champ, width=6)
        e_ch.pack(side="left", padx=(2, 0))
        # Bouton : lire AD/Dec/champ depuis l'image courante (dernière brute
        # reçue ou dernier empilement sauvegardé) — remplit les trois champs.
        ttk.Button(row_ch, text="📷", width=3,
                   command=self._lire_indices_image).pack(side="left",
                                                          padx=(6, 0))
        # Les champs sont relus à la VALIDATION (Entrée / sortie du champ) —
        # pas à chaque frappe : un indice à moitié tapé serait refusé pour rien.
        for e in (e_ra, e_dec, e_ch):
            e.bind("<Return>", lambda ev: self._on_astro())
            e.bind("<FocusOut>", lambda ev: self._on_astro())
        self.lbl_astro = ttk.Label(box, text="Astrométrie : —",
                                   foreground="#888888", wraplength=310)
        self.lbl_astro.pack(anchor="w", pady=(2, 0))

        # Jalon 96 (étapes 5-6) : annotation temps-réel de l'image AFFICHÉE.
        # Deux cases INDÉPENDANTES (l'une peut vivre seule) + seuil de
        # magnitude des étoiles, et l'option du PNG compagnon à la sauvegarde.
        # L'annotation exige un WCS résolu : tant que l'astrométrie n'est pas
        # verte, rien n'est dessiné (la ligne d'état au-dessus le montre déjà).
        # Persistance comme les autres cases (booléens EXPLICITES).
        row_an = ttk.Frame(box)
        row_an.pack(fill="x", pady=(4, 0))
        self.var_annoter_objets = tk.BooleanVar(
            value=bool(_globals_app().CONFIG.get("annoter_objets", False)))
        ttk.Checkbutton(row_an, text="Annoter objets célèbres",
                        variable=self.var_annoter_objets,
                        command=self._on_annoter).pack(side="left")
        self.var_annoter_etoiles = tk.BooleanVar(
            value=bool(_globals_app().CONFIG.get("annoter_etoiles", False)))
        ttk.Checkbutton(row_an, text="Étoiles brillantes",
                        variable=self.var_annoter_etoiles,
                        command=self._on_annoter).pack(side="left", padx=(6, 0))
        row_an2 = ttk.Frame(box)
        row_an2.pack(fill="x", pady=(2, 0))
        ttk.Label(row_an2, text="Seuil mag :").pack(side="left", padx=(6, 0))
        self.var_seuil_mag_etoiles = tk.StringVar(
            value=f"{float(_globals_app().CONFIG.get('seuil_mag_etoiles', 8.0)):.1f}")
        e_seuil = ttk.Entry(row_an2, textvariable=self.var_seuil_mag_etoiles,
                            width=5)
        e_seuil.pack(side="left", padx=(2, 0))
        e_seuil.bind("<Return>", lambda ev: self._on_annoter())
        e_seuil.bind("<FocusOut>", lambda ev: self._on_annoter())
        row_an3 = ttk.Frame(box)
        row_an3.pack(fill="x", pady=(2, 0))
        # v2.56.0 (demande d'Alain, 05/10/2026) : ne pas entourer ce qui
        # n'est pas résolu sur l'image (ex. NGC 206) — l'étiquette reste,
        # seul l'entourage est conditionné à la détection réelle.
        self.var_annoter_visibles = tk.BooleanVar(
            value=bool(_globals_app().CONFIG.get("annoter_visibles", True)))
        ttk.Checkbutton(row_an3, text="Seulement les objets visibles",
                        variable=self.var_annoter_visibles,
                        command=self._on_annoter).pack(side="left")
        self.var_annoter_sauvegarde = tk.BooleanVar(
            value=bool(_globals_app().CONFIG.get("annoter_sauvegarde", True)))
        ttk.Checkbutton(row_an3, text="PNG annoté à côté du FITS",
                        variable=self.var_annoter_sauvegarde,
                        command=self._on_annoter).pack(side="left", padx=(6, 0))

        # Jalon 70 — DONNÉES de l'astrométrie : l'application DIT où elle
        # cherche le catalogue Gaia DR3 de Siril, laisse choisir un autre
        # dossier (config `chemin_catalogues`), et le télécharge (1,1 Go,
        # reprise + sha256 vérifié). Sans catalogue, l'astrométrie interne ne
        # peut pas aboutir : le dire ici évite l'échec silencieux constaté
        # sous Linux le 27/09/2026.
        # v2.38.10 : DEUX lignes (le chemin, puis les boutons). MESURE : le
        # libellé du chemin, insécable (un chemin n'a pas d'espace, donc
        # `wraplength` ne le replie PAS), prenait toute la ligne → avec un chemin
        # long comme `~/.local/share/siril`, `pack` ABANDONNAIT 📂 et « ⬇ Gaia ».
        # Le texte est en plus BORNÉ en caractères (`width`), ce qui garantit
        # qu'il ne peut plus manger la ligne.
        row_cat = ttk.Frame(box)
        row_cat.pack(fill="x", pady=(2, 0))
        self.lbl_cat_dossier = ttk.Label(row_cat, text="Catalogues : —",
                                         foreground="#888888", width=44,
                                         anchor="w")
        self.lbl_cat_dossier.pack(side="left")
        row_cat_b = ttk.Frame(box)
        row_cat_b.pack(fill="x", pady=(2, 0))
        ttk.Button(row_cat_b, text="📂 Dossier", width=12,
                   command=self._choisir_dossier_catalogues).pack(side="left",
                                                                  padx=(6, 0))
        self.btn_cat_dl = ttk.Button(row_cat_b, text="⬇ Gaia", width=9,
                                     command=self._telecharger_catalogue)
        self.btn_cat_dl.pack(side="left", padx=(4, 0))
        self.btn_celebres_dl = ttk.Button(row_cat_b, text="⬇ Célèbres", width=10,
                                          command=self._telecharger_celebres)
        self.btn_celebres_dl.pack(side="left", padx=(4, 0))
        self.lbl_cat_etat = ttk.Label(box, text="", foreground="#888888",
                                      wraplength=310)
        self.lbl_cat_etat.pack(anchor="w")
        # Jalon 77 — LES DONNÉES DE LA SPCC SANS SIRIL. Mesure d'un besoin : il
        # manquait DEUX jeux de données (les 48 morceaux de spectres Gaia XP,
        # dont la fonction de téléchargement n'était branchée nulle part, et la
        # base de profils de capteurs/filtres, qui n'était LUE que chez Siril) :
        # sans eux, la SPCC exigeait Siril installé. Chacun a SA ligne, avec
        # DEUX boutons au plus (règle de mise en page v2.38.9 : `pack` abandonne
        # silencieusement le widget qui ne tient plus) et un état qui DIT ce qui
        # est présent — jamais de bouton muet.
        row_sp = ttk.Frame(box)
        row_sp.pack(fill="x", pady=(4, 0))
        self.btn_spectres = ttk.Button(row_sp, text="⬇ Spectres (champ)",
                                       width=17,
                                       command=self._telecharger_spectres)
        self.btn_spectres.pack(side="left", padx=(6, 0))
        self.btn_spectres_tous = ttk.Button(row_sp, text="⬇ les 48", width=9,
                                            command=self._telecharger_spectres_tous)
        self.btn_spectres_tous.pack(side="left", padx=(4, 0))
        row_sp2 = ttk.Frame(box)
        row_sp2.pack(fill="x", pady=(2, 0))
        self.btn_spcc_base = ttk.Button(row_sp2, text="⬇ Base SPCC", width=13,
                                        command=self._telecharger_base_spcc)
        self.btn_spcc_base.pack(side="left", padx=(6, 0))
        self.btn_spcc_dos = ttk.Button(row_sp2, text="📂 Dossier SPCC", width=15,
                                       command=self._choisir_dossier_spcc)
        self.btn_spcc_dos.pack(side="left", padx=(4, 0))
        self.lbl_base_spcc = ttk.Label(box, text="", foreground="#888888",
                                       wraplength=310)
        self.lbl_base_spcc.pack(anchor="w")
        # File de la conversation réseau → UI (le thread de téléchargement n'a
        # PAS le droit de toucher un widget : il ne pose que des messages ici).
        self._cat_q = queue.Queue()
        self._cat_dl_actif = False
        # v2.38.11 : la ligne « Catalogues » (dossier + présence du catalogue)
        # demande des `listdir`/`glob` sur des dossiers qui peuvent être sur un
        # NAS : plus de sonde ICI (avant l'affichage). Le fil de mesures la
        # remplit APRÈS l'ouverture, borné ; l'appel direct reste pour un geste
        # de l'utilisateur (bouton 📂, téléchargement terminé).
        # Jalon 56 (étape 4) : PHOTOMÉTRIE — zéro-point instrumental par BANDE,
        # mesuré sur l'empilement via le WCS (appariement mutuel des étoiles au
        # catalogue Gaia de Siril). Case SÉPARÉE et cochée par défaut : la
        # mesure n'a AUCUN effet sur l'image (l'application aux gains est
        # l'étape 5) — la décocher arrête simplement la mesure et son état.
        row_p = ttk.Frame(box)
        row_p.pack(fill="x", pady=(2, 0))
        self.var_photo = tk.BooleanVar(value=True)
        ttk.Checkbutton(row_p, text="Photométrie (zéro-point Gaia)",
                        variable=self.var_photo,
                        command=self._on_photo).pack(side="left")
        self.lbl_photo = ttk.Label(box, text="Photométrie : —",
                                   foreground="#888888", wraplength=310)
        self.lbl_photo.pack(anchor="w", pady=(2, 0))
        # Jalon 56 (étape 5) : APPLICATION des gains photométriques au
        # composite — case SÉPARÉE, DÉCOCHÉE PAR DÉFAUT (opt-in d'Alain) : la
        # mesure ci-dessus n'a aucun effet tant que celle-ci n'est pas cochée.
        # Elle n'agit qu'en COMPOSITION (un gain global en mono n'a pas de sens
        # et déréglerait VeraLux, qui travaille en valeurs absolues).
        row_pg = ttk.Frame(box)
        row_pg.pack(fill="x", pady=(2, 0))
        self.var_photo_gains = tk.BooleanVar(value=False)
        ttk.Checkbutton(row_pg, text="Gains photométriques (Gaia)",
                        variable=self.var_photo_gains,
                        command=self._on_photo_gains).pack(side="left")
        self.lbl_photo_gains = ttk.Label(box, text="", foreground="#888888")
        self.lbl_photo_gains.pack(anchor="w")
        # Jalon 58 : SPCC ABSOLUE « à la Siril » — case SÉPARÉE, DÉCOCHÉE PAR
        # DÉFAUT (opt-in, même choix qu'Alain pour les gains Gaia) : elle
        # remplace les gains Gaia par des coefficients calculés à partir des
        # SPECTRES Gaia et des PROFILS capteur/filtres de la base Siril. Sans
        # cette base (non installée), la case est désactivée et le dit — jamais
        # une valeur inventée.
        row_sx = ttk.Frame(box)
        row_sx.pack(fill="x", pady=(4, 0))
        # Jalon 77 : la base de profils peut vivre AILLEURS que chez Siril (copie
        # d'AVAStack téléchargée, dossier choisi) — et ce dossier peut être sur
        # un NAS. La lecture qui remplit les sélecteurs est donc BORNÉE
        # (v2.38.11 : aucune mesure de disque ne doit retenir l'ouverture) ; la
        # sonde différée `_sonder_spcc_base` corrige l'affichage quand elle a
        # répondu, et la fin d'un téléchargement relit tout.
        self._spcc_dispo, self._spcc_noms, _mesure = self._spcc_base_bornee()
        self.var_spcc = tk.BooleanVar(value=False)
        self.chk_spcc = ttk.Checkbutton(
            row_sx, text="SPCC (couleurs absolues)",
            variable=self.var_spcc, command=self._on_spcc)
        self.chk_spcc.pack(side="left")
        if not self._spcc_dispo:
            self.chk_spcc.state(["disabled"])
        self._spcc_vars = {}
        self._spcc_lbls = {}
        self._spcc_cbs = {}
        # v2.40.0 : TYPE de capteur — la SPCC n'est PAS réservée au mono
        # multi-bandes (constat d'Alain, 28/09/2026 : « la case SPCC dit que
        # c'est que pour du mono multibande, alors que SPCC fonctionne en
        # couleurs dans Siril — il faut juste lui dire que c'est un capteur
        # couleur et le choisir »). Ligne AJOUTÉE au-dessus des cinq autres :
        # aucune ligne ne disparaît (règle de mise en page v2.38.9).
        ligne_t = ttk.Frame(box)
        ligne_t.pack(fill="x")
        ttk.Label(ligne_t, text="Type de capteur :", width=19).pack(side="left")
        self.var_spcc_type = tk.StringVar(value=self.SPCC_TYPE_MONO)
        cbt = ttk.Combobox(ligne_t, textvariable=self.var_spcc_type,
                           state="readonly", width=26,
                           values=[self.SPCC_TYPE_MONO, self.SPCC_TYPE_OSC])
        cbt.pack(side="left", fill="x", expand=True)
        cbt.bind("<<ComboboxSelected>>", lambda e: self._on_spcc_type())
        for cle, etiquette, defaut, largeur in (
                ("capteur", "Capteur", "Sony IMX585", 26),
                ("fr", "Filtre R", "QHYCCD MiniCam8M Red", 26),
                ("fg", "Filtre G", "QHYCCD MiniCam8M Green", 26),
                ("fb", "Filtre B", "QHYCCD MiniCam8M Blue", 26),
                ("blanc", "Référence de blanc", "Average Spiral Galaxy", 30)):
            ligne = ttk.Frame(box)
            ligne.pack(fill="x")
            lbl = ttk.Label(ligne, text=f"{etiquette} :", width=19)
            lbl.pack(side="left")
            self._spcc_lbls[cle] = lbl
            valeurs = self._spcc_noms.get(
                {"capteur": "capteur", "fr": "filtres", "fg": "filtres",
                 "fb": "filtres", "blanc": "blancs"}[cle], [])
            v = tk.StringVar(value=defaut)
            cb = ttk.Combobox(ligne, textvariable=v, state="readonly",
                              width=largeur, values=valeurs or [defaut])
            cb.pack(side="left", fill="x", expand=True)
            cb.bind("<<ComboboxSelected>>", lambda e: self._on_spcc())
            if not valeurs:
                cb.state(["disabled"])
            self._spcc_vars[cle] = v
            self._spcc_cbs[cle] = cb
        self.lbl_spcc = ttk.Label(box, text="", foreground="#888888",
                                  wraplength=330, justify="left")
        self.lbl_spcc.pack(anchor="w")
        ttk.Label(box, text="Rejet kappa-sigma :").pack(anchor="w")
        self.var_kappa = tk.StringVar(value="3σ")
        cb = ttk.Combobox(box, textvariable=self.var_kappa, state="readonly", width=8,
                          values=["Off", "2σ", "3σ", "4σ", "5σ"])
        cb.pack(anchor="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_kappa())
        # Méthode de rejet : kappa-sigma séquentiel (rapide, historique) ou
        # Winsorized (adaptation live du Winsorized Sigma Clipping de
        # PixInsight) — médiane/MAD d'une fenêtre glissante de frames
        # alignées, robuste aux traînées de satellites/météores.
        ttk.Label(box, text="Méthode de rejet :").pack(anchor="w")
        self.var_rejet = tk.StringVar(value="kappa-sigma (rapide)")
        self.cb_rejet = ttk.Combobox(box, textvariable=self.var_rejet, state="readonly",
                                     width=24,
                                     values=["kappa-sigma (rapide)",
                                             "Winsorized (satellites)"])
        self.cb_rejet.pack(anchor="w")
        self.cb_rejet.bind("<<ComboboxSelected>>", lambda e: self._on_rejet())
        rowwin = ttk.Frame(box)
        rowwin.pack(fill="x", pady=2)
        ttk.Label(rowwin, text="Fenêtre de référence (frames) :").pack(side="left")
        self.var_fenetre = tk.StringVar(value=str(self.rejet_fenetre))
        self.cb_fenetre = ttk.Combobox(rowwin, textvariable=self.var_fenetre,
                                       state="disabled", width=3,
                                       values=["4", "6", "8", "12", "16"])
        self.cb_fenetre.pack(side="left", padx=4)
        self.cb_fenetre.bind("<<ComboboxSelected>>", lambda e: self._on_rejet())
        # Jalon 13 : équilibrage des canaux (auto) — les capteurs couleur ont
        # 2 sites verts sur 4 (matrice de Bayer) et une réponse spectrale
        # déséquilibrée : l'empilement brut domine dans le vert (constat réel
        # NGC7023). Gains LINÉAIRES par canal égalisant le FOND du ciel (la
        # couleur des objets est préservée) ; tout ce qui sort de
        # l'empilement est équilibré (affichage, histogramme, sauvegardes,
        # traitements externes).
        self.var_wb = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Équilibrage des canaux (auto)",
                        variable=self.var_wb, command=self._on_wb
                        ).pack(anchor="w", pady=(2, 0))
        self.var_wb_force = tk.DoubleVar(value=1.0)
        self._add_slider(box, "Force de l'équilibrage",
                         self.var_wb_force, 0.0, 1.0, 0.05, self._on_wb, "{:.2f}")
        # Jalon 54 : recalage colorimétrique « Linear Fit » — R et B alignés
        # sur le VERT par une droite Gain + Offset (mesurée sur le composite
        # linéaire, réf. = vert). Neutralise le masque coloré (fond bleu dans
        # les poussières de M31, constat réel d'Alain) qui surgit à
        # l'étirement quand les fonds des filtres diffèrent. Appliqué au
        # composite (visu ET sauvegardes — le fichier linéaire reste un
        # float32 simple). DÉCOCHÉE par défaut (décision d'Alain) ; le
        # libellé montre les gains/offsets MESURÉS (règle : le réglage relu
        # n'est pas le réglage appliqué — seul l'effet physique prouve).
        self.var_fit = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Recalage colorimétrique (Linear Fit)",
                        variable=self.var_fit,
                        command=self._on_linear_fit).pack(anchor="w")
        # Jalon 54b (retour du test réel d'Alain) : le GAIN fondé sur le
        # rapport des bruits amplifie halos/bruit du canal bleu d'une image
        # OSC déjà équilibrée → aspect flou/décalé à l'étirement. DÉFAUT =
        # OFFSET SEUL (le fond) ; le gain reste disponible (palettes
        # narrowband, équivalent du Linear Fit d'APP).
        self.FIT_METHODES = (("Offset seul (fond)", "offset"),
                             ("Gain + offset", "gain_offset"))
        row_fm = ttk.Frame(box)
        row_fm.pack(fill="x")
        ttk.Label(row_fm, text="Méthode :").pack(side="left")
        self.var_fit_methode = tk.StringVar(value="Offset seul (fond)")
        self.cb_fit_methode = ttk.Combobox(
            row_fm, textvariable=self.var_fit_methode, state="readonly",
            width=17, values=[lib for lib, _ in self.FIT_METHODES])
        self.cb_fit_methode.pack(side="left", padx=4)
        self.cb_fit_methode.bind("<<ComboboxSelected>>",
                                 lambda e: self._on_linear_fit())
        self.lbl_fit = ttk.Label(box, text="", foreground="#888888")
        self.lbl_fit.pack(anchor="w")
        self._on_linear_fit()
        # Jalon 17 : filtre anti-brutes TRÈS défocalisées — rejet d'office
        # (décision d'Alain), cette case le désactive (les frames passent
        # comme avant le jalon 17 ; le compteur de rejets reste affiché).
        self.var_rejeter_flou = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Rejeter les frames floues (auto)",
                        variable=self.var_rejeter_flou,
                        command=self._on_rejeter_flou).pack(anchor="w")
