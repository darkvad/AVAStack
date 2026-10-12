# -*- coding: utf-8 -*-
"""Banc du jalon 124 — NEUTRALISATION DÉPLACÉE + EXCLUSIVITÉ DES CORRECTIONS COULEUR.

Décisions d'Alain (12/10/2026), après la validation de M33 en v2.75.0 :
  ① « l'UI montre encore la neutralisation dans les traitements AVANT
     l'étirement » → la case QUITTE « Fond et grain (AVANT étirement) » et
     rejoint « Couleur de l'objet (APRÈS étirement) » ;
  ② « la neutralisation juste avant saturation et gamma, qui sont vraiment
     finales » → elle n'est plus appliquée par le solveur (juste après le
     moteur) mais par `process()` / `rendu_pleine_resolution`, APRÈS l'étage de
     niveaux et JUSTE AVANT la finition ;
  ③ « si équilibrage, gaia et spcc sont exclusifs, alors les rendre exclusifs »
     → cocher l'un DÉCOCHE les deux autres (mesuré : l'équilibrage, appliqué
     après les gains, recalcule leurs rapports et ANNULE SPCC/Gaia).

Vérifie :
  [1] UI : la case « Neutraliser la couleur du fond » est dans `frm_couleur`
      (« Couleur de l'objet (APRÈS étirement) »), PLUS dans `frm_fond` ;
  [2] exclusivité Équilibrage / SPCC / gains Gaia : cocher l'un décoche les
      deux autres, dans les trois sens ;
  [3] l'ORDRE : l'image ENTRANT dans la finition (`_finition`) a un fond déjà
      NEUTRE quand la case est cochée — preuve qu'elle la précède (fichier ET
      aperçu) ;
  [4] non-régression : mono inchangé, sortie bornée [0, 1], écran == fichier.

Exécution (interpréteur du venv) :
    python bancs/_test_jalon124_deplacement_et_exclusivite.py
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

from avastack.processing import veralux as V                        # noqa: E402
from avastack.processing.display import DisplayProcessor            # noqa: E402

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Scène aux ciels réels (bleui de ~3 %), galaxie jaune au centre — le MÊME genre
# de scène que les bancs des jalons 62 et 123.
CIEL = (0.0321, 0.0326, 0.0332)
SIGM = (0.00040, 0.00033, 0.00040)
AMPL = (1.00, 0.62, 0.44)
H, W = 700, 1000
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2)
noyau = 0.9 * np.exp(-(rr / 30.0) ** 2) + 0.25 * np.exp(-(rr / 110.0) ** 2)
rng = np.random.default_rng(124)
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


def _processor(neutre_fond):
    """DisplayProcessor VeraLux déterministe (logD déjà résolu) — case on/off."""
    p = DisplayProcessor()
    p.stretch = "veralux"
    p.vl_profil = V.PROFIL_PAR_DEFAUT
    p.vl_mode_res = V.MODE_TARGET_BG
    p.vl_target_bg = 0.16
    p.vl_neutre_fond = bool(neutre_fond)
    _, logd, _ = V.etirer(V.normaliser_lin(scene), mode=V.MODE_TARGET_BG,
                          target_bg=0.16)
    p.vl_log_d_resolu = logd
    return p


def attendre_vl(d, timeout=60.0):
    """Attend la fin du job du solveur VeraLux (polling, 20 ms)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not d._vl_pending and d._vl_result is not None:
            return True
        time.sleep(0.02)
    return False


# ==========================================[1] la case a été déplacée
print("=" * 78)
print("[1] UI : la case vit dans « Couleur de l'objet (APRÈS étirement) »")
print("=" * 78)
import tkinter as tk                                              # noqa: E402
from tkinter import ttk                                           # noqa: E402
import avastack.ui.app as ui                                      # noqa: E402

root = tk.Tk()
root.withdraw()
ui.CONFIG = {}
ui.sauver_config = lambda d: None
app = ui.App(root)


def _cases(cadre):
    """Libellés des cases à cocher d'un cadre (ses enfants directs)."""
    return [w.cget("text") for w in cadre.winfo_children()
            if isinstance(w, ttk.Checkbutton)]


_c_fond, _c_coul = _cases(app.frm_fond), _cases(app.frm_couleur)
verifie(any("Neutraliser la couleur du fond" in t for t in _c_coul),
        f"« Couleur de l'objet (APRÈS étirement) » PORTE la neutralisation "
        f"({_c_coul})")
verifie(not any("Neutraliser la couleur du fond" in t for t in _c_fond),
        f"« Fond et grain (AVANT étirement) » ne la porte PLUS ({_c_fond})")
verifie(any("après étirement" in t for t in _c_coul),
        "son libellé dit « après étirement » (plus « juste avant l'étirement »)")
verifie(hasattr(app, "var_vl_neutre") and bool(app.var_vl_neutre.get()) is True,
        "la case reste présente et COCHÉE par défaut (défaut de rendu)")

# ==========================================[2] exclusivité des corrections
print()
print("=" * 78)
print("[2] Équilibrage / SPCC / gains Gaia : EXCLUSIFS (cocher l'un décoche les autres)")
print("=" * 78)
app.var_wb.set(True)
app._on_wb()
verifie(bool(app.var_wb.get()) is True, "départ : équilibrage coché")
app.var_spcc.set(True)
app._on_spcc()
verifie(bool(app.var_spcc.get()) is True and bool(app.var_wb.get()) is False
        and bool(app.var_photo_gains.get()) is False,
        "cocher SPCC DÉCOCHE l'équilibrage (et les gains Gaia)")
