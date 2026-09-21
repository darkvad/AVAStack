# -*- coding: utf-8 -*-
"""Test du banc caméra Touptek (_diag_camera_touptek.py) et de la sonde
avastack/cameras/touptek.py — SANS matériel.

La DLL est REMPLACÉE par un faux SDK qui répond exactement ce que l'entête
officiel toupcam.h promet (HRESULT >= 0 = succès, exposition en µs, gain en
%, températures en 0,1 °C, EnumV2 remplit des ToupcamDeviceV2). On valide :
disposition des structures V2 (offsets/alignement), sonde TouptekCamera
(lister/open/read avec callback simulé), banc (erreurs HRESULT nommées,
fiche/drapeaux, réglages mesurés, verdict « possibilités », poses,
tolérance aux E_NOTIMPL).
"""
import ctypes
import importlib.util
import os
import queue
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import avastack.cameras.touptek as mtt

spec = importlib.util.spec_from_file_location(
    "diag_touptek", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "_diag_camera_touptek.py"))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

VERIFICATIONS = []


def verifie(label, condition):
    VERIFICATIONS.append((label, bool(condition)))


# --- 1) disposition des structures V2 (toupcam.h) ------------------------------
IS_WIN = mtt.IS_WINDOWS
taille_wbuf = 64 * ctypes.sizeof(ctypes.c_wchar if IS_WIN else ctypes.c_char)
verifie("ToupcamDeviceV2 : displayname 64 chars + id 64 chars + pointeur",
        mtt._ToupcamDeviceV2.displayname.offset == 0
        and mtt._ToupcamDeviceV2.id.offset == taille_wbuf
        and mtt._ToupcamDeviceV2.model.offset ==
        ctypes.sizeof(mtt._ToupcamDeviceV2) -
        ctypes.sizeof(ctypes.c_void_p))
verifie("ToupcamModelV2 : flag juste après name, res[16] en fin de fiche",
        mtt._ToupcamModelV2.flag.offset == ctypes.sizeof(ctypes.c_void_p)
        and mtt._ToupcamModelV2.res.offset > 0
        and mtt._ToupcamModelV2.res.offset + 16 * 8
        <= ctypes.sizeof(mtt._ToupcamModelV2))
verifie("TOUPCAM_MAX = 128 (toupcam.h)", mtt.TOUPCAM_MAX == 128)
verifie("événements : IMAGE=0x0004, STILLIMAGE=0x0005",
        mtt.TOUPCAM_EVENT_IMAGE == 0x0004
        and mtt.TOUPCAM_EVENT_STILLIMAGE == 0x0005)
verifie("options : RAW=0x04, BITDEPTH=0x06, TEC=0x08, TECTARGET=0x0f",
        mtt.TOUPCAM_OPTION_RAW == 0x04
        and mtt.TOUPCAM_OPTION_BITDEPTH == 0x06
        and mtt.TOUPCAM_OPTION_TEC == 0x08
        and mtt.TOUPCAM_OPTION_TECTARGET == 0x0F)

# --- 2) erreurs HRESULT nommées (valeurs NÉGATIVES signées en ctypes) ----------
E_NOTIMPL = 0x80004001 - (1 << 32)
E_BUSY = 0x800700AA - (1 << 32)
verifie("E_NOTIMPL nommé et négatif",
        E_NOTIMPL < 0 and "E_NOTIMPL" in diag.NOMS_HRESULT.get(E_NOTIMPL, ""))
verifie("E_BUSY nommé", "E_BUSY" in diag.NOMS_HRESULT.get(E_BUSY, ""))
verifie("S_OK/S_FALSE traités comme des succès par _err",
        "S_OK" in diag.BancToup._err(None, 0)
        and "S_FALSE" in diag.BancToup._err(None, 1))

# --- 3) sonde avec FAUSSE DLL ---------------------------------------------------


