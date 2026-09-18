# -*- coding: utf-8 -*-
"""Tests jalon 19, Phase 1 — module composition multi-filtres.

Vérifie (sans interface, numpy seul) :
  - la table COMPOSITIONS (rôles, optionnels, mapping canaux) ;
  - extraire_canal : mono intact, couleur → canal(x) du rôle, luma pour L ;
  - normaliser : linéaire SANS clip (étoiles > 1 conservées) ;
  - composer : mapping SHO/HOO exacts (bornes figées), canal absent →
    zéros sans planter, gains, LRGB (L présent → combine, chroma
    préservée ; L vide → radio synthétisé/dégradé), Mono → 2D ;
  - formes hétérogènes → ValueError claire.

Exécution : python _test_composition_jalon19.py
"""
import numpy as np

from avastack.processing.composition import (CANAUX_CFA, COMPOSITIONS,
                                             bornes_normalisation,
                                             extraire_canal, composer,
                                             normaliser, roles_de,
                                             roles_optionnels)

if hasattr(__import__("sys").stdout, "reconfigure"):
    __import__("sys").stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


B01 = {"S2": (0.0, 1.0), "Ha": (0.0, 1.0), "O3": (0.0, 1.0),
       "R": (0.0, 1.0), "G": (0.0, 1.0), "B": (0.0, 1.0), "L": (0.0, 1.0)}

print("[1] Table des compositions")
verifie(roles_de("Mono") == ("L",) and roles_de("HOO") == ("Ha", "O3")
        and roles_de("SHO") == ("S2", "Ha", "O3")
        and roles_de("RGB") == ("R", "G", "B")
        and roles_de("LRGB") == ("L", "R", "G", "B"),
        "rôles attendus (Mono 1, HOO 2, SHO 3, RGB 3, LRGB 4)")
verifie(roles_optionnels("LRGB") == ("L",)
        and all(roles_optionnels(c) == () for c in
                ("Mono", "HOO", "SHO", "RGB")),
        "seul L est optionnel")
verifie(COMPOSITIONS["SHO"]["canaux_rgb"] == {"R": ("S2",), "G": ("Ha",),
                                              "B": ("O3",)}
        and COMPOSITIONS["HOO"]["canaux_rgb"] == {"R": ("Ha",), "G": ("O3",),
                                                  "B": ("O3",)},
        "mappings SHO et HOO")
verifie(CANAUX_CFA["Ha"] == (0,) and CANAUX_CFA["S2"] == (0,)
        and CANAUX_CFA["O3"] == (1, 2) and CANAUX_CFA["L"] == "luma",
        "canaux CFA des rôles (Ha/S2→R, O3→G+B, L→luma)")

print("[2] extraire_canal : mono intact, couleur → canal du rôle")
rng = np.random.default_rng(7)
mono = rng.normal(0.2, 0.02, (16, 24)).astype(np.float32)
verifie(np.array_equal(extraire_canal(mono, "Ha"), mono),
        "brute mono (2D) → telle quelle, quel que soit le rôle")
coul = np.zeros((4, 5, 3), np.float32)
coul[..., 0], coul[..., 1], coul[..., 2] = 0.1, 0.2, 0.3
verifie(np.allclose(extraire_canal(coul, "Ha"), 0.1),
        "couleur + rôle Ha → canal R")
verifie(np.allclose(extraire_canal(coul, "O3"),
                    (coul[..., 1] + coul[..., 2]) / 2),
        "couleur + rôle O3 → moyenne G+B")
verifie(np.allclose(extraire_canal(coul, "L"),
                    0.299 * 0.1 + 0.587 * 0.2 + 0.114 * 0.3),
        "couleur + rôle L → luminance pondérée")

print("[3] normaliser : linéaire, SANS clip")
img = np.linspace(0.0, 0.5, 48, dtype=np.float32).reshape(8, 6)
n = normaliser(img, 0.0, 0.25)
verifie(float(n.max()) > 1.5, "les valeurs au-dessus de hi restent > 1 (pas de clip)")
lo, hi = bornes_normalisation(np.linspace(0, 1, 4096, dtype=np.float32)
                              .reshape(64, 64))
verifie(abs(lo) < 0.05 and abs(hi - 1.0) < 0.05,
        f"bornes auto d'une rampe 0..1 : ({lo:.3f}, {hi:.3f})")

print("[4] composer SHO : mapping exact (bornes figées), canal absent, gains")
sho = composer({"S2": np.full((8, 8), 0.2, np.float32),
                "Ha": np.full((8, 8), 0.3, np.float32),
                "O3": np.full((8, 8), 0.4, np.float32)},
               "SHO", bornes=B01)
verifie(sho.shape == (8, 8, 3)
        and np.allclose(sho[..., 0], 0.2) and np.allclose(sho[..., 1], 0.3)
        and np.allclose(sho[..., 2], 0.4),
        "SHO → R=S2, G=Ha, B=O3 (valeurs exactes)")
