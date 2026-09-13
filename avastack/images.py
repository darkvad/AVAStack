# -*- coding: utf-8 -*-
"""Entrées/sorties image : chargement, sauvegarde, débayerisation, et
utilitaires pour les résultats des outils externes."""

import os
import glob

import numpy as np
import cv2

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


def save_image(path, arr):
    """Sauve une image float [0..1] en FITS (si astropy) ou PNG/TIFF 16 bits."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".fits", ".fit", ".fts") and FITS_OK:
        fits.PrimaryHDU(arr.astype(np.float32)).writeto(path, overwrite=True)
    else:
        u16 = (np.clip(arr, 0, 1) * 65535).astype(np.uint16)
        ok, buf = cv2.imencode(ext, u16)
        if not ok:
            raise IOError("Encodage impossible")
        buf.tofile(path)


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
            if os.path.isfile(f) and os.path.abspath(f) != os.path.abspath(src):
                return f
    return None


def auto_unflip(proc, ref):
    """Certains outils externes rendent l'image en miroir vertical (convention
    FITS « bas en haut » vs image « haut en bas »). Compare le résultat traité
    à l'empilement d'origine (sous-échantillonnés pour la vitesse) et retourne
    le résultat dans la bonne orientation. Marge de sécurité : ne retourne que
    si le miroir corrèle NETTEMENT mieux (évite les faux positifs sur une image
    quasi symétrique)."""
    try:
        a = proc if proc.ndim == 2 else proc.mean(axis=2)
        b = ref if ref.ndim == 2 else ref.mean(axis=2)
        if a.shape != b.shape:
            return proc                       # formes différentes → ne rien risquer
        a = a[::max(1, a.shape[0] // 256), ::max(1, a.shape[1] // 256)]
        b = b[::max(1, b.shape[0] // 256), ::max(1, b.shape[1] // 256)]
        a = a.astype(np.float64)
        b = b.astype(np.float64)

        def corr(x, y):
            x, y = x - x.mean(), y - y.mean()
            d = np.sqrt((x * x).sum() * (y * y).sum())
            return float((x * y).sum() / d) if d > 0 else 0.0

        if corr(a, b[::-1]) > corr(a, b) + 0.05:
            return proc[::-1]                 # miroir vertical → on redresse
        return proc
    except Exception:
        return proc

