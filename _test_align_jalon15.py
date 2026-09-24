# -*- coding: utf-8 -*-
"""Test du jalon 15 — alignement « à la Siril » (canal vert + triangles) et
archive des frames calibrées.

Constat réel d'Alain (17/09/2026) : des brutes que Siril empile sans problème
sortent de AVAStack avec étoiles dédoublées et beaucoup de refus. Causes
traitées : alignement sur la moyenne RGB au lieu du canal vert (esprit
Siril), et appariement soumis à une fenêtre de continuité (un dithering, une
reprise de session ou une autre nuit fait tout refuser) au lieu d'un
appariement GLOBAL. Ce test vérifie :

  [1] canal_alignement : vert pour la couleur ((H, W, 3) et (C, H, W)),
      mono tel quel ;
  [2] _invariants_triangles : stabilité par permutation des sommets et par
      rotation + échelle, discriminants entre triangles différents ;
  [3] appariement GLOBAL par triangles : grand décalage (dithering/reprise de
      session) et rotation — cas qui échouaient avec la fenêtre de
      continuité — retrouvés par le chemin « triangles » ;
  [4] garde-fous : bruit non corrélé → refus propre ;
  [5] canal vert : la référence/détection travaille bien sur le VERT ;
  [6] ArchiveFrames : écriture + relecture identiques (mono et RGB), limite
      de débit, plafond de taille (erreur exposée, jamais d'exception),
      vider() ;
  [7] intégration App : le worker archive les frames calibrées.

Nécessite un affichage (section [7]). Exécution :
python _test_align_jalon15.py
"""
import os
import sys
import threading
import time
import tkinter as tk

import numpy as np
import cv2

from avastack.processing import stars as st_mod
from avastack.processing import alignment as al_mod
from avastack.processing.framestore import ArchiveFrames
from avastack.images import load_image
import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def champ(shape, nb=25, sigma_px=1.5, bruit=0.004, fond=0.02, graine=1,
          marge=25):
    """Champ synthétique mono : nb étoiles gaussiennes + bruit (même esprit
    que le test du jalon 13)."""
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for i in range(nb):
        y = float(rng.integers(marge, h - marge))
        x = float(rng.integers(marge, w - marge))
        a = float(rng.uniform(0.1, 0.7))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    return img


def decale(img, dx, dy):
    """warpAffine d'une translation (sens OpenCV : contenu déplacé de (dx,dy))."""
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_LINEAR)


def transforme(img, dx, dy, angle_deg=0.0):
    """warpAffine rotation autour du centre + translation du contenu."""
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR)


def _trie_lignes(inv):
    """Ordre stable des lignes d'invariants (comparaison ensembles)."""
    return inv[np.lexsort(inv.T[::-1])]


print("[1] canal_alignement : vert (couleur), tel quel (mono)")
mono = champ((40, 50), nb=3, graine=1, marge=5)
c1 = al_mod.canal_alignement(mono)
verifie(c1.shape == mono.shape and np.allclose(c1, mono),
        "mono 2D → rendu tel quel")
rgb = np.zeros((40, 50, 3), np.float32)
rgb[..., 0], rgb[..., 1], rgb[..., 2] = 0.10, 0.30, 0.20
c2 = al_mod.canal_alignement(rgb)
verifie(c2.shape == (40, 50) and np.allclose(c2, 0.30),
        "(H, W, 3) → canal 1 (vert)")
chw = np.transpose(rgb, (2, 0, 1))            # convention canaux-en-tête
c3 = al_mod.canal_alignement(chw)
verifie(c3.shape == (40, 50) and np.allclose(c3, 0.30),
        "(C, H, W) → canal 1 (vert), transposé automatiquement")

print("[2] _invariants_triangles : invariants stables et discriminants")
pts = np.array([[10., 10.], [100., 12.], [12., 90.], [200., 200.]], np.float32)
inv, som, lon = al_mod._invariants_triangles(pts)
verifie(inv is not None and inv.shape[1] == 2 and lon.shape == (len(inv),),
        f"4 points → {len(inv)} triangles décrits par 2 invariants")
inv2, _, _ = al_mod._invariants_triangles(pts[np.array([2, 0, 3, 1])])
verifie(np.allclose(_trie_lignes(inv), _trie_lignes(inv2), atol=1e-6),
        "permutation des entrées → mêmes invariants (canonisation)")
