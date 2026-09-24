# -*- coding: utf-8 -*-
"""Test du câblage dynamique ÉTENDU aux marques non-QHY (jalon 32).

Fenêtre Tk réelle + objets Capacites construits avec les VALEURS DES
RELEVÉS RÉELS d'Alain (jalons 28/28b) :
  - Player One Uranus-C Pro : gain 0→750, offset 0→250, expo 10 µs→2000 s,
    TEC consigne -50→30 °C ;
  - SVBONY SV305C : gain 0→450, BlackLevel (« offset » du SDK SVB, ctrl 13)
    0→255, expo 36 µs→2000 s, pas de TEC.
Jalon 50/51 : s'y ajoute TOUPTEK, dont les capacités sont ici RELEVÉES par la
vraie sonde TouptekCamera.detecter_capacites() sur une fausse DLL qui se
comporte comme la G3M662M RÉELLE d'Alain (gain 100 %→15000 %, expo 100 µs
→1000 s ; noir : garde 0→31, refuse au-delà en E_INVALIDARG — la table
« 7936 pour 16 bits » DÉMENTIE au banc, borne MESURÉE par dichotomie ;
TEC : l'option TEC répond E_NOTIMPL, ce modèle n'en a pas) — le constat
fondateur : les curseurs de l'appli gardaient leurs bornes en dur faute de
sonde, et l'appli ADOpte désormais la valeur lue de l'offset (jalon 51).
Vérifie : plages résolues PAR RÔLE (les cid diffèrent selon la marque —
« 6 » = gain QHY mais balance des blancs B POA et Flip SVB), curseurs
reconstruits aux bornes réelles pour les TROIS marques sur la même fenêtre,
clamp des valeurs, consommation du résultat de connexion (échec propre,
annulation si la source change pendant l'ouverture), retour aux défauts à
la déconnexion. Jeter après usage."""
import sys

import tkinter as tk

sys.path.insert(0, r"c:\Astro\AstroLiveStack")
import avastack.cameras.touptek as mtt
import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)
from avastack.cameras.capacites import Capacites

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


print("[1] plage() : cid résolu PAR MARQUE (jamais un cid littéral)")
cap_poa = Capacites("Player One", modele="Uranus-C Pro", capteur="IMX585",
                    couleur=True, bits=16, max_l=3856, max_h=2180,
                    pixel_um=2.9)
cap_poa.expo_us = (10.0, 2_000_000_000.0)        # relevé réel : 10 µs → 2000 s
cap_poa.gain = (0.0, 750.0)                      # relevé réel (jalon 28)
cap_poa.offset = (0.0, 250.0)
cap_poa.tec = True
cap_poa.tec_consigne = (-50.0, 30.0)
cap_poa.temperature_lisible = True
cap_poa.extras = {
    "0": {"min": 10, "max": 2_000_000_000, "step": 1, "val": 10000,
          "nom": "Exposure (µs)"},
    "1": {"min": 0, "max": 750, "step": 1, "val": 210, "nom": "Gain"},
    "7": {"min": 0, "max": 250, "step": 1, "val": 8, "nom": "Offset"},
}
verifie(cap_poa.plage("gain") == (0.0, 750.0, 1.0),
        "POA : plage('gain') → ctrl 1 (0 → 750, step 1)")
verifie(cap_poa.plage("offset") == (0.0, 250.0, 1.0),
        "POA : plage('offset') → ctrl 7 (0 → 250)")
verifie(cap_poa.plage("tec_consigne") == (-50.0, 30.0, 1.0),
        "POA : plage('tec_consigne') → repli plages normalisées")

cap_svb = Capacites("SVBONY", modele="SV305C", couleur=False, bits=14,
                    max_l=1920, max_h=1080, pixel_um=2.9)
cap_svb.expo_us = (36.0, 2_000_000_000.0)        # relevé réel : 36 µs → 2000 s
cap_svb.gain = (0.0, 450.0)                      # relevé réel (jalon 28b)
cap_svb.offset = (0.0, 255.0)                    # BlackLevel (ctrl 13)
cap_svb.extras = {
    "0": {"min": 0, "max": 450, "step": 1, "val": 60, "nom": "Gain"},
    "1": {"min": 36, "max": 2_000_000_000, "step": 1, "val": 10000,
          "nom": "Exposure"},
    "13": {"min": 0, "max": 255, "step": 1, "val": 8, "nom": "BlackLevel"},
}
verifie(cap_svb.plage("gain") == (0.0, 450.0, 1.0),
        "SVB : plage('gain') → ctrl 0 (0 → 450)")
verifie(cap_svb.plage("offset") == (0.0, 255.0, 1.0),
        "SVB : plage('offset') → ctrl 13 BlackLevel (0 → 255)")
