# -*- coding: utf-8 -*-
"""Test du jalon 13 — alignement robuste + équilibrage des canaux.

Constat réel d'Alain (17/09/2026, Uranus-C Pro + C8/0,63 à 1280 mm) :
étoiles « en plusieurs points puis en trainées » (l'ORB ne s'apparie plus à
cette focale et le repli corrélation de phase, toujours « confiant », renvoyait
(0,0) pendant que le champ dérive) ; image très verte (capteur couleur sans
balance des blancs). Ce test vérifie :

  [1] stars.detecter_positions : centroïdes exacts, tri par éclat, cap, cas
      dégénérés sans exception (message explicite) ;
  [2] StarAligner : translation pure retrouvée (dont un GRAND décalage au
      1er alignement sans prédiction), rotation légère, reconstruction de la
      frame alignée sur la référence ; méthode rapportée pour l'UI ;
  [3] garde-fous : échelle/angle aberrants refusés (_M_valide), champ sans
      étoiles → non concluant, continuité (saut > 40 px avec prédiction →
      refus ; sans prédiction → accepté) ;
  [4] corrélation de phase HONNÊTE : translation retrouvée sur une image
      structurée sans étoiles, REFUS sur du bruit non corrélé ;
  [5] stacking : mean(recadre=False) (référence, même repère) + équilibrage
      des canaux (vert corrigé, force, mono no-op, gains bornés, (C,H,W)) ;
  [6] UI (fenêtre réelle) : combobox « Rafraîchir la référence (frames) »,
      case + force d'équilibrage, config round-trip (`ref_refresh`,
      `wb_auto`, `wb_force`), config invalide → défauts sans crash.

Nécessite un affichage (section [6]). Exécution :
python _test_align_jalon13.py
"""
import sys
import tkinter as tk

import numpy as np
import cv2

