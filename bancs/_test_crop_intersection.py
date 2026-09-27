# -*- coding: utf-8 -*-
"""Test headless du recadrage automatique à l'intersection (v2.3.3).

Cause (constat Alain, 16/09/2026) : les bords d'écart de recouvrement de
l'empilement (décalage des frames) sont une marche de fond pour GraXpert →
« coussin » clair après background-extraction ; le recadrage manuel dans
Siril supprimait le problème. Fix : recadrage à l'intersection GÉOMÉTRIQUE
RÉELLE des frames alignées (équivalent -framing=min de Siril), calculée
incrémentalement à partir des matrices d'alignement.

Vérifie :
  1. les fonctions de géométrie (translations connues → cadre exact) ;
  2. la rotation (le cadre reste valide, l'image reste utilisable) ;
  3. l'intégration LiveStacker : mean() recadrée = crop manuel du plein ;
  4. les garde-fous : sans note_alignement → pas de crop ; reset → plus de
     crop ; M aberrante (quad disjoint) ignorée ; frame RGB (H, W, 3).

Exécution : python bancs/_test_crop_intersection.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np

from avastack.processing.stacking import (LiveStacker, quad_alignement,
                                          cadre_intersection,
                                          _MARGE_CROP, _CROP_MIN_COTE)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


H, W = 100, 120
IDENT = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
TX = np.array([[1.0, 0.0, 10.0], [0.0, 1.0, 0.0]])   # la frame est décalée de +10 px en x
TY = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 8.0]])    # … et de +8 px en y

print("[1] Fonctions de géométrie : translations connues")
s = LiveStacker((H, W), k=None)
s.note_alignement(IDENT)
verifie(s.cadre == (_MARGE_CROP, _MARGE_CROP,
                    H - _MARGE_CROP, W - _MARGE_CROP),
        f"identité → cadre pleine image − marge ({s.cadre})")
s.note_alignement(TX)
verifie(s.cadre == (_MARGE_CROP, _MARGE_CROP + 10,
                    H - _MARGE_CROP, W - _MARGE_CROP),
        f"translation +10 en x → bord droit gardé ({s.cadre})")
s.note_alignement(TY)
verifie(s.cadre == (_MARGE_CROP + 8, _MARGE_CROP + 10,
                    H - _MARGE_CROP, W - _MARGE_CROP),
        f"translation +8 en y → bord bas gardé ({s.cadre})")

print("[2] Rotation légère : le cadre reste valide")
ang = np.deg2rad(5.0)
c, s_ = np.cos(ang), np.sin(ang)
cx, cy = W / 2.0, H / 2.0
ROT = np.array([[c, -s_, cx - c * cx + s_ * cy],
                [s_, c, cy - s_ * cx - c * cy]])
s.note_alignement(ROT)
verifie(s.cadre is not None and
        s.cadre[0] >= _MARGE_CROP and s.cadre[1] >= _MARGE_CROP
        and s.cadre[2] <= H - _MARGE_CROP and s.cadre[3] <= W - _MARGE_CROP,
        f"rotation 5° → cadre contenu dans la marge ({s.cadre})")

print("[3] Garde-fous")
s2 = LiveStacker((H, W), k=None)
verifie(s2.mean() is None and s2.cadre is None, "sans frame : rien")
s2.add(np.full((H, W), 0.2, np.float32))
verifie(s2.mean().shape == (H, W),
        "sans note_alignement : PAS de crop (comportement conservé)")
lointain = np.array([[1.0, 0.0, 400.0], [0.0, 1.0, 300.0]])   # quad disjoint
avant = s.cadre
s.note_alignement(lointain)
verifie(s.cadre == avant, "M aberrante (quad disjoint) → intersection ignorée")
s.reset()
verifie(s.cadre is None, "reset() → plus de crop")
petit = cadre_intersection(np.array([[0.0, 0.0], [5.0, 0.0], [5.0, 5.0],
                                     [0.0, 5.0]]))
verifie(petit is None, f"polygone trop petit ({_CROP_MIN_COTE} px min) → None")

print("[4] Intégration LiveStacker : mean() recadrée = crop manuel du plein")
rng = np.random.default_rng(1)
frames = [np.clip(rng.normal(0.3, 0.05, (H, W)), 0, 1).astype(np.float32)
          for _ in range(4)]
st1 = LiveStacker((H, W), k=None)
st2 = LiveStacker((H, W), k=None)
mats = [IDENT, TX, TY, TX]
for f, M in zip(frames, mats):
    st1.add(f)
    st1.note_alignement(M)
    st2.add(f)
y0, x0, y1, x1 = st1.cadre
verifie(st1.mean().shape == (y1 - y0, x1 - x0),
        f"mean() recadrée : {st1.mean().shape} (cadre {st1.cadre})")
verifie(np.allclose(st1.mean(), st2.mean()[y0:y1, x0:x1]),
        "contenu recadré = crop manuel de l'accumulation pleine")

print("[5] Frame couleur (H, W, 3)")
sc = LiveStacker((H, W, 3), k=None)
fc = np.repeat(frames[0][..., None], 3, axis=2)
sc.add(fc)
sc.note_alignement(TX)
cy0, cx0, cy1, cx1 = sc.cadre
verifie(sc.mean().shape == (cy1 - cy0, cx1 - cx0, 3),
        f"mean() RGB recadrée : {sc.mean().shape} (cadre {sc.cadre})")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
