# -*- coding: utf-8 -*-
"""Caméras Touptek — et TOUS leurs clones OEM (Altair, et autres marques
revendant l'électronique ToupCam : UCMOS, U3CMOS, GCMOS, EXCCD…).

SDK natif officiel (toupcam.dll / libtoupcam.so / libtoupcam.dylib,
téléchargeable sur touptek.com) chargé via ctypes, cf. sdk_loader.py.
Une seule classe gère N'IMPORTE QUELLE caméra ToupCam branchée : les
caractéristiques (résolutions, mono/couleur) sont lues sur la caméra.

API dérivée de la documentation officielle Toupcam (docs embarquées dans le
SDK) et du wrapper NMGRL/toupcam (Apache-2.0, Jake Ross) — seules les
fonctions utilisées par AVAStack sont reprises.

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

# --- constantes du SDK Toupcam ---------------------------------------------
TOUPCAM_EVENT_IMAGE = 4          # image live disponible

TOUPCAM_MAX = 16                 # nombre max de caméras énumérables
MAX_RES = 32                     # résolutions max par caméra (TOUPCAM_MAX)

# options
TOUPCAM_OPTION_RAW = 4           # 0 = RGB (défaut), 1 = bayer brut


class _ToupcamResolution(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint),
                ("height", ctypes.c_uint)]


class _ToupcamModel(ctypes.Structure):
    _fields_ = [("name", ctypes.c_wchar_p if IS_WINDOWS else ctypes.c_char_p),
                ("flag", ctypes.c_uint),
                ("maxspeed", ctypes.c_uint),
                ("preview", ctypes.c_uint),
                ("still", ctypes.c_uint),
                ("res", _ToupcamResolution * MAX_RES)]


# type du handle opaque renvoyé par Toupcam_Open
_HToupCam = ctypes.c_void_p

# signature du callback événementiel : void cb(unsigned nEvent, void* ctx)
_EVENT_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_uint, ctypes.c_void_p) \
    if IS_WINDOWS else ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_void_p)


def _charger_sdk():
    """Charge toupcam.dll/.so/.dylib → objet DLL (None si absent)."""
    nom = nom_bibliotheque("toupcam", IS_WINDOWS, IS_MACOS)
    try:
        dll = charger_dll(nom, "AVASTACK_TOUPTEK_DIR", ("sdk", ""))
    except (RuntimeError, OSError):
        return None
    # signatures
    dll.Toupcam_Enum.argtypes = [ctypes.POINTER(_ToupcamModel * TOUPCAM_MAX)]
    dll.Toupcam_Enum.restype = ctypes.c_uint
    dll.Toupcam_Open.argtypes = [ctypes.c_void_p]     # ToupcamInst* (id) ou NULL
    dll.Toupcam_Open.restype = _HToupCam
    dll.Toupcam_Close.argtypes = [_HToupCam]
    dll.Toupcam_StartPullModeWithCallback.argtypes = [_HToupCam, _EVENT_CALLBACK,
                                                      ctypes.c_void_p]
    dll.Toupcam_Stop.argtypes = [_HToupCam]
    dll.Toupcam_PullImage.argtypes = [_HToupCam, ctypes.c_void_p, ctypes.c_int,
                                      ctypes.POINTER(ctypes.c_uint),
                                      ctypes.POINTER(ctypes.c_uint)]
    dll.Toupcam_get_Size.argtypes = [_HToupCam, ctypes.POINTER(ctypes.c_long),
                                     ctypes.POINTER(ctypes.c_long)]
    dll.Toupcam_put_Size.argtypes = [_HToupCam, ctypes.c_long, ctypes.c_long]
    dll.Toupcam_put_ExpoTime.argtypes = [_HToupCam, ctypes.c_uint]    # µs
    dll.Toupcam_put_ExpoAGain.argtypes = [_HToupCam, ctypes.c_ushort]  # %
    dll.Toupcam_get_ExpoTimeRange.argtypes = [_HToupCam,
                                              ctypes.POINTER(ctypes.c_uint),
                                              ctypes.POINTER(ctypes.c_uint),
                                              ctypes.POINTER(ctypes.c_uint)]
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
        arr = (_ToupcamModel * TOUPCAM_MAX)()
        n = _DLL.Toupcam_Enum(ctypes.byref(arr))
        noms = []
        for i in range(n):
            nom = arr[i].name
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

    def open(self):
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            raise RuntimeError("SDK Touptek introuvable : télécharge le SDK "
                               "sur touptek.com et place toupcam.dll dans le "
                               "dossier du projet (ou AVASTACK_TOUPTEK_DIR).")
        arr = (_ToupcamModel * TOUPCAM_MAX)()
        n = _DLL.Toupcam_Enum(ctypes.byref(arr))
        if n == 0:
            raise RuntimeError("Aucune caméra Touptek/Altair détectée")
        idx = min(self.index, n - 1)
        nom = arr[idx].name
        self.name = (nom if IS_WINDOWS else nom.decode("utf-8", "replace"))

        # Toupcam_Open(NULL) ouvre la première ; on passe l'identifiant de
        # l'instance choisie (champ name = identifiant pour Touptek)
        if IS_WINDOWS:
            ident = ctypes.c_wchar_p(nom)
        else:
            ident = ctypes.c_char_p(nom.encode("utf-8"))
        self._handle = _DLL.Toupcam_Open(ctypes.cast(ident, ctypes.c_void_p))
        if not self._handle:
            raise RuntimeError(f"Ouverture impossible : {self.name}")

        # résolution : la première (pleine capteur) par défaut
        if arr[idx].preview > 0:
            w, h = arr[idx].res[0].width, arr[idx].res[0].height
            _DLL.Toupcam_put_Size(self._handle, w, h)
            self._w, self._h = w, h

        # mode RGB (débayerisation par la caméra) — valeur 0 = RGB par défaut,
        # explicite par sûreté (option RAW = 1 n'est pas ce qu'on veut ici)
        _DLL.Toupcam_put_Option(self._handle, TOUPCAM_OPTION_RAW, 0)

        # démarrage du flux événementiel : le callback du SDK remplit
        # self._derniere via Toupcam_PullImage
        self._callback_ref = _EVENT_CALLBACK(self._sur_evenement)
        if _DLL.Toupcam_StartPullModeWithCallback(self._handle,
                                                  self._callback_ref,
                                                  None) != 0:
            raise RuntimeError(f"Démarrage du flux impossible : {self.name}")

    def _sur_evenement(self, n_event, ctx):
        """Callback du thread interne du SDK — NE JAMAIS bloquer ici."""
        if n_event != TOUPCAM_EVENT_IMAGE or not self._handle:
            return
        w = ctypes.c_uint(self._w)
        h = ctypes.c_uint(self._h)
        _DLL.Toupcam_get_Size(self._handle, ctypes.byref(w), ctypes.byref(h))
        nbytes = w.value * h.value * self._bits
        buf = np.zeros(nbytes, dtype=np.uint8)
        err = _DLL.Toupcam_PullImage(self._handle, buf.ctypes.data_as(ctypes.c_void_p),
                                     self._bits * 8, ctypes.byref(w), ctypes.byref(h))
        if err != 0:
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
        # exposition en µs, gain analogique en % (0-1000 selon modèles)
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
