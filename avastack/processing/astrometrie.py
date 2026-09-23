# -*- coding: utf-8 -*-
"""Astrométrie de l'empilement : résolution UNIQUE puis PROPAGATION (jalon 56).

Décisions d'Alain (22/09/2026) : le solveur interne (étape 2) résout
l'astrométrie de l'empilement UNE SEULE fois, avec les INDICES de la cible ;
à chaque RÉEMPILEMENT (changement de référence d'alignement, donc de grille)
le WCS est PROPAGÉ par composition de transformations (étape 3,
`catalogues/propagation.py`) — aucun re-solve, aucune re-détection d'étoiles,
aucun accès au catalogue. ASTAP reste la référence indépendante/repli hors
session (`_diag_solve_reel.py`).

Ce module est la GLUE entre les deux mondes : il vit dans `processing` parce
que la fondation `catalogues` ne doit JAMAIS dépendre du processing (cycle
d'import, cf. solveur.py) — l'inverse est permis.

DEUX REPÈRES À NE JAMAIS CONFONDRE (c'est LE piège du branchement) :

  * la GRILLE COMPLÈTE de l'empilement — `stacker.mean(recadre=False)`, le
    repère de l'ALIGNEUR (celui de la référence d'alignement) : c'est là que
    le WCS est résolu, puis propagé ;
  * la GRILLE RECADRÉE — `stacker.cadre` = intersection des zones couvertes,
    c'est celle de la VUE et des SAUVEGARDES. Son WCS se déduit du précédent
    par une simple TRANSLATION (+x0, +y0) : jamais un re-solve.

CHAÎNAGE DES PROPAGATIONS : `propager()` exige un `WcsTan` en référence (un
`WcsCompose` n'a ni CRVAL ni CRPIX à exposer à une seconde composition —
cf. docstring de propagation.py). Le suivi garde donc le WcsTan RÉSOLU et
cumule UNE matrice (`compose_M` : les matrices se composent exactement), puis
propage une seule fois — la chaîne reste exacte, sans perte cumulée.

CONVENTIONS DE COORDONNÉES (explicites, jamais devinées) :

  * « 0h42m44s », « 00 42 44 » ou « 0.7123h » → HEURES (× 15 → degrés) ;
  * décimal nu (« 10.68333 ») → DEGRÉS.

L'interprétation retenue est TOUJOURS affichée dans la ligne d'état (étoiles,
rms, ″/px, chemin du solveur) : aucune ambiguïté silencieuse.

Convention du projet : aucune méthode ne lève — tout se rend en
(résultat, message), une fonctionnalité annexe ne doit jamais interrompre
l'acquisition.
"""

import os
import re
import time

import numpy as np

from ..catalogues import WcsTan, compose_M, propager
from ..catalogues import resoudre as _resoudre_interne

try:
    from astropy.io import fits
    FITS_OK = True
except ImportError:                       # astropy absent : pas de FITS
    FITS_OK = False

# --- Politique de résolution (le worker s'y réfère, les bancs la vérifient) --
ASTRO_MIN_FRAMES = 3        # pas de tentative avant ce nombre de frames empilées
ASTRO_ESSAI_DELAI_S = 20.0  # délai minimal entre deux tentatives (réessais)
ASTRO_MAX_ESSAIS = 6        # plafond de tentatives par session (jamais de boucle)
ASTRO_CHAMP_MIN, ASTRO_CHAMP_MAX = 0.05, 30.0   # bornes du champ indicé (°)

# Séparateurs des coordonnées sexagésimales (« 41d16'09" », « 0h42m44s »,
# « 00 42 44 », « 0:42:44 ») — l'espace en fait partie : les logiciels
# d'acquisition écrivent OBJCTRA/OBJCTDEC ainsi.
_SEP_SEXAG = re.compile(r"[hHdD°dmMsS:'\s]+")


def analyser_angle(txt, en_heures=None):
    """« 41.26917 », « 41d16m09s », « 0h42m44.3s », « 00 42 44 » → degrés.
    → (valeur en degrés, message) ; (None, message clair) si illisible.

    `en_heures` : True/False = impose l'interprétation ; None = décide par le
    texte (suffixe « h » → heures, décimal NU → degrés). Un signe devant la
    PREMIÈRE composante vaut pour l'ensemble (« -05 12 30 » = -5,2083°)."""
    t = str(txt if txt is not None else "").strip().replace(",", ".")
    if not t:
        return None, "valeur vide"
    heures = ("h" in t.lower()) if en_heures is None else bool(en_heures)
    corps = t.lstrip("+-")
    signe = -1.0 if t.startswith("-") else 1.0
    morceaux = [m for m in _SEP_SEXAG.split(corps) if m != ""]
    if not morceaux or len(morceaux) > 3:
        return None, f"valeur illisible : « {txt} »"
    try:
        vals = [float(m) for m in morceaux]
    except ValueError:
        return None, f"valeur illisible : « {txt} »"
    v = vals[0]
    if len(vals) > 1:
        v += vals[1] / 60.0
    if len(vals) > 2:
        v += vals[2] / 3600.0
    v *= signe
    if heures:
        v *= 15.0              # ascension droite en heures → degrés
    return v, ""


