# -*- coding: utf-8 -*-
"""Test du jalon 22/23 — SCNR (retrait du vert), SCNR doux (bruit seul) et
démagenta.

Décision d'Alain (19/09/2026) : appliqués APRÈS la composition (sur
l'image COULEUR du composite), chacun derrière sa case à cocher.

NOTE v2.48.0 (jalon 85) — LA CHAÎNE A CHANGÉ DE PLACE, et ce banc suit le
contrat NOUVEAU : SCNR / SCNR doux / démagenta ne sont plus appliqués par la
chaîne EXTERNE (le résultat ⚡ reste LINÉAIRE, non écrêté en vert) ; ils suivent
l'ÉTIREMENT (section « Couleur de l'objet (après étirement) »), pour le live
comme pour l'affichage du résultat externe. Les clés de configuration
`ext_scnr*` ne sont plus écrites — et sont retirées d'une configuration
antérieure. Vérifie :

  [1] module couleurs : SCNR « moyenne neutre » (G = min(G, (R+B)/2)),
      démagenta (négatif → SCNR → positif), SCNR doux (jalon 23 : retire
      le grésillement vert ≤ 3σ, préserve la structure — pensé pour les
      palettes narrowband où le vert est de la DONNÉE), mono no-op,
      entrée intacte. La recette HISTORIQUE (jalons 22/23) est vérifiée à
      `preserve_luminance=False`, et la préservation de L* — ACTIVE par
      défaut depuis le jalon 85, comme Siril / PixInsight — est vérifiée
      au défaut : elle ne touche QUE les pixels corrigés ;
  [2] live : les cases font partie de la clé des réglages VeraLux ; en
      STF/manuel, process() applique le retrait (dominance verte réduite) ;
      vue « traitée » → désactivé ;
  [3] traitement externe : AUCUNE case couleur dans cette chaîne — le
      résultat est l'entrée AU PIXEL près et l'excès de vert la traverse
      intact (aucun écrêtage en vert du fichier linéaire) ; déballage
      tolérant des anciens formats de job ;
  [3bis] chaîne externe : neutralisation de la couleur du fond (9e élément)
      puis réduction du bruit chromatique (10e/11e, force transportée) ;
  [4] persistance : clés vl_scnr / vl_scnr_doux / vl_demagenta / ext_chroma /
      ext_neutre_fond écrites puis restaurées, clés `ext_scnr*` ABSENTES.

Nécessite un affichage. Exécution : python bancs/_test_couleurs_jalon22.py
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
import tempfile
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"              # brutes mono dans ce test
import avastack.external.live as gxl
import avastack.ui.app as ui
from avastack.processing import display as dp
from avastack.processing import couleurs as coul
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def lab_l(img):
    """L* CIE (Lab D65, échelle 0-100) : le canal que la PRÉSERVATION DE LA
    LUMINOSITÉ (v2.48.0, jalon 85) doit rendre au pixel corrigé."""
    return cv2.cvtColor(np.clip(img, 0.0, 1.0).astype(np.float32),
                        cv2.COLOR_RGB2LAB)[..., 0]


# Image COULEUR synthétique : fond vert excédentaire (bruit vert typique),
# quelques étoiles BLANCHES (canaux équilibrés — doivent rester intactes)
# et une tache MAGENTA (R et B > G).
rng = np.random.default_rng(7)
H, W = 120, 160


def image_test():
    img = np.empty((H, W, 3), np.float32)
    img[..., 0] = 0.08                       # R : fond
    img[..., 1] = 0.16 + rng.normal(0, 0.01, (H, W)).astype(np.float32)  # G
    img[..., 2] = 0.08                       # B : fond
    for (x, y) in ((40, 30), (100, 80)):     # étoiles blanches
        img[y - 1:y + 2, x - 1:x + 2] = 0.9
    img[60:70, 20:30] = (0.25, 0.05, 0.25)   # tache magenta
    return img


# ==================================== [1] module couleurs
print("[1] module couleurs : SCNR + démagenta")
src = image_test()
src0 = src.copy()                     # référence pour le test de non-mutation
out = coul.scnr(src)
verifie(out.shape == src.shape and out.dtype == np.float32
        and np.isfinite(out).all(),
        "scnr : (H, W, 3) float32 finie")
verifie(np.all(out[..., 1] <= 0.5 * (out[..., 0] + out[..., 2]) + 1e-6),
        "scnr : plus AUCUN pixel avec G > (R+B)/2 (moyenne neutre)")
# v2.48.0 (jalon 85) : `scnr` préserve désormais la L* CIE PAR DÉFAUT (comme
# Siril / PixInsight) — R et B BOUGENT donc sur les pixels corrigés, et c'est
# le but : l'objet n'est plus éteint. La formule HISTORIQUE des jalons 22/23
# reste disponible telle quelle à `preserve_luminance=False` ; elle seule
# laisse R et B intacts.
hist = coul.scnr(src, preserve_luminance=False)
verifie(float(np.abs(src[..., 0] - hist[..., 0]).max()) < 1e-7
        and float(np.abs(src[..., 2] - hist[..., 2]).max()) < 1e-7,
        "scnr(preserve_luminance=False) : R et B inchangés (seul le vert "
        "excédentaire est ramené) — recette des jalons 22/23")
# Au DÉFAUT, la L* des pixels corrigés est rendue (mesuré ~0,2 unité de Lab
# ici, contre ~14 unités d'écart quand elle n'est pas rendue : TÉMOIN mesuré
# sur le même masque, pour que l'assertion prouve qu'elle discrimine).
modifies = np.abs(src - out).max(axis=2) > 1e-6
dl = float(np.abs(lab_l(out)[modifies] - lab_l(src)[modifies]).max())
dl_sans = float(np.abs(lab_l(hist)[modifies] - lab_l(src)[modifies]).max())
verifie(bool(np.any(modifies)) and dl < 0.5 < dl_sans,
        f"scnr(défaut) : L* des pixels corrigés RENDUE (écart max {dl:.4f} "
        f"unité de Lab, contre {dl_sans:.2f} sans préservation)")
# …et les pixels NON corrigés ressortent AU BIT près (aucun aller-retour Lab
# sur eux) : c'est la non-régression RGB que le jalon 85 a verrouillée.
verifie(np.array_equal(out[~modifies], src[~modifies]),
        "scnr : les pixels non corrigés sont intacts AU BIT près")
verifie(np.allclose(src[29:32, 39:42, 1], out[29:32, 39:42, 1]),
        "scnr : les étoiles blanches (G ≤ (R+B)/2) sont INTACTES")
verifie(np.array_equal(src, src0) and not np.array_equal(src, out),
        "scnr : image d'entrée jamais modifiée")
dm = coul.demagenta(src)
tache_av = float(np.mean(src[60:70, 20:30, 0] - src[60:70, 20:30, 1]))
tache_ap = float(np.mean(dm[60:70, 20:30, 0] - dm[60:70, 20:30, 1]))
verifie(tache_ap < 0.5 * tache_av,
        f"démagenta : la tache magenta est neutralisée "
        f"(R−G {tache_av:.3f} → {tache_ap:.3f})")
modif_dm = np.abs(src - dm).max(axis=2) > 1e-6
dl_dm = float(np.abs(lab_l(dm)[modif_dm] - lab_l(src)[modif_dm]).max())
verifie(bool(np.any(modif_dm)) and dl_dm < 0.5,
        f"démagenta(défaut) : L* des pixels corrigés RENDUE (écart max "
        f"{dl_dm:.4f} unité de Lab sur {int(modif_dm.sum())} pixel(s))")
mono = rng.normal(0.1, 0.01, (H, W)).astype(np.float32)
verifie(np.array_equal(coul.scnr(mono), mono)
        and np.array_equal(coul.demagenta(mono), mono),
        "mono (H, W) : no-op (pour retirer du vert, il faut de la couleur)")
# Démagenta = négatif → scnr → positif, cohérence exacte. La préservation de
# L* s'applique au résultat FINAL (le négatif n'a pas de luminosité
# perceptuelle) : la recette exacte se vérifie donc à
# `preserve_luminance=False`, et le défaut en DIFFÈRE (c'est le contrat neuf).
dm_ref = 1.0 - coul.scnr(1.0 - src, preserve_luminance=False)
verifie(np.allclose(coul.demagenta(src, preserve_luminance=False), dm_ref),
        "démagenta(preserve_luminance=False) = négatif → SCNR → positif "
        "(recette exacte des jalons 22/23)")
verifie(not np.allclose(dm, dm_ref),
        "…et au DÉFAUT le résultat en DIFFÈRE (la L* est rendue au pixel "
        "corrigé) : les deux contrats sont bien distincts")

# --- Jalon 23 : SCNR doux borné par le bruit -------------------------------
# Image à grésillement vert seul : fond équilibré, bruit sur le vert seul.
img_grain = np.empty((H, W, 3), np.float32)
img_grain[..., 0] = 0.10
img_grain[..., 2] = 0.10
img_grain[..., 1] = 0.10 + rng.normal(0, 0.008, (H, W)).astype(np.float32)
# Recette HISTORIQUE (jalons 22/23), vérifiée à `preserve_luminance=False` :
# c'est elle qui définit « le grésillement du fond est retiré » (le canal vert
# seul est corrigé, sans compensation de lumière).
sd = coul.scnr_doux(img_grain, preserve_luminance=False)
exc_av = img_grain[..., 1] - 0.10
exc_ap = sd[..., 1] - 0.10
# Seul l'excès POSITIF (grésillement au-dessus de la moyenne neutre) est
# traité : un déficit de vert n'est jamais « corrigé ».
pos_av = exc_av[exc_av > 0]
pos_ap = exc_ap[exc_ap > 0]
# La garotte douce annule les excès ≤ 3σ (la grande majorité) ; il ne reste
# qu'une queue résiduelle fine (> 3σ, abaissée du plancher de bruit).
verifie(len(pos_ap) < 0.05 * len(pos_av),
        f"scnr_doux : le grésillement vert du fond est retiré "
        f"(pixels à excès résiduel : {len(pos_ap)}/{len(pos_av)})")
verifie(float(exc_ap.max()) < 0.8 * float(exc_av.max()),
        f"scnr_doux : plus aucun excès de vert résiduel notable "
        f"(max {exc_ap.max():.4f} < 0,8 × {exc_av.max():.4f})")
# Au DÉFAUT (préservation de L*) le grain vert est toujours réduit — la
# préservation rend de la LUMIÈRE, pas du grain — et la L* des pixels corrigés
# est rendue. Le σ du vert baisse donc moins qu'à la recette historique : c'est
# le prix, assumé, de la préservation (l'écart de L* sans préservation est
# mesuré ici comme TÉMOIN, sur le même masque).
sd_def = coul.scnr_doux(img_grain)
masque_sd = np.abs(img_grain - sd_def).max(axis=2) > 1e-6
sigma_ap = float(sd_def[..., 1].std())
dl_sd = float(np.abs(lab_l(sd_def)[masque_sd]
                     - lab_l(img_grain)[masque_sd]).max())
dl_sd_sans = float(np.abs(lab_l(sd)[masque_sd]
                         - lab_l(img_grain)[masque_sd]).max())
verifie(sigma_ap < 0.9 * float(exc_av.std()) and dl_sd < 0.5 < dl_sd_sans,
        f"scnr_doux(défaut) : grain vert réduit (σ {exc_av.std():.5f} → "
        f"{sigma_ap:.5f}) ET L* des pixels corrigés RENDUE (écart max "
        f"{dl_sd:.4f} unité de Lab, contre {dl_sd_sans:.2f} sans préservation)")
img_grain0 = img_grain.copy()
coul.scnr_doux(img_grain)
verifie(np.array_equal(img_grain, img_grain0),
        "scnr_doux : image d'entrée jamais modifiée")
# Structure préservée : un grand excès de vert uniforme (0.08 ≫ 3σ) est
# conservé, abaissé seulement du plancher de bruit.
sd2 = coul.scnr_doux(src)
exc_struct_ap = float(np.mean(sd2[..., 1] - 0.5 * (sd2[..., 0]
                                                   + sd2[..., 2])))
verifie(0.5 * 0.08 < exc_struct_ap < 1.05 * 0.08,
        f"scnr_doux : l'excès de vert STRUCTURÉ est préservé "
        f"(0.08 → {exc_struct_ap:.4f})")
mono0 = mono.copy()
verifie(np.array_equal(coul.scnr_doux(mono), mono)
        and np.array_equal(mono, mono0),
        "scnr_doux : mono (H, W) no-op, entrée intacte")

# ==================================== [2] live (DisplayProcessor)
print("[2] live : clé de réglages + process() STF/manuel + vue « traitée »")
ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
d = app.disp
k0 = d._vl_params()
d.vl_scnr = True
k1 = d._vl_params()
d.vl_scnr = False
d.vl_demagenta = True
k2 = d._vl_params()
d.vl_demagenta = False
d.vl_scnr_doux = True
k3 = d._vl_params()
d.vl_scnr_doux = False
verifie(k1 != k0 and k2 != k0 and k1 != k2 and k3 != k0 and k3 != k1,
        "vl_scnr / vl_scnr_doux / vl_demagenta font partie de la clé")

app.var_view.set("empilement")
app.var_moteur.set("STF")
app._on_moteur()                     # mode STF, rendu en MANUEL à points
d.auto = False                       # FIXES (black/white constants) : la
d.black, d.white = 0.02, 0.40        # relation G' ≤ (R'+B')/2 est alors
d.gamma, d.saturation = 1.0, 1.0     # linéaire et exacte après étirement.
# (En STF AUTO, chaque rendu recalcule les stats sur SON image : comparer
# deux rendus d'entrées différentes ne mesure pas la case testée.)
img = image_test()
d.vl_scnr = False
out_sans = d.process(img).astype(np.float32) / 255.0
d.vl_scnr = True
out_avec = d.process(img).astype(np.float32) / 255.0
d.vl_scnr = False
ecart_sans = float(np.mean(out_sans[..., 1]
                           - 0.5 * (out_sans[..., 0] + out_sans[..., 2])))
ecart_avec = float(np.mean(out_avec[..., 1]
                           - 0.5 * (out_avec[..., 0] + out_avec[..., 2])))
verifie(ecart_avec < ecart_sans,
        f"process() STF, case SCNR : dominance verte réduite "
        f"(G−(R+B)/2 : {ecart_sans:.4f} → {ecart_avec:.4f})")
# SCNR doux en STF : le grain vert seul (fond équilibré) est retiré —
# en manuel linéaire, G ≤ n avant étirement ⟹ G' ≤ (R'+B')/2 après.
g_sans = d.process(img_grain).astype(np.float32) / 255.0
d.vl_scnr_doux = True
g_avec = d.process(img_grain).astype(np.float32) / 255.0
d.vl_scnr_doux = False
ec_g_sans = float(np.mean(g_sans[..., 1]
                          - 0.5 * (g_sans[..., 0] + g_sans[..., 2])))
ec_g_avec = float(np.mean(g_avec[..., 1]
                          - 0.5 * (g_avec[..., 0] + g_avec[..., 2])))
verifie(ec_g_sans > 0 and ec_g_avec <= 1e-4,
        f"process() STF, case SCNR doux : grain vert retiré "
        f"(G−(R+B)/2 : {ec_g_sans:.4f} → {ec_g_avec:.4f})")
d.vl_scnr = False
app._on_vl_scnr()
app.var_view.set("traitée")
app._on_view()
app.var_vl_scnr.set(True)
app._on_vl_scnr()
verifie(app.disp.vl_scnr is False,
        "vue « traitée » : SCNR live DÉSACTIVÉ (l'image a déjà été traitée)")
# ==================================== [3] traitement externe
print("[3] traitement externe : plus AUCUNE case couleur dans cette chaîne "
      "(jalon 85) — le résultat reste LINÉAIRE")
app2 = ui.App(root)
app2.rejeter_flou = False


class _Val:
    """Bouchon de variable Tk : var.get() interdit hors thread principal."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app2.var_expo = _Val(0.0)