cap_repli = Capacites("SVBONY", modele="?")      # sonde muette : pas d'extras
cap_repli.gain = (0.0, 450.0)
verifie(cap_repli.plage("gain") == (0.0, 450.0, 1.0),
        "repli sans extras : plage('gain') via les plages normalisées")
cap_bidon = Capacites("QHY", modele="?")
cap_bidon.gain = (500.0, 100.0)                  # incohérente
verifie(cap_bidon.plage("gain") is None,
        "plage incohérente (min ≥ max) → None (jamais de curseur bidon)")
cap_inc = Capacites("MarqueInconnue")
verifie(cap_inc.plage("gain") is None,
        "marque hors table, aucune plage → None")
cap_qhy = Capacites("QHY", modele="QHYminiCam8M")
cap_qhy.gain = (0.0, 230.0)
cap_qhy.offset = (0.0, 255.0)
cap_qhy.extras = {"6": {"min": 0, "max": 230, "step": 1, "val": 30},
                  "7": {"min": 0, "max": 255, "step": 1, "val": 30}}
verifie(cap_qhy.plage("gain") == (0.0, 230.0, 1.0)
        and cap_qhy.plage("offset") == (0.0, 255.0, 1.0),
        "QHY : rôles résolus comme au jalon 31 (non-régression)")


# Touptek (jalon 50) : capacités RELEVÉES par la VRAIE sonde de l'appli sur
# une fausse DLL qui répond ce que la G3M662M d'Alain a mesuré au banc.
class _FauxDLLToup:
    """Faux toupcam.dll : uniquement les lectures de capacités du jalon 50."""

    def Toupcam_get_ExpTimeRange(self, h, pmin, pmax, pdef):
        pmin._obj.value, pmax._obj.value = 100, 1_000_000_000
        pdef._obj.value = 10_000
        return 0

    def Toupcam_get_ExpoAGainRange(self, h, pmin, pmax, pdef):
        pmin._obj.value, pmax._obj.value, pdef._obj.value = 100, 15_000, 100
        return 0

    # noir (jalon 51) : la G3M662M réelle GARDE 0 → 31 et refuse au-delà
    # (E_INVALIDARG) ; TEC : l'option TEC répond E_NOTIMPL (ni TEC ni sonde).
    E_NOTIMPL = 0x80004001 - (1 << 32)
    E_INVALIDARG = 0x80070057 - (1 << 32)

    def __init__(self):
        self.noir = 1                       # niveau de noir COURANT
        self.noir_max = 31                  # plage réelle constatée au banc

    def Toupcam_put_Option(self, h, opt, val):
        if opt == mtt.TOUPCAM_OPTION_BLACKLEVEL:
            if val <= self.noir_max:        # la caméra garde ce qu'elle accepte
                self.noir = val
                return 0
            return self.E_INVALIDARG
        return 0

    def Toupcam_get_Option(self, h, opt, p):
        if opt == mtt.TOUPCAM_OPTION_BLACKLEVEL:
            p._obj.value = self.noir        # relu = ce que la caméra a gardé
            return 0
        if opt in (mtt.TOUPCAM_OPTION_TEC, mtt.TOUPCAM_OPTION_TECTARGET,
                   mtt.TOUPCAM_OPTION_TECTARGET_RANGE):
            return self.E_NOTIMPL
        p._obj.value = 0
        return 0

    def Toupcam_get_MaxBitDepth(self, h):
        return 16                           # le HRESULT EST la profondeur

    def Toupcam_get_MonoMode(self, h):
        return mtt.S_OK                     # mono

    def Toupcam_get_PixelSize(self, h, idx, px, py):
        px._obj.value, py._obj.value = 2.90, 2.90
        return 0


mtt._DLL = _FauxDLLToup()
cam_toup = mtt.TouptekCamera(0)
cam_toup.name = "G3M662M"
cam_toup._handle = 0x01
cam_toup._w, cam_toup._h = 1920, 1080
cap_toup = cam_toup.detecter_capacites()
mtt._DLL = None
verifie(cap_toup.expo_us == (100, 1_000_000_000),
        "Touptek : plage d'expo réelle relevée (100 µs → 1000 s)")
verifie(cap_toup.plage("gain") == (100.0, 15000.0, 1.0),
        "Touptek : plage('gain') en % — unités du SDK (100 % = 1×)")
verifie(cap_toup.plage("offset") == (0.0, 31.0, 1.0),
        "Touptek : plage('offset') MESURÉE 0 → 31 (jalon 51 : la table "
        "« 7936 pour 16 bits » est démentie par la caméra)")
verifie(cap_toup.actuels.get("offset") == 1.0,
        "Touptek : valeur COURANTE du noir lue (l'appli l'adopte, jalon 51)")
verifie(cap_toup.tec is False and cap_toup.plage("tec_consigne") is None,
        "Touptek : pas de TEC annoncé (l'option TEC répond E_NOTIMPL — "
        "G3M662M, constat jalon 51)")

