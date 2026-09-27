# -*- coding: utf-8 -*-
"""Banc de test autonome caméra Touptek/Altair (et clones ToupCam) — la MÊME
DLL que l'appli.

Demande d'Alain (20/09/2026) : tester les caméras Touptek avec le même
programme de détection de leurs possibilités que les bancs QHY
(_diag_camera_qhy.py), Player One (_diag_camera_playerone.py) et SVBONY
(_diag_camera_svbony.py) : capteur, TEC, exposition, gain, black level,
ROI, binning, résolutions, formats, flux, pose (snap), versions.

⚠ CONSTAT FONDATEUR du 20/09/2026 (ce banc) : la sonde
avastack/cameras/touptek.py de la v2.2.0 était FAUSSE contre la DLL réelle
(ToupCam.dll 59.30239.20251209) :
  - Toupcam_get_ExpoTimeRange n'existe PAS → AttributeError au chargement
    (le vrai nom est Toupcam_get_ExpTimeRange) ;
  - Toupcam_Enum (legacy, obsolète) remplit des ToupcamDevice et NON des
    modèles — la sonde lisait du charabia ;
  - Toupcam_Open veut l'ID OPAQUE de la caméra énumérée, pas le nom du modèle.
La sonde a été CORRIGÉE sur l'API moderne Toupcam_EnumV2 / ToupcamDeviceV2
(disposition VALIDÉE empiriquement : 201 modèles lisibles dans la DLL),
conformément à l'entête officiel toupcam.h. Ce banc RÉUTILISE cette sonde
(mtt = avastack/cameras/touptek.py — une seule définition, jamais de copie).

Règles du SDK (entête officiel toupcam.h, miroir INDIGO) :
  - HRESULT : >= 0 = SUCCÈS (S_OK = 0, S_FALSE = 1 = « déjà à la valeur »,
    E_NOTIMPL = non supporté sur ce modèle), < 0 = échec ;
  - exposition en MICROSECONDES, gain analogique en % (100 = 1x),
    températures en unités de 0,1 °C (put_Temperature(-2730) = défaut) ;
  - le TEC se pilote par OPTIONS : TOUPCAM_OPTION_TEC (0x08, on/off) et
    TOUPCAM_OPTION_TECTARGET (0x0f, consigne 0,1 °C) — PAS de
    Toupcam_get/put_CoolerOn dans cette DLL (exports vérifiés un à un) ;
  - flux ÉVÉNEMENTIEL : le callback (thread interne du SDK) annonce les
    frames (TOUPCAM_EVENT_IMAGE = 0x0004), on tire la dernière avec
    Toupcam_PullImage ; ne JAMAIS appeler Stop/Close DANS le callback
    (interblocage documenté) ;
  - pose (still) : Toupcam_Snap → TOUPCAM_EVENT_STILLIMAGE (0x0005) →
    Toupcam_PullStillImage.

⚠ Complément du 21/09/2026 (jalon 50) : les curseurs de l'APPLI gardaient
leurs bornes EN DUR pour Touptek (« Gain (0 – 175) », « Offset (0 – 255) »,
échelles d'expo fixes) — la sonde n'implémentait pas detecter_capacites().
Le banc montre maintenant, pour le NIVEAU DE NOIR (option BLACKLEVEL 0x15),
la plage déduite de la table DOCUMENTÉE de toupcam.h
(TOUPCAM_BLACKLEVELn_MAX = 31 << (n - 8), n = profondeur annoncée par la
caméra) ET la plage RÉELLEMENT CONSTATÉE : le banc POSE les bornes, RELIT
après chaque pose (posé ≠ relu), puis RESTAURE la valeur d'origine.

Lancement (venv, dossier du projet ou %LOCALAPPDATA%/AVAStack) :
    venv/Scripts/python.exe bancs/cameras/_diag_camera_touptek.py
Mode console (détection rapide sans fenêtre) :
    venv/Scripts/python.exe bancs/cameras/_diag_camera_touptek.py --console

⚠ CRASH NATIF : si la fenêtre se ferme brutalement sans message, c'est un
segfault du SDK natif — noter la DERNIÈRE ligne du journal.
⚠ UN SEUL PROGRAMME à la fois peut ouvrir la caméra : fermer le banc avant
de lancer AVAStack, et inversement.
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import ctypes
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import Image, ImageTk

# Le banc importe le code de l'application depuis SON PROPRE dossier
# (fonctionne depuis le dépôt comme depuis %LOCALAPPDATA%/AVAStack).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- chargement DIAGNOSTIQUÉ de l'application (même principe que les bancs
#     POA/SVBONY : symboles attendus vérifiés, message clair si trop ancien).
_ERREUR_CHARGEMENT = ""
_MANQUE = []
try:
    import avastack.cameras.touptek as mtt
except Exception as e:
    mtt = None
    _ERREUR_CHARGEMENT = f"{type(e).__name__} : {e}"

if mtt is not None:
    for _nom in ("_ToupcamDeviceV2", "_ToupcamModelV2", "_HToupCam",
                 "_EVENT_CALLBACK", "TOUPCAM_MAX", "TOUPCAM_EVENT_IMAGE",
                 "TOUPCAM_EVENT_STILLIMAGE", "TOUPCAM_EVENT_ERROR",
                 "TOUPCAM_EVENT_DISCONNECTED", "TOUPCAM_EVENT_NOFRAMETIMEOUT",
                 "TOUPCAM_OPTION_RAW", "TOUPCAM_OPTION_BITDEPTH",
                 "TOUPCAM_OPTION_FAN", "TOUPCAM_OPTION_TEC",
                 "TOUPCAM_OPTION_RGB", "TOUPCAM_OPTION_TECTARGET",
                 "TOUPCAM_OPTION_BLACKLEVEL", "S_OK", "S_FALSE",
                 # jalon 50 : table documentée de la plage du noir + _proto
                 "TOUPCAM_BLACKLEVEL_MIN", "TOUPCAM_BLACKLEVEL_MAX_PAR_BITS",
                 "TOUPCAM_FLAG_BLACKLEVEL", "_proto",
                 "TouptekCamera", "_charger_sdk"):
        if not hasattr(mtt, _nom):
            _MANQUE.append(_nom)

# Le banc est COMPLET seulement si la copie installée expose la sonde V2.
BANC_PRET = (mtt is not None and not _MANQUE)


def message_appli_trop_ancienne():
    """→ texte d'explication quand l'application installée n'expose pas la
    sonde corrigée (cas réel : banc copié sur une installation antérieure à
    la correction API V2 du 20/09/2026)."""
    import avastack
    try:
        version = avastack.AVASTACK_VERSION
    except AttributeError:
        version = "?"

    def dte(p):
        try:
            return time.strftime("%d/%m/%Y %H:%M",
                                 time.localtime(os.path.getmtime(p)))
        except (OSError, TypeError):
            return "?"

    lignes = ["⚠ L'APPLICATION (avastack) EST TROP ANCIENNE POUR CE BANC",
              f"  version avastack  : {version}",
              f"  banc              : {__file__}  ({dte(__file__)})",
              f"  touptek.py        : "
              f"{getattr(mtt, '__file__', 'ABSENT')}  "
              f"({dte(getattr(mtt, '__file__', ''))})"]
    if _ERREUR_CHARGEMENT:
        lignes.append(f"  erreur d'import    : {_ERREUR_CHARGEMENT}")
    if _MANQUE:
        lignes.append(f"  symboles manquants : {', '.join(_MANQUE)}")
    lignes += [
        "",
        "Depuis la correction du 20/09/2026, le banc RÉUTILISE la sonde",
        "de l'application (API V2 Toupcam_EnumV2 / ToupcamDeviceV2).",
        "Depuis le 21/09/2026 (jalon 50), il lui demande aussi la table",
        "DOCUMENTÉE de la plage du niveau de noir (TOUPCAM_BLACKLEVELn_MAX).",
        "",
        "À FAIRE (dossier d'installation, ex. %LOCALAPPDATA%\\AVAStack) :",
        "  copier avastack\\cameras\\touptek.py depuis le dépôt (ou",
        "  réinstaller ≥ 2.21.9), puis relancer ce banc.",
    ]
    return "\n".join(lignes)


# --- constantes du SDK (toupcam.h) -------------------------------------------
# TOUPCAM_FLAG_* (bitmask 64 bits de ToupcamModelV2.flag) — libellés français
FLAGS_NOMS = [
    (0x00000001, "CMOS"), (0x00000002, "CCD progressif"),
    (0x00000004, "CCD interlacé"), (0x00000008, "ROI matériel"),
    (0x00000010, "MONO"), (0x00000020, "bin/skip"),
    (0x00000040, "USB3"), (0x00000080, "TEC"),
    (0x00000100, "USB3 sur port USB2"), (0x00000200, "ST4"),
    (0x00000400, "température lisible"), (0x00000800, "fullwell élevé"),
    (0x00001000, "RAW10"), (0x00002000, "RAW12"),
    (0x00004000, "RAW14"), (0x00008000, "RAW16"),
    (0x00010000, "VENTILATEUR"), (0x00020000, "TEC on/off + consigne"),
    (0x00040000, "ISP"), (0x00080000, "déclencheur logiciel"),
    (0x00100000, "déclencheur externe"), (0x00200000, "déclench. unique"),
    (0x00400000, "blacklevel réglable"),
    (0x0000000100000000, "GMCY8"), (0x0000000200000000, "GMCY12"),
    (0x0000000400000000, "UYVY"), (0x0000000800000000, "CG HCG/LCG"),
    (0x0000001000000000, "obturateur global"),
    (0x0000004000000000, "framerate précis"),
    (0x0000008000000000, "anti-buée (heat)"),
    (0x0000100000000000, "roue à filtres"), (0x0000200000000000, "GigE"),
]

# TOUPCAM_PIXELFORMAT_* (noms)
NOMS_FORMATS_PIXEL = {
    0x00: "RAW8", 0x01: "RAW10", 0x02: "RAW12", 0x03: "RAW14",
    0x04: "RAW16", 0x05: "YUV411", 0x06: "VUYY", 0x07: "YUV444",
    0x08: "RGB888", 0x09: "GMCY8", 0x0A: "GMCY12", 0x0B: "UYVY",
    0x0C: "RAW12PACK", 0x0D: "RAW11", 0x0E: "HDR8HL", 0x0F: "HDR10HL",
    0x10: "HDR11HL", 0x11: "HDR12HL", 0x12: "HDR14HL",
    0x13: "RAW10PACK", 0x14: "RAW14PACK",
}

# TOUPCAM_EVENT_* (noms, pour le journal)
NOMS_EVENEMENTS = {
    0x0001: "EXPOSURE (expo/gain modifiés)", 0x0002: "TEMPTINT",
    0x0004: "IMAGE", 0x0005: "STILLIMAGE", 0x0006: "WBGAIN",
    0x0007: "TRIGGERFAIL", 0x0008: "BLACK", 0x0009: "FFC",
    0x000A: "DFC", 0x000B: "ROI", 0x000C: "LEVELRANGE",
    0x000D: "AUTOEXPO_CONV", 0x000E: "AUTOEXPO_CONVFAIL",
    0x0080: "ERREUR", 0x0081: "DÉBRANCHÉE",
    0x0082: "NO-FRAME TIMEOUT (pas de frame)",
}


def _hresult_non_signe(x):
    """HRESULT en Python (c_int) → valeur hexadécimale d'origine."""
    return x + (1 << 32) if x < 0 else x


