# -*- coding: utf-8 -*-
"""Banc de test autonome caméra QHY — utilise le MÊME code que l'appli.

BANC version 2.18.0 : la sonde ctypes native (plages + roue) vit
désormais dans l'application (avastack/cameras/qhyct.py) — ce banc la
RÉUTILISE via son sous-processus d'isolation (le module embarque sa copie
locale pour rester autonome si la bibliothèque installée est antérieure).

Demande d'Alain (19/09/2026) : déboguer la caméra HORS de l'application,
sans la complexité du live stacking ni la relance des tests de non-
régression. Ce programme réutilise `avastack.cameras.qhy.QHYCamera` TEL
QUEL : détection, ouverture (2 séquences), énumération de TOUS les
contrôles du SDK, flux live affiché.

Contrôles : les 1..63 sont nommés d'après l'enum OFFICIEL du SDK QHY
(crate `qhyccd-rs` 0.1.9 qui sous-tend le paquet PyPI) — gain=6,
offset=7, exposure=8 VÉRIFIÉS en réel ; température=14, PWM=15,
PWM manuel=16, consigne=18. Une valeur 4294967295 (0xFFFFFFFF) est la
SENTINELLE D'ERREUR du SDK : elle marque les contrôles « drapeaux »
(CamBin2x2, Cam8bits, CamIsColor…) qui n'ont pas de valeur numérique.

Refroidissement (TEC) : la MiniCam8M est une caméra REFROIDIE (fiche QHY
« Cooled CMOS astronomy camera », alimentation 12 V nécessaire pour
activer la régulation). Le binding n'expose AUCUNE méthode dédiée au
froid : tout passe par set_param/get_param (cf. « User Manual of
Temperature Control API in QHYCCD SDK », qhyccd.com) — mode AUTO =
set_param(18, consigne °C), mode MANUEL = set_param(16, PWM 0-255),
lectures = get_param(14) température et (15) PWM courant.

`🔬 API du SDK` : introspection de tout ce que le binding expose (le
refroidissement, par exemple, n'a pas de méthode dédiée — preuve à
l'appui).

Sonde ctypes native (ajout du 20/09/2026, voie validée par Alain) : la
section « Sonde ctypes » appelle qhyccd.dll DIRECTEMENT (sans le binding)
pour lire les PLAGES des contrôles (GetQHYCCDParamMinMaxStep — absente du
binding) et piloter la ROUE INTÉGRÉE (IsQHYCCDCFWPlugged /
GetQHYCCDCFWStatus / SendOrder2QHYCCDCFW). Elle tourne dans un
SOUS-PROCESSUS isolé (état SDK propre, un éventuel segfault natif ne tue
que l'enfant) et refuse de tourner pendant que le flux est actif : une
caméra ne doit JAMAIS être ouverte deux fois.

IMPORTANT — crash natif : si la fenêtre se ferme brutalement sans
message, c'est un segfault du SDK natif (Python ne peut rien afficher).
Ouvre alors le log d'étapes (bouton « 📄 Ouvrir le log » ou fichier
avastack_qhy_debug.log du dossier temp) : la DERNIÈRE ligne indique
l'étape fatale — c'est elle qu'il faut rapporter.

Deux façons de démarrer, UN SEUL chemin de code applicatif :
  - « ▶ Démarrer (QHYCamera.open(), séquence APPLI) » : appelle exactement
    ce que fait l'appli (QHYCamera.open), en transmettant la ROI saisie si
    la copie de qhy.py installée sait l'accepter ;
  - case « forcer côté banc » : contourne l'appli et pose la ROI depuis le
    banc (l'ancien « pas-à-pas ») — utile pour distinguer un défaut du code
    applicatif d'un simple problème de copie de fichiers.

Lancement (venv, dossier contenant avastack/) :
    venv/Scripts/python.exe _diag_camera_qhy.py
Sur le miniPC installé : copier CE FICHIER dans le dossier d'installation
(%LOCALAPPDATA%/AVAStack) puis :
    venv/Scripts/python.exe _diag_camera_qhy.py

⚠ À LIRE AVANT D'INTERPRÉTER UN ÉCHEC : le banc et avastack/cameras/qhy.py
doivent venir de la MÊME version. Le 19/09/2026, un banc récent exécuté sur
un qhy.py ANTÉRIEUR (v2.13.1, sans set_resolution) a produit exactement les
symptômes d'un vrai bug : « Démarrer » qui ferme la fenêtre, case ROI qui
semble ignorée. En haut de la fenêtre, le banc AFFICHE donc les fichiers
réellement chargés (chemins, dates, présence de set_resolution, signature de
open()) : à vérifier AU MOINS une fois avant de me rapporter un plantage.
"""
import ctypes
import inspect
import json
import os
import sys
import queue
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import Image, ImageTk

# Le banc importe le code de l'application depuis SON PROPRE dossier
# (fonctionne depuis le dépôt comme depuis %LOCALAPPDATA%/AVAStack).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import avastack.cameras.qhy as mqhy
from avastack.cameras.qhy import QHYCamera

FICHIER_LOG = mqhy.FICHIER_TRACE

# Version PROPRE DU BANC : « avastack version » (ci-dessous) est celle de la
# BIBLIOTHÈQUE installée, qui peut être antérieure au banc — c'est ce qui a
# semé la confusion du 20/09 (log « 2.16.0 » alors que le banc était en
# 2.17.0). Les deux sont affichées séparément.
BANC_VERSION = "2.17.2"

# Enum `Control` OFFICIEL du SDK QHY — source : crate Rust `qhyccd-rs` 0.1.9
# (docs.rs), celle qui sous-tend le paquet PyPI `qhyccd`. Les clés sont les
# discriminants de l'enum. VÉRIFIÉ en réel (Alain, 19/09/2026) : gain (6),
# offset (7) et exposition µs (8) posés via le binding sont relus à
# l'identique — 3 relevés concordants. L'id 38 n'existe PAS dans cet enum.
NOMS_CTRL = {
    0: "Brightness", 1: "Contrast", 2: "WBR", 3: "WBB", 4: "WBG",
    5: "Gamma", 6: "GAIN", 7: "OFFSET", 8: "EXPOSURE (µs)", 9: "Speed",
    10: "TransferBit (bits/px)", 11: "Channels", 12: "UsbTraffic",
    13: "RowDeNoise", 14: "CurTemp (°C capteur)", 15: "CurPWM (TEC 0-255)",
    16: "ManualPWM (TEC 0-255)", 17: "CfwPort", 18: "COOLER (consigne °C)",
    19: "St4Port", 20: "CamColor", 21: "CamBin1x1mode", 22: "CamBin2x2mode",
    23: "CamBin3x3mode", 24: "CamBin4x4mode", 25: "CamMechanicalShutter",
    26: "CamTrigerInterface", 27: "CamTecOverprotect",
    28: "CamSignalClamp", 29: "CamFinetone",
    30: "CamShutterMotorHeating", 31: "CamCalibrateFpn",
    32: "CamChipTempSensor", 33: "CamUsbReadoutSlowest", 34: "Cam8bits",
    35: "Cam16bits", 36: "CamGps", 37: "CamIgnoreOverscan",
    39: "Qhyccd3aAutoexposure", 40: "Qhyccd3aAutofocus", 41: "Ampv",
    42: "Vcam", 43: "CamViewMode", 44: "CfwSlotsNum", 45: "IsExposingDone",
    46: "ScreenStretchB", 47: "ScreenStretchW", 48: "DDR",
    49: "CamLightPerformanceMode", 50: "CamQhy5IIGuideMode",
    51: "DDRBufferCapacity", 52: "DDRBufferReadThreshold",
    53: "DefaultGain", 54: "DefaultOffset", 55: "OutputDataActualBits",
    56: "OutputDataAlignment", 57: "CamSingleFrameMode",
    58: "CamLiveVideoMode", 59: "CamIsColor", 60: "HasHardwareFrameCounter",
}
# Sentinelle d'erreur du SDK : GetQHYCCDParam renvoie 0xFFFFFFFF pour un
# contrôle DRAPEAU (sans valeur numérique). L'afficher brute prêtait à
# confusion (constat Alain : « pourquoi 4294967295 partout ? »).
VALEUR_ERREUR = 4294967295.0

# Refroidissement TEC (cf. doc QHY « Temperature Control API »).
CTRL_TEMP = 14        # CurTemp   : température capteur LUE
CTRL_PWM = 15         # CurPWM    : puissance TEC courante (0-255)
CTRL_PWM_MANU = 16    # ManualPWM : puissance imposée → mode MANUEL
CTRL_CONSIGNE = 18    # Cooler    : consigne °C → mode AUTO

# Contrôles balayés par le SÉQUENCEUR : uniquement des RÉGLAGES, jamais des
# contrôles de CONFIGURATION (binning 21-24, profondeur de bits 34-35, mode
# DDR 48-52, modes de flux 57-58). Écrire ces derniers en série laisse la
# caméra dans un état incohérent — le balayage manuel les autorise, mais
# seulement après confirmation explicite.
CTRLS_SEQUENCEUR = (6, 7, 12)      # GAIN, OFFSET, UsbTraffic


def _nom_ctrl(cid):
    """Nom officiel d'un contrôle ('' si l'id n'est pas documenté ici)."""
    return NOMS_CTRL.get(cid, "")


def _fmt_val(val):
    """Valeur de get_param lisible : la sentinelle 0xFFFFFFFF signifie
    « contrôle drapeau, pas de valeur numérique » (CamBin2x2, Cam8bits,
    IsExposingDone…)."""
    try:
        if float(val) == VALEUR_ERREUR:
            return "(drapeau : pas de valeur — sentinelle 0xFFFFFFFF)"
    except (TypeError, ValueError):
        pass
    return str(val)


def _nb(val, suffixe=""):
    """Nombre lisible ; les lectures TEC peuvent échouer → texte brut."""
    try:
        return f"{float(val):.1f}{suffixe}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_duree(v_us):
    """Durée en µs → lisible : « 12 µs », « 3,5 ms », « 2 s », « 3600 s »."""
    v = float(v_us)
    if v >= 1_000_000:
        return f"{v / 1_000_000:g} s"
    if v >= 1000:
        return f"{v / 1000:g} ms"
    return f"{v:g} µs"


def _open_supporte_roi():
    """→ True si le QHYCamera CHARGÉ accepte open(roi=...).

    Garde-fou d'outillage : si le fichier avastack/cameras/qhy.py copié sur
    la machine est ANTÉRIEUR à la v2.13.2, open() n'a pas de paramètre roi et
    n'appelle JAMAIS set_resolution → le SDK plante en natif au premier
    get_live_frame, la fenêtre se ferme, et la ROI cochée paraît « ignorée ».
    On le DIT au lieu de mourir en TypeError.
    """
    try:
        return "roi" in inspect.signature(QHYCamera.open).parameters
    except (TypeError, ValueError):
        return False


