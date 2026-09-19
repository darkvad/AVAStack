# -*- coding: utf-8 -*-
"""Banc de test autonome caméra SVBONY — la MÊME DLL que l'appli.

Demande d'Alain (19/09/2026) : tester la SVBONY SV305C (guidage sur
lunette 60/240 du 2e setup) avec le même programme de détection de ses
possibilités que les bancs QHY (_diag_camera_qhy.py) et Player One
(_diag_camera_playerone.py) : capteur, TEC, offset, exposition, gain, ROI,
binning, formats, flux.

POURQUOI ce banc ne réécrit PAS la sonde : depuis la v2.16.0, la lecture
des capacités vit dans l'application (`avastack/cameras/svbony.py` →
`SVBonyCamera.detecter_capacites()`, validée par `_test_capacites.py`).
Le banc la RÉUTILISE (une seule définition — deux copies finissent par
diverger, leçon du banc POA) et n'ajoute que l'interactif : poses de
réglages, flux live, rapport.

L'API SVBONY est un quasi-clone de ZWO ASI (cf. en-tête officiel
SVBCameraSDK.h, déposé dans le projet pysvb) :
  - procédure recommandée : GetNumOfConnectedCameras → GetCameraProperty →
    OpenCamera → GetNumOfControls → GetControlCaps (+ get/set values) →
    SetROIFormat → StartVideoCapture → boucle GetVideoData → Stop → Close.
    PAS de SVBInitCamera : `SVBOpenCamera` suffit (36 exports vérifiés dans
    la DLL du dépôt).
  - contrôles (SVB_CONTROL_TYPE 0-19) : GAIN=0, EXPOSURE=1 (µs), GAMMA=2,
    WB_R/G/B=4/5/6, FLIP=7 (0=aucun,1=horiz,2=vert,3=les deux),
    FRAME_SPEED_MODE=8, BLACK_LEVEL=13 (« offset »), COOLER_ENABLE=14,
    TARGET_TEMPERATURE=15, CURRENT_TEMPERATURE=16 (unités 0,1 °C !),
    COOLER_POWER=17.
  - erreurs 0-19 (SVB_SUCCESS … SVB_ERROR_UNKNOW_SENSOR_TYPE), nommées dans
    le log.
  - SVB_CAMERA_PROPERTY.SupportedBins : « 0 is the end » (terminateur
    explicite, contrairement à Player One).

⚠ VERSION DE L'APPLICATION : comme le banc POA, ce banc RÉUTILISE la sonde
de l'application. Si la copie INSTALLÉE est antérieure (pas de
`detecter_capacites` dans avastack/cameras/svbony.py), il le DIT clairement
(bannière rouge + journal) au lieu de planter — copier
`avastack/cameras/svbony.py` et `avastack/cameras/capacites.py`, ou
réinstaller ≥ 2.16.0. La DÉTECTION reste utilisable sans eux.

Lancement (venv, dossier du projet ou %LOCALAPPDATA%/AVAStack) :
    venv/Scripts/python.exe _diag_camera_svbony.py
Mode console (détection rapide sans fenêtre) :
    venv/Scripts/python.exe _diag_camera_svbony.py --console

⚠ CRASH NATIF : si la fenêtre se ferme brutalement sans message, c'est un
segfault du SDK natif — noter la DERNIÈRE ligne du log.
⚠ UN SEUL PROGRAMME à la fois peut ouvrir la caméra : fermer le banc avant
de lancer AVAStack, et inversement.
"""
import ctypes
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import Image, ImageTk

# Le banc importe le code de l'application depuis SON PROPRE dossier
# (fonctionne depuis le dépôt comme depuis %LOCALAPPDATA%/AVAStack).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- chargement DIAGNOSTIQUÉ de l'application (même principe que le banc
#     Player One : symboles attendus vérifiés, message clair si trop ancien).
_ERREUR_CHARGEMENT = ""
_MANQUE = []
try:
    import avastack.cameras.svbony as msvb
except Exception as e:
    msvb = None
    _ERREUR_CHARGEMENT = f"{type(e).__name__} : {e}"

if msvb is not None:
    for _nom in ("_SVBCameraInfo", "_SVBCameraProperty", "_SVBControlCaps",
                 "SVB_SUCCESS", "SVB_EXPOSURE", "SVB_GAIN",
                 "SVB_BLACK_LEVEL", "SVB_COOLER_ENABLE",
                 "SVB_TARGET_TEMPERATURE", "SVB_CURRENT_TEMPERATURE",
                 "SVB_COOLER_POWER", "NOMS_FORMATS_SVB",
                 "SVBonyCamera", "_charger_sdk"):
        if not hasattr(msvb, _nom):
            _MANQUE.append(_nom)
    if not _MANQUE:
        for _nom in ("detecter_capacites",):
            if not hasattr(msvb.SVBonyCamera, _nom):
                _MANQUE.append(f"SVBonyCamera.{_nom}")

# Le banc est COMPLET seulement si la copie installée expose la sonde.
BANC_PRET = (msvb is not None and not _MANQUE)

# --- constantes du SDK SVBONY (SVBCameraSDK.h) --------------------------------
SVB_IMG_RAW8 = 0
SVB_IMG_RAW10 = 1
SVB_IMG_RAW12 = 2
SVB_IMG_RAW14 = 3
SVB_IMG_RAW16 = 4
SVB_IMG_Y8 = 5
SVB_IMG_Y16 = 9
SVB_IMG_RGB24 = 10
SVB_IMG_RGB32 = 11

SVB_FLIP_NONE, SVB_FLIP_HORIZ, SVB_FLIP_VERT, SVB_FLIP_BOTH = 0, 1, 2, 3

BAYER = {0: "RG", 1: "BG", 2: "GR", 3: "GB"}

NOMS_ERREURS = {
    0: "OK", 1: "INDEX invalide", 2: "ID caméra invalide",
    3: "TYPE DE CONTRÔLE invalide", 4: "CAMÉRA NON OUVERTE",
    5: "CAMÉRA DÉBRANCHÉE", 6: "CHEMIN invalide", 7: "FORMAT de fichier",
    8: "TAILLE invalide", 9: "TYPE D'IMAGE non supporté",
    10: "DÉPART HORS CADRE", 11: "TIMEOUT", 12: "SÉQUENCE invalide",
    13: "BUFFER TROP PETIT", 14: "MODE VIDÉO ACTIF",
    15: "EXPOSITION EN COURS", 16: "ERREUR GÉNÉRALE",
    17: "MODE invalide", 18: "DIRECTION invalide",
    19: "CAPTEUR INCONNU",
}

# octets par pixel selon le type d'image (les RAW10/12/14 sont stockés
# sur 2 octets par pixel, comme chez ZWO)
OCTETS_PIXEL = {SVB_IMG_RAW8: 1, SVB_IMG_RAW10: 2, SVB_IMG_RAW12: 2,
                SVB_IMG_RAW14: 2, SVB_IMG_RAW16: 2, SVB_IMG_Y8: 1,
                SVB_IMG_Y16: 2, SVB_IMG_RGB24: 3, SVB_IMG_RGB32: 4}


