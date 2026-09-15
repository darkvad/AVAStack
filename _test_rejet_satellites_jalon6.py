# -*- coding: utf-8 -*-
"""Test headless du jalon 6 — rejet des satellites (mode « Winsorized »).

Vérifie que LiveStacker :
  - mode kappa : comportement HISTORIQUE strictement inchangé (régression,
    comparaison à une réimplémentation de l'ancien code) ;
  - mode winsorized (adaptation live du Winsorized Sigma Clipping de
    PixInsight : médiane/MAD d'une fenêtre glissante) :
      * efface une trace passée pendant le warmup (rejeu de
        l'accumulation quand la fenêtre se remplit), là où le mode kappa
        la garde (σ cumulé contaminé pour toujours) ;
      * rejette une trace faible arrivée ensuite aux mêmes pixels
        (acceptée en kappa à cause du σ gonflé par la 1re trace) ;
      * préserve les étoiles et le champ (pas d'érosion du signal) ;
      * fonctionne en mono ET RGB (piège des canaux) ;
      * le découpage en bandes de lignes (chunks) ne change rien ;
  - set_rejet() change méthode/fenêtre à chaud sans perdre l'accumulation.

Exécution : python _test_rejet_satellites_jalon6.py
"""
import sys

import numpy as np

import avastack.processing.stacking as stacking
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ---------------------------------------------------------- ciel simulé
H, W, NB = 120, 180, 60
FOND, BRUIT = 0.05, 0.004
ETOILES = [(30, 40, 0.30), (80, 120, 0.25), (60, 90, 0.20)]   # (y, x, amp)
YY, XX = np.mgrid[0:H, 0:W]
BANDE = np.abs(YY - (0.5 * XX + 20.0)) < 1.5                  # trace diagonale


def ciel(seed):
    """Frame propre : fond + bruit + étoiles statiques (linéaire [0..1])."""
    rng = np.random.default_rng(seed)
    img = rng.normal(FOND, BRUIT, (H, W))
    for cy, cx, amp in ETOILES:
        img += amp * np.exp(-((YY - cy) ** 2 + (XX - cx) ** 2) / 2.0)
    return img.astype(np.float32)


def avec_trainee(img, amp):
    img = img.copy()
    img[BANDE] += amp
    return img


def session(frames, **kw):
    """Empile frames et renvoie (stack, rejected_total, stacker)."""
    k = kw.pop("k", 3.0)
    st = LiveStacker(frames[0].shape, k=k, **kw)
    for f in frames:
        st.add(f)
    return st.mean(), st.rejected_total, st


# Frames mono : trace FORTE (0.5) pendant le warmup (frame 2), trace FAIBLE
# (0.1) ensuite aux MÊMES pixels (frame 25) — le scénario qui « empoisonne »
# le kappa-sigma cumulé.
frames_mono = [ciel(i) for i in range(NB)]
frames_mono[2] = avec_trainee(frames_mono[2], 0.5)
frames_mono[25] = avec_trainee(frames_mono[25], 0.1)
propres = [f for i, f in enumerate(frames_mono) if i not in (2, 25)]
ref = np.mean(propres, axis=0)        # référence : moyenne des frames saines

print("[1] Mode kappa = comportement historique inchangé (régression)")
petites = [np.random.default_rng(42 + i).normal(0.1, 0.02, (40, 50)
                                                ).astype(np.float32)
           for i in range(12)]
st = LiveStacker((40, 50), k=3.0)
for f in petites:
    st.add(f)
# Réimplémentation de l'ANCIEN code (avant jalon 6), à comparer exactement :
S = np.zeros((40, 50)); SS = np.zeros((40, 50)); Wt = np.zeros((40, 50)); rej = 0
for i, fr in enumerate(petites):
    f = fr.astype(np.float64)
    if i >= 5:
        m = S / np.maximum(Wt, 1e-9)
        s = np.sqrt(np.maximum(SS / np.maximum(Wt, 1e-9) - m * m, 1e-12))
        w = np.where(np.abs(f - m) > 3.0 * s, 0.0, 1.0)
        rej += int((w == 0).sum())
    else:
        w = 1.0
    S += f * w; SS += f * f * w; Wt += w
verifie(np.array_equal(st.sum, S) and np.array_equal(st.wsum, Wt),
        "sommes/poids identiques à l'ancien algorithme")
verifie(st.rejected_total == rej, f"compteur de rejets identique ({rej})")

print("[2] Trace au warmup + trace faible ensuite (le cas « poison »)")
stk, _, _ = session(frames_mono, method="kappa", warmup=5)
swin, _, stw = session(frames_mono, method="winsorized", window=8, warmup=5)
resid_k = float(np.mean(stk[BANDE] - ref[BANDE]))
resid_w = float(np.mean(swin[BANDE] - ref[BANDE]))
verifie(resid_k > 0.008,
        f"kappa : la trace reste (~{resid_k * 1e3:.1f}e-3, attendu ~10e-3)")
