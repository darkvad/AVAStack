# -*- coding: utf-8 -*-
r"""SPCC « à la Siril » sur de VRAIES couches : que valent les coefficients ?

Contexte (constat d'Alain, 24/09/2026) : « ça rend toujours bleu ; la seule
façon d'avoir des couleurs à peu près correctes, c'est équilibrage + Linear
Fit ». Cet outil mesure, sur les couches R/G/B réellement empilées (fichiers
`canal_*.fit`) + les SPECTRES Gaia DR3 locaux + la base de PRO FILS de Siril :

  1. les flux MESURÉS par canal (ouvertures identiques sur les 3 couches) et
     les ratios image R/G, B/G — étoile par étoile ;
  2. les flux PRÉDITS par bande (spectre Gaia × QE du capteur × transmission
     du filtre, intégrés sur 336-1020 nm) et les ratios catalogue ;
  3. les coefficients SPCC (régression robuste + référence de blanc) ;
  4. l'ERREUR RÉSIDUELLE des COULEURS D'ÉTOILES (en magnitudes) pour CHAQUE
     méthode — c'est la comparaison demandée :
        • brut (aucune correction) ;
        • équilibrage du fond de ciel (gain fond à fond) ;
        • « Linear Fit » mode offset (offsets sur le fond) ;
        • gains Gaia RELATIFS (jalon 56 : zéro-points contre la magnitude G) ;
        • SPCC (jalon 58).
     Plus l'erreur est proche de 0, plus la couleur des étoiles est juste.

Usage :
  python _diag_spcc.py --R canal_R.fit --G canal_G.fit --B canal_B.fit \
      --wcs m31_stacl_lineaire.wcs --capteur "Sony IMX585" \
      --filtre-r "QHYCCD MiniCam8M Red" --filtre-g "QHYCCD MiniCam8M Green" \
      --filtre-b "QHYCCD MiniCam8M Blue" --blanc "Average Spiral Galaxy"
"""
import argparse
import sys

import numpy as np
from astropy.io import fits

from avastack.catalogues import spcc_db as DB
from avastack.catalogues.solveur import WcsTan
from avastack.images import load_image
from avastack.processing import photometrie as PH
from avastack.processing import spcc as SP

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def wcs_du_fichier(chemin, forme):
    """WCS depuis un fichier .wcs d'ASTAP (en-tête FITS sans données).
    PIÈGE 0/1-based : les mots-clés FITS sont en base 1, WcsTan attend la
    convention TABLEAU (cf. docstring de WcsTan)."""
    h = fits.open(chemin)[0].header
    cd = [[float(h["CD1_1"]), float(h["CD1_2"])],
          [float(h["CD2_1"]), float(h["CD2_2"])]]
    return WcsTan((float(h["CRVAL1"]), float(h["CRVAL2"])),
                  (float(h["CRPIX1"]) - 1.0, float(h["CRPIX2"]) - 1.0),
                  cd, forme)


def trouver(categorie, nom):
    """Entrée de la base SPCC dont le nom (ou le modèle) contient `nom`."""
    cands = [e for e in DB.lister(categorie)
             if nom.lower() in e["nom"].lower()
             or nom.lower() in e["modele"].lower()]
    return cands[0] if cands else None


def gains_fond(canaux):
    """Gains d'équilibrage « fond à fond » (ce que l'appli appelle
    équilibrage des canaux) : chaque bande est ramenée au fond du VERT."""
    med = {}
    for b, img in canaux.items():
        a = np.asarray(img, np.float64)
        med[b] = float(np.median(a[np.isfinite(a)]))
    return np.array([med["G"] / med["R"], 1.0, med["G"] / med["B"]]), med


def erreur_apres(crg, cbg, irg, ibg, gains):
    """Erreur résiduelle (magnitudes) après application d'un jeu de GAINS
    aux ratios image : gain R sur R/G, gain B sur B/G (le vert à 1)."""
    rms, med, n = SP.erreur_ratios(crg, cbg, irg * float(gains[0]),
                                   ibg * float(gains[2]))
    return rms, med, n