def message_appli_trop_ancienne():
    """→ texte d'explication quand l'application installée n'expose pas la
    sonde (cas réel : banc récent copié sur une installation antérieure)."""
    import avastack
    try:
        version = avastack.AVASTACK_VERSION
    except AttributeError:
        version = "?"

    def dte(p):
        try:
            return time.strftime("%d/%m/%Y %H:%M",
                                 time.localtime(os.path.getmtime(p)))
        except (OSError, TypeError):
            return "?"

    lignes = ["⚠ L'APPLICATION (avastack) EST TROP ANCIENNE POUR CE BANC",
              f"  version avastack  : {version}  (ce banc exige ≥ 2.16.0)",
              f"  banc              : {__file__}  ({dte(__file__)})",
              f"  svbony.py         : "
              f"{getattr(msvb, '__file__', 'ABSENT')}  "
              f"({dte(getattr(msvb, '__file__', ''))})"]
    if _ERREUR_CHARGEMENT:
        lignes.append(f"  erreur d'import    : {_ERREUR_CHARGEMENT}")
    if _MANQUE:
        lignes.append(f"  symboles manquants : {', '.join(_MANQUE)}")
    lignes += [
        "",
        "Depuis la v2.16.0, le banc RÉUTILISE la sonde de l'application",
        "(SVBonyCamera.detecter_capacites) au lieu d'en garder une copie.",
        "",
        "À FAIRE (dossier d'installation, ex. %LOCALAPPDATA%\\AVAStack) :",
        "  copier avastack\\cameras\\svbony.py  ET  avastack\\cameras\\"
        "capacites.py",
        "  depuis le dépôt (ou réinstaller la version ≥ 2.16.0), puis relancer",
        "  ce banc. La détection de la caméra reste utilisable en attendant,",
        "  mais l'ouverture (listage des contrôles) sera refusée.",
    ]
    return "\n".join(lignes)

