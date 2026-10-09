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
import shutil
import time
from typing import Any

import numpy as np

from ..catalogues import WcsTan, compose_M, propager
from ..catalogues import balayage_possible, bases_installees
from ..catalogues import MSG_CATALOGUE_ABSENT, chemin_catalogue_astro
from ..catalogues import resoudre as _resoudre_interne
from ..catalogues import resoudre_avec_astap as _resoudre_astap
from ..images import borner_lineaire, save_image
from .. import travail

try:
    from astropy.io import fits
    FITS_OK: bool = True
except ImportError:                       # astropy absent : pas de FITS
    FITS_OK = False

# --- Politique de résolution (le worker s'y réfère, les bancs la vérifient) --
ASTRO_MIN_FRAMES: int = 3   # pas de tentative avant ce nombre de frames empilées
ASTRO_ESSAI_DELAI_S: float = 20.0      # délai minimal entre deux tentatives…
ASTRO_ESSAI_DELAI_MAX_S: float = 300.0  # …CROISSANT avec le nombre d'essais (backoff),
                                 # plafonné : 20 s, 40 s, 60 s… au lieu de
                                 # brûler tout le quota en deux minutes
ASTRO_MAX_ESSAIS: int = 20  # plafond LARGE : un empilement bien plus profond
                            # n'a plus la même chance. Constat réel d'Alain
                            # (23/09/2026) : avec un plafond de 6 et un délai
                            # fixe, les essais étaient épuisés en ~2 min (sur un
                            # empilement encore trop court) puis PLUS AUCUNE
                            # tentative, même à 33 frames — session perdue.
ASTRO_ESSAI_DOUBLEMENT: bool = True   # un empilement qui a DOUBLÉ de profondeur
                                # justifie un essai IMMÉDIAT : c'est une
                                # information réellement nouvelle (32 frames
                                # après 16, ce n'est plus la même mesure)
ASTRO_CHAMP_MIN: float = 0.05
ASTRO_CHAMP_MAX: float = 30.0   # bornes du champ indicé (°)
ASTRO_MAX_AVEUGLES: int = 2      # plafond des balayages ASTAP (session) — LENTS
ASTRO_ASTAP_TIMEOUT_S: float = 90.0    # délai d'un balayage (borné pour le live)

# Séparateurs des coordonnées sexagésimales (« 41d16'09" », « 0h42m44s »,
# « 00 42 44 », « 0:42:44 ») — l'espace en fait partie : les logiciels
# d'acquisition écrivent OBJCTRA/OBJCTDEC ainsi.
_SEP_SEXAG: re.Pattern[str] = re.compile(r"[hHdD°dmMsS:'\s]+")


def analyser_angle(txt: Any, en_heures: bool | None = None
                   ) -> tuple[float | None, str]:
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


def analyser_indices(ra_txt: Any, dec_txt: Any, champ_txt: Any
                     ) -> tuple[float | None, float | None, float | None, str]:
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


def analyser_champ(txt: Any) -> tuple[float | None, str]:
    """Champ indicatif SEUL (« 2.6 », largeur est-ouest en degrés) →
    (valeur, message). Sert au REPLI ASTAP quand les coordonnées sont
    inconnues mais que l'échantillonnage l'est (une focale se connaît
    toujours) : ASTAP balaie alors BEAUCOUP plus vite et surement."""
    try:
        v = float(str(txt if txt is not None else "").strip().replace(",", "."))
    except ValueError:
        return None, f"champ illisible : « {txt} »"
    if not (ASTRO_CHAMP_MIN <= v <= ASTRO_CHAMP_MAX):
        return None, (f"champ hors bornes ({ASTRO_CHAMP_MIN}–"
                      f"{ASTRO_CHAMP_MAX}°) : {v}")
    return v, ""


def champ_depuis_optique(focale_mm: Any, pixel_um: Any,
                         n_pixels: Any) -> float | None:
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


