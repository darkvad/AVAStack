# -*- coding: utf-8 -*-
"""Caméras Touptek — et TOUS leurs clones OEM (Altair, et autres marques
revendant l'électronique ToupCam : UCMOS, U3CMOS, GCMOS, EXCCD…).

SDK natif officiel (toupcam.dll / libtoupcam.so / libtoupcam.dylib,
téléchargeable sur touptek.com) chargé via ctypes, cf. sdk_loader.py.
Une seule classe gère N'IMPORTE QUELLE caméra ToupCam branchée : les
caractéristiques (résolutions, mono/couleur) sont lues sur la caméra.

⚠ API V2 UNIQUEMENT (correction du 20/09/2026, banc _diag_camera_touptek) :
la première version utilisait l'API legacy (Toupcam_Enum + tableau de
« ToupcamModel ») et Toupcam_get_ExpoTimeRange — TOUTES DEUX FAUSSES contre
la DLL réelle (ToupCam.dll 59.30239.20251209 du dépôt) :
  - Toupcam_get_ExpoTimeRange n'existe PAS (le vrai nom est
    Toupcam_get_ExpTimeRange) → AttributeError au chargement de la DLL ;
  - Toupcam_Enum (déclarée OBSOLÈTE dans l'entête officiel toupcam.h) remplit
    un tableau de ToupcamDevice {pointeur modèle, nom affiché, id} et NON un
    tableau de modèles — lire « arr[i].name » sur ce buffer donnait du
    charabia (constat réel : le champ flag du modèle AE676C était lu comme
    « maxspeed » à 1032) ;
  - Toupcam_Open veut l'ID OPAQUE de la caméra énumérée (champ id), pas le
    nom du modèle.
On utilise donc l'API moderne Toupcam_EnumV2 / ToupcamDeviceV2 — disponible
dans la DLL et VALIDÉE empiriquement sur celle du dépôt (201 modèles lisibles,
champs cohérents), conforme à l'entête officiel toupcam.h (miroir INDIGO,
v60.32499).

Règles du SDK (entête officiel toupcam.h) :
  - HRESULT : >= 0 = SUCCÈS (S_OK = 0, S_FALSE = 1 « déjà à la valeur »),
    < 0 = échec (E_NOTIMPL = « non supporté sur ce modèle » notamment) ;
  - exposition en MICROSECONDES, gain en % (100 = 1x), températures en
    unités de 0,1 °C (put_Temperature(-2730) = valeur par défaut du modèle) ;
  - Windows : __stdcall et chaînes wchar_t ; le callback événementiel tourne
    sur un thread INTERNE du SDK : ne JAMAIS y appeler Stop/Close
    (interblocage documenté).

Particularité Touptek : le mode « pull » est événementiel (callback appelé
par un thread interne du SDK quand une image arrive). Pour coller à
l'interface synchrone read() de CameraBase, on stocke la dernière frame dans
un buffer protégé par un verrou, et read() la renvoie si nouvelle (None
sinon) — la boucle d'acquisition gère déjà le None.

Formats : RGB24 (couleur, débayerisation PAR LA CAMÉRA) ou mono 8 bits.
Le mode RAW (bayer brut) existe mais nécessite un décodage par capteur —
inutile ici puisque la caméra sait débayeriser elle-même, comme ZWO/POA.
"""

import ctypes
import platform
import threading
import numpy as np

from .base import CameraBase
from .sdk_loader import charger_dll, nom_bibliotheque

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

# --- constantes du SDK Toupcam (entête officiel toupcam.h) ------------------
TOUPCAM_MAX = 128                 # nombre max de caméras énumérables

TOUPCAM_EVENT_EXPOSURE = 0x0001   # expo/gain modifiés
TOUPCAM_EVENT_IMAGE = 0x0004      # image live disponible
TOUPCAM_EVENT_STILLIMAGE = 0x0005 # pose (still) disponible
TOUPCAM_EVENT_ERROR = 0x0080
TOUPCAM_EVENT_DISCONNECTED = 0x0081
TOUPCAM_EVENT_NOFRAMETIMEOUT = 0x0082

