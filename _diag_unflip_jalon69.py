# -*- coding: utf-8 -*-
"""_diag_unflip_jalon69.py — pourquoi `auto_unflip` N'A PAS redressé l'externe ?

Constat (27/09/2026) : le résultat du ⚡ (chaîne EXTERNE) est en MIROIR vertical
par rapport à l'empilement, dans v2.38.0 COMME v2.38.1 — alors que
`images.auto_unflip(proc, ref)` est justement prévu pour ça (comparaison à
l'empilement, redressement si le miroir corrèle nettement mieux : +0,05).

Ce banc applique la FONCTION RÉELLE (`avastack.images.auto_unflip`) au couple
réel « empilement linéaire / résultat externe linéaire », puis mesure
l'orientation qui en sort, en imprimant les deux corrélations que la fonction
calcule (ce qu'elle voit, avec SON sous-échantillonnage).

Usage : python _diag_unflip_jalon69.py
"""
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.images import auto_unflip, load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EMPILEMENT = r"C:\Astro\test\M31_traite_lineaire_2.38.0.fits"
EXTERNE = r"C:\Astro\test\m31_traite_externe_lineaire-v2.38.0.fits"
ECH = 8

ref = np.asarray(load_image(EMPILEMENT), np.float32)
ext = np.asarray(load_image(EXTERNE), np.float32)
print("=" * 78)
print("CE QUE `auto_unflip` CALCULE (sa propre formule, imprimée)")
print("=" * 78)
a = ext if ext.ndim == 2 else ext.mean(axis=2)
b = ref if ref.ndim == 2 else ref.mean(axis=2)
print(f"  formes : externe {a.shape} · empilement {b.shape}")
if a.shape == b.shape:
    sa = a[::max(1, a.shape[0] // 256), ::max(1, a.shape[1] // 256)]
    sb = b[::max(1, b.shape[0] // 256), ::max(1, b.shape[1] // 256)]
    sa, sb = sa.astype(np.float64), sb.astype(np.float64)

    def corr(x, y):
        x, y = x - x.mean(), y - y.mean()
        d = np.sqrt((x * x).sum() * (y * y).sum())
        return float((x * y).sum() / d) if d > 0 else 0.0

    c_same = corr(sa, sb)
    c_mir = corr(sa, sb[::-1])
    print(f"  sous-échantillonnage {sa.shape} (pas {max(1, a.shape[0] // 256)}"
          f"×{max(1, a.shape[1] // 256)} px, comme la fonction)")
    print(f"  corrélation telle quelle : {c_same:+.4f}")
    print(f"  corrélation en miroir V  : {c_mir:+.4f}   "
          f"(gain {c_mir - c_same:+.4f} — il faut > +0,05 pour redresser)")
    print(f"  → la fonction devrait "
          f"{'REDRESSER' if c_mir > c_same + 0.05 else 'NE PAS toucher'}")
    print(f"  amplitude : empilement min/max {b.min():.4f}/{b.max():.4f} "
          f"· externe min/max {a.min():.4f}/{a.max():.4f}")

print()
print("=" * 78)
print("EFFET RÉEL DE LA FONCTION SUR LE COUPLE")
print("=" * 78)
corrige = np.asarray(auto_unflip(ext, ref), np.float32)
print(f"  auto_unflip a-t-il retourné l'image ? "
      f"{'OUI (miroir appliqué)' if not np.allclose(
          corrige[..., :3], ext[..., :3]) else 'NON (image inchangée)'}")


def prep(img):
    lum = img if img.ndim == 2 else img.mean(axis=2)
    bas, haut = float(np.percentile(lum, 0.5)), float(np.percentile(lum, 99.5))
    x = np.sqrt(np.clip((lum - bas) / max(1e-9, haut - bas), 0.0, 1.0))
    s = cv2.resize(x, (x.shape[1] // ECH, x.shape[0] // ECH),
                   interpolation=cv2.INTER_AREA)
    m = float(np.median(s))
    return (s - m) / max(1e-6, 1.4826 * float(np.median(np.abs(s - m))))


r = prep(ref)
cote = 160
y0, x0 = (r.shape[0] - cote) // 2, (r.shape[1] - cote) // 2
mot = np.ascontiguousarray(r[y0:y0 + cote, x0:x0 + cote], np.float32)
for nom, img in (("AVANT auto_unflip", ext),
                 ("APRÈS auto_unflip", corrige)):
    c = prep(img)
    sc = []
    for mir in (0, 1):
        t = c[::-1] if mir else c
        sc.append(float(cv2.minMaxLoc(cv2.matchTemplate(
            np.ascontiguousarray(t, np.float32), mot,
            cv2.TM_CCOEFF_NORMED))[1]))
    print(f"  {nom:<18} : corrélation tel quel {sc[0]:+.3f} · "
          f"en miroir {sc[1]:+.3f} → "
          f"{'DROIT' if sc[0] >= sc[1] else 'EN MIROIR'}")
