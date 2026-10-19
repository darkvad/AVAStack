# -*- coding: utf-8 -*-
"""Diagnostic — échelles comparées du Ha (`s`) et du rouge du composite (`R`)
AVANT de réécrire les opérateurs de fusion du Ha (J3bis).

CONTEXTE (test réel du 19/10/2026, M33, branche `LRGBHa`) : les quatre modes
`fondu_rouge`, `ecran_rouge`, `eclaircir_rouge` et `ha_luminance` ont été
condamnés À L'ÉCRAN (fondu bleui, écran cyan, éclaircir inerte, luminance
blanchit). Hypothèse à VÉRIFIER, pas à supposer : `composer()` normalise
CHAQUE rôle sur SES PROPRES percentiles (0,25 / 99,7) ; `s` et `R` ne vivent
donc pas dans le même espace — ni en AMPLITUDE, ni en NIVEAU DE FOND.

Ce banc ne modifie RIEN dans l'appli : il rejoue `composer()` sur les couches
BRUTES par rôle et MESURE :

  1. p0,25 / p50 / p99,7 de `s` et de `R` (R = canal rouge du composite,
     combine LRGB inclus, fusion coupée par `poids = 0`) ;
  2. le NIVEAU de fond des deux (s est recentré ⇒ plancher 0 ; R garde le
     fond normalisé) — c'est la seconde dissymétrie, souvent oubliée ;
  3. le signe de `s − R` dans les zones Ha et la part de pixels où `R > s`
     (c'est ce qui rend `eclaircir_rouge` INERTE : max(0, s − R) = 0) ;
  4. pour chaque mode et pour chaque zone (fond / Ha large / cœur Ha), le
     DELTA appliqué : c'est la preuve chiffrée du fond bleui et des zones
     cyan, pas une impression ;
  5. le FACTEUR d'appariement d'amplitude et le PLANCHER de R, puis le rejeu
     des quatre modes APRÈS appariement — matière première du J3bis.

ENTRÉES — les couches BRUTES par rôle écrites par l'appli (bouton
« 💾 Enregistrer les canaux (par filtre)… »), dans UN dossier :
    canal_L.fit  canal_R.fit  canal_G.fit  canal_B.fit  canal_Ha.fit
(sans L : composition « RGB+Ha » ; avec L : « LRGB+Ha », combine L compris.)
Les fichiers sont des MOYENNES de rôle : linéaires, recadrées au cadre
commun, sans normalisation ni gain — exactement l'entrée de `composer()`.

Usage :
    python bancs/_diag_fusion_ha_echelles.py --canaux C:\\...\\canaux
    python bancs/_diag_fusion_ha_echelles.py --canaux ... --composite m33.fits
    python bancs/_diag_fusion_ha_echelles.py --autotest

`--composite` est un CONTRÔLE, pas une entrée : le fichier linéaire écrit par
« Enregistrer » doit être retrouvé par le rejeu (aux réglages près : mode,
poids, α, Q, continuum, recentrage). Un écart ≤ 1e-4 valide la mesure ; un
écart plus grand veut dire qu'un réglage diffère (case « lisser les halos »,
normalisation commune, poids…) — le banc le DIT au lieu de mesurer faux.
"""

# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc
import pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc))
        break

import argparse
import glob
import os
import sys

import numpy as np

from avastack.images import load_image
from avastack.processing.composition import (BW_HA_NM, BW_RGB_NM, CLIP_HA_MAX,
                                            CLIP_HA_MIN, Q_HA_DEFAUT,
                                            bornes_normalisation, composer,
                                            normaliser)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROLES = ("L", "R", "G", "B", "Ha")
PCT = (0.25, 50.0, 99.7)
MODES = ("fondu_rouge", "ecran_rouge", "eclaircir_rouge", "ha_luminance")


def _verifie(cond, msg):
    """Vérification d'autotest : dit OK, ou sort en ERREUR (jamais silencieux)."""
    print(("  [OK] " if cond else "  [ECHEC] ") + msg)
    if not cond:
        raise SystemExit(1)


def _entete(path):
    """En-tête FITS (best effort) : sert à défaire AVASCALE, jamais bloquant."""
    try:
        from astropy.io import fits
        with fits.open(path) as h:
            return dict(h[0].header)
    except Exception:
        return {}


