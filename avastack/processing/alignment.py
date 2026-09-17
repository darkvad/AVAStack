# -*- coding: utf-8 -*-
"""Alignement de chaque frame sur une référence — 3 chemins en cascade :

1. ORB + RANSAC (translation + rotation + échelle) : rapide et très bon sur
   les champs RICHES en étoiles (petite focale) — constaté en réel ;
2. CENTROÏDES D'ÉTOILES (jalon 13) : sur un champ PAUVRE en étoiles et riche
   en nébulosité (C8 à 1280 mm), l'ORB ne s'apparie plus (0-6 appariements
   mesurés sur de vraies frames le 17/09/2026). On détecte alors les étoiles
   (`stars.detecter_positions`), on vote la translation par histogramme des
   paires autour de la dérive prédite, puis RANSAC affine + raffinement ;
3. CORRÉLATION DE PHASE (translation seule), désormais HONNÊTE (constat du
   17/09/2026 : sans fenêtre de Hann ni retrait du fond, le pic de phase est
   noyé par le gradient et renvoyait (0,0) pendant que le champ dérive —
   les frames étaient empilées faussement, d'où des étoiles « en plusieurs
   points puis des trainées »). Fenêtre de Hann + retrait de la médiane
   avant `phaseCorrelate`, et la translation n'est acceptée que si la SSD
   contre la référence s'améliore NETTEMENT — sinon la frame est refusée
   (comptée « non alignée ») au lieu d'être empilée à l'identité.

Toutes les matrices passent par les mêmes GARDE-FOUS (jalon 13) : échelle
dans [0.9, 1.1], |angle| ≤ 10°, et continuité de la translation avec la
dérive en cours (anti-vote-aberrant : l'histogramme d'un champ presque vide
peut élire un pic parasite)."""

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


class StarAligner:
    def __init__(self, n_features=1000, ratio=0.75, min_matches=8, min_inliers=8):
        self.orb = cv2.ORB_create(nfeatures=n_features, fastThreshold=8)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.ratio, self.min_matches, self.min_inliers = ratio, min_matches, min_inliers
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
        mono = img.mean(axis=2) if img.ndim == 3 else img
        f = mono.astype(np.float32)
        # Bornes de normalisation de la RÉFÉRENCE, réutilisées pour CHAQUE
        # frame (jalon 13) : une normalisation indépendante par image rend
        # les deux étirements incohérents dès que la frame a des bords non
        # couverts (les zéros du bord font glisser les percentiles) — la
        # SSD devient insensible à la BONNE translation et la phase refuse
        # tout. Constaté par le test du jalon 13 (12 px de décalage).
        self._ref_lo, self._ref_hi = np.percentile(f, 1.0), np.percentile(f, 99.7)
        self.ref_gray = self._norm8(img, self._ref_lo, self._ref_hi)
        self.ref_kp, self.ref_des = self.orb.detectAndCompute(self.ref_gray, None)
        self.ref_pos, _msg = _stars.detecter_positions(
            img, max_etoiles=MAX_ALIGN_ETOILES)
        self._last_t = None

    def _norm8(self, img, lo=None, hi=None):
        mono = img.mean(axis=2) if img.ndim == 3 else img
        f = mono.astype(np.float32)
        if lo is None or hi is None:      # pas de bornes partagées : locale
            lo, hi = np.percentile(f, 1.0), np.percentile(f, 99.7)
        if hi - lo < 1e-6:
            hi = lo + 1e-6
        return (np.clip((f - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)

    def compute(self, frame):
        """→ (M 2x3, confiant)  M transforme la frame courante vers la référence."""
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
        """ORB indisponible ou non concluant : centroïdes d'étoiles, puis
        corrélation de phase honnête, sinon refus — JAMAIS un « alignement »
        à (0, 0) déclaré confiant (constat réel du 17/09/2026)."""
        M, ok = self._etoiles(frame)
        if M is not None:
            return M, ok
        return self._phase(g)

    def _etoiles(self, frame):
        """Alignement par centroïdes d'étoiles : vote de translation (lissé)
        autour de la dérive prédite, RANSAC affine, contre-test d'appariements
        mutuels, puis raffinement sur les inliers.
        → (M, True) / (None, False) si non concluant."""
        pos, _msg = _stars.detecter_positions(frame, max_etoiles=MAX_ALIGN_ETOILES)
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
