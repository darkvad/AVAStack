# -*- coding: utf-8 -*-
"""Banc du jalon 137 — NEUTRALISATION APRÈS ÉTIREMENT, AUSSI EN STF.

POURQUOI : la case « Neutraliser la couleur du fond (après étirement) » était
réservée à VeraLux (son ANCRE amplifie le fond). En STF elle était donc
VISIBLE, cochée par défaut et SANS EFFET — exactement le défaut corrigé au
jalon 127 pour la chroma (une case inerte est un mensonge de l'interface).

CE QUI CHANGE : `DisplayProcessor._neutraliser_fond` et
`rendu_pleine_resolution` appliquent l'étage pour LES DEUX MOTEURS AUTOMATIQUES
(STF auto ET VeraLux). Le MODE MANUEL reste en dehors (le point noir y est réglé
à la main, souvent au niveau du fond : il n'y a plus de couleur de fond à
mesurer). Les gains sont ANNONCÉS aussi en STF (« FOND ✓ · fond neutralisé »).

MESURE qui fixe l'attendu (hors dépôt, `_diag_137_probe.py`) : sur une scène au
ciel décalé (R ×0,80 · B ×0,72, au-delà de la garde du correctif 136), l'écart
de couleur du fond rendu tombe de 0,132 (case décochée) à 0,047 (cochée) — la
correction d'AVANT étirement (136) plafonne à 35 %, celle d'APRÈS finit le
travail ; sur une scène au ciel NEUTRE, rien ne bouge (identité AU BIT).

Volets :
  [1] STF : la case AGIT (écart du fond divisé par > 2) ;
  [2] STF : les gains sont PUBLIÉS (`vl_neutre_gains`) ; décochée → None ;
  [3] l'ORDRE : l'image qui entre dans la finition a un fond DÉJÀ neutre ;
  [4] PARITÉ écran / fichier AU BIT, en STF ;
  [5] CIEL NEUTRE : aucune correction, rendu identique au bit ;
  [6] MODE MANUEL : hors périmètre (rendu identique case cochée/décochée) ;
  [7] MONO : rendu identique, aucun gain ;
  [8] UI : les gains sont ANNONCÉS en STF (« FOND ✓ · fond neutralisé … ») et le
      libellé revient au repos quand la correction disparaît.

Exécution : python bancs/_test_neutralisation_stf_jalon137.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys

import numpy as np

from avastack.processing.display import DisplayProcessor

if hasattr(sys.stdout, "reconfigure"):    # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


H, W = 500, 700
BASE = 0.0326
SIGM = (0.00040, 0.00033, 0.00040)
AMPL = (1.00, 0.62, 0.44)


def scene(cast=(1.0, 1.0, 1.0), graine=137, parfait=False):
    """Ciel bruité + galaxie au centre, aux ciels réels du banc 124 — `cast`
    multiplie le niveau de ciel de chaque canal.

    `parfait=True` : ciel ET objet rigoureusement neutres (même bruit, même
    noyau dans les trois canaux) — le seul cas où la neutralisation doit être
    une identité AU BIT. Avec un bruit indépendant par canal, l'écart résiduel
    des médianes — amplifié par la MTF — reste de l'ordre du pour mille, et sur
    une image à objet COLORÉ la « moitié sombre » peut en contenir : c'est
    pourquoi l'étage borne sa correction à ±10 % (`gains_fond`)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2)
    noyau = 0.9 * np.exp(-(rr / 22.0) ** 2) + 0.22 * np.exp(-(rr / 90.0) ** 2)
    rng = np.random.default_rng(graine)
    if parfait:
        bruit = rng.normal(0, SIGM[0], (H, W))
        img = np.stack([BASE * cast[c] + noyau + bruit for c in range(3)], -1)
    else:
        img = np.stack([BASE * cast[c] + AMPL[c] * noyau
                        + rng.normal(0, SIGM[c], (H, W)) for c in range(3)], -1)
    return np.clip(img, 0, 1).astype(np.float32)


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


def proc(neutre_fond, auto=True):
    p = DisplayProcessor()
    p.auto = bool(auto)
    p.vl_neutre_fond = bool(neutre_fond)
    return p


fort = scene(cast=(0.80, 1.0, 0.72 * 1.02))
neutre = scene(parfait=True)

print("[1] STF : la case AGIT (elle était inerte avant ce jalon)")
off = proc(False).rendu_pleine_resolution(fort, {})
on = proc(True).rendu_pleine_resolution(fort, {})
e_off, e_on = ecart(off), ecart(on)
print("        écart de couleur du fond rendu — case DÉCOCHÉE %.4f · "
      "cochée %.4f" % (e_off, e_on))
verifie(e_off > 0.05,
        "scène de test : le fond rendu est franchement coloré sans la case "
        "(%.4f)" % e_off)
verifie(e_on < e_off / 2.0,
        "case cochée : l'écart est divisé par plus de 2 (%.4f → %.4f)"
        % (e_off, e_on))
verifie(not np.array_equal(on, off),
        "le rendu change RÉELLEMENT (la case n'est plus inerte en STF)")

