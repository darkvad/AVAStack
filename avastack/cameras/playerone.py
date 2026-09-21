# -*- coding: utf-8 -*-
"""Caméras Player One Astronomy (Uranus-C Pro, Mars-C, Neptune-C…).

SDK natif officiel (téléchargeable sur player-one-astronomy.com) chargé via
ctypes, cf. sdk_loader.py. Une seule classe gère N'IMPORTE QUELLE caméra
Player One branchée : caractéristiques lues sur la caméra (fiche POACameraProperties),
jamais codées en dur.

Formats : la caméra couleur (Uranus-C Pro) est configurée en RGB24 — la
débayerisation est faite PAR LA CAMÉRA, on reçoit (H, W, 3) prêt à l'emploi.
Les caméras mono sortiraient du RAW16 2D (chemin géré aussi).

Dérivé du wrapper pyPOACamera.py (projet poa_view de Filipe Maia, BSD-2-Clause)
— seules les fonctions utilisées par AVAStack sont reprises, avec attribution.
"""

import ctypes
import platform
import numpy as np

from .base import CameraBase
from .sdk_loader import charger_dll, nom_bibliotheque
from .capacites import Capacites, Controle, dedupliquer

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

# --- constantes du SDK (cf. PlayerOneCamera SDK, POAxxx) --------------------
POA_OK = 0

# Formats d'image
POA_RAW8 = 0
POA_RAW16 = 1        # mono 16 bits
POA_RGB24 = 2        # couleur débayerisée par la caméra
POA_MONO8 = 3        # couleur convertie en mono par la caméra

# Config IDs utilisés
POA_EXPOSURE = 0     # µs
POA_GAIN = 1
POA_USB_BANDWIDTH_LIMIT = 28

# --- Config IDs (enum officielle POAConfigID, cf. POACamera.h) --------------
POA_TEMPERATURE = 3       # °C, flottant, lecture seule
POA_OFFSET = 7
POA_EGAIN = 15            # e-/ADU, flottant, change avec le gain
POA_COOLER_POWER = 16     # % de puissance TEC
POA_TARGET_TEMP = 17      # consigne °C
POA_COOLER = 18           # régulation ON/OFF


class _POAConfigValue(ctypes.Union):
    """Union POAConfigValue du SDK récent (8 octets) : intValue (long),
    floatValue (double), boolValue (POABool). float32 sert SEULEMENT si le
    layout « ancien » est détecté (l'ancien SDK écrivait un float 32 bits)."""
    _fields_ = [("intValue", ctypes.c_long),
                ("floatValue", ctypes.c_double),
                ("boolValue", ctypes.c_uint),
                ("float32", ctypes.c_float)]


class _POAConfigAttributes(ctypes.Structure):
    """Layout du SDK récent (bindgen playerone-sdk-sys 0.1.1, SDK 2026)."""
    _fields_ = [("isSupportAuto", ctypes.c_uint),
                ("isWritable", ctypes.c_uint),
                ("isReadable", ctypes.c_uint),
                ("configID", ctypes.c_uint),
                ("valueType", ctypes.c_uint),
                ("maxValue", _POAConfigValue),
                ("minValue", _POAConfigValue),
                ("defaultValue", _POAConfigValue),
                ("szConfName", ctypes.c_char * 64),
                ("szDescription", ctypes.c_char * 128),
                ("reserved", ctypes.c_char * 64)]


class _POAConfigAttributesAncien(ctypes.Structure):
    """Layout de l'ANCIEN SDK (szDescription en tête, c_long nus) — essayé
    en repli si le layout récent ne se valide pas sur la DLL réellement
    présente."""
    _fields_ = [("szDescription", ctypes.c_char * 128),
                ("maxValue", ctypes.c_long),
                ("minValue", ctypes.c_long),
                ("defaultValue", ctypes.c_long),
                ("configID", ctypes.c_uint),
                ("valueType", ctypes.c_uint),
                ("isWritable", ctypes.c_uint),
                ("isSupportAuto", ctypes.c_uint)]


