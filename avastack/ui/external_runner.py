# -*- coding: utf-8 -*-
"""Traitement externe (GraXpert / BlurXTerminator) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 108 du chantier de refactoring. Ce
module regroupe le TRAITEMENT EXTERNE sur un instantané de l'empilement, dans
un thread séparé — l'empilement accumulé reste linéaire et intact :

  - la demande et le contrôle des outils (`_request_ext`, `_pick_exe`) ;
  - le message d'état thread-safe (`_set_ext_msg`) ;
  - la CHAÎNE MONO (`_run_external`) et sa variante PAR COUCHE en composition
    (`_run_external_compo`, `_compo_couches_traitees`, `_ext_run_cmd`) ;
  - la fin de chaîne et le nettoyage du dossier de travail (`_fin_ext_tmp`).

Les méthodes sont reprises VERBATIM : `App` hérite de `ExternalRunner`, donc
`self` reste l'instance `App` et le comportement est inchangé AU BIT. Les
dépendances de module (`gx_live`, `travail`, `denoiser_local`, `couleurs_mod`,
`composition_mod`, `find_output`, `auto_unflip`, `commande_avec_strength`) sont
importées ICI : ce sont les MÊMES objets qu'`app.py` — les bancs qui patchent
leurs ATTRIBUTS (`ui.gx_live.appliquer = …`, `travail.espace_libre = …`)
restent donc effectifs.

Les attributs d'interface (constantes et variables Tk de la classe `App`) sont
DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur, aucune
logique.
"""

import os
import time
import shutil
from typing import Any, Callable

import numpy as np
import cv2
import tkinter as tk

from ..compat import IS_WINDOWS
from .. import travail
from ..images import find_output, auto_unflip
from ..processing import DisplayProcessor
from ..processing import composition as composition_mod
from ..processing import couleurs as couleurs_mod
from ..processing import denoise as denoiser_local
from ..external import live as gx_live
from ..external.detection import commande_avec_strength