def _charge_couche(dossier, role):
    """Carte 2D du rôle, ou None. Les fichiers s'appellent canal_<rôle>.fit ;
    un repli par motif accepte un dossier renommé à la main."""
    exact = os.path.join(dossier, f"canal_{role}.fit")
    cand = [exact] if os.path.isfile(exact) else []
    if not cand:
        # Repli : le rôle doit suivre un « _ » (sinon le « l » de « canal »
        # ferait matcher canal_B.fit pour le rôle L — piège réel).
        cand = sorted(glob.glob(os.path.join(dossier, f"*_{role}*.fit")))
        cand = [c for c in cand if not os.path.basename(c).startswith("_")]
    if not cand:
        return None, None
    a = np.asarray(load_image(cand[0]), dtype=np.float32)
    if a.ndim != 2:
        raise SystemExit(f"{cand[0]} : couche NON 2D (forme {a.shape}) — "
                         f"ce n'est pas un empilement par rôle")
    sc = _entete(cand[0]).get("AVASCALE")
    if sc:
        # borner_lineaire a divisé la couche par son max à l'écriture : on la
        # remet dans son échelle d'origine (sinon la mesure est décalée).
        a = (a * float(sc)).astype(np.float32)
    return a, cand[0]


def charge(dossier):
    """dict rôle → carte + composition à rejouer + liste des trouvailles."""
    canaux, trouves, manquants = {}, [], []
    for role in ROLES:
        a, p = _charge_couche(dossier, role)
        if a is None:
            manquants.append(role)
        else:
            canaux[role] = a
            trouves.append((role, p, a.shape))
    if "Ha" not in canaux or "R" not in canaux:
        raise SystemExit("Il faut AU MOINS canal_Ha.fit et canal_R.fit "
                         f"(trouvés : {sorted(canaux)})")
    for role, p, shp in trouves:
        print(f"  {role:<2} {shp[0]}x{shp[1]}  {os.path.basename(p)}")
    if manquants:
        print(f"  absents (ignorés) : {', '.join(manquants)}")
    forme = next(iter(canaux.values())).shape
    if any(a.shape != forme for a in canaux.values()):
        raise SystemExit("Couches de formes DIFFÉRENTES : elles ne viennent pas "
                         "du même cadre commun — refaire l'enregistrement en "
                         "une seule fois depuis la session.")
    return canaux, ("LRGB+Ha" if "L" in canaux else "RGB+Ha")


# --------------------------------------------------------------- le signal ---
def signal_et_rouge(canaux, composition, q=Q_HA_DEFAUT, continuum=True,
                    recentrer=True, sigma_l=0.0, normalisation_commune=False):
    """Rejoue EXACTEMENT ce que fait `composer()` puis `fusionner_ha()`.

    `R` est le canal rouge du composite SANS fusion (`poids = 0` → composite
    du J1 au bit), combine LRGB compris. `s` est le signal Ha tel que le voit
    `fusionner_ha` : Ha normalisé par ses bornes, recentré sur sa médiane,
    puis continuum retiré (Q × 7/100 × R_brut/échelle(Ha)) et écrêtage [0 ; 1].

    → (s, R, bornes, échelle_ha). Lève SystemExit si le composite n'est pas
    couleur (couches incohérentes) : mieux vaut ne rien mesurer que mesurer à
    côté.
    """
    bornes = {r: bornes_normalisation(a) for r, a in canaux.items()}
    comp = composer(canaux, composition, bornes=bornes, sigma_l=sigma_l,
                    normalisation_commune=bool(normalisation_commune),
                    fusion_ha={"poids": 0.0})
    if comp is None or comp.ndim != 3 or comp.shape[-1] != 3:
        raise SystemExit("Le rejeu ne produit pas un composite couleur : "
                         "vérifier que les couches viennent bien de la même "
                         "session (mêmes formes, rôles corrects).")
    R = np.asarray(comp[..., 0], dtype=np.float32)
    lo, hi = bornes["Ha"]
    h = normaliser(canaux["Ha"], lo, hi)
    s = h - float(np.median(h))
    echelle = float(hi - lo)
    if continuum:
        r = np.asarray(canaux["R"], dtype=np.float32)
        r = r - float(np.median(r))
        k = float(q) * (BW_HA_NM / BW_RGB_NM)
        s = np.clip(s - np.float32(k / echelle) * r, CLIP_HA_MIN, CLIP_HA_MAX)
    return np.asarray(s, np.float32), R, bornes, echelle


def _pct_str(a, nom):
    v = np.percentile(a, PCT)
    return (f"  {nom:<12} p0,25={v[0]:8.5f}  p50={v[1]:8.5f}  "
            f"p99,7={v[2]:8.5f}   amplitude={v[2] - v[0]:8.5f}")