class _POACameraProperties(ctypes.Structure):
    _fields_ = [("cameraModelName", ctypes.c_char * 256),
                ("userCustomID", ctypes.c_char * 16),
                ("cameraID", ctypes.c_int),
                ("maxWidth", ctypes.c_int),
                ("maxHeight", ctypes.c_int),
                ("bitDepth", ctypes.c_int),
                ("isColorCamera", ctypes.c_int),
                ("isHasST4Port", ctypes.c_int),
                ("isHasCooler", ctypes.c_int),
                ("isUSB3Speed", ctypes.c_int),
                ("bayerPattern_", ctypes.c_int),
                ("pixelSize", ctypes.c_double),
                ("SN", ctypes.c_char * 64),
                ("sensorModelName", ctypes.c_char * 32),
                ("localPath", ctypes.c_char * 256),
                ("bins_", ctypes.c_int * 8),
                ("imgFormats_", ctypes.c_int * 8),
                ("isSupportHardBin", ctypes.c_int),
                ("pID", ctypes.c_int),
                ("reserved", ctypes.c_char * 248)]


def _charger_sdk():
    """Charge PlayerOneCamera.dll/.so/.dylib → objet DLL (None si absent)."""
    nom = nom_bibliotheque("PlayerOneCamera", IS_WINDOWS, IS_MACOS)
    try:
        dll = charger_dll(nom, "AVASTACK_PLAYERONE_DIR", ("sdk", ""))
    except (RuntimeError, OSError):
        return None
    # signatures utiles
    dll.POAGetCameraCount.restype = ctypes.c_int
    dll.POAGetCameraProperties.argtypes = [ctypes.c_int,
                                           ctypes.POINTER(_POACameraProperties)]
    dll.POAGetCameraProperties.restype = ctypes.c_int
    # prototypes de la sonde de capacités (structure attr passée en
    # c_void_p : deux layouts possibles, cf. POASonde.valider_layout)
    dll.POASetConfig.argtypes = [ctypes.c_int, ctypes.c_uint,
                                 _POAConfigValue, ctypes.c_uint]
    dll.POASetConfig.restype = ctypes.c_int
    dll.POAGetConfig.argtypes = [ctypes.c_int, ctypes.c_uint,
                                 ctypes.POINTER(_POAConfigValue),
                                 ctypes.POINTER(ctypes.c_uint)]
    dll.POAGetConfig.restype = ctypes.c_int
    dll.POAGetConfigsCount.argtypes = [ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_int)]
    dll.POAGetConfigsCount.restype = ctypes.c_int
    dll.POAGetConfigAttributes.argtypes = [ctypes.c_int, ctypes.c_int,
                                           ctypes.c_void_p]
    dll.POAGetConfigAttributes.restype = ctypes.c_int
    dll.POAGetConfigAttributesByConfigID.argtypes = [ctypes.c_int,
                                                     ctypes.c_uint,
                                                     ctypes.c_void_p]
    dll.POAGetConfigAttributesByConfigID.restype = ctypes.c_int
    return dll


_DLL = None          # chargé paresseusement (import sans matériel ne doit pas rater)

