# -*- coding: utf-8 -*-
"""Banc de diagnostic — couches R/G/B d'une composition (jalon 54, suite).

CONTEXTE (retour réel d'Alain, 21/09/2026) : l'image composite montre des
étoiles « floues, comme décalées » alors que le recalage colorimétrique
(Linear Fit, offset seul) est devenu quasi inactif (gains ×1.000, offsets
~0,02). Un recalage PHOTOMÉTRIQUE ne peut pas créer ni corriger un
dédoublement géométrique : la cause est donc dans les COUCHES elles-mêmes.
Ce banc mesure et tranche entre les trois hypothèses :

  1. DÉFOCALISATION d'un filtre (parfocalie / dérive de focus) :
     FWHM d'une couche ≫ les autres → refocaliser / autofocus par filtre ;
  2. DÉCALAGE inter-couches (réfraction atmosphérique différentielle,
     résidu d'alignement par dossier) : translation mesurée ≥ 0,5 px →
     correctif logiciel possible (ré-enregistrement des canaux) ;
  3. couches nettes ET enregistrées → le dédoublement vient d'ailleurs
     (sous-échantillonnage, étirement) — coller la sortie complète.

Usage :
    python _diag_canaux_compo.py canal_R.fit canal_G.fit canal_B.fit
(1 à 3 fichiers — empilements PAR CANAL sauvegardés par l'appli, bouton
« 💾 Enregistrer les canaux (par filtre)… » ; l'ordre et les noms sont
libres, le canal de RÉFÉRENCE est celui du nom contenant « G » sinon le
2e fichier.)
"""
import sys

import cv2
import numpy as np

from avastack.images import load_image
from avastack.processing import stars

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_COTE = 1024          # corrélation de phase sur aperçu (coût constant)
APPAREIL_MIN = 0.5       # px : en dessous, translation = négligeable
FLOU_RAPPORT = 1.4       # FWHM max/min ≥ 1,4 → couche nettement plus floue


def _ech(c, cible=MAX_COTE):
    pas = max(1, int(round(max(c.shape) / float(cible))))
    return c[::pas, ::pas], pas


def translation_phase(ref, img):
    """Translation (dx, dy) de `img` vers `ref` — corrélation de phase sur
    aperçu, signe tranché par SSD (même motif que StarAligner._phase).
    → ((dx, dy) px PLEINE RÉSOLUTION, amélioration SSD relative) ou None."""
    a, pa = _ech(ref)
    b, pb = _ech(img)
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    a, b = a[:h, :w], b[:h, :w]
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    a0 = (a - float(np.median(a))) * win
    b0 = (b - float(np.median(b))) * win
    (dx, dy), _resp = cv2.phaseCorrelate(a0, b0)
    if not (np.isfinite(dx) and np.isfinite(dy)):
        return None
    pas = (pa + pb) / 2.0                 # échantillonnage des aperçus
    best = None
    for s in (1.0, -1.0):
        M = np.array([[1.0, 0.0, s * dx], [0.0, 1.0, s * dy]], np.float32)
        warp = cv2.warpAffine(b, M, (w, h))
        d = float(np.mean((warp - a) ** 2))
        if best is None or d < best[0]:
            best = (d, s * dx, s * dy)
    _d, bx, by = best
    d0 = float(np.mean((b - a) ** 2))
    gain = (d0 - best[0]) / d0 if d0 > 0 else 0.0
    return (bx * pas, by * pas), gain


def translation_etoiles(ref, img):
    """Translation + dispersion via appariement MUTUEL des centroïdes
    (≤ 3 px, cf. jalon 13) → (dict, message)."""
    pa, msg_a = stars.detecter_positions(ref)
    pb, msg_b = stars.detecter_positions(img)
    if len(pa) < 6 or len(pb) < 6:
        return None, (f"pas assez d'étoiles ({len(pa)} vs {len(pb)}) : "
                      f"{msg_a or msg_b}")
    d2 = np.hypot(pa[:, None, 0] - pb[None, :, 0],
                  pa[:, None, 1] - pb[None, :, 1])
    j = d2.argmin(axis=1)
    dist = d2[np.arange(len(pa)), j]
    j_inv = d2.T.argmin(axis=1)
    mutuel = (dist <= 3.0) & (j_inv[j] == np.arange(len(pa)))
    n = int(mutuel.sum())
    if n < 6:
        return None, f"appariements mutuels insuffisants ({n})"
    d = pa[mutuel] - pb[j][mutuel]        # Δ qui ramène img sur ref
    dx, dy = float(np.median(d[:, 0])), float(np.median(d[:, 1]))
    disp = (float(1.4826 * np.median(np.abs(d - np.median(d, axis=0))))
            if n > 2 else 0.0)
    return {"dx": dx, "dy": dy, "n": n, "disp": disp,
            "nb_a": len(pa), "nb_b": len(pb)}, ""