th, sc = np.deg2rad(20.0), 2.5
R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
pts3 = (pts[:3] @ R.T) * sc + np.array([500.0, -300.0])
inv3, _, _ = al_mod._invariants_triangles(pts3)
inv_a, _, _ = al_mod._invariants_triangles(pts[:3])
verifie(np.allclose(inv_a[0], inv3[0], atol=1e-5),
        "rotation 20° + échelle 2,5 → invariants identiques (translation, "
        "rotation, échelle éliminées)")
inv4, _, _ = al_mod._invariants_triangles(np.array([[0., 0.], [80., 2.],
                                                    [2., 60.]], np.float32))
verifie(not np.allclose(inv4[0], inv[0], atol=0.01),
        "triangles de formes différentes → invariants différents")
inv0, _, _ = al_mod._invariants_triangles(pts[:2])
verifie(inv0 is None, "moins de 3 points → (None, None, None)")

print("[3] Appariement GLOBAL par triangles (ORB neutralisé)")
ref = champ((300, 400), nb=30, graine=5)
al3 = al_mod.StarAligner()
al3.min_matches = 10 ** 6          # ORB neutralisé → cascade triangles→…
al3.set_reference(ref)

fr = transforme(ref, 55.0, 40.0, angle_deg=3.0)     # dithering/reprise : hors
M, ok3 = al3.compute(fr)                            # fenêtre ±40 avec prédiction
verifie(ok3 and al3.dernier["methode"] == "triangles",
        f"grand décalage (55,40) + rotation 3° → chemin « triangles » "
        f"(méthode « {al3.dernier['methode']} »)")
rec = cv2.warpAffine(fr, M, (fr.shape[1], fr.shape[0]))
verifie(float(np.mean(np.abs(rec - ref))) < 0.02,
        "frame (décalée + pivotée) alignée ≈ référence (reconstruction)")

# Le vote de centroïdes (jalon 13) avec prédiction (0,0) refuserait ce saut
# de ~68 px ; les triangles, globaux, doivent y arriver quand même.
al3._last_t = (0.0, 0.0)
fr2 = transforme(ref, 55.0, 40.0, angle_deg=3.0)
M2, ok4 = al3.compute(fr2)
verifie(ok4 and al3.dernier["methode"] == "triangles",
        "saut hors fenêtre de continuité AVEC prédiction → triangles quand même")
rec2 = cv2.warpAffine(fr2, M2, (fr2.shape[1], fr2.shape[0]))
verifie(float(np.mean(np.abs(rec2 - ref))) < 0.02,
        "reconstruction correcte après saut")

# Translation pure hors fenêtre SANS prédiction (l'ancien vote, borné à
# ±100 px au 1er alignement, échouait ; les triangles non).
al3b = al_mod.StarAligner()
al3b.min_matches = 10 ** 6
al3b.set_reference(ref)
fr3 = decale(ref, 120.0, 0.0)
M3, ok5 = al3b.compute(fr3)
verifie(ok5 and abs(M3[0, 2] + 120.0) < 1.0 and abs(M3[1, 2]) < 1.0
        and al3b.dernier["methode"] == "triangles",
        f"translation (120,0) sans prédiction → triangles "
        f"Δ=({M3[0, 2]:+.2f},{M3[1, 2]:+.2f})")

print("[4] Garde-fous : bruit non corrélé → refus propre")
lisse = champ((300, 400), nb=0, graine=4, bruit=0.001)   # pas d'étoiles
al4 = al_mod.StarAligner()
al4.min_matches = 10 ** 6
al4.set_reference(lisse)
bruit_seul = 0.05 + np.random.default_rng(5).normal(0, 0.01, lisse.shape)
M6, ok6 = al4.compute(bruit_seul.astype(np.float32))
verifie(not ok6, "bruit non corrélé → refus (jamais d'alignement faux)")

print("[5] Canal vert : la référence/détection travaille sur le VERT")
vert = champ((300, 400), nb=20, graine=7)
rouge = champ((300, 400), nb=20, graine=8)
rgb_ref = np.zeros((300, 400, 3), np.float32)
rgb_ref[..., 1] = vert                    # étoiles UNIQUEMENT dans le vert
rgb_ref[..., 0] = rouge * 0.8             # champ rouge DIFFÉRENT
al5 = al_mod.StarAligner()
al5.min_matches = 10 ** 6
al5.set_reference(rgb_ref)
pos_vert, _msg = st_mod.detecter_positions(vert, max_etoiles=60)
err = 0.0
for p in al5.ref_pos[:10]:
    err = max(err, float(np.hypot(*(pos_vert - p).T).min()))
