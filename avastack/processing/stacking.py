# -*- coding: utf-8 -*-
"""Empilement glissant avec rejet des traînées (satellites, avions, météores).

Deux méthodes de rejet :
- « kappa » : kappa-sigma séquentiel (historique, léger en mémoire) — chaque
  frame est comparée aux statistiques CUMULÉES (moyenne/écart-type).
  Faiblesse : une traînée passée pendant le warmup s'incruste dans la
  moyenne cumulée, puis ce sont les frames PROPRES qui s'en écartent et se
  font rejeter — la trace reste figée dans l'empilement.
- « winsorized » : adaptation au live stacking du Winsorized Sigma Clipping
  de PixInsight — chaque frame est comparée à la MÉDIANE et au MAD d'une
  fenêtre glissante des dernières frames alignées. La médiane est robuste
  aux traînées (minoritaires par pixel : un satellite ne traverse une
  position donnée que sur une fraction des frames), donc les traces sont
  rejetées dans les deux sens, y compris si elles sont passées pendant le
  warmup. Coût : la fenêtre de frames alignées reste en RAM (float32).
"""

import numpy as np

# Taille (en valeurs) des bandes de lignes traitées d'un coup en mode
# winsorized : borne la mémoire des temporaires de np.median/np.abs
# (surchargeable par les tests pour forcer le multi-bandes).
_CHUNK_PX = 4_000_000