class _FauxDLLSonde:
    """Faux toupcam.dll : EnumV2 remplissable, Open → handle factice,
    flux démarré OK, PullImage écrit un dégradé RGB24."""

    def __init__(self):
        self.appels = []
        self.handle = 0x1234
        self._callback = None
        self._w = self._h = 4
        # noir (jalon 51) : la G3M662M RÉELLE garde 0 → 31 et refuse au-delà
        # (E_INVALIDARG) — on imite le comportement MESURÉ au banc, pas la
        # table de toupcam.h qui laissait croire à 0 → 7936 pour 16 bits.
        self.noir = 1                    # niveau courant (relu = ce qui est gardé)
        self.noir_max = 31               # plage réelle constatée (jalon 51)

    def Toupcam_EnumV2(self, arr):
        self.appels.append("EnumV2")
        return 0   # remplacé par fake_enum()

    def Toupcam_Open(self, cam_id):
        self.appels.append(("Open", cam_id))
        return self.handle

    def Toupcam_put_Size(self, h, w, hgt):
        self.appels.append(("put_Size", w, hgt))
        return 0

    def Toupcam_put_Option(self, h, opt, val):
        self.appels.append(("put_Option", opt, val))
        if opt == mtt.TOUPCAM_OPTION_BLACKLEVEL:
            if val <= self.noir_max:     # la caméra GARDE ce qu'elle accepte
                self.noir = val
                return 0
            return 0x80070057 - (1 << 32)   # E_INVALIDARG (constat jalon 51)
        return 0

    # --- réglages / capacités (jalon 50) : mêmes valeurs que la référence
    #     MESURÉE sur la G3M662M d'Alain (banc du 20/09/2026)
    def Toupcam_put_ExpoTime(self, h, t):
        self.appels.append(("ExpoTime", t))
        return 0

    def Toupcam_put_ExpoAGain(self, h, g):
        self.appels.append(("ExpoAGain", g))
        return 0

    def Toupcam_put_AutoExpoEnable(self, h, mode):
        self.appels.append(("AutoExpoEnable", mode))
        return 0

    def Toupcam_get_ExpTimeRange(self, h, pmin, pmax, pdef):
        pmin._obj.value, pmax._obj.value = 100, 1_000_000_000
        pdef._obj.value = 10_000
        return 0

    def Toupcam_get_ExpoAGainRange(self, h, pmin, pmax, pdef):
        pmin._obj.value, pmax._obj.value, pdef._obj.value = 100, 15_000, 100
        return 0

    def Toupcam_get_MonoMode(self, h):
        return mtt.S_OK                 # mono 16 bits (G3M662M)

    def Toupcam_get_MaxBitDepth(self, h):
        return 16                       # les bits SONT la valeur du HRESULT

    def Toupcam_get_PixelSize(self, h, idx, px, py):
        px._obj.value, py._obj.value = 2.90, 2.90
        return 0

    def Toupcam_get_Option(self, h, opt, p):
        if opt == mtt.TOUPCAM_OPTION_BLACKLEVEL:
            p._obj.value = self.noir     # relu = ce que la caméra a gardé
            return 0
        if opt in (mtt.TOUPCAM_OPTION_TEC, mtt.TOUPCAM_OPTION_TECTARGET,
                   mtt.TOUPCAM_OPTION_TECTARGET_RANGE):
            return E_NOTIMPL             # ni TEC ni sonde (G3M662M réelle)
        p._obj.value = 0
        return 0

    def Toupcam_StartPullModeWithCallback(self, h, cb, ctx):
        self._callback = cb
        self.appels.append("Start")
        return 0

    def Toupcam_get_Size(self, h, pw, ph):
        pw._obj.value, ph._obj.value = self._w, self._h
        return 0

    def Toupcam_PullImage(self, h, buf, bits, pw, ph):
        pw._obj.value, ph._obj.value = self._w, self._h
        dst = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
        for i in range(self._w * self._h * 3):
            dst[i] = i % 256
        return 0

    def Toupcam_Stop(self, h):
        self.appels.append("Stop")
        return 0

    def Toupcam_Close(self, h):
        self.appels.append("Close")
        return 0


def fake_enum(noms):
    """→ fonction Toupcam_EnumV2 qui remplit arr avec les noms donnés."""
    def enum(arr):
        for i, (dn, ident) in enumerate(noms):
            arr[i].displayname = dn
            arr[i].id = ident
            arr[i].model = None
        return len(noms)
    return enum


cam = mtt.TouptekCamera(0)
faux = _FauxDLLSonde()
faux.Toupcam_EnumV2 = fake_enum([("SkyEye26AM", "sn:TP12345"),
                                 ("Altair26C", "usb#vid&pid#x")])
# espion sur l'identifiant passé à Toupcam_Open (casté en c_void_p ensuite,
# on ne peut plus le lire dans le faux : on intercepte AVANT le cast)
_orig_identifiant = mtt.TouptekCamera._identifiant
_capturé = {}