verifie(err < 1.0,
        f"ref_pos = étoiles du canal VERT (écart max {err:.2f} px au champ vert)")
fr5 = decale(rgb_ref, 9.0, -6.0)
M7, ok7 = al5.compute(fr5)
verifie(ok7 and abs(M7[0, 2] + 9.0) < 1.0 and abs(M7[1, 2] - 6.0) < 1.0,
        f"frame RGB (étoiles vertes) décalée de (9,−6) → "
        f"Δ=({M7[0, 2]:+.2f},{M7[1, 2]:+.2f})")

print("[6] ArchiveFrames : écriture/relecture, débit, plafond, vider")
arc = ArchiveFrames(intervalle_s=0.0)
f1 = np.full((48, 64), 0.25, np.float32)
a1 = arc.ajouter(f1)
a2 = arc.ajouter(f1 + 0.01)
verifie(a1 and a2 and os.path.isfile(a1) and os.path.isfile(a2)
        and arc.n == 2, f"2 frames archivées ({arc.n})")
retour = load_image(a1)
verifie(retour.shape == f1.shape and np.allclose(retour, f1, atol=1e-6),
        "aller-retour FITS mono identique")
f_rgb = np.repeat(f1[..., None], 3, axis=2)
f_rgb[..., 1] += 0.05
a3 = arc.ajouter(f_rgb)
retour_rgb = load_image(a3)
verifie(retour_rgb.shape == (48, 64, 3)
        and np.allclose(retour_rgb, f_rgb, atol=1e-6),
        "aller-retour FITS RGB (H, W, 3) identique")
arc2 = ArchiveFrames(intervalle_s=60.0)
verifie(arc2.ajouter(f1) is not None and arc2.ajouter(f1) is None,
        "limite de débit : 2e frame immédiate → None (1 frame/s par défaut)")
arc3 = ArchiveFrames(max_octets=1, intervalle_s=0.0)
a4 = arc3.ajouter(f1)
verifie(a4 is not None and arc3.erreur != "",
        f"plafond atteint → erreur exposée (« {arc3.erreur} »)")
verifie(arc3.ajouter(f1) is None,
        "après erreur : plus rien n'est écrit (archivage arrêté)")
d_avant = arc3.dossier
arc.vider()
arc2.vider()
arc3.vider()
verifie(arc.dossier is None and arc.n == 0 and not os.path.exists(d_avant),
        "vider() : dossier supprimé, compteurs remis à zéro")

print("[7] Intégration App : le worker archive les frames calibrées")
root = tk.Tk()
root.withdraw()
app = ui.App(root)
verifie(app.archive is not None and app.archive.n == 0
        and app.archive.dossier is None,
        "App.archive existe (rien de créé tant que rien n'arrive)")


class CamFournit:
    """Caméra factice : 3 frames décalées d'un petit champ, puis plus rien."""
    name = "test"

    def __init__(self, frames):
        self.frames = frames
        self.i = 0

    def read(self):
        self.i += 1
        if self.i > len(self.frames):
            return None
        return self.frames[self.i - 1]


try:
    # stacker PRÉ-EXISTANT (comme _test_save_lineaire_fix) : le worker ne
    # touche ainsi aucune variable Tkinter (pas de mainloop dans le test).
    base = champ((48, 64), nb=4, graine=2, marge=6)
    frames_cam = [base.copy(), decale(base, 2.0, 1.0), decale(base, 4.0, 2.0)]
    app.archive.intervalle_s = 0.0     # test : tout archiver
    app.camera = CamFournit(frames_cam)
    from avastack.processing.stacking import LiveStacker
    app.stacker = LiveStacker((48, 64), k=None)
    app.aligner.set_reference(base)
    app.running = True
    app.empilement_on = True            # jalon 26 : le worker n'empile que si armé
    th = threading.Thread(target=app._worker, daemon=True)
    th.start()
    t0 = time.time()
    while time.time() - t0 < 10.0 and (app.stacker is None
                                       or app.stacker.n < 3):
        time.sleep(0.05)
    app.running = False
    th.join(timeout=3.0)
    verifie(app.stacker is not None and app.stacker.n == 3,
            f"worker : 3 frames empilées ({app.stacker.n if app.stacker else 0})")
    verifie(app.archive.n == 3,
            f"3 frames calibrées archivées ({app.archive.n})")
    verifie(all(os.path.isfile(c) for c in app.archive.chemins),
            "fichiers d'archive présents sur disque")
finally:
    app.archive.vider()
    root.destroy()

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)