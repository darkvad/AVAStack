# -*- coding: utf-8 -*-
"""Banc v2.37.0 — RÉDUCTION DU BRUIT CHROMATIQUE (« un SCNR pour le bleu »).

DEMANDE D'ALAIN (25/09/2026, après mesure de ses empilements M31 v2.36.1) :
« Il reste effectivement un bruit résiduel il me semble » → confirmé, et
chiffré : le grain du fond est ÉQUILIBRÉ en R/G (0,902) mais B/G reste à 1,174
(41 frames : 1,163 ; 115 frames : 1,174 — donc STABLE, ce n'est pas un artefact
d'empilement). Cause exacte, vérifiée au chiffre près : une correction
MULTIPLICATIVE amplifie le bruit du canal qu'elle monte, et la SPCC applique
K_B/K_G = 1,0000/0,7587 = 1,32 →
    (σ_B·K_B)/(σ_G·K_G) = 0,891 × 1,318 = 1,174  (mesuré : 1,174)
    (σ_R·K_R)/(σ_G·K_G) = 1,099 × 0,820 = 0,902  (mesuré : 0,902)
Réponse d'Alain : « oui pour la réduction de bruit chromatique (j'allais te
demander un équivalent de SCNR pour le bleu de toute façon) et case décochée par
défaut. »

Vérifie :
  [1] `couleurs.reduire_bruit_chroma` : no-op (mono, force 0), l'entrée n'est
      jamais modifiée, aucune exception sur une forme inattendue ;
  [2] le grain CHROMATIQUE du fond tombe du facteur demandé (mesuré en σ haute
      fréquence sur une zone de ciel) sans toucher à la LUMINANCE ;
  [3] la couleur de l'OBJET (chroma étendue, basse fréquence) est préservée ;
  [4] LE CAS D'ALAIN : des gains de type SPCC déséquilibrent le grain (B/G 1,32),
      la réduction de bruit chromatique le RAMÈNE vers 1,00 ;
  [5] transport de bout en bout : la case voyage dans le job du solveur VeraLux
      (10e/11e éléments) et la sortie DU SOLVEUR est exactement la chaîne
      attendue (comparaison image à image) ;
  [6] branchement UI : case DÉCOCHÉE par défaut, présente dans la clé des
      réglages, rendu IMMÉDIAT au clic (leçon du jalon 39 — une case couleur qui
      n'appelle pas _refresh_preview() semble inerte jusqu'à la frame suivante),
      persistée en config.

Exécution : python _test_chroma_nr_jalon63.py
"""
import sys
import time
import tkinter as tk

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)          # parade du projet : crash OpenCV 5/OpenCL au
                                     # teardown quand on enchaîne les bancs Tk

from avastack.processing import couleurs as C                    # noqa: E402
from avastack.processing import veralux as V                     # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ------------------------------------------------ scène : son ciel, son grain
# Valeurs RÉELLES de son empilement : ciel 0,031, grain 0,0005 par canal (son
# fichier : σ_R/G/B = 0,000519 / 0,000579 / 0,000673 à 41 frames) ; la galaxie
# est JAUNE (R > G > B, chroma étendue) — comme sur ses images.
CIEL = 0.031
GRAIN = 0.0005
COULEUR_OBJ = (1.00, 0.80, 0.55)
SPCC_K = (0.6223, 0.7587, 1.0000)          # ses coefficients SPCC réels
H, W = 600, 900
rng = np.random.default_rng(7)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt((xx - W / 2.0) ** 2 + (yy - H / 2.0) ** 2)
galaxie = 0.9 * np.exp(-(rr / 40.0) ** 2) + 0.25 * np.exp(-(rr / 140.0) ** 2)
bruit = rng.normal(0.0, GRAIN, (H, W, 3)).astype(np.float32)
scene = np.stack([CIEL + COULEUR_OBJ[c] * galaxie + bruit[..., c]
                  for c in range(3)], -1).astype(np.float32)
