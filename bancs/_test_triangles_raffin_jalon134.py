# -*- coding: utf-8 -*-
"""Banc du jalon 134 — étape ② du plan ⑪ : raffiner `triangles` AU-DELÀ DU SEUIL.

CHANTIER CAUSE AMONT, étape ② (18/10/2026). Le plan ⑪ supposait que
`_triangles` rendait « la matrice LMEDS brute », moins précise que les chemins
ORB et « étoiles » qui la raffinent sur les centroïdes. Le CODE dit l'inverse
(correspondances mutuelles ≤ 2,5 px → RANSAC 2,5 px → LMEDS → contre-test final
d'appariements mutuels) et le run réel l'a confirmé : 143 frames posées par
`triangles` sur 472, résidu médian 0,083 px ; les centroïdes ne gagnent moins de
0,05 px sur 95 de ces 143 frames (66 %).

CHOIX C D'ALAIN : raffiner SEULEMENT si le résidu médian des appariements
mutuels dépasse `TRI_RAFFIN_SEUIL` (0,30 px → 43/143 frames du run).

Ce banc vérifie :
  [1] la CONSTANTE (0,30 px) et la signature `pos` optionnelle ;
  [2] un résidu FAIBLE ne déclenche RIEN : `_raffiner_centroides` jamais
      appelée, matrice rendue AU BIT identique (graine RANSAC/LMEDS fixée),
      méthode « triangles » — y compris sur une frame décalée de 1,2 px, où
      `_triangles` reste à ~0,03 px (le plan supposait l'inverse : MESURÉ ici) ;
  [3] les SEUILS pilotent bien : `TRI_RAFFIN_SEUIL = 0` → appelée,
      `= 10` → jamais ;
  [4] le CÂBLAGE, au niveau de ce qui est RENDU : la matrice du raffinement est
      PRISE (espion qui rend une matrice contrôlée), la méthode notée est
      `triangles+étoiles(n)`, et `_last_t` (continuité des frames suivantes) est
      celui de la matrice FINALE ;
  [5] un cas RÉEL où le raffinement GAGNE (frame faible et floue, résidu
      ~0,24 px) : au seuil de la scène la matrice est raffinée et le résidu
      BAISSE ; au seuil par défaut (0,30) la MÊME frame n'est pas touchée — le
      garde-fou de coût fait exactement son travail ;
  [6] `pos` fourni = AUCUNE re-détection des centroïdes (le piège de coût du
      plan : ~100 ms par frame raffinée), et résultat identique sans `pos` ;
  [7] champ PAUVRE (4 étoiles) : refus de `_triangles` sans exception, et
      `_raffiner_centroides` rend l'entrée inchangée (n = 0) sur des centroïdes
      vides ou trop peu nombreux.

Exécution : python bancs/_test_triangles_raffin_jalon134.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys

import numpy as np
import cv2

cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.processing.alignment as al_mod
from avastack.processing import stars as stars_mod

if hasattr(sys.stdout, "reconfigure"):    # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --------------------------------------------------------------- scènes de test
H, W = 300, 400
YY, XX = np.mgrid[0:H, 0:W]


def positions(graine=1, n=40):
    """Positions d'étoiles FIXES : la même scène pour toutes les frames."""
    rng = np.random.default_rng(graine)
    return [(float(rng.uniform(25, W - 25)), float(rng.uniform(25, H - 25)),
             float(rng.uniform(0.25, 0.9))) for _ in range(n)]


POS = positions()


def champ(graine=1, bruit=0.004, amp=1.0, flou=0.0, sigma=1.3, fond=0.03,
          pos=None):
    """Champ d'étoiles gaussiennes + bruit indépendant (graine) — `amp` et
    `flou` fabriquent une frame FAIBLE et DOUCE (brute de mauvaise nuit), seul
    cas synthétique où `_triangles` laisse un résidu appréciable."""
    img = np.full((H, W), fond, np.float32)
    for x, y, a in (POS if pos is None else pos):
        img += (amp * a * np.exp(-((YY - y) ** 2 + (XX - x) ** 2)
                                 / (2.0 * sigma ** 2))).astype(np.float32)
    if flou:
        img = cv2.GaussianBlur(img, (0, 0), float(flou))
    img += np.random.default_rng(graine).normal(0, bruit,
                                                img.shape).astype(np.float32)
    return img


def decale(img, dx, dy):
    """warpAffine d'une translation (sens OpenCV : contenu déplacé de (dx,dy))."""
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float64)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR)


def triangles(al, frame, graine=12345):
    """`_triangles` avec une graine RANSAC/LMEDS FIXÉE : sans cela les deux
    estimateurs d'OpenCV tirent dans le générateur global et deux appels ne
    rendent pas la même matrice — la comparaison « AU BIT » du volet [2] ne
    prouverait alors rien."""
    cv2.setRNGSeed(graine)
    return al._triangles(frame)


