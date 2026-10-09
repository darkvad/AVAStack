# -*- coding: utf-8 -*-
"""Test du jalon 116 (v2.68.0) — ALIGNEMENT des frames d'une AUTRE NUIT.

Constat réel d'Alain (09/10/2026, M31 LRGB = L du 13/09 + R/G/B du 22-23/09) :
210 frames lues, **130 empilées et 80 NON ALIGNÉES**, avec des doublons rouges,
une trace sombre et des biseaux noirs. Rejeu hors-ligne des frames RÉELLEMENT
lues : l'écart entre les deux nuits vaut 176,2° — donc DANS la tolérance du
retournement au méridien (180° ± 10°) —, et seules les frames qui EXIGENT ce
retournement étaient perdues. Deux causes cumulées :

① LA FRAME ÉTAIT NORMALISÉE AVEC LES BORNES DE LA RÉFÉRENCE — d'une nuit (ou
  d'un filtre) à l'autre le fond diffère (facteur ~1,8× mesuré) → 78-97 % des
  pixels de la frame écrasés à 0 et 1-3 appariements au lieu des 8 exigés.
② `_triangles` NE PEUT PAS PORTER LE RETOURNEMENT — il s'appuie sur les 12
  étoiles les plus brillantes et n'en apparie plus que 4-5 sur des couples
  INTER-NUITS (seuil 6).

Ce banc vérifie :
  [1] le DÉFAUT ① lui-même : une frame dont le fond est divisé par 2 est
      ÉCRASÉE dans les premiers niveaux 8 bits par les bornes de la référence,
      et RESTITUÉE par ses propres bornes — avec, à la clé, bien plus
      d'appariements ORB (c'est cette mesure qui a guidé le correctif) ;
  [2] bout en bout : une frame « autre nuit » (fond ÷ 2 + rotation 176°)
      S'ALIGNE (angle retrouvé ≈ 176°, reconstruction ≈ la référence) ; une
      frame d'une autre nuit NON pivotée s'aligne aussi ;
  [3] garde-fous : 30° et 90° restent REFUSÉS, une échelle aberrante aussi, et
      du bruit non corrélé est refusé — le dernier recours n'a pas rendu
      l'aligneur crédule ;
  [4] le DERNIER RECOURS (jalon 116 ②) : `compute` l'essaie sur la frame puis
      sur la frame retournée de 180° (et compose la matrice), et les
      descripteurs de RÉFÉRENCE étoffés ne sont calculés qu'à la première
      demande, CONSERVÉS ensuite, et invalidés par `set_reference` ;
  [5] non-régression : la translation pure reste alignée par le chemin
      historique, et une image plate reste refusée (aucun faux appariement).

Aucun affichage nécessaire. Exécution :
python bancs/_test_align_lumiere_jalon116.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np
import cv2

from avastack.processing import alignment as al_mod

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def champ(shape, nb=25, sigma_px=1.5, bruit=0.004, fond=0.02, graine=1,
          marge=25):
    """Champ synthétique mono : nb étoiles gaussiennes + bruit (même esprit
    que les bancs d'alignement 13/15/111)."""
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


def autre_nuit(ref, fond=0.01, facteur=0.5, angle_deg=176.0, graine=3,
               bruit=0.003):
    """Frame d'une AUTRE nuit/filtre : fond de ciel divisé par 2 (autre
    exposition, autre filtre), bruit neuf, et champ PIVOTÉ (`angle_deg`) —
    c'est le retournement au méridien / la reprise de session."""
    rng = np.random.default_rng(graine)
    lo = float(np.percentile(ref, 1.0))
    img = (ref.astype(np.float32) - lo) * facteur + fond
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    img = img.astype(np.float32)
    if angle_deg:
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
        img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR)
    return img


def ecart_central(a, b, marge=0.2):
    """Écart moyen |a − b| sur le CENTRE des deux images : une frame pivotée a
    des coins noirs (hors champ) qu'il ne faut pas imputer à l'alignement."""
    h, w = a.shape[:2]
    my, mx = int(h * marge), int(w * marge)
    aa = a[my:h - my, mx:w - mx].astype(np.float32)
    bb = b[my:h - my, mx:w - mx].astype(np.float32)
    return float(np.mean(np.abs(aa - bb)))