def _espion_identifiant(self, dev):
    r = _orig_identifiant(self, dev)
    _capturé["id"] = getattr(r, "value", str(r))
    return r


mtt.TouptekCamera._identifiant = _espion_identifiant
mtt._DLL = faux
noms = mtt.TouptekCamera.lister()
verifie("lister() → displayname des 2 caméras énumérées",
        noms == ["SkyEye26AM", "Altair26C"])
cam.open()
verifie("open() : Toupcam_Open reçoit l'ID OPAQUE (pas le nom du modèle)",
        _capturé.get("id") == "sn:TP12345"
        and any(isinstance(a, tuple) and a[0] == "Open" for a in faux.appels))
verifie("open() : put_Option(RAW, 0) posé (RGB24 explicite)",
        ("put_Option", mtt.TOUPCAM_OPTION_RAW, 0) in faux.appels)
verifie("open() : flux démarré (StartPullModeWithCallback)",
        "Start" in faux.appels)
# callback simulé (comme le thread interne du SDK)
faux._callback(mtt.TOUPCAM_EVENT_IMAGE, None)
img1 = cam.read()
verifie("read() → frame RGB24 4×4 après 1 événement",
        img1 is not None and img1.shape == (4, 4, 3))
verifie("read() → None tant qu'aucune nouvelle frame", cam.read() is None)
faux._callback(mtt.TOUPCAM_EVENT_IMAGE, None)
verifie("read() → nouvelle frame si nouvel événement",
        cam.read() is not None)
# --- 3b) capacités et réglages de la sonde (jalon 50) --------------------------
# Constat réel d'Alain (21/09/2026) : les curseurs de l'appli gardaient leurs
# bornes EN DUR parce que TouptekCamera n'implémentait pas detecter_capacites.
cap = cam.detecter_capacites()
verifie("capacites : marque/modèle/mono/bits/pixel lus sur la caméra",
        cap.marque == "Touptek" and cap.modele == "SkyEye26AM"
        and cap.couleur is False and cap.bits == 16
        and abs(cap.pixel_um - 2.9) < 1e-6)
verifie("capacites : plage d'expo RÉELLE (100 µs → 1e9 µs, 1000 s)",
        cap.expo_us == (100, 1_000_000_000))
verifie("capacites : plage de gain RÉELLE en % (100 % → 15000 % = 1× → 150×)",
        cap.gain == (100, 15000))
verifie("capacites : noir = plage MESURÉE 0 → 31 (jalon 51 : la table "
        "« 7936 pour 16 bits » est DÉMENTIE par la caméra)",
        cap.offset == (0, 31) and cap.extras["21"]["val"] == 1
        and cap.extras["21"]["nom"] == "BlackLevel")
verifie("capacites : valeur COURANTE du noir lue (l'appli l'adopte, jalon 51)",
        cap.actuels.get("offset") == 1.0)
verifie("capacites : plage('offset') résolue par la marque Touptek",
        cap.plage("offset") == (0.0, 31.0, 1.0))
verifie("capacites : verdict lisible (expo/gain/offset)",
        "EXPOSITION : 100 µs" in cap.vers_texte()
        and "100 → 15000" in cap.vers_texte()
        and "OFFSET : 0 → 31" in cap.vers_texte())
# profondeur HORS table → aucune plage annoncée (jamais de valeur inventée)
_depth = faux.Toupcam_get_MaxBitDepth
faux.Toupcam_get_MaxBitDepth = lambda h: 13
cam._noir_max = None
cap13 = cam.detecter_capacites()
verifie("capacites : profondeur 13 bits (hors table) → pas de plage de noir",
        cap13.offset is None and cap13.plage("offset") is None
        and cap13.gain == (100, 15000))
faux.Toupcam_get_MaxBitDepth = _depth
# réglages : gain en % (unité SDK) + auto-expo COUPÉE (elle écrase l'expo)
cam.apply_settings(350.0, 500.0)
verifie("apply_settings : expo 350 ms → 350000 µs",
        ("ExpoTime", 350000) in faux.appels)
verifie("apply_settings : gain passé en % tel quel (500 % = 5×)",
        ("ExpoAGain", 500) in faux.appels)
verifie("apply_settings : auto-exposition coupée (AE off)",
        ("AutoExpoEnable", 0) in faux.appels)
