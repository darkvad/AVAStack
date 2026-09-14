# -*- coding: utf-8 -*-
"""Test headless de l'adaptateur VeraLux (jalon 1) — SANS interface.

Vérifie : mono, RGB, forme de sortie, [0,1], entrée non modifiée,
clip des valeurs > 1.1, déterminisme en logD forcé, et chronomètre le
calcul à taille « aperçu » (info pour les jalons suivants).
"""
import sys
import time

import numpy as np

sys.path.insert(0, r"c:\Astro\AstroLiveStack")

from avastack.processing import veralux as vl

rng = np.random.default_rng(42)


def image_synthetique(h=800, w=1200, seed=0):
    """Ciel simulé : fond bruité + gradient + étoiles gaussiennes."""
    r = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    fond = 0.004 + 0.003 * (x / w) + r.normal(0, 0.0015, (h, w)).astype(np.float32)
    img = np.clip(fond, 0, None).astype(np.float32)
    for _ in range(120):
        cy, cx = r.integers(10, h - 10), r.integers(10, w - 10)
        amp = r.uniform(0.2, 1.0)
        s = r.uniform(1.0, 2.5)
        carte = amp * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * s * s))
        img += carte.astype(np.float32)
    return np.clip(img, 0.0, 1.0)


def verifie(cond, msg):
    print(("  OK  " if cond else "  ECHEC ") + msg)
    return bool(cond)


ok = True

print("Moteur disponible :", vl.moteur_disponible())
print("Profils :", len(vl.profils_disponibles()))
ok &= verifie(vl.moteur_disponible(), "moteur tiers importé")
ok &= verifie(vl.PROFIL_PAR_DEFAUT in vl.profils_disponibles(),
              "profil Rec.709 présent")

# --- 1. mono, mode target_bg -------------------------------------------------
print("\n[1] Mono (800x1200), mode target_bg")
mono = image_synthetique()
copie = mono.copy()
t0 = time.perf_counter()
out, log_d, diag = vl.etirer(mono, mode=vl.MODE_TARGET_BG)
dt = time.perf_counter() - t0
print(f"  durée = {dt*1000:.0f} ms, log_d = {log_d:.3f}")
ok &= verifie(out.shape == mono.shape, f"forme identique {out.shape}")
ok &= verifie(out.dtype == np.float32, "sortie float32")
ok &= verifie(out.min() >= 0.0 and out.max() <= 1.0, "sortie dans [0, 1]")
ok &= verifie(np.array_equal(mono, copie), "entrée NON modifiée")
ok &= verifie(float(np.median(out)) > float(np.median(mono)),
              "image éclaircie (fond remonté)")
ok &= verifie("log_d_resolu" in diag, "diagnostics présents")
print("  médiane avant/après :",
      float(np.median(mono)), "->", float(np.median(out)))

# --- 2. RGB, mode target_bg --------------------------------------------------
print("\n[2] RGB (800x1200), mode target_bg")
rgb = np.stack([mono, np.roll(mono, 7, axis=1) * 0.95,
                np.roll(mono, 13, axis=0) * 0.9], axis=2).astype(np.float32)
copie = rgb.copy()
t0 = time.perf_counter()
outr, log_dr, diagr = vl.etirer(rgb, mode=vl.MODE_TARGET_BG)
dt = time.perf_counter() - t0
print(f"  durée = {dt*1000:.0f} ms, log_d = {log_dr:.3f}")
ok &= verifie(outr.shape == rgb.shape, f"forme identique {outr.shape}")
ok &= verifie(outr.min() >= 0.0 and outr.max() <= 1.0, "sortie dans [0, 1]")
ok &= verifie(np.array_equal(rgb, copie), "entrée NON modifiée")
ok &= verifie(np.median(outr) > np.median(rgb), "image éclaircie")
# la teinte générale doit rester (règle VeraLux : préserve les ratios)
ok &= verifie(outr[..., 0].mean() > outr[..., 2].mean(),
              "rapport R/B préservé (R plus fort que B comme en entrée)")

# --- 3. logD forcé : déterministe et identique mono via les deux chemins ------
print("\n[3] Mono, logD forcé = 2.5 (déterminisme)")
out1, ld1, _ = vl.etirer(mono, mode=vl.MODE_LOG_D, log_d=2.5)
out2, ld2, _ = vl.etirer(mono, mode=vl.MODE_LOG_D, log_d=2.5)
ok &= verifie(ld1 == 2.5 and ld2 == 2.5, "log_d rendu = logD forcé")
ok &= verifie(np.array_equal(out1, out2), "deux appels = résultat identique")
t0 = time.perf_counter()
for _ in range(5):
    vl.etirer(mono, mode=vl.MODE_LOG_D, log_d=2.5)
print(f"  durée moyenne = {(time.perf_counter()-t0)/5*1000:.0f} ms")

# --- 4. valeurs > 1.1 : pas d'écrasement /65535 ------------------------------
print("\n[4] Entrée avec max > 1.1 (piège normalize_input)")
piege = mono.copy()
piege[0, 0] = 5.0                            # hot pixel / flat mal appliqué
outp, _, _ = vl.etirer(piege, mode=vl.MODE_TARGET_BG)
ok &= verifie(float(np.median(outp)) > 0.05,
              "image non écrasée (médiane > 0.05, clip [0,1] efficace)")

# --- 5. petite image (chemin sous-échantillonné) ------------------------------
print("\n[5] Petite image mono 64x64")
petit = image_synthetique(64, 64, seed=9)
outp2, _, _ = vl.etirer(petit, mode=vl.MODE_TARGET_BG)
ok &= verifie(outp2.shape == petit.shape and outp2.max() <= 1.0,
              "petite image OK")

# --- 6. profil capteur inconnu → repli Rec.709 --------------------------------
print("\n[6] Profil inconnu → repli silencieux Rec.709")
outp3, _, diag3 = vl.etirer(mono, mode=vl.MODE_LOG_D, log_d=2.0,
                            profil="Capteur au pif")
ok &= verifie(diag3["sensor_profile"] == vl.PROFIL_PAR_DEFAUT,
              "profil de repli utilisé")

# --- 7. aperçu taille réelle (info jalons 2-3) --------------------------------
print("\n[7] Chrono taille aperçu 1600x1000")
apercu = image_synthetique(1000, 1600, seed=3)
t0 = time.perf_counter()
vl.etirer(apercu, mode=vl.MODE_TARGET_BG)
print(f"  target_bg : {(time.perf_counter()-t0)*1000:.0f} ms")
t0 = time.perf_counter()
vl.etirer(apercu, mode=vl.MODE_LOG_D, log_d=2.0)
print(f"  logD forcé : {(time.perf_counter()-t0)*1000:.0f} ms")

print("\n===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)