# -*- coding: utf-8 -*-
"""Rendu d'affichage et annotation de l'image — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 107 du chantier de refactoring. Ce
module regroupe tout ce qui DESSINE sur le Canvas d'image (`cv_img`) :

  - la SÉLECTION DE SOURCE (`_src_pleine_res`, `_src_rendu`,
    `_pleine_res_activee`, `_on_vl_pleine_res`) : l'aperçu 1600 px, ou l'image
    COMPLÈTE quand l'option « Rendu pleine résolution » est cochée ;
  - la CHAÎNE D'AFFICHAGE UNIQUE (`_rendre_et_afficher`, `_refresh_preview`) :
    source linéaire → étirement (STF / manuel / VeraLux) → étage de niveaux →
    gamma et saturations → écran, ET la mise à jour des deux histogrammes ;
  - le DESSIN et les GESTES du Canvas (`_show_image`, `_render`, zoom / pan,
    `_vider_ecran`) ;
  - l'ANNOTATION temps-réel (jalon 96) : objets célèbres + étoiles brillantes
    dessinés sur une COPIE du buffer (`_seuil_mag`, `_on_annoter`,
    `_forme_pleine`, `_wcs_affichage`, `_donnees_annotation`, `_annoter_image`,
    `_sauver_png_annote`).

Les méthodes sont reprises VERBATIM : `App` hérite de `Renderer`, donc `self`
reste l'instance `App` et le rendu est inchangé AU BIT. Seules les lectures de
`CONFIG` / `sauver_config` passent par `_globals_app()` (résolution TARDIVE) —
motif des jalons 104/105a : l'interception des bancs (`ui.CONFIG`,
`ui.sauver_config`) reste effective et le vrai config.json n'est jamais écrit
pendant un test.

Les attributs d'interface (constantes et variables Tk de la classe `App`) sont
DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur, aucune
logique.
"""

import os
from typing import Any, Callable

import numpy as np
import cv2
import tkinter as tk
from PIL import Image, ImageTk

from .. import catalogues as cat_mod
from ..images import save_image
from ..processing import DisplayProcessor
from ..processing import annotations as annoter_mod
from ..processing import photometrie as photo_mod


