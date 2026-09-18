# -*- coding: utf-8 -*-
"""Alignement de chaque frame sur une référence — 4 chemins en cascade :

1. ORB + RANSAC (translation + rotation + échelle) : rapide et très bon sur
   les champs RICHES en étoiles (petite focale) — constaté en réel ;
2. TRIANGLES D'ÉTOILES (jalon 15, esprit Siril / astrometry.net) : appariement
   GLOBAL des listes d'étoiles par similitude de triangles (deux rapports de
   côtés invariants). Aucune fenêtre de continuité à franchir : un dithering,
   une reprise de session ou une nuit différente ne fait plus refuser la frame
   (constat réel d'Alain, 17/09/2026 : étoiles dédoublées + refus en masse sur
   des brutes que Siril empile sans problème) ;
3. CENTROÏDES D'ÉTOILES (jalon 13) : sur un champ PAUVRE en étoiles et riche
   en nébulosité (C8 à 1280 mm), l'ORB ne s'apparie plus (0-6 appariements
   mesurés sur de vraies frames le 17/09/2026). On détecte alors les étoiles
   (`stars.detecter_positions`), on vote la translation par histogramme des
   paires autour de la dérive prédite, puis RANSAC affine + raffinement ;
4. CORRÉLATION DE PHASE (translation seule), désormais HONNÊTE (constat du
   17/09/2026 : sans fenêtre de Hann ni retrait du fond, le pic de phase est
   noyé par le gradient et renvoyait (0,0) pendant que le champ dérive —
   les frames étaient empilées faussement, d'où des étoiles « en plusieurs
   points puis des trainées »). Fenêtre de Hann + retrait de la médiane
   avant `phaseCorrelate`, et la translation n'est acceptée que si la SSD
   contre la référence s'améliore NETTEMENT — sinon la frame est refusée
   (comptée « non alignée ») au lieu d'être empilée à l'identité.

Tous les chemins travaillent sur le CANAL VERT des images couleur (esprit
Siril, qui aligne sur le canal vert de la brute CFA) : 2 sites verts sur 4
dans la matrice Bayer, pleine résolution, aucun artefact d'interpolation de
débayerisation dans les centroïdes ; en mono, l'image telle quelle (jalon 15).

Toutes les matrices passent par les mêmes GARDE-FOUS (jalon 13) : échelle
dans [0.9, 1.1], |angle| ≤ 10° ; les chemins « votants » (centroïdes, phase)
ajoutent la continuité de la translation avec la dérive en cours (anti-vote-
aberrant : l'histogramme d'un champ presque vide peut élire un pic parasite) —
le chemin TRIANGLES, global par construction, s'en passe."""

import itertools

import numpy as np
import cv2

from . import stars as _stars

# Garde-fous géométriques d'une matrice d'alignement acceptable.
ECHELLE_MIN, ECHELLE_MAX = 0.9, 1.1
ANGLE_MAX_DEG = 10.0
# Phase : la SSD doit baisser d'au moins cette fraction pour être acceptée.
PHASE_GAIN_MIN = 0.10
# Inliers minimum du chemin ÉTOILES (jalon 13) : 6 suffit parce que chaque
# estimation est CONTRE-VÉRIFIÉE par appariements mutuels (un champ croisé
# entre deux nuits ne partage que 6-7 étoiles brillantes — constat réel du
# dossier NGC 4565) ; le contre-test élimine les pics parasites du vote.
INLIERS_ETOILES = 6
# On n'aligne que sur les étoiles LES PLUS BRILLANTES : les objets faibles
# (nœuds de galaxie, fragments de nébulosité, blobs de bruit) ont des
# centroïdes instables qui dispersent le vote — constat réel : avec 200
# « étoiles » le vote échoue, avec 60 brillantes il tombe juste
# (16/16 appariements mutuels, échelle 1,000).
MAX_ALIGN_ETOILES = 60

# --- Appariement par TRIANGLES (jalon 15, esprit Siril / astrometry.net) ----
# Chaque triangle des plus brillantes est décrit par deux rapports de côtés
# INVARIANTS (indépendants de la translation, rotation ET échelle) ; les
# triangles appariés donnent une transformation candidate, exacte sur 3
# sommets, scorée par le nombre d'étoiles rapprochées sur la liste complète.
TRI_N_MAX = 12          # triangles construits sur les N plus brillantes
TRI_TOL = 0.02          # tolérance sur les rapports de côtés (bruit de centroïde)
TRI_PAIRS_MAX = 2000    # plafond de paires candidates évaluées (champs riches)
TRI_INLIERS_MIN = 6     # correspondances requises (même exigence que « étoiles »)
TRI_RAYON = 3.0         # rayon d'appariement d'une étoile après transformée (px)


