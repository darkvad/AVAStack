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
    — ignoré silencieusement pour les formats non FITS."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".fits", ".fit", ".fts") and FITS_OK:
        d = np.asarray(arr)
        if d.ndim == 3 and d.shape[-1] <= 4 and d.shape[0] > 4:
            d = np.transpose(d, (2, 0, 1))     # (H, W, C) → (C, H, W)
        hdu = fits.PrimaryHDU(np.ascontiguousarray(d, dtype=np.float32))
        if entete:
            for k, v in entete.items():
                hdu.header[str(k).upper()] = v
        hdu.writeto(path, overwrite=True)
    else:
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