def appariements(reference, frame, normalisation):
    """Appariements ORB (ratio 0,75) entre la référence et la frame, celle-ci
    normalisée par la fonction fournie — mesure directe de l'effet ①."""
    al = al_mod.StarAligner()
    al.set_reference(reference)
    g = normalisation(frame)
    orb = cv2.ORB_create(nfeatures=1000, fastThreshold=8)
    _k1, d1 = al.orb.detectAndCompute(al.ref_gray, None)
    _k2, d2 = orb.detectAndCompute(g, None)
    if d1 is None or d2 is None:
        return 0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    return sum(1 for pair in bf.knnMatch(d1, d2, k=2)
               if len(pair) == 2
               and pair[0].distance < 0.75 * pair[1].distance)


# ==================================================== [1] le défaut ① mesuré
print("[1] Défaut ① : la frame d'une autre nuit est écrasée par les bornes de "
      "la référence")
# Ici le ciel est BRUYEUX COMME EN RÉEL (σ ≈ 4 % du fond) : c'est cette
# propriété qui rend le défaut mesurable, car le percentile 1 % de la référence
# tombe alors JUSTE SOUS le fond du ciel — toute frame dont le fond est plus
# sombre (autre nuit, autre filtre) passe entièrement en dessous et se fait
# écraser à 0. Un fond comparable au bruit (σ ≈ 20 % du fond) masquerait le
# défaut : ce n'est PAS ce que montrent les brutes réelles.
REF1 = champ((300, 400), nb=25, bruit=0.0008, graine=2)
FR = autre_nuit(REF1, fond=0.010, bruit=0.0006, graine=4, angle_deg=0.0)
al1 = al_mod.StarAligner()
al1.set_reference(REF1)
g_partage = al1._norm8(FR, al1._ref_lo, al1._ref_hi)   # bornes de la RÉFÉRENCE
g_propre = al1._norm8(FR)                             # bornes de la FRAME
part_0 = float(np.mean(g_partage == 0)) * 100.0
propre_0 = float(np.mean(g_propre == 0)) * 100.0
med_partage = float(np.median(g_partage))
med_propre = float(np.median(g_propre))
print(f"    fond : référence {float(np.median(REF1)):.4f} · "
      f"frame {float(np.median(FR)):.4f} (÷ 2)")
print(f"    bornes de la référence : médiane {med_partage:.0f}/255 · "
      f"{part_0:.0f} % des pixels à 0")
print(f"    bornes de la frame     : médiane {med_propre:.0f}/255 · "
      f"{propre_0:.0f} % des pixels à 0")
verifie(part_0 > 50.0 and med_partage < 8.0,
        f"bornes de la RÉFÉRENCE → frame écrasée ({part_0:.0f} % de pixels "
        f"nuls, médiane {med_partage:.0f}/255)")
verifie(propre_0 < part_0 / 2.0 and med_propre > med_partage * 2.0,
        f"SES PROPRES bornes → frame restituée ({propre_0:.0f} % de pixels "
        f"nuls, médiane {med_propre:.0f}/255)")
n_partage = appariements(REF1, FR, lambda f: al1._norm8(f, al1._ref_lo,
                                                        al1._ref_hi))
n_propre = appariements(REF1, FR, lambda f: al1._norm8(f))
print(f"    appariements ORB : {n_partage} avec les bornes de la référence, "
      f"{n_propre} avec celles de la frame")
# Sur les VRAIES brutes l'écart était de 1-3 contre 22-96 appariements (mesuré
# le 09/10/2026) ; sur un champ synthétique il est plus modeste, car les étoiles
# SATURENT à 255 dans les deux cas et offrent donc des coins à l'ORB même
# écrasées. Ce que le banc verrouille ici, c'est le DÉFAUT lui-même (99 % de
# pixels nuls) et le fait que l'ORB travaille désormais sur une frame pleine.
verifie(n_propre >= 8,
        f"l'ORB apparie sur SES PROPRES bornes ({n_propre} ≥ 8 appariements, "
        f"contre {n_partage} avec les bornes de la référence)")

