# -*- coding: utf-8 -*-
"""Étirement temps réel : auto STF façon PixInsight, manuel, ou VeraLux (tiers)."""

import threading

import numpy as np
import cv2

from ..external import live as _gx_live
from . import denoise as _denoise
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
    `avastack.processing.veralux`. Deux modes de résolution du logD :
      - MODE_TARGET_BG (défaut, jalon 3) : le moteur résout lui-même le logD
        pour amener le fond du ciel à vl_target_bg ;
      - MODE_LOG_D : logD imposé (curseur ou bouton 🔒 de l'UI) — calcul
        direct, déterministe, réactif.
    Le calcul (~200 ms à taille aperçu) part dans un thread dédié, déclenché
    par notify_new_stack() à CHAQUE nouvel empilement — le rythme des frames
    (≥ 1 s, souvent bien plus) EST le cooldown, aucun calcul entre deux
    frames — et le worker ne garde que le DERNIER job (aucune file
    d'attente). Le résultat est CACHÉ par image et les réglages sont comparés
    par clé — l'UI n'est jamais bloquée, et tant que le calcul n'est pas
    terminé, le STF sert d'image d'attente. VeraLux n'écrit JAMAIS
    dans black/white/gamma (leçon de la 1re tentative) : ces réglages et les
    curseurs gamma/saturation restent la propriété des modes STF/manuel, et
    gamma/saturation s'appliquent après l'étirement, comme pour le STF.

    Mode VERALUX + GRAXPERT LIVE (jalon 4, opt-in) : si self.vl_graxpert est
    True, le thread solveur enchaîne stack → GraXpert (CLI, via
    avastack.external.live, sur un FITS temporaire de l'aperçu) → VeraLux —
    l'ordre photométrique correct : le gradient est retiré AVANT l'étirement.
    Le résultat GraXpert est mis en cache par CONTENU d'image (empreinte) :
    bouger un curseur VeraLux ne relance PAS GraXpert. En cas d'échec
    (binaire absent, timeout…), l'erreur est signalée dans vl_error et
    l'image brute est étirée en repli — l'UI n'est jamais bloquée, le BXT
    reste entièrement manuel (bouton ⚡, inchangé).

    Dans tous les modes, `process()` reçoit une image LINÉAIRE [0..1] et
    renvoie un uint8 affichable ; les données sauvegardées ne passent jamais
    par ici.

    Mode VERALUX + DÉBRUITAGE LIVE (jalon 9, remis le 16/09/2026, opt-in) :
    si self.vl_denoise est True, le thread solveur enchaîne stack → GraXpert
    live (si activé) → débruitage LOCAL (avastack.processing.denoise :
    ondelettes à trous ou Non-local Means, numpy/OpenCV, aucun subprocess)
    → VeraLux. Cache par (CONTENU image APRÈS gradient, méthode, force) ;
    échec = repli sur l'image sans débruitage + message préfixé
    « Débruitage live : … » (jamais de blocage, jamais d'image perdue).
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
        self.vl_mode_res = _veralux.MODE_TARGET_BG  # jalon 3 : résolution auto
                                      # du logD (fond calé sur vl_target_bg) ;
                                      # MODE_LOG_D = logD forcé (bouton 🔒)
        self.vl_target_bg = _veralux.TARGET_BG_PAR_DEFAUT
        self.vl_log_d = _veralux.LOG_D_PAR_DEFAUT
        self.vl_profil = _veralux.PROFIL_PAR_DEFAUT
        # --- GraXpert live (jalon 4, opt-in) --------------------------------
        self.vl_graxpert = False      # GraXpert AVANT l'étirement VeraLux
        self.vl_graxpert_cmd = ""     # commande GraXpert ({input}/{outbase}…)
        self._gx_cache = None         # (empreinte image, image traitée) —
                                      # utilisé par le thread solveur SEUL
        # --- Débruitage live (jalon 9, remis le 16/09/2026, opt-in) ---------
        # Algorithmes LOCAUX rapides (numpy/OpenCV, aucun subprocess) — à la
        # différence du débruitage GraXpert IA (PLUSIEURS minutes), celui-ci
        # peut tourner à chaque nouvel empilement. OPTION DOUCE par défaut :
        # à force utile les méthodes locales moutonnent (« léopard », cf.
        # CLAUDE.md) ; le live sert à JUGER, la sauvegarde linéaire reste
        # intouchée et « tel que vu » reproduit la chaîne affichée.
        self.vl_denoise = False       # algorithme LOCAL avant l'étirement
        self.vl_denoise_methode = "nlm"   # "ondelettes" | "nlm" (défaut : nlm)
        self.vl_denoise_force = 0.5   # 0..1
        self._dn_cache = None         # (empreinte image, méthode, force,
                                      # image traitée) — thread solveur SEUL
        # cache + solveur (thread dédié, jamais le thread UI)
        self._vl_src = None           # dernière image soumise (comparaison d'objet)
        self._vl_key = None           # clé des réglages du dernier calcul lancé
        self._vl_result = None        # (clé, image étirée) du dernier calcul TERMINÉ
        self._vl_job = None           # (copie image, params, clé) en attente
        self._vl_pending = False      # un calcul est en cours
        self._vl_force = False        # un NOUVEL empilement attend la résolution
        self._vl_lock = threading.Lock()
        self._vl_wake = threading.Event()
        self.vl_new = False           # un résultat vient d'arriver (lu par l'UI)
        self.vl_error = ""            # dernière erreur du solveur (pour l'UI)
        self.vl_log_d_resolu = None   # dernier logD utilisé/résolu (pour l'UI)
        self.vl_diagnostics = None    # dernier dict de diagnostics (pour l'UI)
        self._vl_thread = threading.Thread(target=self._vl_worker, daemon=True)
        self._vl_thread.start()

    def reset(self):
        """Oublie les stats lissées et le cache VeraLux (nouvelle session /
        changement de vue) : le prochain process() relance une résolution."""
        self._stats = None
        self._gx_cache = None         # oublie aussi le résultat GraXpert live
        self._dn_cache = None         # …et le résultat du débruitage live
        with self._vl_lock:
            self._vl_result = None
            self._vl_force = True

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

    @staticmethod
    def _calc_stats(img):
        """Statistiques d'étirement (médiane, σ robuste MAD, p99.9) d'une
        image linéaire — fonction PURE : aucune mutation d'état (le
        sous-échantillonnage la garde rapide même en pleine résolution)."""
        mono = img.mean(axis=2) if img.ndim == 3 else img
        s = mono[::max(1, mono.shape[0] // 512), ::max(1, mono.shape[1] // 512)]
        med = float(np.median(s))
        sigma = max(float(np.median(np.abs(s - med))) * 1.4826, 1e-8)  # σ robuste (MAD)
        return med, sigma, float(np.percentile(s, 99.9))

    def _auto_params(self, img, live=True):
        med, sigma, p999 = self._calc_stats(img)

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

    def notify_new_stack(self):
        """Signale qu'un NOUVEL empilement vient d'être produit (une frame de
        plus a été empilée) : le thread solveur relance la résolution. Le
        rythme des frames (≥ 1 s, souvent bien plus) EST le cooldown — aucun
        calcul entre deux frames, et le worker ne garde que le DERNIER job
        (aucune file d'attente). Appelé depuis l'UI, jamais bloquant."""
        with self._vl_lock:
            self._vl_force = True

    def _vl_params(self):
        """Clé de hachage des réglages VeraLux (recalcul si elle change)."""
        return (self.vl_mode_res, round(self.vl_target_bg, 4),
                round(self.vl_log_d, 3), self.vl_profil,
                self.vl_graxpert, self.vl_graxpert_cmd,
                self.vl_denoise, self.vl_denoise_methode,
                round(self.vl_denoise_force, 2))

    def _vl_worker(self):
        """Thread solveur : enchaîne — si activés — GraXpert live (jalon 4)
        PUIS le débruitage local (jalon 9 : algorithmes numpy/OpenCV, aucun
        subprocess) PUIS l'étirement VeraLux, sur le DERNIER job demandé
        (les jobs intermédiaires — slider bougé, frame remplacée — sont
        simplement remplacés, jamais empilés). Écrit le résultat sous verrou."""
        while True:
            self._vl_wake.wait()
            self._vl_wake.clear()
            with self._vl_lock:
                job = self._vl_job
                self._vl_job = None
            if job is None:
                # Aucun job à traiter : ne jamais laisser `_vl_pending` à True
                # (un état « calcul en cours SANS job » figerait l'aperçu sur
                # l'image d'attente STF pour toujours). Job et drapeau étant
                # écrits ensemble sous verrou, cet état est incohérent : on le
                # répare plutôt que d'attendre un job qui n'arrivera pas.
                with self._vl_lock:
                    self._vl_pending = False
                continue
            img, params, key, (gx_actif, gx_cmd), (dn_actif, dn_methode,
                                                   dn_force) = job
            # --- GraXpert live (opt-in) : retrait de gradient AVANT l'étirement
            # Cache indexé par (CONTENU de l'image, commande) : une nouvelle
            # frame relance l'outil, mais pas un simple curseur VeraLux ; et
            # modifier la commande GraXpert invalide le résultat caché.
            img_gx, err_gx = img, ""
            if gx_actif:
                cle = (_gx_live.cle_image(img), gx_cmd)
                if self._gx_cache is not None and self._gx_cache[0] == cle:
                    img_gx = self._gx_cache[1]   # curseur bougé : GraXpert
                else:                            # n'est PAS relancé
                    img_gx, err_gx = _gx_live.appliquer(img, gx_cmd)
                    if err_gx:
                        img_gx = img             # repli : étirement de l'image
                        self._gx_cache = None    # brute, erreur signalée
                    else:
                        self._gx_cache = (cle, img_gx)
            # --- Débruitage live (jalon 9, opt-in) : APRÈS le GraXpert live
            # éventuel — même ordre que la chaîne manuelle (gradient →
            # débruitage). Cache par (CONTENU de l'image ENTRANTE, méthode,
            # force) : une nouvelle frame relance le calcul (l'empreinte
            # change), pas un simple curseur VeraLux ; changer de méthode ou
            # de force invalide aussi le résultat caché. Le seuil k-sigma des
            # ondelettes et la force h du NLM sont AUTO-ADAPTÉS au bruit réel
            # de chaque frame (le débruitage suit l'intégration, comme l'œil).
            img_dn, err_dn = img_gx, ""
            if dn_actif:
                cle = (_gx_live.cle_image(img_gx), dn_methode,
                       round(dn_force, 2))
                if self._dn_cache is not None and self._dn_cache[0] == cle:
                    img_dn = self._dn_cache[1]
                else:
                    img_dn, err_dn = _denoise.denoiser(img_gx, dn_methode,
                                                       dn_force)
                    if err_dn:
                        img_dn = img_gx   # repli : étirement sans débruitage
                        self._dn_cache = None
                    else:
                        self._dn_cache = (cle, img_dn)
            prefixe = ((f"GraXpert live : {err_gx} ; " if err_gx else "")
                       + (f"Débruitage live : {err_dn} ; " if err_dn else ""))
            try:
                result, log_d_util, diag = _veralux.etirer(img_dn, **params)
            except Exception as exc:      # moteur absent, image dégénérée…
                with self._vl_lock:
                    self._vl_pending = False
                    self.vl_error = f"{prefixe}VeraLux : {exc}"
                    self.vl_new = True
                continue
            with self._vl_lock:
                self._vl_pending = False
                self._vl_result = (key, result)
                self.vl_error = prefixe   # "" si tout s'est bien passé
                self.vl_log_d_resolu = log_d_util
                self.vl_diagnostics = diag
                self.vl_new = True

    def _process_veralux(self, img, live=True):
        """Chemin VeraLux : rend le dernier résultat terminé (ou le STF en
        image d'attente) et soumet un calcul si l'image ou les réglages ont
        changé. Jamais bloquant : aucun calcul ici, seulement une copie."""
        key = self._vl_params()
        with self._vl_lock:
            force = self._vl_force
        # Jalon 3 : on ne soumet QUE si l'empilement a changé
        # (notify_new_stack) ou si les réglages ont changé — l'objet image
        # change à chaque tick UI sans nouvel empilement, il ne doit PAS
        # déclencher de recalcul.
        if force or self._vl_key != key:
            params = dict(mode=self.vl_mode_res, target_bg=self.vl_target_bg,
                          log_d=self.vl_log_d, profil=self.vl_profil)
            gx = (self.vl_graxpert, self.vl_graxpert_cmd)   # capté côté UI
            dn = (self.vl_denoise, self.vl_denoise_methode,
                  self.vl_denoise_force)                    # capté côté UI
            with self._vl_lock:
                if not self._vl_pending:
                    self._vl_pending = True
                    self._vl_force = False   # consommé : job réellement soumis
                    # copie défensive : img appartient à l'UI et peut être
                    # remplacée pendant le calcul
                    self._vl_job = (img.astype(np.float32).copy(), params,
                                    key, gx, dn)
                    self._vl_wake.set()
            self._vl_src, self._vl_key = img, key
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

    @staticmethod
    def _gamma_saturation(x, rgb, gamma, saturation):
        """Gamma et saturation COMMUNS — appliqués après l'étirement, quel que
        soit le mode (STF, manuel, VeraLux). Factorisés pour que le rendu
        « tel que vu » de la sauvegarde (jalon 5) soit strictement identique
        à l'affichage."""
        if abs(gamma - 1.0) > 1e-3:
            x = np.power(x, 1.0 / max(gamma, 0.05))
        if rgb and abs(saturation - 1.0) > 1e-3:
            hsv = cv2.cvtColor(np.clip(x, 0.0, 1.0), cv2.COLOR_RGB2HSV)
            hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0.0, 1.0)
            x = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        return np.clip(x, 0.0, 1.0)

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
        x = self._gamma_saturation(x, img.ndim == 3, self.gamma, self.saturation)
        return (x * 255).astype(np.uint8)

    # ------------------------------------------------------------- jalon 5
    def rendu_pleine_resolution(self, img, reglages=None):
        """Rendu « tel que vu » (jalon 5) d'une image LINÉAIRE PLEINE
        résolution — empilement complet ou résultat traité — pour la
        sauvegarde « 💾 Enregistrer tel que vu ». Reproduit l'étirement
        affiché : STF/manuel recalculé sur l'image complète, ou VeraLux
        avec le DERNIER logD résolu (rendu identique à l'écran, sans
        re-résolution ; repli sur une résolution target_bg si aucun logD
        n'a encore été résolu, et repli STF/manuel si le moteur tiers est
        absent — comme l'affichage) — PUIS gamma/saturation communs.

        Appelé depuis un thread de travail, JAMAIS le thread UI : ne touche
        à AUCUN état partagé (pas de stats EMA, pas de solveur, pas de
        cache, jamais black/white/gamma). Les réglages sont lus dans
        reglages (dict capturé côté UI) ou, à défaut, dans les attributs
        courants. Renvoie un float [0..1] de mêmes dimensions ; lève une
        exception en cas d'échec — l'appelant gère l'erreur.

        NB : GraXpert live n'est PAS appliqué ici — l'appelant l'enchaîne
        AVANT (vue « empilement ») ; en vue « traitée », l'image a déjà
        subi le traitement externe (GraXpert/BXT manuels).
        """
        r = (reglages or {}).get
        stretch = r("stretch", self.stretch)
        if stretch == "veralux" and _veralux.moteur_disponible():
            img = np.clip(img.astype(np.float32), 0.0, 1.0)
            if r("vl_mode_res", self.vl_mode_res) == _veralux.MODE_LOG_D:
                log_d = r("vl_log_d", self.vl_log_d)
            elif r("vl_log_d_resolu", self.vl_log_d_resolu) is not None:
                log_d = r("vl_log_d_resolu", self.vl_log_d_resolu)
            else:
                log_d = None
            params = dict(profil=r("vl_profil", self.vl_profil))
            if log_d is None:
                params.update(mode=_veralux.MODE_TARGET_BG,
                              target_bg=r("vl_target_bg", self.vl_target_bg))
            else:
                params.update(mode=_veralux.MODE_LOG_D, log_d=log_d)
            x, _, _ = _veralux.etirer(img, **params)
        elif r("auto", self.auto):
            med, sigma, p999 = self._calc_stats(img)
            lo = med - r("sigma_k", self.sigma_k) * sigma
            hi = max(p999, med + 10.0 * sigma, lo + 1e-8)
            m = self._solve_m((med - lo) / (hi - lo), r("target", self.target))
            x = self._mtf(np.clip((img - lo) / (hi - lo), 0.0, 1.0), m)
        else:
            lo, hi = r("black", self.black), r("white", self.white)
            if hi - lo < 1e-6:
                hi = lo + 1e-6
            x = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
        return self._gamma_saturation(x, img.ndim == 3,
                                      r("gamma", self.gamma),
                                      r("saturation", self.saturation))