def _M_valide(M):
    """Garde-fous géométriques (échelle + angle) d'une matrice 2×3."""
    a, b = float(M[0, 0]), float(M[1, 0])
    ech = float(np.hypot(a, b))
    if not (ECHELLE_MIN <= ech <= ECHELLE_MAX):
        return False
    if abs(np.degrees(np.arctan2(b, a))) > ANGLE_MAX_DEG:
        return False
    return bool(np.isfinite(M).all())


def infos_M(M):
    """→ (angle °, échelle, dx, dy) d'une matrice 2×3 (warpAffine)."""
    a, b = float(M[0, 0]), float(M[1, 0])
    return (float(np.degrees(np.arctan2(b, a))), float(np.hypot(a, b)),
            float(M[0, 2]), float(M[1, 2]))


def canal_alignement(img):
    """Canal sur lequel TOUT l'alignement travaille (esprit Siril, jalon 15) :
    le VERT pour une image couleur — 2 sites verts sur 4 dans la matrice
    Bayer, pleine résolution, aucun artefact d'interpolation de
    débayerisation dans les centroïdes —, l'image telle quelle en mono.
    L'ancienne moyenne RGB diluait les étoiles colorées et y mélangeait le
    bruit chromatique des canaux rouge/bleu.
    Accepte (H, W), (H, W, 3) ou (C, H, W) → numpy (H, W) float32 (l'entrée
    n'est PAS modifiée)."""
    a = np.asarray(img)
    if a.ndim == 2:
        return a.astype(np.float32, copy=False)
    if a.ndim == 3:
        if a.shape[0] <= 4 and a.shape[-1] > 4:   # convention canaux-en-tête
            a = np.transpose(a, (1, 2, 0))
        return np.ascontiguousarray(a[..., 1], dtype=np.float32)
    raise ValueError(f"image de rang inattendu : {a.shape}")


def _invariants_triangles(pts, n_max=TRI_N_MAX):
    """Triangles CANONIQUES des `n_max` plus brillantes de `pts` ((N, 2),
    trié par éclat décroissant — c'est l'ordre de `stars.detecter_positions`).

    Canonisation (indépendante de l'ordre des entrées) : le plus GRAND côté
    du triangle relie deux sommets, l'APEX est le troisième, et les deux
    sommets de base sont ordonnés par distance croissante à l'apex.
    Invariants (indépendants de translation, rotation ET échelle) :
    d(apex→base proche)/grand côté et d(apex→base loin)/grand côté.
    → (inv (T, 2) float32, sommets (T, 3) int [apex, base proche, base loin],
    longueurs (T,) float32) ou (None, None, None) si moins de 3 points."""
    n = min(int(n_max), len(pts))
    if n < 3:
        return None, None, None
    idx = np.array(list(itertools.combinations(range(n), 3)), np.int64)
    p = pts[idx]                                   # (T, 3, 2)
    d = p[:, :, None, :] - p[:, None, :, :]
    L = np.sqrt((d * d).sum(-1))                   # (T, 3, 3) — indices = POSITIONS
    iu = np.triu_indices(3, 1)
    c = L[:, iu[0], iu[1]]                         # (T, 3) côtés (pos 0-1, 0-2, 1-2)
    i_lon = c.argmax(1)                            # le plus grand côté
    base = np.array(iu, np.int64).T[i_lon]         # (T, 2) POSITIONS de ses sommets
    apex = 3 - base.sum(1)                         # la position restante (0..2)
    t = np.arange(len(idx))
    d0 = L[t, apex, base[:, 0]]
    d1 = L[t, apex, base[:, 1]]
    proche = d0 <= d1
    b_proche = np.where(proche, base[:, 0], base[:, 1])   # positions
    b_loin = np.where(proche, base[:, 1], base[:, 0])
    grand = np.maximum(L[t, b_proche, b_loin], 1e-6)
    roles = np.stack([apex, b_proche, b_loin], 1)         # (T, 3) POSITIONS
    # → indices GLOBAUX d'étoiles (piège : positions 0..2 ≠ indices globaux,
    # ça ne coïncide que pour le triangle (0, 1, 2) — bug constaté en test)
    sommets = np.take_along_axis(idx, roles, 1).astype(np.int64)
    inv = np.stack([L[t, apex, b_proche] / grand,
                    L[t, apex, b_loin] / grand], 1).astype(np.float32)
    return inv, sommets, grand.astype(np.float32)


