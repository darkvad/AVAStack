# -*- coding: utf-8 -*-
"""Retraits de couleur (jalon 22) : SCNR (vert) et démagenta.

Décision d'Alain (19/09/2026) : appliqués APRÈS la composition — sur
l'image COULEUR du composite (HOO, SHO, RGB…) — et JUSTE AVANT l'étirement,
en LIVE et en TRAITEMENT EXTERNE, chacun derrière sa case à cocher. Sur un
composite MONOCHROME (source Mono) il n'y a rien à neutraliser : no-op
(« pour retirer du vert, il faut de la couleur »).

SCNR « moyenne neutre » (le standard PixInsight / Siril) :
    G = min(G, (R + B) / 2)
Le vert excédentaire (bruit vert du capteur couleur, pollution OIII dans
un canal…) est ramené à la moyenne des deux autres canaux ; les pixels
équilibrés (étoiles blanches, fond neutre) restent inchangés. Opération
linéaire pixel à pixel : appliquée ici sur l'image LINÉAIRE, avant
l'étirement.

Démagenta (recette d'Alain) : négatif → SCNR → retour au positif.
Le magenta (excès de rouge + bleu — bruit de fond des capteurs CMOS, fonds
des poses longues) devient un excès de VERT dans le négatif ; le SCNR le
ramène à la moyenne des deux autres canaux, et le retour au positif
restitue une image dont le magenta a été neutralisé.
"""
import numpy as np
import cv2

from . import denoise as _denoise


def scnr(img):
    """Retrait du vert (SCNR « moyenne neutre ») : G = min(G, (R+B)/2).

    img : (H, W, 3) couleur — un composite (H, W) monochrome est renvoyé
    inchangé (copie). → copie float32 de mêmes dimensions ; l'entrée n'est
    JAMAIS modifiée ; aucune exception (numpy seul)."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return a.copy()           # mono / forme inattendue : rien à faire
    out = a.copy()
    plafond = 0.5 * (out[..., 0] + out[..., 2])
    out[..., 1] = np.minimum(out[..., 1], plafond)
    return out


def demagenta(img):
    """Suppression du magenta : négatif → SCNR → retour au positif.

    Le magenta (R et B > G) devient un excès de vert dans le négatif, que
    le SCNR ramène à la moyenne ; le retour au positif neutralise le
    magenta. → copie float32, mono inchangé, entrée jamais modifiée."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return a.copy()
    return (1.0 - scnr(1.0 - a)).astype(np.float32)


