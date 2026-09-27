# -*- coding: utf-8 -*-
"""Diag — QUE CONTIENNENT les fichiers d'empilement (brut vs traité) ?

Répond, chiffres en main, aux questions du type « pourquoi l'image est-elle
bleue / bruitée ? » quand on compare les fichiers écrits par AVAStack :

  • par CANAL : médiane (fond), σ robuste (MAD×1,4826 = le BRUIT), percentiles ;
  • le RAPPORT traité/brut par canal (ce que la chaîne de sortie a réellement
    appliqué) et le rapport aux COUCHES BRUTES (canal_R/G/B.fit) — c'est ce
    rapport qui dit si les coefficients SPCC ont été appliqués sur la BONNE
    base d'échelle ;
  • le mot-clé AVAAPPLI et les autres clés AVA* (l'en-tête dit-il vrai ?) ;
  • le contraste de FOND entre canaux (R/G, B/G) : c'est lui qui décide de
    l'aspect « bleu/vert » avant étirement.

Usage :
  python bancs/_diag_empilement_couleur.py <fichier.fits> [<autre.fits> …]
  python bancs/_diag_empilement_couleur.py --couches canal_R.fit canal_G.fit canal_B.fit
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

import numpy as np

from avastack.images import load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLES = ("AVACOMPO", "AVAAPPLI", "AVASPCC", "AVAGAIA", "AVAWB", "AVAFIT",
        "AVAVUE", "AVALAYER", "AVAFRAME", "AVASCALE", "AVANAN", "FILTER")


def _zone(img):
    """Quart central sous-échantillonné ×2 : le fond (bords non couverts et
    objets étendus exclus, comme `stacking.stats_canaux`)."""
    h, w = img.shape[:2]
    sl = (slice(h // 4, max(h // 4 + 1, 3 * h // 4), 2),
          slice(w // 4, max(w // 4 + 1, 3 * w // 4), 2))
    return img[sl] if img.ndim == 2 else img[sl + (slice(None),)]


def mesure(img):
    """(fond, bruit, p99.9, max) par canal — ou une seule entrée si 2D."""
    z = np.asarray(img, np.float32)
    seul = z.ndim == 2
    plan = z[..., None] if seul else z
    q = _zone(plan)
    fond, bruit, p999, mx = [], [], [], []
    for c in range(plan.shape[-1]):
        v = q[..., c].ravel()
        m = float(np.median(v))
        fond.append(m)
        bruit.append(1.4826 * float(np.median(np.abs(v - m))))
        p999.append(float(np.percentile(v, 99.9)))
        mx.append(float(np.max(plan[..., c])))
    if seul:
        return fond[0], bruit[0], p999[0], mx[0]
    return fond, bruit, p999, mx


def plancher_bruit(img, bloc=96):
    """σ robuste des zones `bloc`×`bloc` les PLUS LISSES, par canal — le
    PLANCHER de bruit, donc le GRAIN réel de l'image. C'est la mesure qui dit
    si le grain est gris ou coloré : peu importe le fond (M31 remplit le champ,
    ni le centre ni les coins ne sont du ciel pur), ce qui compte est que les
    trois canaux aient le MÊME plancher — sinon le grain paraît bleu/vert.
    → (sigmas (3,), niveaux (3,)) ; (None, None) si l'image n'est pas couleur."""
    a = np.asarray(img, np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return None, None
    h, w = a.shape[:2]
    sig, nivo = [], []
    for c in range(3):
        best = (float("inf"), 0.0)
        for y in range(0, h - bloc, bloc):
            for x in range(0, w - bloc, bloc):
                v = a[y:y + bloc, x:x + bloc, c].ravel()
                m = float(np.median(v))
                s = 1.4826 * float(np.median(np.abs(v - m)))
                if s < best[0]:
                    best = (s, m)
        sig.append(best[0])
        nivo.append(best[1])
    return sig, nivo


def rapport(a, b):
    """Rapport pixel à pixel a/b (médiane des ratios par canal)."""
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    if a.shape != b.shape:
        return None
    if a.ndim == 2:
        a, b = a[..., None], b[..., None]
    out = []
    for c in range(a.shape[-1]):
        m = b[..., c] > 1e-6
        out.append(float(np.median(a[..., c][m] / b[..., c][m])) if m.any()
                   else float("nan"))
    return out


def entete(path):
    from astropy.io import fits
    h = fits.open(path)[0].header
    print("  en-tête :")
    for k in CLES:
        if k in h:
            print(f"    {k:<9} = {h[k]}")


def main(argv):
    couches = "--couches" in argv
    fichiers = [a for a in argv if not a.startswith("--")]
    if not fichiers:
        print(__doc__)
        return 2
    images = {}
    for p in fichiers:
        if not os.path.exists(p):
            print(f"ABSENT : {p}")
            continue
        img = load_image(p)
        images[p] = img
        fond, bruit, p999, mx = mesure(img)
        print()
        print("=" * 78)
        print(os.path.basename(p), " ", img.shape, img.dtype)
        entete(p)
        if np.ndim(fond) == 0:
            print(f"  fond {fond:.5f} · bruit σ {bruit:.5f} · p99,9 {p999:.5f}"
                  f" · max {mx:.3f}")
            continue
        noms = ["R", "G", "B"][:len(fond)]
        print("  canal : " + " | ".join(
            f"{n} fond {f:.5f} σ {s:.5f} p99,9 {q:.4f} max {x:.3f}"
            for n, f, s, q, x in zip(noms, fond, bruit, p999, mx)))
        print(f"  CONTRASTE de FOND  R/G = {fond[0] / fond[1]:.4f}   "
              f"B/G = {fond[2] / fond[1]:.4f}   "
              f"(neutre = 1,0000 — c'est ce ratio qui fait l'aspect coloré)")
        print(f"  BRUIT relatif      R/G = {bruit[0] / bruit[1]:.4f}   "
              f"B/G = {bruit[2] / bruit[1]:.4f}   "
              f"(un canal qui monte en bruit = grains colorés visibles)")
        sig, nivo = plancher_bruit(img)
        if sig is not None:
            print("  PLANCHER DE BRUIT (zones les plus lisses = le GRAIN) :")
            print("    " + " | ".join(f"{n} σ {s:.6f} (niveau {v:.5f})"
                                      for n, s, v in zip(noms, sig, nivo)))
            print(f"    ÉQUILIBRE DU GRAIN  R/G = {sig[0]/sig[1]:.3f}   "
                  f"B/G = {sig[2]/sig[1]:.3f}   ← si ça s'écarte de 1, le grain "
                  "est COLORÉ (c'est cette mesure qui a montré que le grain "
                  "bleu-vert naît dans la normalisation par rôle de composer())")
    # --- rapports entre fichiers, dans l'ordre de la ligne de commande --------
    cles = [p for p in fichiers if p in images]
    for i in range(1, len(cles)):
        r = rapport(images[cles[i]], images[cles[0]])
        if r is None:
            continue
        noms = ["R", "G", "B"][:len(r)]
        print()
        print(f"RAPPORT {os.path.basename(cles[i])} / "
              f"{os.path.basename(cles[0])} :")
        print("  " + " | ".join(f"{n} ×{v:.4f}" for n, v in zip(noms, r)))
    if couches:
        print()
        print("NB : pour juger un coefficient SPCC, comparer le rapport "
              "« fichier / COUCHE BRUTE correspondante » — la chaîne de "
              "sortie normalise chaque rôle par SES percentiles AVANT "
              "d'appliquer les gains (une base d'échelle différente de celle "
              "où la SPCC a mesuré ses coefficients).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
