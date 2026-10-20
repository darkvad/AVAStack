# -*- coding: utf-8 -*-
"""Étirement temps réel : auto STF façon PixInsight, manuel, ou VeraLux (tiers)."""

import threading
from typing import Any

import numpy as np
import cv2

from ..external import live as _gx_live
from . import couleurs as _couleurs
from . import composition as _composition
from . import denoise as _denoise
from . import sharpness as _sharpness
from . import veralux as _veralux


def params_lissage_halos(compo: Any) -> tuple[bool, float | None]:
    """(lissage actif, seuil de masque) du LISSAGE DU COMBINE LRGB, lus dans le
    8e élément du job de composition (jalon 117d).

    Déballage TOLÉRANT : `compo` peut être None (mode mono) ou un tuple d'avant
    le 117d (6 ou 7 éléments) → (False, None) = lissage inactif, donc le combine
    reste celui d'avant le 117c. Extrait du chemin live pour être testable sans
    lancer le solveur (banc jalon 117d)."""
    lissage = compo[7] if compo is not None and len(compo) > 7 else None
    if not lissage:
        return False, None
    actif = bool(lissage[0])
    seuil = float(lissage[1]) if len(lissage) > 1 else None
    return actif, seuil


def params_fusion_ha(compo: Any) -> dict | None:
    """Réglages de FUSION DU Ha lus dans le 9e élément du job de composition
    (jalon J2, v2.88.0).

    Déballage TOLÉRANT : `compo` peut être None, un tuple d'avant le J2 (8
    éléments) ou d'AVANT le jalon 124 — où le 9e élément était la
    NEUTRALISATION (`bool`, désormais ignorée par le solveur). Seul un DICT est
    accepté : un booléen ou toute autre valeur rend None (aucune fusion, donc
    comportement d'avant le J2). Extrait du chemin live pour être testable sans
    lancer le solveur, comme `params_lissage_halos`."""
    fusion = compo[8] if compo is not None and len(compo) > 8 else None
    return dict(fusion) if isinstance(fusion, dict) else None


def _hachable(v: Any, nd: int = 6) -> Any:
    """Valeur HACHABLE et STABLE (pour une clé de mémoïsation) : les dicts
    deviennent des tuples TRIÉS, les listes/tuples des tuples, les flottants
    (y compris numpy) sont arrondis à `nd` décimales. Tout le reste (str, bool,
    None) est rendu tel quel ; un type inconnu tombe sur son `repr`, ce qui
    reste stable pour un objet immuable et ne lève JAMAIS."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float, np.integer, np.floating)):
        return round(float(v), nd)
    if isinstance(v, dict):
        return tuple(sorted((str(k), _hachable(x, nd)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return tuple(_hachable(x, nd) for x in v)
    return repr(v)


def params_corrections(compo: Any) -> tuple:
    """SIGNATURE HACHABLE des CORRECTIONS DE COULEUR d'un job de composition
    (P7, v2.93.1) : gains EFFECTIFS, mode L, « Linear Fit », équilibrage des
    canaux, normalisation commune, lissage du combine et fusion du Ha.

    POURQUOI : sur le chemin PAR COUCHE (GraXpert / débruitage live), le worker
    applique lui-même `composition.corrections_couleur()` — changer SEUL un gain
    (clic SPCC / gains Gaia) ne modifiait alors aucune clé de mémoïsation : la
    chaîne republiait son image EN CACHE, donc le choix PRÉCÉDENT (défaut P7
    mesuré au banc `_test_p7_recalcul_corrections`). Ces réglages entrent donc
    dans `DisplayProcessor._vl_params()`.

    Les COUCHES (`compo[0]`) sont VOLONTAIREMENT exclues : ce sont de grands
    tableaux numpy, coûteux à parcourir à chaque tick ; une nouvelle frame force
    déjà la chaîne par `notify_new_stack()`. Déballage TOLÉRANT : None (mode
    mono), un dict ou tout autre type rend `()`, un tuple court rend des `None`
    — la fonction ne lève JAMAIS."""
    if not isinstance(compo, (tuple, list)):
        return ()
    n = len(compo)
    return (_hachable(compo[2] if n > 2 else None),      # gains effectifs
            _hachable(compo[3] if n > 3 else None),      # mode du canal L
            _hachable(compo[4] if n > 4 else None),      # Linear Fit
            _hachable(compo[5] if n > 5 else None),      # équilibrage
            _hachable(compo[6] if n > 6 else None),      # normalisation commune
            _hachable(compo[7] if n > 7 else None),      # lissage halos + seuil
            _hachable(params_fusion_ha(compo)))          # fusion du Ha


# ============================================================== jalon 75
# ÉTAGE « NIVEAUX » DE L'ÉCRAN (les 3 barres de l'histogramme : Noir /
# Médian / Blanc) et SATURATION PAR COULEUR.
#
# POURQUOI UN ÉTAGE APRÈS L'ÉTIREMENT (et pas « les points de l'étirement ») :
# le modèle du « mini-histogramme » de SharpCap — « the stretch in the mini
# histogram affects the display only » — est le SEUL qui puisse servir LES
# DEUX moteurs d'étirement du projet :
#   - le STF a bien un point noir, un médian et un point blanc ;
#   - VeraLux n'en a AUCUN (le moteur tiers n'a qu'une ANCRE et un logD,
#     cf. veralux_core_headless.calculate_anchor_adaptive/solve_log_d) : une
#     barre « blanc » n'aurait rien à piloter, et une barre « noir » ne
#     pourrait viser que l'ancre — recalculée à chaque passe.
# Les barres agissent donc sur la SORTIE du moteur (image étirée [0..1]) :
# même geste, même lecture, effet INSTANTANÉ (aucun recalcul du solveur),
# quel que soit le moteur. Le comportement est celui demandé par Alain
# (28/09/2026) : « travailler en delta » — l'étirement automatique continue
# de s'ajuster à chaque frame, les barres s'appliquent PAR-DESSUS.
#
# La loi est celle d'un HistogramTransformation : noir/blanc recadrent
# l'intervalle, le médian place le gris moyen (MTF(m, m) = 0,5 par
# construction : la position de la barre EST le niveau affiché en gris moyen —
# c'est la définition même de SharpCap : « these three lines represent the
# histogram levels that will be displayed as black, mid grey and white »).
#
# DÉFAUT = 0 / 0,5 / 1 = IDENTITÉ EXACTE (et court-circuitée : l'étage n'est
# même pas exécuté) → aucun changement du rendu tant qu'on ne touche à rien.


def mtf(x: Any, m: float) -> np.ndarray:
    """Midtones Transfer Function : x, m ∈ [0,1] (MTF de PixInsight/STF)."""
    m = min(max(m, 0.001), 0.98)
    return np.clip(((m - 1.0) * x) / ((2.0 * m - 1.0) * x - m), 0.0, 1.0)


def niveaux_actifs(noir: float = 0.0, median: float = 0.5,
                   blanc: float = 1.0) -> bool:
    """True si l'étage de niveaux CHANGE quelque chose (sinon on l'ignore :
    le rendu par défaut est alors strictement celui d'avant le jalon 75)."""
    return (abs(float(noir)) > 1e-6
            or abs(float(median) - 0.5) > 1e-6
            or abs(float(blanc) - 1.0) > 1e-6)


def niveaux(x: Any, noir: float = 0.0, median: float = 0.5,
            blanc: float = 1.0) -> Any:
    """Étage « niveaux » : recadrage [noir, blanc] puis MTF médian.

    x : image [0..1] (étirée), noir/blanc dans [0,1] avec noir < blanc.
    Fonction PURE. À l'identité (0 / 0,5 / 1) elle rend x au BIT près
    (MTF(x, 0,5) = x : -0,5·x / -0,5, les deux opérations étant exactes en
    binaire) — c'est ce qui garantit l'absence de régression.
    """
    noir = min(max(float(noir), 0.0), 0.999)
    blanc = min(max(float(blanc), noir + 1e-3), 1.0)
    if not niveaux_actifs(noir, median, blanc):
        return x
    y = np.clip((np.asarray(x, np.float32) - noir) / (blanc - noir), 0.0, 1.0)
    return mtf(y, float(median))


def couleur_apres_etirement(x: Any, actif: Any = (False, False, False),
                            force_scnr: float = 1.0,
                            force_demagenta: float = 1.0,
                            preserve_luminance: bool = True,
                            boost_rouge: bool = False,
                            force_boost: float = _couleurs.BOOST_ROUGE_DEFAUT,
                            boost_preserve_luminance: bool = False) -> Any:
    """Chaîne couleur APRÈS l'étirement (v2.48.0, jalons 85/86) : SCNR classique
    → SCNR doux (bruit seul) → démagenta → boost du rouge (SII) masqué à
    l'objet, dans cet ordre.

    POURQUOI APRÈS L'ÉTIREMENT (et non avant, comme aux jalons 22/23) :
    ① `preserve_luminance` (ACTIVE par défaut) rend au pixel sa L* CIE — une
    grandeur PERCEPTUELLE, sans objet sur une image linéaire ; ② l'ordre des
    références est « égaliser le fond, PUIS retirer le vert » ; ③ la sortie
    LINÉAIRE sauvegardée ne doit porter que l'empilement et les corrections
    (elle était écrêtée en vert : MESURÉ sur l'empilement M31 d'Alain, excès
    de vert max 5,9·10⁻⁸ contre 1,6·10⁻¹ sur l'empilement d'origine).

    POURQUOI LE BOOST EN DERNIER (jalon 86) : le SCNR retire l'excès de vert,
    c'est-à-dire le vert AU-DESSUS de (R+B)/2. Appliqué après le boost du rouge,
    il en reprendrait une partie (le seuil (R+B)/2 monte avec le rouge ajouté) :
    les deux réglages se combattraient au lieu de s'ajouter. En dernier, le boost
    garde TOUTE sa force, et le SCNR garde toute la sienne — les deux restent
    INDÉPENDANTS (décision d'Alain : pas d'exclusivité).

    x    : image ÉTIRÉE (H, W, 3) [0..1] — un composite monochrome (H, W) est
           rendu inchangé (les quatre outils sont des no-op sur du monochrome) ;
    actif: (SCNR, SCNR doux, démagenta) — les trois cases à cocher ;
    force: part de correction (1,0 = formule historique des jalons 22/23) ;
    boost_rouge / force_boost / boost_preserve_luminance : le boost du rouge
           (jalon 86) — `force_boost` à 1,00 est une identité AU BIT, donc le
           réglage peut rester en place sans rien changer (cf. couleurs.boost_rouge).
    → float32 de mêmes dimensions ; l'entrée n'est jamais modifiée.

    NB (les deux faits sont MESURÉS et verrouillés par le banc
    `bancs/_test_couleur_luminance_jalon85.py`) : les cases SCNR et SCNR doux
    ne se complètent que si la force du SCNR est < 1 (à force 1, l'excès est
    ≤ 0 partout : le doux ne retire plus rien, écart 2,98·10⁻⁸) ; la
    préservation de L* ne touche que les pixels réellement corrigés."""
    if x is None or np.ndim(x) != 3 or x.shape[-1] != 3:
        return x
    scnr_actif, sd_actif, dm_actif = (tuple(actif) + (False, False, False))[:3]
    if scnr_actif:
        x = _couleurs.scnr(x, amount=force_scnr,
                           preserve_luminance=preserve_luminance)
    if sd_actif:
        x = _couleurs.scnr_doux(x, preserve_luminance=preserve_luminance)
    if dm_actif:
        x = _couleurs.demagenta(x, amount=force_demagenta,
                                preserve_luminance=preserve_luminance)
    if boost_rouge:
        x = _couleurs.boost_rouge(x, force=force_boost,
                                  preserve_luminance=boost_preserve_luminance)
    return x


def saturation_actifs(gains: Any) -> bool:
    """True si la saturation par canal change quelque chose (1,0 = neutre)."""
    if gains is None:
        return False
    return any(abs(float(v) - 1.0) > 1e-3 for v in gains)


