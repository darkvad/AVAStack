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