app2.var_gain = _Val(0.0)
app2.var_wb = _Val(False)
app2.var_wb_force = _Val(1.0)
app2.camera = type("Muette", (), {"name": "test",
                                  "read": lambda s: None})()
# POURQUOI la chaîne couleur n'est plus ici (décision d'Alain, jalon 85) : le
# fichier LINÉAIRE sauvegardé portait le SCNR et sortait ÉCRÊTÉ EN VERT —
# MESURÉ sur son empilement M31 : excès de vert max 5,9·10⁻⁸ pour 100 % des
# pixels, contre 1,6·10⁻¹ sur le même empilement d'origine. Le job ne
# transporte donc plus les trois cases : 8 éléments suffisent (aucun outil
# externe).
src = image_test()
src0 = src.copy()
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5)
app2._session = 0
app2._run_external(src, 3, 0)
verifie(app2.ext_state == "ok" and app2.proc_full is not None
        and app2.proc_full.shape == src.shape,
        "chaîne externe sans outil : un résultat (H, W, 3) est produit")
if app2.proc_full is not None:
    verifie(np.allclose(app2.proc_full, src, atol=1e-6),
            "résultat = entrée, au pixel près : la chaîne externe ne retire "
            "plus de vert (les cases couleur suivent l'étirement)")
    exc_av = float(np.mean(src[..., 1] - 0.5 * (src[..., 0] + src[..., 2])))
    exc_ap = float(np.mean(app2.proc_full[..., 1]
                           - 0.5 * (app2.proc_full[..., 0]
                                    + app2.proc_full[..., 2])))
    verifie(exc_av > 0.05 and abs(exc_ap - exc_av) < 1e-6,
            f"l'excès de vert TRAVERSE la chaîne intact "
            f"(G−(R+B)/2 : {exc_av:.4f} → {exc_ap:.4f}) — plus d'écrêtage en "
            f"vert du fichier linéaire")
    verifie(np.array_equal(src, src0),
            "l'image d'entrée n'est jamais modifiée par la chaîne")