def saturation_canaux(x: Any, gains: Any) -> np.ndarray:
    """Saturation PAR COULEUR (R/V/B) — par SECTEUR DE TEINTE.

    POURQUOI CE N'EST PAS « c_c = Y + k_c·(c − Y) » (1re écriture, rejetée le
    28/09/2026 après TON essai réel) : cette formule changeait le canal
    PARTOUT, quelle que soit la couleur du pixel. Mesuré sur un pixel vert
    franc (0,20 · 0,60 · 0,20) : le curseur « Saturation rouge » à 2,00 faisait
    TOMBER le rouge (0,20 → 0,00) — le pixel devenait donc PLUS VERT. Ton
    constat : « quand je pousse l'un, c'est l'autre couleur qui semble se
    renforcer ». Un curseur « rouge » qui renforce les verts n'est pas une
    saturation par couleur.

    ICI on ne touche QUE les teintes du secteur visé. Chez OpenCV en float32 la
    teinte va de 0 à 360 (MESURÉ : rouge 0, jaune 60, vert 120, cyan 180,
    bleu 240, magenta 300) ; les trois secteurs reçoivent des poids
    TRIANGULAIRES centrés sur 0 / 120 / 240 qui somment à 1 partout (transition
    douce entre secteurs, aucun bord arbitraire), et la saturation du pixel est
    multipliée par w_R·k_R + w_G·k_G + w_B·k_B. Conséquences vérifiées :
    pousser « rouge » sature les rouges, **laisse les verts intacts**, et un
    pixel gris (S = 0) ne bouge jamais. 1,0 = neutre (chemin rapide, aucun
    calcul).
    """
    x = np.clip(np.asarray(x, np.float32), 0.0, 1.0)
    hsv = cv2.cvtColor(x, cv2.COLOR_RGB2HSV)      # H sur 0..360 (float32)
    h = hsv[..., 0]
    facteur = np.zeros_like(h)
    for centre, k in ((0.0, float(gains[0])),        # rouge
                      (120.0, float(gains[1])),      # vert
                      (240.0, float(gains[2]))):     # bleu
        d = np.abs(h - centre)
        poids = np.clip(1.0 - np.minimum(d, 360.0 - d) / 120.0, 0.0, 1.0)
        facteur += poids * k
    hsv[..., 1] = np.clip(hsv[..., 1] * facteur, 0.0, 1.0)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


# ============================================================== jalon 136
# HALO D'ÉTOILE COLORÉ — NEUTRALISER LE CIEL PAR CANAL AVANT L'ÉTIREMENT STF
#
# MESURÉ sur le run LRGB+Ha de M33 (v2.83.0, fichier LINÉAIRE livré) : les
# niveaux de ciel des trois canaux sont PROPORTIONNELS et très différents —
# R 0,02736 · G 0,03139 · B 0,03987, soit R −12,9 % et B +27,0 % par rapport au
# vert, ÉGAL DANS LES QUATRE COINS et aux quatre milieux de bord (à 0,5 % près)
# ⇒ c'est un CIEL, pas la galaxie, et c'est un écart MULTIPLICATIF (même rapport
# partout), donc l'affaire de GAINS, pas d'offsets.
#
# L'étirement STF applique UN point noir commun (`lo`, calculé sur la
# luminance). Avec lo = 0,03108, le canal R du fond passe SOUS le point noir :
# il est écrêté à 0 dans TOUT le ciel, et la couronne d'une étoile — neutre
# dans le linéaire — ne rallume R qu'au cœur. La MTF étant très raide, la
# transition est amplifiée ⇒ couronne colorée (MESURÉ : le rendu par défaut du
# fichier livré donne un ciel à R 0,00 / G 0,07 / B 0,71, et à r = 14 px d'une
# étoile brillante R/G 0,11 et B/G 2,11 contre 0,88 et 1,30 dans le fond local).
# Second effet, indépendant : la pente locale de la MTF vaut ~18 à hauteur de
# ciel, si bien qu'un écart résiduel de 1 à 3 % d'un bout à l'autre du cadre
# ressort à 20-100 % (MESURÉ sur le fichier « linéaire traité », dont le ciel
# est neutre en moyenne mais varie de ±2 %).
#
# REMÈDE (et non un masque sur la couronne) : ramener les niveaux de ciel au
# même niveau PAR GAINS avant la courbe — c'est `couleurs.gains_fond`, la
# primitive d'espace LINÉAIRE du projet (même esprit que la neutralisation
# appliquée avant l'étirement VeraLux, v2.36.1/jalon 62). MESURÉ sur le même
# fichier, avec le vrai `DisplayProcessor` : l'écart de teinte de la couronne
# tombe de « R perdu (97,34 % des pixels à 0) / B −81 % » à « R +5,0 % /
# B −6,6 % », et le ciel du rendu de (0,00 ; 0,07 ; 0,71) à un gris teinté
# (R +19,4 % / B +16,7 % — résidu de la pente évoquée ci-dessus, sans commune
# mesure avec un ciel bleu vif).
#
# La garde borne la correction : `gains_fond` vaut 10 % par défaut (calibrée sur
# un ciel déjà presque neutre — M31 : 3,6 %), insuffisante ici où les gains
# mesurés valent ×1,1626 (R) et ×0,7964 (B), soit +16,3 % / −20,4 %. 35 %
# couvre ce cas et borne le pire cas (cadrage dominé par un objet étendu, où la
# « moitié sombre » n'est plus du ciel).
GARDE_NEUTRE_STF = 0.35

# En dessous de cet écart aux gains, on ne touche à RIEN (identité AU BIT) :
# une image au ciel neutre doit produire exactement le rendu d'avant.
SEUIL_NEUTRE_STF = 1e-3