def zones(s):
    """Trois zones de lecture, définies SUR `s` (donc après écrêtage, comme
    le signal réellement utilisé) : le fond (moitié basse), la zone Ha large
    (décile haut) et le cœur Ha (centile haut). Les étoiles brillantes
    tombent dans le cœur : c'est voulu, c'est là que `R > 1` et que l'écran
    devient négatif."""
    p50, p90, p99 = np.percentile(s, (50.0, 90.0, 99.0))
    return {"fond": s <= p50, "ha_large": s >= p90, "ha_coeur": s >= p99}, (
        float(p50), float(p90), float(p99))


def deltas(R, s, alpha):
    """Delta de chaque mode (poids 1), formules du J3, appliquées au canal R.
    `ha_luminance` ajoute `s` TEL QUEL : son delta rouge est le même."""
    return {"fondu_rouge": np.float32(alpha) * (s - R),
            "ecran_rouge": s * (np.float32(1.0) - R),
            "eclaircir_rouge": np.maximum(s - R, np.float32(0.0)),
            "ha_luminance": s}


def appariement(R, s, z):
    """Facteur d'amplitude et plancher à appliquer à `s` pour vivre dans
    l'espace de `R`. DEUX nombres, parce qu'il y a DEUX dissymétries :
    l'amplitude (percentiles séparés) et le niveau (R garde son fond, s est
    recentré ⇒ plancher 0)."""
    fond, large = z["fond"], z["ha_large"]
    sr = float(np.median(R[large])) - float(np.median(R[fond]))
    ss = float(np.median(s[large])) - float(np.median(s[fond]))
    f_zone = sr / ss if abs(ss) > 1e-9 else float("nan")
    p = np.percentile(R, PCT)
    qs = np.percentile(s, PCT)
    f_pct = ((p[2] - p[0]) / (qs[2] - qs[0])
             if (qs[2] - qs[0]) > 1e-9 else float("nan"))
    return (f_zone, f_pct, float(np.median(R[fond])), float(np.median(s[fond])),
            float(p[2] - p[0]))


def rapport(s, R, alpha):
    """LE RAPPORT — toutes les mesures, dans l'ordre où on les lit."""
    print("\n" + "=" * 78)
    print("[1] PERCENTILES — les deux couches ne sont PAS dans le même espace")
    print("=" * 78)
    print(_pct_str(s, "s (Ha)"))
    print(_pct_str(R, "R (composite)"))
    print(f"  part de pixels où s > 0 : {100.0 * float(np.mean(s > 0.0)):5.1f} %"
          "   (s est écrêté à 0 : le fond Ha est plat)")
    print(f"  part de pixels où R > 1 : {100.0 * float(np.mean(R > 1.0)):5.2f} %"
          "   (là, 1 − R < 0 : l'écran SOUSTRAIT du rouge)")

    z, seuils = zones(s)
    print("\n" + "=" * 78)
    print("[2] ZONES et SIGNE de s − R (p50 / p90 / p99 de s : "
          f"{seuils[0]:.4f} / {seuils[1]:.4f} / {seuils[2]:.4f})")
    print("=" * 78)
    for nom, m in z.items():
        if not m.any():
            print(f"  {nom:<9} : vide")
            continue
        d = s[m] - R[m]
        print(f"  {nom:<9} n={m.sum():>9}  R médian={float(np.median(R[m])):7.4f}"
              f"  s médian={float(np.median(s[m])):7.4f}"
              f"  s−R médian={float(np.median(d)):+8.4f}"
              f"  R>s : {100.0 * float(np.mean(d < 0)):5.1f} %")

    fz, fp, fond_r, fond_s, amp_r = appariement(R, s, z)
    print("\n" + "=" * 78)
    print("[3] APPARIEMENT — deux axes distincts, à ne pas confondre")
    print("=" * 78)
    print(f"  amplitude GLOBALE (p99,7-p0,25)  R/s = {fp:8.3f}")
    print(f"  contraste DANS LES ZONES         R/s = {fz:8.3f}")
    print(f"  plancher du fond                 R = {fond_r:8.5f}   s = {fond_s:8.5f}")
    if np.isfinite(fp) and abs(fp - 1.0) < 0.05:
        print("  => amplitudes appariees : `normaliser()` cale CHAQUE role sur\n"
              "     p0,25/p99,7, donc R et s ont tous deux une amplitude de 1 si\n"
              "     ni le continuum ni l'ecretage ne les separent.")
    elif np.isfinite(fp):
        print(f"  => l'amplitude de s vaut {1.0 / fp:.2f}x celle de R. Ce n'est pas\n"
              "     une echelle oubliee : `normaliser()` les cale POURTANT toutes\n"
              "     deux sur 1 ; l'ecart vient du CONTINUUM retire a s et de son\n"
              "     ECRETAGE [0;1] (R, lui, n'est jamais ecrete).")
    if np.isfinite(fz) and (fz > 1.5 or fz < 1.0 / 1.5):
        print(f"  => le CONTRASTE du Ha est {fz:.2f}x celui du rouge dans les zones:\n"
              "     continuum + ecretage [0;1] mangent une part du signal.")
    if fond_r > 0.01:
        part = 100.0 * fond_r / max(1e-9, amp_r)
        print("  => NIVEAUX NON APPARIES (l'axe principal) : R vit sur un plancher\n"
              f"     de {fond_r:.5f} ({part:.1f} % de son amplitude), s sur 0.00000\n"
              "     (recentrage). Un fondu ou un eclaircir qui COMPARE les deux ne\n"
              "     peut pas etre neutre au fond : il ramene le rouge du fond vers 0\n"
              "     (=> cyan/bleu), et laisse R>s presque partout (=> eclaircir inerte).")
    else:
        print("  => planchers compatibles (R quasi nul au fond, comme s).")

    print("\n" + "=" * 78)
    print("[4] CE QUE CHAQUE MODE FAIT (poids 1), AVANT appariement")
    print("=" * 78)
    for mode, d in deltas(R, s, alpha).items():
        print(f"  {mode}")
        for nom, m in z.items():
            if not m.any():
                continue
            dm = d[m]
            print(f"    {nom:<9} delta R median={float(np.median(dm)):+8.4f}   "
                  f"monte : {100.0 * float(np.mean(dm > 0)):5.1f} %   "
                  f"baisse : {100.0 * float(np.mean(dm < 0)):5.1f} %")
    return fz, fond_r


