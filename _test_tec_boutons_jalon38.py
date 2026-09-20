# -*- coding: utf-8 -*-
"""Tests du jalon 38 — boutons ❄ TOUJOURS ACTIFS sur SVBONY (décision
d'Alain) : contrôles TEC présents dans le SDK = TEC « pilotable ».

Historique : le jalon 37 avait grisés les boutons ❄ quand CoolerEnable est
refusé à la pose (verdict par l'EFFET). Alain a PRÉFÉRÉ l'ancien
comportement (20/09/2026) : les contrôles TEC du SDK SVBONY existent même
SANS TEC physique (constat réel SV305C : temp 20 °C, puissance 0 % —
firmware probablement commun avec la SV305C Pro refroidie) MAIS les
boutons ❄ doivent rester ACTIFS dès que les contrôles sont énumérés : si
l'alim 12 V d'une caméra refroidie est branchée en cours de session, le
sondage périodique (toutes les 2 s) la fait fonctionner IMMÉDIATEMENT,
sans déconnexion/re-détection. Un « Réguler » sans TEC échoue avec un
message clair (« alim 12 V ») — filet de sécurité suffisant.

Ce test rejoue le constat réel (SV305C sans TEC : CoolerEnable REFUSÉ à
la pose, contrôles 14-17 énumérés avec valeurs bidon) et vérifie :
  - la sonde de capacités n'essaie AUCUNE pose de CoolerEnable ;
  - cap.tec True + plage de consigne + sondage → valeurs (boutons actifs) ;
  - consigne_refroidissement → RuntimeError avec « 12 V » (filet).
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
    quand il n'y a pas de TEC physique."""

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

# --- 1) SV305C SANS TEC (le cas réel d'Alain) : boutons ❄ ACTIFS -----------
faux1 = FauxDLL_SVB_TEC(tec_refuse=True)
cam1 = _camera(faux1)
cap1 = cam1.detecter_capacites()
verifie("décision d'Alain : cap.tec TRUE dès que les contrôles TEC sont "
        "énumérés, MÊME sans TEC physique",
        cap1.tec is True)
verifie("décision d'Alain : plage de consigne + température lisible "
        "(curseur TEC reconstruit, boutons ❄ ACTIFS)",
        cap1.tec_consigne == (-500, 500) and cap1.temperature_lisible is True)
verifie("décision d'Alain : sondage app → valeurs (boutons ❄ ACTIFS, "
        "rebrancher l'alim 12 V en cours de session suffit)",
        cam1.lire_refroidissement() == (20.0, 0, -10.0))
verifie("la sonde de capacités ne pose AUCUN CoolerEnable (pas de verdict "
        "par l'EFFET — essai jalon 37 annulé)",
        not any(t == msvb.SVB_COOLER_ENABLE for t, _ in faux1.journal))
verifie("le reste des capacités reste détecté",
        cap1.gain == (0, 450) and cap1.offset == (0, 255)
        and cap1.expo_us == (36, 2000000000))

# --- 2) filet de sécurité : « Réguler » sans TEC → message clair -----------
try:
    cam1.consigne_refroidissement(-10.0)
    verifie("sans TEC : « Réguler » doit lever RuntimeError (refus SDK)",
            False)
except RuntimeError as e:
    verifie("sans TEC : « Réguler » → message clair avec « alim 12 V »",
            "12 V" in str(e))
verifie("sans TEC : la pose CoolerEnable = 1 a bien été REFUSÉE par le SDK "
        "(l'app ne l'a pas contournée)",
        (msvb.SVB_COOLER_ENABLE, 1) in faux1.journal
        and faux1.cooler == 0)

# --- 3) caméra AVEC TEC : comportement inchangé -----------------------------
faux2 = FauxDLL_SVB_TEC(tec_refuse=False)
cam2 = _camera(faux2)
cap2 = cam2.detecter_capacites()
verifie("avec TEC : cap.tec True + consigne + sondage (aucun changement)",
        cap2.tec is True and cap2.tec_consigne == (-500, 500)
        and cam2.lire_refroidissement() == (20.0, 0, -10.0))
cam2.consigne_refroidissement(-10.5)
verifie("avec TEC : régulation fonctionne (CoolerEnable = 1 puis consigne)",
        faux2.cooler == 1)

# --- bilan -------------------------------------------------------------------
echecs = [l for l, ok in VERIFICATIONS if not ok]
print(f"_test_tec_boutons_jalon38 : "
      f"{len(VERIFICATIONS) - len(echecs)}/{len(VERIFICATIONS)} vérifications OK")
for l in echecs:
    print("  ÉCHEC :", l)
sys.exit(1 if echecs else 0)
