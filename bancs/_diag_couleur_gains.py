# -*- coding: utf-8 -*-
r"""Que font les GAINS photométriques à la couleur d'une image réelle ?

Mesure, sur des canaux réellement empilés :
  1. l'état de chaque canal (fond médian, saturation, dynamique) ;
  2. les zéro-points Gaia par bande + leur DISPERSION (fiabilité) ;
  3. les gains relatifs qui en découlent ;
  4. l'effet RÉEL de ces gains sur la couleur du FOND (hors étoiles) et sur
     celle des étoiles — c'est-à-dire ce que l'utilisateur voit à l'écran.

Usage : python bancs/_diag_couleur_gains.py R=<f> G=<f> B=<f> [--ra deg --dec deg
        --champ deg]
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import argparse
import sys

import numpy as np

from avastack.catalogues.astap import resoudre_avec_astap
from avastack.images import load_image
from avastack.processing import photometrie as PH

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def principal():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("canaux", nargs="+", help="BANDE=chemin (ex. R=canal_R.fit)")
    ap.add_argument("--ra", type=float, default=None)
    ap.add_argument("--dec", type=float, default=None)
    ap.add_argument("--champ", type=float, default=None)
    a = ap.parse_args()

    canaux = {}
    for spec in a.canaux:
        b, _, p = spec.partition("=")
        canaux[b.strip().upper()] = load_image(p.strip())
    bandes = sorted(canaux)
    h, w = canaux[bandes[0]].shape[:2]
    print(f"canaux {bandes} — grille {h}×{w}")

    # --- 1) état de chaque canal ------------------------------------------
    print("\n[1] état de chaque canal")
    for b in bandes:
        im = np.asarray(canaux[b], dtype=np.float64)
        fin = np.isfinite(im)
        med = float(np.median(im[fin]))
        sat = float((im[fin] >= 0.999).mean())
        print(f"    {b} : fond médian {med:.5f} ; max {np.max(im[fin]):.4f} ; "
              f"pixels saturés {100.0 * sat:.3f} %")

    # --- 2) zéro-points Gaia par bande ------------------------------------
    print("\n[2] zéro-points Gaia par bande (fiabilité = rms en magnitude)")
    if a.ra is not None and a.dec is not None and a.champ:
        import os
        import tempfile
        with tempfile.TemporaryDirectory(prefix="diag_gr_") as tmp:
            from avastack.images import borner_lineaire, save_image
            copie = os.path.join(tmp, "b.fits")
            save_image(copie, borner_lineaire(np.asarray(canaux[bandes[0]]))[0])
            wcs, msg = resoudre_avec_astap(copie, ra0=a.ra, dec0=a.dec,
                                           rayon_deg=1.0,
                                           fov_deg=a.champ * h / w,
                                           dossier_sortie=tmp, timeout=180)
        if wcs is None:
            print(f"    ASTAP : ÉCHEC — {msg}")
            return 1
        ph = PH.Photometrie()
        res, msg = ph.mesurer(canaux, wcs, (h, w))
        if res is None:
            print(f"    mesure impossible : {msg}")
            return 1
        for b, d in sorted(res["bandes"].items()):
            print(f"    {b} : ZP {d['zp']:.3f} ; dispersion {d['rms_mag']:.3f} "
                  f"mag ; {d['n']} étoiles gardées / {d['n_mutuels']} "
                  f"appariées ; d_px {d['d_px']:.2f} ; "
                  f"G {d['mag_min']:.1f}→{d['mag_max']:.1f}")
        print(f"    gains relatifs : "
              + ", ".join(f"{b} ×{g:.4f}" for b, g in sorted(res["gains"].items())))
        print(f"    ({msg})")

        # --- 3) effet des gains sur la COULEUR ---------------------------
        print("\n[3] effet des gains sur la couleur (R, G, B moyennés)")
        gains = res["gains"]
        fac = np.array([float(gains.get(b, 1.0)) for b in ("R", "G", "B")])
        print(f"    facteurs appliqués R/G/B : {fac[0]:.4f} / {fac[1]:.4f} / "
              f"{fac[2]:.4f}  (rapport B/R multiplié par "
              f"{fac[2] / fac[0]:.3f})")
        # fond : bande de 30 lignes en haut, sans galaxie supposée au centre
        fond = np.array([float(np.median(np.asarray(canaux[b])[:30, :]))
                         for b in ("R", "G", "B")])
        if fond.min() > 0:
            rel = fond / fond.max()
            print(f"    fond médian par canal (hors centre) : R {fond[0]:.5f} / "
                  f"G {fond[1]:.5f} / B {fond[2]:.5f}")
            print(f"    dominante du fond AVANT gains : R {rel[0]:.2f} / "
                  f"G {rel[1]:.2f} / B {rel[2]:.2f}")
            apres = fond * fac
            rel2 = apres / apres.max()
            print(f"    dominante du fond APRÈS gains : R {rel2[0]:.2f} / "
                  f"G {rel2[1]:.2f} / B {rel2[2]:.2f}  → "
                  f"{'PLUS bleu' if rel2[2] / rel2[0] > rel[2] / rel[0] else 'moins bleu'} "
                  f"(B/R {rel[2] / rel[0]:.3f} → {rel2[2] / rel2[0]:.3f})")

    # --- 4) CHROMATISME : décalage des étoiles ENTRE canaux ----------------
    # Mesure indépendante du WCS (plus proche voisin mutuel) : un décalage
    # SYSTÉMATIQUE d'un canal par rapport aux autres produit des franges
    # colorées autour des étoiles (rouge d'un côté, cyan de l'autre) —
    # constat réel du 24/09/2026 : canal R décalé de 0,61 px (1,5″) par
    # rapport à G (B et G alignés à 0,05 px).
    print("\n[4] décalage des étoiles ENTRE canaux (chromatisme)")
    pos = {}
    for b in bandes:
        pos[b], _f, _m = PH.etoiles_image(canaux[b])

    def paires(b1, b2, rayon=3.0):
        a, c = pos.get(b1), pos.get(b2)
        if a is None or c is None or not len(a) or not len(c):
            return np.zeros(0, np.int64), np.zeros(0, np.int64)
        d = np.hypot(a[:, None, 0] - c[None, :, 0],
                     a[:, None, 1] - c[None, :, 1])
        ja = d.argmin(1)
        da = d[np.arange(len(a)), ja]
        ib = d.argmin(0)
        sel = (da <= rayon) & (ib[ja] == np.arange(len(a)))
        return np.flatnonzero(sel), ja[sel]

    if "G" in pos:
        ref = "G"
    else:
        ref = bandes[0]
    for b in bandes:
        if b == ref:
            continue
        ia, ic = paires(b, ref)
        if not len(ia):
            print(f"    {b} vs {ref} : aucun appariement")
            continue
        dx = pos[b][ia, 0] - pos[ref][ic, 0]
        dy = pos[b][ia, 1] - pos[ref][ic, 1]
        d = np.hypot(dx, dy)
        verdict = ("ALIGNÉS" if d.mean() < 0.15
                   else "DÉCALAGE à corriger (franges colorées)")
        print(f"    {b} vs {ref} : {len(ia)} étoiles ; dX {dx.mean():+.3f}±"
              f"{dx.std():.3f} ; dY {dy.mean():+.3f}±{dy.std():.3f} ; "
              f"distance {d.mean():.3f} px ({verdict})")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
