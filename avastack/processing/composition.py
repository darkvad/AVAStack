# -*- coding: utf-8 -*-
"""Compositions multi-filtres (jalon 19) : RGB, HOO, SHO, LRGB, Mono.

Rôles et mapping
----------------
Chaque dossier surveillé est étiqueté d'un RÔLE (le filtre utilisé) :
L, R, G, B, Ha, O3, S2. Une COMPOSITION déclare les rôles attendus et
comment ils alimentent les canaux R/G/B du composite :

  Mono  (1 dossier)  → composite monochrome (le rôle L)
  HOO   (2 dossiers) → R=Ha, G=O3, B=O3
  SHO   (3 dossiers) → R=S2, G=Ha, B=O3 (palette Hubble)
  RGB   (3 dossiers) → R=R, G=G, B=B
  LRGB  (4 dossiers) → R=R, G=G, B=B + luminance L (rôle OPTIONNEL)

Chaîne de traitement (décisions des 18 et 24/09/2026, cf. AVANCEMENT.md) :
  normalisation LINÉAIRE par canal (percentiles) → composite LINÉAIRE BRUT
  (c'est l'empilement enregistré par la sauvegarde linéaire) → CORRECTIONS
  DE COULEUR de la chaîne de sortie (gains SPCC/Gaia/manuels, équilibrage,
  recalage colorimétrique) → étirement global existant (STF ou VeraLux), qui
  ne change PAS : le composite a la même forme (H, W, 3) float32 linéaire que
  l'empilement couleur actuel. AUCUNE correction de couleur dans `composer()`
  (règle d'Alain, 24/09/2026) : sinon le fichier linéaire ne serait ni brut
  ni fini.

Extraction depuis une brute COULEUR (CFA débayerisée) : le signal d'un
filtre étroit se concentre dans des canaux précis (Ha→R, OIII→G+B,
SII→R) — cf. CANAUX_CFA. Une brute MONO (2D) est prise telle quelle :
c'est déjà le canal du rôle.

LRGB et radio « Canal L » (choix d'Alain) : si le dossier L est VIDE,
la radio décide entre « L synthétisé » (L = luminance du composite,
combine identité — prêt pour un futur traitement spécifique du canal L)
et « dégradé en RGB » (composite RGB pur). Si L contient des frames,
il est utilisé quoi qu'il arrive.

Combine L (jalon 117c) : le rapport L/luma est LISSÉ à l'échelle des étoiles
(σ = 1,7 × FWHM mesurée) MAIS SEULEMENT autour des étoiles brillantes (masque) —
sans ce lissage, une PSF de L plus large que celle du RGB dessine un ANNEAU
coloré (halo ×2,8 mesuré le 09/10/2026) ; et le lisser PARTOUT retirerait 9-18 %
du détail fin de la nébuleuse (le détail venait de L). Ailleurs le ratio reste
BRUT → L garde tout son détail sur la nébuleuse. Le mode « L synthétisé » (L =
luminance du composite) est l'identité : aucun lissage.

Combine L, OPT-IN (jalon 117d) : ce lissage est une OPTION — case décochée par
défaut, on obtient alors le combine d'AVANT le 117c (halos visibles) ; et son
SEUIL DE MASQUE est réglable (il est empirique, il dépend du fond). = façade
`CompositeStacker.lissage_halos` / `seuil_masque_halos`, `composer(sigma_l=…)`.
"""

import numpy as np
import cv2
from typing import Any

# Réutilisation SANS modification du socle d'empilement (jalon 15) : la
# façade multi-rôles tient la MÊME géométrie d'intersection (les helpers
# privés _aire_signee/_clip_poly restent dans stacking.py, source unique).
from .stacking import (LiveStacker, _aire_signee, _clip_poly,
                       cadre_intersection, quad_alignement,
                       aligner_canaux, gains_equilibre)
# Mesure de la FWHM des étoiles (jalon 10) — sert au lissage du combine LRGB
# (jalon 117c). `stars` est une feuille du paquet (numpy/cv2 seulement) :
# aucun cycle d'import, comme dans alignment.py.
from . import stars as _stars

# Rôles possibles d'un dossier (un rôle = un filtre).
ROLES: tuple[str, ...] = ("L", "R", "G", "B", "Ha", "O3", "S2")

# Canal(x) d'une brute COULEUR (H, W, 3) à extraire pour chaque rôle.
# "luma" = luminance pondérée ; un tuple = moyenne des canaux listés.
_POIDS_LUMA: tuple[float, float, float] = (0.299, 0.587, 0.114)   # R, G, B
CANAUX_CFA: dict[str, Any] = {
    "L": "luma",                             # luminance d'une brute couleur
    "R": (0,), "Ha": (0,), "S2": (0,),       # signal dans le rouge
    "G": (1,),
    "B": (2,),
    "O3": (1, 2),                            # OIII : vert + bleu
}

# Compositions : rôles attendus (ordre = ordre de saisie dans l'UI),
# rôles optionnels, mapping vers les canaux du composite.
COMPOSITIONS: dict[str, dict[str, Any]] = {
    "Mono": {"roles": ("L",), "optionnels": ()},
    "HOO":  {"roles": ("Ha", "O3"), "optionnels": (),
             "canaux_rgb": {"R": ("Ha",), "G": ("O3",), "B": ("O3",)}},
    "SHO":  {"roles": ("S2", "Ha", "O3"), "optionnels": (),
             "canaux_rgb": {"R": ("S2",), "G": ("Ha",), "B": ("O3",)}},
    "RGB":  {"roles": ("R", "G", "B"), "optionnels": (),
             "canaux_rgb": {"R": ("R",), "G": ("G",), "B": ("B",)}},
    "LRGB": {"roles": ("L", "R", "G", "B"), "optionnels": ("L",),
             "canaux_rgb": {"R": ("R",), "G": ("G",), "B": ("B",)},
             "luminance": ("L",)},
}

MODES_L: tuple[str, ...] = ("synthetise", "degrade")   # radio « Canal L » (L vide)


def roles_de(composition: str) -> tuple[str, ...]:
    """Rôles attendus d'une composition (dans l'ordre de saisie UI)."""
    return COMPOSITIONS[composition]["roles"]


def roles_optionnels(composition: str) -> tuple[str, ...]:
    """Rôles qui peuvent rester vides sans bloquer la composition."""
    return COMPOSITIONS[composition]["optionnels"]

# Alias usuels du mot-clé FITS FILTER (jalon 19) : N.I.N.A., APT, SGP, ASI
# Air et les roues à filtres écrivent des graphies différentes du même
# filtre. Clés NORMALISÉES (majuscules, séparateurs supprimés à la lecture).
FILTRES_USUELS: dict[str, str] = {
    "HA": "Ha", "HALPHA": "Ha", "H": "Ha",
    "OIII": "O3", "O3": "O3", "O": "O3",
    "SII": "S2", "S2": "S2", "S": "S2",
    "RED": "R", "R": "R",
    "GREEN": "G", "G": "G",
    "BLUE": "B", "B": "B",
    "LUM": "L", "LUMINANCE": "L", "L": "L", "CLEAR": "L", "CL": "L",
    "IR": "L", "IRCUT": "L", "NONE": "L",
}


def role_de_filtre(filtre: Any) -> str | None:
    """Rôle (ROLES) correspondant à la valeur du mot-clé FITS FILTER
    (« Ha », « H-alpha », « OIII », « Red », « L »…), ou None si non reconnu
    (le dossier garde alors son rôle déclaré à la main)."""
    if filtre is None:
        return None
    cle = str(filtre).strip().upper()
    for sep in (" ", "-", "_", ".", "/"):
        cle = cle.replace(sep, "")
    return FILTRES_USUELS.get(cle)