def apres_appariement(s, R, alpha, fz, fond_r):
    """Rejeu des quatre modes APRÈS appariement — chaque opérateur reçoit la
    forme dont il a besoin (le fondu et l'éclaircir comparent deux NIVEAUX,
    l'écran et la luminance ajoutent un SIGNAL) : c'est la piste J3bis, à
    trancher par Alain, pas une décision du banc."""
    fa = fz if np.isfinite(fz) and fz > 0 else 1.0
    sa = (fa * s).astype(np.float32)                  # amplitude seule
    sl = (np.float32(fond_r) + fa * s).astype(np.float32)   # amplitude + niveau
    apres = {"fondu_rouge": np.float32(alpha) * (sl - R),
             "ecran_rouge": s * (np.float32(1.0) - np.minimum(R, 1.0)),
             "eclaircir_rouge": np.maximum(sa - (R - np.float32(fond_r)),
                                           np.float32(0.0)),
             "ha_luminance": fa * s}
    print("\n" + "=" * 78)
    print("[5] APRES APPARIEMENT (piste J3bis) — memes mesures")
    print("=" * 78)
    z, _ = zones(s)
    for mode, d in apres.items():
        print(f"  {mode}")
        for nom, m in z.items():
            if not m.any():
                continue
            dm = d[m]
            print(f"    {nom:<9} delta R median={float(np.median(dm)):+8.4f}   "
                  f"monte : {100.0 * float(np.mean(dm > 0)):5.1f} %   "
                  f"baisse : {100.0 * float(np.mean(dm < 0)):5.1f} %")