scene = np.clip(scene, 0.0, 1.0)
ZONE_CIEL = (slice(20, 160), slice(20, 400))        # loin de la galaxie
COEUR = (slice(292, 308), slice(442, 458))          # cœur de la galaxie


def grain(a, zone=ZONE_CIEL):
    """σ HAUTE FRÉQUENCE (le grain) par canal sur une zone : la structure
    (galaxie) est lisse, le grain vit à l'échelle du pixel."""
    out = []
    for c in range(3):
        p = np.asarray(a, np.float32)[..., c][zone]
        hf = p - cv2.GaussianBlur(p, (0, 0), sigmaX=2.0)
        out.append(float(hf.std()))
    return out


def luminance(a):
    a = np.asarray(a, np.float32)
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def chroma_hf(a, zone=ZONE_CIEL):
    """σ haute fréquence des ÉCARTS DE COULEUR (R−G et B−G) : c'est LA mesure du
    grain CHROMATIQUE. Le grain de LUMINANCE, lui, est commun aux trois canaux et
    s'annule dans ces différences — c'est pour ça qu'une réduction de bruit
    chromatique ne peut PAS l'enlever (rôle du débruitage)."""
    a = np.asarray(a, np.float32)
    out = []
    for i, j in ((0, 1), (2, 1)):
        d = a[..., i][zone] - a[..., j][zone]
        out.append(float((d - cv2.GaussianBlur(d, (0, 0), sigmaX=2.0)).std()))
    return out


# =============================================== [1] no-op / contrat d'entrée
print("[1] reduire_bruit_chroma : no-op et contrat (entrée jamais modifiée)")
mono = np.full((40, 40), 0.031, np.float32)
verifie(np.array_equal(C.reduire_bruit_chroma(mono), mono),
        "image MONO (H, W) : rendue inchangée (pas de chroma à lisser)")
verifie(np.array_equal(C.reduire_bruit_chroma(scene, force=0.0), scene),
        "force 0 : no-op strict (aucune modification)")
avant = scene.copy()
C.reduire_bruit_chroma(scene)
verifie(np.array_equal(scene, avant),
        "l'image d'ORIGINE n'est jamais modifiée en place")
for forme in ((30,), (10, 10, 4), (10, 10, 1)):
    z = np.zeros(forme, np.float32)
    verifie(C.reduire_bruit_chroma(z).shape == z.shape,
            f"forme {forme} : rendue telle quelle (aucune exception)")

# ============================ [2] le grain chromatique tombe, la luminance non
print("[2] le grain CHROMATIQUE du fond tombe ; la LUMINANCE est intacte")
g0 = grain(scene)
verifie(max(g0) / min(g0) < 1.05,
        f"scène de départ : grain ÉQUILIBRÉ entre canaux "
        f"({np.round(g0, 6).tolist()} — c'est le fond déjà neutralisé)")
hf = lambda p: float((p - cv2.GaussianBlur(p, (0, 0), sigmaX=2.0)).std())
ch0 = chroma_hf(scene)
y0 = cv2.cvtColor(scene, cv2.COLOR_RGB2YCrCb)[..., 0].copy()
print(f"    grain CHROMATIQUE de départ : R−G {ch0[0]:.6f} · "
      f"B−G {ch0[1]:.6f} (le grain coloré à retirer)")
