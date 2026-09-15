# -*- coding: utf-8 -*-
"""Test headless du jalon 5 — sauvegarde « 💾 Enregistrer tel que vu ».

Vérifie que DisplayProcessor.rendu_pleine_resolution() :
  - reproduit le rendu STF affiché (identique à process() au 1er rendu) ;
  - est PURE : aucune mutation d'état (stats EMA, black/white/gamma) ;
  - gère le mode manuel, VeraLux logD forcé, VeraLux fond cible (dernier
    logD résolu, puis re-résolution si aucun logD connu) et le repli
    STF quand le moteur tiers est absent ;
  - applique gamma/saturation comme l'affichage (formule commune) ;
  - respecte les réglages capturés (dict) plutôt que l'état courant ;
  - fonctionne en mono ET RGB (piège des axes de canaux).

Exécution : python _test_save_asseen_jalon5.py
"""
import sys

import numpy as np

import avastack.processing.display as disp_mod
from avastack.processing.display import DisplayProcessor
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def image_synthetique(h=400, w=600, rgb=False, seed=0):
    """Ciel factice : fond + nébulosité + étoiles + bruit (linéaire [0..1])."""
    rng = np.random.default_rng(seed)
    shape = (h, w, 3) if rgb else (h, w)
    img = rng.normal(0.02, 0.006, shape)
    yy, xx = np.mgrid[0:h, 0:w]
    prof = 0.05 * np.exp(-((yy - h / 3.0) ** 2 + (xx - w / 2.0) ** 2)
                         / (h * w / 30.0))               # nébulosité
    for _ in range(40):                                   # étoiles
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        prof = prof + 0.6 * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 6.0)
    img = img + (prof[..., None] if rgb else prof)
    return np.clip(img.astype(np.float32), 0.0, 1.0)


mono = image_synthetique()
rgb = image_synthetique(rgb=True, seed=1)

print("[1] STF pur = rendu affiché (process au 1er rendu)")
d = DisplayProcessor()
apercu = d.process(mono)               # 1er rendu : stats EMA = stats pures
rendu = d.rendu_pleine_resolution(mono)
ecart = float(np.max(np.abs((rendu * 255).astype(np.uint8) - apercu)))
verifie(ecart == 0, f"rendu pleine résolution == affichage STF (écart {ecart})")
verifie(rendu.shape == mono.shape and rendu.dtype == np.float32,
        "mono : mêmes dimensions, float [0..1]")
verifie(float(rendu.min()) >= 0.0 and float(rendu.max()) <= 1.0,
        "sortie bornée à [0, 1]")

print("[2] Pureté : aucun état partagé modifié")
d_stats = d._stats                    # initialisées par process() ci-dessus
verifie(d_stats is not None
        and d.rendu_pleine_resolution(mono) is not None
        and d._stats == d_stats,
        "stats EMA inchangées par rendu_pleine_resolution (pas de pompage)")
d2 = DisplayProcessor()
d2.process(mono)                       # 1er rendu → _stats initialisées
avant = (d2.black, d2.white, d2.gamma, d2.saturation, d2._stats)
d2.rendu_pleine_resolution(rgb, {"stretch": "stf", "auto": True,
                                 "sigma_k": 3.5, "target": 0.30,
                                 "gamma": 2.0, "saturation": 2.0})
d2.rendu_pleine_resolution(mono)
apres = (d2.black, d2.white, d2.gamma, d2.saturation, d2._stats)
verifie(avant == apres, "black/white/gamma/saturation/stats intacts")

print("[3] Mode manuel (réglages capturés ≠ état courant)")
d3 = DisplayProcessor()
d3.auto = False                        # état courant : manuel
reglages = {"stretch": "stf", "auto": False, "black": 0.05, "white": 0.5,
            "gamma": 1.0, "saturation": 1.0}
r3 = d3.rendu_pleine_resolution(mono, reglages)
attendu = np.clip((mono - 0.05) / (0.5 - 0.05), 0.0, 1.0)
verifie(float(np.max(np.abs(r3 - attendu))) < 1e-6,
        "rendu = (img − black) / (white − black) des réglages capturés")

