# -*- coding: utf-8 -*-
"""Banc du jalon 113 — ① RAFRAÎCHISSEMENT DE RÉFÉRENCE EN COMPOSITION (défaut
AVÉRÉ, mesuré le 09/10/2026 sur le jeu M31 LRGB d'Alain).

DÉFAUT CORRIGÉ : le rafraîchissement automatique / manuel de la référence
d'alignement passait `stacker.mean(recadre=False)` — en mode COMPOSITION, c'est
le COMPOSITE NORMALISÉ (H, W, 3) dont le canal VERT n'est PAS dans le domaine
des brutes : le fond du composite y vaut ~5× celui des brutes (~0,27 contre
~0,05 ici ; 0,5-1,1 contre 0,03 sur les vraies données). `StarAligner.set_reference`
calcule alors des bornes de normalisation situées AU-DESSUS du fond des brutes :
celles-ci sont écrasées à 0 → ORB aveugle → refus en cascade (8-9 refus sur
12 frames mesurés ; 0 refus sans refresh).

Vérifie :
  [1] LE DOMAINE : en composition, `moyennes(recadre=False)` rend des couches 2D
      BRUTES (même domaine que les brutes : médiane ≈ fond ~0,05) alors que
      `mean(recadre=False)` rend un composite NORMALISÉ (canal VERT ~5× le fond
      des brutes) ;
  [2] `App._image_reference()` : rend la COUCHE BRUTE du rôle qui alimente le
      canal VERT (G en RGB/LRGB, O3 en HOO, Ha en SHO) — exactement la couche de
      `moyennes()` ; replis : rôle vert vide → 1er rôle non vide, hors
      composition → l'empilement tel quel, empilement absent → None ;
  [3] L'EFFET MESURÉ : la MÊME frame s'aligne avec la référence `_image_reference()`
      et est REFUSÉE avec le composite normalisé — c'est le défaut corrigé ;
  [4] REJEU « session » : 12 frames alignées après un rafraîchissement → refus en
      cascade avec le composite, 0 refus avec la couche de rôle.

Exécution : python bancs/_test_refresh_ref_compo_jalon113.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV/OpenCL au teardown sinon

import avastack.ui.app as ui
from avastack.processing.alignment import StarAligner
from avastack.processing.composition import CompositeStacker
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- champ d'étoiles synthétique : FOND DOMINANT (le cas réel LRGB) ----------
# L'amplitude des étoiles (0,025) est du même ordre que quelques fois le bruit
# (0,004) : le fond pèse donc fort dans les percentiles, exactement comme sur
# les brutes M31 d'Alain — c'est ce qui fait que le composite NORMALISÉ place
# son point bas AU-DESSUS du fond des brutes.
H, W = 200, 260
FOND = 0.05
_rng_etoiles = np.random.default_rng(3)
_ETOILES = [(_rng_etoiles.uniform(15, W - 15), _rng_etoiles.uniform(15, H - 15),
             _rng_etoiles.uniform(0.4, 0.9)) for _ in range(40)]


def champ(dx=0.0, dy=0.0, fond=FOND, amp=0.025, bruit=0.004, graine=0):
    """Carte float32 (H, W) : fond bruité + 40 étoiles gaussiennes translatées."""
    img = np.full((H, W), fond, np.float32)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    for (sx, sy, f) in _ETOILES:
        img += amp * f * np.exp(-((x - (sx + dx)) ** 2 + (y - (sy + dy)) ** 2)
                                / (2 * 1.2 ** 2)).astype(np.float32)
    img += np.random.default_rng(1000 + graine).normal(
        0, bruit, img.shape).astype(np.float32)
    return img


def compo(nom, roles_frames, dxs):
    """CompositeStacker peuplé : `roles_frames[r]` frames décalées de `dxs`."""
    st = CompositeStacker(nom, k=None)
    for role, n in roles_frames.items():
        for i in range(n):
            st.role_courant = role
            st.add(champ(dxs[i][0], dxs[i][1], graine=i))
    return st


DXS = [(0.3 * i, 0.2 * i) for i in range(12)]

# Config HERMÉTIQUE (règle du projet) : jamais le vrai config.json du poste.
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None

root = tk.Tk()
root.withdraw()
app = ui.App(root)
app._mode_compo = True


# ================================================ [1] domaine des deux images
print("[1] domaine : couche 2D brute vs composite NORMALISÉ (RGB, 12/rôle)")
st = compo("RGB", {"R": 12, "G": 12, "B": 12}, DXS)
couch = st.moyennes(recadre=False)
comp = st.mean(recadre=False)
frame = champ(DXS[0][0] * 12, DXS[0][1] * 12, graine=12)   # brute suivante

med_brute = float(np.median(frame))
med_couche = float(np.median(couch["G"]))
med_comp = float(np.median(comp[..., 1]))
r_couche = med_couche / med_brute
r_comp = med_comp / med_brute
print(f"    médiane brute={med_brute:.5f} · couche G={med_couche:.5f} "
      f"({r_couche:.2f}×) · composite vert={med_comp:.5f} ({r_comp:.2f}×)")
verifie(comp.shape == (H, W, 3) and couch["G"].shape == (H, W),
        "moyennes() → couche 2D ; mean() → composite (H, W, 3)")
verifie(r_couche < 1.30,
        f"la couche de rôle est DANS le domaine des brutes ({r_couche:.2f}×)")
verifie(r_comp > 2.0,
        f"le composite est HORS domaine des brutes ({r_comp:.2f}× le fond)")


# ============================================ [2] App._image_reference()
print("[2] App._image_reference() : couche BRUTE du rôle du canal VERT")
app.stacker = st
ref = app._image_reference()
verifie(ref is not None and ref.ndim == 2
        and np.array_equal(ref, couch["G"]),
        "RGB → la couche G BRUTE (identique à moyennes()['G'])")

st_hoo = compo("HOO", {"Ha": 3, "O3": 3}, DXS[:3])
app.stacker = st_hoo
verifie(np.array_equal(app._image_reference(),
                       st_hoo.moyennes(recadre=False)["O3"]),
        "HOO → le rôle du canal VERT = O3")

st_sho = compo("SHO", {"S2": 3, "Ha": 3, "O3": 3}, DXS[:3])
app.stacker = st_sho
verifie(np.array_equal(app._image_reference(),
                       st_sho.moyennes(recadre=False)["Ha"]),
        "SHO → le rôle du canal VERT = Ha")

st_vert_vide = compo("RGB", {"R": 4}, DXS[:4])           # rôle G vide
app.stacker = st_vert_vide
verifie(np.array_equal(app._image_reference(),
                       st_vert_vide.moyennes(recadre=False)["R"]),
        "rôle vert vide → 1er rôle NON vide (R)")

app._mode_compo = False
mono = LiveStacker((H, W), k=None)
mono.add(frame)
app.stacker = mono
m = app._image_reference()
verifie(m is not None and m.shape == (H, W)
        and np.array_equal(m, mono.mean(recadre=False)),
        "hors composition (mono) → l'empilement tel quel")

app.stacker = None
verifie(app._image_reference() is None,
        "aucun empilement → None (rien à poser)")

app._mode_compo = True


# ================================== [3] effet MESURÉ : refus → alignement
print("[3] effet sur l'aligneur : composite normalisé = aveugle ; couche = OK")
app.stacker = st
ref_ok = app._image_reference()
ref_ko = st.mean(recadre=False)          # ce que passait l'ANCIEN code

al_ko = StarAligner()
al_ko.set_reference(ref_ko)
_M_ko, ok_ko = al_ko.compute(frame)
al_ok = StarAligner()
al_ok.set_reference(ref_ok)
_M_ok, ok_ok = al_ok.compute(frame)
g8_ko = al_ko._norm8(frame, al_ko._ref_lo, al_ko._ref_hi)
g8_ok = al_ok._norm8(frame, al_ok._ref_lo, al_ok._ref_hi)
med_ko = float(np.median(g8_ko))
med_ok = float(np.median(g8_ok))
print(f"    composite : ok={ok_ko} · haut={al_ko._ref_hi:.3f} · "
      f"médiane 8 bits={med_ko:.1f} | couche : ok={ok_ok} · "
      f"haut={al_ok._ref_hi:.3f} · médiane 8 bits={med_ok:.1f}")
verifie(not ok_ko,
        "référence = composite normalisé → la frame est REFUSÉE (défaut mesuré)")
verifie(ok_ok,
        "référence = couche de rôle → la frame s'aligne (correctif)")
verifie(al_ko._ref_hi > 5.0 * al_ok._ref_hi,
        f"la référence composite couvre une dynamique bien plus large "
        f"({al_ko._ref_hi:.3f} contre {al_ok._ref_hi:.3f})")
verifie(med_ko * 5.0 < med_ok,
        f"la brute est tassée dans les BAS niveaux 8 bits par la référence "
        f"composite ({med_ko:.1f}/255 contre {med_ok:.1f}/255) — c'est la "
        f"cécité de l'ORB")


# ================================================= [4] rejeu « session »
print("[4] rejeu : 12 frames alignées après un rafraîchissement de référence")
suite = [champ(DXS[i][0], DXS[i][1], graine=200 + i) for i in range(12)]


def rejoue(reference):
    """Nombre de refus en alignant les 12 frames sur `reference`."""
    al = StarAligner()
    al.set_reference(reference)
    return sum(1 for f in suite if not al.compute(f)[1])


refus_ko = rejoue(ref_ko)
refus_ok = rejoue(ref_ok)
print(f"    composite : {refus_ko}/12 refus  ·  couche : {refus_ok}/12 refus")
verifie(refus_ok == 0,
        f"couche de rôle : 0 refus sur 12 frames (reçu {refus_ok})")
verifie(refus_ko > refus_ok,
        f"composite normalisé : plus de refus (reçu {refus_ko}/12)")

root.destroy()
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
