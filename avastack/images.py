# -*- coding: utf-8 -*-
"""Entrées/sorties image : chargement, sauvegarde, débayerisation, et
utilitaires pour les résultats des outils externes."""

import os
import glob
import re

import numpy as np
import cv2

from . import travail

try:
    from astropy.io import fits
    FITS_OK = True
except ImportError:
    FITS_OK = False

# --- Brutes capteur couleur (matrice de Bayer / CFA) -----------------------
# « Non »  : caméra mono, ou images déjà en couleur (TIFF/PNG RGB, FITS 3 canaux)
# « Auto » : lit BAYERPAT dans l'en-tête FITS ; sinon devine via les étoiles,
#           et laisse intactes les images sans signature couleur (caméra mono)
# RGGB/BGGR/GRBG/GBRG : force le pattern (RGGB = le plus courant chez ZWO)
# NB : variable de MODULE, modifiée par l'interface (menu déroulant) —
# comportement identique au `global CFA_MODE` de l'ancien fichier unique.
CFA_MODE = "Auto"


def _debayer(a, pattern):
    """Débayerisation 2D → RGB. NB : les noms OpenCV sont décalés d'une maille
    (un capteur RGGB s'appelle « BG »…), d'où la table ci-dessous."""
    codes = {"RGGB": cv2.COLOR_BAYER_BG2RGB, "BGGR": cv2.COLOR_BAYER_RG2RGB,
             "GRBG": cv2.COLOR_BAYER_GB2RGB, "GBRG": cv2.COLOR_BAYER_GR2RGB}
    return cv2.cvtColor(a, codes.get(pattern, codes["RGGB"]))


def _guess_bayer(a):
    """Devine le pattern — ou détecte que l'image est MONO.
    Renvoie 'RGGB'/'BGGR'/'GRBG'/'GBRG', ou None si l'image ne présente
    aucune signature de matrice couleur (caméra mono, image déjà en niveaux
    de gris) → dans ce cas il ne faut surtout pas débayeriser."""
    # OpenCV ne débayerise que du 8/16 bits ENTIERS : une image flottante
    # (master dark/flat, empilement, sortie d'outil externe) n'est jamais une
    # brute Bayer → la traiter comme mono sans rien tenter (sinon cv2.error
    # et fichier déclaré illisible).
    if a.dtype not in (np.uint8, np.uint16):
        return None
    f = a.astype(np.float32)
    mask = f > np.percentile(f, 99.9)
    if int(mask.sum()) < 100:              # pas assez d'étoiles → ne rien risquer
        return None
    star = float(np.median(f[mask]))       # luminosité typique des étoiles
    colorations = {}
    for pat in ("RGGB", "BGGR", "GRBG", "GBRG"):
        # _debayer exige du 8/16 bits entiers (limite OpenCV) : on repasse
        # par l'image ENTIÈRE d'origine, jamais par la copie flottante.
        px = _debayer(a, pat)[mask]
        colorations[pat] = float(np.median(px.max(axis=1) - px.min(axis=1)))
    pat = min(colorations, key=colorations.get)
    c_min, c_max = min(colorations.values()), max(colorations.values())
    # Vraie matrice Bayer : le mauvais pattern colore fortement les étoiles
    # (c_max élevé), le bon les laisse blanches (c_min ≈ 0) → grand écart.
    # Image mono : tous les patterns donnent la même faible coloration
    # (celle du bruit) → pas de gagnant net → mono.
    if c_max < 0.15 * star or c_max < 2.5 * max(c_min, 1e-9):
        return None                        # aucune signature couleur → mono
    return pat


def _apply_cfa(a, path):
    """Débayerise une brute 2D selon CFA_MODE. Ne touche ni aux images déjà
    RGB, ni (en Auto) aux images sans signature de matrice couleur (mono)."""
    if CFA_MODE == "Non" or a.ndim != 2:
        return a
    pat = CFA_MODE
    if pat == "Auto":
        if FITS_OK and path.lower().endswith((".fits", ".fit", ".fts")):
            try:
                with fits.open(path) as hd:
                    h = (hd[0].header.get("BAYERPAT")
                         or hd[0].header.get("BAYPAT") or "").upper().strip()
                if h in ("RGGB", "BGGR", "GRBG", "GBRG"):
                    return _debayer(a, h)   # info fiable de l'acquisition
            except Exception:
                pass
        pat = _guess_bayer(a)
        if pat is None:
            return a                       # image mono → intacte
    return _debayer(a, pat)


