# -*- coding: utf-8 -*-
"""Test du jalon 117a (v2.69.0) — RECADRAGE = plus grand rectangle INSCRIT.

Défaut mesuré le 09/10/2026 (constat d'Alain, M31 LRGB sur deux nuits à
176,2°) : `cadre_intersection` rendait la BOÎTE ENGLOBANTE du polygone
d'intersection des zones couvertes. Or, pour une rotation de quelques degrés,
ce polygone vaut ~96 % de la frame mais ses extrêmes tombent au MILIEU des
côtés (le polygone EST la frame entière, ses coins coupés) : la boîte
englobante vaut donc la PLEINE image, moins `_MARGE_CROP` (3 px) — mesuré
`cadre` = (3, 3, 2176, 3852) sur 3856×2180, et seulement 23×17 px retirés du
PNG livré. Les coins NON COUVERTS restaient visibles, avec une teinte
différente et différente d'un coin à l'autre (c'est le recouvrement des
frames, pas la vignette) → le retrait de gradient échouait derrière.

Correctif : le recadrage rend désormais le PLUS GRAND RECTANGLE AXIAL INSCRIT
dans le polygone (leçon « -framing=min » de Siril : mesuré sur ce jeu, insets
(62, 137) px → 3732×1906 px, 84,6 % de la frame).

Ce banc vérifie :
  [1] une ROTATION de quelques degrés RETIRE les coins (le cadre n'est plus la
      pleine image) et le rectangle retenu est VRAIMENT inscrit (ses quatre
      coins sont dans le polygone) ;
  [2] le résultat coïncide avec un BALAYAGE BRUTE-FORCE indépendant à 1 px, et
      le cas « diamant » (carré tourné de 45°), dont l'optimum ne tombe PAS sur
      un sommet du polygone, donne bien l'aire théorique s²/2 ;
  [3] non-régression : identité et translations pures → MÊMES cadres qu'avant
      (la boîte englobante EST le plus grand rectangle quand il n'y a pas de
      rotation) ;
  [4] garde-fous : polygone absent/dégénéré ou trop petit → None ; M aberrante
      ignorée ;
  [5] intégration LiveStacker : `mean()` recadrée = crop manuel du plein.

Exécution : python bancs/_test_crop_inscrit_jalon117.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np

from avastack.processing.stacking import (LiveStacker, plus_grand_rect_inscrit,
                                          cadre_intersection,
                                          _MARGE_CROP, _CROP_MIN_COTE)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- Références INDÉPENDANTES du module (implémentation propre au banc) ------
def coupe(poly, x):
    """Coupe verticale scalaire (implémentation DU BANC, à dessein différente
    de celle du module) : (lo, hi) ou (inf, -inf) si x est hors emprise."""
    lo, hi = np.inf, -np.inf
    n = len(poly)
    for i in range(n):
        ax, ay = float(poly[i][0]), float(poly[i][1])
        bx, by = float(poly[(i + 1) % n][0]), float(poly[(i + 1) % n][1])
        if ax == bx:
            if x == ax:
                lo, hi = min(lo, ay, by), max(hi, ay, by)
            continue
        if min(ax, bx) <= x <= max(ax, bx):
            t = (x - ax) / (bx - ax)
            y = ay + t * (by - ay)
            lo, hi = min(lo, y), max(hi, y)
    return lo, hi


def bruteforce(poly):
    """Plus grand rectangle AXIAL inscrit, balayage 1 px (vérité du banc)."""
    xmin = int(np.ceil(poly[:, 0].min()))
    xmax = int(np.floor(poly[:, 0].max()))
    meilleur = 0.0
    for x0 in range(xmin, xmax + 1):
        lo0, hi0 = coupe(poly, float(x0))
        if not np.isfinite(lo0):
            continue
        for x1 in range(x0 + 1, xmax + 1):
            lo1, hi1 = coupe(poly, float(x1))
            if not np.isfinite(lo1):
                continue
            ht = min(hi0, hi1) - max(lo0, lo1)
            if ht > 0:
                meilleur = max(meilleur, (x1 - x0) * ht)
    return meilleur


def dedans(poly, pt):
    """Vrai si `pt` est DANS le polygone convexe (mêmes règles que le clipper)."""
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if ((float(b[0]) - float(a[0])) * (pt[1] - float(a[1]))
                - (float(b[1]) - float(a[1])) * (pt[0] - float(a[0])) < -1e-6):
            return False
    return True


def aire(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))


H, W = 300, 400
IDENT = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


def rotation(deg, h=H, w=W):
    """Matrice affine d'une rotation `deg` autour du centre de la frame."""
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    return np.array([[c, -s, w / 2.0 - c * w / 2.0 + s * h / 2.0],
                     [s, c, h / 2.0 - s * w / 2.0 - c * h / 2.0]])



# ================================================ [1] rotation ⇒ coins retirés
print("[1] Rotation de quelques degrés → le cadre RETIRE les coins")
s = LiveStacker((H, W), k=None)
s.note_alignement(IDENT)
s.note_alignement(rotation(6.0))
POLY = s._poly
BOX_W = int(np.floor(POLY[:, 0].max())) - int(np.ceil(POLY[:, 0].min()))
BOX_H = int(np.floor(POLY[:, 1].max())) - int(np.ceil(POLY[:, 1].min()))
cadre = s.cadre
print(f"    polygone : {len(POLY)} sommets, {aire(POLY) / (H * W) * 100:.1f} % "
      f"de la frame · cadre {cadre}")
