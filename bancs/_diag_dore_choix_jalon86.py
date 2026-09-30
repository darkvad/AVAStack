# -*- coding: utf-8 -*-
r"""CHOISIR LE RENDU SHO (doré) — planche de COMPARAISON en IMAGES.

Contexte : après le jalon 86 (boost du rouge masqué), Alain a regardé l'écran et
a répondu « bof, pas satisfait par le boost du rouge, je préférais ma version
avec linear fit offset + gain ». Les statistiques du diagnostic précédent
(_diag_couleur_dore_jalon85.py) donnaient raison au boost — mais c'est LUI qui
regarde l'écran, et deux rendus qui portent le MÊME R:G sur l'objet ne se
ressemblent pas forcément (répartition de la teinte, saturation, fond).

Ce diagnostic ne tranche donc RIEN : il FABRIQUE les images. Il rejoue la
chaîne RÉELLE de l'application (chaque étage appelé est la fonction de
production, pas une copie) sur les trois moyennes de bandes de la session live
(cache local de _diag_couleur_dore_jalon85.py) et écrit une planche + un PNG
par variante, plus le tableau de mesures de chacune.

Variantes :
  [A] TON 22h09        Linear Fit « gain + offset », SCNR DÉCOCHÉ
  [B] ÉCRAN ACTUEL     sans fit, SCNR 0,55, démagenta, boost 1,60
  [C] boost 3,00       le doré que le jalon 86 a mesuré (même R:G que le fit)
  [D] boost 3,00 sans SCNR   (le SCNR et le boost s'additionnent-ils ?)
  [E] boost 3,00 CONCENTRÉ   poids² (doré sur les crêtes, vert ailleurs)
  [F] fit + boost 3,00
  [G] fit + boost 3,00 + SCNR 0,35

Usage : python bancs/_diag_dore_choix_jalon86.py [--dossier-src RACINE]
        [--target-bg 0.16] [--sans-images]
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import argparse
import os
import sys
import tempfile

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

# Les aides de mesure (teintes, masques, chargement des brutes + cache local,
# aperçu, étirement VeraLux) viennent du diagnostic du jalon 85 : recopiées,
# elles finiraient par diverger.
import _diag_couleur_dore_jalon85 as dore

from avastack.processing import couleurs as coul
from avastack.processing import composition as compo
from avastack.processing import stacking as _stacking
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOSSIER_IMAGES = os.path.join(tempfile.gettempdir(), "avastack_diag_dore",
                              "comparaison")


# -------------------------------------------------------------- la chaîne réelle
def chaine(composite, fit=None, scnr=0.0, demag=1.0, boost=1.0,
           preserve=True, chroma=0.6, cible=0.16, poids_boost=None):
    """La chaîne de PRODUCTION, dans l'ORDRE RÉEL du solveur live (relevé dans
    `display.py`, jalons 54 → 86) :

        Linear Fit (corrections_couleur, tramé par le stacker) →
        neutralisation du fond → chroma → VeraLux →
        SCNR → SCNR doux → démagenta → boost du rouge

    Le FIT EST AVANT LA NEUTRALISATION — c'est ce que fait l'application
    (`display.py:833` pour le fit, `display.py:938-941` pour la neutralisation) :
    le fit colore le fond, la neutralisation le ramène ensuite. L'inverse
    (neutralisation puis fit) colorait le fond en bleu : ce n'est PAS ce que
    l'écran d'Alain montrait.

    `fit` : None (décoché), « offset » ou « gain_offset ».
    `poids_boost` : None (poids linéaire, la production) ou une puissance > 1
    (variante « concentrée » : le doré ne va qu'aux pixels brillants).
    → (image [0..1], gains de neutralisation, diag du fit).
    """
    x = np.asarray(composite, np.float32)
    diag = None
    if fit is not None:
        x, diag = _stacking.aligner_canaux(np.ascontiguousarray(x), mode=fit)
    gains = coul.gains_fond(x)
    if gains is not None and not np.allclose(gains, 1.0, atol=1e-4):
        x = coul.neutraliser_fond(x)
    else:
        gains = None
    if chroma > 0:
        rayon = coul.rayon_chroma_apercu(x.shape[1] / 3856.0, rayon=3.0)
        x = coul.reduire_bruit_chroma(x, force=chroma, rayon=rayon)
    x, _logd, _ = vl.etirer(x, mode=vl.MODE_TARGET_BG, target_bg=cible)
    if scnr > 0:
        x = coul.scnr(x, amount=scnr, preserve_luminance=preserve)
    if demag > 0:
        x = coul.demagenta(x, amount=demag, preserve_luminance=preserve)
    if boost > 1.0:
        x = (coul.boost_rouge(x, force=boost, preserve_luminance=preserve)
             if poids_boost is None
             else boost_concentre(x, boost, poids_boost, preserve))
    return x, gains, diag


def boost_concentre(im, force, puissance=2.0, preserve=True, bas=40.0,
                    haut=97.0):
    """VARIANTE À L'ESSAI (pas dans l'application) : le même boost que le jalon
    86, mais le poids est ÉLEVÉ à une puissance — au lieu d'une rampe linéaire
    de luminance (qui dore toute la nébuleuse, y compris ses voiles), le doré se
    concentre sur les pixels brillants et les zones faibles gardent leur vert."""
    a = np.asarray(im, np.float32)
    if a.ndim != 3 or a.shape[-1] != 3 or float(force) <= 1.0:
        return a.copy()
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    b, h = np.percentile(lum, (bas, haut))
    poids = np.clip((lum - b) / max(1e-6, float(h - b)), 0.0, 1.0)
    poids = poids ** float(puissance)
    out = a.copy()
    out[..., 0] = np.clip(a[..., 0] * (1.0 + (float(force) - 1.0) * poids),
                          0.0, 1.0)
    if preserve:
        out = coul._restaurer_luminance(
            a, out, np.abs(out - a).max(axis=2) > coul.SEUIL_REMISE_LUMINANCE)
    return out


def enregistrer(nom, img, largeur=1600):
    """Écrit un PNG (8 bits) dans le dossier de comparaison. → chemin."""
    os.makedirs(DOSSIER_IMAGES, exist_ok=True)
    u8 = (np.clip(np.asarray(img, np.float32), 0.0, 1.0) * 255.0
          + 0.5).astype(np.uint8)[..., ::-1]
    if u8.shape[1] > largeur:
        f = largeur / float(u8.shape[1])
        u8 = cv2.resize(u8, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    chemin = os.path.join(DOSSIER_IMAGES, nom + ".png")
    cv2.imwrite(chemin, u8)
    return chemin



def planche(paires, colonnes=2, largeur=760):
    """Planche contact : chaque variante sous son étiquette (ASCII : cv2 ne sait
    pas écrire les accents)."""
    tuiles = []
    for etiquette, img in paires:
        u8 = (np.clip(np.asarray(img, np.float32), 0.0, 1.0) * 255.0
              + 0.5).astype(np.uint8)[..., ::-1]
        f = largeur / float(u8.shape[1])
        u8 = cv2.resize(u8, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        bande = np.zeros((24, largeur, 3), np.uint8)
        cv2.putText(bande, etiquette.encode("ascii", "replace").decode(),
                    (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255),
                    1, cv2.LINE_AA)
        tuiles.append(np.vstack([bande, u8]))
    h = max(t.shape[0] for t in tuiles)
    w = max(t.shape[1] for t in tuiles)
    tuiles = [np.pad(t, ((0, h - t.shape[0]), (0, w - t.shape[1]), (0, 0)))
              for t in tuiles]
    lignes = []
    for i in range(0, len(tuiles), colonnes):
        ligne_ = tuiles[i:i + colonnes]
        while len(ligne_) < colonnes:
            ligne_.append(np.zeros_like(tuiles[0]))
        lignes.append(np.hstack(ligne_))
    return np.vstack(lignes)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dossier-src", default=None)
    ap.add_argument("--target-bg", type=float, default=0.16)
    ap.add_argument("--sans-images", action="store_true")
    a = ap.parse_args()
    racine = a.dossier_src or dore.dossier_par_defaut()
    print(f"Brutes de la session live : {racine or '(cache local seulement)'}")
    canaux = dore.charger_canaux(racine or "")
    if len(canaux) != 3:
        print("  ARRÊT : il faut les trois rôles (SII, Ha, OIII)")
        return 1
    composite = compo.composer(canaux, "SHO")
    petit = dore.apercu(np.asarray(composite, np.float32))
    print(f"Composite SHO — aperçu de mesure {petit.shape}, "
          f"fond visé {a.target_bg}")

    # --------------------------------------------------------------- variantes
    # (code, étiquette, réglages) — l'ORDRE suit l'écran d'Alain.
    variantes = (
        ("A", "fit-gain-offset  SCNR off  (ton 22h09)",
         dict(fit="gain_offset", scnr=0.00, demag=1.00, boost=1.00)),
        ("B", "sans fit  SCNR 0.55  boost 1.60  (ecran actuel)",
         dict(fit=None, scnr=0.55, demag=1.00, boost=1.60)),
        ("C", "sans fit  SCNR 0.55  boost 3.00",
         dict(fit=None, scnr=0.55, demag=1.00, boost=3.00)),
        ("D", "sans fit  SCNR off  boost 3.00",
         dict(fit=None, scnr=0.00, demag=1.00, boost=3.00)),
        ("E", "sans fit  SCNR 0.55  boost 3.00 CONCENTRE (poids au carre)",
         dict(fit=None, scnr=0.55, demag=1.00, boost=3.00, poids_boost=2.0)),
        ("F", "fit gain+offset  boost 3.00",
         dict(fit="gain_offset", scnr=0.00, demag=1.00, boost=3.00)),
        ("G", "fit gain+offset  SCNR 0.35  boost 3.00",
         dict(fit="gain_offset", scnr=0.35, demag=1.00, boost=3.00)),
        ("H", "sans fit  SCNR 0.75  boost 1.60",
         dict(fit=None, scnr=0.75, demag=1.00, boost=1.60)),
        ("I", "sans fit  SCNR 1.00  boost 2.00",
         dict(fit=None, scnr=1.00, demag=1.00, boost=2.00)),
    )

    images = []
    for code, etiquette, reglages in variantes:
        im, gains, diag = chaine(petit, cible=a.target_bg, **reglages)
        m_neb, _coeur = dore.masques_objet(im)
        fond = im.mean(axis=2) < np.percentile(im.mean(axis=2), 25)
        print(f"\n[{code}] {etiquette}")
        if gains is not None:
            print(f"    neutralisation du fond : R {gains[0]:.3f} · "
                  f"V {gains[1]:.3f} · B {gains[2]:.3f}")
        if diag is not None:
            plafond = (_stacking.FIT_GAIN_MAX
                       - max(diag["gains"]) < 1e-6)
            print(f"    fit {diag['mode']} : gains R {diag['gains'][0]:.3f} · "
                  f"V {diag['gains'][1]:.3f} · B {diag['gains'][2]:.3f} | "
                  f"offsets R {diag['offsets'][0]:+.4f} · "
                  f"B {diag['offsets'][2]:+.4f}   (plafond "
                  f"{_stacking.FIT_GAIN_MAX:.2f} : "
                  f"{'ATTEINT' if plafond else 'libre'})")
        dore.ligne("NÉBULEUSE", im, m_neb)
        dore.ligne("  FOND (25 % les plus sombres)", im, fond)
        images.append((etiquette, im))
        if not a.sans_images:
            enregistrer(f"{code}_{etiquette.split('  ')[0].strip()}",
                        im)
    # ------------------------------------- tableau de balayage SCNR × boost
    # La TEINTE MAJORITAIRE de l'objet est ce qui décide du ressenti (« vert »
    # contre « doré ») : on la lit sur tous les pixels de la nébuleuse, pas
    # seulement sur le cœur brillant — c'est cet écart qui explique qu'un objet
    # « à R:G = 1 en moyenne » puisse paraître vert.
    print("\n[TABLEAU] vert / doré / saturation de l'OBJET — SCNR (lignes) × "
          "boost (colonnes), sans fit :")
    entete = "    SCNR\\boost " + "".join(f"{b:>18.2f}" for b in
                                         (1.00, 1.60, 2.00, 2.50, 3.00))
    print(entete)
    for s in (0.35, 0.55, 0.75, 1.00):
        cellule = []
        for b in (1.00, 1.60, 2.00, 2.50, 3.00):
            im, _g, _d = chaine(petit, fit=None, scnr=s, demag=1.0, boost=b,
                                cible=a.target_bg)
            m, _c = dore.masques_objet(im)
            parts, rgb, l_s, sat, _dor = dore.teintes(im, m)
            p = dict(parts)
            vert = p["vert"]
            dore_pc = p["rouge/orange (doré)"] + p["jaune (doré clair)"]
            cellule.append(f"{vert:4.0f}/{dore_pc:4.0f}/{sat:4.2f}")
        print(f"    {s:>5.2f}     " + "".join(f"{c:>18}" for c in cellule))
    print("    (vert %restant de l'objet / doré % (rouge+jaune) / saturation "
          "moyenne de l'objet)")

    if not a.sans_images:
        chemin = os.path.join(DOSSIER_IMAGES, "planche_00_comparaison.png")
        cv2.imwrite(chemin, planche(images))
        print(f"IMAGES ÉCRITES : {DOSSIER_IMAGES}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
