# -*- coding: utf-8 -*-
"""Banc de test autonome caméra QHY — utilise le MÊME code que l'appli.

Demande d'Alain (19/09/2026) : déboguer la caméra HORS de l'application,
sans la complexité du live stacking ni la relance des tests de non-
régression. Ce programme réutilise `avastack.cameras.qhy.QHYCamera` TEL
QUEL : détection, ouverture (2 séquences), énumération de TOUS les
contrôles du SDK, flux live affiché.

IMPORTANT — crash natif : si la fenêtre se ferme brutalement sans
message, c'est un segfault du SDK natif (Python ne peut rien afficher).
Ouvre alors le log d'étapes (bouton « 📄 Ouvrir le log » ou fichier
avastack_qhy_debug.log du dossier temp) : la DERNIÈRE ligne indique
l'étape fatale — c'est elle qu'il faut rapporter.

Deux boutons de démarrage :
  - « ▶ Démarrer (séquence APPLI) »  : appelle QHYCamera.open() tel quel —
    si l'appli crashe, ce bouton crashe au même endroit (avec la trace) ;
  - « ▶ Démarrer (pas-à-pas + ROI) » : la même séquence décomposée ici,
    avec possibilité d'IMPOSER la ROI (set_resolution) avant begin_live —
    l'hypothèse « buffer non alloué sans ROI » est testable en un clic.

Lancement (venv, dossier contenant avastack/) :
    venv/Scripts/python.exe _diag_camera_qhy.py
Sur le miniPC installé : copier CE FICHIER dans le dossier d'installation
(%LOCALAPPDATA%/AVAStack) puis :
    venv/Scripts/python.exe _diag_camera_qhy.py
"""
import os
import sys
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import Image, ImageTk

# Le banc importe le code de l'application depuis SON PROPRE dossier
# (fonctionne depuis le dépôt comme depuis %LOCALAPPDATA%/AVAStack).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import avastack.cameras.qhy as mqhy
from avastack.cameras.qhy import QHYCamera

FICHIER_LOG = mqhy.FICHIER_TRACE

# Numérotation de l'enum QHYCCD_CONTROL du SDK C (les principaux) — les
# noms manquants sont des contrôles secondaires, la valeur reste lue.
NOMS_CTRL = {1: "EXP", 2: "GAIN", 3: "OFFSET", 4: "USBTRAFFIC", 5: "SPEED",
             6: "CAMSINGLEFRAMEMODE", 7: "CAMLIVEVIDEOMODE",
             9: "AUTOEXPOSURE", 26: "COOLERON", 31: "AUTOBANDBALANCE",
             37: "USB3", 38: "USBGAIN", 40: "SensorTemperature"}