# Noms lisibles des 31 contrôles (enum officielle POAConfigID) — utilisés
# pour le verdict « possibilités » (partagés avec le banc).
NOMS_CONFIGS = {
    0: "Exposition (µs)",
    1: "Gain (unités SDK)",
    2: "Bin matériel",
    3: "Température capteur (°C)",
    4: "Balance des blancs R",
    5: "Balance des blancs G",
    6: "Balance des blancs B",
    7: "Offset",
    8: "Gain max (auto-expo)",
    9: "Expo max (auto-expo, ms)",
    10: "Ciblage luminosité (auto-expo)",
    11: "Guidage N (ST4)",
    12: "Guidage S (ST4)",
    13: "Guidage E (ST4)",
    14: "Guidage O (ST4)",
    15: "e-/ADU (EGAIN, gain courant)",
    16: "Puissance TEC (%)",
    17: "Consigne température (°C)",
    18: "Refroidissement ON/OFF",
    19: "Chauffage antibué ON/OFF",
    20: "Puissance chauffage (%)",
    21: "Puissance ventilateur (%)",
    22: "Flip : aucun",
    23: "Flip : horizontal",
    24: "Flip : vertical",
    25: "Flip : les deux",
    26: "Limite de frames (0 = illimité)",
    27: "HQI (haute qualité, caméras sans DDR)",
    28: "Limite bande passante USB",
    29: "Bin : somme (sinon moyenne)",
    30: "Bin mono (couleur → perd le motif Bayer)",
    # 31 est AU-DELÀ de l'enum documentée (0-30) : la DLL du 18/02/2026
    # l'expose réellement (« Exp », exposition en SECONDES, flottant, avec
    # un maximum DIFFÉRENT du contrôle 0 en µs). Les noms affichés viennent
    # d'abord du SDK (szConfName) — cette table n'est qu'un repli.
    31: "Exp (secondes, contrôle additionnel du SDK)",
}

NOMS_FORMATS = {0: "RAW8", 1: "RAW16", 2: "RGB24", 3: "MONO8"}


