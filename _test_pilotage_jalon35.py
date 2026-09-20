# -*- coding: utf-8 -*-
"""Test du CÂBLAGE APP du pilotage TEC (jalon 35, correctif point 3 de
l'item 2d) — sans matériel.

Retour réel d'Alain (20/09/2026, setup 2, POA Uranus-C Pro) : les contrôles
TEC s'affichaient (bornes de consigne détectées) mais les boutons ❄
restaient GRISÉS. Cause : `cam_pilotee` (la caméra que le thread de travail
sonde et pilote) était resté QHY-only depuis le jalon 25 — le sondage
`lire_refroidissement()` n'était JAMAIS lancé pour Player One / SVBONY,
donc les implémentations du jalon 33 (saines, testées) n'étaient jamais
appelées. Ce test vérifie le câblage COMPLET côté app, avec des DOUBLES de
DLL fidèles aux relevés réels des bancs (repris du test jalon 33) :
  _installer_camera_connectee → cam_pilotee → _sonder_controles → _tec_ok
  → _tick (boutons ❄ activés + consigne par défaut posée)
  → _appliquer_demande_tec (consigne/arrêt exécutés sur le double SDK).

Fenêtre Tk réelle (modèle des tests jalon 31/32)."""

import sys

import tkinter as tk

sys.path.insert(0, r"c:\Astro\AstroLiveStack")
import avastack.ui.app as ui
from avastack.cameras import playerone as mpo
from avastack.cameras import svbony as msvb
from avastack.cameras import SimulatedCamera

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ECHECS = []


def verifie(cond, txt):
    ok = bool(cond)
    print(("  ✓ " if ok else "  ✗ ÉCHEC : ") + txt)
    if not ok:
        ECHECS.append(txt)


# --- doubles de DLL (repris du test jalon 33, fidèles aux relevés réels) -----
class _FakePOA:
    """Fonctions SDK du chemin TEC POA : ctrl 3 float RO, 16 int RO,
    17 écrivable, 18 bool écrivable (+ expo 0 / offset 7 pour valider
    le layout de la sonde)."""

    def __init__(self, avec_tec=True):
        self.configs = {}
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
        self._remplir_attr(cid, ptr._obj)
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
            return 3
        t = self.attrs[cid][0]
        val = u.floatValue if t == 1 else u.intValue
        self.configs[cid] = (val, t)
        self.lectures[cid] = val
        return 0


class _FakeSVB:
    """Fonctions SDK du chemin TEC SVBONY : contrôles 14 (CoolerEnable),
    15 (TargetTemp ×10), 16 (température ×10), 17 (puissance %)."""

    def __init__(self, avec_tec=True):
        self.etat = {}
        self.refus_set = set()
        self.cids = {14, 15, 16, 17} if avec_tec else {0, 1}
        if avec_tec:
            self.etat[16] = -101          # -10,1 °C (unités 0,1)
            self.etat[17] = 45            # 45 %
            self.etat[15] = -100          # consigne -10,0 °C

    def SVBGetControlValue(self, cam_id, cid, vptr, aptr):
        if cid not in self.etat:
            return 1
        vptr._obj.value = int(self.etat[cid])
        aptr._obj.value = 0
        return 0

    def SVBSetControlValue(self, cam_id, cid, val, auto):
        if cid in self.refus_set or cid not in self.cids:
            return 1
        self.etat[cid] = int(val)
        return 0


class _FauxThread:
    """Empêche _installer_camera_connectee de démarrer le VRAI worker
    (le test pilote sondage/_tick/demandes à la main, pas en parallèle)."""

    def is_alive(self):
        return True


# --- 1) Player One AVEC TEC : câblage complet des boutons ❄ --------------------
print("[1] Player One (POA) : sondage → boutons ❄ activés → consigne")
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
app.thread = _FauxThread()        # pas de worker réel : chemin entièrement
                                  # contrôlé (sondage → _tick → demande)

fake = _FakePOA()
mpo._DLL = fake
cam = mpo.PlayerOneCamera(index=0)
cam.id = 0
cam._started = True
app._installer_camera_connectee(cam, "Player One (SDK)")
verifie(app.cam_pilotee is cam,
        "cam_pilotee pointe la caméra Player One (correctif jalon 35)")
