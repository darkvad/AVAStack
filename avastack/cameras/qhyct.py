# -*- coding: utf-8 -*-
"""Sonde ctypes NATIVE QHYCCD — réutilisée par l'application ET le banc.

Extrait du banc (_diag_camera_qhy.py, jalon 30, VALIDÉ EN RÉEL sur la
MiniCam8M le 20/09/2026) : une seule définition, le banc délègue désormais
(leçon du banc Player One — deux copies finissent par diverger).

Le paquet PyPI `qhyccd` (Rust/PyO3) n'expose AUCUNE fonction de plages ;
la DLL native les a toutes. Conventions vérifiées EN RÉEL :
  - SetQHYCCDStreamMode + InitQHYCCD(handle) OBLIGATOIRES après
    OpenQHYCCD avant toute lecture de contrôle (sinon tout « indispo ») ;
  - IsQHYCCDControlAvailable : 0 (QHYCCD_SUCCESS) = contrôle DISPONIBLE
    (convention du SDK entier — pas « 1 = vrai » ; confirmé par le driver
    INDI) ; 0xFFFFFFFF = id inconnu du SDK ;
  - GetQHYCCDParamMinMaxStep(h, id, &min, &max, &step) → 0 = OK ;
  - IsQHYCCDCFWPlugged → 0 = roue TROUVÉE (doc « Filter Wheel APIs ») ;
  - statut/ordre roue = caractère ASCII ('0' = position 1 selon la doc ;
    la voie binding lit/écrit 48+n — l'EFFET PHYSIQUE tranche).

La sonde charge la DLL DANS LE PROCESS (l'application a déjà initialisé le
SDK via le binding : un 2e InitQHYCCDResource est toléré — retour non nul,
constaté sans effet) ; le banc, lui, garde son isolement par sous-processus.
"""
import ctypes
import os

# Contrôles d'ENTRÉE (id selon l'enum CONTROL_ID du SDK, identique à la
# table NOMS_CTRL du banc) : seuls ceux-ci donnent des curseurs.
CTRL_ENTREE = (0, 1, 5, 6, 7, 8, 10, 12, 18)
VALEUR_ERREUR = 4294967295.0     # sentinelle du SDK (0xFFFFFFFF)

NOMS = {0: "Brightness", 1: "Contrast", 5: "Gamma", 6: "GAIN",
        7: "OFFSET", 8: "EXPOSURE (µs)", 10: "TransferBit (bits/px)",
        12: "UsbTraffic", 14: "CurTemp (°C)", 15: "CurPWM (TEC)",
        16: "ManualPWM (TEC)", 17: "CfwPort", 18: "COOLER (consigne °C)",
        19: "St4Port", 21: "CamBin1x1mode", 22: "CamBin2x2mode",
        23: "CamBin3x3mode", 24: "CamBin4x4mode", 34: "Cam8bits",
        35: "Cam16bits", 39: "Qhyccd3aAutoexposure", 42: "Vcam",
        44: "CfwSlotsNum", 57: "CamSingleFrameMode", 58: "CamLiveVideoMode",
        60: "HasHardwareFrameCounter"}


def trouver_dll():
    """→ chemin de la bibliothèque native QHYCCD, ou None (priorité à la
    DLL embarquée du paquet — le MÊME fichier que le binding)."""
    noms = ("qhyccd.dll", "libqhyccd.so", "libqhyccd.dylib")
    candidats = []
    env = os.environ.get("AVASTACK_QHY_DIR")
    if env:
        candidats.append(env if os.path.isfile(env)
                         else os.path.join(env, noms[0]))
    try:
        import qhyccd as _paquet
        ici = os.path.dirname(os.path.abspath(_paquet.__file__))
        for racine in (os.path.join(ici, "vendor"),
                       os.path.join(os.path.dirname(ici), "vendor")):
            if os.path.isdir(racine):
                for rac, _s, fichiers in os.walk(racine):
                    candidats.extend(os.path.join(rac, n) for n in noms
                                     if n in fichiers)
    except Exception:
        pass
    ici_module = os.path.dirname(os.path.abspath(__file__))
    candidats.extend(os.path.join(os.path.dirname(os.path.dirname(
        ici_module)), n) for n in noms)
    candidats.extend(noms)           # PATH système (en dernier recours)
    for c in candidats:
        if c and os.path.isfile(c):
            return c
    return None


