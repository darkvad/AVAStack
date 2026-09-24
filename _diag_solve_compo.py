# -*- coding: utf-8 -*-
r"""Diagnostic de la RÉSOLUTION ASTROMÉTRIQUE d'une COMPOSITION (jalon 56).

Constat réel du 23/09/2026 (Alain, composition RGB, 33 frames empilées) :
« aucune affinité convaincante (meilleur score : 5 étoiles) ; RANSAC paires :
meilleur 4 inliers, échelle 2.459″/px » — l'échelle trouvée est JUSTE, mais
trop peu d'étoiles sont appariées. Hypothèse à trancher : l'image analysée
(le COMPOSITE, dont seul le canal VERT sert à la détection) contient beaucoup
moins d'étoiles détectables qu'une COUCHE seule.

Usage (canaux séparés écrits par l'appli « Enregistrer les canaux ») :
    python _diag_solve_compo.py --canal R=canal_R.fit --canal G=canal_G.fit \
        --canal B=canal_B.fit --ra 10.683333 --dec 41.268611 --champ 2.6366

Sortie : pour CHAQUE couche seule ET pour le composite — nombre d'étoiles
détectées, taille du catalogue, appariements, rms, verdict.
"""
import argparse
import os
import sys

import numpy as np

from avastack.catalogues import resoudre
from avastack.catalogues.solveur import _detecter      # diagnostic assumé
from avastack.images import load_image
from avastack.processing.composition import composer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def etoiles_detectees(img, quoi):
    """Compteurs de détection du solveur, tels quels (aucune réinterprétation)."""
    pos, msg = _detecter(img, 120)
    mono = np.asarray(img)
    if mono.ndim == 3:
        mono = mono[..., 1] if mono.shape[-1] == 3 else mono[1]
    bruit = 1.4826 * float(np.median(np.abs(mono - np.median(mono))))
    print(f"    détection {quoi} : {len(pos)} étoiles ; fond "
          f"{float(np.median(mono)):.4f} ; bruit MAD {bruit:.5f}"
          + (f" ; « {msg} »" if msg else ""))
    return len(pos)


def resoudre_et_raconter(img, quoi, ra, dec, champ):
    n_det = etoiles_detectees(img, quoi)
    wcs, info, msg = resoudre(img, ra, dec, champ)
    if wcs is None:
        print(f"    {quoi} : ÉCHEC — {msg}")
        print(f"      compteurs du solveur : image {info['n_etoiles_img']} "
              f"étoiles, catalogue {info['n_etoiles_cat']}, appariements "
              f"{info['n_appariements']}")
    else:
        print(f"    {quoi} : RÉSOLU — {info['n_appariements']} appariements, "
              f"rms {info['rms_px']:.2f} px, échelle "
              f"{info['echelle_arcsec_px']:.4f}″/px ({info['methode']})")
    return wcs, info, msg, n_det


def principal():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--canal", action="append", default=[],
                    metavar="ROLE=fichier",
                    help="canal séparé (répétable : R=… G=… B=… Ha=… O3=…)")
    ap.add_argument("--composite", default=None,
                    help="image composite déjà empilée (facultatif)")
    ap.add_argument("--composition", default=None,
                    help="nom de composition (RGB, HOO, SHO, LRGB) ; déduit "
                         "des rôles si absent")
    ap.add_argument("--ra", type=float, required=True, help="AD en degrés")
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--champ", type=float, required=True,
                    help="LARGEUR du champ en degrés")
    a = ap.parse_args()

    canaux = {}
    for item in a.canal:
        if "=" not in item:
            print(f"ERREUR : --canal attend ROLE=fichier (reçu {item})")
            return 1
        role, chemin = item.split("=", 1)
        if not os.path.isfile(chemin):
            print(f"ERREUR : fichier absent : {chemin}")
            return 1
        canaux[role] = load_image(chemin)
        print(f"couche {role} : {chemin} — {canaux[role].shape}, "
              f"max {float(np.nanmax(canaux[role])):.4g}")

    print(f"\nIndices : AD {a.ra:.6f}°, Dec {a.dec:+.6f}°, champ "
          f"{a.champ:.4f}° (largeur)")
    print("\n[1] CHAQUE COUCHE SEULE (ce que le solveur voit d'un canal)")
    for role, img in canaux.items():
        resoudre_et_raconter(img, f"couche {role}", a.ra, a.dec, a.champ)

    if canaux:
        comp_nom = a.composition
        if comp_nom is None:
            rôles = set(canaux)
            for nom, spec in (("RGB", {"R", "G", "B"}),
                              ("HOO", {"Ha", "O3"}),
                              ("SHO", {"S2", "Ha", "O3"}),
                              ("LRGB", {"L", "R", "G", "B"})):
                if rôles == spec:
                    comp_nom = nom
                    break
            print(f"\n    (composition déduite des rôles : {comp_nom})")
        if comp_nom:
            print(f"\n[2] COMPOSITE {comp_nom} — exactement ce que l'appli "
                  f"analyse (canaux normalisés par percentiles)")
            comp = composer(canaux, comp_nom)
            if comp is None:
                print("    composite impossible (aucun rôle exploitable)")
            else:
                print(f"    composite : {comp.shape}, max "
                      f"{float(np.nanmax(comp)):.4g}")
                resoudre_et_raconter(comp, "composite", a.ra, a.dec, a.champ)
        else:
            print("\n    composition indéterminée : préciser --composition")

    if a.composite and os.path.isfile(a.composite):
        print(f"\n[3] FICHIER COMPOSITE fourni : {a.composite}")
        img = load_image(a.composite)
        resoudre_et_raconter(img, "composite sauvegardé", a.ra, a.dec, a.champ)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
