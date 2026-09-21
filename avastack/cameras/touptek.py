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

⚠ CAPACITÉS (correctif du 21/09/2026, jalon 50 — constat RÉEL d'Alain) : les
curseurs Expo/Gain/Offset de l'appli restaient sur leurs bornes EN DUR
(« Gain (0 – 175) », « Offset (0 – 255) », échelles d'expo fixes) alors que
le banc mesurait 100 µs → 1000 s et 100 % → 15000 % : TouptekCamera
n'implémentait PAS `detecter_capacites()` (seules QHY, Player One, SVBONY et
ZWO le faisaient). Elle le fait maintenant — relevé DIRECT des plages sur la
caméra ouverte (get_ExpTimeRange, get_ExpoAGainRange, option BLACKLEVEL) — et
elle POSE aussi le niveau de noir (option 0x15 : c'est l'« offset » chez
Touptek). Conséquence sur les unités : le gain de l'appli est en POUR CENT
(unité du SDK, 100 = 1×), comme les autres marques passent leurs unités SDK
telles quelles ; l'auto-exposition de la caméra est COUPÉE quand l'appli pose
ses réglages (mesuré : l'AE « continue » écrase l'expo posée).

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
from .capacites import Capacites
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
TOUPCAM_OPTION_TECTARGET_RANGE = 0x6D   # [RO] plage de consigne TEC :
                                        # min = 16 bits bas, max = 16 bits
                                        # hauts (chacun SIGNÉ, en 0,1 °C)

# TOUPCAM_FLAG_BLACKLEVEL : la caméra sait LIRE et POSER le niveau de noir
TOUPCAM_FLAG_BLACKLEVEL = 0x00400000

# Plage du niveau de noir — table DOCUMENTÉE de toupcam.h (jalon 50) :
#   #define TOUPCAM_BLACKLEVEL_MIN     0
#   #define TOUPCAM_BLACKLEVEL8_MAX    31        (bitdepth  8)
#   #define TOUPCAM_BLACKLEVEL10_MAX   (31 * 4)  (bitdepth 10)
#   …  11 → ×8 · 12 → ×16 · 14 → ×64 · 16 → ×256
# ⚠ CONSTAT RÉEL DU 21/09/2026 (Alain, G3M662M, banc) : cette table est un
# PLAFOND DE RECHERCHE, pas la vérité — la caméra annonce 16 bits mais REFUSE
# 7936 (E_INVALIDARG), accepte 31 et 30, refuse 32 : sa plage réelle est
# 0 → 31 (celle de la profondeur 8 bits). Le SDK n'expose donc AUCUNE plage
# fiable : on ÉPROUVE (dichotomie posé/relu, cf. _mesurer_noir) et la table
# ne sert qu'à BORNER la recherche (jamais écrire n'importe quoi).
TOUPCAM_BLACKLEVEL_MIN = 0
TOUPCAM_BLACKLEVEL_MAX_PAR_BITS = {8: 31, 10: 31 * 4, 11: 31 * 8,
                                   12: 31 * 16, 14: 31 * 64, 16: 31 * 256}

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


# pointeurs réutilisés par les signatures (lisibilité)
_p_uint = ctypes.POINTER(ctypes.c_uint)
_p_int = ctypes.POINTER(ctypes.c_int)
_p_ushort = ctypes.POINTER(ctypes.c_ushort)
_p_float = ctypes.POINTER(ctypes.c_float)


def _proto(dll, nom, argtypes, restype=ctypes.c_int):
    """Déclare la signature de `nom` SI le symbole est exporté → True/False.

    Leçon du 20/09/2026 (jalon 49) : une fonction ABSENTE de la DLL ne doit
    pas casser le chargement du SDK (Toupcam_get_ExpoTimeRange n'existe pas
    → AttributeError à l'import). Toute signature NON indispensable à
    l'ouverture passe donc par ici ; le code vérifie ensuite sa présence
    avec hasattr avant de s'en servir (dégradation propre, jamais de crash)."""
    try:
        fn = getattr(dll, nom)
    except AttributeError:
        return False
    if argtypes is not None:
        fn.argtypes = argtypes
    fn.restype = restype
    return True


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
        _HToupCam, _p_uint, _p_uint, _p_uint]
    dll.Toupcam_get_ExpTimeRange.restype = ctypes.c_int
    dll.Toupcam_put_Option.argtypes = [_HToupCam, ctypes.c_uint, ctypes.c_int]
    dll.Toupcam_put_Option.restype = ctypes.c_int
    # --- signatures utilisées par detecter_capacites() / le noir (jalon 50) --
    # TOUTES optionnelles (_proto) : elles ne servent qu'aux RÉGLAGES, jamais
    # à ouvrir la caméra — une DLL qui ne les exporte pas doit continuer à
    # fonctionner (l'UI gardera simplement ses bornes par défaut).
    _proto(dll, "Toupcam_get_ExpoAGainRange", [_HToupCam, _p_ushort,
                                               _p_ushort, _p_ushort])
    _proto(dll, "Toupcam_get_Option",
           [_HToupCam, ctypes.c_uint, _p_int])       # option → valeur (int)
    _proto(dll, "Toupcam_get_MaxBitDepth", [_HToupCam])   # bits dans le HRESULT
    _proto(dll, "Toupcam_get_MonoMode", [_HToupCam])      # S_OK = mono
    _proto(dll, "Toupcam_get_PixelSize",
           [_HToupCam, ctypes.c_uint, _p_float, _p_float])
    _proto(dll, "Toupcam_put_AutoExpoEnable", [_HToupCam, ctypes.c_int])
    # --- TEC (jalon 51) : température du capteur + repli de consigne --------
    _proto(dll, "Toupcam_get_Temperature",
           [_HToupCam, ctypes.POINTER(ctypes.c_short)])   # unités 0,1 °C
    _proto(dll, "Toupcam_put_Temperature", [_HToupCam, ctypes.c_short])
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
        self._modele_nom = ""            # nom de MODÈLE copié à l'ouverture
        self._flag = 0                   # TOUPCAM_FLAG_* du modèle (copié)
        self._noir_max = None            # borne max du noir MESURÉE (jalon 51)

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
        if modele is not None:
            # ⚠ la mémoire de `arr` disparaît à la sortie de open() : on COPIE
            # ce qu'on veut garder (nom de modèle + drapeaux, utiles à la
            # fiche capacités et à savoir ce que le modèle SAIT faire)
            self._modele_nom = modele.name or ""
            if not IS_WINDOWS and isinstance(self._modele_nom, bytes):
                self._modele_nom = self._modele_nom.decode("utf-8", "replace")
            self._flag = int(modele.flag)
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
        """Pose l'expo (ms → µs) et le gain en unités SDK Touptek = POUR CENT
        (100 % = 1×) — les autres marques passent elles aussi leurs unités SDK
        telles quelles (POA/SVB/ZWO/QHY).

        L'AUTO-EXPOSITION est COUPÉE au passage : relevé RÉEL du 20/09/2026
        (G3M662M) — l'AE « continue », état par défaut de la caméra, ÉCRASE
        l'expo posée (l'expo retombait à 350 ms). Sans cette coupe, les
        curseurs d'expo/gain de l'appli mentiraient (jalon 50)."""
        if self._handle is None:
            return
        dll = _DLL
        if hasattr(dll, "Toupcam_put_AutoExpoEnable"):
            dll.Toupcam_put_AutoExpoEnable(self._handle, 0)   # AE off
        dll.Toupcam_put_ExpoTime(self._handle, int(exposure_ms * 1000))
        dll.Toupcam_put_ExpoAGain(self._handle, int(gain))

    def definir_offset(self, offset):
        """Pose le niveau de NOIR du capteur — c'est l'« offset » chez Touptek
        (option BLACKLEVEL 0x15). Borné à la plage documentée quand elle est
        connue (relevée par detecter_capacites), pour ne jamais poser une
        valeur que le SDK refuserait ou rognerait SILENCIEUSEMENT."""
        if self._handle is None or _DLL is None:
            return
        if not hasattr(_DLL, "Toupcam_put_Option"):
            return
        v = int(offset)
        if self._noir_max is not None:
            v = min(max(v, TOUPCAM_BLACKLEVEL_MIN), self._noir_max)
        _DLL.Toupcam_put_Option(self._handle, TOUPCAM_OPTION_BLACKLEVEL,
                                max(v, TOUPCAM_BLACKLEVEL_MIN))

    def detecter_capacites(self):
        """→ Capacites rempli EN DYNAMIQUE depuis la caméra OUVERTE (jalon 50).

        DEMANDE D'ALAIN (21/09/2026) : les curseurs Expo/Gain/Offset de
        l'appli gardaient leurs bornes EN DUR (échelles d'expo fixes,
        « Gain (0 – 175) », « Offset (0 – 255) ») alors que le banc mesurait
        100 µs → 1000 s et 100 % → 15000 % : `TouptekCamera` n'implémentait
        pas cette méthode.

        Touptek n'énumère PAS de liste de contrôles (contrairement à
        ZWO/SVBONY/Player One) : on interroge les fonctions et OPTIONS
        documentées de toupcam.h, une par une :
          - exposition (µs) : Toupcam_get_ExpTimeRange [min, max, défaut] ;
          - gain (%)        : Toupcam_get_ExpoAGainRange (100 % = 1×, unité
                              du SDK — le curseur de l'appli est donc en %) ;
          - noir            : option BLACKLEVEL 0x15. Le SDK n'a AUCUNE
                              fonction de plage : la borne max se DÉDUIT de
                              la table documentée (TOUPCAM_BLACKLEVELn_MAX =
                              31 << (n - 8)) indexée par la profondeur de
                              bits annoncée par get_MaxBitDepth (les bits
                              sont codés dans le HRESULT). Profondeur hors
                              table ou lecture en échec ⇒ pas de plage : on
                              préfère laisser les défauts de l'UI plutôt
                              qu'un curseur construit sur une valeur inventée.
          - refroidissement : le TEC se pilote par OPTIONS (TEC 0x08,
            TECTARGET 0x0f — la DLL n'a PAS de CoolerOn), la plage de consigne
            vient de TECTARGET_RANGE (0x6d) et la température du capteur de
            get_Temperature ; un modèle sans TEC répond E_NOTIMPL et laisse
            les boutons ❄ grisés (jalon 51).

        À appeler APRÈS open() (le SDK exige la caméra ouverte), avant
        close(). Aucune exception ne remonte : une lecture ratée laisse le
        champ à None (l'UI conserve ses valeurs par défaut)."""
        if self._handle is None:
            raise RuntimeError("ouvre d'abord la caméra (open()) avant "
                               "detecter_capacites()")
        dll = _DLL
        if dll is None:
            return None
        h = self._handle
        byref = ctypes.byref

        # --- identité : mono/couleur (get_MonoMode : S_OK = mono) ----------
        mono = None
        if hasattr(dll, "Toupcam_get_MonoMode"):
            r = dll.Toupcam_get_MonoMode(h)
            if r >= 0:
                mono = (r == S_OK)          # S_FALSE = couleur
        cap = Capacites("Touptek", modele=self.name or "",
                        capteur=self._modele_nom or "",
                        couleur=(not mono) if mono is not None else False,
                        max_l=self._w, max_h=self._h)

        # --- exposition (µs) ----------------------------------------------
        tmin, tmax, tdef = (ctypes.c_uint(0), ctypes.c_uint(0),
                            ctypes.c_uint(0))
        if hasattr(dll, "Toupcam_get_ExpTimeRange"):
            hr = dll.Toupcam_get_ExpTimeRange(h, byref(tmin), byref(tmax),
                                              byref(tdef))
            if hr >= 0 and tmax.value > tmin.value:
                cap.expo_us = (tmin.value, tmax.value)

        # --- gain (%) ------------------------------------------------------
        gmin, gmax, gdef = (ctypes.c_ushort(0), ctypes.c_ushort(0),
                            ctypes.c_ushort(0))
        if hasattr(dll, "Toupcam_get_ExpoAGainRange"):
            hr = dll.Toupcam_get_ExpoAGainRange(h, byref(gmin), byref(gmax),
                                                byref(gdef))
            if hr >= 0 and gmax.value > gmin.value:
                cap.gain = (gmin.value, gmax.value)      # unité SDK = %
        return self._capacites_tec(
            dll, h, self._capacites_noir(dll, h, cap, byref), byref)

    def _capacites_noir(self, dll, h, cap, byref):
        """Complète `cap` : profondeur de bits, pixel et niveau de NOIR.

        Séparé de detecter_capacites() pour rester lisible : c'est ici que
        se joue la seule plage que le SDK ne donne PAS directement (le noir),
        déduite de la table documentée de toupcam.h."""
        if hasattr(dll, "Toupcam_get_MaxBitDepth"):
            b = dll.Toupcam_get_MaxBitDepth(h)     # les bits SONT le HRESULT
            if b > 0:
                cap.bits = b
        if hasattr(dll, "Toupcam_get_PixelSize"):
            px, py = ctypes.c_float(0), ctypes.c_float(0)
            if dll.Toupcam_get_PixelSize(h, 0, byref(px), byref(py)) >= 0 \
                    and px.value > 0:
                cap.pixel_um = px.value

        # --- noir (option BLACKLEVEL) : valeur courante + plage MESURÉE ----
        noir = ctypes.c_int(0)
        if hasattr(dll, "Toupcam_get_Option") \
                and dll.Toupcam_get_Option(h, TOUPCAM_OPTION_BLACKLEVEL,
                                           byref(noir)) >= 0:
            # valeur COURANTE lue sur la caméra (jalon 51 : l'appli l'adopte
            # au lieu d'imposer la sienne)
            cap.actuels["offset"] = float(noir.value)
            noir_max = self._mesurer_noir(dll, h, cap.bits, noir.value)
            if noir_max:
                self._noir_max = noir_max          # borne de sécurité (pose)
                cap.offset = (TOUPCAM_BLACKLEVEL_MIN, noir_max)
                # extras : la valeur COURANTE + la plage, sous la clé de
                # l'option — c'est ce que Capacites.plage('offset') lit pour
                # la marque « Touptek » (cf. CID_CONTROLES_PAR_MARQUE).
                cap.extras[str(TOUPCAM_OPTION_BLACKLEVEL)] = {
                    "min": TOUPCAM_BLACKLEVEL_MIN, "max": noir_max,
                    "step": 1, "val": noir.value, "nom": "BlackLevel"}
        return cap

    def _mesurer_noir(self, dll, h, bits, val0):
        """→ borne max du niveau de noir RÉELLEMENT acceptée par la caméra.

        Jalon 51 — CONSTAT RÉEL d'Alain (21/09/2026, G3M662M, banc) : la caméra
        annonce 16 bits et la table de toupcam.h laisse croire à 0 → 7936,
        mais elle REFUSE 7936 (E_INVALIDARG), ACCEPTE 31 et 30, refuse 32 →
        plage réelle 0 → 31 (celle de la profondeur 8 bits). Ni constante ni
        fonction du SDK n'est donc fiable ici : on MESURE la borne par
        DICHOTOMIE (poser, puis RELIRE — règle du projet : « posé ≠ relu, seul
        l'effet physique prouve »), la table documentée ne servant que de
        PLAFOND de recherche (on n'écrit jamais au-delà). La valeur d'origine
        de la caméra est RESTAURÉE avant de rendre la main (aucune trace).

        Coût : ≤ ~13 aller-retours d'option (quelques millisecondes), AVANT
        l'empilement — le flux live peut montrer des images transitoires.
        → None si la plage n'est pas mesurable (l'UI garde alors ses défauts,
        jamais un curseur construit sur une valeur inventée)."""
        if not hasattr(dll, "Toupcam_get_Option") \
                or not hasattr(dll, "Toupcam_put_Option"):
            return None
        # caméra qui DÉCLARE ne pas régler le noir (drapeaux du modèle) :
        # on ne touche à RIEN
        if self._flag and not (self._flag & TOUPCAM_FLAG_BLACKLEVEL):
            return None
        plafond = TOUPCAM_BLACKLEVEL_MAX_PAR_BITS.get(bits)
        if not plafond:
            return None
        byref = ctypes.byref

        def accepte(v):
            """Pose v puis RELIT : la caméra a accepté si elle le garde."""
            if dll.Toupcam_put_Option(h, TOUPCAM_OPTION_BLACKLEVEL, v) < 0:
                return False
            relu = ctypes.c_int(-1)
            if dll.Toupcam_get_Option(h, TOUPCAM_OPTION_BLACKLEVEL,
                                      byref(relu)) < 0:
                return False
            return relu.value == v

        try:
            if not accepte(TOUPCAM_BLACKLEVEL_MIN):
                return None                   # même 0 refusé : pas de plage
            if accepte(plafond):
                return plafond                # le plafond passe : plafond = max
            bas, haut = TOUPCAM_BLACKLEVEL_MIN, plafond   # bas = accepté
            while haut - bas > 1:             # dernier accepté = borne max
                milieu = (bas + haut) // 2
                if accepte(milieu):
                    bas = milieu
                else:
                    haut = milieu
            return bas
        finally:
            # RESTAURATION de la valeur d'origine, quoi qu'il arrive
            try:
                dll.Toupcam_put_Option(h, TOUPCAM_OPTION_BLACKLEVEL, val0)
            except Exception:
                pass

    def _capacites_tec(self, dll, h, cap, byref):
        """Complète `cap` : refroidissement (TEC) — jalon 51.

        Touptek pilote son TEC par OPTIONS (la DLL n'a PAS de CoolerOn) :
        TOUPCAM_OPTION_TEC (0x08, marche/arrêt) et TOUPCAM_OPTION_TECTARGET
        (0x0f, consigne en 0,1 °C). Un modèle SANS TEC répond en échec
        (E_NOTIMPL — constat réel G3M662M : ni TEC ni sonde) → cap.tec reste
        False et les boutons ❄ de l'appli restent grisés : aucune promesse en
        l'air. La plage de consigne vient de TECTARGET_RANGE (0x6d, [RO])."""
        if not hasattr(dll, "Toupcam_get_Option"):
            return cap
        etat = ctypes.c_int(0)
        if dll.Toupcam_get_Option(h, TOUPCAM_OPTION_TEC, byref(etat)) < 0:
            return cap
        cap.tec = True
        cap.tec_consigne = self._plage_tec(dll, h)
        if hasattr(dll, "Toupcam_get_Temperature"):
            t = ctypes.c_short(0)
            cap.temperature_lisible = dll.Toupcam_get_Temperature(
                h, byref(t)) >= 0
        return cap

    def _plage_tec(self, dll, h):
        """→ (min °C, max °C) de la consigne TEC, lus via TECTARGET_RANGE
        (0x6d : min = 16 bits bas, max = 16 bits hauts, chacun SIGNÉ, en
        0,1 °C), ou None si la caméra ne l'expose pas (l'UI conserve alors
        ses bornes prudentes d'origine)."""
        v = ctypes.c_int(0)
        if not hasattr(dll, "Toupcam_get_Option") \
                or dll.Toupcam_get_Option(h, TOUPCAM_OPTION_TECTARGET_RANGE,
                                          ctypes.byref(v)) < 0:
            return None
        brut = v.value & 0xFFFFFFFF
        mn, mx = brut & 0xFFFF, (brut >> 16) & 0xFFFF
        mn = mn - 65536 if mn >= 32768 else mn      # champs SIGNÉS
        mx = mx - 65536 if mx >= 32768 else mx
        if mn >= mx:
            return None
        return (mn / 10.0, mx / 10.0)

    # --- refroidissement TEC (options du SDK Touptek — jalon 51) ----------
    def consigne_refroidissement(self, temp_c):
        """Régulation automatique à `temp_c` °C.

        ⚠ La DLL n'a PAS de put_CoolerOn : le TEC se pilote par OPTIONS —
        TECTARGET (0x0f, consigne) puis TEC (0x08, marche). Les températures
        Touptek sont en UNITÉS DE 0,1 °C (toupcam.h) → ×10 pour poser."""
        if self._handle is None or _DLL is None:
            raise RuntimeError("caméra fermée — TEC inaccessible")
        cible = int(round(float(temp_c) * 10))
        hr = _DLL.Toupcam_put_Option(self._handle,
                                     TOUPCAM_OPTION_TECTARGET, cible)
        if hr < 0 and hasattr(_DLL, "Toupcam_put_Temperature"):
            # repli documenté : certaines DLL n'ont que put_Temperature
            hr = _DLL.Toupcam_put_Temperature(self._handle, cible)
        if hr < 0:
            raise RuntimeError(f"consigne TEC refusée par le SDK (HRESULT "
                               f"{hr}) — vérifier l'alimentation 12 V")
        hr = _DLL.Toupcam_put_Option(self._handle, TOUPCAM_OPTION_TEC, 1)
        if hr < 0:
            raise RuntimeError("démarrage du refroidissement refusé par le "
                               f"SDK (HRESULT {hr}) — vérifier l'alimentation "
                               "12 V")

    def lire_refroidissement(self):
        """→ (temp capteur °C, puissance, consigne °C), None si le TEC n'est
        pas exposé par ce modèle (constat réel G3M662M : get_Option(TEC) en
        échec → None → les boutons ❄ restent grisés, aucune promesse en
        l'air).

        Touptek n'expose AUCUNE puissance de refroidissement (ni option ni
        getter) → None : l'appli affiche « — » au lieu d'un « 0 % » qui
        laisserait croire que le TEC ne travaille pas. La température peut
        manquer sur un modèle sans sonde → None également. La consigne est
        masquée quand la caméra répond « -2730 » (= « valeur par défaut du
        modèle », cf. toupcam.h)."""
        if self._handle is None or _DLL is None \
                or not hasattr(_DLL, "Toupcam_get_Option"):
            return None
        etat = ctypes.c_int(0)
        if _DLL.Toupcam_get_Option(self._handle, TOUPCAM_OPTION_TEC,
                                   ctypes.byref(etat)) < 0:
            return None                      # pas de TEC sur ce modèle
        temp = None
        if hasattr(_DLL, "Toupcam_get_Temperature"):
            t = ctypes.c_short(0)
            if _DLL.Toupcam_get_Temperature(self._handle,
                                            ctypes.byref(t)) >= 0:
                temp = t.value / 10.0        # unités de 0,1 °C
        consigne = None
        v = ctypes.c_int(0)
        if _DLL.Toupcam_get_Option(self._handle, TOUPCAM_OPTION_TECTARGET,
                                   ctypes.byref(v)) >= 0 and v.value > -2730:
            consigne = v.value / 10.0
        return (temp, None, consigne)

    def arreter_refroidissement(self):
        """Coupe le TEC (option TEC = 0 — la caméra reste ouverte et le flux
        continue). Silencieux si la caméra est déjà fermée (appel lors de la
        déconnexion / à la fermeture de l'app)."""
        if self._handle is None or _DLL is None \
                or not hasattr(_DLL, "Toupcam_put_Option"):
            return
        try:
            _DLL.Toupcam_put_Option(self._handle, TOUPCAM_OPTION_TEC, 0)
        except Exception:
            pass

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