class POASonde:
    """Sonde des capacités d'une caméra Player One OUVERTE.

    Lit, via les fonctions du SDK, les attributs de chaque contrôle
    (min/max/défaut/écriture/auto) et la valeur courante. Gère les DEUX
    layouts possibles de POAConfigAttributes (récent 2026 / ancien) : le
    layout n'est utilisé que s'il se VALIDE sur deux configs indépendantes
    (0 puis 7) — jamais de confiance aveugle dans une structure.
    Réutilisé par l'application (detecter_capacites) ET par le banc
    (_diag_camera_playerone.py) : une seule définition, zéro duplication.
    """

    def __init__(self, dll, cam_id):
        self.dll = dll
        self.cam_id = cam_id
        self.layout = "récent"          # validé par valider_layout()
        self.valide = False
        self.attributs_cache = {}       # confID → dict d'attributs

    # --- lecture/écriture d'une POAConfigValue --------------------------------

    def valeur_union(self, u, type_val):
        """→ valeur Python d'une POAConfigValue selon le type déclaré."""
        if type_val == 1:                       # VAL_FLOAT
            if self.layout == "ancien":
                return float(u.float32)
            return float(u.floatValue)
        if type_val == 2:                       # VAL_BOOL
            return bool(u.boolValue)
        return int(u.intValue)                  # VAL_INT

    def union_depuis(self, val, type_val):
        """→ POAConfigValue remplie pour poser une valeur."""
        u = _POAConfigValue()
        if type_val == 1:
            u.floatValue = float(val)
        else:
            u.intValue = int(val)               # VAL_INT et VAL_BOOL
        return u

    # --- attributs d'un contrôle ----------------------------------------------

    def attributs(self, conf_id):
        """Lit les attributs d'une config (layout courant) → dict, ou None."""
        if self.layout == "ancien":
            attr = _POAConfigAttributesAncien()
        else:
            attr = _POAConfigAttributes()
        err = self.dll.POAGetConfigAttributesByConfigID(
            self.cam_id, conf_id, ctypes.byref(attr))
        if err != POA_OK:
            return None
        if self.layout == "ancien":
            return {"min": int(attr.minValue), "max": int(attr.maxValue),
                    "defaut": int(attr.defaultValue),
                    "type": int(attr.valueType),
                    "ecrivable": bool(attr.isWritable),
                    "lisible": True, "auto": bool(attr.isSupportAuto),
                    "nom": NOMS_CONFIGS.get(conf_id, f"config {conf_id}"),
                    "desc": attr.szDescription.decode("utf-8", "replace")}
        return {"min": self.valeur_union(attr.minValue, attr.valueType),
                "max": self.valeur_union(attr.maxValue, attr.valueType),
                "defaut": self.valeur_union(attr.defaultValue,
                                            attr.valueType),
                "type": int(attr.valueType),
                "ecrivable": bool(attr.isWritable),
                "lisible": bool(attr.isReadable),
                "auto": bool(attr.isSupportAuto),
                "nom": attr.szConfName.decode("utf-8", "replace").strip()
                       or NOMS_CONFIGS.get(conf_id, f"config {conf_id}"),
                "desc": attr.szDescription.decode("utf-8", "replace")}

    def valider_layout(self):
        """Détecte le layout : configID relu == ID demandé sur DEUX configs
        (0 puis 7 — un seul match ne prouve rien). → layout ou None."""
        for essai in ("récent", "ancien"):
            self.layout = essai
            ok = True
            for cid in (0, 7):
                if essai == "ancien":
                    attr = _POAConfigAttributesAncien()
                else:
                    attr = _POAConfigAttributes()
                err = self.dll.POAGetConfigAttributesByConfigID(
                    self.cam_id, cid, ctypes.byref(attr))
                if err != POA_OK or attr.configID != cid:
                    ok = False
                    break
                if essai == "récent" and attr.valueType > 2:
                    ok = False
                    break
            if ok:
                self.valide = True
                return essai
        self.layout = "récent"
        self.valide = False
        return None

    # --- valeurs courantes ------------------------------------------------------

    def lire(self, conf_id):
        """→ (valeur, is_auto) courante d'une config, ou None si erreur."""
        v = _POAConfigValue()
        auto = ctypes.c_uint(0)
        err = self.dll.POAGetConfig(self.cam_id, conf_id, ctypes.byref(v),
                                    ctypes.byref(auto))
        if err != POA_OK:
            return None
        t = self.attributs_cache.get(conf_id, {}).get("type", 0)
        return self.valeur_union(v, t), bool(auto.value)

    def poser(self, conf_id, val):
        """Pose une valeur (type déduit des attributs connus) → booléen."""
        t = self.attributs_cache.get(conf_id, {}).get("type", 0)
        err = self.dll.POASetConfig(self.cam_id, conf_id,
                                    self.union_depuis(val, t), 0)
        if err != POA_OK:
            return False
        relue = self.lire(conf_id)
        return relue is not None and relue[0] == val

    def lister(self):
        """Énumère TOUS les contrôles supportés → {confID: attributs}.
        Remplit aussi le cache des types (indispensable pour poser)."""
        n = ctypes.c_int(0)
        err = self.dll.POAGetConfigsCount(self.cam_id, ctypes.byref(n))
        if err != POA_OK:
            return {}
        cache = {}
        for i in range(n.value):
            if self.layout == "ancien":
                attr = _POAConfigAttributesAncien()
            else:
                attr = _POAConfigAttributes()
            err = self.dll.POAGetConfigAttributes(self.cam_id, i,
                                                  ctypes.byref(attr))
            if err != POA_OK:
                continue
            cid = attr.configID
            a = self.attributs(cid)
            if a is None:
                continue
            cache[cid] = a
        self.attributs_cache = cache
        return cache


