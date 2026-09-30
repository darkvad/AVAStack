# -*- coding: utf-8 -*-
r"""POURQUOI L'EMPILEMENT SHO RESTE VERT — mesure sur les BRUTES RÉELLES.

Constat d'Alain (30/09/2026, capture v2.48.0 en chantier) : avec la
préservation de L* activée, la nébuleuse N'EST PLUS ÉTEINTE (la correction
principale fonctionne) — mais elle reste VERTE, « il manque le doré ».

Ce diagnostic mesure, sur les brutes de la MÊME session live (les dossiers
`compo_dossier_*` de config.json), ce qui produit le vert et ce qui peut le
faire virer au doré :

  [1] rapports PHYSIQUES des trois bandes dans la nébuleuse (SII/Ha, OIII/Ha) ;
  [2] reproduction de la chaîne de la capture (neutralisation → chroma →
      étirement VeraLux → SCNR → démagenta) et son bilan de teintes ;
  [3] balayage de la FORCE du SCNR (0 → 1) : teintes, R:G:B, L* ;
  [4] effet propre du DÉMAGENTA sur la nébuleuse ;
  [5] le levier « étirement PAR CANAL » (moteur appliqué canal par canal) ;
  [6] le gain ROUGE qu'il faudrait pour que R atteigne G (le « doré »).

Usage : python bancs/_diag_couleur_dore_jalon85.py [--dossier-src RACINE]
        (défaut : les dossiers compo_dossier_* lus dans config.json)
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import argparse
import glob
import os
import sys
import tempfile
import time

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing import couleurs as coul
from avastack.processing import composition as compo
from avastack.processing import stacking as _stacking
from avastack.processing import veralux as vl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------- utilitaires
BANDES = (("rouge/orange (doré)", -25.0, 25.0),
          ("jaune (doré clair)", 25.0, 50.0),
          ("vert", 60.0, 160.0),
          ("cyan", 160.0, 200.0),
          ("bleu", 200.0, 260.0),
          ("magenta/violet", 260.0, 335.0))


def teintes(im, masque):
    """Répartition des TEINTES (degrés HSV OpenCV) d'un masque + R:G:B + L*."""
    x = np.clip(np.asarray(im, np.float32), 0.0, 1.0)
    hsv = cv2.cvtColor(x, cv2.COLOR_RGB2HSV)
    h = hsv[..., 0][masque]
    l_s = cv2.cvtColor(x, cv2.COLOR_RGB2LAB)[..., 0][masque]
    tot = max(1, h.size)
    parts = []
    for nom, a, b in BANDES:
        if a < 0:
            n = int((h < b).sum() + (h >= 360.0 + a).sum())
        else:
            n = int(((h >= a) & (h < b)).sum())
        parts.append((nom, 100.0 * n / tot))
    rgb = x[masque].mean(axis=0)
    rgb = rgb / max(1e-9, float(rgb[0]))          # normalisé sur le ROUGE
    dore = 100.0 * float((x[..., 0][masque] > x[..., 1][masque]).mean())
    return parts, rgb, float(l_s.mean()), float(hsv[..., 1][masque].mean()), dore


def ligne(nom, im, masque, extra=""):
    parts, rgb, l_s, sat, dore = teintes(im, masque)
    txt = "  ".join(f"{n.split(' ')[0]} {v:4.1f}%" for n, v in parts)
    print(f"    {nom:<32} R:G:B 1:{rgb[1]:5.2f}:{rgb[2]:5.2f}  "
          f"R>V {dore:4.1f}%  L* {l_s:5.2f}  sat {sat:4.2f} | {txt}{extra}")


def masques_objet(im):
    """(nébuleuse, cœur) : seuils sur la luminance de l'image ÉTIRÉE."""
    lum = im.mean(axis=2)
    return lum > np.percentile(lum, 80), lum > np.percentile(lum, 95)