class StarAligner:
    def __init__(self, n_features=1000, ratio=0.75, min_matches=8, min_inliers=8):
        self.orb = cv2.ORB_create(nfeatures=n_features, fastThreshold=8)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.ratio, self.min_matches, self.min_inliers = ratio, min_matches, min_inliers
        # Jalon 21 (décision d'Alain) : compositions narrowband (HOO/SHO) —
        # TRIANGLES d'abord, ORB écarté. Jalon 21b : repli « étoiles » puis
        # phase (retour réel : trop de refus quand le canal narrowband montre
        # peu d'étoiles).
        self.triangles_seuls = False
        self.reset()

    def reset(self):
        self.ref_kp = self.ref_des = self.ref_gray = None
        self.ref_pos = None        # centroïdes d'étoiles de la référence
        self._last_t = None        # dernière translation acceptée (continuité)
        self._ref_lo = self._ref_hi = None   # bornes de normalisation partagées
        self.dernier = None        # info du dernier alignement (UI, jalon 13)

    def _noter(self, M, methode):
        """Mémorise la dernière décision d'alignement pour la ligne d'état."""
        ang, _ech, dx, dy = infos_M(M)
        self.dernier = {"methode": methode, "dx": dx, "dy": dy, "angle": ang}

    def set_reference(self, img):
        canal = canal_alignement(img)     # vert (couleur) / tel quel (mono)
        f = canal.astype(np.float32)
        # Bornes de normalisation de la RÉFÉRENCE, réutilisées pour CHAQUE
        # frame (jalon 13) : une normalisation indépendante par image rend
        # les deux étirements incohérents dès que la frame a des bords non
        # couverts (les zéros du bord font glisser les percentiles) — la
        # SSD devient insensible à la BONNE translation et la phase refuse
        # tout. Constaté par le test du jalon 13 (12 px de décalage).
        self._ref_lo, self._ref_hi = np.percentile(f, 1.0), np.percentile(f, 99.7)
        self.ref_gray = self._norm8(canal, self._ref_lo, self._ref_hi)
        self.ref_kp, self.ref_des = self.orb.detectAndCompute(self.ref_gray, None)
        self.ref_pos, _msg = _stars.detecter_positions(
            canal, max_etoiles=MAX_ALIGN_ETOILES)
        self._last_t = None

    def _norm8(self, img, lo=None, hi=None):
        mono = canal_alignement(img)
        f = mono.astype(np.float32)
        if lo is None or hi is None:      # pas de bornes partagées : locale
            lo, hi = np.percentile(f, 1.0), np.percentile(f, 99.7)
        if hi - lo < 1e-6:
            hi = lo + 1e-6
        return (np.clip((f - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)

    def compute(self, frame):
        """→ (M 2x3, confiant)  M transforme la frame courante vers la référence."""
        # Jalon 21 (HOO/SHO) : TRIANGLES d'abord, ORB ÉCARTÉ (descripteurs de
        # gradients qui s'apparient mal d'un filtre à l'autre). Jalon 21b
        # (retour réel d'Alain : 86 frames refusées en début de session SHO —
        # les canaux narrowband montrent souvent moins de 6 étoiles communes,
        # le minimum des triangles) : REPLI sur « étoiles » puis sur la
        # corrélation de phase, deux chemins à garde-fous forts (contre-
        # vérification par appariements mutuels, gain SSD net exigé) —
        # toujours SANS ORB. Si tout échoue, la frame est refusée.
        if self.triangles_seuls:
            M, ok = self._triangles(frame)
            if M is not None:
                return M, ok
            M, ok = self._etoiles(frame)
            if M is not None:
                return M, ok
            g = self._norm8(frame, self._ref_lo, self._ref_hi)
            return self._phase(g)
        g = self._norm8(frame, self._ref_lo, self._ref_hi)
        kp, des = self.orb.detectAndCompute(g, None)
        if (self.ref_des is None or des is None
                or len(kp) < self.min_matches or len(self.ref_kp) < self.min_matches):
            return self._sans_orb(frame, g)
        good = [pair[0] for pair in self.bf.knnMatch(self.ref_des, des, k=2)
                if len(pair) == 2 and pair[0].distance < self.ratio * pair[1].distance]
        if len(good) < self.min_matches:
            return self._sans_orb(frame, g)
        src = np.float32([kp[m.trainIdx].pt for m in good])           # frame courante
        dst = np.float32([self.ref_kp[m.queryIdx].pt for m in good])  # référence
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.0, maxIters=5000)
        if M is None or inl is None:
            return self._sans_orb(frame, g)
        if int(inl.sum()) < self.min_inliers or not _M_valide(M):
            return self._sans_orb(frame, g)
        self._last_t = (float(M[0, 2]), float(M[1, 2]))
        self._noter(M, "ORB")
        return M, True

    # ------------------------------------------------------------ jalon 13
    def _sans_orb(self, frame, g):
        """ORB indisponible ou non concluant : TRIANGLES (jalon 15, appariement
        global), puis centroïdes d'étoiles (vote + continuité), puis
        corrélation de phase honnête, sinon refus — JAMAIS un « alignement »
        à (0, 0) déclaré confiant (constat réel du 17/09/2026)."""
        M, ok = self._triangles(frame)
        if M is not None:
            return M, ok
        M, ok = self._etoiles(frame)
        if M is not None:
            return M, ok
        return self._phase(g)

    # ------------------------------------------------------------ jalon 15
    def _triangles(self, frame):
        """Appariement GLOBAL par similitude de triangles (esprit Siril /
        astrometry.net) : chaque paire de triangles candidats (référence,
        frame) fournit une transformation candidate exacte sur ses 3 sommets,
        scorée par le nombre d'étoiles rapprochées ; la meilleure est
        consolidée (RANSAC partiel + raffinement LMEDS + contre-test
        d'appariements mutuels, comme le chemin « étoiles »). AUCUNE fenêtre
        de continuité : c'est un appariement global, un dithering, une
        reprise de session ou une autre nuit ne fait plus refuser la frame.
        → (M, True) / (None, False) si non concluant."""
        canal = canal_alignement(frame)
        pos, _msg = _stars.detecter_positions(canal, max_etoiles=MAX_ALIGN_ETOILES)
        if self.ref_pos is None or len(pos) < TRI_INLIERS_MIN \
                or len(self.ref_pos) < TRI_INLIERS_MIN:
            return None, False
        inv_r, som_r, _lon_r = _invariants_triangles(self.ref_pos)
        inv_c, som_c, _lon_c = _invariants_triangles(pos)
        if inv_r is None or inv_c is None:
            return None, False
        # Paires candidates : rapports de côtés proches (écart max sur les 2
        # invariants), triées par ressemblance et plafonnées (champs riches).
        ecart = np.abs(inv_r[:, None, :] - inv_c[None, :, :]).max(-1)
        paires = np.argwhere(ecart <= TRI_TOL)
        if not len(paires):
            return None, False
        if len(paires) > TRI_PAIRS_MAX:
            ordre = np.argsort(ecart[paires[:, 0], paires[:, 1]])[:TRI_PAIRS_MAX]
            paires = paires[ordre]
        p_ref = np.asarray(self.ref_pos, np.float32)
        p_cur = np.asarray(pos, np.float32)
        n_stop = min(len(p_cur), len(p_ref))
        best_M, best_n = None, 0
        for ir, ic in paires:
            M0 = cv2.getAffineTransform(p_cur[som_c[ic]].astype(np.float32),
                                        p_ref[som_r[ir]].astype(np.float32))
            if M0 is None or not np.isfinite(M0).all() or not _M_valide(M0):
                continue
            pc = cv2.transform(p_cur.reshape(-1, 1, 2), M0)[:, 0, :]
            d2 = np.hypot(pc[:, None, 0] - p_ref[None, :, 0],
                          pc[:, None, 1] - p_ref[None, :, 1])
            n = int((d2.min(1) <= TRI_RAYON).sum())
            if n > best_n:
                best_n, best_M = n, M0
                if best_n >= n_stop:
                    break                   # impossible de mieux → inutile
        if best_M is None or best_n < TRI_INLIERS_MIN:
            return None, False
        # Consolidation : correspondances mutuelles (≤ 2,5 px) de la meilleure
        # candidate, RANSAC partiel, raffinement, contre-test final.
        pc = cv2.transform(p_cur.reshape(-1, 1, 2), best_M)[:, 0, :]
        d2 = np.hypot(pc[:, None, 0] - p_ref[None, :, 0],
                      pc[:, None, 1] - p_ref[None, :, 1])
        proche_cur = d2.argmin(1)
        dist_cur = d2[np.arange(len(pc)), proche_cur]
        proche_ref = d2.T.argmin(1)
        sel = (dist_cur <= 2.5) & (proche_ref[proche_cur]
                                   == np.arange(len(pc)))
        if int(sel.sum()) < TRI_INLIERS_MIN:
            return None, False
        src, dst = p_cur[sel], p_ref[proche_cur[sel]]
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.5,
                                             maxIters=5000)
        if M is None or inl is None or int(inl.sum()) < TRI_INLIERS_MIN \
                or not _M_valide(M):
            return None, False
        m_inl = inl[:, 0].astype(bool)
        M2, _ = cv2.estimateAffinePartial2D(src[m_inl], dst[m_inl],
                                            method=cv2.LMEDS, maxIters=5000)
        if M2 is not None and _M_valide(M2):
            M = M2
        pc = cv2.transform(p_cur.reshape(-1, 1, 2), M)[:, 0, :]
        d2 = np.hypot(pc[:, None, 0] - p_ref[None, :, 0],
                      pc[:, None, 1] - p_ref[None, :, 1])
        proche_cur = d2.argmin(1)
        dist_cur = d2[np.arange(len(pc)), proche_cur]
        proche_ref = d2.T.argmin(1)
        mutuel = (dist_cur <= 2.5) & (proche_ref[proche_cur]
                                      == np.arange(len(pc)))
        if int(mutuel.sum()) < TRI_INLIERS_MIN:
            return None, False
        self._last_t = (float(M[0, 2]), float(M[1, 2]))
        self._noter(M, "triangles")
        return M, True

    def _etoiles(self, frame):
        """Alignement par centroïdes d'étoiles : vote de translation (lissé)
        autour de la dérive prédite, RANSAC affine, contre-test d'appariements
        mutuels, puis raffinement sur les inliers.
        → (M, True) / (None, False) si non concluant."""
        pos, _msg = _stars.detecter_positions(
            canal_alignement(frame), max_etoiles=MAX_ALIGN_ETOILES)
        if self.ref_pos is None or len(self.ref_pos) < INLIERS_ETOILES \
                or len(pos) < INLIERS_ETOILES:
            return None, False
        d = self.ref_pos[None, :, :] - pos[:, None, :]     # (Ncur, Nref, 2)
        # Vote autour de la dérive prédite (continuité). Sans prédiction
        # (1er alignement après une (re)référence) la fenêtre est LARGE :
        # un décalage légitime (autre nuit, reprise de session) ne doit pas
        # être raté ; avec prédiction, ±40 px suffisent (dérive ~px/frame)
        # et bloquent les votes parasites.
        had_pred = self._last_t is not None
        t0 = self._last_t if had_pred else (0.0, 0.0)
        search = 40.0 if had_pred else 100.0
        # Sans prédiction (1er alignement = ANCRE du repère), l'exigence est
        # plus forte : 8 mutuels au lieu de 6 — un pic parasite auto-
        # consistant du vote (motif répété du champ, constat réel sur le
        # dossier mixé 03/06+07/06) peut réunion 6 coïncidences, rarement 8.
        seuil = INLIERS_ETOILES if had_pred else 8
        ok = ((np.abs(d[..., 0] - t0[0]) <= search)
              & (np.abs(d[..., 1] - t0[1]) <= search))
        if not ok.any():
            return None, False
        dv = d[ok]                                         # (P, 2)
        # Vote BRUT (PAS de lissage : le balayage du jalon 13 sur les vraies
        # frames montre que le lissage gaussien étale le vrai amas de votes
        # — 3 réussites contre 14 sans lissage), puis recentrage sur la
        # MOYENNE des paires du bin vainqueur (le centre de bin coûte ±5 px
        # en fenêtre large). Sélection à ±3 px autour du pic recentré.
        H2, xe, ye = np.histogram2d(dv[:, 0], dv[:, 1], bins=10,
                                    range=[[t0[0] - search, t0[0] + search],
                                           [t0[1] - search, t0[1] + search]])
        i, j = np.unravel_index(np.argmax(H2), H2.shape)
        tx = 0.5 * (xe[i] + xe[i + 1])
        ty = 0.5 * (ye[j] + ye[j + 1])
        pres = dv[(np.abs(dv[:, 0] - tx) <= (xe[1] - xe[0]))
                  & (np.abs(dv[:, 1] - ty) <= (ye[1] - ye[0]))]
        if len(pres):
            tx, ty = float(pres[:, 0].mean()), float(pres[:, 1].mean())
        ii, jj = np.where((np.abs(d[..., 0] - tx) <= 3.0)
                          & (np.abs(d[..., 1] - ty) <= 3.0))
        if len(ii) < seuil:
            return None, False
        src, dst = pos[ii], self.ref_pos[jj]
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.5,
                                             maxIters=5000)
        if M is None or inl is None:
            return None, False
        if int(inl.sum()) < seuil or not _M_valide(M):
            return None, False
        # Raffinement : ré-estimation sur les seuls inliers (précision).
        m_inl = inl[:, 0].astype(bool)
        M2, _ = cv2.estimateAffinePartial2D(src[m_inl], dst[m_inl],
                                            method=cv2.LMEDS, maxIters=5000)
        if M2 is not None and _M_valide(M2):
            M = M2
        # CONTRE-VÉRIFICATION (jalon 13) : l'estimation doit réunir assez
        # d'appariements MUTUELS (plus proche voisin des deux côtés, ≤ 3 px).
        # Un pic parasite du vote ne survit pas à ce contre-test — la vraie
        # solution, elle, regroupe toutes les étoiles communes des deux
        # images (6-7 suffisent, cf. dossier mixé 03/06 + 07/06).
        pc = cv2.transform(pos.reshape(-1, 1, 2), M)[:, 0, :]
        d2 = np.hypot(pc[:, None, 0] - self.ref_pos[None, :, 0],
                      pc[:, None, 1] - self.ref_pos[None, :, 1])
        proche_cur = d2.argmin(axis=1)
        dist_cur = d2[np.arange(len(pc)), proche_cur]
        proche_ref = d2.T.argmin(axis=1)
        mutuel = (dist_cur <= 2.5) & (proche_ref[proche_cur]
                                      == np.arange(len(pc)))
        if int(mutuel.sum()) < seuil:
            return None, False
        # Continuité (seulement avec une prédiction réelle) : un saut > 40 px
        # est un vote aberrant (champ presque vide → pic parasite).
        dx, dy = float(M[0, 2]), float(M[1, 2])
        if had_pred and np.hypot(dx - t0[0], dy - t0[1]) > 40.0:
            return None, False
        self._last_t = (dx, dy)
        self._noter(M, "étoiles")
        return M, True

    def _phase(self, g):
        """Corrélation de phase HONNÊTE (jalon 13) : Hann + retrait de la
        médiane, puis acceptation SEULEMENT si la SSD s'améliore nettement
        et que la translation reste dans ±40 px — sinon refus."""
        if self.ref_gray is None or self.ref_gray.shape != g.shape:
            return np.eye(2, 3), False
        a = self.ref_gray.astype(np.float32)
        b = g.astype(np.float32)
        h, w = g.shape
        win = cv2.createHanningWindow((w, h), cv2.CV_32F)
        a0 = (a - float(np.median(a))) * win
        b0 = (b - float(np.median(b))) * win
        (dx, dy), _resp = cv2.phaseCorrelate(a0, b0)
        if not (np.isfinite(dx) and np.isfinite(dy)):
            return np.eye(2, 3), False
        if abs(dx) > 40.0 or abs(dy) > 40.0:
            return np.eye(2, 3), False
        best_d, best_M = None, np.eye(2, 3)
        for s in (1.0, -1.0):  # signe déterminé empiriquement (comparaison SSD)
            M = np.array([[1.0, 0.0, s * dx], [0.0, 1.0, s * dy]])
            warp = cv2.warpAffine(b, M, (w, h))
            d = float(np.mean((warp - a) ** 2))
            if best_d is None or d < best_d:
                best_d, best_M = d, M
        d0 = float(np.mean((b - a) ** 2))     # SSD sans translation (identité)
        if best_d > d0 * (1.0 - PHASE_GAIN_MIN):
            return np.eye(2, 3), False        # pas d'amélioration nette → refus
        self._last_t = (float(best_M[0, 2]), float(best_M[1, 2]))
        self._noter(best_M, "phase")
        return best_M, True