def analyser_indices(ra_txt, dec_txt, champ_txt):
    """Indices de la cible saisis dans l'UI → (ra_deg, dec_deg, champ_deg,
    message). Message NON VIDE = refus, avec la cause exacte (toujours
    affichée : l'utilisateur voit ainsi comment sa saisie a été comprise)."""
    ra, m = analyser_angle(ra_txt)
    if ra is None:
        return None, None, None, f"AD : {m}"
    dec, m = analyser_angle(dec_txt)
    if dec is None:
        return None, None, None, f"Dec : {m}"
    if abs(dec) > 90.0:
        return None, None, None, f"Dec hors bornes : {dec:.4f}°"
    try:
        champ = float(str(champ_txt if champ_txt is not None else "")
                      .strip().replace(",", "."))
    except ValueError:
        return None, None, None, f"champ illisible : « {champ_txt} »"
    if not (ASTRO_CHAMP_MIN <= champ <= ASTRO_CHAMP_MAX):
        return None, None, None, (f"champ hors bornes ({ASTRO_CHAMP_MIN}–"
                                  f"{ASTRO_CHAMP_MAX}°) : {champ}")
    return ra % 360.0, dec, champ, ""


def champ_depuis_optique(focale_mm, pixel_um, n_pixels):
    """Largeur du champ (degrés, est-ouest) d'un capteur : échelle de
    206,265 ″/rad (même formule que _diag_solve_reel.py) → None si l'un des
    paramètres est absent ou nul (jamais de division par zéro)."""
    try:
        f, p, n = float(focale_mm), float(pixel_um), float(n_pixels)
    except (TypeError, ValueError):
        return None
    if f <= 0.0 or p <= 0.0 or n <= 0.0:
        return None
    return 206.265 * p * n / f / 3600.0


def _valeur_entete(entete, noms):
    """Première valeur non vide parmi `noms` (str), sinon None."""
    for nom in noms:
        v = entete.get(nom)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def indices_entete_fits(chemin):
    """Indices (ra_deg, dec_deg, champ_deg, message) lus dans l'en-tête d'une
    BRUTE FITS — ou (None, None, None, raison).

    LECTURE STRICTE, jamais de supposition (règle de CLAUDE.md : ne jamais
    présumer du logiciel de capture) : seuls des mots-clés EXPLICITES et
    documentés sont exploités —
      • OBJCTRA / OBJCTDEC (N.I.N.A., SGP, APT : sexagésimal « 00 42 44 »,
        OBJCTRA en HEURES) ;
      • à défaut RA / DEC (degrés, en-tête déjà écrit par une source WCS) ;
      • champ : FOCALLEN (mm) + XPIXSZ ou PIXSIZE1 (µm) + largeur de l'image.
    Aucun de ces mots-clés → refus explicite : l'appelant garde alors ses
    champs de saisie (jamais de valeur inventée)."""
    if not FITS_OK:
        return None, None, None, "astropy absent (lecture FITS impossible)"
    if not str(chemin or "").lower().endswith((".fits", ".fit", ".fts")):
        return None, None, None, "source sans en-tête FITS (PNG/TIFF)"
    try:
        with fits.open(chemin) as hd:
            entete = hd[0].header
    except Exception as exc:
        return None, None, None, f"en-tête illisible ({exc})"

    ra = dec = None
    source = ""
    txt = _valeur_entete(entete, ("OBJCTRA",))
    if txt:
        ra, m = analyser_angle(txt, en_heures=True)
        if ra is None:
            return None, None, None, f"OBJCTRA illisible ({m})"
        source = "OBJCTRA"
    txt = _valeur_entete(entete, ("OBJCTDEC",))
    if txt:
        dec, m = analyser_angle(txt, en_heures=False)
        if dec is None:
            return None, None, None, f"OBJCTDEC illisible ({m})"
        source += " + OBJCTDEC" if source else "OBJCTDEC"
    if ra is None or dec is None:
        # Repli : RA/DEC en degrés (en-tête WCS d'une autre source) — jamais
        # utilisés si OBJCTRA/OBJCTDEC étaient présents.
        try:
            v_ra = entete.get("RA")
            v_dec = entete.get("DEC")
            ra = float(v_ra) if v_ra is not None else None
            dec = float(v_dec) if v_dec is not None else None
        except (TypeError, ValueError):
            ra = dec = None
        if ra is not None and dec is not None:
            source = "RA/DEC (degrés)"
        else:
            return (None, None, None,
                    "en-tête sans OBJCTRA/OBJCTDEC ni RA/DEC")

    # Champ : FOCALLEN (mm) × XPIXSZ/PIXSIZE1 (µm) × largeur — les trois
    # doivent être présents et cohérents, sinon le champ est REFUSÉ (un
    # champ faux ferait échouer les garde-fous du solveur sans rien dire).
    larg = entete.get("NAXIS1")
    try:
        larg = int(larg)
    except (TypeError, ValueError):
        larg = None
    foc = _valeur_entete(entete, ("FOCALLEN",))
    pix = _valeur_entete(entete, ("XPIXSZ", "PIXSIZE1"))
    champ = (champ_depuis_optique(foc, pix, larg)
             if (foc and pix and larg) else None)
    if champ is None:
        return (ra % 360.0, dec, None,
                f"indices {source} lus, mais CHAMP non déductible "
                f"(FOCALLEN/XPIXSZ/NAXIS1 incomplets) — saisir le champ (deg)")
    if not (ASTRO_CHAMP_MIN <= champ <= ASTRO_CHAMP_MAX):
        return (ra % 360.0, dec, None,
                f"champ calculé hors bornes ({champ:.3f}°) — "
                f"vérifier FOCALLEN/XPIXSZ")
    return ra % 360.0, dec, champ, f"indices lus dans l'en-tête ({source})"