# ------------------------------------------------------------ extraction ---
def extraire_canal(img: np.ndarray, role: str) -> np.ndarray:
    """Carte 2D float32 du rôle depuis une brute/empilement du dossier :
    mono (H, W) → telle quelle ; couleur (H, W, 3) → canal(x) du rôle
    (CANAUX_CFA : moyenne si plusieurs, luma pondérée pour L).
    Rôle inconnu → luminance (comportement sûr par défaut)."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim == 2:
        return a
    if a.ndim != 3 or a.shape[-1] != 3:
        raise ValueError(f"Forme d'image non gérée pour le rôle "
                         f"{role!r} : {a.shape}")
    c = CANAUX_CFA.get(role, "luma")
    if c == "luma":
        return (_POIDS_LUMA[0] * a[..., 0] + _POIDS_LUMA[1] * a[..., 1]
                + _POIDS_LUMA[2] * a[..., 2]).astype(np.float32)
    return a[..., list(c)].mean(axis=-1).astype(np.float32)


# ------------------------------------------------------- normalisation ----
def _echantillon(img: np.ndarray, cible: int = 512 * 512) -> np.ndarray:
    """Sous-échantillonnage régulier (~`cible` pixels) : les percentiles
    restent représentatifs à coût constant, même en 16 Mpx."""
    pas = max(1, int(round(np.sqrt(img.size / float(cible)))))
    return img[::pas, ::pas]


def bornes_normalisation(img: np.ndarray, lo_pct: float = 0.25,
                         hi_pct: float = 99.7) -> tuple[float, float]:
    """Bornes (lo, hi) robustes d'un canal (percentiles bas/haut).
    Public : permet à l'app de les FIGER (composite stable entre deux
    frames) avant d'appeler composer()."""
    s = _echantillon(np.asarray(img, dtype=np.float32))
    lo = float(np.percentile(s, lo_pct))
    hi = float(np.percentile(s, hi_pct))
    if hi - lo < 1e-9:
        hi = lo + 1e-9                        # canal plat → éviter /0
    return lo, hi


def normaliser(img: np.ndarray, lo: float | None = None,
               hi: float | None = None, lo_pct: float = 0.25,
               hi_pct: float = 99.7) -> np.ndarray:
    """Normalisation LINÉAIRE [lo..hi] → 0..1, SANS clip : les étoiles
    brillantes restent > 1 (l'empilement reste linéaire, convention du
    projet). bornes figées = composite stable entre deux frames.

    Jalon 79 : plus de `.astype(np.float32)` final — c'était une COPIE
    INUTILE (numpy copie même quand le dtype est déjà le bon) : `a` est
    float32 et lo/hi sont des scalaires Python, l'expression est donc DÉJÀ en
    float32, valeur identique au bit (mesuré : `composer('HOO')` 225 → 82 ms)."""
    a = np.asarray(img, dtype=np.float32)
    if lo is None or hi is None:
        lo, hi = bornes_normalisation(a, lo_pct, hi_pct)
    return (a - lo) / (hi - lo)


# ------------------------------------------------------------- composer ---
def _channel_de(norm: Any, roles: Any, forme: Any) -> np.ndarray:
    """Moyenne des rôles normalisés alimentant un canal ; absent → zéros
    (canal neutre, la composition ne plante jamais sur un dossier vide).

    Jalon 79 : ① un SEUL rôle est rendu TEL QUEL (`np.mean` d'une liste d'un
    élément ne faisait que copier) ; ② plus de `.astype` final (copie inutile :
    le résultat est déjà float32). Le tableau rendu est partagé avec `norm` —
    il n'est jamais modifié (`np.stack` recopie)."""
    dispo = [norm[r] for r in roles if norm.get(r) is not None]
    if not dispo:
        return np.zeros(forme, np.float32)
    if len(dispo) == 1:
        return dispo[0]
    return np.mean(dispo, axis=0)


def _luma(rgb: np.ndarray) -> np.ndarray:
    """Luminance pondérée d'un composite (H, W, 3)."""
    return (_POIDS_LUMA[0] * rgb[..., 0] + _POIDS_LUMA[1] * rgb[..., 1]
            + _POIDS_LUMA[2] * rgb[..., 2])


# ------------------------------------ combine LRGB : lissage du ratio L/luma ---
# Jalon 117c (v2.70.0). Reçu MESURÉ le 09/10/2026 sur le jeu réel M31 LRGB
# (L du 13/09 + R/G/B du 22-23/09, deux nuits à 176,2°) : le combine
# `rgb *= L/luma` AMPLIFIE les AILES des étoiles, parce que la PSF de L (autre
# nuit, autre filtre) est plus large que celle de la luminance RGB — le rapport
# L/luma vaut 1,00 au cœur mais MONTE à ~3 dans les ailes (r ≈ 4-5 px), et
# chaque étoile brillante prend un ANNEAU coloré (rapport anneau/cœur 0,124 en
# RGB seul → 0,347 avec L = halo ×2,8). CAUSE : ni l'alignement (résidu ramené à
# ~0,2 px au 117b) ni l'optique (FWHM L/R/V/B identiques, R/G = 1,039) — c'est
# le COMBINE. Il ne s'agit PAS du réglage de couleur : le combine est neutre
# (`rgb * ratio[..., None]`), l'anneau prend simplement la couleur des ailes.
# CORRECTIF : LISSER le rapport à l'ÉCHELLE DES ÉTOILES → la luminance n'apporte
# plus que le GRAND ÉCHELLE (nébuleuse), sans épaissir les halos. σ = 1,7 × FWHM
# est le réglage qui ramène le rapport anneau/cœur au niveau du RGB seul ; un σ
# de 0,5-1 px (rayon proposé par erreur) NE SUFFISAIT PAS (0,347 → 0,338/0,286).
#
# ⚠ MESURÉ SUR LES COUCHES RÉELLES (10/10/2026) : lisser le ratio PARTOUT ne va
# pas — `composite_lum = luma(rgb) × ratio`, donc au repos (= sans lissage) le
# détail fin de la NÉBULEUSE vient de L (profond) ; en le lissant partout, ce
# détail fin vient désormais de la luminance RGB (bruitée) → −9 % de détail fin
# en linéaire, −16/-18 % après étirement, changement LARGE BANDE (60 % de
# l'énergie fine). Or le mismatch de PSF L↔RGB n'existe QU'À L'ÉCHELLE DES
# ÉTOILES (sur la nébuleuse la structure est ≫ PSF). D'où le correctif JUSTE :
# lisser le ratio SEULEMENT autour des ÉTOILES BRILLANTES (là où elles prennent
# un halo) et garder le ratio BRUT ailleurs → détail de L préservé (−4 % au lieu
# de −16 %, mesuré) ET halos éteints.
SIGMA_L_PAR_FWHM: float = 1.7   # σ du flou du ratio ≈ 1,7 × FWHM des étoiles
SIGMA_L_MIN: float = 1.0        # plancher (px) — un lissage nul ne sert à rien
SIGMA_L_MAX: float = 15.0       # plafond (px) — n'efface pas le grand échelle
# Repli quand AUCUNE étoile n'est mesurable (champ sans étoile, image minuscule) :
# il n'y a alors pas de halo à corriger — on garde un lissage de SÉCURITÉ
# proportionnel à la LARGEUR (donc à la RÉSOLUTION), même esprit que les rayons
# de chroma (couleurs.rayon_chroma_apercu).
SIGMA_L_REPLI_FRAC: float = 1.0 / 800.0
# --- masque d'étoiles (n'ÉTOILES que les étoiles, pas la nébulosité) ----------
# Étoile = pic > fond + SEUIL_MASQUE_SIGMA·bruit (médiane-MAD), et BOÎTE
# ENGLOBANTE petite : au-delà de LIMITE_MASQUE_PX c'est un bras de galaxie, le
# cœur ou une nébulosité (structure LARGE), qu'il ne faut PAS lisser. Le masque
# est ensuite DILATÉ de DILAT_MASQUE_FWHM·σ (les ailes d'étoile, seul endroit où
# L et le RGB diffèrent) puis FONDU à σ/2 (aucune couture).
# ⚠ SEUIL_MASQUE_SIGMA MESURÉ sur le jeu M31 (10/10/2026) : le DISQUE de la
# galaxie gonfle la MAD, si bien qu'un seuil « classique » (6σ) laisse passer le
# disque (10 900 composantes → masque = 30 % de l'image, donc lissage quasi
# global). À 20σ on ne garde que ~4 000 sources vraiment brillantes (~11 % de
# l'image après dilatation) : le détail de la nébuleuse remonte de 0,84 (lissage
# global) à 0,92, tout en masquant les étoiles qui portent un halo. Compromis
# à réviser si le test réel montre qu'un halo survit.
SEUIL_MASQUE_SIGMA: float = 20.0
# Jalon 117d : le seuil ci-dessus est EMPIRIQUE (il dépend du fond — le disque
# d'une galaxie gonfle la MAD). Il devient RÉGLABLE depuis l'interface (case
# opt-in « Lisser le combine LRGB », champ « σ du masque ») : ces deux bornes
# encadrent la saisie (l'app les applique, `composer` les accepte telles quelles).
SEUIL_MASQUE_MIN: float = 3.0
SEUIL_MASQUE_MAX: float = 100.0
LIMITE_MASQUE_PX: int = 60
DILAT_MASQUE_FWHM: float = 1.5