verifie(cadre is not None and cadre[0] > _MARGE_CROP and cadre[1] > _MARGE_CROP,
        f"bords hauts/gauches retirés AU-DELÀ de la marge "
        f"({cadre[0]}, {cadre[1]} > {_MARGE_CROP})")
surface = (cadre[2] - cadre[0]) * (cadre[3] - cadre[1])
verifie(surface < 0.95 * H * W,
        f"surface gardée {surface / (H * W) * 100:.1f} % < 95 % (l'ancienne "
        f"boîte englobante en gardait {BOX_W * BOX_H / (H * W) * 100:.1f} %)")
y0, x0, y1, x1 = cadre
coins = [(float(x0), float(y0)), (float(x1), float(y0)),
         (float(x0), float(y1)), (float(x1), float(y1))]
verifie(all(dedans(POLY, c) for c in coins),
        "les QUATRE coins du cadre retenu sont DANS le polygone (rectangle "
        "réellement inscrit)")

# ================================================ [2] vérité brute-force
print("[2] Coïncide avec un balayage BRUTE-FORCE 1 px indépendant")
ref = bruteforce(POLY)
rec = plus_grand_rect_inscrit(POLY)
aire_rec = (rec[1] - rec[0]) * (rec[3] - rec[2])
print(f"    aire inscrite : module {aire_rec:.0f} px² · brute-force {ref:.0f} px²")
verifie(aire_rec <= ref + 1e-6 and aire_rec >= 0.97 * ref,
        f"aire du module dans [97 %, 100 %] de la vérité "
        f"({aire_rec / ref * 100:.1f} %)")
cote = 200.0
r2 = cote / np.sqrt(2.0)             # demi-diagonale du carré tourné de 45°
cx = cy = 400.0
DIAM = np.array([[cx, cy - r2], [cx + r2, cy], [cx, cy + r2], [cx - r2, cy]])
rec_d = plus_grand_rect_inscrit(DIAM)
aire_d = (rec_d[1] - rec_d[0]) * (rec_d[3] - rec_d[2])
theorie = cote * cote / 2.0
print(f"    diamant (carré {cote:.0f} tourné de 45°) : aire {aire_d:.0f} px² "
      f"· théorie s²/2 = {theorie:.0f} px²")
verifie(abs(aire_d - theorie) < 0.02 * theorie,
        "optimum NON sur un sommet retrouvé (théorie dans ±2 %)")
verifie(abs((rec_d[0] + rec_d[1]) / 2.0 - cx) < 2.0,
        "rectangle optimal centré comme la théorie (bords non verticaux)")


# ================================================ [3] non-régression
print("[3] Non-régression : sans rotation, le cadre est inchangé")
TX = np.array([[1.0, 0.0, 10.0], [0.0, 1.0, 0.0]])
TY = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 8.0]])
s3 = LiveStacker((H, W), k=None)
s3.note_alignement(IDENT)
verifie(s3.cadre == (_MARGE_CROP, _MARGE_CROP, H - _MARGE_CROP, W - _MARGE_CROP),
        f"identité → pleine image − marge ({s3.cadre})")
s3.note_alignement(TX)
verifie(s3.cadre == (_MARGE_CROP, _MARGE_CROP + 10,
                     H - _MARGE_CROP, W - _MARGE_CROP),
        f"translation +10 en x → bord droit gardé ({s3.cadre})")
s3.note_alignement(TY)
verifie(s3.cadre == (_MARGE_CROP + 8, _MARGE_CROP + 10,
                     H - _MARGE_CROP, W - _MARGE_CROP),
        f"translation +8 en y → bord bas gardé ({s3.cadre})")

# ================================================ [4] garde-fous
print("[4] Garde-fous")
s4 = LiveStacker((H, W), k=None)
verifie(s4.mean() is None and s4.cadre is None, "sans frame : rien")
s4.add(np.full((H, W), 0.2, np.float32))
verifie(s4.mean().shape == (H, W), "sans note_alignement : PAS de crop")
lointain = np.array([[1.0, 0.0, 4000.0], [0.0, 1.0, 3000.0]])
avant = s3.cadre
s3.note_alignement(lointain)
verifie(s3.cadre == avant, "M aberrante (quad disjoint) → intersection ignorée")
s3.reset()
verifie(s3.cadre is None, "reset() → plus de crop")
petit = np.array([[0.0, 0.0], [5.0, 0.0], [5.0, 5.0], [0.0, 5.0]])
verifie(cadre_intersection(petit) is None,
        f"polygone trop petit ({_CROP_MIN_COTE} px min) → None")
verifie(cadre_intersection(None) is None
        and cadre_intersection(np.array([[0.0, 0.0], [1.0, 1.0]])) is None,
        "polygone absent ou dégénéré → None")

# ================================================ [5] intégration
print("[5] Intégration LiveStacker : mean() recadrée = crop manuel du plein")
rng = np.random.default_rng(1)
frames = [np.clip(rng.normal(0.3, 0.05, (H, W)), 0, 1).astype(np.float32)
          for _ in range(4)]
st1 = LiveStacker((H, W), k=None)
st2 = LiveStacker((H, W), k=None)
for f, M in zip(frames, (IDENT, rotation(4.0), rotation(4.0), IDENT)):
    st1.add(f)
    st1.note_alignement(M)
    st2.add(f)
ky0, kx0, ky1, kx1 = st1.cadre
verifie(st1.mean().shape == (ky1 - ky0, kx1 - kx0),
        f"mean() recadrée : {st1.mean().shape} (cadre {st1.cadre})")
verifie(np.allclose(st1.mean(), st2.mean()[ky0:ky1, kx0:kx1]),
        "contenu recadré = crop manuel de l'accumulation pleine")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)

