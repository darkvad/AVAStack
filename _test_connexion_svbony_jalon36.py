# -*- coding: utf-8 -*-
"""Tests du jalon 36 — connexion automatique SVBONY « Propriétés illisibles ».

Constat RÉEL (banc _diag_camera_svbony.py, SV305C, 19/09/2026) :
SVBGetCameraProperty échoue AVANT l'ouverture — le SDK SVBONY n'expose la
fiche qu'une fois SVBOpenCamera passé, contrairement à la procédure « fiche
puis ouverture » de la doc (clone ZWO). L'app lisait donc la fiche AVANT
l'ouverture et refusait toute connexion automatique (« Propriétés
illisibles ») sans même tenter SVBOpenCamera — alors que le banc, qui
ouvre d'abord, fonctionne.

Correctif jalon 36 : SVBonyCamera.open() ouvre D'ABORD, lit la fiche
ENSUITE, et REFERME la caméra si la fiche reste illisible. Ce test rejoue
le comportement réel du SDK via un double de DLL qui REFUSE
SVBGetCameraProperty tant que SVBOpenCamera n'a pas réussi (comme la
SV305C réelle), et vérifie l'ordre des appels + la fermeture propre.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):        # ✓/✗ → toujours encodable
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from avastack.cameras import svbony as msvb

VERIFICATIONS = []


def verifie(label, condition):
    VERIFICATIONS.append((label, bool(condition)))


class FauxDLL_SVB_Preouverture:
    """Reproduit le comportement RÉEL constaté sur la SV305C (19/09/2026) :
    SVBGetCameraProperty → erreur tant que SVBOpenCamera n'a pas réussi.
    Journalise l'ordre des appels SDK pour vérifier le chemin d'ouverture."""

    def __init__(self, prop_toujours_refusee=False):
        self.journal = []             # ordre des appels SDK
        self.ouverte = False
        self.prop_toujours_refusee = prop_toujours_refusee
        self.fermee_apres_echec = False

    def SVBGetNumOfConnectedCameras(self):
        self.journal.append("num")
        return 1

    def SVBGetCameraInfo(self, ptr, idx):
        self.journal.append("info")
        info = ptr._obj               # byref() → CArgObject
        info.FriendlyName = b"SVBONY SV305C"
        info.CameraID = 0
        return 0

    def SVBOpenCamera(self, cid):
        self.journal.append("open")
        self.ouverte = True
        return 0

    def SVBCloseCamera(self, cid):
        self.journal.append("close")
        self.ouverte = False
        self.fermee_apres_echec = True
        return 0

    def SVBGetCameraProperty(self, cid, ptr):
        self.journal.append("prop")
        if not self.ouverte:
            return 1                  # ← le refus RÉEL du SDK pré-ouverture
        if self.prop_toujours_refusee:
            return 1
        p = ptr._obj
        p.MaxWidth, p.MaxHeight = 1920, 1080
        p.IsColorCam = 1
        p.MaxBitDepth = 12
        return 0

    def SVBSetOutputImageType(self, cid, fmt):
        self.journal.append("fmt")
        return 0

    def SVBSetROIFormat(self, cid, x, y, w, h, b):
        self.journal.append("roi")
        return 0

    def SVBStartVideoCapture(self, cid):
        self.journal.append("start")
        return 0

    def SVBStopVideoCapture(self, cid):
        self.journal.append("stop")
        return 0

    def SVBSetAutoSaveParam(self, cid, flag):
        self.journal.append("autosave")
        return 0


# --- 1) chemin nominal — SDK SVBONY réel (fiche refusée avant ouverture) ----
faux = FauxDLL_SVB_Preouverture()
msvb._DLL = faux
cam = msvb.SVBonyCamera(0)
cam.open()
verifie("ordre SDK : info → OPEN → prop (la fiche est lue APRÈS l'ouverture, "
        "jamais avant)", faux.journal[:4] == ["num", "info", "open", "prop"])
verifie("connexion réussie (caméra ouverte, flux démarré)",
        cam._started and cam.id == 0)
verifie("fiche lue après ouverture : couleur + plein champ",
        cam._is_color is True and cam._w == 1920 and cam._h == 1080)
verifie("format/ROI posés puis flux démarré puis auto-sauvegarde coupée",
        faux.journal[-4:] == ["fmt", "roi", "start", "autosave"])
cam.close()
verifie("close : flux arrêté + caméra fermée",
        not cam._started and cam.id is None
        and faux.journal[-2:] == ["stop", "close"])

# --- 2) fiche illisible MÊME après ouverture (SDK capricieux) ---------------
# La caméra doit être REFERMÉE avant l'échec (pas de caméra orpheline qui
# bloquerait la connexion suivante — leçon générale des SDK natifs).
faux2 = FauxDLL_SVB_Preouverture(prop_toujours_refusee=True)
msvb._DLL = faux2
cam2 = msvb.SVBonyCamera(0)
try:
    cam2.open()
    verifie("fiche illisible après ouverture : exception levée", False)
except RuntimeError as e:
    verifie("fiche illisible après ouverture : exception « Propriétés "
            "illisibles » levée", "Propriétés illisibles" in str(e))
verifie("fiche illisible : caméra REFERMÉE avant l'échec (pas de caméra "
        "orpheline)", faux2.fermee_apres_echec
        and faux2.journal[-2:] == ["prop", "close"])
verifie("fiche illisible : id réinitialisé", cam2.id is None)

# --- bilan -------------------------------------------------------------------
echecs = [l for l, ok in VERIFICATIONS if not ok]
print(f"_test_connexion_svbony_jalon36 : "
      f"{len(VERIFICATIONS) - len(echecs)}/{len(VERIFICATIONS)} vérifications OK")
for l in echecs:
    print("  ÉCHEC :", l)
sys.exit(1 if echecs else 0)