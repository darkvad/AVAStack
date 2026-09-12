#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AVAStack — live stacking (empilement temps réel, version complète)
================================================================
Sources disponibles :
  - Simulée (démo)          : ciel synthétique avec dérive, pour tester sans matériel
  - Dossier surveillé       : empile les brutes FITS/PNG/TIFF au fur et à mesure de
                              leur arrivée (N.I.N.A., APT, SGP, ASI Air… écrivent dedans)
  - OpenCV 0/1              : webcams, cartes d'acquisition
  - ZWO ASI (SDK)           : caméras ZWO (pip install zwoasi + DLL du SDK)

Pipeline : Acquisition → Calibration (dark/flat) → Alignement (ORB + RANSAC,
repli corrélation de phase) → Empilement avec rejet kappa-sigma →
Étirement temps réel (auto STF ou manuel) → Affichage + histogramme →
Sauvegarde FITS/TIFF/PNG.

Affichage :
  - Auto-stretch « STF » : point noir = médiane − k·σ, point blanc = percentile 99.9,
    midtones calées pour poser le fond du ciel à ~25 % ; stats lissées (anti-pompage).
  - Zoom : molette sur l'image (centré sur le curseur), glisser pour se déplacer,
    double-clic pour réajuster.
  - Dark/flat chargés indiqués (nom + dimensions).

Traitement externe (GraXpert, RC-Astro CLI…) : appliqué à un INSTANTANÉ de
l'empilement courant, dans un thread séparé — l'acquisition continue. Le
résultat n'affecte que l'affichage (vue « traitée ») et une sauvegarde dédiée ;
l'empilement accumulé reste linéaire et intact. Commandes configurables
(bouton « … ») ; placeholders {input} / {output} / {outbase}. Erreurs signalées :
libellé coloré, chrono, popup. Le fichier de sortie est retrouvé
automatiquement (extension et suffixe quelconques : -bxt, _GraXpert…), et un
éventuel miroir vertical (conventions FITS) est corrigé automatiquement.

Dépendances :
    pip install numpy opencv-python pillow
Optionnel :
    pip install astropy          # sauvegarde FITS
    pip install zwoasi           # caméras ZWO (nécessite la DLL du SDK ASI)

