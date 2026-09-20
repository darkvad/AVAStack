# -*- coding: utf-8 -*-
"""Tests du jalon 37 — sonde TEC SVBONY PAR L'EFFET (contrôles présents ≠
TEC présent).

Constat RÉEL (Alain, test SV305C du 20/09/2026) : la SV305C de guidage
n'a PAS de TEC, mais le SDK énumère quand même les contrôles 14-17
(CoolerEnable, TargetTemp, Temperature, CoolerPower) qui affichent « 20 °C,
puissance 0 % » — valeurs bidon. Résultat : les boutons ❄ s'activaient et
« Réguler » levait « CoolerEnable refusé par le SDK — vérifier
l'alimentation 12 V » (probablement un firmware commun avec la SV305C Pro
refroidie).

Correctif jalon 37 : detecter_capacites() TENTE CoolerEnable = 1 (verdict
par l'EFFET, cf. règle générale « réglage relu ≠ réglage appliqué ») :
refus → pas de TEC (cap.tec False, lire_refroidissement → None → boutons ❄
grisés) ; succès → TEC présent, puis l'état initial de CoolerEnable est
RESTAURÉ (ne pas laisser le TEC démarré rien que pour une détection).
"""

import sys

if hasattr(sys.stdout, "reconfigure"):        # ✓/✗ → toujours encodable
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from avastack.cameras import svbony as msvb

VERIFICATIONS = []


def verifie(label, condition):
    VERIFICATIONS.append((label, bool(condition)))


# --- contrôles énumérés par le SDK (les MÊMES avec et sans TEC, cf. réel) --
CONTROLES = [
    (msvb.SVB_GAIN, b"Gain", 0, 450, 100),
    (msvb.SVB_EXPOSURE, b"Exposure", 36, 2000000000, 10000),
    (msvb.SVB_BLACK_LEVEL, b"Black Level", 0, 255, 10),
    (msvb.SVB_COOLER_ENABLE, b"Cooler Enable", 0, 1, 0),
    (msvb.SVB_TARGET_TEMPERATURE, b"Target Temperature", -500, 500, 0),
    (msvb.SVB_CURRENT_TEMPERATURE, b"Temperature", -500, 500, 0),
    (msvb.SVB_COOLER_POWER, b"Cooler Power Perc", 0, 100, 0),
]


class FauxDLL_SVB_TEC:
    """Reproduit le comportement RÉEL de la SV305C (20/09/2026) : les
    contrôles TEC 14-17 sont ÉNUMÉRÉS et LISIBLES (valeurs bidon : temp
    200 = 20,0 °C, puissance 0) mais CoolerEnable est REFUSÉ à la pose
    quand il n'y a pas de TEC physique. Journalise les poses pour vérifier
    la restauration après le sondage."""

    def __init__(self, tec_refuse=True):
        self.tec_refuse = tec_refuse
        self.cooler = 0              # état courant de CoolerEnable
        self.journal = []            # poses (cid, valeur)

    def SVBGetSensorPixelSize(self, cid, ptr):
        return 1                     # contrôle optionnel : échec, pas grave

    def SVBGetNumOfControls(self, cid, ptr):
        ptr._obj.value = len(CONTROLES)
        return 0

    def SVBGetControlCaps(self, cid, i, ptr):
        if i >= len(CONTROLES):
            return 1
        cid_ctl, nom, mini, maxi, defaut = CONTROLES[i]
        c = ptr._obj
        c.Name = nom
        c.MaxValue, c.MinValue, c.DefaultValue = maxi, mini, defaut
        c.IsWritable = 1
        c.IsAutoSupported = 0
        c.ControlType = cid_ctl
        return 0

    def SVBGetControlValue(self, cid, t, val, auto):
        valeurs = {msvb.SVB_BLACK_LEVEL: 10,
                   msvb.SVB_COOLER_ENABLE: self.cooler,
                   msvb.SVB_TARGET_TEMPERATURE: -100,   # -10,0 °C (×10)
                   msvb.SVB_CURRENT_TEMPERATURE: 200,   # 20,0 °C (×10) BIDON
                   msvb.SVB_COOLER_POWER: 0,            # 0 % — BIDON
                   msvb.SVB_GAIN: 100,
                   msvb.SVB_EXPOSURE: 10000}
        if t not in valeurs:
            return 1
        val._obj.value = valeurs[t]
        auto._obj.value = 0
        return 0

    def SVBSetControlValue(self, cid, t, v, auto):
        self.journal.append((t, v))
        if t == msvb.SVB_COOLER_ENABLE and self.tec_refuse:
            return 3                     # ← le REFUS RÉEL (pas de TEC)
        if t == msvb.SVB_COOLER_ENABLE:
            self.cooler = v
        return 0