for force in (0.25, 0.5, 1.0):
    s = C.reduire_bruit_chroma(scene, force=force)
    ch = chroma_hf(s)
    ratio = max(ch) / max(ch0)
    ecart_y = float(np.abs(
        cv2.cvtColor(s, cv2.COLOR_RGB2YCrCb)[..., 0] - y0).max())
    verifie(abs(ratio - (1.0 - force)) < 0.05,
            f"force {force} : grain CHROMATIQUE ×{ratio:.3f} (attendu "
            f"×{1.0 - force:.2f} — la part demandée est retirée)")
    # Le canal Y de OpenCV doit être intact — mesuré sur le FOND (la zone qui
    # compte) ; sur toute l'image il reste une queue < 1,4e-05 dans le cœur, où
    # la reconstruction YCrCb→RVB sature au bord haut de l'échelle.
    dy = np.abs(cv2.cvtColor(s, cv2.COLOR_RGB2YCrCb)[..., 0] - y0)
    verifie(float(dy[ZONE_CIEL].max()) < 2e-6,
            f"force {force} : LUMINANCE du FOND inchangée (écart max "
            f"{float(dy[ZONE_CIEL].max()):.2e} sur le canal Y de OpenCV — seuls "
            f"Cr et Cb sont réécrits)")
    verifie(float(dy.max()) < 2e-5,
            f"force {force} : luminance inchangée PARTOUT à "
            f"{float(dy.max()):.2e} près (le seul écart est dans le cœur à "
            f"0,93 — saturation au bord de l'échelle, invisible après étirement)")
    verifie(float(np.abs(luminance(s) - luminance(scene)).max()) < 1e-4,
            f"force {force} : luminance RÉELLE (0,299/0,587/0,114) inchangée à "
            f"{float(np.abs(luminance(s) - luminance(scene)).max()):.1e} près")
# Le grain de LUMINANCE ne doit pas être aplati : la réduction vise le grain
# COLORÉ, pas le grain tout court (lisser tout serait un débruitage, réglage
# déjà disponible séparément).
det_scene = hf(luminance(scene))
det_lisse = hf(luminance(C.reduire_bruit_chroma(scene, force=1.0)))
print(f"    grain de luminance : {det_scene:.6f} → {det_lisse:.6f} "
      f"(×{det_lisse / det_scene:.2f} — le grain GRIS subsiste)")
verifie(det_lisse > 0.9 * det_scene,
        "le grain de LUMINANCE n'est pas touché (la réduction ne retire que la "
        "COULEUR du grain, pas sa présence : c'est le débruitage qui la réduit)")

# ================================================== [3] l'objet est préservé
print("[3] la couleur de l'OBJET (chroma étendue) est préservée")
c0 = np.asarray(scene, np.float32)[COEUR].reshape(-1, 3).mean(0)
c1 = np.asarray(C.reduire_bruit_chroma(scene, force=1.0),
                np.float32)[COEUR].reshape(-1, 3).mean(0)
ecart = max(abs(c1[k] / c1[1] - c0[k] / c0[1]) for k in (0, 2))
verifie(ecart < 0.02,
        f"couleur du cœur de la galaxie préservée à {ecart * 100:.2f} % "
        f"(R/G {c0[0] / c0[1]:.4f} → {c1[0] / c1[1]:.4f} · "
        f"B/G {c0[2] / c0[1]:.4f} → {c1[2] / c1[1]:.4f})")


# ============================================ [4] LE CAS D'ALAIN (le grain B)
print("[4] les gains de la SPCC déséquilibrent le grain par canal ; la chroma le décolore")
# MESURE DÉCISIVE (la même que sur ses fichiers) : le grain σ PAR CANAL suit
# EXACTEMENT les gains multiplicatifs — un canal monté de 32 % a 32 % de grain
# en plus, toute chose égale. Le déséquilibre observé sur son empilement (B/G
# 1,174) est donc bien le produit de son propre équilibre de couches (0,891, plus
# fine que le vert) par K_B/K_G (1,318) : 0,891 × 1,318 = 1,174 (mesuré 1,174).
spcc = (scene * np.array(SPCC_K, np.float32).reshape(1, 1, 3)).astype(np.float32)
g_scene, g_spcc = grain(scene), grain(spcc)
suivi_g = (g_scene[2] and g_spcc[2] / g_scene[2]) / (g_spcc[1] / g_scene[1])
verifie(abs(suivi_g - SPCC_K[2] / SPCC_K[1]) < 0.02,
        f"le grain σ PAR CANAL suit les gains : σ_B/σ_G monte à ×{suivi_g:.3f} "
        f"= K_B/K_G = {SPCC_K[2] / SPCC_K[1]:.3f} (σ ∝ gain)")
