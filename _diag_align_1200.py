# -*- coding: utf-8 -*-
"""DIAGNOSTIC JETABLE — rejoue l'alignement de l'appli sur un dossier de brutes
réelles et imprime, frame par frame, ce qui se passe.

Usage :  python _diag_align_1200.py <dossier> [nb_max]

Rejoue EXACTEMENT le pipeline de l'appli (load_image CFA « Auto » →
StarAligner ORB+RANSAC avec repli corrélation de phase) puis, en parallèle,
une approche par CENTROÏDES D'ÉTOILES (détection type jalon 10, vote de
translation par histogramme de paires, RANSAC affine) pour comparer les deux.
But : comprendre l'échec d'alignement constaté par Alain en réel (étoiles
« en plusieurs points puis trainées », C8 + 0.63 → 1280 mm, Uranus-C Pro,
poses 120 s). Aucune modification du code de l'appli ici.
"""

import os
import sys
import glob
import math
import time

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from avastack.images import load_image, save_image      # noqa: E402
from avastack.processing.alignment import StarAligner   # noqa: E402
from avastack.processing.stacking import LiveStacker    # noqa: E402


def positions_etoiles(img, seuil_sigma=8.0, max_etoiles=300):
    """Centroïdes d'étoiles (détection grossière du jalon 10, sans FWHM)."""
    mono = img.mean(axis=2) if img.ndim == 3 else img
    f = mono.astype(np.float32)
    fond = float(np.median(f))
    bruit = 1.4826 * float(np.median(np.abs(f - fond)))
    if bruit <= 1e-9:
        return np.zeros((0, 2), np.float32)
    masque = (f > fond + seuil_sigma * bruit).astype(np.uint8)
    nb, _, stats, _ = cv2.connectedComponentsWithStats(masque, connectivity=8)
    h, w = f.shape
    cands = []
    for i in range(1, nb):
        x, y = int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP])
        bw, bh = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
        aire = int(stats[i, cv2.CC_STAT_AREA])
        if aire < 2 or aire > 400:
            continue
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            continue
        pic = float(f[y:y + bh, x:x + bw].max())
        cands.append((pic, x, y, bw, bh))
    cands.sort(key=lambda c: -c[0])
    pos = []
    for _pic, x, y, bw, bh in cands[:max_etoiles]:
        sub = np.clip(f[y:y + bh, x:x + bw] - fond, 0, None)
        s = float(sub.sum())
        if s <= 0:
            pos.append((x + bw / 2.0, y + bh / 2.0))
            continue
        ys, xs = np.mgrid[y:y + bh, x:x + bw]
        pos.append((float((xs * sub).sum() / s), float((ys * sub).sum() / s)))
    return np.array(pos, np.float32).reshape(-1, 2)


def align_etoiles(pos_ref, pos_cur, search=150.0, tol=3.0):
    """Translation votée (histogramme 2D des paires) puis RANSAC affine.
    → (M, n_inliers, info) ; M None si échec."""
    if len(pos_ref) < 6 or len(pos_cur) < 6:
        return None, 0, "trop peu d'étoiles"
    d = pos_ref[None, :, :] - pos_cur[:, None, :]      # (Ncur, Nref, 2)
    ok = (np.abs(d[..., 0]) <= search) & (np.abs(d[..., 1]) <= search)
    if not ok.any():
        return None, 0, "aucune paire dans la fenêtre"
    dv = d[ok]                                         # (P, 2)
    bins = max(4, int(2 * search / 4.0))
    H2, xe, ye = np.histogram2d(dv[:, 0], dv[:, 1], bins=bins,
                                range=[[-search, search], [-search, search]])
    i, j = np.unravel_index(np.argmax(H2), H2.shape)
    tx = 0.5 * (xe[i] + xe[i + 1])
    ty = 0.5 * (ye[j] + ye[j + 1])
    ii, jj = np.where((np.abs(d[..., 0] - tx) <= tol)
                      & (np.abs(d[..., 1] - ty) <= tol))
    if len(ii) < 6:
        return None, len(ii), f"pic ({tx:.1f},{ty:.1f}) mais {len(ii)} paires"
    M, inl = cv2.estimateAffinePartial2D(pos_cur[ii], pos_ref[jj],
                                         method=cv2.RANSAC,
                                         ransacReprojThreshold=3.0,
                                         maxIters=5000)
    if M is None or inl is None:
        return None, len(ii), "RANSAC affine échoué"
    n_inl = int(inl.sum())
    if n_inl < 6:
        return None, len(ii), f"RANSAC {n_inl} inliers"
    return M, n_inl, f"pic ({tx:.1f},{ty:.1f}) px"


def mat_infos(M):
    a, b = float(M[0, 0]), float(M[1, 0])
    echelle = math.hypot(a, b)
    angle = math.degrees(math.atan2(b, a))
    return angle, echelle, float(M[0, 2]), float(M[1, 2])