# ------------------------------------------------------- contrôle du rejeu ---
def controles(canaux, composition, chemin, mode, poids, alpha, q, continuum,
              recentrer, sigma_l, norm_commune):
    """Le fichier linéaire enregistré par l'appli doit être RETROUVÉ par le
    rejeu. Sert de garde-fou : si les réglages passés en ligne de commande ne
    sont pas ceux de la session, l'écart le dit (jamais de mesure muette)."""
    print("\n" + "=" * 78)
    print("[0] CONTROLE — le rejeu retrouve-t-il le fichier enregistre ?")
    print("=" * 78)
    a = np.asarray(load_image(chemin), dtype=np.float32)
    if a.ndim == 3:
        a = a[..., 0]
    sc = _entete(chemin).get("AVASCALE")
    if sc:
        a = (a * float(sc)).astype(np.float32)
        print(f"  AVASCALE defait : x{float(sc):.6f}")
    bornes = {r: bornes_normalisation(v) for r, v in canaux.items()}
    b = composer(canaux, composition, bornes=bornes, sigma_l=sigma_l,
                 normalisation_commune=bool(norm_commune),
                 fusion_ha={"mode": mode, "poids": poids, "alpha": alpha,
                            "continuum": continuum, "q": q,
                            "recentrer": recentrer})
    if b is None:
        raise SystemExit("rejeu impossible pour le controle")
    b = np.asarray(b[..., 0], dtype=np.float32)
    if b.shape != a.shape:
        print(f"  ATTENTION formes differentes : rejeu {b.shape} / "
              f"fichier {a.shape} (recadrage ?) — controle NON conclu")
        return
    d = np.abs(a - b)
    corr = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
    print(f"  |ecart| max={float(d.max()):.6f}  p99={float(np.percentile(d, 99)):.6f}"
          f"  correlation={corr:.6f}")
    if float(d.max()) <= 1e-4:
        print("  => REJEU FIDELE : la mesure de s et R decrit bien la session.")
    else:
        print("  => ECART : un reglage differe (mode/poids/alpha/Q/continuum/"
              "recentrer, halos 117d, normalisation commune, recadrage...).\n"
              "     Relancer avec les reglages REELLEMENT affiches, ou ignorer "
              "ce controle (la mesure reste valable, seule la comparaison au "
              "fichier ne l'est pas).")


# --------------------------------------------------------------- autotest ---
def _jeu(fond_ha, neb_ha, etoiles_ha):
    """Couches synthétiques : fond + nébuleuse (3 blobs) + 4 étoiles + bruit.
    R/G/B ont une « nébuleuse » faible et des étoiles fortes (continuum) ;
    le Ha est réglé par l'appelant — c'est le rapport Ha/rouge qu'on teste."""
    rng = np.random.default_rng(3)
    h = w = 192
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    neb = np.zeros((h, w), np.float32)
    for cy, cx, sig, amp in ((70, 80, 22, 1.0), (110, 130, 16, 0.7),
                             (95, 60, 9, 0.5)):
        neb += amp * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2.0 * sig * sig))
    etoiles = np.zeros((h, w), np.float32)
    for cy, cx, amp in ((40, 50, 30.0), (150, 40, 12.0), (60, 160, 20.0),
                        (130, 100, 8.0)):
        etoiles += amp * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / 2.2)
    bruit = rng.normal(0.0, 0.0015, (h, w)).astype(np.float32)
    return {"R": (0.050 + 0.030 * neb + 0.40 * etoiles + bruit).astype(np.float32),
            "G": (0.045 + 0.022 * neb + 0.38 * etoiles + bruit).astype(np.float32),
            "B": (0.040 + 0.016 * neb + 0.36 * etoiles + bruit).astype(np.float32),
            "Ha": (fond_ha + neb_ha * neb + etoiles_ha * etoiles
                   + bruit).astype(np.float32)}


def _indicateurs(canaux, alpha, q, continuum, recentrer):
    s, R, _b, _e = signal_et_rouge(canaux, "RGB+Ha", q=q, continuum=continuum,
                                   recentrer=recentrer)
    z, _seuils = zones(s)
    fz, fp, fond_r, _fs, _amp = appariement(R, s, z)
    d = deltas(R, s, alpha)
    return {"s": s, "R": R, "z": z, "fz": fz, "fp": fp, "fond_r": fond_r,
            "d": d,
            "monte_eclaircir_ha": float(np.mean(d["eclaircir_rouge"][z["ha_coeur"]] > 0)),
            "fondu_fond": float(np.median(d["fondu_rouge"][z["fond"]])),
            "fondu_ha": float(np.median(d["fondu_rouge"][z["ha_coeur"]])),
            "part_R_sup_1": float(np.mean(R > 1.0))}