class ExternalRunner:
    """Mixin : traitement externe (GraXpert / BlurXTerminator) sur instantané."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS DE TYPAGE seulement.
    # Moteur d'affichage et empileur.
    disp: DisplayProcessor
    stacker: Any
    # État de session.
    running: Any
    _session: Any
    _mode_compo: Any
    rayon_chroma_ref: Any
    DN_EXT_CODES: Any
    # État du traitement externe (posé par le thread, relu par _tick).
    ext_busy: Any
    ext_job: Any
    ext_msg: Any
    ext_state: Any
    ext_t0: Any
    ext_request: Any
    _ext_popup: Any
    proc_full: Any
    proc_entete: Any
    proc_new: Any
    proc_show: Any
    btn_ext: Any
    # Variables Tk du panneau « Traitement externe ».
    var_cmd_graxpert: tk.Variable
    var_cmd_graxpert_dn: tk.Variable
    var_cmd_bxt: tk.Variable
    var_dn_force: tk.Variable
    var_dn_methode: tk.Variable
    var_ext_graxpert: tk.Variable
    var_ext_dn: tk.Variable
    var_ext_bxt: tk.Variable
    var_ext_neutre: tk.Variable
    var_ext_chroma: tk.Variable
    # Méthodes de l'hôte (`App`, portées par d'autres mixins) appelées ici.
    _avertir: Callable[..., Any]
    _demander_fichier: Callable[..., Any]
    _dire: Callable[..., Any]
    _entete_externe: Callable[..., Any]

    def _pick_exe(self, var):
        """Sélectionne l'exécutable d'un outil externe et le place en tête de
        la commande — les options déjà saisies ({input}, {output}…) sont
                conservées telles quelles."""
        p = self._demander_fichier(
            "Exécutable de l'outil",
            filetypes=[("Exécutables", "*.exe *.bat *.cmd *.py" if IS_WINDOWS
                        else "*.py *.sh *.AppImage"),
                       ("Tous les fichiers", "*.*")])
        if not p:
            return
        cmd = var.get().strip()
        rest = ""                                  # options existantes à conserver
        if cmd.startswith('"'):
            end = cmd.find('"', 1)
            if end != -1:
                rest = cmd[end + 1:].strip()
        elif cmd:
            parts = cmd.split(None, 1)
            rest = parts[1] if len(parts) > 1 else ""
        var.set(f'"{p}"' + (f" {rest}" if rest else ""))

    def _request_ext(self):
        """Demande un traitement externe sur l'empilement courant (lancé par le worker)."""
        if not self.running or self.stacker is None or self.stacker.n == 0:
            self._dire("Traitement externe", "Aucun empilement à traiter.")
            return
        if self.ext_busy:
            self._dire("Traitement externe",
                       "Un traitement est déjà en cours — patientez.")
            return
        if not (self.var_ext_graxpert.get() or self.var_ext_dn.get()
                or self.var_ext_bxt.get()
                or self.var_ext_neutre.get()            # v2.37.1
                or self.var_ext_chroma.get()):          # v2.37.1
            self._dire("Traitement externe",
                       "Cochez au moins un traitement.")
            return
        # v2.38.5 : dire AVANT de lancer (des minutes de calcul) qu'un outil
        # est introuvable — l'échec n'arrivait jusque-là qu'à SON étape, sous
        # la forme d'un « command not found » noyé dans la sortie de l'outil.
        manques = []
        for actif, var, nom in (
                (self.var_ext_graxpert.get(), self.var_cmd_graxpert,
                 "GraXpert (gradient)"),
                (self.var_ext_dn.get() and self.DN_EXT_CODES.get(
                    self.var_dn_methode.get(), "graxpert") == "graxpert",
                 self.var_cmd_graxpert_dn, "GraXpert (débruitage)"),
                (self.var_ext_bxt.get(), self.var_cmd_bxt,
                 "BlurXTerminator")):
            if not actif:
                continue
            m = gx_live.outil_manquant(var.get().strip())
            if m:
                manques.append(f"• {nom} : {m}")
        if manques:
            self._avertir(
                "Traitement externe",
                "Outil externe introuvable — le traitement échouerait :\n\n"
                + "\n".join(manques)
                + "\n\nRéglez le chemin avec le bouton « … » du cadre "
                  "« Traitement externe (long) ».")
            return
        # Capture des réglages ici (thread principal) : le thread externe ne
        # touchera pas aux variables Tkinter. Méthode de débruitage : la
        # force est injectée DANS la commande GraXpert (source de vérité =
        # curseur, l'Entry n'est jamais modifiée) ; pour ondelettes/NLM la
        # force est transportée telle quelle (étape locale, en mémoire).
        mode_dn = self.DN_EXT_CODES.get(self.var_dn_methode.get(), "graxpert")
        cmd_dn = (commande_avec_strength(self.var_cmd_graxpert_dn.get().strip(),
                                         self.var_dn_force.get())
                  if mode_dn == "graxpert" else "")
        self.ext_job = (self.var_ext_graxpert.get(),
                        self.var_cmd_graxpert.get().strip(),
                        self.var_ext_dn.get(),
                        cmd_dn,
                        self.var_ext_bxt.get(),
                        self.var_cmd_bxt.get().strip(),
                        mode_dn,
                        self.var_dn_force.get(),
                        # v2.48.0 (jalon 85) : la chaîne couleur
                        # (SCNR / SCNR doux / démagenta) N'EST PLUS dans ce job
                        # — elle suit l'étirement et est réglée par la section
                        # « Couleur de l'objet (après étirement) ». Le résultat
                        # ⚡ reste LINÉAIRE, non écrêté en vert.
                        # v2.37.1 : corrections PRÉ-ÉTIREMENT de la chaîne live
                        # (9e/10e éléments + la force en 11e) — déballage
                        # tolérant côté thread de traitement. La force est
                        # CAPTURÉE ici (curseur « Couleur live ») : le thread
                        # externe ne lit jamais une variable Tk.
                        self.var_ext_neutre.get(),
                        self.var_ext_chroma.get(),
                        float(self.disp.vl_chroma_force),
                        # v2.37.4 : RAYON DE RÉFÉRENCE du flou de chroma
                        # (12e élément), en pixels PLEINE RÉSOLUTION — la chaîne
                        # externe travaille à cette résolution, elle l'utilise
                        # tel quel. Capturé ici : le thread de traitement ne lit
                        # JAMAIS une variable Tk.
                        float(self.rayon_chroma_ref))
        self.ext_request = True
        self._set_ext_msg("Traitement demandé…", state="busy")
        self.btn_ext.config(state="disabled")

    def _set_ext_msg(self, txt, state=None):
        """Message d'état du traitement externe (thread-safe : simple attribut
        relu par _tick, jamais un widget directement depuis un thread).
        state : 'busy' (en cours), 'ok' (terminé), 'error' (échec → popup)."""
        self.ext_msg = txt
        if state:
            self.ext_state = state
            if state == "busy":
                self.ext_t0 = time.time()
            if state == "error":
                self._ext_popup = True

    def _run_external(self, stack, n_frames, session):
        """Chaîne les outils externes (GraXpert → BlurXTerminator) sur un
        instantané de l'empilement. Tourne en thread séparé : l'acquisition
        continue pendant ce temps. Le résultat n'affecte QUE l'affichage (vue
        « traitée ») et la sauvegarde dédiée — l'empilement accumulé reste
        linéaire et intact.

        Jalon 24 (décision d'Alain, 19/09/2026) : en mode COMPOSITION, le
        gradient et le débruitage sont faits PAR COUCHE (la pollution
        lumineuse et la lune ne frappent pas pareil selon le filtre ; le
        modèle de fond de GraXpert ne doit voir que des couches mono 2D —
        élimine aussi le canal-mort SHO sans S, cf. jalon 23b) ; BXT et la
        chaîne couleur restent sur le composite. Voir _run_external_compo.

        Placeholders des commandes :
          {input}   → fichier FITS d'entrée (instantané de l'empilement, float 32F)
          {output}  → chemin de sortie complet, extension .fits
          {outbase} → chemin de sortie SANS extension (GraXpert : -output)
        Le fichier réellement produit est retrouvé automatiquement (_find_output),
        quelle que soit son extension ou son suffixe (-bxt, _GraXpert…), et un
        éventuel miroir vertical est corrigé (_auto_unflip)."""
        tmp = None
        try:
            # Jalon 24 : en composition, chaîne PAR COUCHE (gradient +
            # débruitage sur chaque couche 2D, recomposition, puis BXT +
            # chaîne couleur sur le composite).
            if self._mode_compo and hasattr(self.stacker,
                                            "mean_avec_canaux") \
                    and len(self.ext_job) > 11 \
                    and (self.ext_job[0] or self.ext_job[2]):
                comp, canaux = self.stacker.mean_avec_canaux()
                if comp is not None and canaux:
                    self._run_external_compo(comp, canaux, n_frames, session)
                    return
            (use_gx, cmd_gx, use_dn, cmd_dn, use_bxt, cmd_bxt,
             mode_dn, force_dn) = self.ext_job[:8]
            # v2.48.0 (jalon 85) : la chaîne couleur (SCNR / SCNR doux /
            # démagenta) NE FAIT PLUS PARTIE DE CETTE CHAÎNE — elle suit
            # l'étirement, donc elle est appliquée par l'AFFICHAGE et par la
            # sauvegarde « tel que vu » (`display.couleur_apres_etirement`).
            # Le résultat ⚡ reste ainsi LINÉAIRE et non écrêté en vert :
            # réutilisable tel quel.
            # v2.37.1 : corrections pré-étirement de la chaîne LIVE (9e, 10e et
            # 11e éléments du job — déballage tolérant : les jobs antérieurs n'en
            # ont pas → inactives) : neutralisation du fond → réduction du bruit
            # chromatique, juste avant l'étirement d'affichage.
            nf_ext = bool(self.ext_job[8]) if len(self.ext_job) > 8 else False
            chroma_ext = bool(self.ext_job[9]) if len(self.ext_job) > 9 \
                else False
            force_chroma_ext = (float(self.ext_job[10])
                                if len(self.ext_job) > 10 else 0.5)
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma (12e élément —
            # déballage tolérant : les jobs antérieurs n'en ont pas → rayon de
            # référence, soit le comportement de la v2.37.3).
            rayon_chroma_ext = (float(self.ext_job[11])
                                if len(self.ext_job) > 11
                                else couleurs_mod.RAYON_CHROMA_DEFAUT)
            steps = []
            if use_gx:
                steps.append(("GraXpert gradient", "cmd", cmd_gx))
            if use_dn:
                if mode_dn == "graxpert":
                    # Débruitage GraXpert IA (jalon 7, remis le 16/09/2026) :
                    # étape SUBPROCESS comme les autres, LONGUE (minutes).
                    steps.append(("GraXpert débruitage", "cmd", cmd_dn))
                else:
                    # Jalon 8 : débruitage LOCAL (ondelettes à trous ou
                    # Non-local means) en numpy/OpenCV, quelques secondes —
                    # étape EN MÉMOIRE entre les étapes subprocess.
                    libelle = ("Ondelettes à trous" if mode_dn == "ondelettes"
                               else "Non-local means")
                    steps.append((f"Débruitage local ({libelle})",
                                  "dn_local", None))
            if use_bxt:
                steps.append(("BlurXTerminator", "cmd", cmd_bxt))
            for name, kind, cmd in steps:
                if kind == "cmd" and ("{input}" not in cmd
                                      or ("{output}" not in cmd
                                          and "{outbase}" not in cmd)):
                    self._set_ext_msg(f"Commande {name} incomplète : il manque "
                                      "{{input}} ou {output}/{outbase}.", state="error")
                    return
            tmp = travail.creer_dossier("avastack_")
            # v2.38.6 : la chaîne écrit PLUSIEURS FITS de la taille de l'image
            # (entrée + une par étape). On vérifie l'espace AVANT d'écrire et on
            # REFUSE en une phrase chiffrée, plutôt que de remplir le volume à la
            # 3e étape après plusieurs minutes de calcul (constat du 27/09/2026 :
            # « 24962352 requested and 10902832 written » sur un /tmp plein).
            ok_esp, msg_esp = travail.verifier_espace(
                tmp, int(np.asarray(stack).nbytes) * (len(steps) + 2),
                f"la chaîne externe ({len(steps)} étape(s) + fichiers de "
                "travail)")
            if not ok_esp:
                self._set_ext_msg(msg_esp, state="error")
                return
            cur = os.path.join(tmp, "stack.fits")
            # Jalon 14 : les outils externes (GraXpert, et BXT côté PixInsight)
            # lisent le FITS avec les CANAUX sur NAXIS3 ((C, H, W) côté
            # astropy). Le save_image standard ((H, W, C) → NAXIS1=3) est MAL
            # LU et fait planter GraXpert dans cv2.resize
            # (« !dsize.empty() », boîte modale cx_Freeze) — constat réel
            # d'Alain le 17/09/2026 sur empilement RGB (Uranus-C Pro). Parade
            # déjà éprouvée du chemin live (external/live.py) : écrire
            # canaux-en-tête. Le mono 2D n'est pas concerné.
            gx_live._ecrire_entree(cur, stack)
            journal = os.path.join(tmp, "outils_sortie.txt")

            def run_step(name, cmd_tpl, src, outbase):
                cmd = (cmd_tpl.replace("{input}", src)
                              .replace("{output}", outbase + ".fits")
                              .replace("{outbase}", outbase))
                self._set_ext_msg(f"{name} en cours… ({n_frames} frames)", state="busy")
                # Jalon 14 : lanceur « survivable » (piège documenté du
                # 14/09/2026) — sorties dans un FICHIER et kill de
                # l'ARBORESCENCE au délai : un outil qui plante affiche sa
                # boîte modale puis meurt, au lieu de bloquer
                # subprocess.run(capture_output) pour toujours (le kill ne
                # touchait que cmd.exe, pas GraXpert).
                code, err = gx_live._run_bloquant_survivable(cmd, tmp, 1800)
                if err:
                    self._set_ext_msg(f"Erreur {name} : {err}", state="error")
                    return None
                if code != 0:
                    lignes = []
                    try:
                        with open(journal, encoding="utf-8",
                                  errors="replace") as f:
                            lignes = [l for l in f.read().splitlines() if l.strip()]
                    except OSError:
                        pass
                    detail = lignes[-1] if lignes else "aucun message"
                    self._set_ext_msg(f"Erreur {name} (code {code}) : {detail}",
                                      state="error")
                    return None
                res = find_output(src, outbase)      # extension/suffixe quelconques
                if res is None:
                    self._set_ext_msg(f"Erreur {name} : fichier de sortie introuvable "
                                      "(l'outil n'a rien écrit)", state="error")
                    return None
                return res

            for i, (name, kind, cmd_tpl) in enumerate(steps):
                outbase = os.path.join(tmp, f"step{i}")
                if kind == "dn_local":
                    # Jalon 8 : étape locale EN MÉMOIRE (pas de subprocess) —
                    # l'image courante est relue, débruitée (numpy/OpenCV)
                    # puis réécrite pour l'outil suivant de la chaîne.
                    self._set_ext_msg(f"{name} en cours… ({n_frames} frames)",
                                      state="busy")
                    # Jalon 14 : lecture normalisée ((3,H,W) → (H,W,3)) pour
                    # le débruiteur, réécriture canaux-en-tête pour l'outil
                    # suivant (cf. convention FITS des outils externes).
                    img_cur = gx_live._lire_sortie(cur)
                    img_dn, err = denoiser_local.denoiser(img_cur, mode_dn,
                                                          force_dn)
                    if err:
                        self._set_ext_msg(f"Erreur {name} : {err}",
                                          state="error")
                        return
                    cur = outbase + ".fits"
                    gx_live._ecrire_entree(cur, img_dn)
                    continue
                res = run_step(name, cmd_tpl, cur, outbase)
                if res is None:
                    return
                # Jalon 14 : normalise la sortie de l'outil ((3, H, W) →
                # (H, W, 3) le cas échéant) puis la réécrit canaux-en-tête
                # pour l'étape SUIVANTE — chaque outil reçoit la même
                # convention, quelle que soit celle de son prédécesseur.
                img_out = gx_live._lire_sortie(res)
                cur = outbase + "_conv.fits"
                gx_live._ecrire_entree(cur, img_out)

            img = gx_live._lire_sortie(cur)
            img = auto_unflip(img, stack)     # corrige un éventuel miroir vertical
            # Jalon 23b : sortie d'outil DÉGÉNÉRÉE (pixels non finis, image
            # vide — cf. le « plus d'image » en SHO sans S) → erreur claire
            # au lieu d'un résultat noir en visu / sauvegardé.
            if (not np.isfinite(img).all()
                    or float(np.max(np.abs(img))) < 1e-9):
                self._set_ext_msg("Erreur : sortie dégénérée de l'outil "
                                  "(pixels non finis ou image vide)",
                                  state="error")
                return
            # v2.48.0 (jalon 85) : la chaîne couleur a QUITTÉ la chaîne externe
            # (elle suit l'étirement : `display.couleur_apres_etirement`,
            # appliquée à l'affichage du résultat et à « tel que vu ») — le
            # résultat ⚡ est donc LINÉAIRE et non écrêté en vert.
            # v2.37.1 : NEUTRALISATION DU FOND puis RÉDUCTION DU BRUIT
            # CHROMATIQUE — les deux corrections pré-étirement de la chaîne live,
            # au même rang qu'elle (elles corrigent ce que l'ANCRE de VeraLux
            # amplifie ensuite : sa soustraction transforme 2 % d'écart de ciel
            # en un fond franc bleu, et les gains multiplicatifs — SPCC en tête —
            # amplifient le grain du canal qu'ils montent). Gains ANNONCÉS dans
            # le message final, comme dans « État des calculs » du live.
            gains_fond_ext = None
            if nf_ext:
                gains_fond_ext = couleurs_mod.gains_fond(img)
                if gains_fond_ext is not None \
                        and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                    img = couleurs_mod.neutraliser_fond(img)
            if chroma_ext:
                img = couleurs_mod.reduire_bruit_chroma(
                    img, force=force_chroma_ext, rayon=rayon_chroma_ext)
            if session != self._session:             # session relancée entre-temps
                return
            self.proc_full = img                     # pleine résolution (sauvegarde)
            # v2.38.3 : la chaîne QUI A PRODUIT ce résultat (outils et leurs
            # paramètres) est consignée dans l'en-tête du fichier enregistré.
            self.proc_entete = self._entete_externe(n_frames)
            h, w = img.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                img = cv2.resize(img, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            self.proc_show = img                     # version allégée (affichage)
            self.proc_new = True
            detail_fond = ""
            if gains_fond_ext is not None \
                    and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                detail_fond = (" · fond neutralisé (R %.4f / G %.4f / B %.4f)"
                               % gains_fond_ext)
            self._set_ext_msg(f"Traité à {time.strftime('%H:%M:%S')} "
                              f"({n_frames} frames){detail_fond}", state="ok")
        except Exception as e:
            self._set_ext_msg(f"Erreur : {e}", state="error")
        finally:
            self._fin_ext_tmp(tmp, session)

    def _fin_ext_tmp(self, tmp, session):
        """Fin de chaîne externe : nettoyage du dossier de travail — SAUF en cas
        d'échec, où il est CONSERVÉ et annoncé (v2.38.6).

        POURQUOI : le dossier était supprimé quoi qu'il arrive, donc le journal
        de l'outil (`outils_sortie.txt`), les FITS d'entrée et les sorties
        d'étape disparaissaient avec l'erreur — le « requested and written » du
        27/09/2026 était indiagnosticable. Un dossier VIDÉ (échec avant toute
        écriture) est supprimé comme avant (rien à conserver)."""
        try:
            if tmp is None:
                pass
            elif self.ext_state == "error":
                vide = True
                try:
                    vide = not os.listdir(tmp)
                except OSError:
                    vide = True
                if vide:
                    shutil.rmtree(tmp, ignore_errors=True)
                else:
                    self.ext_msg = (f"{self.ext_msg} — fichiers de travail "
                                    f"conservés : {tmp}")
            else:
                shutil.rmtree(tmp, ignore_errors=True)
        finally:
            if session == self._session:
                self.ext_busy = False

    def _run_external_compo(self, comp, canaux, n_frames, session):
        """Chaîne externe PAR COUCHE (jalon 24, décision d'Alain du 19/09/2026) :
        sur un instantané de la composition — GraXpert gradient et débruitage
        exécutés sur CHAQUE couche 2D (FITS mono — plus de piège RGB jalon 14),
        composite re-fait depuis les couches traitées, PUIS BXT et la chaîne
        couleur (SCNR…) sur le composite, comme la chaîne mono. Échec d'une
        étape sur une couche = la couche brute passe à la suite, message
        signalé — jamais de blocage, jamais d'image perdue. Même contrat de
        thread que _run_external (ext_busy géré par son finally)."""
        tmp = None
        try:
            (use_gx, cmd_gx, use_dn, cmd_dn, use_bxt, cmd_bxt,
             mode_dn, force_dn) = self.ext_job[:8]
            # v2.48.0 (jalon 85) : plus de chaîne couleur ici (elle suit
            # l'étirement, cf. `display.couleur_apres_etirement`) — seules les
            # corrections PRÉ-étirement restent dans cette chaîne.
            nf_ext = bool(self.ext_job[8]) if len(self.ext_job) > 8 else False
            chroma_ext = bool(self.ext_job[9]) if len(self.ext_job) > 9 \
                else False
            force_chroma_ext = (float(self.ext_job[10])
                                if len(self.ext_job) > 10 else 0.5)
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma (12e élément —
            # déballage tolérant, comme la chaîne mono).
            rayon_chroma_ext = (float(self.ext_job[11])
                                if len(self.ext_job) > 11
                                else couleurs_mod.RAYON_CHROMA_DEFAUT)
            tmp = travail.creer_dossier("avastack_compo_")
            journal = os.path.join(tmp, "outils_sortie.txt")
            n_etapes = ((len(canaux) if use_gx else 0)
                        + (len(canaux) if use_dn and mode_dn == "graxpert"
                           else 0))
            # v2.38.6 : espace vérifié AVANT d'écrire (entrée + une sortie par
            # étape) — refus chiffré et immédiat plutôt qu'un volume saturé en
            # pleine chaîne. Placé APRÈS `n_etapes` (piège attrapé par le banc
            # jalon 24 : un `NameError` ici était avalé par le `except` et
            # l'échec apparaissait… en silence).
            ok_esp, msg_esp = travail.verifier_espace(
                tmp, int(np.asarray(comp).nbytes) * (n_etapes + 2),
                f"la chaîne externe par couche ({n_etapes} étape(s))")
            if not ok_esp:
                self._set_ext_msg(msg_esp, state="error")
                return
            i_etape, msgs = 0, []   # noqa: F841 (avertissement préexistant)
            traites = self._compo_couches_traitees(
                canaux, use_gx, cmd_gx, use_dn, cmd_dn, mode_dn, force_dn,
                tmp, journal, n_frames, n_etapes, msgs)
            if traites is None:
                return                      # erreur déjà posée par _ext_run_cmd
            comp_traite = composition_mod.composer(
                traites, self.stacker.composition,
                mode_l=self.stacker.mode_l,
                # v2.36.0 : même normalisation que la vue live — sinon la sortie
                # traitée ne serait pas au même niveau que l'écran.
                normalisation_commune=bool(getattr(
                    self.stacker, "normalisation_commune", False)))
            if comp_traite is None:
                self._set_ext_msg("Erreur : recomposition impossible après "
                                  "traitement par couche", state="error")
                return
            comp_traite = np.asarray(comp_traite, dtype=np.float32)
            # Chantier 24/09/2026 (décision (b)) : les CORRECTIONS DE COULEUR de
            # la chaîne de sortie s'appliquent ICI, sur le composite re-fait
            # depuis les couches traitées — exactement comme le solveur live.
            # Les couches, elles, restent BRUTES (contrat jalon 54).
            gains_ext = (self.stacker.gains_effectifs()
                         if hasattr(self.stacker, "gains_effectifs")
                         else self.stacker.gains)
            comp_traite, _d = composition_mod.corrections_couleur(
                comp_traite,
                gains=gains_ext,
                wb_auto=bool(getattr(self.stacker, "wb_auto", False)),
                wb_force=float(getattr(self.stacker, "wb_force", 1.0)),
                cadre=getattr(self.stacker, "cadre", None),
                linear_fit=bool(getattr(self.stacker, "linear_fit", False)),
                linear_fit_mode=getattr(self.stacker, "linear_fit_mode",
                                        "offset"))
            # --- Suite de la chaîne SUR LE COMPOSITE : BXT et chaîne couleur
            # — identique à la fin de la chaîne mono.
            cur = os.path.join(tmp, "comp_traite.fits")
            gx_live._ecrire_entree(cur, comp_traite)
            if use_bxt:
                outbase = os.path.join(tmp, "bxt")
                res = self._ext_run_cmd("BlurXTerminator", cmd_bxt, cur,
                                        outbase, tmp, journal, n_frames)
                if res is None:
                    return
                cur = res
            img = gx_live._lire_sortie(cur)
            img = auto_unflip(img, comp)
            if (not np.isfinite(img).all()
                    or float(np.max(np.abs(img))) < 1e-9):
                self._set_ext_msg("Erreur : sortie dégénérée de l'outil "
                                  "(pixels non finis ou image vide)",
                                  state="error")
                return
            # v2.48.0 (jalon 85) : la chaîne couleur a QUITTÉ la chaîne externe
            # (composition comprise) — elle suit l'étirement et est appliquée à
            # l'affichage / « tel que vu » (`display.couleur_apres_etirement`).
            # v2.37.1 : neutralisation du fond puis réduction du bruit
            # chromatique (chaîne live) — sur le COMPOSITE re-fait, comme les
            # SCNR ; les couches restent brutes (contrat jalon 54).
            gains_fond_ext = None
            if nf_ext:
                gains_fond_ext = couleurs_mod.gains_fond(img)
                if gains_fond_ext is not None \
                        and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                    img = couleurs_mod.neutraliser_fond(img)
            if chroma_ext:
                img = couleurs_mod.reduire_bruit_chroma(
                    img, force=force_chroma_ext, rayon=rayon_chroma_ext)
            if session != self._session:      # session relancée entre-temps
                return
            self.proc_full = img
            self.proc_entete = self._entete_externe(n_frames)   # v2.38.3
            h, w = img.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                img = cv2.resize(img, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            self.proc_show = img
            self.proc_new = True
            if gains_fond_ext is not None \
                    and not np.allclose(gains_fond_ext, 1.0, atol=1e-4):
                msgs.append("fond neutralisé (R %.4f / G %.4f / B %.4f)"
                            % gains_fond_ext)
            detail = (" ; ".join(msgs) + " — ") if msgs else ""
            self._set_ext_msg(f"{detail}Traité par couche à "
                              f"{time.strftime('%H:%M:%S')} ({n_frames} "
                              "frames)", state="ok" if not msgs else "busy")
        except Exception as e:
            self._set_ext_msg(f"Erreur : {e}", state="error")
        finally:
            self._fin_ext_tmp(tmp, None)

    def _compo_couches_traitees(self, canaux, use_gx, cmd_gx, use_dn, cmd_dn,
                                mode_dn, force_dn, tmp, journal, n_frames,
                                n_etapes, msgs):
        """Chaîne PAR COUCHE du traitement externe (jalon 24), avec le GRADIENT
        EN UN SEUL LOT (jalon 83) et le DÉBRUITAGE couche par couche.

        POURQUOI le lot POUR LE GRADIENT SEUL : les couches sont INDÉPENDANTES et
        chaque appel GraXpert paie un démarrage FIXE (~3,4 s, identiques sur
        iGPU, RTX 4070 et RTX 4060 Ti) — les lancer ensemble recouvre ces temps
        morts : **+57 à +60 % sur les trois machines**, sorties identiques AU BIT
        (banc `_test_gx_lot_externe_jalon83`). Le DÉBRUITAGE reste en SÉRIE : sur
        ces mêmes trois machines son lot ne rapporte rien (un appel sature déjà
        le GPU : −13 % sur iGPU, +12,9 % sur 4070, +1,2 % sur 4060 Ti) et il
        coûte 2,2 à 3,7 Go de VRAM par appel.

        → dict rôle → couche traitée, ou None (échec TOTAL du gradient, ou échec
        d'un subprocess de débruitage : message posé, chaîne arrêtée — même
        politique que la chaîne mono ; un échec PARTIEL du gradient conserve la
        couche brute, le signale, et la chaîne continue)."""
        traites = {}
        i_etape = 0
        couches = {role: np.asarray(couche, dtype=np.float32)
                   for role, couche in canaux.items()}
        # --- ① GRADIENT : UN SEUL LOT pour toutes les couches (jalon 83).
        # Validation du GABARIT et de l'exécutable AVANT tout lancement — mêmes
        # messages que la chaîne mono (leçon du jalon 24 : après substitution les
        # placeholders n'existent plus, on ne peut plus les vérifier).
        if use_gx:
            if ("{input}" not in cmd_gx
                    or ("{output}" not in cmd_gx
                        and "{outbase}" not in cmd_gx)):
                self._set_ext_msg("Commande GraXpert gradient incomplète : il "
                                  "manque {input} ou {output}/{outbase}.",
                                  state="error")
                return None
            manque = gx_live.outil_manquant(cmd_gx)
            if manque:
                self._set_ext_msg(
                    f"GraXpert gradient : {manque} — désignez l'exécutable avec "
                    "le bouton « … » du cadre « Traitement externe (long) ».",
                    state="error")
                return None
            a_lancer = []                    # (rôle, couche) à envoyer à l'outil
            for role, c in couches.items():
                if float(np.max(np.abs(c))) < 1e-9:
                    msgs.append(f"GraXpert ({role}) : couche vide — ignorée")
                else:
                    a_lancer.append((role, c))
            if a_lancer:
                i_etape += len(a_lancer)
                self._set_ext_msg(
                    f"GraXpert gradient : {len(a_lancer)} couche(s) en "
                    f"parallèle… ({n_frames} frames)", state="busy")
                lot = gx_live.appliquer_lot(
                    [(role, c, cmd_gx) for role, c in a_lancer])
                echecs = 0
                for role, _c in a_lancer:
                    c2, err = lot.get(role, (None, "appel non exécuté"))
                    if err or c2 is None:
                        echecs += 1
                        msgs.append(f"GraXpert ({role}) : "
                                    f"{err or 'aucun résultat'}")
                    else:
                        couches[role] = c2.astype(np.float32)
                if echecs == len(a_lancer):
                    # ÉCHEC TOTAL : on ARRÊTE et on le dit — continuer
                    # produirait une image « traitée » qui ne l'est pas.
                    self._set_ext_msg(
                        "Erreur GraXpert gradient : "
                        + (msgs[-1] if msgs else "aucun résultat"),
                        state="error")
                    return None
        # --- ② DÉBRUITAGE par couche : SÉRIE (mesuré : le lot n'apporte rien).
        # L'entrée du subprocess est la couche APRÈS gradient, écrite ici dans le
        # dossier de la chaîne (le gradient travaille, lui, dans le sien).
        for role, c in list(couches.items()):
            if use_dn:
                if mode_dn == "graxpert":
                    src = os.path.join(tmp, f"dn_in_{role}.fits")
                    gx_live._ecrire_entree(src, c)
                    i_etape += 1
                    outbase = os.path.join(tmp, f"dn_{role}")
                    res = self._ext_run_cmd(
                        f"GraXpert débruitage {role}", cmd_dn, src, outbase,
                        tmp, journal, n_frames, f" ({i_etape}/{n_etapes})")
                    if res is None:
                        return None
                    c2 = auto_unflip(gx_live._lire_sortie(res), c)
                    if (not np.isfinite(c2).all()
                            or float(np.max(np.abs(c2))) < 1e-9):
                        msgs.append(f"Débruitage ({role}) : sortie dégénérée "
                                    "— couche brute conservée")
                    else:
                        c = c2.astype(np.float32)
                else:
                    c2, err = denoiser_local.denoiser(c, mode_dn, force_dn)
                    if err:
                        msgs.append(f"Débruitage ({role}) : {err}")
                    else:
                        c = c2
            traites[role] = c
        return traites

    def _ext_run_cmd(self, name, cmd_tpl, src, outbase, tmp, journal,
                     n_frames, progression=""):
        """Une étape SUBPROCESS de la chaîne externe (jalon 24) : lanceur
        « survivable » partagé avec la chaîne mono, progression par étape.
        → chemin du fichier de sortie, ou None (message d'erreur déjà posé)."""
        # Validation du GABARIT AVANT substitution (après, les placeholders
        # n'existent plus — leçon du débogage du jalon 24).
        if ("{input}" not in cmd_tpl or ("{output}" not in cmd_tpl
                                         and "{outbase}" not in cmd_tpl)):
            self._set_ext_msg(f"Commande {name} incomplète : il manque "
                              "{{input}} ou {output}/{outbase}.", state="error")
            return None
        # v2.38.5 : outil introuvable = échec ANNONCÉ (au lieu d'un « command
        # not found » du shell, noyé dans la sortie de l'outil et illisible).
        manque = gx_live.outil_manquant(cmd_tpl)
        if manque:
            self._set_ext_msg(
                f"{name} : {manque} — désignez l'exécutable avec le bouton "
                "« … » du cadre « Traitement externe (long) ».",
                state="error")
            return None
        cmd = (cmd_tpl.replace("{input}", src)
                      .replace("{output}", outbase + ".fits")
                      .replace("{outbase}", outbase))
        self._set_ext_msg(f"{name} en cours…{progression} ({n_frames} frames)",
                          state="busy")
        code, err = gx_live._run_bloquant_survivable(cmd, tmp, 1800)
        if err:
            self._set_ext_msg(f"Erreur {name} : {err}", state="error")
            return None
        if code != 0:
            lignes = []
            try:
                with open(journal, encoding="utf-8", errors="replace") as f:
                    lignes = [l for l in f.read().splitlines() if l.strip()]
            except OSError:
                pass
            detail = lignes[-1] if lignes else "aucun message"
            self._set_ext_msg(f"Erreur {name} (code {code}) : {detail}",
                              state="error")
            return None
        res = find_output(src, outbase)
        if res is None:
            self._set_ext_msg(f"Erreur {name} : fichier de sortie introuvable "
                              "(l'outil n'a rien écrit)", state="error")
            return None
        return res