def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    dossier = sys.argv[1]
    nb_max = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    fs = sorted(glob.glob(os.path.join(dossier, "*.fits")),
                key=lambda p: (os.path.getmtime(p), p))[:nb_max]
    print(f"{len(fs)} frames (ordre mtime, comme l'appli)")
    t0 = time.perf_counter()
    images = [load_image(p) for p in fs]
    noms = [os.path.basename(p) for p in fs]
    print(f"lecture : {time.perf_counter() - t0:.1f} s")

    def passe(ref_idx, indices, titre, empiler=False):
        print(f"\n=== {titre} ===")
        print(f"    référence = frame [{ref_idx}] {noms[ref_idx]}")
        aligner = StarAligner()
        aligner.set_reference(images[ref_idx])
        pos_ref = positions_etoiles(images[ref_idx])
        ref_g = aligner.ref_gray.astype(np.float32)
        stacker = None
        if empiler:
            stacker = LiveStacker(images[ref_idx].shape, k=None)
            stacker.wb_auto = True       # comme la case cochée de l'appli
        print(f"    référence : {len(pos_ref)} étoiles, "
              f"{len(aligner.ref_kp)} keypoints ORB")
        t_prev = None
        n_ok = n_refus = 0
        n_meth = {}
        n_frames = n_bad = 0            # compteurs du rafraîchissement auto
        for k in indices:
            img = images[k]
            g = aligner._norm8(img, aligner._ref_lo, aligner._ref_hi)
            kp, des = aligner.orb.detectAndCompute(g, None)
            n_kp = 0 if kp is None else len(kp)
            n_m = 0
            if aligner.ref_des is not None and des is not None and n_kp > 0:
                good = [p[0] for p in aligner.bf.knnMatch(aligner.ref_des, des, k=2)
                        if len(p) == 2 and p[0].distance < aligner.ratio * p[1].distance]
                n_m = len(good)
            M, okk = aligner.compute(img)
            methode = (aligner.dernier or {}).get("methode", "refus")
            if okk:
                n_ok += 1
                n_meth[methode] = n_meth.get(methode, 0) + 1
            else:
                n_refus += 1
            a, e, dx, dy = mat_infos(M)
            # La matrice améliore-t-elle VRAIMENT l'accord (contrôle) ?
            warp = cv2.warpAffine(g, M, (g.shape[1], g.shape[0]))
            ssd_id = float(np.mean((g - ref_g) ** 2))
            ssd_w = float(np.mean((warp - ref_g) ** 2))
            verdict = ("améliore" if ssd_w < 0.9 * ssd_id
                       else "AGGRAVE" if ssd_w > 1.1 * ssd_id
                       else "inutile")
            saut = ("" if t_prev is None
                    else f" Δt=({dx - t_prev[0]:+6.1f},{dy - t_prev[1]:+6.1f})")
            t_prev = (dx, dy)
            print(f"[{k:2d}] {noms[k]}  kp={n_kp:4d} match={n_m:4d} "
                  f"{'OK  ' if okk else 'REFUS'} {methode:7s} "
                  f"a={a:+7.2f}° e={e:.3f} dx={dx:+8.1f} dy={dy:+8.1f} | "
                  f"SSD id={ssd_id:.5f} warp={ssd_w:.5f} → {verdict}{saut}")
            if stacker is None:
                continue
            # --- simulation exacte de l'appli (jalon 13) ---------------
            if okk:
                aligned = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                                         flags=cv2.INTER_LINEAR)
                stacker.add(aligned)
                stacker.note_alignement(M)
                n_bad = 0
            else:
                n_bad += 1
                if stacker.n <= 2 and n_bad >= 3:   # dossier mixé (comme l'appli)
                    aligner.set_reference(img)
                    n_frames = n_bad = 0
                    print("      → référence recalée sur la frame courante "
                          "(empilement quasi vide : dossier mixé)")
            n_frames += 1
            if (n_frames >= 20 or (n_bad >= 3 and 2 * n_bad >= n_frames)) \
                    and stacker.n > 0:      # rien d'empilé → rien à rafraîchir
                aligner.set_reference(stacker.mean(recadre=False))
                n_frames = n_bad = 0
                print(f"      → référence rafraîchie (empilement complet, "
                      f"{stacker.n} frames)")
        if stacker is not None:
            stack = stacker.mean()          # recadrée + équilibrée (jalon 13)
            save_image("_diag_stack_4565.fit", stack)
            f32 = stack.astype(np.float32)
            lo, hi = np.percentile(f32, 20.0), np.percentile(f32, 99.9)
            x = np.clip((f32 - lo) / max(hi - lo, 1e-9), 0.0, 1.0) ** 0.5
            buf_ok, buf = cv2.imencode(".png", (x * 65535).astype(np.uint16))
            if buf_ok:
                buf.tofile("_diag_stack_4565.png")
            print(f"    EMPILEMENT RÉEL sauvegardé : _diag_stack_4565.fit/.png "
                  f"({stacker.n} frames, recadré {stack.shape[1]}×"
                  f"{stack.shape[0]}, équilibré)")
        print(f"    BILAN passe : OK={n_ok} {n_meth} REFUS={n_refus}")

    passe(0, range(1, len(fs)),
          "PASSÉE 1 : simulation EXACTE de l'appli (référence = 1re frame du "
          "03/06, rafraîchissement auto, équilibrage) + empilement réel",
          empiler=True)
    if len(fs) > 2:
        passe(1, range(2, len(fs)),
              "PASSÉE 2 : référence = 1re frame du 07/06 (même nuit)")


if __name__ == "__main__":
    main()