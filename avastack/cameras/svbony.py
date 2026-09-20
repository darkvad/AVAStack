# -*- coding: utf-8 -*-
"""Caméras SVBONY (SV105, SV205, SV405CC, SV605CC…).

SDK natif officiel (SVBCameraSDK.dll / .so / .dylib, téléchargeable sur
svbony.com) chargé via ctypes, cf. sdk_loader.py. Une seule classe gère
N'IMPORTE QUELLE caméra SVBONY branchée : caractéristiques lues sur la
caméra (fiche SVBCameraProperty), jamais codées en dur.

API dérivée du SDK officiel SVBONY (quasi-clone de l'API ZWO ASI —
mêmes concepts : num caméras connectées, fiche, contrôles, ROI, flux vidéo)
et des wrappers MIT pysvbony (ssmichael1) / pysvb (olosnet). Attribution
dans le commentaire ; seules les fonctions utilisées par AVAStack sont
reprises ici.

Formats : RGB24 pour les caméras couleur (débayerisation PAR LA CAMÉRA,
(H,W,3) prêt à l'emploi), RAW16 pour les mono ((H,W) 2D).
"""

import ctypes
import platform
import numpy as np

from .base import CameraBase
from .capacites import Capacites, Controle, dedupliquer
from .sdk_loader import charger_dll, nom_bibliotheque

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

SVB_SUCCESS = 0

# types d'image (cf. SVB_IMG_TYPE du SDK)
SVB_IMG_RAW16 = 4
SVB_IMG_RGB24 = 10

# contrôles utilisés (SVB_CONTROL_TYPE)
SVB_EXPOSURE = 1     # µs
SVB_GAIN = 0

# --- autres contrôles utiles pour la détection de capacités ------------------
SVB_FLIP = 7                  # 0=aucun, 1=horizontal, 2=vertical, 3=les deux
SVB_BLACK_LEVEL = 13          # « offset » du SDK SVBONY
SVB_COOLER_ENABLE = 14        # régulation ON/OFF
SVB_TARGET_TEMPERATURE = 15   # consigne °C
SVB_CURRENT_TEMPERATURE = 16  # lecture °C
SVB_COOLER_POWER = 17         # % de puissance TEC

# noms lisibles des types d'image (SVB_IMG_TYPE, SDK officiel)
NOMS_FORMATS_SVB = {0: "RAW8", 1: "RAW10", 2: "RAW12", 3: "RAW14",
                    4: "RAW16", 5: "Y8", 9: "Y16", 10: "RGB24",
                    11: "RGB32"}


class _SVBControlCaps(ctypes.Structure):
    """SVB_CONTROL_CAPS du SDK officiel (cf. wrapper pysvbony, MIT) :
    Name puis Description, c_long nus, drapeaux en c_int, Unused[32]."""
    _fields_ = [("Name", ctypes.c_char * 64),
                ("Description", ctypes.c_char * 128),
                ("MaxValue", ctypes.c_long),
                ("MinValue", ctypes.c_long),
                ("DefaultValue", ctypes.c_long),
                ("IsAutoSupported", ctypes.c_int),
                ("IsWritable", ctypes.c_int),
                ("ControlType", ctypes.c_int),
                ("Unused", ctypes.c_char * 32)]


class _SVBCameraInfo(ctypes.Structure):
    _fields_ = [("FriendlyName", ctypes.c_char * 32),
                ("CameraSN", ctypes.c_char * 32),
                ("PortType", ctypes.c_char * 32),
                ("DeviceID", ctypes.c_uint32),
                ("CameraID", ctypes.c_int32)]


class _SVBCameraProperty(ctypes.Structure):
    _fields_ = [("MaxHeight", ctypes.c_long),
                ("MaxWidth", ctypes.c_long),
                ("IsColorCam", ctypes.c_int),
                ("BayerPattern", ctypes.c_int),
                ("SupportedBins", ctypes.c_int * 16),
                ("SupportedVideoFormat", ctypes.c_int * 8),
                ("MaxBitDepth", ctypes.c_int),
                ("IsTriggerCam", ctypes.c_int)]


