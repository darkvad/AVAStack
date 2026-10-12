# -*- coding: utf-8 -*-
"""Banc du jalon 123 (v2.75.0) — NEUTRALISATION DU FOND APRÈS L'ÉTIREMENT.

« Les gains sont MESURÉS SUR LA SORTIE étirée (ce que l'œil voit) et appliqués
APRÈS le moteur. » Cause (mesurée, M33, 11/10/2026) : appliquée AVANT l'étirement
(v2.36.1), la neutralisation employait un estimateur (« moitié la plus sombre »)
qui n'est PAS la grandeur que l'ANCRE de VeraLux amplifie — l'ancre SOUTRAIT un
scalaire puis étire en log. Le résultat « visait 0,7 % à côté » et FABRIQUAIT le
magenta. Remède mesuré : neutraliser APRÈS, sur la sortie.

Vérifie :
  [1] `couleurs.neutraliser_apres_etirement` : mono → no-op, sortie BORNÉE [0, 1],
      fond de SORTIE neutralisé, force atténue, entrée JAMAIS modifiée, neutre au
      bit près ;
  [2] l'intégration : un ciel bleui étiré par VeraLux (PIÉDESTAL ACTIF) sort avec
      un fond encore COLORÉ ; l'étage APRÈS le ramène NEUTRE (effet mesurable) —
      preuve que la neutralisation APRÈS a bien un travail à faire ;
  [3] `DisplayProcessor` : `rendu_pleine_resolution` (VeraLux) INTÈGRE la
      neutralisation → `vl_neutre_fond=True` rend un fond NEUTRE, `False` un fond
      COLORÉ ; c'est le MÊME étage que le solveur live (`_vl_worker`), et l'écran
      == le fichier ;
  [4] non-régression : mono rendu INCHANGÉ avec/sans la case, déterminisme,
      sortie bornée [0, 1].

Exécution (interpréteur du venv) :
    python bancs/_test_neutralisation_apres_etirement_jalon123.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from avastack.processing import couleurs as C                       # noqa: E402
from avastack.processing import veralux as V                        # noqa: E402
from avastack.processing.display import DisplayProcessor            # noqa: E402

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Scène aux ciels réels de M31 (bleui de ~3 %), bruit de son empilement, galaxie
# jaune au centre — le MÊME genre de scène que le banc du jalon 62.
CIEL = (0.0321, 0.0326, 0.0332)
SIGM = (0.00040, 0.00033, 0.00040)
AMPL = (1.00, 0.62, 0.44)
H, W = 700, 1000
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2)
noyau = 0.9 * np.exp(-(rr / 30.0) ** 2) + 0.25 * np.exp(-(rr / 110.0) ** 2)
rng = np.random.default_rng(123)
scene = np.stack([CIEL[c] + AMPL[c] * noyau + rng.normal(0, SIGM[c], (H, W))
                  for c in range(3)], -1)
scene = np.clip(scene, 0, 1).astype(np.float32)


def fond(a):
    """Niveau du fond par canal : médiane de la moitié la plus sombre (le MÊME
    estimateur que la neutralisation — c'est ce qui rend la mesure honnête)."""
    a = np.asarray(a, np.float32)
    lum = a.mean(-1)
    m = lum <= np.percentile(lum, 50)
    return [float(np.median(a[..., c][m])) for c in range(3)]


def ecart(a):
    """Écart de couleur du FOND : max(|R/G − 1|, |B/G − 1|) — 0 = neutre."""
    f = fond(a)
    return max(abs(f[0] / f[1] - 1.0), abs(f[2] / f[1] - 1.0))


def attendre_vl(d, timeout=60.0):
    """Attend la fin du job du solveur VeraLux (polling, 20 ms)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not d._vl_pending and d._vl_result is not None:
            return True
        time.sleep(0.02)
    return False


print("=" * 78)
print("[1] couleurs.neutraliser_apres_etirement : la primitive")
print("=" * 78)
# Une image d'AFFICHAGE (étirée) : fond coloré (écart ~8 %, DANS la garde ±10 %)
# + objet plus clair. Un écart plus fort serait BORNÉ par la garde (voulu).
base = np.empty((256, 256, 3), np.float32)
base[..., 0], base[..., 1], base[..., 2] = 0.19, 0.20, 0.216
base[60:200, 60:200] = (0.70, 0.75, 0.80)
touche = base.copy()
out = C.neutraliser_apres_etirement(base)
verifie(out.shape == base.shape and out.dtype == np.float32,
        "mêmes dimensions, float32")
verifie(np.array_equal(base, touche), "l'image d'origine n'est JAMAIS modifiée")
verifie(ecart(base) > 0.05, f"fond de départ COLORÉ (écart {ecart(base):.3f})")
verifie(ecart(out) < 5e-3,
        f"fond NEUTRE après correction (écart {ecart(out):.3f})")
verifie(0.0 <= float(out.min()) and float(out.max()) <= 1.0,
        "image étirée : le produit est BORNÉ [0, 1]")
verifie(float(np.abs(out - base).max()) > 1e-4, "la correction a bien eu lieu")
demi = C.neutraliser_apres_etirement(base, force=0.5)
verifie(ecart(out) < ecart(demi) < ecart(base),
        f"force 0,5 : correction ATTÉNUÉE (écart {ecart(demi):.3f}, entre "
        f"{ecart(out):.3f} et {ecart(base):.3f})")
mono = base[..., 1].copy()
verifie(np.array_equal(C.neutraliser_apres_etirement(mono), mono),
        "image MONO (H, W) : renvoyée inchangée")
neutre = np.full((32, 32, 3), 0.2, np.float32)
verifie(np.array_equal(C.neutraliser_apres_etirement(neutre), neutre),
        "fond déjà NEUTRE : renvoyé inchangé (au bit près)")


print()
print("=" * 78)
print("[2] L'ÉTAGE APRÈS a un effet MESURABLE (piédestal ACTIF compris)")
print("=" * 78)
verifie(V.moteur_disponible(), "moteur VeraLux disponible")
etire, _, _ = V.etirer(scene, mode=V.MODE_TARGET_BG, target_bg=0.20)
apres = C.neutraliser_apres_etirement(etire)
fe, fa = fond(etire), fond(apres)
print(f"    fond étiré AVANT : R/G {fe[0]/fe[1]:.3f} · B/G {fe[2]/fe[1]:.3f} "
      f"(écart {ecart(etire):.3f})")
print(f"    fond étiré APRÈS : R/G {fa[0]/fa[1]:.3f} · B/G {fa[2]/fa[1]:.3f} "
      f"(écart {ecart(apres):.3f})")
verifie(ecart(etire) > 0.01,
        "le fond ÉTIRÉ est encore COLORÉ (le piédestal seul ne suffit pas) — "
        "c'est le défaut mesuré")
verifie(ecart(apres) < ecart(etire),
        "l'étage APRÈS réduit l'écart de couleur du fond de la SORTIE")
verifie(ecart(apres) < 0.02,
        f"fond étiré NEUTRE après l'étage (écart {ecart(apres):.3f})")
g = C.gains_fond(etire)
verifie(g is None or all(0.90 - 1e-6 <= float(v) <= 1.10 + 1e-6 for v in g),
        f"gains MESURÉS SUR LA SORTIE, bornés à ±10 % "
        f"({None if g is None else np.round(g, 4).tolist()})")


print()
print("=" * 78)
print("[3] DisplayProcessor : la neutralisation fait partie du RENDU (VeraLux)")
print("=" * 78)
_, logd, _ = V.etirer(V.normaliser_lin(scene), mode=V.MODE_TARGET_BG,
                      target_bg=0.16)


def _processor(neutre_fond):
    """DisplayProcessor VeraLux déterministe (logD fixé) — case on/off."""
    p = DisplayProcessor()
    p.stretch = "veralux"
    p.vl_profil = V.PROFIL_PAR_DEFAUT
    p.vl_mode_res = V.MODE_TARGET_BG
    p.vl_target_bg = 0.16
    p.vl_log_d_resolu = logd           # logD déjà résolu → pas de re-résolution
    p.vl_neutre_fond = bool(neutre_fond)
    return p


d_on = _processor(True)
d_off = _processor(False)
r_on = d_on.rendu_pleine_resolution(scene)
r_off = d_off.rendu_pleine_resolution(scene)
print(f"    fond rendu case COCHÉE : écart {ecart(r_on):.3f} · "
      f"case DÉCOCHÉE : écart {ecart(r_off):.3f}")
verifie(ecart(r_off) > 0.01,
        "case DÉCOCHÉE : fond rendu COLORÉ (l'ancien rendu)")
verifie(ecart(r_on) < ecart(r_off) and ecart(r_on) < 0.02,
        "case COCHÉE : fond rendu NEUTRE — la neutralisation est DANS le rendu")
verifie(0.0 <= float(r_on.min()) and float(r_on.max()) <= 1.0,
        "le rendu neutralisé reste borné [0, 1]")

# JALON 124 : la neutralisation a QUITTÉ le solveur — c'est `process()` qui
# l'applique (après l'étage de niveaux, juste avant gamma/saturation) et publie
# les gains MESURÉS SUR LA SORTIE.
d_live = _processor(True)
d_live.vl_log_d_resolu = None         # force la résolution TARGET_BG du solveur
d_live.notify_new_stack()
d_live._process_veralux(scene, live=False)
fait = attendre_vl(d_live)
d_live.process(scene, live=False)     # étage de niveaux + NEUTRALISATION
verifie(fait and d_live.vl_neutre_gains is not None
        and not np.allclose(d_live.vl_neutre_gains, 1.0, atol=1e-3),
        "l'aperçu LIVE publie une correction (gains "
        f"{None if d_live.vl_neutre_gains is None else np.round(d_live.vl_neutre_gains, 4).tolist()}) "
        "— mesurés sur la SORTIE")
d_off.notify_new_stack()
d_off._process_veralux(scene, live=False)
attendre_vl(d_off)
d_off.process(scene, live=False)
verifie(d_off.vl_neutre_gains is None,
        "case décochée : l'aperçu ne publie AUCUN gain")
# L'écran (solveur live) == le fichier (« tel que vu ») — la règle du projet.
ecran = np.asarray(d_live.process(scene, live=False), np.uint8)
fichier = np.asarray(
    (d_live.rendu_pleine_resolution(scene) * 255.0).astype(np.uint8), np.uint8)
pire = int(np.max(np.abs(ecran.astype(np.int16) - fichier.astype(np.int16))))
verifie(ecran.shape == fichier.shape and pire == 0,
        f"l'écran == le fichier (écart {pire} niveau de 8 bits)")


print()
print("=" * 78)
print("[4] Non-régression : mono inchangé, déterminisme, bornes")
print("=" * 78)
mono_src = scene[..., 1].copy()
verifie(np.array_equal(d_on.rendu_pleine_resolution(mono_src),
                       d_off.rendu_pleine_resolution(mono_src)),
        "image MONO : rendu IDENTIQUE avec/sans la neutralisation")
verifie(np.array_equal(d_on.rendu_pleine_resolution(scene),
                       d_on.rendu_pleine_resolution(scene)),
        "deux rendus = résultat identique (déterministe)")


print()
print("===", "TOUS LES TESTS PASSENT" if ok else "!!! ECHECS !!!", "===")
sys.exit(0 if ok else 1)