def _globals_app():
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    POURQUOI (jalon 107, écho des jalons 104/105a) : les bancs remplacent
    `avastack.ui.app.CONFIG` et `.sauver_config` pour INTERCEPTER le vrai
    config.json (ne jamais l'écrire pendant un test). Or l'annotation lit son
    état persisté (cases « annoter… », seuil de magnitude) ET l'écrit au
    changement : lire/crire ces globals au MOMENT DE L'APPEL préserve cette
    interception ; en production, c'est le MÊME objet que
    `avastack.config.CONFIG` / `avastack.config.sauver_config` (d'où un
    comportement identique AU BIT).
    """
    from . import app as _app              # import TARDIF (évite le cycle)
    return _app


class Renderer:
    """Mixin : rendu d'affichage à l'écran et annotation de l'image."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS DE TYPAGE seulement.
    # Constantes de classe.
    W_IMG: int
    H_IMG: int

    # Moteur d'affichage et Canvas d'image.
    disp: DisplayProcessor
    cv_img: tk.Canvas
    # Dernière image étirée affichée (`_last_disp`, tenue PROPRE par rapport à
    # l'annotation) et référence PhotoImage gardée en vie (anti-GC).
    _last_disp: Any
    _photo: Any

    # Zoom / pan.
    zoom: float
    view_cx: Any
    view_cy: Any
    _drag: Any

    # Sources et options de rendu.
    last_show: Any
    proc_full: Any
    _stack_pleine_res: Any
    _echelle_apercu: float
    pleine_res_ecran: bool
    var_view: tk.Variable
    var_vl_pleine_res: tk.Variable

    # Annotation (jalon 96).
    stacker: Any
    suivi_astro: Any
    _echelle_police_annot: Any
    _annote_cache: Any
    _annote_rendu: Any
    var_annoter_objets: tk.Variable
    var_annoter_etoiles: tk.Variable
    var_annoter_visibles: tk.Variable
    var_annoter_sauvegarde: tk.Variable
    var_seuil_mag_etoiles: tk.Variable

    # Méthodes de l'hôte (`App`, portées par d'autres mixins) appelées ici.
    _maj_histogrammes: Callable[..., None]

    # ============================= sélection de source =====================
    def _pleine_res_activee(self):
        """True si l'option « Rendu pleine résolution » de l'écran est cochée
        (v2.38.0).

        ATTENTION THREADS : l'état vit dans `self.pleine_res_ecran`, un simple
        attribut Python — la boucle d'acquisition et `_pousser_rendu` (threads de
        travail) l'interrogent pour mémoriser l'empilement COMPLET. Une variable
        Tk ne peut PAS être lue hors du thread d'interface
        (`RuntimeError: main thread is not in main loop`, constat réel du banc
        jalon 59 : la sauvegarde n'était plus produite), d'où ce miroir posé
        UNIQUEMENT par l'interface (`_on_vl_pleine_res`, restauration de config)."""
        return bool(getattr(self, "pleine_res_ecran", False))

    def _on_vl_pleine_res(self):
        """Case « Rendu pleine résolution (zoom fidèle) » (v2.38.0, demande
        d'Alain du 26/09/2026 : « sur l'écran, je veux pouvoir zoomer sur l'image
        pleine résolution »).

        Trois effets, et rien d'autre :
          - l'état est MIRÉ dans un attribut Python (`self.pleine_res_ecran`),
            seul lisible par les threads de travail (cf. `_pleine_res_activee`) ;
          - décochée : la copie pleine résolution de l'EMPILEMENT (25 Mo) est
            LIBÉRÉE. `proc_full` (résultat du ⚡ traitement externe) n'est PAS
            touché : il sert aux sauvegardes « résultat traité (linéaire) » et
            « tel que vu » en vue traitée, indépendamment de cette option ;
          - `notify_new_stack()` force un nouveau rendu — le cache du solveur
            VeraLux n'a pour clé que les RÉGLAGES, pas la résolution : sans ce
            drapeau, l'ancien rendu d'aperçu resservirait.
        Pendant le calcul (7 à 8 s), l'écran garde la dernière image."""
        v = getattr(self, "var_vl_pleine_res", None)
        self.pleine_res_ecran = bool(v.get()) if v is not None else False
        if not self.pleine_res_ecran:
            self._stack_pleine_res = None
        self.disp.notify_new_stack()
        self._refresh_preview()

    def _src_pleine_res(self):
        """Image LINÉAIRE pleine résolution de la VUE COURANTE (v2.38.1), ou
        None si elle n'existe pas encore.

        Vue « empilement » → `self._stack_pleine_res`, la copie de l'empilement
        COMPLET posée par la boucle d'acquisition (seul endroit du code qui a
        l'image entière sous la main).
        Vue « traitée » → `self.proc_full`, le résultat du ⚡ traitement externe :
        il est DÉJÀ mémorisé (sauvegardes « résultat traité (linéaire) » et
        « tel que vu » en vue traitée, cf. `_save_proc` / `_save_asseen`), donc
        l'écran peut s'en servir SANS copie supplémentaire — et il montre alors
        le même instantané que celui que le fichier contiendra.

        ⚠️ THREADS : `self.var_view` (variable Tk) ne se lit QUE depuis le thread
        d'interface ; cette méthode n'est appelée que par `_src_rendu`, lui-même
        réservé à l'UI (`_tick`, `_on_view`, `_refresh_preview`) — jamais par la
        boucle d'acquisition ni par un thread de travail."""
        if self.var_view.get() == "traitée":
            return self.proc_full
        return self._stack_pleine_res

    def _src_rendu(self, lineaire):
        """Image LINÉAIRE donnée à la chaîne d'affichage (v2.38.0 ; pleine
        résolution en vue « traitée » depuis la v2.38.1).

        Par défaut : `lineaire`, l'aperçu 1600 px — rapide (~1,7 s), mais la
        chaîne non linéaire (GraXpert, débruitage, netteté, couleurs, chroma,
        étirement) n'est alors PAS appliquée à la même échelle que pour le
        fichier : mesuré au jalon 66, écart moyen 0,015-0,023 et jusqu'à 0,49 aux
        cœurs d'étoiles — l'anneau de couleur des étoiles, lui, n'existe QUE dans
        les fichiers (l'aperçu l'écrase).

        Option « Rendu pleine résolution » COCHÉE (et image complète disponible
        pour la vue courante) : la MÊME chaîne est appliquée à l'image COMPLÈTE →
        l'écran montre exactement ce que le fichier contiendra, et le zoom
        recadre de VRAIS pixels. Coût mesuré : 7,2-8,3 s par recalcul complet
        (×4,3).

        v2.38.1 — la source suit la VUE (`_src_pleine_res`) : en vue « traitée »
        c'est le RÉSULTAT EXTERNE pleine résolution qui est rendu. Avant, la
        méthode rendait l'empilement complet quel que soit l'état de la vue : en
        vue « traitée », l'écran montrait donc l'EMPILEMENT au lieu du résultat
        du ⚡ (et le zoom « fidèle » ne portait pas sur l'image annoncée).

        Repli sur l'aperçu quand l'image complète de la vue n'existe pas encore :
        avant le premier empilement d'une session, ou en vue « traitée » avant le
        premier ⚡ traitement."""
        if self._pleine_res_activee():
            src = self._src_pleine_res()
            if src is not None:
                return src
        return lineaire

    # ============================= chaîne d'affichage ======================
    def _rendre_et_afficher(self, lineaire, live=True, hist=True):
        """Chaîne d'affichage COMPLÈTE et UNIQUE (jalon 75) : source linéaire →
        étirement (STF / manuel / VeraLux) → étage de niveaux → gamma et
        saturations → écran, ET mise à jour des deux histogrammes.

        Un seul point de passage pour les endroits qui affichaient une image :
        c'est ce qui garantit que l'histogramme décrit toujours ce qui est à
        l'écran (avant le jalon 75 le calcul vivait dans le thread
        d'acquisition, sur l'aperçu de l'empilement — donc jamais sur l'image
        d'une vue « traitée », et à ~55 ms par frame de CPU).
        """
        src = self._src_rendu(lineaire)
        img8 = self.disp.process(src, live=live)
        if hist:
            self._maj_histogrammes(src,
                                   getattr(self.disp, "dernier_brut_niveaux",
                                           None))
        self._show_image(img8)

    def _refresh_preview(self, hist=True):
        """Re-rend l'aperçu immédiatement après un réglage (indispensable en mode
        dossier : pas de frame régulière pour rafraîchir l'écran).
        live=False : ne fait pas avancer le lissage temporel des stats.
        hist=False : le glissement d'une BARRE DE NIVEAUX ne recalcule pas
        l'histogramme (la donnée du moteur ne change pas — seules les barres
        bougent) : sans cela, chaque pixel de souris coûterait un histogramme."""
        if self.last_show is not None:
            self._rendre_et_afficher(self.last_show, live=False, hist=hist)

    # ============================= dessin du Canvas ========================
    def _show_image(self, disp):
        """Mémorise la dernière image étirée puis la dessine (zoom/pan conservés)."""
        self._last_disp = disp
        self._render()

    def _render(self):
        """Dessine self._last_disp en tenant compte du zoom et du pan."""
        disp_src = self._last_disp
        if disp_src is None:
            return
        # v2.55.3 : l'échelle d'affichage est calculée AVANT l'annotation —
        # les étiquettes gardent une TAILLE À L'ÉCRAN constante quel que soit
        # le buffer (aperçu 1600 px OU rendu pleine résolution) : à pleine
        # résolution elles étaient dessinées à ~11 px DANS le buffer (6000 px)
        # puis réduites à ~2 px à l'écran, illisibles (constat d'Alain).
        # Jamais < 1 (le zoom avant ne rapetisse pas les textes) ; plafonnée
        # à 12 pour un canvas minuscule.
        ih, iw = disp_src.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        fit = min(cw / iw, ch / ih)                    # échelle « ajuster »
        scale = fit * self.zoom
        echelle_police = min(12.0, max(1.0, 1.0 / max(scale, 1e-9)))
        self._echelle_police_annot = echelle_police
        # Jalon 96 (étape 5) : annotation temps-réel — overlay dessiné sur une
        # COPIE du buffer, UNIQUE point de passage (tous les rendus : nouvelle
        # image, réglage, zoom). `_last_disp` reste PROPRE : le PNG compagnon
        # repart de la version sans annotation.
        disp = self._annoter_image(disp_src, echelle_police)
        ih, iw = disp.shape[:2]
        if self.zoom <= 1.0001:                        # vue ajustée, pas de recadrage
            crop, interp = disp, (cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        else:
            vx = self.view_cx if self.view_cx is not None else iw / 2.0
            vy = self.view_cy if self.view_cy is not None else ih / 2.0
            x0, x1 = vx - cw / (2 * scale), vx + cw / (2 * scale)
            y0, y1 = vy - ch / (2 * scale), vy + ch / (2 * scale)
            # recadrage borné aux limites de l'image
            if x1 - x0 >= iw:
                x0, x1 = 0.0, float(iw)
            elif x0 < 0:
                x1 -= x0; x0 = 0.0
            elif x1 > iw:
                x0 -= x1 - iw; x1 = float(iw)
            if y1 - y0 >= ih:
                y0, y1 = 0.0, float(ih)
            elif y0 < 0:
                y1 -= y0; y0 = 0.0
            elif y1 > ih:
                y0 -= y1 - ih; y1 = float(ih)
            xi0, yi0 = int(np.floor(x0)), int(np.floor(y0))
            xi1, yi1 = min(iw, int(np.ceil(x1))), min(ih, int(np.ceil(y1)))
            if xi1 - xi0 < 1 or yi1 - yi0 < 1:
                return
            crop = disp[yi0:yi1, xi0:xi1]
            nw = max(1, int(round((xi1 - xi0) * scale)))
            nh = max(1, int(round((yi1 - yi0) * scale)))
            interp = cv2.INTER_NEAREST if self.zoom >= 2.0 else cv2.INTER_LINEAR
        img = cv2.resize(crop, (nw, nh), interpolation=interp)
        self._photo = ImageTk.PhotoImage(Image.fromarray(img))
        self.cv_img.delete("all")
        self.cv_img.create_image(cw // 2, ch // 2, image=self._photo)
        if self.zoom > 1.01:
            # v2.38.0 : l'échelle RÉELLE (px image par px écran) est affichée —
            # 1,00 signifie que l'écran montre les pixels du fichier sans
            # interpolation ; avec le rendu pleine résolution, ces pixels sont
            # ceux que le fichier contiendra.
            info = f"{scale:.2f} px image / px écran" \
                + (", 1:1" if abs(scale - 1.0) < 0.02 else "")
            if self._pleine_res_activee():
                info += " · PLEINE RÉSOLUTION"
            self.cv_img.create_text(8, 8, anchor="nw", fill="#ffd75e",
                                    text=f"zoom ×{self.zoom:.1f}   ({info})   "
                                         f"double-clic : ajuster")

    # ------------------------------------------------------------ zoom / pan
    def _on_wheel_zoom(self, e):
        d = getattr(e, "delta", 0)
        if d:
            factor = 1.25 if d > 0 else 0.8
        else:
            factor = 1.25 if getattr(e, "num", 0) == 4 else 0.8
        self._zoom_at(e.x, e.y, factor)
        return "break"                 # ne pas faire défiler le panneau gauche

    def _zoom_at(self, mx, my, factor):
        """Zoom centré sur le curseur : le point de l'image sous la souris
        reste sous la souris après le zoom."""
        if self._last_disp is None:
            return
        ih, iw = self._last_disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        fit = min(cw / iw, ch / ih)                    # échelle « ajuster »
        scale = fit * self.zoom
        vx = self.view_cx if self.view_cx is not None else iw / 2.0
        vy = self.view_cy if self.view_cy is not None else ih / 2.0
        ix = vx + (mx - cw / 2.0) / scale              # point sous le curseur
        iy = vy + (my - ch / 2.0) / scale
        new_zoom = min(32.0, max(1.0, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-9:
            return
        self.view_cx = min(max(ix - (ix - vx) * (self.zoom / new_zoom), 0.0), float(iw))
        self.view_cy = min(max(iy - (iy - vy) * (self.zoom / new_zoom), 0.0), float(ih))
        self.zoom = new_zoom
        self._render()

    def _on_img_press(self, e):
        self._drag = (e.x, e.y)

    def _on_img_drag(self, e):
        if self._drag is None or self._last_disp is None or self.zoom <= 1.0001:
            return
        px, py = self._drag
        self._drag = (e.x, e.y)
        ih, iw = self._last_disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        scale = min(cw / iw, ch / ih) * self.zoom
        if self.view_cx is None:
            self.view_cx = iw / 2.0
        if self.view_cy is None:
            self.view_cy = ih / 2.0
        self.view_cx = min(max(self.view_cx - (e.x - px) / scale, 0.0), float(iw))
        self.view_cy = min(max(self.view_cy - (e.y - py) / scale, 0.0), float(ih))
        self._render()

    def _on_img_release(self, e):
        self._drag = None

    def _on_img_dblclick(self, e):
        self.zoom, self.view_cx, self.view_cy = 1.0, None, None
        self._render()

    def _vider_ecran(self, texte=""):
        """Efface l'image affichée (v2.41.0) : après une remise à zéro, l'écran
        ne doit plus montrer l'empilement de la cible précédente. `texte` est
        posé au centre (jamais un écran muet — leçon des jalons 72/74)."""
        self._last_disp = None
        try:
            self.cv_img.delete("all")
            cw = self.cv_img.winfo_width() or self.W_IMG
            ch = self.cv_img.winfo_height() or self.H_IMG
            if texte:
                self.cv_img.create_text(cw // 2, ch // 2, text=texte,
                                        fill="#888888",
                                        width=max(80, cw - 40))
        except tk.TclError:           # fenêtre en cours de destruction
            pass

    # ============================= annotation (jalon 96) ===================
    def _seuil_mag(self):
        """Seuil de magnitude des étoiles annotées (jalon 96), lu TOLÉRANT
        (saisie invalide = valeur de config) et BORNÉ (0 à 20 : un seuil
        aberrant ne doit pas noyer l'image d'étiquettes)."""
        try:
            v = float(str(self.var_seuil_mag_etoiles.get()).replace(",", "."))
        except (tk.TclError, TypeError, ValueError):
            v = float(_globals_app().CONFIG.get("seuil_mag_etoiles", 8.0))
        return min(20.0, max(0.0, v))

    def _on_annoter(self):
        """Cases « Annoter objets célèbres » / « Étoiles brillantes » / seuil
        de magnitude / PNG compagnon (jalon 96, étapes 5-6) : persistance
        IMMÉDIATE (comme les autres cases), cache des listes de ciel INVALIDÉ
        (un seuil changé doit relire le catalogue) et rendu immédiat."""
        _app = _globals_app()
        _app.CONFIG["annoter_objets"] = bool(self.var_annoter_objets.get())
        _app.CONFIG["annoter_etoiles"] = bool(self.var_annoter_etoiles.get())
        _app.CONFIG["annoter_visibles"] = bool(self.var_annoter_visibles.get())
        _app.CONFIG["annoter_sauvegarde"] = bool(self.var_annoter_sauvegarde.get())
        _app.CONFIG["seuil_mag_etoiles"] = self._seuil_mag()
        _app.sauver_config(_app.CONFIG)
        self._annote_cache = None
        self._annote_rendu = None
        self._refresh_preview()

    def _forme_pleine(self, disp=None):
        """Forme (h, w) PLEINE RÉSOLUTION de la grille recadrée affichée, ou
        None. `stacker.cadre` = (y0, x0, y1, x1) du recadrage d'intersection :
        la grille affichée en est le recadrage. Sans cadre, la copie pleine
        résolution de l'empilement fait foi ; à défaut, l'aperçu RÉDUIT d'un
        facteur uniforme `_echelle_apercu` (posé par le worker) est remonté.
        → None si aucune de ces sources n'est disponible : JAMAIS de forme
        devinée (l'annotation serait décalée)."""
        st = self.stacker
        if st is None:
            return None
        cadre = getattr(st, "cadre", None)
        if cadre:
            try:
                y0, x0, y1, x1 = (int(v) for v in cadre)
            except (TypeError, ValueError):
                return None
            if y1 - y0 > 0 and x1 - x0 > 0:
                return (y1 - y0, x1 - x0)
            return None
        plein = getattr(self, "_stack_pleine_res", None)
        if plein is not None:
            h, w = plein.shape[:2]
            return (int(h), int(w))
        if disp is not None and not self._pleine_res_activee():
            s = float(getattr(self, "_echelle_apercu", 1.0) or 1.0)
            if 0.0 < s < 1.0:
                h, w = disp.shape[:2]
                return (int(round(h / s)), int(round(w / s)))
        return None

    def _wcs_affichage(self, disp):
        """WCS du buffer AFFICHÉ, ou None (astrométrie non résolue, pas de
        forme). Le WCS rendu est celui de la grille recadrée PLEINE
        résolution, ENVELOPPÉ dans `WcsEchelle` : l'aperçu est une réduction
        uniforme de cette grille, multiplier les coordonnées suffit."""
        sa = self.suivi_astro
        if sa is None or not getattr(sa, "resolu", False):
            return None
        if disp is None:
            return None
        st = self.stacker
        cadre = getattr(st, "cadre", None) if st is not None else None
        wcs, msg = sa.wcs_grille(cadre=cadre)
        if wcs is None:
            return None
        forme = self._forme_pleine(disp)
        if forme is None:
            return None
        ech = float(disp.shape[1]) / float(forme[1])
        return annoter_mod.WcsEchelle(wcs, ech)

    def _donnees_annotation(self, wcs, disp) -> tuple[Any, Any]:
        """Listes de ciel de l'annotation (objets célèbres + étoiles Gaia du
        champ), mises en CACHE par (centre, champ, seuil) : la lecture du
        catalogue Gaia (≈ 1 Go) est trop lourde pour un rendu par image, et a
        fortiori sous le zoom. → (objets, etoiles) ; (None, None) si rien
        d'exploitable (catalogue absent, champ vide)."""
        sa = self.suivi_astro
        ra = getattr(sa, "ra0", None)
        dec = getattr(sa, "dec0", None)
        if ra is None or dec is None:
            return None, None
        champ = getattr(sa, "champ", None)
        seuil = self._seuil_mag()
        objets_act = bool(self.var_annoter_objets.get())
        etoiles_act = bool(self.var_annoter_etoiles.get())
        rayon = max(0.5, float(champ)) if champ else 0.5
        cle = (round(float(ra), 4), round(float(dec), 4), round(rayon, 3),
               round(seuil, 2), objets_act, etoiles_act)
        c = self._annote_cache
        if c is not None and c[0] == cle:
            return c[1], c[2]
        objets = etoiles = None
        if objets_act:
            try:
                objets = cat_mod.celebres.cherche_celebres(
                    ra, dec, rayon) or None
                if objets:
                    # DÉDUPLICATION PARTAGÉE : le catalogue brut renvoie M31 +
                    # NGC 224 + « 224 » aux MÊMES coordonnées — les doublons
                    # empilaient leurs textes au même endroit, illisibles
                    # (constat Alain sur M31, 04/10/2026).
                    objets = (cat_mod.celebres.deduplique_celebres(
                        objets, ra, dec) or None)
            except Exception:
                objets = None
        if etoiles_act:
            forme = self._forme_pleine(disp)
            if forme is not None:
                try:
                    etoiles, _msg = photo_mod.etoiles_catalogue(
                        wcs, forme, limmag=seuil)
                    etoiles = etoiles or None
                except Exception:
                    etoiles = None
        self._annote_cache = (cle, objets, etoiles)
        return objets, etoiles


    def _annoter_image(self, disp, echelle_police=1.0) -> Any:
        """Copie de l'image affichée AVEC l'annotation (objets + étoiles), ou
        l'image telle quelle si rien à dessiner. `_last_disp` reste SANS
        annotation : le PNG compagnon et le zoom repartent de la version
        propre, jamais d'une image déjà annotée (double étiquette).
        `echelle_police` (v2.55.3) : taille des étiquettes pour une TAILLE À
        L'ÉCRAN constante (pleine résolution ≠ aperçu).
        Cache MONO-SLOT : à pleine résolution l'overlay recopie ~69 Mo — le
        glissement de vue (pan) re-rend en continu, le cache l'évite. La clé
        retient le buffer (id + référence, donc pas d'id recyclé), l'échelle
        et l'état des deux cases."""
        if disp is None:
            return disp
        try:
            objets_act = bool(self.var_annoter_objets.get())
            etoiles_act = bool(self.var_annoter_etoiles.get())
            visibles_act = bool(self.var_annoter_visibles.get())
        except (tk.TclError, AttributeError):
            return disp
        if not (objets_act or etoiles_act):
            return disp
        cle_cache = (id(disp), round(float(echelle_police), 3),
                     objets_act, etoiles_act, visibles_act)
        c = getattr(self, "_annote_rendu", None)
        if c is not None and c[0] == cle_cache:
            return c[1]
        wcs = self._wcs_affichage(disp)
        if wcs is None:
            return disp
        objets, etoiles = self._donnees_annotation(wcs, disp)
        if objets is None and etoiles is None:
            return disp
        img = np.ascontiguousarray(disp)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        # `objets` / `etoiles` peuvent être None SÉPARÉMENT (la garde ci-dessus
        # ne sort que si LES DEUX sont nuls) et `generer_image_annotee` les gère :
        # son paramètre typé trop étroit impose un ignore CIBLÉ (motif du chantier).
        img_ann = annoter_mod.generer_image_annotee(
            img, wcs, objets, etoiles, self._seuil_mag(),  # pyright: ignore[reportArgumentType]
            annoter_objets=objets_act, annoter_etoiles=etoiles_act,
            echelle_police=echelle_police, seulement_visibles=visibles_act)
        if img_ann is None:
            return disp
        self._annote_rendu = (cle_cache, img_ann, disp)
        return img_ann

    def _sauver_png_annote(self, chemin):
        """PNG annoté COMPAGNON à côté du FITS (jalon 96, étape 6) : copie du
        buffer d'affichage courant (PROPRE) + étiquettes. → (chemin écrit,
        message d'erreur) ; (None, "") si rien à écrire. AUCUNE exception
        propagée : un PNG compagnon ne doit jamais faire échouer la
        sauvegarde du FITS (linéarité photométrique préservée)."""
        try:
            if not (bool(_globals_app().CONFIG.get("annoter_sauvegarde", True))
                    and self.var_annoter_sauvegarde.get()):
                return None, ""
            objets_act = bool(self.var_annoter_objets.get())
            etoiles_act = bool(self.var_annoter_etoiles.get())
            visibles_act = bool(self.var_annoter_visibles.get())
        except (tk.TclError, AttributeError):
            return None, ""
        if not (objets_act or etoiles_act):
            return None, ""
        disp = getattr(self, "_last_disp", None)
        if disp is None:
            return None, ""
        wcs = self._wcs_affichage(disp)
        if wcs is None:
            return None, ""
        objets, etoiles = self._donnees_annotation(wcs, disp)
        if objets is None and etoiles is None:
            return None, ""
        img = np.ascontiguousarray(disp)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        # Même échelle que le DERNIER rendu à l'écran (le PNG doit ressembler
        # à l'écran) ; jamais rendu → repli sur la taille de l'image.
        echelle = getattr(self, "_echelle_police_annot", None)
        if not echelle or echelle < 1.0:
            ih, iw = img.shape[:2]
            echelle = min(12.0, max(1.0, max(ih, iw) / 1600.0))
        img_ann = annoter_mod.generer_image_annotee(
            img, wcs, objets, etoiles, self._seuil_mag(),  # pyright: ignore[reportArgumentType]
            annoter_objets=objets_act, annoter_etoiles=etoiles_act,
            echelle_police=echelle, seulement_visibles=visibles_act)
        if img_ann is None:
            return None, ""
        sortie = os.path.splitext(chemin)[0] + "_annote.png"
        try:
            save_image(sortie, img_ann.astype(np.float32) / 255.0)
        except Exception as exc:
            return None, str(exc)
        return sortie, ""