def centroides(img):
    """Mêmes centroïdes que ceux que `_triangles` vient de calculer."""
    p, _msg = stars_mod.detecter_positions(
        al_mod.canal_alignement(img), max_etoiles=al_mod.MAX_ALIGN_ETOILES,
        distance_min=al_mod._distance_repartition(img.shape))
    return p


def residu(a, M, pos):
    return a._verif_centroides(pos, M)[1]


REF = champ(1)                                   # référence : champ propre
FR_PROPRE = decale(champ(2), 1.2, 0.4)           # frame nette, décalée (sous-pixel)
FR_FAIBLE = decale(champ(2, amp=0.20, flou=1.0, bruit=0.008), 0.05, 0.4)


class AligneurEspion(al_mod.StarAligner):
    """Compte les appels au raffinement et retient la matrice d'entrée."""

    def __init__(self):
        super().__init__()
        self.appels = []
        self.pos_fourni = []

    def _raffiner_centroides(self, frame, M, pos=None):
        self.appels.append(1)
        self.pos_fourni.append(pos)
        return super()._raffiner_centroides(frame, M, pos=pos)


class AligneurRaffinFactice(al_mod.StarAligner):
    """Raffinement REMPLACÉ par une matrice contrôlée : prouve ce que
    `_triangles` FAIT du résultat (matrice prise, méthode, `_last_t`)."""

    def __init__(self, n=17):
        super().__init__()
        self.n = n
        self.appels = 0
        self.M_entree = None
        self.M_sortie = None

    def _raffiner_centroides(self, frame, M, pos=None):
        self.appels += 1
        self.M_entree = np.array(M, np.float64).copy()
        M2 = self.M_entree.copy()
        M2[0, 2] += 0.5                  # un gain NET, reconnaissable
        M2[1, 2] -= 0.25
        self.M_sortie = M2
        return M2, self.n


# ==================================== [1] constante et signature
print("[1] constante TRI_RAFFIN_SEUIL et signature `pos` optionnelle")
verifie(hasattr(al_mod, "TRI_RAFFIN_SEUIL"), "TRI_RAFFIN_SEUIL existe")
verifie(abs(float(al_mod.TRI_RAFFIN_SEUIL) - 0.30) < 1e-12,
        f"seuil par défaut = 0,30 px (43/143 frames du run ; lu "
        f"{al_mod.TRI_RAFFIN_SEUIL})")
verifie(isinstance(al_mod.TRI_RAFFIN_SEUIL, float),
        "le seuil est un float (comparé à un résidu float)")
try:
    al_mod.StarAligner()._raffiner_centroides(np.zeros((10, 10), np.float32),
                                              np.eye(2, 3), pos=None)
    sig_ok = True
except Exception:                # noqa: BLE001 — on ne teste que la signature
    sig_ok = False
verifie(sig_ok, "_raffiner_centroides accepte `pos=` (mot-clé, défaut None)")

# ==================================== [2] résidu faible → rien ne bouge
print("[2] résidu faible : RAFFINEMENT JAMAIS appelé, matrice AU BIT")
seuil_ini = al_mod.TRI_RAFFIN_SEUIL
a2 = AligneurEspion()
a2.set_reference(REF)
M2, ok2 = triangles(a2, FR_PROPRE)
pos_propre = centroides(FR_PROPRE)
res2 = residu(a2, M2, pos_propre) if ok2 else float("nan")
verifie(ok2 and M2 is not None,
        "une frame nette décalée de 1,2 px passe par « triangles »")
verifie(not a2.appels,
        f"…et `_raffiner_centroides` n'est JAMAIS appelée (0 appel — résidu "
        f"médian mesuré {res2:.3f} px < {seuil_ini:.2f})")
verifie(res2 <= seuil_ini,
        f"…ce qui est cohérent : `_triangles` laisse {res2:.3f} px même sur un "
        f"décalage de 1,2 px (le plan ⑪ supposait l'inverse — mesuré ici)")
verifie(a2.dernier is not None and a2.dernier["methode"] == "triangles",
        f"…méthode notée « triangles » (lu « "
        f"{(a2.dernier or {}).get('methode')} »)")
try:
    al_mod.TRI_RAFFIN_SEUIL = 10.0       # jamais raffiné : matrice de RÉFÉRENCE
    a2b = al_mod.StarAligner()
    a2b.set_reference(REF)
    M2_ref, ok2_ref = triangles(a2b, FR_PROPRE)
finally:
    al_mod.TRI_RAFFIN_SEUIL = seuil_ini