def autotest():
    """Le banc doit SAVOIR reconnaître un jeu condamné et un jeu sain : sans
    ça, ses chiffres sur M33 ne prouveraient rien (leçon des bancs 132-134)."""
    print("[A] jeu CONDAMNE — Ha proportionnel au rouge, recentre (cas M33)")
    a = _indicateurs(_jeu(0.030, 0.0075, 0.100), alpha=0.5, q=0.80,
                     continuum=True, recentrer=True)
    print(f"    R/s amplitude={a['fp']:.3f}  contraste={a['fz']:.3f}  "
          f"plancher R={a['fond_r']:.4f}  R>1: {100 * a['part_R_sup_1']:.2f} %")
    print(f"    fondu : delta fond={a['fondu_fond']:+.5f}  "
          f"delta coeur Ha={a['fondu_ha']:+.5f}")
    print(f"    eclaircir : monte dans {100 * a['monte_eclaircir_ha']:.1f} % "
          "du coeur Ha")
    _verifie(a["fond_r"] > 0.02,
             "R vit sur un PLANCHER, s sur 0 (niveaux non apparies)")
    _verifie(a["monte_eclaircir_ha"] < 0.10,
             "eclaircir quasi INERTE en zone Ha — defaut reproduit")
    _verifie(a["fondu_ha"] < 0.0,
             "fondu BAISSE le rouge en zone Ha — zones bleuies reproduites")
    _verifie(a["fondu_fond"] < 0.0,
             "fondu BAISSE aussi le rouge du FOND — cyan/bleu du fond reproduit")

    print("[B] jeu SAIN — Ha domine la nebuleuse, non recentre")
    b = _indicateurs(_jeu(0.050, 0.060, 0.020), alpha=0.5, q=0.80,
                     continuum=False, recentrer=False)
    print(f"    R/s amplitude={b['fp']:.3f}  contraste={b['fz']:.3f}  "
          f"fond fondu={b['fondu_fond']:+.5f}  fond Ha={b['fondu_ha']:+.5f}")
    print(f"    eclaircir : monte dans {100 * b['monte_eclaircir_ha']:.1f} % "
          "du coeur Ha")
    _verifie(b["monte_eclaircir_ha"] > 0.80,
             "eclaircir AGIT quand le Ha domine (mode non inerte)")
    _verifie(abs(b["fondu_ha"]) > 3.0 * abs(b["fondu_fond"]),
             "fondu FAIBLE au fond, FORT en zone Ha (appariement correct)")


# ------------------------------------------------------------------- main ---
def main(argv=None):
    p = argparse.ArgumentParser(
        description="Mesure des echelles s (Ha) / R (rouge du composite) "
                    "avant J3bis.")
    p.add_argument("--canaux", help="dossier des canal_<role>.fit")
    p.add_argument("--composite", default=None,
                   help="fichier lineaire enregistre, pour CONTROLER le rejeu")
    p.add_argument("--mode", default="ajout_rouge",
                   choices=("ajout_rouge", "fondu_rouge", "ecran_rouge",
                            "eclaircir_rouge", "ha_luminance"))
    p.add_argument("--poids", type=float, default=1.5,
                   help="poids de la fusion J2 (1,5 sur M33 ; defaut 1,0)")
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--q", type=float, default=Q_HA_DEFAUT)
    p.add_argument("--sans-continuum", action="store_true")
    p.add_argument("--sans-recentrer", action="store_true")
    p.add_argument("--norm-commune", action="store_true")
    p.add_argument("--lissage-halos", action="store_true",
                   help="case 117d cochee (par defaut : decochee = sigma 0)")
    p.add_argument("--autotest", action="store_true")
    a = p.parse_args(argv)

    if a.autotest:
        autotest()
        return 0
    if not a.canaux:
        p.error("--canaux DOSSIER est requis (ou --autotest)")

    print("Couches lues :")
    canaux, composition = charge(a.canaux)
    continuum = not a.sans_continuum
    recentrer = not a.sans_recentrer
    sigma_l = None if a.lissage_halos else 0.0
    print(f"  composition rejouee : {composition}")
    print(f"  reglages : mode={a.mode} poids={a.poids} alpha={a.alpha} q={a.q} "
          f"continuum={continuum} recentrer={recentrer} "
          f"halos={a.lissage_halos} norm_commune={a.norm_commune}")

    if a.composite:
        controles(canaux, composition, a.composite, a.mode, a.poids, a.alpha,
                  a.q, continuum, recentrer, sigma_l, a.norm_commune)

    s, R, bornes, echelle = signal_et_rouge(
        canaux, composition, q=a.q, continuum=continuum, recentrer=recentrer,
        sigma_l=sigma_l, normalisation_commune=a.norm_commune)
    print("\n  bornes de normalisation (CHAQUE role a les siennes) :")
    for role, (lo, hi) in bornes.items():
        print(f"    {role:<2} lo={lo:.6f}  hi={hi:.6f}  amplitude={hi - lo:.6f}")
    fz, fond_r = rapport(s, R, a.alpha)
    apres_appariement(s, R, a.alpha, fz, fond_r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
