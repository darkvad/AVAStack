# -*- coding: utf-8 -*-
"""Test du banc caméra Player One (_diag_camera_playerone.py) — sans matériel.

Le banc parle au SDK via ctypes : ici, la DLL est REMPLACÉE par un faux
SDK qui répond exactement ce que l'en-tête officiel POACamera.h promet
(configID relu == ID demandé, valeurs d'attributs plausibles). On valide :
constantes complètes, conversion POAConfigValue (layouts récent ET ancien),
détection du layout (validation double sur configs 0 et 7, et rejet d'un
faux SDK incohérent), attributs, verdict « possibilités », tolérance aux
erreurs SDK (11 = EXPOSING traité comme OK par _stop_expo_si_besoin).
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "diag_poa", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "_diag_camera_playerone.py"))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

VERIFICATIONS = []


def verifie(label, condition):
    VERIFICATIONS.append((label, bool(condition)))


def banc_frais():
    """Instance du banc sans UI ni DLL (mode test pur)."""
    b = diag.BancPOA.__new__(diag.BancPOA)
    b.mode_console = True
    b.dll = None
    b.chemin_dll = None
    b.layout = "récent"
    b.cam_id = 7
    b.props = None
    b.nom = ""
    b.ouverte = True
    b.flux_actif = False
    b._ui_q = queue.Queue()
    b._jobs = queue.Queue()
    b._verdict = []
    b._attr_cache = {}
    b._log = lambda m: None
    b.sonde = diag.mpoa.POASonde(None, 7)   # DLL branchée avant usage
    return b


# --- 1) constantes ------------------------------------------------------------
verifie("31 configs nommées (0-30)",
        all(i in diag.NOMS_CONFIGS for i in range(31)))
verifie("4 formats nommés", set(diag.NOMS_FORMATS) == {0, 1, 2, 3})
verifie("18 erreurs nommées", all(i in diag.NOMS_ERREURS for i in range(18)))
verifie("IDs clés du verdict : expo=0, gain=1, offset=7, TEC=18",
        diag.NOMS_CONFIGS[0].startswith("Exposition")
        and diag.NOMS_CONFIGS[1].startswith("Gain")
        and diag.NOMS_CONFIGS[7] == "Offset"
        and diag.NOMS_CONFIGS[18].startswith("Refroidissement"))

# --- 2) conversion POAConfigValue (union) -------------------------------------
b = banc_frais()
u = b._union_depuis(1234, 0)
verifie("union int aller-retour", b._valeur_union(u, 0) == 1234)
u = b._union_depuis(-10, 0)
verifie("union int négatif (consigne TEC)", b._valeur_union(u, 0) == -10)
u = b._union_depuis(3.25, 1)
verifie("union float (layout récent, double)",
        abs(b._valeur_union(u, 1) - 3.25) < 1e-12)
# layout ancien : la sonde garde son PROPRE état de layout (délégation)
b.sonde.layout = "ancien"
# c'est le SDK qui ÉCRIT un float 32 bits dans l'union — on simule
# exactement cette écriture, puis on relit comme le banc le fait.
u32 = diag._POAConfigValue()
u32.float32 = 3.25
verifie("union float (layout ancien, float32)",
        abs(b._valeur_union(u32, 1) - 3.25) < 1e-5)
verifie("union bool", b._valeur_union(u, 2) in (True, False))
b.layout = "récent"
b.sonde.layout = "récent"

# --- 3) détection du layout avec faux SDK -------------------------------------


class _FauxAttrDLL:
    """Faux SDK : remplit la structure avec configID == ID demandé
    (correct) ou avec des valeurs incohérentes (incorrect)."""

    def __init__(self, correct=True):
        self.correct = correct

    def POAGetConfigAttributesByConfigID(self, cam, cid, ptr):
        if b.layout == "ancien":
            s = ctypes.cast(ptr, ctypes.POINTER(
                diag._POAConfigAttributesAncien)).contents
            if self.correct:
                s.configID = cid
                s.valueType = 0
                s.maxValue = 9000
                s.minValue = 24
                s.defaultValue = 25
            else:
                s.configID = 999
        else:
            s = ctypes.cast(ptr, ctypes.POINTER(
                diag._POAConfigAttributes)).contents
            if self.correct:
                s.configID = cid
                s.valueType = 0
                s.maxValue.intValue = 9000
                s.minValue.intValue = 24
                s.defaultValue.intValue = 25
            else:
                s.configID = 999
                s.valueType = 9
        return 0


b.dll = _FauxAttrDLL(correct=True)
b.sonde = diag.mpoa.POASonde(b.dll, 7)
verifie("layout récent validé par le faux SDK récent",
        b._valider_layout() == "récent")
verifie("attributs lus via le faux SDK",
        b._attributs(0)["max"] == 9000 and b._attributs(0)["min"] == 24)

b.dll = _FauxAttrDLL(correct=False)
b.sonde = diag.mpoa.POASonde(b.dll, 7)
verifie("faux SDK incohérent → layout NON reconnu",
        b._valider_layout() is None)

# --- 3b) BUG RÉEL corrigé (rapport Uranus-C Pro, 19/09/2026) : les
#     contrôles FLOTTANTS étaient relus comme des ENTIERS (température
#     affichée « -1073741824 » = les bits du flottant -2.0). Cause : le banc
#     réénumérait lui-même et ne remplissait donc pas le cache de types de
#     la sonde. Correctif : le banc passe par sonde.lister(). On vérifie ici
#     que lister() remplit bien le cache ET que lire() rend un FLOTTANT.


class _FauxConfigsDLL(_FauxAttrDLL):
    """Faux SDK minimal pour la sonde : 2 contrôles (0 = INT, 3 = FLOAT).
    Surcharges le handler par configID du parent, qui force valueType = 0."""

    def POAGetConfigAttributesByConfigID(self, cam, cid, ptr):
        attr = ctypes.cast(ptr, ctypes.POINTER(
            diag._POAConfigAttributes)).contents
        if cid == 3:
            attr.configID, attr.valueType = 3, 1           # VAL_FLOAT
            attr.maxValue.floatValue = 100.0
            attr.minValue.floatValue = -50.0
        else:
            attr.configID, attr.valueType = cid, 0         # VAL_INT
            attr.maxValue.intValue, attr.minValue.intValue = 9000, 24
        attr.isWritable, attr.isReadable = 1, 1
        attr.szConfName = b"Temp" if cid == 3 else b"Exposure"
        return 0

    def POAGetConfigsCount(self, cam, ptr):
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_int)).contents.value = 2
        return 0

    def POAGetConfigAttributes(self, cam, i, ptr):
        attr = ctypes.cast(ptr, ctypes.POINTER(
            diag._POAConfigAttributes)).contents
        if i == 0:
            attr.configID, attr.valueType = 0, 0
            attr.maxValue.intValue, attr.minValue.intValue = 9000, 24
        else:
            attr.configID, attr.valueType = 3, 1        # VAL_FLOAT
            attr.maxValue.floatValue = 100.0
            attr.minValue.floatValue = -50.0
        attr.isWritable, attr.isReadable = 1, 1
        attr.szConfName = b"Temp" if i else b"Exposure"
        return 0

    def POAGetConfig(self, cam, cid, ptr, ptr_auto):
        val = ctypes.cast(ptr, ctypes.POINTER(diag._POAConfigValue)).contents
        if cid == 3:
            val.floatValue = -2.0          # les bits qui donnaient -1073741824
        else:
            val.intValue = 10000
        return 0


b = banc_frais()
b.dll = _FauxConfigsDLL()
b.sonde = diag.mpoa.POASonde(b.dll, 7)
cache = b.sonde.lister()
verifie("lister() énumère les contrôles", sorted(cache) == [0, 3])
verifie("cache de types rempli (0 = INT, 3 = FLOAT)",
        cache[0]["type"] == 0 and cache[3]["type"] == 1)
cur = b.sonde.lire(3)
verifie("contrôle FLOTTANT relu en flottant (et non en entier)",
        isinstance(cur[0], float) and abs(cur[0] + 2.0) < 1e-9)
cur = b.sonde.lire(0)
verifie("contrôle ENTIER relu en entier", cur[0] == 10000)

# --- 4) verdict « possibilités » ----------------------------------------------
b = banc_frais()
p = diag._POACameraProperties()
p.cameraModelName = b"URANUS-C PRO"
p.sensorModelName = b"IMX585"
p.maxWidth, p.maxHeight = 3856, 2180
p.bitDepth = 16
p.isColorCamera, p.isHasCooler, p.isUSB3Speed = 1, 1, 1
p.bayerPattern_ = 0
p.pixelSize = 2.9
p.isSupportHardBin = 1
for i, v in enumerate((1, 2, 0, 0, 0, 0, 0, 0)):
    p.bins_[i] = v
for i, v in enumerate((0, 1, 2, -1, 0, 0, 0, 0)):
    p.imgFormats_[i] = v
b.props = p
b._attr_cache = {
    0: {"min": 24, "max": 2000000000, "defaut": 10000, "type": 0,
        "ecrivable": True, "lisible": True, "auto": False,
        "nom": "Exposure", "desc": ""},
    1: {"min": 100, "max": 4692, "defaut": 210, "type": 0,
        "ecrivable": True, "lisible": True, "auto": False,
        "nom": "Gain", "desc": ""},
    7: {"min": 0, "max": 100, "defaut": 25, "type": 0,
        "ecrivable": True, "lisible": True, "auto": False,
        "nom": "Offset", "desc": ""},
    15: {"min": 0, "max": 0, "defaut": 1.72, "type": 1,
         "ecrivable": False, "lisible": True, "auto": False,
         "nom": "EGain", "desc": ""},
    17: {"min": -40, "max": 30, "defaut": -10, "type": 0,
         "ecrivable": True, "lisible": True, "auto": False,
         "nom": "TargetTemp", "desc": ""},
    18: {"min": 0, "max": 1, "defaut": 0, "type": 0,
         "ecrivable": True, "lisible": True, "auto": False,
         "nom": "Cooler", "desc": ""},
    3: {"min": 0, "max": 0, "defaut": 12.5, "type": 1,
        "ecrivable": False, "lisible": True, "auto": False,
        "nom": "Temperature", "desc": ""},
}
b._construire_verdict()
verdict = "\n".join(b._verdict)
verifie("verdict : capteur IMX585 présent", "IMX585" in verdict)
verifie("verdict : plage exposition en µs et s",
        "EXPOSITION : 24 µs" in verdict and "2000.0 s" in verdict)
verifie("verdict : plage gain + mention gain unitaire 210",
        "GAIN : 100 → 4692" in verdict and "210" in verdict
        and "DANS la plage" in verdict)
verifie("verdict : plage offset", "OFFSET : 0 → 100" in verdict)
verifie("verdict : TEC écrivable + consigne",
        "écrivable ✓" in verdict and "-40→30 °C" in verdict)
verifie("verdict : bins supportés (1x1, 2x2)", "[1, 2]" in verdict)
verifie("verdict : bin matériel signalé", "bin MATÉRIEL oui" in verdict)
verifie("verdict : ROI plein champ 3856×2180",
        "3856×2180" in verdict and "ROI" in verdict)
verifie("verdict : formats RAW8/RAW16/RGB24",
        "RAW8" in verdict and "RAW16" in verdict and "RGB24" in verdict)
verifie("verdict : EGAIN flottant", "1.72" in verdict)

# --- 5) tolérance à l'erreur 11 (EXPOSING) ------------------------------------


class _FauxFluxDLL:
    def __init__(self, code_stop):
        self.code_stop = code_stop

    def POAStopExposure(self, cam):
        b.stops.append(cam)
        return self.code_stop


b = banc_frais()
b.stops = []
b.dll = _FauxFluxDLL(0)          # arrêt OK
b._stop_expo_si_besoin()
verifie("stop exposure OK accepté", len(b.stops) == 1)
b.dll = _FauxFluxDLL(11)         # déjà en cours → toléré, pas de log d'erreur
b._stop_expo_si_besoin()
verifie("erreur 11 (EXPOSING) tolérée", len(b.stops) == 2)
msgs = []


def _log(m):
    msgs.append(m)


b.dll = _FauxFluxDLL(5)          # 5 = NOT_OPENED → doit être SIGNALÉ
b._log = _log
b._stop_expo_si_besoin()
verifie("vraie erreur signalée dans le log",
        any("NON OUVERTE" in m for m in msgs))

# --- bilan ---------------------------------------------------------------------
echecs = [l for l, ok in VERIFICATIONS if not ok]
print(f"_test_camera_playerone : {len(VERIFICATIONS) - len(echecs)}"
      f"/{len(VERIFICATIONS)} vérifications OK")
for l in echecs:
    print("  ÉCHEC :", l)
sys.exit(1 if echecs else 0)