# offset = niveau de NOIR (option BLACKLEVEL), borné à la plage documentée
cam._noir_max = mtt.TOUPCAM_BLACKLEVEL_MAX_PAR_BITS[16]
cam.definir_offset(300)
verifie("definir_offset : put_Option(BLACKLEVEL 0x15, 300)",
        ("put_Option", mtt.TOUPCAM_OPTION_BLACKLEVEL, 300) in faux.appels)
cam.definir_offset(99999)
verifie("definir_offset : valeur hors plage bornée au max documenté (7936)",
        ("put_Option", mtt.TOUPCAM_OPTION_BLACKLEVEL, 7936) in faux.appels)
cam.close()
verifie("close() : Stop + Close appelés",
        "Stop" in faux.appels and "Close" in faux.appels)
mtt._DLL = None

# --- 4) banc avec FAUSSE DLL : réglages mesurés + verdict ----------------------

class _FauxDLLBanc:
    """Faux toupcam.dll complet pour le banc : toutes les valeurs plausibles
    d'une caméra couleur 12 bits refroidie (toupcam.h). Les sorties arrivent
    en byref(...) → CArgObject, on écrit via ._obj.value."""

    def __init__(self):
        self.appels = []
        self.temp = -52            # 0,1 °C
        self.consigne = -100       # 0,1 °C
        self.noir = 25             # niveau de noir courant (option 0x15)

    # exposition / gain
    def Toupcam_get_ExpTimeRange(self, h, pmin, pmax, pdef):
        pmin._obj.value, pmax._obj.value = 24, 2_000_000_000
        pdef._obj.value = 10_000
        return 0
    def Toupcam_get_ExpoTime(self, h, p):
        p._obj.value = 10_000
        return 0
    def Toupcam_get_RealExpoTime(self, h, p):
        p._obj.value = 9_872
        return 0
    def Toupcam_get_ExpoAGainRange(self, h, pmin, pmax, pdef):
        pmin._obj.value, pmax._obj.value, pdef._obj.value = 100, 2600, 100
        return 0
    def Toupcam_get_ExpoAGain(self, h, p):
        p._obj.value = 100
        return 0
    def Toupcam_put_ExpoTime(self, h, t):
        self.appels.append(("ExpoTime", t))
        return 0
    def Toupcam_put_ExpoAGain(self, h, g):
        self.appels.append(("ExpoAGain", g))
        return 0
    def Toupcam_get_AutoExpoEnable(self, h, p):
        p._obj.value = 0
        return 0
    # vitesse / noir / TEC / fan
    def Toupcam_get_MaxSpeed(self, h):
        return 2
    def Toupcam_get_Speed(self, h, p):
        p._obj.value = 0
        return 0
    def Toupcam_get_Option(self, h, opt, p):
        if opt == mtt.TOUPCAM_OPTION_BLACKLEVEL:
            p._obj.value = self.noir      # relu après chaque pose (jalon 50)
        elif opt == mtt.TOUPCAM_OPTION_TEC:
            p._obj.value = 0
        elif opt == mtt.TOUPCAM_OPTION_TECTARGET:
            p._obj.value = self.consigne
        elif opt == mtt.TOUPCAM_OPTION_FAN:
            p._obj.value = 1
        else:
            p._obj.value = 0
        return 0
    def Toupcam_put_Option(self, h, opt, val):
        self.appels.append(("put_Option", opt, val))
        if opt == mtt.TOUPCAM_OPTION_BLACKLEVEL:
            self.noir = val               # le faux SDK GARDE ce qu'on lui pose
        return 0
    def Toupcam_put_Temperature(self, h, t):
        self.appels.append(("put_Temperature", t))
        self.consigne = t
        return 0
    def Toupcam_get_Temperature(self, h, p):
        p._obj.value = self.temp
        return 0
    def Toupcam_get_FanMaxSpeed(self, h):
        return 3

    # identité / capteur
    def Toupcam_get_MonoMode(self, h):
        return mtt.S_FALSE            # couleur
    def Toupcam_get_MaxBitDepth(self, h):
        return 12
    def Toupcam_get_RawFormat(self, h, pf, pb):
        pf._obj.value = 0x47424752    # FourCC
        pb._obj.value = 12
        return 0
    def Toupcam_get_PixelSize(self, h, idx, px, py):
        px._obj.value, py._obj.value = 3.76, 3.76
        return 0
    def Toupcam_get_ResolutionNumber(self, h):
        return 3
    def Toupcam_get_StillResolutionNumber(self, h):
        return 3
    def Toupcam_get_Revision(self, h, p):
        p._obj.value = 5
        return 0
    @staticmethod
    def _remplir(buf, texte):
        octets = texte.encode("utf-8")[:len(buf) - 1]
        buf[:len(octets)] = octets
    def Toupcam_get_SerialNumber(self, h, buf):
        self._remplir(buf, "TP110826145730ABCD1234FEDC56787")
        return 0
    def Toupcam_get_FwVersion(self, h, buf):
        self._remplir(buf, "3.2.1.20260922")
        return 0
    def Toupcam_get_HwVersion(self, h, buf):
        self._remplir(buf, "3.12")
        return 0
    def Toupcam_get_FpgaVersion(self, h, buf):
        self._remplir(buf, "1.13")
        return 0
    def Toupcam_get_ProductionDate(self, h, buf):
        self._remplir(buf, "20260327")
        return 0
    # formats / binning
    def Toupcam_get_PixelFormatSupport(self, h, cmd, p):
        if cmd == b"\xff":
            p._obj.value = 3
        else:
            p._obj.value = (0x00, 0x04, 0x08)[cmd[0]]
        return 0
    def Toupcam_get_BinningNumber(self, h):
        return 2
    def Toupcam_get_BinningValue(self, h, idx, pp):
        pp._obj.value = (b"1", b"2")[idx]
        return 0
    # ROI / flux
    def Toupcam_put_Roi(self, h, x, y, w, hgt):
        self.appels.append(("put_Roi", x, y, w, hgt))
        return 0
    def Toupcam_get_Roi(self, h, px, py, pw, ph):
        px._obj.value, py._obj.value = 0, 0
        pw._obj.value, ph._obj.value = 3856, 2180
        return 0
    def Toupcam_get_Size(self, h, pw, ph):
        pw._obj.value, ph._obj.value = 1920, 1080
        return 0
    def Toupcam_get_FinalSize(self, h, pw, ph):
        pw._obj.value, ph._obj.value = 1920, 1080
        return 0