# codes d'échec HRESULT (toupcam.h) — nommés pour le journal
NOMS_HRESULT = {
    _hresult_non_signe(0x8000FFFF) & 0xFFFFFFFF: "E_UNEXPECTED (précondition non respectée)",
    _hresult_non_signe(0x80004001) & 0xFFFFFFFF: "E_NOTIMPL (non supporté sur ce modèle)",
    _hresult_non_signe(0x80004003) & 0xFFFFFFFF: "E_POINTER (pointeur NULL/valide non)",
    _hresult_non_signe(0x80004005) & 0xFFFFFFFF: "E_FAIL (échec générique)",
    _hresult_non_signe(0x80070005) & 0xFFFFFFFF: "E_ACCESSDENIED (permissions)",
    _hresult_non_signe(0x8007000E) & 0xFFFFFFFF: "E_OUTOFMEMORY",
    _hresult_non_signe(0x80070057) & 0xFFFFFFFF: "E_INVALIDARG (argument invalide)",
    _hresult_non_signe(0x8007001F) & 0xFFFFFFFF: "E_GEN_FAILURE (matériel/câblage)",
    _hresult_non_signe(0x800700AA) & 0xFFFFFFFF: "E_BUSY (caméra déjà ouverte/occupée)",
    _hresult_non_signe(0x8001010E) & 0xFFFFFFFF: "E_WRONG_THREAD (mauvais thread)",
    _hresult_non_signe(0x8001011F) & 0xFFFFFFFF: "E_TIMEOUT",
    _hresult_non_signe(0x8000000A) & 0xFFFFFFFF: "E_PENDING (données pas encore prêtes)",
    _hresult_non_signe(0x80072743) & 0xFFFFFFFF: "E_UNREACH (réseau GigE injoignable)",
    _hresult_non_signe(0x800704C7) & 0xFFFFFFFF: "E_CANCELLED",
}
# clé signée pour la recherche : ctypes renvoie des c_int NÉGATIFS
NOMS_HRESULT = {k - (1 << 32) if k >= (1 << 31) else k: v
                for k, v in NOMS_HRESULT.items()}

# libellés d'options testées par le banc (TOUPCAM_OPTION_* déjà dans mtt)
NOMS_OPTIONS = {
    mtt.TOUPCAM_OPTION_RAW: "RAW (0=RGB, 1=bayer brut)",
    mtt.TOUPCAM_OPTION_BITDEPTH: "BITDEPTH (0=8 bits, 1=16 bits)",
    mtt.TOUPCAM_OPTION_FAN: "FAN (0=éteint, [1,max]=vitesse)",
    mtt.TOUPCAM_OPTION_TEC: "TEC (0=éteint, 1=allumé)",
    mtt.TOUPCAM_OPTION_RGB: "RGB (0=RGB24)",
    mtt.TOUPCAM_OPTION_TECTARGET: "TECTARGET (0,1 °C, -2730=défaut)",
    mtt.TOUPCAM_OPTION_BLACKLEVEL: "BLACKLEVEL (niveau de noir)",
}

