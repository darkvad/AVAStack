# -*- coding: utf-8 -*-
"""Banc du jalon 136 — HALO D'ÉTOILE COLORÉ : neutraliser le ciel avant le STF.

DÉFAUT mesuré (run LRGB+Ha de M33, v2.83.0, fichier LINÉAIRE livré) : les
niveaux de ciel des trois canaux sont proportionnels mais très différents
(R −12,9 % / B +27,0 % par rapport au vert, ÉGAL dans les quatre coins) ; le
point noir COMMUN du STF passe alors AU-DESSUS du ciel du canal R, qui est
écrêté à 0 dans tout le fond, et la couronne d'une étoile — neutre dans le
linéaire — se colore au passage de la MTF (très raide).

CORRECTIF LIVRÉ : `display.source_etirement` applique des GAINS par canal
(`couleurs.gains_fond`, primitive d'espace LINÉAIRE du projet) pour ramener
les ciels au même niveau AVANT la courbe, et l'étirement comme ses
statistiques portent sur cette image neutralisée. Ciel neutre ⇒ aucun gain ⇒
rendu identique AU BIT.

Ce banc vérifie :
  [1] CIEL NEUTRE : aucun gain, rendu identique AU BIT à la formule d'avant ;
  [2] CIEL COLORÉ (cast mesuré) : la couronne de l'étoile cesse d'être colorée
      (écart R et B à r = 14, relatif au fond local à r = 30) ;
  [3] La GARDE borne la correction (ciel ×0,2 → gain plafonné à 1 − 0,35) ;
  [4] MONO : aucune neutralisation ;
  [5] PARITÉ ÉCRAN / FICHIER (« tel que vu ») au bit, avec un ciel coloré ;
  [6] MODE MANUEL : inchangé, aucune neutralisation ;
  [7] IDEMPOTENCE (l'image corrigée n'appelle plus de correction) et l'image
      d'entrée n'est JAMAIS modifiée ;
  [8] Les STATS suivent l'image neutralisée : le fond rendu reste à la cible
      (25 %) avec ET sans décalage de ciel.

Exécution : python bancs/_test_halo_couleur_jalon136.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys

import numpy as np

from avastack.processing.display import (DisplayProcessor, mtf,
                                        gains_avant_etirement,
                                        source_etirement, GARDE_NEUTRE_STF)

if hasattr(sys.stdout, "reconfigure"):    # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def image_ciel(cast=(0.87, 1.0, 1.28), graine=1, etoile=True):
    """Ciel bruité + « galaxie » large (fixe le point blanc) + une étoile dont
    la COURONNE EST NEUTRE (même supplément dans les trois canaux), comme dans
    le brut du run M33. `cast` = niveau de ciel par canal (R, V, B)."""
    n = 400
    yy, xx = np.mgrid[0:n, 0:n]
    rng = np.random.default_rng(graine)
    base = 0.030
    galaxie = 0.115 * np.exp(-(((xx - 70.0) ** 2 + (yy - 330.0) ** 2)
                               / (2 * 50.0 ** 2)))
    fond = base + galaxie + rng.standard_normal((n, n)) * 0.0004
    img = np.stack([fond * c for c in cast], axis=-1).astype(np.float32)
    if etoile:
        r = np.sqrt((yy - 200.0) ** 2 + (xx - 200.0) ** 2)
        couronne = 0.90 * np.exp(-(r / 1.8) ** 2) + 0.26 / (1.0 + r) ** 2
        img = img + couronne[..., None].astype(np.float32)
    return img


def ancien_rendu(d, img):
    """Formule d'AVANT le jalon 136 : point noir commun, MTF par canal."""
    med, sigma, p999 = d._calc_stats(img)
    lo = med - d.sigma_k * sigma
    hi = max(p999, med + 10.0 * sigma, lo + 1e-8)
    m = d._solve_m((med - lo) / (hi - lo), d.target)
    return mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)


def anneau(img, y, x, r, demi=34):
    t = np.asarray(img, np.float64)[y - demi:y + demi, x - demi:x + demi]
    yy, xx = np.mgrid[-demi:demi, -demi:demi]
    rr = np.sqrt(yy * yy + xx * xx)
    m = (rr >= r) & (rr < r + 1)
    return t[m].mean(axis=0)


def ecart_teinte(img, y=200, x=200, r=14, rf=30):
    """Écart (R/G, B/G) de l'anneau r à celui du fond local rf, en fraction.
    Un canal ENTIÈREMENT perdu (rendu à 0, cas d'avant le correctif) vaut
    −100 % : c'est bien l'écart maximal, et il évite un 0/0 silencieux."""
    p, f = anneau(img, y, x, r), anneau(img, y, x, rf)
    ecarts = []
    for c in (0, 2):
        if min(p[c], p[1], f[c], f[1]) <= 1e-9:
            ecarts.append(-1.0)             # canal perdu → écart maximal
        else:
            ecarts.append((p[c] / p[1]) / (f[c] / f[1]) - 1.0)
    return ecarts[0], ecarts[1]


neutre = image_ciel(cast=(1.0, 1.0, 1.0))
colore = image_ciel()
copie = colore.copy()

print("[1] Ciel NEUTRE : aucun gain, rendu identique AU BIT à la formule d'avant")
verifie(gains_avant_etirement(neutre) is None,
        "ciel neutre : `gains_avant_etirement` ne propose AUCUNE correction")