def banc_frais(dll):
    """Instance du banc sans UI ni thread (mode test pur)."""
    b = diag.BancToup.__new__(diag.BancToup)
    b.mode_console = True
    b.dll = dll
    b.chemin_dll = "FAUX.dll"
    b.handle = 0x4242
    b.nom = "SkyEye26AM"
    b.ouverte = True
    b.flux_actif = False
    b.caps = None
    b._verdict = []
    b._fiches = []
    b._callback_ref = None
    b._verrou = __import__("threading").Lock()
    b._derniere = None
    b._still = None
    b._compteur = 0
    b._w = b._h = 3856
    b._ui_q = queue.Queue()
    b._jobs = queue.Queue()
    b._tec_allume = False
    b._last_fps_log = 0.0
    b._log = lambda m: None
    return b


faux_b = _FauxDLLBanc()
b = banc_frais(faux_b)
b._lister_controles()
verifie("réglages : plage expo lue (24 µs → 2e9 µs)",
        b.caps.get("expo") == (24, 2_000_000_000, 10_000))
verifie("réglages : plage gain lue (100 % → 2600 %)",
        b.caps.get("gain") == (100, 2600, 100))
verifie("réglages : TEC exposé via get_Option", "tec" in b.caps)
verifie("réglages : noir = 25", b.caps.get("noir") == 25)
verifie("réglages : température -5,2 °C (unités 0,1 °C)",
        b.caps.get("temperature") == -52)
verdict = "\n".join(b._verdict)
verifie("verdict : COULEUR (S_FALSE)", "COULEUR" in verdict)
verifie("verdict : 12 bits max", "12 bits" in verdict)
verifie("verdict : plage expo en µs et s", "24 µs" in verdict
        and "2e+06" in verdict or "2000000" in verdict or "s max" in verdict)
verifie("verdict : plage gain 100 → 2600 %", "100 % → 2600 %" in verdict)
verifie("verdict : TEC PILOTABLE", "TEC       : PILOTABLE" in verdict)
verifie("verdict : noir réglable, actuel 25", "actuel 25" in verdict)
verifie("verdict : bins exposés [1, 2]", "'1', '2'" in verdict)
verifie("verdict : formats RAW8/RAW16/RGB888",
        "RAW8" in verdict and "RAW16" in verdict and "RGB888" in verdict)
