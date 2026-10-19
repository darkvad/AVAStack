# -*- coding: utf-8 -*-
"""Banc P7 (19/10/2026) — UN CHOIX DE CORRECTION DE COULEUR DOIT RECALCULER L'IMAGE.

DÉFAUT SIGNALÉ PAR ALAIN (19/10/2026, après la validation du Lot 1) :
« au clic sur un choix de correction de couleur, l'image ne se recalcule pas
toujours ou garde le choix précédent ».

DEUX CAUSES MESURÉES SÉPARÉMENT (aucune n'est une absence de code : ce sont
deux trous dans le TRANSPORT du changement) :

  ⓐ un rendu poussé par le worker APRÈS un changement de réglage porte le MÊME
    nombre de frames que le précédent. `_tick` ne force donc pas la chaîne
    (il n'appelle `notify_new_stack()` que quand `st["frames"]` change) et la
    clé de mémoïsation (`_vl_params() + (img.shape,)`) ne bouge pas → la
    chaîne rend son résultat EN CACHE, calculé avec les corrections
    PRÉCÉDENTES. C'est le cas d'un clic SPCC / gains Gaia : les gains sont
    posés dans le stacker par le worker au tour suivant, puis il pousse le
    rendu — sans nouvelle frame.
  ⓑ la clé `_vl_params()` ne contient NI les gains, NI l'équilibrage, NI le
    Linear Fit. Sur le chemin PAR COUCHE (GraXpert / débruitage live en
    composition), `corrections_couleur()` est appliquée DANS la chaîne
    (`display._vl_worker`) : changer seulement un gain ne change pas la clé →
    l'image en cache est republiée à l'identique.

Vérifie :
  [1] `_vl_params()` change quand les CORRECTIONS de la composition changent
      (gains effectifs, équilibrage, Linear Fit) ;
  [2] `App._pousser_rendu()` (rendu SANS nouvelle frame) FORCE la chaîne ;
  [3] STF + débruitage : le rendu publié est bien celui de la NOUVELLE
      correction, pas celui d'avant ;
  [4] VeraLux (si le moteur est disponible) : même exigence — le symptôme
      d'origine était « il garde le choix précédent » ;
  [5] chemin PAR COUCHE : changer les gains SEUL relance la chaîne et change
      la sortie (corrections appliquées DANS le worker) ;
  [6] non-régression : mode mono (aucune composition) → clé inchangée, et
      `process()` rend toujours du 8 bits de mêmes dimensions.

Exécution (interpréteur du venv) :
    python bancs/_test_p7_recalcul_corrections.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import queue
import sys
import time

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.ui.app as app_mod                                   # noqa: E402
from avastack.processing import couleurs as C                       # noqa: E402
from avastack.processing import veralux as V                        # noqa: E402
from avastack.processing.display import DisplayProcessor            # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def attendre_vl(d, timeout=60.0, avant=None):
    """Attend la fin d'un job de la chaîne (polling, 20 ms).

    `avant` : objet image du résultat PRÉCÉDENT ; on attend alors un résultat
    DIFFÉRENT (sans quoi on repartirait aussitôt sur l'ancien, déjà publié)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with d._vl_lock:
            res = d._vl_result
            if (d._vl_job is None and not d._vl_pending and res is not None
                    and (avant is None or res[1] is not avant)):
                return True
        time.sleep(0.02)
    return False



# Scène COULEUR déterministe : fond bleuté + noyau jaune (mêmes genres de scène
# que les bancs 124/125, où l'écart entre deux jeux de gains est VISIBLE).
H, W = 96, 128
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2)
noyau = 0.6 * np.exp(-(rr / 12.0) ** 2) + 0.2 * np.exp(-(rr / 40.0) ** 2)
rng = np.random.default_rng(7)
SCENE = np.stack([0.03 + 1.00 * noyau + rng.normal(0, 0.002, (H, W)),
                  0.032 + 0.62 * noyau + rng.normal(0, 0.002, (H, W)),
                  0.034 + 0.44 * noyau + rng.normal(0, 0.002, (H, W))],
                 -1).astype(np.float32)
