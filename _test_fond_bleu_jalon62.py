# -*- coding: utf-8 -*-
"""Banc v2.36.1 — LE FOND BLEU, DEUX CAUSES, DEUX CORRECTIFS.

Constats d'Alain (25/09/2026, v2.36.0) :
  • « Le fichier tel que vu en png : PROBLEME, vachement bleu et ca me fait ca
    depuis le début je pense, donc problème vieux » — alors que le FITS du même
    écran était juste ;
  • « il reste quand même pas mal de bruit bleu » et le fond reste bleu à
    l'écran.

DEUX CAUSES INDÉPENDANTES, mesurées sur ses fichiers :
  ① `save_image` écrivait les PNG/TIFF avec R et B PERMUTÉS : `cv2.imencode`
     attend du BGR alors que toute l'appli travaille en RGB (et `load_image`
     convertit à la lecture). L'aller-retour interne restait donc cohérent — le
     bug ne se voyait QUE dans les fichiers exportés. Mesuré sur son PNG :
     PNG_R ≈ FITS_B et PNG_B ≈ FITS_R (corrélation 1,0000).
  ② l'étirement VeraLux soustrait une ANCRE (scalaire lu dans l'histogramme de
     luminance) puis étire en log : pour le fond, seul compte le RÉSIDU
     (niveau du canal − ancre) → quelques pour cent d'écart de ciel deviennent
     un facteur ~2,4 de couleur de fond. Mesuré sur son empilement linéaire
     (fond pourtant NEUTRE : R/G 0,9991 · B/G 0,9991) : ciels 0,0321 / 0,0326 /
     0,0332, ancre 0,0313 → résidus 1 : 1,70 : 2,44 → fond étiré R/G 0,363 ·
     B/G 1,611 (franchement bleu). L'équilibrage des canaux ne l'enlève pas :
     il estime le fond sur un PERCENTILE BAS (les coins, déjà neutres) alors que
     l'ancre vit dans l'histogramme GLOBAL.

Vérifie :
  [1] PNG/TIFF : plus de permutation R/B (lecture INDÉPENDANTE : OpenCV brut et
      PIL quand il est là), et l'aller-retour interne par load_image est intact ;
      le FITS (C, H, W) n'a pas bougé ;
  [2] `couleurs.gains_fond` / `neutraliser_fond` : gains ~2 %, fond neutralisé,
      couleur de l'objet préservée à 2 %, garde-fou ±18 %, no-op sur mono,
      image neutre et canal mort ;
  [3] LA propriété décisive : sur une scène synthétique aux valeurs RÉELLES
      mesurées chez Alain, VeraLux transforme un ciel bleui de 1,7 % en fond
      R/G 0,35 · B/G 1,55 ; avec la neutralisation AVANT étirement, le fond
      étiré redevient neutre (0,95 / 0,94) ;
  [4] branchement : case COCHÉE par défaut, posée sur le solveur (clé de
      réglages → re-résolution), persistée en config, et présente dans le chemin
      de sauvegarde « tel que vu » — MAIS jamais dans la 3e sortie LINÉAIRE, qui
      reste « empilement + corrections » (verrouillé par le banc jalon 59 [6] : le
      premier jet l'avait polluée, le banc l'a attrapé).

Exécution : python _test_fond_bleu_jalon62.py
"""
import os
import sys
import tempfile
import tkinter as tk

import numpy as np

from avastack.images import find_output, load_image, save_image   # noqa: E402
from avastack.processing import couleurs as C                    # noqa: E402
from avastack.processing import veralux as V                     # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


racine = tempfile.mkdtemp(prefix="avastack_j62_")