def load_image(path):
    """Charge FITS/PNG/TIFF/JPG → float32, RGB ou mono. Débayerise
    éventuellement (CFA_MODE) les brutes d'un capteur couleur.
    Normalisation selon le TYPE de données (et non la valeur max) :
    entiers 8/16 bits → [0..1] ; flottants (empilements, sorties GraXpert/BXT
    en 32F) → inchangés, y compris les valeurs > 1 des étoiles brillantes."""
    p = path.lower()
    if p.endswith((".fits", ".fit", ".fts")) and FITS_OK:
        with fits.open(path) as hd:
            a = np.asarray(hd[0].data)
        if a.ndim == 3 and a.shape[0] <= 4 and a.shape[-1] > 4:
            # PIÈGE axes FITS couleur (même convention que
            # alignment.canal_alignement) : un FITS RGB standard écrit les
            # canaux sur NAXIS3 — astropy le rend (C, H, W). Toute l'appli
            # travaille en (H, W, C) → normalisation ICI, une fois pour toutes
            # (nos propres sauvegardes RGB incluses depuis le correctif
            # « save_image canaux sur NAXIS3 »).
            a = np.ascontiguousarray(np.transpose(a, (1, 2, 0)))
    else:
        a = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_UNCHANGED)
        if a is None:
            raise IOError(f"Lecture impossible : {path}")
        if a.ndim == 3 and a.shape[2] == 4:          # PNG/TIFF avec canal alpha
            a = cv2.cvtColor(a, cv2.COLOR_BGRA2RGB)
        elif a.ndim == 3 and a.shape[2] == 3:
            a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
    a = _apply_cfa(a, path)
    if a.dtype == np.uint8:
        a = a.astype(np.float32) / 255.0
    elif a.dtype == np.uint16:
        a = a.astype(np.float32) / 65535.0
    elif a.dtype == np.int16:                        # FITS 16 bits = signé
        a = np.clip(a, 0, None).astype(np.float32) / 32768.0
    else:                                            # float32/64 : tel quel
        a = a.astype(np.float32)
    return a

def lire_filtre_fits(path):
    """Mot-clé FILTER de l'en-tête d'un FITS (jalon 19 : auto-détection du
    filtre d'un dossier surveillé), ou None (PNG/TIFF, absence du mot-clé,
    lecture impossible — jamais d'exception)."""
    if not FITS_OK or not str(path).lower().endswith((".fits", ".fit", ".fts")):
        return None
    try:
        with fits.open(path) as hd:
            f = hd[0].header.get("FILTER")
    except Exception:
        return None
    f = str(f).strip() if f is not None else ""
    return f or None




def borner_lineaire(arr, entete=None, seuil=1.0):
    """Ramène une image LINÉAIRE dans [0, seuil] AVANT sauvegarde, en
    consignant le facteur global retiré dans l'en-tête FITS (AVASCALE).

    Pourquoi : toute l'appli travaille en float [0..1] (load_image normalise
    selon le dtype réel, et l'affichage VeraLux, le débruitage, les sorties
    TIFF/PNG et le solveur supposent cette plage). SEULE exception : le
    composite d'une composition multi-dossiers — `composition.normaliser`
    cale chaque rôle sur ses percentiles 0,25/99,7 SANS clip, donc le cœur
    d'une galaxie monte beaucoup plus haut que 1 (constat RÉEL du
    22/09/2026 sur l'empilement RGB M31 d'Alain en mode dossiers : max 14,1
    pour un fond à 0,02 — 0,3 % des pixels au-dessus de 1). Écrit tel quel,
    un tel fichier est inutilisable par l'extérieur :
      • ASTAP convertit en 16 bits et n'y détecte plus AUCUNE étoile
        (« Only 0 stars found in image » → « Not enough stars » → jamais
        résolu) ; le même contenu borné à 1 est résolu en 0,2 s (143 quads
        sur 144, échelle identique à celle de la brute du même setup) ;
      • tout lecteur qui suppose [0..1] (ASIFitsView, Siril…) clippe le
        cœur et les cœurs d'étoiles en blanc : l'empilement « paraît
        saturé » alors qu'il est simplement hors échelle.

    Un SEUL facteur GLOBAL est retiré (jamais par canal) : l'équilibre des
    couleurs et la linéarité sont préservés au bit près, et l'opération est
    RÉVERSIBLE (facteur dans l'en-tête). Les valeurs non finies (nan/inf)
    sont neutralisées et comptées (AVANAN) : astropy les écrirait telles
    quelles, et aucun outil externe ne sait les lire.

    arr    : image float 2D ou (H, W, C) — JAMAIS modifiée sur place.
    entete : dict de mots-clés FITS à compléter (optionnel).
    seuil  : plafond de l'écriture (1.0 par défaut = convention du projet).
    → (arr float32 borné, entete dict) ; arr inchangé si max <= seuil.
    """
    d = np.asarray(arr, dtype=np.float32)
    entete = dict(entete or {})
    fini = np.isfinite(d)
    if not bool(fini.all()):
        entete["AVANAN"] = int(fini.size - int(fini.sum()))
        d = np.where(fini, d, 0.0).astype(np.float32)
    if d.size:
        mx = float(d.max())
        if mx > float(seuil) and mx > 0.0:
            d = (d / mx).astype(np.float32)
            entete["AVASCALE"] = (mx, "facteur global retire a l'ecriture")
            entete["HISTORY"] = ("donnees lineaires bornees a [0,1] par "
                                 "AVAStack (cf. AVASCALE)")
    return d, entete


