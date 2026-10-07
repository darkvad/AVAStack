# -*- coding: utf-8 -*-
"""Sections pliables de la colonne gauche (jalons 95/98/99) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 103 du chantier de refactoring. La
méthode `_creer_section_pliable` est reprise VERBATIM : `App` hérite de
`SectionsPliables`, donc `self` reste l'instance `App` et le comportement
(sections pliables persistées dans config.json, ordre de pack, flèche ▼/▶) est
inchangé AU BIT.

Les attributs d'interface (constantes de la classe `App`) sont DÉCLARÉS ici
pour le typage statique (`pyright`) — aucune valeur, aucune logique.
"""

import tkinter as tk
from tkinter import ttk, font as tkfont

from ...config import CONFIG, sauver_config


class SectionsPliables:
    """Mixin : sections pliables persistées (cf. docstring du module)."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS DE TYPAGE seulement.
    SECTIONS_NOM_MAP: dict[str, str]
    SECTION_TITRE_BG: str
    SECTION_TITRE_FG: str
    SECTION_TITRE_BG_ACTIF: str
    SECTION_CADRE: str
    _font_titre_section: tkfont.Font

    # --- Jalon 95 : création d'une section pliable persistée ------------------
    def _creer_section_pliable(
            self, parent: tk.Misc, cle_section: str,
            defaut_ouvert: bool = True
    ) -> tuple[tk.Frame, ttk.Frame, tk.BooleanVar, tk.Button]:
        """
        Crée une section pliable/dépliable avec persistance dans config.json.
        Retourne (labelframe, frame_contenu, var_etat, btn_header).
        - cle_section : clé dans SECTIONS_NOM_MAP (ex: "camera")
        - Le titre affiché vient de SECTIONS_NOM_MAP[cle_section]
        - L'état est sauvé dans CONFIG["ui_section_<cle_section>"] (bool)
        - Le CONTENEUR EXTERNE (porteur encadré) est packé dans parent quand
          ouvert ; le bouton d'en-tête reste TOUJOURS visible dans parent.
        Jalon 99 (choix d'Alain, variante « B+ » de la maquette du 06/10) :
        en-tête en bouton Tk CLASSIQUE (fond bleu très clair, texte bleu
        foncé gras — le thème ttk « vista » ignore le fond des ttk.Button)
        et cadre du contenu matérialisé par un FILET de 2 px. Le widget
        retourné en premier est le PORTEUR : c'est lui qui est packé/dépacké
        (dans on_change et dans _maj_visibilite_cadres), la bordure suit
        donc TOUJOURS le contenu qu'elle entoure ; le LabelFrame interne ne
        sert plus qu'au rembourrage.
        """
        titre = self.SECTIONS_NOM_MAP.get(cle_section, cle_section)
        cle_config = f"ui_section_{cle_section}"

        # Variable d'état (persistée)
        etat_ouvert = tk.BooleanVar(
            value=bool(CONFIG.get(cle_config, defaut_ouvert))
        )

        # Police des titres : dérivée de la police PAR DÉFAUT de la
        # plateforme (Segoe UI sur Windows, équivalents ailleurs — jamais de
        # fonte codée en dur), en gras.
        if not hasattr(self, "_font_titre_section"):
            self._font_titre_section = tkfont.nametofont("TkDefaultFont").copy()
            self._font_titre_section.configure(weight="bold")

        # Bouton d'en-tête (cliquable) avec flèche ▼/▶ — TOUJOURS visible
        def maj_icone(*_):
            btn.config(text=("▼ " if etat_ouvert.get() else "▶ ") + titre)

        def toggle(*_):
            etat_ouvert.set(not etat_ouvert.get())
            # Persistance immédiate
            CONFIG[cle_config] = etat_ouvert.get()
            sauver_config(CONFIG)

        btn = tk.Button(
            parent,
            command=toggle,
            anchor="w", relief="flat", bd=0, highlightthickness=0,
            cursor="hand2",
            bg=self.SECTION_TITRE_BG, fg=self.SECTION_TITRE_FG,
            activebackground=self.SECTION_TITRE_BG_ACTIF,
            activeforeground=self.SECTION_TITRE_FG,
            font=self._font_titre_section, padx=6, pady=3,
        )
        # NB : PAS de binds <Return>/<space> explicites — un bouton Tk
        # classique les gère NATIVEMENT quand il a le focus (les doubler
        # ferait basculer la section deux fois).
        btn.pack(fill="x", pady=(3, 0))
        maj_icone()

        # Porteur = conteneur EXTERNE de la section (c'est LUI qui est
        # packé/dépacké) ; son filet de 2 px matérialise la section. Le
        # LabelFrame interne ne sert plus qu'au rembourrage du contenu.
        lf = tk.Frame(parent, bd=0, highlightthickness=2,
                      highlightbackground=self.SECTION_CADRE)
        # Jalon 99 bis : PAS de padx ici — la bordure highlight est tracée
        # HORS du widget, padx ajouterait 2 px perdus pour le contenu (banc
        # jalon 72 : des labels rognés de 4 px à cause de ce filet).
        inter = ttk.LabelFrame(lf, padding=7)
        inter.pack(fill="x")

        # Frame interne qui contiendra les vrais widgets
        contenu = ttk.Frame(inter)
        contenu.pack(fill="x")

        # Callback quand la variable change (pour maj icône + pack/unpack du LF)
        def on_change(*_):
            maj_icone()
            if etat_ouvert.get():
                if btn.winfo_manager():
                    # Packer le porteur APRÈS le bouton dans parent
                    lf.pack(fill="x", pady=(0, 3), after=btn)
                # sinon : la section est cachée par la source (jalon 98bis) —
                # le pli est MÉMORISÉ dans var_etat et sera appliqué au
                # prochain _maj_visibilite_cadres ; packer ici avec after=btn
                # lèverait « TclError: isn't packed » (en-tête dépacké).
            else:
                lf.pack_forget()
            # Force la mise à jour du scrollregion du canvas
            parent.update_idletasks()

        etat_ouvert.trace_add("write", on_change)
        # État initial
        if etat_ouvert.get():
            lf.pack(fill="x", pady=(0, 3), after=btn)

        # Attribut de compatibilité pour les bancs de test
        lf._contenu_interne = contenu  # pyright: ignore[reportAttributeAccessIssue]
        # Stocker le bouton d'en-tête pour pouvoir le cacher avec le LabelFrame
        lf._btn_header = btn  # pyright: ignore[reportAttributeAccessIssue]
        # Jalon 98 : stocker la variable d'état (True = déplié) —
        # `_maj_visibilite_cadres` doit RESPECTER l'état replié/déplié choisi
        # par l'utilisateur quand elle réaffiche une section (avant, elle
        # re-packait le contenu sans le consulter : une section repliée
        # réapparaissait dépliée, avec sa flèche ▶ menteuse).
        lf._var_etat = etat_ouvert  # pyright: ignore[reportAttributeAccessIssue]

        return lf, contenu, etat_ouvert, btn
