# -*- coding: utf-8 -*-
"""Banc v2.37.2 — CŒUR « CRAMÉ » : la coupe à 1,0 avant l'étirement.

CONSTAT D'ALAIN (25/09/2026) : « le cœur de M31 est vraiment cramé », dans
l'appli comme sur le PNG. Ce n'est AUCUN paramètre : c'est une COUPE.

Mesure (profil du cœur par anneaux, % du canal vert, MÊME fichier linéaire) :
    image en mémoire (coupe à 1,0) : 86,0  86,0  86,0  86,0  86,0  82,9
    fichier borné (facteur global) : 85,8  78,7  73,1  67,4  62,6  56,4
L'empilement vit en mémoire à une échelle arbitraire : le facteur global que la
sauvegarde linéaire retire (`images.borner_lineaire`, AVASCALE) valait 13 à 18
sur ses empilements M31. Le chemin d'étirement faisait `np.clip(img, 0, 1)`
AVANT d'étirer : tout ce qui dépassait — le cœur de M31 ENTIER (0,4 à 0,8 % de
l'image) — devenait UNE SEULE VALEUR, donc un disque blanc PLAT sans dégradé ;
le fichier sauvegardé, lui, gardait son dégradé — d'où l'écart entre l'appli et
le fichier.

Correctif : `veralux.normaliser_lin()` — UN SEUL facteur GLOBAL (même règle que
les sauvegardes linéaires), appliqué dans `etirer()` et dans
`DisplayProcessor.rendu_pleine_resolution` (vue « tel que vu »).

Vérifie :
  [1] `normaliser_lin` : aucun facteur si max ≤ 1 (bit à bit), max = 1 sinon,
      rapports entre pixels conservés, négatifs → 0, NaN/Inf neutralisés,
      ENTRÉE jamais modifiée ;
  [2] le rendu ne dépend plus de l'échelle : etirer(x) == etirer(3·x) ; l'ancien
      chemin (coupe) en diffère (le bug) ;
  [3] cœur DÉGRADÉ sur une scène type M31 à l'échelle mémoire ; l'ancien
      chemin le rendait plat ;
  [4] ses fichiers réels s'il en trouve (C:\\Astro\\test) : × AVASCALE puis
      VeraLux → le cœur retrouve son dégradé ;
  [5] non-régression : image déjà dans [0,1] → rendu inchangé (comparé à un
      appel DIRECT du moteur, ce que faisait l'ancien code) ; la vue « tel que
      vu » == etirer(normaliser_lin(·)) ;
  [6] le tableau de l'appelant n'est plus écrasé (l'ancien `np.clip(out=img)`
      écrivait dans l'image reçue).

Exécution : python bancs/_test_coeur_crame_jalon64.py
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from avastack.processing import veralux as V                       # noqa: E402
from avastack.processing.display import DisplayProcessor           # noqa: E402
from veralux_core_headless import solve_and_stretch                # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --------------------------------------------------------------------------
# Scène type M31 à l'ÉCHELLE MÉMOIRE de ses empilements : ciel 0,030 (unité
# fichier), cœur 10× le ciel, une étoile saturée à 1,0 ; ECHELLE = 15,271 =
# l'AVASCALE réel de son empilement 115 frames.
# --------------------------------------------------------------------------
ECHELLE = 15.271
H, W = 400, 600
rng = np.random.default_rng(11)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
cy, cx = (H - 1) / 2.0, (W - 1) / 2.0
rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
CIEL_F = 0.030                                   # unité fichier [0,1]
coeur_f = 0.300 * np.exp(-rr / 60.0)             # 10× le ciel au centre
POIDS = np.array([1.00, 0.80, 0.55], np.float32)  # M31 : R > G > B
bruit = rng.normal(0.0, 0.0006, (H, W)).astype(np.float32)
scene_f = ((CIEL_F + coeur_f + bruit)[..., None] * POIDS).astype(np.float32)
scene_f[H // 4, W // 3, :] = 1.0                 # étoile saturée (le max)
scene = (scene_f * ECHELLE).astype(np.float32)   # ce que voit l'appli (H, W, 3)
print(f"scène : {scene.shape} · ciel R {np.median(scene[..., 0]):.3f} · "
      f"cœur G {scene[H // 2, W // 2, 1]:.3f} · max {scene.max():.3f} "
      f"(échelle mémoire, AVASCALE {ECHELLE})")

print("[1] normaliser_lin")
petit = (scene_f * 0.5).astype(np.float32)        # déjà ≤ 1
n1 = V.normaliser_lin(petit)
verifie(np.array_equal(n1, petit),
        "max ≤ 1 → image renvoyée TELLE QUELLE (aucun facteur retiré)")
copie_scene = scene.copy()
n2 = V.normaliser_lin(copie_scene)
verifie(abs(float(n2.max()) - 1.0) < 1e-6,
        f"max > 1 → ramenée à 1,0 (obtenu {float(n2.max()):.6f})")
rapport = ((n2[200, 300, 1] - n2[10, 10, 1])
           / max(scene[200, 300, 1] - scene[10, 10, 1], 1e-9))
verifie(abs(rapport - 1.0 / ECHELLE) < 1e-5,
        f"UN SEUL facteur global : les écarts entre pixels suivent ×1/{ECHELLE} "
        f"(mesuré ×{rapport:.6f}) — linéarité et canaux intacts")
sale = scene.copy()
sale[5, 5], sale[6, 6], sale[7, 7], sale[8, 8] = -3.0, np.nan, np.inf, -np.inf
propre = V.normaliser_lin(sale)
verifie(bool(np.isfinite(propre).all()) and float(propre.min()) >= 0.0,
        "négatifs ramenés à 0, NaN/Inf neutralisés (recalage géométrique)")
verifie(np.array_equal(copie_scene, scene),
        "l'image d'entrée n'est pas modifiée (l'ancien clip écrivait dedans)")

print("[2] le rendu ne dépend plus de l'échelle de l'empilement")
triple = (scene * 3.0).astype(np.float32)
r1, ld1, _ = V.etirer(scene)
r3, ld3, _ = V.etirer(triple)
ecart = float(np.max(np.abs(r1 - r3)))
verifie(ecart < 2e-5,
        f"etirer(x) == etirer(3·x) (écart max {ecart:.2e}) — le rendu ne dépend "
        f"plus de l'échelle arbitraire de l'empilement")
ancien, _, _ = V.etirer(np.clip(scene, 0.0, 1.0))   # ancien chemin : coupe puis étirement
ecart_ancien = float(np.max(np.abs(r1 - ancien)))
verifie(ecart_ancien > 0.02,
        f"l'ANCIEN chemin (coupe à 1,0) donnait un AUTRE rendu (écart max "
        f"{ecart_ancien:.3f}) : c'est le bug corrigé")


print("[3] le cœur garde son DÉGRADÉ (l'ancien chemin le rendait plat)")


def profil(out):
    """Médianes du canal vert par anneau du cœur (r < 90 px)."""
    return [float(np.median(out[..., 1][(rr >= a) & (rr < b)])) * 100.0
            for a, b in ((0, 10), (10, 20), (20, 30), (30, 45), (45, 60), (60, 90))]


p_new, p_old = profil(r1), profil(ancien)
print("    anneaux (px)     0-10  10-20  20-30  30-45  45-60  60-90")
print("    avant (coupe)  " + "".join(f"{v:7.2f}" for v in p_old))
print("    après (facteur)" + "".join(f"{v:7.2f}" for v in p_new))
etendue_new = max(p_new) - min(p_new)
etendue_old = max(p_old) - min(p_old)
verifie(etendue_new > 8.0,
        f"après correctif : le cœur s'étale sur {etendue_new:.2f} points de % "
        f"entre le centre et son bord (dégradé visible)")
verifie(etendue_old < 1.0,
        f"avant correctif : {etendue_old:.2f} point de % seulement (PLAT — "
        f"c'est le « cramé »)")
verifie(p_new[0] > p_new[-1] + 5.0,
        f"le cœur est plus clair au centre qu'au bord ({p_new[0]:.2f} % → "
        f"{p_new[-1]:.2f} %) : le noyau est de nouveau visible")

print("[5] non-régression : image déjà dans [0,1] et vue « tel que vu »")
# L'ancien code passait au moteur l'image CLIPPÉE ; pour une image ≤ 1 la coupe
# était sans effet : le rendu doit donc être IDENTIQUE à un appel direct.
direct, ld_direct, _ = solve_and_stretch(
    V.normaliser_lin(petit), working_space=V.PROFIL_PAR_DEFAUT,
    target_bg=V.TARGET_BG_PAR_DEFAUT, protect_b=V.PROTECT_B_PAR_DEFAUT,
    convergence_power=V.CONVERGENCE_POWER_PAR_DEFAUT, use_adaptive_anchor=True,
    log_d_override=None, color_grip=1.0, shadow_convergence=0.0)
direct = direct.transpose(1, 2, 0)          # le moteur rend (3, H, W)
via, ld_via, _ = V.etirer(petit)
verifie(float(np.max(np.abs(via - direct))) < 1e-7 and ld_via == ld_direct,
        "image ≤ 1 : étirement INCHANGÉ (aucun facteur ajouté) — non-régression")
dp = DisplayProcessor()
dp.stretch = "veralux"
vue = dp.rendu_pleine_resolution(scene.copy())
ref, ld_ref, _ = V.etirer(scene)
verifie(float(np.max(np.abs(vue - ref))) < 1e-6,
        "vue « tel que vu » (rendu_pleine_resolution) == etirer(normaliser_lin(·))")

print("[6] le tableau de l'appelant n'est plus écrasé")
avant = scene.copy()
V.etirer(avant)
verifie(np.array_equal(avant, scene),
        "etirer() n'écrit plus dans l'image reçue (l'ancien np.clip(out=img) "
        "la coupait à 1,0 sur place)")

print("[4] ses fichiers réels (si présents)")
DOSSIER = r"C:\Astro\test"
import cv2                                                   # noqa: E402
from astropy.io import fits                                   # noqa: E402
for nom in ("M31_traite_lineaire_2.37.1.fits",
            "m31_stack_lineaire_traite-v2.36.1_115frames.fits"):
    p = os.path.join(DOSSIER, nom)
    if not os.path.isfile(p):
        print(f"    ({nom} absent — test ignoré)")
        continue
    h = fits.open(p)
    d = h[0].data.astype(np.float32)
    ava = float(h[0].header.get("AVASCALE", 1.0))
    img = np.transpose(d, (1, 2, 0)).copy()
    memoire = img * ava                       # l'image telle que l'appli la voit
    lum = 0.2126 * d[0] + 0.7152 * d[1] + 0.0722 * d[2]
    petit2 = cv2.resize(lum, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    iy, ix = np.unravel_index(np.argmax(cv2.GaussianBlur(petit2, (0, 0), 15)),
                              petit2.shape)
    gy, gx = int(iy * 4), int(ix * 4)
    Y, X = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    rg = np.sqrt((X - gx) ** 2 + (Y - gy) ** 2)
    f_ava = float((memoire > 1.0).mean() * 100)
    out_f, _, _ = V.etirer(img)
    out_m, _, _ = V.etirer(np.clip(memoire, 0.0, 1.0))
    a = [float(np.median(out_f[..., 1][(rg >= x) & (rg < y)])) * 100
         for x, y in ((0, 10), (10, 20), (20, 30), (30, 45), (45, 60))]
    b = [float(np.median(out_m[..., 1][(rg >= x) & (rg < y)])) * 100
         for x, y in ((0, 10), (10, 20), (20, 30), (30, 45), (45, 60))]
    print(f"    {nom} — AVASCALE {ava:.2f} ({f_ava:.2f} % de l'image au-dessus "
          f"de 1,0 avant le correctif)")
    print("      avant (coupe)  " + "".join(f"{v:7.2f}" for v in b))
    print("      après (facteur)" + "".join(f"{v:7.2f}" for v in a))
    verifie(max(b) - min(b) < 1.0 and max(a) - min(a) > 5.0,
            f"cœur PLAT avant ({max(b) - min(b):.2f} pt) et DÉGRADÉ après "
            f"({max(a) - min(a):.2f} pt)")

print()
print("BANC " + ("RÉUSSI" if ok else "EN ÉCHEC"))
sys.exit(0 if ok else 1)