# --- Écriture ATOMIQUE et ESPACE DISQUE (v2.38.6) ---------------------------
# Constat RÉEL (Alain, 27/09/2026, Linux) : « Erreur : 24962352 requested and
# 10902832 written » au moment de BlurX. Ce message est celui de
# `numpy.ndarray.tofile()`, appelé par ASTROPY pour écrire les données d'un
# FITS (`io/fits/util.py::_array_to_file` : « delegates directly to
# ndarray.tofile ») : l'écriture s'est ARRÊTÉE à 43 % — signature d'un VOLUME
# PLEIN (le `/tmp` de sa machine est un tmpfs de 4,6 Go que l'archivage des
# frames remplissait), pas d'un chemin invalide (lequel échouerait dès
# l'ouverture). Deux corrections : ① on vérifie l'espace AVANT d'écrire et on
# REFUSE avec une phrase chiffrée ; ② on écrit dans un `.part` qu'on RENOMME à
# la fin, donc un fichier tronqué ne peut plus rester à la place d'une image
# valide (danger réel : un FITS partiel se relit !).
_MOTIF_PARTIEL = re.compile(r"(\d+)\s+requested\s+and\s+(\d+)\s+written")


def traduction_erreur_ecriture(exc, chemin, octets=None):
    """Phrase CLAIRE pour un échec d'écriture disque (v2.38.6).

    L'utilisateur ne peut pas deviner ce que veut dire « N requested and M
    written » : on lui dit le fichier, la quantité écrite, l'espace restant et
    ce qu'il peut faire."""
    dossier = os.path.dirname(os.path.abspath(chemin)) or "."
    libre = travail.espace_libre(dossier)
    txt, errno_ = str(exc), getattr(exc, "errno", None)
    trouve = _MOTIF_PARTIEL.search(txt)
    if trouve or errno_ in (28, 122):     # 28 = ENOSPC (plein), 122 = quota
        detail = ("écriture incomplète (%s écrits sur %s) "
                  % (travail.texte_octets(int(trouve.group(2))),
                     travail.texte_octets(octets))
                  if (trouve and octets) else "écriture incomplète ")
        return (f"{detail}— plus d'espace sur le volume de « {dossier} » "
                f"({travail.texte_octets(libre)} libres"
                + (", en RAM : tmpfs" if travail.est_tmpfs(dossier) else "")
                + ") : libérez de l'espace ou choisissez un autre dossier de "
                  "travail (bouton « dossier de travail »).")
    if errno_ == 27:                      # EFBIG : limite `ulimit -f`
        return (f"écriture refusée (limite de taille de fichier du système) "
                f"pour {chemin} : relevez `ulimit -f`.")
    if errno_ == 2 or isinstance(exc, FileNotFoundError):
        return f"dossier introuvable pour écrire {chemin}."
    return (f"écriture impossible dans {chemin} : {txt} "
            f"({travail.texte_octets(libre)} libres sur le volume)")