# options (TOUPCAM_OPTION_*)
TOUPCAM_OPTION_RAW = 0x04         # 0 = RGB (défaut), 1 = bayer brut
TOUPCAM_OPTION_BITDEPTH = 0x06    # 0 = 8 bits, 1 = 16 bits (mono/RAW)
TOUPCAM_OPTION_FAN = 0x07         # 0 = éteint, [1, max] = vitesse
TOUPCAM_OPTION_TEC = 0x08         # 0 = TEC éteint, 1 = TEC allumé
TOUPCAM_OPTION_RGB = 0x0C         # 0 = RGB24 (flux de l'appli)
TOUPCAM_OPTION_TECTARGET = 0x0F   # consigne TEC en 0,1 °C (-2730 = défaut)
TOUPCAM_OPTION_BLACKLEVEL = 0x15  # niveau de noir (si FLAG_BLACKLEVEL)

# HRESULT remarquables
S_OK = 0                          # succès
S_FALSE = 1                       # succès « déjà à la valeur » (mono/couleur)

# type de chaîne selon l'OS (Windows = UTF-16 wchar_t, ailleurs char)
_WSTR = ctypes.c_wchar_p if IS_WINDOWS else ctypes.c_char_p
_WBUF = ctypes.c_wchar * 64 if IS_WINDOWS else ctypes.c_char * 64

class _ToupcamResolution(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint),
                ("height", ctypes.c_uint)]


class _ToupcamModelV2(ctypes.Structure):
    """Fiche statique d'un modèle (ToupcamModelV2, toupcam.h)."""
    _fields_ = [("name", _WSTR),
                ("flag", ctypes.c_uint64),       # TOUPCAM_FLAG_*, 64 bits
                ("maxspeed", ctypes.c_uint),
                ("preview", ctypes.c_uint),      # nb de résolutions live
                ("still", ctypes.c_uint),        # nb de résolutions still
                ("maxfanspeed", ctypes.c_uint),
                ("ioctrol", ctypes.c_uint),
                ("xpixsz", ctypes.c_float),      # pixel en µm
                ("ypixsz", ctypes.c_float),
                ("res", _ToupcamResolution * 16)]


class _ToupcamDeviceV2(ctypes.Structure):
    """Une caméra branchée énumérée (ToupcamDeviceV2, toupcam.h)."""
    _fields_ = [("displayname", _WBUF),
                ("id", _WBUF),                   # id opaque pour Toupcam_Open
                ("model", ctypes.POINTER(_ToupcamModelV2))]


# type du handle opaque renvoyé par Toupcam_Open
_HToupCam = ctypes.c_void_p

# signature du callback événementiel : void cb(unsigned nEvent, void* ctx)
# (stdcall sur Windows, cf. PTOUPCAM_EVENT_CALLBACK dans toupcam.h)
_EVENT_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_uint, ctypes.c_void_p) \
    if IS_WINDOWS else ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_void_p)