b_avant = g_spcc[2] / g_spcc[1]
r_avant = g_spcc[0] / g_spcc[1]
print(f"    grain B/G après gains SPCC : ×{b_avant:.3f} · R/G ×{r_avant:.3f} — "
      f"chez Alain : 0,891 × 1,318 = {0.891 * 1.318:.3f} (mesuré 1,174)")
verifie(1.28 < b_avant < 1.36 and 0.78 < r_avant < 0.86,
        f"grain BLEU en excès (×{b_avant:.3f}) et rouge en déficit "
        f"(×{r_avant:.3f}) : c'est le déséquilibre constaté sur son fichier")
ch_avant = chroma_hf(spcc)
for force in (0.5, 1.0):
    s = C.reduire_bruit_chroma(spcc, force=force)
    ch_apres = chroma_hf(s)
    ratio = max(ch_apres) / max(ch_avant)
    verifie(abs(ratio - (1.0 - force)) < 0.05,
            f"force {force} : GRAIN COLORÉ (chroma haute fréquence) ×{ratio:.3f} "
            f"— la part demandée du grain coloré disparaît")
colore = max(chroma_hf(C.reduire_bruit_chroma(spcc, force=1.0))) / max(ch_avant)
verifie(colore < 0.10,
        f"force 1,0 : il ne reste {colore * 100:.1f} % du grain coloré — le "
        f"grain restant est GRIS (amplitude par canal, rôle du débruitage)")

# ================================[5] transport : le solveur VeraLux l'applique
print("[5] transport : la case voyage dans le job et le solveur l'applique")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui                                 # noqa: E402
ui.CONFIG = {}
vus = []
ui.sauver_config = lambda d: vus.append(d)
app = ui.App(root)
# État de CONSTRUCTION (avant tout bascule) : la case est DÉCOCHÉE par défaut.
verifie(hasattr(app, "var_vl_chroma") and bool(app.var_vl_chroma.get()) is False,
        "case « Réduire le bruit chromatique (live) » présente et DÉCOCHÉE par "
        "défaut (choix d'Alain)")
verifie(bool(app.disp.vl_chroma) is False,
        "le solveur démarre sans réduction de bruit chromatique")
# La clé des réglages doit CHANGER en la cochant — c'est elle qui relance la
# résolution (et le curseur de force en fait partie, plus bas).
cle_off = app.disp._vl_params()
app.var_vl_chroma.set(True)
app._on_vl_chroma()
cle_on = app.disp._vl_params()
verifie(cle_off != cle_on and bool(app.disp.vl_chroma) is True,
        "cochée : l'option entre dans la clé des réglages (→ re-résolution)")
app.var_vl_chroma.set(False)
app._on_vl_chroma()
petite = scene[0:192, 0:192].astype(np.float32)      # cadrage de CIEL


def _attendre(predicat, delai=60.0):
    t0 = time.time()
    while time.time() - t0 < delai:
        if predicat():
            return True
        time.sleep(0.2)
    return False


def _resultat_solveur():
    """Sortie PUBLIÉE par le solveur VeraLux (résultat complet, clé courante)."""
    if not _attendre(lambda: not app.disp._vl_pending
                     and app.disp._vl_result is not None
                     and app.disp._vl_result[0] == app.disp._vl_params()):
        return None
    return np.asarray(app.disp._vl_result[1], np.float32)


def _params_disp():
    d = app.disp
    return dict(mode=d.vl_mode_res, target_bg=d.vl_target_bg,
                log_d=d.vl_log_d, profil=d.vl_profil)


# On isole la réduction de bruit chromatique : neutralisation décochée (la scène
# a un fond neutre, cette correction serait de toute façon nulle).
app.var_vl_neutre.set(False)
app._on_vl_neutre()
app.var_vl_chroma.set(False)
app._on_vl_chroma()
app.disp.reset()
app.disp.notify_new_stack()
app.disp._process_veralux(petite, live=False)
sans = _resultat_solveur()
verifie(sans is not None, "solveur VeraLux : résultat publié (case décochée)")
attendu_sans = np.asarray(V.etirer(petite, **_params_disp())[0], np.float32)
ecart = float(np.abs(sans - attendu_sans).max()) if sans is not None else 1.0
verifie(ecart < 1e-6,
        f"case décochée : sortie du solveur = chaîne SANS réduction de bruit "
        f"chromatique (écart max {ecart:.2e})")