class LiveStacker:
    """Moyenne glissante + rejet kappa-sigma ou Winsorized (fenêtre glissante)."""

    METHODES = ("kappa", "winsorized")

    def __init__(self, shape, k=3.0, warmup=5, method="kappa", window=8):
        self.shape = shape
        self.k = k
        self.warmup = warmup
        self.method = method if method in self.METHODES else "kappa"
        self.window = max(3, int(window))
        self.reset()

    def reset(self):
        self.sum = np.zeros(self.shape, np.float64)
        self.sumsq = np.zeros(self.shape, np.float64)
        self.wsum = np.zeros(self.shape, np.float64)
        self.n = 0
        self.rejected_total = 0
        self._buf = None       # fenêtre glissante (mode winsorized)
        self._nbuf = 0
        self._rejeu = False    # rejeu du warmup déjà effectué ?

    def set_rejet(self, method=None, window=None):
        """Change de méthode / de taille de fenêtre à chaud, sans perdre
        l'accumulation : seule la fenêtre de référence est vidée (elle se
        remplit à nouveau, le rejet redevient effectif dès qu'elle est
        pleine — cf. warmup)."""
        changed = False
        if method is not None and method in self.METHODES and method != self.method:
            self.method = method
            changed = True
        if window is not None:
            window = max(3, int(window))
            if window != self.window:
                self.window = window
                changed = True
        if changed:
            self._buf = None
            self._nbuf = 0
            self._rejeu = False

    def add(self, frame):
        f = frame.astype(np.float64)
        w = self._poids(f)
        self.sum += f * w
        self.sumsq += (f * f) * w
        self.wsum += w
        self.n += 1

    def mean(self):
        if self.n == 0:
            return None
        return (self.sum / np.maximum(self.wsum, 1e-9)).astype(np.float32)

    # ------------------------------------------------------------- rejet
    def _poids(self, f):
        """Poids par pixel de la frame courante (0 = rejeté, 1 = gardé)."""
        if self.k is None:
            return 1.0
        if self.method == "winsorized":
            return self._poids_winsorized(f)
        # kappa-sigma séquentiel (comportement historique inchangé)
        if self.n >= self.warmup:
            mean = self.sum / np.maximum(self.wsum, 1e-9)
            std = np.sqrt(np.maximum(self.sumsq / np.maximum(self.wsum, 1e-9) - mean * mean, 1e-12))
            w = np.where(np.abs(f - mean) > self.k * std, 0.0, 1.0)
            self.rejected_total += int((w == 0).sum())
            return w
        return 1.0

    def _poids_winsorized(self, f):
        """Rejet contre la médiane/MAD de la fenêtre glissante (PixInsight).

        σ_robuste = 1.4826 × MAD (équivalent gaussien de l'écart-type
        médian absolu) : insensible aux valeurs aberrantes du buffer lui-
        même, contrairement à l'écart-type cumulé du mode kappa (une
        traînée passée pendant le warmup y gonfle σ pour toujours, ce qui
        masque les traces suivantes aux mêmes pixels). Rejet symétrique
        |frame − médiane| > k·σ_robuste (le k de la combobox kappa sert de
        seuil haut/bas).

        REJEU DU WARMUP : pendant les premières frames, la médiane
        n'existe pas encore et tout est accumulé à poids 1 — une trace
        passée là s'incrusterait à jamais (diluée en A/n). Quand la
        fenêtre se remplit pour la PREMIÈRE fois (elle contient alors
        toutes les frames accumulées), l'accumulation est reconstruite
        avec les poids robustes : la trace précoce est effacée, pas
        seulement diluée."""
        self._push_buf(f)
        if self._nbuf < min(self.warmup, self.window) or self._nbuf < 2:
            return 1.0
        buf = self._buf[:self._nbuf]           # (n, H, W) ou (n, H, W, 3)
        w = np.empty(buf.shape[1:], np.float64)
        # Rejeu uniquement si le buffer plein contient TOUTES les frames
        # accumulées (n+1 == window) : sinon la reconstruction écraserait
        # des frames plus anciennes jamais rejouées.
        rejeu = (not self._rejeu and self._nbuf == self.window
                 and self.n + 1 == self._nbuf)
        rej = 0                                # rejets des frames 0..n-2 (rejeu)
        # Découpage par bandes de lignes pour borner les temporaires
        # (np.median et np.abs créent des copies intermédiaires).
        px_par_ligne = int(np.prod(buf.shape[2:], dtype=np.int64))  # W ou W*3
        lignes = max(1, _CHUNK_PX // max(1, px_par_ligne * buf.shape[0]))
        for a in range(0, buf.shape[1], lignes):
            b = min(buf.shape[1], a + lignes)
            blk = buf[:, a:b]                              # (n, l, ...)
            med = np.median(blk, axis=0)
            mad = np.median(np.abs(blk - med), axis=0)
            sigma = np.maximum(1.4826 * mad, 1e-6)         # plancher zones plates
            hors = np.abs(blk - med) > self.k * sigma      # (n, l, ...)
            if rejeu:
                # frames 0..n-2 reconstruites avec les poids robustes
                # (la frame courante, dernière du buffer, est ajoutée
                # ensuite par add() — jamais de double comptage) ;
                # AFFECTATION (pas +=) : on remplace l'accumulation
                # contaminée du warmup.
                passe = hors[:-1]
                self.sum[a:b] = (blk[:-1] * ~passe).sum(axis=0)
                self.sumsq[a:b] = (blk[:-1] * blk[:-1] * ~passe).sum(axis=0)
                self.wsum[a:b] = (~passe).sum(axis=0)
                rej += int(passe.sum())
            w[a:b] = np.where(hors[-1], 0.0, 1.0)          # frame courante
        if rejeu:
            self._rejeu = True
            self.rejected_total = rej
        self.rejected_total += int((w == 0).sum())
        return w

    def _push_buf(self, frame):
        """Insère la frame dans la fenêtre glissante (buffer circulaire)."""
        if self._buf is None or self._buf.shape[1:] != frame.shape:
            self._buf = np.zeros((self.window,) + frame.shape, np.float32)
            self._nbuf = 0
        if self._nbuf < self.window:
            self._buf[self._nbuf] = frame
            self._nbuf += 1
        else:
            self._buf[:-1] = self._buf[1:]                 # décalage memcpy
            self._buf[-1] = frame