print("[4] VeraLux logD forcé = appel direct du moteur")
if vl.moteur_disponible():
    d4 = DisplayProcessor()
    d4.stretch = "veralux"
    d4.vl_mode_res = vl.MODE_LOG_D
    d4.vl_log_d = 2.5
    r4 = d4.rendu_pleine_resolution(mono)
    ref4, ld4, _ = vl.etirer(np.clip(mono, 0.0, 1.0), mode=vl.MODE_LOG_D,
                             log_d=2.5, profil=d4.vl_profil)
    verifie(float(np.max(np.abs(r4 - ref4))) < 1e-6,
            "rendu VeraLux (logD forcé) == etirer direct")

    print("[5] VeraLux fond cible = DERNIER logD résolu (pas de re-résolution)")
    d5 = DisplayProcessor()
    d5.stretch = "veralux"
    d5.vl_mode_res = vl.MODE_TARGET_BG
    d5.vl_log_d_resolu = 1.8           # capté côté UI lors de la sauvegarde
    r5 = d5.rendu_pleine_resolution(mono)
    ref5, ld5, _ = vl.etirer(np.clip(mono, 0.0, 1.0), mode=vl.MODE_LOG_D,
                             log_d=1.8, profil=d5.vl_profil)
    verifie(ld5 == 1.8 and float(np.max(np.abs(r5 - ref5))) < 1e-6,
            "rendu avec le logD résolu 1.8 (déterministe, sans résolution)")

    print("[6] VeraLux fond cible sans logD connu → re-résolution target_bg")
    d6 = DisplayProcessor()
    d6.stretch = "veralux"
    d6.vl_mode_res = vl.MODE_TARGET_BG
    d6.vl_target_bg = 0.20
    r6 = d6.rendu_pleine_resolution(mono)
    ref6, _, _ = vl.etirer(np.clip(mono, 0.0, 1.0), mode=vl.MODE_TARGET_BG,
                           target_bg=0.20, profil=d6.vl_profil)
    verifie(float(np.max(np.abs(r6 - ref6))) < 1e-6,
            "rendu == résolution target_bg du moteur")

    print("[7] VeraLux RGB : pas de mélange d'axes de canaux")
    d7 = DisplayProcessor()
    d7.stretch = "veralux"
    d7.vl_mode_res = vl.MODE_LOG_D
    d7.vl_log_d = 2.0
    r7 = d7.rendu_pleine_resolution(rgb)
    ref7, _, _ = vl.etirer(np.clip(rgb, 0.0, 1.0), mode=vl.MODE_LOG_D,
                           log_d=2.0, profil=d7.vl_profil)
    verifie(r7.shape == rgb.shape
            and float(np.max(np.abs(r7 - ref7))) < 1e-6,
            "RGB : mêmes dimensions, rendu == etirer direct")
else:
    print("  (moteur tiers absent — [4] à [7] ignorés)")

print("[8] Gamma / saturation communs = formule de l'affichage")
d8 = DisplayProcessor()
base = d8.rendu_pleine_resolution(rgb)          # gamma/saturation à 1.0
d9 = DisplayProcessor()
d9.gamma, d9.saturation = 1.4, 1.3
r9 = d9.rendu_pleine_resolution(rgb)
attendu9 = DisplayProcessor._gamma_saturation(base, True, 1.4, 1.3)
verifie(float(np.max(np.abs(r9 - attendu9))) < 1e-6,
        "gamma 1.4 + saturation 1.3 appliqués comme dans process()")

print("[9] Repli STF quand le moteur tiers est absent")


class _MoteurAbsent:
    """Stub du module veralux : moteur indisponible (comme exe manquant)."""
    MODE_TARGET_BG = vl.MODE_TARGET_BG
    MODE_LOG_D = vl.MODE_LOG_D
    TARGET_BG_PAR_DEFAUT = vl.TARGET_BG_PAR_DEFAUT
    LOG_D_PAR_DEFAUT = vl.LOG_D_PAR_DEFAUT
    PROFIL_PAR_DEFAUT = vl.PROFIL_PAR_DEFAUT

    @staticmethod
    def moteur_disponible():
        return False


original = disp_mod._veralux
disp_mod._veralux = _MoteurAbsent
try:
    d10 = DisplayProcessor()
    r10 = d10.rendu_pleine_resolution(mono, {"stretch": "veralux"})
finally:
    disp_mod._veralux = original
d10b = DisplayProcessor()
ref10 = d10b.rendu_pleine_resolution(mono, {"stretch": "stf", "auto": True})
verifie(float(np.max(np.abs(r10 - ref10))) < 1e-6,
        "stretch veralux + moteur absent → rendu STF (comme l'affichage)")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