def _valeur_entete(entete: Any, noms: Any) -> str | None:
    """Première valeur non vide parmi `noms` (str), sinon None."""
    for nom in noms:
        v = entete.get(nom)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def indices_entete_fits(chemin: Any
                        ) -> tuple[float | None, float | None, float | None, str]:
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
            # astropy renvoie `hd[0]` typé HDUList par son stub : l'accès
            # `.header` est valide à l'exécution → ignore CIBLÉ.
            entete = hd[0].header  # pyright: ignore[reportAttributeAccessIssue]
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


def nom_objet_entete_fits(chemin: Any) -> str | None:
    """Nom d'objet lu dans l'en-tête FITS (OBJECT, OBJNAME, TARGNAME, TARGET).
    Retourne le premier non-vide, ou None si aucun n'est présent.
    JAMAIS d'invention — si absent, l'appelant gère le repli (catalogue, saisie)."""
    if not FITS_OK:
        return None
    if not str(chemin or "").lower().endswith((".fits", ".fit", ".fts")):
        return None
    try:
        with fits.open(chemin) as hd:
            # cf. `indices_entete_fits` : stub astropy → ignore CIBLÉ.
            entete = hd[0].header  # pyright: ignore[reportAttributeAccessIssue]
    except Exception:
        return None
    # Ordre de priorité : conventions N.I.N.A., MaxIm DL, ACP, APT, SGP...
    for cle in ("OBJECT", "OBJNAME", "TARGNAME", "TARGET"):
        val = _valeur_entete(entete, (cle,))
        if val and val.strip():
            return val.strip()
    return None