verifie("verdict : SN lu", "TP110826145730ABCD1234FEDC56787" in verdict)
verifie("verdict : fw/hw/fpga lus",
        "3.2.1.20260922" in verdict and "3.12" in verdict
        and "1.13" in verdict)

# --- 4b) plage du NOIR : table DOCUMENTÉE puis ÉPROUVÉE (jalon 50) -------------
verifie("banc : profondeur 12 bits → table toupcam.h 31 × 16 = 496",
        mtt.TOUPCAM_BLACKLEVEL_MAX_PAR_BITS[12] == 496
        and mtt.TOUPCAM_BLACKLEVEL_MAX_PAR_BITS[16] == 7936
        and mtt.TOUPCAM_BLACKLEVEL_MIN == 0)
verifie("banc : bornes du noir ÉPROUVÉES (posé 0 puis 496 → relu pareil)",
        b.caps.get("noir_plage") == (0, 496))
verifie("banc : valeur d'origine du noir RESTAURÉE après l'essai",
        faux_b.noir == 25 and b.caps.get("noir") == 25)
verifie("verdict : plage du noir CONSTATÉE affichée",
        "NOIR      : réglable, actuel 25 · plage CONSTATÉE 0 → 496"
        in verdict)

# la SONDE de l'appli sur le même faux SDK (12 bits) → bornes des curseurs
cam_b = mtt.TouptekCamera(0)
cam_b.name = "SkyEye26AM"
cam_b._handle = 0x4242
cam_b._w, cam_b._h = 3856, 2180
mtt._DLL = faux_b
cap_b = cam_b.detecter_capacites()
verifie("capacites (12 bits) : expo 24 µs → 2e9 µs et gain % 100 → 2600",
        cap_b.expo_us == (24, 2_000_000_000) and cap_b.gain == (100, 2600))
verifie("capacites (12 bits) : couleur (get_MonoMode = S_FALSE) et 12 bits",
        cap_b.couleur is True and cap_b.bits == 12)
verifie("capacites (12 bits) : noir 0 → 496, valeur courante 25",
        cap_b.offset == (0, 496) and cap_b.extras["21"]["val"] == 25
        and cap_b.plage("offset") == (0.0, 496.0, 1.0))
cam_b.definir_offset(50)
verifie("definir_offset : posé tel quel dans la plage détectée",
        ("put_Option", mtt.TOUPCAM_OPTION_BLACKLEVEL, 50) in faux_b.appels
        and cam_b._noir_max == 496)
mtt._DLL = None

# --- 5) poses : expo, gain, TEC (0,1 °C), ROI (pair, min 8×8) -------------------
b._pose_expo(50_000)
verifie("pose expo : put_ExpoTime(50000) envoyé",
        ("ExpoTime", 50_000) in faux_b.appels)
b._pose_gain(210)
verifie("pose gain : put_ExpoAGain(210 %) envoyé",
        ("ExpoAGain", 210) in faux_b.appels)
b._tec_on(-10)
verifie("pose TEC : put_Option(TEC, 1) + put_Temperature(-100 = -10 °C)",
        ("put_Option", mtt.TOUPCAM_OPTION_TEC, 1) in faux_b.appels
        and ("put_Temperature", -100) in faux_b.appels)
b._tec_off()
verifie("TEC off : put_Option(TEC, 0)",
        ("put_Option", mtt.TOUPCAM_OPTION_TEC, 0) in faux_b.appels)
b._pose_roi(1, 3, 3857, 2199)
verifie("pose ROI : offset/ taille rendus PAIRS (0, 2, 3856, 2198)",
        ("put_Roi", 0, 2, 3856, 2198) in faux_b.appels)
b._pose_roi(0, 0, 4, 4)
verifie("pose ROI : taille forcée au minimum 8×8",
        ("put_Roi", 0, 0, 8, 8) in faux_b.appels)

# --- bilan ---------------------------------------------------------------------
echecs = [l for l, ok in VERIFICATIONS if not ok]
print(f"_test_camera_touptek : {len(VERIFICATIONS) - len(echecs)}"
      f"/{len(VERIFICATIONS)} vérifications OK")
for l in echecs:
    print("  ÉCHEC :", l)
sys.exit(1 if echecs else 0)