verifie(ok2_ref and np.array_equal(np.asarray(M2, np.float64),
                                   np.asarray(M2_ref, np.float64)),
        "matrice rendue AU BIT identique à celle de `_triangles` sans "
        "raffinement (graine RANSAC/LMEDS fixée)")

# ==================================== [3] le SEUIL pilote la décision
print("[3] les seuils pilotent : 0 → appelée, 10 → jamais")
a3 = AligneurEspion()
a3.set_reference(REF)
try:
    al_mod.TRI_RAFFIN_SEUIL = 0.0
    M3, ok3 = triangles(a3, FR_PROPRE)
finally:
    al_mod.TRI_RAFFIN_SEUIL = seuil_ini
verifie(ok3 and len(a3.appels) == 1,
        f"seuil 0 px → `_raffiner_centroides` APPELÉE ({len(a3.appels)} appel)")
verifie(bool(a3.pos_fourni) and a3.pos_fourni[0] is not None,
        "…et elle reçoit les centroïdes DÉJÀ calculés (`pos` non None)")
a3b = AligneurEspion()
a3b.set_reference(REF)
try:
    al_mod.TRI_RAFFIN_SEUIL = 10.0
    M3b, ok3b = triangles(a3b, FR_PROPRE)
finally:
    al_mod.TRI_RAFFIN_SEUIL = seuil_ini
verifie(ok3b and not a3b.appels,
        "seuil 10 px → JAMAIS appelée (aucun coût sur cette frame)")
verifie(a3b.dernier is not None and a3b.dernier["methode"] == "triangles",
        "…et la méthode reste « triangles »")

# ==================================== [4] câblage : ce qui est RENDU
print("[4] câblage : matrice du raffinement PRISE, méthode et `_last_t` finaux")
a4 = AligneurRaffinFactice(n=17)
a4.set_reference(REF)
try:
    al_mod.TRI_RAFFIN_SEUIL = 0.0        # force le passage dans la branche
    M4, ok4 = triangles(a4, FR_PROPRE)
finally:
    al_mod.TRI_RAFFIN_SEUIL = seuil_ini
verifie(ok4 and a4.appels == 1, "branche empruntée (1 appel au raffinement)")
verifie(ok4 and np.array_equal(np.asarray(M4, np.float64), a4.M_sortie),
        "la matrice RENDUE est celle du raffinement, pas celle des triangles")
verifie(not np.array_equal(a4.M_sortie, a4.M_entree),
        "…et elle DIFFÈRE bien de l'entrée (le gain contrôlé a été pris)")
verifie(a4.dernier is not None
        and a4.dernier["methode"] == "triangles+étoiles(17)",
        f"méthode notée « triangles+étoiles(17) » (lu « "
        f"{(a4.dernier or {}).get('methode')} ») — la ligne d'état et la trace ⑦ "
        f"distinguent les deux chemins")
verifie(a4._last_t is not None
        and abs(a4._last_t[0] - float(a4.M_sortie[0, 2])) < 1e-9
        and abs(a4._last_t[1] - float(a4.M_sortie[1, 2])) < 1e-9,
        "`_last_t` (continuité des frames suivantes) = translation de la "
        "matrice FINALE")
verifie(a4.dernier is not None
        and abs(float(a4.dernier["dx"]) - float(a4.M_sortie[0, 2])) < 1e-9
        and abs(float(a4.dernier["dy"]) - float(a4.M_sortie[1, 2])) < 1e-9,
        "…et la ligne d'état annonce la MÊME translation")
verifie(abs(float(a4.M_entree[0, 2]) + 1.2) < 0.6,
        f"cohérence de la scène : translation « triangles » = "
        f"{float(a4.M_entree[0, 2]):+.2f} px pour −1,20 px attendus")

# ==================================== [5] un cas RÉEL où le raffinement gagne
print("[5] frame FAIBLE et DOUCE : le raffinement gagne, mais seulement sous "
      "le seuil")
a5 = AligneurEspion()
a5.set_reference(REF)
try:
    al_mod.TRI_RAFFIN_SEUIL = 10.0       # matrice de référence, sans raffinement
    M5_ref, ok5_ref = triangles(a5, FR_FAIBLE)
finally:
    al_mod.TRI_RAFFIN_SEUIL = seuil_ini
pos_faible = centroides(FR_FAIBLE)
res5_ref = residu(a5, M5_ref, pos_faible) if ok5_ref else float("nan")
verifie(ok5_ref and 0.10 < res5_ref < seuil_ini,
        f"scène : résidu médian {res5_ref:.3f} px — au-dessus de 0,10 px et "
        f"sous le seuil par défaut (0,30) : les deux comportements se testent "
        f"sur la MÊME frame")