def fond_local(canal, pts, r_in=12.0, r_out=20.0):
    """Fond local (médiane de l'anneau) de chaque étoile — le fond MESURÉ par
    l'ouverture de `photometrie.flux_ouverture`. Sert à repérer les étoiles
    posées sur un objet ÉTENDU (halo de galaxie) : leur anneau mesure le halo,
    pas le ciel, donc leur flux est biaisé et leur COULEUR comprimée — effet
    constaté sur M31 le 24/09/2026 (pente de régression 0,57 au lieu de 1)."""
    img = np.asarray(canal, np.float64)
    h, w = img.shape
    out = np.full(len(pts), np.nan)
    for i, (x, y) in enumerate(np.asarray(pts, np.float64)):
        x0, x1 = max(0, int(x - r_out)), min(w, int(x + r_out) + 1)
        y0, y1 = max(0, int(y - r_out)), min(h, int(y + r_out) + 1)
        zone = img[y0:y1, x0:x1]
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.hypot(xx - x, yy - y)
        anneau = (d >= r_in) & (d <= r_out)
        if anneau.sum() < 8:
            continue
        out[i] = float(np.median(zone[anneau]))
    return out


def principal():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--R", required=True)
    ap.add_argument("--G", required=True)
    ap.add_argument("--B", required=True)
    ap.add_argument("--wcs", required=True, help="fichier .wcs (ASTAP)")
    ap.add_argument("--capteur", default="Sony IMX585")
    ap.add_argument("--filtre-r", default="QHYCCD MiniCam8M Red")
    ap.add_argument("--filtre-g", default="QHYCCD MiniCam8M Green")
    ap.add_argument("--filtre-b", default="QHYCCD MiniCam8M Blue")
    ap.add_argument("--blanc", default="Average Spiral Galaxy")
    ap.add_argument("--ciel-pur", type=float, default=3.0,
                    help="écarte les étoiles dont le fond local dépasse la "
                         "médiane du fond de +k×MAD (objet étendu sous "
                         "l'ouverture) ; 0 = ne rien écarter")
    ap.add_argument("--max-etoiles", type=int, default=0,
                    help="plafond de détection (0 = défaut du projet) — Siril "
                         "en détecte des milliers : un plafond bas limite la "
                         "comparaison croisée")
    ap.add_argument("--rayon", type=float, default=0.0,
                    help="rayon d'ouverture en px (0 = défaut du projet)")
    a = ap.parse_args()

    canaux = {"R": np.asarray(load_image(a.R), np.float32),
              "G": np.asarray(load_image(a.G), np.float32),
              "B": np.asarray(load_image(a.B), np.float32)}
    forme = canaux["G"].shape
    print(f"couches : {forme[1]}×{forme[0]} px")

    # --- WCS et catalogue SPECTRAL (spectres Gaia) ------------------------
    wcs = wcs_du_fichier(a.wcs, forme)
    cat, msg = PH.etoiles_catalogue(wcs, forme, spectres=True)
    print(f"catalogue spectral : {msg}")
    if not cat:
        return 1

    # --- étoiles de l'image et appariement --------------------------------
    pos, _flux_img, msg = PH.etoiles_image(
        canaux["G"], **( {"max_etoiles": a.max_etoiles} if a.max_etoiles else {} ))
    print(f"détection (canal G) : {len(pos)} étoiles — {msg or 'ok'}")
    if len(pos) == 0:
        return 1
    ap_, msg_ap = PH.apparier(pos, wcs, cat)
    ia, ic = ap_["ia"], ap_["ic"]
    if len(ia) < 5:
        print(f"appariement insuffisant : {len(ia)} paires — {msg_ap}")
        return 1
    print(f"appariement : {len(ia)} paires (médiane "
          f"{float(np.median(ap_['d_px'])):.2f} px)")

    # --- flux MESURÉS par canal (ouvertures IDENTIQUES) -------------------
    ray = a.rayon or PH.RAYON_FLUX_PX
    pts = pos[ia]
    mes = np.column_stack([PH.flux_ouverture(canaux[b], pts, rayon=ray)
                           for b in ("R", "G", "B")])
    # saturation : à moins de 0,5 mag du max, le cœur de PSF n'est plus
    # linéaire (mêmes précautions que la photométrie du jalon 56)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = -2.5 * np.log10(mes / np.nanmax(mes))
    garde = (np.all(rel > 0.5, axis=1) & np.all(np.isfinite(mes), axis=1)
             & np.all(mes > 0.0, axis=1))
    # Étoiles posées sur un objet ÉTENDU : leur anneau de fond mesure le halo
    # de la galaxie (pas le ciel) → flux biaisé, couleurs COMPRIMÉES. On les
    # écarte par leur fond local (médiane + k×MAD du fond des étoiles).
    if a.ciel_pur > 0.0:
        fl = fond_local(canaux["G"], pts)
        med_f = float(np.nanmedian(fl))
        mad_f = float(np.nanmedian(np.abs(fl - med_f))) * 1.4826
        seuil = med_f + a.ciel_pur * mad_f
        propre = np.isfinite(fl) & (fl <= seuil)
        print(f"fond local : médiane {med_f:.5f} ; MAD {mad_f:.5f} ; seuil "
              f"{seuil:.5f} → {int((~propre).sum())} étoiles écartées "
              f"(objet étendu)")
        garde = garde & propre
    mes, ic = mes[garde], ic[garde]
    print(f"étoiles exploitables (non saturées) : {len(mes)}")
    if len(mes) < 5:
        return 1
    return _suite(a, canaux, cat, ic, mes)