app._sonder_controles()           # ce que le worker fait une fois, à la connexion
verifie(app._tec_ok, "sondage lire_refroidissement() → TEC détecté")
app._tick()
root.update_idletasks()
verifie(str(app.btn_tec_on["state"]) == "normal"
        and str(app.btn_tec_off["state"]) == "normal",
        "boutons ❄ Réguler / ⏹ Arrêter ACTIVÉS par _tick")
verifie(app._tec_demande == ("consigne", -10.0),
        "consigne par défaut (-10 °C) posée automatiquement")
app._appliquer_demande_tec()
verifie(fake.configs.get(17) == (-10, 0),
        "consigne exécutée : POA_TARGET_TEMP = -10 (int °C)")
verifie(fake.configs.get(18) == (1, 2), "POA_COOLER = ON")
app._tec_demande = ("stop", None)
app._appliquer_demande_tec()
verifie(fake.configs.get(18) == (0, 2), "⏹ Arrêter → POA_COOLER = OFF")

# --- 2) Player One SANS TEC : boutons ❄ restent grisés --------------------------
print("[2] Player One sans TEC : boutons ❄ restent grisés")
app2 = ui.App(tk.Toplevel(root))
root.update_idletasks()
app2.thread = _FauxThread()
mpo._DLL = _FakePOA(avec_tec=False)
cam2 = mpo.PlayerOneCamera(index=0)
cam2.id = 0
cam2._started = True
app2._installer_camera_connectee(cam2, "Player One (SDK)")
app2._sonder_controles()
verifie(not app2._tec_ok, "sans TEC : sondage → None → pas d'activation")
app2._tick()
root.update_idletasks()
verifie(str(app2.btn_tec_on["state"]) == "disabled"
        and str(app2.btn_tec_off["state"]) == "disabled",
        "boutons ❄ toujours GRISÉS (caméra sans TEC — comportement attendu)")
app2._deconnecter_camera()

# --- 3) SVBONY : même câblage (le point 4 « connexion auto » est un autre
#     bug, mais le TEC doit marcher dès que la connexion aboutira) ---------------
print("[3] SVBONY (SV305C) : sondage → boutons ❄ activés → consigne")
app3 = ui.App(tk.Toplevel(root))
root.update_idletasks()
app3.thread = _FauxThread()
fsvb = _FakeSVB()
msvb._DLL = fsvb
svb = msvb.SVBonyCamera(index=0)
svb.id = 0
svb._started = True
app3._installer_camera_connectee(svb, "SVBONY (SDK)")
verifie(app3.cam_pilotee is svb,
        "cam_pilotee pointe la caméra SVBONY (correctif jalon 35)")
app3._sonder_controles()
verifie(app3._tec_ok, "sondage lire_refroidissement() → TEC détecté")
app3._tick()
root.update_idletasks()
verifie(str(app3.btn_tec_on["state"]) == "normal"
        and str(app3.btn_tec_off["state"]) == "normal",
        "boutons ❄ ACTIVÉS par _tick")
app3._appliquer_demande_tec()
verifie(fsvb.etat.get(14) == 1, "CoolerEnable = 1 avant la consigne")
verifie(fsvb.etat.get(15) == -100, "TargetTemp = -100 (×10 : unités 0,1 °C)")

# --- 4) Sources non-SDK : cam_pilotee reste None (aucun pilotage inutile) ------
print("[4] Sources non-SDK : cam_pilotee = None")
app4 = ui.App(tk.Toplevel(root))
root.update_idletasks()
app4.thread = _FauxThread()
sim = SimulatedCamera()
app4._installer_camera_connectee(sim, "Simulée (démo)")
verifie(app4.cam_pilotee is None,
        "ciel simulé : pas de caméra pilotée (no-op CameraBase inutile ici)")
app4._deconnecter_camera()

root.destroy()
print("\n=== JALON 35 : "
      + ("TOUT OK" if not ECHECS else f"{len(ECHECS)} ÉCHEC(S)") + " ===")
for e in ECHECS:
    print("  - " + e)
sys.exit(0 if not ECHECS else 1)