# ================================================= [1] PNG/TIFF : plus de R/B
print("[1] save_image : PNG/TIFF en RGB (plus de permutation R et B)")
# Image témoin : un carré ROUGE, un VERT, un BLEU (chacun dans son coin).
H = W = 60
temoins = {
    "R": (0.9, 0.05, 0.05),
    "G": (0.05, 0.9, 0.05),
    "B": (0.05, 0.05, 0.9),
}
img = np.zeros((H, W, 3), np.float32)
img[:H // 2, :W // 2] = temoins["R"]
img[:H // 2, W // 2:] = temoins["G"]
img[H // 2:, :W // 2] = temoins["B"]


def triplets(a):
    """Couleur MOYENNE des trois carrés témoins (R en haut à gauche, G en haut à
    droite, B en bas à gauche), normalisée en [0..1] selon le type lu."""
    a = np.asarray(a)
    if a.dtype == np.uint16:              # PNG/TIFF 16 bits (OpenCV brut)
        a = a.astype(np.float32) / 65535.0
    elif a.dtype == np.uint8:
        a = a.astype(np.float32) / 255.0
    else:
        a = a.astype(np.float32)
    return [a[5:25, 5:25].reshape(-1, 3).mean(0),      # carré ROUGE
            a[5:25, -25:-5].reshape(-1, 3).mean(0),    # carré VERT
            a[-25:-5, 5:25].reshape(-1, 3).mean(0)]    # carré BLEU


def controle_couleurs(lus, etiquette):
    """Chaque carré doit montrer SA couleur dominante (le bug historique donnait
    R et B échangés : le carré rouge sortait bleu)."""
    def vu(carre, canal, dominante):
        i = "RGB".index(canal)
        autre = [k for k in range(3) if k != i]
        return (abs(carre[i] - dominante) < 0.02
                and all(carre[k] < 0.10 for k in autre))
    r, g, b = lus
    verifie(vu(r, "R", 0.9), f"{etiquette} : carré ROUGE lu rouge "
                             f"({np.round(r, 3).tolist()})")
    verifie(vu(g, "G", 0.9), f"{etiquette} : carré VERT lu vert "
                             f"({np.round(g, 3).tolist()})")
    verifie(vu(b, "B", 0.9), f"{etiquette} : carré BLEU lu bleu "
                             f"({np.round(b, 3).tolist()})")


import cv2                                                    # noqa: E402

for ext in (".png", ".tif"):
    p = os.path.join(racine, "temoins" + ext)
    save_image(p, img)
    # Lecture INDÉPENDANTE (OpenCV brut, remis en RGB par NOUS : aucun appel à
    # load_image ici, sinon le contrôle serait circulaire — c'est justement la
    # conversion de load_image qui masquait le bug en aller-retour).
    brut = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_UNCHANGED)
    if brut is not None and brut.ndim == 3 and brut.shape[2] == 3:
        brut = cv2.cvtColor(brut, cv2.COLOR_BGR2RGB)
    controle_couleurs(triplets(brut), f"{ext} (OpenCV brut)")
    relu = load_image(p)
    verifie(float(np.abs(relu - img).max()) < 0.02,
            f"{ext} : aller-retour interne intact (écart max "
            f"{float(np.abs(relu - img).max()):.4f})")
    if ext == ".png":
        try:
            from PIL import Image
            pil = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255.0
            controle_couleurs(triplets(pil), "PNG (lecteur PIL, 2e avis)")
        except ImportError:
            print("  (PIL absent : contrôle croisé ignoré)")
fits = os.path.join(racine, "temoins.fits")
save_image(fits, img)
relu = load_image(fits)
verifie(float(np.abs(relu - img).max()) < 0.02,
        "FITS : canaux sur NAXIS3 inchangés (aller-retour intact)")

# ================================[2] gains_fond / neutraliser_fond : le remède
print("[2] couleurs.neutraliser_fond : ~2 % de gains, objet préservé, garde-fous")

# Scène synthétique aux valeurs RÉELLES mesurées chez Alain (ciels 0,0321 /
# 0,0326 / 0,0332 et σ 0,00040 / 0,00033 / 0,00040) : un ciel bleui de 1,7 %,
# une galaxie jaune, le bruit de son empilement.
CIEL = (0.0321, 0.0326, 0.0332)
SIGM = (0.00040, 0.00033, 0.00040)
AMPL = (1.00, 0.62, 0.44)
H2, W2 = 700, 1000
yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float32)
rr = np.sqrt((xx - W2 / 2) ** 2 + (yy - H2 / 2) ** 2)
noyau = 0.9 * np.exp(-(rr / 30.0) ** 2) + 0.25 * np.exp(-(rr / 110.0) ** 2)
rng = np.random.default_rng(3)
scene = np.stack([CIEL[c] + AMPL[c] * noyau + rng.normal(0, SIGM[c], (H2, W2))
                  for c in range(3)], -1)
scene = np.clip(scene, 0, 1).astype(np.float32)


def fond(a):
    """Niveau du fond par canal : médiane de la moitié la plus sombre."""
    a = np.asarray(a, np.float32)
    lum = a.mean(-1)
    m = lum <= np.percentile(lum, 50)
    return [float(np.median(a[..., c][m])) for c in range(3)]


g = C.gains_fond(scene)
verifie(g is not None and 1.005 < g[0] < 1.05 and 0.95 < g[2] < 0.995,
        f"gains mesurés ≈ 2 % (R ×{g[0]:.4f} · G ×{g[1]:.4f} · B ×{g[2]:.4f})")
f0 = fond(scene)
verifie(abs(f0[0] / f0[1] - 1) > 0.01,
        f"la scène de départ a bien un ciel BLEUI ({f0[0]/f0[1]:.4f} · "
        f"{f0[2]/f0[1]:.4f} — R et B autour de G)")
neutre = C.neutraliser_fond(scene)
f1 = fond(neutre)
verifie(abs(f1[0] / f1[1] - 1) < 2e-3 and abs(f1[2] / f1[1] - 1) < 2e-3,
        f"fond NEUTRE après correction ({f1[0]/f1[1]:.4f} · {f1[2]/f1[1]:.4f})")
# La couleur de l'OBJET ne doit pas bouger (les gains sont appliqués partout).
c0 = scene[350:360, 495:505].reshape(-1, 3).mean(0)
c1 = neutre[350:360, 495:505].reshape(-1, 3).mean(0)
ecart = max(abs(c1[k] / c1[1] - c0[k] / c0[1]) for k in (0, 2))
verifie(ecart < 0.035,
        f"couleur du cœur de la galaxie préservée (écart de rapport "
        f"{ecart*100:.2f} % — c'est l'ampleur même de la correction, "
        f"appliquée à toute l'image)")
# Garde-fous : mono, image neutre, canal mort, et borne ±18 %.
verifie(C.gains_fond(np.zeros((10, 10), np.float32)) is None,
        "image MONO (H, W) : pas de gains (None)")
verifie(tuple(C.gains_fond(np.full((10, 10, 3), 0.5, np.float32))) == (1.0, 1.0,
                                                                       1.0),
        "image déjà NEUTRE : gains unitaires")
mort = scene.copy()
mort[..., 1] = 0.0
verifie(C.gains_fond(mort) is None, "canal VERT mort : aucun gain proposé")
aberrant = np.stack([np.full((20, 20), 0.10, np.float32),
                     np.full((20, 20), 0.20, np.float32),
                     np.full((20, 20), 0.40, np.float32)], -1)
ga = C.gains_fond(aberrant)
verifie(all(abs(v - 1.0) <= 0.1001 for v in ga),
        f"ciel aberrant (2× plus vert) : correction BORNÉE à ±10 % "
        f"({np.round(ga, 3).tolist()}) — c'est la borne qui rend l'option sûre "
        f"même sur un cadrage dominé par un objet")
h = C.neutraliser_fond(scene, force=0.5)
verifie(float(np.abs(h - scene).max()) < float(np.abs(neutre - scene).max()),
        "force 0,5 : correction ATTÉNUÉE (plus proche de l'original)")
verifie(float(np.abs(C.neutraliser_fond(scene) - scene).max()) > 1e-4,
        "l'image d'origine n'est JAMAIS modifiée en place")

# =============[3] LA PREUVE : VeraLux faisait d'un ciel bleui un fond bleu
print("[3] la preuve : 1,7 % de bleu de ciel -> fond bleu après VeraLux (corrigé)")
res = {}
for nom, src in (("sans correction", scene), ("avec neutralisation", neutre)):
    out = np.asarray(V.etirer(src, mode=V.MODE_TARGET_BG, target_bg=0.20)[0],
                     np.float32)
    ff = fond(out)
    res[nom] = (ff[0] / ff[1], ff[2] / ff[1])
    print(f"    {nom:<20} : fond étiré R/G {res[nom][0]:.3f} · "
          f"B/G {res[nom][1]:.3f}")
verifie(res["sans correction"][1] > 1.35 and res["sans correction"][0] < 0.7,
        f"sans correction : fond étiré franchement BLEU (R/G "
        f"{res['sans correction'][0]:.3f} · B/G "
        f"{res['sans correction'][1]:.3f}) — c'est le défaut constaté")
verifie(0.85 < res["avec neutralisation"][1] < 1.12
        and 0.85 < res["avec neutralisation"][0] < 1.12,
        f"avec neutralisation : fond étiré NEUTRE (R/G "
        f"{res['avec neutralisation'][0]:.3f} · B/G "
        f"{res['avec neutralisation'][1]:.3f})")

# =====================================[4] branchement UI / solveur / config
print("[4] branchement : case cochée par défaut, transportée, persistée")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui                     # noqa: E402
ui.CONFIG = {}
vus = []
ui.sauver_config = lambda d: vus.append(d)
app = ui.App(root)
verifie(hasattr(app, "var_vl_neutre")
        and bool(app.var_vl_neutre.get()) is True,
        "case « Neutraliser la couleur du fond (live) » présente et COCHÉE "
        "par défaut")
verifie(bool(app.disp.vl_neutre_fond) is True,
        "le solveur démarre avec la neutralisation active (défaut du display)")
# La clé des réglages doit CHANGER : c'est elle qui relance la résolution.
cle_on = app.disp._vl_params()
app.var_vl_neutre.set(False)
app._on_vl_neutre()
cle_off = app.disp._vl_params()
verifie(cle_on != cle_off and bool(app.disp.vl_neutre_fond) is False,
        "décochée : le solveur ne neutralise plus (clé de réglages changée → "
        "re-résolution)")
# TRANSPORT de bout en bout : on SOUMET un job au vrai solveur VeraLux et on
# attend qu'il publie le résultat. Inspecter `_vl_job` serait couru (le thread
# worker le consomme immédiatement) : ce qui compte est que l'option ARRIVE
# jusqu'au calcul — et `vl_neutre_gains` en est la preuve publiée.
import time                                                   # noqa: E402


def _attendre(predicat, delai=60.0):
    t0 = time.time()
    while time.time() - t0 < delai:
        if predicat():
            return True
        time.sleep(0.2)
    return False


petite = scene[0:192, 0:192].astype(np.float32)   # cadrage dominé par le CIEL
                                                  # (cas réel d'usage : le fond)
app.disp.reset()
app.var_vl_neutre.set(True)
app._on_vl_neutre()
app.disp.notify_new_stack()
app.disp._process_veralux(petite, live=False)
fait = _attendre(lambda: not app.disp._vl_pending
                 and app.disp.vl_neutre_gains is not None)
gains_job = app.disp.vl_neutre_gains
verifie(fait and gains_job is not None,
        "case cochée : le solveur VERA LUX a bien neutralisé le fond "
        f"(gains publiés {None if gains_job is None else np.round(gains_job, 4).tolist()})")
verifie(gains_job is not None and 1.004 < gains_job[0] < 1.05
        and 0.95 < gains_job[2] < 0.996,
        "les gains appliqués par le solveur sont ceux attendus (~2 %, R en "
        "hausse et B en baisse)")
app.var_vl_neutre.set(False)
app._on_vl_neutre()
app.disp.reset()
app.disp.notify_new_stack()
app.disp._process_veralux(petite, live=False)
_attendre(lambda: not app.disp._vl_pending and app.disp.vl_neutre_gains is None)
verifie(app.disp.vl_neutre_gains is None,
        "case décochée : le solveur ne publie AUCUN gain (aucune correction)")
# Persistance : valeur explicite dans les deux sens.
app.var_vl_neutre.set(True)                      # on repart de la case cochée
app._on_vl_neutre()
app._sauver_config_app()
verifie(vus and bool(vus[-1].get("vl_neutre_fond")) is True,
        "config : « vl_neutre_fond » = True persistée (case cochée)")
ui.CONFIG = {"vl_neutre_fond": False}
app.var_vl_neutre.set(True)
app._on_vl_neutre()
app._restaurer_config()
verifie(bool(app.var_vl_neutre.get()) is False
        and bool(app.disp.vl_neutre_fond) is False,
        "config relue : case décochée restaurée dans l'UI ET dans le solveur")
# Le chemin de SAUVEGARDE « tel que vu » doit transporter le réglage.
app.var_vl_neutre.set(True)
app._on_vl_neutre()
verifie(bool(app._reglages_rendu().get("vl_neutre_fond")) is True,
        "transmise au chemin de sauvegarde « tel que vu » (même rendu qu'à "
        "l'écran)")
root.destroy()

# ===================[5] SUR UN FICHIER RÉEL (optionnel) : tout en une commande
if len(sys.argv) > 1:
    print(f"[5] mesure sur un fichier RÉEL : {os.path.basename(sys.argv[1])}")
    reel = load_image(sys.argv[1])
    if reel.ndim == 2:
        print("  (fichier mono : rien à mesurer pour la couleur du fond)")
    else:
        f = fond(reel)
        gr = C.gains_fond(reel)
        print(f"    fond R/G/B  {f[0]:.5f} / {f[1]:.5f} / {f[2]:.5f} "
              f"→ R/G {f[0]/f[1]:.4f} · B/G {f[2]/f[1]:.4f}")
        print(f"    gains proposés : "
              f"{None if gr is None else np.round(gr, 4).tolist()}")
        for nom, src in (("sans correction", reel),
                         ("avec neutralisation", C.neutraliser_fond(reel))):
            out = np.asarray(V.etirer(src, mode=V.MODE_TARGET_BG,
                                      target_bg=0.20)[0], np.float32)
            ff = fond(out)
            print(f"    {nom:<20} : fond ÉTIRÉ R/G {ff[0]/ff[1]:.3f} · "
                  f"B/G {ff[2]/ff[1]:.3f}")
        # Le bug historique des PNG : on écrit le fichier réel en PNG avec le
        # code CORRIGÉ et on relit chaque canal (doit être du même canal).
        png = os.path.join(racine, "reel.png")
        save_image(png, reel)
        essaye = False
        try:
            from PIL import Image
            lu = np.asarray(Image.open(png).convert("RGB"), np.float32) / 255.0
            essaye = True
        except ImportError:
            lu = cv2.cvtColor(cv2.imdecode(np.fromfile(png, np.uint8),
                                           cv2.IMREAD_UNCHANGED),
                              cv2.COLOR_BGR2RGB).astype(np.float32) / 65535.0
            essaye = True
        if essaye:
            for i, ci in enumerate("RGB"):
                corr = float(np.corrcoef(reel[..., i].ravel()[::7],
                                         lu[..., i].ravel()[::7])[0, 1])
                print(f"    PNG {ci} ~ FITS {ci} : corrélation {corr:.4f} "
                      f"(≈ 1 = canaux NON permutés)")
            permute = all(float(np.corrcoef(reel[..., i].ravel()[::7],
                                            lu[..., 2 - i].ravel()[::7])[0, 1])
                          > 0.999 for i in (0, 2))
            verifie(not permute,
                    "fichier réel : le PNG écrit ne permute plus R et B "
                    "(c'était le bug « vachement bleu »)")

print()
print("RÉSULTAT :", "TOUT OK" if ok else "ÉCHECS À CORRIGER")
sys.exit(0 if ok else 1)