print("[2] UI Player One : curseurs aux bornes réelles (relevé)")
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
app._adapter_ui_capacites(cap_poa)
root.update_idletasks()
g = app.sl_gain
o = app.sl_offset
verifie(abs(g.cget("from") - 0.0) < 1e-9 and abs(g.cget("to") - 750.0) < 1e-9,
        "curseur gain reconstruit 0 → 750")
verifie("750" in g._lbl_txt, "étiquette gain affiche les bornes réelles")
verifie(abs(o.cget("to") - 250.0) < 1e-9, "curseur offset 0 → 250")
verifie(app._EXPO_DYN == (0.01, 2_000_000.0),
        "bornes expo dynamiques (10 µs → 2000 s, en ms)")
verifie(app.tec_plage == (-50.0, 30.0), "plage TEC réelle (-50 → 30)")
verifie(not app._roue_ok, "pas de roue détectée (la POA n'en a pas)")
verifie(0.0 <= app.var_gain.get() <= 750.0, "valeur gain clampée")

print("[2b] UI Touptek : bornes réelles du constat d'Alain (jalon 50)")
app.var_gain.set(30.0)           # défaut de l'appli : HORS plage Touptek
app.var_offset.set(10.0)
app._adapter_ui_capacites(cap_toup)
root.update_idletasks()
g = app.sl_gain
o = app.sl_offset
verifie(abs(g.cget("from") - 100.0) < 1e-9
        and abs(g.cget("to") - 15000.0) < 1e-9,
        "curseur gain reconstruit 100 → 15000 (% du SDK)")
verifie(abs(o.cget("from") - 0.0) < 1e-9 and abs(o.cget("to") - 31.0) < 1e-9,
        "curseur offset (niveau de noir) reconstruit 0 → 31")
verifie(app.var_offset.get() == 1.0,
        "offset 10 (défaut UI) REMPLACÉ par la valeur LUE sur la caméra (1)")
verifie(app.var_gain.get() == 100.0,
        "gain 30 (défaut) clampé à la borne réelle 100 % = 1×")
verifie(app._EXPO_DYN == (0.1, 1_000_000.0),
        "bornes expo dynamiques (100 µs → 1000 s, en ms)")
verifie(cap_toup.tec is False and cap_toup.roue_slots is None
        and not app._roue_ok,
        "ni TEC ni roue annoncés (pas de bouton ❄ / combobox factice)")

print("[3] UI SVBONY : reconstruction sur la même fenêtre")
app.var_gain.set(900.0)          # hors plage SVB → sera clampé à 450
app._adapter_ui_capacites(cap_svb)
root.update_idletasks()
g = app.sl_gain
o = app.sl_offset
verifie(abs(g.cget("to") - 450.0) < 1e-9, "curseur gain reconstruit 0 → 450")
verifie(abs(o.cget("to") - 255.0) < 1e-9,
        "curseur offset (BlackLevel) 0 → 255")
verifie(abs(app.var_gain.get() - 450.0) < 1e-9,
        "gain 900 clampé à la borne réelle 450")
verifie(app._EXPO_DYN == (0.036, 2_000_000.0),
        "bornes expo dynamiques (36 µs → 2000 s, en ms)")
verifie(app.tec_plage == (-50.0, 30.0),
        "tec_plage conservée tant que pas de déconnexion")

print("[4] Consommation du résultat de connexion (thread → _tick)")
app._connexion_sdk_result = ("Player One (SDK)", None,
                             "Aucune caméra Player One détectée")
app._tick()
verifie("connexion impossible" in app.lbl_detect.cget("text")
        and app._connexion_busy is False,
        "échec propre : message clair + rescan possible")


class CamFactice:
    """Remplace une caméra pour vérifier l'annulation (close appelé)."""

    def __init__(self):
        self.fermee = False

    def close(self):
        self.fermee = True


app.var_source.set("Simulée (démo)")             # la source a changé
f = CamFactice()
app._connexion_sdk_result = ("SVBONY (SDK)", f, None)
app._tick()
root.update_idletasks()
verifie(f.fermee and app.camera is None
        and "annulée" in app.lbl_detect.cget("text"),
        "source changée pendant l'ouverture → connexion annulée + close")

print("[5] Déconnexion → retour aux défauts")
app.var_source.set("Player One (SDK)")
app._deconnecter_camera()
root.update_idletasks()
verifie(app.capacites is None and app._EXPO_DYN is None
        and app.tec_plage is None, "capacités vidées")
verifie(app.lbl_tec_lib.cget("text") == "Consigne °C :",
        "label TEC revenu au défaut")

root.destroy()
print("BILAN :", "TOUTES LES VERIFICATIONS PASSENT" if ok else "ÉCHECS")
sys.exit(0 if ok else 1)