def _charger_sdk():
    """Charge SVBCameraSDK.dll/.so/.dylib → objet DLL (None si absent)."""
    nom = nom_bibliotheque("SVBCameraSDK", IS_WINDOWS, IS_MACOS)
    try:
        dll = charger_dll(nom, "AVASTACK_SVBONY_DIR", ("sdk", ""))
    except (RuntimeError, OSError):
        return None
    # signatures
    dll.SVBGetNumOfConnectedCameras.restype = ctypes.c_int
    dll.SVBGetCameraInfo.argtypes = [ctypes.POINTER(_SVBCameraInfo), ctypes.c_int]
    dll.SVBGetCameraInfo.restype = ctypes.c_int
    dll.SVBGetCameraProperty.argtypes = [ctypes.c_int, ctypes.POINTER(_SVBCameraProperty)]
    dll.SVBGetCameraProperty.restype = ctypes.c_int
    dll.SVBSetOutputImageType.argtypes = [ctypes.c_int, ctypes.c_int]
    dll.SVBSetROIFormat.argtypes = [ctypes.c_int] * 6
    dll.SVBStartVideoCapture.argtypes = [ctypes.c_int]
    dll.SVBGetVideoData.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte),
                                    ctypes.c_long, ctypes.c_int]
    dll.SVBSetControlValue.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_long,
                                       ctypes.c_int]
    # sonde de capacités (SVBGetNumOfControls/SVBGetControlCaps — même
    # modèle que ZWO ASI, vérifié dans les exports de la DLL)
    dll.SVBGetNumOfControls.argtypes = [ctypes.c_int,
                                        ctypes.POINTER(ctypes.c_int)]
    dll.SVBGetNumOfControls.restype = ctypes.c_int
    dll.SVBGetControlCaps.argtypes = [ctypes.c_int, ctypes.c_int,
                                      ctypes.POINTER(_SVBControlCaps)]
    dll.SVBGetControlCaps.restype = ctypes.c_int
    dll.SVBGetControlValue.argtypes = [ctypes.c_int, ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_long),
                                       ctypes.POINTER(ctypes.c_int)]
    dll.SVBGetControlValue.restype = ctypes.c_int
    dll.SVBGetSensorPixelSize.argtypes = [ctypes.c_int,
                                          ctypes.POINTER(ctypes.c_float)]
    dll.SVBGetSensorPixelSize.restype = ctypes.c_int
    return dll


_DLL = None          # chargé paresseusement (l'import sans matériel ne doit pas rater)