def _lisser_ratio(ratio: np.ndarray, sigma: float) -> np.ndarray:
    """Flou gaussien ISOTROPE du ratio de luminance L/luma (jalon 117c), σ en
    PIXELS de l'image traitée. `sigma` ≤ 0 → ratio INCHANGÉ (aucun flou)."""
    if not (sigma > 0.0):
        return ratio
    return cv2.GaussianBlur(ratio, (0, 0), sigmaX=float(sigma))


def _masque_etoiles(lum: np.ndarray, sigma: float,
                    seuil: float | None = None) -> np.ndarray | None:
    """Masque (0..1, feutré) des ÉTOILES BRILLANTES de la luminance RGB `lum`,
    ou None s'il n'y en a AUCUNE. Brique du lissage du ratio (jalon 117c) :
    seules les étoiles brillantes prennent un halo (le mismatch de PSF L↔RGB
    n'existe qu'à leur échelle), on ne lisse donc QUE là — la nébuleuse garde le
    ratio BRUT, donc le détail de L.

    Étoile = composante au-dessus de `fond + seuil·bruit` (médiane/MAD,
    robustes) dont la BOÎTE ENGLOBANTE est < LIMITE_MASQUE_PX : au-delà, c'est un
    bras de galaxie / le cœur / une nébulosité — une structure LARGE, qu'il ne
    faut PAS lisser. Le masque est ensuite DILATÉ de DILAT_MASQUE_FWHM·σ (les
    ailes d'étoile, là où L déborde du RGB) puis FONDU à σ/2 (aucune couture).

    `seuil` (jalon 117d) : le seuil en σ, réglable par l'utilisateur (case
    opt-in). None → `SEUIL_MASQUE_SIGMA` (défaut historique du 117c)."""
    h, w = lum.shape
    if min(h, w) < 16:
        return None
    ech = lum[::4, ::4]
    fond = float(np.median(ech))
    bruit = 1.4826 * float(np.median(np.abs(ech - fond)))
    if bruit <= 1e-9:
        return None
    seuil_sig = SEUIL_MASQUE_SIGMA if seuil is None else float(seuil)
    binaire = (lum > fond + seuil_sig * bruit).astype(np.uint8)
    if not binaire.any():
        return None
    nb, labels, stats, _c = cv2.connectedComponentsWithStats(binaire,
                                                             connectivity=8)
    # Les stubs cv2 renvoient `MatLike` (typage large) : on caste pour que le
    # typage de l'indexation vectorielle ci-dessous reste vérifiable (pyright).
    lab = np.asarray(labels, dtype=np.int64)
    st = np.asarray(stats, dtype=np.int64)
    ok = np.zeros(nb, dtype=bool)              # composante = ÉTOILE ?
    for i in range(1, nb):
        ok[i] = (int(st[i, cv2.CC_STAT_WIDTH]) <= LIMITE_MASQUE_PX
                 and int(st[i, cv2.CC_STAT_HEIGHT]) <= LIMITE_MASQUE_PX)
    garde = ok[lab].astype(np.uint8)           # vectorisé (sans boucle pixel)
    if not garde.any():
        return None
    rayon = max(1, int(round(DILAT_MASQUE_FWHM * float(sigma))))
    noyau = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (2 * rayon + 1, 2 * rayon + 1))
    garde = cv2.dilate(garde, noyau)
    fondu = cv2.GaussianBlur(garde.astype(np.float32), (0, 0),
                             max(1.0, 0.5 * float(sigma)))
    return np.clip(fondu * 2.0, 0.0, 1.0).astype(np.float32)


def _lisser_ratio_masque(ratio: np.ndarray, lum: np.ndarray, sigma: float,
                         seuil: float | None = None) -> np.ndarray:
    """Ratio L/luma lissé SEULEMENT dans le masque d'étoiles brillantes (jalon
    117c) : `ratio` lissé là où le masque vaut 1, `ratio` BRUT ailleurs — le
    détail fin de L est donc PRÉSERVÉ sur la nébuleuse. Sans étoile brillante
    (masque None) → ratio BRUT : il n'y a rien à corriger.

    `seuil` (jalon 117d) : seuil du masque en σ (None → `SEUIL_MASQUE_SIGMA`).
    σ ≤ 0 court-circuite AVANT tout calcul : c'est le chemin « case décochée »,
    bit-identique au comportement d'avant le 117c."""
    if not (sigma > 0.0):                      # σ ≤ 0 = pas de flou (opt-out)
        return ratio
    masque = _masque_etoiles(lum, sigma, seuil)
    if masque is None:
        return ratio
    lisse = cv2.GaussianBlur(ratio, (0, 0), sigmaX=float(sigma))
    return (lisse * masque + ratio * (1.0 - masque)).astype(np.float32)


def sigma_l_auto(lum: np.ndarray) -> float:
    """σ (px) du lissage du ratio L/luma, déduit de la TAILLE DES ÉTOILES de la
    luminance RGB `lum` (carte 2D) : `SIGMA_L_PAR_FWHM × FWHM`, borné à
    [SIGMA_L_MIN, SIGMA_L_MAX].

    POURQUOI auto : un σ FIXE en pixels serait faux dès que la résolution change
    (l'aperçu est réduit à ≤ 1600 px, les canaux en pleine résolution font
    plusieurs milliers de px). La FWHM est mesurée par `stars.mesurer_seeing`
    (jalon 10) SUR l'image reçue → elle suit la résolution, comme les rayons de
    chroma. Aucune étoile mesurable (nb = 0, image minuscule) → repli
    proportionnel à la largeur (`SIGMA_L_REPLI_FRAC`) : il n'y a alors pas de
    halo à corriger. N'échoue JAMAIS (mesure enveloppée) — même contrat que
    `stars.mesurer_seeing`."""
    sigma = None
    try:
        mesure, _msg = _stars.mesurer_seeing(np.asarray(lum, dtype=np.float32))
    except Exception:
        mesure = None
    if isinstance(mesure, dict):
        fwhm = mesure.get("fwhm")
        if fwhm is not None:
            try:
                f = float(fwhm)
            except (TypeError, ValueError):
                f = 0.0
            if np.isfinite(f) and f > 0.0:
                sigma = SIGMA_L_PAR_FWHM * f
    if sigma is None:
        sigma = SIGMA_L_REPLI_FRAC * float(np.asarray(lum).shape[-1])
    return float(min(max(sigma, SIGMA_L_MIN), SIGMA_L_MAX))