def principal(fichiers):
    print("=== DIAGNOSTIC COUCHES R/G/B (composition) ===\n")
    donnees = []
    for f in fichiers:
        img = load_image(f)
        img2d = (img.mean(axis=2) if img.ndim == 3 else img).astype(np.float32)
        m, msg = stars.mesurer_seeing(img2d)
        fwhm = m.get("fwhm")
        print(f"[{f}] {img2d.shape[1]}×{img2d.shape[0]} px · étoiles "
              f"exploitables : {m.get('nb', '?')}"
              f"{' — ' + msg if msg else ''}")
        print(f"        FWHM médiane : "
              f"{f'{fwhm:.2f} px' if fwhm is not None else 'non mesurée'} · "
              f"ellipticité : {m.get('ellipticite', '—')}")
        donnees.append((f, img2d, fwhm))
    if len(donnees) < 2:
        print("\n⚠ donne au moins 2 fichiers pour comparer les couches.")
        return 1

    # --- canal de référence : nom contenant « G », sinon le 2e fichier ---
    idx_ref = next((i for i, (f, *_r) in enumerate(donnees)
                    if "g" in f.lower()), 1 if len(donnees) > 1 else 0)
    ref_f, ref, _ = donnees[idx_ref]
    print(f"\nCanal de RÉFÉRENCE : [{ref_f}]")

    # --- 1) défocalisation par couche --------------------------------------
    fwhms = {f: fwhm for f, _i, fwhm in donnees if fwhm is not None}
    if len(fwhms) >= 2:
        f_max = max(fwhms, key=fwhms.get)
        f_min = min(fwhms, key=fwhms.get)
        rapport = fwhms[f_max] / fwhms[f_min]
        print("\n--- Focalisation ---")
        for f, _i, fwhm in donnees:
            if fwhm is not None:
                print(f"    {f} : FWHM {fwhm:.2f} px")
        if rapport >= FLOU_RAPPORT:
            print(f"  ⇒ {f_max} est NETTEMENT plus floue que {f_min} "
                  f"(×{rapport:.2f}) → DÉFOCALISATION de ce filtre "
                  f"(parfocalie / autofocus par filtre). Aucun logiciel "
                  f"ne le corrige : refocaliser ce filtre.")
        else:
            print(f"  ⇒ FWHM homogènes (rapport ×{rapport:.2f} < "
                  f"{FLOU_RAPPORT}) : pas de défocalisation évidente.")
    print()

    # --- 2) décalage inter-couches -----------------------------------------
    print(f"--- Enregistrement inter-couches (réf. = {ref_f}) ---")
    conclusions = []
    for f, img, _fwhm in donnees:
        if f == ref_f:
            continue
        res, msg = translation_etoiles(ref, img)
        if res is None:
            print(f"    [{f}] : {msg}")
            continue
        mag = float(np.hypot(res["dx"], res["dy"]))
        print(f"    [{f}] : Δ=({res['dx']:+.2f}, {res['dy']:+.2f}) px sur "
              f"{res['n']} étoiles · dispersion (MAD) {res['disp']:.2f} px")
        conclusions.append((f, mag))
    print()
    for f, mag in conclusions:
        if mag >= APPAREIL_MIN:
            print(f"  ⇒ [{f}] est DÉCALÉE de {mag:.2f} px vs {ref_f} → "
                  f"ré-enregistrement POSSIBLE en logiciel (translation) ; "
                  f"causes typiques : réfraction atmosphérique "
                  f"différentielle entre filtres, résidu d'alignement.")
        else:
            print(f"  ⇒ [{f}] : pas de décalage mesurable "
                  f"(< {APPAREIL_MIN} px) — couches enregistrées.")
    if not conclusions:
        print("  ⇒ aucune comparaison possible (pas assez d'étoiles).")
    print("\nColle cette sortie complète dans la conversation si le verdict "
          "ne suffit pas à trancher.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(principal(sys.argv[1:4]))