sho2 = composer({"S2": np.full((8, 8), 0.2, np.float32),
                 "Ha": np.full((8, 8), 0.3, np.float32), "O3": None},
                "SHO", bornes=B01)
verifie(sho2 is not None and np.allclose(sho2[..., 2], 0.0)
        and np.allclose(sho2[..., 0], 0.2),
        "rôle O3 vide → canal B à zéros, pas d'exception")
sho3 = composer({"S2": np.full((8, 8), 0.2, np.float32),
                 "Ha": np.full((8, 8), 0.3, np.float32),
                 "O3": np.full((8, 8), 0.4, np.float32)},
                "SHO", gains={"R": 2.0}, bornes=B01)
verifie(np.allclose(sho3[..., 0], 0.4) and np.allclose(sho3[..., 1], 0.3),
        "gains appliqués après normalisation (R ×2)")
verifie(composer({}, "SHO") is None, "aucun rôle fourni → None (pas de plantage)")

print("[5] composer HOO : O3 alimente G ET B")
hoo = composer({"Ha": np.full((6, 6), 0.25, np.float32),
                "O3": np.full((6, 6), 0.5, np.float32)},
               "HOO", bornes=B01)
verifie(np.allclose(hoo[..., 0], 0.25) and np.allclose(hoo[..., 1], 0.5)
        and np.allclose(hoo[..., 2], 0.5),
        "HOO → R=Ha, G=B=O3")

print("[6] LRGB : L présent → combine, chroma préservée")
lrgb = composer({"L": np.full((8, 8), 0.6, np.float32),
                 "R": np.full((8, 8), 0.2, np.float32),
                 "G": np.full((8, 8), 0.2, np.float32),
                 "B": np.full((8, 8), 0.2, np.float32)},
                "LRGB", bornes=B01)
verifie(lrgb.shape == (8, 8, 3) and np.allclose(lrgb, 0.6),
        "gris 0.2 + L=0.6 → gris 0.6 (ratio luminance)")
canaux_colores = {"R": np.full((8, 8), 0.1, np.float32),
                  "G": np.full((8, 8), 0.2, np.float32),
                  "B": np.full((8, 8), 0.3, np.float32),
                  "L": np.full((8, 8), 0.1815, np.float32)}
lrgb2 = composer(canaux_colores, "LRGB", bornes=B01)
verifie(np.allclose(lrgb2[..., 0], 0.1) and np.allclose(lrgb2[..., 1], 0.2)
        and np.allclose(lrgb2[..., 2], 0.3),
        "L = luminance du composite → chroma inchangée (ratio 1)")

print("[7] LRGB : L VIDE → la radio décide (synthétisé / dégradé RGB)")
rgb_seul = composer({"R": canaux_colores["R"], "G": canaux_colores["G"],
                     "B": canaux_colores["B"]}, "RGB", bornes=B01)
synth = composer(dict(canaux_colores, L=None), "LRGB", bornes=B01,
                 mode_l="synthetise")
degr = composer(dict(canaux_colores, L=None), "LRGB", bornes=B01,
                mode_l="degrade")
verifie(synth is not None and np.allclose(synth, rgb_seul),
        "mode « synthétisé » : identique au RGB pur (combine identité)")
verifie(degr is not None and np.allclose(degr, rgb_seul),
        "mode « dégradé » : identique au RGB pur")
fallback = composer(dict(canaux_colores, L=None), "LRGB", bornes=B01,
                    mode_l="valeur_inconnue")
verifie(fallback is not None and np.allclose(fallback, rgb_seul),
        "mode_l invalide → repli « synthétisé » (pas d'exception)")

print("[8] Mono → composite 2D ; formes hétérogènes → ValueError")
m = composer({"L": np.full((5, 7), 0.3, np.float32)}, "Mono", bornes=B01)
verifie(m.shape == (5, 7) and np.allclose(m, 0.3), "Mono → (H, W)")
verifie(composer({"L": None}, "Mono") is None, "Mono sans données → None")
deja_norm = composer({"S2": np.full((8, 8), 0.2, np.float32),
                      "Ha": np.full((8, 8), 0.3, np.float32),
                      "O3": np.full((8, 8), 0.4, np.float32)},
                     "SHO", normaliser_canal=False)
verifie(np.allclose(deja_norm[..., 0], 0.2) and np.allclose(deja_norm[..., 1], 0.3),
        "normaliser_canal=False : canaux déjà normalisés passés tels quels")
try:
    composer({"S2": np.zeros((8, 8), np.float32),
              "Ha": np.zeros((9, 8), np.float32),
              "O3": np.zeros((8, 8), np.float32)}, "SHO", bornes=B01)
    verifie(False, "formes hétérogènes → ValueError attendu")
except ValueError as e:
    verifie("recadrer" in str(e), f"formes hétérogènes → ValueError ({e})")

print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
import sys
sys.exit(0 if ok else 1)