def ecrire_fichier(chemin, ecrivain, octets=None, quoi=None):
    """Écrit un fichier de façon ATOMIQUE, après contrôle d'espace.

    `ecrivain(destination)` reçoit le chemin d'un fichier `.part` à écrire
    (astropy pour un FITS, `ndarray.tofile` pour un PNG/TIFF). Renvoie le
    chemin écrit, ou lève `OSError` avec un message CLAIR (jamais le message
    brut de numpy) :

      - espace vérifié AVANT l'écriture (`travail.verifier_espace`) ;
      - le fichier partiel est TOUJOURS supprimé en cas d'échec ;
      - `os.replace` à la fin : le nom définitif n'apparaît que complet."""
    dossier = os.path.dirname(os.path.abspath(chemin)) or "."
    quoi = quoi or f"l'écriture de {os.path.basename(chemin)}"
    if octets:
        ok, msg = travail.verifier_espace(dossier, octets, quoi)
        if not ok:
            raise OSError(msg)
    part = chemin + ".part"
    try:
        ecrivain(part)
    except Exception as exc:
        supprimer_si_present(part)
        raise OSError(traduction_erreur_ecriture(exc, chemin, octets)) from exc
    try:
        os.replace(part, chemin)
    except OSError as exc:
        supprimer_si_present(part)
        raise OSError(traduction_erreur_ecriture(exc, chemin, octets)) from exc
    return chemin


def supprimer_si_present(chemin):
    """Supprime un fichier partiel (jamais d'exception)."""
    try:
        if os.path.exists(chemin):
            os.remove(chemin)
    except OSError:
        pass


def ecrire_fits(chemin, arr, entete=None):
    """Écrit un FITS float32 (astropy) de façon atomique — UNE seule route
    d'écriture FITS pour l'application (sauvegardes ET fichiers de travail des
    chaînes externes, qui avaient chacun la leur)."""
    if not FITS_OK:
        raise OSError("astropy est absent : écriture FITS impossible")
    d = np.asarray(arr)
    if d.ndim == 3 and d.shape[-1] <= 4 and d.shape[0] > 4:
        d = np.transpose(d, (2, 0, 1))     # (H, W, C) → (C, H, W)
    d = np.ascontiguousarray(d, dtype=np.float32)

    def _ecrire(destination):
        hdu = fits.PrimaryHDU(d)
        if entete:
            for k, v in entete.items():
                hdu.header[str(k).upper()] = v
        hdu.writeto(destination, overwrite=True)

    return ecrire_fichier(chemin, _ecrire, octets=d.nbytes)


def save_image(path, arr, entete=None):
    """Sauve une image float en FITS (si astropy) ou PNG/TIFF 16 bits.

    Couleur : l'appli travaille en (H, W, C) mais un FITS RGB lisible par
    les outils externes (Siril, ASIFitsView, GraXpert, PixInsight…) exige
    les canaux sur NAXIS3 → écrit en (C, H, W) (c'est LA convention astro ;
    le piège inverse — (H, W, C) → NAXIS1 = 3 pixels de large, image « noire
    » chez tous les lecteurs — a été constaté en réel par Alain le
    22/09/2026 sur un empilement M31 : cf. aussi le contournement jalon 14
    pour GraXpert). Mono 2D inchangé.

    entete : dict optionnel de mots-clés FITS (p.ex. {"FILTER": "Ha"})
    — ignoré silencieusement pour les formats non FITS.

    v2.38.6 : l'écriture passe par `ecrire_fits` / `ecrire_fichier` —
    ESPACE VÉRIFIÉ AVANT, fichier écrit en `.part` puis renommé (jamais de
    fichier tronqué), et message clair en cas d'échec (le message brut de
    numpy « N requested and M written » ne disait ni le fichier ni la cause)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".fits", ".fit", ".fts") and FITS_OK:
        return ecrire_fits(path, arr, entete)
    d = np.asarray(arr, dtype=np.float32)
    u16 = (np.clip(d, 0, 1) * 65535).astype(np.uint16)
    # CORRECTIF v2.36.1 (constat d'Alain, 25/09/2026 : le PNG « tel que vu »
    # était « vachement bleu » alors que le FITS du même écran était juste) :
    # `cv2.imencode` attend du BGR (convention OpenCV) alors que TOUTE
    # l'appli travaille en RGB — `load_image` convertit à la lecture
    # (COLOR_BGR2RGB). Sans cette conversion, chaque PNG/TIFF écrit sortait
    # avec R et B PERMUTÉS (mesuré sur son fichier : PNG_R ≈ FITS_B et
    # PNG_B ≈ FITS_R, corrélation 1,0000) — et l'aller-retour interne
    # (écriture sans conversion, relecture avec conversion) restait
    # cohérent, ce qui masquait le bug : seuls les outils EXTERNES (viewer,
    # Siril, GraXpert…) et l'utilisateur le voyaient.
    if u16.ndim == 3 and u16.shape[-1] == 3:
        u16 = cv2.cvtColor(u16, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(ext, u16)       # l'extension FINALE choisit le format
    if not ok:
        raise OSError(f"format d'image non pris en charge pour l'écriture : "
                      f"« {ext or 'sans extension'} »")
    # Le buffer est en mémoire : sa taille est connue AVANT d'écrire.
    return ecrire_fichier(path, lambda destination: buf.tofile(destination),
                          octets=int(buf.nbytes))


def find_output(src, outbase):
    """Retrouve le fichier produit par un outil externe : d'abord le chemin
    exact attendu (toute extension), sinon n'importe quel fichier dérivé de
    outbase ou de l'entrée (suffixes « -bxt », « _GraXpert »…), en excluant
    l'entrée elle-même."""
    for ext in (".fits", ".fit", ".fts", ".tif", ".tiff", ".png", "", ".jpg"):
        c = outbase + ext
        if os.path.isfile(c):
            return c
    base = os.path.splitext(src)[0]
    for pat in (outbase + "*", base + "*"):
        for f in sorted(glob.glob(pat)):
            if os.path.isfile(f) and os.path.abspath(f) != os.path.abspath(src) \
                    and not f.endswith(".part"):     # jamais un partiel (v2.38.6)
                return f
    return None