def charger_fonctions(chemin):
    """Charge la DLL avec des prototypes EXPLICITES (restype/argtypes :
    sans eux, ctypes tronque les doubles — leçon v2.16)."""
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

    def decl(nom, restype, argtypes):
        f = getattr(lib, nom)
        f.restype = restype
        f.argtypes = argtypes
        fns[nom] = f

    decl("InitQHYCCDResource", ctypes.c_uint32, [])
    decl("ReleaseQHYCCDResource", ctypes.c_uint32, [])
    decl("ScanQHYCCD", ctypes.c_uint32, [])
    decl("GetQHYCCDId", ctypes.c_uint32, [ctypes.c_uint32, ctypes.c_char_p])
    decl("GetQHYCCDModel", ctypes.c_uint32,
         [ctypes.c_char_p, ctypes.c_char_p])
    decl("OpenQHYCCD", H, [ctypes.c_char_p])
    decl("CloseQHYCCD", ctypes.c_uint32, [H])
    decl("SetQHYCCDStreamMode", ctypes.c_uint32, [H, ctypes.c_ubyte])
    decl("InitQHYCCD", ctypes.c_uint32, [H])
    decl("GetQHYCCDParam", ctypes.c_double, [H, ctypes.c_int])
    decl("SetQHYCCDParam", ctypes.c_uint32, [H, ctypes.c_int, ctypes.c_double])
    decl("GetQHYCCDParamMinMaxStep", ctypes.c_uint32,
         [H, ctypes.c_int, D, D, D])
    decl("IsQHYCCDControlAvailable", ctypes.c_uint32, [H, ctypes.c_int])
    decl("IsQHYCCDCFWPlugged", ctypes.c_uint32, [H])
    decl("GetQHYCCDCFWStatus", ctypes.c_uint32, [H, ctypes.c_char_p])
    decl("SendOrder2QHYCCDCFW", ctypes.c_uint32,
         [H, ctypes.c_char_p, ctypes.c_uint32])
    return fns


class QhyNatif:
    """Handle natif ouvert (scène minimale : scan → open → init → lecture).

    TOUT est protégé : un échec = False / dict vide, jamais une exception —
    l'application doit rester utilisable même si le SDK natif répond mal
    (le binding, lui, continue de faire fonctionner le flux).
    """

    def __init__(self):
        self.fns = None
        self.h = None
        self.cid = None

    def ouvrir(self):
        """Scan → ouverture du 1er id détecté → init par handle.
        → True si un handle est prêt, False sinon (silencieux)."""
        try:
            chemin = trouver_dll()
            if chemin is None:
                return False
            self.fns = charger_fonctions(chemin)
            self.fns["InitQHYCCDResource"]()      # déjà init : toléré (réel)
            n = self.fns["ScanQHYCCD"]()
            if n == 0 or n > 1024:
                return False
            ids = []
            for i in range(n):
                buf = ctypes.create_string_buffer(128)   # sur-allocation
                if self.fns["GetQHYCCDId"](i, buf) == 0 and buf.value:
                    ids.append(buf.value.decode("utf-8", "replace"))
            if not ids:
                return False
            self.cid = ids[0]
            self.h = self.fns["OpenQHYCCD"](self.cid.encode())
            if not self.h:
                return False
            self.fns["SetQHYCCDStreamMode"](self.h, 1)
            if self.fns["InitQHYCCD"](self.h) != 0:
                return False
            return True
        except Exception:
            self.h = None
            return False

    def plages(self):
        """→ dict extras {id_str: {nom, val, min, max, step}} des contrôles
        d'ENTRÉE disponibles (0 = dispo) avec une plage cohérente."""
        extras = {}
        if not self.h:
            return extras
        for cid in CTRL_ENTREE:
            try:
                if self.fns["IsQHYCCDControlAvailable"](self.h, cid) != 0:
                    continue
                mn, mx, st = (ctypes.c_double(), ctypes.c_double(),
                              ctypes.c_double())
                rc = self.fns["GetQHYCCDParamMinMaxStep"](
                    self.h, cid, ctypes.byref(mn), ctypes.byref(mx),
                    ctypes.byref(st))
                e = {"nom": NOMS.get(cid, str(cid)),
                     "val": self.fns["GetQHYCCDParam"](self.h, cid)}
                if rc == 0 and mn.value < mx.value:
                    e["min"], e["max"], e["step"] = (mn.value, mx.value,
                                                     st.value)
                    extras[str(cid)] = e
            except Exception:
                continue
        return extras

    def cfw_info(self):
        """→ (plugged, slots, statut_char) — None si la roue ne répond pas."""
        if not self.h:
            return None
        try:
            plugged = self.fns["IsQHYCCDCFWPlugged"](self.h)
            slots = self.fns["GetQHYCCDParam"](self.h, 44)
            buf = ctypes.create_string_buffer(128)
            self.fns["GetQHYCCDCFWStatus"](self.h, buf)
            return (plugged == 0,
                    None if slots == VALEUR_ERREUR else slots,
                    buf.value.decode("ascii", "replace"))
        except Exception:
            return None

    def fermer(self, release=True):
        """CloseQHYCCD (+ ReleaseQHYCCDResource si `release`).

        ⚠ release=False quand on tourne DANS l'application à côté du
        binding : celui-ci a déjà initialisé le SDK, et le libérer casserait
        l'état global (même piège que le double init_sdk, constat du
        19/09/2026). Le banc (sous-processus isolé) libère, lui."""
        try:
            if self.h is not None and self.fns is not None:
                self.fns["CloseQHYCCD"](self.h)
        except Exception:
            pass
        self.h = None
        if release:
            try:
                if self.fns is not None:
                    self.fns["ReleaseQHYCCDResource"]()
            except Exception:
                pass
        self.fns = None