def gains_fond(img, garde=0.10):
    """Gains par canal (R, G, B) qui NEUTRALISENT LA COULEUR DU FOND d'une image
    couleur — ou None si l'image ne s'y prête pas (mono, canal vide).

    Estimation : la MÉDIANE DE LA MOITIÉ LA PLUS SOMBRE de l'image (sélection par
    luminance), canal par canal. Ce choix est volontaire : la médiane GLOBALE est
    déplacée par un objet qui remplirait le champ (une grande nébuleuse), alors
    que la moitié sombre reste du CIEL dans tous les cas ; et un percentile TRÈS
    bas (ce qu'utilise `composition.appliquer_equilibrage`) décrit les coins les
    plus sombres, pas le ciel moyen — c'est justement cet écart qui laissait
    passer le fond bleu que VeraLux amplifiait (cf. `neutraliser_fond`).

    `garde` borne les gains à ±garde (10 % par défaut). POURQUOI si serré : sur
    un cadrage où un OBJET étendu domine (une nébuleuse qui remplit le champ),
    la « moitié sombre » n'est plus du ciel mais l'objet lui-même — mesuré au
    banc : les gains partent alors à la borne (0,82 / 1,18 avec une garde de
    18 %), c'est-à-dire une désaturation visible de l'objet. Aucun estimateur bon
    marché ne sait distinguer un ciel d'un objet étendu (c'est le travail de
    GraXpert) : on borne donc l'ampleur de la correction, on ANNONCE les gains
    appliqués à l'écran, et la case se décoche. Le cas visé (le résidu de couleur
    du ciel qui bleuit tout après l'étirement) demande 2 %. Une palette
    volontairement colorée (SHO, fond vert…) garde donc l'intention de
    l'utilisateur."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return None
    lum = a.mean(axis=2)
    masque = lum <= float(np.percentile(lum, 50))
    if not bool(masque.any()):
        return None
    med = [float(np.median(a[..., c][masque])) for c in range(3)]
    if min(med) <= 1e-9:                  # canal vide : aucun gain raisonnable
        return None
    return tuple(float(v) for v in np.clip(np.array([med[1] / m for m in med],
                                                    dtype=np.float32),
                                           1.0 - garde, 1.0 + garde))


def neutraliser_fond(img, force=1.0, garde=0.10):
    """Neutralise la COULEUR DU FOND (gains par canal) — « background
    neutralization », à appliquer JUSTE AVANT l'étirement.

    POURQUOI (constat d'Alain, 25/09/2026 : « vachement bleu » en PNG alors que
    le FITS était juste — et le fond restait bleu à l'écran) : l'étirement
    VeraLux soustrait une ANCRE (un scalaire lu dans l'histogramme de luminance)
    puis étire logarithmiquement. Pour le fond, il ne reste donc que le RÉSIDU
    (niveau du canal − ancre) : quelques pour cent d'écart de ciel deviennent
    plusieurs centaines de pour cent d'écart de couleur. MESURÉ sur son
    empilement M31 : ciels R 0,0321 / G 0,0326 / B 0,0332 (3,6 % — ciel bleu
    réel), ancre 0,0313 → résidus +0,00080 / +0,00137 / +0,00196 (rapports
    1 : 1,70 : 2,44) → fond étiré à R/G 0,363 · B/G 1,611, franchement bleu.
    Deux gains de 2 % appliqués AVANT l'étirement le ramènent à R/G 1,020 ·
    B/G 0,996 (mesuré sur le même fichier).

    À ne pas confondre avec `composition.appliquer_equilibrage` (équilibrage des
    canaux) : celui-ci neutralise le fond estimé sur un PERCENTILE BAS — les
    coins les plus sombres, déjà neutres (0,1 % mesuré) — alors que l'ancre de
    VeraLux vit dans l'histogramme globbal. Les deux se complètent.

    force : 0..1 — atténue la correction (`gains ** force`), comme l'équilibrage.
    → copie float32 ; image mono ou non couleur renvoyée inchangée ; jamais
    d'exception (numpy seul)."""
    a = np.asarray(img, dtype=np.float32)
    g = gains_fond(a, garde)
    if g is None:
        return a.copy()
    gg = np.array(g, dtype=np.float32)
    if force < 1.0:
        gg = gg ** float(force)
    if bool(np.allclose(gg, 1.0, atol=1e-4)):
        return a.copy()
    return (a * gg.reshape(1, 1, 3)).astype(np.float32)


# --- Réduction du bruit chromatique : échelles de référence ------------------
# Rayon de flou de RÉFÉRENCE, en pixels PLEINE RÉSOLUTION (la valeur validée par
# Alain sur ses empilements) ; PLANCHER_CHROMA borne l'échelle de normalisation
# de la chroma (fraction de la luminance médiane de l'image).
RAYON_CHROMA_DEFAUT = 3.0
RAYON_CHROMA_MIN = 0.2
PLANCHER_CHROMA = 0.25
# v2.37.5 : SEUIL de STRUCTURE du flou de chroma, en σ du bruit de luminance
# (σ estimé sur place par MAD de l'écart à son propre flou gaussien), et FORME
# de la transition. Mesuré au banc jalon 67 : sur le FOND (écart ≈ 1 σ) le poids
# vaut 1/(1 + 1/3⁶) = 0,999 → le grain coloré tombe toujours (mesuré ×0,16 à
# ×0,19 sur son empilement, contre ×0,16 pour la v2.37.4) ; sur une ÉTOILE le
# poids tombe à 0,5 dès 3 σ, 0,045 à 5 σ et 0,0007 à 10 σ → plus d'anneau
# (mesuré 1,96 sans chroma → 4,63 v2.37.4 → 2,00 v2.37.5).
SEUIL_STRUCTURE_CHROMA = 3.0
EXPOSANT_STRUCTURE_CHROMA = 6.0


def rayon_chroma_apercu(scale, rayon=RAYON_CHROMA_DEFAUT):
    """Rayon de flou ÉQUIVALENT pour une image RÉDUITE (aperçu) de facteur
    `scale` (< 1) — le rayon de référence reste exprimé, lui, en pixels PLEINE
    RÉSOLUTION.

    POURQUOI (constat réel d'Alain, 26/09/2026, v2.37.3) : le solveur de
    l'aperçu reçoit une image RÉDUITE (facteur 1600/largeur — 0,417 sur son
    image de 3838 px) alors que le rayon restait fixé à 3 px. Or les ÉTOILES
    rétrécissent avec l'image : le même flou de 3 px étale donc leur couleur
    1/scale = 2,4 fois plus loin PAR RAPPORT À LEUR TAILLE à l'écran que dans
    le fichier pleine résolution. Le rayon suit désormais la résolution :
    l'aperçu montre ce que le fichier contient (règle du projet : « le fichier
    correspond à l'écran »).

    scale : facteur de réduction ayant servi à construire l'aperçu (1.0 =
            pleine résolution → rayon inchangé) ;
    → rayon effectif, en pixels de l'image reçue, jamais sous RAYON_CHROMA_MIN
    (en dessous il n'y a plus rien à lisser : le grain vit à l'échelle du
    pixel). Aucune exception : `scale` illisible ou absurde → rayon de
    référence (jamais moins de travail que demandé).
    """
    try:
        s = float(scale)
    except (TypeError, ValueError):
        return float(rayon)
    if not np.isfinite(s) or s <= 0.0:
        return float(rayon)
    return max(RAYON_CHROMA_MIN, float(rayon) * min(1.0, s))


def _poids_structure(lum, flou, ecart_min):
    """Poids 1.0 sur le FOND (grain seul) → 0.0 sur une STRUCTURE (étoile, bord).

    POURQUOI (v2.37.5, constat d'Alain du 26/09/2026 : « les étoiles moyennes
    rouges sont bien plus rouges et ont presque un halo » DANS LES FICHIERS, alors
    que l'affichage est correct) : le flou de chroma est appliqué PLEINE RÉSOLUTION
    au fichier mais à l'APERÇU 1600 px à l'écran. Sur le fichier, le flou du
    RAPPORT `cn = (Cr−0,5)/den` dépose la couleur du CŒUR de l'étoile dans ses
    ailes (`den = min(y, flou(y))` y est faible) et y fabrique un ANNEAU coloré,
    mesuré R/G 1,80 sans chroma → 2,33 / 2,93 / 3,89 aux forces 0,25 / 0,50 / 0,85
    (sa valeur). À l'écran l'étoile fait 1 px : le flou écrase l'anneau, donc il
    ne le voyait que dans les fichiers.

    Le remède est un poids qui ne laisse la correction travailler QUE là où la
    luminance ressemble à son voisinage lissé — c'est-à-dire sur le FOND (grain
    pixel à pixel) et sur les zones LISSES (nébuleuses) — et pas sur une
    structure : `lum` est la luminance Y de l'image, `flou` SON propre flou
    gaussien (déjà calculé par l'appelant, aucun flou supplémentaire).

    σ du bruit : MAD de l'écart (insensible aux étoiles et à la structure, qui
    pèsent peu dans la médiane des |écarts|) × 1,4826 → σ d'une loi normale ;
    `ecart_min` est un plancher d'échelle (fraction de la luminance médiane)
    pour les images SANS bruit, où le MAD serait nul alors que la structure,
    elle, existe toujours. L'échantillonnage (1 pixel sur N) ne change pas le
    MAD et évite un tri de plusieurs millions de valeurs à chaque appel.

    poids = 1 / (1 + (|écart| / (SEUIL·σ)) ** EXPOSANT) — un seuil DOUX mais
    FRANCHI : à 1 σ (le grain du fond) le poids vaut 0,999 (le grain coloré tombe
    toujours), à 3 σ il est de 0,5, à 5 σ de 0,045, à 10 σ de 0,0007 (plus rien
    n'est déposé dans les ailes). L'exposant a été MESURÉ : à 4 la transition
    laissait encore l'anneau à +6 % de la référence sur la scène témoin, à 6 il
    revient au niveau sans chroma — et le grain du fond est MIEUX préservé
    (1 σ : 0,999 contre 0,988).
    Si l'échelle est inexploitable (σ non fini, ≤ 0), renvoie None : l'appelant
    retombe alors sur 1.0, c'est-à-dire le comportement v2.37.4 à l'identique.
    """
    ecart = np.asarray(lum, dtype=np.float32) - np.asarray(flou, dtype=np.float32)
    pas = max(1, int(ecart.size) // 400000)
    sig = float(np.median(np.abs(ecart.ravel()[::pas]))) * 1.4826
    sig = max(sig, float(ecart_min))
    if not np.isfinite(sig) or sig <= 0.0:
        return None
    r = np.abs(ecart) / np.float32(SEUIL_STRUCTURE_CHROMA * sig)
    return (np.float32(1.0)
            / (np.float32(1.0) + np.power(r, np.float32(
                EXPOSANT_STRUCTURE_CHROMA)))).astype(np.float32)


def reduire_bruit_chroma(img, force=0.5, rayon=RAYON_CHROMA_DEFAUT):
    """Réduit le BRUIT CHROMATIQUE d'une image couleur (v2.37.0) — le
    « chroma noise reduction », équivalent d'un SCNR généralisé.

    DEMANDE D'ALAIN (25/09/2026 : « oui pour la réduction de bruit
    chromatique, et case décochée par défaut », après avoir constaté qu'il
    restait du grain coloré malgré le fond neutralisé).

    POURQUOI une CHROMA et pas un canal : une correction MULTIPLICATIVE (SPCC,
    équilibrage des canaux, recalage colorimétrique) amplifie le bruit du canal
    qu'elle MONTE. MESURÉ sur son empilement M31 (v2.36.1, 115 frames) : grain
    R/G 0,902 (équilibré) mais B/G 1,174 — et les comptes tombent exactement :
    (σ_B·K_B)/(σ_G·K_G) = 0,891 × (1,0000/0,7587) = 1,174. La SPCC applique
    K_B/K_G = 1,32 : son gain de bleu amplifie le bruit bleu de 32 %. Retirer du
    bleu déréglerait la calibration ; lisser la COULEUR sans toucher la
    LUMINANCE retire le grain coloré sans toucher ni au niveau ni au contraste
    (c'est le seul levier direct : ni l'équilibrage, ni le SCNR vert ne
    corrigent un excès de grain BLEU).

    CORRECTIF v2.37.3 (constat d'Alain, 26/09/2026 : « les étoiles brillantes
    rouges et bleues ont un halo gênant », VISIBLE AUSSI APRÈS BlurXTerminator) :
    la chroma était jusqu'ici lissée comme un ÉCART ABSOLU (Cr/Cb tels quels).
    Or un écart de chroma ne dépend PAS de la luminosité du pixel : autour d'une
    étoile, le flou mélangeait la couleur du CŒUR avec celle du CIEL voisin et
    déposait ce mélange sur les AILES faibles, où un minuscule écart devient une
    énorme couleur. MESURÉ sur son empilement M31 (anneau r = 3..9 px, en
    multiples du niveau de ciel local, fond neutralisé) :
      - étoile la plus brillante (rouge) : R 41,3 → 34,9 (−16 %) et B 19,9 →
        23,6 (+19 %) — le halo perdait la couleur de l'étoile et prenait celle
        du fond (R/B 2,08 → 1,47) ;
      - étoile bleue : R 3,53 → 1,74 (−51 %) et B 2,72 → 3,92 (+44 %) — un HALO
        BLEU apparaissait là où il n'y en avait aucun (R/B 1,30 → 0,44).
    C'est bien le FLOU qui est en cause, pas la conversion : à force ≈ 0, la même
    conversion YCrCb→RVB rend l'image au bit près (vérifié sur son fichier).
    À cela s'ajoute que BXT tourne AVANT cette case dans la chaîne externe : le
    halo est donc créé APRÈS le « halo killer », qui ne peut rien y faire.

    CORRECTIF v2.37.5 (constat d'Alain, 26/09/2026 : « les étoiles moyennes rouges
    sont bien plus rouges et ont presque un halo … alors que l'affichage est
    correct ») : la v2.37.3 avait corrigé le halo des étoiles BRILLANTES ; il
    restait, dans les FICHIERS seulement, un ANNEAU de couleur autour de TOUTES
    les étoiles (même blanches et bleues). Le flou du RAPPORT `cn = (Cr−0,5)/den`
    dépose la couleur du CŒUR dans les ailes, où `den = min(y, flou(y))` est
    faible : un minuscule dépôt absolu devient une énorme couleur après
    l'étirement. MESURÉ sur son empilement (R/G de l'anneau 2-3 px d'aperçu, × le
    R/G du fond) : 1,80 sans chroma → 2,33 à 0,25 → 2,93 à 0,50 → 3,89 à 0,85
    (sa valeur) ; le rayon l'élargit encore. À l'écran, l'étoile fait 1 px et le
    flou écrase l'anneau : c'est POURQUOI il ne le voyait que dans les fichiers
    (l'écran étire l'APERÇU 1600 px, le fichier la PLEINE résolution).
    Le remède est le POIDS DE STRUCTURE `_poids_structure` : la correction est
    multipliée par 1 / (1 + (|Y − flou(Y)| / (SEUIL·σ)) ** EXPOSANT), qui vaut
    ~1 sur le fond (grain seul, écart ≈ 1 σ) et ~0 sur une structure (étoile,
    bord d'objet) — on garde donc tout le bénéfice sur le grain coloré du fond
    sans jamais déposer de couleur dans les ailes d'une étoile.

    Calcul (v2.37.3, poids v2.37.5) — on lisse la chroma NORMALISÉE PAR LA
    LUMINOSITÉ, c'est-à-dire le RAPPORT de couleur, puis on le re-multiplie par
    l'échelle locale `den` (minimum entre la luminance du pixel et sa version
    lissée, plancher PLANCHER_CHROMA × luminance médiane) :
      cn = (chroma − 0,5) / den ; lisse = flou gaussien de rayon `rayon` sur cn ;
      poids = 1 / (1 + (|Y − flou(Y)| / (SEUIL·σ)) ** EXPOSANT) ;
      chroma' = 0,5 + den · (cn + poids · force · (lisse − cn)).
    Sur le FOND, `den` est la version lissée (quasi constante) : la part demandée
    du grain coloré disparaît — mesuré ×0,169 à force 0,847, contre ×0,155 pour
    l'ancienne formulation. Près d'une ÉTOILE, `den` redevient la luminance du
    pixel (la plus faible) : l'amplitude de couleur reste celle de la lumière
    réellement présente — mesuré sur son étoile bleue, R/B 1,26 (référence 1,30)
    au lieu de 0,44. Y (luminance) n'est JAMAIS réécrit (seuls Cr et Cb le
    sont) — mesuré au banc : écart < 2e-6 sur le canal Y de OpenCV sur le fond,
    et < 1,4e-05 en tout, cette petite queue venant des pixels du bord haut de
    l'échelle où la reconstruction YCrCb→RVB sature. Le grain vit à l'échelle du
    PIXEL, la couleur des objets (nébuleuses) s'étale sur beaucoup plus que
    `rayon` : la couleur de l'objet reste préservée à mieux de 2 %. Sur une image
    MONOCHROME, il n'y a pas de chroma : no-op.

    force : 0..1 — part du bruit chromatique retirée (0 = no-op, 1 = chroma
            entièrement lissée) ;
    rayon : écart-type du flou, EN PIXELS DE L'IMAGE REÇUE. Il vaut
            RAYON_CHROMA_DEFAUT (3 px en PLEINE RÉSOLUTION) pour un fichier, et
            `rayon_chroma_apercu(scale)` pour un aperçu réduit — sinon le halo
            est 1/scale fois trop large à l'écran par rapport aux fichiers.
    → copie float32, entrée JAMAIS modifiée, aucune exception (numpy/OpenCV,
    mêmes garanties que les autres primitives de ce module)."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3 or float(force) <= 0.0 \
            or float(rayon) <= 0.0:
        return a.copy()               # mono, forme inattendue ou force nulle
    f = np.float32(min(1.0, max(0.0, float(force))))
    ycc = cv2.cvtColor(a, cv2.COLOR_RGB2YCrCb)
    y = ycc[..., 0]
    niveau = float(np.median(y))
    if not np.isfinite(niveau) or niveau <= 1e-9:
        return a.copy()               # image noire/vide : aucune échelle locale
    # ÉCHELLE LOCALE de la chroma (v2.37.3) : le MINIMUM entre la luminance DU
    # PIXEL et sa version LISSÉE. Le pixel borne la correction près d'une étoile
    # (l'amplitude de couleur reste celle de la lumière réellement présente →
    # plus de halo) ; la version lissée donne une échelle quasi constante sur le
    # fond (le bruit de luminance ne se re-dépose pas dans la couleur → le grain
    # coloré tombe toujours d'un facteur (1 − force)). Le plancher évite la
    # division par zéro dans les pixels noirs ou négatifs.
    flou_y = cv2.GaussianBlur(y, (0, 0), sigmaX=float(rayon))
    den = np.maximum(np.minimum(y, flou_y),
                     np.float32(max(PLANCHER_CHROMA * niveau, 1e-7)))
    # v2.37.5 : poids de STRUCTURE — 1 sur le fond, ~0 sur une étoile ou un bord.
    # Sans lui, le flou du RAPPORT dépose la couleur du CŒUR de l'étoile dans ses
    # ailes et y fabrique l'ANNEAU visible dans les fichiers (cf. _poids_structure).
    poids = _poids_structure(y, flou_y, 1e-4 * niveau)
    for i in (1, 2):                  # Cr puis Cb — jamais Y (canal 0)
        cn = (ycc[..., i] - 0.5) / den          # RAPPORT de couleur local
        lisse = cv2.GaussianBlur(cn, (0, 0), sigmaX=float(rayon))
        corr = np.float32(f) * (lisse - cn)
        if poids is not None:                   # None = échelle inexploitable :
            corr = corr * poids                 # comportement v2.37.4 exact
        ycc[..., i] = 0.5 + den * (cn + corr)
    out = cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB)
    # Le flou d'un plan de chroma reste dans l'intervalle de ses voisins, mais
    # la reconstruction peut passer très légèrement sous zéro près du noir :
    # on borne (un pixel négatif n'a pas de sens pour l'étirement en log).
    return np.maximum(out, np.float32(0.0)).astype(np.float32)


def canal_mort(img):
    """→ nom du canal entièrement vide ('R', 'G' ou 'B') d'une image
    couleur, ou None si les trois canaux portent des données (ou si img
    est monochrome).

    Un canal MORT (SHO sans S → R = 0, aucun dossier S2) rend le
    comportement des outils externes (GraXpert…) imprévisible — sortie
    dégénérée, image noire en visu. Les appelants doivent refuser de
    lancer l'outil et afficher un message clair."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return None
    for i, nom in enumerate("RGB"):
        if float(a[..., i].std()) < 1e-8:
            return nom
    return None


def scnr_doux(img, k=3.0):
    """SCNR doux borné par le bruit (jalon 23) : ne retire que l'excès de
    vert DE L'ORDRE DU BRUIT, jamais la structure.

    Motivation (retour réel d'Alain) : le SCNR « moyenne neutre » classique
    est inadapté aux palettes narrowband — en SHO sans S (R = 0, G = Ha,
    B = O3), le neutre devient (0+B)/2 = O3/2 et TOUT le signal Ha est
    écrêté : l'image vire franchement au bleu. Or le vert y est de la
    DONNÉE, pas du bruit ; le grésillement vert du fond, seul, est à
    retirer.

    Calcul par pixel :
      e = G − (R+B)/2                      (excès de vert ; on ne traite
                                            que la partie positive)
      σ = bruit de e, estimé par MAD sur le DÉTAIL haute-fréquence de e
          (1re couche starlet, cf. denoise.estimer_sigma) — insensible au
          fait que la structure (nébuleuse) soit majoritaire dans l'image :
          une nébuleuse est LISSE, le grain seul vit en haute fréquence ;
      t = k·σ (k = 3 par défaut) ;
      garotte douce sur la partie positive (la MÊME fonction que le
      seuillage du débruitage ondelettes) :
        e ≤ 0     → pixel inchangé (pas d'excès de vert) ;
        0 < e ≤ t → e' = 0 (grésillement vert du fond neutralisé) ;
        e > t     → e' = e − t²/e (structure préservée, abaissée seulement
                    du plancher de bruit) ;
      G' = (R+B)/2 + e'.

    → copie float32, mono inchangé, entrée jamais modifiée, aucune
    exception (numpy seul)."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return a.copy()
    n = 0.5 * (a[..., 0] + a[..., 2])
    e = a[..., 1] - n
    sigma = _denoise.estimer_sigma(e)
    t = np.float32(max(0.0, float(k)) * sigma)
    ee = np.maximum(e, np.float32(1e-12))
    garotte = np.where(e > t, e - t * t / ee, np.float32(0.0))
    e_prime = np.where(e > 0, garotte, e)     # pas d'excès : inchangé
    out = a.copy()
    out[..., 1] = n + e_prime
    return out