# ==================================================== [2] bout en bout
print("[2] Une frame « autre nuit » (fond ÷ 2 + rotation 176°) S'ALIGNE")
REF = champ((300, 400), nb=25, graine=2)     # champ de référence des sections 2-5
al2 = al_mod.StarAligner()
al2.set_reference(REF)
FR_PIV = autre_nuit(REF, angle_deg=176.0)
M, okk = al2.compute(FR_PIV)
methode = al2.dernier["methode"] if (okk and al2.dernier) else "REFUS"
print(f"    méthode « {methode} »")
ang, ech, _dx, _dy = (al_mod.infos_M(M) if M is not None
                      else (0.0, 0.0, 0.0, 0.0))
verifie(okk, f"frame retournée de 176° ALIGNÉE (méthode « {methode} »)")
verifie(okk and abs(abs(ang) - 176.0) < 3.0,
        f"angle retrouvé ≈ 176° ({ang:+.2f}°) · échelle {ech:.4f}")
if okk:
    rec = cv2.warpAffine(FR_PIV, M, (FR_PIV.shape[1], FR_PIV.shape[0]))
    ec = ecart_central(rec, REF)
    verifie(ec < 0.02,
            f"frame de l'autre nuit reconstruite ≈ référence "
            f"(écart moyen au centre {ec:.4f})")
al2b = al_mod.StarAligner()
al2b.set_reference(REF)
M_d, ok_d = al2b.compute(FR)      # autre nuit, MÊME orientation (fond ÷ 2)
verifie(ok_d and abs(float(M_d[0, 2])) < 1.0 and abs(float(M_d[1, 2])) < 1.0,
        f"frame d'une autre nuit NON pivotée alignée aussi "
        f"(Δ=({float(M_d[0, 2]):+.2f},{float(M_d[1, 2]):+.2f}))")


# ==================================================== [3] garde-fous
print("[3] Garde-fous : les rotations hors tolérance restent REFUSÉES")
for deg in (30.0, 90.0):
    _al = al_mod.StarAligner()
    _al.set_reference(REF)
    M3, ok3 = _al.compute(autre_nuit(REF, angle_deg=deg))
    ang3 = abs(al_mod.infos_M(M3)[0]) if M3 is not None else 0.0
    verifie(not ok3,
            f"rotation {deg:.0f}° → REFUSÉE (ok={ok3}, angle={ang3:.1f}°)")
al3b = al_mod.StarAligner()
al3b.set_reference(REF)
_h, _w = REF.shape
M_ech = cv2.getRotationMatrix2D((_w / 2.0, _h / 2.0), 0.0, 1.3)
FR_ECH = cv2.warpAffine(REF, M_ech, (_w, _h), flags=cv2.INTER_LINEAR)
M4, ok4 = al3b.compute(FR_ECH)
verifie(not ok4, f"échelle 1,3 → REFUSÉE (ok={ok4})")
al3c = al_mod.StarAligner()
al3c.set_reference(REF)
bruit = (0.05 + np.random.default_rng(5).normal(0, 0.01, REF.shape)
         ).astype(np.float32)
M5, ok5 = al3c.compute(bruit)
verifie(not ok5, f"bruit non corrélé → REFUSÉ (ok={ok5})")

# ==================================================== [4] dernier recours ②
print("[4] Dernier recours ② : ORB étoffé, wiring et cache des descripteurs")


class FauxDirect:
    """Neutralise TOUTE la cascade historique (`_compute_direct`) pour vérifier
    le wiring du dernier recours, sans dépendre de sa réussite."""

    def __call__(self, *a, **k):
        return None, False


def _faux_renforce(al, essais):
    """`_orb_renforce` factice : rend (M, True) au i-ème essai listé dans
    `essais`, échoue aux autres. Compte les appels (et garde les frames)."""
    appels = []

    def faux(frame):
        appels.append(frame)
        i = len(appels) - 1
        if i < len(essais) and essais[i]:
            al._noter(np.eye(2, 3), "ORB étoffé")
            return np.eye(2, 3), True
        return None, False
    return faux, appels