Test sans matériel : source « Simulée (démo) » → Démarrer.
Test en dossier : choisir le dossier, éventuellement déposer une brute dedans → Démarrer.
"""

# --- Version + changelog (entrée la plus récente en premier) ----------------
AVASTACK_VERSION = "1.1.0"
# v1.1.0 : COMPATIBILITE MULTIPLATEFORME (demande Alain : Windows/Linux/macOS).
#          - Chemin Windows en dur de BlurXTerminator supprime : detection
#            automatique de GraXpert et rc-astro (variable d'environnement
#            AVASTACK_GRAXPERT / AVASTACK_RC_ASTRO, puis PATH, puis
#            emplacements d'installation courants selon l'OS).
#          - PERSISTANCE des reglages dans config.json (emplacement selon les
#            conventions de l'OS : %APPDATA%\AVAStack, ~/Library/Application
#            Support/AVAStack, ~/.config/AVAStack) : commandes des outils
#            externes (choisies via le bouton « ... » ou detectees), dossier
#            surveille, CFA, cases GraXpert/BXT, reglages d'etirement
#            (sigk/target/gamma/saturation). Plus rien a reconfigurer au
#            lancement suivant.
#          - Bibliothque SDK ZWO selon l'OS (ASICamera2.dll /
#            libASICamera2.so / libASICamera2.dylib).
#          - Filtre de selection d'executable adapte a l'OS (bouton « ... »).
# Aucune nouvelle dependance Python (json/sys/shutil : bibliotheque standard).
# v1.0.0 : RENOMMAGE (demande Alain) : AstroLiveStack → AVAStack (éviter la
#          confusion avec ALS - Astro Live Stacker). Fichier renommé en
#          AVAStack.py, titre de fenêtre, préfixe des dossiers temporaires
#          (avastack_), variable AVASTACK_VERSION créée (n'existait pas
#          auparavant malgré la convention CLAUDE.md).

import os
import sys
import json
import glob
import time
import queue
import shutil
import subprocess
import tempfile
import threading
from collections import deque

import numpy as np
import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    raise SystemExit("Pillow est requis :  pip install pillow")

try:
    from astropy.io import fits
    FITS_OK = True
except ImportError:
    FITS_OK = False

# --- Compatibilite multiplateforme (Windows / Linux / macOS) ---------------
IS_WINDOWS = (os.name == "nt")
IS_MACOS = (sys.platform == "darwin")

# Nom de bibliotheque du SDK ZWO selon l'OS (DLL Windows, .so Linux, .dylib macOS)
ZWO_DLL_NAME = "ASICamera2.dll" if IS_WINDOWS else (
    "libASICamera2.dylib" if IS_MACOS else "libASICamera2.so")


def dossier_config():
    """Dossier de configuration persistante, selon les conventions de l'OS :
    %APPDATA%\\AVAStack (Windows), ~/Library/Application Support/AVAStack
    (macOS), ~/.config/avastack (Linux). Cree si absent."""
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif IS_MACOS:
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "AVAStack")
    os.makedirs(d, exist_ok=True)
    return d


CHEMIN_CONFIG = os.path.join(dossier_config(), "config.json")

SOURCES = ["Simulée (démo)",
           "Dossier surveillé (brutes FITS/PNG/TIFF…)",
           "OpenCV 0", "OpenCV 1", "ZWO ASI (SDK)"]

# --- Brutes capteur couleur (matrice de Bayer / CFA) -----------------------
# « Non »  : caméra mono, ou images déjà en couleur (TIFF/PNG RGB, FITS 3 canaux)
# « Auto » : lit BAYERPAT dans l'en-tête FITS ; sinon devine via les étoiles,
#           et laisse intactes les images sans signature couleur (caméra mono)
# RGGB/BGGR/GRBG/GBRG : force le pattern (RGGB = le plus courant chez ZWO)
CFA_MODE = "Auto"

# --- Traitement externe (instantané de l'empilement) -----------------------
# Commandes par défaut : l'exécutable est DETECTÉ AUTOMATIQUEMENT au premier
# lancement (variables d'environnement AVASTACK_GRAXPERT / AVASTACK_RC_ASTRO,
# puis PATH, puis emplacements d'installation courants selon l'OS). Une fois
# détecté ou choisi via le bouton « … », la commande complète est PERSISTÉE
# dans le fichier de configuration (dossier_config()/config.json) — plus
# besoin de la reconfigurer au lancement suivant.
# Placeholders :
#   {input}    fichier d'entrée (FITS temporaire, instantané de l'empilement)
#   {output}   fichier de sortie complet (…\\xxx.fits)
#   {outbase}  chemin de sortie SANS extension (GraXpert : -output)
# Syntaxe GraXpert (le flag -cli est indispensable) :
#   graxpert <image> -cli [-cmd background-extraction|denoising]
#            [-correction Subtraction|Division] [-smoothing 0..1]
#            [-output <nom_sans_extension>] [-bg] [-ai_version X]
#   NB : la valeur de -correction est SENSIBLE À LA CASSE (S et D majuscules).
# Syntaxe RC-Astro (BlurXTerminator) :
#   rc-astro bxt <image> -o <sortie> --overwrite
#            [--ss 0..0.7] [--sn 0..1] [--correct-only] [--device gpu]


def _trouver_exe(noms, env_var, sous_chemins):
    """Cherche un exécutable : 1) variable d'environnement dédiée,
    2) dans le PATH (shutil.which), 3) emplacements d'installation courants
    selon l'OS. → chemin complet ou None."""
    env = os.environ.get(env_var)
    if env and os.path.isfile(env):
        return env
    for nom in noms:
        trouve = shutil.which(nom)
        if trouve:
            return trouve
    racines = ([os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMFILES", ""),
                os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMW6432", "")]
               if IS_WINDOWS else
               [os.path.expanduser("~/Applications"), "/Applications"]
               if IS_MACOS else
               [os.path.expanduser("~/.local"), "/usr/local", "/opt"])
    for racine in racines:
        if not racine:
            continue
        for sous in sous_chemins:
            for nom in noms:
                c = os.path.join(racine, sous, nom)
                if os.path.isfile(c):
                    return c
    return None


# Noms de binaires par OS (Windows : .exe ; Linux/macOS : sans extension)
_NOM_GRAXPERT = ("graxpert.exe",) if IS_WINDOWS else ("graxpert", "GraXpert")
_NOM_RC_ASTRO = ("rc-astro.exe",) if IS_WINDOWS else ("rc-astro",)
# Emplacements d'installation connus (relatifs aux racines de _trouver_exe)
_SOUS_GRAXPERT = ("" if IS_WINDOWS else "GraXpert",)
_SOUS_RC_ASTRO = (os.path.join("RC-Astro", "CLI"), "")


def commande_par_defaut_graxpert():
    exe = _trouver_exe(_NOM_GRAXPERT, "AVASTACK_GRAXPERT", _SOUS_GRAXPERT)
    if exe is None:
        return 'graxpert "{input}" -cli -cmd background-extraction ' \
               '-correction Subtraction -smoothing 0.5 -output "{outbase}"'
    return f'"{exe}" ' + ('"{input}" -cli -cmd background-extraction '
                          '-correction Subtraction -smoothing 0.5 -output "{outbase}"')


def commande_par_defaut_bxt():
    exe = _trouver_exe(_NOM_RC_ASTRO, "AVASTACK_RC_ASTRO", _SOUS_RC_ASTRO)
    if exe is None:
        return 'rc-astro bxt "{input}" -o "{output}" --overwrite'
    return f'"{exe}" bxt "{{input}}" -o "{{output}}" --overwrite'


# Commandes effectives au lancement : persistance d'abord, détection ensuite
def _charger_config():
    """Lit config.json → dict ({} si absent/corrompu)."""
    try:
        with open(CHEMIN_CONFIG, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _sauver_config(d):
    """Écrit config.json (tolérant aux échecs : réglages non vitaux)."""
    try:
        with open(CHEMIN_CONFIG, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


CONFIG = _charger_config()
DEFAULT_CMD_GRAXPERT = CONFIG.get("cmd_graxpert") or commande_par_defaut_graxpert()
DEFAULT_CMD_BXT = CONFIG.get("cmd_bxt") or commande_par_defaut_bxt()


# ============================================================ utilitaires E/S
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
    f = a.astype(np.float32)
    mask = f > np.percentile(f, 99.9)
    if int(mask.sum()) < 100:              # pas assez d'étoiles → ne rien risquer
        return None
    star = float(np.median(f[mask]))       # luminosité typique des étoiles
    colorations = {}
    for pat in ("RGGB", "BGGR", "GRBG", "GBRG"):
        px = _debayer(f, pat)[mask]
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


def _find_output(src, outbase):
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


def _auto_unflip(proc, ref):
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


# ============================================================ backends caméra
class CameraBase:
    name = "?"
    def open(self): pass
    def close(self): pass
    def read(self):
        """→ float32 [0..1] de forme (H,W) mono ou (H,W,3) RGB, ou None."""
        raise NotImplementedError
    def apply_settings(self, exposure_ms, gain):
        pass


class SimulatedCamera(CameraBase):
    """Ciel synthétique : étoiles colorées + nébulosité faible + bruit + dérive/rotation lente."""
    name = "Ciel simulé"

    def __init__(self, w=960, h=640, n_stars=400, seed=7):
        self.w, self.h = w, h
        self.rng = np.random.default_rng(seed)
        self.t = 0
        self.exposure_ms = 100.0
        self.gain = 1.0
        xy = self.rng.uniform(0, 1, (n_stars, 2)) * [w, h]
        bright = np.clip(0.08 + self.rng.pareto(2.5, n_stars) * 0.05, 0.05, 1.0)
        temp = self.rng.uniform(3500, 9500, n_stars)          # température de couleur
        self.xy = xy.astype(np.float32)
        self.bright, self.red = bright, np.clip((temp - 3500) / 6000 * 0.45, 0, 0.45)
        self.blue = np.clip((9500 - temp) / 6000 * 0.45, 0, 0.45)
        self.drift = np.array([0.30, 0.12])                   # px / frame
        self.rot_deg = 0.002                                  # ° / frame
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.neb = (0.012 * np.exp(-((xx - w * 0.68) ** 2 + (yy - h * 0.35) ** 2)
                                   / (2 * (w * 0.22) ** 2))
                    + 0.004 * (1 - yy / h)).astype(np.float32)

    def apply_settings(self, exposure_ms, gain):
        self.exposure_ms = float(exposure_ms)
        self.gain = float(gain)

    def read(self):
        self.t += 1
        expo = self.exposure_ms / 100.0
        ang = self.rot_deg * self.t
        M = cv2.getRotationMatrix2D((self.w / 2, self.h / 2), ang, 1.0)
        M[0, 2] += self.drift[0] * self.t
        M[1, 2] += self.drift[1] * self.t
        pts = cv2.transform(self.xy.reshape(-1, 1, 2), M)[:, 0, :]
        canR = np.zeros((self.h, self.w), np.uint8)
        canG = np.zeros_like(canR)
        canB = np.zeros_like(canR)
        for (x, y), b, r, bl in zip(pts, self.bright, self.red, self.blue):
            xi, yi = int(round(x)), int(round(y))
            if -2 <= xi < self.w + 2 and -2 <= yi < self.h + 2:
                scint = 0.75 + 0.25 * self.rng.normal()       # seeing / scintillement
                v = int(np.clip(b * scint * expo * 255, 0, 255))
                if v > 0:
                    cv2.circle(canR, (xi, yi), 1, int(v * (1 - bl)), -1, cv2.LINE_AA)
                    cv2.circle(canG, (xi, yi), 1, v, -1, cv2.LINE_AA)
                    cv2.circle(canB, (xi, yi), 1, int(v * (1 - r)), -1, cv2.LINE_AA)
        img = np.stack([cv2.GaussianBlur(c, (0, 0), 0.8).astype(np.float32) / 255.0
                        for c in (canR, canG, canB)], axis=-1)
        img += (self.neb * expo)[..., None]
        # bruit : photonique (approx. gaussienne de Poisson) + bruit de lecture
        e = img * 1500.0
        noise = self.rng.normal(0.0, 1.0, img.shape).astype(np.float32)
        img = np.clip(e + noise * (np.sqrt(e) + 6.0), 0, None) / 1500.0
        return np.clip(img * self.gain, 0, 1.5)


class OpenCVCamera(CameraBase):
    """Webcams et cartes d'acquisition (pilote générique)."""
    def __init__(self, index=0):
        self.index = index
        self.name = f"OpenCV {index}"
        self.cap = None

    def open(self):
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(self.index, backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la caméra OpenCV {self.index}")
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def read(self):
        ok, f = self.cap.read()
        if not ok:
            return None
        return cv2.cvtColor(f, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

    def apply_settings(self, exposure_ms, gain):
        if not self.cap:
            return
        # Ces réglages dépendent fortement du driver (valeurs souvent ignorées) :
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_ms / 1000.0)
        self.cap.set(cv2.CAP_PROP_GAIN, gain)

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None


class ZWOASICamera(CameraBase):
    """Caméras ZWO — nécessite : pip install zwoasi + la bibliothèque du SDK
    (ASICamera2.dll Windows / libASICamera2.so Linux / libASICamera2.dylib macOS),
    à placer dans le dossier du script."""
    def __init__(self, index=0, dll_path=None):
        self.index, self.dll = index, dll_path or ZWO_DLL_NAME
        self.name = f"ZWO ASI #{index}"
        self.cam = None
        self._asi = None

    def open(self):
        try:
            import zwoasi as asi
        except ImportError:
            raise RuntimeError("SDK manquant :  pip install zwoasi  (+ DLL du SDK ASI)")
        if os.path.exists(self.dll):
            asi.init(self.dll)
        if asi.get_num_cameras() == 0:
            raise RuntimeError("Aucune caméra ZWO détectée")
        self._asi = asi
        self.cam = asi.Camera(self.index)
        self.cam.open()
        self.cam.set_control_value(asi.ASI_BANDWIDTHOVERLOAD, 40)
        self.cam.set_control_value(asi.ASI_HIGH_SPEED_MODE, 0)
        w, h, _, _ = self.cam.get_roi_format()
        self.cam.set_roi_format(w, h, 1, asi.ASI_RGB24)   # débayerisation par la caméra
        self.cam.start_video_capture()

    def apply_settings(self, exposure_ms, gain):
        if not self.cam:
            return
        asi = self._asi
        self.cam.set_control_value(asi.ASI_EXPOSURE, int(exposure_ms * 1000))  # µs
        self.cam.set_control_value(asi.ASI_GAIN, int(gain * 50))               # à adapter

    def read(self):
        try:
            a = self.cam.capture_video_frame(timeout=5000)
        except Exception:
            return None
        if a.ndim == 2:   # mono RAW
            return a.astype(np.float32) / (65535.0 if a.dtype == np.uint16 else 255.0)
        return a[:, :, ::-1].astype(np.float32) / 255.0  # si couleurs inversées: retirer [::-1]

    def close(self):
        if self.cam:
            try:
                self.cam.stop_video_capture()
                self.cam.close()
            finally:
                self.cam = None


class FolderCamera(CameraBase):
    """Source = dossier surveillé : empile les brutes au fur et à mesure qu'un
    logiciel d'acquisition (N.I.N.A., APT, SGP, ASI Air…) les écrit dedans.

    Un fichier n'est pris en compte que s'il est complet :
      - taille stable sur 2 scans consécutifs ET mtime > 0,5 s,
      - lecture réussie (3 essais, sinon abandonné et compté 'illisible').
    Les fichiers sont traités dans l'ordre chronologique (mtime, puis nom).
    """
    EXT = (".fits", ".fit", ".fts", ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp")

    def __init__(self, folder, process_existing=True, poll=0.4):
        self.folder = folder
        self.name = f"Dossier : {os.path.basename(folder) or folder}"
        self.process_existing = process_existing
        self.poll = poll
        self._seen = {}                 # nom -> dernière taille vue
        self._queued = set()            # en file d'attente
        self._processed = set()         # traités (ou à ignorer)
        self._pending = deque()
        self.last_file, self.count, self.failed = "", 0, 0
        self._running = False

    # -- cycle de vie -----------------------------------------------------
    def open(self):
        if not os.path.isdir(self.folder):
            raise RuntimeError(f"Dossier introuvable : {self.folder}")
        if not self.process_existing:   # ne traiter que ce qui arrivera ensuite
            self._processed = {e.name for e in self._entries()}
        self._running = True

    def close(self):
        self._running = False

    def apply_settings(self, *a):       # exposition/gain déjà « cuits » dans les fichiers
        pass

    # -- surveillance -------------------------------------------------------
    def _entries(self):
        try:
            with os.scandir(self.folder) as it:
                return [e for e in it
                        if e.is_file() and e.name.lower().endswith(self.EXT)]
        except OSError:                 # partage réseau momentanément absent, etc.
            return []

    def _scan(self):
        """Repère les nouveaux fichiers complets et les met en file (ordre chrono)."""
        now = time.time()
        entries = []
        for e in self._entries():
            try:
                st = e.stat()
                entries.append((st.st_mtime, e.name, e.path, st.st_size))
            except OSError:             # disparaît pendant le scan
                continue
        entries.sort()
        for mtime, name, path, size in entries:
            if name in self._processed or name in self._queued:
                continue
            prev = self._seen.get(name)
            if prev is None:                        # 1er aperçu → on attend le scan suivant
                self._seen[name] = size
            elif prev == size and now - mtime > 0.5:
                self._seen.pop(name)                # taille stable + mtime ancien → complet
                self._queued.add(name)
                self._pending.append(path)
            else:
                self._seen[name] = size             # encore en cours d'écriture

    def _try_load(self, path, attempts=3, delay=0.5):
        for _ in range(attempts):
            try:
                return load_image(path)
            except Exception:                       # FITS tronqué… → réessai
                time.sleep(delay)
        return None

    # -- interface CameraBase ---------------------------------------------
    def read(self):
        """→ prochaine image du dossier (attend jusqu'à ~1 s), sinon None."""
        deadline = time.time() + 1.0
        while time.time() < deadline and self._running:
            self._scan()
            if self._pending:
                path = self._pending.popleft()
                name = os.path.basename(path)
                self._queued.discard(name)
                img = self._try_load(path)
                self._processed.add(name)           # tenté = définitif (pas de boucle infinie)
                if img is not None:
                    self.last_file, self.count = path, self.count + 1
                    return img
                self.failed += 1
                continue
            time.sleep(self.poll)
        return None


# ============================================================ calibration
class Calibrator:
    def __init__(self):
        self.dark = None
        self.flat = None

    def load_dark(self, path):
        self.dark = load_image(path)

    def load_flat(self, path):
        self.flat = load_image(path)

    def clear(self):
        self.dark = self.flat = None

    def apply(self, img):
        out = img
        if self.dark is not None and self.dark.shape == img.shape:
            out = out - self.dark
        if self.flat is not None and self.flat.shape == img.shape:
            m = float(np.median(self.flat))
            if m > 1e-6:
                out = out / np.clip(self.flat / m, 0.2, None)
        return np.clip(out, 0, None)


# ============================================================ alignement
class StarAligner:
    """Aligne chaque frame sur une référence : features ORB + RANSAC
    (translation + rotation + échelle), repli sur corrélation de phase (translation)."""
    def __init__(self, n_features=1000, ratio=0.75, min_matches=8, min_inliers=8):
        self.orb = cv2.ORB_create(nfeatures=n_features, fastThreshold=8)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.ratio, self.min_matches, self.min_inliers = ratio, min_matches, min_inliers
        self.reset()

    def reset(self):
        self.ref_kp = self.ref_des = self.ref_gray = None

    def set_reference(self, img):
        self.ref_gray = self._norm8(img)
        self.ref_kp, self.ref_des = self.orb.detectAndCompute(self.ref_gray, None)

    def _norm8(self, img):
        mono = img.mean(axis=2) if img.ndim == 3 else img
        f = mono.astype(np.float32)
        lo, hi = np.percentile(f, 1.0), np.percentile(f, 99.7)
        if hi - lo < 1e-6:
            hi = lo + 1e-6
        return (np.clip((f - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)

    def compute(self, frame):
        """→ (M 2x3, confiant)  M transforme la frame courante vers la référence."""
        g = self._norm8(frame)
        kp, des = self.orb.detectAndCompute(g, None)
        if (self.ref_des is None or des is None
                or len(kp) < self.min_matches or len(self.ref_kp) < self.min_matches):
            return self._phase(g)
        good = [pair[0] for pair in self.bf.knnMatch(self.ref_des, des, k=2)
                if len(pair) == 2 and pair[0].distance < self.ratio * pair[1].distance]
        if len(good) < self.min_matches:
            return self._phase(g)
        src = np.float32([kp[m.trainIdx].pt for m in good])           # frame courante
        dst = np.float32([self.ref_kp[m.queryIdx].pt for m in good])  # référence
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.0, maxIters=5000)
        if M is None or inl is None:
            return self._phase(g)
        return M, int(inl.sum()) >= self.min_inliers

    def _phase(self, g):
        if self.ref_gray is None or self.ref_gray.shape != g.shape:
            return np.eye(2, 3), True
        a, b = self.ref_gray.astype(np.float32), g.astype(np.float32)
        (dx, dy), _ = cv2.phaseCorrelate(a, b)
        best_d, best_M = None, np.eye(2, 3)
        for s in (1.0, -1.0):  # signe déterminé empiriquement (comparaison SSD)
            M = np.array([[1.0, 0.0, s * dx], [0.0, 1.0, s * dy]])
            warp = cv2.warpAffine(b, M, (g.shape[1], g.shape[0]))
            d = float(np.mean((warp - a) ** 2))
            if best_d is None or d < best_d:
                best_d, best_M = d, M
        return best_M, True


# ============================================================ empilement
class LiveStacker:
    """Moyenne glissante + rejet kappa-sigma séquentiel (traînées de satellites, avions)."""
    def __init__(self, shape, k=3.0, warmup=5):
        self.shape = shape
        self.k = k
        self.warmup = warmup
        self.reset()

    def reset(self):
        self.sum = np.zeros(self.shape, np.float64)
        self.sumsq = np.zeros(self.shape, np.float64)
        self.wsum = np.zeros(self.shape, np.float64)
        self.n = 0
        self.rejected_total = 0

    def add(self, frame):
        f = frame.astype(np.float64)
        if self.k is not None and self.n >= self.warmup:
            mean = self.sum / np.maximum(self.wsum, 1e-9)
            std = np.sqrt(np.maximum(self.sumsq / np.maximum(self.wsum, 1e-9) - mean * mean, 1e-12))
            w = np.where(np.abs(f - mean) > self.k * std, 0.0, 1.0)
            self.rejected_total += int((w == 0).sum())
        else:
            w = 1.0
        self.sum += f * w
        self.sumsq += (f * f) * w
        self.wsum += w
        self.n += 1

    def mean(self):
        if self.n == 0:
            return None
        return (self.sum / np.maximum(self.wsum, 1e-9)).astype(np.float32)


# ============================================================ affichage
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
    Gamma et saturation s'appliquent dans les deux modes.
    """
    def __init__(self):
        self.auto = True
        self.sigma_k = 2.8            # coupure des ombres, en σ SOUS la médiane
        self.target = 0.25            # luminosité cible du fond du ciel après MTF
        self.black, self.white = 0.0, 1.0
        self.gamma, self.saturation = 1.0, 1.0
        self.last_lo, self.last_hi = 0.0, 1.0
        self._stats = None            # (médiane, σ, p99.9) lissées — anti-pompage
        self._ema = 0.25              # réactivité : 0 = figé, 1 = instantané

    def reset(self):
        """Oublie les stats lissées (nouvel empilement / changement de vue)."""
        self._stats = None

    @staticmethod
    def _mtf(x, m):
        """Midtones Transfer Function : x, m ∈ [0,1]."""
        m = min(max(m, 0.001), 0.98)
        return np.clip(((m - 1.0) * x) / ((2.0 * m - 1.0) * x - m), 0.0, 1.0)

    @staticmethod
    def _solve_m(x, t):
        """m tel que MTF(x, m) = t — inversion exacte de la MTF."""
        x = min(max(x, 1e-4), 0.9999)
        m = x * (1.0 - t) / (t + x - 2.0 * t * x)
        return min(max(m, 0.001), 0.98)

    def _auto_params(self, img, live=True):
        mono = img.mean(axis=2) if img.ndim == 3 else img
        s = mono[::max(1, mono.shape[0] // 512), ::max(1, mono.shape[1] // 512)]
        med = float(np.median(s))
        sigma = max(float(np.median(np.abs(s - med))) * 1.4826, 1e-8)  # σ robuste (MAD)
        p999 = float(np.percentile(s, 99.9))

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

    def process(self, img, live=True):
        img = img.astype(np.float32, copy=False)
        if self.auto:
            lo, hi, m = self._auto_params(img, live=live)
            self.last_lo, self.last_hi = lo, hi
            x = self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)
        else:
            lo, hi = self.black, self.white
            if hi - lo < 1e-6:
                hi = lo + 1e-6
            x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        if abs(self.gamma - 1.0) > 1e-3:
            x = np.power(x, 1.0 / max(self.gamma, 0.05))
        if img.ndim == 3 and abs(self.saturation - 1.0) > 1e-3:
            hsv = cv2.cvtColor(np.clip(x, 0.0, 1.0), cv2.COLOR_RGB2HSV)
            hsv[..., 1] = np.clip(hsv[..., 1] * self.saturation, 0.0, 1.0)
            x = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        return (np.clip(x, 0.0, 1.0) * 255).astype(np.uint8)


# ============================================================ interface
class App:
    W_IMG, H_IMG, W_HIST, H_HIST = 840, 560, 840, 110

    def __init__(self, root):
        self.root = root
        root.title("AVAStack — live stacking (empilement temps réel)")
        root.geometry("1300x820")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.camera = self.thread = None
        self.running = False
        self.q = queue.Queue(maxsize=2)
        self.stacker = None
        self.aligner = StarAligner()
        self.calib = Calibrator()
        self.disp = DisplayProcessor()
        self.kappa = 3.0
        self.pending_settings = None
        self.reset_request = self.ref_request = False
        self.save_request = self.saved_path = None
        self.bad_frames = 0
        self.fps = 0.0
        self.show_stack = None       # dernier aperçu linéaire de l'empilement
        self.last_show = None       # image linéaire actuellement affichée
        self._session = 0           # anti-mélange entre sessions

        # --- état du zoom / pan (affichage)
        self.zoom = 1.0                # 1.0 = image ajustée à la fenêtre
        self.view_cx = self.view_cy = None   # centre de vue (coords image), None = centre
        self._last_disp = None         # dernière image déjà étirée (pour re-rendu)
        self._drag = None              # point de départ du glisser-déplacer

        # --- traitement externe (instantané de l'empilement)
        self.ext_request = False        # demande en attente (lue par le worker)
        self.ext_busy = False           # un traitement externe tourne
        self.ext_job = None             # (graxpert?, cmd_gx, bxt?, cmd_bxt)
        self.proc_show = None           # aperçu traité (réduit, pour affichage)
        self.proc_full = None           # résultat traité pleine résolution (sauvegarde)
        self.proc_new = False           # un nouveau résultat vient d'arriver
        self.ext_msg = "—"              # message d'état (écrit par le thread, lu par _tick)
        self._ext_shown = None
        self.ext_state = "idle"         # idle | busy | ok | error
        self.ext_t0 = None              # début du traitement en cours (chrono)
        self._ext_popup = False        # erreur à signaler par popup

        self._build_ui()
        self._restaurer_config()
        self.root.after(30, self._tick)

    # ------------------------------------------------------------ persistance config
    def _restaurer_config(self):
        """Restaure les réglages persistés (dossier surveillé, CFA, traitement
        externe, étirement) après la construction de l'UI. Les commandes des
        outils externes ont déjà été restaurées au niveau module
        (DEFAULT_CMD_*). Si une commande détectée automatiquement (pas
        persistée) n'existe plus sur cette machine, elle est re-détectée."""
        c = CONFIG
        if c.get("dossier"):
            self.var_folder.set(c["dossier"])
        if c.get("cfa") in ("Auto", "RGGB", "BGGR", "GRBG", "GBRG", "Non"):
            self.var_cfa.set(c["cfa"])
        if c.get("process_existing") is False:
            self.var_process_existing.set(False)
        # Traitement externe : ne pas écraser une commande persistée par un
        # défaut re-détecté qui aurait changé ; si la commande au démarrage
        # était un chemin (détection) devenu inexistant, re-détecter.
        for cle, var in (("cmd_graxpert", self.var_cmd_graxpert),
                         ("cmd_bxt", self.var_cmd_bxt)):
            enreg = c.get(cle)
            if enreg:
                var.set(enreg)
            else:
                # commande détectée automatiquement → vérifier que l'exe existe
                premier = var.get().strip().split('"')[1] \
                    if var.get().strip().startswith('"') else None
                if premier and not os.path.isfile(premier):
                    var.set(commande_par_defaut_graxpert() if cle == "cmd_graxpert"
                            else commande_par_defaut_bxt())
        if c.get("ext_graxpert"):
            self.var_ext_graxpert.set(True)
        if c.get("ext_bxt"):
            self.var_ext_bxt.set(True)
        for cle, var, mini, maxi in (
                ("sigk", self.var_sigk, 0.5, 5.0),
                ("target", self.var_target, 0.10, 0.45),
                ("gamma", self.var_gamma, 0.2, 4.0),
                ("saturation", self.var_saturation, 0.0, 3.0)):
            v = c.get(cle)
            if isinstance(v, (int, float)) and mini <= v <= maxi:
                var.set(float(v))
        self.disp.sigma_k = self.var_sigk.get()
        self.disp.target = self.var_target.get()

    def _sauver_config_app(self):
        """Persiste les réglages de l'interface dans config.json (appelé à la
        fermeture). Ne touche pas aux entrées inconnues (extensibilité)."""
        c = dict(CONFIG)          # conserve les clés futures/éventuelles
        if self.var_folder.get().strip():
            c["dossier"] = self.var_folder.get().strip()
        c["cfa"] = self.var_cfa.get()
        c["process_existing"] = self.var_process_existing.get()
        # Les commandes ne sont persistées que si utilisées au moins une fois
        # ou modifiées par l'utilisateur — sinon on laisse la détection se
        # rejouer au prochain lancement (installation déplacée, etc.).
        if self.var_cmd_graxpert.get().strip():
            c["cmd_graxpert"] = self.var_cmd_graxpert.get().strip()
        if self.var_cmd_bxt.get().strip():
            c["cmd_bxt"] = self.var_cmd_bxt.get().strip()
        if self.var_ext_graxpert.get():
            c["ext_graxpert"] = True
        if self.var_ext_bxt.get():
            c["ext_bxt"] = True
        c["sigk"] = self.var_sigk.get()
        c["target"] = self.var_target.get()
        c["gamma"] = self.var_gamma.get()
        c["saturation"] = self.var_saturation.get()
        _sauver_config(c)

    # ------------------------------------------------------------ construction UI
    def _build_ui(self):
        main = ttk.PanedWindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True)

        # ------- Colonne gauche : zone défilable (canvas + scrollbar)
        container = ttk.Frame(main)
        main.add(container, weight=0)
        canvas = tk.Canvas(container, width=350, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        left = ttk.Frame(canvas, padding=8)
        win_id = canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=max(330, e.width)))

        def _wheel(event):
            w = self.root.winfo_containing(event.x_root, event.y_root)
            if w is None or not (w is canvas or str(w).startswith(str(left))):
                return                                  # molette hors du panneau → ignorer
            if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0:
                canvas.yview_scroll(-2, "units")
            elif getattr(event, "num", 0) == 5 or getattr(event, "delta", 0) < 0:
                canvas.yview_scroll(2, "units")
        canvas.bind_all("<MouseWheel>", _wheel)   # Windows / macOS
        canvas.bind_all("<Button-4>", _wheel)     # Linux
        canvas.bind_all("<Button-5>", _wheel)

        # --- Caméra
        box = ttk.LabelFrame(left, text="Caméra", padding=6)
        box.pack(fill="x", pady=3)
        self.var_source = tk.StringVar(value=SOURCES[0])
        ttk.Combobox(box, textvariable=self.var_source, values=SOURCES,
                     state="readonly", width=28).pack(fill="x", pady=2)
        rowbtn = ttk.Frame(box)
        rowbtn.pack(fill="x", pady=1)
        self.btn_start = ttk.Button(rowbtn, text="▶ Démarrer", command=self._start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=1)
        self.btn_stop = ttk.Button(rowbtn, text="■ Arrêter", command=self._stop,
                                   state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=1)
        self.var_expo = tk.DoubleVar(value=100.0)
        self.var_gain = tk.DoubleVar(value=1.0)
        self._add_slider(box, "Exposition (ms)", self.var_expo, 5, 1000, 5,
                         self._push_settings, "{:.0f}")
        self._add_slider(box, "Gain", self.var_gain, 0.5, 8.0, 0.1,
                         self._push_settings, "{:.1f}")

        # --- Dossier surveillé
        box = ttk.LabelFrame(left, text="Dossier surveillé", padding=6)
        box.pack(fill="x", pady=3)
        row = ttk.Frame(box)
        row.pack(fill="x")
        self.var_folder = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.var_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=self._pick_folder).pack(side="left", padx=(4, 0))
        self.var_process_existing = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Empiler aussi les images déjà présentes",
                        variable=self.var_process_existing).pack(anchor="w")
        rowc = ttk.Frame(box)
        rowc.pack(fill="x", pady=(3, 0))
        ttk.Label(rowc, text="Brutes capteur couleur :").pack(side="left")
        self.var_cfa = tk.StringVar(value=CFA_MODE)
        ttk.Combobox(rowc, textvariable=self.var_cfa, state="readonly", width=6,
                     values=["Auto", "RGGB", "BGGR", "GRBG", "GBRG", "Non"]
                     ).pack(side="left", padx=(4, 0))
        self.var_cfa.trace_add("write", self._on_cfa)
        self.lbl_last = ttk.Label(box, text="Dernier fichier : —")
        self.lbl_last.pack(anchor="w")

        # --- Calibration
        box = ttk.LabelFrame(left, text="Calibration", padding=6)
        box.pack(fill="x", pady=3)
        ttk.Button(box, text="Charger un dark…", command=self._load_dark).pack(fill="x", pady=1)
        ttk.Button(box, text="Charger un flat…", command=self._load_flat).pack(fill="x", pady=1)
        ttk.Button(box, text="Effacer calibration",
                   command=self._clear_calib).pack(fill="x", pady=1)
        self.lbl_dark = ttk.Label(box, text="Dark : —", foreground="#888888")
        self.lbl_dark.pack(anchor="w")
        self.lbl_flat = ttk.Label(box, text="Flat : —", foreground="#888888")
        self.lbl_flat.pack(anchor="w")

        # --- Empilement
        box = ttk.LabelFrame(left, text="Empilement", padding=6)
        box.pack(fill="x", pady=3)
        self.lbl_stats = ttk.Label(box, text="Frames : 0\nPixels rejetés (σ) : 0\nFrames non alignées : 0")
        self.lbl_stats.pack(anchor="w", pady=(0, 3))
        rowf = ttk.Frame(box)
        rowf.pack(fill="x", pady=2)
        ttk.Button(rowf, text="Réinitialiser l'empilement",
                   command=lambda: setattr(self, "reset_request", True)
                   ).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(rowf, text="Réf. = empilement",
                   command=lambda: setattr(self, "ref_request", True)
                   ).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Label(box, text="Rejet kappa-sigma :").pack(anchor="w")
        self.var_kappa = tk.StringVar(value="3σ")
        cb = ttk.Combobox(box, textvariable=self.var_kappa, state="readonly", width=8,
                          values=["Off", "2σ", "3σ", "4σ", "5σ"])
        cb.pack(anchor="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_kappa())

        # --- Affichage
        box = ttk.LabelFrame(left, text="Affichage (temps réel)", padding=6)
        box.pack(fill="x", pady=3)
        self.var_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Auto-stretch STF (fond calé sur la cible)",
                        variable=self.var_auto, command=self._on_auto).pack(anchor="w")
        self.var_sigk = tk.DoubleVar(value=2.8)
        self._add_slider(box, "Coupure du bruit (k·σ sous le fond)",
                         self.var_sigk, 0.5, 5.0, 0.1,
                         lambda: (setattr(self.disp, "sigma_k", self.var_sigk.get()),
                                  self._refresh_preview()), "{:.1f}")
        self.var_target = tk.DoubleVar(value=0.25)
        self._add_slider(box, "Luminosité du fond du ciel",
                         self.var_target, 0.10, 0.45, 0.01,
                         lambda: (setattr(self.disp, "target", self.var_target.get()),
                                  self._refresh_preview()), "{:.2f}")
        ttk.Separator(box).pack(fill="x", pady=4)
        ttk.Label(box, text="Manuel (si auto décoché) :").pack(anchor="w")
        self.var_black = tk.DoubleVar(value=0.0)
        self.var_white = tk.DoubleVar(value=1.0)
        self.scl_black = self._add_slider(box, "Black point", self.var_black, 0.0, 1.0, 0.005,
                                          lambda: (setattr(self.disp, "black", self.var_black.get()),
                                                   self._refresh_preview()), "{:.3f}")
        self.scl_white = self._add_slider(box, "White point", self.var_white, 0.0, 2.0, 0.005,
                                          lambda: (setattr(self.disp, "white", self.var_white.get()),
                                                                                                      self._refresh_preview()), "{:.3f}")
        vg = tk.DoubleVar(value=1.0)
        self.var_gamma = vg
        self._add_slider(box, "Gamma (les 2 modes)", vg, 0.2, 4.0, 0.05,
                         lambda: (setattr(self.disp, "gamma", vg.get()),
                                  self._refresh_preview()), "{:.2f}")
        vs = tk.DoubleVar(value=1.0)
        self.var_saturation = vs
        self._add_slider(box, "Saturation", vs, 0.0, 3.0, 0.05,
                         lambda: (setattr(self.disp, "saturation", vs.get()),
                                  self._refresh_preview()), "{:.2f}")

        # --- Traitement externe (instantané de l'empilement)
        box = ttk.LabelFrame(left, text="Traitement externe (instantané)", padding=6)
        box.pack(fill="x", pady=3)
        self.var_ext_graxpert = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="1. GraXpert — retrait de gradient",
                        variable=self.var_ext_graxpert).pack(anchor="w")
        rowgx = ttk.Frame(box)
        rowgx.pack(fill="x")
        self.var_cmd_graxpert = tk.StringVar(value=DEFAULT_CMD_GRAXPERT)
        ttk.Entry(rowgx, textvariable=self.var_cmd_graxpert).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowgx, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_graxpert)
                   ).pack(side="left", padx=(4, 0))
        self.var_ext_bxt = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="2. BlurXTerminator — netteté",
                        variable=self.var_ext_bxt).pack(anchor="w")
        rowbx = ttk.Frame(box)
        rowbx.pack(fill="x")
        self.var_cmd_bxt = tk.StringVar(value=DEFAULT_CMD_BXT)
        ttk.Entry(rowbx, textvariable=self.var_cmd_bxt).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rowbx, text="…", width=3,
                   command=lambda: self._pick_exe(self.var_cmd_bxt)
                   ).pack(side="left", padx=(4, 0))
        ttk.Label(box, text="Placeholders : {input} · {output} (.fits complet) · "
                           "{outbase} (sans extension, GraXpert). « … » : choisir "
                           "l'exécutable, options conservées.",
                  foreground="#888888", wraplength=310).pack(anchor="w")
        rowv = ttk.Frame(box)
        rowv.pack(fill="x", pady=2)
        self.var_view = tk.StringVar(value="pile")
        ttk.Radiobutton(rowv, text="Vue : empilement", variable=self.var_view, value="pile",
                        command=self._on_view).pack(side="left")
        ttk.Radiobutton(rowv, text="vue traitée", variable=self.var_view, value="traitée",
                        command=self._on_view).pack(side="left")
        self.btn_ext = ttk.Button(box, text="⚡ Traiter l'empilement courant",
                                  command=self._request_ext)
        self.btn_ext.pack(fill="x", pady=2)
        self.btn_save_proc = ttk.Button(box, text="💾 Enregistrer le résultat traité…",
                                        command=self._save_proc, state="disabled")
        self.btn_save_proc.pack(fill="x")
        self.lbl_ext = ttk.Label(box, text="—", foreground="#888888", wraplength=310)
        self.lbl_ext.pack(anchor="w")

        # --- Sortie
        box = ttk.LabelFrame(left, text="Sortie", padding=6)
        box.pack(fill="x", pady=3)
        ttk.Button(box, text="💾 Enregistrer l'empilement…", command=self._save).pack(fill="x")

        # --- Panneau droit
        right = ttk.Frame(main)
        main.add(right, weight=1)
        self.cv_img = tk.Canvas(right, width=self.W_IMG, height=self.H_IMG,
                                bg="black", highlightthickness=0)
        self.cv_img.pack(fill="both", expand=True)
        self.cv_hist = tk.Canvas(right, width=self.W_HIST, height=self.H_HIST,
                                 bg="#101010", highlightthickness=0)
        self.cv_hist.pack(fill="x")
        self.lbl_status = ttk.Label(right, text="Prêt. Choisissez une source puis cliquez Démarrer.\n"
                                               "Molette sur l'image : zoom · glisser : déplacer · "
                                               "double-clic : ajuster",
                                    anchor="w")
        self.lbl_status.pack(fill="x")

        # Zoom / pan sur l'image
        self.cv_img.bind("<MouseWheel>", self._on_wheel_zoom)   # Windows / macOS
        self.cv_img.bind("<Button-4>", self._on_wheel_zoom)    # Linux
        self.cv_img.bind("<Button-5>", self._on_wheel_zoom)
        self.cv_img.bind("<Button-1>", self._on_img_press)
        self.cv_img.bind("<B1-Motion>", self._on_img_drag)
        self.cv_img.bind("<ButtonRelease-1>", self._on_img_release)
        self.cv_img.bind("<Double-Button-1>", self._on_img_dblclick)
        self.cv_img.bind("<Configure>", lambda e: self._render())

    def _add_slider(self, parent, label, var, frm, to, res, onchange=None, fmt="{:g}"):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        head = ttk.Frame(row)
        head.pack(fill="x")
        ttk.Label(head, text=label).pack(side="left")
        lab_val = ttk.Label(head, text=fmt.format(var.get()))
        lab_val.pack(side="right")

        def cmd(v):
            var.set(float(v))
            lab_val.config(text=fmt.format(float(v)))
            if onchange:
                onchange()

        s = ttk.Scale(row, from_=frm, to=to, value=var.get(), command=cmd)
        s.pack(fill="x")
        return s

    # ------------------------------------------------------------ callbacks UI
    def _on_kappa(self):
        self.kappa = {"Off": None, "2σ": 2.0, "3σ": 3.0, "4σ": 4.0, "5σ": 5.0}[self.var_kappa.get()]
        if self.stacker:
            self.stacker.k = self.kappa

    def _on_cfa(self, *args):
        global CFA_MODE
        CFA_MODE = self.var_cfa.get()

    def _on_auto(self):
        self.disp.auto = self.var_auto.get()
        if not self.disp.auto:  # fige les réglages sur les points calculés par l'auto
            self.var_black.set(round(self.disp.last_lo, 4))
            self.var_white.set(round(self.disp.last_hi, 4))
            self.scl_black.set(self.var_black.get())
            self.scl_white.set(self.var_white.get())
        self._refresh_preview()

    def _on_view(self):
        """Bascule empilement ↔ résultat traité (stats d'étirement réinitialisées :
        les niveaux après GraXpert/BXT ne sont pas les mêmes)."""
        self.disp.reset()
        if self.var_view.get() == "traitée":
            if self.proc_show is not None:
                self.last_show = self.proc_show
                self._show_image(self.disp.process(self.last_show, live=False))
            else:
                self._set_ext_msg("Aucun résultat traité — cliquez « ⚡ Traiter » d'abord.")
        else:
            if self.show_stack is not None:
                self.last_show = self.show_stack
                self._show_image(self.disp.process(self.last_show, live=False))

    def _refresh_preview(self):
        """Re-rend l'aperçu immédiatement après un réglage (indispensable en mode
        dossier : pas de frame régulière pour rafraîchir l'écran).
        live=False : ne fait pas avancer le lissage temporel des stats."""
        if self.last_show is not None:
            self._show_image(self.disp.process(self.last_show, live=False))

    def _push_settings(self):
        if self.camera is not None:
            self.pending_settings = (self.var_expo.get(), self.var_gain.get())

    def _make_camera(self, key):
        if key.startswith("Simulée"):
            return SimulatedCamera()
        if key.startswith("Dossier"):
            folder = self.var_folder.get().strip()
            if not folder:
                raise RuntimeError("Choisissez d'abord le dossier à surveiller (bouton …)")
            return FolderCamera(folder, process_existing=self.var_process_existing.get())
        if key.startswith("OpenCV"):
            return OpenCVCamera(int(key.split()[-1]))
        return ZWOASICamera()

    def _pick_folder(self):
        d = filedialog.askdirectory(title="Dossier où arrivent les brutes")
        if d:
            self.var_folder.set(d)

    def _start(self):
        if self.running:
            return
        try:
            cam = self._make_camera(self.var_source.get())
            cam.open()
            cam.apply_settings(self.var_expo.get(), self.var_gain.get())
        except Exception as e:
            messagebox.showerror("Caméra", str(e))
            return
        self.camera = cam
        self.aligner = StarAligner()
        self.stacker = None
        self.disp.reset()                      # stats d'affichage repartent de zéro
        self.bad_frames, self.fps = 0, 0.0
        self.show_stack = None
        self.last_show = None
        self._session += 1                     # invalide tout traitement externe en vol
        self.proc_show = self.proc_full = None
        self.proc_new = False
        self.ext_request = False
        self.ext_busy = False
        self.ext_state = "idle"
        self.ext_t0 = None
        self._ext_popup = False
        self.btn_save_proc.config(state="disabled")
        self.zoom, self.view_cx, self.view_cy = 1.0, None, None
        self._last_disp = None
        self.q = queue.Queue(maxsize=2)
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

    def _stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
            self.thread = None
        if self.camera:
            self.camera.close()
            self.camera = None
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="Arrêté.")

    def _on_close(self):
        self._sauver_config_app()
        self._stop()
        self.root.destroy()

    def _save(self):
        if not self.running or self.stacker is None or self.stacker.n == 0:
            messagebox.showinfo("Enregistrer", "Aucun empilement à enregistrer.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")])
        if path:
            self.save_request = path  # la sauvegarde est faite par le thread d'acquisition

    def _load_dark(self):
        p = filedialog.askopenfilename(filetypes=[
            ("Images", "*.fits *.fit *.fts *.png *.tif *.tiff *.jpg *.jpeg"), ("Tous", "*.*")])
        if p:
            try:
                self.calib.load_dark(p)
                h, w = self.calib.dark.shape[:2]
                self.lbl_dark.config(text=f"Dark : {os.path.basename(p)}  ({h}×{w})",
                                     foreground="#1d7f1d")
                msg = f"Dark chargé : {p}"
                if self.running:
                    msg += "  —  pensez à « Réinitialiser l'empilement » pour que tout soit calibré pareil"
                self.lbl_status.config(text=msg)
            except Exception as e:
                messagebox.showerror("Dark", str(e))

    def _load_flat(self):
        p = filedialog.askopenfilename(filetypes=[
            ("Images", "*.fits *.fit *.fts *.png *.tif *.tiff *.jpg *.jpeg"), ("Tous", "*.*")])
        if p:
            try:
                self.calib.load_flat(p)
                h, w = self.calib.flat.shape[:2]
                self.lbl_flat.config(text=f"Flat : {os.path.basename(p)}  ({h}×{w})",
                                     foreground="#1d7f1d")
                msg = f"Flat chargé : {p}"
                if self.running:
                    msg += "  —  pensez à « Réinitialiser l'empilement » pour que tout soit calibré pareil"
                self.lbl_status.config(text=msg)
            except Exception as e:
                messagebox.showerror("Flat", str(e))

    def _clear_calib(self):
        self.calib.clear()
        self.lbl_dark.config(text="Dark : —", foreground="#888888")
        self.lbl_flat.config(text="Flat : —", foreground="#888888")

    # ------------------------------------------------------------ traitement externe
    def _pick_exe(self, var):
        """Sélectionne l'exécutable d'un outil externe et le place en tête de
        la commande — les options déjà saisies ({input}, {output}…) sont
                conservées telles quelles."""
        p = filedialog.askopenfilename(
            title="Exécutable de l'outil",
            filetypes=[("Exécutables", "*.exe *.bat *.cmd *.py" if IS_WINDOWS
                        else "*.py *.sh *.AppImage"),
                       ("Tous les fichiers", "*.*")])
        if not p:
            return
        cmd = var.get().strip()
        rest = ""                                  # options existantes à conserver
        if cmd.startswith('"'):
            end = cmd.find('"', 1)
            if end != -1:
                rest = cmd[end + 1:].strip()
        elif cmd:
            parts = cmd.split(None, 1)
            rest = parts[1] if len(parts) > 1 else ""
        var.set(f'"{p}"' + (f" {rest}" if rest else ""))

    def _request_ext(self):
        """Demande un traitement externe sur l'empilement courant (lancé par le worker)."""
        if not self.running or self.stacker is None or self.stacker.n == 0:
            messagebox.showinfo("Traitement externe", "Aucun empilement à traiter.")
            return
        if self.ext_busy:
            messagebox.showinfo("Traitement externe",
                                "Un traitement est déjà en cours — patientez.")
            return
        if not (self.var_ext_graxpert.get() or self.var_ext_bxt.get()):
            messagebox.showinfo("Traitement externe",
                                "Cochez au moins GraXpert ou BlurXTerminator.")
            return
        # Capture des réglages ici (thread principal) : le thread externe ne
        # touchera pas aux variables Tkinter.
        self.ext_job = (self.var_ext_graxpert.get(),
                        self.var_cmd_graxpert.get().strip(),
                        self.var_ext_bxt.get(),
                        self.var_cmd_bxt.get().strip())
        self.ext_request = True
        self._set_ext_msg("Traitement demandé…", state="busy")
        self.btn_ext.config(state="disabled")

    def _set_ext_msg(self, txt, state=None):
        """Message d'état du traitement externe (thread-safe : simple attribut
        relu par _tick, jamais un widget directement depuis un thread).
        state : 'busy' (en cours), 'ok' (terminé), 'error' (échec → popup)."""
        self.ext_msg = txt
        if state:
            self.ext_state = state
            if state == "busy":
                self.ext_t0 = time.time()
            if state == "error":
                self._ext_popup = True

    def _save_proc(self):
        if self.proc_full is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")])
        if path:
            try:
                save_image(path, self.proc_full)
                messagebox.showinfo("Enregistrer", f"Résultat traité sauvegardé :\n{path}")
            except Exception as e:
                messagebox.showerror("Enregistrer", str(e))

    def _run_external(self, stack, n_frames, session):
        """Chaîne les outils externes (GraXpert → BlurXTerminator) sur un
        instantané de l'empilement. Tourne en thread séparé : l'acquisition
        continue pendant ce temps. Le résultat n'affecte QUE l'affichage (vue
        « traitée ») et la sauvegarde dédiée — l'empilement accumulé reste
        linéaire et intact.

        Placeholders des commandes :
          {input}   → fichier FITS d'entrée (instantané de l'empilement, float 32F)
          {output}  → chemin de sortie complet, extension .fits
          {outbase} → chemin de sortie SANS extension (GraXpert : -output)
        Le fichier réellement produit est retrouvé automatiquement (_find_output),
        quelle que soit son extension ou son suffixe (-bxt, _GraXpert…), et un
        éventuel miroir vertical est corrigé (_auto_unflip)."""
        tmp = None
        try:
            use_gx, cmd_gx, use_bxt, cmd_bxt = self.ext_job
            steps = []
            if use_gx:
                steps.append(("GraXpert", cmd_gx))
            if use_bxt:
                steps.append(("BlurXTerminator", cmd_bxt))
            for name, cmd in steps:
                if "{input}" not in cmd or ("{output}" not in cmd and "{outbase}" not in cmd):
                    self._set_ext_msg(f"Commande {name} incomplète : il manque "
                                      "{{input}} ou {output}/{outbase}.", state="error")
                    return
            tmp = tempfile.mkdtemp(prefix="avastack_")
            cur = os.path.join(tmp, "stack.fits")
            save_image(cur, stack)

            def run_step(name, cmd_tpl, src, outbase):
                cmd = (cmd_tpl.replace("{input}", src)
                              .replace("{output}", outbase + ".fits")
                              .replace("{outbase}", outbase))
                self._set_ext_msg(f"{name} en cours… ({n_frames} frames)", state="busy")
                r = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=1800)
                if r.returncode != 0:
                    lines = (r.stderr or r.stdout or "").strip().splitlines()
                    detail = lines[-1] if lines else "aucun message"
                    self._set_ext_msg(f"Erreur {name} (code {r.returncode}) : {detail}",
                                      state="error")
                    return None
                res = _find_output(src, outbase)      # extension/suffixe quelconques
                if res is None:
                    self._set_ext_msg(f"Erreur {name} : fichier de sortie introuvable "
                                      "(l'outil n'a rien écrit)", state="error")
                    return None
                return res

            for i, (name, cmd_tpl) in enumerate(steps):
                outbase = os.path.join(tmp, f"step{i}")
                res = run_step(name, cmd_tpl, cur, outbase)
                if res is None:
                    return
                cur = res

            img = load_image(cur)
            img = _auto_unflip(img, stack)     # corrige un éventuel miroir vertical
            if session != self._session:             # session relancée entre-temps
                return
            self.proc_full = img                     # pleine résolution (sauvegarde)
            h, w = img.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                img = cv2.resize(img, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            self.proc_show = img                     # version allégée (affichage)
            self.proc_new = True
            self._set_ext_msg(f"Traité à {time.strftime('%H:%M:%S')} "
                              f"({n_frames} frames)", state="ok")
        except Exception as e:
            self._set_ext_msg(f"Erreur : {e}", state="error")
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
            if session == self._session:
                self.ext_busy = False

    # ------------------------------------------------------------ thread d'acquisition
    def _worker(self):
        last_good = None
        while self.running:
            t0 = time.perf_counter()

            if self.pending_settings is not None:
                self.camera.apply_settings(*self.pending_settings)
                self.pending_settings = None

            # Traitement externe demandé → thread dédié, l'acquisition continue.
            # Placé AVANT la lecture d'une frame : doit fonctionner même si
            # aucune brute n'arrive (acquisition en pause, dossier silencieux…).
            if self.ext_request and self.stacker is not None and not self.ext_busy:
                stack_now = self.stacker.mean()
                if stack_now is not None:
                    self.ext_request = False
                    self.ext_busy = True
                    threading.Thread(target=self._run_external,
                                     args=(stack_now, self.stacker.n, self._session),
                                     daemon=True).start()

            frame = self.camera.read()
            if frame is None:
                time.sleep(0.005)
                continue
            frame = self.calib.apply(frame)

            # (re)création de l'empilement / nouvelle référence
            if self.reset_request or self.stacker is None or self.stacker.shape != frame.shape:
                self.reset_request = False
                self.stacker = LiveStacker(frame.shape, k=self.kappa)
                self.aligner.reset()
                self.aligner.set_reference(frame)
                self.disp.reset()          # stats d'affichage repartent de zéro

            M, ok = self.aligner.compute(frame)
            if ok:
                aligned = cv2.warpAffine(frame, M, (frame.shape[1], frame.shape[0]),
                                         flags=cv2.INTER_LINEAR)
                self.stacker.add(aligned)
                last_good = aligned
            else:
                self.bad_frames += 1

            stack = self.stacker.mean()

            if self.ref_request and stack is not None:
                self.ref_request = False
                self.aligner.set_reference(stack)   # utile en longue session (rotation de champ)

            if self.save_request is not None and stack is not None:
                path, self.save_request = self.save_request, None
                try:
                    save_image(path, stack)
                    self.saved_path = path
                except Exception as e:
                    self.saved_path = f"ERREUR: {e}"

            show = stack if stack is not None else (last_good if last_good is not None else frame)

            # Aperçu allégé pour l'UI : réactif même en 16 Mpx ; l'étirement est
            # recalculé côté interface → curseurs réactifs entre deux frames.
            h, w = show.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                show = cv2.resize(show, None, fx=scale, fy=scale,
                                  interpolation=cv2.INTER_AREA)
            hist = self._compute_hist(show)

            dt = time.perf_counter() - t0
            inst = 1.0 / max(dt, 1e-4)
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
            st = dict(frames=self.stacker.n, rejets=self.stacker.rejected_total,
                      bad=self.bad_frames, fps=self.fps, cam=self.camera.name,
                      file=getattr(self.camera, "last_file", ""),
                      pending=len(getattr(self.camera, "_pending", [])),
                      failed=getattr(self.camera, "failed", 0))
            try:
                self.q.put_nowait((show, hist, st))
            except queue.Full:
                pass
            time.sleep(max(0.0, 1.0 / 20.0 - (time.perf_counter() - t0)))

    @staticmethod
    def _compute_hist(img):
        hi = float(np.percentile(img, 99.9)) * 1.15 + 1e-6
        chans = [img] if img.ndim == 2 else [img[..., i] for i in range(3)]
        return [np.histogram(c, bins=256, range=(0.0, hi))[0].astype(np.float64) for c in chans]

    # ------------------------------------------------------------ rafraîchissement UI
    def _tick(self):
        try:
            while True:
                show, hist, st = self.q.get_nowait()
                self.show_stack = show
                self._update_status(st)
                self._draw_hist(hist)
                if self.var_view.get() == "pile":     # la vue traitée garde son instantané
                    self.last_show = show
                    self._show_image(self.disp.process(show))
        except queue.Empty:
            pass
        if self.proc_new:
            self.proc_new = False
            self.btn_save_proc.config(state="normal")
            if self.var_view.get() == "traitée" and self.proc_show is not None:
                self.last_show = self.proc_show
                self._show_image(self.disp.process(self.proc_show, live=False))
        if self.ext_msg != self._ext_shown:
            self._ext_shown = self.ext_msg
            self.lbl_ext.config(
                text=self.ext_msg,
                foreground={"busy": "#c98a00", "ok": "#1d7f1d",
                            "error": "#d04040"}.get(self.ext_state, "#888888"))
        if self.ext_busy:                      # chrono pendant le traitement
            self.lbl_ext.config(text=f"{self.ext_msg}  "
                                      f"({time.time() - (self.ext_t0 or time.time()):.0f} s)")
        self.btn_ext.config(state="disabled"
                            if (self.ext_busy or self.ext_request) else "normal")
        if self._ext_popup:
            self._ext_popup = False
            messagebox.showerror("Traitement externe", self.ext_msg)
        if self.saved_path:
            p, self.saved_path = self.saved_path, None
            if p.startswith("ERREUR"):
                messagebox.showerror("Enregistrer", p)
            else:
                messagebox.showinfo("Enregistrer", f"Empilement sauvegardé :\n{p}")
        self.root.after(30, self._tick)

    def _show_image(self, disp):
        """Mémorise la dernière image étirée puis la dessine (zoom/pan conservés)."""
        self._last_disp = disp
        self._render()

    # ------------------------------------------------------------ zoom / pan
    def _on_wheel_zoom(self, e):
        d = getattr(e, "delta", 0)
        if d:
            factor = 1.25 if d > 0 else 0.8
        else:
            factor = 1.25 if getattr(e, "num", 0) == 4 else 0.8
        self._zoom_at(e.x, e.y, factor)
        return "break"                 # ne pas faire défiler le panneau gauche

    def _zoom_at(self, mx, my, factor):
        """Zoom centré sur le curseur : le point de l'image sous la souris
        reste sous la souris après le zoom."""
        if self._last_disp is None:
            return
        ih, iw = self._last_disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        fit = min(cw / iw, ch / ih)                    # échelle « ajuster »
        scale = fit * self.zoom
        vx = self.view_cx if self.view_cx is not None else iw / 2.0
        vy = self.view_cy if self.view_cy is not None else ih / 2.0
        ix = vx + (mx - cw / 2.0) / scale              # point sous le curseur
        iy = vy + (my - ch / 2.0) / scale
        new_zoom = min(32.0, max(1.0, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-9:
            return
        self.view_cx = min(max(ix - (ix - vx) * (self.zoom / new_zoom), 0.0), float(iw))
        self.view_cy = min(max(iy - (iy - vy) * (self.zoom / new_zoom), 0.0), float(ih))
        self.zoom = new_zoom
        self._render()

    def _on_img_press(self, e):
        self._drag = (e.x, e.y)

    def _on_img_drag(self, e):
        if self._drag is None or self._last_disp is None or self.zoom <= 1.0001:
            return
        px, py = self._drag
        self._drag = (e.x, e.y)
        ih, iw = self._last_disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        scale = min(cw / iw, ch / ih) * self.zoom
        if self.view_cx is None:
            self.view_cx = iw / 2.0
        if self.view_cy is None:
            self.view_cy = ih / 2.0
        self.view_cx = min(max(self.view_cx - (e.x - px) / scale, 0.0), float(iw))
        self.view_cy = min(max(self.view_cy - (e.y - py) / scale, 0.0), float(ih))
        self._render()

    def _on_img_release(self, e):
        self._drag = None

    def _on_img_dblclick(self, e):
        self.zoom, self.view_cx, self.view_cy = 1.0, None, None
        self._render()

    def _render(self):
        """Dessine self._last_disp en tenant compte du zoom et du pan."""
        disp = self._last_disp
        if disp is None:
            return
        ih, iw = disp.shape[:2]
        cw = self.cv_img.winfo_width() or self.W_IMG
        ch = self.cv_img.winfo_height() or self.H_IMG
        fit = min(cw / iw, ch / ih)                    # échelle « ajuster »
        scale = fit * self.zoom
        if self.zoom <= 1.0001:                        # vue ajustée, pas de recadrage
            crop, interp = disp, (cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        else:
            vx = self.view_cx if self.view_cx is not None else iw / 2.0
            vy = self.view_cy if self.view_cy is not None else ih / 2.0
            x0, x1 = vx - cw / (2 * scale), vx + cw / (2 * scale)
            y0, y1 = vy - ch / (2 * scale), vy + ch / (2 * scale)
            # recadrage borné aux limites de l'image
            if x1 - x0 >= iw:
                x0, x1 = 0.0, float(iw)
            elif x0 < 0:
                x1 -= x0; x0 = 0.0
            elif x1 > iw:
                x0 -= x1 - iw; x1 = float(iw)
            if y1 - y0 >= ih:
                y0, y1 = 0.0, float(ih)
            elif y0 < 0:
                y1 -= y0; y0 = 0.0
            elif y1 > ih:
                y0 -= y1 - ih; y1 = float(ih)
            xi0, yi0 = int(np.floor(x0)), int(np.floor(y0))
            xi1, yi1 = min(iw, int(np.ceil(x1))), min(ih, int(np.ceil(y1)))
            if xi1 - xi0 < 1 or yi1 - yi0 < 1:
                return
            crop = disp[yi0:yi1, xi0:xi1]
            nw = max(1, int(round((xi1 - xi0) * scale)))
            nh = max(1, int(round((yi1 - yi0) * scale)))
            interp = cv2.INTER_NEAREST if self.zoom >= 2.0 else cv2.INTER_LINEAR
        img = cv2.resize(crop, (nw, nh), interpolation=interp)
        self._photo = ImageTk.PhotoImage(Image.fromarray(img))
        self.cv_img.delete("all")
        self.cv_img.create_image(cw // 2, ch // 2, image=self._photo)
        if self.zoom > 1.01:
            self.cv_img.create_text(8, 8, anchor="nw", fill="#ffd75e",
                                    text=f"zoom ×{self.zoom:.1f}   (double-clic : ajuster)")

    def _draw_hist(self, chans):
        self.cv_hist.delete("all")
        w = self.cv_hist.winfo_width() or self.W_HIST
        h = self.cv_hist.winfo_height() or self.H_HIST
        colors = ["#ff5555", "#55ff55", "#5599ff"] if len(chans) == 3 else ["#bbbbbb"]
        mx = max(float(c.max()) for c in chans) or 1.0
        for arr, col in zip(chans, colors):
            pts = []
            for i in range(256):
                v = float(np.log1p(arr[i]) / np.log1p(mx))
                pts += [i / 255.0 * w, h - v * (h - 4) - 2]
            self.cv_hist.create_line(*pts, fill=col, width=1)

    def _update_status(self, st):
        self.lbl_stats.config(text=(f"Frames : {st['frames']}\n"
                                    f"Pixels rejetés (σ) : {st['rejets']}\n"
                                    f"Frames non alignées : {st['bad']}"))
        extra = ""
        if st.get("pending"):
            extra += f"   |  en attente : {st['pending']}"
        if st.get("failed"):
            extra += f"   |  illisibles : {st['failed']}"
        self.lbl_last.config(text="Dernier fichier : "
                             f"{os.path.basename(st.get('file', '')) or '—'}{extra}")
        self.lbl_status.config(
            text=f"{st['cam']}  |  {st['fps']:.1f} fps  |  "
                 f"{st['frames']} frames empilées (intégration cumulée)")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()