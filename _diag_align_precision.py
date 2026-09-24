# -*- coding: utf-8 -*-
r"""Précision (et BIAIS) des chemins d'alignement sur de VRAIES couches.

Contexte — constat réel d'Alain du 24/09/2026 : l'astrométrie et la
photométrie Gaia d'un empilement M31 (31 frames, R+G+B) sont justes, mais
l'image montre des FRANGES colorées autour des étoiles. Mesure : la couche
ROUGE sort décalée de 0,612 px (dX -0,207±0,231 ; dY -0,534±0,116 px) par
rapport à G, tandis que B/G sont alignés à 0,049 px — décalage
SYSTÉMATIQUE (σ 0,12 px) et donc corrigeable.

Les fichiers « canal_<rôle>.fit » et le composite sont écrits depuis la
MÊME grille (même cadre commun, même `stacker.moyennes()`) : le décalage
naît donc DANS l'empilement — c'est-à-dire dans l'alignement des frames.

Cet outil mesure, sur des canaux réellement empilés :
  1. la VÉRITÉ (décalage des étoiles entre deux couches, appariement
     mutuel, indépendant du WCS) — et sa répartition SPATIALE (translation
     globale, ou rotation/échelle ?) ;
  2. la corrélation de phase globale, comme second avis indépendant ;
  3. ce que chaque chemin de StarAligner RETOURNE pour cette paire
     (compute → méthode élue, puis chaque chemin forcé) ;
  4. sa PRÉCISION sur un décalage CONNU (0,15 → 3,4 px) : c'est le biais
     résiduel qui fabrique les franges colorées.

Usage : python _diag_align_precision.py --ref canal_G.fit --frame canal_R.fit
"""
import argparse
import sys

import cv2
import numpy as np

from avastack.images import load_image
from avastack.processing import photometrie as PH
from avastack.processing.alignment import StarAligner

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def etoiles(img):
    """Centroïdes (n, 2) d'une image — le détecteur de la production."""
    pos, _f, _m = PH.etoiles_image(img)
    return np.asarray(pos, np.float64) if pos is not None else np.zeros((0, 2))


def decalage(pa, pb, rayon=3.0):
    """Décalage (dx, dy) de `pa` par rapport à `pb` par plus proche voisin
    MUTUEL (aucun WCS, aucune hypothèse de transformation) : moyenne,
    écart-type et nombre d'appariements."""
    if not len(pa) or not len(pb):
        return None
    d = np.hypot(pa[:, None, 0] - pb[None, :, 0], pa[:, None, 1] - pb[None, :, 1])
    ja = d.argmin(1)
    da = d[np.arange(len(pa)), ja]
    ib = d.argmin(0)
    sel = (da <= rayon) & (ib[ja] == np.arange(len(pa)))
    if int(sel.sum()) < 5:
        return None
    dx = pa[sel, 0] - pb[ja[sel], 0]
    dy = pa[sel, 1] - pb[ja[sel], 1]
    return (float(dx.mean()), float(dy.mean()), float(dx.std()),
            float(dy.std()), int(sel.sum()))


def phase_globale(a, b):
    """Corrélation de phase (Hann + retrait de la médiane) : translation de
    `b` par rapport à `a`, second avis indépendant des centres d'étoiles."""
    h, w = a.shape
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    a0 = (a.astype(np.float32) - float(np.median(a))) * win
    b0 = (b.astype(np.float32) - float(np.median(b))) * win
    (dx, dy), resp = cv2.phaseCorrelate(a0, b0)
    return float(dx), float(dy), float(resp)


def _translation(M):
    if M is None:
        return None
    return float(M[0, 2]), float(M[1, 2])