al4 = al_mod.StarAligner()
al4.set_reference(REF)
al4._compute_direct = FauxDirect()             # cascade historique neutralisée
al4._orb_renforce, appels4 = _faux_renforce(al4, [True])
M6, ok6 = al4.compute(FR_PIV)
verifie(ok6 and len(appels4) == 1,
        f"cascade neutralisée → le DERNIER RECOURS sauve la frame "
        f"({len(appels4)} appel(s), méthode « "
        f"{al4.dernier['methode'] if al4.dernier else '?'} »)")

al4b = al_mod.StarAligner()
al4b.set_reference(REF)
al4b._compute_direct = FauxDirect()
al4b._orb_renforce, appels4b = _faux_renforce(al4b, [False, True])
M7, ok7 = al4b.compute(FR_PIV)
ang7 = abs(al_mod.infos_M(M7)[0]) if M7 is not None else 0.0
verifie(len(appels4b) == 2 and ok7,
        f"échec sur la frame → le recours est repris sur la frame RETOURNÉE "
        f"({len(appels4b)} appels)")
verifie(ok7 and abs(ang7 - 180.0) < 1.0,
        f"matrice composée « retournement PUIS alignement » (angle {ang7:.1f}°)")
_meth7 = al4b.dernier["methode"] if al4b.dernier else "?"
verifie(al4b.dernier is not None and _meth7 == "ORB étoffé +180°",
        f"la méthode rapportée dit le retournement (« {_meth7} »)")
_M7c, ok7c = al4b._composer_retournement(
    np.array([[0.5, 0.0, 0.0], [0.0, 0.5, 0.0]], np.float64), FR_PIV)
verifie(not ok7c, "composition hors tolérance (échelle 0,5) → refusée")

al_c = al_mod.StarAligner()
al_c.set_reference(REF)
verifie(al_c.ref_des_fort is None and al_c.ref_kp_fort is None,
        "descripteurs ÉTOFFÉS de la référence NON calculés par set_reference "
        "(rien payé tant que rien ne l'exige)")
M8, ok8 = al_c._orb_renforce(FR_PIV)
_meth8 = al_c.dernier["methode"] if al_c.dernier else "?"
verifie(ok8 and al_c.ref_des_fort is not None and al_c.ref_kp_fort is not None,
        f"calculés à la 1re demande, et le recours aligne (méthode « "
        f"{_meth8} »)")
_id_av = id(al_c.ref_des_fort)
al_c._orb_renforce(FR_PIV)
verifie(id(al_c.ref_des_fort) == _id_av and al_c._ref_fort_vue is True,
        "CONSERVÉS au 2e appel (même objet : aucun recalcul)")
al_c.set_reference(REF)
verifie(al_c.ref_des_fort is None and al_c._ref_fort_vue is False,
        "cache INVALIDÉ par set_reference (jamais périmé après un "
        "rafraîchissement de référence)")

# ==================================================== [5] non-régression
print("[5] Non-régression : chemin historique et absence de faux appariement")
al5 = al_mod.StarAligner()
al5.set_reference(REF)
Mt = np.array([[1.0, 0.0, 7.0], [0.0, 1.0, -5.0]], np.float64)
FR_T = cv2.warpAffine(REF, Mt, (REF.shape[1], REF.shape[0]),
                      flags=cv2.INTER_LINEAR)
M9, ok9 = al5.compute(FR_T)
_meth9 = al5.dernier["methode"] if al5.dernier else "?"
verifie(ok9 and abs(float(M9[0, 2]) + 7.0) < 0.7
        and abs(float(M9[1, 2]) - 5.0) < 0.7,
        f"translation (+7,−5) toujours retrouvée (méthode « {_meth9} »)")
PLATE = np.full((300, 400), 0.4, np.float32)
al6 = al_mod.StarAligner()
al6.set_reference(PLATE)
_M10, ok10 = al6._orb_renforce(PLATE)
verifie(not ok10, "image plate → le dernier recours REFUSE (aucun faux "
                  "appariement)")
verifie(al_mod.ORB_RENFORCE_FEATURES == 8000 and al6.orb_fort is not al6.orb,
        f"détecteur étoffé DISTINCT ({al_mod.ORB_RENFORCE_FEATURES} points) du "
        f"détecteur principal (1 000)")

print()
print("RÉSULTAT :", "TOUT AU VERT" if ok else "ÉCHEC(S) — voir ci-dessus")
sys.exit(0 if ok else 1)