def _echelle_commune(canaux: Any, spec: Any, lo_pct: float,
                     hi_pct: float) -> float | None:
    """ÉCHELLE partagée par les trois rôles du composite : l'amplitude
    (p99,7 − p0,25) du rôle qui alimente le canal VERT — référence habituelle
    des travaux couleur, comme le recalage « Linear Fit » qui cale R et B sur G
    — sinon du premier rôle non vide. → float > 0, ou None si aucun rôle.

    POURQUOI (option, décision d'Alain du 25/09/2026) : par défaut `composer()`
    cale CHAQUE rôle sur SES percentiles, avec SON point noir. Or un percentile
    bas est toujours à ~2,8 σ sous le ciel : le NIVEAU du fond du composite
    devient donc PROPORTIONNEL AU BRUIT du canal. Deux conséquences mesurées
    sur l'empilement M31 d'Alain :
      • empiler plus fait baisser le fond ET le grain dans la même proportion,
        l'étirement compense, et le grain du fond ne s'améliore JAMAIS
        (fond/σ = 2,88 à 28 frames, 2,50 à 111 frames, alors que le grain
        diminuait bien en ÷2,2, soit 1/√n) ;
      • le grain est COLORÉ (R/G 0,66 · B/G 1,45) puisque chaque canal est
        divisé par SA dynamique (celle du bleu est 2,1× plus étroite).
    En partageant l'ÉCHELLE du vert et en ne soustrayant AUCUN point noir par
    canal, le fond garde son niveau et sa couleur PHYSIQUES : seul le bruit
    baisse (1/√n) → le grain du fond s'améliore enfin avec l'intégration, et il
    redevient gris. Les coefficients SPCC, eux, sont des RATIOS mesurés sur les
    COUCHES : avec une échelle commune ils s'appliquent enfin sur la base où ils
    ont été mesurés.

    NB (pourquoi PAS un point noir commun) : les ciels des trois canaux n'ont
    pas le même niveau ; retrancher le point noir du vert rendrait le fond de R
    et B NÉGATIF (constaté : −4 % et −2 % de l'amplitude sur l'empilement M31),
    ce qui écrête leur bruit au premier étirement et teinte le fond en vert. Une
    échelle pure ne pose pas ce problème — c'est le comportement du mode MONO,
    où aucun point noir n'est soustrait."""
    roles = []
    g = (spec.get("canaux_rgb") or {}).get("G") or ()
    roles.extend(r for r in g if canaux.get(r) is not None)
    roles.extend(r for r in spec["roles"]
                 if r not in roles and canaux.get(r) is not None)
    for role in roles:
        a = np.asarray(canaux[role], dtype=np.float32)
        if a.size:
            lo, hi = bornes_normalisation(a, lo_pct, hi_pct)
            return max(hi - lo, 1e-9)
    return None


def composer(canaux: Any, composition: str, bornes: Any = None,
             normaliser_canal: bool = True, mode_l: str = "synthetise",
             lo_pct: float = 0.25, hi_pct: float = 99.7,
             normalisation_commune: bool = False,
             sigma_l: float | None = None,
             seuil_masque_sigma: float | None = None) -> np.ndarray | None:
    """Composite linéaire d'une composition.

    canaux   : dict rôle → carte 2D float32 (empilement du rôle), ou None
               pour un rôle sans aucune frame.
    bornes   : dict rôle → (lo, hi) pour FIGER la normalisation par rôle
               (sinon recalculée à chaque appel — attention, la borne
               bouge légèrement à chaque nouvelle frame).
    normaliser_canal : False → les canaux sont déjà normalisés (le combine
               L reste appliqué).
    normalisation_commune : True → les trois rôles partagent la MÊME ÉCHELLE
               (l'amplitude du rôle qui alimente le canal VERT) et AUCUN point
               noir n'est soustrait : les niveaux et les couleurs du fond
               restent PHYSIQUES, seul le bruit baisse avec l'intégration (1/√n)
               et le grain cesse d'être coloré. Option (décision d'Alain du
               25/09/2026) — cf. `_echelle_commune`.
    mode_l   : "synthetise" | "degrade" — sortie de la radio « Canal L »,
               utilisée SEULEMENT si le rôle L est vide.
    sigma_l  : σ (px) du flou du RATIO L/luma du combine LRGB (jalon 117c), en
               MASQUANT les étoiles brillantes (le ratio n'est lissé QUE là ;
               ailleurs il reste BRUT, donc L garde son détail sur la nébuleuse).
               None (DÉFAUT) → σ déduit de la FWHM des étoiles (`sigma_l_auto`) ;
               > 0 → σ imposé ; 0 (ou ≤ 0) → AUCUN flou = comportement d'avant
               le 117c. Sans objet hors composition à luminance (LRGB) et quand L
               est SYNTHÉTISÉ (L = luminance du composite : combine identité).
    seuil_masque_sigma : seuil du masque d'étoiles, en σ au-dessus du fond
               (jalon 117d). None (DÉFAUT) → `SEUIL_MASQUE_SIGMA` (20). Réglable
               car ce seuil est EMPIRIQUE : il dépend du fond (le disque d'une
               galaxie gonfle la MAD) — voir la constante et `_masque_etoiles`.
               N'a d'effet que si `sigma_l` déclenche effectivement le lissage.

    → (H, W, 3) float32 linéaire, (H, W) pour Mono, ou None si AUCUN rôle
    n'a de données. ValueError si les formes des rôles diffèrent (l'app
    doit recadrer sur le cadre commun AVANT d'appeler).

    AUCUNE correction de couleur n'est appliquée ici (décision d'Alain,
    24/09/2026) : les gains SPCC/Gaia/manuels, l'équilibrage des canaux et
    le recalage colorimétrique appartiennent à la CHAÎNE DE SORTIE, en aval
    (`corrections_couleur` / `CompositeStacker.mean(corrections=True)`).
    Conséquence directe : `composer()` seul produit l'EMPILEMENT BRUT — la
    référence linéaire sauvegardée."""
    if composition not in COMPOSITIONS:
        raise ValueError(f"Composition inconnue : {composition!r}")
    if mode_l not in MODES_L:
        mode_l = "synthetise"
    spec = COMPOSITIONS[composition]
    bornes = bornes or {}

    # 1) normalisation par rôle (rôle vide → ignoré, jamais bloquant)
    norm = {}
    echelle = (_echelle_commune(canaux, spec, lo_pct, hi_pct)
               if (normaliser_canal and normalisation_commune) else None)
    for role in spec["roles"]:
        img = canaux.get(role)
        if img is None:
            continue
        a = np.asarray(img, dtype=np.float32)
        if a.size == 0:
            continue
        if normaliser_canal:
            if echelle is not None:
                # ÉCHELLE PARTAGÉE (option) : aucune soustraction par canal —
                # le fond garde son niveau et sa couleur physiques (cf.
                # `_echelle_commune`).
                a = normaliser(a, 0.0, echelle)
            else:
                lo, hi = bornes.get(role) or (None, None)
                a = normaliser(a, lo, hi, lo_pct, hi_pct)
        norm[role] = a

    if not norm:
        return None                            # aucune donnée du tout

    # 2) Mono : composite monochrome direct
    if "canaux_rgb" not in spec:
        return norm[spec["roles"][0]]

    forme = norm[next(iter(norm))].shape
    for r, a in norm.items():
        if a.shape != forme:
            raise ValueError(
                f"Formes hétérogènes entre les rôles ({r} : {a.shape} vs "
                f"{forme}) — recadrer sur le cadre commun avant composer()")

    # 3) canaux R/G/B du composite (SANS gain : les corrections de couleur
    #    sont appliquées APRÈS la composition, dans la chaîne de sortie)
    rgb = [_channel_de(norm, spec["canaux_rgb"][canal], forme)
           for canal in ("R", "G", "B")]
    rgb = np.stack(rgb, axis=-1)

    # 4) LRGB : combine luminance — L du dossier s'il a des frames, sinon
    #    la radio décide (« synthétisé » = luminance du composite, combine
    #    identité aujourd'hui, prêt pour un traitement spécifique de L)
    if "luminance" in spec:
        L = norm.get(spec["luminance"][0])
        l_du_dossier = L is not None
        if L is None and mode_l == "synthetise":
            L = _luma(rgb)
        if L is not None:
            lum = _luma(rgb)
            ratio = np.where(lum > 1e-6,
                             L / np.maximum(lum, 1e-6),
                             1.0).astype(np.float32)
            # Jalon 117c : un L VENU DU DOSSIER a une PSF plus large que celle
            # du RGB → son rapport brut AMPLIFIE les ailes des étoiles (anneau
            # coloré). On LISSE le ratio À L'ÉCHELLE DES ÉTOILES, mais SEULEMENT
            # autour des étoiles BRILLANTES (masque) : ailleurs le ratio reste
            # BRUT, donc le détail fin de L est préservé sur la nébuleuse (le
            # lisser PARTOUT retirait 9-18 % du détail fin — mesuré). σ =
            # `sigma_l` s'il est fourni, sinon déduit de la FWHM des étoiles
            # (`sigma_l_auto`). Le mode « synthétisé » (L = luminance du
            # composite) est l'IDENTITÉ (ratio ≡ 1) : rien à lisser.
            if l_du_dossier:
                sig = sigma_l if sigma_l is not None else sigma_l_auto(lum)
                ratio = _lisser_ratio_masque(ratio, lum, float(sig),
                                             seuil_masque_sigma)
            rgb = (rgb * ratio[..., None]).astype(np.float32)

    return rgb