def _infos_versions():
    """→ liste de lignes identifiant les fichiers RÉELLEMENT chargés.

    Constat du 19/09/2026 (log du miniPC) : `begin_live` apparaissait SANS
    AUCUN `set_resolution` alors que le code était censé le faire depuis la
    v2.13.2 → les deux fichiers (banc et avastack/cameras/qhy.py) n'avaient
    pas été copiés ENSEMBLE. Un banc récent sur un qhy.py périmé affiche
    exactement les mêmes symptômes qu'un vrai bug : « Démarrer » plante
    (aucune ROI posée → segfault du SDK) alors que le pas-à-pas fonctionne
    (le banc pose la ROI lui-même) et la case ROI semble ignorée. On affiche
    donc l'identité des fichiers au lieu de la deviner.
    """
    import avastack
    from avastack.cameras import qhy as _q
    lignes = []
    try:
        import qhyccd
        lignes.append("paquet qhyccd : " + getattr(qhyccd, "__file__", "?"))
    except Exception as e:
        lignes.append(f"paquet qhyccd : ABSENT ({e})")
    f = getattr(_q, "__file__", "?")
    try:
        mtime = time.strftime("%d/%m/%Y %H:%M:%S",
                              time.localtime(os.path.getmtime(f)))
    except OSError:
        mtime = "?"
    src = ""
    try:
        with open(f, encoding="utf-8", errors="replace") as fichier:
            src = fichier.read()
    except OSError:
        pass
    lignes.append(f"avastack/cameras/qhy.py : {f}")
    lignes.append(f"    modifié le {mtime} — classe chargée : {QHYCamera}")
    lignes.append("    init_sdk unique (_initialiser_sdk) : "
                  + ("OUI" if "_initialiser_sdk" in src else "NON"))
    lignes.append("    set_resolution dans qhy.py : "
                  + ("OUI" if "set_resolution" in src else
                     "NON — fichiers désaccordés ! qhy.py est ANTÉRIEUR à la "
                     "v2.13.2 : la ROI ne sera JAMAIS transmise → segfault"))
    try:
        sig = str(inspect.signature(QHYCamera.open))
    except (TypeError, ValueError):
        sig = "(illisible)"
    lignes.append(f"    signature open() : {sig}"
                  + ("" if _open_supporte_roi() else
                     "  ← PAS de paramètre roi : le banc ne peut pas "
                     "transmettre la case ROI"))
    # DLL native pour la sonde ctypes : identité affichée comme les autres
    # fichiers (une mauvaise DLL imite parfaitement un bug de code).
    _dll_nat = _trouver_dll_qhy()
    if _dll_nat:
        try:
            _md = time.strftime("%d/%m/%Y %H:%M:%S",
                                time.localtime(os.path.getmtime(_dll_nat)))
        except OSError:
            _md = "?"
        lignes.append(f"qhyccd native (sonde ctypes) : {_dll_nat}"
                      f"  (modifiée le {_md})")
    else:
        lignes.append("qhyccd native (sonde ctypes) : INTROUVABLE — "
                      "plages/roue ctypes indisponibles")
    lignes.append(f"banc _diag_camera_qhy.py : {os.path.abspath(__file__)}")
    lignes.append(f"avastack version : {avastack.AVASTACK_VERSION}")
    return lignes


def _dossier_courant():
    """→ dossier de travail au lancement (renseigne sur la copie utilisée)."""
    return os.path.abspath(os.getcwd())


def _taille_log():
    """→ taille courante du fichier de trace (octets), 0 s'il n'existe pas.

    Sert à DÉLIMITER les lignes écrites par une opération précise : on note
    la taille avant, puis on ne relit que ce qui a été ajouté depuis. C'est
    ce qui permet de vérifier ce qu'a RÉELLEMENT fait une ouverture donnée,
    sans être trompé par les traces des essais précédents.
    """
    try:
        return os.path.getsize(FICHIER_LOG)
    except OSError:
        return 0