SCENE = np.clip(SCENE, 0, 1).astype(np.float32)


def corrigee(img, gains):
    """Ce que `CompositeStacker.mean()` pousse : les gains appliqués EN AMONT
    (l'écran reçoit une image DÉJÀ corrigée, sans savoir ce qu'elle porte)."""
    out = np.array(img, np.float32, copy=True)
    for i, canal in enumerate(("R", "G", "B")):
        out[..., i] *= float(gains.get(canal, 1.0))
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def compo(gains, wb=None, fit=None, canaux=None):
    """Tuple de composition au format du worker (déballage tolérant côté
    display) : (canaux, nom, gains, mode_l, fit, wb, norm, lissage, fusion)."""
    if canaux is None:
        canaux = {"R": SCENE[..., 0], "G": SCENE[..., 1], "B": SCENE[..., 2]}
    return (canaux, "RGB", dict(gains), None, fit, wb, False,
            (False, 0.0), None)


def _processor(stretch="stf", denoise=False):
    d = DisplayProcessor()
    d.stretch = stretch
    if denoise:
        d.vl_denoise = True
        d.vl_denoise_methode = "nlm"
        d.vl_denoise_force = 0.3
    return d


# =========================================== [1] la clé suit les corrections
print("=" * 78)
print("[1] `_vl_params()` suit les CORRECTIONS de la composition")
print("=" * 78)
d = _processor()
d.vl_compo = compo({"R": 1.0, "G": 1.0, "B": 1.0})
k_gains_1 = d._vl_params()
d.vl_compo = compo({"R": 1.35, "G": 1.0, "B": 0.82})
k_gains_2 = d._vl_params()
verifie(k_gains_1 != k_gains_2,
        "changer les GAINS EFFECTIFS change la clé (sinon l'image en cache "
        "est republiée à l'identique)")

d.vl_compo = compo({"R": 1.0, "G": 1.0, "B": 1.0}, wb=(False, 1.0, None))
k_wb_off = d._vl_params()
d.vl_compo = compo({"R": 1.0, "G": 1.0, "B": 1.0}, wb=(True, 0.8, None))
k_wb_on = d._vl_params()
verifie(k_wb_off != k_wb_on, "changer l'ÉQUILIBRAGE change la clé")

d.vl_compo = compo({"R": 1.0, "G": 1.0, "B": 1.0},
                   fit=(False, "offset"))
k_fit_off = d._vl_params()
d.vl_compo = compo({"R": 1.0, "G": 1.0, "B": 1.0},
                   fit=(True, "gain_offset"))
k_fit_on = d._vl_params()
verifie(k_fit_off != k_fit_on, "changer le LINEAR FIT change la clé")

# Mode MONO : aucune composition → la clé ne doit pas dépendre d'un état absent.
mono = _processor()
k_mono_1 = mono._vl_params()
mono.vl_compo = None
verifie(mono._vl_params() == k_mono_1,
        "mode MONO (vl_compo None) : la clé reste stable")

# Déballage TOLÉRANT : un type inattendu ne doit JAMAIS faire lever la clé (un
# `_vl_params()` qui lève figerait l'aperçu pour toute la session).
import avastack.processing.display as D                            # noqa: E402
verifie(D.params_corrections(None) == ()
        and D.params_corrections({}) == ()
        and len(D.params_corrections(("court",))) == 7,
        "signature TOLÉRANTE : None / dict / tuple court ne lèvent pas")



# ============================== [2] un rendu poussé sans frame FORCE la chaîne
print()
print("=" * 78)
print("[2] `App._pousser_rendu()` (SANS nouvelle frame) force la chaîne")
print("=" * 78)


