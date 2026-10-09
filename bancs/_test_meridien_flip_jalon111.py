# -*- coding: utf-8 -*-
"""Test du jalon 111 (v2.63.0) — RETOURNEMENT AU MÉRIDIEN accepté par l'aligneur.

Constat réel d'Alain (08/10/2026) : sur deux nuits d'acquisition (même caméra,
NINA), les couches R/G/B ont subi un retournement au méridien (rotation ~180°
par rapport au ciel) alors que la couche L ne l'a pas subi. L'aligneur REJETAIT
toutes les frames retournées (|angle| > 10°) : résultat 3-4 frames R/G/B
empilées sur 50, un empilement appauvri, ET des « taches rouges » (la formule
LRGB amplifie le fond là où L seul portait encore un objet). Ce banc vérifie :

  [1] `_M_valide` : accepte ~0° ET ~180° (± tolérance), refuse tout le reste
      (15°, 90°, 165°, 195°), refuse une échelle aberrante et les NaN ;
  [2] `StarAligner` de bout en bout sur une frame PIVOTÉE de 180° : la rotation
      est retrouvée (|angle| ≈ 180°) et la frame reconstruite ≈ la référence ;
  [3] NON-RÉGRESSION : une translation normale reste alignée, une rotation de
      15° reste refusée (le garde-fou n'est pas devenu permissif).

Exécution : python bancs/_test_meridien_flip_jalon111.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np
import cv2

from avastack.processing import alignment as al_mod
from avastack.processing import stars as st_mod

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def champ(shape, nb=25, sigma_px=1.5, bruit=0.004, fond=0.02, graine=1,
          marge=25):
    """Champ synthétique : nb étoiles gaussiennes + bruit (même fabrication
    que `_test_align_jalon13` — champ riche, résolution d'alignement unique)."""
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(nb):
        y = float(rng.integers(marge, h - marge))
        x = float(rng.integers(marge, w - marge))
        a = float(rng.uniform(0.1, 0.7))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    return img


def M_rotation(deg, cx, cy):
    """Matrice warpAffine d'une rotation `deg` autour de (cx, cy). Sert à figer
    des angles EXACTS dans les tests de garde-fou."""
    r = np.deg2rad(deg)
    c, s = np.cos(r), np.sin(r)
    return np.array([[c, -s, cx - c * cx + s * cy],
                     [s, c, cy - s * cx - c * cy]], np.float64)


print("[1] _M_valide : 0° et 180° acceptés, le reste refusé")
I3 = np.eye(2, 3)
verifie(al_mod._M_valide(I3), "identité (0°) valide")
M180 = M_rotation(180.0, 200.0, 150.0)
verifie(al_mod._M_valide(M180), "rotation 180° EXACTE → acceptée (méridien flip)")
verifie(al_mod._M_valide(M_rotation(170.0, 200.0, 150.0)),
        "170° (bord bas de la tolérance) → accepté")
verifie(al_mod._M_valide(M_rotation(190.0, 200.0, 150.0)),
        "190° (bord haut de la tolérance) → accepté")
verifie(not al_mod._M_valide(M_rotation(165.0, 200.0, 150.0)),
        "165° (hors tolérance) → refusé")
verifie(not al_mod._M_valide(M_rotation(195.0, 200.0, 150.0)),
        "195° (hors tolérance) → refusé")
verifie(not al_mod._M_valide(M_rotation(90.0, 200.0, 150.0)),
        "90° (rotation d'optique) → refusé")
verifie(not al_mod._M_valide(M_rotation(15.0, 200.0, 150.0)),
        "15° → refusé (garde-fou inchangé)")
M_big = M180.copy(); M_big[0, 0] *= 0.5            # échelle ~0.5 à 180°
verifie(not al_mod._M_valide(M_big),
        "180° mais échelle 0,5 → refusé (l'échelle borne encore)")
Mn = I3.copy(); Mn[0, 2] = np.nan
verifie(not al_mod._M_valide(Mn), "NaN → refusé")
ang, ech, _dx, _dy = al_mod.infos_M(M180)
verifie(abs(abs(ang) - 180.0) < 1e-6 and abs(ech - 1.0) < 1e-6,
        f"infos_M(rotation 180°) : angle {ang:+.2f}° · échelle {ech:.3f}")


print("[2] StarAligner : une frame pivotée de 180° est alignée (plus refusée)")
ref = champ((300, 400), nb=25, graine=2)
al = al_mod.StarAligner()
al.set_reference(ref)
fr = cv2.rotate(ref, cv2.ROTATE_180)              # retournement au méridien
M, okk = al.compute(fr)
ang, ech, _dx, _dy = (al_mod.infos_M(M) if M is not None
                      else (0.0, 0.0, 0.0, 0.0))
verifie(okk, "frame à 180° ALIGNÉE (méthode « "
             f"{al.dernier['methode'] if al.dernier else '?'} »)")
verifie(okk and abs(abs(ang) - 180.0) < 1.0,
        f"angle retrouvé ≈ 180° ({ang:+.2f}°), échelle {ech:.4f}")
if okk:
    rec = cv2.warpAffine(fr, M, (fr.shape[1], fr.shape[0]))
    ecart = float(np.mean(np.abs(rec - ref)))
    verifie(ecart < 0.02,
            f"frame retournée reconstruite ≈ référence (écart moyen {ecart:.4f})")


print("[3] Non-régression : translation normale OK, 15° toujours refusé")
ref2 = champ((300, 400), nb=25, graine=7)
al2 = al_mod.StarAligner()
al2.set_reference(ref2)
Mt = np.array([[1.0, 0.0, 7.0], [0.0, 1.0, -5.0]], np.float64)
fr2 = cv2.warpAffine(ref2, Mt, (400, 300), flags=cv2.INTER_LINEAR)
M2, ok2 = al2.compute(fr2)
verifie(ok2 and abs(M2[0, 2] + 7.0) < 0.7 and abs(M2[1, 2] - 5.0) < 0.7,
        (f"translation (+7,−5) toujours retrouvée Δ=({M2[0, 2]:+.2f},"
         f"{M2[1, 2]:+.2f})") if ok2 else "translation (+7,−5) : REPLI PERDU")
M3 = M_rotation(15.0, 200.0, 150.0)
fr3 = cv2.warpAffine(ref2, M3, (400, 300), flags=cv2.INTER_LINEAR)
al3 = al_mod.StarAligner()
al3.set_reference(ref2)
M3r, ok3 = al3.compute(fr3)
# 15° reste HORS tolérance : l'aligneur ne doit jamais ACCEPTER une matrice à
# ~15° (il peut échouer proprement — refus — ou retomber sur une translation,
# mais pas valider la rotation de 15°).
ang3 = abs(al_mod.infos_M(M3r)[0]) if M3r is not None else 0.0
verifie((not ok3) or abs(ang3 - 15.0) > 5.0,
        f"rotation 15° : aucun alignement à 15° accepté (ok={ok3}, "
        f"angle={ang3:.1f}°)")

print("[4] Sélection RÉPARTIE : repli progressif (champ concentré / pauvre / riche)")
import time as _time


def _champ(shape, pts, graine=1):
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), 0.02, np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for x, y, a in pts:
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                            / (2 * 1.4 ** 2))).astype(np.float32)
    img += rng.normal(0.0, 0.004, img.shape).astype(np.float32)
    return img


