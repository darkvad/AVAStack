# -*- coding: utf-8 -*-
"""_diag_ecran_fichier_jalon68.py — où divergent le chemin d'AFFICHAGE
(`DisplayProcessor.process`) et le chemin de SAUVEGARDE
(`rendu_pleine_resolution`) quand on leur donne la MÊME image pleine résolution ?

Le banc `_test_zoom_pleine_res_jalon68.py` [3] mesure 18 niveaux d'écart : ce banc
isole la cause — résultat du worker comparé à un appel DIRECT au moteur, avec et
sans les étapes pré-étirement, et état des cases du DisplayProcessor.

Usage : python bancs/_diag_ecran_fichier_jalon68.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.processing.display import DisplayProcessor
from avastack.processing import veralux as V
from avastack.processing import couleurs as C

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

rng = np.random.default_rng(8038)
n = 320
yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
scene = np.full((n, n, 3), 0.02, np.float32)
for (cx, cy, coul, amp) in ((90.0, 80.0, (1.0, 0.72, 0.42), 0.6),
                            (230.0, 210.0, (0.42, 0.70, 1.0), 0.6),
                            (180.0, 60.0, (0.9, 0.95, 1.0), 0.08)):
    prof = amp / (1.0 + ((xx - cx) ** 2 + (yy - cy) ** 2) / 2.5 ** 2) ** 2.0
    scene += prof[..., None] * np.array(coul, np.float32).reshape(1, 1, 3)
scene += rng.normal(0.0, 0.0006, scene.shape).astype(np.float32)
scene = np.clip(scene, 0.0, None).astype(np.float32)

d = DisplayProcessor()
d.stretch = "veralux"
d.vl_mode_res = V.MODE_TARGET_BG
d.vl_target_bg = 0.16
print("cases du DisplayProcessor :")
for k in ("vl_graxpert", "vl_denoise", "vl_sharp", "vl_scnr", "vl_scnr_doux",
          "vl_demagenta", "vl_neutre_fond", "vl_chroma"):
    print(f"    {k:16s} {getattr(d, k)}")
_ = d.process(scene)
t0 = time.time()
while time.time() - t0 < 60:
    with d._vl_lock:
        if d._vl_job is None and not d._vl_pending and d._vl_result is not None:
            break
    time.sleep(0.02)
res = d._vl_result[1]
print(f"\nlogD résolu par le worker : {d.vl_log_d_resolu}")
print(f"ancre (diag moteur) : {d.vl_diagnostics.get('anchor')} · "
      f"médiane L finale : {d.vl_diagnostics.get('median_luminance_finale')}")


def cmp(nom, img):
    r, ld, dg = V.etirer(img, mode=V.MODE_LOG_D, log_d=d.vl_log_d_resolu,
                         target_bg=0.16, profil=d.vl_profil)
    ec = float(np.max(np.abs(res - r)))
    ec8 = int(np.round(ec * 255))
    print(f"    {nom:34s} écart max {ec:.6f} ({ec8} niveau(x) 8 bits) · "
          f"ancre {dg.get('anchor')}")


print("\nrésultat du worker comparé à un appel DIRECT :")
cmp("scene brute (sans pré-étapes)", scene)
cmp("scene neutralisée", C.neutraliser_fond(scene))
cmp("neutralisée + chroma", C.reduire_bruit_chroma(
    C.neutraliser_fond(scene), force=d.vl_chroma_force, rayon=d.vl_chroma_rayon))

# --- Le fond cible de SORTIE : 0,16 (écran) contre 0,20 (défaut du module, ce
# que `rendu_pleine_resolution` utilise quand le logD est déjà résolu).
print("\nle fond cible de l'étape de sortie du moteur (mode logD imposé) :")
neutre = C.neutraliser_fond(scene)
a, _, _ = V.etirer(neutre, mode=V.MODE_LOG_D, log_d=d.vl_log_d_resolu,
                   target_bg=0.16, profil=d.vl_profil)
b, _, _ = V.etirer(neutre, mode=V.MODE_LOG_D, log_d=d.vl_log_d_resolu,
                   target_bg=0.20, profil=d.vl_profil)
ec = np.abs(a - b)
print(f"    fond cible 0,16 contre 0,20 : écart max {float(ec.max()):.4f} "
      f"({int(round(float(ec.max()) * 255))} niveaux 8 bits) · moyen "
      f"{float(ec.mean()):.5f} ({float(ec.mean()) * 255:.1f} niveaux)")
print(f"    fond médian obtenu : {float(np.median(a.mean(axis=2))):.4f} "
      f"(cible 0,16) contre {float(np.median(b.mean(axis=2))):.4f} (cible 0,20)")
