# -*- coding: utf-8 -*-
"""DIAGNOSTIC (21/10/2026, branche `OptimisationUI`) — BASCULE VeraLux → STF :
OÙ NAÎT L'IMAGE BLANCHE ?

DÉFAUT SIGNALÉ PAR ALAIN (test complet du 21/10, SEUL point qui bloque la fusion
vers `master`) : après avoir joué en fin d'empilement avec « un peu tous les
paramètres » EN ÉTIREMENT VERALUX, basculer sur l'étirement STF donne une IMAGE
BLANCHE.

CE SCRIPT NE CORRIGE RIEN : il MESURE. Il rejoue la séquence RÉELLE de
l'interface (vraie `App`, vraie `DisplayProcessor`, vraie chaîne, messages de la
file du worker) : VeraLux rendu → bascule du moteur SANS nouvelle frame
(`App._on_moteur`, le VRAI gestionnaire) → on observe CHAQUE image réellement
dessinée et l'état interne qui la produit (`_stats`, `last_lo/hi`, barres de
niveaux, `dernier_etait_attente`, clé de la chaîne…).

SORTIE : pour chaque scénario, la médiane/le maximum de chaque image dessinée
après la bascule (une image blanche = médiane ≈ 255), les réglages en cause, et
la référence « STF sain » (vraie `DisplayProcessor` neuve, mêmes réglages).

Exécution (interpréteur du venv) :
    python bancs/_diag_bascule_stf_blanc.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui
from avastack.external import live as gx_live
from avastack.processing import display as display_mod
from avastack.processing.display import DisplayProcessor
from avastack.processing import veralux as V

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================ images de travail
H, W = 96, 128
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt((xx - W / 2.0) ** 2 + (yy - H / 2.0) ** 2)
noyau = 0.8 * np.exp(-(rr / 10.0) ** 2) + 0.25 * np.exp(-(rr / 34.0) ** 2)


def pile(frames):
    """Empilement synthétique mono : le FOND change de NIVEAU entre le début de
    la session (calibration appliquée : fond retiré) et la suite (maître dark
    retiré, autre nuit/filtre d'un dossier mixte, Lune qui se couche…) — c'est
    ce changement de niveau qui rend une mémoire d'étirement PÉRIMÉE dangereuse
    (`mean()` = `sum/wsum` est à niveau CONSTANT à calibration donnée)."""
    rng = np.random.default_rng(1000 + frames)
    fond = 0.008 if frames <= 6 else 0.048
    sc = np.stack([fond * (1.0 + 1.15 * noyau), fond * (1.0 + 0.75 * noyau),
                   fond * (1.0 + 0.60 * noyau)], -1).astype(np.float32)
    sc += rng.normal(0.0, 0.0006 / np.sqrt(max(1.0, float(frames))),
                     sc.shape).astype(np.float32)
    return np.clip(sc, 0.0, 1.0).astype(np.float32)


# ================================================================ outillage Tk
ui.CONFIG = {}
ui.sauver_config = lambda d: None

root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.rendu.immediat = True          # mesure : rendu sur place (comme avant 1b)
app.var_view.set("pile")


class _CameraMuette:
    """Source sans fichier : `_cadence_dossier()` est FAUX (comportement caméra)."""
    pending = 0
    last_file = ""


app.camera = _CameraMuette()


def pomper(secondes):
    t0 = time.time()
    while time.time() - t0 < secondes:
        root.update()
        time.sleep(0.005)


def message(frames, image):
    st = dict(frames=frames, rejets=0, bad=0, floues=0, fps=1.0, cam="banc",
              file="", pending=0, failed=0, align="—", seeing=None,
              seeing_msg="", archive=0, archive_err="", compo=None,
              restack="", restack_n=0, astro="", photo="", spcc="")
    return (image, st)


def stats8(img8):
    """(médiane, maximum, part de pixels ≥ 250) d'une image affichée."""
    a = np.asarray(img8)
    return (float(np.median(a)), float(a.max()),
            float(np.mean(a >= 250)))


def decris(nom, img8):
    med, mx, sat = stats8(img8)
    print(f"    {nom:28s} médiane {med:6.1f} · max {mx:5.0f} · "
          f"pixels ≥250 : {100.0 * sat:5.1f} %"
          + ("   <<< BLANC" if med >= 200.0 else ""))


# ================================================== instrumentation du dessin
_dessinees = []
_show_reel = app._show_image


def _show_mouchard(img8):
    _dessinees.append(np.array(img8, copy=True))
    _show_reel(img8)


app._show_image = _show_mouchard


def etat(d, prefixe="      · "):
    """État interne qui décide de l'étirement STF."""
    st = d._stats
    print(prefixe + f"stretch={d.stretch!r} auto={d.auto} fige={d.fige} "
          f"chaine={d.chaine_sollicitee()} attente={d.dernier_etait_attente}")
    print(prefixe + "stats="
          + (f"{tuple(round(v, 6) for v in st)}" if st is not None else "None")
          + f" lo={d.last_lo:.6f} hi={d.last_hi:.6f} m={d.last_m:.4f}")
    print(prefixe + f"barres {d.bar_noir:.3f}/{d.bar_median:.3f}/"
          f"{d.bar_blanc:.3f} niveaux_actifs="
          f"{display_mod.niveaux_actifs(d.bar_noir, d.bar_median, d.bar_blanc)}")
    print(prefixe + f"vl_error={d.vl_error!r} memo_moteur="
          f"{'posé' if d._memo_moteur is not None else 'vide'} "
          f"neutre_gains={d.vl_neutre_gains}")


# ============================================================ le scénario type
def scenario(nom, *,
             chroma=False, barres=None, fige=False, chaine_lourde=False,
             geste=False, frames=(1, 6, 20, 60)):
    """Joue « une session en VeraLux, puis bascule STF sans nouvelle frame ».

    `barres` : (noir, median, blanc) posés AVANT la bascule (ce que fait la
    souris d'Alain quand il « joue avec tous les paramètres »).
    `chaine_lourde` : GraXpert (factice) + débruitage + netteté cochés.
    """
    print()
    print("=" * 78)
    print(f"SCÉNARIO : {nom}")
    print("=" * 78)
    d = app.disp
    app.var_moteur.set("VeraLux")
    app._on_moteur()
    d.reset()                        # session neuve, moteur VeraLux choisi
    d._stats = None
    d.bar_noir, d.bar_median, d.bar_blanc = 0.0, 0.5, 1.0
    d.fige = False
    # Les CASES vivent dans l'interface : on les pose par leurs VARIABLES Tk et
    # par les VRAIS gestionnaires de synchronisation — c'est `_tick` qui
    # réécrit `disp.vl_*` à partir d'elles à chaque tour (poser l'attribut
    # directement ne tient pas).
    app.var_vl_chroma.set(bool(chroma))
    app.var_vl_dn.set(bool(chaine_lourde))
    app.var_vl_graxpert.set(bool(chaine_lourde))
    app.var_vl_sharp.set(bool(chaine_lourde))
    app.var_cmd_graxpert.set("faux {input} {output}")
    app._sync_vl_chroma_vue()
    app._sync_vl_denoise_vue()
    app._sync_vl_graxpert_vue()
    app._sync_vl_sharp_vue()
    app.var_vl_neutre.set(True)
    app._sync_vl_neutre_vue()
    app.var_vl_scnr.set(False)
    app.var_vl_demagenta.set(False)
    app.var_vl_scnr_doux.set(False)
    app.var_vl_boost.set(False)
    app._sync_vl_couleur_vue()
    app._last_disp = None
    app._rendu_attente = None
    app._vl_frames = None
    app._rendu_differ = None
    _dessinees.clear()

    print("  [phase VeraLux] empilement qui grossit, moteur VeraLux")
    dernier = None
    for f in frames:
        dernier = pile(f)
        app.q.put_nowait(message(f, dernier))
        pomper(0.35)                 # frame → chaîne sollicitée
        if geste and f == frames[0]:
            # « Alain joue avec les paramètres » : un curseur VeraLux bougé
            # PENDANT que la chaîne calcule (c'est ce qui déclenche l'image
            # d'attente et la consommation du drapeau de soumission).
            print("      geste : curseur « fond cible » VeraLux pendant le calcul")
            app.var_vl_target.set(0.15)
            app._on_vl_target()
            print(f"      · en cours={d.vl_en_cours()} "
                  f"attente={d.dernier_etait_attente} "
                  f"stats={'None' if d._stats is None else 'posées'}")
        fini = time.time() + 20.0
        while time.time() < fini and (d.vl_en_cours() or d.vl_new):
            pomper(0.05)
        pomper(0.15)                 # le `vl_new` déclenche le rendu final
    if _dessinees:
        decris("image VeraLux affichée", _dessinees[-1])
    print("  état APRÈS la phase VeraLux :")
    etat(d)

    # Ce que fait Alain : régler les barres de niveaux « pour de bon » sur
    # l'image VeraLux (c'est un réglage PARTAGÉ par les deux moteurs).
    if barres is not None:
        d.bar_noir, d.bar_median, d.bar_blanc = barres
        print(f"  réglages de l'utilisateur : barres = {barres}, fige = {fige}")
    if fige:
        d.fige = True

    # --- LA BASCULE : `_on_moteur`, SANS nouvelle frame --------------------
    _dessinees.clear()
    print("  [bascule] moteur → STF (aucune nouvelle frame)")
    app.var_moteur.set("STF")
    app._on_moteur()
    pomper(0.1)
    for i, img8 in enumerate(list(_dessinees)):
        decris(f"image #{i + 1} (immédiate)", img8)
    fini = time.time() + 25.0
    while time.time() < fini and (d.vl_en_cours() or d.vl_new):
        pomper(0.05)
    pomper(0.2)
    for i, img8 in enumerate(list(_dessinees)):
        decris(f"image #{i + 1} (au total)", img8)
    print("  état APRÈS la bascule :")
    etat(d)

    # --- référence : le MÊME étirement STF sur la MÊME image, sans mémoire --
    ref = DisplayProcessor()
    ref.stretch = "stf"
    ref.auto = d.auto
    ref.fige = False
    ref.bar_noir, ref.bar_median, ref.bar_blanc = (d.bar_noir, d.bar_median,
                                                   d.bar_blanc)
    ref.gamma, ref.saturation = d.gamma, d.saturation
    ref.sat_canaux = d.sat_canaux
    ref.black, ref.white = d.black, d.white
    ref.vl_neutre_fond = d.vl_neutre_fond
    ref.vl_chroma = d.vl_chroma
    ref.vl_denoise = d.vl_denoise
    ref.vl_denoise_methode = d.vl_denoise_methode
    ref.vl_denoise_force = d.vl_denoise_force
    ref.vl_graxpert = d.vl_graxpert
    ref.vl_graxpert_cmd = d.vl_graxpert_cmd
    ref.vl_sharp = d.vl_sharp
    ref.vl_sharp_iterations = d.vl_sharp_iterations
    ref.notify_new_stack()
    ref_img = ref.process(dernier, live=False)
    decris("référence STF (stats neuves)", ref_img)
    print("      · référence : stats="
          f"{tuple(round(v, 6) for v in ref._stats)} "
          f"lo={ref.last_lo:.6f} hi={ref.last_hi:.6f} m={ref.last_m:.4f}")
    if _dessinees:
        ecart = float(np.mean(np.abs(np.asarray(_dessinees[-1], np.float32)
                                     - np.asarray(ref_img, np.float32))))
        print(f"      · écart moyen |bascule − référence| = {ecart:.2f} niveaux")
    return d, dernier, ref_img


# ================================================================= exécution
if not V.moteur_disponible():
    print("Moteur VeraLux indisponible — diagnostic impossible.")
    raise SystemExit(0)

_reel_gx = gx_live.appliquer
gx_live.appliquer = lambda img, cmd, timeout=gx_live.TIMEOUT_S: \
    (np.flipud(img), "")          # GraXpert factice : copie retournée
try:
    scenario("A — VeraLux seul, puis bascule STF")
    scenario("B — VeraLux + chroma, puis bascule STF", chroma=True)
    scenario("C — VeraLux + barres réglées à la main, puis bascule STF",
             chroma=True, barres=(0.05, 0.35, 0.45))
    scenario("D — VeraLux + auto FIGÉ, puis bascule STF", chroma=True, fige=True)
    scenario("E — VeraLux + chaîne lourde (GX/DN/NET/CH), puis bascule STF",
             chroma=True, chaine_lourde=True)
    scenario("F — VeraLux + GESTE pendant le calcul, puis bascule STF",
             chroma=True, geste=True)
    scenario("G — VeraLux + chaîne lourde + GESTE, puis bascule STF",
             chroma=True, chaine_lourde=True, geste=True)
finally:
    gx_live.appliquer = _reel_gx

print()
print("Fin du diagnostic — aucune correction appliquée.")
root.destroy()