app.var_photo_gains.set(True)
app._on_photo_gains()
verifie(bool(app.var_photo_gains.get()) is True
        and bool(app.var_wb.get()) is False and bool(app.var_spcc.get()) is False,
        "cocher les gains Gaia DÉCOCHE l'équilibrage et la SPCC")
app.var_wb.set(True)
app._on_wb()
verifie(bool(app.var_wb.get()) is True and bool(app.var_spcc.get()) is False
        and bool(app.var_photo_gains.get()) is False,
        "re-cocher l'équilibrage DÉCOCHE la SPCC et les gains Gaia")
# Décocher à la main ne recoche PERSONNE (l'exclusivité n'agit qu'à la coche).
app.var_wb.set(False)
app._on_wb()
verifie(bool(app.var_wb.get()) is False and bool(app.var_spcc.get()) is False,
        "décocher l'équilibrage ne recoche rien (pas d'effet de bord)")
root.destroy()

# ==========================================[3] l'ordre : juste avant la finition
print()
print("=" * 78)
print("[3] l'ORDRE : la finition reçoit un fond DÉJÀ NEUTRE (neutralisation juste avant)")
print("=" * 78)
# On ENVELOPPE `_finition` pour mesurer le fond de l'image qu'elle reçoit : si la
# neutralisation la précède, ce fond est neutre ; si elle était appliquée plus
# tôt (dans le solveur, comme au jalon 123) puis suivie de niveaux/finition, il
# pourrait être coloré. C'est la preuve DIRECTE de la position choisie.
_orig_finition = DisplayProcessor._finition
_capture = {}


def _finition_capture(x, rgb, gamma, saturation, sat_canaux=None):
    _capture["ecart"] = ecart(np.asarray(x, np.float32))
    return _orig_finition(x, rgb, gamma, saturation, sat_canaux)


DisplayProcessor._finition = staticmethod(_finition_capture)
try:
    d_on, d_off = _processor(True), _processor(False)
    _ = d_on.rendu_pleine_resolution(scene)      # FICHIER « tel que vu »
    e_fichier_on = _capture["ecart"]
    _ = d_off.rendu_pleine_resolution(scene)
    e_fichier_off = _capture["ecart"]
    # APERÇU : il faut d'abord laisser le solveur VeraLux produire son résultat
    # (sinon `process()` rend l'image d'attente STF), puis rendre.
    for dd in (d_on, d_off):
        dd.notify_new_stack()
        dd._process_veralux(scene, live=False)
        attendre_vl(dd)
    _ = d_on.process(scene, live=False)          # APERÇU (même étage)
    e_ecran_on = _capture["ecart"]
    print(f"    fond ENTRANT dans la finition — fichier : "
          f"cochée {e_fichier_on:.4f} · décochée {e_fichier_off:.4f} "
          f"· aperçu {e_ecran_on:.4f}")
    verifie(e_fichier_on < 0.005,
            f"le fichier passe à la finition un fond NEUTRE ({e_fichier_on:.4f}) "
            "— la neutralisation la PRÉCÈDE")
    verifie(e_fichier_off > 0.01,
            f"case décochée : le fond qui entre dans la finition reste COLORÉ "
            f"({e_fichier_off:.4f})")
    verifie(e_ecran_on < 0.005,
            f"l'aperçu (`process()`) applique le MÊME étage avant la finition "
            f"({e_ecran_on:.4f})")
finally:
    DisplayProcessor._finition = staticmethod(_orig_finition)

# ==========================================[4] non-régression
print()
print("=" * 78)
print("[4] Non-régression : écran == fichier, bornes, mono")
print("=" * 78)
d = _processor(True)
d.notify_new_stack()
d._process_veralux(scene, live=False)
attendre_vl(d)
d.process(scene, live=False)                  # publie vl_neutre_gains
gains = d.vl_neutre_gains
verifie(gains is not None and not np.allclose(gains, 1.0, atol=1e-3),
        "l'aperçu publie les gains de neutralisation mesurés sur la SORTIE "
        f"({None if gains is None else np.round(gains, 4).tolist()})")
ecran = np.asarray(d.process(scene, live=False), np.uint8)
fichier = np.asarray(
    (d.rendu_pleine_resolution(scene) * 255.0).astype(np.uint8), np.uint8)
pire = int(np.max(np.abs(ecran.astype(np.int16) - fichier.astype(np.int16))))
verifie(ecran.shape == fichier.shape and pire == 0,
        f"l'écran == le fichier (écart {pire} niveau de 8 bits)")
r = d.rendu_pleine_resolution(scene)
verifie(0.0 <= float(r.min()) and float(r.max()) <= 1.0,
        "le rendu neutralisé reste borné [0, 1]")
mono = scene[..., 1].copy()
verifie(np.array_equal(d.rendu_pleine_resolution(mono),
                       _processor(False).rendu_pleine_resolution(mono)),
        "image MONO : rendu IDENTIQUE avec/sans la neutralisation")

print()
print("RÉSULTAT :", "OK" if ok else "ÉCHECS À CORRIGER")
raise SystemExit(0 if ok else 1)
