# -*- coding: utf-8 -*-
"""Test du jalon 117b (v2.69.1) — RAFFINEMENT SOUS-PIXEL À PORTE LARGE.

Défaut mesuré le 09/10/2026 sur le jeu M31 LRGB (deux nuits à 176,2°) : sur les
frames RETOURNÉES, la matrice rendue par `compute` laisse un résidu d'étoiles de
0,96 à 2,38 px (contre 0,14-0,15 px pour les frames de la même nuit), et le
fichier livré « save as seen » montre le canal R décalé de (−1,30, −1,33) px par
rapport au VERT → un ÉCHO ROUGE autour de chaque étoile.

Deux causes racines :
  ① le raffinement sous-pixel du jalon 57 (`_raffiner_centroides`) était
     GATED par un appariement mutuel serré (≤ 1,5 px) calculé avec la matrice
     BRUTE — précisément là où l'erreur dépasse 1,5 px il ne trouvait que 0 à 4
     couples et ne corrigeait RIEN ;
  ② rien ne VÉRIFIAIT la matrice retenue sur les centroïdes d'étoiles avant de
     l'accepter (seul garde-fou : le consensus RANSAC à 2 px sur les points ORB).

Correctif : la porte d'appariement devient LARGE puis RESSERRÉE par itérations
(4 → 1,5 → 1,0 px), et chaque matrice candidate est VÉRIFIÉE sur les centroïdes ;
la matrice d'entrée est rendue INCHANGÉE si le raffinement ne l'améliore pas.

Ce banc vérifie :
  [1] LE défaut lui-même : sur une matrice décalée d'environ 3 px, l'ANCIENNE
      porte (1,5 px) ne trouve AUCUN appariement (le défaut était invisible)
      tandis que la nouvelle la CORRIGE sous 0,5 px ;
  [2] la convergence sur une batterie d'erreurs (0,5 → 3,5 px) et l'absence de
      régression : la matrice rendue n'est jamais de résidu PIRE que l'entrée ;
  [3] le cas RETOURNÉ (~176°) : la même mécanique rattrape l'erreur d'une
      matrice à angle retourné (le cas réel du jalon 117) ;
  [4] non-régression du jalon 57 : un décalage SOUS-PIXEL connu est récupéré ;
  [5] garde-fous : image plate ou sans étoiles → matrice d'entrée INCHANGÉE.

Exécution : python bancs/_test_align_raffin_jalon117.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np
import cv2

from avastack.processing import alignment as al_mod
from avastack.processing import stars as stars_mod
from avastack.processing.alignment import StarAligner, canal_alignement

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def champ(shape, nb=40, sigma_px=1.3, bruit=0.004, fond=0.02, graine=1,
          marge=25):
    """Champ synthétique mono : `nb` étoiles gaussiennes + bruit (même esprit
    que les bancs d'alignement 13/15/116)."""
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(nb):
        y = float(rng.integers(marge, h - marge))
        x = float(rng.integers(marge, w - marge))
        a = float(rng.uniform(0.1, 0.7))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    return img


def translation(dx, dy):
    return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)


def rot_retour(deg, h, w, dx=0.0, dy=0.0):
    """Matrice « retournement au méridien » : rotation `deg` (~176°) autour du
    centre de la frame, plus une petite translation."""
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    return np.array([[c, -s, w / 2.0 - c * w / 2.0 + s * h / 2.0 + dx],
                     [s, c, h / 2.0 - s * w / 2.0 - c * h / 2.0 + dy]])


def pos_etoiles(al, frame):
    pos, _msg = stars_mod.detecter_positions(
        canal_alignement(frame), max_etoiles=al_mod.MAX_ALIGN_ETOILES,
        distance_min=al_mod._distance_repartition(frame.shape))
    return pos


def err_translation(M, Mref):
    """Écart (px) des translations de deux matrices (même convention : la
    matrice ramène la FRAME vers la RÉFÉRENCE)."""
    return float(np.hypot(float(M[0, 2]) - float(Mref[0, 2]),
                          float(M[1, 2]) - float(Mref[1, 2])))


H, W = 300, 400
REF = champ((H, W), nb=40, graine=2)
AL = StarAligner()
AL.set_reference(REF)

# ================================================ [1] le défaut lui-même
print("[1] Une matrice à ~3 px : l'ancienne porte ne voit RIEN, la nouvelle "
      "corrige")
POSE = translation(2.0, -2.0)         # la frame est la référence décalée
FR = cv2.warpAffine(REF, POSE, (W, H), flags=cv2.INTER_LINEAR)
M_true = cv2.invertAffineTransform(POSE)      # FR → RÉFÉRENCE
M_entree = M_true.copy()
M_entree[0, 2] += 2.0
M_entree[1, 2] += 2.0                 # erreur de ~2,83 px
pos = pos_etoiles(AL, FR)
_src_ancien, _dst_ancien, d_ancien = AL._appariements_mutuels(pos, M_entree, 1.5)
verifie(len(d_ancien) < al_mod.INLIERS_ETOILES,
        f"ANCIENNE porte (1,5 px) : {len(d_ancien)} appariement(s) < "
        f"{al_mod.INLIERS_ETOILES} → le défaut était INVISIBLE")