app.var_vl_chroma.set(True)
app.var_vl_chroma_force.set(0.5)
app._on_vl_chroma()
app.disp.reset()
app.disp.notify_new_stack()
app.disp._process_veralux(petite, live=False)
avec = _resultat_solveur()
verifie(avec is not None, "solveur VeraLux : résultat publié (case cochée)")
attendu = np.asarray(
    V.etirer(C.reduire_bruit_chroma(petite, force=0.5), **_params_disp())[0],
    np.float32)
ecart = float(np.abs(avec - attendu).max()) if avec is not None else 1.0
verifie(ecart < 1e-6,
        f"case cochée (force 0,5) : sortie du solveur = chaîne AVEC réduction de "
        f"bruit chromatique AVANT l'étirement (écart max {ecart:.2e})")
if sans is not None and avec is not None:
    ch_sans, ch_avec = chroma_hf(sans), chroma_hf(avec)
    verifie(max(ch_avec) < max(ch_sans),
            f"le fond ÉTIRÉ est bien moins bruité en couleur : "
            f"{max(ch_sans):.5f} → {max(ch_avec):.5f} "
            f"(×{max(ch_avec) / max(ch_sans):.3f} après la chaîne complète)")



# ============================================ [6] rendu IMMÉDIAT + config
print("[6] UI : rendu IMMÉDIAT au clic (leçon du jalon 39) et persistance")
# Mise en place « comme en session » (mêmes réglages que le banc jalon 39) :
# moteur VeraLux, vue « empilement », aperçu courant posé — puis AUCUNE frame et
# AUCUN autre réglage : seul le callback de la case doit tout relancer.
app.disp.stretch = "veralux"
app.var_view.set("pile")
app._sync_vl_couleur_vue()
app.last_show = petite
# Le CURSEUR de force change aussi la clé (sinon bouger la force ne ferait rien).
app.var_vl_chroma.set(True)
app.var_vl_chroma_force.set(0.5)
app._on_vl_chroma()
cle_f1 = app.disp._vl_params()
app.var_vl_chroma_force.set(0.9)
app._on_vl_chroma()
verifie(cle_f1 != app.disp._vl_params() and app.disp.vl_chroma_force == 0.9,
        "curseur de force : la clé change à chaque valeur (re-résolution)")
app.var_vl_chroma_force.set(0.5)
app.var_vl_chroma.set(False)
app._on_vl_chroma()
_resultat_solveur()
app.var_vl_chroma.set(True)
t0 = time.time()
app._on_vl_chroma()                      # SEUL le callback de la case
instant = time.time() - t0
verifie(instant < 2.0,
        f"le clic soumet la chaîne IMMÉDIATEMENT ({instant * 1000:.0f} ms, sans "
        f"nouvelle frame ni autre réglage)")
attendu = np.asarray(
    V.etirer(C.reduire_bruit_chroma(petite, force=0.5), **_params_disp())[0],
    np.float32)
res = _resultat_solveur()
verifie(res is not None and float(np.abs(res - attendu).max()) < 1e-6,
        "…et le rendu affiché est bien celui de la nouvelle chaîne (réduction de "
        "bruit chromatique AVANT l'étirement)")
app.var_vl_chroma.set(False)
t0 = time.time()
app._on_vl_chroma()
instant = time.time() - t0
attendu = np.asarray(V.etirer(petite, **_params_disp())[0], np.float32)
res = _resultat_solveur()
verifie(instant < 2.0 and res is not None
        and float(np.abs(res - attendu).max()) < 1e-6,
        f"décochée : retour immédiat au rendu sans réduction "
        f"({instant * 1000:.0f} ms)")