print("[2] STF : les gains sont PUBLIÉS (annonce dans « État des calculs »)")
d_on, d_off = proc(True), proc(False)
d_on.process(fort, live=False)
d_off.process(fort, live=False)
g = d_on.vl_neutre_gains
verifie(g is not None and not np.allclose(g, 1.0, atol=1e-3),
        "aperçu STF, case cochée : gains publiés (%s)"
        % (None if g is None else np.round(g, 4).tolist()))
verifie(d_off.vl_neutre_gains is None,
        "case décochée : aucun gain publié")
verifie(all(0.90 - 1e-6 <= float(v) <= 1.10 + 1e-6 for v in g),
        "les gains restent BORNÉS à ±10 % (la garde de `gains_fond`)")

print("[3] l'ORDRE : la finition reçoit un fond DÉJÀ neutre (STF)")
_orig = DisplayProcessor._finition
_cap = {}


def _capture(x, rgb, gamma, saturation, sat_canaux=None):
    _cap["ecart"] = ecart(np.asarray(x, np.float32))
    return _orig(x, rgb, gamma, saturation, sat_canaux)


DisplayProcessor._finition = staticmethod(_capture)
try:
    proc(True).process(fort, live=False)
    e_fin_on = _cap["ecart"]
    proc(False).process(fort, live=False)
    e_fin_off = _cap["ecart"]
finally:
    DisplayProcessor._finition = staticmethod(_orig)
print("        fond ENTRANT dans la finition — cochée %.4f · décochée %.4f"
      % (e_fin_on, e_fin_off))
verifie(e_fin_on < e_fin_off / 2.0,
        "la neutralisation PRÉCÈDE la finition (elle a déjà corrigé le fond)")

print("[4] PARITÉ écran / fichier AU BIT, en STF")
d4 = proc(True)
ecran = d4.process(fort, live=False)
fichier = (d4.rendu_pleine_resolution(fort, {}) * 255).astype(np.uint8)
pire = int(np.max(np.abs(ecran.astype(np.int16) - fichier.astype(np.int16))))
verifie(np.array_equal(ecran, fichier),
        "écran == fichier au bit près (écart %d niveau de 8 bits)" % pire)

print("[5] CIEL NEUTRE : aucune correction, rendu identique AU BIT")
n_on = proc(True).rendu_pleine_resolution(neutre, {})
n_off = proc(False).rendu_pleine_resolution(neutre, {})
verifie(np.array_equal(n_on, n_off),
        "ciel neutre : case cochée ou décochée, le rendu est IDENTIQUE")
d5 = proc(True)
d5.process(neutre, live=False)
verifie(d5.vl_neutre_gains is None,
        "ciel neutre : aucun gain publié (rien à corriger)")

print("[6] MODE MANUEL : hors périmètre (le point noir y est réglé à la main)")
m_on = proc(True, auto=False).rendu_pleine_resolution(fort, {})
m_off = proc(False, auto=False).rendu_pleine_resolution(fort, {})
verifie(np.array_equal(m_on, m_off),
        "manuel : la case ne change RIEN (comportement d'avant, assumé)")
d6 = proc(True, auto=False)
d6.process(fort, live=False)
verifie(d6.vl_neutre_gains is None,
        "manuel : aucun gain publié (pas de fond à mesurer)")

print("[7] MONO : rendu identique, aucun gain")
mono = fort[..., 1].copy()
verifie(np.array_equal(proc(True).rendu_pleine_resolution(mono, {}),
                       proc(False).rendu_pleine_resolution(mono, {})),
        "mono : rendu identique case cochée/décochée")
d7 = proc(True)
d7.process(mono, live=False)
verifie(d7.vl_neutre_gains is None, "mono : aucun gain publié")

print("[8] UI : les gains sont ANNONCÉS en STF (et pas reconfigurés à chaque tick)")
import tkinter as tk                                              # noqa: E402
import avastack.ui.app as ui                                      # noqa: E402

ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
try:
    app = ui.App(root)
    app.disp.vl_new = False          # pas de rendu déclenché par ce volet
    app.disp.vl_neutre_gains = (1.0123, 1.0, 0.9544)
    app._maj_lbl_vl()
    texte = app.lbl_vl.cget("text")
    verifie("FOND ✓" in texte and "1.0123" in texte and "0.9544" in texte,
            "l'état des calculs annonce la correction STF (%r)" % texte)
    avant = app.lbl_vl.cget("text")
    app._maj_lbl_vl()
    verifie(app.lbl_vl.cget("text") == avant,
            "le libellé ne change pas au tick suivant (mémo respecté)")
    app.disp.vl_neutre_gains = None
    app._maj_lbl_vl()
    verifie("FOND ✓" not in app.lbl_vl.cget("text"),
            "aucune correction : l'annonce disparaît")
finally:
    root.destroy()

print("\n" + ("BANC 137 : TOUT EST VERT" if ok else "BANC 137 : ÉCHEC"))
sys.exit(0 if ok else 1)