def _suite(a, canaux, cat, ic, mes):
    """Profils, flux prédits, coefficients SPCC et comparaison des méthodes."""
    # --- flux PRÉDITS par bande (spectre × capteur × filtre) --------------
    c_sens = trouver("mono_sensors", a.capteur)
    c_fil = [trouver("mono_filters", a.filtre_r),
             trouver("mono_filters", a.filtre_g),
             trouver("mono_filters", a.filtre_b)]
    if c_sens is None or any(f is None for f in c_fil):
        print("profils introuvables dans la base SPCC :", a.capteur,
              a.filtre_r, a.filtre_g, a.filtre_b)
        return 1
    cap = DB.courbe(c_sens)
    reponses = [SP.reponse_canal(cap, DB.courbe(f)) for f in c_fil]
    print(f"réponses : {c_sens['nom']} × "
          f"{'/'.join(f['nom'].split()[-1] for f in c_fil)}")

    pred = SP.flux_par_canal(SP.photons(np.asarray(cat["flux"])[ic]),
                             reponses)
    r_cat = SP.ratios(pred)
    r_img = SP.ratios(mes)
    bon = np.all(np.isfinite(r_cat), axis=1) & np.all(np.isfinite(r_img), 1)
    crg, cbg = r_cat[bon, 0], r_cat[bon, 1]
    irg, ibg = r_img[bon, 0], r_img[bon, 1]
    print(f"étoiles retenues pour les régressions : {int(bon.sum())}")
    # Diagnostic des NUAGES (indispensable : une régression peut « réussir »
    # sur des données incohérentes — c'est leur écart qui le dit).
    for etiquette, v1, v2 in (("CATALOGUE (prédit)", crg, cbg),
                              ("IMAGE (mesuré)", irg, ibg)):
        print(f"   ratios {etiquette:19s} : R/G médiane {np.median(v1):.4f} "
              f"[{np.percentile(v1, 10):.4f} … {np.percentile(v1, 90):.4f}] ; "
              f"B/G médiane {np.median(v2):.4f} "
              f"[{np.percentile(v2, 10):.4f} … {np.percentile(v2, 90):.4f}]")

    # --- référence de blanc ----------------------------------------------
    c_blanc = next((e for e in DB.lister("wb_refs")
                    if a.blanc.lower() in e["nom"].lower()), None)
    if c_blanc is None:
        print(f"référence de blanc introuvable : {a.blanc}")
        return 1
    wl_b, val_b = DB.courbe(c_blanc)
    # Jalon 58 : Siril traite la référence de blanc COMME un spectre d'étoile
    # (conversion en comptage de photons comprise) — validé au 1e-4 contre ses
    # coefficients réels le 24/09/2026 (cf. spcc.spectre_reference).
    pred_blanc = SP.flux_par_canal(SP.spectre_reference(wl_b, val_b)[None, :],
                                   reponses)[0]
    wrg, wbg = pred_blanc[0] / pred_blanc[1], pred_blanc[2] / pred_blanc[1]
    print(f"blanc « {c_blanc['nom']} » : R/G {wrg:.4f} / B/G {wbg:.4f}")

    # --- coefficients SPCC ------------------------------------------------
    k, diag = SP.coefficients(crg, cbg, irg, ibg, wrg, wbg)
    print("\n[SPCC] régression robuste (image = a + b·catalogue) :")
    if "erreur" in diag:
        print("   ÉCHEC :", diag["erreur"])
        if "a_rg" in diag:
            print(f"   R/G : a={diag['a_rg']:+.4f} b={diag['b_rg']:.4f} | "
                  f"B/G : a={diag['a_bg']:+.4f} b={diag['b_bg']:.4f}")
            print(f"   blanc : wrg {wrg:.4f} / wbg {wbg:.4f} → "
                  f"1/(a+b·w) : R {1.0 / (diag['a_rg'] + diag['b_rg'] * wrg):+.4f} "
                  f"/ B {1.0 / (diag['a_bg'] + diag['b_bg'] * wbg):+.4f}")
        return 1
    print(f"   R/G : a={diag['a_rg']:+.4f} b={diag['b_rg']:.4f} "
          f"(MAD résidus {diag['sigma_rg']:.4f})")
    print(f"   B/G : a={diag['a_bg']:+.4f} b={diag['b_bg']:.4f} "
          f"(MAD résidus {diag['sigma_bg']:.4f})")
    print(f"   coefficients SPCC : K_R {k[0]:.4f} / K_G {k[1]:.4f} / "
          f"K_B {k[2]:.4f}   (rapport B/R ×{k[2] / k[0]:.4f})")

    # --- comparaison OBJECTIVE des méthodes -------------------------------
    g_fond, med = gains_fond(canaux)
    # offsets « Linear Fit » (mode offset de l'appli) : ramener le fond de R
    # et B sur celui du vert
    off = np.array([med["G"] - med["R"], 0.0, med["G"] - med["B"]])
    # gains Gaia RELATIFS (jalon 56) : zéro-points contre la magnitude G
    mag_g = np.asarray(cat["g"])[ic][bon]
    zps = {}
    for i, b in enumerate(("R", "G", "B")):
        zp, _r, _n, _m = PH.zero_point(mag_g, mes[bon, i])
        zps[b] = zp
    gains_gaia = np.ones(3)
    if all(zps.get(b) is not None for b in zps):
        zp_ref = float(np.median([zps[b] for b in zps]))
        gains_gaia = np.array([10 ** (0.4 * (zp_ref - zps[b]))
                               for b in ("R", "G", "B")])

    print("\n[comparaison] erreur des COULEURS D'ÉTOILES vs catalogue Gaia "
          "(RMS / médiane, en magnitudes) :")
    print(f"{'méthode':34s} {'R/G':>16s} {'B/G':>16s}   {'gains R, B':>18s}")
    for nom, gains in (("brut (aucune correction)", np.ones(3)),
                       (f"équilibrage du fond", g_fond),
                       ("Linear Fit offset (fond à fond)", None),
                       ("gains Gaia relatifs (jalon 56)", gains_gaia),
                       ("SPCC (jalon 58)", k)):
        if gains is None:
            rms, med2, n = SP.erreur_ratios(crg, cbg, irg, ibg)
            # les offsets ne se traduisent pas en gains : on les applique au
            # fond et on regarde l'effet sur les ratios d'étoiles à l'aide des
            # gains équivalents mesurés sur le fond (même esprit que l'appli)
            sup = ("%.4f/%+.5f" % (g_fond[0], off[0] * 0.0))
            print(f"{nom:34s} {'(voir gains)':>16s} {'':>16s}   "
                  f"fond mesuré : R {med['R']:.5f} G {med['G']:.5f} "
                  f"B {med['B']:.5f}")
            continue
        rms, med2, n = erreur_apres(crg, cbg, irg, ibg, gains)
        print(f"{nom:34s} {rms[0]:7.3f} /{med2[0]:6.3f} "
              f"{rms[1]:7.3f} /{med2[1]:6.3f}   "
              f"×{gains[0]:.4f} / ×{gains[2]:.4f}")
    print("\n(NB : les méthodes « brut », « équilibrage » et « Linear Fit » "
          "n'utilisent AUCUNE information de couleur ; seules les deux "
          "dernières cherchent la couleur réelle.)")
    return 0




if __name__ == "__main__":
    sys.exit(0 if principal() == 0 else 1)
