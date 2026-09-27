# -*- coding: utf-8 -*-
"""Test de la couche générique de CAPACITÉS (avastack/cameras/capacites.py)
et des sondes ZWO / SVBONY — sans matériel, via faux SDK.

Le même principe que _test_camera_playerone : les DLL sont remplacées par
des faux SDK qui répondent ce que les en-têtes officiels promettent
(ASI_CONTROL_CAPS / SVB_CONTROL_CAPS, structs du wrapper de référence).
On valide : le modèle Capacites (rendus texte/JSON, annotation du gain
unitaire IMX585 = 210, cas « hors plage »), et les sondes ZWO/SVBONY
(énumération des contrôles, plages expo/gain/offset, TEC, bins, formats).
Player One est couvert par _test_camera_playerone.py (sonde POASonde).
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import ctypes
import sys


from avastack.cameras import capacites as mcap
from avastack.cameras import zwo as mzwo
from avastack.cameras import svbony as msvb

VERIFICATIONS = []


def verifie(label, condition):
    VERIFICATIONS.append((label, bool(condition)))


# --- 1) modèle Capacites -------------------------------------------------------
c = mcap.Capacites("Player One", modele="URANUS-C PRO", capteur="IMX585",
                   couleur=True, bits=16, max_l=3856, max_h=2180,
                   pixel_um=2.9)
c.expo_us = (24, 2000000000)
c.gain = (100, 4692)
c.offset = (0, 100)
c.tec = True
c.tec_consigne = (-40, 30)
c.temperature_lisible = True
c.bins = [1, 2]
c.formats = ["RAW8", "RAW16", "RGB24"]
c.usb3 = True
c.st4 = True
t = c.vers_texte()
verifie("verdict : caméra + capteur", "URANUS-C PRO" in t
        and "IMX585" in t)
verifie("verdict : gain unitaire 210 DANS la plage",
        "gain unitaire 210" in t and "DANS la plage" in t)
verifie("verdict : exposition µs et secondes",
        "EXPOSITION : 24 µs" in t and "2000.0 s" in t)
verifie("verdict : offset", "OFFSET : 0 → 100" in t)
verifie("verdict : TEC + consigne + température",
        "TEC OUI" in t and "-40→30 °C" in t and "lisible ✓" in t)
verifie("verdict : bins + formats + USB3/ST4",
        "[1, 2]" in t and "RGB24" in t and "USB3 : oui" in t)
d = c.vers_dict()
verifie("dict : plages sérialisées", d["gain"] == [100, 4692]
        and d["expo_us"] == [24, 2000000000]
        and d["tec_consigne"] == [-40, 30])
verifie("gain unitaire inconnu → None",
        mcap.Capacites("X", capteur="SONY-XYZ").gain_unitaire() is None)
c.gain = (500, 1000)
verifie("verdict : gain unitaire HORS plage signalé",
        "HORS plage" in c.vers_texte())
verifie("verdict sans TEC", "pas de TEC" in
        mcap.Capacites("Y").vers_texte())

# --- 2) sonde ZWO (faux SDK ASI) ------------------------------------------------


class FauxDLL_ZWO:
    """Répond ce que ASICamera2.h promet : fiche + caps par index."""
    CONTROLES = [
        # (id, nom, MAX, MIN, défaut, auto, écrivable) — ordre du SDK
        (mzwo.ASI_GAIN, b"Gain", 4692, 100, 210, 0, 1),
        (mzwo.ASI_EXPOSURE, b"Exposure", 2000000000, 32, 10000, 1, 1),
        (mzwo.ASI_OFFSET, b"Brightness", 100, 0, 8, 0, 1),
        (mzwo.ASI_HARDWARE_BIN, b"Hardware Bin", 1, 0, 0, 0, 1),
        (mzwo.ASI_TARGET_TEMP, b"TargetTemp", 50, -50, -10, 0, 1),
        (mzwo.ASI_TEMPERATURE, b"Temperature", 500, -500, 0, 0, 0),
        (mzwo.ASI_COOLER_ON, b"CoolerOn", 1, 0, 0, 0, 1),
    ]

    def ASIGetCameraProperty(self, ptr, idx):
        info = ctypes.cast(ptr, ctypes.POINTER(
            mzwo._ASICameraInfo)).contents
        info.Name = b"ASI585MC PRO"
        info.CameraID = idx
        info.MaxHeight, info.MaxWidth = 2180, 3856
        info.IsColorCam = 1
        for i, v in enumerate((1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)):
            info.SupportedBins[i] = v
        for i, v in enumerate((0, 1, 2, -1, 0, 0, 0, 0)):
            info.SupportedVideoFormat[i] = v
        info.PixelSize = 2.9
        info.ST4Port = 1
        info.IsCoolerCam = 1
        info.IsUSB3Camera = 1
        info.ElecPerADU = 0.58
        info.BitDepth = 16
        return 0

    def ASIGetNumOfControls(self, cid, ptr):
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_int)).contents.value = \
            len(self.CONTROLES)
        return 0

    def ASIGetControlCaps(self, cid, i, ptr):
        c = ctypes.cast(ptr, ctypes.POINTER(mzwo._ASIControlCaps)).contents
        cid_ctl, nom, maxi, mini, defaut, auto, ecr = self.CONTROLES[i]
        c.Name = nom
        c.MaxValue, c.MinValue, c.DefaultValue = maxi, mini, defaut
        c.IsAutoSupported, c.IsWritable = auto, ecr
        c.ControlType = cid_ctl
        return 0


cam = mzwo.ZWOASICamera.__new__(mzwo.ZWOASICamera)
cam.index = 0
cam.cam = object()          # « ouverte » (sans matériel réel)
cam._asi = None
mzwo._charger_dll = lambda: FauxDLL_ZWO()
cap = cam.detecter_capacites()
verifie("ZWO : sonde renvoie Capacites", isinstance(cap, mcap.Capacites))
verifie("ZWO : marque + modèle dynamiques", cap.marque == "ZWO"
        and cap.modele == "ASI585MC PRO")
verifie("ZWO : plages gain/expo/offset",
        cap.gain == (100, 4692) and cap.expo_us == (32, 2000000000)
        and cap.offset == (0, 100))
verifie("ZWO : TEC détecté via COOLER_ON (+ consigne)",
        cap.tec is True and cap.tec_consigne == (-50, 50)
        and cap.temperature_lisible is True)
verifie("ZWO : bin matériel via le CONTRÔLE (pas la fiche)",
        cap.bin_materiel is True)
verifie("ZWO : bins/formats/USB3/ST4",
        cap.bins == [1, 2] and "RGB24" in cap.formats
        and cap.usb3 is True and cap.st4 is True)
verifie("ZWO : énumération brute complète", len(cap.controles) == 7)
verifie("ZWO : gain unitaire — capteur inconnu → None (pas de guess)",
        cap.gain_unitaire() is None)

# --- 3) sonde SVBONY (faux SDK SVB) ---------------------------------------------


class FauxDLL_SVB:
    """Répond ce que le SDK SVBONY promet (cf. wrapper pysvbony, MIT)."""
    CONTROLES = [
        # (id, nom, MAX, MIN, défaut) — ordre du SDK SVB
        (msvb.SVB_GAIN, b"Gain", 2500, 100, 120),
        (msvb.SVB_EXPOSURE, b"Exposure", 2000000000, 28, 10000),
        (msvb.SVB_BLACK_LEVEL, b"BlackLevel", 64, 0, 8),
        (msvb.SVB_COOLER_ENABLE, b"CoolerEnable", 1, 0, 0),
        (msvb.SVB_TARGET_TEMPERATURE, b"TargetTemp", 50, -50, -10),
        (msvb.SVB_CURRENT_TEMPERATURE, b"Temp", 0, 0, 0),
    ]

    def SVBGetSensorPixelSize(self, cid, ptr):
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_float)).contents.value = 2.9
        return 0

    def SVBGetNumOfControls(self, cid, ptr):
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_int)).contents.value = \
            len(self.CONTROLES)
        return 0

    def SVBGetControlCaps(self, cid, i, ptr):
        c = ctypes.cast(ptr, ctypes.POINTER(msvb._SVBControlCaps)).contents
        cid_ctl, nom, maxi, mini, defaut = self.CONTROLES[i]
        c.Name = nom
        c.MaxValue, c.MinValue, c.DefaultValue = maxi, mini, defaut
        c.IsWritable = 1
        c.ControlType = cid_ctl
        return 0

    def SVBGetControlValue(self, cid, t, val, auto):
        return 0                                  # pas utilisé par la sonde

    def SVBSetControlValue(self, cid, t, v, auto):
        # jalon 37 : le sondage TEC pose CoolerEnable = 1 (verdict par
        # l'EFFET) puis le restaure — le faux SDK l'accepte comme le vrai.
        return 0


cam = msvb.SVBonyCamera.__new__(msvb.SVBonyCamera)
cam.id = 3
cam.name = "SV605CC"
cam._started = True                       # « ouverte » (detecter_capacites
                                          # est à appeler APRÈS open())
prop = msvb._SVBCameraProperty()
prop.MaxWidth, prop.MaxHeight = 3000, 2000
prop.IsColorCam = 0
for i, v in enumerate((1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)):
    prop.SupportedBins[i] = v
for i, v in enumerate((4, 0, -1, 0, 0, 0, 0, 0)):
    prop.SupportedVideoFormat[i] = v
prop.MaxBitDepth = 14
cam._props = prop
msvb._DLL = FauxDLL_SVB()
cap = cam.detecter_capacites()
verifie("SVB : sonde renvoie Capacites", isinstance(cap, mcap.Capacites))
verifie("SVB : marque + modèle (nom lu à l'ouverture)",
        cap.marque == "SVBONY" and cap.modele == "SV605CC")
verifie("SVB : plages gain/expo + offset via BLACK_LEVEL",
        cap.gain == (100, 2500) and cap.expo_us == (28, 2000000000)
        and cap.offset == (0, 64))
verifie("SVB : TEC via COOLER_ENABLE (+ consigne + température lisible)",
        cap.tec is True and cap.tec_consigne == (-50, 50)
        and cap.temperature_lisible is True)
verifie("SVB : bins/formats/mono/bits/pixel",
        cap.bins == [1, 2] and "RAW16" in cap.formats
        and cap.couleur is False and cap.bits == 14
        and abs(cap.pixel_um - 2.9) < 1e-3)
verifie("SVB : énumération brute complète", len(cap.controles) == 6)
verifie("SVB : note « offset = BLACK_LEVEL » documentée",
        cap.extras.get("offset", "").startswith("BLACK_LEVEL"))

# --- 4) contrat CameraBase -------------------------------------------------------
from avastack.cameras.base import CameraBase
verifie("contrat : CameraBase.detecter_capacites → None par défaut",
        CameraBase().detecter_capacites() is None)

# --- 5) déduplication des listes (padding des tableaux SDK) --------------------
# Constat réel du 19/09/2026 : l'Uranus-C Pro renvoie 8 formats dont
# 4 × « RAW8 » (zéro de remplissage = valeur d'énumération VALIDE).
verifie("dedupliquer : ordre conservé, doublons retirés",
        mcap.dedupliquer(["RAW8", "RAW16", "RGB24", "MONO8",
                          "RAW8", "RAW8", "RAW8"])
        == ["RAW8", "RAW16", "RGB24", "MONO8"])
verifie("dedupliquer : liste vide / sans doublon inchangée",
        mcap.dedupliquer([]) == [] and mcap.dedupliquer([1, 2]) == [1, 2])
import avastack.cameras.playerone as mpoa
verifie("contrôle 31 du SDK Player One nommé (au-delà de l'enum 0-30)",
        mpoa.NOMS_CONFIGS.get(31, "").startswith("Exp"))

# --- bilan -----------------------------------------------------------------------
echecs = [l for l, ok in VERIFICATIONS if not ok]
print(f"_test_capacites : {len(VERIFICATIONS) - len(echecs)}"
      f"/{len(VERIFICATIONS)} vérifications OK")
for l in echecs:
    print("  ÉCHEC :", l)
sys.exit(1 if echecs else 0)