# Job 12-TUPLE (format courant) tout décoché : les emplacements 9 à 12 sont la
# neutralisation du fond, le bruit chromatique, sa force et le rayon de
# référence (v2.37.1 / v2.37.4).
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                False, False, 0.5, 3.0)
app2._run_external(src, 3, 0)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full, src, atol=1e-6),
        "job 12-tuple (format courant, tout décoché) : déballage tolérant, "
        "résultat = entrée")
# Mono : no-op — résultat identique à l'entrée.
mono = np.clip(rng.normal(0.1, 0.01, (60, 80)), 0, None).astype(np.float32)
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5)
app2._run_external(mono, 2, 0)
verifie(app2.proc_full is not None
        and np.allclose(app2.proc_full, mono, atol=1e-6),
        "mono : résultat = entrée (aucune correction de couleur dans cette "
        "chaîne)")

# v2.37.1 : corrections PRÉ-ÉTIREMENT de la chaîne live dans la chaîne EXTERNE
# (demande d'Alain, 25/09/2026 : « intégrer les derniers ajouts (SPCC,
# neutralisation, bruit chroma) dans la chaîne de traitement externe »).
# v2.48.0 (jalon 85) : le job passe de 15 à 12 éléments (plus de cases couleur)
# → la neutralisation du fond est le 9e (indice 8), le bruit chromatique le
# 10e (9), sa force le 11e (10) et le rayon de référence le 12e (11).
print("[3bis] chaîne externe : neutralisation du fond + bruit chromatique "
      "(v2.37.1, indices décalés par le jalon 85)")