class _FauxStacker:
    """Le minimum que `App._pousser_rendu` lit sur la façade de composition."""

    composition = "RGB"
    linear_fit = False
    linear_fit_mode = "offset"
    wb_auto = False
    wb_force = 1.0
    cadre = None
    normalisation_commune = False
    lissage_halos = False
    seuil_masque_halos = 3.0

    def __init__(self, img, gains):
        self.img = img
        self.gains = dict(gains)

    def gains_effectifs(self):
        return dict(self.gains)

    def mean_avec_canaux(self):
        c = self.img
        return c, {"R": c[..., 0].copy(), "G": c[..., 1].copy(),
                   "B": c[..., 2].copy()}


class _FauxApp:
    """Objet minimal qui porte la VRAIE méthode `App._pousser_rendu` : on mesure
    le comportement du code de production, pas une copie."""

    _pousser_rendu = app_mod.App._pousser_rendu

    def __init__(self, disp, stacker):
        self.disp = disp
        self.stacker = stacker
        self._mode_compo = True
        self._compo_mode_l = None
        self._compo_fusion_ha = None
        self._dernier_st = {"frames": 3}
        self.astro_info = self.photo_info = ""
        self.spcc_info = self.restack_info = ""
        self.q = queue.Queue(maxsize=8)

    def _pleine_res_activee(self):
        return False

    def _poser_rayon_chroma(self, scale):
        pass


d_push = _processor(denoise=True)
stacker = _FauxStacker(corrigee(SCENE, {"R": 1.0, "G": 1.0, "B": 1.0}),
                       {"R": 1.0, "G": 1.0, "B": 1.0})
faux = _FauxApp(d_push, stacker)
d_push._vl_force = False           # état au repos : aucune frame en attente
faux._pousser_rendu()
verifie(d_push._vl_force is True,
        "un rendu poussé HORS nouvelle frame arme `_vl_force` (sinon la chaîne "
        "rend son cache : le choix précédent reste affiché)")
verifie(not faux.q.empty(),
        "…et le rendu part bien vers l'interface (message en file)")


# ================== [3] STF + chroma : le rendu suit la nouvelle correction
print()
print("=" * 78)
print("[3] STF + chroma : l'écran rend la NOUVELLE correction")
print("=" * 78)
GAINS_1 = {"R": 1.0, "G": 1.0, "B": 1.0}
GAINS_2 = {"R": 1.45, "G": 1.0, "B": 0.80}
IMG_1 = corrigee(SCENE, GAINS_1)
IMG_2 = corrigee(SCENE, GAINS_2)

d3 = _processor()
d3.vl_chroma = True                 # chaîne pré-étirement ACTIVE (hors couches)
d3.vl_chroma_force = 0.8
d3.vl_compo = compo(GAINS_1)
d3.notify_new_stack()
d3._process_chaine(IMG_1, live=False)
verifie(attendre_vl(d3), "1er passage de la chaîne terminé")
res_1 = np.array(d3._vl_result[1], copy=True)
_ = d3.process(IMG_1, live=False)


# LE CLIC : la correction change EN AMONT (le stacker est recalculé), le rendu
# est poussé par `_pousser_rendu` — même nombre de frames, donc AUCUN
# `notify_new_stack()` ne vient de `_tick`.
st3 = _FauxStacker(IMG_2, GAINS_2)
faux3 = _FauxApp(d3, st3)
faux3._pousser_rendu()
# L'interface consomme le message : `process()` soumet la chaîne (le forçage
# armé par `_pousser_rendu` est consommé ICI, comme dans `_tick`).
out3 = d3.process(IMG_2, live=False)
verifie(attendre_vl(d3, avant=res_1), "2e passage de la chaîne terminé")
res_2 = np.array(d3._vl_result[1], copy=True)
ecart = float(np.max(np.abs(res_2 - res_1)))
verifie(ecart > 0.01,
        f"la sortie de chaîne A CHANGÉ avec la correction (écart {ecart:.4f})")