def gains_avant_etirement(img: Any) -> np.ndarray | None:
    """Gains (R,V,B) qui neutralisent le CIEL avant l'étirement STF — None
    quand il n'y a rien à corriger : image mono, canal vide, ou gains à moins
    de `SEUIL_NEUTRE_STF` de 1,0 (le rendu reste alors identique AU BIT).

    L'estimation se fait sur un SOUS-ÉCHANTILLON (un maximum de ~256×256
    points) : `gains_fond` repose sur des médianes, insensibles au
    sous-échantillonnage, et cela coûte ~8 ms au lieu de ~115 ms sur un aperçu
    1600x904 (mesuré) — l'étirement STF doit rester réactif à chaque frame.
    """
    a = np.asarray(img)
    if a.ndim != 3 or a.shape[-1] != 3:
        return None                       # mono : pas de couleur à neutraliser
    pas_y = max(1, a.shape[0] // 256)
    pas_x = max(1, a.shape[1] // 256)
    g = _couleurs.gains_fond(a[::pas_y, ::pas_x], garde=GARDE_NEUTRE_STF)
    if g is None:
        return None
    gg = np.asarray(g, dtype=np.float32)
    if bool(np.allclose(gg, 1.0, atol=SEUIL_NEUTRE_STF)):
        return None                       # ciel déjà neutre : identité exacte
    return gg


def source_etirement(img: Any) -> tuple[np.ndarray, np.ndarray | None]:
    """(image que voit la COURBE d'étirement, gains appliqués ou None).

    L'étirement et ses statistiques doivent porter sur la MÊME image : quand
    les canaux ne partent pas du même niveau, c'est l'image neutralisée qui
    entre dans `_calc_stats`, sinon le point noir reste calé sur un ciel moyen
    que deux canaux sur trois ne touchent jamais.
    """
    g = gains_avant_etirement(img)
    if g is None:
        return img, None
    return (img * g.reshape(1, 1, 3)).astype(np.float32), g


class DisplayProcessor:
    """Étirement temps réel.

    Mode AUTO — « STF » façon PixInsight :
      1. point noir  lo = médiane − k·σ        (coupe le bruit sous le fond)
      2. point blanc hi = percentile 99.9       (vraies hautes lumières, pas med+k·σ !)
      3. midtones m résolues pour que le FOND tombe à self.target (~0.25) après MTF.
    Le fond garde donc une luminosité stable quelle que soit l'exposition :
    c'est la nébulosité qui « monte » avec l'intégration, pas le fond.
    Les stats (médiane, σ, p99.9) sont lissées dans le temps → pas de pompage.

    Mode MANUEL — black/white point.

    Mode VERALUX (self.stretch == "veralux", opt-in) — étirement hyperbolique
    du moteur tiers `veralux_core_headless.py`, via l'adaptateur
    `avastack.processing.veralux`. Deux modes de résolution du logD :
      - MODE_TARGET_BG (défaut, jalon 3) : le moteur résout lui-même le logD
        pour amener le fond du ciel à vl_target_bg ;
      - MODE_LOG_D : logD imposé (curseur ou bouton 🔒 de l'UI) — calcul
        direct, déterministe, réactif.
    Le calcul (~200 ms à taille aperçu) part dans un thread dédié, déclenché
    par notify_new_stack() à CHAQUE nouvel empilement — le rythme des frames
    (≥ 1 s, souvent bien plus) EST le cooldown, aucun calcul entre deux
    frames — et le worker ne garde que le DERNIER job (aucune file
    d'attente). Le résultat est CACHÉ par image et les réglages sont comparés
    par clé — l'UI n'est jamais bloquée, et tant que le calcul n'est pas
    terminé, le STF sert d'image d'attente. VeraLux n'écrit JAMAIS
    dans black/white/gamma (leçon de la 1re tentative) : ces réglages et les
    curseurs gamma/saturation restent la propriété des modes STF/manuel, et
    gamma/saturation s'appliquent après l'étirement, comme pour le STF.

    Mode VERALUX + GRAXPERT LIVE (jalon 4, opt-in) : si self.vl_graxpert est
    True, le thread solveur enchaîne stack → GraXpert (CLI, via
    avastack.external.live, sur un FITS temporaire de l'aperçu) → VeraLux —
    l'ordre photométrique correct : le gradient est retiré AVANT l'étirement.
    Le résultat GraXpert est mis en cache par CONTENU d'image (empreinte) :
    bouger un curseur VeraLux ne relance PAS GraXpert. En cas d'échec
    (binaire absent, timeout…), l'erreur est signalée dans vl_error et
    l'image brute est étirée en repli — l'UI n'est jamais bloquée, le BXT
    reste entièrement manuel (bouton ⚡, inchangé).

    Dans tous les modes, `process()` reçoit une image LINÉAIRE [0..1] et
    renvoie un uint8 affichable ; les données sauvegardées ne passent jamais
    par ici.

    Mode VERALUX + DÉBRUITAGE LIVE (jalon 9, remis le 16/09/2026, opt-in) :
    si self.vl_denoise est True, le thread solveur enchaîne stack → GraXpert
    live (si activé) → débruitage LOCAL (avastack.processing.denoise :
    ondelettes à trous ou Non-local Means, numpy/OpenCV, aucun subprocess)
    → VeraLux. Cache par (CONTENU image APRÈS gradient, méthode, force) ;
    échec = repli sur l'image sans débruitage + message préfixé
    « Débruitage live : … » (jamais de blocage, jamais d'image perdue).

    NETTETÉ LIVE (jalon 12, opt-in) : si self.vl_sharp est True,
    Richardson-Lucy (avastack.processing.sharpness, numpy/OpenCV) est
    appliquée APRÈS le débruitage et AVANT l'étirement — on lisse d'abord, on
    restaure ensuite (l'ordre inverse amplifierait le bruit que le débruitage
    doit retirer). Contrairement à GraXpert/débruitage live, son cadre d'UI
    est INDÉPENDANT du moteur d'étirement (demande d'Alain) : elle s'applique
    donc AUSSI en STF/manuel. JALON 125 (VOLET A) : la netteté n'a plus de
    chemin dédié — elle fait partie de la chaîne pré-étirement UNIQUE
    (`_vl_worker`), pour les DEUX moteurs (gradient → débruitage → netteté →
    étirement, la dernière étape seule dépendant du moteur) ; tant que le
    résultat n'est pas prêt, l'image d'attente est l'image NON nette (jamais
    bloquant, jamais l'image d'un autre empilement).
    La PSF est celle du seeing mesuré au jalon 10 (`vl_seeing`, mesuré sur
    l'aperçu par le thread d'acquisition) quand elle est disponible : c'est la
    mesure du flou réel, et elle évite une 2e mesure ; sinon le module mesure
    lui-même. Refus explicite (image inchangée + raison, jamais de no-op
    silencieux) si le module juge la déconvolution sans objet.
    """
    def __init__(self) -> None:
        self.auto = True
        self.sigma_k = 2.8            # coupure des ombres, en σ SOUS la médiane
        self.target = 0.25            # luminosité cible du fond du ciel après MTF
        self.black, self.white = 0.0, 1.0
        self.gamma, self.saturation = 1.0, 1.0
        # --- Jalon 75 : étage « niveaux » de l'écran (3 barres de l'histogramme)
        # Noir / Médian / Blanc, appliqués à la SORTIE du moteur (STF OU
        # VeraLux) — modèle du mini-histogramme SharpCap, cf. le commentaire
        # en tête de module. Défaut = identité exacte (aucun effet).
        # `fige` : l'étirement automatique du moteur est GELÉ (⏹) — STF : les
        # stats ne se recalculent plus ; VeraLux : l'UI passe le logD en mode
        # forcé (verrou existant du jalon 3).
        self.bar_noir, self.bar_median, self.bar_blanc = 0.0, 0.5, 1.0
        self.fige = False
        self.sat_canaux = (1.0, 1.0, 1.0)   # saturation par couleur R/V/B
        # Image de SORTIE DU MOTEUR (avant l'étage de niveaux) : c'est elle que
        # la bande basse de l'histogramme affiche, pour que les barres
        # découpent bien la donnée qu'elles reçoivent. Écrite par `process()`,
        # lue par l'UI juste après (même thread).
        self.dernier_brut_niveaux = None
        self.niveaux_new = False      # l'UI doit resynchroniser ses champs
        self.last_lo, self.last_hi = 0.0, 1.0
        # Jalon 75 : médian résolu du dernier rendu auto (repère de la bande
        # « brut » de l'histogramme : lo + m·(hi − lo)).
        self.last_m = 0.5
        # JALON 136 : gains par canal appliqués AVANT l'étirement pour
        # neutraliser un ciel coloré (None = aucun, cas d'un ciel neutre).
        # Publié pour le diagnostic et le banc ; ne change aucun réglage.
        self.gains_etirement = None
        self._stats: Any = None       # (médiane, σ, p99.9) lissées — anti-pompage
        self._ema = 0.25              # réactivité : 0 = figé, 1 = instantané
        # Jalon 79 : mémoire de la SORTIE DU MOTEUR d'étirement STF/manuel
        # (image avant niveaux/gamma/saturation), cf. `_moteur_stf`. Évite de
        # recalculer tout l'étirement à chaque geste sur un réglage d'APRÈS
        # étirement. Tuple : (image source, clé des réglages, image étirée,
        # last_lo, last_hi, last_m) — la source est GARDÉE, donc son identité
        # ne peut pas être confondue avec celle d'un autre tableau.
        self._memo_moteur = None

        # --- VeraLux (moteur tiers) -----------------------------------------
        self.stretch = "stf"          # "stf" (défaut, inchangé) | "veralux"
        self.vl_mode_res = _veralux.MODE_TARGET_BG  # jalon 3 : résolution auto
                                      # du logD (fond calé sur vl_target_bg) ;
                                      # MODE_LOG_D = logD forcé (bouton 🔒)
        self.vl_target_bg = _veralux.TARGET_BG_PAR_DEFAUT
        self.vl_log_d = _veralux.LOG_D_PAR_DEFAUT
        self.vl_profil = _veralux.PROFIL_PAR_DEFAUT
        # --- GraXpert live (jalon 4, opt-in) --------------------------------
        self.vl_graxpert = False      # GraXpert AVANT l'étirement VeraLux
        self.vl_graxpert_cmd = ""     # commande GraXpert ({input}/{outbase}…)
        self._gx_cache = None         # (empreinte image, image traitée) —
                                      # utilisé par le thread solveur SEUL
        # --- Débruitage live (jalon 9, remis le 16/09/2026, opt-in) ---------
        # Algorithmes LOCAUX rapides (numpy/OpenCV, aucun subprocess) — à la
        # différence du débruitage GraXpert IA (PLUSIEURS minutes), celui-ci
        # peut tourner à chaque nouvel empilement. OPTION DOUCE par défaut :
        # à force utile les méthodes locales moutonnent (« léopard », cf.
        # CLAUDE.md) ; le live sert à JUGER, la sauvegarde linéaire reste
        # intouchée et « tel que vu » reproduit la chaîne affichée.
        self.vl_denoise = False       # algorithme LOCAL avant l'étirement
        self.vl_denoise_methode = "nlm"   # "ondelettes" | "nlm" (défaut : nlm)
        self.vl_denoise_force = 0.5   # 0..1
        self._dn_cache = None         # (empreinte image, méthode, force,
                                      # image traitée) — thread solveur SEUL
        # --- Jalon 24 : mode composition (multi-couches) ---------------------
        # Posé par l'UI à chaque nouvel état de la file worker :
        # (canaux {rôle → carte 2D linéaire de l'APERÇU}, nom de composition,
        # gains, mode_l, recalage Linear Fit, équilibrage des canaux). None en
        # mode mono → la chaîne agit sur le composite comme avant (jalon 4/9).
        # En composition, le gradient ET le débruitage sont faits PAR COUCHE
        # (décision d'Alain du 19/09/2026 : la pollution lumineuse et la lune
        # ne frappent pas pareil selon le filtre, et la palette Hubble n'est
        # pas un fond physique — le modèle de fond de GraXpert ne doit voir que
        # des couches mono 2D). Les trois derniers éléments sont les
        # CORRECTIONS DE COULEUR (décision (b)/(c) du 24/09/2026) : le solveur
        # les applique lui-même APRÈS la recomposition des couches traitées
        # (avant la netteté et l'étirement) — les couches, elles, restent
        # BRUTES (contrat jalon 54). La netteté reste SUR LE COMPOSITE (PSF
        # identique pour toutes les couches, meilleur SNR après débruitage,
        # moitié moins de calcul).
        self.vl_compo: Any = None
        self._gx_couches = {}         # rôle → (clé, couche après gradient)
        self._dn_couches = {}         # rôle → (clé, couche après débruitage)
                                      # (caches du thread solveur SEUL, un par
                                      # rôle : une nouvelle frame ne relance le
                                      # traitement QUE de la couche qui a reçu)
        # --- Netteté live (jalon 12, opt-in) --------------------------------
        # Richardson-Lucy (avastack.processing.sharpness) APRÈS le débruitage
        # et AVANT l'étirement, dans TOUS les moteurs d'étirement (le cadre de
        # la netteté est indépendant de la bascule STF/VeraLux). 3-5 itérations
        # = réglage utile, ITERATIONS_MAX (10) en plafond dur.
        self.vl_sharp = False         # netteté live activée (vue « empilement »)
        self.vl_sharp_iterations = _sharpness.ITERATIONS_DEFAUT
        # --- SCNR + démagenta (jalon 22, opt-in) ----------------------------
        # APPLIQUÉS APRÈS L'ÉTIREMENT (v2.48.0, jalon 85 : ils étaient juste
        # AVANT depuis le jalon 22) sur l'image COULEUR du composite — no-op
        # sur un composite monochrome. POURQUOI le déplacement : ① la
        # préservation de la luminosité (option ACTIVE par défaut, cf.
        # `couleurs.scnr`) est une grandeur PERCEPTUELLE, sans objet en
        # linéaire ; ② l'ordre des références est « égaliser le fond, PUIS
        # retirer le vert » ; ③ la sortie LINÉAIRE sauvegardée ne doit porter
        # que l'empilement et les corrections — elle était ÉCRÊTÉE EN VERT
        # (MESURÉ sur son empilement M31 : excès de vert max 5,9·10⁻⁸ contre
        # 1,6·10⁻¹ sur l'empilement non écrêté).
        self.vl_scnr = False          # SCNR « moyenne neutre » (retrait du vert)
        self.vl_demagenta = False     # négatif → SCNR → positif (anti-magenta)
        self.vl_scnr_doux = False     # jalon 23 : SCNR borné par le bruit
                                      # (bruit seul — structure préservée)
        # v2.48.0 (jalon 85) : options communes aux trois outils.
        # `vl_preserve_luminance` — ACTIVE par défaut, comme Siril et
        # PixInsight (« lightness is preserved by default », `-nopreserve` pour
        # l'annuler) : après le retrait du vert, le pixel retrouve sa L* CIE.
        # MESURÉ sur l'empilement SHO NGC 2237 d'Alain (composite + étirement
        # VeraLux) : sans elle la nébuleuse passe de L* 56,5 à 25,8 — elle
        # s'ÉTEINT, c'est le « manque de doré » constaté ; avec elle, 56,4. La
        # remise de L* ne touche QUE les pixels réellement corrigés (identité
        # au bit partout ailleurs : non-régression vérifiée sur ses empilements
        # M31, 0 pixel changé).
        # `vl_scnr_force` / `vl_demagenta_force` — part de la correction
        # (1,00 = formule historique des jalons 22/23, 0,00 = aucun effet).
        # Un SCNR à force 1,00 laisse l'excès ≤ 0 PARTOUT, donc le « SCNR
        # doux » ne retire plus rien derrière lui (mesuré : 2,98·10⁻⁸) : les
        # deux cases ne se complètent qu'à force < 1.
        self.vl_preserve_luminance = True
        self.vl_scnr_force = 1.0
        self.vl_demagenta_force = 1.0
        # v2.48.0 (jalon 86) : BOOST DU ROUGE (SII) masqué à l'objet — la case
        # et sa force. DÉCOCHÉ par défaut : c'est une retouche ESTHÉTIQUE (le
        # doré du SHO), pas la correction d'un défaut de rendu — un rendu par
        # défaut reste donc inchangé AU BIT près. `force` à 1,00 est une
        # identité exacte, donc le curseur peut rester en place sans effet.
        self.vl_boost_rouge = False
        self.vl_boost_force = float(_couleurs.BOOST_ROUGE_DEFAUT)
        # --- Neutralisation de la COULEUR DU FOND (v2.36.1 ; APRÈS l'étirement
        # depuis le jalon 123) -------------------------------------------------
        # Constat d'Alain (25/09/2026) : « le fond reste bleu » à l'écran et
        # « vachement bleu » en PNG. Mesuré : le fichier LINÉAIRE a un fond
        # neutre (R/G 0,9991), mais VeraLux soustrait une ANCRE puis étire en
        # log → quelques pour cent d'écart de ciel deviennent un facteur 2,4 de
        # couleur de fond. La v2.36.1 corrigeait par des gains AVANT l'étirement
        # (`neutraliser_fond`) : insuffisant, et FABRIQUANT du magenta (mesuré
        # M33, 11/10/2026 — le gain vise à côté de ce que l'ancre SOUTRAIT).
        # Depuis le jalon 123, les gains sont mesurés sur la SORTIE étirée et
        # appliqués APRÈS le moteur (`couleurs.neutraliser_apres_etirement`),
        # complétés en amont par le PIÉDESTAL PAR CANAL (jalon 122, dans
        # `veralux.etirer`). ACTIF par défaut (défaut de rendu, pas un choix
        # esthétique) ; l'équilibrage des canaux ne le remplace pas (il estime
        # le fond sur un percentile bas — les coins, déjà neutres). Décocher =
        # ancien rendu.
        self.vl_neutre_fond = True     # neutralisation de la couleur du fond
        self.vl_neutre_gains = None    # derniers gains appliqués (R, G, B) —
                                      # informatif, lu par l'UI (None = aucun)
        # --- Réduction du BRUIT CHROMATIQUE avant étirement (v2.37.0) --------
        # Demande d'Alain (25/09/2026) : « oui pour la réduction de bruit
        # chromatique (j'allais te demander un équivalent de SCNR pour le bleu
        # de toute façon), et case DÉCOCHÉE par défaut. » Mesure qui l'a motivée
        # (son empilement M31, 115 frames) : le grain du fond est équilibré en
        # R/G (0,902) mais B/G reste à 1,174 — la SPCC applique K_B/K_G = 1,32,
        # et un gain multiplicatif amplifie le bruit du canal qu'il monte.
        # `couleurs.reduire_bruit_chroma` lisse la CHROMA (YCrCb) en laissant la
        # luminance intacte, JUSTE APRÈS la neutralisation et juste avant
        # l'étirement (no-op sur un composite monochrome). Décocher = grain
        # coloré d'origine (comportement v2.36.x). v2.37.3 : le lissage porte
        # désormais sur le RAPPORT de couleur (chroma / luminance locale) — un
        # écart de chroma absolu n'a pas de sens physique dans les ailes faibles
        # d'une étoile, où il fabriquait un halo de couleur (cf. couleurs.py).
        self.vl_chroma = False         # réduction du bruit chromatique (opt-in)
        self.vl_chroma_force = 0.5     # part du bruit chromatique retirée
        # v2.37.3 : rayon du flou de chroma. La valeur de RÉFÉRENCE (3 px) est
        # celle de la PLEINE RÉSOLUTION — donc celle des fichiers ; l'interface
        # le ramène à l'échelle de l'APERÇU (`couleurs.rayon_chroma_apercu`),
        # sinon le même rayon en pixels étale la couleur des étoiles 1/scale
        # fois plus loin qu'elles à l'écran que dans les fichiers (constat du
        # 26/09/2026 : 3 px d'aperçu = 7,2 px pleine résolution à 3838 px).
        self.vl_chroma_rayon = _couleurs.RAYON_CHROMA_DEFAUT
        self.vl_seeing = None         # mesure du seeing (jalon 10, dict) : sert
                                      # de PSF à la netteté — posée par le
                                      # thread d'acquisition, jamais mesurée ici
        self.sh_msg = ""              # message de la netteté (raison du refus),
                                      # lu par l'UI — "" si elle s'est appliquée
        self.sh_new = False           # un message vient d'arriver (lu par l'UI)
        # JALON 125 (VOLET A) : le solveur de netteté DÉDIÉ aux modes
        # STF/manuel est RETIRÉ — la chaîne pré-étirement (GraXpert →
        # débruitage → netteté) tourne désormais dans le worker UNIQUE
        # `_vl_worker`, pour LES DEUX moteurs. `sh_msg`/`sh_new` restent
        # publiés par ce worker et lus par l'UI (message de la netteté).
        # cache + solveur (thread dédié, jamais le thread UI)
        self._vl_src = None           # dernière image soumise (comparaison d'objet)
        self._vl_key = None           # clé des réglages du dernier calcul lancé
        self._vl_result = None        # (clé, image étirée) du dernier calcul TERMINÉ
        # JALON 128 : MOTEUR du dernier résultat publié (« veralux » ou « stf »).
        # Sert à ne garder à l'écran, pendant un recalcul VeraLux, QU'une image
        # réellement ÉTIRÉE par VeraLux : après un passage STF → VeraLux,
        # `_vl_result` contient l'image PRÉ-ÉTIRÉE (linéaire) — la garder
        # afficherait une image sombre au lieu du repli STF.
        self._vl_result_moteur = ""
        self._vl_job: Any = None      # (copie image, params, clé) en attente
        self._vl_pending = False      # un calcul est en cours
        self._vl_force = False        # un NOUVEL empilement attend la résolution
        self._vl_lock = threading.Lock()
        self._vl_wake = threading.Event()
        self.vl_new = False           # un résultat vient d'arriver (lu par l'UI)
        # 1a (20/10/2026) : le DERNIER `process()` a-t-il rendu l'IMAGE
        # D'ATTENTE (repli STF, pas le résultat de la chaîne) ? L'interface s'en
        # sert pour NE PAS remplacer l'image affichée : Alain ne veut jamais voir
        # d'image « bâchée » entre deux images finales.
        self.dernier_etait_attente = False
        self.vl_stage = ""            # étape COURANTE du calcul (jalon 40 :
                                      # "préparation"/"composition"/"GraXpert"…/
                                      # "étirement"), écrite par le thread
                                      # solveur, lue par l'UI (thread Tk) —
                                      # "" = calcul terminé/rien en cours.
        self.vl_error = ""            # dernière erreur du solveur (pour l'UI)
        self.vl_log_d_resolu = None   # dernier logD utilisé/résolu (pour l'UI)
        self.vl_diagnostics = None    # dernier dict de diagnostics (pour l'UI)
        self._vl_thread = threading.Thread(target=self._vl_worker, daemon=True)
        self._vl_thread.start()

    def reset(self) -> None:
        """Oublie les stats lissées et le cache VeraLux (nouvelle session /
        changement de vue) : le prochain process() relance une résolution."""
        self._stats = None
        self._gx_cache = None         # oublie aussi le résultat GraXpert live
        self._dn_cache = None         # …et le résultat du débruitage live
        self._gx_couches = {}         # …et les caches PAR COUCHE (jalon 24)
        self._dn_couches = {}
        self.vl_compo: Any = None     # couches de composition (obsolètes)
        self.sh_msg = ""
        self.sh_new = True
        # Jalon 75 : les barres de l'histogramme et l'état « figé » sont
        # propres à UNE session (comme `auto` et black/white) : un étirement
        # retouché à la main sur une cible ne doit jamais s'appliquer
        # silencieusement à la suivante. `niveaux_new` prévient l'UI qu'elle
        # doit resynchroniser ses champs (barres + valeurs).
        self.bar_noir, self.bar_median, self.bar_blanc = 0.0, 0.5, 1.0
        self.fige = False
        self.dernier_brut_niveaux = None
        self.gains_etirement = None   # jalon 136 : rien à garder d'une autre vue
        self._memo_moteur = None      # jalon 79 : rien à réutiliser d'une autre vue
        self.niveaux_new = True
        with self._vl_lock:
            self._vl_result = None
            self._vl_force = True

    def reprendre_auto(self) -> None:
        """▶ « Reprendre » (jalon 75) : l'étirement automatique repart. Les
        stats lissées sont OUBLIÉES pour que le prochain rendu reparte de
        l'image courante (saut visible, assumé et annoncé à l'écran) — sinon
        un fond figé depuis longtemps reviendrait par petites touches."""
        self.fige = False
        self._stats = None
        self._memo_moteur = None      # jalon 79 : la clé contient les stats

    @staticmethod
    def _mtf(x: Any, m: float) -> np.ndarray:
        """Midtones Transfer Function : x, m ∈ [0,1] (alias de `mtf`, jalon 75)."""
        return mtf(x, m)

    @staticmethod
    def _solve_m(x: Any, t: float) -> float:
        """m tel que MTF(x, m) = t — inversion exacte de la MTF."""
        x = min(max(x, 1e-4), 0.9999)
        m = x * (1.0 - t) / (t + x - 2.0 * t * x)
        return min(max(m, 0.001), 0.98)

    @staticmethod
    def _calc_stats(img: np.ndarray) -> tuple[float, float, float]:
        """Statistiques d'étirement (médiane, σ robuste MAD, p99.9) d'une
        image linéaire — fonction PURE : aucune mutation d'état (le
        sous-échantillonnage la garde rapide même en pleine résolution)."""
        mono = img.mean(axis=2) if img.ndim == 3 else img
        s = mono[::max(1, mono.shape[0] // 512), ::max(1, mono.shape[1] // 512)]
        med = float(np.median(s))
        sigma = max(float(np.median(np.abs(s - med))) * 1.4826, 1e-8)  # σ robuste (MAD)
        return med, sigma, float(np.percentile(s, 99.9))

    def _auto_params(self, img: np.ndarray,
                     live: bool = True) -> tuple[float, float, float]:
        # Jalon 75 : étirement GELÉ (bouton ⏹ « Figer ») — les stats ne se
        # recalculent plus ET n'avancent plus : l'image ne « respire » plus du
        # tout, et les barres de l'histogramme deviennent les seules à agir.
        # Sans ce garde-fou le gel serait un leurre (les paramètres
        # continueraient de suivre l'empilement). ▶ « Reprendre » appelle
        # `reprendre_auto()` : les stats oubliées repartent de l'image
        # courante, donc le fond se recale immédiatement.
        if self.fige and self._stats is not None:
            med, sigma, p999 = self._stats
            lo = med - self.sigma_k * sigma
            hi = max(p999, med + 10.0 * sigma, lo + 1e-8)
            return lo, hi, self._solve_m((med - lo) / (hi - lo), self.target)

        # Jalon 79 — `live=False` (rafraîchissement d'un réglage, c'est-à-dire un
        # geste de souris) RÉUTILISE les stats déjà en mémoire : `_calc_stats`
        # était calculé puis JETÉ (seule la branche `live=True` lisait son
        # résultat), soit ~30 ms d'aperçu couleur par événement pour rien.
        if not live and self._stats is not None:
            med, sigma, p999 = self._stats
        else:
            med, sigma, p999 = self._calc_stats(img)
            # Lissage temporel des STATS (pas des paramètres) : les curseurs
            # restent réactifs, mais l'image ne « pompe » pas entre deux frames.
            if self._stats is None:
                self._stats = (med, sigma, p999)
            elif live:
                a = self._ema
                self._stats = tuple(v0 + a * (v1 - v0)
                                    for v0, v1 in zip(self._stats,
                                                      (med, sigma, p999)))
            med, sigma, p999 = self._stats

        lo = med - self.sigma_k * sigma                     # ombres : bruit coupé
        hi = max(p999, med + 10.0 * sigma, lo + 1e-8)        # hautes lumières réelles
        m = self._solve_m((med - lo) / (hi - lo), self.target)
        return lo, hi, m

    # ------------------------------------ jalon 79 : mémoire du moteur d'étirement
    def _cle_moteur(self, img: np.ndarray) -> Any:
        """Clé des réglages qui déterminent la SORTIE DU MOTEUR STF/manuel :
        dimensions, mode auto/manuel, points noir et blanc, gel, k des ombres,
        cible de fond et STATS courantes. Tout ce qui n'y figure pas — gamma,
        saturation globale et par couleur, barres de niveaux — s'applique APRÈS
        le moteur : bouger l'un d'eux ne doit donc rien recalculer ici."""
        return (img.shape, img.ndim, bool(self.auto), float(self.black),
                float(self.white), bool(self.fige), self.sigma_k, self.target,
                None if self._stats is None else tuple(self._stats))

    def _moteur_stf(self, img: np.ndarray, live: bool = True) -> np.ndarray:
        """Sortie du moteur d'étirement STF ou manuel, MÉMOÏSÉE quand rien n'a
        changé (jalon 79).

        POURQUOI : les réglages d'APRÈS étirement — gamma, saturation globale,
        saturation par couleur, barres de niveaux — ne modifient PAS cette
        image. Sans mémoire, chaque pixel de souris la recalculait entièrement
        (médiane/σ/p99,9 puis MTF : 78 ms mesurés sur l'aperçu couleur
        1600x904, soit la moitié du coût d'un geste). La mémo ne PEUT PAS
        changer un rendu : elle rend l'image que le même appel aurait
        recalculée à l'identique, car TOUTES ses entrées sont dans la clé —
        image source comparée par IDENTITÉ (l'UI remplace son aperçu à chaque
        nouvelle frame, elle ne le modifie jamais en place), réglages et stats.
        `live=True` (arrivée d'une frame : le lissage temporel des stats
        avance) ne mémoïse jamais. Oubliée par `reset()` et
        `reprendre_auto()`."""
        memo = self._memo_moteur
        cle = None if live else self._cle_moteur(img)
        if (cle is not None and memo is not None and memo[0] is img
                and memo[1] == cle):
            self.last_lo, self.last_hi = memo[3], memo[4]
            self.last_m = memo[5]
            return memo[2]
        if self.auto:
            # JALON 136 : l'étirement ET ses statistiques portent sur l'image
            # NEUTRALISÉE par canal quand les ciels des trois canaux ne
            # partent pas du même niveau — sinon le point noir commun écrête
            # le canal le plus faible et la couronne des étoiles se colore
            # (halo coloré, mesure et rationale dans l'en-tête de section).
            # Ciel neutre ⇒ `src is img` et le rendu est celui d'avant AU BIT.
            src, gains = source_etirement(img)
            self.gains_etirement = gains
            lo, hi, m = self._auto_params(src, live=live)
            self.last_lo, self.last_hi = lo, hi
            # Jalon 75 : le médian résolu est conservé pour que la bande
            # « brut » de l'histogramme puisse placer son repère de médian
            # (lo + m·(hi − lo)) — sinon l'utilisateur verrait deux repères
            # sur trois et croirait à un oubli.
            self.last_m = m
            x = self._mtf(np.clip((src - lo) / (hi - lo), 0.0, 1.0), m)
        else:
            lo, hi = self.black, self.white
            if hi - lo < 1e-6:
                hi = lo + 1e-6
            x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        if cle is not None:
            self._memo_moteur = (img, cle, x, self.last_lo, self.last_hi,
                                 self.last_m)
        return x

    def notify_new_stack(self) -> None:
        """Signale qu'un NOUVEL empilement vient d'être produit (une frame de
        plus a été empilée) : le thread solveur relance la résolution. Le
        rythme des frames (≥ 1 s, souvent bien plus) EST le cooldown — aucun
        calcul entre deux frames, et le worker ne garde que le DERNIER job
        (aucune file d'attente). Appelé depuis l'UI, jamais bloquant."""
        with self._vl_lock:
            self._vl_force = True

    def vl_en_cours(self) -> bool:
        """True si le thread solveur VeraLux a un calcul en marche (jalon 40 :
        l'UI affiche alors l'étape courante `vl_stage` + un curseur animé).
        Lecture thread-sûre (booléen écrit sous verrou par le worker)."""
        return self._vl_pending

    def _vl_params(self) -> Any:
        """Clé de hachage des réglages de la chaîne PRÉ-ÉTIREMENT — COMMUNE
        aux deux moteurs depuis le jalon 125 (VOLET A) : GraXpert live,
        débruitage live, netteté live (jalon 12), SCNR et démagenta (jalon
        22), plus les paramètres d'étirement : bouger l'un d'eux relance la
        chaîne. Le MOTEUR en fait partie (STF renvoie l'image pré-étirée,
        VeraLux l'image étirée) : en changer relance donc la chaîne.
        P7 (v2.93.1) : les CORRECTIONS DE COULEUR de la composition en font
        aussi partie (`params_corrections`), sans quoi un clic sur un choix de
        couleur pouvait republier l'image en cache — le choix PRÉCÉDENT."""
        return (self.vl_mode_res, round(self.vl_target_bg, 4),
                round(self.vl_log_d, 3), self.vl_profil,
                self.vl_graxpert, self.vl_graxpert_cmd,
                self.vl_denoise, self.vl_denoise_methode,
                round(self.vl_denoise_force, 2),
                self.vl_sharp, int(self.vl_sharp_iterations),
                self.vl_scnr, self.vl_demagenta, self.vl_scnr_doux,
                # v2.48.0 (jalon 85) : force de chaque outil et préservation de
                # la luminosité — la chaîne couleur vit APRÈS l'étirement, donc
                # la modifier doit relancer le solveur.
                bool(self.vl_preserve_luminance),
                round(float(self.vl_scnr_force), 2),
                round(float(self.vl_demagenta_force), 2),
                # v2.48.0 (jalon 86) : le boost du rouge fait partie de la chaîne
                # couleur APRÈS l'étirement (le solveur doit donc le refaire) —
                # la case ET la force entrent dans la clé des réglages.
                bool(self.vl_boost_rouge),
                round(float(self.vl_boost_force), 2),
                # JALON 124 : `vl_neutre_fond` A QUITTÉ cette clé — la
                # neutralisation a quitté le solveur (elle s'applique dans
                # `process()` / `rendu_pleine_resolution`, juste avant
                # gamma/saturation) : elle ne change plus la SORTIE du moteur,
                # un basculement ne doit donc pas relancer la résolution (il est
                # rendu immédiatement par `process()`).
                bool(self.vl_chroma),                  # v2.37.0 (option)
                round(float(self.vl_chroma_force), 2),
                round(float(self.vl_chroma_rayon), 2),  # v2.37.3 (résolution)
                # P7 (v2.93.1) : LES CORRECTIONS DE COULEUR entrent dans la
                # clé — gains EFFECTIFS (manuels × SPCC/Gaia), mode du canal L,
                # équilibrage des canaux, « Linear Fit », normalisation commune,
                # lissage du combine et fusion du Ha, lus dans `vl_compo` par
                # `params_corrections()`. POURQUOI : sur le chemin PAR COUCHE le
                # worker applique lui-même `corrections_couleur()` — un clic sur
                # un choix de couleur ne changeait alors AUCUNE clé, et l'image
                # en cache était republiée à l'identique (défaut P7 mesuré :
                # « l'image garde le choix précédent »). Hors composition
                # (`vl_compo` None), la signature est vide : rien ne change.
                params_corrections(getattr(self, "vl_compo", None)),
                # JALON 125 (VOLET A) : le MOTEUR entre dans la clé (dernier
                # élément) — la chaîne pré-étirement est COMMUNE, seule la
                # dernière étape dépend du moteur : en changer doit relancer
                # la chaîne (STF publie l'image pré-étirée, VeraLux l'étirée).
                self.stretch)


    def _vl_worker(self) -> None:
        """Thread CHAÎNE PRÉ-ÉTIREMENT (vol. A, jalon 125) : enchaîne — si
        activés — GraXpert live (jalon 4) PUIS le débruitage local (jalon 9 :
        algorithmes numpy/OpenCV, aucun subprocess) PUIS la netteté live
        (jalon 12 : Richardson-Lucy, numpy/OpenCV, aucun subprocess) PUIS —
        COMMUNE aux deux moteurs depuis le jalon 127 — la chroma PUIS — en
        VeraLux SEULEMENT — l'étirement VeraLux et la chaîne couleur APRÈS
        étirement, sur le DERNIER job demandé (les jobs
        intermédiaires — slider bougé, frame remplacée — sont simplement
        remplacés, jamais empilés). Écrit le résultat sous verrou.

        La chaîne PRÉ-ÉTIREMENT (GraXpert → débruitage → netteté → chroma,
        jalon 127) est COMMUNE aux deux moteurs ; seule la DERNIÈRE étape en
        dépend : en mode STF/manuel le worker publie l'image PRÉ-ÉTIRÉE et
        c'est `process()` qui applique l'étirement STF/manuel dessus (jamais ce
        thread : les stats EMA du STF vivent dans le fil d'interface)."""
        while True:
            self._vl_wake.wait()
            self._vl_wake.clear()
            with self._vl_lock:
                job = self._vl_job
                self._vl_job = None
            if job is None:
                # Aucun job à traiter : ne jamais laisser `_vl_pending` à True
                # (un état « calcul en cours SANS job » figerait l'aperçu sur
                # l'image d'attente STF pour toujours). Job et drapeau étant
                # écrits ensemble sous verrou, cet état est incohérent : on le
                # répare plutôt que d'attendre un job qui n'arrivera pas.
                with self._vl_lock:
                    self._vl_pending = False
                continue
            img, params, key, gx, dn, sh = job[:6]
            # Jalon 40 : l'UI affiche l'étape courante (⏳) — le solveur est
            # le SEUL écrivain de vl_stage (simple str lu par le thread Tk).
            self.vl_stage = "préparation"
            gx_actif, gx_cmd = gx
            dn_actif, dn_methode, dn_force = dn
            sh_actif, sh_iter = sh
            # Jalon 22/23 : SCNR, SCNR doux et démagenta transportés dans le
            # job (7e élément, ordre d'application). Déballage TOLÉRANT
            # (6 éléments = tout False) pour compatibilité des tests qui
            # fabriquent des jobs jalon 9/12.
            coul = job[6] if len(job) > 6 else ()
            scnr_actif = bool(coul[0]) if len(coul) > 0 else False  # noqa: F841
            sd_actif = bool(coul[1]) if len(coul) > 1 else False  # noqa: F841
            dm_actif = bool(coul[2]) if len(coul) > 2 else False  # noqa: F841
            # v2.48.0 (jalon 85) : force du SCNR, force du démagenta et
            # préservation de la luminosité (3 éléments suivants du sous-tuple,
            # déballage TOLÉRANT : les jobs antérieurs n'en ont pas → 1,0/1,0/
            # True, soit les valeurs par défaut de la chaîne couleur).
            force_scnr = float(coul[3]) if len(coul) > 3 else 1.0
            force_dm = float(coul[4]) if len(coul) > 4 else 1.0
            preserve_lum = bool(coul[5]) if len(coul) > 5 else True
            # v2.48.0 (jalon 86) : boost du ROUGE (SII) masqué à l'objet — 7e et
            # 8e éléments du sous-tuple (déballage TOLÉRANT : les jobs
            # antérieurs n'en ont pas → case décochée, comme le défaut).
            boost_actif = bool(coul[6]) if len(coul) > 6 else False
            force_boost = (float(coul[7]) if len(coul) > 7
                           else _couleurs.BOOST_ROUGE_DEFAUT)
            # v2.37.0 : réduction du BRUIT CHROMATIQUE (10e élément du job —
            # déballage tolérant : les jobs antérieurs n'en ont pas → inactif).
            chroma_actif = bool(job[9]) if len(job) > 9 else False
            chroma_force = float(job[10]) if len(job) > 10 else 0.5
            # v2.37.3 : rayon du flou de chroma, déjà ramené à l'échelle de
            # l'image reçue par l'interface (déballage TOLÉRANT : les jobs
            # antérieurs n'en ont pas → rayon de référence pleine résolution).
            chroma_rayon = (float(job[11]) if len(job) > 11
                            else _couleurs.RAYON_CHROMA_DEFAUT)
            # JALON 125 (VOLET A) : le MOTEUR voyage dans le job (13e élément,
            # déballage TOLÉRANT : les jobs antérieurs n'en ont pas → "veralux",
            # leur comportement d'origine — ce solveur ne faisait que VeraLux).
            engine = str(job[12]) if len(job) > 12 else "veralux"
            # Jalon 24 : données de composition transportées dans le job
            # (8e élément : (canaux, nom, gains, mode_l), None en mode mono).
            # Jalon 54 : 5e élément OPTIONNEL du tuple — (actif, mode) du
            # recalage « Linear Fit » (déballage tolérant : les jobs des
            # tests antérieurs n'ont que 4 éléments).
            compo = job[7] if len(job) > 7 else None
            fit = (compo[4] if compo is not None and len(compo) > 4
                   else None)
            # Chantier 24/09/2026 (décision (b)/(c)) : l'équilibrage des
            # canaux (auto, et sa force) fait partie des CORRECTIONS, comme les
            # gains et le recalage — transporté en 6e élément du tuple de
            # composition (déballage TOLÉRANT : les jobs antérieurs n'ont que
            # 5 éléments → pas d'équilibrage côté solveur).
            wb = (compo[5] if compo is not None and len(compo) > 5
                  else None)
            # v2.36.0 : normalisation COMMUNE des canaux (option) — 7e élément,
            # déballage tolérant (les jobs antérieurs n'en ont pas).
            norm_commune = (bool(compo[6]) if compo is not None
                            and len(compo) > 6 else False)
            # Jalon 117d : lissage du combine LRGB (halos d'étoiles) et son seuil
            # de masque — 8e élément, déballage TOLÉRANT (helper testable).
            lissage_halos, seuil_halos = params_lissage_halos(compo)
            # JALON 124 : la NEUTRALISATION de la couleur du fond a QUITTÉ le
            # solveur (le 9e élément du job est désormais IGNORÉ — la case est
            # appliquée dans `process()`/`rendu_pleine_resolution`, juste avant
            # gamma/saturation). La clé `vl_neutre_fond` a aussi quitté
            # `_vl_params` : son basculement ne relance plus la résolution.
            # --- Jalon 24 : mode COMPOSITION — gradient ET débruitage PAR
            # COUCHE, AVANT recomposition (décision d'Alain du 19/09/2026 :
            # la pollution lumineuse et la clarté de la lune ne frappent pas
            # pareil selon le filtre, et une palette Hubble n'est pas un fond
            # physique — le modèle de fond de GraXpert ne doit voir que des
            # couches mono 2D). Chaque couche : gradient puis débruitage
            # (caches PAR RÔLE : une nouvelle frame ne relance que la couche
            # qui en a reçu une), puis composite re-fait par composer() — la
            # netteté, la chaîne couleur et l'étirement restent sur le
            # composite. Échec d'une couche = repli sur la couche brute +
            # message ; la chaîne n'est jamais bloquée. Succès → les drapeaux
            # gx/dn sont neutralisés : la chaîne composite (jalons 4/9)
            # ci-dessous est sautée — c'est aussi le repli si la
            # recomposition échoue (chaîne composite reprise sur l'image
            # brute, jamais d'image perdue).
            img_gx, err_gx = img, ""
            if compo is not None and (gx_actif or dn_actif):
                self.vl_stage = "composition"   # jalon 40 : gradient/débruitage
                canaux, nom_compo, gains, mode_l = compo[:4]   # PAR COUCHE
                                              # (jalon 54 : le 5e élément est
                                              # le recalage Linear Fit, déjà
                                              # déballé dans `fit` ci-dessus)
                msgs, traites = [], {}
                couches = {role: np.asarray(couche, dtype=np.float32)
                           for role, couche in canaux.items()}
                # --- ① GRADIENT par couche, EN PARALLÈLE (jalon 81) : les
                # couches sont INDÉPENDANTES et chaque appel GraXpert paie
                # ~2,8 s FIXES (démarrage du binaire + chargement des 217 Mo
                # du modèle). On prépare donc TOUS les appels à faire — les
                # caches par rôle évitent toujours ceux qui n'ont pas changé —
                # on les lance ENSEMBLE (mémoire bornée : cf. appliquer_lot),
                # puis on range les résultats par rôle. Les valeurs obtenues
                # sont celles de la série : mêmes commandes, mêmes fichiers,
                # aucune dépendance entre couches (vérifié : fichiers produits
                # identiques OCTET À OCTET, banc _test_gx_parallele_jalon81).
                if gx_actif:
                    a_lancer = []                # (role, cle, image)
                    for role, c in couches.items():
                        if float(np.max(np.abs(c))) < 1e-9:
                            # Équivalent par couche du garde-fou jalon 23b :
                            # une couche sans données n'est pas envoyée à
                            # l'outil (comportement imprévisible).
                            msgs.append(f"GraXpert live ({role}) : couche vide"
                                        " — ignorée")
                            continue
                        cle = ("gx", role, _gx_live.cle_image(c), gx_cmd)
                        cache = self._gx_couches.get(role)
                        if cache is not None and cache[0] == cle:
                            couches[role] = cache[1]   # cette couche n'est PAS
                        else:                          # relancée — les autres
                            a_lancer.append((role, cle, c))   # seulement
                    if a_lancer:
                        lot = _gx_live.appliquer_lot(
                            [(role, c, gx_cmd) for role, _cle, c in a_lancer])
                        for role, cle, _c in a_lancer:
                            c2, err = lot.get(role,
                                              (None, "appel non exécuté"))
                            if err or c2 is None:
                                msgs.append(f"GraXpert live ({role}) : "
                                            f"{err or 'aucun résultat'}")
                            else:
                                couches[role] = c2
                                self._gx_couches[role] = (cle, c2)
                # --- ② DÉBRUITAGE par couche : même ordre qu'avant (gradient
                # PUIS débruitage sur la couche), mêmes caches par rôle.
                if dn_actif:
                    for role, c in couches.items():
                        cle = ("dn", role, _gx_live.cle_image(c), dn_methode,
                               round(dn_force, 2))
                        cache = self._dn_couches.get(role)
                        if cache is not None and cache[0] == cle:
                            couches[role] = cache[1]
                        else:
                            c2, err = _denoise.denoiser(c, dn_methode, dn_force)
                            if err:
                                msgs.append(f"Débruitage live ({role}) : {err}")
                            else:
                                couches[role] = c2
                                self._dn_couches[role] = (cle, c2)
                traites = couches
                try:
                    # composer() NE porte AUCUNE correction de couleur : le
                    # composite re-fait depuis les couches traitées est BRUT,
                    # les corrections s'appliquent juste après, dans l'ordre
                    # validé (débruitage → CORRECTIONS → netteté/étirement).
                    comp = _composition.composer(
                        traites, nom_compo,
                        mode_l=mode_l,
                        normalisation_commune=norm_commune,
                        # Jalon 117d : la vue « traitée » recompose comme la vue
                        # « empilement » — case décochée → σ = 0 (aucun flou).
                        sigma_l=None if lissage_halos else 0.0,
                        seuil_masque_sigma=seuil_halos,
                        # Jalon J2 : la FUSION DU Ha fait partie du COMPOSITE
                        # (pas des corrections) — la vue « traitée » doit la
                        # refaire à l'identique, sinon l'écran et le fichier
                        # « tel que vu » ne montreraient pas la même image.
                        fusion_ha=params_fusion_ha(compo))
                except Exception as exc:    # formes hétérogènes (ne doit pas
                    comp = None             # arriver : cadre commun) → repli
                    msgs.append(f"Recomposition : {exc}")
                if comp is not None:
                    # --- Corrections de couleur (décision (b)/(c)) : gains
                    # EFFECTIFS (manuels × SPCC/Gaia) → équilibrage des canaux
                    # → recalage « Linear Fit ». Sans cache ici (un job par
                    # nouvel empilement) et SANS état : `moyennes()` et le
                    # composite BRUT restent intacts (contrat jalon 54). Les
                    # trois réglages sont transportés dans le job — le solveur
                    # lit une copie, jamais l'UI.
                    comp, _diag_fit = _composition.corrections_couleur(
                        comp,
                        gains=gains,
                        wb_auto=bool(wb[0]) if wb else False,
                        wb_force=float(wb[1]) if wb else 1.0,
                        cadre=wb[2] if wb and len(wb) > 2 else None,
                        linear_fit=bool(fit[0]) if fit is not None else False,
                        linear_fit_mode=(fit[1] if fit is not None
                                         else "offset"))
                    img_gx = comp           # composite re-fait depuis les
                    gx_actif = False        # couches traitées : la chaîne
                    dn_actif = False        # composite est sautée ci-dessous
                err_gx = " ; ".join(msgs)
            # --- GraXpert live (opt-in) : retrait de gradient AVANT l'étirement
            # Cache indexé par (CONTENU de l'image, commande) : une nouvelle
            # frame relance l'outil, mais pas un simple curseur VeraLux ; et
            # modifier la commande GraXpert invalide le résultat caché.
            # (Jalon 24 : sauté si le chemin PAR COUCHE ci-dessus a réussi —
            # gx_actif/dn_actif y sont neutralisés, et img_gx porte alors le
            # composite re-fait depuis les couches traitées.)
            img_gx, err_gx = (img_gx, err_gx) if compo is not None \
                else (img, "")
            if gx_actif:
                self.vl_stage = "GraXpert"      # jalon 40 : étape courante
                # Jalon 23b : un canal MORT (SHO sans S → R = 0) rend le
                # comportement de GraXpert imprévisible (sortie dégénérée →
                # image noire en visu, constat réel d'Alain). On ne lance
                # PAS l'outil : message clair + repli sur l'image brute, la
                # chaîne (débruitage/netteté/étirement) continue normalement.
                mort = _couleurs.canal_mort(img)
                if mort is not None:
                    img_gx, err_gx = img, (f"canal {mort} vide (aucune "
                                           f"donnée) : GraXpert live ignoré")
                else:
                    cle = (_gx_live.cle_image(img), gx_cmd)
                    if self._gx_cache is not None and self._gx_cache[0] == cle:
                        img_gx = self._gx_cache[1]   # curseur bougé : GraXpert
                    else:                            # n'est PAS relancé
                        img_gx, err_gx = _gx_live.appliquer(img, gx_cmd)
                        if err_gx:
                            img_gx = img             # repli : étirement de
                            self._gx_cache = None    # l'image brute, erreur
                        else:                        # signalée
                            self._gx_cache = (cle, img_gx)
            # --- Débruitage live (jalon 9, opt-in) : APRÈS le GraXpert live
            # éventuel — même ordre que la chaîne manuelle (gradient →
            # débruitage). Cache par (CONTENU de l'image ENTRANTE, méthode,
            # force) : une nouvelle frame relance le calcul (l'empreinte
            # change), pas un simple curseur VeraLux ; changer de méthode ou
            # de force invalide aussi le résultat caché. Le seuil k-sigma des
            # ondelettes et la force h du NLM sont AUTO-ADAPTÉS au bruit réel
            # de chaque frame (le débruitage suit l'intégration, comme l'œil).
            # (Jalon 24 : si le chemin par couche a réussi, dn_actif est déjà
            # False — le composite est conservé tel quel, sans 2e débruitage.)
            img_dn, err_dn = img_gx, ""
            if dn_actif:
                self.vl_stage = "débruitage"    # jalon 40 : étape courante
                cle = (_gx_live.cle_image(img_gx), dn_methode,
                       round(dn_force, 2))
                if self._dn_cache is not None and self._dn_cache[0] == cle:
                    img_dn = self._dn_cache[1]
                else:
                    img_dn, err_dn = _denoise.denoiser(img_gx, dn_methode,
                                                       dn_force)
                    if err_dn:
                        img_dn = img_gx   # repli : étirement sans débruitage
                        self._dn_cache = None
                    else:
                        self._dn_cache = (cle, img_dn)
            # --- Netteté live (jalon 12, opt-in) : APRÈS le débruitage (on
            # lisse d'abord, on restaure ensuite), AVANT l'étirement. La PSF
            # vient de la mesure de seeing du jalon 10 quand elle est
            # disponible : elle porte sur l'aperçu BRUT (c'est donc le flou
            # atmosphérique/optique de la nuit, pas la texture du débruitage)
            # et cela évite une 2e détection d'étoiles.
            img_net, err_net = img_dn, ""
            if sh_actif:
                self.vl_stage = "netteté"       # jalon 40 : étape courante
                try:
                    img_net, err_net = _sharpness.deconvoluer(
                        img_dn, iterations=sh_iter, mesure=self.vl_seeing)
                except Exception as exc:
                    # Le module ne lève JAMAIS (contrat : repli explicite) ;
                    # ce garde-fou est là pour qu'une exception imprévue ne
                    # TUE pas ce thread — un solveur mort figerait l'aperçu
                    # VeraLux pour toujours.
                    img_net, err_net = img_dn, str(exc)
                if err_net:
                    img_net = img_dn     # repli : étirement sans netteté
                self.sh_msg, self.sh_new = err_net, True
            # v2.37.0 / JALON 127 : RÉDUCTION DU BRUIT CHROMATIQUE, juste AVANT
            # l'étirement. Elle vit désormais dans la chaîne PRÉ-ÉTIREMENT
            # COMMUNE (comme GraXpert/débruitage/netteté) : elle tourne donc
            # pour LES DEUX moteurs — cocher sa case agit AUSSI en STF/manuel
            # (écran ET fichier, « le fichier = l'écran »). Lisse la chroma
            # (YCrCb) en laissant la LUMINANCE intacte : ni le niveau ni le
            # contraste du fond ne bougent — seulement le GRAIN COLORÉ que les
            # gains multiplicatifs (SPCC en tête : K_B/K_G = 1,32) ont
            # amplifié. No-op si l'option est décochée ou si l'image est mono.
            if chroma_actif:
                self.vl_stage = "chroma"        # jalon 40 : étape courante
                img_net = _couleurs.reduire_bruit_chroma(
                    img_net, force=chroma_force, rayon=chroma_rayon)
            # v2.48.0 (jalon 85) : la chaîne couleur (SCNR → SCNR doux →
            # démagenta) n'est PLUS ICI — elle est appliquée APRÈS l'étirement
            # (`couleur_apres_etirement`, juste après le moteur d'étirement).
            # NE PAS la remettre avant : elle écrêterait la sortie LINÉAIRE
            # sauvegardée et priverait la préservation de L* de tout sens
            # (cf. la note de tête du module `couleurs`).
            # JALON 123 : la NEUTRALISATION de la couleur du fond a QUITTÉ cet
            # étage (elle était juste AVANT l'étirement). Mesuré (M33,
            # 11/10/2026) : appliquée AVANT, elle visait « 0,7 % à côté » de ce
            # que l'ANCRE de VeraLux amplifie et FABRIQUAIT le magenta. Elle est
            # désormais appliquée APRÈS l'étirement, juste après le moteur (cf.
            # plus bas) — le travail pré-étirement revient au PIÉDESTAL PAR CANAL
            # (jalon 122), intégré à `veralux.etirer`.
            # JALON 125 (VOLET A) : chaîne pré-étirement COMMUNE — en mode
            # STF/manuel elle S'ARRÊTE ICI : le worker publie l'image
            # PRÉ-ÉTIRÉE (GraXpert → débruitage → netteté → chroma, JALON 127),
            # puis `process()` applique l'étirement STF/manuel DANS LE FIL
            # D'INTERFACE (les stats EMA du STF y vivent — ce thread ne doit
            # jamais y toucher). La chaîne couleur APRÈS étirement reste, elle,
            # réservée à VeraLux (elle compense les gains du moteur) ; la CHROMA
            # a QUITTÉ ce privilège au jalon 127 — elle vaut pour les DEUX
            # moteurs, à l'écran comme au fichier.
            if engine != "veralux":
                prefixe_stf = (
                    (f"GraXpert live : {err_gx} ; " if err_gx else "")
                    + (f"Débruitage live : {err_dn} ; " if err_dn else "")
                    + (f"Netteté live : {err_net} ; " if err_net else ""))
                with self._vl_lock:
                    self._vl_pending = False
                    self._vl_result = (key, img_net)
                    self._vl_result_moteur = "stf"   # jalon 128 (cf. _process_chaine)
                    self.vl_error = prefixe_stf
                    self.vl_log_d_resolu = None
                    self.vl_diagnostics = None
                    self.vl_new = True
                    self.vl_stage = ""
                continue
            prefixe = ((f"GraXpert live : {err_gx} ; " if err_gx else "")
                       + (f"Débruitage live : {err_dn} ; " if err_dn else "")
                       + (f"Netteté live : {err_net} ; " if err_net else ""))
            self.vl_stage = "étirement"         # jalon 40 : étape courante
            try:
                result, log_d_util, diag = _veralux.etirer(img_net, **params)
            except Exception as exc:      # moteur absent, image dégénérée…
                with self._vl_lock:
                    self._vl_pending = False
                    self.vl_error = f"{prefixe}VeraLux : {exc}"
                    self.vl_new = True
                    self.vl_stage = ""    # calcul terminé (en erreur) — jalon 40
                continue
            # JALON 124 : la NEUTRALISATION de la couleur du fond a QUITTÉ le
            # solveur — elle s'applique désormais APRÈS l'étage de niveaux,
            # juste avant gamma/saturation (cf. `process()` et
            # `rendu_pleine_resolution`), pour que ces derniers ne la
            # contredisent plus. Le solveur ne fait donc plus que l'étirement
            # puis la chaîne couleur APRÈS étirement ci-dessous.
            # v2.48.0 (jalon 85) : CHAÎNE COULEUR APRÈS L'ÉTIREMENT — SCNR →
            # SCNR doux → démagenta, avec préservation de la luminosité. Elle
            # était appliquée AVANT le moteur aux jalons 22/23 (cf. la note du
            # module `couleurs`). Garde-fou : un échec n'est jamais silencieux
            # (le résultat non corrigé est publié ET la raison est annoncée).
            err_coul = ""
            try:
                result = couleur_apres_etirement(
                    result, coul, force_scnr=force_scnr,
                    force_demagenta=force_dm,
                    preserve_luminance=preserve_lum,
                    boost_rouge=boost_actif, force_boost=force_boost)
            except Exception as exc:
                err_coul = f"Chaîne couleur live : {exc} ; "
            with self._vl_lock:
                self._vl_pending = False
                self._vl_result = (key, result)
                self._vl_result_moteur = "veralux"   # jalon 128 (cf. _process_chaine)
                self.vl_error = prefixe + err_coul   # "" si tout s'est bien passé
                self.vl_log_d_resolu = log_d_util
                self.vl_diagnostics = diag
                # JALON 124 : `vl_neutre_gains` n'est PLUS publié ici (la
                # neutralisation a quitté le solveur) — `process()` le publie
                # désormais, au moment où il applique réellement la correction.
                self.vl_new = True
                self.vl_stage = ""        # calcul terminé — jalon 40

    def sh_en_cours(self) -> bool:
        """JALON 125 (VOLET A) : TOUJOURS False — le solveur de netteté DÉDIÉ
        (modes STF/manuel) n'existe plus ; la netteté vit désormais dans la
        chaîne pré-étirement UNIQUE (`_vl_worker`), pour les DEUX moteurs.
        Conservé pour la compatibilité des appelants (l'état des calculs suit
        `vl_en_cours()` / `vl_stage`, qui couvrent les deux moteurs)."""
        return False

    def _soumettre_chaine(self, img: np.ndarray) -> Any:
        """[Interne] SOUMET un job à la chaîne pré-étirement si nécessaire.

        Étape 1a (20/10/2026) — factorisé depuis `_process_chaine` : quand la
        chaîne est active, l'interface ne rend plus la pile brute et laisse
        l'image FINALE arriver par `vl_new`. `process()` n'étant alors plus
        appelé pour cette frame, c'est `demander_chaine()` qui alimente le
        worker par CE MÊME code — mêmes clés, mêmes paramètres, même ordre :
        aucun pixel ne change.

        Rend la clé de réglages courante (celle du cache de résultat).
        """
        key = self._vl_params() + (img.shape,)
        with self._vl_lock:
            force = self._vl_force
        # Jalon 3 : on ne soumet QUE si l'empilement a changé
        # (notify_new_stack) ou si les réglages ont changé — l'objet image
        # change à chaque tick UI sans nouvel empilement, il ne doit PAS
        # déclencher de recalcul.
        if force or self._vl_key != key:
            params = dict(mode=self.vl_mode_res, target_bg=self.vl_target_bg,
                          log_d=self.vl_log_d, profil=self.vl_profil)
            gx = (self.vl_graxpert, self.vl_graxpert_cmd)   # capté côté UI
            dn = (self.vl_denoise, self.vl_denoise_methode,
                  self.vl_denoise_force)                    # capté côté UI
            sh = (self.vl_sharp, int(self.vl_sharp_iterations))
            coul = (self.vl_scnr, self.vl_scnr_doux, self.vl_demagenta,
                    float(self.vl_scnr_force),
                    float(self.vl_demagenta_force),
                    bool(self.vl_preserve_luminance),
                    bool(self.vl_boost_rouge),      # v2.48.0 (jalon 86)
                    float(self.vl_boost_force))
            # v2.48.0 (jalons 85/86) : les trois cases couleur ET leurs options
            # (dont le boost du rouge) voyagent ensemble — sous-tuple de 8,
            # deballage TOLERANT cote worker ; appliquees APRES l'etirement.
            # v2.48.0 (jalon 85) : les trois cases ET leurs options voyagent
            # ensemble (sous-tuple de 6 — déballage tolérant côté worker) —
            # elles sont appliquées APRÈS l'étirement du solveur.
            # v2.36.1 : neutralisation de la couleur du fond AVANT l'étirement
            # (9e élément du job — déballage tolérant côté worker).
            nf = bool(self.vl_neutre_fond)
            # v2.37.0 : réduction du bruit chromatique (10e et 11e éléments).
            chroma = bool(self.vl_chroma)
            chroma_force = float(self.vl_chroma_force)
            chroma_rayon = float(self.vl_chroma_rayon)   # v2.37.3 (résolution)
            # Jalon 24 : couches de la composition (posées par l'UI, jamais
            # mutées en place — remplacement entier), capturées avec le job.
            compo = self.vl_compo
            with self._vl_lock:
                if not self._vl_pending:
                    self._vl_pending = True
                    self._vl_force = False   # consommé : job réellement soumis
                    # copie défensive : img appartient à l'UI et peut être
                    # remplacée pendant le calcul
                    self._vl_job = (img.astype(np.float32).copy(), params,
                                    key, gx, dn, sh, coul, compo, nf,
                                    chroma, chroma_force, chroma_rayon,
                                    # jalon 125 : le MOTEUR (« veralux » seulement
                                    # si le chemin VeraLux est RÉELLEMENT utilisé)
                                    "veralux" if self._veralux_actif() else "stf")
                    self._vl_wake.set()
            self._vl_src, self._vl_key = img, key
        return key

    def demander_chaine(self, img: np.ndarray) -> None:
        """Demande le calcul de `img` par la chaîne, SANS RIEN RENDRE.

        Étape 1a (20/10/2026) : quand la chaîne est active, la pile brute n'est
        plus rendue (son image serait remplacée ~2 s plus tard par l'image
        finale). Mais `process()` était le SEUL point qui soumettait le job au
        worker : sans cet appel, la chaîne ne calculerait jamais. Cette méthode
        fait donc exactement la SOUMISSION de `process()` — aucun calcul, aucun
        résultat lu, aucune variable Tk touchée.
        """
        self._soumettre_chaine(img)

    def chaine_sollicitee(self) -> bool:
        """True si `process()` va SOUMETTRE la chaîne pré-étirement.

        C'est la condition EXACTE du `vl_new` attendu par l'interface (étape 1a,
        20/10/2026) : le worker n'est sollicité que par le chemin VeraLux (qui
        étire DANS le worker) ou par une étape active de la chaîne pré-étirement
        en STF/manuel. Les cases couleur d'APRÈS étirement (SCNR, démagenta,
        boost) ne déclenchent AUCUN calcul en STF/manuel : elles s'appliquent
        dans `process()`. Les confondre ferait différer un rendu qui n'arrive-
        rait jamais — l'interface attendrait un `vl_new` en vain.
        """
        return bool(self._veralux_actif() or self.vl_graxpert
                    or self.vl_denoise or self.vl_sharp or self.vl_chroma)

    def _process_chaine(self, img: np.ndarray,
                        live: bool = True) -> np.ndarray:
        """CHAÎNE PRÉ-ÉTIREMENT (vol. A, jalon 125) : rend le dernier résultat
        terminé du worker (ou l'image d'attente STF) et soumet un calcul si
        l'image ou les réglages ont changé. Jamais bloquant : aucun calcul ici,
        seulement une copie. Pour VeraLux la sortie est l'image ÉTIRÉE ; pour
        STF/manuel c'est l'image PRÉ-ÉTIRÉE (GraXpert → débruitage → netteté),
        l'étirement STF/manuel étant appliqué ensuite par `process()`.
        v2.55.3 : la FORME de la source entre dans la clé — sans elle, le
        résultat PLEINE RÉSOLUTION en cache resservait après décochage de
        « Rendu pleine résolution » (même clé de réglages) : l'écran gardait
        l'ancienne image et ses étiquettes minuscules, constat d'Alain.

        Étape 1a (20/10/2026) : la SOUMISSION est déléguée à `_soumettre_chaine`
        (partagée avec `demander_chaine`) ; cette méthode ne garde que la
        LECTURE du cache et l'image d'attente.
        """
        key = self._soumettre_chaine(img)
        self.dernier_etait_attente = False

        with self._vl_lock:
            res = self._vl_result \
                if (self._vl_result is not None
                    and self._vl_result[0] == key) else None
            # JALON 128 : pas de résultat pour la clé COURANTE, mais un calcul
            # VeraLux est EN COURS et un résultat VeraLux PRÉCÉDENT existe (même
            # forme d'image) → on le garde à l'écran au lieu de basculer sur le
            # repli STF. Constat d'Alain (12/10/2026) : à chaque recalcul, l'image
            # « sautait » brutalement de l'aspect VeraLux à l'aspect STF ; garder
            # l'image VeraLux existante (périmée de quelques dixièmes de seconde)
            # est bien plus fidèle, et l'UI superpose un indicateur de calcul.
            # On n'accepte QUE le moteur VeraLux (`_vl_result_moteur`) : après un
            # passage STF → VeraLux, `_vl_result` contient l'image PRÉ-ÉTIRÉE
            # (linéaire) — la garder afficherait une image sombre.
            precedent = None
            if (res is None and self._vl_pending
                    and self._veralux_actif()
                    and self._vl_result_moteur == "veralux"
                    and self._vl_result is not None
                    and self._vl_result[1].shape == img.shape):
                precedent = self._vl_result[1]
        if res is not None:
            # JALON 125 (VOLET A) : image ÉTIRÉE (VeraLux) ou PRÉ-ÉTIRÉE
            # (STF/manuel — l'étirement STF/manuel est appliqué par
            # `process()`), mêmes dimensions [0..1] dans les deux cas.
            return res[1]
        if precedent is not None:
            # JALON 128 : image VeraLux PRÉCÉDENTE gardée à l'écran pendant le
            # recalcul (l'indicateur de calcul est superposé par l'UI, cf.
            # `ui/renderer._dessiner_spinner_vl`). Elle est DÉJÀ étirée par
            # VeraLux : `process()` n'ajoute que les étages finaux (niveaux /
            # neutralisation / gamma / saturation), comme pour un résultat à
            # jour — AUCUN double étirement.
            return precedent
        # Image d'attente (la chaîne n'a pas encore rendu son résultat).
        # En VeraLux : le STF auto (aperçu rapide, SANS toucher aux réglages
        # utilisateur black/white/gamma — on ne lit que les stats lissées).
        # En STF/manuel : l'image LINÉAIRE telle quelle — c'est `process()`
        # qui l'étire, et la rendre déjà étirée la ferait étirer DEUX FOIS.
        # 1a : on SIGNALE que ce n'est pas un résultat final — l'interface
        # gardera l'image précédente au lieu d'afficher ce repli « bâché ».
        self.dernier_etait_attente = True
        # Elle n'est pas nette (transitoire, quelques dixièmes de seconde).
        if self._veralux_actif():
            # JALON 136 : même neutralisation par canal que `_moteur_stf` —
            # l'image d'attente VeraLux est un STF auto, elle ne doit pas
            # montrer un ciel bleu vif pendant le calcul.
            src, _ = source_etirement(img)
            lo, hi, m = self._auto_params(src, live=live)
            return self._mtf(np.clip((src - lo) / (hi - lo), 0.0, 1.0), m)
        return img

    @staticmethod
    def _gamma_saturation(x: Any, rgb: bool, gamma: float,
                          saturation: float) -> Any:
        """Gamma et saturation COMMUNS — appliqués après l'étirement, quel que
        soit le mode (STF, manuel, VeraLux). Factorisés pour que le rendu
        « tel que vu » de la sauvegarde (jalon 5) soit strictement identique
        à l'affichage. (Simple relais de `_finition` depuis le jalon 75 : la
        signature d'origine est conservée pour les appelants et les bancs.)"""
        return DisplayProcessor._finition(x, rgb, gamma, saturation, None)

    @staticmethod
    def _finition(x: Any, rgb: bool, gamma: float, saturation: float,
                  sat_canaux: Any = None) -> Any:
        """Dernières retouches d'écran, dans un ordre FIXE : gamma →
        saturation globale → saturation PAR COULEUR (jalon 75).
        Appliquées après l'étirement ET après l'étage de niveaux, quel que
        soit le mode ; factorisées pour que « tel que vu » soit identique à
        l'affichage au pixel près (jalon 5)."""
        if abs(gamma - 1.0) > 1e-3:
            x = np.power(x, 1.0 / max(gamma, 0.05))
        if rgb and abs(saturation - 1.0) > 1e-3:
            hsv = cv2.cvtColor(np.clip(x, 0.0, 1.0), cv2.COLOR_RGB2HSV)
            hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0.0, 1.0)
            x = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        if rgb and saturation_actifs(sat_canaux):
            x = saturation_canaux(x, sat_canaux)
        return np.clip(x, 0.0, 1.0)

    def _veralux_actif(self) -> bool:
        """True si le chemin VeraLux est RÉELLEMENT utilisé (moteur choisi ET
        disponible) — c'est ce qui décide où la netteté est appliquée."""
        return self.stretch == "veralux" and _veralux.moteur_disponible()

    def process(self, img: np.ndarray, live: bool = True) -> np.ndarray:
        img = img.astype(np.float32, copy=False)
        # 1a (20/10/2026) : ce drapeau dit à l'interface si le rendu qui suit est
        # un RÉSULTAT ou seulement l'image d'attente. Remis à False à CHAQUE
        # appel (tous les chemins), pour qu'un ancien « attente » ne fasse pas
        # sauter un rendu légitime.
        self.dernier_etait_attente = False
        # JALON 125 (VOLET A) : plus de solveur de netteté dédié — la chaîne
        # pré-étirement (GraXpert → débruitage → netteté) tourne dans le worker
        # UNIQUE `_vl_worker`, pour LES DEUX moteurs (décision d'Alain,
        # 12/10/2026 : « le fichier = l'écran » — GraXpert + débruitage
        # tournent désormais À L'ÉCRAN en STF/manuel aussi).
        # v2.48.0 (jalon 85) : la chaîne couleur (SCNR / SCNR doux / démagenta)
        # n'est plus appliquée AVANT l'étirement — elle suit le moteur, juste
        # après. En mode VeraLux, comme la chaîne pré-étirement, elle est
        # appliquée par le worker : ne pas la refaire ici.
        if self._veralux_actif():
            x = self._process_chaine(img, live=live)
        else:
            if self.stretch == "veralux" and not self.vl_error:
                self.vl_error = ("VeraLux : moteur tiers veralux_core_headless.py "
                                 "introuvable — affichage STF en attendant.")
                self.vl_new = True
            # Sortie de la chaîne pré-étirement (GraXpert/débruitage/netteté/
            # chroma — jalon 127 pour la chroma). AUCUNE étape active → l'image
            # brute, à l'identique : le rendu STF reste INSTANTANÉ (aucun
            # détour par le worker), comme avant.
            if self.chaine_sollicitee():
                img_chaine = self._process_chaine(img, live=live)
            else:
                img_chaine = img
            # Jalon 79 : l'étirement passe par une MÉMOIRE (`_moteur_stf`) —
            # un réglage d'APRÈS étirement (gamma, saturations, barres de
            # niveaux) retrouve l'image déjà étirée au lieu de la recalculer.
            x = self._moteur_stf(img_chaine, live=live)
            # v2.48.0 (jalon 85) : chaîne couleur APRÈS l'étirement — la
            # préservation de la luminosité est une grandeur perceptuelle, et
            # l'entrée linéaire (et donc le fichier « empilement traité ») n'est
            # plus écrêtée en vert. En mode VeraLux, elle est appliquée par le
            # solveur (branche ci-dessus) : ne pas la refaire.
            x = couleur_apres_etirement(
                x, (self.vl_scnr, self.vl_scnr_doux, self.vl_demagenta),
                force_scnr=self.vl_scnr_force,
                force_demagenta=self.vl_demagenta_force,
                preserve_luminance=self.vl_preserve_luminance,
                boost_rouge=self.vl_boost_rouge,
                force_boost=self.vl_boost_force)
        # Jalon 75 : l'image de SORTIE DU MOTEUR est mémorisée AVANT l'étage
        # de niveaux — c'est elle qu'affiche la bande basse de l'histogramme,
        # pour que les barres découpent bien la donnée qu'elles reçoivent (et
        # que la courbe ne bouge pas sous les doigts). Relue par l'UI juste
        # après cet appel, dans le MÊME thread ; jamais modifiée ici.
        self.dernier_brut_niveaux = x
        if niveaux_actifs(self.bar_noir, self.bar_median, self.bar_blanc):
            x = niveaux(x, self.bar_noir, self.bar_median, self.bar_blanc)
        # JALON 124 : neutralisation de la couleur du fond JUSTE AVANT
        # gamma/saturation — les retouches vraiment finales (décision d'Alain,
        # 12/10/2026). Elle a QUITTÉ le solveur (`_vl_worker`) : c'est ici
        # qu'elle trouve sa place, après l'étage de niveaux. JALON 137 : elle
        # vaut aussi en STF (moteurs AUTOMATIQUES), plus seulement en VeraLux.
        x = self._neutraliser_fond(x)
        x = self._finition(x, img.ndim == 3, self.gamma, self.saturation,
                           self.sat_canaux)
        return (x * 255).astype(np.uint8)

    def _neutraliser_fond(self, x: Any) -> Any:
        """NEUTRALISATION de la couleur du fond APRÈS l'étirement — jalon 124.

        Appliquée APRÈS l'étage de niveaux, JUSTE AVANT gamma/saturation, pour
        que ces dernières retouches ne la contredisent plus (appliquée plus tôt,
        elle était partiellement réintroduite par la saturation par couleur —
        MESURÉ sur M33 : fond R/G 1,0007 après neutralisation → 1,0108 après
        la finition, contre 1,0128 sans neutralisation du tout). Mesure les
        gains sur la SORTIE (ce que l'œil voit, `couleurs.gains_fond`) et les
        applique ; publie `vl_neutre_gains` (None si l'option est décochée, si
        aucun moteur AUTOMATIQUE n'est à l'œuvre, ou si rien n'est corrigé) —
        l'UI s'en sert pour ANNONCER la correction. MÊME étage que le fichier
        « tel que vu » (`rendu_pleine_resolution`) : l'écran == le fichier.

        JALON 137 : elle vaut pour **LES DEUX moteurs automatiques** — VeraLux
        (son ANCRE amplifie le fond, c'était le cas d'origine) **ET le STF
        auto**, où la case était VISIBLE et SANS EFFET (exactement le défaut
        corrigé au jalon 127 pour la chroma : une case inerte est un mensonge
        de l'interface). Le MODE MANUEL reste en dehors : l'utilisateur y règle
        lui-même le point noir, souvent AU niveau du fond — il n'y a alors plus
        de « couleur du fond » à mesurer (et une correction mesurée sur du noir
        serait du bruit appliqué à toute l'image).
        """
        self.vl_neutre_gains = None
        if not (self.vl_neutre_fond
                and (self.auto or self._veralux_actif())):
            return x
        g = _couleurs.gains_fond(x)
        if g is None or bool(np.allclose(g, 1.0, atol=1e-4)):
            return x
        self.vl_neutre_gains = g
        return _couleurs.neutraliser_apres_etirement(x)

    # ------------------------------------------------------------- jalon 5
    def rendu_pleine_resolution(self, img: np.ndarray,
                                reglages: Any = None) -> np.ndarray:
        """Rendu « tel que vu » (jalon 5) d'une image LINÉAIRE PLEINE
        résolution — empilement complet ou résultat traité — pour la
        sauvegarde « 💾 Enregistrer tel que vu ». Reproduit l'étirement
        affiché : STF/manuel recalculé sur l'image complète, ou VeraLux
        avec le DERNIER logD résolu (rendu identique à l'écran, sans
        re-résolution ; repli sur une résolution target_bg si aucun logD
        n'a encore été résolu, et repli STF/manuel si le moteur tiers est
        absent — comme l'affichage) — PUIS gamma/saturation communs.

        Appelé depuis un thread de travail, JAMAIS le thread UI : ne touche
        à AUCUN état partagé (pas de stats EMA, pas de solveur, pas de
        cache, jamais black/white/gamma). Les réglages sont lus dans
        reglages (dict capturé côté UI) ou, à défaut, dans les attributs
        courants. Renvoie un float [0..1] de mêmes dimensions ; lève une
        exception en cas d'échec — l'appelant gère l'erreur.

        NB : GraXpert live n'est PAS appliqué ici — l'appelant l'enchaîne
        AVANT (vue « empilement ») ; en vue « traitée », l'image a déjà
        subi le traitement externe (GraXpert/BXT manuels).
        """
        r = (reglages or {}).get
        stretch = r("stretch", self.stretch)
        if stretch == "veralux" and _veralux.moteur_disponible():
            # v2.37.2 : mise à l'échelle GLOBALE (jamais une coupe à 1,0 : elle
            # écrasait tout ce qui dépasse — le CŒUR de M31 entier — sur une
            # seule valeur, donc un rendu PLAT, alors que le même étirement
            # appliqué au fichier sauvegardé garde son dégradé).
            img = _veralux.normaliser_lin(img)
            if r("vl_mode_res", self.vl_mode_res) == _veralux.MODE_LOG_D:
                log_d = r("vl_log_d", self.vl_log_d)
            elif r("vl_log_d_resolu", self.vl_log_d_resolu) is not None:
                log_d = r("vl_log_d_resolu", self.vl_log_d_resolu)
            else:
                log_d = None
            params: dict[str, Any] = dict(
                          profil=r("vl_profil", self.vl_profil),
                          # v2.38.0 : le FOND CIBLE de l'étape de sortie du moteur
                          # est transmis DANS LES DEUX MODES. Il ne l'était que
                          # lorsque le logD restait à résoudre : une fois le logD
                          # mémorisé (cas courant en live), `etirer` reprenait le
                          # défaut du module (0,20) alors que l'écran, lui, utilise
                          # le fond cible de l'utilisateur — mesuré sur une image
                          # réelle : fond final 0,197 contre 0,159, écart moyen
                          # 9,6 niveaux de 8 bits (17 au pire). Le fichier ne
                          # correspondait donc PAS à l'écran, ce que la règle du
                          # projet interdit (« le fichier correspond à l'écran »).
                          target_bg=float(r("vl_target_bg", self.vl_target_bg)))
            if log_d is None:
                params.update(mode=_veralux.MODE_TARGET_BG)
            else:
                params.update(mode=_veralux.MODE_LOG_D, log_d=log_d)
            x, _, _ = _veralux.etirer(img, **params)
        elif r("auto", self.auto):
            # JALON 136 : même neutralisation par canal que l'écran — « tel que
            # vu » doit rester l'écran au pixel près (règle du projet). Ciel
            # neutre ⇒ `src is img` et le rendu est celui d'avant AU BIT.
            src, _ = source_etirement(img)
            # Jalon 75 : étirement GELÉ (⏹) → le fichier doit reproduire
            # l'écran, donc utiliser les MÊMES stats gelées que l'affichage
            # (dict capturé côté UI) ; sinon « tel que vu » serait calculé sur
            # les stats du moment et ne correspondrait plus à ce qu'on voit.
            gelees = r("stats_gelees",
                       self._stats if self.fige else None)
            if gelees is not None:
                med, sigma, p999 = gelees
            else:
                med, sigma, p999 = self._calc_stats(src)
            lo = med - r("sigma_k", self.sigma_k) * sigma
            hi = max(p999, med + 10.0 * sigma, lo + 1e-8)
            m = self._solve_m((med - lo) / (hi - lo), r("target", self.target))
            x = self._mtf(np.clip((src - lo) / (hi - lo), 0.0, 1.0), m)
        else:
            lo, hi = r("black", self.black), r("white", self.white)
            if hi - lo < 1e-6:
                hi = lo + 1e-6
            x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        # v2.48.0 (jalon 85) : CHAÎNE COULEUR APRÈS L'ÉTIREMENT, comme à
        # l'écran — le fichier « tel que vu » doit être l'écran au pixel près
        # (règle du projet). Aux jalons 22/23 elle était appliquée AVANT, par
        # l'appelant, et n'apparaissait donc pas ici.
        x = couleur_apres_etirement(
            x, (r("vl_scnr", self.vl_scnr),
                r("vl_scnr_doux", self.vl_scnr_doux),
                r("vl_demagenta", self.vl_demagenta)),
            force_scnr=float(r("vl_scnr_force", self.vl_scnr_force)),
            force_demagenta=float(r("vl_demagenta_force",
                                    self.vl_demagenta_force)),
            preserve_luminance=bool(r("vl_preserve_luminance",
                                      self.vl_preserve_luminance)),
            boost_rouge=bool(r("vl_boost_rouge", self.vl_boost_rouge)),
            force_boost=float(r("vl_boost_force", self.vl_boost_force)))
        # Jalon 75 : étage de NIVEAUX (les 3 barres de l'histogramme) puis
        # finition (gamma, saturation globale, saturation par couleur) —
        # exactement la même chaîne que `process()`, au même endroit, pour que
        # le fichier « tel que vu » soit l'écran au pixel près.
        noir = float(r("bar_noir", self.bar_noir))
        median = float(r("bar_median", self.bar_median))
        blanc = float(r("bar_blanc", self.bar_blanc))
        if niveaux_actifs(noir, median, blanc):
            x = niveaux(x, noir, median, blanc)
        # JALON 124 : NEUTRALISATION de la couleur du fond APRÈS l'étirement ET
        # l'étage de niveaux, JUSTE AVANT gamma/saturation (décision d'Alain,
        # 12/10/2026) — MÊME étage que l'affichage (`process()._neutraliser_fond`),
        # pour que le fichier « tel que vu » reste l'écran au pixel près.
        # JALON 137 : LES DEUX moteurs automatiques (STF auto ET VeraLux) — la
        # condition doit rester le MIROIR de `_neutraliser_fond`, sinon l'écran
        # et le fichier divergent (le banc 137 vérifie la parité au bit).
        if (bool(r("vl_neutre_fond", self.vl_neutre_fond))
                and (bool(r("auto", self.auto))
                     or (stretch == "veralux" and _veralux.moteur_disponible()))):
            x = _couleurs.neutraliser_apres_etirement(x)
        return self._finition(x, img.ndim == 3,
                              r("gamma", self.gamma),
                              r("saturation", self.saturation),
                              r("sat_canaux", self.sat_canaux))