class SVBonyCamera(CameraBase):
    """Une caméra SVBONY connectée (index = position dans l'énumération)."""

    @staticmethod
    def lister():
        """→ noms des caméras SVBONY branchées ('' si SDK absent)."""
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            return []
        n = _DLL.SVBGetNumOfConnectedCameras()
        noms = []
        for i in range(n):
            info = _SVBCameraInfo()
            if _DLL.SVBGetCameraInfo(ctypes.byref(info), i) == SVB_SUCCESS:
                noms.append(info.FriendlyName.decode("utf-8", "replace").strip())
        return noms

    # --- cycle de vie -----------------------------------------------------
    def __init__(self, index=0):
        self.index = index
        self.name = f"SVBONY #{index}"
        self.id = None
        self._started = False
        self._w = self._h = 0
        self._is_color = False

    def open(self):
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            raise RuntimeError("SDK SVBONY introuvable : télécharge le SDK "
                               "sur svbony.com et place SVBCameraSDK.dll dans "
                               "le dossier du projet (ou AVASTACK_SVBONY_DIR).")
        n = _DLL.SVBGetNumOfConnectedCameras()
        if n == 0:
            raise RuntimeError("Aucune caméra SVBONY détectée")
        idx = min(self.index, n - 1)

        info = _SVBCameraInfo()
        if _DLL.SVBGetCameraInfo(ctypes.byref(info), idx) != SVB_SUCCESS:
            raise RuntimeError("Impossible de lire les informations de la caméra")
        self.id = info.CameraID
        self.name = info.FriendlyName.decode("utf-8", "replace").strip() or self.name

        prop = _SVBCameraProperty()
        if _DLL.SVBGetCameraProperty(self.id, ctypes.byref(prop)) != SVB_SUCCESS:
            raise RuntimeError(f"Propriétés illisibles : {self.name}")
        self._is_color = bool(prop.IsColorCam)
        self._w, self._h = prop.MaxWidth, prop.MaxHeight
        self._props = prop             # fiche SDK conservée pour la sonde

        if _DLL.SVBOpenCamera(self.id) != SVB_SUCCESS:
            raise RuntimeError(f"Ouverture impossible : {self.name}")
        # format : RGB24 pour couleur (débayerisation par la caméra), RAW16 mono
        _DLL.SVBSetOutputImageType(self.id, SVB_IMG_RGB24 if self._is_color
                                   else SVB_IMG_RAW16)
        _DLL.SVBSetROIFormat(self.id, 0, 0, self._w, self._h, 1)
        if _DLL.SVBStartVideoCapture(self.id) != SVB_SUCCESS:
            raise RuntimeError(f"Démarrage du flux impossible : {self.name}")
        self._started = True

    def read(self):
        if not self._started:
            return None
        if self._is_color:
            nbytes = self._w * self._h * 3
            buf = np.zeros(nbytes, dtype=np.uint8)
            err = _DLL.SVBGetVideoData(
                self.id, buf.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)),
                nbytes, 200)
            if err != SVB_SUCCESS:
                return None
            return buf.reshape(self._h, self._w, 3).astype(np.float32) / 255.0
        nbytes = self._w * self._h * 2
        buf = np.zeros(nbytes, dtype=np.uint8)
        err = _DLL.SVBGetVideoData(
            self.id, buf.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)),
            nbytes, 200)
        if err != SVB_SUCCESS:
            return None
        return (buf.view(np.uint16).reshape(self._h, self._w)
                .astype(np.float32) / 65535.0)

    def apply_settings(self, exposure_ms, gain):
        if not self._started:
            return
        _DLL.SVBSetControlValue(self.id, SVB_EXPOSURE, int(exposure_ms * 1000), 0)
        _DLL.SVBSetControlValue(self.id, SVB_GAIN, int(gain), 0)

    # --- refroidissement TEC (contrôles 14/15/16/17 du SDK) ---------------
    def _lire_ctrl(self, cid):
        """→ valeur courante d'un contrôle SDK, None si erreur ou contrôle
        absent (jamais d'exception : le sondage de l'app en déduit « TEC
        indisponible » et laisse les boutons ❄ grisés)."""
        if self.id is None or _DLL is None or not self._started:
            return None
        v = ctypes.c_long(0)
        auto = ctypes.c_int(0)
        if _DLL.SVBGetControlValue(self.id, cid, ctypes.byref(v),
                                   ctypes.byref(auto)) != SVB_SUCCESS:
            return None
        return v.value

    def consigne_refroidissement(self, temp_c):
        """Régulation automatique à `temp_c` °C.

        ⚠ Les températures SVBONY sont en UNITÉS DE 0,1 °C (en-tête
        officiel, éprouvé par le banc du 19/09/2026) → ×10 pour poser.
        Pose éprouvée par le banc : CoolerEnable PUIS TargetTemp."""
        if self.id is None or _DLL is None or not self._started:
            raise RuntimeError("caméra fermée — TEC inaccessible")
        if _DLL.SVBSetControlValue(self.id, SVB_COOLER_ENABLE, 1,
                                   0) != SVB_SUCCESS:
            raise RuntimeError("CoolerEnable refusé par le SDK — vérifier "
                               "l'alimentation 12 V")
        if _DLL.SVBSetControlValue(self.id, SVB_TARGET_TEMPERATURE,
                                   int(round(float(temp_c) * 10)),
                                   0) != SVB_SUCCESS:
            raise RuntimeError("consigne TEC refusée par le SDK "
                               "(TargetTemp)")

    def lire_refroidissement(self):
        """→ (temp capteur °C, PWM 0-255, consigne °C), None si indisponible
        (caméra sans TEC ou contrôles absents). Températures SDK en unités
        de 0,1 °C → conversion ; puissance en % → PWM 0-255 (convention
        d'affichage commune à l'app)."""
        t = self._lire_ctrl(SVB_CURRENT_TEMPERATURE)
        p = self._lire_ctrl(SVB_COOLER_POWER)
        c = self._lire_ctrl(SVB_TARGET_TEMPERATURE)
        if t is None or p is None or c is None:
            return None
        pwm = int(round(min(max(float(p), 0.0), 100.0) * 255.0 / 100.0))
        return (t / 10.0, pwm, c / 10.0)

    def arreter_refroidissement(self):
        """Coupe le TEC (CoolerEnable = 0 — la caméra reste ouverte et le
        flux continue). Silencieux si la caméra est déjà fermée (appel
        lors de la déconnexion / à la fermeture de l'app)."""
        if self.id is None or _DLL is None or not self._started:
            return
        try:
            _DLL.SVBSetControlValue(self.id, SVB_COOLER_ENABLE, 0, 0)
        except Exception:
            pass

    def close(self):
        if self.id is not None and _DLL is not None:
            try:
                if self._started:
                    _DLL.SVBStopVideoCapture(self.id)
                _DLL.SVBCloseCamera(self.id)
            except Exception:
                pass
            finally:
                self.id = None
                self._started = False

    def detecter_capacites(self):
        """→ Capacites rempli EN DYNAMIQUE depuis la caméra OUVERTE.

        Énumère les contrôles du SDK (SVBGetNumOfControls +
        SVBGetControlCaps — même modèle que ZWO, contrôles: GAIN=0,
        EXPOSURE=1, BLACK_LEVEL=13 « offset », TEC 14/15/16/17) et les
        complète par la fiche SVBCameraProperty (bins, formats, bits,
        couleur). Ne suppose RIEN du modèle : tout vient du SDK.
        À appeler APRÈS open(), avant close()."""
        if self.id is None or _DLL is None:
            return None
        p = getattr(self, "_props", None)
        if p is None:
            return None
        cap = Capacites("SVBONY", modele=self.name,
                        capteur=self.name,   # le SDK SVB n'expose pas de
                                             # nom de capteur séparé
                        couleur=bool(p.IsColorCam), bits=p.MaxBitDepth,
                        max_l=p.MaxWidth, max_h=p.MaxHeight)
        cap.bins = dedupliquer([b for b in p.SupportedBins if 1 <= b <= 4])
        cap.formats = dedupliquer([NOMS_FORMATS_SVB.get(f, str(f))
                                   for f in p.SupportedVideoFormat
                                   if f >= 0])[:8]
        # taille de pixel (optionnelle, SDK récent)
        try:
            px = ctypes.c_float(0)
            if _DLL.SVBGetSensorPixelSize(self.id, ctypes.byref(px)) == \
                    SVB_SUCCESS:
                cap.pixel_um = px.value
        except AttributeError:
            pass
        # énumération des contrôles
        n = ctypes.c_int(0)
        if _DLL.SVBGetNumOfControls(self.id, ctypes.byref(n)) != SVB_SUCCESS:
            return cap
        caps = {}
        for i in range(n.value):
            c = _SVBControlCaps()
            if _DLL.SVBGetControlCaps(self.id, i, ctypes.byref(c)) != \
                    SVB_SUCCESS:
                continue
            cid = c.ControlType
            dic = {"nom": c.Name.decode("utf-8", "replace").strip(),
                   "desc": c.Description.decode("utf-8", "replace"),
                   "min": c.MinValue, "max": c.MaxValue,
                   "defaut": c.DefaultValue,
                   "ecrivable": bool(c.IsWritable),
                   "auto": bool(c.IsAutoSupported), "type": 0}
            caps[cid] = dic
            cap.controles.append(Controle(
                cid, nom=dic["nom"], mini=dic["min"], maxi=dic["max"],
                defaut=dic["defaut"], ecrivable=dic["ecrivable"],
                lisible=True, auto=dic["auto"], desc=dic["desc"]))
        # Jalon 32 : plages PAR CONTRÔLE (clé = id string) — le câblage de
        # l'UI les lit via CID_CONTROLES_PAR_MARQUE (« gain » → 0,
        # « offset » → 13 BlackLevel), jamais un cid QHY (« 6 » = Flip chez
        # SVBONY). Le SDK SVB n'expose pas de pas → step 1.
        for cid, dic in caps.items():
            cap.extras[str(cid)] = {"min": dic["min"], "max": dic["max"],
                                    "step": 1, "val": dic["defaut"],
                                    "nom": dic["nom"]}
        # plages, si les contrôles correspondants sont supportés
        c = caps.get(SVB_EXPOSURE)
        if c:
            cap.expo_us = (c["min"], c["max"])
        c = caps.get(SVB_GAIN)
        if c:
            cap.gain = (c["min"], c["max"])
        c = caps.get(SVB_BLACK_LEVEL)
        if c:
            cap.offset = (c["min"], c["max"])
            cap.extras["offset"] = "BLACK_LEVEL (ctrl 13) du SDK SVBONY"
        # refroidissement : contrôles réellement présents
        if SVB_COOLER_ENABLE in caps:
            cap.tec = True
            c = caps.get(SVB_TARGET_TEMPERATURE)
            if c:
                cap.tec_consigne = (c["min"], c["max"])
            cap.temperature_lisible = SVB_CURRENT_TEMPERATURE in caps
        return cap