# ------------------------------------------- corrections de couleur (sortie) ---
# DÉCISION D'ALAIN (24/09/2026, cf. CLAUDE.md § Sauvegardes) : la sauvegarde
# linéaire est BRUTE — ni gradient retiré, ni correction de couleur. Les
# corrections de couleur (SPCC, gains photométriques Gaia, gains manuels de
# l'UI, équilibrage des canaux, recalage colorimétrique « Linear Fit ») vivent
# dans la CHAÎNE DE SORTIE : affichage, solveur live, sortie « traitée ». Elles
# sont donc appliquées APRÈS `composer()` (donc après la normalisation par
# rôle, qui n'absorbe plus rien) et JAMAIS dans le fichier brut.
#
# Ordre validé par Alain (décision (c)) : ... → débruitage → CORRECTIONS
# (gains + équilibrage + recalage) → netteté/chaîne couleur → étirement.

def appliquer_gains_canaux(img: np.ndarray, gains: Any,
                           force: float = 1.0) -> np.ndarray:
    """Multiplie chaque canal d'un composite par un gain par CANAL
    (séquence de 3, ordre R/G/B). `force` < 1 atténue la correction
    (`gains ** force`, comme l'équilibrage à force partielle). → COPIE ;
    image inchangée si elle n'est pas un composite couleur ou sans gains."""
    if img is None or gains is None:
        return img
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return img
    g = np.asarray(gains, dtype=np.float32)
    if g.shape != (3,):
        return img
    if force < 1.0:
        g = g ** float(force)
    if bool(np.allclose(g, 1.0)):
        return img
    return (a * g.reshape(1, 1, 3)).astype(np.float32)


def appliquer_gains(img: np.ndarray, gains: Any) -> np.ndarray:
    """Applique des gains R/G/B (dict 'R'/'G'/'B' → facteur) à un composite
    (H, W, 3). → COPIE (ou l'image telle quelle si rien à faire) ; no-op sur
    une image qui n'est pas un composite couleur."""
    if img is None or not gains:
        return img
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return img
    g = [float(gains.get(c, 1.0)) for c in ("R", "G", "B")]
    if abs(g[0] - 1.0) < 1e-9 and abs(g[1] - 1.0) < 1e-9 \
            and abs(g[2] - 1.0) < 1e-9:
        return img
    return appliquer_gains_canaux(a, np.array(g, np.float32))


def appliquer_equilibrage(img: np.ndarray, cadre: Any = None,
                          force: float = 1.0) -> np.ndarray:
    """Équilibrage des canaux (« auto », jalon 13) appliqué à un COMPOSITE :
    gains dérivés du FOND (percentile bas), force < 1 → correction partielle.
    → COPIE ; no-op si l'image n'est pas un composite couleur ou si le fond
    est dégénéré (canal noir : aucun gain raisonnable)."""
    if img is None:
        return img
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return img
    gains = gains_equilibre(a, cadre)
    if gains is None:
        return img
    return appliquer_gains_canaux(a, gains, force)


def corrections_couleur(img: np.ndarray, gains: Any = None,
                        wb_auto: bool = False, wb_force: float = 1.0,
                        cadre: Any = None, linear_fit: bool = False,
                        linear_fit_mode: str = "offset"
                        ) -> tuple[np.ndarray, Any]:
    """CHAÎNE DES CORRECTIONS DE COULEUR d'un composite (décision (c)) :
    gains (manuels × SPCC/Gaia) → équilibrage des canaux (auto) → recalage
    colorimétrique « Linear Fit ». SANS état ni cache : utilisable telle
    quelle depuis la façade (`CompositeStacker`, qui gère ses caches) comme
    depuis le thread du solveur live, qui re-compose l'image traitée.

    → (image corrigée, diag du recalage — None si aucun recalcul). L'entrée
    n'est JAMAIS modifiée ; une image non couleur (mono, 2D) ressort telle
    quelle (ces corrections portent sur les couleurs)."""
    out = appliquer_gains(img, gains)
    diag = None
    if wb_auto:
        out = appliquer_equilibrage(out, cadre, wb_force)
    if linear_fit:
        out, diag = aligner_canaux(out, mode=linear_fit_mode)
    return out, diag


# ------------------------------------------------------ façade worker -----
def composition_pour_roles(roles: Any) -> str | None:
    """Composition correspondant à un ensemble de rôles (jalon 19, phase 2 :
    SANS choix UI encore, le worker la déduit des dossiers configurés).
    Correspondance EXACTE d'abord ; sinon la première composition dont les
    rôles englobent ceux fournis (ordre HOO, SHO, RGB, LRGB) — ex.
    (« Ha »,) → HOO (O3 restera vide, canal neutre). → nom, ou None si vide."""
    roles = tuple(roles)
    if not roles:
        return None
    for nom in COMPOSITIONS:
        if COMPOSITIONS[nom]["roles"] == roles:
            return nom
    ens = set(roles)
    for nom in ("HOO", "SHO", "RGB", "LRGB"):
        if ens <= set(COMPOSITIONS[nom]["roles"]):
            return nom
    return None