src_sp = image_test()
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                True, False, 0.5, 3.0)
app2._run_external(src_sp, 4, 0)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full, coul.neutraliser_fond(src_sp),
                        atol=1e-6),
        "9e élément : neutralisation du fond seule → fond égalisé")
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                False, True, 0.75, 3.0)
app2._run_external(src_sp, 4, 0)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full,
                        coul.reduire_bruit_chroma(src_sp, force=0.75),
                        atol=1e-6),
        "10e/11e éléments : bruit chromatique à la FORCE transportée (0,75)")
# Ordre de la chaîne : … → neutralisation du fond → bruit chromatique (le vert
# de l'objet n'est plus touché ICI : il l'est APRÈS l'étirement, à l'affichage).
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                True, True, 0.5, 3.0)
app2._run_external(src_sp, 5, 0)
attendu = coul.reduire_bruit_chroma(coul.neutraliser_fond(src_sp), force=0.5)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full, attendu, atol=1e-6),
        "chaîne complète : fond → chromatique (sans SCNR : il suit "
        "l'étirement)")
# Les gains de neutralisation sont ANNONCÉS dans le message final — même
# exigence d'honnêteté que « État des calculs » du live. Ici le fond de
# `image_test()` est franchement vert : la correction a lieu, donc elle se dit.
verifie("fond neutralisé" in (app2.ext_msg or ""),
        f"fond non neutre : les gains appliqués sont ANNONCÉS "
        f"(« {str(app2.ext_msg)[:70]}… »)")