# Persistance (valeur explicite dans les deux sens) + chemin de sauvegarde.
app.var_vl_chroma.set(True)
app.var_vl_chroma_force.set(0.75)
app._on_vl_chroma()
app._sauver_config_app()
verifie(vus and bool(vus[-1].get("vl_chroma")) is True
        and abs(float(vus[-1].get("vl_chroma_force")) - 0.75) < 1e-9,
        "config : « vl_chroma » et sa force persistées")
ui.CONFIG = {"vl_chroma": True, "vl_chroma_force": 10.0}   # force aberrante
app.var_vl_chroma.set(False)
app._on_vl_chroma()
app._restaurer_config()
verifie(bool(app.var_vl_chroma.get()) is True
        and bool(app.disp.vl_chroma) is True,
        "config relue : case cochée restaurée dans l'UI ET dans le solveur")
app.var_vl_chroma_force.set(0.5)               # état de départ « propre »
app.disp.vl_chroma_force = 0.5
app._restaurer_config()                        # config à force aberrante (10,0)
verifie(app.disp.vl_chroma_force == 0.5
        and float(app.var_vl_chroma_force.get()) == 0.5,
        f"force aberrante (10,0) IGNORÉE : la valeur d'usage reste 0,5 "
        f"({app.disp.vl_chroma_force})")
ui.CONFIG = {}                                 # config ANTÉRIEURE : sans la clé
app.var_vl_chroma.set(False)
app._on_vl_chroma()
app._restaurer_config()
verifie(bool(app.var_vl_chroma.get()) is False and bool(app.disp.vl_chroma) is False,
        "config antérieure (sans la clé) : la case ne s'active PAS toute seule")
app.var_vl_chroma.set(True)
app._on_vl_chroma()
r = app._reglages_rendu()
verifie(bool(r.get("vl_chroma")) is True and "vl_chroma_force" in r,
        "transmise au chemin de sauvegarde « tel que vu » (même rendu que "
        "l'écran)")
root.destroy()

# =====================[7] SUR UN FICHIER RÉEL (optionnel) : mesurer SON grain
if len(sys.argv) > 1:
    import os                                                  # noqa: E402
    from avastack.images import load_image                     # noqa: E402
    print(f"[7] mesure sur un fichier RÉEL : {os.path.basename(sys.argv[1])}")
    reel = np.asarray(load_image(sys.argv[1]), np.float32)
    if reel.ndim != 3 or reel.shape[-1] != 3:
        print("    (fichier monochrome : aucune chroma à réduire)")
    else:
        # Grain chromatique du FOND : σ des écarts de couleur, sur la MOITIÉ
        # SOMBRE (robuste à un objet étendu qui remplirait le champ).
        lum = reel.mean(-1)
        bas = lum <= np.percentile(lum, 50)

        def graine(a):
            a = np.asarray(a, np.float32)
            out = []
            for i, j in ((0, 1), (2, 1)):
                d = a[..., i] - a[..., j]
                out.append(float((d - cv2.GaussianBlur(d, (0, 0), sigmaX=2.0))
                                 [bas].std()))
            return out

        ga = graine(reel)
        print(f"    grain chromatique du fond : R−G {ga[0]:.6f} · "
              f"B−G {ga[1]:.6f} (moitié sombre, {int(bas.sum())} px)")
        for force in (0.5, 1.0):
            gb = graine(C.reduire_bruit_chroma(reel, force=force))
            print(f"    force {force} : R−G ×{gb[0] / ga[0]:.3f} · "
                  f"B−G ×{gb[1] / ga[1]:.3f} (attendu ×{1.0 - force:.2f})")
        s = C.reduire_bruit_chroma(reel, force=0.5)
        dy = float(np.abs(cv2.cvtColor(np.clip(s, 0, 1), cv2.COLOR_RGB2YCrCb)
                          [..., 0] - cv2.cvtColor(np.clip(reel, 0, 1),
                                                  cv2.COLOR_RGB2YCrCb)[..., 0]).max())
        verifie(dy < 2e-4,
                f"luminance du fichier inchangée par le lissage "
                f"(écart max du canal Y {dy:.2e} — mesuré sur TOUTE l'image, "
                f"donc borné par les pixels saturés)")


print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