class CompositeStacker:
    """Façade multi-rôles (jalon 19, phase 2) : UN LiveStacker par rôle.

    Imite l'interface de LiveStacker telle que le worker l'utilise
    (add / mean / n / cadre / note_alignement / k / set_rejet / wb_auto /
    wb_force / reset) — ainsi TOUT le code existant du worker (aperçu,
    sauvegardes, traitement externe) fonctionne sans le savoir : mean()
    renvoie le COMPOSITE linéaire, corrections de couleur comprises
    (`mean(corrections=False)` renvoie l'empilement BRUT).

    Décisions tranchées (AVANCEMENT.md, 18/09/2026) :
    - les stackers de rôle accumulent des CANAUX 2D (extraire_canal) dans le
      repère des frames alignées — l'aligneur est PARTAGÉ (référence unique),
      donc tous les rôles partagent le MÊME repère ;
    - l'intersection des zones couvertes est tenue GLOBALEMENT (un seul
      polygone, tous rôles confondus) : c'est le CADRE COMMUN appliqué avant
      composer() — les stackers de rôle n'ont pas à se recadrer entre eux ;
    - mean(recadre=False) renvoie le composite SANS recadrage (même repère
      que les frames) — mais NORMALISÉ (chaque rôle est calé sur ses propres
      percentiles) : ce n'est donc PAS le domaine des brutes. Comme référence
      d'ALIGNEMENT, passer la COUCHE 2D BRUTE du rôle du canal VERT
      (`moyennes(recadre=False)`, cf. `worker._image_reference`, jalon 113) :
      sinon `canal_alignement` écrase les brutes suivantes à 0 → ORB aveugle
      (8-9 refus sur 12 frames MESURÉS).
    """

    def __init__(self, composition: str, k: float | None = 3.0, warmup: int = 5,
                 method: str = "kappa", window: int = 8) -> None:
        if composition not in COMPOSITIONS:
            raise ValueError(f"Composition inconnue : {composition!r}")
        self.composition: str = composition
        self._k: float | None = k
        self.warmup: int = warmup
        self._method: str = method if method in LiveStacker.METHODES else "kappa"
        self._window: int = max(3, int(window))
        self._wb_auto: bool = False
        self._wb_force: float = 1.0
        self.gains: Any = None            # gains R/G/B (UI, phase 3)
        # Jalon 56 (étape 5) : gains PHOTOMÉTRIQUES par rôle (zéro-point Gaia,
        # mesuré par processing/photometrie). Posés par le worker depuis la
        # mesure de la SESSION ; vide = AUCUNE correction (défaut : la mesure
        # seule n'a jamais touché l'image). Appliqués aux CARTES DE RÔLE dans
        # `moyennes()` — donc au composite ET aux couches transmises au solveur
        # live, en un seul point : les deux vues restent cohérentes.
        self.gains_roles: dict[str, Any] = {}
        # v2.36.0 — OPTION (décision d'Alain, 25/09/2026) : normalisation
        # COMMUNE des canaux. Défaut False = comportement historique (chaque
        # rôle calé sur SES percentiles). True : les trois rôles partagent les
        # bornes du rôle qui alimente le canal VERT → le fond du composite garde
        # son niveau physique (donc son grain s'améliore en 1/√n avec
        # l'intégration) et le grain cesse d'être coloré. Le fond gardant sa
        # couleur, sa neutralisation relève des offsets du recalage colorimétrique
        # (ou de GraXpert live, par couche) — comme les B0/B1/B2 de Siril.
        self.normalisation_commune: bool = False
        # Jalon 117d — OPTION (décision d'Alain, 10/10/2026) : LISSAGE DU COMBINE
        # LRGB (halos d'étoiles). Case DÉCOCHÉE par défaut = VRAI opt-in : le
        # combine reste celui d'avant le 117c (rapport L/luma BRUT, σ = 0), donc
        # les halos reviennent tant qu'on ne coche pas. Cochée → lissage masqué à
        # l'échelle des étoiles (σ auto = 1,7 × FWHM), avec le SEUIL DU MASQUE
        # réglable (`seuil_masque_halos`, en σ au-dessus du fond) car ce seuil est
        # empirique et dépend du fond (cf. `SEUIL_MASQUE_SIGMA`).
        self.lissage_halos: bool = False
        self.seuil_masque_halos: float = SEUIL_MASQUE_SIGMA
        self.mode_l: str = "synthetise"   # radio « Canal L » (UI, phase 3)
        # Recalage colorimétrique « Linear Fit » (jalon 54) : appliqué au
        # COMPOSITE SEUL — JAMAIS aux couches (le solveur live re-fait la
        # recomposition depuis les couches brutes et ré-applique le recalage
        # lui-même, réglage transporté dans disp.vl_compo). Mode « offset »
        # PAR DÉFAUT (retour du test réel d'Alain : le gain fondé sur le
        # rapport des bruits amplifie halos/bruit bleus d'une image OSC).
        self.linear_fit: bool = False
        self.linear_fit_mode: str = "offset"
        self.fit_diag: Any = None              # gains/offsets mesurés (UI)
        self._fit_cache: Any = None
        # v2.34.5 : cache de l'équilibrage des canaux appliqué au COMPOSITE
        # (la case n'agissait qu'en mono : no-op sur une carte 2D de rôle).
        self._wb_cache_comp: Any = None
        self.role_courant: Any = None     # rôle de la frame en cours d'ajout
        self.stackers: dict[str, LiveStacker] = {}   # rôle → LiveStacker (2D)
        self._shape: Any = None           # forme des canaux (posée au 1er add)
        self._poly: Any = None            # intersection GLOBALE des couvertures
        self.cadre: Any = None            # cadre commun (y0, x0, y1, x1)
        # Jalon 79 : mémoire du COMPOSITE BRUT (avant corrections de couleur) et
        # bornes de normalisation figées — cf. `mean_avec_canaux`.
        self._memo_compo: Any = None      # (clé, composite)
        self._bornes_cache: Any = None    # (n, {rôle: (lo, hi)})

    # -- attributs répercutés sur tous les stackers (existants ET futurs) ---
    @property
    def k(self) -> float | None:
        return self._k

    @k.setter
    def k(self, v: Any) -> None:
        self._k = v
        for s in self.stackers.values():
            s.k = v

    @property
    def wb_auto(self) -> bool:
        return self._wb_auto

    @wb_auto.setter
    def wb_auto(self, v: Any) -> None:
        self._wb_auto = bool(v)
        for s in self.stackers.values():
            s.wb_auto = self._wb_auto

    @property
    def wb_force(self) -> float:
        return self._wb_force

    @wb_force.setter
    def wb_force(self, v: Any) -> None:
        self._wb_force = float(v)
        for s in self.stackers.values():
            s.wb_force = self._wb_force

    @property
    def method(self) -> str:
        return self._method

    @property
    def window(self) -> int:
        return self._window

    def set_rejet(self, method: str | None = None,
                  window: int | None = None) -> None:
        """Change la méthode / fenêtre de rejet à chaud, sur tous les rôles
        (accumulations préservées — cf. LiveStacker.set_rejet)."""
        if method is not None and method in LiveStacker.METHODES:
            self._method = method
        if window is not None:
            self._window = max(3, int(window))
        for s in self.stackers.values():
            s.set_rejet(method=method, window=window)

    # -- compteurs (somme sur les rôles) ------------------------------------
    @property
    def shape(self) -> Any:
        return self._shape

    @property
    def n(self) -> int:
        return sum(s.n for s in self.stackers.values())

    @property
    def rejected_total(self) -> int:
        return sum(s.rejected_total for s in self.stackers.values())

    def profondeur_min(self) -> int:
        """Nombre MINIMAL de frames empilées parmi les rôles NON VIDES —
        profondeur RÉELLE d'un composite (jalon 113).

        `n` est une SOMME des rôles : en LRGB, 1 frame par rôle donne n = 4 et
        l'astrométrie tentait alors sa résolution sur une image DÉJÀ INSOLUBLE
        (« image constante ») — MESURÉ : 2 frames/rôle = échec, 3 = 24
        appariements. C'est la profondeur du rôle le plus FAIBLE qui décide de
        la qualité du composite (chaque canal entre dans l'image) : c'est ELLE
        qu'il faut comparer à `astrometrie.ASTRO_MIN_FRAMES`.

        → min des rôles non vides ; 0 si aucun rôle n'a de frame."""
        prof = [s.n for s in self.stackers.values() if s.n > 0]
        return min(prof) if prof else 0

    # -- accumulation --------------------------------------------------------
    def _stacker_de(self, role: str) -> LiveStacker:
        s = self.stackers.get(role)
        if s is None:                     # 1re frame de ce rôle
            s = LiveStacker(self._shape, k=self._k, warmup=self.warmup,
                            method=self._method, window=self._window)
            s.wb_auto = self._wb_auto
            s.wb_force = self._wb_force
            self.stackers[role] = s
        return s

    def add(self, frame: np.ndarray, role: str | None = None) -> None:
        """Empile `frame` (canal 2D du rôle) dans le stacker de son rôle.
        Le rôle vient de l'argument ou de `role_courant` (posé par le worker)."""
        role = role or self.role_courant
        if not role:
            raise ValueError("CompositeStacker.add : rôle inconnu (ni "
                             "argument ni role_courant)")
        if self._shape is None:
            self._shape = tuple(frame.shape)
        self._stacker_de(role).add(frame)

    def note_alignement(self, M: Any) -> None:
        """Intersection GLOBALE des zones couvertes (tous rôles confondus —
        même repère, aligneur partagé) : le cadre commun appliqué à CHAQUE
        moyenne de rôle avant composer(), garantissant des formes identiques.
        Même géométrie que LiveStacker.note_alignement (jalon 15)."""
        if M is None or self._shape is None:
            return
        q = quad_alignement(M, self._shape)
        if _aire_signee(q) < 0:           # orientation normalisée
            q = q[::-1].copy()
        if self._poly is None:            # le cadre cible est la borne absolue
            self._poly = quad_alignement(
                np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]), self._shape)
        p = _clip_poly(self._poly, q)
        if p is not None:                 # vide = M aberrante → on ignore
            self._poly = p
        self.cadre = cadre_intersection(self._poly)

    def reset(self) -> None:
        """Vide TOUT (tous rôles + cadre commun)."""
        self.stackers.clear()
        self._poly = None
        self.cadre = None
        self._shape = None
        self._fit_cache = None            # recalage Linear Fit (jalon 54)
        self.fit_diag = None
        self._wb_cache_comp = None        # équilibrage des canaux du composite
                                          # (v2.34.5 : la case n'agissait qu'en
                                          # mono — no-op sur un rôle 2D)
        self._memo_compo = None           # jalon 79 : composite mémoïsé (clé → n,
                                          # cadre, composition, mode L, option)
        self._bornes_cache = None         # jalon 79 : bornes figées par frame

    # -- lecture du composite -------------------------------------------------
    def _recadrer(self, img: np.ndarray) -> np.ndarray:
        if self.cadre is None:
            return img
        y0, x0, y1, x1 = self.cadre
        return img[y0:y1, x0:x1]

    def moyennes(self, recadre: bool = True) -> dict[str, np.ndarray]:
        """{rôle: carte 2D float32 de l'empilement du rôle} — recadrées au
        cadre COMMUN si `recadre` (formes identiques, exigence de composer()).
        Matière de l'état par canal et des futures sauvegardes par canal.

        Jalon 56 (étape 5) : les gains photométriques par rôle ne sont PAS
        appliqués ici — `composer()` normalise chaque rôle par ses propres
        percentiles, ce qui ABSORBERAIT un facteur global (vérifié : le
        composite ne changeait pas). Ils passent par `gains_effectifs()`, donc
        par les gains de CANAL appliqués APRÈS la composition, dans la chaîne
        de sortie (`_appliquer_corrections`) ; les couches restent BRUTES
        (contrat jalon 54 : le solveur live re-compose depuis les couches
        brutes et ré-applique les corrections lui-même)."""
        out = {}
        for role, s in self.stackers.items():
            if s.n == 0:
                continue
            m = s.mean(recadre=False)     # accumulation complète, même repère
            # `s.mean()` n'est None que si `s.n == 0` (exclu ci-dessus) :
            # pyright ne le sait pas → ignore CIBLÉ.
            out[role] = self._recadrer(m) if recadre else m  # pyright: ignore[reportArgumentType]
        return out

    def gains_effectifs(self) -> dict[str, float]:
        """Gains R/G/B du composite : gains MANUELS (UI) × gains
        PHOTOMÉTRIQUES convertis de RÔLE en CANAL (jalon 56, étape 5).

        Pourquoi par canal : `composer()` normalise chaque rôle par ses propres
        percentiles AVANT toute correction → un facteur par rôle appliqué en
        amont serait absorbé (piège vérifié au banc : le composite ne
        changeait pas). Les facteurs mesurés sont donc convertis via
        `canaux_rgb` de la composition, puis appliqués APRÈS la composition
        (chaîne de sortie, `_appliquer_corrections`) — donc JAMAIS dans la
        sauvegarde linéaire brute.

        Rôle alimentant PLUSIEURS canaux (O3 → G et B en HOO) : même facteur
        partout. Canal alimenté par plusieurs rôles (cas rare) : MOYENNE
        GÉOMÉTRIQUE de leurs facteurs. → dict 'R'/'G'/'B' → facteur."""
        gains = dict(self.gains or {})
        if not self.gains_roles:
            return gains
        spec = COMPOSITIONS.get(self.composition) or {}
        mapping = spec.get("canaux_rgb")
        if not mapping:
            return gains                       # Mono : aucun canal RGB
        for canal, roles in mapping.items():
            facteurs = [float(self.gains_roles[r]) for r in roles
                        if r in self.gains_roles
                        and float(self.gains_roles[r]) > 0.0]
            if not facteurs:
                continue
            g = float(np.exp(np.mean(np.log(facteurs))))
            gains[canal] = float(gains.get(canal, 1.0)) * g
        return gains

    def mean_avec_canaux(self, recadre: bool = True, corrections: bool = True
                         ) -> tuple[np.ndarray | None,
                                    dict[str, np.ndarray] | None]:
        """(composite, {rôle: carte 2D}) en UNE passe de moyennes (jalon 24) :
        le worker a besoin des DEUX à chaque nouvel empilement (composite pour
        l'affichage, couches pour le traitement par couche du solveur live) —
        une seule exécution de mean()/recadrage au lieu de deux.
        Jalon 54 : le recalage « Linear Fit » est appliqué au COMPOSITE SEUL
        (les couches restent brutes — elles alimentent les caches du solveur
        et sa recomposition, qui ré-applique le recalage lui-même).

        `corrections` (chantier 24/09/2026 — décision d'Alain) :
          True  (DÉFAUT)  → chaîne de SORTIE : composite + corrections de
                            couleur (gains SPCC/Gaia/manuels, équilibrage,
                            recalage colorimétrique) = ce qui s'AFFICHE ;
          False           → composite BRUT, sans AUCUNE correction : c'est la
                            référence enregistrée par « Enregistrer
                            l'empilement (linéaire) ». Le fichier ne dépend
                            donc plus de l'état des cases de couleur.
        Les corrections ne s'appliquent QUE sur le chemin recadré (visu +
        sauvegardes) : `recadre=False` est la référence d'ALIGNEMENT (jalon 13)
        et reste brutalement brute, comme en mono.

        → (composite ou None, dict — vide si aucun rôle n'a de frame)."""
        canaux = self.moyennes(recadre=recadre)
        if not canaux:
            return None, None
        # Jalon 79 : le composite BRUT (avant corrections de couleur) est
        # MÉMOÏSÉ — il ne dépend que de l'accumulation des rôles et de la
        # composition, JAMAIS des corrections (gains, équilibrage, recalage) :
        # bouger un gain réutilise donc l'assemblage au lieu de le refaire
        # (mesuré : 225 ms pour HOO sur 8,4 Mpx, et jusqu'à trois fois dans la
        # même frame). Même raison pour les bornes de normalisation, FIGÉES
        # pour la frame (`composer` les recalculerait à chaque appel — le
        # paramètre `bornes` existe pour ça et n'était pas utilisé).
        n = sum(s.n for s in self.stackers.values())
        # Jalon 117d : le LISSAGE DES HALOS (et son seuil de masque) entre dans
        # la CLÉ DE MÉMOÏSATION — sans quoi cocher/décocher la case ou changer σ
        # réafficherait le composite mémoïsé (réglage « sans effet » apparent).
        cle = (n, bool(recadre), self.composition, self.mode_l,
               bool(self.normalisation_commune),
               bool(self.lissage_halos), float(self.seuil_masque_halos))
        if self._memo_compo is not None and self._memo_compo[0] == cle:
            comp = self._memo_compo[1]
        else:
            # Case décochée (défaut) → σ = 0 : AUCUN flou = combine d'avant le
            # 117c (bit-identique). Cochée → σ = None (auto, 1,7 × FWHM) + le
            # seuil de masque choisi par l'utilisateur.
            sig_l = None if self.lissage_halos else 0.0
            try:
                comp = composer(canaux, self.composition,
                                bornes=self._bornes_par_role(canaux, n),
                                mode_l=self.mode_l,
                                normalisation_commune=self.normalisation_commune,
                                sigma_l=sig_l,
                                seuil_masque_sigma=self.seuil_masque_halos)
            except ValueError:
                comp = None               # formes hétérogènes (ne doit pas
            self._memo_compo = (cle, comp)
        # Jalon 58b/chantier 24-09 : ÉQUILIBRAGE DES CANAUX (auto, jalon 13)
        # sur le COMPOSITE, puis RECALAGE « Linear Fit » — et, en amont, les
        # GAINS (manuels × SPCC/Gaia). BUG CORRIGÉ (constat Alain, 24/09/2026) :
        # l'équilibrage n'avait AUCUN effet en mode composition —
        # `LiveStacker._equilibrer` est no-op sur une carte 2D, or chaque rôle
        # de la composition EST une carte 2D (l'équilibrage attend une image
        # couleur). Ici les corrections s'appliquent au composite (H, W, 3),
        # là où les trois canaux existent enfin — même fonction
        # `gains_equilibre`, même force.
        # NOTE MESURÉE (24/09/2026) : les corrections étant appliquées APRÈS
        # `composer()` (qui normalise chaque rôle par SES percentiles), elles ne
        # sont PLUS absorbées par cette normalisation : c'est tout l'intérêt du
        # chantier. Une normalisation COMMUNE aux trois canaux (testée) NE
        # suffisait PAS : sans soustraction du fond, le fond pollué
        # déséquilibré devient visible et l'étirement l'amplifie (mesuré :
        # R/G affiché 0,079 — image inutilisable). La neutralisation du fond
        # relève du RECALAGE COLORIMÉTRIQUE (Linear Fit, mode « Gain + offset ») :
        # mesuré sur les couches réelles, SPCC seule laisse un fond linéaire
        # 0,0130/0,0219/0,0385 (très bleu) alors que SPCC + Linear Fit donne
        # 0,0213/0,0219/0,0220 — fond NEUTRE.
        if comp is not None and corrections and recadre:
            comp = self._appliquer_corrections(comp)
        return comp, canaux

    def _bornes_par_role(self, canaux: Any, n: int) -> Any:
        """Bornes (lo, hi) de normalisation de chaque rôle, FIGÉES pour la frame
        courante (jalon 79) : `composer()` les recalcule sinon à chaque appel,
        alors qu'elles ne dépendent que de l'accumulation (donc de `n`) — c'est
        pour cela que le paramètre `bornes` existe. Les VALEURS sont celles
        d'avant, au bit près : même fonction `bornes_normalisation`, appelée une
        fois par frame au lieu de deux à quatre fois."""
        if self._bornes_cache is not None and self._bornes_cache[0] == n:
            return self._bornes_cache[1]
        bornes = {r: bornes_normalisation(a) for r, a in canaux.items()
                  if a is not None}
        self._bornes_cache = (n, bornes)
        return bornes

    def _appliquer_corrections(self, comp: np.ndarray) -> np.ndarray:
        """Chaîne des corrections de couleur du composite (chantier
        24/09/2026, décision (b)/(c)) — MÊME ordre que `corrections_couleur` :
        gains effectifs (manuels × SPCC/Gaia) → équilibrage des canaux →
        recalage « Linear Fit » (avec ses caches : `mean()` est appelée ~20×/s).
        No-op sur une image non couleur (Mono : aucune correction de couleur,
        l'empilement mono est déjà brut)."""
        if comp is None or comp.ndim != 3 or comp.shape[-1] != 3:
            return comp
        comp = appliquer_gains(comp, self.gains_effectifs())
        if self._wb_auto:
            comp = self._equilibrer_composite(comp)
        if self.linear_fit:
            comp = self._recaler_fit(comp)         # → case DÉCOCHÉE = brut
        return comp

    def _equilibrer_composite(self, comp: np.ndarray) -> np.ndarray:
        """Équilibrage des canaux du COMPOSITE (jalon 13 appliqué au composite,
        v2.34.5) : gains par canal dérivés du FOND (percentile bas), mis en
        cache par (frames totales, force, cadre) — `mean()` est appelée ~20×/s
        mais rien ne change entre deux frames. Force < 1 → gains partiels
        (`gains ** force`), comme dans `LiveStacker._equilibrer`."""
        if comp.ndim != 3 or comp.shape[-1] != 3:
            return comp
        cle = (sum(s.n for s in self.stackers.values()),
               round(float(self.wb_force), 4), self.cadre)
        if self._wb_cache_comp is not None and self._wb_cache_comp[0] == cle:
            gains = self._wb_cache_comp[1]
        else:
            gains = gains_equilibre(comp, self.cadre)
            self._wb_cache_comp = (cle, gains)
        return appliquer_gains_canaux(comp, gains, self.wb_force)

    def _recaler_fit(self, comp: np.ndarray) -> np.ndarray:
        """Recalage « Linear Fit » du composite (jalon 54) : cf.
        CompositeStacker.linear_fit. Cache par (frames totales, GAINS EFFECTIFS,
        mode L, mode) : les stats du composite dépendent de l'accumulation ET
        des réglages qui la composent → recalcul seulement quand l'un change
        (aucun pompage entre deux ticks). Les gains EFFECTIFS (manuels ×
        photométriques) entrent dans la clé : un facteur photométrique qui
        apparaît doit recalculer le fit, sinon la vue serait incohérente."""
        if comp.ndim != 3 or comp.shape[-1] != 3:
            return comp
        ge = self.gains_effectifs()
        gains_sig = (tuple(round(float(ge.get(c, 1.0)), 4)
                           for c in ("R", "G", "B"))
                     if ge else None)
        cle = (sum(s.n for s in self.stackers.values()),
               self.linear_fit_mode, gains_sig, self.mode_l)
        if self._fit_cache is not None and self._fit_cache[0] == cle:
            out, diag = self._fit_cache[1]
        else:
            out, diag = aligner_canaux(comp, mode=self.linear_fit_mode)
            self._fit_cache = (cle, (out, diag))
        self.fit_diag = diag
        return out if diag is not None else comp

    def mean(self, recadre: bool = True,
             corrections: bool = True) -> np.ndarray | None:
        """Composite LINÉAIRE courant (composer : normalisation par canal,
        puis — si `corrections` — les corrections de couleur de la chaîne de
        sortie), recadré au cadre commun si `recadre`. → (H, W, 3) float32
        (ou (H, W) en Mono), None si aucun rôle n'a de frame.

        `corrections=False` → EMPILEMENT BRUT (aucun gain, aucun équilibrage,
        aucun recalage) : c'est ce que la sauvegarde linéaire enregistre."""
        comp, _ = self.mean_avec_canaux(recadre=recadre, corrections=corrections)
        return comp

    def etat(self) -> str:
        """État par canal « Ha: 12 · O3: 9 » (frames EMPILÉES par rôle, dans
        l'ordre de la composition ; rôles vides absents)."""
        ordre = list(roles_de(self.composition))
        parties = []
        for role in ordre + [r for r in self.stackers if r not in ordre]:
            s = self.stackers.get(role)
            if s is not None and s.n > 0:
                parties.append(f"{role}: {s.n}")
        return " · ".join(parties)