def _camera(fake):
    """Caméra SVBONY ouverte prête pour detecter_capacites (fiche minime)."""
    cam = msvb.SVBonyCamera.__new__(msvb.SVBonyCamera)
    cam.id = 0
    cam.name = "SVBONY SV305C"
    cam._started = True
    prop = msvb._SVBCameraProperty()
    prop.MaxWidth, prop.MaxHeight = 1920, 1080
    prop.IsColorCam = 1
    prop.MaxBitDepth = 12
    cam._props = prop
    msvb._DLL = fake
    return cam


# === SUITE (tests + bilan) ===

# --- 1) SV305C SANS TEC (le cas réel d'Alain) : CoolerEnable REFUSÉ --------
faux1 = FauxDLL_SVB_TEC(tec_refuse=True)
cam1 = _camera(faux1)
cap1 = cam1.detecter_capacites()
verifie("pas de TEC : cap.tec FALSE malgré les contrôles 14-17 énumérés",
        cap1.tec is False)
verifie("pas de TEC : pas de plage de consigne, température non lisible",
        cap1.tec_consigne is None and cap1.temperature_lisible is False)
verifie("pas de TEC : note explicative « REFUSÉ » dans les extras",
        "REFUSÉ" in cap1.extras.get("tec", ""))
verifie("pas de TEC : sondage app → None (boutons ❄ RESTENT GRISÉS)",
        cam1.lire_refroidissement() is None)
verifie("pas de TEC : le sondage a tenté CoolerEnable = 1 (verdict par "
        "l'EFFET) et n'a RIEN restauré (le set initial a été refusé)",
        (msvb.SVB_COOLER_ENABLE, 1) in faux1.journal
        and (msvb.SVB_COOLER_ENABLE, 0) not in faux1.journal)
verifie("pas de TEC : le reste des capacités reste détecté",
        cap1.gain == (0, 450) and cap1.offset == (0, 255)
        and cap1.expo_us == (36, 2000000000))

# --- 2) caméra AVEC TEC : CoolerEnable accepté puis RESTAURÉ ---------------
faux2 = FauxDLL_SVB_TEC(tec_refuse=False)
cam2 = _camera(faux2)
cap2 = cam2.detecter_capacites()
verifie("avec TEC : cap.tec TRUE (CoolerEnable accepté par le SDK)",
        cap2.tec is True)
verifie("avec TEC : plage de consigne + température lisible",
        cap2.tec_consigne == (-500, 500)
        and cap2.temperature_lisible is True)
verifie("avec TEC : sondage app → valeurs réelles (20,0 °C, PWM 0, -10 °C)",
        cam2.lire_refroidissement() == (20.0, 0, -10.0))
verifie("avec TEC : CoolerEnable = 1 tenté PUIS restauré à 0 (le TEC n'est "
        "pas laissé démarré rien que pour une détection)",
        faux2.journal == [(msvb.SVB_COOLER_ENABLE, 1),
                          (msvb.SVB_COOLER_ENABLE, 0)]
        and faux2.cooler == 0)

# --- 3) compatibilité : sondage direct SANS detecter_capacites (bancs) -----
# Les bancs appellent lire_refroidissement() directement, sans passer par
# detecter_capacites : _tec_pilotable absent → comportement inchangé.
faux3 = FauxDLL_SVB_TEC(tec_refuse=False)
cam3 = _camera(faux3)
verifie("compatibilité bancs : sans sondage préalable, lire_refroidissement "
        "fonctionne comme avant (défaut = TEC pilotable)",
        cam3.lire_refroidissement() == (20.0, 0, -10.0))

# --- bilan -------------------------------------------------------------------
echecs = [l for l, ok in VERIFICATIONS if not ok]
print(f"_test_tec_sonde_jalon37 : "
      f"{len(VERIFICATIONS) - len(echecs)}/{len(VERIFICATIONS)} vérifications OK")
for l in echecs:
    print("  ÉCHEC :", l)
sys.exit(1 if echecs else 0)