class BancToup:
    """Banc de test Touptek : détection V2, options, TEC, ROI, binning,
    flux événementiel, pose (snap), rapport."""

    def __init__(self, root, mode_console=False):
        self.root = root
        self.mode_console = mode_console
        self.dll = None              # handle DLL (chargé par mtt._charger_sdk)
        self.chemin_dll = None
        self.handle = None           # handle caméra (Toupcam_Open)
        self.nom = ""
        self._fiches = []            # [(displayname, id, modele_V2)] énumérés
        self.ouverte = False
        self.flux_actif = False
        self.caps = None             # dict de faits lus à l'ouverture (verdict)
        self._verdict = []
        self._callback_ref = None    # réf. maintenue vivante (GC !)
        self._verrou = threading.Lock()
        self._derniere = None        # dernière frame live (numpy uint8 HxWx3)
        self._still = None           # dernière pose (numpy uint8 HxWx3)
        self._compteur = 0
        self._w = self._h = 0
        self._ui_q = queue.Queue()   # messages pour Tk (jamais SDK dans Tk)
        self._jobs = queue.Queue()   # travaux séquentiels (appel SDK)
        self._derniere_photo = None
        self._frame_attente = None
        self._tec_allume = False
        self._last_fps_log = 0.0

        self._preparer_dll()
        self._construire_ui()
        if not BANC_PRET:
            self.lbl_fichiers.configure(fg="#aa0000")
            self.btn_ouvrir.configure(state="disabled")
            for ligne in message_appli_trop_ancienne().splitlines():
                self._log(ligne)
        threading.Thread(target=self._boucle_travaux, daemon=True).start()
        self.root.after(80, self._poll_ui)

    # --- SDK ------------------------------------------------------------------

    def _preparer_dll(self):
        """Charge la DLL via le MÊME chargeur que l'appli (mtt._charger_sdk)
        + lie les prototypes ctypes supplémentaires du banc (toupcam.h)."""
        if mtt is None:
            return
        self.dll = mtt._charger_sdk()
        if self.dll is None:
            return
        try:
            self.chemin_dll = self.dll._name
        except AttributeError:
            self.chemin_dll = "?"
        d = self.dll
        H = mtt._HToupCam
        u32, u16 = ctypes.c_uint, ctypes.c_ushort
        p32 = ctypes.POINTER(u32)
        p16 = ctypes.POINTER(u16)
        pi = ctypes.POINTER(ctypes.c_int)
        pf = ctypes.POINTER(ctypes.c_float)
        d.Toupcam_get_ExpoTime.argtypes = [H, p32]
        d.Toupcam_get_ExpoTime.restype = ctypes.c_int
        d.Toupcam_get_RealExpoTime.argtypes = [H, p32]
        d.Toupcam_get_RealExpoTime.restype = ctypes.c_int
        d.Toupcam_get_ExpoAGain.argtypes = [H, p16]
        d.Toupcam_get_ExpoAGain.restype = ctypes.c_int
        d.Toupcam_get_ExpoAGainRange.argtypes = [H, p16, p16, p16]
        d.Toupcam_get_ExpoAGainRange.restype = ctypes.c_int
        d.Toupcam_put_Temperature.argtypes = [H, ctypes.c_short]   # 0,1 °C
        d.Toupcam_put_Temperature.restype = ctypes.c_int
        d.Toupcam_get_Temperature.argtypes = [H,
                                              ctypes.POINTER(ctypes.c_short)]
        d.Toupcam_get_Temperature.restype = ctypes.c_int
        d.Toupcam_get_Option.argtypes = [H, u32, pi]
        d.Toupcam_get_Option.restype = ctypes.c_int
        d.Toupcam_get_FrameRate.argtypes = [H, p32, p32, p32]
        d.Toupcam_get_FrameRate.restype = ctypes.c_int
        d.Toupcam_get_MonoMode.argtypes = [H]
        d.Toupcam_get_MonoMode.restype = ctypes.c_int  # S_OK=mono,S_FALSE=coul
        d.Toupcam_get_MaxBitDepth.argtypes = [H]
        d.Toupcam_get_MaxBitDepth.restype = ctypes.c_int  # bits codés dans hr
        d.Toupcam_get_RawFormat.argtypes = [H, p32, p32]
        d.Toupcam_get_RawFormat.restype = ctypes.c_int
        d.Toupcam_get_PixelSize.argtypes = [H, u32, pf, pf]
        d.Toupcam_get_PixelSize.restype = ctypes.c_int

        d.Toupcam_get_SerialNumber.argtypes = [H, ctypes.c_char_p]  # char[32]
        d.Toupcam_get_SerialNumber.restype = ctypes.c_int
        d.Toupcam_get_FwVersion.argtypes = [H, ctypes.c_char_p]     # char[16]
        d.Toupcam_get_FwVersion.restype = ctypes.c_int
        d.Toupcam_get_HwVersion.argtypes = [H, ctypes.c_char_p]     # char[16]
        d.Toupcam_get_HwVersion.restype = ctypes.c_int
        d.Toupcam_get_FpgaVersion.argtypes = [H, ctypes.c_char_p]   # char[16]
        d.Toupcam_get_FpgaVersion.restype = ctypes.c_int
        d.Toupcam_get_ProductionDate.argtypes = [H, ctypes.c_char_p]  # [10]
        d.Toupcam_get_ProductionDate.restype = ctypes.c_int
        d.Toupcam_get_Revision.argtypes = [H, p16]
        d.Toupcam_get_Revision.restype = ctypes.c_int
        d.Toupcam_put_Roi.argtypes = [H, u32, u32, u32, u32]  # pair, min 8x8
        d.Toupcam_put_Roi.restype = ctypes.c_int
        d.Toupcam_get_Roi.argtypes = [H, p32, p32, p32, p32]
        d.Toupcam_get_Roi.restype = ctypes.c_int
        d.Toupcam_get_ResolutionNumber.argtypes = [H]
        d.Toupcam_get_ResolutionNumber.restype = ctypes.c_int
        d.Toupcam_get_Resolution.argtypes = [H, u32, pi, pi]
        d.Toupcam_get_Resolution.restype = ctypes.c_int
        d.Toupcam_get_ResolutionRatio.argtypes = [H, u32, pi, pi]
        d.Toupcam_get_ResolutionRatio.restype = ctypes.c_int
        d.Toupcam_put_eSize.argtypes = [H, u32]
        d.Toupcam_put_eSize.restype = ctypes.c_int
        d.Toupcam_get_eSize.argtypes = [H, p32]
        d.Toupcam_get_eSize.restype = ctypes.c_int
        d.Toupcam_Snap.argtypes = [H, u32]  # 0xffffffff = résolution courante
        d.Toupcam_Snap.restype = ctypes.c_int
        d.Toupcam_PullStillImage.argtypes = [H, ctypes.c_void_p, ctypes.c_int,
                                             p32, p32]
        d.Toupcam_PullStillImage.restype = ctypes.c_int
        d.Toupcam_put_AutoExpoEnable.argtypes = [H, ctypes.c_int]
        d.Toupcam_put_AutoExpoEnable.restype = ctypes.c_int
        d.Toupcam_get_AutoExpoEnable.argtypes = [H, pi]
        d.Toupcam_get_AutoExpoEnable.restype = ctypes.c_int
        d.Toupcam_get_PixelFormatSupport.argtypes = [H, ctypes.c_char, pi]
        d.Toupcam_get_PixelFormatSupport.restype = ctypes.c_int
        d.Toupcam_get_PixelFormatName.argtypes = [ctypes.c_int]
        d.Toupcam_get_PixelFormatName.restype = ctypes.c_char_p
        d.Toupcam_get_BinningNumber.argtypes = [H]
        d.Toupcam_get_BinningNumber.restype = ctypes.c_int
        d.Toupcam_get_BinningValue.argtypes = [H, u32,
                                               ctypes.POINTER(ctypes.c_char_p)]
        d.Toupcam_get_BinningValue.restype = ctypes.c_int
        d.Toupcam_put_Binning.argtypes = [H, ctypes.c_char_p, ctypes.c_char_p]
        d.Toupcam_put_Binning.restype = ctypes.c_int
        d.Toupcam_get_Speed.argtypes = [H, p16]
        d.Toupcam_get_Speed.restype = ctypes.c_int
        d.Toupcam_put_Speed.argtypes = [H, u16]
        d.Toupcam_put_Speed.restype = ctypes.c_int
        d.Toupcam_get_FanMaxSpeed.argtypes = [H]
        d.Toupcam_get_FanMaxSpeed.restype = ctypes.c_int
        # ⚠ CONSTAT RÉEL (G3M662M, test d'Alain, 20/09/2026) : TOUTE
        # fonction appelée SANS argtypes déclarées reçoit le handle en
        # « int » 32 bits → OverflowError « int too long to convert »
        # (l'affichage s'arrêtait à mi-liste). Ces quatre-là étaient
        # manquantes :
        d.Toupcam_get_MaxSpeed.argtypes = [H]
        d.Toupcam_get_StillResolutionNumber.argtypes = [H]
        d.Toupcam_get_StillResolution.argtypes = [H, u32, pi, pi]
        d.Toupcam_get_StillResolution.restype = ctypes.c_int
        d.Toupcam_get_FinalSize.argtypes = [H, pi, pi]   # après ROI + binning
        d.Toupcam_get_FinalSize.restype = ctypes.c_int

    # --- journal / travaux (jamais d'appel SDK dans le thread Tk) --------------

    def _err(self, hr):
        """→ nom lisible d'un HRESULT (>= 0 = succès !)."""
        if hr == mtt.S_OK:
            return "S_OK"
        if hr == mtt.S_FALSE:
            return "S_FALSE (succès : déjà à la valeur)"
        if hr >= 0:
            return f"hr={hr} (succès)"
        return NOMS_HRESULT.get(hr, f"code {hr:#010x}")

    def _log(self, msg):
        """Journal (thread-safe) : file d'attente + horodatage."""
        self._ui_q.put(("log", time.strftime("%H:%M:%S ") + msg))

    def _travail(self, fn):
        """Empile un travail à exécuter par le thread de travail."""
        self._jobs.put(fn)

    def _boucle_travaux(self):
        """Thread de travail : exécute les fonctions SDK séquentiellement."""
        while True:
            fn = self._jobs.get()
            try:
                fn()
            except Exception as e:
                self._log(f"ERREUR : {e!r}")

    def _poll_ui(self):
        """Côté Tk : vide la file de messages + rafraîchit l'affichage."""
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return                     # fenêtre détruite (fermeture)
        try:
            while True:
                genre, contenu = self._ui_q.get_nowait()
                if genre == "log":
                    self.txt_log.configure(state="normal")
                    self.txt_log.insert("end", contenu + "\n")
                    self.txt_log.see("end")
                    self.txt_log.configure(state="disabled")
                elif genre == "frame":
                    # on ÉCRASE : seule la dernière frame compte (leçon banc
                    # POA — sinon la file grossit pendant que Tk dessine)
                    self._frame_attente = contenu
                elif genre == "fps":
                    self.lbl_fps.configure(text=contenu)
                elif genre == "temp":
                    self.lbl_temp.configure(text=contenu)
                elif genre in ("cams", "ouvert", "ferme", "verdict", "res"):
                    self._maj_apres_evenement(genre, contenu)
        except queue.Empty:
            pass
        if self._frame_attente is not None:
            img, self._frame_attente = self._frame_attente, None
            self._afficher_frame(img)
        # sondage température (léger, via le thread de travail)
        if self.ouverte and not self.flux_actif:
            self._travail(self._travail_temp)
        # cadence rapide PENDANT le flux, lente au repos (leçon banc POA)
        self.root.after(200 if self.flux_actif else 2000, self._poll_ui)

    def _travail_temp(self):
        """Lecture température capteur + consigne TEC (thread de travail).
        Les températures Toupcam sont en UNITÉS DE 0,1 °C (toupcam.h)."""
        if not self.ouverte:
            return
        t = ctypes.c_short(0)
        hr = self.dll.Toupcam_get_Temperature(self.handle, ctypes.byref(t))
        if hr < 0:
            txt = "Capteur : pas de sonde de température (E_NOTIMPL)"
        else:
            txt = f"Capteur : {t.value / 10:.1f} °C (SDK {t.value})"
        consigne = ctypes.c_int(0)
        hr2 = self.dll.Toupcam_get_Option(self.handle,
                                          mtt.TOUPCAM_OPTION_TECTARGET,
                                          ctypes.byref(consigne))
        if hr2 >= 0 and -10000 < consigne.value < 500:
            txt += f" · consigne TEC {consigne.value / 10:.1f} °C"
        txt += " · TEC " + ("ON" if self._tec_allume else "off")
        self._ui_q.put(("temp", txt))

    # --- construction de la fenêtre -------------------------------------------

    def _construire_ui(self):
        self.root.title("Banc de test Touptek/Altair — AVAStack")
        haut = ttk.Frame(self.root)
        haut.pack(fill="x", padx=8, pady=(8, 2))
        self.lbl_fichiers = tk.Label(haut, anchor="w", justify="left")
        self.lbl_fichiers.pack(fill="x")
        self._maj_lbl_fichiers()

        ligne1 = ttk.Frame(self.root)
        ligne1.pack(fill="x", padx=8, pady=2)
        ttk.Button(ligne1, text="🔎 Détecter",
                   command=self._action_detecter).pack(side="left")
        self.cmb_cams = ttk.Combobox(ligne1, width=34, state="readonly")
        self.cmb_cams.pack(side="left", padx=4)
        self.cmb_cams.bind("<<ComboboxSelected>>",
                           lambda e: self._maj_fiche())
        self.btn_ouvrir = ttk.Button(ligne1, text="🔌 Ouvrir",
                                     command=self._action_ouvrir,
                                     state="disabled")
        self.btn_ouvrir.pack(side="left")
        self.btn_fermer = ttk.Button(ligne1, text="Fermer",
                                     command=self._action_fermer,
                                     state="disabled")
        self.btn_fermer.pack(side="left", padx=4)
        self.lbl_etat = ttk.Label(ligne1, text="caméra non ouverte")
        self.lbl_etat.pack(side="left", padx=8)

        ligne2 = ttk.Frame(self.root)
        ligne2.pack(fill="x", padx=8, pady=2)
        ttk.Button(ligne2, text="⚙ Lister les réglages mesurés",
                   command=self._action_lister_controles).pack(side="left")
        ttk.Button(ligne2, text="✅ Verdict « possibilités » → log",
                   command=self._action_verdict).pack(side="left", padx=4)
        ttk.Button(ligne2, text="💾 Sauver le rapport",
                   command=self._action_rapport).pack(side="left", padx=4)

        self.lbl_verdict = tk.Label(self.root, anchor="w", justify="left",
                                    fg="#000080")
        self.lbl_verdict.pack(fill="x", padx=8, pady=2)

        # --- contrôles en direct ---------------------------------------------------
        ctrl = ttk.LabelFrame(self.root, text="Contrôles en direct")
        ctrl.pack(fill="x", padx=8, pady=2)
        ttk.Label(ctrl, text="Expo (µs) :").grid(row=0, column=0)
        self.ent_expo = ttk.Entry(ctrl, width=10)
        self.ent_expo.insert(0, "10000")
        self.ent_expo.grid(row=0, column=1)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_expo).grid(row=0, column=2,
                                                    padx=(2, 8))
        ttk.Label(ctrl, text="Gain (%) :").grid(row=0, column=3)
        self.ent_gain = ttk.Entry(ctrl, width=8)
        self.ent_gain.insert(0, "100")
        self.ent_gain.grid(row=0, column=4)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_gain).grid(row=0, column=5,
                                                    padx=(2, 8))
        ttk.Label(ctrl, text="Noir :").grid(row=0, column=6)
        self.ent_noir = ttk.Entry(ctrl, width=7)
        self.ent_noir.grid(row=0, column=7)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_noir).grid(row=0, column=8,
                                                    padx=(2, 8))
        ttk.Label(ctrl, text="Consigne °C :").grid(row=0, column=9)
        self.ent_temp = ttk.Entry(ctrl, width=7)
        self.ent_temp.insert(0, "-10")
        self.ent_temp.grid(row=0, column=10)
        ttk.Button(ctrl, text="❄ Réguler",
                   command=self._tk_tec_on).grid(row=0, column=11)
        ttk.Button(ctrl, text="⏹ Arrêter",
                   command=lambda: self._travail(self._tec_off)).grid(
            row=0, column=12, padx=2)
        self.lbl_temp = ttk.Label(ctrl, text="Capteur : ? · TEC : ?")
        self.lbl_temp.grid(row=0, column=13, padx=8)

        ttk.Label(ctrl, text="Résolution :").grid(row=1, column=0, pady=(6, 0))
        self.cmb_res = ttk.Combobox(ctrl, width=14, state="disabled",
                                    values=["plein champ"])
        self.cmb_res.current(0)
        self.cmb_res.grid(row=1, column=1, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_resolution).grid(
            row=1, column=2, padx=(2, 8), pady=(6, 0))
        ttk.Label(ctrl, text="Bin :").grid(row=1, column=3, pady=(6, 0))
        self.cmb_bin = ttk.Combobox(ctrl, width=9, state="disabled",
                                    values=["1x1"])
        self.cmb_bin.current(0)
        self.cmb_bin.grid(row=1, column=4, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_bin).grid(row=1, column=5,
                                                   padx=(2, 8), pady=(6, 0))
        ttk.Button(ctrl, text="▶ Flux live",
                   command=self._action_flux).grid(row=1, column=6,
                                                   padx=8, pady=(6, 0))
        ttk.Button(ctrl, text="■ Stop",
                   command=self._action_stop_flux).grid(row=1, column=7,
                                                        pady=(6, 0))
        ttk.Button(ctrl, text="📸 Pose (snap)",
                   command=lambda: self._travail(self._snap)).grid(
            row=1, column=8, padx=8, pady=(6, 0))
        self.lbl_fps = ttk.Label(ctrl, text="")
        self.lbl_fps.grid(row=1, column=9, columnspan=4, padx=8, pady=(6, 0))

        # --- ROI -------------------------------------------------------------------
        roi = ttk.LabelFrame(self.root, text="ROI (Toupcam_put_Roi : départ "
                                              "+ taille, pair, min 8×8)")
        roi.pack(fill="x", padx=8, pady=2)
        for i, (lab, w) in enumerate((("Départ X", 7), ("Départ Y", 7),
                                      ("Largeur", 8), ("Hauteur", 8))):
            ttk.Label(roi, text=lab + " :").grid(row=0, column=2 * i)
            e = ttk.Entry(roi, width=w)
            e.grid(row=0, column=2 * i + 1, padx=(2, 8))
            setattr(self, f"ent_roi{i}", e)
        ttk.Button(roi, text="Poser ROI",
                   command=self._tk_pose_roi).grid(row=0, column=8, padx=4)
        ttk.Button(roi, text="Plein champ",
                   command=lambda: self._travail(self._roi_plein)).grid(
            row=0, column=9, padx=4)
        ttk.Button(roi, text="🅰 Auto-expo on/off",
                   command=lambda: self._travail(self._toggle_autoexpo)).grid(
            row=0, column=10, padx=8)

        # --- aperçu + journal ------------------------------------------------------
        self.lbl_image = tk.Label(self.root, bg="#222222")
        self.lbl_image.pack(fill="x", padx=8, pady=4)
        self.txt_log = tk.Text(self.root, height=14, state="disabled",
                               font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _maj_lbl_fichiers(self):
        """Affiche les fichiers réellement chargés (leçon du banc QHY)."""
        def dte(p):
            try:
                return time.strftime("%d/%m/%Y %H:%M",
                                     time.localtime(os.path.getmtime(p)))
            except OSError:
                return "?"
        mp = getattr(mtt, "__file__", None) or "ABSENT (import impossible)"
        dll = self.chemin_dll or "INTROUVABLE (SDK absent !)"
        self.lbl_fichiers.configure(text=(
            f"DLL SDK    : {dll}  ({dte(dll)})\n"
            f"touptek.py : {mp}  ({dte(mp)})\n"
            f"Sonde      : TouptekCamera / _charger_sdk (réutilisés de "
            f"l'application — le banc n'a PAS sa propre copie)"))
        if self.dll is None:
            self.lbl_fichiers.configure(fg="#aa0000")

    # --- actions (côté Tk : ne font QUE de l'UI + _travail) --------------------

    def _action_detecter(self):
        self._travail(self._detecter)

    def _action_ouvrir(self):
        sel = self.cmb_cams.current()
        if sel < 0:
            return
        self._travail(lambda: self._ouvrir(sel))

    def _action_fermer(self):
        self._travail(self._fermer)

    def _action_lister_controles(self):
        self._travail(self._lister_controles)

    def _action_verdict(self):
        txt = "\n".join(self._verdict) or "Ouvre la caméra d'abord."
        self.lbl_verdict.configure(text=txt)
        for ligne in self._verdict:
            self._log("VERDICT : " + ligne)

    def _maj_fiche(self):
        """Affiche la fiche détaillée de la caméra sélectionnée (Tk)."""
        sel = self.cmb_cams.current()
        if sel < 0 or not self._fiches:
            return
        displayname, ident, modele = self._fiches[sel]
        self._log("=== FICHE (ToupcamDeviceV2 + ToupcamModelV2) ===")
        self._log(f"  nom affiché  : {displayname}")
        self._log(f"  id opaque    : {ident}")
        if modele is None:
            self._log("  (modèle illisible)")
            return
        drapeaux = " · ".join(n for bit, n in FLAGS_NOMS
                              if modele.flag & bit)
        self._log(f"  nom modèle   : {modele.name}")
        self._log(f"  drapeaux     : 0x{modele.flag:016x} = {drapeaux}")
        self._log(f"  capteur      : {modele.xpixsz:.2f} × {modele.ypixsz:.2f} µm"
                  f" · vitesses 0-{modele.maxspeed} · fan max "
                  f"{modele.maxfanspeed}")
        res = [(modele.res[i].width, modele.res[i].height)
               for i in range(modele.preview)]
        self._log(f"  résolutions live ({modele.preview}) : {res}")
        res_s = [(modele.res[i].width, modele.res[i].height)
                 for i in range(modele.still)]
        self._log(f"  résolutions pose ({modele.still}) : {res_s}")

    def _maj_apres_evenement(self, genre, contenu):
        if genre == "cams":
            noms = contenu
            self.cmb_cams.configure(values=noms)
            if noms:
                self.cmb_cams.current(0)
                self._maj_fiche()
                self.btn_ouvrir.configure(state="normal")
        elif genre == "ouvert":
            self.btn_ouvrir.configure(state="disabled")
            self.btn_fermer.configure(state="normal")
            self.lbl_etat.configure(text=f"ouverte : {self.nom}",
                                    foreground="#006600")
        elif genre == "ferme":
            self.btn_ouvrir.configure(state="normal")
            self.btn_fermer.configure(state="disabled")
            self.lbl_etat.configure(text="caméra non ouverte",
                                    foreground="#000000")
            self.lbl_verdict.configure(text="")
        elif genre == "verdict":
            self.lbl_verdict.configure(text=contenu)
        elif genre == "res":
            vals, bins = contenu
            self.cmb_res.configure(values=vals, state="readonly")
            if vals:
                self.cmb_res.current(0)
            if bins:
                self.cmb_bin.configure(values=bins, state="readonly")
                self.cmb_bin.current(0)

    # --- détection / ouverture / fermeture (thread de travail) ------------------

    def _detecter(self):
        """Énumère les caméras (Toupcam_EnumV2) + lit la fiche de chacune."""
        if self.dll is None:
            self._log("✗ SDK Touptek introuvable : place toupcam.dll dans "
                      "le dossier du projet (ou AVASTACK_TOUPTEK_DIR).")
            return
        try:
            ver = self.dll.Toupcam_Version()
            self._log(f"Toupcam_Version() → {ver}")
        except AttributeError:
            pass
        arr = (mtt._ToupcamDeviceV2 * mtt.TOUPCAM_MAX)()
        n = self.dll.Toupcam_EnumV2(arr)
        self._log(f"Toupcam_EnumV2() → {n} caméra(s)")
        if n == 0:
            self._log("Aucune caméra Touptek/Altair détectée (vérifier le "
                      "câble USB et le pilote).")
            return
        self._fiches = []
        noms = []
        for i in range(n):
            dev = arr[i]
            displayname = dev.displayname if mtt.IS_WINDOWS else \
                dev.displayname.decode("utf-8", "replace")
            ident = dev.id if mtt.IS_WINDOWS else dev.id.decode("utf-8",
                                                                "replace")
            modele = dev.model.contents if dev.model else None
            self._fiches.append((displayname, ident, modele))
            noms.append(displayname)
            if modele is not None:
                self._log(f"#{i} : {displayname} · "
                          f"{modele.res[0].width}×{modele.res[0].height} px "
                          f"· flag 0x{modele.flag:016x}")
            else:
                self._log(f"#{i} : {displayname} (modèle illisible)")
        self._ui_q.put(("cams", noms))

    def _ouvrir(self, index):
        """Ouvre la caméra (thread de travail) : Toupcam_Open(id) → mode
        RGB24 → put_Size plein champ → StartPullModeWithCallback → mesures."""
        if not BANC_PRET:
            for ligne in message_appli_trop_ancienne().splitlines():
                self._log(ligne)
            return
        if self.ouverte:
            self._fermer()
        displayname, ident, modele = self._fiches[index]
        self._log(f"=== OUVERTURE #{index} : {displayname} ===")
        self.nom = displayname
        if mtt.IS_WINDOWS:
            ident_arg = ctypes.c_wchar_p(ident)
        else:
            ident_arg = ctypes.c_char_p(ident.encode("utf-8"))
        self.handle = self.dll.Toupcam_Open(
            ctypes.cast(ident_arg, ctypes.c_void_p))
        if not self.handle:
            self._log("✗ Toupcam_Open a échoué (NULL) — caméra occupée ? "
                      "(E_BUSY : fermer AVAStack ou ToupCam/ToupView)")
            return
        self._log(f"  Toupcam_Open OK (handle {self.handle:#x})")

        # mode RGB24 = débayerisation par la caméra (comme dans l'appli) :
        # POSER PUIS RELIRE et logger (leçon des bancs POA/SVBONY)
        hr = self.dll.Toupcam_put_Option(self.handle, mtt.TOUPCAM_OPTION_RAW, 0)
        relu = ctypes.c_int(-1)
        self.dll.Toupcam_get_Option(self.handle, mtt.TOUPCAM_OPTION_RAW,
                                    ctypes.byref(relu))
        self._log(f"  put_Option(RAW, 0) → {self._err(hr)} · relu : {relu.value}")
        mono_hr = self.dll.Toupcam_get_MonoMode(self.handle)
        self._log(f"  MonoMode → {self._err(mono_hr)} "
                  f"({'MONO' if mono_hr == mtt.S_OK else 'COULEUR'})")
        bits_hr = self.dll.Toupcam_get_MaxBitDepth(self.handle)
        self._log(f"  MaxBitDepth → {self._err(bits_hr)}"
                  f"{f' ({bits_hr} bits)' if bits_hr > 0 else ''}")

        # résolution plein champ (index 0) AVANT le démarrage
        if modele is not None and modele.preview > 0:
            w, h = modele.res[0].width, modele.res[0].height
            hr = self.dll.Toupcam_put_Size(self.handle, w, h)
            self._log(f"  put_Size({w}, {h}) → {self._err(hr)}")
            self._w, self._h = w, h
            self._remplir_res(modele)
        else:
            wi, hi = ctypes.c_int(0), ctypes.c_int(0)
            self.dll.Toupcam_get_Size(self.handle, ctypes.byref(wi),
                                      ctypes.byref(hi))
            self._w, self._h = wi.value, hi.value
            self._log(f"  get_Size → {self._w}×{self._h}")

        # démarrage du flux ÉVÉNEMENTIEL (succès = HRESULT >= 0, jamais != 0)
        self._callback_ref = mtt._EVENT_CALLBACK(self._sur_evenement)
        hr = self.dll.Toupcam_StartPullModeWithCallback(
            self.handle, self._callback_ref, None)
        if hr < 0:
            self._log(f"✗ StartPullModeWithCallback → {self._err(hr)}")
            self.dll.Toupcam_Close(self.handle)
            self.handle = None
            return
        self._log(f"  flux événementiel démarré ({self._err(hr)})")
        self.ouverte = True
        self._ui_q.put(("ouvert", None))
        self._lister_controles()
        self._travail_temp()

    def _remplir_res(self, modele):
        """Préremplit la combobox de résolution depuis le modèle + lit les
        valeurs de binning (thread de travail — JAMAIS de SDK dans Tk)."""
        vals = []
        for i in range(modele.preview):
            w, h = modele.res[i].width, modele.res[i].height
            vals.append(f"{i} : {w}×{h}")
        bins = []
        nbins = self.dll.Toupcam_get_BinningNumber(self.handle)
        if nbins > 0:
            for i in range(min(nbins, 8)):
                pv = ctypes.c_char_p()
                if self.dll.Toupcam_get_BinningValue(
                        self.handle, i, ctypes.byref(pv)) >= 0 \
                        and pv.value:
                    bins.append(pv.value.decode("utf-8", "replace") + "×1")
        self._ui_q.put(("res", (vals, bins)))

    def _sur_evenement(self, n_event, ctx):
        """Callback du THREAD INTERNE du SDK — ne JAMAIS bloquer ici, et ne
        JAMAIS appeler Stop/Close (interblocage documenté)."""
        if self.handle is None:
            return
        if n_event == mtt.TOUPCAM_EVENT_IMAGE:
            with self._verrou:
                wi, hi = ctypes.c_int(self._w), ctypes.c_int(self._h)
                self.dll.Toupcam_get_Size(self.handle, ctypes.byref(wi),
                                          ctypes.byref(hi))
                w = ctypes.c_uint(max(1, wi.value))
                h = ctypes.c_uint(max(1, hi.value))
                buf = np.zeros(w.value * h.value * 3, dtype=np.uint8)
                hr = self.dll.Toupcam_PullImage(
                    self.handle, buf.ctypes.data_as(ctypes.c_void_p), 24,
                    ctypes.byref(w), ctypes.byref(h))
                if hr >= 0:
                    self._w, self._h = w.value, h.value
                    self._derniere = buf.reshape(h.value, w.value, 3)
                    self._compteur += 1
        elif n_event == mtt.TOUPCAM_EVENT_STILLIMAGE:
            with self._verrou:
                wi, hi = ctypes.c_int(self._w), ctypes.c_int(self._h)
                w = ctypes.c_uint(max(1, self._w))
                h = ctypes.c_uint(max(1, self._h))
                buf = np.zeros(w.value * h.value * 3, dtype=np.uint8)
                hr = self.dll.Toupcam_PullStillImage(
                    self.handle, buf.ctypes.data_as(ctypes.c_void_p), 24,
                    ctypes.byref(w), ctypes.byref(h))
                if hr >= 0:
                    self._still = buf.reshape(h.value, w.value, 3)
                    self._ui_q.put(("frame", self._still))
                    self._log(f"📸 pose reçue : {w.value}×{h.value} px "
                              f"(RGB24)")
        elif n_event in (mtt.TOUPCAM_EVENT_ERROR, mtt.TOUPCAM_EVENT_DISCONNECTED,
                         mtt.TOUPCAM_EVENT_NOFRAMETIMEOUT):
            self._ui_q.put(("log", time.strftime("%H:%M:%S ")
                            + f"⚠ ÉVÉNEMENT SDK : "
                            f"{NOMS_EVENEMENTS.get(n_event, n_event)}"))

    def _fermer(self):
        """Arrête le flux, coupe le TEC et ferme la caméra (thread de
        travail)."""
        self.flux_actif = False
        if not self.ouverte:
            return
        self._log("=== FERMETURE ===")
        if self._tec_allume:
            self.dll.Toupcam_put_Option(self.handle, mtt.TOUPCAM_OPTION_TEC, 0)
            self._tec_allume = False
        self.dll.Toupcam_Stop(self.handle)
        self.dll.Toupcam_Close(self.handle)
        self.handle = None
        self._callback_ref = None
        self.ouverte = False
        self._log("  Toupcam_Stop + Toupcam_Close → fait")
        self._ui_q.put(("ferme", None))

    # --- mesures / verdict (thread de travail) ----------------------------------

    def _lire_chaine(self, fn, taille):
        """→ str lisible depuis un getter char[taille] (SN, versions…)."""
        buf = ctypes.create_string_buffer(taille + 1)
        hr = fn(self.handle, buf)
        if hr < 0:
            return None
        return buf.value.decode("utf-8", "replace").strip("\x00 ").strip()

    def _eprouver_noir(self, val0, bits):
        """ÉPROUVE la plage du niveau de noir sur la caméra (thread de travail).

        Le banc n'a PAS sa propre mesure : il fait exécuter à la caméra
        OUVERTE la fonction de l'application (TouptekCamera._mesurer_noir —
        dichotomie « posé puis RELU », bornée par la table de toupcam.h), puis
        il lit la valeur pour montrer que la caméra a bien été RESTAURÉE.

        Jalon 51 — CONSTAT RÉEL du 21/09/2026 (Alain, G3M662M) : la table
        annonçait 0 → 7936 (profondeur 16 bits) mais la caméra REFUSE 7936
        (E_INVALIDARG) alors qu'elle ACCEPTE 31 et 30 et refuse 32 → plage
        réelle 0 → 31. Le banc ne suppose donc plus rien : il MESURE.
        → (min, max accepté) ou None si la mesure n'a pas abouti."""
        cam = mtt.TouptekCamera.__new__(mtt.TouptekCamera)
        cam._flag = 0                 # éprouver sans filtre de drapeaux
        maxi = cam._mesurer_noir(self.dll, self.handle, bits, val0)
        relu = ctypes.c_int(0)
        self.dll.Toupcam_get_Option(self.handle, mtt.TOUPCAM_OPTION_BLACKLEVEL,
                                    ctypes.byref(relu))
        self._log(f"  noir bornes: dichotomie posé/relu → max ACCEPTÉ "
                  f"{maxi} · valeur d'origine restaurée : relu {relu.value}")
        return (mtt.TOUPCAM_BLACKLEVEL_MIN, maxi) if maxi else None

    def _lister_controles(self):
        """Tableau des réglages LUS sur la caméra ouverte (Touptek n'expose
        pas de liste de contrôles comme ZWO/SVBONY : on sonde les points
        connus de l'entête officiel, un par un, et on journalise)."""
        if not self.ouverte:
            self._log("Ouvre d'abord la caméra.")
            return
        d = self.dll
        h = self.handle
        faits = {}
        u32, u16, cint, byref = (ctypes.c_uint, ctypes.c_ushort,
                                 ctypes.c_int, ctypes.byref)
        self._log("=== RÉGLAGES MESURÉS (get_*/get_Option, posé ≠ relu) ===")

        # exposition (µs)
        tmin, tmax, tdef = u32(0), u32(0), u32(0)
        hr = d.Toupcam_get_ExpTimeRange(h, byref(tmin), byref(tmax),
                                        byref(tdef))
        if hr >= 0:
            faits["expo"] = (tmin.value, tmax.value, tdef.value)
            self._log(f"  expo      : min {tmin.value} µs · max "
                      f"{tmax.value} µs ({tmax.value / 1e6:.1f} s) · défaut "
                      f"{tdef.value} µs")
        else:
            self._log(f"  expo      : plage illisible ({self._err(hr)})")
        tcur, trel = u32(0), u32(0)
        if d.Toupcam_get_ExpoTime(h, byref(tcur)) >= 0:
            self._log(f"  expo posée: {tcur.value} µs", )
        if d.Toupcam_get_RealExpoTime(h, byref(trel)) >= 0:
            self._log(f"  expo RÉELLE (RealExpoTime) : {trel.value} µs")

        # gain (%)
        gmin, gmax, gdef = u16(0), u16(0), u16(0)
        hr = d.Toupcam_get_ExpoAGainRange(h, byref(gmin), byref(gmax),
                                          byref(gdef))
        if hr >= 0:
            faits["gain"] = (gmin.value, gmax.value, gdef.value)
            self._log(f"  gain      : min {gmin.value} % ({gmin.value / 100:g}x)"
                      f" · max {gmax.value} % ({gmax.value / 100:g}x)"
                      f" · défaut {gdef.value} %")
        else:
            self._log(f"  gain      : plage illisible ({self._err(hr)})")
        gcur = u16(0)
        if d.Toupcam_get_ExpoAGain(h, byref(gcur)) >= 0:
            faits["gain_posé"] = gcur.value
            self._log(f"  gain posé : {gcur.value} %")

        # exposition automatique — ⚠ CONSTAT RÉEL (G3M662M, 20/09/2026) :
        # en mode « continue », l'AE RETIRE la main sur l'expo posée
        # (l'expo manuelle retombait à 350 ms malgré put_ExpoTime)
        mode = cint(0)
        hr = d.Toupcam_get_AutoExpoEnable(h, byref(mode))
        if hr >= 0:
            faits["autoexpo"] = mode.value
            libelle = ("off" if mode.value == 0
                       else "continue" if mode.value == 1
                       else "once" if mode.value == 2
                       else str(mode.value))
            self._log(f"  auto-expos: {libelle}")
            if mode.value != 0:
                self._log("  ⚠ auto-exposition ACTIVE : elle écrase l'expo "
                          "manuelle (bouton 🅰 pour la couper)")
        else:
            self._log(f"  auto-expos: illisible ({self._err(hr)})")

        # vitesse
        vit = u16(0)
        vmax_hr = d.Toupcam_get_MaxSpeed(h)
        if d.Toupcam_get_Speed(h, byref(vit)) >= 0 and vmax_hr >= 0:
            faits["vitesse"] = (vit.value, vmax_hr)
            self._log(f"  vitesse   : {vit.value} (max {vmax_hr})")

        # noir (black level)
        noir = cint(0)
        hr = d.Toupcam_get_Option(h, mtt.TOUPCAM_OPTION_BLACKLEVEL, byref(noir))
        if hr >= 0:
            faits["noir"] = noir.value
            self._log(f"  noir      : {noir.value} (option BLACKLEVEL 0x15)")
            # PLAGE (jalons 50/51) : le SDK n'expose AUCUNE fonction de plage
            # pour le noir — la table DOCUMENTÉE de toupcam.h
            # (TOUPCAM_BLACKLEVELn_MAX = 31 << (n - 8), n = profondeur
            # annoncée) sert de PLAFOND DE RECHERCHE, et la borne réelle est
            # MESURÉE par la fonction de l'application (dichotomie posé/relu,
            # restaurée ensuite) : le constat réel a démenti la table.
            prof = d.Toupcam_get_MaxBitDepth(h)      # bits dans le HRESULT
            plafond = mtt.TOUPCAM_BLACKLEVEL_MAX_PAR_BITS.get(prof)
            self._log(f"  noir plafond: profondeur {prof} bits → table "
                      f"toupcam.h {mtt.TOUPCAM_BLACKLEVEL_MIN} → "
                      f"{plafond if plafond else '? (profondeur HORS table)'}"
                      f" (plafond de recherche, PAS la borne réelle)")
            if plafond:
                faits["noir_plage"] = self._eprouver_noir(noir.value, prof)
        else:
            self._log(f"  noir      : non supporté ({self._err(hr)})")

        # TEC + fan
        tec = cint(0)
        hr = d.Toupcam_get_Option(h, mtt.TOUPCAM_OPTION_TEC, byref(tec))
        if hr >= 0:
            faits["tec"] = tec.value
            self._log(f"  TEC       : {'ALLUMÉ' if tec.value else 'éteint'}"
                      f" (option TEC — PAS de get/put_CoolerOn dans la DLL)")
        cible = cint(0)
        hr = d.Toupcam_get_Option(h, mtt.TOUPCAM_OPTION_TECTARGET,
                                  byref(cible))
        if hr >= 0 and cible.value > -2730:
            faits["tec_cible"] = cible.value
            self._log(f"  TEC cible : {cible.value / 10:.1f} °C")
        temp = ctypes.c_short(0)
        hr = d.Toupcam_get_Temperature(h, byref(temp))
        if hr >= 0:
            faits["temperature"] = temp.value
            self._log(f"  capteur   : {temp.value / 10:.1f} °C")
        else:
            self._log(f"  capteur   : pas de sonde ({self._err(hr)})")
        fan = cint(0)
        hr = d.Toupcam_get_Option(h, mtt.TOUPCAM_OPTION_FAN, byref(fan))
        fmax = d.Toupcam_get_FanMaxSpeed(h)
        if hr >= 0:
            faits["fan"] = (fan.value, fmax if fmax >= 0 else None)
            self._log(f"  ventil.   : {fan.value} (max {fmax})")

        self.caps = faits
        self._construire_verdict()

    def _construire_verdict(self):
        """Verdict « possibilités » : détection des capacités + identité."""
        faits = self.caps or {}
        d = self.dll
        h = self.handle
        mono_hr = d.Toupcam_get_MonoMode(h)
        bits_hr = d.Toupcam_get_MaxBitDepth(h)
        fourcc, bits_px = ctypes.c_uint(0), ctypes.c_uint(0)
        hr_raw = d.Toupcam_get_RawFormat(h, ctypes.byref(fourcc),
                                         ctypes.byref(bits_px))
        fcc = "" if hr_raw < 0 else bytes(
            [fourcc.value & 0xFF, (fourcc.value >> 8) & 0xFF,
             (fourcc.value >> 16) & 0xFF, (fourcc.value >> 24) & 0xFF]
        ).decode("ascii", "replace")
        px = ctypes.c_float(0), ctypes.c_float(0)
        hr_px = d.Toupcam_get_PixelSize(h, 0, ctypes.byref(px[0]),
                                        ctypes.byref(px[1]))
        nres = d.Toupcam_get_ResolutionNumber(h)
        nstill = d.Toupcam_get_StillResolutionNumber(h) \
            if hasattr(d, "Toupcam_get_StillResolutionNumber") else -1
        sn = self._lire_chaine(d.Toupcam_get_SerialNumber, 32) or "?"
        fw = self._lire_chaine(d.Toupcam_get_FwVersion, 16) or "?"
        hw = self._lire_chaine(d.Toupcam_get_HwVersion, 16) or "?"
        fpga = self._lire_chaine(d.Toupcam_get_FpgaVersion, 16) or "?"
        pdate = self._lire_chaine(d.Toupcam_get_ProductionDate, 10) or "?"
        rev = ctypes.c_ushort(0)
        d.Toupcam_get_Revision(h, ctypes.byref(rev))
        # formats de pixel supportés (cmd = -1 (0xFF) → nombre, n → n-ième)
        nfmt = ctypes.c_int(0)
        formats = []
        if d.Toupcam_get_PixelFormatSupport(h, b"\xff",
                                            ctypes.byref(nfmt)) >= 0:
            for i in range(min(nfmt.value, 24)):
                f = ctypes.c_int(0)
                if d.Toupcam_get_PixelFormatSupport(h, bytes([i]),
                                                    ctypes.byref(f)) >= 0:
                    formats.append(NOMS_FORMATS_PIXEL.get(f.value,
                                                          f"0x{f.value:02x}"))
        # binning matériel (valeurs chaîne "1", "2"…)
        bins = []
        nbins = d.Toupcam_get_BinningNumber(h)
        if nbins > 0:
            for i in range(min(nbins, 8)):
                pv = ctypes.c_char_p()
                if d.Toupcam_get_BinningValue(h, i,
                                              ctypes.byref(pv)) >= 0 \
                        and pv.value:
                    bins.append(pv.value.decode("utf-8", "replace"))

        lignes = ["=== VERDICT « POSSIBILITÉS » (mesuré sur la caméra) ===",
                  f"CAPTEUR   : {'MONO' if mono_hr == mtt.S_OK else 'COULEUR'}"
                  f" · profondeur max "
                  f"{bits_hr if bits_hr > 0 else '?'} bits"
                  f" · format brut FourCC={fcc or '?'} à "
                  f"{bits_px.value if hr_raw >= 0 else '?'} bits/pix"]
        if hr_px >= 0:
            lignes.append(f"PIXELS    : {px[0].value:.2f} × "
                          f"{px[1].value:.2f} µm")
        lignes.append(f"RESOLUTIONS : {nres if nres >= 0 else '?'} live · "
                      f"{nstill if nstill >= 0 else '?'} pose")
        if "expo" in faits:
            tmin, tmax, _ = faits["expo"]
            lignes.append(f"EXPOSITION: {tmin} µs → {tmax} µs "
                          f"({tmax / 1e6:g} s max)")
        if "gain" in faits:
            gmin, gmax, _ = faits["gain"]
            lignes.append(f"GAIN      : {gmin} % → {gmax} % "
                          f"({gmax / 100:g}× max, unité % · 100 = 1×)")
        if "tec" in faits:
            cible = faits.get("tec_cible")
            cible_txt = (f"{cible / 10:.1f} °C"
                         if isinstance(cible, (int, float)) else "?")
            lignes.append(f"TEC       : PILOTABLE (option TEC, consigne "
                          f"{cible_txt}, get_Temperature OK)")
        else:
            lignes.append("TEC       : non exposé (get_Option TEC en échec)")
        if "noir" in faits:
            pl = faits.get("noir_plage")
            txt = f"réglable, actuel {faits['noir']}"
            if pl and None not in pl:
                txt += f" · plage CONSTATÉE {pl[0]} → {pl[1]}"
            lignes.append("NOIR      : " + txt)
        else:
            lignes.append("NOIR      : non supporté sur ce modèle")
        lignes.append(f"BINS       : {bins if bins else 'aucun exposé'}")
        lignes.append(f"FORMATS    : {formats if formats else 'non exposés'}")
        lignes.append(f"IDENTITÉ   : SN {sn} · fw {fw} · hw {hw} · fpga {fpga}"
                      f" · révision {rev.value} · produit {pdate}")
        self._verdict = lignes
        self._ui_q.put(("verdict", "\n".join(lignes)))
        for ligne in lignes:
            self._log("VERDICT : " + ligne)

    # --- poses (thread de travail, lecture widgets DANS le thread Tk) -----------

    def _ent_valeur(self, entry, defaut=0):
        try:
            return int(float(entry.get()))
        except (ValueError, tk.TclError):
            return defaut

    def _tk_pose_expo(self):
        val = self._ent_valeur(self.ent_expo, 10000)
        self._travail(lambda: self._pose_expo(val))

    def _tk_pose_gain(self):
        val = self._ent_valeur(self.ent_gain, 100)
        self._travail(lambda: self._pose_gain(val))

    def _tk_pose_noir(self):
        val = self._ent_valeur(self.ent_noir, 0)
        self._travail(lambda: self._pose_noir(val))

    def _tk_tec_on(self):
        cible = self._ent_valeur(self.ent_temp, -10)
        self._travail(lambda: self._tec_on(cible))

    def _tk_pose_resolution(self):
        sel = self.cmb_res.current()
        if sel >= 0:
            self._travail(lambda: self._pose_resolution(sel))

    def _tk_pose_bin(self):
        val = self.cmb_bin.get()
        self._travail(lambda: self._pose_bin(val))

    def _tk_pose_roi(self):
        sx = self._ent_valeur(self.ent_roi0, 0)
        sy = self._ent_valeur(self.ent_roi1, 0)
        w = self._ent_valeur(self.ent_roi2, self._w)
        h = self._ent_valeur(self.ent_roi3, self._h)
        self._travail(lambda: self._pose_roi(sx, sy, w, h))

    def _pose_expo(self, val):
        if not self.ouverte:
            return
        hr = self.dll.Toupcam_put_ExpoTime(self.handle, max(0, val))
        relu = ctypes.c_uint(0)
        self.dll.Toupcam_get_ExpoTime(self.handle, ctypes.byref(relu))
        self._log(f"✓ expo = {val} µs → {self._err(hr)} · relu "
                  f"{relu.value} µs (RealExpoTime = la valeur RÉELLE peut "
                  f"différer)")

    def _pose_gain(self, val):
        if not self.ouverte:
            return
        hr = self.dll.Toupcam_put_ExpoAGain(self.handle,
                                            max(0, min(10000, val)))
        relu = ctypes.c_ushort(0)
        self.dll.Toupcam_get_ExpoAGain(self.handle, ctypes.byref(relu))
        self._log(f"✓ gain = {val} % ({val / 100:g}×) → {self._err(hr)} · "
                  f"relu {relu.value} %")

    def _pose_noir(self, val):
        if not self.ouverte:
            return
        hr = self.dll.Toupcam_put_Option(self.handle,
                                         mtt.TOUPCAM_OPTION_BLACKLEVEL, val)
        relu = ctypes.c_int(0)
        self.dll.Toupcam_get_Option(self.handle, mtt.TOUPCAM_OPTION_BLACKLEVEL,
                                    ctypes.byref(relu))
        self._log(f"✓ noir = {val} → {self._err(hr)} · relu {relu.value}")

    def _tec_on(self, cible):
        """Régulation TEC : put_Option(TEC, 1) puis put_Temperature(cible
        × 10) — les températures sont en unités de 0,1 °C (toupcam.h)."""
        if not self.ouverte:
            return
        hr1 = self.dll.Toupcam_put_Option(self.handle, mtt.TOUPCAM_OPTION_TEC, 1)
        self._log(f"✓ TEC ON → {self._err(hr1)}")
        hr2 = self.dll.Toupcam_put_Temperature(self.handle, cible * 10)
        self._log(f"✓ consigne {cible} °C = {cible * 10} (0,1 °C) → "
                  f"{self._err(hr2)} (attention : le refroidissement prend "
                  f"plusieurs minutes, et l'alimentation 12 V doit être "
                  f"branchée)")
        self._tec_allume = (hr1 >= 0)
        self._travail_temp()

    def _toggle_autoexpo(self):
        """Coupe/rétablit l'auto-exposition (constat réel G3M662M : en
        « continue », l'AE écrase l'expo posée manuellement)."""
        if not self.ouverte:
            return
        actuel = ctypes.c_int(0)
        hr = self.dll.Toupcam_get_AutoExpoEnable(self.handle,
                                                 ctypes.byref(actuel))
        if hr < 0:
            self._log(f"✗ auto-expo illisible ({self._err(hr)})")
            return
        nouveau = 0 if actuel.value != 0 else 1
        hr = self.dll.Toupcam_put_AutoExpoEnable(self.handle, nouveau)
        relu = ctypes.c_int(0)
        self.dll.Toupcam_get_AutoExpoEnable(self.handle, ctypes.byref(relu))
        etat = {0: "OFF (main sur l'expo manuelle)", 1: "CONTINUE",
                2: "UNE FOIS"}.get(relu.value, str(relu.value))
        self._log(f"✓ auto-expo → {etat} ({self._err(hr)}) — reposer "
                  f"l'expo/gain voulus si besoin")

    def _tec_off(self):
        if not self.ouverte:
            return
        hr = self.dll.Toupcam_put_Option(self.handle, mtt.TOUPCAM_OPTION_TEC, 0)
        self._tec_allume = False
        self._log(f"✓ TEC OFF → {self._err(hr)}")
        self._travail_temp()

    def _pose_resolution(self, index):
        """Change la résolution : Stop → put_eSize → re-Start (put_eSize est
        documenté « BEFORE Start » : on ne prend pas de risque)."""
        if not self.ouverte:
            return
        self.dll.Toupcam_Stop(self.handle)
        hr = self.dll.Toupcam_put_eSize(self.handle, index)
        relu = ctypes.c_uint(0)
        self.dll.Toupcam_get_eSize(self.handle, ctypes.byref(relu))
        self._log(f"✓ résolution #{index} → {self._err(hr)} · "
                  f"relu #{relu.value}")
        wi, hi = ctypes.c_int(0), ctypes.c_int(0)
        self.dll.Toupcam_get_Size(self.handle, ctypes.byref(wi),
                                  ctypes.byref(hi))
        self._log(f"  get_Size → {wi.value}×{hi.value}")
        self._w, self._h = wi.value, hi.value
        hr2 = self.dll.Toupcam_StartPullModeWithCallback(
            self.handle, self._callback_ref, None)
        self._log(f"  flux relancé → {self._err(hr2)}")

    def _pose_bin(self, val):
        """Binning MATÉRIEL : Toupcam_put_Binning("2", "Average") — valeurs
        chaînes ("1","2"…), méthode Average/Add/Skip (toupcam.h)."""
        if not self.ouverte:
            return
        valeur = val.split("×")[0].strip() or "1"
        methode = "Average"
        hr = self.dll.Toupcam_put_Binning(self.handle, valeur.encode(),
                                          methode.encode())
        self._log(f"✓ bin {valeur} ({methode}) → {self._err(hr)}"
                  f" (⚠ peut modifier la taille : vérifier get_Size)")

    def _taille_reelle(self):
        """Journalise get_Size ET get_FinalSize — ⚠ CONSTAT RÉEL (G3M662M) :
        get_Roi relu peut être suspecte ; la VÉRITÉ est la taille des
        frames (get_Size) et la taille finale après ROI+binning."""
        wi, hi = ctypes.c_int(0), ctypes.c_int(0)
        self.dll.Toupcam_get_Size(self.handle, ctypes.byref(wi),
                                  ctypes.byref(hi))
        fw, fh = ctypes.c_int(0), ctypes.c_int(0)
        hr = self.dll.Toupcam_get_FinalSize(self.handle, ctypes.byref(fw),
                                            ctypes.byref(fh))
        if hr >= 0:
            self._log(f"  taille des frames : get_Size {wi.value}×{hi.value}"
                      f" · get_FinalSize (après ROI/bin) {fw.value}×"
                      f"{fh.value} — c'est CELA que le flux doit donner")
        else:
            self._log(f"  taille des frames : get_Size {wi.value}×"
                      f"{hi.value} (get_FinalSize : {self._err(hr)})")
        return wi.value, hi.value

    def _pose_roi(self, sx, sy, w, h):
        """ROI : offset + taille (PAIRES, min 8×8 — toupcam.h)."""
        if not self.ouverte:
            return
        sx -= sx % 2
        sy -= sy % 2
        w = max(8, w - w % 2)
        h = max(8, h - h % 2)
        hr = self.dll.Toupcam_put_Roi(self.handle, sx, sy, w, h)
        rx, ry, rw, rh = (ctypes.c_uint(0),) * 4
        hr2 = self.dll.Toupcam_get_Roi(self.handle, ctypes.byref(rx),
                                       ctypes.byref(ry), ctypes.byref(rw),
                                       ctypes.byref(rh))
        if hr >= 0 and hr2 >= 0:
            self._log(f"✓ ROI posée ({sx},{sy} {w}×{h}) → relu "
                      f"({rx.value},{ry.value}) {rw.value}×{rh.value}")
            self._taille_reelle()
        else:
            self._log(f"✗ ROI refusée ({self._err(hr)} / relu "
                      f"{self._err(hr2)})")

    def _roi_plein(self):
        if not self.ouverte:
            return
        hr = self.dll.Toupcam_put_Roi(self.handle, 0, 0, self._w, self._h)
        rx, ry, rw, rh = (ctypes.c_uint(0),) * 4
        self.dll.Toupcam_get_Roi(self.handle, ctypes.byref(rx),
                                 ctypes.byref(ry), ctypes.byref(rw),
                                 ctypes.byref(rh))
        self._log(f"✓ plein champ ({self._err(hr)}) → relu "
                  f"({rx.value},{ry.value}) {rw.value}×{rh.value}")
        self._taille_reelle()

    # --- flux live ---------------------------------------------------------------

    def _action_flux(self):
        if not self.ouverte:
            return
        self.flux_actif = True
        self._compteur = 0
        t0 = time.time()
        threading.Thread(target=self._boucle_flux, args=(t0,),
                         daemon=True).start()

    def _action_stop_flux(self):
        self.flux_actif = False

    def _boucle_flux(self, t0):
        """Thread d'observateur : le SDK pousse les frames via le callback ;
        ce thread surveille le compteur, calcule les fps et pousse la
        dernière frame à l'UI. TOUTE exception est JOURNALISÉE (une
        exception dans un thread secondaire tue le thread SILENCIEUSEMENT —
        constat réel du banc SVBONY 19/09/2026)."""
        try:
            dernier = -1
            silence = 0.0
            while self.flux_actif:
                with self._verrou:
                    cnt = self._compteur
                    img = self._derniere
                if cnt == dernier:
                    silence += 0.05
                    if silence > 10.0:
                        self._log(f"⚠ toujours aucune frame depuis "
                                  f"{silence:.0f} s (expo trop longue ? "
                                  f"flux démarré ?)")
                        silence = 0.0
                    time.sleep(0.05)
                    continue
                dernier = cnt
                silence = 0.0
                if img is not None:
                    fps = cnt / max(time.time() - t0, 0.001)
                    self._ui_q.put(("fps", f"{cnt} frames · {fps:.2f} fps · "
                                           f"{self._w}×{self._h} px (RGB24)"))
                    self._ui_q.put(("frame", img))
                # cadence OFFICIELLE du SDK toutes les ~3 s (croisement)
                if time.time() - self._last_fps_log > 3.0:
                    self._last_fps_log = time.time()
                    nf, nt, tot = (ctypes.c_uint(0),) * 3
                    if self.dll.Toupcam_get_FrameRate(
                            self.handle, ctypes.byref(nf), ctypes.byref(nt),
                            ctypes.byref(tot)) >= 0 and nt.value:
                        self._log(f"  Toupcam_get_FrameRate : {nf.value} "
                                  f"frames / {nt.value} ms → "
                                  f"{nf.value * 1000.0 / nt.value:.2f} fps "
                                  f"(total {tot.value}) — ⚠ compteurs SDK "
                                  f"parfois suspects (constat G3M662M : "
                                  f"« 1000 fps »), le fps MESURÉ ci-dessus "
                                  f"fait foi")
                time.sleep(0.03)
        except Exception:
            import traceback
            self.flux_actif = False
            for ligne in traceback.format_exc().splitlines():
                self._log("💥 FLUX : " + ligne)

    def _snap(self):
        """Pose (still) : Toupcam_Snap → événement STILLIMAGE → la callback
        pousse l'image à l'UI. 0xffffffff = résolution courante."""
        if not self.ouverte:
            return
        hr = self.dll.Toupcam_Snap(self.handle, 0xFFFFFFFF)
        self._log(f"📸 Snap demandé → {self._err(hr)} (l'image arrivera via "
                  f"l'événement STILLIMAGE, patience = durée de la pose)")

    def _afficher_frame(self, img):
        """Convertit et affiche une frame RGB24 dans le label (Tk).
        DÉCIMATION AVANT CALCUL (frame plein format lourde — leçon POA)."""
        pas = max(1, int(max(img.shape[0], img.shape[1]) / 900))
        petit = img[::pas, ::pas]
        pil = Image.fromarray(petit)
        lw = 460
        lh = int(pil.height * lw / pil.width)
        pil = pil.resize((lw, max(1, lh)))
        self._derniere_photo = ImageTk.PhotoImage(pil)
        self.lbl_image.configure(image=self._derniere_photo,
                                 width=lw, height=max(1, lh))

    # --- rapport -----------------------------------------------------------------

    def _action_rapport(self):
        """Écrit le rapport complet dans %TEMP% et affiche le chemin."""
        def dte(p):
            try:
                return time.strftime("%Y-%m-%d %H:%M",
                                     time.localtime(os.path.getmtime(p)))
            except OSError:
                return "?"
        nom = time.strftime("avastack_touptek_diag_%Y%m%d_%H%M%S.txt")
        chemin = os.path.join(os.environ.get("TEMP",
                                             os.path.expanduser("~")), nom)
        lignes = ["Rapport banc Touptek — " + time.strftime(
            "%d/%m/%Y %H:%M:%S"),
            f"DLL          : {self.chemin_dll} ({dte(self.chemin_dll)})",
            f"touptek.py   : {getattr(mtt, '__file__', '?')} "
            f"({dte(getattr(mtt, '__file__', '?'))})",
            "",
            "=== VERDICT « POSSIBILITÉS » ==="]
        lignes += self._verdict or ["(ouvrir la caméra d'abord)"]
        lignes += ["", "=== JOURNAL COMPLET ==="]
        try:
            lignes += self.txt_log.get("1.0", "end").splitlines()
        except Exception:
            pass
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write("\n".join(lignes) + "\n")
            self._log(f"💾 rapport écrit : {chemin}")
        except OSError as e:
            self._log(f"✗ rapport non écrit : {e}")

    # --- mode console (--console) ------------------------------------------------

    def detection_console(self):
        """Détection rapide sans fenêtre : fiche + ouverture + verdict,
        tout imprimé sur stdout, puis fermeture propre."""
        if not BANC_PRET:
            print(message_appli_trop_ancienne())
            return 2
        if self.dll is None:
            print("SDK Touptek introuvable — place toupcam.dll dans le "
                  "dossier du projet.")
            return 1
        print("DLL :", self.chemin_dll)
        try:
            print("version SDK :", self.dll.Toupcam_Version())
        except AttributeError:
            pass
        arr = (mtt._ToupcamDeviceV2 * mtt.TOUPCAM_MAX)()
        n = self.dll.Toupcam_EnumV2(arr)
        print("caméras détectées :", n)
        if n == 0:
            return 1
        for i in range(n):
            dev = arr[i]
            nom = dev.displayname if mtt.IS_WINDOWS else \
                dev.displayname.decode("utf-8", "replace")
            ident = dev.id if mtt.IS_WINDOWS else dev.id.decode("utf-8",
                                                                "replace")
            print(f"  #{i} : {nom} · id {ident}")
        self._fiches = [(arr[0].displayname if mtt.IS_WINDOWS
                         else arr[0].displayname.decode("utf-8", "replace"),
                         arr[0].id if mtt.IS_WINDOWS
                         else arr[0].id.decode("utf-8", "replace"),
                         arr[0].model.contents if arr[0].model else None)]
        self._ouvrir(0)
        if not self.ouverte:
            return 1
        print()
        for ligne in self._verdict:
            print(ligne)
        # fermeture propre (TEC coupé, flux arrêté, caméra fermée)
        self.flux_actif = False
        self._fermer()
        return 0


def main():
    mode_console = "--console" in sys.argv
    if mode_console:
        class _Faux:
            """Root Tk factice pour le mode console (aucune UI créée)."""
            def after(self, *a):
                pass
            def title(self, *a):
                pass
        banc = BancToup.__new__(BancToup)
        banc.root = _Faux()
        banc.mode_console = True
        banc.dll = None
        banc.chemin_dll = None
        banc.handle = None
        banc.nom = ""
        banc._fiches = []
        banc.ouverte = False
        banc.flux_actif = False
        banc.caps = None
        banc._verdict = []
        banc._callback_ref = None
        banc._verrou = threading.Lock()
        banc._derniere = None
        banc._still = None
        banc._compteur = 0
        banc._w = banc._h = 0
        banc._ui_q = queue.Queue()
        banc._jobs = queue.Queue()
        banc._derniere_photo = None
        banc._frame_attente = None
        banc._tec_allume = False
        banc._last_fps_log = 0.0
        banc._preparer_dll()
        banc._log = print
        sys.exit(banc.detection_console())
    root = tk.Tk()
    banc = BancToup(root)
    if not BANC_PRET:
        messagebox.showerror("Banc Touptek — application trop ancienne",
                             message_appli_trop_ancienne())
    root.mainloop()


if __name__ == "__main__":
    main()
