verifie(resid_w < 0.004,
        f"winsorized : trace effacée ({resid_w * 1e3:.2f}e-3 < 4e-3)")
verifie(resid_w < 0.4 * resid_k, "winsorized nettement meilleur que kappa")
verifie(stw.n == NB, f"les {NB} frames restent comptabilisées (n={stw.n})")
verifie(stw.rejected_total > 0,
        f"des pixels ont été rejetés ({stw.rejected_total})")
verifie(stw.mean().dtype == np.float32 and stw.mean().shape == (H, W),
        "sortie float32, forme préservée (mono)")

print("[3] Champ propre préservé (pas d'érosion des étoiles)")
ecart_etoiles = max(float(np.abs(swin[y, x] - ref[y, x])) for y, x, _ in ETOILES)
verifie(ecart_etoiles < 0.02,
        f"étoiles intactes (écart max {ecart_etoiles:.4f})")
frames_propres = [ciel(i + 1000) for i in range(30)]
swin2, _, _ = session(frames_propres, method="winsorized", window=8)
ecart = float(np.max(np.abs(swin2 - np.mean(frames_propres, axis=0))))
verifie(ecart < 0.01, f"session sans trace : écart max {ecart:.4f} < 0.01")

print("[4] RGB (3 canaux)")
nb, h, w = 25, 40, 60
frames_rgb = [np.random.default_rng(7 + i).normal(FOND, BRUIT, (h, w, 3)
                                                   ).astype(np.float32)
              for i in range(nb)]
bande_h = np.abs(np.mgrid[0:h, 0:w][0] - 30) < 1.5     # trace horizontale
frames_rgb[3] = np.where(bande_h[..., None], frames_rgb[3] + 0.4, frames_rgb[3])
frames_rgb[15] = np.where(bande_h[..., None], frames_rgb[15] + 0.2, frames_rgb[15])
srgb, _, _ = session(frames_rgb, method="winsorized", window=8, warmup=5)
resid_rgb = srgb[bande_h].mean(axis=0) - srgb[~bande_h].mean(axis=0)
verifie(float(np.max(np.abs(resid_rgb))) < 0.005,
        f"traces effacées sur les 3 canaux (max {np.max(np.abs(resid_rgb)) * 1e3:.2f}e-3)")
verifie(srgb.shape == (h, w, 3) and srgb.dtype == np.float32,
        "sortie RGB float32 (piège des axes de canaux)")

print("[5] Warmup sans rejet, puis rejeu de l'accumulation")
stw2 = LiveStacker((H, W), k=3.0, method="winsorized", window=8, warmup=5)
for f in frames_mono[:4]:
    stw2.add(f)
verifie(stw2.rejected_total == 0,
        "aucun rejet tant que la fenêtre n'est pas remplie")
for f in frames_mono[4:8]:
    stw2.add(f)
verifie(stw2._rejeu and stw2.rejected_total > 0,
        f"rejeu du warmup effectué ({stw2.rejected_total} rejets)")
verifie(stw2.n == 8 and stw2.wsum.max() <= 8,
        "accumulation reconstruite sans double comptage")

print("[6] Découpage en bandes de lignes (chunks) : résultat identique")
old = stacking._CHUNK_PX
stacking._CHUNK_PX = 32
swin_c, _, _ = session(frames_mono, method="winsorized", window=8, warmup=5)
stacking._CHUNK_PX = old
verifie(np.allclose(swin, swin_c, rtol=0, atol=1e-12),
        "multi-chunks = même résultat qu'en un seul bloc")

print("[7] set_rejet à chaud : accumulation préservée")
stc = LiveStacker((H, W), k=3.0)
for f in frames_mono[:10]:
    stc.add(f)
n_avant = stc.n
stc.set_rejet(method="winsorized", window=8)
verifie(stc.n == n_avant and stc.method == "winsorized",
        "méthode changée sans perte d'accumulation")
verifie(stc._nbuf == 0, "fenêtre vidée (elle se remplit à nouveau)")
for f in frames_mono[10:20]:
    stc.add(f)
verifie(stc.mean() is not None and stc.mean().shape == (H, W),
        "l'empilement continue normalement")
stc.set_rejet(window=4)
verifie(stc.window == 4, "fenêtre redimensionnée à chaud")

print("[8] Rejet désactivé (k=None) : moyenne pure")
stoff = LiveStacker((H, W), k=None, method="winsorized", window=8)
for f in frames_mono:
    stoff.add(f)
verifie(stoff.rejected_total == 0, "aucun rejet")
verifie(np.allclose(stoff.mean(), np.mean(frames_mono, axis=0), atol=1e-6),
        "moyenne pure identique à numpy")

print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