def resoudre_aveugle_astap(img: np.ndarray, fov_deg: float = 0.0,
                           ra0: float | None = None, dec0: float | None = None,
                           rayon_deg: float | None = None,
                           chemin_astap: Any = None,
                           timeout: float = ASTRO_ASTAP_TIMEOUT_S,
                           dossier: str | None = None,
                           garder: bool = False
                           ) -> tuple[Any, float | None, float | None,
                                      float | None, str]:
    """Résolution ASTAP SANS AUCUN INDICE (« aveugle ») sur une image EN MÉMOIRE.

    Décision d'Alain (23/09/2026) : quand ni la saisie ni l'en-tête des brutes
    ne fournit d'indices (caméra live sans en-tête FITS), ASTAP résout seul et
    son CENTRE sert d'indice au solveur interne — chemin déjà VALIDÉ EN RÉEL par
    `_diag_solve_reel.py`. Le WCS d'ASTAP sert aussi de REPLI si le solveur
    interne refuse ensuite (décision : « ASTAP = référence indépendante/repli »).

    L'image est écrite dans un FITS TEMPORAIRE borné à [0,1] (leçon v2.27.1 :
    sur un composite hors [0,1] — cœur de galaxie à 14 — ASTAP ne détecte
    AUCUNE étoile, « Only 0 stars found in image »).

    `fov_deg` : LARGEUR de champ INDICATIVE en degrés (0 = balayage complet) —
    même convention que `catalogues.resoudre` ; elle est convertie en hauteur
    pour ASTAP (piège de convention, cf. plus bas). CONSTAT RÉEL du 23/09/2026 :
    sur l'empilement M31 d'Alain, le balayage COMPLET échoue (« No solution
    found » en 0,4 s) alors que le même fichier est résolu en 0,2 s dès qu'une
    position de départ est donnée — un champ indicatif seul NE SUFFIT PAS avec
    une base D50/D80 (cf. `balayage_possible`).

    `ra0`/`dec0` (+ `rayon_deg`) : position APPROXIMATIVE (degrés) pour une
    résolution GUIDÉE — elle peut être fausse de plusieurs degrés (rayon
    élargi en conséquence) ; c'est le SEUL chemin qui aboutit avec les bases
    D50/D80.

    → (wcs WcsTan, ra_deg, dec_deg, champ_deg, message) ;
      (None, None, None, None, message) sinon — jamais d'exception.
    `champ_deg` = LARGEUR du champ (est-ouest), même convention que
    `catalogues.resoudre` (le solveur en déduit son échelle indicative)."""
    a = np.asarray(img)
    if a.ndim not in (2, 3) or min(a.shape[:2]) < 16:
        return (None, None, None, None,
                f"image inexploitable pour un balayage ({a.shape})")
    h, w = int(a.shape[0]), int(a.shape[1])
    tmp = dossier or travail.creer_dossier("avastack_astro_")
    propre = dossier is None
    chemin = os.path.join(tmp, "empilement_aveugle.fits")
    try:
        bornee, _ = borner_lineaire(img)
        save_image(chemin, bornee)
    except Exception as exc:
        if propre and not garder:
            shutil.rmtree(tmp, ignore_errors=True)
        return None, None, None, None, f"écriture temporaire impossible ({exc})"
    try:
        # PIÈGE de convention : `-fov` d'ASTAP est la HAUTEUR du champ, alors
        # que `fov_deg` reçu ici (comme `catalogues.resoudre`) est la LARGEUR
        # est-ouest → conversion par la forme de l'image. Se tromper d'un
        # facteur h/w fait chercher à la mauvaise échelle et ASTAP répond
        # « No solution found! » (constaté en réel le 23/09/2026 : 2,6° passé
        # pour 1,47° attendu → échec ; avec la conversion → résolu).
        fov_h = (float(fov_deg) * (h / float(w))) if fov_deg else 0.0
        wcs, msg = _resoudre_astap(chemin, ra0=ra0, dec0=dec0,
                                   rayon_deg=rayon_deg, fov_deg=fov_h,
                                   chemin_astap=chemin_astap,
                                   # `timeout` d'astap.py est déduit `int` (défaut
                                   # 300) : notre délai est un float en secondes,
                                   # sans incidence → ignore CIBLÉ.
                                   timeout=timeout,  # pyright: ignore[reportArgumentType]
                                   dossier_sortie=tmp)
    except Exception as exc:          # un wrapper ne doit jamais remonter
        wcs, msg = None, f"exception ASTAP ({exc})"
    if not garder and propre:
        shutil.rmtree(tmp, ignore_errors=True)
    if wcs is None:
        # Message ENRICHI : quand aucune base de BALAYAGE n'est installée et
        # qu'aucune position n'a été donnée, ASTAP ne PEUT pas trouver (les
        # bases D50/D80 ne cherchent qu'au voisinage d'une position) — dire la
        # cause évite de croire à un bug de l'appli.
        if ra0 is None and not balayage_possible(chemin_astap):
            bases = ", ".join(sorted(bases_installees(chemin_astap))) or "aucune"
            return (None, None, None, None,
                    f"ASTAP : {msg} — bases installées : {bases} (aucune base "
                    f"de BALAYAGE) : ASTAP a besoin d'une position de départ "
                    f"approximative. Saisir AD/Dec (même à quelques degrés), "
                    f"ou installer une base G18/H18")
        return None, None, None, None, f"ASTAP : {msg}"
    try:
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        ra_c, dec_c = wcs.vers_radec(np.array([[cx, cy]]))
        ra_c = float(np.ravel(ra_c)[0])
        dec_c = float(np.ravel(dec_c)[0])
        champ = w * float(wcs.echelle_arcsec) / 3600.0
    except Exception as exc:
        return None, None, None, None, f"WCS ASTAP inexploitable ({exc})"
    if not (ASTRO_CHAMP_MIN <= champ <= ASTRO_CHAMP_MAX):
        return (None, None, None, None,
                f"champ résolu par ASTAP hors bornes ({champ:.3f}°)")
    return (wcs, ra_c % 360.0, dec_c, champ,
            f"ASTAP{' aveugle' if not fov_deg else f' (champ indicatif {float(fov_deg):.3f}°)'}"
            f" : {champ:.3f}° de champ, {float(wcs.echelle_arcsec):.3f}″/px, "
            f"centre ({ra_c % 360.0:.4f}°, {dec_c:+.4f}°)")




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

    def __init__(self, solveur: Any = None, dossier: Any = None,
                 limmag: float | None = None) -> None:
        self._solveur: Any = solveur or _resoudre_interne
        self.dossier: Any = dossier       # dossier des catalogues (None = défaut)
        self.limmag: float | None = limmag  # magnitude limite du catalogue
        # Indices de la cible : posés AVANT reset() car un reset de SESSION les
        # conserve (la case reste cochée, les valeurs saisies aussi).
        self.ra0: float | None = None
        self.dec0: float | None = None
        self.champ: float | None = None
        self.reset()

    def effacer_indices(self) -> None:
        """Indices de la cible EFFACÉS — indices ET WCS oubliés.

        Distinct de `reset()` : celui-ci CONSERVE les indices (même cible, on
        repart sur un empilement neuf — la case reste cochée et les valeurs
        saisies aussi). Ici, la CIBLE change (décision d'Alain du 28/09/2026 :
        un autre dossier, donc un autre champ) : garder les coordonnées de
        l'ancienne cible FERAIT ÉCHOUER la résolution de la nouvelle — le
        solveur chercherait à l'ancien endroit du ciel. Le repli d'un `pret`
        resté vrai serait exactement le piège que ce défaut a montré.
        """
        self.ra0 = self.dec0 = self.champ = None
        self.reset()

    # -- cycle de vie ---------------------------------------------------------
    def reset(self) -> None:
        """Session neuve (ou case décochée) : indices CONSERVÉS, WCS oublié."""
        self.wcs: Any = None              # WcsTan de la grille de référence
        self.matrice: np.ndarray = np.eye(2, 3)   # grille courante → grille du solve
        self.info: dict[str, Any] = {}    # dict d'info du solveur
        # Jalon 115 : compteurs du DERNIER ÉCHEC (n_etoiles_img, n_etoiles_cat,
        # n_appariements) — le solveur les renvoie même en échec, mais ils
        # étaient jetés : le message ne disait pas si c'était la DÉTECTION ou
        # l'APPARIEMENT qui manquait. Cf. `resume_echec`.
        self.info_echec: dict[str, Any] = {}
        self.essais: int = 0              # tentatives de résolution (session)
        self.propagations: int = 0        # propagations réussies
        self.derniere_erreur: str = ""
        # Jalon 70 : cause de DONNÉES (catalogue astrométrique absent) — quand
        # elle est posée, les essais s'arrêtent : ce n'est pas l'image qui est
        # en cause, et répéter 20 fois le même échec ne l'aurait pas résolu.
        self.donnees_absentes: str = ""
        self._dernier_essai: float = 0.0
        self._n_dernier_essai: int = 0    # profondeur de l'empilement essayée
                                          # (un doublement justifie un essai
                                          # immédiat : information neuve)

    def indice(self, ra_deg: float, dec_deg: float, champ_deg: float) -> bool:
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
    def pret(self) -> bool:
        """Indices de la cible renseignés (rien d'autre n'est nécessaire pour
        tenter une résolution) ?"""
        return (self.ra0 is not None and self.dec0 is not None
                and self.champ is not None)

    @property
    def resolu(self) -> bool:
        """Un WCS exploitable est disponible ?"""
        return self.wcs is not None

    def peut_essayer(self, n_frames: int,
                     maintenant: float | None = None) -> bool:
        """Une tentative de résolution a-t-elle un sens MAINTENANT ?

        Politique (corrigée le 23/09/2026 après un constat réel d'Alain) :
        indice posé, pas déjà résolu, empilement au moins ASTRO_MIN_FRAMES,
        plafond ASTRO_MAX_ESSAIS non atteint — puis, s'il y a déjà eu des
        essais : délai CROISSANT avec leur nombre (20 s, 40 s, 60 s… plafonné)
        OU empilement qui a DOUBLÉ depuis le dernier essai (information neuve).
        Le délai fixe de 20 s d'avant épuisait le quota en deux minutes, pendant
        que l'empilement était encore trop court — et l'appli n'essayait plus
        jamais, même à 33 frames."""
        if self.resolu or not self.pret:
            return False
        if self.donnees_absentes:
            # Cause de DONNÉES : tant que le catalogue n'est pas là, réessayer
            # ne peut pas aboutir (constat Linux du 27/09/2026 : 20 essais pour
            # répéter le même échec). Dès qu'un catalogue apparaît — fichier
            # déposé, téléchargé, ou dossier changé dans l'interface — les
            # essais repartent, SANS redémarrer l'application.
            if chemin_catalogue_astro(self.dossier) is None:
                return False
            self.donnees_absentes = ""
        n = int(n_frames)
        if n < ASTRO_MIN_FRAMES:
            return False
        if self.essais >= ASTRO_MAX_ESSAIS:
            return False
        if not self.essais:
            return True
        if ASTRO_ESSAI_DOUBLEMENT and self._n_dernier_essai > 0 \
                and n >= 2 * self._n_dernier_essai:
            return True
        t = time.monotonic() if maintenant is None else float(maintenant)
        delai = min(ASTRO_ESSAI_DELAI_S * self.essais, ASTRO_ESSAI_DELAI_MAX_S)
        return (t - self._dernier_essai) >= delai

    def raison_attente(self) -> str:
        """Pourquoi aucune résolution n'est possible maintenant (texte court à
        afficher : jamais de silence sur l'absence de WCS)."""
        if self.resolu:
            return ""
        if self.donnees_absentes:
            # Rien à attendre d'un empilement plus profond : c'est une DONNÉE
            # qui manque — on dit laquelle et où, jamais de silence.
            return f"DONNÉES MANQUANTES — {self.donnees_absentes}"
        if not self.pret:
            return "indices de la cible manquants"
        if self.essais >= ASTRO_MAX_ESSAIS:
            return (f"échec après {self.essais} tentatives"
                    + (f" — {self.derniere_erreur}"
                       if self.derniere_erreur else ""))
        if self.essais:
            # Ni échec définitif ni prêt à réessayer TOUT DE SUITE : dire où on
            # en est (le worker affiche ce texte tel quel).
            return (f"en attente d'un empilement plus profond "
                    f"({self.essais}/{ASTRO_MAX_ESSAIS} essais, dernier sur "
                    f"{self._n_dernier_essai} frames)")
        return ""

    # -- repli : adopter un WCS résolu ailleurs (ASTAP) ----------------------
    def adopter(self, wcs: Any, forme: Any,
                methode: str = "astap") -> tuple[bool, str]:
        """Adopte un WCS DÉJÀ RÉSOLU ailleurs — REPLI ASTAP (décision d'Alain :
        « ASTAP = référence indépendante/repli »). Les indices (centre du champ,
        largeur) sont EXTRAITS du WCS, et la propagation s'appliquera ensuite
        exactement comme après un solve interne (le WCS adopté est un WcsTan,
        seule entrée acceptée par `propager`).

        `forme` = (h, w) de la grille décrite par ce WCS — REQUISE : ASTAP ne
        rend pas la forme de l'image, et le centre ne se lit pas sans elle.
        → (True, texte d'état) / (False, message) ; jamais d'exception."""
        if wcs is None:
            return False, "WCS de repli absent"
        try:
            h, w = int(forme[0]), int(forme[1])
        except (TypeError, IndexError, ValueError):
            return False, "forme (h, w) requise pour adopter un WCS"
        if h <= 0 or w <= 0:
            return False, f"forme invalide ({forme})"
        try:
            ra_c, dec_c = wcs.vers_radec(np.array([[(w - 1) / 2.0,
                                                    (h - 1) / 2.0]]))
            ra_c = float(np.ravel(ra_c)[0])
            dec_c = float(np.ravel(dec_c)[0])
            champ = w * float(wcs.echelle_arcsec) / 3600.0
        except Exception as exc:
            return False, f"WCS de repli inexploitable ({exc})"
        if not (ASTRO_CHAMP_MIN <= champ <= ASTRO_CHAMP_MAX):
            return False, (f"champ du WCS de repli hors bornes "
                           f"({champ:.3f}°) — WCS refusé")
        self.ra0, self.dec0, self.champ = ra_c % 360.0, dec_c, float(champ)
        self.wcs = wcs
        self.matrice = np.eye(2, 3)
        self.info = {"n_etoiles_img": 0, "n_etoiles_cat": 0, "n_appariements": 0,
                     "rms_px": None, "rms_arcsec": None,
                     "echelle_arcsec_px": float(wcs.echelle_arcsec),
                     "angle_deg": float(wcs.angle_deg), "methode": str(methode)}
        self.derniere_erreur = ""
        # Un WCS adopté (ASTAP) rend le catalogue astrométrique inutile pour la
        # session : la cause « données manquantes » tombe.
        self.donnees_absentes = ""
        return True, self.texte_resume()

    # -- résolution -----------------------------------------------------------
    def resoudre_sur(self, img: np.ndarray,
                     n_frames: int | None = None) -> tuple[bool, str]:
        """Résout l'astrométrie de `img` — la GRILLE COMPLÈTE de l'empilement
        (le repère de l'aligneur ; le worker y passe la COUCHE BRUTE du canal
        vert — `_image_reference_de`, jalon 115 — JAMAIS le composite normalisé,
        dont le fond ~0,7 rend le seuil du solveur aveugle). → (True/False,
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
        if n_frames is not None:
            # Profondeur essayée : sert au déclencheur « empilement qui a
            # doublé » (cf. peut_essayer) — un essai sur 16 frames et un sur 32
            # ne mesurent pas la même chose.
            self._n_dernier_essai = int(n_frames)
        try:
            wcs, info, msg = self._solveur(img, self.ra0, self.dec0,
                                           self.champ, dossier=self.dossier,
                                           limmag=self.limmag)
        except Exception as exc:      # un solveur ne doit jamais tuer le worker
            wcs, info, msg = None, {}, f"exception du solveur ({exc})"
        if wcs is None:
            self.derniere_erreur = str(msg or "échec de résolution")
            self.info_echec = dict(info or {})
            resume = self.resume_echec()
            if resume:
                self.derniere_erreur = f"{self.derniere_erreur} {resume}"
            if self.derniere_erreur.startswith(MSG_CATALOGUE_ABSENT):
                self.donnees_absentes = self.derniere_erreur
            return False, self.derniere_erreur
        self.wcs = wcs
        self.matrice = np.eye(2, 3)
        self.info = dict(info or {})
        self.info_echec = {}
        self.derniere_erreur = ""
        self.donnees_absentes = ""
        return True, self.texte_resume()

    def resume_echec(self) -> str:
        """Compteurs du DERNIER échec de résolution, en clair (jalon 115).

        POURQUOI (constat d'Alain, 09/10/2026 : « aucune info dans le journal »
        devant un échec d'astrométrie) : le message ne disait QUE la cause de
        l'appariement (« pas assez de correspondances mutuelles »), jamais
        COMBIEN d'étoiles avaient été vues de chaque côté — impossible de
        distinguer une image trop pauvre (DÉTECTION) d'un catalogue/indices
        inadaptés, ni de soupçonner le DOMAINE de l'image (un composite normalisé
        au fond ~0,7 monte le seuil à ~0,99 : plus rien ne passe). Renvoie
        « [image N étoiles, catalogue M, appariements K] », ou "" si rien."""
        i = self.info_echec or {}
        if not i:
            return ""
        return (f"[image {int(i.get('n_etoiles_img') or 0)} étoiles, "
                f"catalogue {int(i.get('n_etoiles_cat') or 0)}, "
                f"appariements {int(i.get('n_appariements') or 0)}]")

    # -- propagation ----------------------------------------------------------
    def propager(self, M: Any) -> tuple[bool, str]:
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
    def wcs_grille(self, cadre: Any = None, forme: Any = None
                   ) -> tuple[Any, str]:
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

    def mots_cles(self, cadre: Any = None, forme: Any = None
                  ) -> tuple[dict[str, Any], str]:
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
    def texte_resume(self) -> str:
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
