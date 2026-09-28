# -*- coding: utf-8 -*-
"""Étirement temps réel : auto STF façon PixInsight, manuel, ou VeraLux (tiers)."""

import threading

import numpy as np
import cv2

from ..external import live as _gx_live
from . import couleurs as _couleurs
from . import composition as _composition
from . import denoise as _denoise
from . import sharpness as _sharpness
from . import veralux as _veralux


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


def mtf(x, m):
    """Midtones Transfer Function : x, m ∈ [0,1] (MTF de PixInsight/STF)."""
    m = min(max(m, 0.001), 0.98)
    return np.clip(((m - 1.0) * x) / ((2.0 * m - 1.0) * x - m), 0.0, 1.0)


def niveaux_actifs(noir=0.0, median=0.5, blanc=1.0):
    """True si l'étage de niveaux CHANGE quelque chose (sinon on l'ignore :
    le rendu par défaut est alors strictement celui d'avant le jalon 75)."""
    return (abs(float(noir)) > 1e-6
            or abs(float(median) - 0.5) > 1e-6
            or abs(float(blanc) - 1.0) > 1e-6)


def niveaux(x, noir=0.0, median=0.5, blanc=1.0):
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


def saturation_actifs(gains):
    """True si la saturation par canal change quelque chose (1,0 = neutre)."""
    if gains is None:
        return False
    return any(abs(float(v) - 1.0) > 1e-3 for v in gains)