def principal():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", required=True, help="couche de RÉFÉRENCE (canal_*.fit)")
    ap.add_argument("--frame", required=True, help="couche à aligner (canal_*.fit)")
    ap.add_argument("--cote", type=int, default=1024,
                    help="côté du carré utilisé pour les tests de précision")
    a = ap.parse_args()

    ref = np.asarray(load_image(a.ref), np.float32)
    frame = np.asarray(load_image(a.frame), np.float32)
    print(f"référence {a.ref} {ref.shape} / frame {a.frame} {frame.shape}")

    # --- 1) vérité terrain ------------------------------------------------
    print("\n[1] VÉRITÉ (appariement mutuel d'étoiles, sans WCS)")
    pr, pf = etoiles(ref), etoiles(frame)
    print(f"    étoiles détectées : référence {len(pr)} / frame {len(pf)}")
    v = decalage(pf, pr)
    if v is None:
        print("    aucun appariement — impossible de conclure")
        return 1
    print(f"    frame - référence : dX {v[0]:+.3f}±{v[2]:.3f} ; "
          f"dY {v[1]:+.3f}±{v[3]:.3f} ; {v[4]} appariements "
          f"(distance {np.hypot(v[0], v[1]):.3f} px)")

    # --- 2) répartition SPATIALE du décalage ------------------------------
    print("\n[2] répartition SPATIALE (translation globale ou champ variable ?)")
    h, w = ref.shape
    for (y, x) in [(0, 0), (0, w // 2), (h // 2, 0), (h // 2, w // 2)]:
        c = a.cote
        sr = ref[y:y + c, x:x + c]
        sf = frame[y:y + c, x:x + c]
        if sr.shape != (c, c) or sf.shape != (c, c):
            continue
        q = decalage(etoiles(sf), etoiles(sr))
        if q is None:
            print(f"    zone ({y},{x}) : trop peu d'étoiles")
            continue
        print(f"    zone ({y},{x}) {c}×{c} : dX {q[0]:+.3f}±{q[2]:.3f} ; "
              f"dY {q[1]:+.3f}±{q[3]:.3f} ; {q[4]} appariements")

    # --- 3) second avis : corrélation de phase ----------------------------
    print("\n[3] corrélation de phase (indépendante des étoiles)")
    dxp, dyp, resp = phase_globale(ref, frame)
    print(f"    dX {dxp:+.3f} ; dY {dyp:+.3f} px (réponse {resp:.4f})")

    # --- 4) chemins de l'aligneur sur la paire réelle ---------------------
    print("\n[4] ce que l'ALIGNEUR retourne pour cette paire (reste mesuré "
          "APRÈS application — la translation d'un modèle affine à échelle "
          "≠ 1 n'est PAS le déplacement moyen)")
    al = StarAligner()
    al.set_reference(ref)
    M, ok = al.compute(frame)
    print(f"    méthode RETENUE par compute() : "
          f"{al.dernier['methode'] if ok and al.dernier else 'REFUS'}")
    for nom, fct in (("compute", lambda: (M, ok)),
                     ("triangles", lambda: al._triangles(frame)),
                     ("étoiles", lambda: al._etoiles(frame)),
                     ("phase", lambda: al._phase(
                         al._norm8(frame, al._ref_lo, al._ref_hi)))):
        Mc, okc = fct()
        if Mc is None or not okc:
            print(f"    {nom:10s} → REFUS")
            continue
        t = _translation(Mc)
        corr = cv2.warpAffine(frame, Mc, (frame.shape[1], frame.shape[0]),
                              flags=cv2.INTER_LINEAR)
        res = decalage(etoiles(corr), pr)
        ech = float(np.hypot(Mc[0, 0], Mc[1, 0]))
        suite = ("reste illisible" if res is None
                 else f"reste ({res[0]:+.3f}, {res[1]:+.3f}) px sur "
                      f"{res[4]} étoiles")
        meth = (" [méthode retenue]" if nom == "compute" else "")
        print(f"    {nom:10s} → Δ=({t[0]:+.3f}, {t[1]:+.3f}) ; échelle "
              f"{ech:.5f} ; {suite}{meth}")

    # --- 5) précision sur un décalage CONNU -------------------------------
    # Le cas réel : la frame et la référence diffèrent d'un petit décalage
    # (chromatisme entre filtres). On impose un décalage connu (sous-pixel
    # inclus) et on mesure l'ERREUR RÉSIDUELLE de chaque chemin : c'est
    # exactement ce biais qui décale une couche par rapport à l'autre.
    print("\n[5] précision sur un décalage CONNU (erreur résiduelle après "
          "correction)")
    c = a.cote
    y0, x0 = h // 2 - c // 2, w // 2 - c // 2
    sr = ref[y0:y0 + c, x0:x0 + c]
    sf0 = frame[y0:y0 + c, x0:x0 + c]
    al2 = StarAligner()
    al2.set_reference(sr)
    M_, ok_ = al2.compute(sf0)
    print(f"    zone test ({y0},{x0}) {c}×{c} ; chemin retenu par compute() : "
          f"{al2.dernier['methode'] if ok_ and al2.dernier else 'REFUS'}")
    print("    décalage | vérité mesurée | compute : reste | triangles : reste"
          " | étoiles : reste")
    psr = etoiles(sr)
    for (ddx, ddy) in ((0.15, -0.10), (0.35, -0.25), (0.50, -0.35),
                       (0.80, -0.55), (1.50, -1.00), (3.40, -2.20)):
        Mw = np.array([[1.0, 0.0, ddx], [0.0, 1.0, ddy]])
        sw = cv2.warpAffine(sf0, Mw, (c, c), flags=cv2.INTER_LINEAR)
        pv = decalage(etoiles(sw), psr)
        if pv is None:
            print(f"    ({ddx:+.2f},{ddy:+.2f}) : trop peu d'étoiles")
            continue
        ligne = f"    ({ddx:+.2f},{ddy:+.2f}) | ({pv[0]:+.3f},{pv[1]:+.3f})"
        for nom in ("compute", "triangles", "étoiles"):
            if nom == "compute":
                Mc, okc = al2.compute(sw)
                al2._last_t = None      # pas de continuité entre essais
            elif nom == "triangles":
                Mc, okc = al2._triangles(sw)
            else:
                Mc, okc = al2._etoiles(sw)
            if Mc is None or not okc:
                ligne += " | REFUS     "
                continue
            corr = cv2.warpAffine(sw, Mc, (c, c), flags=cv2.INTER_LINEAR)
            res = decalage(etoiles(corr), psr)
            ligne += (" | ?         " if res is None
                      else f" | ({res[0]:+.3f},{res[1]:+.3f})")
        print(ligne)
    return 0


if __name__ == "__main__":
    sys.exit(principal())