# …et ils ne le sont PAS quand il n'y a rien à corriger : fond déjà neutre.
fond_neutre = np.full((60, 80, 3), 0.08, np.float32)
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                True, False, 0.5, 3.0)
app2._run_external(fond_neutre, 3, 0)
verifie("fond neutralisé" not in (app2.ext_msg or ""),
        "fond déjà neutre : les gains ne sont PAS annoncés (aucune correction "
        "inventée)")
# …et sur un ciel réellement coloré (bleu de 3 %, comme sur ses empilements
# M31), ils le sont — mesuré ici sur une image dont les DEUX bords diffèrent.
ciel_bleu = np.empty((60, 80, 3), np.float32)
ciel_bleu[..., 0] = 0.0310
ciel_bleu[..., 1] = 0.0320
ciel_bleu[..., 2] = 0.0330
ciel_bleu += rng.normal(0, 0.0005, ciel_bleu.shape).astype(np.float32)
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                True, False, 0.5, 3.0)
app2._run_external(ciel_bleu, 3, 0)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full, coul.neutraliser_fond(ciel_bleu),
                        atol=1e-6),
        "ciel bleui : le fond corrigé est bien celui de la chaîne externe")
# Mono : les deux étapes sont des no-op.
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                True, True, 1.0, 3.0)
app2._run_external(mono, 2, 0)
verifie(app2.proc_full is not None
        and np.allclose(app2.proc_full, mono, atol=1e-6),
        "mono : neutralisation et bruit chromatique sont des no-op")