def _charger_sdk():
    """Charge toupcam.dll/.so/.dylib → objet DLL (None si absent)."""
    nom = nom_bibliotheque("toupcam", IS_WINDOWS, IS_MACOS)
    try:
        dll = charger_dll(nom, "AVASTACK_TOUPTEK_DIR", ("sdk", ""))
    except (RuntimeError, OSError):
        return None
    # signatures — uniquement ce que l'application utilise ; le banc
    # _diag_camera_touptek.py déclare les siennes EN PLUS, sur le MÊME objet
    dll.Toupcam_Version.restype = _WSTR
    dll.Toupcam_EnumV2.argtypes = [
        ctypes.POINTER(_ToupcamDeviceV2 * TOUPCAM_MAX)]
    dll.Toupcam_EnumV2.restype = ctypes.c_uint
    dll.Toupcam_Open.argtypes = [ctypes.c_void_p]     # camId (wchar*) ou NULL
    dll.Toupcam_Open.restype = _HToupCam
    dll.Toupcam_Close.argtypes = [_HToupCam]
    dll.Toupcam_StartPullModeWithCallback.argtypes = [_HToupCam,
                                                      _EVENT_CALLBACK,
                                                      ctypes.c_void_p]
    dll.Toupcam_StartPullModeWithCallback.restype = ctypes.c_int
    dll.Toupcam_Stop.argtypes = [_HToupCam]
    dll.Toupcam_Stop.restype = ctypes.c_int
    dll.Toupcam_PullImage.argtypes = [_HToupCam, ctypes.c_void_p,
                                      ctypes.c_int,
                                      ctypes.POINTER(ctypes.c_uint),
                                      ctypes.POINTER(ctypes.c_uint)]
    dll.Toupcam_PullImage.restype = ctypes.c_int
    dll.Toupcam_get_Size.argtypes = [_HToupCam,
                                     ctypes.POINTER(ctypes.c_int),
                                     ctypes.POINTER(ctypes.c_int)]
    dll.Toupcam_get_Size.restype = ctypes.c_int
    dll.Toupcam_put_Size.argtypes = [_HToupCam, ctypes.c_int, ctypes.c_int]
    dll.Toupcam_put_Size.restype = ctypes.c_int
    dll.Toupcam_put_ExpoTime.argtypes = [_HToupCam, ctypes.c_uint]    # µs
    dll.Toupcam_put_ExpoTime.restype = ctypes.c_int
    dll.Toupcam_put_ExpoAGain.argtypes = [_HToupCam, ctypes.c_ushort] # %
    dll.Toupcam_put_ExpoAGain.restype = ctypes.c_int
    dll.Toupcam_get_ExpTimeRange.argtypes = [
        _HToupCam, ctypes.POINTER(ctypes.c_uint),
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
    dll.Toupcam_get_ExpTimeRange.restype = ctypes.c_int
    dll.Toupcam_put_Option.argtypes = [_HToupCam, ctypes.c_uint, ctypes.c_int]
    dll.Toupcam_put_Option.restype = ctypes.c_int
    return dll

_DLL = None          # chargé paresseusement (l'import sans matériel ne doit pas rater)


class TouptekCamera(CameraBase):
    """Une caméra Touptek/clone connectée (index = position dans l'énumération)."""

    @staticmethod
    def lister():
        """→ noms des caméras ToupCam branchées ('' si SDK absent)."""
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            return []
        arr = (_ToupcamDeviceV2 * TOUPCAM_MAX)()
        n = _DLL.Toupcam_EnumV2(arr)
        noms = []
        for i in range(n):
            nom = arr[i].displayname
            noms.append(nom if IS_WINDOWS
                        else nom.decode("utf-8", "replace"))
        return noms

    # --- cycle de vie -----------------------------------------------------
    def __init__(self, index=0):
        self.index = index
        self.name = f"Touptek #{index}"
        self._handle = None
        self._callback_ref = None        # réf. maintenue vivante (GC !)
        self._verrou = threading.Lock()
        self._derniere = None            # (numpy, compteur) protégé par verrou
        self._compteur = 0               # incrémenté à chaque frame arrivée
        self._compteur_lu = 0            # dernier compteur vu par read()
        self._bits = 3                   # RGB24 = 3 octets/pixel (ou 1 = mono8)
        self._w = self._h = 0

    def _identifiant(self, dev):
        """→ l'ID opaque d'un ToupcamDeviceV2, typé pour Toupcam_Open."""
        raw = dev.id
        return ctypes.c_wchar_p(str(raw)) if IS_WINDOWS \
            else ctypes.c_char_p(bytes(raw))

    def open(self):
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            raise RuntimeError("SDK Touptek introuvable : télécharge le SDK "
                               "sur touptek.com et place toupcam.dll dans le "
                               "dossier du projet (ou AVASTACK_TOUPTEK_DIR).")
        arr = (_ToupcamDeviceV2 * TOUPCAM_MAX)()
        n = _DLL.Toupcam_EnumV2(arr)
        if n == 0:
            raise RuntimeError("Aucune caméra Touptek/Altair détectée")
        idx = min(self.index, n - 1)
        dev = arr[idx]
        self.name = (dev.displayname if IS_WINDOWS
                     else dev.displayname.decode("utf-8", "replace"))

        # Toupcam_Open(camId) : l'ID OPAQUE de la caméra énumérée (champ id),
        # JAMAIS le nom du modèle (leçon du 20/09/2026). NULL = la première.
        self._handle = _DLL.Toupcam_Open(
            ctypes.cast(self._identifiant(dev), ctypes.c_void_p))
        if not self._handle:
            raise RuntimeError(f"Ouverture impossible : {self.name}")

        # résolution : la première (plein capteur) par défaut
        modele = dev.model.contents if dev.model else None
        if modele is not None and modele.preview > 0:
            w, h = modele.res[0].width, modele.res[0].height
            _DLL.Toupcam_put_Size(self._handle, w, h)
            self._w, self._h = w, h

        # mode RGB (débayerisation par la caméra) — valeur 0 = RGB par défaut,
        # explicite par sûreté (option RAW = 1 n'est pas ce qu'on veut ici)
        _DLL.Toupcam_put_Option(self._handle, TOUPCAM_OPTION_RAW, 0)

        # démarrage du flux événementiel : le callback du SDK remplit
        # self._derniere via Toupcam_PullImage (succès = HRESULT >= 0,
        # S_FALSE = 1 possible — ne JAMAIS tester « != 0 »)
        self._callback_ref = _EVENT_CALLBACK(self._sur_evenement)
        if _DLL.Toupcam_StartPullModeWithCallback(self._handle,
                                                  self._callback_ref,
                                                  None) < 0:
            raise RuntimeError(f"Démarrage du flux impossible : {self.name}")

    def _sur_evenement(self, n_event, ctx):
        """Callback du thread interne du SDK — NE JAMAIS bloquer ici
        (ni Stop/Close : interblocage documenté dans toupcam.h)."""
        if n_event != TOUPCAM_EVENT_IMAGE or not self._handle:
            return
        wi = ctypes.c_int(self._w)
        hi = ctypes.c_int(self._h)
        _DLL.Toupcam_get_Size(self._handle, ctypes.byref(wi), ctypes.byref(hi))
        w = ctypes.c_uint(max(1, wi.value))
        h = ctypes.c_uint(max(1, hi.value))
        nbytes = w.value * h.value * self._bits
        buf = np.zeros(nbytes, dtype=np.uint8)
        err = _DLL.Toupcam_PullImage(self._handle,
                                     buf.ctypes.data_as(ctypes.c_void_p),
                                     self._bits * 8,
                                     ctypes.byref(w), ctypes.byref(h))
        if err < 0:                       # échec (HRESULT < 0)
            return
        self._w, self._h = w.value, h.value
        img = (buf.reshape(h.value, w.value, 3).astype(np.float32) / 255.0
               if self._bits == 3
               else buf.reshape(h.value, w.value).astype(np.float32) / 255.0)
        with self._verrou:
            self._derniere = img
            self._compteur += 1

    def read(self):
        """→ dernière frame arrivée depuis l'appel précédent, sinon None."""
        if self._handle is None:
            return None
        with self._verrou:
            if self._compteur == self._compteur_lu:
                return None             # rien de nouveau depuis la dernière fois
            self._compteur_lu = self._compteur
            return self._derniere

    def apply_settings(self, exposure_ms, gain):
        if self._handle is None:
            return
        # exposition en µs, gain analogique en % (100 = 1x selon l'entête)
        _DLL.Toupcam_put_ExpoTime(self._handle, int(exposure_ms * 1000))
        _DLL.Toupcam_put_ExpoAGain(self._handle, int(gain * 100))

    def close(self):
        if self._handle is not None and _DLL is not None:
            try:
                _DLL.Toupcam_Stop(self._handle)
                _DLL.Toupcam_Close(self._handle)
            except Exception:
                pass
            finally:
                self._handle = None
                self._callback_ref = None