def boost_rouge_masque(im, gain, preserve_luminance=False):
    """PROPOSITION À L'ESSAI — boost du canal ROUGE (SII) PONDÉRÉ PAR LA
    LUMINANCE : le gain vaut `gain` sur l'objet et retombe à 1,0 dans le fond
    (poids linéaire entre le 40e et le 97e centile de luminance).

    POURQUOI un masque : mesuré plus haut dans ce diagnostic, un gain rouge
    GLOBAL dore l'objet MAIS teinte aussi le fond (R>V 97 % du fond à ×2,5) et
    les étoiles ; ici le fond garde exactement ses valeurs (poids 0), donc sa
    neutralité, et l'objet reçoit seul le SII supplémentaire.

    preserve_luminance : True → la L* CIE d'AVANT est rendue (même mécanique
    que le SCNR du jalon 85) : la teinte part vers le doré SANS gagner de
    lumière (équivalent d'une saturation sélective) ; False → le boost gagne
    aussi en luminance (comportement « boost SII » de Siril)."""
    a = np.asarray(im, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return a.copy()
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    bas = float(np.percentile(lum, 40.0))
    haut = float(np.percentile(lum, 97.0))
    poids = np.clip((lum - bas) / max(1e-6, haut - bas), 0.0, 1.0)
    out = a.copy()
    out[..., 0] = np.clip(a[..., 0] * (1.0 + (gain - 1.0) * poids), 0.0, 1.0)
    if preserve_luminance:
        out = coul._restaurer_luminance(
            a, out, np.abs(out - a).max(axis=2) > coul.SEUIL_REMISE_LUMINANCE)
    return out


# ------------------------------------------------------------------- données
def charger_canaux(racine):
    """Moyenne des brutes de chaque rôle — mise en CACHE locale (1 Go sur le
    NAS : on ne relit pas les dossiers à chaque essai)."""
    dossiers = {r: os.path.join(racine, d) for r, d in
                (("S2", "SII"), ("Ha", "Ha"), ("O3", "OIII"))}
    cache = os.path.join(tempfile.gettempdir(), "avastack_diag_dore")
    os.makedirs(cache, exist_ok=True)
    from astropy.io import fits
    canaux = {}
    for role, d in dossiers.items():
        dest = os.path.join(cache, f"moyenne_{role}.npy")
        if os.path.exists(dest):
            canaux[role] = np.load(dest, mmap_mode=None)
            print(f"    {role} : moyenne en cache {canaux[role].shape}")
            continue
        fichiers = sorted(f for f in glob.glob(os.path.join(d, "*.fit*"))
                          if os.path.isfile(f))
        if not fichiers:
            print(f"    {role} : AUCUNE brute dans {d}")
            continue
        t0 = time.perf_counter()
        s = None
        for i, f in enumerate(fichiers):
            a = fits.getdata(f, memmap=False).astype(np.float32)
            s = a if s is None else s + a
        canaux[role] = (s / float(len(fichiers))).astype(np.float32)
        np.save(dest, canaux[role])
        print(f"    {role} : {len(fichiers)} brutes moyennées en "
              f"{time.perf_counter() - t0:.1f} s {canaux[role].shape}")
    return canaux


def dossier_par_defaut():
    """Racine des brutes de la session live : les `compo_dossier_*` de
    config.json (le rôle 0 est `…/SII`, donc son parent est la racine)."""
    from avastack.config import CONFIG
    d = ""
    for i in range(4):
        v = (CONFIG.get(f"compo_dossier_{i}") or "").strip()
        if v and CONFIG.get(f"compo_role_{i}"):
            d = os.path.dirname(v)
            break
    return d


def apercu(im, largeur=1600):
    """Réduit à la largeur de l'APERÇU live (c'est l'échelle des mesures)."""
    h, w = im.shape[:2]
    if w <= largeur:
        return im
    f = largeur / float(w)
    return np.asarray(cv2.resize(im, None, fx=f, fy=f,
                                 interpolation=cv2.INTER_AREA), np.float32)


def chaine_avant_etirement(petit, chroma_force=0.6, neutre=True):
    """Ce que la chaîne live fait AVANT le moteur : neutralisation du fond
    puis réduction du bruit chromatique (v2.36.1 / v2.37.0)."""
    x = petit
    gains = None
    if neutre:
        gains = coul.gains_fond(x)
        if gains is not None and not np.allclose(gains, 1.0, atol=1e-4):
            x = coul.neutraliser_fond(x)
        else:
            gains = None
    if chroma_force > 0:
        rayon = coul.rayon_chroma_apercu(x.shape[1] / 3856.0, rayon=3.0)
        x = coul.reduire_bruit_chroma(x, force=chroma_force, rayon=rayon)
    return x, gains


def etirer(x, target_bg=0.16):
    return vl.etirer(x, mode=vl.MODE_TARGET_BG, target_bg=target_bg)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dossier-src", default=None)
    ap.add_argument("--target-bg", type=float, default=0.16)
    a = ap.parse_args()
    racine = a.dossier_src or dossier_par_defaut()
    print(f"Brutes de la session live : {racine}")
    if not racine or not os.path.isdir(racine):
        print("  ARRÊT : dossiers de brutes introuvables")
        return 1
    canaux = charger_canaux(racine)
    if len(canaux) != 3:
        print("  ARRÊT : il faut les trois rôles (SII, Ha, OIII)")
        return 1

    # ======================================== [1] rapports PHYSIQUES des bandes
    print("\n[1] RAPPORTS PHYSIQUES des trois bandes DANS la nébuleuse "
          "(brutes 300 s, même gain, même télescope)")
    lum = np.mean([np.asarray(c, np.float32) for c in canaux.values()], axis=0)
    neb = lum > np.percentile(lum, 80)
    ciel = lum < np.percentile(lum, 25)
    flux = {}
    for r, im in canaux.items():
        v = np.asarray(im, np.float32)
        c, n = float(np.median(v[ciel])), float(np.median(v[neb]))
        flux[r] = n - c
        print(f"    {r} : ciel {c:9.2f}  nébuleuse {n:9.2f}  "
              f"FLUX (nébuleuse − ciel) {n - c:9.2f}")
    print(f"    → SII/Ha = {flux['S2'] / flux['Ha']:.3f} · "
          f"OIII/Ha = {flux['O3'] / flux['Ha']:.3f}")
    print(f"    → le canal du ROUGE est alimenté par SII : il lui manque "
          f"{flux['Ha'] / max(flux['S2'], 1e-9):.2f}× le flux de Ha pour "
          f"atteindre le vert, "
          f"{flux['O3'] / max(flux['S2'], 1e-9):.2f}× pour atteindre le bleu")

    # =========================================== [2] la chaîne de la capture
    print("\n[2] CHAÎNE DE LA CAPTURE (fond → chroma → étirement VeraLux → "
          "SCNR 0,35 → démagenta 1,00, préservation de L*)")
    resultats = {}
    for mode in ("par canal (défaut)", "échelle commune"):
        commun = mode == "échelle commune"
        composite = compo.composer(canaux, "SHO", normalisation_commune=commun)
        petit = apercu(np.asarray(composite, np.float32))
        avant, gains = chaine_avant_etirement(petit)
        etire, logd, _ = etirer(avant, a.target_bg)
        m_neb, m_coeur = masques_objet(etire)
        print(f"  --- normalisation {mode} (logD {logd:.3f})")
        if gains is not None:
            print(f"      gains de neutralisation du fond : "
                  f"R {gains[0]:.3f} · V {gains[1]:.3f} · B {gains[2]:.3f}")
        ligne("étirement seul", etire, m_neb)
        chaine = coul.scnr(etire, amount=0.35, preserve_luminance=True)
        chaine = coul.demagenta(chaine, amount=1.0, preserve_luminance=True)
        ligne("capture (SCNR 0,35 + démagenta)", chaine, m_neb)
        ligne("  dont le CŒUR (5 % les plus clairs)", chaine, m_coeur)
        resultats[mode] = (chaine, m_neb, etire, avant, petit)

    etire, m_neb, avant = resultats["par canal (défaut)"][2], \
        resultats["par canal (défaut)"][1], resultats["par canal (défaut)"][3]

    # ==================================================== [3] force du SCNR
    print("\n[3] EFFET DE LA FORCE DU SCNR (préservation de L* ON, "
          "démagenta 1,00) — masque de la nébuleuse")
    for force in (0.0, 0.2, 0.35, 0.5, 0.75, 1.0):
        y = coul.scnr(etire, amount=force, preserve_luminance=True)
        y = coul.demagenta(y, amount=1.0, preserve_luminance=True)
        ligne(f"force {force:.2f}", y, m_neb)

    # ========================================================= [4] démagenta
    print("\n[4] EFFET PROPRE DU DÉMAGENTA (SCNR 0,35 fixe)")
    y = coul.scnr(etire, amount=0.35, preserve_luminance=True)
    ligne("sans démagenta", y, m_neb)
    ligne("avec démagenta 1,00",
          coul.demagenta(y, amount=1.0, preserve_luminance=True), m_neb)

    # ============================================ [5] étirement PAR CANAL
    print("\n[5] LEVIER « ÉTIREMENT PAR CANAL » (moteur appliqué canal par "
          "canal, même fond visé)")
    colonnes = []
    for i in range(3):
        e, lg, _ = etirer(np.ascontiguousarray(avant[..., i]), a.target_bg)
        colonnes.append(e)
        print(f"      canal {'RVB'[i]} : logD {lg:.3f}")
    par_canal = np.stack(colonnes, axis=-1).astype(np.float32)
    m2, _ = masques_objet(par_canal)
    ligne("étirement par canal", par_canal, m2)
    y = coul.scnr(par_canal, amount=0.35, preserve_luminance=True)
    ligne("  + SCNR 0,35", y, m2)
    ligne("  + SCNR 0,35 + démagenta",
          coul.demagenta(y, amount=1.0, preserve_luminance=True), m2)

    # ================================================ [6] gain rouge du doré
    print("\n[6] CE QU'IL FAUDRAIT POUR QUE LE ROUGE DÉPASSE LE VERT (doré)")
    for nom, im, m in (("étirement seul", etire, m_neb),
                       ("SCNR 1,00", coul.scnr(etire, 1.0, True), m_neb),
                       ("par canal", par_canal, m2),
                       ("par canal + SCNR 0,35", y, m2)):
        rgb = np.clip(im, 0, 1)[m].mean(axis=0)
        print(f"    {nom:<24} R:G:B 1:{rgb[1] / rgb[0]:5.2f}:"
              f"{rgb[2] / rgb[0]:5.2f}  → gain rouge pour R = G : "
              f"{rgb[1] / rgb[0]:5.2f}× ; pour R = 1,3·G : "
              f"{1.3 * rgb[1] / rgb[0]:5.2f}×")

    # ================================= [7] OÙ appliquer un boost du ROUGE
    print("\n[7] BOOST DU ROUGE (SII) : AVANT ou APRÈS l'étirement ? — la "
          "neutralisation du fond est un gain GLOBAL par canal, calibré sur "
          "le ciel : elle peut ANNULER un boost appliqué avant elle")
    composite = compo.composer(canaux, "SHO")
    petit = apercu(np.asarray(composite, np.float32))
    for quand in ("avant (linéaire)", "après l'étirement"):
        for gain in (1.0, 1.5, 2.0, 2.5):
            x = np.array(petit, np.float32)
            if quand.startswith("avant"):
                x[..., 0] *= gain
            av, g = chaine_avant_etirement(x)
            e, lg, _ = etirer(av, a.target_bg)
            if quand.startswith("après"):
                e = np.array(e, np.float32)
                e[..., 0] = np.clip(e[..., 0] * gain, 0.0, 1.0)
            z = coul.scnr(e, amount=0.35, preserve_luminance=True)
            z = coul.demagenta(z, amount=1.0, preserve_luminance=True)
            mm, mc = masques_objet(z)
            ligne(f"{quand} ×{gain:.1f}", z, mm)
            ligne("        fond (25 % les plus sombres)", z,
                  z.mean(axis=2) < np.percentile(z.mean(axis=2), 25))

    # ================== [8] LA RECETTE « BOOST SII + OFFSET (Linear Fit) »
    print("\n[8] RECETTE AVEC L'OUTILLAGE EXISTANT : gain R (SII) × N PUIS "
          "recalage « Linear Fit (offset) » — un point noir PAR CANAL : le fond "
          "redevient neutre, l'OBJET garde son boost")
    for gain in (1.0, 1.5, 2.0, 2.5, 3.0):
        x = compo.appliquer_gains(np.array(petit, np.float32),
                                  {"R": gain, "G": 1.0, "B": 1.0})
        xf, diagf = _stacking.aligner_canaux(x, mode="offset")
        av, g = chaine_avant_etirement(xf)
        e, lg, _ = etirer(av, a.target_bg)
        z = coul.scnr(e, amount=0.35, preserve_luminance=True)
        z = coul.demagenta(z, amount=1.0, preserve_luminance=True)
        mm, _ = masques_objet(z)
        dec = "" if diagf is None else ("  offset R "
                                        f"{diagf['offsets'][0]:+.4f} · B "
                                        f"{diagf['offsets'][2]:+.4f}")
        ligne(f"R ×{gain:.1f} + offset", z, mm, dec)
        ligne("        fond (25 % les plus sombres)", z,
              z.mean(axis=2) < np.percentile(z.mean(axis=2), 25))

    # ============================ [9] saturation par couleur (curseur rouge)
    print("\n[9] CURSEUR « SATURATION PAR COULEUR » (R) : peut-il créer du doré "
          "sur une nébuleuse verte ?")
    from avastack.processing import display as _disp
    base = coul.demagenta(coul.scnr(etire, 0.35, True), 1.0, True)
    for g in ((1.0, 1.0, 1.0), (2.0, 1.0, 1.0), (3.0, 1.0, 1.0)):
        ligne(f"saturation rouge ×{g[0]:.1f}",
              _disp.saturation_canaux(base, g), m_neb)

    # ============ [10] TA RECETTE (capture du 30/09 22:09) PUIS LA PROPOSITION
    print("\n[10] TA RECETTE (Linear Fit « GAIN + OFFSET », SCNR décoché) — puis "
          "la PROPOSITION : boost du rouge MASQUÉ à l'objet")

    def chaine_fit(x0, fit_mode):
        """Chaîne live AVANT le moteur : neutralisation → Linear Fit → chroma
        (c'est l'ordre réel du code : _equilibrer puis _recaler_fit dans
        mean(), la réduction chroma venant ensuite au rendu)."""
        x = np.array(x0, np.float32)
        g = coul.gains_fond(x)
        if g is not None and not np.allclose(g, 1.0, atol=1e-4):
            x = coul.neutraliser_fond(x)
        d = None
        if fit_mode is not None:
            x, d = _stacking.aligner_canaux(np.ascontiguousarray(x),
                                            mode=fit_mode)
        rayon = coul.rayon_chroma_apercu(x.shape[1] / 3856.0, rayon=3.0)
        return coul.reduire_bruit_chroma(x, force=0.6, rayon=rayon), d

    h, w = petit.shape[:2]
    q = np.zeros((h, w), bool)
    q[h // 4:3 * h // 4, w // 4:3 * w // 4] = True
    lum_p = petit.mean(axis=2)
    print(f"    zone de calibration du fit (quart central, cf. stats_canaux) : "
          f"{100.0 * float((lum_p[q] > np.percentile(lum_p, 80)).mean()):.1f} % "
          f"de pixels d'OBJET — le fit se cale donc sur la NÉBULEUSE, pas sur "
          f"le ciel")

    bases = {}
    for mode in (None, "offset", "gain_offset"):
        av, d = chaine_fit(petit, mode)
        e, lg, _ = etirer(av, a.target_bg)
        z = coul.demagenta(e, amount=1.0, preserve_luminance=True)   # SCNR OFF
        bases[mode] = z
        dec = "" if d is None else (
            "  gains R %.3f · B %.3f | offsets R %+.4f · B %+.4f"
            % (d["gains"][0], d["gains"][2], d["offsets"][0], d["offsets"][2]))
        ligne(f"fit {'AUCUN' if mode is None else mode} — nébuleuse", z, m_neb,
              dec)
        ligne("        FOND (25 % les plus sombres)", z,
              z.mean(axis=2) < np.percentile(z.mean(axis=2), 25))

    print("    → PROPOSITION sur la base SANS fit (le fit n'est plus nécessaire "
          "si le rouge est boosté à l'objet) : le FOND doit rester neutre")
    for preserve in (False, True):
        for gain in (1.5, 2.0, 2.5, 3.0, 4.0):
            z = boost_rouge_masque(bases[None], gain, preserve)
            mm, _ = masques_objet(z)
            nom = f"boost ×{gain:.1f}" + (" + L* gardée" if preserve else "")
            ligne(f"{nom} — nébuleuse", z, mm)
            ligne("        FOND (25 % les plus sombres)", z,
                  z.mean(axis=2) < np.percentile(z.mean(axis=2), 25))

    print("    → et posé APRÈS ta recette (fit gain+offset) : les deux se "
          "cumulent-ils proprement ?")
    for gain in (1.5, 2.0):
        z = boost_rouge_masque(bases["gain_offset"], gain, False)
        mm, _ = masques_objet(z)
        ligne(f"fit gain_offset + boost ×{gain:.1f} — nébuleuse", z, mm)
        ligne("        FOND (25 % les plus sombres)", z,
              z.mean(axis=2) < np.percentile(z.mean(axis=2), 25))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
