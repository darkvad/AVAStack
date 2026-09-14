# -*- coding: utf-8 -*-
"""Test headless du mode VeraLux du DisplayProcessor (jalon 2) — sans Tk."""
import sys
import time

import numpy as np

# Sortie redirigée (fichier/pipe) → cp1252 ne sait pas encoder →/— des prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, r"c:\Astro\AstroLiveStack")

from avastack.processing.display import DisplayProcessor
from avastack.processing import veralux as vl

rng = np.random.default_rng(0)
y, x = np.mgrid[0:400, 0:600]
img = np.clip(rng.normal(0.008, 0.004, (400, 600)).astype(np.float32), 0, None)
img += (0.8 * np.exp(-((y - 200) ** 2 + (x - 300) ** 2) / 8.0)).astype(np.float32)
img = np.clip(img, 0.0, 1.0)


def attendre(d, max_s=5.0):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < max_s:
        if d._vl_result is not None and not d._vl_pending:
            return True
        time.sleep(0.05)
    return False


ok = True


def verifie(cond, msg):
    global ok
    print(("  OK  " if cond else "  ECHEC ") + msg)
    ok = bool(ok and cond)


d = DisplayProcessor()
d.vl_mode_res = vl.MODE_LOG_D   # jalon 2 : logD forcé seul — le jalon 3 a fait
                                # de target_bg le défaut (testé dans
                                # _test_veralux_jalon3.py)

# --- 1. mode STF inchangé -----------------------------------------------------
print("[1] Mode STF (défaut)")
d.gamma, d.saturation = 1.0, 1.0
out = d.process(img)
verifie(out.dtype == np.uint8 and out.shape == img.shape, "sortie uint8")
verifie(d.stretch == "stf", "stretch par défaut = stf")

# --- 2. passage VeraLux : fallback STF puis résultat du thread -----------------
print("[2] Mode VeraLux (logD forcé 2.0)")
d.black, d.white = 0.1, 0.9                     # ne doivent JAMAIS bouger
d.stretch = "veralux"
d.vl_log_d = 2.0
out_attente = d.process(img)                    # 1er appel : fallback + job soumis
verifie(d._vl_pending, "calcul soumis au thread solveur")
verifie(attendre(d), "calcul terminé dans le thread")
verifie(d.vl_error == "", f"pas d'erreur ({d.vl_error!r})")
out_vl = d.process(img)                         # 2e appel : résultat en cache
med = float(np.median(out_vl))
verifie(40.0 <= med <= 70.0,
        f"VeraLux cale le fond sur target_bg 0.20 (médiane {med:.1f} ≈ 51)")
verifie(med > 10.0 * float(np.median(img)) * 255.0,
        "fond largement remonté par rapport à l'entrée linéaire")
verifie(d.black == 0.1 and d.white == 0.9,
        "black/white JAMAIS modifiés par VeraLux")
verifie(d.vl_diagnostics is not None and "log_d_resolu" in d.vl_diagnostics,
        "diagnostics disponibles pour l'UI")

# --- 3. même image + mêmes réglages → cache (pas de resoumission) --------------
print("[3] Cache")
d._vl_pending = False
d.process(img)
verifie(d._vl_job is None, "rien resoumis (cache utilisé)")

# --- 4. changement de logD → recalcul ------------------------------------------
print("[4] logD 4.0 → recalcul")
d.vl_log_d = 4.0
d.process(img)
verifie(attendre(d), "recalcul terminé")
out_vl4 = d.process(img)
verifie(d.vl_log_d_resolu == 4.0, "diagnostic logD = 4.0")
verifie(not np.array_equal(out_vl4, out_vl),
        "logD plus fort → image différente (étoiles plus gonflées, "
        "fond toujours calé par adaptive_output_scaling)")

# --- 5. gamma/saturation communs appliqués après -------------------------------
print("[5] Gamma commun")
d.gamma = 2.0
d.process(img)
verifie(attendre(d) or True, "recalcul éventuel")
out_g = d.process(img)
d.gamma = 1.0
d.process(img)
if d._vl_pending:
    attendre(d)
out_ng = d.process(img)
verifie(not np.array_equal(out_g, out_ng), "gamma change le rendu en VeraLux")

# --- 6. RGB ---------------------------------------------------------------------
print("[6] RGB")
rgb = np.stack([img, np.roll(img, 5, axis=1) * 0.95, img * 0.9], axis=2)
d.vl_log_d = 2.5
d.process(rgb)
verifie(attendre(d), "calcul RGB terminé")
out_rgb = d.process(rgb)
verifie(out_rgb.shape == rgb.shape, "sortie RGB même forme")

# --- 7. retour STF propre -------------------------------------------------------
print("[7] Retour STF")
d.stretch = "stf"
out_stf = d.process(img)
verifie(out_stf.dtype == np.uint8, "STF de nouveau opérationnel")

print("\n===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)