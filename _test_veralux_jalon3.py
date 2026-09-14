# -*- coding: utf-8 -*-
"""Test headless du jalon 3 VeraLux — mode target_bg + solveur par frame.

Vérifie, SANS Tk :
  - le mode de résolution « target_bg » par défaut (fond calé sur la cible) ;
  - qu'AUCUN recalcul n'est déclenché entre deux frames (l'objet image change
    à chaque tick UI sans nouvel empilement) ;
  - que notify_new_stack() relance bien la résolution (dernier empilement
    gagnant, aucune file d'attente) ;
  - le verrouillage : logD forcé = logD résolu → résultat déterministe ;
  - reset() (nouvelle session / changement de vue) ;
  - black/white/gamma JAMAIS modifiés par VeraLux.
"""
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

# « empilement suivant » : autre contenu (comme après une nouvelle frame)
img2 = np.clip(np.roll(img, 30, axis=1) * 0.9, 0.0, 1.0)


def attendre(d, max_s=10.0):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < max_s:
        if not d._vl_pending:
            return True
        time.sleep(0.05)
    return False


def resoudre(d, img, max_s=10.0):
    """Soumet et attend JUSQU'À STABILITÉ : si un calcul était déjà en cours,
    la demande de recalcul est différée d'un tour (dernier empilement
    gagnant) — il faut donc re-soumettre après la fin du calcul en cours."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < max_s:
        d.process(img)
        attendre(d)
        d.process(img)
        if not d._vl_pending and d._vl_job is None:
            return True
    return False


ok = True


def verifie(cond, msg):
    global ok
    print(("  OK  " if cond else "  ECHEC ") + msg)
    ok = bool(ok and cond)


d = DisplayProcessor()
d.black, d.white = 0.1, 0.9                     # ne doivent JAMAIS bouger

# --- 1. défauts du jalon 3 -----------------------------------------------------
print("[1] Défauts jalon 3")
verifie(d.vl_mode_res == vl.MODE_TARGET_BG,
        "mode de résolution par défaut = target_bg")

# --- 2. mode VeraLux target_bg : fallback STF puis fond calé -------------------
print("[2] VeraLux target_bg (fond cible 0.20)")
d.stretch = "veralux"
out_attente = d.process(img)                    # 1er appel : fallback + job soumis
verifie(d._vl_pending, "calcul soumis au thread solveur")
verifie(attendre(d), "calcul terminé dans le thread")
verifie(d.vl_error == "", f"pas d'erreur ({d.vl_error!r})")
out_vl = d.process(img)
verifie(d.vl_log_d_resolu is not None and d.vl_log_d_resolu > 0.0,
        f"logD résolu ({d.vl_log_d_resolu})")
diag = d.vl_diagnostics or {}
verifie("median_luminance_finale" in diag
        and abs(diag["median_luminance_finale"] - d.vl_target_bg) < 0.05,
        f"fond calé sur la cible ({diag.get('median_luminance_finale')})")
verifie(d.black == 0.1 and d.white == 0.9,
        "black/white JAMAIS modifiés par VeraLux")

# --- 3. AUCUN recalcul entre deux frames (tick UI sans nouvel empilement) ------
print("[3] Pas de recalcul entre deux frames")
d._vl_pending = False
d._vl_job = None
d.process(img.copy())                           # NOUVEL objet, MÊME empilement
verifie(d._vl_job is None and not d._vl_pending,
        "objet image nouveau mais pas de nouvel empilement → rien soumis")

# --- 4. notify_new_stack() → dernier empilement gagnant ------------------------
print("[4] Nouvel empilement → résolution relancée")
d.notify_new_stack()
d.process(img)                                  # tick avec l'ancien aperçu
d.notify_new_stack()                            # puis une nouvelle frame arrive
verifie(resoudre(d, img2), "résolution du dernier empilement terminée")
verifie(d._vl_job is None, "aucune file d'attente (dernier job seul gardé)")
out_vl2 = d.process(img2)
verifie(out_vl2.shape == img2.shape, "rendu du dernier empilement")

# --- 4b. curseur target_bg → recalcul et nouveau calage ------------------------
print("[4b] Changement du fond cible → recalcul")
d.vl_target_bg = 0.30
verifie(resoudre(d, img2), "recalcul pour fond cible 0.30 terminé")
d.process(img2)
diag = d.vl_diagnostics or {}
verifie("median_luminance_finale" in diag
        and abs(diag["median_luminance_finale"] - 0.30) < 0.05,
        f"fond recalé sur la nouvelle cible ({diag.get('median_luminance_finale')})")
d.vl_target_bg = vl.TARGET_BG_PAR_DEFAUT

# --- 5. verrouillage : logD forcé = logD résolu → déterministe ------------------
print("[5] Verrouillage du logD résolu")
ld = d.vl_log_d_resolu
r1, ld1, _ = vl.etirer(img, mode=vl.MODE_TARGET_BG, target_bg=0.20)
r2, ld2, _ = vl.etirer(img, mode=vl.MODE_LOG_D, log_d=ld1)
verifie(ld2 == ld1, "logD forcé = logD résolu rendu tel quel")
ecart = float(np.max(np.abs(r1 - r2))) if r1.shape == r2.shape else 9e9
verifie(ecart < 0.05,
        f"étirement forcé ≈ étirement résolu (écart max {ecart:.4f})")
# via le DisplayProcessor :
d.vl_mode_res = vl.MODE_LOG_D
d.vl_log_d = ld
d.process(img)
verifie(attendre(d), "recalcul en logD forcé terminé")
out_lock = d.process(img)
ecart_u8 = float(np.max(np.abs(out_lock.astype(int) - out_vl.astype(int))))
verifie(ecart_u8 <= 6,
        f"rendu verrouillé ≈ rendu résolu (écart max uint8 {ecart_u8:.0f})")

# --- 6. reset() : nouvelle session / changement de vue -------------------------
print("[6] reset()")
d.reset()
verifie(d._vl_result is None, "cache VeraLux vidé")
d.process(img)
verifie(d._vl_pending or d._vl_job is not None,
        "résolution relancée après reset")
verifie(attendre(d), "résolution après reset terminée")

# --- 7. retour STF propre -------------------------------------------------------
print("[7] Retour STF")
d.stretch = "stf"
out_stf = d.process(img)
verifie(out_stf.dtype == np.uint8, "STF de nouveau opérationnel")
verifie(d.black == 0.1 and d.white == 0.9,
        "black/white toujours intacts après tous les allers-retours")

print("\n===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)