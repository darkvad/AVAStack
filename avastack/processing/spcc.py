# -*- coding: utf-8 -*-
"""Calibration spectrophotométrique ABSOLUE « à la Siril » (jalon 58).

POURQUOI : la photométrie RELATIVE du jalon 56 (zéro-point par bande contre la
magnitude Gaia G) ne peut pas corriger la couleur d'une image multi-filtres —
G est une bande très large (330-1050 nm) et rien ne relie le flux d'une bande
instrumentale à celui d'une autre. Mesuré sur les couches réelles d'Alain
(24/09/2026) : dispersion des zéro-points croissante vers le bleu (R 0,162 /
G 0,233 / B 0,376 mag) et gains qui refroidissent l'image (R ×0,7665 /
B ×1,0426). La SPCC fait autrement : elle PRÉDIT le flux attendu dans CHAQUE
bande en multipliant le SPECTRE Gaia DR3 de chaque étoile (`xp_sampled`,
336-1020 nm par pas de 2 nm) par la RÉPONSE de la bande = QE du capteur ×
transmission du filtre, puis en intégrant. Les rapports prédits (R/G, B/G)
sont confrontés aux rapports MESURÉS, et une régression robuste donne les
coefficients — corrigés par une RÉFÉRENCE DE BLANC (couleur visée).

MODÈLE repris de Siril (src/algos/photometric_cc.c `get_spcc_white_balance_
coeffs` + src/algos/spcc.c, lu le 24/09/2026) :
  1. réponse du canal : R_c(λ) = QE(λ) · T_c(λ), interpolée sur la grille
     `xp_sampled` (interpolation LINÉAIRE : le projet n'a ni scipy ni GSL ;
     Siril interpole en Akima — écart négligeable sur les intégrales, cf.
     banc _diag_spcc) ; les courbes sont ramenées à ZÉRO hors de leur domaine
     mesuré (pas d'extrapolation numérique aux extrémités) ;
  2. flux Gaia → comptage de PHOTONS : Siril multiplie par λ puis normalise à
     500 nm (facteur PAR ÉTOILE, donc sans effet sur des ratios) ;
  3. flux attendu : F_c = ∫ R_c(λ)·S(λ) dλ (trapèzes) → ratios catalogue
     crg = F_R/F_G, cbg = F_B/F_G ;
  4. flux mesurés I_c (photométrie d'ouverture) → irg = I_R/I_G, ibg = I_B/I_G ;
  5. régression ROBUSTE par médianes répétées (Siegel) : irg = a + b·crg ;
  6. référence de BLANC (spectre de galaxie spirale moyenne par défaut),
     traitée comme un « spectre d'étoile » → wrg = W_R/W_G, wbg = W_B/W_G ;
  7. coefficients : k_R = 1/(a_RG + b_RG·wrg), k_G = 1,
     k_B = 1/(a_BG + b_BG·wbg), normalisés par le plus grand.

Aucune dépendance nouvelle : numpy seul (l'image et les catalogues sont lus
par les modules existants). Tout est PUR : ce module ne touche ni au disque
ni à l'UI, ce qui le rend directement testable au banc.
"""

import numpy as np

# Grille spectrale Gaia DR3 xp_sampled : 336 → 1020 nm par pas de 2 nm
# (343 points — identique à DTYPE_XPSAMP de catalogues/siril_cat.py).
GRILLE_WL = np.arange(336.0, 1021.0, 2.0)
XPSAMPLED_LEN = GRILLE_WL.size          # 343
# Indice de normalisation utilisé par Siril (xps->y[82] → 500 nm) : facteur
# PAR ÉTOILE, conservé pour la fidélité du modèle.
INDICE_NORM = 82


def sur_grille(wl, val):
    """Courbe (nm, valeurs) → valeurs sur `GRILLE_WL`, interpolées
    linéairement et RAMENÉES À ZÉRO hors de son domaine mesuré.

    Pourquoi zéro hors domaine : Siril laisse GSL Akima EXTRAPOLER (pente des
    derniers points), ce qui peut fabriquer une réponse fantôme en dessous de
    380 nm (début des profils capteurs) ou au-delà de 1000 nm. Multipliée par
    la QE puis intégrée, elle faussait les ratios ; physiquement, aucune
    donnée = aucune réponse connue."""
    if wl is None or val is None or len(wl) < 2:
        return np.zeros(XPSAMPLED_LEN, dtype=np.float64)
    wl = np.asarray(wl, dtype=np.float64)
    val = np.asarray(val, dtype=np.float64)
    out = np.interp(GRILLE_WL, wl, val, left=0.0, right=0.0)
    return out