# Job 11-tuple (format v2.36, trois cases couleur dont AUCUNE n'existe plus) :
# déballage tolérant — les emplacements lus sont ceux du format courant, donc
# ici tout est décoché et le résultat est l'entrée, au pixel près.
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                False, False, 0.5)
app2._run_external(src_sp, 3, 0)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full, src_sp, atol=1e-6),
        "job 11-tuple (v2.36) : déballage tolérant, rien appliqué")

# ==================================== [4] persistance
print("[4] persistance : clés explicites, restauration")
app3 = ui.App(root)
app3.var_vl_scnr.set(True)
app3.var_vl_scnr_doux.set(True)
app3.var_vl_demagenta.set(True)
app3.var_ext_chroma.set(True)          # v2.37.1 : opt-in
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
app3._sauver_config_app()
c_cfg = sauvegardes[-1]
verifie(c_cfg.get("vl_scnr") is True and c_cfg.get("vl_scnr_doux") is True
        and c_cfg.get("vl_demagenta") is True,
        "config : vl_scnr / vl_scnr_doux / vl_demagenta écrits")
verifie(c_cfg.get("ext_chroma") is True
        and c_cfg.get("ext_neutre_fond") is True,
        "config : ext_chroma (coché) et ext_neutre_fond (défaut) écrits")