def auto_unflip(proc, ref):
    """Certains outils externes rendent l'image en miroir vertical (convention
    FITS « bas en haut » vs image « haut en bas »). Compare le résultat traité
    à l'empilement d'origine et retourne le résultat dans la bonne orientation.
    Marge de sécurité : ne retourne que si le miroir corrèle NETTEMENT mieux
    (+0,20 depuis la v2.38.2 — mesuré +0,27 à +0,46 sur les vrais miroirs, contre
    un écart de bruit < 0,05 quand l'orientation est bonne).

    CORRECTION v2.38.2 (constat mesuré sur les fichiers d'Alain, 27/09/2026) :
    la comparaison se fait désormais sur une version ÉTIRÉE et NORMALISÉE des
    deux images. Sur des images LINÉAIRES, la corrélation brute est écrasée par
    les quelques pixels du cœur des objets (≈ 1 contre un ciel à 0,03) : mesuré
    sur ses deux fichiers M31, les deux orientations donnaient +0,1085 (droite)
    et +0,1212 (miroir) — écart +0,0127, SOUS la marge de 0,05 → le miroir du
    CLI rc-astro (BXT) n'était pas détecté, et le résultat du ⚡ était
    enregistré ET affiché À L'ENVERS (constaté sur les fichiers v2.373, v2.38.0
    et v2.38.1 : corrélation +0,99 en miroir contre +0,35 tel quel). Sur ces
    MÊMES images, la comparaison étirée donne +0,539 (droite) contre +0,996
    (miroir) : la décision devient franche. Banc : `_test_unflip_jalon69.py`.
    """
    try:
        a = proc if proc.ndim == 2 else proc.mean(axis=2)
        b = ref if ref.ndim == 2 else ref.mean(axis=2)
        if a.shape != b.shape:
            return proc                       # formes différentes → ne rien risquer
        # Sous-échantillonnage par MOYENNE (INTER_AREA) : un pas de sélection
        # « 1 pixel sur N » fabriquait de l'aliasing et perturbait la mesure.
        ech = max(1.0, max(a.shape) / 256.0)
        taille = (max(8, int(round(a.shape[1] / ech))),
                  max(8, int(round(a.shape[0] / ech))))

        def preparer(x):
            """Luminance → étirement doux → normalisée (cf. docstring)."""
            y = cv2.resize(np.asarray(x, np.float32), taille,
                           interpolation=cv2.INTER_AREA)
            bas, haut = (float(v) for v in np.percentile(y, (0.5, 99.5)))
            y = np.clip((y - bas) / max(1e-9, haut - bas), 0.0, 1.0)
            return np.sqrt(y).astype(np.float64)

        a, b = preparer(a), preparer(b)

        def corr(x, y):
            x, y = x - x.mean(), y - y.mean()
            d = np.sqrt((x * x).sum() * (y * y).sum())
            return float((x * y).sum() / d) if d > 0 else 0.0

        if corr(a, b[::-1]) > corr(a, b) + 0.20:
            return proc[::-1]                 # miroir vertical → on redresse
        return proc
    except Exception:
        return proc