def saturation_canaux(x, gains):
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
    donc AUSSI en STF/manuel. Deux chemins, mêmes réglages et même module :
      - mode VeraLux : la netteté est la DERNIÈRE étape du thread solveur,
        donc correctement APRÈS GraXpert/débruitage (gradient → débruitage →
        netteté → étirement) ;
      - mode STF/manuel : un thread solveur DÉDIÉ (`_sh_worker`) la calcule
        sur l'aperçu, déclenché par `_process_nettete()` à la lecture ; tant
        que le résultat n'est pas prêt, l'image d'attente est l'image NON
        nette (jamais bloquant, jamais l'image d'un autre empilement).
    La PSF est celle du seeing mesuré au jalon 10 (`vl_seeing`, mesuré sur
    l'aperçu par le thread d'acquisition) quand elle est disponible : c'est la
    mesure du flou réel, et elle évite une 2e mesure ; sinon le module mesure
    lui-même. Refus explicite (image inchangée + raison, jamais de no-op
    silencieux) si le module juge la déconvolution sans objet.
    """
    def __init__(self):
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
        self._stats = None            # (médiane, σ, p99.9) lissées — anti-pompage
        self._ema = 0.25              # réactivité : 0 = figé, 1 = instantané

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
        self.vl_compo = None
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
        # APRÈS composition (image COULEUR du composite) et JUSTE AVANT
        # l'étirement (décision d'Alain) — no-op sur un composite monochrome.
        self.vl_scnr = False          # SCNR « moyenne neutre » (retrait du vert)
        self.vl_demagenta = False     # négatif → SCNR → positif (anti-magenta)
        self.vl_scnr_doux = False     # jalon 23 : SCNR borné par le bruit
                                      # (bruit seul — structure préservée)
        # --- Neutralisation de la COULEUR DU FOND avant étirement (v2.36.1) --
        # Constat d'Alain (25/09/2026) : « le fond reste bleu » à l'écran et
        # « vachement bleu » en PNG. Mesuré : le fichier LINÉAIRE a un fond
        # neutre (R/G 0,9991), mais VeraLux soustrait une ANCRE puis étire en
        # log → quelques pour cent d'écart de ciel deviennent un facteur 2,4 de
        # couleur de fond (résidus 1 : 1,70 : 2,44 → fond étiré R/G 0,363 ·
        # B/G 1,611). `couleurs.neutraliser_fond` corrige par des gains par
        # canal (~2 % ici) mesurés sur la médiane de la MOITIÉ SOMBRE juste
        # AVANT l'étirement → fond étiré R/G 1,020 · B/G 0,996. ACTIF par
        # défaut (c'est un défaut de rendu, pas un choix esthétique) ;
        # l'équilibrage des canaux ne le remplace pas : il estime le fond sur
        # un percentile bas (les coins, déjà neutres), pas sur l'histogramme
        # global où vit l'ancre. Décocher = ancien rendu.
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
        # solveur DÉDIÉ à la netteté des modes STF/manuel (le mode VeraLux
        # l'applique dans son propre solveur, cf. _vl_worker)
        self._sh_job = None           # (copie image, clé, objet source)
        self._sh_pending = False      # un calcul de netteté est en cours
        self._sh_soumis = None        # (objet source, clé) du dernier job SOUMIS
        self._sh_result = None        # (clé, objet source, image nette)
        self._sh_lock = threading.Lock()
        self._sh_wake = threading.Event()
        self._sh_thread = threading.Thread(target=self._sh_worker, daemon=True)
        self._sh_thread.start()
        # cache + solveur (thread dédié, jamais le thread UI)
        self._vl_src = None           # dernière image soumise (comparaison d'objet)
        self._vl_key = None           # clé des réglages du dernier calcul lancé
        self._vl_result = None        # (clé, image étirée) du dernier calcul TERMINÉ
        self._vl_job = None           # (copie image, params, clé) en attente
        self._vl_pending = False      # un calcul est en cours
        self._vl_force = False        # un NOUVEL empilement attend la résolution
        self._vl_lock = threading.Lock()
        self._vl_wake = threading.Event()
        self.vl_new = False           # un résultat vient d'arriver (lu par l'UI)
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

    def reset(self):
        """Oublie les stats lissées et le cache VeraLux (nouvelle session /
        changement de vue) : le prochain process() relance une résolution."""
        self._stats = None
        self._gx_cache = None         # oublie aussi le résultat GraXpert live
        self._dn_cache = None         # …et le résultat du débruitage live
        self._gx_couches = {}         # …et les caches PAR COUCHE (jalon 24)
        self._dn_couches = {}
        self.vl_compo = None          # couches de composition (obsolètes)
        with self._sh_lock:           # …et celui de la netteté live (jalon 12) :
            self._sh_result = None    # un autre empilement ou une autre vue ne
            self._sh_soumis = None    # doit jamais réutiliser un résultat
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
        self.niveaux_new = True
        with self._vl_lock:
            self._vl_result = None
            self._vl_force = True

    def reprendre_auto(self):
        """▶ « Reprendre » (jalon 75) : l'étirement automatique repart. Les
        stats lissées sont OUBLIÉES pour que le prochain rendu reparte de
        l'image courante (saut visible, assumé et annoncé à l'écran) — sinon
        un fond figé depuis longtemps reviendrait par petites touches."""
        self.fige = False
        self._stats = None

    @staticmethod
    def _mtf(x, m):
        """Midtones Transfer Function : x, m ∈ [0,1] (alias de `mtf`, jalon 75)."""
        return mtf(x, m)

    @staticmethod
    def _solve_m(x, t):
        """m tel que MTF(x, m) = t — inversion exacte de la MTF."""
        x = min(max(x, 1e-4), 0.9999)
        m = x * (1.0 - t) / (t + x - 2.0 * t * x)
        return min(max(m, 0.001), 0.98)

    @staticmethod
    def _calc_stats(img):
        """Statistiques d'étirement (médiane, σ robuste MAD, p99.9) d'une
        image linéaire — fonction PURE : aucune mutation d'état (le
        sous-échantillonnage la garde rapide même en pleine résolution)."""
        mono = img.mean(axis=2) if img.ndim == 3 else img
        s = mono[::max(1, mono.shape[0] // 512), ::max(1, mono.shape[1] // 512)]
        med = float(np.median(s))
        sigma = max(float(np.median(np.abs(s - med))) * 1.4826, 1e-8)  # σ robuste (MAD)
        return med, sigma, float(np.percentile(s, 99.9))

    def _auto_params(self, img, live=True):
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

        med, sigma, p999 = self._calc_stats(img)

        # Lissage temporel des STATS (pas des paramètres) : les curseurs restent
        # réactifs, mais l'image ne « pompe » pas entre deux frames.
        if self._stats is None:
            self._stats = (med, sigma, p999)
        elif live:
            a = self._ema
            self._stats = tuple(v0 + a * (v1 - v0)
                                for v0, v1 in zip(self._stats, (med, sigma, p999)))
        med, sigma, p999 = self._stats

        lo = med - self.sigma_k * sigma                     # ombres : bruit coupé
        hi = max(p999, med + 10.0 * sigma, lo + 1e-8)        # hautes lumières réelles
        m = self._solve_m((med - lo) / (hi - lo), self.target)
        return lo, hi, m

    def notify_new_stack(self):
        """Signale qu'un NOUVEL empilement vient d'être produit (une frame de
        plus a été empilée) : le thread solveur relance la résolution. Le
        rythme des frames (≥ 1 s, souvent bien plus) EST le cooldown — aucun
        calcul entre deux frames, et le worker ne garde que le DERNIER job
        (aucune file d'attente). Appelé depuis l'UI, jamais bloquant."""
        with self._vl_lock:
            self._vl_force = True

    def vl_en_cours(self):
        """True si le thread solveur VeraLux a un calcul en marche (jalon 40 :
        l'UI affiche alors l'étape courante `vl_stage` + un curseur animé).
        Lecture thread-sûre (booléen écrit sous verrou par le worker)."""
        return self._vl_pending

    def _vl_params(self):
        """Clé de hachage des réglages de la chaîne PRÉ-ÉTIREMENT VeraLux —
        GraXpert live, débruitage live, netteté live (jalon 12), SCNR et
        démagenta (jalon 22), plus les paramètres d'étirement : bouger
        l'un d'eux relance la résolution."""
        return (self.vl_mode_res, round(self.vl_target_bg, 4),
                round(self.vl_log_d, 3), self.vl_profil,
                self.vl_graxpert, self.vl_graxpert_cmd,
                self.vl_denoise, self.vl_denoise_methode,
                round(self.vl_denoise_force, 2),
                self.vl_sharp, int(self.vl_sharp_iterations),
                self.vl_scnr, self.vl_demagenta, self.vl_scnr_doux,
                bool(self.vl_neutre_fond),             # v2.36.1 (option)
                bool(self.vl_chroma),                  # v2.37.0 (option)
                round(float(self.vl_chroma_force), 2),
                round(float(self.vl_chroma_rayon), 2))  # v2.37.3 (résolution)

    def _vl_worker(self):
        """Thread solveur : enchaîne — si activés — GraXpert live (jalon 4)
        PUIS le débruitage local (jalon 9 : algorithmes numpy/OpenCV, aucun
        subprocess) PUIS la netteté live (jalon 12 : Richardson-Lucy, numpy/
        OpenCV, aucun subprocess) PUIS l'étirement VeraLux, sur le DERNIER job
        demandé (les jobs intermédiaires — slider bougé, frame remplacée — sont
        simplement remplacés, jamais empilés). Écrit le résultat sous verrou.
        C'est le seul chemin qui applique la netteté en mode VeraLux : elle y
        est donc correctement APRÈS GraXpert/débruitage (gradient → débruitage
        → netteté → étirement) ; les modes STF/manuel passent par le solveur
        dédié `_sh_worker`."""
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
            scnr_actif = bool(coul[0]) if len(coul) > 0 else False
            sd_actif = bool(coul[1]) if len(coul) > 1 else False
            dm_actif = bool(coul[2]) if len(coul) > 2 else False
            # v2.37.0 : réduction du BRUIT CHROMATIQUE (10e élément du job —
            # déballage tolérant : les jobs antérieurs n'en ont pas → inactif).
            chroma_actif = bool(job[9]) if len(job) > 9 else False
            chroma_force = float(job[10]) if len(job) > 10 else 0.5
            # v2.37.3 : rayon du flou de chroma, déjà ramené à l'échelle de
            # l'image reçue par l'interface (déballage TOLÉRANT : les jobs
            # antérieurs n'en ont pas → rayon de référence pleine résolution).
            chroma_rayon = (float(job[11]) if len(job) > 11
                            else _couleurs.RAYON_CHROMA_DEFAUT)
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
            # v2.36.1 : neutralisation de la couleur du fond avant étirement
            # (9e élément du job — déballage tolérant : les jobs des bancs
            # antérieurs n'ont que 8 éléments → option considérée décochée).
            nf = bool(job[8]) if len(job) > 8 else False
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
                for role, couche in canaux.items():
                    c = np.asarray(couche, dtype=np.float32)
                    if gx_actif:
                        if float(np.max(np.abs(c))) < 1e-9:
                            # Équivalent par couche du garde-fou jalon 23b :
                            # une couche sans données n'est pas envoyée à
                            # l'outil (comportement imprévisible).
                            msgs.append(f"GraXpert live ({role}) : couche vide"
                                        " — ignorée")
                        else:
                            cle = ("gx", role, _gx_live.cle_image(c), gx_cmd)
                            cache = self._gx_couches.get(role)
                            if cache is not None and cache[0] == cle:
                                c = cache[1]     # autre rôle seulement : cette
                            else:                # couche n'est PAS relancée
                                c2, err = _gx_live.appliquer(c, gx_cmd)
                                if err:
                                    msgs.append(f"GraXpert live ({role}) : "
                                                f"{err}")
                                else:
                                    c = c2
                                    self._gx_couches[role] = (cle, c2)
                    if dn_actif:
                        cle = ("dn", role, _gx_live.cle_image(c), dn_methode,
                               round(dn_force, 2))
                        cache = self._dn_couches.get(role)
                        if cache is not None and cache[0] == cle:
                            c = cache[1]
                        else:
                            c2, err = _denoise.denoiser(c, dn_methode, dn_force)
                            if err:
                                msgs.append(f"Débruitage live ({role}) : {err}")
                            else:
                                c = c2
                                self._dn_couches[role] = (cle, c2)
                    traites[role] = c
                try:
                    # composer() NE porte AUCUNE correction de couleur : le
                    # composite re-fait depuis les couches traitées est BRUT,
                    # les corrections s'appliquent juste après, dans l'ordre
                    # validé (débruitage → CORRECTIONS → netteté/étirement).
                    comp = _composition.composer(traites, nom_compo,
                                                 mode_l=mode_l,
                                                 normalisation_commune=
                                                 norm_commune)
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
            # Jalon 22/23 : chaîne couleur (opt-in) — APRÈS la netteté,
            # JUSTE AVANT l'étirement (décision d'Alain : sur le composite
            # COULEUR ; no-op si l'image est monochrome). Ordre :
            # SCNR classique → SCNR doux (bruit seul) → démagenta.
            if scnr_actif:
                img_net = _couleurs.scnr(img_net)
            if sd_actif:
                img_net = _couleurs.scnr_doux(img_net)
            if dm_actif:
                img_net = _couleurs.demagenta(img_net)
            # v2.36.1 : NEUTRALISATION DE LA COULEUR DU FOND, juste AVANT
            # l'étirement (9e élément du job, déballage tolérant). L'étirement
            # VeraLux soustrait une ancre puis étire en log : quelques pour cent
            # d'écart de ciel y deviennent un facteur ~2,4 de couleur de fond
            # (mesuré : fond étiré R/G 0,363 · B/G 1,611 → R/G 1,020 ·
            # B/G 0,996 après correction). Les gains appliqués sont publiés
            # (`vl_neutre_gains`) pour que l'interface puisse les ANNONCER.
            gains = None
            if nf:
                gains = _couleurs.gains_fond(img_net)
                if gains is not None and not np.allclose(gains, 1.0,
                                                         atol=1e-4):
                    img_net = _couleurs.neutraliser_fond(img_net)
            with self._vl_lock:
                # Publié pour l'UI (annonce honnête de ce qui est appliqué) ;
                # None si l'option est décochée ou si rien n'a été corrigé.
                self.vl_neutre_gains = gains if (nf and gains is not None
                                                 and not np.allclose(
                                                     gains, 1.0, atol=1e-4)
                                                 ) else None
            # v2.37.0 : RÉDUCTION DU BRUIT CHROMATIQUE, APRÈS la neutralisation
            # (elle est un gain par canal) et juste AVANT l'étirement. Lisse la
            # chroma (YCrCb) : la luminance reste intacte, donc ni le niveau ni
            # le contraste du fond ne bougent — seulement le GRAIN COLORÉ que
            # les gains multiplicatifs (SPCC en tête : K_B/K_G = 1,32) ont
            # amplifié. No-op si l'option est décochée ou si l'image est mono.
            if chroma_actif:
                self.vl_stage = "chroma"        # jalon 40 : étape courante
                img_net = _couleurs.reduire_bruit_chroma(
                    img_net, force=chroma_force, rayon=chroma_rayon)
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
            with self._vl_lock:
                self._vl_pending = False
                self._vl_result = (key, result)
                self.vl_error = prefixe   # "" si tout s'est bien passé
                self.vl_log_d_resolu = log_d_util
                self.vl_diagnostics = diag
                self.vl_new = True
                self.vl_stage = ""        # calcul terminé — jalon 40

    def sh_en_cours(self):
        """True si le solveur de netteté DÉDIÉ (modes STF/manuel, jalon 12)
        a un calcul en marche — jalon 41 : le cadre « État des calculs »
        est visible dans les DEUX modes, l'UI affiche ⏳ + curseur pendant
        la déconvolution STF/manuel aussi."""
        return self._sh_pending

    def _process_veralux(self, img, live=True):
        """Chemin VeraLux : rend le dernier résultat terminé (ou le STF en
        image d'attente) et soumet un calcul si l'image ou les réglages ont
        changé. Jamais bloquant : aucun calcul ici, seulement une copie."""
        key = self._vl_params()
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
            coul = (self.vl_scnr, self.vl_scnr_doux,
                    self.vl_demagenta)     # jalon 22/23 : chaîne couleur
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
                                    chroma, chroma_force, chroma_rayon)
                    self._vl_wake.set()
            self._vl_src, self._vl_key = img, key
        with self._vl_lock:
            res = self._vl_result \
                if (self._vl_result is not None
                    and self._vl_result[0] == key) else None
        if res is not None:
            return res[1]                 # image étirée [0..1], mêmes dimensions
        # Image d'attente : le STF auto (SANS toucher aux réglages utilisateur
        # black/white/gamma — on ne fait que lire les stats lissées).
        # NB : elle n'est pas nette — en mode VeraLux la netteté fait partie de
        # la chaîne du solveur (après GraXpert/débruitage éventuels), c'est un
        # état transitoire de quelques dixièmes de seconde.
        lo, hi, m = self._auto_params(img, live=live)
        return self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)

    # ------------------------------------------- netteté live (jalon 12)
    def _sh_key(self):
        """Clé des réglages de la netteté : itérations + FWHM de la PSF
        utilisée (celle du seeing mesuré au jalon 10, None si l'app doit
        mesurer elle-même) — une nouvelle mesure de seeing relance donc la
        netteté, comme un changement d'itérations."""
        v = self.vl_seeing if isinstance(self.vl_seeing, dict) else {}
        f = v.get("fwhm")
        return (int(self.vl_sharp_iterations),
                None if f is None else round(float(f), 2))

    def _sh_worker(self):
        """Thread solveur DÉDIÉ à la netteté des modes STF/manuel.

        Le mode VeraLux l'applique dans son propre solveur (après GraXpert et
        débruitage, cf. `_vl_worker`) ; les deux autres moteurs d'étirement
        n'ont aucune chaîne pré-étirement, d'où ce second thread. Dernier job
        gagnant : un empilement plus récent remplace celui en attente, le
        travail n'est jamais fait deux fois pour la même image (le résultat,
        refus compris, est MÉMORISÉ — sinon chaque tick d'UI resoumettrait un
        job refusé, 30 fois par seconde). Résultat écrit sous verrou, l'UI
        n'est jamais bloquée : en attendant, elle affiche l'image NON nette."""
        while True:
            self._sh_wake.wait()
            self._sh_wake.clear()
            with self._sh_lock:
                job = self._sh_job
                self._sh_job = None
            if job is None:
                # Aucun job : ne jamais laisser `_sh_pending` à True (un état
                # « calcul en cours SANS job » empêcherait toute nouvelle
                # soumission). Job et drapeau sont écrits ensemble sous
                # verrou : cet état est incohérent, on le répare.
                with self._sh_lock:
                    self._sh_pending = False
                continue
            img, key, source = job
            try:
                nette, err = _sharpness.deconvoluer(
                    img, iterations=key[0], mesure=self.vl_seeing)
            except Exception as exc:       # jamais de plantage muet
                nette, err = img, str(exc)
            with self._sh_lock:
                self._sh_pending = False
                # Le refus est mémorisé LUI AUSSI (image d'entrée inchangée) :
                # c'est ce qui évite une boucle de resoumissions.
                self._sh_result = (key, source, nette)
            self.sh_msg, self.sh_new = err, True

    def _process_nettete(self, img):
        """Netteté des modes STF/manuel (le mode VeraLux est traité dans
        `_vl_worker`) : rend l'image nette si un résultat correspond EXACTEMENT
        à l'image courante, sinon l'image d'attente (inchangée) et soumet le
        calcul au thread dédié.

        L'IDENTITÉ de l'objet image est la clé d'image : l'aperçu d'un
        empilement donné est un objet stable (recréé à chaque nouvel
        empilement), retouché à chaque tick d'UI — l'empreinter par son contenu
        à chaque tick coûterait bien plus cher que la netteté elle-même
        (sha1 du buffer). Le résultat mémorise l'objet qu'il a déconvolué, ce
        qui garantit qu'on n'affiche JAMAIS l'image nette d'un autre
        empilement (même objet, même clé de réglages → sinon image d'attente).
        Jamais bloquant : aucun calcul ici."""
        if img is None:
            return img
        key = self._sh_key()
        with self._sh_lock:
            soumis = self._sh_soumis
            if (not self._sh_pending
                    and (soumis is None or soumis[0] is not img
                         or soumis[1] != key)):
                self._sh_pending = True
                self._sh_soumis = (img, key)
                # copie défensive : l'image appartient à l'UI et peut être
                # remplacée pendant le calcul
                self._sh_job = (np.asarray(img, dtype=np.float32).copy(),
                                key, img)
                self._sh_wake.set()
            res = self._sh_result
        if res is not None and res[0] == key and res[1] is img:
            return res[2]
        return img

    @staticmethod
    def _gamma_saturation(x, rgb, gamma, saturation):
        """Gamma et saturation COMMUNS — appliqués après l'étirement, quel que
        soit le mode (STF, manuel, VeraLux). Factorisés pour que le rendu
        « tel que vu » de la sauvegarde (jalon 5) soit strictement identique
        à l'affichage. (Simple relais de `_finition` depuis le jalon 75 : la
        signature d'origine est conservée pour les appelants et les bancs.)"""
        return DisplayProcessor._finition(x, rgb, gamma, saturation, None)

    @staticmethod
    def _finition(x, rgb, gamma, saturation, sat_canaux=None):
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

    def _veralux_actif(self):
        """True si le chemin VeraLux est RÉELLEMENT utilisé (moteur choisi ET
        disponible) — c'est ce qui décide où la netteté est appliquée."""
        return self.stretch == "veralux" and _veralux.moteur_disponible()

    def process(self, img, live=True):
        img = img.astype(np.float32, copy=False)
        # Netteté live (jalon 12) : AVANT l'étirement, quel que soit le
        # moteur. En mode VeraLux elle est déjà appliquée par le solveur
        # VeraLux (où elle suit correctement GraXpert/débruitage) : ne pas la
        # refaire ici — d'où le test sur le moteur RÉELLEMENT utilisé.
        if self.vl_sharp and not self._veralux_actif():
            img = self._process_nettete(img)
        # Jalon 22/23 : chaîne couleur (opt-in) — AVANT l'étirement, en
        # STF/manuel ; en VeraLux elle fait partie de la chaîne du solveur
        # (appliquée dans _vl_worker) : ne pas la refaire ici.
        if self.vl_scnr and not self._veralux_actif():
            img = _couleurs.scnr(img)
        if self.vl_scnr_doux and not self._veralux_actif():
            img = _couleurs.scnr_doux(img)
        if self.vl_demagenta and not self._veralux_actif():
            img = _couleurs.demagenta(img)
        if self._veralux_actif():
            x = self._process_veralux(img, live=live)
        else:
            if self.stretch == "veralux" and not self.vl_error:
                self.vl_error = ("VeraLux : moteur tiers veralux_core_headless.py "
                                 "introuvable — affichage STF en attendant.")
                self.vl_new = True
            if self.auto:
                lo, hi, m = self._auto_params(img, live=live)
                self.last_lo, self.last_hi = lo, hi
                # Jalon 75 : le médian résolu est conservé pour que la bande
                # « brut » de l'histogramme puisse placer son repère de médian
                # (lo + m·(hi − lo)) — sinon l'utilisateur verrait deux repères
                # sur trois et croirait à un oubli.
                self.last_m = m
                x = self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)
            else:
                lo, hi = self.black, self.white
                if hi - lo < 1e-6:
                    hi = lo + 1e-6
                x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        # Jalon 75 : l'image de SORTIE DU MOTEUR est mémorisée AVANT l'étage
        # de niveaux — c'est elle qu'affiche la bande basse de l'histogramme,
        # pour que les barres découpent bien la donnée qu'elles reçoivent (et
        # que la courbe ne bouge pas sous les doigts). Relue par l'UI juste
        # après cet appel, dans le MÊME thread ; jamais modifiée ici.
        self.dernier_brut_niveaux = x
        if niveaux_actifs(self.bar_noir, self.bar_median, self.bar_blanc):
            x = niveaux(x, self.bar_noir, self.bar_median, self.bar_blanc)
        x = self._finition(x, img.ndim == 3, self.gamma, self.saturation,
                           self.sat_canaux)
        return (x * 255).astype(np.uint8)

    # ------------------------------------------------------------- jalon 5
    def rendu_pleine_resolution(self, img, reglages=None):
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
            params = dict(profil=r("vl_profil", self.vl_profil),
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
            # Jalon 75 : étirement GELÉ (⏹) → le fichier doit reproduire
            # l'écran, donc utiliser les MÊMES stats gelées que l'affichage
            # (dict capturé côté UI) ; sinon « tel que vu » serait calculé sur
            # les stats du moment et ne correspondrait plus à ce qu'on voit.
            gelees = r("stats_gelees",
                       self._stats if self.fige else None)
            if gelees is not None:
                med, sigma, p999 = gelees
            else:
                med, sigma, p999 = self._calc_stats(img)
            lo = med - r("sigma_k", self.sigma_k) * sigma
            hi = max(p999, med + 10.0 * sigma, lo + 1e-8)
            m = self._solve_m((med - lo) / (hi - lo), r("target", self.target))
            x = self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)
        else:
            lo, hi = r("black", self.black), r("white", self.white)
            if hi - lo < 1e-6:
                hi = lo + 1e-6
            x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        # Jalon 75 : étage de NIVEAUX (les 3 barres de l'histogramme) puis
        # finition (gamma, saturation globale, saturation par couleur) —
        # exactement la même chaîne que `process()`, au même endroit, pour que
        # le fichier « tel que vu » soit l'écran au pixel près.
        noir = float(r("bar_noir", self.bar_noir))
        median = float(r("bar_median", self.bar_median))
        blanc = float(r("bar_blanc", self.bar_blanc))
        if niveaux_actifs(noir, median, blanc):
            x = niveaux(x, noir, median, blanc)
        return self._finition(x, img.ndim == 3,
                              r("gamma", self.gamma),
                              r("saturation", self.saturation),
                              r("sat_canaux", self.sat_canaux))