class SuiviAstrometrie:
    """WCS de l'empilement : résolu UNE fois, puis PROPAGÉ (jalon 56).

    Cycle de vie dans le worker :
      `indice(ra, dec, champ)` → indices de la cible (saisis ou lus dans
      l'en-tête) ; `peut_essayer(n)` → une tentative a-t-elle un sens
      maintenant ; `resoudre_sur(stacker.mean(recadre=False))` → résolution
      UNIQUE sur la GRILLE COMPLÈTE ; `propager(M)` à chaque RÉEMPILEMENT ;
      `mots_cles(cadre)` au moment d'ÉCRIRE un FITS.

    `wcs` = WcsTan de la GRILLE COMPLÈTE de référence (celui du solve) ;
    `matrice` = transformation cumulée de la grille COURANTE vers cette
    grille de référence (identité juste après le solve). Le WCS d'une grille
    donnée n'est calculé qu'à la demande, par UNE propagation (cf. en-tête du
    module : `propager` n'accepte que des WcsTan en référence).

    `solveur` est INJECTABLE (bancs : solveur factice, aucun catalogue requis) ;
    par défaut le solveur interne du jalon 56 (étape 2)."""

    def __init__(self, solveur=None, dossier=None, limmag=None):
        self._solveur = solveur or _resoudre_interne
        self.dossier = dossier            # dossier des catalogues (None = défaut)
        self.limmag = limmag              # magnitude limite du catalogue
        # Indices de la cible : posés AVANT reset() car un reset de SESSION les
        # conserve (la case reste cochée, les valeurs saisies aussi).
        self.ra0 = self.dec0 = self.champ = None
        self.reset()

    # -- cycle de vie ---------------------------------------------------------
    def reset(self):
        """Session neuve (ou case décochée) : indices CONSERVÉS, WCS oublié."""
        self.wcs = None                   # WcsTan de la grille de référence
        self.matrice = np.eye(2, 3)       # grille courante → grille du solve
        self.info = {}                    # dict d'info du solveur
        self.essais = 0                   # tentatives de résolution (session)
        self.propagations = 0             # propagations réussies
        self.derniere_erreur = ""
        self._dernier_essai = 0.0

    def indice(self, ra_deg, dec_deg, champ_deg):
        """Pose (ou remplace) les indices de la cible → True s'ils ont CHANGÉ.

        Des indices DIFFÉRENTS rendent le WCS résolu caduc (autre cible, autre
        champ, autre échelle) : il est oublié et les tentatives repartent de
        zéro. Les MÊMES indices ne touchent à RIEN (le worker repose ses
        indices à chaque tentative — une remise à zéro à chaque tour
        relancerait un solve en boucle)."""
        try:
            nouveaux = (float(ra_deg) % 360.0, float(dec_deg),
                        float(champ_deg))
        except (TypeError, ValueError):
            return False
        if self.pret and nouveaux == (self.ra0, self.dec0, self.champ):
            return False
        self.ra0, self.dec0, self.champ = nouveaux
        self.wcs = None
        self.matrice = np.eye(2, 3)
        self.info = {}
        self.essais = 0
        self.derniere_erreur = ""
        return True

    @property
    def pret(self):
        """Indices de la cible renseignés (rien d'autre n'est nécessaire pour
        tenter une résolution) ?"""
        return (self.ra0 is not None and self.dec0 is not None
                and self.champ is not None)

    @property
    def resolu(self):
        """Un WCS exploitable est disponible ?"""
        return self.wcs is not None

    def peut_essayer(self, n_frames, maintenant=None):
        """Une tentative de résolution a-t-elle un sens MAINTENANT ?
        (indices posés, pas déjà résolu, assez de frames empilées, délai
        écoulé, plafond d'essais non atteint — cf. constantes du module)."""
        if self.resolu or not self.pret:
            return False
        if int(n_frames) < ASTRO_MIN_FRAMES:
            return False
        if self.essais >= ASTRO_MAX_ESSAIS:
            return False
        t = time.monotonic() if maintenant is None else float(maintenant)
        if self.essais and t - self._dernier_essai < ASTRO_ESSAI_DELAI_S:
            return False
        return True

    def raison_attente(self):
        """Pourquoi aucune résolution n'est possible maintenant (texte court à
        afficher : jamais de silence sur l'absence de WCS)."""
        if self.resolu:
            return ""
        if not self.pret:
            return "indices de la cible manquants"
        if self.essais >= ASTRO_MAX_ESSAIS:
            return (f"échec après {self.essais} tentatives"
                    + (f" — {self.derniere_erreur}"
                       if self.derniere_erreur else ""))
        return ""

    # -- résolution -----------------------------------------------------------
    def resoudre_sur(self, img):
        """Résout l'astrométrie de `img` — la GRILLE COMPLÈTE de l'empilement
        (`stacker.mean(recadre=False)`, le repère de l'aligneur). → (True/False,
        message) ; compte la tentative, ne lève JAMAIS.

        Une image insuffisante (trop peu d'étoiles, indices trop loin du
        champ réel) est un ÉCHEC NORMAL : le worker réessaiera plus tard, sur
        un empilement plus profond — d'où les réessais espacés
        (ASTRO_ESSAI_DELAI_S) et le plafond ASTRO_MAX_ESSAIS, appliqué ICI
        aussi (un appelant qui ignorerait `peut_essayer` ne peut pas boucler)."""
        if self.resolu:
            return True, self.texte_resume()
        if not self.pret:
            return False, "indices de la cible absents"
        if self.essais >= ASTRO_MAX_ESSAIS:
            return False, (f"plafond de {ASTRO_MAX_ESSAIS} tentatives atteint"
                           + (f" — {self.derniere_erreur}"
                              if self.derniere_erreur else ""))
        self.essais += 1
        self._dernier_essai = time.monotonic()
        try:
            wcs, info, msg = self._solveur(img, self.ra0, self.dec0,
                                           self.champ, dossier=self.dossier,
                                           limmag=self.limmag)
        except Exception as exc:      # un solveur ne doit jamais tuer le worker
            wcs, info, msg = None, {}, f"exception du solveur ({exc})"
        if wcs is None:
            self.derniere_erreur = str(msg or "échec de résolution")
            return False, self.derniere_erreur
        self.wcs = wcs
        self.matrice = np.eye(2, 3)
        self.info = dict(info or {})
        self.derniere_erreur = ""
        return True, self.texte_resume()

    # -- propagation ----------------------------------------------------------
    def propager(self, M):
        """La grille de l'empilement vient de changer (RÉEMPILEMENT : la
        nouvelle référence d'alignement est une brute archivée, son repère
        pixel n'est pas celui de l'ancienne grille).

        `M` = matrice de l'ALIGNEUR pour cette nouvelle référence, convention
        warpAffine du projet : elle va de la NOUVELLE grille vers l'ANCIENNE
        (`W1 = propager(W0, M10)` — le chemin validé par le banc jalon 56
        étape 3, StarAligner réel). → (True, message) / (False, message).

        Sans WCS résolu : no-op SANS erreur (rien à propager — la résolution
        se fera sur la nouvelle grille au prochain essai)."""
        if self.wcs is None:
            return False, ""
        try:
            M = np.asarray(M, dtype=np.float64).reshape(2, 3)
        except (TypeError, ValueError) as exc:
            return False, f"matrice d'alignement inexploitable ({exc})"
        if not np.isfinite(M).all():
            return False, "matrice d'alignement non finie"
        avant = self.matrice
        self.matrice = compose_M(self.matrice, M)
        # VOYANT sur la chaîne CUMULÉE : deux matrices d'alignement valides
        # peuvent composer hors bornes (1,1 × 1,1 = 1,21). Si la similitude
        # cumulée n'est plus plausible, la traduction « grille courante →
        # grille du solve » est fausse : on refuse AVANT d'écrire un WCS faux.
        ech = float(np.sqrt(abs(np.linalg.det(self.matrice[:2, :2]))))
        if not (0.5 <= ech <= 2.0) or not np.isfinite(self.matrice).all():
            self.matrice = avant
            return False, f"échelle cumulée aberrante ({ech:.3f})"
        self.propagations += 1
        return True, ""

    # -- WCS d'une grille donnée ---------------------------------------------
    def wcs_grille(self, cadre=None, forme=None):
        """WCS de la grille VISÉE (vue et sauvegardes) → (WCS ou None, message).

        `cadre` = (y0, x0, y1, x1) du recadrage d'intersection (None ou vide =
        grille complète) ; `forme` = (h, w) de la grille visée (défaut :
        déduite du cadre). Le recadrage ne change QUE l'origine : une
        TRANSLATION (+x0, +y0) va de la grille recadrée vers la grille
        complète (sens warpAffine) et se compose à la matrice cumulée —
        exact, sans re-solve, sans nouvelle détection."""
        if self.wcs is None:
            return None, "astrométrie non résolue"
        M = self.matrice
        f_deduite = None
        if cadre:
            y0, x0, y1, x1 = (int(v) for v in cadre)
            if x0 or y0:
                M = compose_M(M, np.array([[1.0, 0.0, float(x0)],
                                           [0.0, 1.0, float(y0)]]))
            f_deduite = (y1 - y0, x1 - x0)
        forme = tuple(int(v) for v in forme) if forme else f_deduite
        try:
            w, msg = propager(self.wcs, M, forme=forme)
        except Exception as exc:
            return None, f"propagation impossible ({exc})"
        if w is None:
            return None, str(msg or "propagation refusée")
        return w, ""

    def mots_cles(self, cadre=None, forme=None):
        """Mots-clés FITS WCS (CTYPE/CRVAL/CRPIX/CD…) de la grille visée, prêts
        pour `save_image(..., entete=...)`. → (dict, message) ; dict VIDE si
        l'astrométrie n'est pas résolue (jamais de mot-clé inventé).

        Un WcsTan résolu donne ses mots-clés tels quels ; après propagation
        (WcsCompose) `vers_tan` en ré-ajuste un équivalent (composer un TAN
        avec une similitude rend un TAN exact) — le rms de l'ajustement est
        consigné dans AVARMS, jamais caché."""
        w, msg = self.wcs_grille(cadre, forme=forme)
        if w is None:
            return {}, msg
        try:
            if isinstance(w, WcsTan):
                return dict(w.mots_cles_fits()), ""
            tan, rms = w.vers_tan(forme=forme)
            m = dict(tan.mots_cles_fits())
            m["AVARMS"] = (round(float(rms), 4),
                           "rms du re-ajustement TAN (px)")
            return m, ""
        except Exception as exc:
            return {}, f"mots-clés WCS indisponibles ({exc})"

    # -- état (ligne dédiée de l'UI) ------------------------------------------
    def texte_resume(self):
        """Ligne d'état de l'astrométrie RÉSOLUE : étoiles, rms, échelle,
        chemin retenu par le solveur, propagations — et les INDICES retenus
        (l'utilisateur voit ainsi comment sa saisie a été comprise).
        "" si l'astrométrie n'est pas résolue."""
        if not self.resolu:
            return ""
        i = self.info
        txt = "Astrométrie : résolue"
        if i.get("n_etoiles_img"):
            txt += f" — {int(i['n_etoiles_img'])} étoiles"
        if i.get("rms_px") is not None:
            txt += f", rms {float(i['rms_px']):.2f} px"
        if i.get("echelle_arcsec_px") is not None:
            txt += f", {float(i['echelle_arcsec_px']):.3f}″/px"
        if i.get("methode"):
            txt += f" ({i['methode']})"
        txt += (f" · AD {self.ra0:.5f}° Dec {self.dec0:+.5f}° "
                f"champ {self.champ:.3f}°")
        if self.propagations:
            txt += f" · {self.propagations} propagation(s)"
        return txt