class BancSVB:
    """Banc de test SVBONY : détection, contrôles, flux, rapport."""

    def __init__(self, root, mode_console=False):
        self.root = root
        self.mode_console = mode_console
        self.dll = None              # handle DLL (chargé par msvb._charger_sdk)
        self.chemin_dll = None
        self.cam_id = None           # handle SDK (SVB_CAMERA_INFO.CameraID)
        self.props = None            # _SVBCameraProperty
        self.info = None             # _SVBCameraInfo
        self.nom = ""
        self.caps = None             # Capacites (via detecter_capacites)
        self.ouverte = False
        self.capture = False         # SVBStartVideoCapture fait ?
        self.flux_actif = False
        self._th_flux = None
        self._ui_q = queue.Queue()   # messages pour Tk (jamais SDK dans Tk)
        self._jobs = queue.Queue()   # travaux séquentiels (appel SDK)
        self._verdict = []
        self._n_frames = 0
        self._derniere_photo = None
        self._frame_attente = None   # dernière frame reçue (l'UI écrase)
        self._fmt_pose = None        # format DERNIÈREMENT POSÉ (la relecture
                                     # SVBGetOutputImageType peut mentir)

        self._preparer_dll()
        self._construire_ui()
        if not BANC_PRET:
            # l'application installée n'expose pas la sonde : on le DIT
            self.lbl_fichiers.configure(fg="#aa0000")
            self.btn_ouvrir.configure(state="disabled")
            for ligne in message_appli_trop_ancienne().splitlines():
                self._log(ligne)
        threading.Thread(target=self._boucle_travaux, daemon=True).start()
        self.root.after(80, self._poll_ui)

    # --- SDK ------------------------------------------------------------------

    def _preparer_dll(self):
        """Charge la DLL via le MÊME chargeur que l'appli + lie les
        prototypes ctypes supplémentaires utilisés par le banc."""
        if msvb is None:
            return
        self.dll = msvb._charger_sdk()
        if self.dll is None:
            return
        try:
            self.chemin_dll = self.dll._name
        except AttributeError:
            self.chemin_dll = "?"
        d = self.dll
        c_int, c_long = ctypes.c_int, ctypes.c_long
        d.SVBGetNumOfConnectedCameras.restype = c_int
        d.SVBOpenCamera.restype = c_int
        d.SVBOpenCamera.argtypes = [c_int]
        d.SVBCloseCamera.restype = c_int
        d.SVBCloseCamera.argtypes = [c_int]
        d.SVBStartVideoCapture.restype = c_int
        d.SVBStartVideoCapture.argtypes = [c_int]
        d.SVBStopVideoCapture.restype = c_int
        d.SVBStopVideoCapture.argtypes = [c_int]
        d.SVBGetOutputImageType.restype = c_int
        d.SVBGetOutputImageType.argtypes = [c_int, ctypes.POINTER(c_int)]
        d.SVBGetROIFormat.restype = c_int
        d.SVBGetROIFormat.argtypes = [c_int] + [ctypes.POINTER(c_int)] * 5
        d.SVBGetSDKVersion.restype = ctypes.c_char_p
        d.SVBRestoreDefaultParam.restype = c_int
        d.SVBRestoreDefaultParam.argtypes = [c_int]
        d.SVBSetAutoSaveParam.restype = c_int
        d.SVBSetAutoSaveParam.argtypes = [c_int, c_int]

    def _err(self, code):
        """→ nom lisible de l'erreur SDK."""
        return NOMS_ERREURS.get(code, f"code {code}")

    # --- log / travaux (jamais d'appel SDK dans le thread Tk) -----------------

    def _log(self, msg):
        """Journal (thread-safe) : file d'attente + horodatage."""
        self._ui_q.put(("log", time.strftime("%H:%M:%S ") + msg))

    def _travail(self, fn):
        """Empile un travail à exécuter par le thread de travail."""
        self._jobs.put(fn)

    def _boucle_travaux(self):
        """Thread de travail : exécute les fonctions SDK séquentiellement."""
        while True:
            fn = self._jobs.get()
            try:
                fn()
            except Exception as e:
                self._log(f"ERREUR : {e!r}")

    def _poll_ui(self):
        """Côté Tk : vide la file de messages + rafraîchit l'état."""
        try:
            while True:
                genre, contenu = self._ui_q.get_nowait()
                if genre == "log":
                    self.txt_log.configure(state="normal")
                    self.txt_log.insert("end", contenu + "\n")
                    self.txt_log.see("end")
                    self.txt_log.configure(state="disabled")
                elif genre == "frame":
                    # on ÉCRASE : seule la dernière frame compte (sinon la
                    # file grossit pendant que Tk dessine — leçon banc POA)
                    self._frame_attente = contenu
                elif genre == "fps":
                    self.lbl_fps.configure(text=contenu)
                elif genre == "temp":
                    self.lbl_temp.configure(text=contenu)
                elif genre in ("cams", "ouvert", "ferme", "verdict",
                               "fluxfini"):
                    self._maj_apres_evenement(genre, contenu)
        except queue.Empty:
            pass
        if self._frame_attente is not None:
            img, self._frame_attente = self._frame_attente, None
            self._afficher_frame(img)
        # sondage température/puissance TEC (léger, via le thread de travail)
        if self.ouverte and not self.flux_actif:
            self._travail(self._travail_temp)
        # cadence rapide PENDANT le flux, lente au repos (leçon banc POA)
        self.root.after(200 if self.flux_actif else 2000, self._poll_ui)

    def _travail_temp(self):
        """Lecture température + puissance TEC (thread de travail).
        Les températures SVBONY sont en UNITÉS DE 0,1 °C (en-tête officiel
        et wrapper de référence pysvb) → conversion pour l'affichage."""
        if not self.ouverte:
            return
        t = self._lire_ctrl(msvb.SVB_CURRENT_TEMPERATURE)
        p = self._lire_ctrl(msvb.SVB_COOLER_POWER)
        cible = self._lire_ctrl(msvb.SVB_TARGET_TEMPERATURE)
        txt = "Capteur : "
        txt += (f"{t[0] / 10:.1f} °C (SDK {t[0]})" if t else "?")
        txt += f" · TEC : {p[0]} %" if p else " · TEC : ?"
        if cible is not None:
            txt += f" · consigne {cible[0] / 10:.1f} °C"
        self._ui_q.put(("temp", txt))

    def _lire_ctrl(self, cid):
        """→ (valeur, is_auto) d'un contrôle, ou None si erreur.
        SVBGetControlValue(id, type, *long, *int)."""
        v = ctypes.c_long(0)
        auto = ctypes.c_int(0)
        err = self.dll.SVBGetControlValue(self.cam_id, cid,
                                          ctypes.byref(v), ctypes.byref(auto))
        if err != msvb.SVB_SUCCESS:
            return None
        return v.value, bool(auto.value)

    # --- construction de la fenêtre -------------------------------------------

    def _construire_ui(self):
        self.root.title("Banc de test SVBONY — AVAStack")
        haut = ttk.Frame(self.root)
        haut.pack(fill="x", padx=8, pady=(8, 2))
        self.lbl_fichiers = tk.Label(haut, anchor="w", justify="left")
        self.lbl_fichiers.pack(fill="x")
        self._maj_lbl_fichiers()

        ligne1 = ttk.Frame(self.root)
        ligne1.pack(fill="x", padx=8, pady=2)
        ttk.Button(ligne1, text="🔎 Détecter",
                   command=self._action_detecter).pack(side="left")
        self.cmb_cams = ttk.Combobox(ligne1, width=32, state="readonly")
        self.cmb_cams.pack(side="left", padx=4)
        self.cmb_cams.bind("<<ComboboxSelected>>",
                           lambda e: self._maj_fiche())
        self.btn_ouvrir = ttk.Button(ligne1, text="🔌 Ouvrir",
                                     command=self._action_ouvrir,
                                     state="disabled")
        self.btn_ouvrir.pack(side="left")
        self.btn_fermer = ttk.Button(ligne1, text="Fermer",
                                     command=self._action_fermer,
                                     state="disabled")
        self.btn_fermer.pack(side="left", padx=4)
        self.lbl_etat = ttk.Label(ligne1, text="caméra non ouverte")
        self.lbl_etat.pack(side="left", padx=8)

        ligne2 = ttk.Frame(self.root)
        ligne2.pack(fill="x", padx=8, pady=2)
        ttk.Button(ligne2, text="⚙ Lister les contrôles (tableau)",
                   command=self._action_lister_controles).pack(side="left")
        ttk.Button(ligne2, text="✅ Verdict « possibilités » → log",
                   command=self._action_verdict).pack(side="left", padx=4)
        ttk.Button(ligne2, text="💾 Sauver le rapport",
                   command=self._action_rapport).pack(side="left", padx=4)

        self.lbl_verdict = tk.Label(self.root, anchor="w", justify="left",
                                    fg="#000080")
        self.lbl_verdict.pack(fill="x", padx=8, pady=2)

        # --- panneau de contrôles -------------------------------------------------
        ctrl = ttk.LabelFrame(self.root, text="Contrôles en direct")
        ctrl.pack(fill="x", padx=8, pady=2)
        ttk.Label(ctrl, text="Expo (µs) :").grid(row=0, column=0)
        self.ent_expo = ttk.Entry(ctrl, width=9)
        self.ent_expo.insert(0, "10000")
        self.ent_expo.grid(row=0, column=1)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_expo).grid(row=0, column=2,
                                                    padx=(2, 8))
        ttk.Label(ctrl, text="Gain :").grid(row=0, column=3)
        self.ent_gain = ttk.Entry(ctrl, width=9)
        self.ent_gain.grid(row=0, column=4)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_gain).grid(row=0, column=5,
                                                    padx=(2, 8))
        ttk.Label(ctrl, text="BlackLevel :").grid(row=0, column=6)
        self.ent_offset = ttk.Entry(ctrl, width=9)
        self.ent_offset.grid(row=0, column=7)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_offset).grid(row=0, column=8,
                                                      padx=(2, 8))
        ttk.Label(ctrl, text="Consigne °C :").grid(row=0, column=9)
        self.ent_temp = ttk.Entry(ctrl, width=7)
        self.ent_temp.insert(0, "-10")
        self.ent_temp.grid(row=0, column=10)
        ttk.Button(ctrl, text="❄ Réguler",
                   command=self._tk_tec_on).grid(row=0, column=11,
                                                 padx=(2, 2))
        ttk.Button(ctrl, text="⏹ Arrêter",
                   command=lambda: self._travail(self._tec_off)).grid(
            row=0, column=12, padx=2)
        self.lbl_temp = ttk.Label(ctrl, text="Capteur : ? · TEC : ?")
        self.lbl_temp.grid(row=0, column=13, padx=8)
        ttk.Label(ctrl, text="Bin :").grid(row=1, column=0, pady=(6, 0))
        self.cmb_bin = ttk.Combobox(ctrl, width=6, state="disabled",
                                    values=["1"])
        self.cmb_bin.current(0)
        self.cmb_bin.grid(row=1, column=1, pady=(6, 0))
        ttk.Label(ctrl, text="Format :").grid(row=1, column=3, pady=(6, 0))
        self.cmb_fmt = ttk.Combobox(ctrl, width=9, state="disabled",
                                    values=["RGB24"])
        self.cmb_fmt.current(0)
        self.cmb_fmt.grid(row=1, column=4, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_format).grid(
            row=1, column=5, padx=(2, 8), pady=(6, 0))
        ttk.Label(ctrl, text="Flip :").grid(row=1, column=6, pady=(6, 0))
        self.cmb_flip = ttk.Combobox(ctrl, width=9, state="disabled",
                                     values=["aucun", "horizontal",
                                             "vertical", "les deux"])
        self.cmb_flip.current(0)
        self.cmb_flip.grid(row=1, column=7, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_flip).grid(
            row=1, column=8, padx=(2, 8), pady=(6, 0))
        ttk.Button(ctrl, text="⚙ défauts d'usine",
                   command=lambda: self._travail(self._defauts_usine)).grid(
            row=1, column=9, padx=(2, 8), pady=(6, 0))

        # --- ROI ------------------------------------------------------------------
        roi = ttk.LabelFrame(self.root, text="ROI (SVBSetROIFormat : "
                                              "départ + taille + bin)")
        roi.pack(fill="x", padx=8, pady=2)
        for i, (lab, w) in enumerate((("Départ X", 7), ("Départ Y", 7),
                                      ("Largeur", 8), ("Hauteur", 8))):
            ttk.Label(roi, text=lab + " :").grid(row=0, column=2 * i)
            e = ttk.Entry(roi, width=w)
            e.grid(row=0, column=2 * i + 1, padx=(2, 8))
            setattr(self, f"ent_roi{i}", e)
        ttk.Button(roi, text="Poser ROI",
                   command=self._tk_pose_roi).grid(row=0, column=8, padx=4)
        ttk.Button(roi, text="Plein champ",
                   command=lambda: self._travail(self._roi_plein)).grid(
            row=0, column=9, padx=4)
        ttk.Button(roi, text="▶ Flux live",
                   command=self._action_flux).grid(row=0, column=10, padx=8)
        ttk.Button(roi, text="■ Stop",
                   command=self._action_stop_flux).grid(row=0, column=11)
        self.lbl_fps = ttk.Label(roi, text="")
        self.lbl_fps.grid(row=0, column=12, padx=10)

        # --- aperçu + journal ------------------------------------------------------
        self.lbl_image = tk.Label(self.root, bg="#222222")
        self.lbl_image.pack(fill="x", padx=8, pady=4)
        self.txt_log = tk.Text(self.root, height=14, state="disabled",
                               font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _maj_lbl_fichiers(self):
        """Affiche les fichiers réellement chargés (leçon du banc QHY)."""
        def dte(p):
            try:
                return time.strftime("%d/%m/%Y %H:%M",
                                     time.localtime(os.path.getmtime(p)))
            except OSError:
                return "?"
        mp = getattr(msvb, "__file__", None) or "ABSENT (import impossible)"
        dll = self.chemin_dll or "INTRUVABLE (SDK absent !)"
        self.lbl_fichiers.configure(text=(
            f"DLL SDK  : {dll}  ({dte(dll)})\n"
            f"svbony.py : {mp}  ({dte(mp)})\n"
            f"Sonde : SVBonyCamera.detecter_capacites (réutilisée de "
            f"l'application — le banc n'a PAS sa propre copie)"))
        if self.dll is None:
            self.lbl_fichiers.configure(fg="#aa0000")

    # --- actions (côté Tk : ne font QUE de l'UI + _travail) --------------------

    def _action_detecter(self):
        self._travail(self._detecter)

    def _detecter(self):
        """Énumère les caméras + lit la fiche de chacune (thread de travail)."""
        if self.dll is None:
            self._log("✗ SDK SVBONY introuvable : place SVBCameraSDK.dll "
                      "dans le dossier du projet (ou AVASTACK_SVBONY_DIR).")
            return
        try:
            ver = self.dll.SVBGetSDKVersion()
            self._log(f"SVBGetSDKVersion() → "
                      f"{ver.decode('utf-8', 'replace') if ver else '?'}")
        except AttributeError:
            pass
        n = self.dll.SVBGetNumOfConnectedCameras()
        self._log(f"SVBGetNumOfConnectedCameras() → {n}")
        if n == 0:
            self._log("Aucune caméra SVBONY détectée (vérifier le câble USB "
                      "et le pilote).")
            return
        self._fiches = []
        noms = []
        for i in range(n):
            info = msvb._SVBCameraInfo()
            if self.dll.SVBGetCameraInfo(ctypes.byref(info), i) != \
                    msvb.SVB_SUCCESS:
                self._log(f"✗ fiche caméra #{i} illisible")
                continue
            prop = msvb._SVBCameraProperty()
            ok_prop = self.dll.SVBGetCameraProperty(
                info.CameraID, ctypes.byref(prop)) == msvb.SVB_SUCCESS
            if not ok_prop:
                # constat réel (SV305C, 19/09/2026) : SVBGetCameraProperty
                # échoue AVANT l'ouverture — essai bref open → lire → close
                if self.dll.SVBOpenCamera(info.CameraID) == msvb.SVB_SUCCESS:
                    ok_prop = self.dll.SVBGetCameraProperty(
                        info.CameraID, ctypes.byref(prop)) == msvb.SVB_SUCCESS
                    self.dll.SVBCloseCamera(info.CameraID)
                    if ok_prop:
                        self._log(f"#{i} : fiche lue avec une ouverture "
                                  f"brève (le SDK l'exige avant ?)")
            nom = info.FriendlyName.decode("utf-8", "replace").strip() \
                or f"SVB #{i}"
            self._fiches.append((info, prop if ok_prop else None))
            noms.append(nom)
            if ok_prop:
                self._log(f"#{i} : {nom} · {prop.MaxWidth}×{prop.MaxHeight}"
                          f" px · {prop.MaxBitDepth} bits")
            else:
                self._log(f"#{i} : {nom} (fiche illisible pour l'instant)")
        self._ui_q.put(("cams", (noms, self._fiches)))

    def _maj_fiche(self):
        """Affiche la fiche détaillée de la caméra sélectionnée (Tk)."""
        sel = self.cmb_cams.current()
        if sel < 0 or not getattr(self, "_fiches", None):
            return
        info, prop = self._fiches[sel]
        self.props = prop
        self.info = info
        self._log("=== FICHE ===")
        self._log(f"  modèle       : {info.FriendlyName.decode('utf-8','replace')}")
        self._log(f"  n° série     : {info.CameraSN.decode('utf-8','replace')}"
                  f" · port {info.PortType.decode('utf-8','replace')}")
        if prop is None:
            self._log("  (propriétés non lues — réessayer après ouverture)")
            return
        bins = [b for b in prop.SupportedBins if 1 <= b <= 4]
        fmts = [msvb.NOMS_FORMATS_SVB.get(f, str(f))
                for f in prop.SupportedVideoFormat if f >= 0]
        coul = "COULEUR" if prop.IsColorCam else "mono"
        self._log(f"  capteur      : {coul}, {prop.MaxBitDepth} bits, "
                  f"Bayer {BAYER.get(prop.BayerPattern, prop.BayerPattern)}")
        self._log(f"  plein champ  : {prop.MaxWidth}×{prop.MaxHeight} px")
        self._log(f"  matériel     : TEC (voir contrôles) · déclencheur "
                  f"{'oui' if prop.IsTriggerCam else 'non'}")
        self._log(f"  bins supportés : {bins} · formats : {fmts}")

    def _action_ouvrir(self):
        sel = self.cmb_cams.current()
        if sel < 0:
            return
        self._travail(lambda: self._ouvrir(sel))

    def _ouvrir(self, index):
        """Ouvre la caméra (thread de travail) : open → format → ROI plein
        champ → **SVBStartVideoCapture** (leçon du 19/09 : le flux ne
        réponde JAMAIS tant que la capture n'est pas démarrée) → sonde."""
        if not BANC_PRET:
            for ligne in message_appli_trop_ancienne().splitlines():
                self._log(ligne)
            return
        if self.ouverte:
            self._fermer()
        info, prop = self._fiches[index]
        self._log(f"=== OUVERTURE #{index} : "
                  f"{info.FriendlyName.decode('utf-8','replace')} ===")
        self.cam_id = info.CameraID
        self.info = info
        self.nom = info.FriendlyName.decode("utf-8", "replace").strip()
        self.props = prop
        if self.dll.SVBOpenCamera(self.cam_id) != msvb.SVB_SUCCESS:
            self._log("✗ SVBOpenCamera a échoué")
            self.cam_id = None
            return
        self._log("  SVBOpenCamera OK")
        if prop is None:                     # fiche illisible à la détection
            prop = msvb._SVBCameraProperty()
            if self.dll.SVBGetCameraProperty(self.cam_id,
                                             ctypes.byref(prop)) != \
                    msvb.SVB_SUCCESS:
                self._log("✗ SVBGetCameraProperty a échoué")
                self.dll.SVBCloseCamera(self.cam_id)
                self.cam_id = None
                return
            self.props = prop
        # format par défaut : couleur → RGB24 (débayerisation par la caméra,
        # comme dans l'appli), mono → RAW16. ⚠ POSER PUIS RELIRE et LOGGER
        # (constat réel du 19/09/2026 : le flux a démarré en RAW8 alors
        # qu'on avait posé RGB24 — le résultat du set n'était pas vérifié).
        fmt = msvb.SVB_IMG_RGB24 if prop.IsColorCam else msvb.SVB_IMG_RAW16
        err_f = self.dll.SVBSetOutputImageType(self.cam_id, fmt)
        f = ctypes.c_int(0)
        self.dll.SVBGetOutputImageType(self.cam_id, ctypes.byref(f))
        if err_f != msvb.SVB_SUCCESS or f.value != fmt:
            self._log(f"⚠ SVBSetOutputImageType("
                      f"{msvb.NOMS_FORMATS_SVB.get(fmt)}) → {self._err(err_f)}"
                      f" mais relu {msvb.NOMS_FORMATS_SVB.get(f.value)} — "
                      f"réessai une fois")
            self.dll.SVBSetOutputImageType(self.cam_id, fmt)
            self.dll.SVBGetOutputImageType(self.cam_id, ctypes.byref(f))
        self._log(f"  format relu : "
                  f"{msvb.NOMS_FORMATS_SVB.get(f.value, f.value)}")
        # le format de référence pour le DÉCODAGE est celui qu'on a POSÉ
        # (la relecture peut mentir — constat réel du 19/09/2026)
        self._fmt_pose = fmt
        self.dll.SVBSetROIFormat(self.cam_id, 0, 0, prop.MaxWidth,
                                 prop.MaxHeight, 1)
        w, h = self._lire_roi()[2:4]
        self._log(f"  taille relu : {w}×{h}")
        # régages hérités d'un usage précédent ? (constat réel : expo 2 s
        # et gain 225 à l'ouverture — les paramètres SVBONY persistent)
        expo = self._lire_ctrl(msvb.SVB_EXPOSURE)
        gain = self._lire_ctrl(msvb.SVB_GAIN)
        if expo:
            self._log(f"  expo courante : {expo[0] / 1000:.1f} ms"
                      + (" ⚠ longue — la 1re frame peut mettre autant de "
                         "temps (bouton « défauts d'usine » pour nettoyer)"
                         if expo[0] > 500000 else ""))
        if gain:
            self._log(f"  gain courant : {gain[0]}")
        # DÉMARRER la capture À L'OUVERTURE (leçon du 19/09/2026 sur le banc
        # Player One : POAImageReady/SVBGetVideoData ne répondent JAMAIS
        # tant que la capture n'est pas démarrée)
        err = self.dll.SVBStartVideoCapture(self.cam_id)
        self.capture = (err == msvb.SVB_SUCCESS)
        self._log(f"  SVBStartVideoCapture → {self._err(err)}")
        # DÉSACTIVER l'auto-sauvegarde (constat réel du 20/09/2026 : après
        # des cycles stop/start, l'expo posée à 30 ms est REVENUE à 2000 ms
        # — le SDK recharge ses paramètres sauvegardés au redémarrage)
        try:
            err_a = self.dll.SVBSetAutoSaveParam(self.cam_id, 0)
            self._log(f"  SVBSetAutoSaveParam(0) → {self._err(err_a)} "
                      f"(sinon l'expo/gain hérités reviennent après chaque "
                      f"stop/start)")
        except AttributeError:
            pass
        self.ouverte = True
        self._ui_q.put(("ouvert", None))
        # sonde de l'APPLICATION (une seule définition) + listage + verdict
        msvb._DLL = self.dll           # la sonde utilise ce handle
        probe = msvb.SVBonyCamera.__new__(msvb.SVBonyCamera)
        probe.id = self.cam_id
        probe.name = self.nom
        probe._props = prop
        self.caps = probe.detecter_capacites()
        if self.caps is None:
            self._log("⚠ sonde sans résultat (voir symboles manquants)")
        else:
            self._log(f"  sonde : {len(self.caps.controles)} contrôles, "
                      f"e-/ADU annoncé "
                      f"{self.caps.extras.get('elec_per_adu', '?')}")
        self._lister_controles()
        self._travail_temp()

    def _lire_roi(self):
        """→ (startX, startY, width, height, bin) courants."""
        vals = [ctypes.c_int(0) for _ in range(5)]
        err = self.dll.SVBGetROIFormat(self.cam_id, *[ctypes.byref(v)
                                                     for v in vals])
        if err != msvb.SVB_SUCCESS:
            return (0, 0, 0, 0, 1)
        return tuple(v.value for v in vals)

    def _action_fermer(self):
        self._travail(self._fermer)

    def _fermer(self):
        """Arrête le flux, coupe le TEC et ferme la caméra (thread de
        travail)."""
        self.flux_actif = False
        if not self.ouverte:
            return
        self._log("=== FERMETURE ===")
        self.dll.SVBStopVideoCapture(self.cam_id)
        self.capture = False
        self._fmt_pose = None
        # couper le TEC avant de fermer (même principe que les autres bancs)
        if self.caps is not None and self.caps.tec:
            self.dll.SVBSetControlValue(self.cam_id, msvb.SVB_COOLER_ENABLE,
                                        0, 0)
        err = self.dll.SVBCloseCamera(self.cam_id)
        self._log(f"  SVBCloseCamera → {self._err(err)}")
        self.ouverte = False
        self.cam_id = None
        self._ui_q.put(("ferme", None))

    def _action_lister_controles(self):
        self._travail(self._lister_controles)

    def _lister_controles(self):
        """Tableau des contrôles depuis la sonde de l'APPLICATION + valeurs
        courantes lues via SVBGetControlValue (thread de travail)."""
        if not self.ouverte or self.caps is None:
            self._log("Ouvre d'abord la caméra.")
            return
        self._log(f"=== {len(self.caps.controles)} CONTRÔLES SUPPORTÉS ===")
        for c in sorted(self.caps.controles, key=lambda x: x.cid):
            cur = self._lire_ctrl(c.cid)
            curseur = f"courant {cur[0]}" if cur else "courant ?"
            flags = "".join((("W" if c.ecrivable else "-"),
                             ("R" if c.lisible else "-"),
                             ("A" if c.auto else "-")))
            hors = ""
            if isinstance(c.defaut, (int, float)) and \
                    not (c.min <= c.defaut <= c.max):
                hors = " ⚠ DÉFAUT HORS BORNES (attribut peu fiable)"
            self._log(f"  {c.cid:>2} {c.nom:<28} min {c.min} max {c.max} "
                      f"défaut {c.defaut} · {curseur}{hors}")
        self._log("(W = écrivable, R = lisible, A = mode auto supporté)")
        self._verdict = self.caps.vers_texte().splitlines()
        self._ui_q.put(("verdict", "\n".join(self._verdict)))

    def _action_verdict(self):
        txt = "\n".join(self._verdict) or "Ouvre la caméra d'abord."
        self.lbl_verdict.configure(text=txt)
        for ligne in self._verdict:
            self._log("VERDICT : " + ligne)

    def _action_rapport(self):
        """Écrit le rapport complet dans %TEMP% et affiche le chemin."""
        def dte(p):
            try:
                return time.strftime("%Y-%m-%d %H:%M",
                                     time.localtime(os.path.getmtime(p)))
            except OSError:
                return "?"
        nom = time.strftime("avastack_svb_diag_%Y%m%d_%H%M%S.txt")
        chemin = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")),
                              nom)
        lignes = ["Rapport banc SVBONY — " + time.strftime(
            "%d/%m/%Y %H:%M:%S"),
            f"DLL          : {self.chemin_dll} ({dte(self.chemin_dll)})",
            f"svbony.py    : {getattr(msvb, '__file__', '?')} "
            f"({dte(getattr(msvb, '__file__', '?'))})",
            "",
            "=== VERDICT « POSSIBILITÉS » ==="]
        lignes += self._verdict or ["(ouvrir la caméra d'abord)"]
        lignes += ["", "=== JOURNAL COMPLET ==="]
        try:
            lignes += self.txt_log.get("1.0", "end").splitlines()
        except Exception:
            pass
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write("\n".join(lignes) + "\n")
            self._log(f"💾 rapport écrit : {chemin}")
        except OSError as e:
            self._log(f"✗ rapport non écrit : {e}")

    def _maj_apres_evenement(self, genre, contenu):
        if genre == "cams":
            noms, fiches = contenu
            self._fiches = fiches
            self.cmb_cams.configure(values=noms)
            if noms:
                self.cmb_cams.current(0)
                self._maj_fiche()
                self.btn_ouvrir.configure(state="normal")
        elif genre == "ouvert":
            self.btn_ouvrir.configure(state="disabled")
            self.btn_fermer.configure(state="normal")
            self.lbl_etat.configure(text=f"ouverte : {self.nom}",
                                    foreground="#006600")
        elif genre == "ferme":
            self.btn_ouvrir.configure(state="normal")
            self.btn_fermer.configure(state="disabled")
            self.lbl_etat.configure(text="caméra non ouverte",
                                    foreground="#000000")
            self.lbl_verdict.configure(text="")
        elif genre == "verdict":
            self.lbl_verdict.configure(text=contenu)
            # comboboxes depuis la sonde + préremplissage des défauts
            if self.caps is not None:
                self.cmb_bin.configure(
                    values=[str(b) for b in self.caps.bins] or ["1"],
                    state="readonly")
                self.cmb_bin.current(0)
                self.cmb_fmt.configure(
                    values=self.caps.formats or ["RGB24"], state="readonly")
                if self.caps.formats and self.caps.formats[0] in \
                        self.caps.formats:
                    self.cmb_fmt.current(0)
                ctrl = {c.cid: c for c in self.caps.controles}
                if msvb.SVB_EXPOSURE in ctrl:
                    self.ent_expo.delete(0, "end")
                    self.ent_expo.insert(0, str(ctrl[msvb.SVB_EXPOSURE].defaut))
                if msvb.SVB_GAIN in ctrl:
                    self.ent_gain.delete(0, "end")
                    self.ent_gain.insert(0, str(ctrl[msvb.SVB_GAIN].defaut))
                if msvb.SVB_BLACK_LEVEL in ctrl:
                    self.ent_offset.delete(0, "end")
                    self.ent_offset.insert(
                        0, str(ctrl[msvb.SVB_BLACK_LEVEL].defaut))
                if not self.caps.tec:
                    self.ent_temp.configure(state="disabled")
                    self.lbl_temp.configure(text="pas de TEC sur cette caméra")
                self.cmb_flip.configure(state="readonly")
        elif genre == "fluxfini":
            pass

    # --- poses : lecture des widgets DANS le thread Tk, SDK dans le
    #     thread de travail (règle : jamais .get() Tk hors thread principal) --

    def _ent_valeur(self, entry, defaut=0):
        try:
            return int(float(entry.get()))
        except (ValueError, tk.TclError):
            return defaut

    def _tk_pose_expo(self):
        val = self._ent_valeur(self.ent_expo, 10000)
        self._travail(lambda: self._pose_ctrl(msvb.SVB_EXPOSURE, val,
                                              "Exposition (µs)"))

    def _tk_pose_gain(self):
        val = self._ent_valeur(self.ent_gain, 30)
        self._travail(lambda: self._pose_ctrl(msvb.SVB_GAIN, val, "Gain"))

    def _tk_pose_offset(self):
        val = self._ent_valeur(self.ent_offset, 8)
        self._travail(lambda: self._pose_ctrl(msvb.SVB_BLACK_LEVEL, val,
                                              "BlackLevel (offset)"))

    def _tk_tec_on(self):
        cible = self._ent_valeur(self.ent_temp, -10)
        self._travail(lambda: self._tec_on(cible))

    def _tk_pose_flip(self):
        choix = self.cmb_flip.get()
        self._travail(lambda: self._pose_flip(choix))

    def _tk_pose_format(self):
        inv = {v: k for k, v in msvb.NOMS_FORMATS_SVB.items()}
        fmt = inv.get(self.cmb_fmt.get())
        if fmt is not None:
            self._travail(lambda: self._pose_format(fmt))

    def _tk_pose_roi(self):
        sx = self._ent_valeur(self.ent_roi0, 0)
        sy = self._ent_valeur(self.ent_roi1, 0)
        w = self._ent_valeur(self.ent_roi2, self.props.MaxWidth
                             if self.props else 0)
        h = self._ent_valeur(self.ent_roi3, self.props.MaxHeight
                             if self.props else 0)
        try:
            bin_val = int(self.cmb_bin.get())
        except ValueError:
            bin_val = 1
        self._travail(lambda: self._pose_roi(sx, sy, w, h, bin_val))

    def _pose_ctrl(self, cid, val, nom):
        """Pose un contrôle et RELIT (SVBSetControlValue(id, type, val,
        auto)). → True/False."""
        if not self.ouverte:
            return False
        err = self.dll.SVBSetControlValue(self.cam_id, cid, int(val), 0)
        if err != msvb.SVB_SUCCESS:
            self._log(f"✗ {nom} = {val} → REFUSÉ ({self._err(err)})")
            return False
        relue = self._lire_ctrl(cid)
        relu = f"(relu : {relue[0]})" if relue else "(pose OK, relecture KO)"
        self._log(f"✓ {nom} = {val} {relu}")
        return True

    def _tec_on(self, cible):
        """Régulation TEC (thread de travail). ⚠ Les températures SVBONY
        sont en unités de 0,1 °C → multiplier par 10 pour poser."""
        if not self.ouverte:
            return
        if self.caps is None or not self.caps.tec:
            self._log("Cette caméra n'a pas de TEC (contrôles absents).")
            return
        self._pose_ctrl(msvb.SVB_COOLER_ENABLE, 1, "CoolerEnable")
        self._pose_ctrl(msvb.SVB_TARGET_TEMPERATURE, cible * 10,
                        f"TargetTemp ({cible} °C = SDK {cible * 10})")
        self._travail_temp()

    def _tec_off(self):
        if not self.ouverte:
            return
        if self.caps is None or not self.caps.tec:
            return
        self._pose_ctrl(msvb.SVB_COOLER_ENABLE, 0, "CoolerEnable")
        self._travail_temp()

    def _pose_flip(self, choix):
        """Flip : UN seul contrôle (SVB_FLIP 0-3), contrairement à POA."""
        if not self.ouverte:
            return
        ctrl = {c.cid: c for c in self.caps.controles} \
            if self.caps else {}
        if msvb.SVB_FLIP not in ctrl:
            self._log("Pas de contrôle FLIP sur cette caméra.")
            return
        val = {"aucun": SVB_FLIP_NONE, "horizontal": SVB_FLIP_HORIZ,
               "vertical": SVB_FLIP_VERT, "les deux": SVB_FLIP_BOTH}.get(
            choix, SVB_FLIP_NONE)
        self._pose_ctrl(msvb.SVB_FLIP, val, f"Flip ({choix})")

    def _stop_capture_si_besoin(self):
        """Arrête la capture (préalable à tout changement ROI/format) —
        SVB_ERROR_INVALID_SEQUENCE = « stop capture first »."""
        if self.capture:
            err = self.dll.SVBStopVideoCapture(self.cam_id)
            if err != msvb.SVB_SUCCESS:
                self._log(f"⚠ SVBStopVideoCapture → {self._err(err)}")
            self.capture = False

    def _pose_format(self, fmt):
        """Change le type d'image : stop → SVBSetOutputImageType →
        RÉ-APPLIQUER la ROI (certains SDK recalculent la taille de frame au
        moment du SetROIFormat — sinon l'ancienne taille interne persiste)
        → start."""
        if not self.ouverte:
            return
        self._stop_capture_si_besoin()
        err = self.dll.SVBSetOutputImageType(self.cam_id, fmt)
        if err != msvb.SVB_SUCCESS:
            self._log(f"✗ SVBSetOutputImageType("
                      f"{msvb.NOMS_FORMATS_SVB.get(fmt, fmt)}) refusé "
                      f"({self._err(err)})")
            self.dll.SVBStartVideoCapture(self.cam_id)
            self.capture = True
            return
        self._fmt_pose = fmt          # référence pour le décodage du flux
        f = ctypes.c_int(0)
        self.dll.SVBGetOutputImageType(self.cam_id, ctypes.byref(f))
        self._log(f"✓ format {msvb.NOMS_FORMATS_SVB.get(fmt)} posé "
                  f"(relu : {msvb.NOMS_FORMATS_SVB.get(f.value)})")
        if self.props is not None:
            # ré-appliquer la ROI pour que le SDK recalcule sa taille de
            # frame avec le NOUVEAU format
            self.dll.SVBSetROIFormat(self.cam_id, 0, 0, self.props.MaxWidth,
                                     self.props.MaxHeight, 1)
            sx, sy, w, h, b = self._lire_roi()
            self._log(f"  ROI réappliquée : ({sx},{sy}) {w}×{h} bin {b}")
        err = self.dll.SVBStartVideoCapture(self.cam_id)
        self.capture = (err == msvb.SVB_SUCCESS)
        self._log(f"  SVBStartVideoCapture → {self._err(err)} — ⚠ le SDK "
                  f"peut RECHARGER ses paramètres sauvegardés "
                  f"(expo/gain) : reposer si besoin")

    def _defauts_usine(self):
        """Restaure les paramètres d'usine (SVBRestoreDefaultParam) — utile
        quand des réglages d'un usage précédent persistent (constat réel :
        expo 2000 ms et gain 225 à l'ouverture de la SV305C)."""
        if not self.ouverte:
            return
        err = self.dll.SVBRestoreDefaultParam(self.cam_id)
        self._log(f"⚙ SVBRestoreDefaultParam → {self._err(err)}")
        if err == msvb.SVB_SUCCESS:
            self._lister_controles()
            self._travail_temp()

    def _pose_roi(self, sx, sy, w, h, bin_val):
        """Pose la ROI + le bin : stop → SVBSetROIFormat → relecture →
        start (⚠ la taille attendue est la taille FINALE après bin, comme
        chez ZWO : diviser par le bin)."""
        if not self.ouverte:
            return
        self._stop_capture_si_besoin()
        w_bin = max(8, w // bin_val)
        h_bin = max(2, h // bin_val)
        err = self.dll.SVBSetROIFormat(self.cam_id, sx, sy, w_bin, h_bin,
                                       bin_val)
        sx_r, sy_r, w_r, h_r, b_r = self._lire_roi()
        if err == msvb.SVB_SUCCESS:
            self._log(f"✓ ROI posée ({sx},{sy} {w}×{h} bin {bin_val}) → "
                      f"relu : ({sx_r},{sy_r}) {w_r}×{h_r} bin {b_r}")
        else:
            self._log(f"✗ ROI refusée ({self._err(err)}) (relu : "
                      f"({sx_r},{sy_r}) {w_r}×{h_r} bin {b_r})")
        err = self.dll.SVBStartVideoCapture(self.cam_id)
        self.capture = (err == msvb.SVB_SUCCESS)
        self._log(f"  SVBStartVideoCapture → {self._err(err)} — ⚠ le SDK "
                  f"peut recharger ses paramètres sauvegardés "
                  f"(expo/gain) : reposer si besoin")

    def _roi_plein(self):
        if not self.ouverte or self.props is None:
            return
        self._stop_capture_si_besoin()
        self.dll.SVBSetROIFormat(self.cam_id, 0, 0, self.props.MaxWidth,
                                 self.props.MaxHeight, 1)
        sx, sy, w, h, b = self._lire_roi()
        self._log(f"✓ plein champ relu : ({sx},{sy}) {w}×{h} bin {b}")
        err = self.dll.SVBStartVideoCapture(self.cam_id)
        self.capture = (err == msvb.SVB_SUCCESS)
        self._log(f"  SVBStartVideoCapture → {self._err(err)}")

    # --- flux live -------------------------------------------------------------

    def _action_flux(self):
        if not self.ouverte:
            return
        self.flux_actif = True
        self._n_frames = 0
        t0 = time.time()
        self._th_flux = threading.Thread(
            target=self._boucle_flux, args=(t0,), daemon=True)
        self._th_flux.start()

    def _action_stop_flux(self):
        self.flux_actif = False

    def _boucle_flux(self, t0):
        """Thread de lecture : SVBGetVideoData en boucle (le même que
        SVBonyCamera.read(), avec diagnostic : état journalisé AVANT le
        départ, relance UNIQUE (stop+start) à mi-patience, abandon
        expliqué — leçons du banc Player One du 19/09/2026).

        ⚠ TOUTE EXCEPTION est maintenant JOURNALISÉE avec son traceback :
        le constat réel du 19/09/2026 (SV305C) est que le thread de flux
        disparaissait SANS AUCUN message (ni relance ni abandon dans le
        log) — une exception non interceptée dans un thread secondaire ne
        tue pas le programme, elle tue SILENCIEUSEMENT le thread."""
        expo = self._lire_ctrl(msvb.SVB_EXPOSURE)
        expo_s = (expo[0] / 1e6) if expo and expo[0] > 0 else 0.01
        patience = max(2.0 * expo_s, 6.0)
        try:
            self._boucle_flux_interne(t0, expo_s, patience)
        except Exception:
            import traceback
            self.flux_actif = False
            for ligne in traceback.format_exc().splitlines():
                self._log("💥 FLUX : " + ligne)
            self._ui_q.put(("fluxfini", None))

    def _boucle_flux_interne(self, t0, expo_s, patience):
        sx, sy, w, h, b = self._lire_roi()
        fmt = ctypes.c_int(0)
        self.dll.SVBGetOutputImageType(self.cam_id, ctypes.byref(fmt))
        fmt_nom = self._fmt_pose if self._fmt_pose is not None else fmt.value
        octets = w * h * OCTETS_PIXEL.get(fmt_nom, 2)
        self._log(f"▶ flux : format "
                  f"{msvb.NOMS_FORMATS_SVB.get(fmt_nom)} (posé) — relu : "
                  f"{msvb.NOMS_FORMATS_SVB.get(fmt.value)}, {w}×{h} px "
                  f"(bin {b}), expo {expo_s * 1000:.1f} ms, "
                  f"~{octets / 1e6:.1f} Mo par frame, patience "
                  f"{patience:.0f} s")
        t_derniere = time.time()
        vide = 0
        relance_faite = False
        dernier_etat = 0.0
        # ⚠ SUR-ALLOCATION MAXIMALE (constats réels 19-20/09/2026 : crash
        # d'écriture avec 2,1 Mo (RAW8 nominal) PUIS avec 6,2 Mo (RGB24) —
        # le SDK écrit sa frame SANS vérifier la taille du buffer, et son
        # format interne est PLUS GRAND que tout ce que disent le set et la
        # relecture. Dernier candidat pour 1920×1080 : RGB32 (4 o/pixel).
        # On alloue 4 o/pixel + marge, et le VRAI format est DÉDUIT de la
        # donnée elle-même (dernier octet non nul d'un buffer initialisé à
        # zéro) — voir détection plus bas.
        alloc = w * h * 4 + 65536
        self._log(f"  buffer flux : {alloc / 1e6:.1f} Mo alloués "
                  f"(4 o/pixel + marge — le format réel est déduit de la "
                  f"donnée)")
        while self.flux_actif and self.ouverte:
            _, _, w, h, _ = self._lire_roi()
            f = ctypes.c_int(0)
            self.dll.SVBGetOutputImageType(self.cam_id, ctypes.byref(f))
            buf = np.zeros(alloc, dtype=np.uint8)
            err = self.dll.SVBGetVideoData(
                self.cam_id, buf.ctypes.data_as(
                    ctypes.POINTER(ctypes.c_ubyte)), alloc, 200)
            if err != msvb.SVB_SUCCESS:
                vide += 1
                dt = time.time() - t_derniere
                # état périodique (1×/s) : sinon la boucle en timeouts est
                # muette et on ne sait pas si elle tourne encore
                if dt - dernier_etat >= 1.0:
                    dernier_etat = dt
                    self._log(f"… flux : {vide} timeouts en {dt:.1f} s "
                              f"(la 1re frame peut prendre {expo_s:.1f} s)")
                if err == 11:                     # TIMEOUT (pas de frame)
                    if not relance_faite and dt > patience / 2:
                        relance_faite = True
                        e1 = self.dll.SVBStopVideoCapture(self.cam_id)
                        e2 = self.dll.SVBStartVideoCapture(self.cam_id)
                        self._log(f"⚠ aucune frame après {dt:.1f} s "
                                  f"({vide} timeouts) → relance "
                                  f"stop({self._err(e1)})/"
                                  f"start({self._err(e2)})")
                    if dt > patience:
                        self._log(
                            f"⚠ TOUJOURS aucune frame après {patience:.0f} s "
                            f"(expo {expo_s * 1000:.0f} ms, {vide} timeouts, "
                            f"format {msvb.NOMS_FORMATS_SVB.get(f.value)}, "
                            f"{w}×{h}) — STOP flux. Pistes : exposition déjà "
                            f"pilotée par un autre logiciel, ou capture non "
                            f"démarrée (SVBStartVideoCapture en erreur).")
                        self.flux_actif = False
                        self._ui_q.put(("fluxfini", None))
                    continue
                self._log(f"⚠ SVBGetVideoData → {self._err(err)}")
                time.sleep(0.02)
                continue
            t_derniere = time.time()
            vide = 0
            dernier_etat = 0.0
            # ⚠ DÉCODAGE DÉFENSIF : la relecture SVBGetOutputImageType peut
            # MENTIR (constat réel : RAW8 relu après un set RGB24 réussi,
            # et frame du SDK plus grande que RAW8 = access violation). Le
            # format de référence est donc CELUI QU'ON A POSÉ (self._fmt_pose),
            # la relecture n'est qu'un diagnostic ; le VRAI format est déduit
            # de la donnée (dernier octet non nul d'un buffer initialisé à 0).
            nonz = np.nonzero(buf)[0]
            if nonz.size == 0:
                # frame entièrement à zéro : nuit noire ou expo très courte —
                # décodage avec le format posé (aucune information réelle)
                if not getattr(self, "_warn_noir", False):
                    self._warn_noir = True
                    self._log("⚠ frame ENTIÈREMENT à zéro (noire) — expo "
                              "trop courte ou capteur couvert ? décodage "
                              "avec le format posé")
                oct_pix = OCTETS_PIXEL.get(
                    self._fmt_pose if self._fmt_pose is not None
                    else f.value, 1)
                n = min(w * h * oct_pix, len(buf))
                img = (buf[:n].reshape(h, w, 3) if oct_pix == 3 else
                       buf[:n].view(np.uint16).reshape(h, w)
                       if oct_pix == 2 else buf[:n].reshape(h, w))
            else:
                fin = int(nonz[-1]) + 1
                oct_pix = max(1, min(4, -(-fin // (w * h))))
                n = min(w * h * oct_pix, len(buf))
                if oct_pix == 3:
                    img = buf[:n].reshape(h, w, 3)
                elif oct_pix == 4:
                    img = buf[:n].reshape(h, w, 4)[:, :, :3]
                elif oct_pix == 2:
                    img = buf[:n].view(np.uint16).reshape(h, w)
                else:
                    img = buf[:n].reshape(h, w)
                if oct_pix != getattr(self, "_dernier_oct_pix", None):
                    self._dernier_oct_pix = oct_pix
                    self._log(f"🔎 FORMAT RÉEL DÉTECTÉ : {oct_pix} o/pixel "
                              f"({n / 1e6:.1f} Mo par frame) — relu SDK : "
                              f"{msvb.NOMS_FORMATS_SVB.get(f.value)}. "
                              f"À REPORTER (SVBGetOutputImageType et "
                              f"SVBSetOutputImageType ne disent pas la "
                              f"vérité sur cette caméra)")
            self._n_frames += 1          # (réintégré : perdu dans une édition,
            # le compteur restait à 0 → warning répété et fps à 0,00)
            nom_fmt = self._dernier_oct_pix or (
                self._fmt_pose if self._fmt_pose is not None else f.value)
            if self._n_frames == 1:
                self._log(f"✓ 1re frame reçue après "
                          f"{time.time() - t0:.1f} s")
            self._fps = self._n_frames / max(time.time() - t0, 0.001)
            self._ui_q.put(("fps", f"{self._n_frames} frames · "
                                   f"{self._fps:.2f} fps · {w}×{h} · "
                                   f"{getattr(self, '_dernier_oct_pix', '?')} "
                                   f"o/px (relu : "
                                   f"{msvb.NOMS_FORMATS_SVB.get(f.value)})"))
            self._ui_q.put(("frame", img))
        self._ui_q.put(("fluxfini", None))

    def _afficher_frame(self, img):
        """Convertit et affiche une frame dans le label (Tk).
        DÉCIMATION AVANT CALCUL (frame plein format lourde — leçon banc POA)."""
        pas = max(1, int(max(img.shape[0], img.shape[1]) / 900))
        petit = img[::pas, ::pas]
        if petit.ndim == 3:                       # RGB : déjà en 8 bits
            u8 = petit
        else:
            lo, hi = np.percentile(petit, (0.1, 99.9))
            if hi <= lo:
                hi = lo + 1
            u8 = np.clip((petit.astype(np.float32) - lo) * 255.0 / (hi - lo),
                         0, 255).astype(np.uint8)
        pil = Image.fromarray(u8)
        lw = 460
        lh = int(pil.height * lw / pil.width)
        pil = pil.resize((lw, max(1, lh)))
        self._derniere_photo = ImageTk.PhotoImage(pil)
        self.lbl_image.configure(image=self._derniere_photo,
                                 width=lw, height=max(1, lh))

    # --- mode console (--console) -----------------------------------------------

    def detection_console(self):
        """Détection rapide sans fenêtre : fiche + contrôles + verdict,
        tout imprimé sur stdout, puis fermeture propre."""
        if not BANC_PRET:
            print(message_appli_trop_ancienne())
            return 2
        if self.dll is None:
            print("SDK SVBONY introuvable — place SVBCameraSDK.dll dans le "
                  "dossier du projet.")
            return 1
        print("DLL :", self.chemin_dll)
        n = self.dll.SVBGetNumOfConnectedCameras()
        print("caméras détectées :", n)
        if n == 0:
            return 1
        info = msvb._SVBCameraInfo()
        if self.dll.SVBGetCameraInfo(ctypes.byref(info), 0) != \
                msvb.SVB_SUCCESS:
            print("fiche illisible")
            return 1
        self._fiches = [(info, None)]
        self.nom = info.FriendlyName.decode("utf-8", "replace").strip()
        print("nom    :", self.nom)
        print("série  :", info.CameraSN.decode("utf-8", "replace"))
        self._ouvrir(0)
        if self.cam_id is None:
            return 1
        print()
        for ligne in self._verdict:
            print(ligne)
        # fermeture propre (TEC coupé, capture arrêtée, caméra fermée)
        self.flux_actif = False
        if self.caps is not None and self.caps.tec:
            self.dll.SVBSetControlValue(self.cam_id, msvb.SVB_COOLER_ENABLE,
                                        0, 0)
        self.dll.SVBStopVideoCapture(self.cam_id)
        self.capture = False
        err = self.dll.SVBCloseCamera(self.cam_id)
        print("fermeture :", NOMS_ERREURS.get(err, err))
        return 0


def main():
    mode_console = "--console" in sys.argv
    if mode_console:
        class _Faux:
            """Root Tk factice pour le mode console (aucune UI créée)."""
            def after(self, *a):
                pass
            def title(self, *a):
                pass
        banc = BancSVB.__new__(BancSVB)
        banc.root = _Faux()
        banc.mode_console = True
        banc.dll = None
        banc.chemin_dll = None
        banc.cam_id = None
        banc.props = None
        banc.info = None
        banc.nom = ""
        banc.caps = None
        banc.ouverte = False
        banc.capture = False
        banc.flux_actif = False
        banc._th_flux = None
        banc._ui_q = queue.Queue()
        banc._jobs = queue.Queue()
        banc._verdict = []
        banc._n_frames = 0
        banc._derniere_photo = None
        banc._frame_attente = None
        banc._fmt_pose = None
        banc._preparer_dll()
        banc._log = print
        sys.exit(banc.detection_console())
    root = tk.Tk()
    banc = BancSVB(root)
    if not BANC_PRET:
        messagebox.showerror("Banc SVBONY — application trop ancienne",
                             message_appli_trop_ancienne())
    root.mainloop()


if __name__ == "__main__":
    main()