# v2.48.0 (jalon 85) : les cases couleur ont QUITTÉ la chaîne externe → les clés
# ext_scnr / ext_scnr_doux / ext_demagenta ne sont plus ÉCRITES (elles ne
# décrivent plus aucun réglage).
verifie("ext_scnr" not in c_cfg and "ext_scnr_doux" not in c_cfg
        and "ext_demagenta" not in c_cfg,
        "config : ext_scnr / ext_scnr_doux / ext_demagenta ABSENTES (plus de "
        "case couleur dans la chaîne externe)")
ui.CONFIG = dict(c_cfg)
app4 = ui.App(root)
verifie(app4.var_vl_scnr.get() is True
        and app4.var_vl_scnr_doux.get() is True
        and app4.var_vl_demagenta.get() is True
        and app4.disp.vl_scnr is True,
        "config : cases couleur restaurées (disp.vl_scnr actif)")
verifie(app4.var_ext_chroma.get() is True
        and bool(app4.var_ext_neutre.get()) is True,
        "config : ext_chroma restauré, ext_neutre_fond reste coché")
# Une configuration ANTÉRIEURE qui porte encore les trois clés retirées les voit
# RETIRÉES à la sauvegarde — seule exception à la règle « ne touche pas aux
# entrées inconnues » : sinon le fichier laisserait croire à une case qui
# n'existe plus. Le réglage respecté au passage : ext_neutre_fond décoché.
sauvegardes = []
ui.CONFIG = {"ext_scnr": True, "ext_scnr_doux": True,
             "ext_demagenta": True, "ext_neutre_fond": False}
app5 = ui.App(root)
app5._sauver_config_app()
c5 = sauvegardes[-1]
verifie("ext_scnr" not in c5 and "ext_scnr_doux" not in c5
        and "ext_demagenta" not in c5,
        "config antérieure : les clés ext_scnr* sont RETIRÉES à la sauvegarde")
verifie(bool(app5.var_ext_neutre.get()) is False,
        "config : ext_neutre_fond DÉCOCHÉ par l'utilisateur est respecté")

# ==================================== [5] GraXpert : garde-fous (jalon 23b)
print("[5] GraXpert live : canal mort refusé, sortie dégénérée rejetée")
# canal_mort : SHO sans S → R vide ; composite sain → None.
verifie(coul.canal_mort(img_grain) is None,
        "canal_mort : image aux 3 canaux vivants → None")
img_sho = np.zeros((60, 80, 3), np.float32)
img_sho[..., 1] = 0.10 + 0.005 * rng.standard_normal((60, 80))
img_sho[..., 2] = 0.12 + 0.005 * rng.standard_normal((60, 80))
verifie(coul.canal_mort(img_sho) == "R",
        "canal_mort : SHO sans S (R = 0) → canal 'R' détecté")
verifie(coul.canal_mort(mono) is None, "canal_mort : mono → None")

