# -*- coding: utf-8 -*-
"""_diag_png_fits_jalon69.py — LE PNG CORRESPOND-IL AU FITS ?

Alain a livré les deux sorties du même écran (27/09/2026) : le « tel que vu » du
résultat traité en .fits ET en .png. On vérifie, avec des lecteurs INDÉPENDANTS
(cv2 brut pour le PNG, astropy pour le FITS — règle du projet, leçon jalon 62) :

  [1] même géométrie, même sens (identité, pas de miroir) ;
  [2] mêmes valeurs : les deux sortent du MÊME rendu flottant, donc l'écart ne
      doit être QUE la quantification 16 bits (1/65535) ;
  [3] ORDRE DES CANAUX : la comparaison « R du PNG ↔ B du FITS » doit être
      franchement PIRE — c'est le piège qui a produit des PNG bleus pendant des
      mois (imencode attend du BGR, v2.36.1).

Usage : python bancs/_diag_png_fits_jalon69.py [fichier.png fichier.fits]
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PNG = r"C:\Astro\test\m31_traite_externe_etire-v2.38.2.png"
FITS = r"C:\Astro\test\m31_traite_externe_etire-v2.38.2.fits"
_args = [a for a in sys.argv[1:] if not a.startswith("-")]
if len(_args) >= 2:
    PNG, FITS = _args[0], _args[1]

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


from astropy.io import fits

print("=" * 78)
print("[1] lecture par des lecteurs INDÉPENDANTS")
print("=" * 78)
png = cv2.imdecode(np.fromfile(PNG, np.uint8), cv2.IMREAD_UNCHANGED)
if png is None:
    print("  PNG illisible :", PNG)
    raise SystemExit(2)
dtype_png = png.dtype
if png.ndim == 3 and png.shape[2] == 3:
    png = cv2.cvtColor(png, cv2.COLOR_BGR2RGB)      # convention OpenCV
elif png.ndim == 3 and png.shape[2] == 4:
    png = cv2.cvtColor(png, cv2.COLOR_BGRA2RGB)
a = np.asarray(png).astype(np.float32)
a = a / (65535.0 if dtype_png == np.uint16 else 255.0)
d = np.asarray(fits.getdata(FITS))
if d.ndim == 3 and d.shape[0] <= 4 and d.shape[-1] > 4:
    d = np.ascontiguousarray(np.transpose(d, (1, 2, 0)))
b = np.asarray(d, np.float32)
print(f"  PNG  : {PNG}\n         {png.shape} · {dtype_png} "
      f"· min {a.min():.5f} max {a.max():.5f}")
print(f"  FITS : {FITS}\n         {b.shape} · {b.dtype} "
      f"· min {b.min():.5f} max {b.max():.5f}")
verifie(a.shape == b.shape, "même géométrie")

print()
print("=" * 78)
print("[2] même image ? (l'écart ne doit être QUE la quantification 16 bits)")
print("=" * 78)
if a.shape == b.shape:
    diff = a - b
    pire = float(np.max(np.abs(diff)))
    moyen = float(np.mean(np.abs(diff)))
    print(f"    écart max {pire:.6f} niveau ({pire * 65535:.2f}/65535) · "
          f"moyen {moyen:.7f} ({moyen * 65535:.3f}/65535)")
    verifie(pire <= 1.0 / 65535.0 + 1e-6,
            "écart ≤ 1 niveau sur 65535 (les deux sortent du même rendu)")
    # sens : le PNG ne doit pas être retourné par rapport au FITS
    g_p = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    g_f = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    ech = max(1, g_p.shape[0] // 200)
    s_p = g_p[::ech, ::ech]
    s_f = g_f[::ech, ::ech]

    def corr(x, y):
        x, y = x - x.mean(), y - y.mean()
        den = np.sqrt((x * x).sum() * (y * y).sum())
        return float((x * y).sum() / den) if den > 0 else 0.0

    c_meme, c_miroir = corr(s_p, s_f), corr(s_p, s_f[::-1])
    print(f"    orientation : identité {c_meme:+.4f} · miroir V {c_miroir:+.4f}")
    verifie(c_meme > c_miroir, "même sens dans les deux fichiers")

print()
print("=" * 78)
print("[3] ordre des canaux (le piège « PNG bleu »)")
print("=" * 78)
if a.shape == b.shape:
    juste = float(np.mean(np.abs(a - b)))
    permute = float(np.mean(np.abs(a[..., [2, 1, 0]] - b)))
    print(f"    écart moyen R↔R/B↔B : {juste:.7f} · R↔B permuté : "
          f"{permute:.7f} (×{permute / max(1e-9, juste):.1f})")
    verifie(permute > 20 * juste,
            "les canaux sont dans le BON ordre (une permutation serait "
            "évidente)")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