def _lignes_depuis(offset):
    """→ lignes ajoutées au fichier de trace depuis `offset` (octets)."""
    try:
        with open(FICHIER_LOG, encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            return [l for l in f.read().splitlines() if l.strip()]
    except OSError:
        return []


def _binding_sans_liberation():
    """→ (True, liste) si le binding n'expose AUCUNE libération du SDK.

    Vérifié par introspection le 19/09/2026 : le module `qhyccd` n'expose que
    `Camera`, `init_sdk`, `scan_cameras` (plus des utilitaires de chemins) —
    ni `release_sdk` ni `ReleaseQHYCCDResource`. Conséquence PRATIQUE : après
    une fermeture, on ne peut PAS réinitialiser l'état global du SDK dans le
    même process — d'où le constat « après un Arrêter, Démarrer ne reçoit
    plus jamais de frame ». On le DIT au lieu de le laisser deviner.
    """
    try:
        import qhyccd
        noms = [n for n in dir(qhyccd) if not n.startswith("_")]
    except Exception as e:
        return None, [f"module qhyccd illisible ({e})"]
    suspects = [n for n in noms
                if any(m in n.lower() for m in ("release", "deinit",
                                                "close_sdk", "shutdown",
                                                "cleanup", "finalize"))]
    return (not suspects), noms


# ============================================================================
# SONDE CTYPES NATIVE — qhyccd.dll appelée DIRECTEMENT (sans le binding PyPI)
#
# Voie validée par Alain (19/09/2026) : le binding n'expose AUCUNE fonction de
# plages ; la fonction native existe et s'appelle GetQHYCCDParamMinMaxStep
# (« GetQHYCCDParamMinMax » tout court N'EXISTE PAS) — vérifié le 20/09/2026
# dans les exports RÉELS de la DLL livrée avec le paquet (parseur PE : 328
# exports, dont aussi IsQHYCCDCFWPlugged, GetQHYCCDCFWStatus,
# SendOrder2QHYCCDCFW, GetQHYCCDFWVersion et tout le cycle de vie du SDK).
#
# Signatures reprises de l'en-tête OFFICIEL du SDK (qhyccd.h +
# qhyccdstruct.h) ; l'enum CONTROL_ID y est IDENTIQUE à la table NOMS_CTRL
# ci-dessus (gain=6, offset=7, exposure µs=8 — cohérent avec le relevé réel
# du binding) :
#     uint32_t InitQHYCCDResource(void);
#     uint32_t ReleaseQHYCCDResource(void);
#     uint32_t ScanQHYCCD(void);                       -> nb de caméras
#     uint32_t GetQHYCCDId(uint32_t index, char *id);
#     uint32_t GetQHYCCDModel(char *id, char *model);
#     qhyccd_handle *OpenQHYCCD(char *id);             -> NULL si échec
#     uint32_t CloseQHYCCD(qhyccd_handle *handle);
#     double   GetQHYCCDParam(qhyccd_handle *h, int controlId);
#     uint32_t GetQHYCCDParamMinMaxStep(qhyccd_handle *h, int controlId,
#                 double *min, double *max, double *step);
#     uint32_t IsQHYCCDControlAvailable(qhyccd_handle *h, int controlId);
#                 -> 0 = contrôle DISPONIBLE (même convention que la roue :
#                 QHYCCD_SUCCESS ; confirmé par le driver INDI)
#     uint32_t IsQHYCCDCFWPlugged(qhyccd_handle *h);   -> 0 = CFW TROUVÉ
#                 (doc QHY « User Manual of Filter Wheel APIs » :
#                 QHYCCD_SUCCESS = roue branchée — PAS un booléen « vrai »)
#     uint32_t GetQHYCCDCFWStatus(qhyccd_handle *h, char *status);
#                 -> status[0] = caractère ASCII '0'..'F', '0' = position 1
#     uint32_t SendOrder2QHYCCDCFW(qhyccd_handle *h, char *order,
#                                  uint32_t length);
#                 -> ordre = 1 SEUL caractère ASCII, '0' + (position - 1)
#     uint32_t GetQHYCCDFWVersion(qhyccd_handle *h, uint8_t *buf);
# Conventions roue (même doc) : boucle de relecture avec pause de 0,5 s
# (éviter le spam USB), timeout conseillé 25 s ; la rotation n'est confirmée
# que lorsque le statut relu = le caractère envoyé.
#
# ISOLEMENT : la sonde tourne dans un SOUS-PROCESSUS (même mécanique que
# lister_via_sous_processus) — Init/Release du SDK y sont SANS DANGER pour
# l'état du banc (un 2e init DANS CE process est un suspect de crash
# documenté ci-dessus), et un segfault natif ne tue que l'enfant. Le parent
# refuse d'ailleurs de lancer la sonde si le flux est actif : une caméra ne
# doit JAMAIS être ouverte deux fois (constat du 19/09/2026).
#
# Sortie de l'enfant : des lignes « # ... » (progression, ASCII
# volontairement PUR — un caractère hors cp1252 ferait planter le décodage
# du tube, cf. piège consigné) puis UNE ligne JSON (ensure_ascii).
# ============================================================================


def _trouver_dll_qhy():
    """→ chemin de la bibliothèque native QHYCCD, ou None.

    Ordre de recherche : AVASTACK_QHY_DIR (fichier ou dossier) → DLL
    embarquée du paquet qhyccd (le MÊME fichier que déclare le binding via
    os.add_dll_directory — les résultats restent donc comparables) →
    dossier du banc → nom nu (PATH).
    Piège corrigé le 20/09 : une VIEILLE qhyccd.dll traînait à la racine du
    projet (vestige gitignoré d'essais antérieurs) et MASQUAIT la DLL
    récente du paquet quand le banc est cherché avant le paquet.
    """
    noms = ("qhyccd.dll", "libqhyccd.so", "libqhyccd.dylib")
    candidats = []
    env = os.environ.get("AVASTACK_QHY_DIR")
    if env:
        candidats.append(env if os.path.isfile(env)
                         else os.path.join(env, noms[0]))
    try:
        import qhyccd as _paquet
        # La DLL embarquée du paquet peut vivre DANS son dossier
        # (.../qhyccd/vendor/lib) ou À CÔTÉ (…/site-packages/vendor/lib —
        # vérifié en réel le 20/09/2026 : c'est le second) → on teste les
        # deux racines, avec descente récursive.
        ici_paquet = os.path.dirname(os.path.abspath(_paquet.__file__))
        racines = [os.path.join(ici_paquet, "vendor"),
                   os.path.join(os.path.dirname(ici_paquet), "vendor")]
        for vend in racines:
            if os.path.isdir(vend):
                for rac, _sous, fichiers in os.walk(vend):
                    for n in noms:
                        if n in fichiers:
                            candidats.append(os.path.join(rac, n))
    except Exception:
        pass
    banc = os.path.dirname(os.path.abspath(__file__))
    candidats.extend(os.path.join(banc, n) for n in noms)
    candidats.extend(noms)            # PATH système (en dernier recours)
    for c in candidats:
        if c and os.path.isfile(c):
            return c
    return None


def _charger_fonctions_qhy(chemin):
    """Charge la DLL et FIXE les prototypes (restype/argtypes).

    Sans prototypes, ctypes renvoie des entiers tronqués pour les fonctions
    à double (leçon v2.16 : température lue en bits) — chaque fonction est
    déclarée explicitement. WinDLL sous Windows (STDCALL de l'en-tête ;
    identique à CDLL en x64, correct en x86), CDLL ailleurs.
    """
    if os.name == "nt":
        try:
            os.add_dll_directory(os.path.dirname(chemin))
        except (AttributeError, OSError):
            pass
        lib = ctypes.WinDLL(chemin)
    else:
        lib = ctypes.CDLL(chemin)
    H = ctypes.c_void_p
    D = ctypes.POINTER(ctypes.c_double)
    fns = {}

    def declare(nom, restype, argtypes):
        f = getattr(lib, nom)
        f.restype = restype
        f.argtypes = argtypes
        fns[nom] = f

    declare("InitQHYCCDResource", ctypes.c_uint32, [])
    declare("ReleaseQHYCCDResource", ctypes.c_uint32, [])
    declare("ScanQHYCCD", ctypes.c_uint32, [])
    declare("GetQHYCCDId", ctypes.c_uint32,
            [ctypes.c_uint32, ctypes.c_char_p])
    declare("GetQHYCCDModel", ctypes.c_uint32,
            [ctypes.c_char_p, ctypes.c_char_p])
    declare("OpenQHYCCD", H, [ctypes.c_char_p])
    declare("CloseQHYCCD", ctypes.c_uint32, [H])
    declare("SetQHYCCDStreamMode", ctypes.c_uint32, [H, ctypes.c_ubyte])
    declare("InitQHYCCD", ctypes.c_uint32, [H])
    declare("GetQHYCCDParam", ctypes.c_double, [H, ctypes.c_int])
    declare("GetQHYCCDParamMinMaxStep", ctypes.c_uint32,
            [H, ctypes.c_int, D, D, D])
    declare("IsQHYCCDControlAvailable", ctypes.c_uint32, [H, ctypes.c_int])
    declare("IsQHYCCDCFWPlugged", ctypes.c_uint32, [H])
    declare("GetQHYCCDCFWStatus", ctypes.c_uint32, [H, ctypes.c_char_p])
    declare("SendOrder2QHYCCDCFW", ctypes.c_uint32,
            [H, ctypes.c_char_p, ctypes.c_uint32])
    declare("GetQHYCCDFWVersion", ctypes.c_uint32,
            [H, ctypes.POINTER(ctypes.c_ubyte)])
    return fns


def _sonde_plages(fns, h, res, info):
    """Lit disponibilité + MinMaxStep + valeur de chaque contrôle (0..62)."""
    controles = {}
    indispo = []
    rc_dispo = {}                     # codes bruts de IsQHYCCDControlAvailable
    for cid_ in range(0, 63):        # 0..62 : jusqu'à CAM_HUMIDITY (enum)
        nom = _nom_ctrl(cid_)
        d = fns["IsQHYCCDControlAvailable"](h, cid_)
        if d != 0:
            # 0 = QHYCCD_SUCCESS = contrôle DISPONIBLE (convention du SDK
            # entier, cf. IsQHYCCDCFWPlugged ; confirmé par le driver INDI :
            # « ... == QHYCCD_SUCCESS »). Constat réel 20/09 : 26 réponses 0
            # = les contrôles disponibles, 37 × 0xFFFFFFFF = id inconnus.
            indispo.append(cid_)
            rc_dispo[str(d)] = rc_dispo.get(str(d), 0) + 1
            continue
        mn, mx, st = (ctypes.c_double(), ctypes.c_double(),
                      ctypes.c_double())
        rc = fns["GetQHYCCDParamMinMaxStep"](h, cid_, ctypes.byref(mn),
                                             ctypes.byref(mx),
                                             ctypes.byref(st))
        val = fns["GetQHYCCDParam"](h, cid_)
        e = {"nom": nom, "val": val}
        if val == VALEUR_ERREUR:
            e["val_txt"] = "drapeau (0xFFFFFFFF)"
        if rc == 0:
            e["min"], e["max"], e["step"] = mn.value, mx.value, st.value
            if mn.value > mx.value or (mn.value == 0.0 and mx.value == 0.0):
                e["doute"] = "plage incohérente (min>max ou min=max=0)"
        else:
            e["rc_minmax"] = rc
        controles[str(cid_)] = e
        info("ctrl %2d %-24s valeur=%s  %s"
             % (cid_, nom, e.get("val_txt", val),
                ("plage=[%g .. %g] pas=%g" % (mn.value, mx.value, st.value))
                if rc == 0 else "pas de plage (rc=%d)" % rc))
    res["controles"] = controles
    res["indisponibles"] = indispo
    res["dispo_rc"] = rc_dispo
    info("(%d contrôles disponibles, %d indisponibles)"
         % (len(controles), len(indispo)))


def _sonde_cfw(fns, h, res, action, slot, info):
    """Roue intégrée via les fonctions CFW natives (« Filter Wheel APIs »).

    IsQHYCCDCFWPlugged -> 0 = roue TROUVÉE ; statut et ordre sont des
    caractères ASCII ('0' = position 1) ; le contrôle 44 (CfwSlotsNum)
    renvoie 9 sur les caméras qui ne savent PAS le lire (doc QHY).
    """
    cfw = {}
    plugged = fns["IsQHYCCDCFWPlugged"](h)
    cfw["plugged_rc"] = plugged
    cfw["plugged"] = (plugged == 0)
    val44 = fns["GetQHYCCDParam"](h, 44)          # CONTROL_CFWSLOTSNUM
    cfw["slots_param"] = None if val44 == VALEUR_ERREUR else val44
    info("IsQHYCCDCFWPlugged -> %d %s"
         % (plugged, "(0 = roue TROUVEE)" if plugged == 0
            else "(non nul : pas de roue detectee)"))
    info("CONTROL_CFWSLOTSNUM (ctrl 44) -> %s (9 = lecture non supportee, "
         "doc QHY)" % val44)
    buf = ctypes.create_string_buffer(128)
    rc = fns["GetQHYCCDCFWStatus"](h, buf)
    cfw["status_rc"] = rc
    cfw["status"] = buf.value.decode("ascii", "replace")
    info("GetQHYCCDCFWStatus -> rc=%d, statut=%r" % (rc, cfw["status"]))
    if action == "cfw_order":
        ascii_ordre = ord('0') + int(slot) - 1    # '0' = position 1 (doc QHY)
        cfw["envoyee"] = {"position": int(slot), "ascii": chr(ascii_ordre)}
        rc = fns["SendOrder2QHYCCDCFW"](h, bytes([ascii_ordre]), 1)
        cfw["send_rc"] = rc
        info("SendOrder2QHYCCDCFW(position %d, ASCII %r) -> rc=%d"
             % (int(slot), chr(ascii_ordre), rc))
        etats = []
        confirme = False
        t0 = time.monotonic()
        while time.monotonic() - t0 < 25.0:       # timeout doc QHY : 25 s
            time.sleep(0.5)                       # pause doc QHY : 0,5 s
            b2 = ctypes.create_string_buffer(128)
            fns["GetQHYCCDCFWStatus"](h, b2)
            s = b2.value.decode("ascii", "replace")
            if not etats or etats[-1] != s:
                etats.append(s)
                if s:
                    info("  statut relu : %r (position %d)"
                         % (s, ord(s[0]) - ord('0') + 1))
                else:
                    info("  statut relu : (vide)")
            if s and ord(s[0]) == ascii_ordre:
                confirme = True
                break
        cfw["etats"] = etats
        cfw["confirme"] = confirme
        cfw["final"] = etats[-1] if etats else None
        info("position CONFIRMEE par relecture" if confirme
             else "PAS de confirmation en 25 s (voir statuts relus)")
    res["cfw"] = cfw


def _sonde_ctypes(action, camera_id, slot):
    """Corps de la sonde, exécuté DANS L'ENFANT (sous-processus)."""
    res = {"ok": False, "action": action, "erreurs": []}

    def err(msg):
        res["erreurs"].append(msg)
        print("# ERREUR : " + msg, flush=True)

    def info(msg):
        print("# " + msg, flush=True)

    chemin = _trouver_dll_qhy()
    if chemin is None:
        err("qhyccd.dll introuvable (ni AVASTACK_QHY_DIR, ni dossier du "
            "banc, ni DLL embarquee du paquet qhyccd, ni PATH)")
        return res
    res["dll"] = chemin
    try:
        dte = time.strftime("%Y-%m-%d %H:%M:%S",
                            time.localtime(os.path.getmtime(chemin)))
    except OSError:
        dte = "?"
    info("DLL chargee : %s (mtime %s)" % (chemin, dte))
    try:
        fns = _charger_fonctions_qhy(chemin)
    except Exception as e:
        err("chargement ctypes impossible : " + repr(e))
        return res
    rc = fns["InitQHYCCDResource"]()
    info("InitQHYCCDResource -> %d (0 = OK ; deja initialise : tolere)" % rc)
    n = fns["ScanQHYCCD"]()
    if n == 0 or n > 1024:
        err("ScanQHYCCD -> %d : aucune camera exploitable (branchee ? "
            "alimentation 12 V ? driver ?)" % n)
        return res
    ids = []
    for i in range(n):
        buf = ctypes.create_string_buffer(128)   # sur-allocation (leçon SVB)
        if fns["GetQHYCCDId"](i, buf) == 0 and buf.value:
            ids.append(buf.value.decode("utf-8", "replace"))
    res["ids"] = ids
    info("ScanQHYCCD -> %d camera(s) : %s"
         % (n, ", ".join(ids) or "(aucun id lisible)"))
    if not ids:
        err("des cameras sont vues mais aucun id n'a pu etre lu")
        return res
    cid = camera_id if camera_id in ids else ids[0]
    res["cid"] = cid
    bufm = ctypes.create_string_buffer(128)
    if fns["GetQHYCCDModel"](cid.encode(), bufm) == 0:
        res["model"] = bufm.value.decode("utf-8", "replace")
    info("lecture sur id=%r modele=%r" % (cid, res.get("model", "?")))
    h = fns["OpenQHYCCD"](cid.encode())
    if not h:
        err("OpenQHYCCD -> handle NULL (ouverture refusee)")
        return res
    info("OpenQHYCCD -> handle OK")
    # Initialisation par handle : OBLIGATOIRE avant les lectures de
    # contrôles (constat réel 20/09 : sans elle, IsQHYCCDControlAvailable
    # répond « non disponible » pour TOUT, alors que la roue CFW répond
    # quand même). Même logique que la séquence binding du banc :
    # set_stream_mode puis init().
    rcs = fns["SetQHYCCDStreamMode"](h, 1)
    info("SetQHYCCDStreamMode(h, 1) -> %d (0 = OK)" % rcs)
    rci = fns["InitQHYCCD"](h)
    info("InitQHYCCD(h) -> %d (0 = OK) — initialisation par handle" % rci)
    if rci != 0:
        err("InitQHYCCD a echoue (%d) : les plages seront probablement "
            "vides" % rci)
    try:
        if action == "plages":
            _sonde_plages(fns, h, res, info)
        elif action in ("cfw_status", "cfw_order"):
            _sonde_cfw(fns, h, res, action, slot, info)
        else:
            err("action inconnue : " + action)
    finally:
        rcc = fns["CloseQHYCCD"](h)
        info("CloseQHYCCD -> %d (0 = OK)" % rcc)
    rc = fns["ReleaseQHYCCDResource"]()
    info("ReleaseQHYCCDResource -> %d (0 = OK)" % rc)
    res["ok"] = not res["erreurs"]
    return res


def _ctypes_main(argv):
    """Point d'entrée de l'ENFANT : _diag_camera_qhy.py --ctypes-sonde ..."""
    action = argv[2] if len(argv) > 2 else "plages"
    cid = argv[3] if len(argv) > 3 else ""
    slot = int(argv[4]) if len(argv) > 4 else 1
    try:
        res = _sonde_ctypes(action, cid, slot)
    except Exception as e:
        print("# EXCEPTION : " + repr(e), flush=True)
        res = {"ok": False, "action": action, "erreurs": [repr(e)]}
    print(json.dumps(res, ensure_ascii=True), flush=True)
    return 0


# (fusion du 19/09/2026 : UNE SEULE définition de _infos_versions() et de
#  _open_supporte_roi() — les doublons qui suivaient écrasaient la version la
#  plus informative, seule conservée ci-dessus. Une redéfinition silencieuse
#  est exactement le genre de piège que ce banc doit éviter.)


class BancQHY:
    def __init__(self, root):
        self.root = root
        self.cam = None              # QHYCamera (même classe que l'appli)
        self.camera_id = ""          # id détecté (scan)
        self._flux_actif = False
        self._aperçu = None          # dernière frame float32 [0..1]
        self._photo = None
        self._dims = "—"
        self._froid = None           # (temp °C, PWM, consigne °C) du TEC
        # Cadence de test : on RALENTIT volontairement la boucle pour voir
        # chaque frame s'installer (l'œil ne perçoit rien à 30 fps) et pour
        # horodater l'arrivée des premières — diagnostic des « pas de
        # frame ». `_pause` gèle la lecture SANS fermer la caméra.
        self._total = 0              # frames reçues depuis le démarrage
        self._derniere = 0.0         # horodatage de la dernière frame
        self._pause = False          # test de cadence : on ne lit PLUS rien
        self._expo_s = 0.1           # exposition courante (s) pour l'affichage
        self._pause_txt = ""         # compte à rebours de pause (affichage)
        self._roi_txt = "—"          # ce qui a été transmis à open()
        self._balayage_resume = None  # résumé du dernier balayage (affichage)
        # Caméra déjà ouverte PUIS fermée dans ce process : l'état global du
        # SDK natif n'est PAS réinitialisable (aucune fonction de libération
        # dans le binding) — la 2e ouverture est à risque (constat réel).
        self._deja_ouverte = False
        self._ctypes_occupe = False   # sonde ctypes déjà en cours ?
        self._lbl_ctypes_txt = None   # maj de l'étiquette sonde (via _tick)
        self._fps = 0.0
        self._n = 0
        self._t0 = 0.0
        self.q_msg = queue.Queue()   # messages thread → UI (jamais de Tk
                                     # hors thread principal)
        self._lbl_cam_txt = None
        self._btn_demande = None     # "flux" | "libre" (consommé par _tick)
        self._construire()
        self._log_direct(f"Log d'étapes : {FICHIER_LOG}")
        self._log_direct("Si la fenêtre meurt sans message : crash natif du "
                         "SDK — regarde le log (bouton 📄).")
        # Identité des fichiers chargés : affichée AVANT toute manip, parce
        # qu'une copie périmée de qhy.py imite parfaitement un bug du code
        # (constat du 19/09/2026 : begin_live sans set_resolution dans le log
        # alors que le fichier était censé être à jour).
        self._log_direct("=== fichiers réellement chargés ===")
        self._log_direct("dossier courant : " + _dossier_courant())
        for ligne in _infos_versions():
            self._log_direct(ligne)
        self._log_direct(f"case ROI transmise à open() : "
                         f"{'OUI' if _open_supporte_roi() else 'NON'}")
        self._log_direct(f"BANC version : {BANC_VERSION} (la sonde ctypes "
                         f"plages/roue n'existe qu'à partir de la 2.17.0 — "
                         f"si cette ligne manque ou dit 2.16, le banc "
                         f"exécuté est l'ANCIEN : remplacer "
                         f"_diag_camera_qhy.py)")
        ok_libre, noms = _binding_sans_liberation()
        if ok_libre:
            self._log_direct(
                "libération du SDK : AUCUNE fonction exposée par le binding ("
                + ", ".join(noms) + ") → après « ■ Arrêter », fermer le banc "
                "et le relancer pour repartir d'un état SDK propre.")
        self.root.after(40, self._tick)

    def _trace(self, msg):
        """Trace côté thread : fichier persistant + file → log de l'UI."""
        mqhy._tracer("[diag] " + msg)
        self.q_msg.put(msg)

    def _log_direct(self, msg):
        self.txt.config(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def _construire(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="🔎 Détecter", command=self._detecter).pack(
            side="left")
        self.lbl_cam = ttk.Label(top, text="— cliquer sur « Détecter » —")
        self.lbl_cam.pack(side="left", padx=8)

        box = ttk.LabelFrame(self.root, text="Réglages (transmis à la "
                                              "caméra)", padding=6)
        box.pack(fill="x", padx=6)
        ttk.Label(box, text="Expo (ms)").pack(side="left")
        self.var_expo = tk.StringVar(value="100")
        ttk.Entry(box, textvariable=self.var_expo, width=7).pack(
            side="left", padx=(2, 10))
        ttk.Label(box, text="Gain (unités SDK QHY)").pack(side="left")
        self.var_gain = tk.StringVar(value="10")
        ttk.Entry(box, textvariable=self.var_gain, width=7).pack(
            side="left", padx=(2, 10))
        ttk.Label(box, text="Offset").pack(side="left")
        self.var_offset = tk.StringVar(value="10")
        ttk.Entry(box, textvariable=self.var_offset, width=7).pack(
            side="left", padx=(2, 10))
        self.var_roi = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Imposer la ROI (set_resolution) :",
                        variable=self.var_roi).pack(side="left", padx=(14, 2))
        self.var_w = tk.StringVar(value="3840")   # IMX585 QHY MiniCam8M
        self.var_h = tk.StringVar(value="2160")   # (3864×2192 = fiche Player
        # One, REFUSÉE par le SDK QHY — erreur 0xFFFFFFFF, constat du test)
        ttk.Entry(box, textvariable=self.var_w, width=7).pack(
            side="left", padx=(2, 2))
        ttk.Label(box, text="×").pack(side="left")
        ttk.Entry(box, textvariable=self.var_h, width=7).pack(
            side="left", padx=(2, 0))

        act = ttk.Frame(self.root, padding=6)
        act.pack(fill="x")
        # Il n'y a PLUS qu'un seul bouton de démarrage : il exécute la
        # séquence EXACTE de l'application via QHYCamera.open() — c'est ce
        # chemin qu'il faut valider, pas un chemin parallèle. (Un second
        # bouton « pas-à-pas » maintenait deux séquences divergentes : le
        # diagnostic interrogeait le code de l'appli tout en le contournant.)
        self.btn_start = ttk.Button(
            act, text="▶ Démarrer (QHYCamera.open(), séquence APPLI)",
            command=self._demarrer)
        self.btn_start.pack(side="left")
        self.btn_pause = ttk.Button(act, text="\u23F8 Pause 3 s (cadence)",
                                    command=self._pause_ctrl)
        self.btn_pause.pack(side="left", padx=(6, 0))
        self.btn_stop = ttk.Button(act, text="■ Arrêter",
                                   command=self._arreter, state="disabled")
        self.btn_stop.pack(side="left", padx=(6, 0))
        ttk.Button(act, text="\U0001F4CB Lister les contrôles",
                   command=self._lister_controles).pack(side="left",
                                                        padx=(6, 0))
        ttk.Button(act, text="\U0001F52C API du SDK",
                   command=self._lister_api).pack(side="left", padx=(6, 0))
        ttk.Button(act, text="📄 Ouvrir le log",
                   command=self._ouvrir_log).pack(side="left", padx=(6, 0))
        self.lbl_cadence = ttk.Label(act, text="—")
        self.lbl_cadence.pack(side="left", padx=10)
        ttk.Label(self.root, text="Fichiers réellement chargés (une copie "
                                  "périmée rendrait tout diagnostic faux) :"
                  ).pack(anchor="w", padx=6)
        self.lbl_roi_etat = ttk.Label(self.root, text="ROI transmise : —",
                                      foreground="#1d7f1d")
        self.lbl_roi_etat.pack(anchor="w", padx=6)
        self.var_contourner = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.root, variable=self.var_contourner,
            text="forcer côté banc (poser la ROI depuis le banc, sans passer "
                 "par QHYCamera.open — outil de comparaison)").pack(
            anchor="w", padx=6)

        # Balayage d'un contrôle : l'outil de DÉCOUVERTE DES VALEURS (quelles
        # bornes accepte réellement ce capteur ?). Pose chaque valeur, la
        # relit, note les refus. Indispensable avant de recalibrer les
        # curseurs de l'appli (le gain est aujourd'hui borné à 8 alors que le
        # SDK QHY raisonne en unités constructeur).
        boxb = ttk.LabelFrame(self.root, text="Balayage d'un contrôle "
                                              "(relevé des bornes réelles)",
                              padding=6)
        boxb.pack(fill="x", padx=6, pady=(4, 0))
        ttk.Label(boxb, text="id").pack(side="left")
        self.var_bid = tk.StringVar(value="6")        # gain
        ttk.Entry(boxb, textvariable=self.var_bid, width=5).pack(
            side="left", padx=(2, 8))
        ttk.Label(boxb, text="de").pack(side="left")
        self.var_bmin = tk.StringVar(value="0")
        ttk.Entry(boxb, textvariable=self.var_bmin, width=6).pack(
            side="left", padx=(2, 8))
        ttk.Label(boxb, text="à").pack(side="left")
        self.var_bmax = tk.StringVar(value="100")
        ttk.Entry(boxb, textvariable=self.var_bmax, width=6).pack(
            side="left", padx=(2, 8))
        ttk.Label(boxb, text="pas").pack(side="left")
        self.var_bpas = tk.StringVar(value="10")
        ttk.Entry(boxb, textvariable=self.var_bpas, width=5).pack(
            side="left", padx=(2, 8))
        ttk.Button(boxb, text="▶ Balayer",
                   command=self._balayer).pack(side="left", padx=(2, 0))
        ttk.Button(boxb, text="\U0001F4CA Séquenceur (gain/offset/usb)",
                   command=self._sequenceur).pack(side="left", padx=(6, 0))
        self.lbl_balayage = ttk.Label(boxb, text="—")
        self.lbl_balayage.pack(side="left", padx=10)

        # Écriture d'un contrôle arbitraire (set_param) — pour tester les
        # contrôles non couverts par expo/gain/offset (USB traffic,
        # binning mono…). À manipuler avec prudence.
        boxw = ttk.LabelFrame(self.root,
                              text="Écrire un contrôle (set_param) — "
                                   "prudence !", padding=6)
        boxw.pack(fill="x", padx=6)
        ttk.Label(boxw, text="id ctrl").pack(side="left")
        self.var_cid = tk.StringVar(value="10")
        ttk.Entry(boxw, textvariable=self.var_cid, width=5).pack(
            side="left", padx=(2, 10))
        ttk.Label(boxw, text="valeur").pack(side="left")
        self.var_cval = tk.StringVar(value="")
        ttk.Entry(boxw, textvariable=self.var_cval, width=10).pack(
            side="left", padx=(2, 10))
        ttk.Button(boxw, text="✍ Écrire",
                   command=self._ecrire_ctrl).pack(side="left", padx=(2, 0))

        # Refroidissement TEC — la MiniCam8M est refroidie (spéc. QHY). Le
        # binding n'a AUCUNE méthode « cooler » : on passe par set_param,
        # conformément à la doc QHY « Temperature Control API » :
        #   AUTO   : ctrl 18 = consigne (°C) — régulation par la caméra ;
        #   MANUEL : ctrl 16 = PWM 0-255 — puissance TEC imposée (le SDK
        #            BASCULE en mode manuel dès qu'on écrit 16) ;
        #   lecture: ctrl 14 = température capteur, ctrl 15 = PWM courant.
        # ⚠ Alimentation 12 V OBLIGATOIRE : sans elle le circuit de
        # régulation est inactif (et la température lue n'a pas de sens).
        boxf = ttk.LabelFrame(self.root, text="\u2744 Refroidissement (TEC)"
                                              " — alim. 12 V requise",
                              padding=6)
        boxf.pack(fill="x", padx=6, pady=(4, 0))
        self.lbl_t14 = ttk.Label(boxf, text="temp capteur : —")
        self.lbl_t14.pack(side="left")
        self.lbl_t15 = ttk.Label(boxf, text="PWM TEC : —")
        self.lbl_t15.pack(side="left", padx=(10, 12))
        ttk.Label(boxf, text="Consigne °C").pack(side="left")
        self.var_temp = tk.StringVar(value="0")
        ttk.Entry(boxf, textvariable=self.var_temp, width=6).pack(
            side="left", padx=(2, 2))
        ttk.Button(boxf, text="❄ Réguler (ctrl 18)",
                   command=lambda: self._ecrire_ctrl_valeur(
                       CTRL_CONSIGNE, self.var_temp.get(),
                       "consigne °C")).pack(side="left", padx=(2, 12))
        ttk.Label(boxf, text="PWM 0-255").pack(side="left")
        self.var_pwm = tk.StringVar(value="0")
        ttk.Entry(boxf, textvariable=self.var_pwm, width=5).pack(
            side="left", padx=(2, 2))
        ttk.Button(boxf, text="🎛 Manuel (ctrl 16)",
                   command=lambda: self._ecrire_ctrl_valeur(
                       CTRL_PWM_MANU, self.var_pwm.get(),
                       "PWM manuel")).pack(side="left", padx=(2, 0))
        ttk.Button(boxf, text="Couper le froid (PWM 0)",
                   command=lambda: self._ecrire_ctrl_valeur(
                       CTRL_PWM_MANU, "0", "arrêt TEC")).pack(
            side="left", padx=(6, 0))
        ttk.Button(boxf, text="🔁 Relire",
                   command=self._relire_froid).pack(side="left",
                                                    padx=(6, 0))

        # Sonde ctypes native : qhyccd.dll DIRECTEMENT (le binding n'expose
        # ni les PLAGES (GetQHYCCDParamMinMaxStep) ni la ROUE (CFW*)). La
        # sonde tourne dans un SOUS-PROCESSUS isolé : aucun conflit d'état
        # SDK avec le banc, un segfault natif ne tue que l'enfant. Refus si
        # le flux est actif : une caméra ne doit jamais être ouverte 2 fois.
        boxc = ttk.LabelFrame(self.root,
                              text="Sonde ctypes native (qhyccd.dll direct)"
                                   " — plages des contrôles + roue intégrée",
                              padding=6)
        boxc.pack(fill="x", padx=6, pady=(4, 0))
        ttk.Button(boxc, text="\U0001F4CF Plages (MinMaxStep)",
                   command=self._plages_ctypes).pack(side="left")
        ttk.Label(boxc, text="roue → position").pack(side="left",
                                                     padx=(10, 2))
        self.var_slot = tk.StringVar(value="1")
        ttk.Entry(boxc, textvariable=self.var_slot, width=4).pack(
            side="left")
        ttk.Button(boxc, text="\U0001F300 Tourner (ctypes)",
                   command=self._roue_ctypes).pack(side="left", padx=(4, 0))
        ttk.Button(boxc, text="\U0001F4D6 Statut CFW",
                   command=self._cfw_statut_ctypes).pack(side="left",
                                                         padx=(6, 0))
        self.lbl_ctypes = ttk.Label(boxc, text="—")
        self.lbl_ctypes.pack(side="left", padx=10)

        self.lbl_img = ttk.Label(self.root, anchor="center",
                                 text="\n\n(le flux apparaîtra ici)\n\n")
        self.lbl_img.pack(fill="both", expand=True, padx=6, pady=4)
        self.lbl_fps = ttk.Label(self.root, text="—")
        self.lbl_fps.pack()
        self.txt = tk.Text(self.root, height=10, state="disabled",
                           font=("Consolas", 9))
        self.txt.pack(fill="both", padx=6, pady=(0, 6))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _tick(self):
        # Consommation des messages du thread → log de l'UI
        try:
            while True:
                self._log_direct(self.q_msg.get_nowait())
        except queue.Empty:
            pass
        if self._lbl_cam_txt is not None:
            self.lbl_cam.config(text=self._lbl_cam_txt,
                                foreground="#1d7f1d")
            self._lbl_cam_txt = None
        if self._lbl_ctypes_txt is not None:
            self.lbl_ctypes.config(text=self._lbl_ctypes_txt)
            self._lbl_ctypes_txt = None
        # Affichage de la dernière frame (normalisation min→max, mono)
        a = self._aperçu
        if a is not None:
            self._aperçu = None
            mn, mx = float(np.min(a)), float(np.max(a))
            v = np.zeros_like(a) if mx <= mn else (a - mn) / (mx - mn)
            pil = Image.fromarray((v * 255.0).astype(np.uint8), mode="L")
            pil.thumbnail((860, 540))
            self._photo = ImageTk.PhotoImage(pil)
            self.lbl_img.config(image=self._photo, text="")
        if self._flux_actif:
            self.lbl_fps.config(text=f"{self._fps:.1f} fps — {self._dims}")
        # Cadence : compteur de frames, âge de la dernière, état de pause.
        # À exposition 1 s, « 0,5 fps » et « dernière frame il y a 2,0 s »
        # sont les deux mesures qui distinguent une caméra lente d'une caméra
        # qui n'émet plus.
        etat = f"{self._total} frames — dernière il y a " + (
            f"{time.time() - self._derniere:.1f} s"
            if self._derniere else "—")
        if self._pause_txt:
            etat += " — " + self._pause_txt
        self.lbl_cadence.config(text=etat)
        self.lbl_roi_etat.config(text="ROI transmise : " + self._roi_txt)
        if self._balayage_resume is not None:
            self.lbl_balayage.config(text=self._balayage_resume)
        # Refroidissement : temp/PWM/consigne relus par le thread de flux
        # (toutes les 2 s) — l'affichage ne fait que consommer le résultat.
        if self._froid is not None:
            t, pwm, cons = self._froid
            self.lbl_t14.config(text="temp capteur : " + _nb(t, " °C"))
            self.lbl_t15.config(text="PWM TEC : " + _nb(pwm)
                                + " — consigne : " + _nb(cons, " °C"))
        # États des boutons demandés depuis les threads
        if self._btn_demande == "flux":
            self._btn_demande = None
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
        elif self._btn_demande == "libre":
            self._btn_demande = None
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
        self.root.after(40, self._tick)

    def _detecter(self):
        threading.Thread(target=self._detecter_thread, daemon=True).start()

    def _detecter_thread(self):
        self._trace("scan (sous-processus isolé)…")
        ids, err = mqhy.lister_via_sous_processus()
        if err is not None:
            self.q_msg.put("détection : ERREUR — " + err)
            return
        if not ids:
            self.q_msg.put("détection : aucune caméra QHY détectée "
                           "(USB ? driver ?)")
            return
        self.camera_id = str(ids[0])
        self._lbl_cam_txt = "détectée : " + ", ".join(map(str, ids))
        self.q_msg.put(f"détection OK : {len(ids)} caméra(s) — "
                       f"la 1re sera ouverte")

    def _demarrer(self):
        """Bouton unique : séquence EXACTE de l'application.

        La ROI cochée est LUE ICI (thread Tk — var.get() hors thread Tk est
        interdit) puis TRANSMISE à open() : elle ne peut plus « ne rien
        faire » en silence. Si la copie de qhy.py installée n'accepte pas de
        ROI (antérieure à la v2.13.2), on l'annonce explicitement : c'est le
        scénario qui a fait croire à un bug le 19/09/2026.
        """
        if self._flux_actif:
            return
        try:
            expo = float(self.var_expo.get().replace(",", "."))
            gain = float(self.var_gain.get().replace(",", "."))
            offset = float(self.var_offset.get().replace(",", "."))
            roi = ((int(self.var_w.get()), int(self.var_h.get()))
                   if self.var_roi.get() else None)
        except ValueError:
            messagebox.showerror("Réglages", "Expo/Gain/Offset/ROI : "
                                 "nombres invalides.")
            return
        contourner = bool(self.var_contourner.get())
        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal")
        threading.Thread(target=self._demarrer_thread,
                         args=(expo, gain, offset, roi, contourner),
                         daemon=True).start()

    def _demarrer_thread(self, expo, gain, offset, roi, contourner):
        try:
            if not self.camera_id:
                # NE PAS appeler QHYCamera.lister() ici : le scan de
                # découverte a déjà tourné et le SDK natif est DÉJÀ initialisé
                # dans ce process (vérification exhaustive faite dans le
                # sous-processus). Un second init_sdk() dans le même process
                # est justement le suspect du crash — constat du banc :
                # « Démarrer » sans détection préalable plantait, alors que
                # le pas-à-pas (lancé APRÈS « Détecter ») fonctionnait.
                raise RuntimeError("aucune caméra détectée — clique "
                                   "d'abord sur « 🔎 Détecter »")
            self._total = 0
            self._derniere = 0.0
            self._dims = "—"
            # Marque de départ dans le log : on ne relira QUE les lignes
            # écrites par CETTE ouverture (verdict ROI, cf. _verdict_roi).
            offset_ouverture = _taille_log()
            if self._deja_ouverte:
                self._trace(
                    "⚠ CETTE caméra a DÉJÀ été ouverte puis fermée dans ce "
                    "même process. Le binding n'expose AUCUNE fonction de "
                    "libération du SDK (ni release_sdk ni "
                    "ReleaseQHYCCDResource — vérifié par introspection) : "
                    "constat du 19/09/2026, après un Arrêter un nouveau "
                    "Démarrer n'a PLUS JAMAIS reçu de frame, sans planter. "
                    "Si ça se reproduit : FERME LE BANC ET RELANCE-LE "
                    "(process neuf = état SDK propre). C'est une limite du "
                    "paquet qhyccd, pas un défaut de votre matériel.")
            if contourner:
                # Comparaison : le banc pose la ROI lui-même (ancien
                # « pas-à-pas »). Ce chemin ne prouve RIEN sur l'appli — il
                # sert juste à confirmer qu'un plantage vient bien de la
                # version de qhy.py installée.
                self._roi_txt = ("forçage banc — " +
                                 ("aucune" if roi is None else
                                  f"{roi[0]}×{roi[1]}"))
                self._ouvrir_pasapas(roi)
            else:
                self._trace("démarrage via QHYCamera.open() "
                            "(séquence EXACTE de l'application)")
                if roi is not None and not _open_supporte_roi():
                    self._roi_txt = ("ROI IGNORÉE — la copie installée de "
                                     "qhy.py n'accepte pas de ROI (antérieure "
                                     "à la v2.13.2) : c'est CE fichier qu'il "
                                     "faut remplacer")
                    self._trace("⚠ open(roi=...) impossible : la copie "
                                "chargée de avastack/cameras/qhy.py n'a PAS "
                                "de paramètre roi → set_resolution ne sera "
                                "jamais appelé → segfault probable. Voir le "
                                "bloc « fichiers réellement chargés ».")
                else:
                    self._roi_txt = ("aucune" if roi is None else
                                     f"{roi[0]}×{roi[1]}")
                self.cam = QHYCamera(camera_id=self.camera_id)
                if _open_supporte_roi():
                    self.cam.open(roi=roi)   # SEUL écart avec l'appli
                else:
                    self.cam.open()          # l'appli, telle qu'installée
            self.cam.apply_settings(expo, gain)
            self._deja_ouverte = True
            # Verdict AUTOMATIQUE sur la ROI : c'est ce que la case cochée
            # n'arrivait pas à prouver (constat du 19/09/2026 : aucune ligne
            # set_resolution dans le log, même ROI cochée).
            self._verdict_roi(offset_ouverture, roi, contourner)
            self._expo_s = expo / 1000.0     # pour le garde-fou de la boucle
            self._trace(f"apply_settings : expo {expo:g} ms "
                        f"({int(expo * 1000)} µs), gain {gain:g}")
            if self.cam.cam is not None:
                try:
                    self.cam.cam.set_offset(offset)
                    self._trace(f"set_offset({offset:g}) OK")
                except Exception as e:
                    self._trace(f"set_offset ignoré ({e})")
                # Relire les réglages posés — numérotation RÉELLE du binding
                # (gain=6, offset=7, exposure µs=8 ; vérifié empiriquement
                # par Alain : ce qu'on pose sur ces ids revient à l'identique)
                for cid_, nom in ((6, "gain"), (7, "offset"),
                                  (8, "exposure µs")):
                    try:
                        self._trace(f"relu {nom} (ctrl {cid_}) = "
                                    f"{self.cam.cam.get_param(cid_)}")
                    except Exception as e:
                        self._trace(f"relu {nom} (ctrl {cid_}) : {e}")
            # Premier frame diagnostique : shape/dtype RÉELS du buffer.
            # NB (constat réel) : juste après begin_live, la 1re image n'est
            # pas encore prête (exposition de 1000 ms !) → le SDK renvoie
            # son erreur 0xFFFFFFFF pendant ~1 s. Ce n'est PAS une erreur :
            # on patiente et on réessaie avant de déclarer un problème.
            f = None
            for essai in range(12):        # 12 × 0,5 s = 6 s max
                try:
                    f = self.cam.cam.get_live_frame()
                    break
                except Exception as e:
                    if essai == 0:
                        self._trace(f"1er get_live_frame() : {e} — la 1re "
                                    "image n'est pas encore prête "
                                    "(exposition en cours), essais…")
                    time.sleep(0.5)
            if f is None:
                self._trace("1er get_live_frame() : aucune image reçue "
                            "en 6 s — voir erreurs ci-dessus")
            else:
                a = np.asarray(f)
                self._dims = f"{a.shape[1]}×{a.shape[0]} px"
                self._trace(f"1er frame : shape={a.shape} dtype={a.dtype} "
                            f"min={a.min()} max={a.max()}")
            self._flux_actif = True
            self._n = 0
            self._t0 = time.time()
            threading.Thread(target=self._boucle, daemon=True).start()
            self._btn_demande = "flux"
            self._trace("flux démarré ✔")
        except Exception as e:
            self._trace(f"ERREUR : {e}")
            self._btn_demande = "libre"

    def _verdict_roi(self, offset, roi, contourner):
        """VERDICT AUTOMATIQUE : cette ouverture a-t-elle POSÉ la ROI ?

        Constat d'Alain (19/09/2026, miniPC) : « Démarrer » ne contenait
        AUCUNE ligne set_resolution, MÊME case ROI cochée — parce que la
        copie chargée de avastack/cameras/qhy.py était ANTÉRIEURE à la
        v2.13.2 et n'appelait jamais set_resolution. Or sans résolution
        posée, le SDK QHY plante en natif au premier get_live_frame (fenêtre
        fermée sans message) ou n'émet aucune frame : les DEUX symptômes
        rapportés s'expliquent ainsi. La case ROI ne pouvait rien prouver
        (le fichier fautif ignore l'argument) : on relit donc la trace
        elle-même et on conclut explicitement.
        """
        if contourner and roi is None:
            self._roi_txt = "forçage banc SANS ROI (rien à poser : normal)"
            self._trace("verdict ROI : " + self._roi_txt)
            return
        lignes = _lignes_depuis(offset)
        tentees = [l for l in lignes if "set_resolution" in l]
        acceptees = [l for l in tentees
                     if " OK" in l and "REFUS" not in l]
        if acceptees:
            self._roi_txt = ("POSÉE ✔ — " + acceptees[-1].split("] ", 1)[-1])
            self._trace("verdict ROI : " + self._roi_txt)
        elif tentees:
            self._roi_txt = ("TENTÉE MAIS REFUSÉE par le SDK — "
                             + tentees[-1].split("] ", 1)[-1])
            self._trace("⚠ verdict ROI : " + self._roi_txt + " — aucune taille "
                        "acceptée : le flux ne peut pas démarrer dans de "
                        "bonnes conditions (voir les refus ci-dessus).")
        else:
            self._roi_txt = ("AUCUNE TENTATIVE de set_resolution PENDANT "
                             "cette ouverture → la copie chargée de "
                             "avastack/cameras/qhy.py est ANTÉRIEURE à la "
                             "v2.13.2 : c'est la CAUSE (pas la case ROI). "
                             "Remplacer ce fichier par la version à jour.")
            self._trace("⚠ verdict ROI : " + self._roi_txt)

    def _ouvrir_pasapas(self, roi):
        """Séquence officielle DÉCOMPOSÉE : chaque étape tracée + ROI
        imposable avant begin_live (test de l'hypothèse « buffer non
        alloué sans set_resolution »). Réutilise QHYCamera pour read()/
        close() (self.cam.cam = handle du binding)."""
        self._trace("=== séquence pas-à-pas (chaque étape tracée) ===")
        import qhyccd
        if mqhy._initialiser_sdk():
            self._trace("init_sdk() OK (1re initialisation du process)")
        else:
            self._trace("init_sdk() DÉJÀ fait — ré-initialisation ÉVITÉE "
                        "(état global du SDK)")
        ids = list(qhyccd.scan_cameras())
        self._trace(f"scan_cameras() -> {ids}")
        if not ids:
            raise RuntimeError("scan vide : aucune caméra QHY")
        cid = self.camera_id if self.camera_id in ids else ids[0]
        cam = qhyccd.Camera(cid)
        self._trace(f"Camera({cid!r}) ouverte (constructeur)")
        self.cam = QHYCamera(camera_id=cid)
        self.cam.cam = cam          # read()/close() de la classe pour la suite
        self.cam.name = f"QHY {cid}"
        cam.set_stream_mode(1)
        self._trace("set_stream_mode(1) OK")
        cam.init()
        self._trace("init() OK")
        cam.set_bin_mode(1, 1)
        self._trace("set_bin_mode(1,1) OK")
        if roi is not None:
            w, h = roi
            tailles = [(w, h)] + [t for t in [(3840, 2160), (3856, 2180),
                                              (3848, 2168), (1920, 1080)]
                                  if t != (w, h)]
            posee = False
            for tw, th in tailles:
                try:
                    cam.set_resolution(0, 0, tw, th)
                    self._trace(f"set_resolution(0,0,{tw},{th}) OK")
                    posee = True
                    break
                except Exception as e:
                    self._trace(f"set_resolution(0,0,{tw},{th}) REFUSÉE ({e})"
                                " — taille invalide pour ce capteur")
            if not posee:
                raise RuntimeError("aucune ROI acceptée par le SDK — "
                                   "essayer d'autres dimensions")
        else:
            self._trace("(ROI non imposée — zone par défaut du SDK)")
        cam.begin_live()
        self._trace("begin_live() OK")

    def _boucle(self):
        """Boucle de lecture du flux (thread) — QHYCamera.read(), la même
        méthode que dans l'application. Tolérante aux erreurs transitoires
        (entre deux frames, pendant l'exposition, le SDK répond par son
        erreur 0xFFFFFFFF : on réessaie). Garde-fou ADAPTÉ À L'EXPOSITION :
        (constat réel, expo 5000 ms → la 1re frame arrive après ~5 s, un
        seuil fixe de 4 s coupait à tort) — patience = 2× l'exposition,
        minimum 4 s."""
        echecs = 0
        delai_max = max(2.0 * self._expo_s, 4.0)
        t_derniere = time.time()
        t_dernier_msg = time.time()
        t_maj_froid = 0.0
        t0_flux = time.time()
        while self._flux_actif and self.cam is not None:
            # PAUSE (test de cadence) : on ne lit PLUS RIEN. À exposition
            # 1000 ms le flux tourne à ~1 fps et rien ne permet de distinguer
            # « la caméra n'émet plus » de « nos lectures vident le buffer ».
            # La pause tranche : si le flux repart d'un coup à la reprise, le
            # rythme est piloté par nos lectures.
            if self._pause:
                time.sleep(0.05)
                continue
            # Relecture TEC (température/PWM/consigne) toutes les 2 s —
            # pendant le flux, c'est le seul moment où les valeurs bougent.
            maintenant = time.time()
            if maintenant - t_maj_froid > 2.0:
                t_maj_froid = maintenant
                self._lire_froid()
            try:
                f = self.cam.read()
            except Exception as e:
                self._trace(f"read() : {e}")
                break
            if f is None:
                echecs += 1
                maintenant = time.time()
                if maintenant - t_dernier_msg > 2.0:
                    self._trace(f"{echecs} lectures sans frame (exposition "
                                f"{self._expo_s:g} s ?) — réessais en cours")
                    t_dernier_msg = maintenant
                if maintenant - t_derniere > delai_max:
                    self._trace(f"arrêt : aucune frame pendant "
                                f"{maintenant - t_derniere:.1f} s (limite "
                                f"{delai_max:.1f} s = 2× exposition, "
                                "min 4 s)")
                    break
                time.sleep(0.01)
                continue
            echecs = 0
            t_derniere = time.time()
            self._total += 1
            self._derniere = t_derniere
            self._n += 1
            dt = t_derniere - self._t0
            if dt >= 1.0:
                self._fps = self._n / dt
                self._n = 0
                self._t0 = t_derniere
            # Horodatage des 5 premières frames : on SAIT quand chacune
            # arrive. À exposition 1 s, c'est cette ligne qui dit si la
            # caméra tient son rythme (t+1,0 / t+2,0 / t+3,0 s…) ou si elle
            # décroche — un compteur seul ne le montrerait pas.
            if self._total <= 5:
                self._trace(f"frame #{self._total} à t+"
                            f"{t_derniere - t0_flux:.1f} s — shape={f.shape} "
                            f"dtype={f.dtype} min={f.min()} max={f.max()}")
            if self._dims == "—":
                self._dims = f"{f.shape[1]}×{f.shape[0]} px"
            self._aperçu = f
        self._trace("boucle de flux terminée")

    def _lire_froid(self):
        """Lit le TEC : température (14), PWM courant (15), consigne (18).

        Appelé depuis les threads (flux ou écriture) : ne touche JAMAIS à
        Tk (les valeurs passent par self._froid, consommé par _tick). Un
        échec de lecture est NORMAL sur une caméra non refroidie ou sans
        alimentation 12 V — on l'affiche au lieu de planter.
        """
        if self.cam is None or self.cam.cam is None:
            return
        vals = []
        for cid in (CTRL_TEMP, CTRL_PWM, CTRL_CONSIGNE):
            try:
                vals.append(float(self.cam.cam.get_param(cid)))
            except Exception as e:
                vals.append(f"erreur ({e})")
        self._froid = tuple(vals)

    def _relire_froid(self):
        threading.Thread(target=self._lire_froid, daemon=True).start()

    def _arreter(self):
        self._flux_actif = False
        self._pause = False
        self._pause_txt = ""
        threading.Thread(target=self._fermer_thread, daemon=True).start()

    def _pause_ctrl(self):
        """Pause de 3 s : teste si le flux REPART après une interruption.

        À expo 1000 ms, on ne peut pas distinguer « la caméra n'émet plus »
        de « nos lectures vident le buffer ». On arrête donc de LIRE pendant
        3 s, puis on reprend : si une frame (ou plusieurs) arrive aussitôt,
        c'est bien nous qui pilotons le rythme (comportement normal, le
        getter vidant la file du SDK) — pas un défaut de la caméra.
        """
        if not self._flux_actif or self._pause:
            return
        threading.Thread(target=self._pause_thread, daemon=True).start()

    def _pause_thread(self):
        self._pause = True
        t0 = time.time()
        try:
            while time.time() - t0 < 3.0:
                self._pause_txt = (f"PAUSE — plus aucune lecture "
                                   f"({3.0 - (time.time() - t0):.1f} s)")
                time.sleep(0.1)
        finally:
            self._pause_txt = ""
            self._pause = False
        self._trace("reprise des lectures après 3 s de pause — si le flux "
                    "repart aussitôt, c'est bien nos lectures qui pilotent "
                    "le rythme (pas un défaut caméra)")

    def _fermer_thread(self):
        if self.cam is not None:
            try:
                self.cam.close()
                self._trace("close OK")
                ok_libre, noms = _binding_sans_liberation()
                if ok_libre:
                    self._trace(
                        "RAPPEL : le binding qhyccd n'expose AUCUNE fonction "
                        "de libération du SDK (ni release_sdk ni "
                        "ReleaseQHYCCDResource — introspection : "
                        + ", ".join(noms) + "). Fermer la caméra ne "
                        "réinitialise donc PAS l'état global du SDK : un "
                        "nouveau ▶ Démarrer dans CE process est à risque "
                        "(constat du 19/09/2026 : plus AUCUNE frame reçue "
                        "après un Arrêter). Pour repartir proprement : "
                        "FERMER LE BANC et le relancer.")
            except Exception as e:
                self._trace(f"close : {e}")
            self.cam = None
        self._btn_demande = "libre"

    def _balayer(self):
        """Balayage d'un contrôle : POSE chaque valeur, la RELIT, note les refus.

        Outil de DÉCOUVERTE DES BORNES RÉELLES (demande d'Alain : « la
        découverte de toutes les valeurs »). Il est indispensable parce que
        trois comportements coexistent côté SDK :
          1. valeur acceptée et relue à l'identique (cas du gain) ;
          2. valeur acceptée mais RELUE AUTREMENT (le SDK la borne ou
             l'arrondit — invisible sans relecture) ;
          3. valeur REFUSÉE (erreur, souvent la sentinelle 0xFFFFFFFF).
        Les variables Tk sont lues ICI (thread principal) : var.get() hors
        thread Tk est interdit (piège consigné dans CLAUDE.md).
        """
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("balayage : ouvre d'abord la caméra (▶ Démarrer)")
            return
        try:
            cid = int(self.var_bid.get())
            vmin = float(self.var_bmin.get().replace(",", "."))
            vmax = float(self.var_bmax.get().replace(",", "."))
            pas = float(self.var_bpas.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Balayage", "id/de/à/pas : nombres invalides.")
            return
        if pas <= 0 or vmax < vmin:
            messagebox.showerror("Balayage", "« pas » doit être > 0 et « à » "
                                 "supérieur ou égal à « de ».")
            return
        # Garde-fou : certains contrôles changent la CONFIGURATION de la
        # caméra (binning, profondeur de bits, mode DDR…) — les écrire en
        # série mérite une confirmation explicite.
        if cid in (20, 21, 22, 23, 24, 25, 30, 31, 34, 35, 43, 48, 49, 51,
                   52, 57, 58):
            if not messagebox.askokcancel(
                    "Balayage",
                    f"Le contrôle {cid} ({_nom_ctrl(cid) or 'inconnu'}) "
                    "change la CONFIGURATION de la caméra (binning, bits, "
                    "mode…).\n\nBalayer plusieurs valeurs le laissera dans "
                    "un état quelconque — il faudra relancer ▶ Démarrer.\n\n"
                    "Continuer ?"):
                return
        self.lbl_balayage.config(text="balayage en cours…")
        threading.Thread(target=self._balayer_thread,
                         args=(cid, vmin, vmax, pas), daemon=True).start()

    def _balayer_thread(self, cid, vmin, vmax, pas):
        """Exécute le balayage (thread) puis publie un RÉSUMÉ exploitable.

        Chaque valeur : set_param puis get_param immédiat. On consigne les
        refus, et surtout les valeurs RELUES différentes de la valeur posée
        (signe que le SDK borne/arrondit) — c'est ce relevé qui permettra de
        recalibrer les curseurs de l'application (le gain y est borné à 8
        alors que la MiniCam8M travaille en unités constructeur).
        """
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("balayage : caméra fermée entre-temps")
            return
        nom = _nom_ctrl(cid) or "?"
        self._trace(f"=== balayage ctrl {cid} ({nom}) : de {vmin:g} à "
                    f"{vmax:g} pas {pas:g} ===")
        n = int(round((vmax - vmin) / pas)) + 1
        valeurs = [vmin + i * pas for i in range(max(n, 1))]
        acceptees, refusees, transformees = [], 0, []
        for v in valeurs:
            try:
                self.cam.cam.set_param(cid, v)
            except Exception as e:
                refusees += 1
                self._trace(f"  {v:g} → REFUSÉ ({e})")
                continue
            acceptees.append(v)
            try:
                relu = float(self.cam.cam.get_param(cid))
                if abs(relu - v) > 1e-6:
                    transformees.append((v, relu))
                    self._trace(f"  {v:g} → accepté mais RELU {relu:g}")
            except Exception as e:
                self._trace(f"  {v:g} → posé, relecture impossible ({e})")
        # Résumé : bornes réellement acceptées + valeurs transformées.
        if acceptees:
            resume = (f"ctrl {cid} ({nom}) : {len(acceptees)}/{len(valeurs)} "
                      f"acceptées, {refusees} refusées — plage réellement "
                      f"acceptée [{min(acceptees):g} … {max(acceptees):g}]")
        else:
            resume = (f"ctrl {cid} ({nom}) : AUCUNE valeur acceptée sur "
                      f"[{vmin:g} … {vmax:g}] — contrôle non inscriptible")
        if transformees:
            resume += (f" — {len(transformees)} valeur(s) TRANSFORMÉE(S) par "
                       "le SDK (voir le log)")
        self._balayage_resume = resume
        self._trace(resume)
        self._trace("NB : les réglages de la caméra ont été modifiés par le "
                    "balayage — relance ▶ Démarrer pour repartir d'un état "
                    "connu.")
        self._lire_froid()

    def _ctrl_dispo(self, cid):
        """→ True si le SDK déclare ce contrôle disponible sur CETTE caméra.

        Garde-fou : on n'essaie pas d'écrire un contrôle que le capteur
        n'expose pas (la MiniCam8M n'en expose que 22 sur 63 — constat réel).
        """
        try:
            return bool(self.cam.cam.is_control_available(cid))
        except Exception:
            return False

    def _sequenceur(self):
        """Séquenceur : balaye une LISTE de contrôles SÛRS en plusieurs points.

        Répond à la demande « la découverte de TOUTES les valeurs » : pour
        chaque contrôle de RÉGLAGE disponible, on pose des échantillons
        réguliers entre « de » et « à », on RELIT après chaque écriture et on
        classe la réponse en trois, car trois comportements coexistent :
          1. accepté et relu à l'identique  → borne fiable, utilisable dans
             l'application ;
          2. accepté mais RELU AUTREMENT    → le SDK borne ou arrondit
             (invisible sans relecture) ;
          3. REFUSÉ (souvent 0xFFFFFFFF)    → hors domaine du capteur.
        Les contrôles de CONFIGURATION en sont EXCLUS (cf.
        CTRLS_SEQUENCEUR) : les écrire en série laisse la caméra dans un état
        incohérent, il faudrait relancer ▶ Démarrer.
        Les variables Tk sont lues ICI (thread principal) : var.get() hors
        thread Tk est interdit (piège consigné dans CLAUDE.md).
        """
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("séquenceur : ouvre d'abord la caméra (▶ Démarrer)")
            return
        try:
            vmin = float(self.var_bmin.get().replace(",", "."))
            vmax = float(self.var_bmax.get().replace(",", "."))
            pas = float(self.var_bpas.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Séquenceur", "de/à/pas : nombres invalides.")
            return
        if pas <= 0 or vmax < vmin:
            messagebox.showerror("Séquenceur", "« pas » doit être > 0 et "
                                 "« à » supérieur ou égal à « de ».")
            return
        cibles = [c for c in CTRLS_SEQUENCEUR if self._ctrl_dispo(c)]
        if not cibles:
            self.q_msg.put("séquenceur : aucun contrôle ciblé disponible "
                           "(caméra ouverte ?)")
            return
        if not messagebox.askokcancel(
                "Séquenceur",
                "Balayage de " + ", ".join(f"{c} ({_nom_ctrl(c)})"
                                           for c in cibles)
                + f" entre {vmin:g} et {vmax:g} (pas {pas:g}).\n\n"
                "Ces contrôles sont des RÉGLAGES : rien n'est cassé, mais "
                "chaque contrôle restera sur la DERNIÈRE valeur testée. "
                "Continuer ?"):
            return
        self.lbl_balayage.config(text="séquenceur en cours…")
        threading.Thread(target=self._sequenceur_thread,
                         args=(cibles, vmin, vmax, pas), daemon=True).start()

    def _sequenceur_thread(self, cibles, vmin, vmax, pas):
        """Exécute le séquenceur (thread : set_param bloque sur le SDK)."""
        self.q_msg.put("=== séquenceur : valeurs acceptées "
                       "(pose + relecture) ===")
        valeurs = []
        v = vmin
        while v <= vmax + 1e-9:
            valeurs.append(round(v, 4))
            v += pas
        if len(valeurs) > 40:
            valeurs = valeurs[:40]
            self.q_msg.put("    (limité à 40 échantillons)")
        resume = []
        for cid in cibles:
            notes = []
            ok_min = ok_max = None
            for val in valeurs:
                try:
                    self.cam.cam.set_param(cid, val)
                except Exception:
                    notes.append(f"{val:g}=refusé")
                    continue
                try:
                    relu = float(self.cam.cam.get_param(cid))
                except Exception:
                    notes.append(f"{val:g}=posé,relecture KO")
                    continue
                if abs(relu - val) <= max(abs(val) * 1e-6, 1e-6):
                    notes.append(f"{val:g}=ok")
                    ok_min = val if ok_min is None else ok_min
                    ok_max = val
                else:
                    notes.append(f"{val:g}->{relu:g}")
            self.q_msg.put(f"ctrl {cid:>2} {_nom_ctrl(cid):<20} "
                           + " ".join(notes))
            if ok_min is None:
                resume.append(f"{cid} ({_nom_ctrl(cid)}): aucune valeur "
                              "acceptée telle quelle")
            else:
                resume.append(f"{cid} ({_nom_ctrl(cid)}): "
                              f"{ok_min:g}..{ok_max:g} acceptés tels quels")
        self.q_msg.put("résumé — " + " | ".join(resume))
        self._balayage_resume = "séquenceur : " + "; ".join(resume)[:90]

    def _lister_controles(self):
        threading.Thread(target=self._lister_thread, daemon=True).start()

    def _ecrire_ctrl(self):
        """Écriture depuis le panneau générique (id + valeur saisis).

        Les variables Tk sont lues ICI (thread principal) : var.get() hors
        du thread Tk est interdit (piège consigné dans CLAUDE.md).
        """
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("écrire : ouvre d'abord la caméra (▶ Démarrer)")
            return
        try:
            cid = int(self.var_cid.get())
            val = float(self.var_cval.get().replace(",", "."))
        except ValueError:
            self.q_msg.put("écrire : id/valeur invalides (nombres attendus)")
            return
        self._ecrire_valeur(cid, val, "")

    def _ecrire_ctrl_valeur(self, cid, texte, libelle):
        """Boutons du panneau TEC : valide la saisie PUIS écrit dans un
        thread (set_param bloque sur le SDK natif)."""
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("écrire : ouvre d'abord la caméra (▶ Démarrer)")
            return
        try:
            val = float(str(texte).replace(",", "."))
        except ValueError:
            self.q_msg.put(f"{libelle} : valeur invalide « {texte} »")
            return
        self._ecrire_valeur(cid, val, libelle)

    def _ecrire_valeur(self, cid, val, libelle):
        threading.Thread(target=self._ecrire_thread,
                         args=(cid, val, libelle), daemon=True).start()

    def _ecrire_thread(self, cid, val, libelle):
        """set_param(id, valeur) : écrit n'importe quel contrôle du SDK
        (PWM du TEC, USB traffic, binning…) puis RELIT pour confirmer."""
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("écrire : caméra fermée entre-temps")
            return
        prefixe = f"{libelle} — " if libelle else ""
        try:
            self.cam.cam.set_param(cid, val)
        except Exception as e:
            self.q_msg.put(f"{prefixe}set_param({cid}, {val:g}) : {e}")
            return
        try:
            relu = self.cam.cam.get_param(cid)
            self.q_msg.put(f"{prefixe}set_param({cid}, {val:g}) OK — "
                           f"relu : {_fmt_val(relu)}")
        except Exception as e:
            self.q_msg.put(f"{prefixe}set_param({cid}, {val:g}) OK — "
                           f"relecture : {e}")
        self._lire_froid()      # rafraîchit l'affichage température/PWM

    def _lister_thread(self):
        """Énumère les contrôles du SDK et relève TOUTES les valeurs.

        Deux passes, volontairement distinctes :
          1. les contrôles réellement DISPONIBLES (is_control_available) avec
             leur nom officiel et leur valeur — ceux sur lesquels on peut agir ;
          2. un balayage EXHAUSTIF de 0 à 63 (demande d'Alain : « on finit la
             découverte de toutes les valeurs ») : les id indisponibles sont
             affichés quand même, avec leur valeur brute en hexadécimal. C'est
             indispensable pour trancher un cas limite : un contrôle ABSENT
             (is_control_available() faux) et un contrôle « drapeau » (valeur
             sentinelle 0xFFFFFFFF) ne se distinguent pas autrement.

        Nécessite la caméra ouverte. Lectures seules (get_param) : aucun
        réglage n'est modifié ; un id inconnu du SDK lève une exception, on
        l'affiche au lieu de planter.
        """
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("lister : ouvre d'abord la caméra (▶ Démarrer)")
            return
        self.q_msg.put("=== contrôles DISPONIBLES (is_control_available) ===")
        dispo = 0
        for ctrl in range(1, 64):
            try:
                if not self.cam.cam.is_control_available(ctrl):
                    continue
            except Exception as e:
                self.q_msg.put(f"ctrl {ctrl} : erreur {e}")
                continue
            dispo += 1
            try:
                val = self.cam.cam.get_param(ctrl)
            except Exception as e:
                val = f"(erreur {e})"
            self.q_msg.put(f"ctrl {ctrl:>2} {_nom_ctrl(ctrl):<24} "
                           f"valeur={_fmt_val(val)}")
        self.q_msg.put(f"({dispo} contrôles disponibles sur 1..63)")

        # --- Passe 2 : TOUTES les valeurs, y compris les id indisponibles ---
        self.q_msg.put("=== TOUTES les valeurs (0..63, y compris "
                       "indisponibles) ===")
        for ctrl in range(0, 64):
            dispo_txt = "dispo"
            try:
                if not self.cam.cam.is_control_available(ctrl):
                    dispo_txt = "INDISPO"
            except Exception as e:
                dispo_txt = f"erreur is_control_available ({e})"
            try:
                brut = self.cam.cam.get_param(ctrl)
                valeur = f"{brut:g}"
                try:
                    valeur += f" (0x{int(brut) & 0xFFFFFFFF:08X})"
                except (OverflowError, ValueError):
                    pass
            except Exception as e:
                valeur = f"(get_param : {e})"
            self.q_msg.put(f"ctrl {ctrl:>2} [{dispo_txt:<7}] "
                           f"{_nom_ctrl(ctrl):<24} {valeur}")
        self.q_msg.put("Rappel : 0xFFFFFFFF (4294967295) = sentinelle du SDK "
                       "pour un contrôle sans valeur numérique ; les id sans "
                       "nom ne figurent pas dans l'enum officiel qhyccd-rs.")

    def _lister_api(self):
        """Introspection : liste TOUT ce que le binding expose.

        Répond à « quels contrôles sont possibles ? » : le refroidissement
        n'a AUCUNE méthode dédiée (pas de set_cooler / set_temperature) —
        il ne peut passer que par set_param(18, consigne) / set_param(16,
        PWM), d'où la nécessité des id numériques. Introspection pure Python
        (dir/__doc__), sans appel natif → sans risque.
        """
        self.q_msg.put("=== API du binding qhyccd (introspection) ===")
        try:
            import qhyccd
            self.q_msg.put("module : " + ", ".join(
                n for n in dir(qhyccd) if not n.startswith("_")))
            for nom in sorted(n for n in dir(qhyccd.Camera)
                              if not n.startswith("_")):
                try:
                    doc = getattr(qhyccd.Camera, nom).__doc__ or ""
                except Exception:
                    doc = ""
                doc = doc.strip().splitlines()
                self.q_msg.put(f"  Camera.{nom:<22}"
                               + (f"  {doc[0].strip()}" if doc else ""))
        except Exception as e:
            self.q_msg.put(f"introspection : {e}")
        # NB : la flèche « ⇒ » est évitée volontairement — un caractère hors
        # cp1252 fait planter tout affichage redirigé vers un stdout Windows
        # (piège consigné dans CLAUDE.md ; ici le message va à Tk, mais le
        # log peut être relu/pipé).
        self.q_msg.put("=> refroidissement : set_param(18, °C) ou "
                       "set_param(16, PWM 0-255) ; lecture 14 (temp) / "
                       "15 (PWM) — aucune méthode dédiée dans le binding.")

    # --- sonde ctypes native (plages + roue intégrée) ---------------------

    def _plages_ctypes(self):
        self._lancer_sonde_ctypes("plages", 60)

    def _cfw_statut_ctypes(self):
        self._lancer_sonde_ctypes("cfw_status", 40)

    def _roue_ctypes(self):
        try:
            pos = int(self.var_slot.get())
        except ValueError:
            messagebox.showerror("Roue", "Position : nombre entier (1..16).")
            return
        if not 1 <= pos <= 16:
            messagebox.showerror("Roue",
                                 "Position entre 1 et 16 (ASCII '0'..'F').")
            return
        self._lancer_sonde_ctypes("cfw_order", 50, pos)

    def _lancer_sonde_ctypes(self, action, timeout_s, slot=1):
        """Garde-fous puis lancement de la sonde dans un sous-processus.

        Refus si le flux est actif (ou caméra encore ouverte côté binding) :
        une caméra ne doit JAMAIS être ouverte deux fois (constat du
        19/09/2026 : double ouverture du handle USB = segfault natif).
        """
        if (self.cam is not None and self.cam.cam is not None) \
                or self._flux_actif:
            self.q_msg.put("sonde ctypes : une caméra est OUVERTE côté banc "
                           "(▶ Démarrer) — clique « ■ Arrêter » d'abord : "
                           "une caméra ne doit jamais être ouverte deux "
                           "fois.")
            return
        if self._ctypes_occupe:
            self.q_msg.put("sonde ctypes : déjà en cours, patiente…")
            return
        self._ctypes_occupe = True
        self._lbl_ctypes_txt = "sonde en cours…"
        self._trace(f"sonde ctypes ({action}) : lancement du sous-processus")
        threading.Thread(target=self._sonde_thread,
                         args=(action, self.camera_id, slot, timeout_s),
                         daemon=True).start()

    def _sonde_thread(self, action, cid, slot, timeout_s):
        """Exécute l'enfant, relaie ses lignes « # », puis affiche le JSON."""
        try:
            cmd = [sys.executable, os.path.abspath(__file__),
                   "--ctypes-sonde", action, cid or "", str(slot)]
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout_s,
                               creationflags=mqhy._CREATE_NO_WINDOW)
            for ligne in (r.stdout or "").splitlines():
                if ligne.startswith("#"):
                    self.q_msg.put("  " + ligne[1:].strip())
            jsonl = None
            for ligne in (r.stdout or "").splitlines():
                if ligne.startswith("{"):
                    jsonl = ligne
            if jsonl is None:
                det = (r.stderr or "").strip().splitlines()
                self.q_msg.put(
                    "sonde ctypes : le sous-processus n'a rien répondu"
                    + (f" — dernier mot : {det[-1]}" if det else "")
                    + " (segfault natif possible : retente une fois ; si ça "
                      "se répète, note le chemin de la DLL affiché plus "
                      "haut).")
                return
            res = json.loads(jsonl)
            if res.get("action") == "plages":
                self._afficher_plages(res)
            else:
                self._afficher_cfw(res)
        except subprocess.TimeoutExpired:
            self.q_msg.put(f"sonde ctypes : PAS DE RÉPONSE en {timeout_s} s "
                           "— le SDK est resté bloqué ; retente, et si ça "
                           "persiste, c'est la DLL native qu'il faudra "
                           "examiner.")
        except Exception as e:
            self.q_msg.put(f"sonde ctypes : erreur inattendue ({e!r})")
        finally:
            self._ctypes_occupe = False
            self._lbl_ctypes_txt = "—"

    @staticmethod
    def _ligne_controle(cid_, e, fmt=None):
        """Une ligne lisible pour un contrôle de la sonde (min/max/step)."""
        nom = e.get("nom", "")
        base = f"ctrl {cid_:>2} {nom:<24}"
        if "min" in e:
            plage = f"[{e['min']:g} .. {e['max']:g}] pas {e['step']:g}"
            if fmt == "duree":
                plage += (f"   ({_fmt_duree(e['min'])} -> "
                          f"{_fmt_duree(e['max'])})")
            doute = ("   ⚠ " + e["doute"]) if "doute" in e else ""
            return f"{base} {plage}{doute}"
        return f"{base} pas de plage (rc={e.get('rc_minmax', '?')})"

    def _afficher_plages(self, res):
        self.q_msg.put("=== SONDE CTYPES (qhyccd.dll direct) — PLAGES ===")
        if not res.get("ok"):
            for e in res.get("erreurs", []):
                self.q_msg.put("  échec : " + e)
            if not res.get("controles"):
                return
        self.q_msg.put(f"  DLL : {res.get('dll', '?')}")
        if res.get("model"):
            self.q_msg.put(f"  modèle : {res['model']}   "
                           f"id : {res.get('cid', '?')}")
        ctr = res.get("controles", {})
        self.q_msg.put("--- RÉSUMÉ (valeurs pour câbler les curseurs) ---")
        for cid_, libelle, fmt in ((8, "EXPOSURE (µs)", "duree"),
                                   (6, "GAIN", None),
                                   (7, "OFFSET", None),
                                   (18, "COOLER (consigne °C)", None),
                                   (12, "UsbTraffic", None),
                                   (44, "CfwSlotsNum", None)):
            e = ctr.get(str(cid_))
            if e is None:
                self.q_msg.put(f"  {libelle:<24} INDISPONIBLE")
            else:
                self.q_msg.put("  " + self._ligne_controle(cid_, e, fmt))
        self.q_msg.put("--- TOUS les contrôles disponibles ---")
        for k in sorted(ctr, key=int):
            self.q_msg.put("  " + self._ligne_controle(int(k), ctr[k]))
        ind = res.get("indisponibles", [])
        if ind:
            self.q_msg.put("(indisponibles : " + ", ".join(map(str, ind))
                           + ")")
        rcs = res.get("dispo_rc")
        if rcs and not ctr:
            self.q_msg.put(
                "⚠ IsQHYCCDControlAvailable n'a JAMAIS répondu 0 (= dispo) "
                "(codes : " + ", ".join(f"{k} ×{v}" for k, v in rcs.items())
                + ") — regarde plus haut les codes de SetQHYCCDStreamMode et "
                "InitQHYCCD : si InitQHYCCD != 0, c'est l'initialisation "
                "par handle qui bloque (le rapporter tel quel).")
        cfw = res.get("cfw")
        if cfw:
            self._lignes_cfw(cfw)

    def _afficher_cfw(self, res):
        self.q_msg.put("=== SONDE CTYPES — ROUE INTÉGRÉE (CFW) ===")
        if not res.get("ok"):
            for e in res.get("erreurs", []):
                self.q_msg.put("  échec : " + e)
            if not res.get("cfw"):
                return
        self.q_msg.put(f"  DLL : {res.get('dll', '?')}")
        if res.get("model"):
            self.q_msg.put(f"  modèle : {res['model']}")
        self._lignes_cfw(res.get("cfw", {}))

    def _lignes_cfw(self, cfw):
        """Verdicts roue : détection, slots, statut relu (ASCII doc QHY)."""
        self.q_msg.put("--- ROUE INTÉGRÉE (fonctions natives CFW) ---")
        if cfw.get("plugged"):
            self.q_msg.put("  roue DÉTECTÉE (IsQHYCCDCFWPlugged = 0 = "
                           "trouvé, doc QHY)")
        else:
            self.q_msg.put(f"  pas de roue détectée "
                           f"(IsQHYCCDCFWPlugged = {cfw.get('plugged_rc')})")
        sp = cfw.get("slots_param")
        if sp is not None:
            note = " (9 = lecture non supportée, doc QHY)" if sp == 9 else ""
            self.q_msg.put(f"  slots (ctrl 44) : {sp:g}{note}")
        statut = cfw.get("status", "")
        if statut:
            p = ord(statut[0]) - ord('0') + 1
            self.q_msg.put(
                f"  statut relu : {statut!r} -> position {p} selon la doc "
                "('0' = position 1). Rappel : la voie binding lit/écrit "
                "48+n (49 = « filtre 1 » relevé en réel) — si les deux ne "
                "concordent pas, c'est l'EFFET PHYSIQUE qui tranche "
                "(leçon CLAUDE.md).")
        else:
            self.q_msg.put("  statut relu : (chaîne vide)")
        if "envoyee" in cfw:
            en = cfw["envoyee"]
            self.q_msg.put(f"  ordre envoyé : position {en['position']} "
                           f"(ASCII {en['ascii']!r}), rc="
                           f"{cfw.get('send_rc')}")
            if cfw.get("confirme"):
                self.q_msg.put("  VERDICT : rotation CONFIRMÉE par relecture "
                               f"(statut final {cfw.get('final')!r}). "
                               "⚠ Vérifie quand même l'EFFET PHYSIQUE "
                               "(slot vide/opaque → le flux change).")
            else:
                self.q_msg.put("  VERDICT : PAS de confirmation en 25 s — "
                               "voir les statuts relus ci-dessus.")

    def _ouvrir_log(self):
        if os.path.isfile(FICHIER_LOG):
            os.startfile(FICHIER_LOG)
        else:
            messagebox.showinfo("Log", f"Aucun log à :\n{FICHIER_LOG}")

    def _on_close(self):
        self._flux_actif = False
        if self.cam is not None:
            try:
                self.cam.close()
            except Exception:
                pass
        self.root.destroy()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--ctypes-sonde":
        # ENFANT de la sonde ctypes (sous-processus isolé, cf. section
        # SONDE CTYPES NATIVE) : pas de fenêtre, JSON sur stdout.
        sys.exit(_ctypes_main(sys.argv))
    root = tk.Tk()
    root.title("Banc de test QHY — AVAStack (diagnostic, même code caméra)")
    root.geometry("1020x860")
    BancQHY(root)
    root.mainloop()


if __name__ == "__main__":
    main()