class PlayerOneCamera(CameraBase):
    """Une caméra Player One connectée (index = position dans l'énumération)."""

    @staticmethod
    def lister():
        """→ noms des caméras Player One branchées ('' si SDK absent)."""
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            return []
        n = _DLL.POAGetCameraCount()
        noms = []
        for i in range(n):
            props = _POACameraProperties()
            if _DLL.POAGetCameraProperties(i, ctypes.byref(props)) == POA_OK:
                noms.append(props.cameraModelName.decode("utf-8", "replace").strip())
        return noms

    # --- cycle de vie -----------------------------------------------------
    def __init__(self, index=0):
        self.index = index
        self.name = f"Player One #{index}"
        self.id = None
        self._started = False
        self._w = self._h = 0
        self._is_color = False
        self._sonde = None      # POASonde TEC validée — construite paresseusement

    def open(self):
        global _DLL
        if _DLL is None:
            _DLL = _charger_sdk()
        if _DLL is None:
            raise RuntimeError("SDK Player One introuvable : télécharge le SDK "
                               "sur player-one-astronomy.com et place "
                               "PlayerOneCamera.dll dans le dossier du projet "
                               "(ou AVASTACK_PLAYERONE_DIR).")
        n = _DLL.POAGetCameraCount()
        if n == 0:
            raise RuntimeError("Aucune caméra Player One détectée")
        idx = min(self.index, n - 1)
        props = _POACameraProperties()
        if _DLL.POAGetCameraProperties(idx, ctypes.byref(props)) != POA_OK:
            raise RuntimeError("Impossible de lire les propriétés de la caméra")
        self.id = props.cameraID
        self._is_color = bool(props.isColorCamera)
        self._props = props          # fiche SDK conservée pour la sonde
        self.name = props.cameraModelName.decode("utf-8", "replace").strip() or self.name

        if _DLL.POAOpenCamera(self.id) != POA_OK:
            raise RuntimeError(f"Ouverture impossible : {self.name}")
        _DLL.POAInitCamera(self.id)
        # format : RGB24 pour la couleur (débayerisation par la caméra),
        # RAW16 pour le mono
        _DLL.POASetImageFormat(self.id, POA_RGB24 if self._is_color else POA_RAW16)
        _DLL.POASetImageSize(self.id, props.maxWidth, props.maxHeight)
        self._w, self._h = props.maxWidth, props.maxHeight
        # bande passante USB : défaut raisonnable (union POAConfigValue —
        # la signature du SDK attend l'union 8 octets, jamais un entier nu)
        u = _POAConfigValue()
        u.intValue = 40
        _DLL.POASetConfig(self.id, POA_USB_BANDWIDTH_LIMIT, u, 0)
        _DLL.POAStartExposure(self.id, 0)     # 0 = mode vidéo continu
        self._started = True

    def read(self):
        if not self._started:
            return None
        # frame prête ?
        ready = ctypes.c_int(0)
        _DLL.POAImageReady(self.id, ctypes.byref(ready))
        if not ready.value:
            return None
        # dimensions courantes (peuvent changer via ROI)
        w = ctypes.c_int(self._w)
        h = ctypes.c_int(self._h)
        fmt = ctypes.c_int(0)
        _DLL.POAGetImageSize(self.id, ctypes.byref(w), ctypes.byref(h))
        _DLL.POAGetImageFormat(self.id, ctypes.byref(fmt))
        self._w, self._h = w.value, h.value
        if fmt.value == POA_RGB24:
            buf = np.zeros(h.value * w.value * 3, dtype=np.uint8)
        else:
            buf = np.zeros(h.value * w.value * 2, dtype=np.uint8)   # RAW16
        err = _DLL.POAGetImageData(self.id, buf.ctypes.data_as(ctypes.c_char_p),
                                   buf.nbytes, 1000)
        if err != POA_OK:
            return None
        if fmt.value == POA_RGB24:
            img = buf.reshape(h.value, w.value, 3)
            return img.astype(np.float32) / 255.0
        img = buf.view(np.uint16).reshape(h.value, w.value)
        return img.astype(np.float32) / 65535.0

    def apply_settings(self, exposure_ms, gain):
        if not self._started:
            return
        u = _POAConfigValue()
        u.intValue = int(exposure_ms * 1000)               # µs
        _DLL.POASetConfig(self.id, POA_EXPOSURE, u, 0)
        u = _POAConfigValue()
        u.intValue = int(gain)
        _DLL.POASetConfig(self.id, POA_GAIN, u, 0)

    # --- refroidissement TEC (contrôles 3/16/17/18 du SDK) ----------------
    def _sonde_tec(self):
        """→ POASonde VALIDÉE (layout reconnu + types des contrôles en
        cache — indispensables pour lire/poser), construite UNE SEULE fois
        (lister() coûte ~31 lectures d'attributs : inacceptable à chaque
        rafraîchissement de 2 s), ou None si le SDK ne sait pas répondre
        (jamais d'erreur : le sondage de l'app en déduit « TEC
        indisponible » et laisse les boutons ❄ grisés)."""
        if self.id is None or _DLL is None or not self._started:
            return None
        s = self._sonde
        if s is None:
            s = POASonde(_DLL, self.id)
            if s.valider_layout() is None:
                return None
            s.lister()              # remplit le cache des types
            self._sonde = s
        return s

    def consigne_refroidissement(self, temp_c):
        """Régulation automatique à `temp_c` °C (POA_TARGET_TEMP puis
        POA_COOLER ON — ordre ÉPROUVÉ par le banc du 19/09/2026 : la
        consigne d'abord, l'activation ensuite)."""
        sonde = self._sonde_tec()
        if sonde is None:
            raise RuntimeError("caméra fermée ou contrôles TEC illisibles")
        a = sonde.attributs_cache.get(POA_TARGET_TEMP)
        if a is not None:
            val = float(temp_c) if a["type"] == 1 else int(round(temp_c))
            u = sonde.union_depuis(val, a["type"])
            if _DLL.POASetConfig(self.id, POA_TARGET_TEMP, u, 0) != POA_OK:
                raise RuntimeError("consigne TEC refusée par le SDK "
                                   "(POA_TARGET_TEMP)")
        u = sonde.union_depuis(1, 2)    # POA_COOLER = ON (VAL_BOOL)
        err = _DLL.POASetConfig(self.id, POA_COOLER, u, 0)
        if err != POA_OK:
            raise RuntimeError(f"POA_COOLER ON refusé (code {err}) — "
                               "vérifier l'alimentation 12 V")

    def lire_refroidissement(self):
        """→ (temp capteur °C, PWM 0-255, consigne °C), None si indisponible
        (caméra sans TEC ou contrôles absents). Puissance TEC du SDK en %
        → convertie en PWM 0-255 (convention d'affichage commune à l'app)."""
        sonde = self._sonde_tec()
        if sonde is None:
            return None
        t = sonde.lire(POA_TEMPERATURE)     # °C (VAL_FLOAT)
        p = sonde.lire(POA_COOLER_POWER)    # %
        c = sonde.lire(POA_TARGET_TEMP)     # °C
        if t is None or p is None or c is None:
            return None
        pwm = int(round(min(max(float(p[0]), 0.0), 100.0) * 255.0 / 100.0))
        return (float(t[0]), pwm, float(c[0]))

    def arreter_refroidissement(self):
        """Coupe le TEC (POA_COOLER OFF — la caméra reste ouverte et le
        flux continue). Silencieux si la caméra est déjà fermée (appel
        lors de la déconnexion / à la fermeture de l'app)."""
        if self.id is None or _DLL is None or not self._started:
            return
        sonde = self._sonde_tec()
        if sonde is None:
            return
        try:
            u = sonde.union_depuis(0, 2)    # POA_COOLER = OFF
            _DLL.POASetConfig(self.id, POA_COOLER, u, 0)
        except Exception:
            pass

    def detecter_capacites(self):
        """→ Capacites rempli EN DYNAMIQUE depuis la caméra OUVERTE.

        Ouvre une sonde (POASonde) sur la caméra, valide le layout des
        attributs, énumère TOUS les contrôles supportés et en déduit les
        plages expo/gain/offset, le TEC (présent, plage de consigne,
        température lisible), les bins, formats, bin matériel, USB3, ST4.
        Ne suppose RIEN du modèle : tout vient des réponses du SDK."""
        if self.id is None or _DLL is None:
            return None
        p = getattr(self, "_props", None)
        if p is None:
            return None
        cap = Capacites("Player One",
                        modele=p.cameraModelName.decode("utf-8",
                                                        "replace").strip(),
                        capteur=p.sensorModelName.decode("utf-8",
                                                         "replace").strip(),
                        couleur=bool(p.isColorCamera), bits=p.bitDepth,
                        max_l=p.maxWidth, max_h=p.maxHeight,
                        pixel_um=p.pixelSize)
        cap.serie = p.SN.decode("utf-8", "replace").strip()
        cap.usb3 = bool(p.isUSB3Speed)
        cap.st4 = bool(p.isHasST4Port)
        cap.bin_materiel = bool(p.isSupportHardBin)
        cap.bins = dedupliquer([b for b in p.bins_ if 1 <= b <= 4])
        # formats : le tableau du SDK a une taille FIXE dont la queue est du
        # remplissage (zéro = RAW8, une valeur valide !) → dédupliquer, cf.
        # relevé réel du 19/09/2026 (4 × RAW8 renvoyés).
        cap.formats = dedupliquer(
            [NOMS_FORMATS.get(f, str(f)) for f in p.imgFormats_
             if 0 <= f <= 3])
        sonde = POASonde(_DLL, self.id)
        layout = sonde.valider_layout()
        cache = sonde.lister()
        cap.extras["layout_attributs"] = layout or "NON reconnu"
        cap.extras["configs_supportees"] = sorted(cache)
        # Jalon 32 : plages PAR CONTRÔLE (clé = confID string) — le câblage
        # de l'UI les lit via CID_CONTROLES_PAR_MARQUE (« gain » → 1,
        # « offset » → 7), jamais un cid QHY. Le SDK POA n'expose pas de
        # pas (POAConfigAttributes) → step 1 (curseur entier).
        for cid, a in cache.items():
            cap.extras[str(cid)] = {"min": a["min"], "max": a["max"],
                                    "step": 1, "val": a["defaut"],
                                    "nom": a["nom"]}
        # plages, si les contrôles correspondants sont supportés
        a = cache.get(POA_EXPOSURE)
        if a:
            cap.expo_us = (a["min"], a["max"])
        a = cache.get(POA_GAIN)
        if a:
            cap.gain = (a["min"], a["max"])
        a = cache.get(POA_OFFSET)
        if a:
            cap.offset = (a["min"], a["max"])
            # valeur COURANTE (POAGetConfig) — jalon 51 : l'appli l'ADOPTE au
            # lieu d'imposer son défaut (réglage de CAPTEUR : l'écraser
            # fausserait les brutes et les darks associés).
            try:
                lu = sonde.lire(POA_OFFSET)
                if lu is not None:
                    cap.actuels["offset"] = float(lu[0])
            except Exception:
                pass
        # refroidissement : fiche + contrôles réellement présents
        if p.isHasCooler:
            cap.tec = True
            a = cache.get(POA_TARGET_TEMP)
            if a:
                cap.tec_consigne = (a["min"], a["max"])
            a = cache.get(POA_TEMPERATURE)
            cap.temperature_lisible = bool(a and a["lisible"])
        # énumération brute (pour l'affichage / le rapport)
        for cid in sorted(cache):
            a = cache[cid]
            cap.controles.append(
                Controle(cid, nom=a["nom"], type_val=a["type"],
                         mini=a["min"], maxi=a["max"], defaut=a["defaut"],
                         ecrivable=a["ecrivable"], lisible=a["lisible"],
                         auto=a["auto"], desc=a["desc"]))
        return cap

    def close(self):
        if self.id is not None and _DLL is not None:
            try:
                if self._started:
                    _DLL.POAStopExposure(self.id)
                _DLL.POACloseCamera(self.id)
            except Exception:
                pass
            finally:
                self.id = None
                self._started = False
                self._sonde = None   # sonde TEC invalidée avec la caméra