a5d = AligneurEspion()
a5d.set_reference(REF)
M5d, ok5d = triangles(a5d, FR_FAIBLE)          # seuil par défaut
verifie(ok5d and not a5d.appels
        and np.array_equal(np.asarray(M5d, np.float64),
                           np.asarray(M5_ref, np.float64)),
        "au seuil par défaut (0,30) : PAS raffinée, matrice AU BIT inchangée "
        "— le garde-fou de coût fait son travail")
a5s = AligneurEspion()
a5s.set_reference(REF)
try:
    al_mod.TRI_RAFFIN_SEUIL = 0.10       # sous le résidu de la scène
    M5s, ok5s = triangles(a5s, FR_FAIBLE)
finally:
    al_mod.TRI_RAFFIN_SEUIL = seuil_ini
n5 = len(a5s.appels)
res5_s = residu(a5s, M5s, pos_faible) if ok5s else float("nan")
verifie(ok5s and n5 == 1, f"au seuil 0,10 : raffinée ({n5} appel)")
verifie(res5_s <= res5_ref + 1e-9,
        f"résidu APRÈS = {res5_s:.3f} px contre {res5_ref:.3f} px avant "
        f"(jamais de régression : le raffinement rend l'entrée INCHANGÉE "
        f"quand il ne fait pas mieux)")
methode5 = (a5s.dernier or {}).get("methode")
verifie(methode5 == "triangles" or str(methode5).startswith("triangles+étoiles("),
        f"méthode renseignée et cohérente (lu « {methode5} » : rien si le "
        f"raffinement n'a pas conclu, `triangles+étoiles(n)` sinon)")

# ==================================== [6] `pos` fourni = aucune re-détection
print("[6] `pos` fourni : AUCUNE re-détection des centroïdes (coût du plan ⑪)")
appels_detect = []
detect_orig = stars_mod.detecter_positions


def detect_espion(*a, **k):
    appels_detect.append(1)
    return detect_orig(*a, **k)


a6 = al_mod.StarAligner()
a6.set_reference(REF)
pos6 = centroides(FR_FAIBLE)
M6 = np.asarray(M5_ref, np.float64).copy()
try:
    stars_mod.detecter_positions = detect_espion
    cv2.setRNGSeed(777)
    Ma, na = a6._raffiner_centroides(FR_FAIBLE, M6, pos=pos6)
    avec_pos = len(appels_detect)
    appels_detect.clear()
    cv2.setRNGSeed(777)
    Mb, nb = a6._raffiner_centroides(FR_FAIBLE, M6)
    sans_pos = len(appels_detect)
finally:
    stars_mod.detecter_positions = detect_orig
verifie(avec_pos == 0 and sans_pos >= 1,
        f"`pos` fourni → {avec_pos} détection ; sans `pos` → {sans_pos} "
        f"détection (comportement historique des appelants ORB / étoiles)")
verifie(np.array_equal(np.asarray(Ma, np.float64), np.asarray(Mb, np.float64))
        and na == nb,
        f"résultat IDENTIQUE dans les deux cas ({na} appariements) — fournir "
        f"`pos` n'économise QUE le calcul")

# ==================================== [7] champ pauvre : refus sans exception
print("[7] champ PAUVRE : refus de `_triangles`, entrée rendue inchangée")
pos_pauvre = POS[:4]
img_pauvre = champ(9, pos=pos_pauvre)
a7 = AligneurEspion()
a7.set_reference(REF)
try:
    al_mod.TRI_RAFFIN_SEUIL = 0.0        # même en forçant la branche
    M7, ok7 = triangles(a7, img_pauvre)
    leve = False
except Exception:                        # noqa: BLE001
    M7, ok7, leve = None, False, True
finally:
    al_mod.TRI_RAFFIN_SEUIL = seuil_ini
verifie(not leve, "aucune exception ne sort de `_triangles` sur un champ pauvre")
verifie(not ok7 and M7 is None and not a7.appels,
        "…la frame est REFUSÉE (aucune matrice inventée) et le raffinement "
        "n'est même pas tenté")
I7 = np.eye(2, 3)
vide = np.zeros((0, 2), np.float32)
Mv, nv = a7._raffiner_centroides(img_pauvre, I7, pos=vide)
verifie(nv == 0 and np.array_equal(np.asarray(Mv, np.float64), I7),
        "centroïdes VIDES → entrée rendue INCHANGÉE, n = 0 (jamais d'exception)")
Mc, nc = a7._raffiner_centroides(img_pauvre, I7, pos=pos_pauvre)
verifie(nc == 0 and np.array_equal(np.asarray(Mc, np.float64), I7),
        "4 étoiles seulement → entrée INCHANGÉE, n = 0")

print()
print("JALON 134 : " + ("TOUS LES TESTS PASSENT" if ok
                         else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)