M_cor, n_cor = AL._raffiner_centroides(FR, M_entree)
err_av = err_translation(M_entree, M_true)
err_ap = err_translation(M_cor, M_true)
print(f"    avant {err_av:.2f} px → après {err_ap:.2f} px ({n_cor} appariements)")
verifie(n_cor >= al_mod.INLIERS_ETOILES,
        f"matrice RETENUE par le raffinement ({n_cor} appariements)")
verifie(err_ap < 0.5,
        f"erreur ramenée SOUS 0,5 px ({err_ap:.2f} px)")

# ================================================ [2] convergence + non-régression
print("[2] Batterie d'erreurs : corrigées, et JAMAIS pire que l'entrée")
_ang = np.deg2rad(35.0)
for m in (0.5, 1.0, 1.5, 2.0, 2.8, 3.5):
    M_in = M_true.copy()
    M_in[0, 2] += m * np.cos(_ang)
    M_in[1, 2] += m * np.sin(_ang)
    M_out, n = AL._raffiner_centroides(FR, M_in)
    e_out = err_translation(M_out, M_true)
    res_in = AL._verif_centroides(pos, M_in)[1]
    res_out = AL._verif_centroides(pos, M_out)[1]
    print(f"    erreur entrée {m:.1f} px → sortie {e_out:.2f} px, résidu "
          f"entrée {res_in:.2f} → sortie {res_out:.2f} ({n} appariements)")
    verifie(e_out < 0.5 and res_out <= res_in + 1e-6,
            f"entrée {m:.1f} px : corrigée ({e_out:.2f} px) et résidu non "
            f"dégradé ({res_out:.2f} ≤ {res_in:.2f})")


# ================================================ [3] cas RETOURNÉ (~176°)
print("[3] Cas RETOURNÉ (~176°) : l'erreur d'une matrice retournée est "
      "rattrapée")
POSE_R = rot_retour(176.0, H, W, dx=1.0, dy=-0.5)
FR_R = cv2.warpAffine(REF, POSE_R, (W, H), flags=cv2.INTER_LINEAR)
M_vrai = cv2.invertAffineTransform(POSE_R)     # FR retournée → RÉFÉRENCE
M_r_in = M_vrai.copy()
M_r_in[0, 2] += 2.0
M_r_in[1, 2] += 1.5                            # erreur de ~2,5 px
pos_r = pos_etoiles(AL, FR_R)
M_r_out, n_r = AL._raffiner_centroides(FR_R, M_r_in)
res_r_in = AL._verif_centroides(pos_r, M_r_in)[1]
res_r_out = AL._verif_centroides(pos_r, M_r_out)[1]
ang_r = abs(al_mod.infos_M(M_r_out)[0]) if M_r_out is not None else 0.0
e_r = err_translation(M_r_out, M_vrai)
print(f"    résidu {res_r_in:.2f} px → {res_r_out:.2f} px ({n_r} appariements, "
      f"angle {ang_r:.2f}°, erreur translation {e_r:.2f} px)")
verifie(n_r >= al_mod.INLIERS_ETOILES and e_r < 0.5
        and abs(ang_r - 176.0) < 3.0,
        f"matrice retournée corrigée ({e_r:.2f} px) et restée à ~176°")

# ================================================ [4] non-régression jalon 57
print("[4] Non-régression jalon 57 : décalage SOUS-PIXEL récupéré")
SUB = 0.573
POSE_S = translation(SUB, -SUB / 2.0)
FR_S = cv2.warpAffine(REF, POSE_S, (W, H), flags=cv2.INTER_LINEAR)
M_true_s = cv2.invertAffineTransform(POSE_S)
M_s, n_s = AL._raffiner_centroides(FR_S, np.eye(2, 3))   # ORB n'y voit rien
e_s = err_translation(M_s, M_true_s)
print(f"    décalage imposé ({SUB:.3f}, {-SUB / 2.0:.3f}) px → erreur "
      f"résiduelle {e_s:.3f} px ({n_s} appariements)")
verifie(n_s >= al_mod.INLIERS_ETOILES and e_s < 0.15,
        f"correction sous-pixel conservée (erreur {e_s:.3f} < 0,15 px)")

# ================================================ [5] garde-fous
print("[5] Garde-fous : rien à raffiner → matrice d'entrée INCHANGÉE")
PLATE = np.full((H, W), 0.4, np.float32)
AL5 = StarAligner()
AL5.set_reference(PLATE)
M_in5 = translation(3.0, -2.0)
M_out5, n5 = AL5._raffiner_centroides(PLATE, M_in5)
verifie(n5 == 0 and M_out5 is M_in5,
        "image plate → entrée rendue TELLE QUELLE (n = 0)")
AL6 = StarAligner()
AL6.set_reference(REF)
bruit = (0.05 + np.random.default_rng(5).normal(0, 0.01, (H, W))
         ).astype(np.float32)
M_in6 = translation(2.0, 2.0)
M_out6, n6 = AL6._raffiner_centroides(bruit, M_in6)
verifie(M_out6 is M_in6, "champ non corrélé → entrée rendue TELLE QUELLE")
verifie(al_mod.RAFFIN_RAYONS[0] > 1.5 and
        al_mod.RAFFIN_VERIF_RAYON == 2.5,
        f"porte initiale LARGE ({al_mod.RAFFIN_RAYONS[0]} px > 1,5 px) et "
        f"contre-test à {al_mod.RAFFIN_VERIF_RAYON} px")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)