def _compte(img, d):
    return len(st_mod.detecter_positions(img, max_etoiles=al_mod.MAX_ALIGN_ETOILES,
                                         distance_min=d)[0])


H, W = 2180, 3856
d_full = al_mod._distance_repartition((H, W))
rng = np.random.default_rng(11)

pts_pauvre = [(float(rng.uniform(200, W - 200)), float(rng.uniform(200, H - 200)),
               float(rng.uniform(0.2, 0.8))) for _ in range(15)]
img_p = _champ((H, W), pts_pauvre)
n0 = _compte(img_p, 0.0)
n1 = _compte(img_p, d_full)
verifie(n1 == n0 == 15,
        f"champ PAUVRE (15 étoiles réparties) : {n0} → {n1} (aucune perte)")

pts_conc = [(1200 + float(rng.uniform(0, 300)), 1000 + float(rng.uniform(0, 300)),
             float(rng.uniform(0.2, 0.8))) for _ in range(40)]
img_c = _champ((H, W), pts_conc)
n0 = _compte(img_c, 0.0)
t0 = _time.perf_counter()
n1 = _compte(img_c, d_full)
dt = _time.perf_counter() - t0
verifie(n1 >= min(st_mod.MIN_REPARTI, n0) - 2,
        f"champ CONCENTRÉ (40 étoiles / 300 px) : {n0} → {n1} "
        f"(repli progressif, PAS d'effondrement)")

pts_riche = [(float(rng.uniform(200, W - 200)), float(rng.uniform(200, H - 200)),
              float(rng.uniform(0.2, 0.8))) for _ in range(400)]
img_r = _champ((H, W), pts_riche, graine=3)
n0 = _compte(img_r, 0.0)
n1 = _compte(img_r, d_full)
verifie(n1 >= 100 and n1 < n0,
        f"champ RICHE (400 étoiles) : {n0} → {n1} (liste étalée, plafonnée "
        f"par l'écart {d_full:.0f} px)")
verifie(dt < 1.0, f"coût du repli borné : {dt * 1000:.0f} ms (< 1 s)")

print()
print("RÉSULTAT :", "TOUT AU VERT" if ok else "ÉCHEC(S) — voir ci-dessus")
sys.exit(0 if ok else 1)