d1 = DisplayProcessor()
apres1 = d1.rendu_pleine_resolution(neutre, {})
verifie(d1.gains_etirement is None,
        "ciel neutre : aucun gain appliqué (attribut publié à None)")
avant1 = ancien_rendu(DisplayProcessor(), neutre)
verifie(np.array_equal(np.asarray(apres1, np.float32),
                       np.asarray(avant1, np.float32)),
        "ciel neutre : le rendu est celui d'AVANT, au bit près")

print("[2] Ciel COLORÉ mesuré (R −13 %, B +28 %) : la couronne perd sa couleur")
d2 = DisplayProcessor()
avant2 = ancien_rendu(DisplayProcessor(), colore)
apres2 = d2.rendu_pleine_resolution(colore, {})
g = gains_avant_etirement(colore)
verifie(g is not None and g[0] > 1.10 and g[2] < 0.90,
        "gains proposés : R %.3f  V %.3f  B %.3f" % tuple(g))
ar, ab = ecart_teinte(avant2)
nr, nb = ecart_teinte(apres2)
print("        couronne r=14 vs fond r=30 — AVANT : R %+6.1f %%  B %+6.1f %%"
      % (100 * ar, 100 * ab))
print("                                        APRÈS : R %+6.1f %%  B %+6.1f %%"
      % (100 * nr, 100 * nb))
verifie(max(abs(ar), abs(ab)) > 0.30,
        "le défaut est REPRÉSENTÉ avant le correctif (écart > 30 %)")
verifie(max(abs(nr), abs(nb)) < 0.10,
        "après le correctif, la couronne a la couleur du fond local (< 10 %)")
verifie(abs(nr) < abs(ar) / 3.0 and abs(nb) < abs(ab) / 3.0,
        "le correctif divise l'écart par plus de 3 dans les DEUX canaux")

print("[3] La GARDE borne la correction (ciel ×0,2 dans le rouge)")
g3 = gains_avant_etirement(image_ciel(cast=(0.2, 1.0, 1.0)))
verifie(g3 is not None
        and abs(float(g3[0]) - (1.0 + GARDE_NEUTRE_STF)) < 1e-5,
        "gain rouge plafonné à %.2f (garde %.2f)" % (1.0 + GARDE_NEUTRE_STF,
                                                     GARDE_NEUTRE_STF))
verifie(abs(float(g3[1]) - 1.0) < 1e-5 and abs(float(g3[2]) - 1.0) < 1e-5,
        "les canaux déjà au niveau du vert ne bougent pas")

print("[4] MONO : aucune neutralisation")
mono = image_ciel(cast=(1.0, 1.0, 1.0), etoile=False).mean(axis=2)
verifie(gains_avant_etirement(mono) is None,
        "image monochrome : aucun gain (rien à neutraliser)")
d4 = DisplayProcessor()
verifie(np.array_equal(d4.process(mono, live=False),
                       (ancien_rendu(d4, mono) * 255).astype(np.uint8)),
        "mono : rendu inchangé")

print("[5] PARITÉ ÉCRAN / FICHIER (« tel que vu ») au bit, ciel coloré")
d5 = DisplayProcessor()
ecran = d5.process(colore, live=False)
fichier = (d5.rendu_pleine_resolution(colore, {}) * 255).astype(np.uint8)
verifie(np.array_equal(ecran, fichier),
        "écran == fichier au bit près (mêmes gains, mêmes stats)")
verifie(d5.gains_etirement is not None,
        "l'écran a bien neutralisé (l'attribut porte les gains)")

print("[6] MODE MANUEL : inchangé, aucune neutralisation")
d6 = DisplayProcessor()
d6.auto = False
man = d6.process(colore, live=False)
verifie(d6.gains_etirement is None,
        "mode manuel : aucun gain appliqué (le correctif vit dans le STF auto)")
attendu = (np.clip(colore, 0.0, 1.0) * 255).astype(np.uint8)
verifie(np.array_equal(man, attendu),
        "mode manuel : le rendu est noir/blanc linéaire, comme avant")

print("[7] IDEMPOTENCE et image d'entrée JAMAIS modifiée")
src, g7 = source_etirement(colore)
verifie(g7 is not None, "une image corrigée n'appelle plus de correction")
verifie(gains_avant_etirement(src) is None,
        "ré-appliquer la neutralisation à l'image corrigée ne fait plus rien")
verifie(np.array_equal(colore, copie),
        "l'image d'entrée est intacte (aucune mutation en place)")

print("[8] Les STATS suivent l'image neutralisée : le fond reste à la cible")
n1 = np.median(anneau(apres1, 20, 20, 4, demi=8).mean(axis=-1))
n2 = np.median(anneau(apres2, 20, 20, 4, demi=8).mean(axis=-1))
print("        niveau du fond rendu : ciel neutre %.3f  /  ciel coloré %.3f"
      % (n1, n2))
verifie(abs(n1 - 0.25) < 0.06 and abs(n2 - 0.25) < 0.06,
        "le fond rendu vise la cible (25 %) dans les DEUX cas")

print("\n" + ("BANC 136 : TOUT EST VERT" if ok else "BANC 136 : ÉCHEC"))
sys.exit(0 if ok else 1)