attendu = C.reduire_bruit_chroma(IMG_2, force=0.8, rayon=d3.vl_chroma_rayon)
verifie(float(np.max(np.abs(res_2 - attendu))) < 1e-6,
        "la sortie est bien calculée sur l'image de la NOUVELLE correction "
        "(chroma appliquée dessus)")
verifie(out3.dtype == np.uint8 and out3.shape == IMG_2.shape,
        "l'écran rend une image 8 bits de mêmes dimensions")



# ============================== [4] VeraLux (si le moteur est disponible)
print()
print("=" * 78)
print("[4] VeraLux : le choix précédent ne doit pas être republié")
print("=" * 78)
if not V.moteur_disponible():
    print("  (moteur VeraLux absent : volet sauté, comportement STF déjà couvert)")
else:
    dv = _processor("veralux", denoise=True)
    dv.vl_compo = compo(GAINS_1)
    dv.notify_new_stack()
    dv._process_chaine(IMG_1, live=False)
    verifie(attendre_vl(dv, timeout=120.0), "1er étirement VeraLux terminé")
    vres_1 = np.array(dv._vl_result[1], copy=True)
    stv = _FauxStacker(IMG_2, GAINS_2)
    fauxv = _FauxApp(dv, stv)
    fauxv._pousser_rendu()
    _ = dv.process(IMG_2, live=False)      # l'UI rend → la chaîne est soumise
    verifie(attendre_vl(dv, timeout=120.0, avant=vres_1),
            "2e étirement VeraLux terminé")
    vres_2 = np.array(dv._vl_result[1], copy=True)

    ecart_v = float(np.max(np.abs(vres_2 - vres_1)))
    verifie(ecart_v > 0.005,
            "l'image VeraLux est RECALCULÉE avec la nouvelle correction "
            f"(écart {ecart_v:.4f}) — pas republiée à l'identique")


# ==================== [5] chemin PAR COUCHE : les gains entrent dans la clé
print()
print("=" * 78)
print("[5] chemin PAR COUCHE : changer les gains SEUL relance la chaîne")
print("=" * 78)
canaux = {"R": SCENE[..., 0].copy(), "G": SCENE[..., 1].copy(),
          "B": SCENE[..., 2].copy()}
d5 = _processor(denoise=True)
d5.vl_compo = compo(GAINS_1, canaux=canaux)
d5.notify_new_stack()
d5._process_chaine(SCENE, live=False)
verifie(attendre_vl(d5), "1er passage (recomposition + gains 1.0) terminé")
pc_1 = np.array(d5._vl_result[1], copy=True)
# MÊMES couches, MÊME image d'entrée : SEULS les gains changent (le clic).
d5.vl_compo = compo(GAINS_2, canaux=canaux)
d5._process_chaine(SCENE, live=False)
verifie(attendre_vl(d5, avant=pc_1), "2e passage terminé")

pc_2 = np.array(d5._vl_result[1], copy=True)
ecart_pc = float(np.max(np.abs(pc_2 - pc_1)))
verifie(ecart_pc > 0.01,
        "le chemin par couche APPLIQUE les nouveaux gains "
        f"(écart {ecart_pc:.4f}) — la clé a bien changé")


# ======================================================= [6] non-régression
print()
print("=" * 78)
print("[6] Non-régression : bornes, dimensions, clé mono stable")
print("=" * 78)
d6 = _processor(denoise=True)          # aucun vl_compo : rendu d'image seule
d6.notify_new_stack()
d6._process_chaine(IMG_1, live=False)
verifie(attendre_vl(d6), "chaîne mono terminée")
out6 = d6.process(IMG_1, live=False)
verifie(out6.dtype == np.uint8 and out6.shape == IMG_1.shape
        and int(out6.min()) >= 0 and int(out6.max()) <= 255,
        "sortie 8 bits bornée, mêmes dimensions")
verifie(d6.vl_compo is None, "aucune composition posée en mono")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)


