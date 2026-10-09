# -*- coding: utf-8 -*-
"""DIAGNOSTIC — VÉRITÉ géométrique entre la référence et une frame.

Pourquoi : sur les vraies données d'Alain, des frames R/G/B sont REFUSÉES
alors qu'elles recouvrent la même cible (M31). Ce script MESURE la relation
réelle SANS le garde-fou `_M_valide` : il cherche la meilleure transformation
par appariement de triangles (invariants = rotation/échelle éliminées) et
affiche l'ANGLE, l'ÉCHELLE et le NOMBRE D'ÉTOILES. Il indique aussi combien
d'étoiles sont détectées dans chaque image — une frame pauvre en étoiles
explique un refus.

Usage :
  python bancs/_diag_align_verite.py <REF> <IMG1> [<IMG2> ...]
    où REF = une brute de référence (ex. une L), IMG* = des brutes à mesurer.
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys

import numpy as np
import cv2

from avastack.processing import alignment as al_mod
from avastack.processing import stars as st_mod
from avastack.processing.composition import extraire_canal, role_de_filtre
import avastack.images as images

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def charger(chemin, role):
    a = np.asarray(images.load_image(chemin), np.float32)
    return extraire_canal(a, role)


def angle_verite(ref_pos, pos, tri_pairs_max=2000):
    """Meilleure transformation par triangles SANS `_M_valide`.

    → (n_inliers, angle, échelle, dx, dy, nb_paires) ou None."""
    inv_r, som_r, _ = al_mod._invariants_triangles(ref_pos)
    inv_c, som_c, _ = al_mod._invariants_triangles(pos)
    if inv_r is None or inv_c is None:
        return None
    ecart = np.abs(inv_r[:, None, :] - inv_c[None, :, :]).max(-1)
    paires = np.argwhere(ecart <= al_mod.TRI_TOL)
    if not len(paires):
        return None
    if len(paires) > tri_pairs_max:
        ordre = np.argsort(ecart[paires[:, 0], paires[:, 1]])[:tri_pairs_max]
        paires = paires[ordre]
    p_ref = np.asarray(ref_pos, np.float32)
    p_cur = np.asarray(pos, np.float32)
    best = None
    for ir, ic in paires:
        M0 = cv2.getAffineTransform(p_cur[som_c[ic]].astype(np.float32),
                                    p_ref[som_r[ir]].astype(np.float32))
        if M0 is None or not np.isfinite(M0).all():
            continue
        ang, ech, dx, dy = al_mod.infos_M(M0)
        if not (0.5 <= ech <= 2.0):          # borne LARGE (pas _M_valide)
            continue
        pc = cv2.transform(p_cur.reshape(-1, 1, 2), M0)[:, 0, :]
        d2 = np.hypot(pc[:, None, 0] - p_ref[None, :, 0],
                      pc[:, None, 1] - p_ref[None, :, 1])
        n = int((d2.min(1) <= al_mod.TRI_RAYON).sum())
        if best is None or n > best[0]:
            best = (n, ang, ech, dx, dy, len(paires))
    return best


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ref_path, cibles = argv[0], argv[1:]
    role_ref = role_de_filtre(images.lire_filtre_fits(ref_path)) or "L"
    ref = charger(ref_path, role_ref)
    ref_pos, msg = st_mod.detecter_positions(ref, max_etoiles=al_mod.MAX_ALIGN_ETOILES)
    print(f"RÉFÉRENCE : {os.path.basename(ref_path)} (rôle {role_ref}) — "
          f"{len(ref_pos)} étoiles « {msg} »")
    print()
    for chemin in cibles:
        try:
            img = charger(chemin, role_ref)
        except Exception as exc:
            print(f"{os.path.basename(chemin):44s} ILLISIBLE ({exc})")
            continue
        pos, msg = st_mod.detecter_positions(img, max_etoiles=al_mod.MAX_ALIGN_ETOILES)
        b = angle_verite(ref_pos, pos)
        nom = os.path.basename(chemin)
        if b is None:
            print(f"{nom:44s} {len(pos):3d} étoiles — AUCUN triangle apparié "
                  f"« {msg} »")
            continue
        n, ang, ech, dx, dy, np_ = b
        verdict = ("≈0° (même sens)" if abs(ang) < 30
                   else "≈180° (RETOURNÉ)" if abs(abs(ang) - 180) < 30
                   else "AUTRE")
        print(f"{nom:44s} {len(pos):3d} étoiles | meilleur appariement : "
              f"angle={ang:+8.2f}° ({verdict}) éch={ech:.4f} "
              f"n_inliers={n:3d} (paires={np_})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
