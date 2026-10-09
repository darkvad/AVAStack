# -*- coding: utf-8 -*-
"""DIAGNOSTIC — orientation RÉELLE (0° vs 180°) + montage visuel."""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import numpy as np
import cv2
from avastack.processing import stars as st_mod
from avastack.processing.composition import extraire_canal
import avastack.images as images

L = ('//192.168.155.45/Telechargements/Astro/SV555/NINA/2026-09-13/Soiree_20260913/'
     'Andromeda Nebula/LIGHT/QHYminiCam8M/Full Resolution/1x1/60.00/-15.00/90/25/L/'
     '2026-09-13_04-43-00_L_-14.90_60.00s_0000.fits')
B = ('//192.168.155.45/Telechargements/Astro/SV555/NINA/2026-09-22/Soiree_20260922/'
     'Andromeda Nebula/LIGHT/QHYminiCam8M/Full Resolution/1x1/60.00/-15.00/90/25')
C = {'R_debut': B + '/R/2026-09-22_23-53-00_R_-14.90_60.00s_0066.fits',
     'R_fin': B + '/R/2026-09-23_03-17-07_R_-15.00_60.00s_0115.fits',
     'G_debut': B + '/G/2026-09-22_23-55-52_G_-15.00_60.00s_0060.fits'}


def charge(p):
    return extraire_canal(np.asarray(images.load_image(p), np.float32), "L")


def points(img):
    pos, _ = st_mod.detecter_positions(img, max_etoiles=200)
    return np.asarray(pos, np.float64)


def vote(ref, cur, retourne, h, w, rayon=3.0):
    """Compte les étoiles appariées pour translation seule (0°) ou 180°."""
    c = cur.copy()
    if retourne:
        c[:, 0] = (w - 1) - c[:, 0]
        c[:, 1] = (h - 1) - c[:, 1]
    d = ref[None, :, :] - c[:, None, :]
    H2, xe, ye = np.histogram2d(d[..., 0].ravel(), d[..., 1].ravel(), bins=40)
    i, j = np.unravel_index(np.argmax(H2), H2.shape)
    tx = 0.5 * (xe[i] + xe[i + 1])
    ty = 0.5 * (ye[j] + ye[j + 1])
    dd = np.hypot(d[..., 0] - tx, d[..., 1] - ty)
    return int((dd.min(1) <= rayon).sum()), tx, ty


ref_img = charge(L)
ref_pos = points(ref_img)
h, w = ref_img.shape
print(f"Référence : {os.path.basename(L)} — {len(ref_pos)} étoiles détectées")
print()
for nom, p in C.items():
    img = charge(p)
    pos = points(img)
    n0, tx0, ty0 = vote(ref_pos, pos, False, h, w)
    n180, tx1, ty1 = vote(ref_pos, pos, True, h, w)
    print(f"{nom:9s} {os.path.basename(p)}")
    print(f"          étoiles={len(pos):3d} | appariées 0°={n0:3d} "
          f"(Δ={tx0:+.0f},{ty0:+.0f}) | 180°={n180:3d} (Δ={tx1:+.0f},{ty1:+.0f})")
print()

W = 430
panneaux = []
for titre, img in (("REF L 13/09", ref_img),
                   ("R 22/09 23:53 (tel quel)", charge(C['R_debut'])),
                   ("R 22/09 23:53 TOURNÉ 180°", cv2.rotate(charge(C['R_debut']),
                                                           cv2.ROTATE_180))):
    hh, ww = img.shape
    p = cv2.resize(img, (W, int(hh * W / ww)), interpolation=cv2.INTER_AREA)
    lo, hi = np.percentile(p, (1.0, 99.5))
    v = np.clip((p - lo) / max(1e-9, hi - lo), 0, 1)
    u8 = (np.sqrt(v) * 255).astype(np.uint8)
    rgb = cv2.cvtColor(u8, cv2.COLOR_GRAY2BGR)
    cv2.putText(rgb, titre, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (0, 255, 0), 2)
    panneaux.append(rgb)
montage = np.hstack(panneaux)
out = os.path.join(os.environ.get("TEMP", "."), "diag_montage2.jpg")
cv2.imwrite(out, montage, [cv2.IMWRITE_JPEG_QUALITY, 68])
print("Montage :", out, montage.shape)