def reponse_canal(capteur, filtre):
    """Réponse d'un canal : QE du capteur × transmission du filtre, sur la
    grille xp_sampled. `capteur` et `filtre` sont des couples (wl, val) issus
    de `catalogues.spcc_db.courbe` (le filtre peut être None : mode
    narrowband ou canal sans filtre). → (343,) float64."""
    r = sur_grille(*capteur) if capteur else np.ones(XPSAMPLED_LEN)
    if filtre:
        r = r * sur_grille(*filtre)
    return r


def spectre_reference(wl, val):
    """Spectre de RÉFÉRENCE DE BLANC prêt à intégrer : interpolation sur la
    grille spectrale PUIS conversion en comptage de photons, exactement comme
    les spectres d'ÉTOILES (× λ).

    VÉRIFIÉ CONTRE SIRIL le 24/09/2026 (banc _diag_spcc + log réel d'Alain) :
    avec les réponses Sony IMX585 × filtres QHYCCD MiniCam8M R/G/B, cette
    fonction donne w_R/G = 1,2954 et w_B/G = 0,8331 ; les valeurs DÉDUITES des
    coefficients K0/K1/K2 réellement produits par Siril (1,000 / 0,923 / 0,866,
    via k_R = 1/(a + b·w) et K = k/max) sont 1,2953 / 0,8332 — accord à 1e-4.
    SANS la conversion on obtenait 1,0943 / 1,0128, soit des coefficients SPCC
    quasi neutres et une correction de couleur fausse d'environ 20 %."""
    return sur_grille(wl, val) * GRILLE_WL


def photons(spectres):
    """Flux Gaia (N, 343) — W·m⁻²·nm⁻¹ — → comptage de PHOTONS RELATIF.

    Siril (`flux_to_relcount`) multiplie par λ (un photon de grande longueur
    d'onde porte moins d'énergie) puis normalise à 500 nm.

    PIÈGE MESURÉ AU BANC DU JALON 58 (24/09/2026) : la DIVISION est bien un
    facteur PAR ÉTOILE (neutre sur les ratios), mais la MULTIPLICATION par λ est
    À L'INTÉRIEUR des intégrales — donc ∫S·λ·R dλ / ∫S·λ·G dλ ≠ ∫S·R/∫S·G :
    la conversion change les ratios prédits de ~18 % selon la couleur. Un banc
    qui génère son image sans cette conversion (ou qui compare des ratios
    calculés de part et d'autre) trouve des pentes fausses d'environ 20 %."""
    s = np.asarray(spectres, dtype=np.float64)
    if s.ndim == 1:
        s = s[None, :]
    s = s * GRILLE_WL[None, :]
    return s / np.where(s[:, INDICE_NORM:INDICE_NORM + 1] == 0.0, 1.0,
                        s[:, INDICE_NORM:INDICE_NORM + 1])


def _trapeze(y, x, axis=-1):
    """Intégration par trapèzes, COMPATIBLE numpy 1 ET 2.

    PIÈGE RÉEL (constaté par Alain le 24/09/2026, Python 3.14 + numpy récent) :
    `np.trapz` a été renommé `np.trapezoid` en numpy 2.0 puis SUPPRIMÉ des
    versions suivantes — la SPCC s'arrêtait sur « module 'numpy' has no attribute
    'trapz' » (erreur attrapée proprement, mais aucune calibration). On prend
    donc `trapezoid` quand il existe, `trapz` sinon : les deux donnent le même
    résultat au bit près (même algorithme)."""
    f = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)
    return f(y, x, axis=axis)