# Outils factices : sortie NaN, sortie vide (image noire), sortie correcte.
# AUTONOMES (astropy seul, aucun import avastack) : le subprocess est lancé
# avec cwd = dossier temporaire — le package n'y est pas importable.
tmp5 = tempfile.mkdtemp(prefix="avastack_j23b_")
LIRE = "from astropy.io import fits\nimport sys\n" \
       "d = fits.getdata(sys.argv[1])\n"
FAKE_NAN = (LIRE + "import numpy as np\n"
            "fits.PrimaryHDU(np.full(d.shape, np.nan, np.float32))"
            ".writeto(sys.argv[2], overwrite=True)\n")
FAKE_ZERO = FAKE_NAN.replace("np.nan", "0.0")
FAKE_OK = (LIRE + "fits.PrimaryHDU(d).writeto(sys.argv[2], overwrite=True)\n"
           "open(sys.argv[3], 'a', encoding='utf-8').write('x\\n')\n")
p_nan, p_zero, p_ok = (os.path.join(tmp5, n) for n in
                       ("nan.py", "zero.py", "ok.py"))
for chemin, contenu in ((p_nan, FAKE_NAN), (p_zero, FAKE_ZERO),
                        (p_ok, FAKE_OK)):
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
img3 = image_test()
out, err = gxl.appliquer(img3, f'"{sys.executable}" "{p_nan}" '
                               f'"{{input}}" "{{output}}"')
verifie(err != "" and "non finis" in err and np.array_equal(out, img3),
        f"appliquer : sortie NaN → repli + message (« {err} »)")
out, err = gxl.appliquer(img3, f'"{sys.executable}" "{p_zero}" '
                               f'"{{input}}" "{{output}}"')
verifie(err != "" and "vide" in err and np.array_equal(out, img3),
        f"appliquer : sortie vide (image noire) → repli + message "
        f"(« {err} »)")

# Worker VeraLux : image à canal mort → l'outil n'est JAMAIS appelé,
# l'erreur est signalée, la chaîne produit quand même un résultat.
compteur = os.path.join(tmp5, "compteur.txt")
open(compteur, "w").close()
d2 = dp.DisplayProcessor()
d2.stretch = "veralux"
d2.vl_mode_res = vl.MODE_LOG_D
d2.vl_log_d = 2.0
d2.vl_profil = vl.PROFIL_PAR_DEFAUT
d2.vl_graxpert = True
d2.vl_graxpert_cmd = (f'"{sys.executable}" "{p_ok}" "{{input}}" '
                      f'"{{output}}" "{compteur}"')
appels = {"n": 0}
_appeler = gxl.appliquer


def _compter(*a, **k):
    appels["n"] += 1
    return _appeler(*a, **k)


gxl.appliquer = _compter


def resoudre(d, img_):
    d.process(img_)
    t0 = time.time()
    while (d._vl_pending or d._vl_job is not None) \
            and time.time() - t0 < 60:
        time.sleep(0.01)
    d.process(img_)
    return d._vl_result is not None


try:
    verifie(resoudre(d2, img_sho), "résolution terminée (canal mort)")
    verifie(appels["n"] == 0,
            "canal mort : GraXpert JAMAIS appelé (pas de sortie dégénérée)")
    verifie("canal R vide" in d2.vl_error,
            f"erreur claire signalée (« {d2.vl_error} »)")
    verifie(d2._vl_result is not None
            and np.isfinite(d2._vl_result[1]).all(),
            "la chaîne produit un résultat FINI (image visible, pas de noir)")
    # Contrôle : une image Saine passe par l'outil normalement (un NOUVEL
    # empilement est signalé, comme le fait le worker réel).
    img_saine = image_test()[:60, :80]
    d2.notify_new_stack()
    verifie(resoudre(d2, img_saine) and appels["n"] == 1
            and d2.vl_error == "",
            "image saine : GraXpert appelé normalement (une fois)")
finally:
    gxl.appliquer = _appeler
    import shutil
    shutil.rmtree(tmp5, ignore_errors=True)

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
