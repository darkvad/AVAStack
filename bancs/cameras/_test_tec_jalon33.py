# -*- coding: utf-8 -*-
"""Tests unitaires du jalon 33 — pilotage TEC Player One / SVBONY.

Le mécanisme app (sondage → boutons ❄, demande consigne/arrêt exécutée
dans le thread de travail, rafraîchissement 2 s) est DÉJÀ générique depuis
le jalon 26 : il appelle les trois méthodes de CameraBase. Ce test vérifie
les deux implémentations SDK ajoutées au jalon 33, contre des DOUBLES de
DLL fidèles aux relevés réels des bancs (19/09/2026) :
  - Player One : TargetTemp (ctrl 17, °C, int OU float selon les attributs)
    PUIS Cooler ON/OFF (ctrl 18) ; température (ctrl 3, FLOAT), puissance
    en % (ctrl 16) ;
  - SVBONY : CoolerEnable (ctrl 14) PUIS TargetTemp ×10 (ctrl 15 — unités
    de 0,1 °C) ; température (ctrl 16, 0,1 °C), puissance en % (ctrl 17) ;
    conversion % → PWM 0-255 (convention d'affichage commune à l'app).
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

if hasattr(sys.stdout, "reconfigure"):        # ✓/✗ → toujours encodable
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from avastack.cameras import playerone as mpo
from avastack.cameras import svbony as msvb

ECHECS = []


def verifie(cond, txt):
    ok = bool(cond)
    print(("  ✓ " if ok else "  ✗ ÉCHEC : ") + txt)
    if not ok:
        ECHECS.append(txt)


# --- double de la DLL Player One ---------------------------------------------
class _FakePOA:
    """Fonctions SDK du chemin TEC, types fidèles au relevé réel :
    ctrl 3 float lecture seule, 16 int RO, 17 écrivable, 18 bool."""

    def __init__(self, avec_tec=True):
        self.configs = {}       # cid → (valeur posée, type)
        self.attrs = {0: (0, 10, 2_000_000_000, 1),   # expo µs, RW
                      7: (0, 0, 250, 1)}              # offset, RW
        self.lectures = {0: 10000, 7: 30}
        if avec_tec:
            self.attrs[3] = (1, -50.0, 30.0, 0)       # température, FLOAT, RO
            self.attrs[16] = (0, 0, 100, 0)           # puissance %, RO
            self.attrs[17] = (0, -50, 30, 1)          # consigne °C, RW
            self.attrs[18] = (2, 0, 1, 1)             # cooler, BOOL, RW
            self.lectures[3] = -12.5
            self.lectures[16] = 37
            self.lectures[17] = -10
            self.lectures[18] = 0

    def _remplir_attr(self, cid, a):
        t, mn, mx, wr = self.attrs[cid]
        a.configID = cid
        a.valueType = t
        a.isWritable = wr
        a.isReadable = 1
        a.isSupportAuto = 0
        if t == 1:
            a.minValue.floatValue = float(mn)
            a.maxValue.floatValue = float(mx)
        else:
            a.minValue.intValue = int(mn)
            a.maxValue.intValue = int(mx)
        a.defaultValue.intValue = 0
        a.szConfName = b"X"

    def POAGetConfigAttributesByConfigID(self, cam_id, cid, ptr):
        if cid not in self.attrs:
            return 1
        self._remplir_attr(cid, ptr._obj)     # byref() → CArgObject
        return 0

    def POAGetConfigsCount(self, cam_id, ptr):
        ptr._obj.value = len(self.attrs)
        return 0

    def POAGetConfigAttributes(self, cam_id, i, ptr):
        cids = sorted(self.attrs)
        if i >= len(cids):
            return 1
        self._remplir_attr(cids[i], ptr._obj)
        return 0

    def POAGetConfig(self, cam_id, cid, vptr, aptr):
        if cid not in self.attrs or cid not in self.lectures:
            return 1
        if self.attrs[cid][0] == 1:
            vptr._obj.floatValue = float(self.lectures[cid])
        else:
            vptr._obj.intValue = int(self.lectures[cid])
        aptr._obj.value = 0
        return 0

    def POASetConfig(self, cam_id, cid, u, auto):
        if cid not in self.attrs or not self.attrs[cid][3]:
            return 3                      # refus : contrôle non écrivable
        t = self.attrs[cid][0]
        val = u.floatValue if t == 1 else u.intValue
        self.configs[cid] = (val, t)
        self.lectures[cid] = val          # la valeur posée devient relisable
        return 0




# --- double de la DLL SVBONY --------------------------------------------------
class _FakeSVB:
    def __init__(self, avec_tec=True):
        self.etat = {}
        self.refus_set = set()            # cids refusés à la pose
        self.cids = {14, 15, 16, 17} if avec_tec else {0, 1}
        if avec_tec:
            self.etat[16] = -101          # -10.1 °C (unités 0,1)
            self.etat[17] = 45            # 45 %
            self.etat[15] = -100          # consigne -10.0 °C (unités 0,1)

    def SVBGetControlValue(self, cam_id, cid, vptr, aptr):
        if cid not in self.etat:
            return 1
        vptr._obj.value = int(self.etat[cid])   # byref() → CArgObject
        aptr._obj.value = 0
        return 0

    def SVBSetControlValue(self, cam_id, cid, val, auto):
        if cid in self.refus_set or cid not in self.cids:
            return 1                      # refus : contrôle absent du SDK
        self.etat[cid] = int(val)
        return 0


def _verdict(nom):
    print("\n=== " + nom + " : "
          + ("TOUT OK" if not ECHECS else f"{len(ECHECS)} ÉCHEC(S)") + " ===")
    for e in ECHECS:
        print("  - " + e)
    return not ECHECS


# --- Player One ---------------------------------------------------------------
print("=== TEC Player One (double SDK fidèle au relevé réel) ===")
fake = _FakePOA()
mpo._DLL = fake
cam = mpo.PlayerOneCamera(index=0)
cam.id = 0
cam._started = True

r = cam.lire_refroidissement()
verifie(r == (-12.5, 94, -10.0),
        f"lire → (-12.5 °C, PWM 94, -10.0 °C) [37 % → 94] ; reçu {r}")
verifie(cam._sonde is not None and cam._sonde.valide,
        "sonde TEC construite une fois (layout validé, cache rempli)")

cam.consigne_refroidissement(-15.0)
verifie(fake.configs.get(17) == (-15, 0),
        "consigne posée sur POA_TARGET_TEMP (int °C)")
verifie(fake.configs.get(18) == (1, 2),
        "POA_COOLER posé à ON après la consigne")

cam.arreter_refroidissement()
verifie(fake.configs.get(18) == (0, 2), "POA_COOLER = OFF")

fake.attrs[17] = (1, -50.0, 30.0, 1)      # variante : consigne FLOAT
cam._sonde = None                         # invalide le cache de sonde (les
                                          # types sont figés à la 1re énum.)
cam.consigne_refroidissement(-12.5)
verifie(fake.configs.get(17) == (-12.5, 1),
        "consigne FLOAT posée via floatValue si les attributs le disent")

fake.attrs[18] = (2, 0, 1, 0)             # SDK refuse Cooler
try:
    cam.consigne_refroidissement(-10.0)
    verifie(False, "consigne doit échouer si POA_COOLER est refusé")
except RuntimeError as e:
    verifie("12 V" in str(e), f"échec POA_COOLER → message clair : {e}")
fake.attrs[18] = (2, 0, 1, 1)

fake2 = _FakePOA(avec_tec=False)          # caméra SANS TEC
mpo._DLL = fake2
cam2 = mpo.PlayerOneCamera(index=0)
cam2.id = 0
cam2._started = True
verifie(cam2.lire_refroidissement() is None,
        "sans TEC : lire → None (boutons ❄ restent grisés — sondage app)")
try:
    cam2.consigne_refroidissement(-10.0)
    verifie(False, "sans TEC : consigne doit lever RuntimeError")
except RuntimeError:
    verifie(True, "sans TEC : consigne → RuntimeError (affiché par l'app)")

cam.id = None                              # caméra fermée
cam._started = False
verifie(cam.lire_refroidissement() is None, "fermée : lire → None")
cam.arreter_refroidissement()              # ne doit PAS lever
verifie(True, "fermée : arrêt silencieux (appelé à la déconnexion)")

# --- SVBONY -------------------------------------------------------------------
print("\n=== TEC SVBONY (double SDK fidèle au relevé réel) ===")
fsvb = _FakeSVB()
msvb._DLL = fsvb
svb = msvb.SVBonyCamera(index=0)
svb.id = 0
svb._started = True

r = svb.lire_refroidissement()
verifie(r == (-10.1, 115, -10.0),
        f"lire → (-10.1 °C, PWM 115, -10.0 °C) [45 % → 115] ; reçu {r}")

svb.consigne_refroidissement(-10.5)
verifie(fsvb.etat.get(14) == 1, "CoolerEnable = 1 avant la consigne")
verifie(fsvb.etat.get(15) == -105,
        "TargetTemp = -105 (×10 : unités SDK de 0,1 °C)")

svb.arreter_refroidissement()
verifie(fsvb.etat.get(14) == 0, "CoolerEnable = 0")

fsvb.refus_set.add(14)                     # SDK refuse CoolerEnable
try:
    svb.consigne_refroidissement(-10.0)
    verifie(False, "consigne doit échouer si CoolerEnable est refusé")
except RuntimeError as e:
    verifie("12 V" in str(e), f"échec CoolerEnable → message clair : {e}")
fsvb.refus_set.discard(14)

fsvb2 = _FakeSVB(avec_tec=False)
msvb._DLL = fsvb2
svb2 = msvb.SVBonyCamera(index=0)
svb2.id = 0
svb2._started = True
verifie(svb2.lire_refroidissement() is None,
        "sans TEC : lire → None (boutons ❄ restent grisés — sondage app)")
try:
    svb2.consigne_refroidissement(-10.0)
    verifie(False, "sans TEC : consigne doit lever RuntimeError")
except RuntimeError:
    verifie(True, "sans TEC : consigne → RuntimeError (affiché par l'app)")

svb.id = None
svb._started = False
verifie(svb.lire_refroidissement() is None, "fermée : lire → None")
svb.arreter_refroidissement()
verifie(True, "fermée : arrêt silencieux (appelé à la déconnexion)")

import sys
sys.exit(0 if _verdict("JALON 33") else 1)