class BancQHY:
    def __init__(self, root):
        self.root = root
        self.cam = None              # QHYCamera (même classe que l'appli)
        self.camera_id = ""          # id détecté (scan)
        self._flux_actif = False
        self._aperçu = None          # dernière frame float32 [0..1]
        self._photo = None
        self._dims = "—"
        self._fps = 0.0
        self._n = 0
        self._t0 = 0.0
        self.q_msg = queue.Queue()   # messages thread → UI (jamais de Tk
                                     # hors thread principal)
        self._lbl_cam_txt = None
        self._btn_demande = None     # "flux" | "libre" (consommé par _tick)
        self._construire()
        self._log_direct(f"Log d'étapes : {FICHIER_LOG}")
        self._log_direct("Si la fenêtre meurt sans message : crash natif du "
                         "SDK — regarde le log (bouton 📄).")
        self.root.after(40, self._tick)

    def _trace(self, msg):
        """Trace côté thread : fichier persistant + file → log de l'UI."""
        mqhy._tracer("[diag] " + msg)
        self.q_msg.put(msg)

    def _log_direct(self, msg):
        self.txt.config(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def _construire(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="🔎 Détecter", command=self._detecter).pack(
            side="left")
        self.lbl_cam = ttk.Label(top, text="— cliquer sur « Détecter » —")
        self.lbl_cam.pack(side="left", padx=8)

        box = ttk.LabelFrame(self.root, text="Réglages (transmis à la "
                                              "caméra)", padding=6)
        box.pack(fill="x", padx=6)
        ttk.Label(box, text="Expo (ms)").pack(side="left")
        self.var_expo = tk.StringVar(value="100")
        ttk.Entry(box, textvariable=self.var_expo, width=7).pack(
            side="left", padx=(2, 10))
        ttk.Label(box, text="Gain (unités SDK QHY)").pack(side="left")
        self.var_gain = tk.StringVar(value="10")
        ttk.Entry(box, textvariable=self.var_gain, width=7).pack(
            side="left", padx=(2, 10))
        ttk.Label(box, text="Offset").pack(side="left")
        self.var_offset = tk.StringVar(value="10")
        ttk.Entry(box, textvariable=self.var_offset, width=7).pack(
            side="left", padx=(2, 10))
        self.var_roi = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Imposer la ROI (set_resolution) :",
                        variable=self.var_roi).pack(side="left", padx=(14, 2))
        self.var_w = tk.StringVar(value="3840")   # IMX585 QHY MiniCam8M
        self.var_h = tk.StringVar(value="2160")   # (3864×2192 = fiche Player
        # One, REFUSÉE par le SDK QHY — erreur 0xFFFFFFFF, constat du test)
        ttk.Entry(box, textvariable=self.var_w, width=7).pack(
            side="left", padx=(2, 2))
        ttk.Label(box, text="×").pack(side="left")
        ttk.Entry(box, textvariable=self.var_h, width=7).pack(
            side="left", padx=(2, 0))

        act = ttk.Frame(self.root, padding=6)
        act.pack(fill="x")
        self.btn_start = ttk.Button(act, text="▶ Démarrer (séquence APPLI)",
                                    command=lambda: self._demarrer(False))
        self.btn_start.pack(side="left")
        self.btn_start2 = ttk.Button(act, text="▶ Démarrer (pas-à-pas + ROI)",
                                     command=lambda: self._demarrer(True))
        self.btn_start2.pack(side="left", padx=(6, 0))
        self.btn_stop = ttk.Button(act, text="■ Arrêter",
                                   command=self._arreter, state="disabled")
        self.btn_stop.pack(side="left", padx=(6, 0))
        ttk.Button(act, text="📋 Lister les contrôles",
                   command=self._lister_controles).pack(side="left",
                                                        padx=(6, 0))
        ttk.Button(act, text="📄 Ouvrir le log",
                   command=self._ouvrir_log).pack(side="left", padx=(6, 0))

        self.lbl_img = ttk.Label(self.root, anchor="center",
                                 text="\n\n(le flux apparaîtra ici)\n\n")
        self.lbl_img.pack(fill="both", expand=True, padx=6, pady=4)
        self.lbl_fps = ttk.Label(self.root, text="—")
        self.lbl_fps.pack()
        self.txt = tk.Text(self.root, height=10, state="disabled",
                           font=("Consolas", 9))
        self.txt.pack(fill="both", padx=6, pady=(0, 6))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _tick(self):
        # Consommation des messages du thread → log de l'UI
        try:
            while True:
                self._log_direct(self.q_msg.get_nowait())
        except queue.Empty:
            pass
        if self._lbl_cam_txt is not None:
            self.lbl_cam.config(text=self._lbl_cam_txt,
                                foreground="#1d7f1d")
            self._lbl_cam_txt = None
        # Affichage de la dernière frame (normalisation min→max, mono)
        a = self._aperçu
        if a is not None:
            self._aperçu = None
            mn, mx = float(np.min(a)), float(np.max(a))
            v = np.zeros_like(a) if mx <= mn else (a - mn) / (mx - mn)
            pil = Image.fromarray((v * 255.0).astype(np.uint8), mode="L")
            pil.thumbnail((860, 540))
            self._photo = ImageTk.PhotoImage(pil)
            self.lbl_img.config(image=self._photo, text="")
        if self._flux_actif:
            self.lbl_fps.config(text=f"{self._fps:.1f} fps — {self._dims}")
        # États des boutons demandés depuis les threads
        if self._btn_demande == "flux":
            self._btn_demande = None
            self.btn_start.config(state="disabled")
            self.btn_start2.config(state="disabled")
            self.btn_stop.config(state="normal")
        elif self._btn_demande == "libre":
            self._btn_demande = None
            self.btn_start.config(state="normal")
            self.btn_start2.config(state="normal")
            self.btn_stop.config(state="disabled")
        self.root.after(40, self._tick)

    def _detecter(self):
        threading.Thread(target=self._detecter_thread, daemon=True).start()

    def _detecter_thread(self):
        self._trace("scan (sous-processus isolé)…")
        ids, err = mqhy.lister_via_sous_processus()
        if err is not None:
            self.q_msg.put("détection : ERREUR — " + err)
            return
        if not ids:
            self.q_msg.put("détection : aucune caméra QHY détectée "
                           "(USB ? driver ?)")
            return
        self.camera_id = str(ids[0])
        self._lbl_cam_txt = "détectée : " + ", ".join(map(str, ids))
        self.q_msg.put(f"détection OK : {len(ids)} caméra(s) — "
                       f"la 1re sera ouverte")

    def _demarrer(self, pasapas):
        if self._flux_actif:
            return
        try:
            expo = float(self.var_expo.get().replace(",", "."))
            gain = float(self.var_gain.get().replace(",", "."))
            offset = float(self.var_offset.get().replace(",", "."))
            roi = ((int(self.var_w.get()), int(self.var_h.get()))
                   if self.var_roi.get() else None)
        except ValueError:
            messagebox.showerror("Réglages", "Expo/Gain/Offset/ROI : "
                                 "nombres invalides.")
            return
        self.btn_start.config(state="disabled")
        self.btn_start2.config(state="disabled")
        threading.Thread(target=self._demarrer_thread,
                         args=(pasapas, expo, gain, offset, roi),
                         daemon=True).start()

    def _demarrer_thread(self, pasapas, expo, gain, offset, roi):
        try:
            if not self.camera_id:
                ids = QHYCamera.lister()
                if not ids:
                    raise RuntimeError("aucune caméra QHY détectée "
                                       "(bouton 🔎 Détecter d'abord)")
                self.camera_id = str(ids[0])
                self._lbl_cam_txt = "détectée (auto) : " + self.camera_id
            if pasapas:
                self._ouvrir_pasapas(roi)
            else:
                self._trace("démarrage via QHYCamera.open() "
                            "(séquence EXACTE de l'application)")
                self.cam = QHYCamera(camera_id=self.camera_id)
                self.cam.open()
            self.cam.apply_settings(expo, gain)
            self._trace(f"apply_settings : expo {expo:g} ms "
                        f"({int(expo * 1000)} µs), gain {gain:g}")
            if self.cam.cam is not None:
                try:
                    self.cam.cam.set_offset(offset)
                    self._trace(f"set_offset({offset:g}) OK")
                except Exception as e:
                    self._trace(f"set_offset ignoré ({e})")
            # Premier frame diagnostique : shape/dtype RÉELS du buffer.
            # NB (constat réel) : juste après begin_live, la 1re image n'est
            # pas encore prête (exposition de 1000 ms !) → le SDK renvoie
            # son erreur 0xFFFFFFFF pendant ~1 s. Ce n'est PAS une erreur :
            # on patiente et on réessaie avant de déclarer un problème.
            f = None
            for essai in range(12):        # 12 × 0,5 s = 6 s max
                try:
                    f = self.cam.cam.get_live_frame()
                    break
                except Exception as e:
                    if essai == 0:
                        self._trace(f"1er get_live_frame() : {e} — la 1re "
                                    "image n'est pas encore prête "
                                    "(exposition en cours), essais…")
                    time.sleep(0.5)
            if f is None:
                self._trace("1er get_live_frame() : aucune image reçue "
                            "en 6 s — voir erreurs ci-dessus")
            else:
                a = np.asarray(f)
                self._dims = f"{a.shape[1]}×{a.shape[0]} px"
                self._trace(f"1er frame : shape={a.shape} dtype={a.dtype} "
                            f"min={a.min()} max={a.max()}")
            self._flux_actif = True
            self._n = 0
            self._t0 = time.time()
            threading.Thread(target=self._boucle, daemon=True).start()
            self._btn_demande = "flux"
            self._trace("flux démarré ✔")
        except Exception as e:
            self._trace(f"ERREUR : {e}")
            self._btn_demande = "libre"

    def _ouvrir_pasapas(self, roi):
        """Séquence officielle DÉCOMPOSÉE : chaque étape tracée + ROI
        imposable avant begin_live (test de l'hypothèse « buffer non
        alloué sans set_resolution »). Réutilise QHYCamera pour read()/
        close() (self.cam.cam = handle du binding)."""
        self._trace("=== séquence pas-à-pas (chaque étape tracée) ===")
        import qhyccd
        qhyccd.init_sdk()
        self._trace("init_sdk() OK")
        ids = list(qhyccd.scan_cameras())
        self._trace(f"scan_cameras() -> {ids}")
        if not ids:
            raise RuntimeError("scan vide : aucune caméra QHY")
        cid = self.camera_id if self.camera_id in ids else ids[0]
        cam = qhyccd.Camera(cid)
        self._trace(f"Camera({cid!r}) ouverte (constructeur)")
        self.cam = QHYCamera(camera_id=cid)
        self.cam.cam = cam          # read()/close() de la classe pour la suite
        self.cam.name = f"QHY {cid}"
        cam.set_stream_mode(1)
        self._trace("set_stream_mode(1) OK")
        cam.init()
        self._trace("init() OK")
        cam.set_bin_mode(1, 1)
        self._trace("set_bin_mode(1,1) OK")
        if roi is not None:
            w, h = roi
            tailles = [(w, h)] + [t for t in [(3840, 2160), (3856, 2180),
                                              (3848, 2168), (1920, 1080)]
                                  if t != (w, h)]
            posee = False
            for tw, th in tailles:
                try:
                    cam.set_resolution(0, 0, tw, th)
                    self._trace(f"set_resolution(0,0,{tw},{th}) OK")
                    posee = True
                    break
                except Exception as e:
                    self._trace(f"set_resolution(0,0,{tw},{th}) REFUSÉE ({e})"
                                " — taille invalide pour ce capteur")
            if not posee:
                raise RuntimeError("aucune ROI acceptée par le SDK — "
                                   "essayer d'autres dimensions")
        else:
            self._trace("(ROI non imposée — zone par défaut du SDK)")
        cam.begin_live()
        self._trace("begin_live() OK")

    def _boucle(self):
        """Boucle de lecture du flux (thread) — QHYCamera.read(), la même
        méthode que dans l'application. Tolérante aux erreurs transitoires
        (entre deux frames, pendant l'exposition, le SDK répond par son
        erreur 0xFFFFFFFF : on réessaie au lieu d'abandonner)."""
        echecs = 0
        t_dernier_msg = time.time()
        while self._flux_actif and self.cam is not None:
            try:
                f = self.cam.read()
            except Exception as e:
                self._trace(f"read() : {e}")
                break
            if f is None:
                echecs += 1
                if (echecs > 1 and time.time() - t_dernier_msg > 2.0):
                    self._trace(f"{echecs} lectures sans frame (exposition "
                                "longue ?) — réessais en cours")
                    t_dernier_msg = time.time()
                if echecs > 400:               # ~4 s sans AUCUNE frame
                    self._trace(f"arrêt : aucune frame après "
                                f"{echecs} essais (voir log)")
                    break
                time.sleep(0.01)
                continue
            echecs = 0
            if self._dims == "—":
                self._dims = f"{f.shape[1]}×{f.shape[0]} px"
            self._aperçu = f
            self._n += 1
            dt = time.time() - self._t0
            if dt >= 1.0:
                self._fps = self._n / dt
                self._n = 0
                self._t0 = time.time()
        self._trace("boucle de flux terminée")

    def _arreter(self):
        self._flux_actif = False
        threading.Thread(target=self._fermer_thread, daemon=True).start()

    def _fermer_thread(self):
        if self.cam is not None:
            try:
                self.cam.close()
                self._trace("close OK")
            except Exception as e:
                self._trace(f"close : {e}")
            self.cam = None
        self._btn_demande = "libre"

    def _lister_controles(self):
        threading.Thread(target=self._lister_thread, daemon=True).start()

    def _lister_thread(self):
        """Énumère TOUS les contrôles du SDK (1..63) : is_control_available
        puis get_param (valeur courante). Nécessite la caméra ouverte."""
        if self.cam is None or self.cam.cam is None:
            self.q_msg.put("lister : ouvre d'abord la caméra (▶ Démarrer)")
            return
        self.q_msg.put("=== contrôles disponibles (is_control_available) ===")
        dispo = 0
        for ctrl in range(1, 64):
            try:
                if not self.cam.cam.is_control_available(ctrl):
                    continue
            except Exception as e:
                self.q_msg.put(f"ctrl {ctrl} : erreur {e}")
                continue
            dispo += 1
            try:
                val = self.cam.cam.get_param(ctrl)
            except Exception as e:
                val = f"(erreur {e})"
            self.q_msg.put(f"ctrl {ctrl:>2} {NOMS_CTRL.get(ctrl, ''):<16} "
                           f"valeur={val}")
        self.q_msg.put(f"({dispo} contrôles disponibles sur 1..63)")

    def _ouvrir_log(self):
        if os.path.isfile(FICHIER_LOG):
            os.startfile(FICHIER_LOG)
        else:
            messagebox.showinfo("Log", f"Aucun log à :\n{FICHIER_LOG}")

    def _on_close(self):
        self._flux_actif = False
        if self.cam is not None:
            try:
                self.cam.close()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    root.title("Banc de test QHY — AVAStack (diagnostic, même code caméra)")
    root.geometry("1020x860")
    BancQHY(root)
    root.mainloop()


if __name__ == "__main__":
    main()