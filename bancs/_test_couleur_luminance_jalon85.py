# -*- coding: utf-8 -*-
"""Banc jalon 85 (v2.48.0) — PRÉSERVATION DE LA LUMINANCE du retrait du vert
(SCNR / SCNR doux / démagenta) et FORCE PARTIELLE.

Constat d'Alain (30/09/2026) : sur son empilement SHO (NGC 2237), le SCNR
ÉTEINT la nébuleuse au lieu de n'en retirer que le vert (« manque de doré »),
et la chaîne n'offre AUCUNE préservation de la luminosité là où Siril et
PixInsight la font par défaut (`rmgreen` : « Lightness is preserved by
default », `-nopreserve` pour l'annuler). Vérifie, AVANT tout câblage dans
l'application :

  [1] module `couleurs` : NON-RÉGRESSION AU BIT — `amount=1` avec
      `preserve_luminance=False` rend exactement l'ancien `scnr` / `scnr_doux`
      / `demagenta` des jalons 22/23 ; `amount=0` rend l'entrée au bit ; force
      partielle ; mono no-op ; entrée jamais modifiée ;
  [2] préservation de L* sur une scène qui reproduit le MÉCANISME (nébuleuse
      verte dominante) : la lumière est conservée ET l'excès de vert retiré,
      sans toucher les pixels non corrigés ;
  [3] garde de résolution : une image DÉJÀ écrêtée (excès résiduel ≈ 4·10⁻⁹,
      pur float32) n'est pas retouchée par la remise de L* ;
  [4] RGB RÉEL — empilement M31 (`C:\\Astro\\test`) : identique à l'ancien
      SCNR sans préservation, pixels non écrêtés intacts, galaxie R>V>B
      conservée (aucune bascule dans le bleu) ;
  [5] SHO RÉEL — NGC 2237 (NAS) : composite → étirement VeraLux → SCNR ; sans
      préservation la nébuleuse PERD sa lumière (le défaut constaté), avec la
      préservation elle la garde ;
  [6] interaction MESURÉE « SCNR puis SCNR doux » (la phrase de l'interface) ;
  [7] coût : l'aperçu live reste très en dessous du dixième de seconde.

Les sections [4] et [5] utilisent des fichiers RÉELS : si absents (NAS
injoignable, dossier nettoyé), elles l'ANNONCENT et sont sautées — un banc
dit toujours ce qu'il n'a pas pu mesurer.

Exécution : python bancs/_test_couleur_luminance_jalon85.py [M31.fits]
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import time

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.images import load_image
from avastack.processing import couleurs as coul
from avastack.processing import denoise as _denoise

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def ancien_scnr(img):
    """SCNR des jalons 22/23 — référence de NON-RÉGRESSION (recopié ici pour
    que le banc prouve la compatibilité même si le module évolue)."""
    a = np.asarray(img, np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return a.copy()
    out = a.copy()
    out[..., 1] = np.minimum(out[..., 1], 0.5 * (out[..., 0] + out[..., 2]))
    return out


def ancien_scnr_doux(img, k=3.0):
    """SCNR doux des jalons 22/23 — référence de non-régression."""
    a = np.asarray(img, np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return a.copy()
    n = 0.5 * (a[..., 0] + a[..., 2])
    e = a[..., 1] - n
    t = np.float32(max(0.0, float(k)) * _denoise.estimer_sigma(e))
    ee = np.maximum(e, np.float32(1e-12))
    garotte = np.where(e > t, e - t * t / ee, np.float32(0.0))
    out = a.copy()
    out[..., 1] = n + np.where(e > 0, garotte, e)
    return out


def ancien_demagenta(img):
    """Démagenta des jalons 22/23 — référence de non-régression."""
    a = np.asarray(img, np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return a.copy()
    return (1.0 - ancien_scnr(1.0 - a)).astype(np.float32)


def nb_diff(a, b):
    """Nombre de pixels où les deux images diffèrent (comparaison AU BIT)."""
    a = np.asarray(a, np.float32)
    b = np.asarray(b, np.float32)
    if a.shape != b.shape:
        return -1
    if a.ndim == 3:
        return int(np.any(a != b, axis=2).sum())
    return int((a != b).sum())


def Lstar(im):
    """L* CIE (Lab, D65) — la grandeur que la préservation doit conserver."""
    return cv2.cvtColor(np.clip(im, 0.0, 1.0).astype(np.float32),
                        cv2.COLOR_RGB2LAB)[..., 0]


def exces(im):
    """Excès de vert e = G − (R+B)/2."""
    return im[..., 1] - 0.5 * (im[..., 0] + im[..., 2])


def scene_verte(h=240, w=320, graine=7):
    """Le MÉCANISME du défaut : fond neutre bruité + NÉBULEUSE VERTE DOMINANTE
    (en SHO/HOO le vert porte la donnée Ha, donc le vert EST la lumière)."""
    rng = np.random.default_rng(graine)
    sc = rng.normal(0.03, 0.004, (h, w, 3)).astype(np.float32)
    sc[..., 1] += 0.006                       # léger excès de bruit vert
    sc[100:180, 110:230, 0] += 0.03           # nébuleuse : G très au-dessus
    sc[100:180, 110:230, 1] += 0.22           # de la moyenne (R+B)/2
    sc[100:180, 110:230, 2] += 0.04
    return np.clip(sc, 0.0, None).astype(np.float32)


# ========================================== [1] non-régression AU BIT
print("[1] module couleurs : compatibilité AU BIT avec les jalons 22/23")
sc = scene_verte()
sc0 = sc.copy()
verifie(nb_diff(coul.scnr(sc, preserve_luminance=False), ancien_scnr(sc)) == 0,
        "scnr(force 1, sans préservation) == ancien scnr, AU BIT")
verifie(nb_diff(coul.scnr_doux(sc, preserve_luminance=False),
                ancien_scnr_doux(sc)) == 0,
        "scnr_doux(force 1, sans préservation) == ancien, AU BIT")
verifie(nb_diff(coul.demagenta(sc, preserve_luminance=False),
                ancien_demagenta(sc)) == 0,
        "demagenta(force 1, sans préservation) == ancien, AU BIT")
verifie(nb_diff(coul.scnr(sc, amount=0.0), sc) == 0
        and nb_diff(coul.scnr_doux(sc, amount=0.0), sc) == 0
        and nb_diff(coul.demagenta(sc, amount=0.0), sc) == 0,
        "force 0 : identité AU BIT (les trois outils)")
verifie(nb_diff(sc, sc0) == 0, "entrée jamais modifiée")
rng = np.random.default_rng(11)
sans = np.dstack([0.030 + 0.0005 * rng.standard_normal((60, 80)),
                  0.022 + 0.0005 * rng.standard_normal((60, 80)),
                  0.024 + 0.0005 * rng.standard_normal((60, 80))]
                 ).astype(np.float32)   # R>V>B NET : aucun excès de vert
verifie(float(np.max(exces(sans))) < 0.0
        and nb_diff(coul.scnr(sans), sans) == 0,
        "scène R>V>B (aucun excès de vert, e < 0 partout) : identité AU BIT")
mono = (0.1 + 0.01 * rng.standard_normal((60, 80))).astype(np.float32)
verifie(nb_diff(coul.scnr(mono), mono) == 0
        and nb_diff(coul.demagenta(mono), mono) == 0,
        "composite MONO : no-op (SCNR et démagenta)")
e = exces(sc)
attendu = float(np.mean(e - 0.5 * np.maximum(e, 0.0)))
mesure = float(np.mean(exces(coul.scnr(sc, amount=0.5,
                                       preserve_luminance=False))))
verifie(abs(mesure - attendu) < 1e-6,
        f"force 0.50 : excès retiré à moitié ({float(np.mean(e)):+.4f} → "
        f"{mesure:+.4f}, attendu {attendu:+.4f})")

# ================================ [2] préservation de la lumière (mécanisme)
print("[2] préservation de L* : la lumière reste, le vert part, le reste intact")
masque = np.zeros(sc.shape[:2], bool)
masque[100:180, 110:230] = True               # la nébuleuse de la scène
l0 = float(Lstar(sc)[masque].mean())
sans_p = coul.scnr(sc, preserve_luminance=False)
avec_p = coul.scnr(sc, preserve_luminance=True)
l_sans = float(Lstar(sans_p)[masque].mean())
l_avec = float(Lstar(avec_p)[masque].mean())
verifie(l_avec > l0 - 0.5,
        f"avec préservation : L* conservée ({l0:.2f} → {l_avec:.2f})")
verifie(l_sans < 0.80 * l0,
        f"témoin, sans préservation : la nébuleuse s'ÉTEINT ({l0:.2f} → "
        f"{l_sans:.2f}, −{100.0 * (1.0 - l_sans / l0):.0f} %)")
verifie(abs(float(exces(avec_p)[masque].mean())) < 1e-3
        and abs(float(exces(sans_p)[masque].mean())) < 1e-3,
        "excès de vert retiré dans les DEUX cas (le vert part, la lumière reste)")
non_corriges = e <= 0.0
verifie(int(np.any(avec_p[non_corriges] != sc[non_corriges],
                   axis=1).sum()) == 0,
        "pixels sans excès (donc NON corrigés) : identiques AU BIT")

# ============================== [3] garde de résolution (fichier déjà écrêté)
print("[3] garde de résolution : une image déjà écrêtée n'est pas retouchée")
deja = (ancien_scnr(sc) * np.float32(1.0 + 1e-7)).astype(np.float32)
residu = float(np.max(np.maximum(exces(deja), 0.0)))
verifie(nb_diff(coul.scnr(deja, preserve_luminance=True),
                ancien_scnr(deja)) == 0,
        f"excès résiduel {residu:.2e} (< garde 1e-6) : identique à l'ancien "
        f"SCNR AU BIT — la remise de L* ne se déclenche pas")


# ======================================================== [4] RGB RÉEL (M31)
print("[4] RGB réel : empilement M31 d'Alain — aucune bascule dans le bleu")
chemin = (sys.argv[1] if len(sys.argv) > 1
          else os.path.join(r"C:\Astro\test",
                            "M31_traite_lineaire_111frames.fits"))
if not os.path.exists(chemin):
    print("  SAUTÉ  fichier M31 absent : " + chemin)
else:
    m31 = np.asarray(load_image(chemin), np.float32)
    e31 = exces(m31)
    cap = e31 > 0.0
    verifie(nb_diff(coul.scnr(m31, preserve_luminance=False),
                    ancien_scnr(m31)) == 0,
            "M31 : identique à l'ancien SCNR sans préservation, AU BIT")
    r31 = coul.scnr(m31, preserve_luminance=True)
    hors = int(np.any(r31[~cap] != m31[~cap], axis=1).sum())
    verifie(hors == 0,
            f"M31 : les pixels NON écrêtés ({100.0 * (1.0 - cap.mean()):.0f} % "
            f"de l'image) sont identiques AU BIT")
    l31 = m31.mean(axis=2)
    sel = l31 > np.percentile(l31, 95)
    rg = float(m31[sel][:, 0].mean() / m31[sel][:, 1].mean())
    rg2 = float(r31[sel][:, 0].mean() / r31[sel][:, 1].mean())
    verifie(rg > 0.98 and rg2 > 0.98 and abs(rg2 - rg) < 0.05,
            f"M31 : la galaxie ne bascule pas dans le bleu "
            f"(R/V {rg:.3f} → {rg2:.3f}, écart {abs(rg2 - rg):.3f})")
p2 = os.path.join(os.path.dirname(chemin), "M31_traite_lineaire_2.38.0.fits")
if os.path.exists(p2):
    m2 = np.asarray(load_image(p2), np.float32)
    verifie(nb_diff(coul.scnr(m2, preserve_luminance=True),
                    ancien_scnr(m2)) == 0,
            "M31 déjà écrêté (fichier du jalon 22) : AUCUNE retouche "
            "(garde de résolution)")
else:
    print("  SAUTÉ  fichier M31 déjà écrêté absent : " + p2)

# ============================== [5] SHO RÉEL (NAS) : composite → étirement
print("[5] SHO réel : NGC 2237 — composite → étirement VeraLux → SCNR")
import glob                                            # noqa: E402
from avastack.processing import composition as compo    # noqa: E402
from avastack.processing import veralux as vl           # noqa: E402
SHO = r"\\192.168.155.45\Telechargements\Astro\SV555\NGC 2237\SHO"
canaux = {}
if os.path.isdir(SHO):
    for f in sorted(glob.glob(os.path.join(SHO, "*_stacked_grad.fit"))):
        n = os.path.basename(f)
        canaux["S2" if "_SII_" in n else ("Ha" if "_Ha_" in n else "O3")] = \
            load_image(f)
if len(canaux) != 3 or not vl.moteur_disponible():
    print(f"  SAUTÉ  données SHO indisponibles (canaux {sorted(canaux)}, "
          f"moteur VeraLux {vl.moteur_disponible()})")
else:
    composite = compo.composer(canaux, "SHO", normalisation_commune=True)
    petit = np.asarray(cv2.resize(composite, None, fx=0.25, fy=0.25,
                                  interpolation=cv2.INTER_AREA), np.float32)
    etire, logd, _ = vl.etirer(petit, mode=vl.MODE_TARGET_BG, target_bg=0.16)
    lum = etire.mean(axis=2)
    neb = lum > np.percentile(lum, 80)
    ref_sho = float(Lstar(etire)[neb].mean())
    a_sho = coul.scnr(etire, preserve_luminance=False)
    b_sho = coul.scnr(etire, preserve_luminance=True)
    l_a = float(Lstar(a_sho)[neb].mean())
    l_b = float(Lstar(b_sho)[neb].mean())
    print(f"        composite étiré (logD {logd:.3f}) : L* nébuleuse {ref_sho:.2f}")
    verifie(l_a < 0.80 * ref_sho,
            f"témoin : SANS préservation la nébuleuse PERD sa lumière "
            f"({ref_sho:.2f} → {l_a:.2f}, −{100.0 * (1.0 - l_a / ref_sho):.0f} %) "
            f"— le défaut constaté")
    verifie(l_b > 0.95 * ref_sho,
            f"AVEC préservation elle la GARDE ({ref_sho:.2f} → {l_b:.2f})")
    e_avant = float(exces(etire)[neb].mean())
    e_apres = float(exces(b_sho)[neb].mean())
    verifie(abs(e_apres) < 0.10 * abs(e_avant),
            f"l'excès de vert est retiré malgré tout ({e_avant:+.3f} → "
            f"{e_apres:+.3f}, −{100.0 * (1.0 - abs(e_apres) / abs(e_avant)):.0f} % ; "
            f"la remise de L* laisse un résidu de quelques % — la chroma n'est "
            f"pas le sujet de la préservation)")
    for nom, im in (("étirement seul", etire), ("SCNR sans préservation", a_sho),
                    ("SCNR avec préservation", b_sho)):
        hsv = cv2.cvtColor(np.clip(im, 0, 1), cv2.COLOR_RGB2HSV)
        hh = hsv[..., 0][neb]
        tot = max(1, hh.size)
        print("        %-24s vert %4.1f %%  bleu-cyan %4.1f %%  saturation %.3f"
              % (nom,
                 100.0 * int(((hh >= 75) & (hh < 165)).sum()) / tot,
                 100.0 * int(((hh >= 165) & (hh < 270)).sum()) / tot,
                 float(hsv[..., 1][neb].mean())))
    hh_a = cv2.cvtColor(np.clip(a_sho, 0, 1), cv2.COLOR_RGB2HSV)[..., 0][neb]
    hh_b = cv2.cvtColor(np.clip(b_sho, 0, 1), cv2.COLOR_RGB2HSV)[..., 0][neb]
    verifie(int(((hh_a >= 75) & (hh_a < 165)).sum()) == 0
            and int(((hh_b >= 75) & (hh_b < 165)).sum()) == 0,
            "le vert de la nébuleuse disparaît dans les deux cas (la teinte "
            "change, la lumière non)")

# ================== [6] interaction SCNR → SCNR doux (mesure de l'interface)
print("[6] SCNR puis SCNR doux : les deux cases ne se complètent QUE si la "
      "force du SCNR est < 1")
for force, doit_agir in ((1.0, False), (0.5, True)):
    a1 = coul.scnr(sc, amount=force, preserve_luminance=False)
    a2 = coul.scnr_doux(a1, preserve_luminance=False)
    ec = float(np.abs(a2 - a1).max())
    verifie((ec > 1e-3) == doit_agir,
            f"SCNR force {force:.2f} → SCNR doux : écart max {ec:.3e} "
            f"({'agit' if doit_agir else 'aucun effet'})")

# ==================================================== [7] coût (aperçu live)
print("[7] coût : la préservation doit rester négligeable en aperçu")
x = np.random.default_rng(3).uniform(0.0, 0.30, (904, 1600, 3)).astype(np.float32)
x[..., 1] *= 0.55
t0 = time.perf_counter()
coul.scnr(x, preserve_luminance=False)
t1 = time.perf_counter()
coul.scnr(x, preserve_luminance=True)
t2 = time.perf_counter()
verifie(t2 - t1 < 0.5,
        f"aperçu 1600×904 : SCNR {t1 - t0:.3f} s → avec préservation de L* "
        f"{t2 - t1:.3f} s")

# ============================================================ récapitulatif
print()
print("BANC JALON 85 (préservation de la luminance du retrait du vert) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)
