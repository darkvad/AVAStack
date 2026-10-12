# -*- coding: utf-8 -*-
"""Banc du jalon 122 (v2.74.0) — PIÉDESTAL PAR CANAL avant l'étirement VeraLux.

« Amener les niveaux de ciel des trois canaux au MÊME niveau, par des OFFSETS
(soustraction) et non des gains. » Cause racine (mesurée, M33) : l'ANCRE de
VeraLux SOUTRAIT un scalaire puis étire en log → un écart de ciel par canal y
est amplifié ×20 à ×40 (fond cyan/magenta) ; une correction de MÊME NATURE (un
offset) l'annule, là où les gains de `neutraliser_fond` visaient « 0,7 % à
côté » et FABRIQUAIENT le magenta.

Vérifie :
  [1] `couleurs.niveaux_ciel_canaux` : mono → None, RGB → les 3 niveaux, canal
      mort → None, entrée jamais modifiée ;
  [2] `couleurs.piedestal_canaux` : ciels ALIGNÉS, objet préservé à l'ordre de la
      correction, mono/neutre/canal mort → no-op, force atténue, garde borne ;
  [3] intégration `veralux.etirer` : un ciel bleui devient un FOND NEUTRE avec le
      piédestal, et reste franchement coloré SANS (`piedestal=False`) ;
  [4] non-régression : mono et RGB neutre rendus INCHANGÉS, déterminisme.

Exécution (interpréteur du venv) :
    python bancs/_test_piedestal_canaux_jalon122.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np

# Sortie redirigée (fichier/pipe) → cp1252 ne sait pas encoder →/— des prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from avastack.processing import couleurs as C                       # noqa: E402
from avastack.processing import veralux as V                        # noqa: E402

ok = True


def verifie(cond, msg):
    print(("  OK  " if cond else "  ECHEC ") + msg)
    return bool(cond)


# Scene aux valeurs REELLES mesurees chez Alain (ciels 0,0321 / 0,0326 / 0,0332,
# un ciel bleui de 1,7 % ; bruit de son empilement ; galaxie jaune au centre).
CIEL = (0.0321, 0.0326, 0.0332)
SIGM = (0.00040, 0.00033, 0.00040)
AMPL = (1.00, 0.62, 0.44)
H, W = 700, 1000
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2)
noyau = 0.9 * np.exp(-(rr / 30.0) ** 2) + 0.25 * np.exp(-(rr / 110.0) ** 2)
rng = np.random.default_rng(3)
scene = np.stack([CIEL[c] + AMPL[c] * noyau + rng.normal(0, SIGM[c], (H, W))
                  for c in range(3)], -1)
scene = np.clip(scene, 0, 1).astype(np.float32)


def fond(a):
    """Niveau du fond par canal : médiane de la moitié la plus sombre (le MÊME
    estimateur que le piédestal — c'est ce qui rend la mesure honnête)."""
    a = np.asarray(a, np.float32)
    lum = a.mean(-1)
    m = lum <= np.percentile(lum, 50)
    return [float(np.median(a[..., c][m])) for c in range(3)]


print("=" * 78)
print("[1] couleurs.niveaux_ciel_canaux : les TROIS niveaux de ciel")
print("=" * 78)
niv = C.niveaux_ciel_canaux(scene)
verifie(niv is not None and len(niv) == 3,
        f"RGB : trois niveaux rendus {None if niv is None else np.round(niv, 5).tolist()}")
verifie(niv is not None and all(abs(niv[c] - CIEL[c]) < 2e-3 for c in range(3)),
        "les niveaux retrouvent les ciels de la scène (à ±0,002)")
verifie(C.niveaux_ciel_canaux(np.zeros((10, 10), np.float32)) is None,
        "image MONO (H, W) : aucun niveau (None)")
mort = scene.copy()
mort[..., 1] = 0.0
verifie(C.niveaux_ciel_canaux(mort) is None,
        "canal VERT mort : aucun niveau proposé (None)")
garde_scene = scene.copy()
_ = C.niveaux_ciel_canaux(scene)
verifie(np.array_equal(scene, garde_scene),
        "l'image d'origine n'est JAMAIS modifiée (niveaux_ciel_canaux)")

print()
print("=" * 78)
print("[2] couleurs.piedestal_canaux : CIEUX ALIGNÉS, objet préservé, garde-fous")
print("=" * 78)
f0 = fond(scene)
verifie(abs(f0[0] / f0[1] - 1) > 0.01 or abs(f0[2] / f0[1] - 1) > 0.001,
        f"la scène de départ a bien un ciel COLORÉ (R/G {f0[0]/f0[1]:.4f} · "
        f"B/G {f0[2]/f0[1]:.4f})")
pied = C.piedestal_canaux(scene)
f1 = fond(pied)
verifie(abs(f1[0] / f1[1] - 1) < 3e-3 and abs(f1[2] / f1[1] - 1) < 3e-3,
        f"fond ALIGNÉ après piédestal (R/G {f1[0]/f1[1]:.4f} · "
        f"B/G {f1[2]/f1[1]:.4f}) — les trois ciels au MÊME niveau")
# La couleur de l'OBJET bouge de l'AMPLEUR même de la correction (un offset
# n'est pas un gain : il ne préserve pas les rapports, mais il reste minuscule).
c0 = scene[350:360, 495:505].reshape(-1, 3).mean(0)
c1 = pied[350:360, 495:505].reshape(-1, 3).mean(0)
ecart = max(abs(c1[k] / c1[1] - c0[k] / c0[1]) for k in (0, 2))
verifie(ecart < 0.05,
        f"couleur du cœur de la galaxie ~préservée (écart de rapport "
        f"{ecart*100:.2f} % — l'ampleur même de la correction)")
verifie(float(np.abs(C.piedestal_canaux(scene) - scene).max()) > 1e-4,
        "l'image d'origine n'est JAMAIS modifiée en place (piedestal_canaux)")
verifie(np.array_equal(C.piedestal_canaux(scene, force=0.0), scene),
        "force 0 : no-op au bit près")
demi = C.piedestal_canaux(scene, force=0.5)
verifie(float(np.abs(demi - scene).max()) < float(np.abs(pied - scene).max()),
        "force 0,5 : correction ATTÉNUÉE (plus proche de l'original)")
verifie(np.array_equal(C.piedestal_canaux(np.zeros((10, 10), np.float32)),
                       np.zeros((10, 10), np.float32)),
        "image MONO : renvoyée inchangée")
neutre = np.full((10, 10, 3), 0.5, np.float32)
verifie(np.array_equal(C.piedestal_canaux(neutre), neutre),
        "image déjà NEUTRE : renvoyée inchangée (au bit près)")
verifie(np.array_equal(C.piedestal_canaux(mort), mort),
        "canal mort : renvoyé inchangé")
aberrant = np.stack([np.full((40, 40), 0.10, np.float32),
                     np.full((40, 40), 0.20, np.float32),
                     np.full((40, 40), 0.40, np.float32)], -1)
borne = 0.10 * 0.20                       # garde 0,10 × niveau médian (0,20)
fa = fond(C.piedestal_canaux(aberrant))                        # garde par défaut
flibre = fond(C.piedestal_canaux(aberrant, garde=10.0))        # sans borne efficace
residu = [abs(fa[c] - 0.20) for c in range(3)]
attendu = [max(0.0, e - borne) for e in (0.10, 0.0, 0.20)]
verifie(all(abs(residu[c] - attendu[c]) < 1e-6 for c in range(3)),
        f"ciel aberrant (2× plus vert) : correction BORNÉE à ±{borne:.3f} "
        f"(résidus {np.round(residu, 4).tolist()}) — c'est la borne qui rend "
        f"l'option sûre même sur un cadrage dominé par un objet")
verifie(all(abs(v - 0.20) < 1e-6 for v in flibre),
        "sans borne (garde large), la même correction est PARFAITE — preuve que "
        "c'est bien la borne, et non la mesure, qui limite l'offset")

print()
print("=" * 78)
print("[3] L'INTÉGRATION : un ciel bleui sort NEUTRE après étirement (coloré sans)")
print("=" * 78)
verifie(V.moteur_disponible(), "moteur VeraLux disponible")
sans, _, _ = V.etirer(scene, mode=V.MODE_TARGET_BG, target_bg=0.20,
                      piedestal=False)
avec, _, _ = V.etirer(scene, mode=V.MODE_TARGET_BG, target_bg=0.20,
                      piedestal=True)
fs, fa2 = fond(sans), fond(avec)
print(f"    sans piédestal : fond étiré R/G {fs[0]/fs[1]:.3f} · B/G {fs[2]/fs[1]:.3f}")
print(f"    avec piédestal : fond étiré R/G {fa2[0]/fa2[1]:.3f} · B/G {fa2[2]/fa2[1]:.3f}")
verifie(abs(fs[2] / fs[1] - 1) > 0.3,
        "SANS piédestal : fond étiré franchement COLORÉ (c'est le défaut constaté)")
verifie(abs(fa2[0] / fa2[1] - 1) < 0.15 and abs(fa2[2] / fa2[1] - 1) < 0.15,
        "AVEC piédestal : fond étiré NEUTRE (R/G et B/G proches de 1)")

print()
print("=" * 78)
print("[4] NON-RÉGRESSION : mono et neutre INCHANGÉS, déterminisme")
print("=" * 78)
mono = scene[..., 1].copy()
m1, _, _ = V.etirer(mono, mode=V.MODE_TARGET_BG, target_bg=0.20, piedestal=True)
m2, _, _ = V.etirer(mono, mode=V.MODE_TARGET_BG, target_bg=0.20, piedestal=False)
verifie(np.array_equal(m1, m2),
        "image MONO : rendu IDENTIQUE avec/sans piédestal (aucune couleur à aligner)")
neutre_rgb = np.full((64, 64, 3), 0.2, np.float32)
n1, _, _ = V.etirer(neutre_rgb, mode=V.MODE_TARGET_BG, target_bg=0.20,
                    piedestal=True)
n2, _, _ = V.etirer(neutre_rgb, mode=V.MODE_TARGET_BG, target_bg=0.20,
                    piedestal=False)
verifie(float(np.max(np.abs(n1 - n2))) < 1e-6,
        "RGB déjà NEUTRE : rendu inchangé (aucun offset appliqué)")
d1, _, _ = V.etirer(scene, mode=V.MODE_TARGET_BG, target_bg=0.20)
d2, _, _ = V.etirer(scene, mode=V.MODE_TARGET_BG, target_bg=0.20)
verifie(np.array_equal(d1, d2), "deux appels = résultat identique (déterministe)")

print()
print("===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)
