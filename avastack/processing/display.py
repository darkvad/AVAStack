# -*- coding: utf-8 -*-
"""Étirement temps réel : auto STF façon PixInsight, manuel, ou VeraLux (tiers)."""

import threading

import numpy as np
import cv2

from . import veralux as _veralux


class DisplayProcessor:
    """Étirement temps réel.

    Mode AUTO — « STF » façon PixInsight :
      1. point noir  lo = médiane − k·σ        (coupe le bruit sous le fond)
      2. point blanc hi = percentile 99.9       (vraies hautes lumières, pas med+k·σ !)
      3. midtones m résolues pour que le FOND tombe à self.target (~0.25) après MTF.
    Le fond garde donc une luminosité stable quelle que soit l'exposition :
    c'est la nébulosité qui « monte » avec l'intégration, pas le fond.
    Les stats (médiane, σ, p99.9) sont lissées dans le temps → pas de pompage.

    Mode MANUEL — black/white point.

    Mode VERALUX (self.stretch == "veralux", opt-in) — étirement hyperbolique
    du moteur tiers `veralux_core_headless.py`, via l'adaptateur
    `avastack.processing.veralux`. Le calcul (~200 ms à taille aperçu) part
    dans un thread dédié : le résultat est CACHÉ par image et les réglages
    sont comparés par clé — l'UI n'est jamais bloquée, et tant que le calcul
    n'est pas terminé, le STF sert d'image d'attente. VeraLux n'écrit JAMAIS
    dans black/white/gamma (leçon de la 1re tentative) : ces réglages et les
    curseurs gamma/saturation restent la propriété des modes STF/manuel, et
    gamma/saturation s'appliquent après l'étirement, comme pour le STF.

    Dans tous les modes, `process()` reçoit une image LINÉAIRE [0..1] et
    renvoie un uint8 affichable ; les données sauvegardées ne passent jamais
    par ici.
    """
    def __init__(self):
        self.auto = True
        self.sigma_k = 2.8            # coupure des ombres, en σ SOUS la médiane
        self.target = 0.25            # luminosité cible du fond du ciel après MTF
        self.black, self.white = 0.0, 1.0
        self.gamma, self.saturation = 1.0, 1.0
        self.last_lo, self.last_hi = 0.0, 1.0
        self._stats = None            # (médiane, σ, p99.9) lissées — anti-pompage
        self._ema = 0.25              # réactivité : 0 = figé, 1 = instantané

        # --- VeraLux (moteur tiers) -----------------------------------------
        self.stretch = "stf"          # "stf" (défaut, inchangé) | "veralux"
        self.vl_mode_res = _veralux.MODE_LOG_D   # jalon 3 ajoutera MODE_TARGET_BG
        self.vl_target_bg = _veralux.TARGET_BG_PAR_DEFAUT
        self.vl_log_d = _veralux.LOG_D_PAR_DEFAUT
        self.vl_profil = _veralux.PROFIL_PAR_DEFAUT
        # cache + solveur (thread dédié, jamais le thread UI)
        self._vl_src = None           # dernière image soumise (comparaison d'objet)
        self._vl_key = None           # clé des réglages du dernier calcul lancé
        self._vl_result = None        # (clé, image étirée) du dernier calcul TERMINÉ
        self._vl_job = None           # (copie image, params, clé) en attente
        self._vl_pending = False      # un calcul est en cours
        self._vl_lock = threading.Lock()
        self._vl_wake = threading.Event()
        self.vl_new = False           # un résultat vient d'arriver (lu par l'UI)
        self.vl_error = ""            # dernière erreur du solveur (pour l'UI)
        self.vl_log_d_resolu = None   # dernier logD utilisé/résolu (pour l'UI)
        self.vl_diagnostics = None    # dernier dict de diagnostics (pour l'UI)
        self._vl_thread = threading.Thread(target=self._vl_worker, daemon=True)
        self._vl_thread.start()

    def reset(self):
        """Oublie les stats lissées (nouvel empilement / changement de vue)."""
        self._stats = None

    @staticmethod
    def _mtf(x, m):
        """Midtones Transfer Function : x, m ∈ [0,1]."""
        m = min(max(m, 0.001), 0.98)
        return np.clip(((m - 1.0) * x) / ((2.0 * m - 1.0) * x - m), 0.0, 1.0)

    @staticmethod
    def _solve_m(x, t):
        """m tel que MTF(x, m) = t — inversion exacte de la MTF."""
        x = min(max(x, 1e-4), 0.9999)
        m = x * (1.0 - t) / (t + x - 2.0 * t * x)
        return min(max(m, 0.001), 0.98)

    def _auto_params(self, img, live=True):
        mono = img.mean(axis=2) if img.ndim == 3 else img
        s = mono[::max(1, mono.shape[0] // 512), ::max(1, mono.shape[1] // 512)]
        med = float(np.median(s))
        sigma = max(float(np.median(np.abs(s - med))) * 1.4826, 1e-8)  # σ robuste (MAD)
        p999 = float(np.percentile(s, 99.9))

        # Lissage temporel des STATS (pas des paramètres) : les curseurs restent
        # réactifs, mais l'image ne « pompe » pas entre deux frames.
        if self._stats is None:
            self._stats = (med, sigma, p999)
        elif live:
            a = self._ema
            self._stats = tuple(v0 + a * (v1 - v0)
                                for v0, v1 in zip(self._stats, (med, sigma, p999)))
        med, sigma, p999 = self._stats

        lo = med - self.sigma_k * sigma                     # ombres : bruit coupé
        hi = max(p999, med + 10.0 * sigma, lo + 1e-8)        # hautes lumières réelles
        m = self._solve_m((med - lo) / (hi - lo), self.target)
        return lo, hi, m

    def _vl_params(self):
        """Clé de hachage des réglages VeraLux (recalcul si elle change)."""
        return (self.vl_mode_res, round(self.vl_target_bg, 4),
                round(self.vl_log_d, 3), self.vl_profil)

    def _vl_worker(self):
        """Thread solveur VeraLux : calcule le DERNIER job demandé (les jobs
        intermédiaires — slider bougé, frame remplacée — sont simplement
        remplacés, jamais empilés). Écrit le résultat sous verrou."""
        while True:
            self._vl_wake.wait()
            self._vl_wake.clear()
            with self._vl_lock:
                job = self._vl_job
                self._vl_job = None
            if job is None:
                continue
            img, params, key = job
            try:
                result, log_d_util, diag = _veralux.etirer(img, **params)
            except Exception as exc:      # moteur absent, image dégénérée…
                with self._vl_lock:
                    self._vl_pending = False
                    self.vl_error = f"VeraLux : {exc}"
                    self.vl_new = True
                continue
            with self._vl_lock:
                self._vl_pending = False
                self._vl_result = (key, result)
                self.vl_error = ""
                self.vl_log_d_resolu = log_d_util
                self.vl_diagnostics = diag
                self.vl_new = True

    def _process_veralux(self, img, live=True):
        """Chemin VeraLux : rend le dernier résultat terminé (ou le STF en
        image d'attente) et soumet un calcul si l'image ou les réglages ont
        changé. Jamais bloquant : aucun calcul ici, seulement une copie."""
        key = self._vl_params()
        if self._vl_src is not img or self._vl_key != key:
            self._vl_src, self._vl_key = img, key
            params = dict(mode=self.vl_mode_res, target_bg=self.vl_target_bg,
                          log_d=self.vl_log_d, profil=self.vl_profil)
            with self._vl_lock:
                if not self._vl_pending:
                    self._vl_pending = True
                    # copie défensive : img appartient à l'UI et peut être
                    # remplacée pendant le calcul
                    self._vl_job = (img.astype(np.float32).copy(), params, key)
                    self._vl_wake.set()
        with self._vl_lock:
            res = self._vl_result \
                if (self._vl_result is not None
                    and self._vl_result[0] == key) else None
        if res is not None:
            return res[1]                 # image étirée [0..1], mêmes dimensions
        # Image d'attente : le STF auto (SANS toucher aux réglages utilisateur
        # black/white/gamma — on ne fait que lire les stats lissées).
        lo, hi, m = self._auto_params(img, live=live)
        return self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)

    def process(self, img, live=True):
        img = img.astype(np.float32, copy=False)
        if self.stretch == "veralux" and _veralux.moteur_disponible():
            x = self._process_veralux(img, live=live)
        else:
            if self.stretch == "veralux" and not self.vl_error:
                self.vl_error = ("VeraLux : moteur tiers veralux_core_headless.py "
                                 "introuvable — affichage STF en attendant.")
                self.vl_new = True
            if self.auto:
                lo, hi, m = self._auto_params(img, live=live)
                self.last_lo, self.last_hi = lo, hi
                x = self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)
            else:
                lo, hi = self.black, self.white
                if hi - lo < 1e-6:
                    hi = lo + 1e-6
                x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        if abs(self.gamma - 1.0) > 1e-3:
            x = np.power(x, 1.0 / max(self.gamma, 0.05))
        if img.ndim == 3 and abs(self.saturation - 1.0) > 1e-3:
            hsv = cv2.cvtColor(np.clip(x, 0.0, 1.0), cv2.COLOR_RGB2HSV)
            hsv[..., 1] = np.clip(hsv[..., 1] * self.saturation, 0.0, 1.0)
            x = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        return (np.clip(x, 0.0, 1.0) * 255).astype(np.uint8)
