# -*- coding: utf-8 -*-
"""Test du jalon 22/23 — SCNR (retrait du vert), SCNR doux (bruit seul) et
démagenta.

Décision d'Alain (19/09/2026) : appliqués APRÈS la composition (sur
l'image COULEUR du composite) et JUSTE AVANT l'étirement, en LIVE et en
TRAITEMENT EXTERNE, chacun derrière sa case à cocher. Vérifie :

  [1] module couleurs : SCNR « moyenne neutre » (G = min(G, (R+B)/2)),
      démagenta (négatif → SCNR → positif), SCNR doux (jalon 23 : retire
      le grésillement vert ≤ 3σ, préserve la structure — pensé pour les
      palettes narrowband où le vert est de la DONNÉE), mono no-op,
      entrée intacte ;
  [2] live : les cases font partie de la clé des réglages VeraLux ; en
      STF/manuel, process() applique le retrait (dominance verte réduite) ;
      vue « traitée » → désactivé ;
  [3] traitement externe : les cases 4/5/6 (job 11-tuple) appliquent
      SCNR → SCNR doux → démagenta EN FIN de chaîne — sur (H, W, 3),
      no-op sur (H, W) mono ;
  [4] persistance : clés vl_scnr / vl_scnr_doux / vl_demagenta / ext_scnr /
      ext_scnr_doux / ext_demagenta écrites puis restaurées.

Nécessite un affichage. Exécution : python _test_couleurs_jalon22.py
"""
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
verifie(float(np.abs(src[..., 0] - out[..., 0]).max()) < 1e-7
        and float(np.abs(src[..., 2] - out[..., 2]).max()) < 1e-7,
        "scnr : R et B inchangés (seul le vert excédentaire est ramené)")
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
mono = rng.normal(0.1, 0.01, (H, W)).astype(np.float32)
verifie(np.array_equal(coul.scnr(mono), mono)
        and np.array_equal(coul.demagenta(mono), mono),
        "mono (H, W) : no-op (pour retirer du vert, il faut de la couleur)")
# Démagenta = négatif → scnr → positif, cohérence exacte :
dm_ref = 1.0 - coul.scnr(1.0 - src)
verifie(np.allclose(dm, dm_ref),
        "démagenta = négatif → SCNR → positif (recette exacte)")

# --- Jalon 23 : SCNR doux borné par le bruit -------------------------------
# Image à grésillement vert seul : fond équilibré, bruit sur le vert seul.
img_grain = np.empty((H, W, 3), np.float32)
img_grain[..., 0] = 0.10
img_grain[..., 2] = 0.10
img_grain[..., 1] = 0.10 + rng.normal(0, 0.008, (H, W)).astype(np.float32)
sd = coul.scnr_doux(img_grain)
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
print("[3] traitement externe : cases 4/5 en fin de chaîne")
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
# Job 11-TUPLE (jalon 22/23) : AUCUN outil externe (tout à False), uniquement
# les cases couleur — la chaîne doit tout de même produire un résultat
# transformé. Ordre d'application : SCNR → SCNR doux → démagenta.
src = image_test()
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                True, False, True)
app2._session = 0
app2._run_external(src, 3, 0)
verifie(app2.ext_state == "ok" and app2.proc_full is not None
        and app2.proc_full.shape == src.shape,
        "SCNR + démagenta seuls : la chaîne produit un résultat (H, W, 3)")
if app2.proc_full is not None:
    verifie(np.allclose(app2.proc_full, coul.demagenta(coul.scnr(src)),
                        atol=1e-6),
            "résultat = démagenta(SCNR(image)) (ordre de la chaîne)")
# SCNR doux seul (jalon 23) :
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                False, True, False)
app2._run_external(src, 3, 0)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full, coul.scnr_doux(src), atol=1e-6),
        "SCNR doux seul : résultat = scnr_doux(image)")
# Mono : no-op — résultat identique à l'entrée.
mono = np.clip(rng.normal(0.1, 0.01, (60, 80)), 0, None).astype(np.float32)
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5,
                True, False, False)
app2._run_external(mono, 2, 0)
verifie(app2.proc_full is not None
        and np.allclose(app2.proc_full, mono, atol=1e-6),
        "mono : SCNR est un no-op (résultat = entrée)")
# Job 8-TUPLE (jalon 7/14, ancien format) : déballage tolérant, rien appliqué.
app2.ext_job = (False, "", False, "", False, "", "nlm", 0.5)
app2._run_external(src, 3, 0)
verifie(app2.ext_state == "ok"
        and np.allclose(app2.proc_full, src, atol=1e-6),
        "job 8-tuple (ancien format) : déballage tolérant, aucun retrait")

# ==================================== [4] persistance
print("[4] persistance : clés explicites, restauration")
app3 = ui.App(root)
app3.var_vl_scnr.set(True)
app3.var_vl_scnr_doux.set(True)
app3.var_vl_demagenta.set(True)
app3.var_ext_scnr.set(True)
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
app3._sauver_config_app()
c_cfg = sauvegardes[-1]
verifie(c_cfg.get("vl_scnr") is True and c_cfg.get("vl_scnr_doux") is True
        and c_cfg.get("vl_demagenta") is True
        and c_cfg.get("ext_scnr") is True
        and c_cfg.get("ext_scnr_doux") is False
        and c_cfg.get("ext_demagenta") is False,
        "config : vl_scnr / vl_scnr_doux / vl_demagenta / ext_scnr / "
        "ext_scnr_doux / ext_demagenta écrits")
ui.CONFIG = dict(c_cfg)
app4 = ui.App(root)
verifie(app4.var_vl_scnr.get() is True
        and app4.var_vl_scnr_doux.get() is True
        and app4.var_vl_demagenta.get() is True
        and app4.var_ext_scnr.get() is True
        and app4.var_ext_scnr_doux.get() is False
        and app4.var_ext_demagenta.get() is False
        and app4.disp.vl_scnr is True,
        "config : cases restaurées (disp.vl_scnr actif)")

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