def flux_par_canal(spectres, reponses):
    """Intégrale (trapèzes) de réponse × spectre par canal.
    → (N, 3) float64 : [R, G, B] ; NaN si une intégrale est nulle ou non
    finie (canal inexploitable — jamais une valeur inventée)."""
    s = np.asarray(spectres, dtype=np.float64)
    if s.ndim == 1:
        s = s[None, :]
    out = np.full((s.shape[0], 3), np.nan)
    for c in range(3):
        out[:, c] = _trapeze(s * reponses[c][None, :], GRILLE_WL, axis=1)
    mauvais = ~np.isfinite(out) | (out <= 0.0)
    if mauvais.any(axis=1).any():
        out[np.any(mauvais, axis=1)] = np.nan
    return out


def ratios(flux, canaux=(0, 2)):
    """Ratios d'un tableau (N, 3) par rapport au VERT → (N, 2) [R/G, B/G].
    Lignes inexploitables (NaN) → NaN."""
    f = np.asarray(flux, dtype=np.float64)
    g = f[:, 1]
    out = np.column_stack([f[:, canaux[0]] / g, f[:, canaux[1]] / g])
    return out


def regression_mediane(x, y):
    """Régression linéaire ROBUSTE par médianes répétées (Siegel 1982),
    celle de Siril (`repeated_median_fit`, src/algos/fitting.c, lu le
    24/09/2026) :
        b = médiane_i ( médiane_{j≠i} (y_j - y_i)/(x_j - x_i) )
        a = médiane_i ( y_i - b·x_i )
    Insensible aux étoiles aberrantes (variabilité, saturation, fusions
    apparentes) — indispensable ici : le nuage contient toujours quelques
    points aberrants que l'astrométrie n'exclut pas.
    → (a, b, ecart) : `ecart` = MAD des résidus (diagnostic affichable) ;
    (nan, nan, nan) si moins de 3 points exploitables (Siril exige ≥ 3)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    bon = np.isfinite(x) & np.isfinite(y)
    x, y = x[bon], y[bon]
    n = x.size
    if n < 3:
        return float("nan"), float("nan"), float("nan")
    # pentes de chaque point vers tous les autres (vecteurisé)
    dx = x[None, :] - x[:, None]
    dy = y[None, :] - y[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        pentes = np.where(dx != 0.0, dy / dx, np.nan)
    med_i = np.nanmedian(pentes, axis=1)
    pente = float(np.median(med_i[np.isfinite(med_i)]))
    ordonnee = float(np.median(y - pente * x))
    residus = y - (ordonnee + pente * x)
    ecart = float(np.median(np.abs(residus - np.median(residus))) * 1.4826)
    return ordonnee, pente, ecart


def coefficients(crg, cbg, irg, ibg, wrg, wbg):
    """Coefficients SPCC (R, G, B) — formules de Siril :
        k_R = 1/(a_RG + b_RG·wrg) ; k_G = 1 ; k_B = 1/(a_BG + b_BG·wbg)
    puis division par le plus grand (le vert reste à 1, comme Siril).

    Entrées : ratios CATALOGUE par étoile (crg, cbg), ratios IMAGE par étoile
    (irg, ibg), ratios de la RÉFÉRENCE DE BLANC (wrg, wbg).
    → (k (3,) float64, diag dict) ; k vide (nan) si la régression échoue ou
    donne un coefficient négatif/nul (Siril : « kw contains negative values »
    → échec, jamais un gain négatif appliqué à l'image)."""
    a_rg, b_rg, s_rg = regression_mediane(crg, irg)
    a_bg, b_bg, s_bg = regression_mediane(cbg, ibg)
    if not all(np.isfinite(v) for v in (a_rg, b_rg, a_bg, b_bg)):
        return np.full(3, np.nan), {"erreur": "régression impossible "
                                             "(moins de 3 étoiles valides)"}
    k_r = 1.0 / (a_rg + b_rg * wrg)
    k_b = 1.0 / (a_bg + b_bg * wbg)
    k = np.array([k_r, 1.0, k_b], dtype=np.float64)
    if not np.all(np.isfinite(k)) or np.any(k <= 0.0):
        return np.full(3, np.nan), {
            "erreur": "coefficient négatif ou nul (vérifier capteur/filtres)",
            "a_rg": a_rg, "b_rg": b_rg, "a_bg": a_bg, "b_bg": b_bg}
    k = k / k.max()
    diag = {"a_rg": a_rg, "b_rg": b_rg, "sigma_rg": s_rg,
            "a_bg": a_bg, "b_bg": b_bg, "sigma_bg": s_bg,
            "wrg": float(wrg), "wbg": float(wbg)}
    return k, diag


def erreur_ratios(crg, cbg, irg, ibg):
    """Erreur résiduelle des ratios image vs catalogue, en MAGNITUDES
    équivalentes (log10) — c'est la mesure OBJECTIVE de la qualité de
    couleur, celle que la SPCC minimise. → (rms (2,), mediane (2,), n)."""
    import math
    crg = np.asarray(crg, np.float64)
    cbg = np.asarray(cbg, np.float64)
    irg = np.asarray(irg, np.float64)
    ibg = np.asarray(ibg, np.float64)
    bon = (np.isfinite(crg) & np.isfinite(irg) & (crg > 0) & (irg > 0)
           & np.isfinite(cbg) & np.isfinite(ibg) & (cbg > 0) & (ibg > 0))
    if not bon.any():
        return np.zeros(2), np.zeros(2), 0
    d_r = np.abs(2.5 * np.log10(irg[bon] / crg[bon]))
    d_b = np.abs(2.5 * np.log10(ibg[bon] / cbg[bon]))
    rms = np.array([math.sqrt(float((d_r ** 2).mean())),
                    math.sqrt(float((d_b ** 2).mean()))])
    med = np.array([float(np.median(d_r)), float(np.median(d_b))])
    return rms, med, int(bon.sum())


def coherence_bandes(noms_fil):
    """Contrôle de COHÉRENCE des trois profils de filtres → liste d'avis.

    Constat réel (24/09/2026, capture d'Alain) : l'UI affichait « Filtre R :
    QHYCCD MiniCam8M Luminance » — un profil de LUMINANCE (bande large) ou deux
    profils identiques donnent des coefficients FAUX ; mieux vaut le dire avant
    de calculer que de rendre un chiffre trompeur. Message partagé par le module
    (diagnostic) et par l'UI (affichage immédiat, sans attendre une mesure)."""
    bas = [str(n).lower() for n in noms_fil if n]
    avis = []
    if len(set(bas)) < 3:
        avis.append("profils de filtres répétés : les trois canaux doivent "
                    "avoir des filtres distincts")
    if any(("luminance" in n) or n.strip() == "l" or n.strip().endswith(" l")
           or "-l" in n for n in bas):
        avis.append("un profil de LUMINANCE est utilisé comme filtre de "
                    "couleur : les coefficients seraient faux")
    return avis


def base_presente():
    """La base SPCC de Siril est-elle installée (profils de capteurs, de
    filtres et références de blanc lisibles) ? L'UI s'en sert pour activer ou
    non sa case : sans base, aucune SPCC n'est possible — et le dire est plus
    honnête qu'échouer silencieusement à chaque tentative."""
    try:
        from ..catalogues import spcc_db as DB
        return bool(DB.lister("mono_sensors")) and bool(DB.lister("wb_refs"))
    except Exception:
        return False


def noms_base():
    """Noms des profils de la base Siril, pour peupler les sélecteurs de l'UI
    → {"capteur": [...], "filtres": [...], "blancs": [...]} (listes vides si
    la base est absente)."""
    vide = {"capteur": [], "filtres": [], "blancs": []}
    try:
        from ..catalogues import spcc_db as DB
        return {"capteur": [e["nom"] for e in DB.lister("mono_sensors")],
                "filtres": [e["nom"] for e in DB.lister("mono_filters")],
                "blancs": [e["nom"] for e in DB.lister("wb_refs")]}
    except Exception:
        return vide


# --- Mesure sur une image réelle (orchestration réutilisable) ----------------
# Réglages surchargeables par les bancs (même convention que photometrie).
RAYON_FLUX_PX = 3.0          # rayon d'ouverture du flux (px)
ANNEAU_FOND = (5.0, 8.0)     # anneau de mesure du fond local (px)
MAX_ETOILES = 300            # étoiles les plus brillantes analysées
MARGE_SATURATION = 0.5       # écart (mag) à l'étoile la plus brillante :
                             # cœur de PSF non linéaire → mesure fausse
CIEL_PUR_SIGMA = 3.0         # écarte les étoiles posées sur un objet ÉTENDU
                             # (halo de galaxie dans l'anneau → flux biaisé)
SIGMA_MAX = 0.5              # dispersion (mag) au-delà de laquelle la mesure
                             # est considérée non significative
PENTE_MINI, PENTE_MAXI = 0.5, 1.5   # pente de régression attendue : hors de
                             # ces bornes, le modèle de bandes ne décrit pas
                             # l'image (Siril avertit dans ce cas)


def fond_local(img, positions, anneau=ANNEAU_FOND):
    """Fond local (médiane de l'anneau) sous chaque étoile → (N,) float64.
    NaN si l'anneau sort de l'image. L'anneau plutôt qu'un fond global : sur
    une image à gradient, un fond global est faux — et ici la valeur sert à
    ÉCARTER les étoiles posées sur un objet étendu (halo de galaxie)."""
    import math
    p = np.asarray(positions, dtype=np.float64).reshape(-1, 2)
    im = np.asarray(img, dtype=np.float64)
    h, w = im.shape
    r_out = float(anneau[1])
    out = np.full(len(p), np.nan)
    for i, (x, y) in enumerate(p):
        ix, iy = int(round(x)), int(round(y))
        if (ix - r_out < 0 or iy - r_out < 0
                or ix + r_out > w - 1 or iy + r_out > h - 1):
            continue
        x0, x1 = max(0, int(math.floor(x - r_out))), \
            min(w, int(math.ceil(x + r_out)) + 1)
        y0, y1 = max(0, int(math.floor(y - r_out))), \
            min(h, int(math.ceil(y + r_out)) + 1)
        zone = im[y0:y1, x0:x1]
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.hypot(xx - x, yy - y)
        ann = (d >= float(anneau[0])) & (d <= r_out)
        if int(ann.sum()) < 8:
            continue
        out[i] = float(np.median(zone[ann]))
    return out


def mesures_etoiles(canaux, positions, rayon=RAYON_FLUX_PX,
                    anneau=ANNEAU_FOND):
    """Flux par canal pour les MÊMES positions (ouvertures identiques, seul
    moyen d'obtenir des ratios de couleur comparables) → (N, 3) float64,
    NaN quand une ouverture est inexploitable."""
    from . import photometrie as _photo
    cols = []
    for b in ("R", "G", "B"):
        img = canaux.get(b)
        cols.append(np.full(len(positions), np.nan) if img is None else
                    _photo.flux_ouverture(img, positions, rayon=rayon,
                                          anneau=anneau))
    return np.column_stack(cols)




def _profil(entree, categorie, nom):
    """Profil de la base SPCC depuis un nom OU une entrée déjà résolue.
    → (nom, couple (wl, val)) ; (None, None) si introuvable."""
    from ..catalogues import spcc_db as DB
    if entree is None:
        return None, None
    if isinstance(entree, dict):
        return entree.get("nom", nom), DB.courbe(entree)
    e = next((c for c in DB.lister(categorie)
              if str(entree).lower() in str(c["nom"]).lower()), None)
    return (e["nom"], DB.courbe(e)) if e is not None else (None, None)


def coefficients_spcc(canaux, wcs, capteur, filtres, blanc, dossier=None,
                      forme=None, rayon=RAYON_FLUX_PX, anneau=ANNEAU_FOND,
                      max_etoiles=MAX_ETOILES, ciel_pur=CIEL_PUR_SIGMA,
                      catalogue=None, reponses=None, spectre_blanc=None):
    """SPCC de bout en bout sur l'empilement → (coefficients (3,), diag).

    `canaux` : {"R": image 2D, "G": …, "B": …} ; `wcs` : WCS résolu de la
    session (indispensable pour situer les étoiles au ciel) ; `capteur`,
    `filtres` ({"R","G","B"}), `blanc` : noms ou entrées de la base SPCC de
    Siril (`catalogues.spcc_db`) ; `catalogue` : injectable pour les bancs
    (mêmes conventions que `photometrie.Photometrie`).

    → (k (3,) float64 OU None, diag dict). `diag` contient TOUJOURS de quoi
    expliquer : pentes a/b des régressions, dispersion, nombre d'étoiles,
    noms des profils retenus, et « avertissement » quand la régression trahit
    un modèle de bandes inadapté (pente hors [0,5 ; 1,5] ou dispersion > 0,5
    mag — ce que Siril annonce par « solution imprécise, corrigez le
    gradient »). Aucune exception ne sort d'ici : un échec est un diag avec
    « erreur »."""
    diag = {"erreur": "", "avertissement": ""}
    try:
        # --- 1. profils capteur / filtres / référence de blanc ------------
        # `reponses` / `spectre_blanc` : injection directe (bancs) — court-
        # circuite la base SPCC de Siril, qui n'est pas toujours installée.
        if reponses is not None and spectre_blanc is not None:
            reponses = [np.asarray(r, float) for r in reponses]
            nom_cap, curve_bl = str(capteur), tuple(spectre_blanc)
            noms_fil = [str((filtres or {}).get(b, f"filtre {b}"))
                        for b in ("R", "G", "B")]
            nom_bl = str(blanc)
            diag.update({"capteur": nom_cap, "filtres": noms_fil,
                         "blanc": nom_bl})
        else:
            nom_cap, curve_cap = _profil(capteur, "mono_sensors", str(capteur))
            if curve_cap is None:
                diag["erreur"] = (f"capteur introuvable dans la base SPCC : "
                                  f"{capteur}")
                return None, diag
            reponses, noms_fil = [], []
            for b in ("R", "G", "B"):
                cle = (filtres or {}).get(b)
                nom, curve = _profil(cle, "mono_filters", f"filtre {b}")
                if curve is None and cle is not None:
                    diag["erreur"] = (f"filtre {b} introuvable dans la base "
                                      f"SPCC : {cle}")
                    return None, diag
                reponses.append(reponse_canal(curve_cap, curve))
                noms_fil.append(nom or f"(sans filtre {b})")
            nom_bl, curve_bl = _profil(blanc, "wb_refs", str(blanc))
            if curve_bl is None:
                diag["erreur"] = f"référence de blanc introuvable : {blanc}"
                return None, diag
            diag.update({"capteur": nom_cap, "filtres": noms_fil,
                         "blanc": nom_bl})
            # --- cohérence des BANDES : trois profils identiques, ou un profil
            # de LUMINANCE à la place d'une couleur, donnent des coefficients
            # faux — on le dit AVANT de calculer (cf. `coherence_bandes`).
            avis = coherence_bandes(noms_fil)
            if avis:
                diag["avertissement"] = " ; ".join(avis)

        # --- 2. catalogue SPECTRAL du champ -------------------------------
        from . import photometrie as _photo
        obtenir = catalogue or _photo.etoiles_catalogue
        h, w = (tuple(int(v) for v in forme) if forme else
                tuple(np.asarray(canaux["G"]).shape[:2]))
        cat, msg = ((obtenir(wcs, (h, w), dossier=dossier, spectres=True)
                     if dossier is not None
                     else obtenir(wcs, (h, w), spectres=True)))
        if not cat:
            diag["erreur"] = f"catalogue spectral indisponible — {msg}"
            return None, diag

        # --- 3. étoiles de l'image et appariement MUTUEL ------------------
        pos, _, msg_det = _photo.etoiles_image(canaux["G"],
                                              max_etoiles=max_etoiles)
        if len(pos) == 0:
            diag["erreur"] = f"aucune étoile détectée — {msg_det}"
            return None, diag
        ap, msg_ap = _photo.apparier(pos, wcs, cat)
        ia, ic = ap["ia"], ap["ic"]
        if len(ia) < 5:
            diag["erreur"] = f"appariement insuffisant ({len(ia)}) — {msg_ap}"
            return None, diag
        diag["n_apparies"] = int(len(ia))
        diag["d_px"] = float(np.median(ap["d_px"]))

        # --- 4. flux MESURÉS (ouvertures identiques sur les 3 canaux) -----
        mes = mesures_etoiles(canaux, pos[ia], rayon=rayon, anneau=anneau)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = -2.5 * np.log10(mes / np.nanmax(mes))
        garde = (np.all(rel > MARGE_SATURATION, axis=1)
                 & np.all(np.isfinite(mes), axis=1)
                 & np.all(mes > 0.0, axis=1))
        # étoiles posées sur un objet ÉTENDU : l'anneau mesure le halo de la
        # galaxie (pas le ciel) → flux et couleur biaisés.
        if ciel_pur > 0.0:
            fl = fond_local(canaux["G"], pos[ia], anneau)
            med = float(np.nanmedian(fl))
            mad = float(np.nanmedian(np.abs(fl - med))) * 1.4826
            garde &= np.isfinite(fl) & (fl <= med + ciel_pur * mad)
            diag["fond_median"], diag["fond_mad"] = med, mad
        mes, ic = mes[garde], ic[garde]
        diag["n_etoiles"] = int(len(mes))
        if len(mes) < 5:
            diag["erreur"] = (f"trop peu d'étoiles exploitables ({len(mes)}) "
                              f"après saturation et fond local")
            return None, diag

        # --- 5. rapports CATALOGUE (spectre × capteur × filtre) -----------
        pred = flux_par_canal(photons(np.asarray(cat["flux"])[ic]), reponses)
        r_cat, r_img = ratios(pred), ratios(mes)
        bon = (np.all(np.isfinite(r_cat), axis=1)
               & np.all(np.isfinite(r_img), axis=1))
        if int(bon.sum()) < 5:
            diag["erreur"] = "ratios catalogue inexploitables (réponses nulles)"
            return None, diag

        # --- 6. coefficients (régression robuste + référence de blanc) ----
        fb = flux_par_canal(spectre_reference(*curve_bl)[None, :], reponses)[0]
        wrg, wbg = fb[0] / fb[1], fb[2] / fb[1]
        k, d2 = coefficients(r_cat[bon, 0], r_cat[bon, 1], r_img[bon, 0],
                             r_img[bon, 1], wrg, wbg)
        diag.update(d2)
        if not np.all(np.isfinite(k)):
            diag["erreur"] = d2.get("erreur", "coefficients incalculables")
            return None, diag
        diag["wrg"], diag["wbg"] = float(wrg), float(wbg)
        rms, _med, n = erreur_ratios(r_cat[bon, 0], r_cat[bon, 1],
                                     r_img[bon, 0], r_img[bon, 1])
        diag["rms_couleur_mag"] = float(np.max(rms))
        diag["n_regression"] = int(n)

        # --- 7. garde-fou : le modèle de bandes décrit-il l'image ? --------
        pentes = (d2.get("b_rg", np.nan), d2.get("b_bg", np.nan))
        sigmas = (d2.get("sigma_rg", np.nan), d2.get("sigma_bg", np.nan))
        if any(not np.isfinite(v) or v < PENTE_MINI or v > PENTE_MAXI
               for v in pentes):
            diag["avertissement"] = " ; ".join(filter(None, [
                diag.get("avertissement"),
                "pente de régression hors de [0,5 ; 1,5] : les bandes "
                "modélisées décrivent mal cette image (gradient, profils de "
                "filtres) — correction à appliquer avec prudence"]))
        elif any(np.isfinite(v) and v > SIGMA_MAX for v in sigmas):
            diag["avertissement"] = " ; ".join(filter(None, [
                diag.get("avertissement"),
                f"dispersion élevée ({max(sigmas):.2f} mag) : solution "
                "imprécise (corrigez d'abord le gradient)"]))
        return k, diag
    except Exception as exc:            # jamais de panne silencieuse
        diag["erreur"] = f"SPCC interrompue ({type(exc).__name__} : {exc})"
        return None, diag


# --- Session SPCC (état pour l'application) ---------------------------------
MAX_ESSAIS = 3               # tentatives de mesure par session (le catalogue
                             # spectral est lourd : 48 chunks à lire)
DELAI_ESSAI_S = 25.0         # délai minimal entre deux tentatives


class SessionSpcc:
    """Session SPCC : mesure les coefficients UNE fois (réessais plafonnés) et
    porte l'état affiché par l'UI — même esprit que `Photometrie` du jalon 56.

    `catalogue` : injectable pour les bancs (accès au catalogue spectral).
    Aucune exception ne remonte : un échec est `(None, message)` et
    `derniere_erreur`."""

    def __init__(self, catalogue=None):
        self._catalogue = catalogue
        self.reset()

    def reset(self):
        """Session neuve : aucun coefficient, aucun diagnostic."""
        self.coefficients = None       # (3,) float64 [R, G, B]
        self.diag = {}
        self.mesures = 0
        self.derniere_erreur = ""

    @property
    def valide(self):
        """Des coefficients exploitables sont-ils disponibles ?"""
        return (self.coefficients is not None
                and bool(np.all(np.isfinite(self.coefficients)))
                and bool(np.all(self.coefficients > 0.0)))

    def gains(self, roles=("R", "G", "B")):
        """Gains par RÔLE pour le composite → dict (vide si non valide).
        C'est l'interface attendue par `CompositeStacker.gains_roles`."""
        if not self.valide:
            return {}
        return {r: float(c) for r, c in zip(roles, self.coefficients)}

    def mesurer(self, canaux, wcs, capteur, filtres, blanc, dossier=None,
                forme=None, reponses=None, spectre_blanc=None):
        """SPCC sur les canaux R/G/B courants → (résultat|None, message).

        `canaux` doit contenir les trois bandes R, G et B sur la MÊME grille
        (sinon les ratios de couleur n'ont aucun sens) — un manque est refusé
        explicitement, jamais deviné. `reponses` / `spectre_blanc` sont des
        INJECTIONS pour les bancs (cf. `coefficients_spcc`)."""
        if not canaux:
            self.derniere_erreur = "aucun canal à calibrer"
            return None, self.derniere_erreur
        if wcs is None:
            self.derniere_erreur = ("astrométrie non résolue (WCS absent : la "
                                    "SPCC a besoin des étoiles au ciel)")
            return None, self.derniere_erreur
        absents = [b for b in ("R", "G", "B") if canaux.get(b) is None]
        if absents:
            self.derniere_erreur = ("bandes manquantes : "
                                    + ", ".join(absents)
                                    + " (la SPCC exige R, G et B)")
            return None, self.derniere_erreur
        k, diag = coefficients_spcc(canaux, wcs, capteur, filtres, blanc,
                                    dossier=dossier, forme=forme,
                                    catalogue=self._catalogue,
                                    reponses=reponses,
                                    spectre_blanc=spectre_blanc)
        self.diag = diag
        if k is None:
            self.derniere_erreur = diag.get("erreur", "échec inconnu")
            return None, self.derniere_erreur
        self.coefficients = np.asarray(k, dtype=np.float64)
        self.mesures += 1
        self.derniere_erreur = ""
        return ({"coefficients": self.coefficients.tolist(), "diag": diag},
                texte_resume(k, diag))

    def texte_resume(self):
        """Ligne d'état pour l'UI ("" si rien à dire)."""
        if not self.valide:
            return (f"SPCC : {self.derniere_erreur}" if self.derniere_erreur
                    else "")
        return texte_resume(self.coefficients, self.diag)


def texte_resume(k, diag):
    """Ligne d'état en clair pour l'UI (jamais vide si `diag` est renseigné)."""
    if not np.all(np.isfinite(k)):
        return f"SPCC indisponible : {diag.get('erreur') or 'échec inconnu'}"
    txt = (f"SPCC {diag.get('capteur', '?')} : R ×{k[0]:.4f} / G ×{k[1]:.4f} "
           f"/ B ×{k[2]:.4f} — pente R/G {diag.get('b_rg', float('nan')):.3f} "
           f"(σ {diag.get('sigma_rg', float('nan')):.3f}), B/G "
           f"{diag.get('b_bg', float('nan')):.3f} "
           f"(σ {diag.get('sigma_bg', float('nan')):.3f}) sur "
           f"{diag.get('n_regression', 0)} étoiles")
    if diag.get("avertissement"):
        txt += " — ⚠ " + diag["avertissement"]
    return txt