from avastack.processing import stars as st_mod
from avastack.processing import alignment as al_mod
from avastack.processing import stacking as stk_mod
from avastack.processing.stacking import LiveStacker, gains_equilibre
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def champ(shape, nb=25, sigma_px=1.5, bruit=0.004, fond=0.02, graine=1,
          marge=25, rgb=False, grosses=False, sigma_taches=45.0):
    """Champ synthétique : nb étoiles gaussiennes + bruit (option : RGB et
    grosses taches floues « nébulosité », sans étoiles si nb=0)."""
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    pos_vraies = []
    eclat = []
    for i in range(nb):
        y = float(rng.integers(marge, h - marge))
        x = float(rng.integers(marge, w - marge))
        s = sigma_px * (6.0 if grosses else 1.0)
        a = float(rng.uniform(0.1, 0.7))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * s ** 2))).astype(np.float32)
        pos_vraies.append((x, y))
        eclat.append(a)
    if grosses:                          # taches floues larges (pas des étoiles)
        for _ in range(3):
            y = float(rng.integers(0, h))
            x = float(rng.integers(0, w))
            img += (0.04 * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                                  / (2.0 * sigma_taches ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    if rgb:
        # léger déséquilibre « capteur couleur » : vert ×2 dans le fond
        img = np.repeat(img[..., None], 3, axis=2)
        img[..., 0] *= 0.6               # rouge plus faible
        img[..., 1] *= 1.4               # vert dominant
    return img, np.array(pos_vraies, np.float32), np.array(eclat, np.float32)


def decale(img, dx, dy):
    """warpAffine d'une translation (sens OpenCV : contenu déplacé de (dx,dy))."""
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_LINEAR)


print("[1] stars.detecter_positions : centroïdes, tri, cap, cas dégénérés")
img, pos_vraies, eclat = champ((300, 400), nb=12)
pos, msg = st_mod.detecter_positions(img)
verifie(msg == "" and pos.ndim == 2 and pos.shape[1] == 2 and len(pos) >= 10,
        f"12 étoiles → {len(pos)} positions (N,2), pas de message (« {msg} »)")
err_max = 0.0
for p in pos:
    d = np.hypot(*(pos_vraies - p).T).min()
    err_max = max(err_max, float(d))
verifie(err_max < 0.8, f"centroïdes à ≤ 0,8 px des vraies positions "
                       f"(max {err_max:.2f} px)")
verifie(bool(eclat.max() >= eclat[np.argmin(
    np.hypot(*(pos_vraies - pos[0]).T))]),
    "tri par éclat décroissant (la 1re position est une étoile brillante)")
pos_cap, _ = st_mod.detecter_positions(img, max_etoiles=3)
verifie(len(pos_cap) == 3, f"cap max_etoiles=3 respecté ({len(pos_cap)})")
plat = np.full((200, 300), 0.01, np.float32)
pos_p, msg_p = st_mod.detecter_positions(plat)
verifie(pos_p.shape == (0, 2) and msg_p != "",
        f"image constante → (0,2) + message (« {msg_p} »)")
pos_t, msg_t = st_mod.detecter_positions(np.zeros((5, 5), np.float32))
verifie(pos_t.shape == (0, 2) and msg_t != "",
        f"image trop petite → message (« {msg_t} »)")


print("[2] StarAligner : translations (dont grand décalage initial), rotation")
ref, _, _ = champ((300, 400), nb=25, graine=2)
aligner = al_mod.StarAligner()
aligner.set_reference(ref)

fr1 = decale(ref, 7.0, -5.0) + 0.0      # translation « petite »
fr1 = np.clip(fr1 + np.random.default_rng(11).normal(0, 0.004, fr1.shape), 0, 1)
M, ok1 = aligner.compute(fr1)
verifie(ok1 and abs(M[0, 2] + 7.0) < 0.7 and abs(M[1, 2] - 5.0) < 0.7,
        f"translation (+7,−5) → Δ=({M[0, 2]:+.2f},{M[1, 2]:+.2f}) retrouvé "
        f"(méthode « {aligner.dernier['methode']} »)")
rec = cv2.warpAffine(fr1, M, (fr1.shape[1], fr1.shape[0]))
verifie(float(np.mean(np.abs(rec - ref))) < 0.02,
        "frame alignée ≈ référence (reconstruction)")

fr2 = decale(ref, 60.0, 40.0)           # GRAND décalage : 1er alignement
M, ok2 = aligner.compute(fr2)
verifie(ok2 and abs(M[0, 2] + 60.0) < 0.7 and abs(M[1, 2] + 40.0) < 0.7,
        f"grand décalage (60,40) sans prédiction → "
        f"Δ=({M[0, 2]:+.2f},{M[1, 2]:+.2f}) retrouvé")

Mrot = cv2.getRotationMatrix2D((200.0, 150.0), 0.8, 1.0)
Mrot[0, 2] += 5.0
Mrot[1, 2] += 3.0
fr3 = cv2.warpAffine(ref, Mrot, (400, 300), flags=cv2.INTER_LINEAR)
M, ok3 = aligner.compute(fr3)
verifie(ok3, "rotation 0,8° + translation acceptée")
rec = cv2.warpAffine(fr3, M, (fr3.shape[1], fr3.shape[0]))
verifie(float(np.mean(np.abs(rec - ref))) < 0.02,
        "frame pivotée alignée ≈ référence (reconstruction)")
ang, _ech, _dx, _dy = al_mod.infos_M(M)
verifie(abs(ang - 0.8) < 0.25, f"angle compensé ≈ +0,8° ({ang:+.2f}° — "
                               f"getRotationMatrix2D tourne le contenu à l'inverse)")

print("[3] Garde-fous : matrices aberrantes, champ vide, continuité")
I3 = np.eye(2, 3)
verifie(al_mod._M_valide(I3), "identité valide")
M20 = I3.copy(); M20[0, 0] = 1.2
verifie(not al_mod._M_valide(M20), "échelle 1,2 → refusée")
M15 = I3.copy(); M15[1, 0] = np.tan(np.deg2rad(15.0))
verifie(not al_mod._M_valide(M15), "angle 15° → refusé")
Mn = I3.copy(); Mn[0, 2] = np.nan
verifie(not al_mod._M_valide(Mn), "NaN → refusé")
ang1, ech1, dx1, dy1 = al_mod.infos_M(I3)
verifie(abs(ang1) < 1e-9 and abs(ech1 - 1.0) < 1e-9
        and abs(dx1) < 1e-9 and abs(dy1) < 1e-9, "infos_M(identité)")

petit, _, _ = champ((300, 400), nb=4, graine=3)     # < 6 étoiles
al, msg_al = st_mod.detecter_positions(petit)
al2 = al_mod.StarAligner()
al2.set_reference(ref)
al2.ref_pos = al                      # simulation : référence quasi vide
M_e, ok_e = al2._etoiles(fr1)
verifie(M_e is None and not ok_e,
        "moins de 6 étoiles de référence → non concluant (pas de M inventé)")

# Continuité : avec une prédiction à (60, 40), une frame ramenée à (0, 0)
# (saut de 72 px) doit être refusée ; sans prédiction, elle doit passer.
al3 = al_mod.StarAligner()
al3.set_reference(ref)
al3._last_t = (60.0, 40.0)
M_c, ok_c = al3._etoiles(decale(ref, 0.0, 0.0))
verifie(M_c is None and not ok_c,
        "saut de translation > 40 px avec prédiction → refus")
al4 = al_mod.StarAligner()
al4.set_reference(ref)
M_d, ok_d = al4._etoiles(decale(ref, 0.0, 0.0))
verifie(ok_d and abs(M_d[0, 2]) < 0.7 and abs(M_d[1, 2]) < 0.7,
        "même frame SANS prédiction (fenêtre large) → acceptée")


print("[4] Corrélation de phase HONNÊTE : retrouvée si utile, refus sinon")
# Image structurée SANS étoiles (taches floues) : ni l'ORB ni les centroïdes
# ne doivent rien trouver — seule la phase peut aligner. min_matches est
# porté hors d'atteinte pour neutraliser l'ORB de façon DÉTERMINISTE.
lisse, _, _ = champ((300, 400), nb=0, graine=4, grosses=True, bruit=0.001,
                    sigma_taches=12.0)
al5 = al_mod.StarAligner()
al5.min_matches = 10 ** 6              # ORB neutralisé → cascade étoiles→phase
al5.set_reference(lisse)
M, ok5 = al5.compute(decale(lisse, 12.0, -8.0))
verifie(ok5 and abs(M[0, 2] + 12.0) < 0.9 and abs(M[1, 2] - 8.0) < 0.9
        and al5.dernier["methode"] == "phase",
        f"translation (12,−8) sans étoiles → phase "
        f"Δ=({M[0, 2]:+.2f},{M[1, 2]:+.2f})")
bruit_seul = 0.05 + np.random.default_rng(5).normal(0, 0.01, lisse.shape)
al6 = al_mod.StarAligner()
al6.set_reference(lisse)
M, ok6 = al6.compute(bruit_seul.astype(np.float32))
verifie(not ok6 and al6.dernier is None or not ok6,
        "bruit non corrélé → REFUS (plus jamais de (0,0) « confiant »)")

print("[5] stacking : mean(recadre=False) + équilibrage des canaux")
H, W = 64, 48
s1 = LiveStacker((H, W, 3), k=None)
f1 = np.full((H, W, 3), 0.02, np.float32)
f2 = decale(f1, 4.0, -3.0)
s1.add(f1)
s1.mean()
s1.note_alignement(I3)
s1.add(f2)
s1.note_alignement(np.array([[1.0, 0.0, 4.0], [0.0, 1.0, -3.0]]))
plein = s1.mean(recadre=False)
verifie(plein.shape == (H, W, 3), "mean(recadre=False) → image COMPLÈTE")
coupe = s1.mean()
y0, x0, y1, x1 = s1.cadre
verifie(coupe.shape == plein[y0:y1, x0:x1].shape and y0 >= 3 and x0 >= 3
        and y1 <= H - 3 and x1 <= W - 3,
        f"mean() recadrée = intersection réelle ({x1 - x0}×{y1 - y0}, "
        f"comportement inchangé)")
verifie(np.allclose(coupe, plein[y0:y1, x0:x1]),
        "la recadrée = découpage exact de la complète (même repère)")

vert = np.zeros((H, W, 3), np.float32)
vert[..., 0] = 0.05                    # rouge
vert[..., 1] = 0.10                    # vert dominant (constat réel)
vert[..., 2] = 0.05                    # bleu
s2 = LiveStacker((H, W, 3), k=None)
s2.wb_auto, s2.wb_force = True, 1.0
s2.add(vert)
s2.add(vert)
m = s2.mean()
p20 = [float(np.percentile(m[..., c], 20)) for c in range(3)]
cible = (0.05 * 0.10 * 0.05) ** (1.0 / 3.0)
verifie(max(abs(p - cible) / cible for p in p20) < 0.02,
        f"fonds des 3 canaux égalisés à la moyenne géométrique "
        f"({p20[0]:.4f}/{p20[1]:.4f}/{p20[2]:.4f} ≈ {cible:.4f})")
s3 = LiveStacker((H, W, 3), k=None)
s3.wb_auto, s3.wb_force = True, 0.5
s3.add(vert)
s3.add(vert)
m = s3.mean()
p20f = [float(np.percentile(m[..., c], 20)) for c in range(3)]
verifie(abs(p20f[0] - 0.05 * (cible / 0.05) ** 0.5) < 0.002
        and abs(p20f[1] - 0.10 * (cible / 0.10) ** 0.5) < 0.002,
        f"force 0,5 → gains partiels ({p20f[0]:.4f}/{p20f[1]:.4f})")
s4 = LiveStacker((H, W), k=None)       # mono : no-op garanti
s4.wb_auto = True
mono = np.full((H, W), 0.07, np.float32)
s4.add(mono)
s4.add(mono + 0.01)
verifie(np.allclose(s4.mean(), (2 * mono + 0.01) / 2),
        "mono : équilibrage no-op")
g = gains_equilibre(vert)
verifie(g is not None and g.min() >= stk_mod.WB_GAIN_MIN
        and g.max() <= stk_mod.WB_GAIN_MAX,
        f"gains bornés [{stk_mod.WB_GAIN_MIN}, {stk_mod.WB_GAIN_MAX}] "
        f"(→ {np.round(g, 3).tolist()})")
extreme = vert.copy()
extreme[..., 0] = 0.001                # canal quasi noir → gain borné
g2 = gains_equilibre(extreme)
verifie(g2 is not None and abs(float(g2[0]) - stk_mod.WB_GAIN_MAX) < 1e-6,
        "canal quasi noir → gain plafonné (pas d'amplification folle)")
g3 = gains_equilibre(vert.transpose(2, 0, 1))
verifie(g3 is not None and np.allclose(g3, g),
        "layout (C,H,W) : mêmes gains que (H,W,3)")

print("[6] UI : combobox référence auto, équilibrage, config round-trip")
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
ui.CONFIG = {}
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
verifie(app.var_ref_refresh.get() == "20" and app.ref_refresh == 20,
        "référence auto par défaut : 20 frames")
verifie(app.var_wb.get() is True,
        "case « Équilibrage des canaux (auto) » cochée par défaut")
app.var_ref_refresh.set("jamais"); app._on_ref_refresh()
verifie(app.ref_refresh == 0, "« jamais » → 0 (ancien comportement)")
app.var_ref_refresh.set("30"); app._on_ref_refresh()
verifie(app.ref_refresh == 30, "« 30 » → 30")
app.var_wb.set(False); app._on_wb()
verifie(app.var_wb.get() is False, "case équilibrage décochée")
app.var_wb.set(True)
app.var_wb_force.set(0.5); app._on_wb()
app._sauver_config_app()
c = sauvegardes[-1]
verifie(c.get("ref_refresh") == 30 and c.get("wb_auto") is True
        and c.get("wb_force") == 0.5,
        "config écrite : ref_refresh, wb_auto (explicite), wb_force")
root.destroy()
ui.CONFIG = {"ref_refresh": 10, "wb_auto": False, "wb_force": 0.3}
root2 = tk.Tk()
app2 = ui.App(root2)
root2.update_idletasks()
verifie(app2.ref_refresh == 10 and app2.var_ref_refresh.get() == "10"
        and app2.var_wb.get() is False
        and abs(app2.var_wb_force.get() - 0.3) < 1e-9,
        "config restaurée (case décochée comprise)")
root2.destroy()
ui.CONFIG = {"ref_refresh": 99, "wb_force": 7.0}
root3 = tk.Tk()
app3 = ui.App(root3)
root3.update_idletasks()
verifie(app3.ref_refresh == 20 and abs(app3.var_wb_force.get() - 1.0) < 1e-9,
        "config invalide → défauts, sans crash")
root3.destroy()

print()
print("JALON 13 : " + ("TOUS LES TESTS PASSENT" if ok
                       else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)