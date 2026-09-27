# -*- coding: utf-8 -*-
"""Banc de test autonome caméra Player One — la MÊME DLL que l'appli.

Demande d'Alain (19/09/2026) : deuxième setup — Player One Uranus-C Pro
(IMX585 couleur, TEC, gain unitaire annoncé à 210), montée sur C8 +
réducteur 0,63 (1280 mm) sur monture Open Astro Mount, avec une SVBONY
SV305C en guidage (lunette 60/240). Il faut un programme de test qui
DÉTECTE les possibilités de la caméra, comme le banc QHY
(_diag_camera_qhy.py) : capteur, refroidissement TEC, plage offset,
plage exposition, plage gain, ROI, binning.

POURQUOI ce banc ne réutilise PAS la classe PlayerOneCamera : elle est
trop pauvre (ni offset, ni TEC, ni ROI, ni binning — seuls expo/gain).
Le banc parle donc DIRECTEMENT au SDK officiel via ctypes, en chargeant
la MÊME PlayerOneCamera.dll que l'appli (avastack/cameras/sdk_loader.py —
le fichier réellement chargé est affiché en haut de la fenêtre, comme
pour le banc QHY : ne JAMAIS interpréter un diagnostic sans connaître
le fichier exécuté). Tout ce que ce banc apprend servira à enrichir
avastack/cameras/playerone.py dans un jalon suivant.

Constantes du SDK (l'en-tête officiel POACamera.h) :
  - Configs (IDs 0-30) : POA_EXPOSURE=0 (µs), POA_GAIN=1,
    POA_HARDWARE_BIN=2, POA_TEMPERATURE=3 (°C, flottant),
    POA_WB_R/G/B=4/5/6, POA_OFFSET=7, POA_AUTOEXPO_MAX_GAIN=8,
    POA_AUTOEXPO_MAX_EXPOSURE=9 (ms), POA_AUTOEXPO_BRIGHTNESS=10,
    POA_GUIDE_N/S/E/W=11-14, POA_EGAIN=15 (e-/ADU, flottant),
    POA_COOLER_POWER=16 (%), POA_TARGET_TEMP=17 (°C), POA_COOLER=18,
    POA_HEATER=19, POA_HEATER_POWER=20, POA_FAN_POWER=21,
    POA_FLIP_NONE/HORI/VERT/BOTH=22-25, POA_FRAME_LIMIT=26 (0-2000),
    POA_HQI=27, POA_USB_BANDWIDTH_LIMIT=28, POA_PIXEL_BIN_SUM=29,
    POA_MONO_BIN=30.
  - Formats : POA_RAW8=0, POA_RAW16=1, POA_RGB24=2, POA_MONO8=3
    (RGB24 et MONO8 : caméra couleur uniquement).
  - ROI : POASetImageSize exige width % 4 == 0 et height % 2 == 0 (le SDK
    ajuste silencieusement sinon — TOUJOURS relire la taille réelle).
  - Bin/ROI/format : à poser HORS exposition (stop → set → relecture →
    start). POASetImageBin change aussi la position/la taille : relire.
  - Erreurs : POA_OK=0 … POA_ERROR_MEMORY_FAILED=17 (nommées dans le log).

Deux layouts possibles pour la structure POAConfigAttributes (le SDK
récent — bindgen 2026 — utilise POAConfigValue en union 8 octets avec
szConfName ; l'ancien SDK utilisait des c_long + szDescription en tête).
Le banc DÉTECTE le layout en vérifiant que l'ID relu correspond à l'ID
demandé sur DEUX configs indépendantes (0 puis 7) — jamais de confiance
aveugle dans une structure non confirmée.

Lancement (venv, dossier du projet) :
    venv/Scripts/python.exe bancs/cameras/_diag_camera_playerone.py
Mode console (détection rapide sans fenêtre) :
    venv/Scripts/python.exe bancs/cameras/_diag_camera_playerone.py --console

⚠ CRASH NATIF : si la fenêtre se ferme brutalement sans message, c'est un
segfault du SDK natif (Python ne peut rien afficher) — noter la DERNIÈRE
ligne du log et le bouton « 💾 Rapport ».

⚠ VERSION DE L'APPLICATION : depuis la v2.16.0, ce banc RÉUTILISE la sonde
de l'application (`avastack/cameras/playerone.py` → POASonde) au lieu d'en
garder une copie. Si la copie INSTALLÉE de l'application est antérieure,
le banc le DIT clairement (bannière rouge + boîte de dialogue + journal)
et n'ouvre pas la caméra : copier alors `avastack/cameras/playerone.py`
ET `avastack/cameras/capacites.py` depuis le dépôt, ou réinstaller la
version ≥ 2.16.0. La DÉTECTION de la caméra reste utilisable sans eux.
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import ctypes
import os
import platform
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

# --- chargement DIAGNOSTIQUÉ de l'application --------------------------------
# Depuis la v2.16.0, la sonde (POASonde) et les structures du SDK vivent dans
# avastack/cameras/playerone.py (+ capacites.py) : le banc les RÉUTILISE au
# lieu d'en garder une copie (deux copies finissent toujours par diverger).
# Si l'application INSTALLÉE est antérieure, le banc doit le DIRE clairement
# au lieu de planter sur un AttributeError — c'est le même piège que le banc
# QHY (constat réel du 19/09/2026 : banc récent + qhy.py v2.13.1).
_ERREUR_CHARGEMENT = ""
_MANQUE = []                 # symboles absents de la copie installée
try:
    import avastack.cameras.playerone as mpoa
    from avastack.cameras.playerone import _POACameraProperties, POA_OK
except Exception as e:
    mpoa = None
    _POACameraProperties = None
    POA_OK = None
    dedupliquer = None
    _ERREUR_CHARGEMENT = f"{type(e).__name__} : {e}"

if mpoa is not None:
    for _nom in ("_POAConfigValue", "_POAConfigAttributes",
                 "_POAConfigAttributesAncien", "NOMS_CONFIGS",
                 "NOMS_FORMATS", "POASonde", "dedupliquer"):
        if not hasattr(mpoa, _nom):
            _MANQUE.append(_nom)
    if _MANQUE:
        # repli minimal : le banc démarre, mais la sonde restera indisponible
        _POAConfigValue = getattr(mpoa, "_POAConfigValue", None)
        _POAConfigAttributes = getattr(mpoa, "_POAConfigAttributes", None)
        _POAConfigAttributesAncien = getattr(
            mpoa, "_POAConfigAttributesAncien", None)
        NOMS_CONFIGS = getattr(mpoa, "NOMS_CONFIGS", {})
        NOMS_FORMATS = getattr(mpoa, "NOMS_FORMATS", {})
        dedupliquer = getattr(mpoa, "dedupliquer", None)
    else:
        _POAConfigValue = mpoa._POAConfigValue
        _POAConfigAttributes = mpoa._POAConfigAttributes
        _POAConfigAttributesAncien = mpoa._POAConfigAttributesAncien
        NOMS_CONFIGS = mpoa.NOMS_CONFIGS
        NOMS_FORMATS = mpoa.NOMS_FORMATS
        dedupliquer = mpoa.dedupliquer

# Le banc est COMPLET seulement si la copie installée expose la sonde.
BANC_PRET = (mpoa is not None and not _MANQUE)
_VALIDATION_FORMATS = ("RAW8", "RAW16", "RGB24", "MONO8")


def message_appli_trop_ancienne():
    """→ texte d'explication quand l'application installée n'expose pas la
    sonde (cas réel : banc v2.16+ copié sur une installation v2.15.0)."""
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
              f"  playerone.py      : "
              f"{getattr(mpoa, '__file__', 'ABSENT')}  "
              f"({dte(getattr(mpoa, '__file__', ''))})"]
    if _ERREUR_CHARGEMENT:
        lignes.append(f"  erreur d'import    : {_ERREUR_CHARGEMENT}")
    if _MANQUE:
        lignes.append(f"  symboles manquants : {', '.join(_MANQUE)}")
    lignes += [
        "",
        "Depuis la v2.16.0, le banc RÉUTILISE la sonde de l'application",
        "(POASonde, avastack/cameras/playerone.py) au lieu d'en garder une",
        "copie — précisément pour éviter que deux copies divergent.",
        "",
        "À FAIRE (dossier d'installation, ex. %LOCALAPPDATA%\\AVAStack) :",
        "  copier avastack\\cameras\\playerone.py  ET  avastack\\cameras\\"
        "capacites.py",
        "  depuis le dépôt (ou réinstaller la version ≥ 2.16.0), puis relancer",
        "  ce banc. La détection de la caméra reste utilisable en attendant,",
        "  mais l'ouverture (listage des contrôles) sera refusée.",
    ]
    return "\n".join(lignes)

IS_WINDOWS = platform.system() == "Windows"

# --- constantes du SDK Player One (POACamera.h) ------------------------------
VALEURS = {0: "VAL_INT", 1: "VAL_FLOAT", 2: "VAL_BOOL"}

NOMS_CONFIGS = {
    0: "Exposition (µs)",
    1: "Gain (unités SDK)",
    2: "Bin matériel",
    3: "Température capteur (°C)",
    4: "Balance des blancs R",
    5: "Balance des blancs G",
    6: "Balance des blancs B",
    7: "Offset",
    8: "Gain max (auto-expo)",
    9: "Expo max (auto-expo, ms)",
    10: "Ciblage luminosité (auto-expo)",
    11: "Guidage N (ST4)",
    12: "Guidage S (ST4)",
    13: "Guidage E (ST4)",
    14: "Guidage O (ST4)",
    15: "e-/ADU (EGAIN, gain courant)",
    16: "Puissance TEC (%)",
    17: "Consigne température (°C)",
    18: "Refroidissement ON/OFF",
    19: "Chauffage antibué ON/OFF",
    20: "Puissance chauffage (%)",
    21: "Puissance ventilateur (%)",
    22: "Flip : aucun",
    23: "Flip : horizontal",
    24: "Flip : vertical",
    25: "Flip : les deux",
    26: "Limite de frames (0 = illimité)",
    27: "HQI (haute qualité, caméras sans DDR)",
    28: "Limite bande passante USB",
    29: "Bin : somme (sinon moyenne)",
    30: "Bin mono (couleur → perd le motif Bayer)",
}

NOMS_FORMATS = {0: "RAW8", 1: "RAW16", 2: "RGB24", 3: "MONO8"}

NOMS_ERREURS = {
    0: "OK", 1: "INDEX invalide", 2: "ID caméra invalide",
    3: "CONFIG invalide", 4: "ARGUMENT invalide", 5: "CAMÉRA NON OUVERTE",
    6: "CAMÉRA INTRUVABLE (débranchée ?)", 7: "HORS LIMITES",
    8: "EXPOSITION ÉCHOUÉE", 9: "TIMEOUT", 10: "BUFFER TROP PETIT",
    11: "EXPOSITION EN COURS", 12: "POINTEUR invalide",
    13: "CONFIG non écrivable", 14: "CONFIG non lisible",
    15: "ACCÈS REFUSÉ", 16: "OPÉRATION ÉCHOUÉE", 17: "MÉMOIRE",
}

BAYER = {0: "RG", 1: "BG", 2: "GR", 3: "GB"}

# (les alias _POAConfigValue / _POAConfigAttributes / NOMS_CONFIGS sont
#  définis PLUS HAUT par le chargement diagnostiqué de l'application)


class BancPOA:
    """Banc de test Player One : détection, contrôles, flux, rapport."""

    def __init__(self, root, mode_console=False):
        self.root = root
        self.mode_console = mode_console
        self.dll = None              # handle DLL (chargé par mpoa._charger_sdk)
        self.chemin_dll = None
        self.layout = "récent"       # ou "ancien" (détecté à l'ouverture)
        self.cam_id = None           # handle SDK (props.cameraID)
        self.props = None            # _POACameraProperties
        self.nom = ""
        self.ouverte = False
        self.flux_actif = False
        self._th_flux = None
        self._ui_q = queue.Queue()   # messages pour Tk (jamais SDK dans Tk)
        self._jobs = queue.Queue()   # travaux séquentiels (appel SDK)
        self._verdict = []           # lignes du rapport « possibilités »
        self._attr_cache = {}        # confID → attributs (après listage)
        self._fps = 0.0
        self._n_frames = 0
        self._derniere_photo = None
        self._frame_attente = None   # dernière frame reçue (l'UI écrase)
        self.sonde = None            # POASonde (créée à l'ouverture)

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
        prototypes ctypes utilisés par le banc."""
        if mpoa is None:
            return
        self.dll = mpoa._charger_sdk()
        if self.dll is None:
            return
        try:
            self.chemin_dll = self.dll._name
        except AttributeError:
            self.chemin_dll = "?"
        d = self.dll
        c_int, c_uint = ctypes.c_int, ctypes.c_uint
        d.POAGetCameraCount.restype = c_int
        d.POAGetCameraProperties.restype = c_int
        d.POAOpenCamera.restype = c_int
        d.POAOpenCamera.argtypes = [c_int]
        d.POACloseCamera.restype = c_int
        d.POACloseCamera.argtypes = [c_int]
        d.POAInitCamera.restype = c_int
        d.POAInitCamera.argtypes = [c_int]
        d.POAStartExposure.restype = c_int
        d.POAStartExposure.argtypes = [c_int, c_int]
        d.POAStopExposure.restype = c_int
        d.POAStopExposure.argtypes = [c_int]
        d.POAImageReady.restype = c_int
        d.POAImageReady.argtypes = [c_int, ctypes.POINTER(c_int)]
        d.POAGetImageData.restype = c_int
        d.POAGetImageData.argtypes = [c_int, ctypes.c_char_p, c_int, c_int]
        d.POASetImageFormat.restype = c_int
        d.POASetImageFormat.argtypes = [c_int, c_int]
        d.POAGetImageFormat.restype = c_int
        d.POAGetImageFormat.argtypes = [c_int, ctypes.POINTER(c_int)]
        d.POASetImageSize.restype = c_int
        d.POASetImageSize.argtypes = [c_int, c_int, c_int]
        d.POAGetImageSize.restype = c_int
        d.POAGetImageSize.argtypes = [c_int, ctypes.POINTER(c_int),
                                      ctypes.POINTER(c_int)]
        d.POASetImageStartPos.restype = c_int
        d.POASetImageStartPos.argtypes = [c_int, c_int, c_int]
        d.POAGetImageStartPos.restype = c_int
        d.POAGetImageStartPos.argtypes = [c_int, ctypes.POINTER(c_int),
                                          ctypes.POINTER(c_int)]
        d.POASetImageBin.restype = c_int
        d.POASetImageBin.argtypes = [c_int, c_int]
        d.POAGetImageBin.restype = c_int
        d.POAGetImageBin.argtypes = [c_int, ctypes.POINTER(c_int)]
        d.POASetConfig.restype = c_int
        d.POASetConfig.argtypes = [c_int, c_uint, _POAConfigValue, c_uint]
        d.POAGetConfig.restype = c_int
        d.POAGetConfig.argtypes = [c_int, c_uint,
                                   ctypes.POINTER(_POAConfigValue),
                                   ctypes.POINTER(c_uint)]
        d.POAGetConfigsCount.restype = c_int
        d.POAGetConfigsCount.argtypes = [c_int, ctypes.POINTER(c_int)]
        d.POAGetConfigAttributes.restype = c_int
        d.POAGetConfigAttributes.argtypes = [c_int, c_int, ctypes.c_void_p]
        d.POAGetConfigAttributesByConfigID.restype = c_int
        d.POAGetConfigAttributesByConfigID.argtypes = [c_int, c_uint,
                                                       ctypes.c_void_p]

    def _err(self, code):
        """→ nom lisible de l'erreur SDK."""
        return NOMS_ERREURS.get(code, f"code {code}")

    # --- lecture/écriture des configs : DÉLÉGUÉE À POASonde
    #     (avastack/cameras/playerone.py) — le banc n'a qu'une seule
    #     définition de la logique SDK, comme l'application. -------------------

    def _valeur_union(self, u, type_val):
        return self.sonde.valeur_union(u, type_val)

    def _union_depuis(self, val, type_val):
        return self.sonde.union_depuis(val, type_val)

    def _attributs(self, conf_id):
        return self.sonde.attributs(conf_id)

    def _valider_layout(self):
        layout = self.sonde.valider_layout()
        self.layout = self.sonde.layout
        return layout

    def _lire_config(self, conf_id):
        return self.sonde.lire(conf_id)

    def _poser_config(self, conf_id, val):
        """Pose une valeur (type déduit des attributs connus). → True/False."""
        t = self._attr_cache.get(conf_id, {}).get("type", 0)
        err = self.dll.POASetConfig(self.cam_id, conf_id,
                                    self.sonde.union_depuis(val, t), 0)
        if err != POA_OK:
            self._log(f"✗ {NOMS_CONFIGS.get(conf_id, conf_id)} = {val} → "
                      f"REFUSÉ ({self._err(err)})")
            return False
        relue = self._lire_config(conf_id)
        if relue is not None:
            self._log(f"✓ {NOMS_CONFIGS.get(conf_id, conf_id)} = {val} "
                      f"(relu : {relue[0]})")
        else:
            self._log(f"✓ {NOMS_CONFIGS.get(conf_id, conf_id)} = {val} "
                      f"(pose OK, relecture KO)")
        return True

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
                    # file grossit pendant que Tk dessine, et l'aperçu prend
                    # un retard irrattrapable)
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
        # cadence de rafraîchissement : rapide PENDANT le flux (sinon
        # l'aperçu n'avance qu'une fois toutes les 2 s), lente au repos
        self.root.after(200 if self.flux_actif else 2000, self._poll_ui)

    def _travail_temp(self):
        """Lecture température + puissance TEC (thread de travail)."""
        if not self.ouverte:
            return
        t = self._lire_config(3)      # POA_TEMPERATURE (flottant)
        p = self._lire_config(16)     # POA_COOLER_POWER (%)
        cible = self._lire_config(17)  # POA_TARGET_TEMP
        txt = "Capteur : "
        txt += f"{t[0]:.1f} °C" if t else "?"
        txt += f" · TEC : {p[0]} %" if p else " · TEC : ?"
        if cible is not None:
            txt += f" · consigne {cible[0]} °C"
        self._ui_q.put(("temp", txt))

    # --- construction de la fenêtre -------------------------------------------

    def _construire_ui(self):
        self.root.title("Banc de test Player One — AVAStack")
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
                   command=self._action_lister_controles,
                   state="disabled").pack(side="left")
        ttk.Button(ligne2, text="✅ Verdict « possibilités » → log",
                   command=self._action_verdict,
                   state="disabled").pack(side="left", padx=4)
        self.btn_verdict = ligne2.winfo_children()[-1]
        ttk.Button(ligne2, text="💾 Sauver le rapport",
                   command=self._action_rapport).pack(side="left", padx=4)

        self.lbl_verdict = tk.Label(self.root, anchor="w", justify="left",
                                    fg="#000080")
        self.lbl_verdict.pack(fill="x", padx=8, pady=2)

        # --- panneau de contrôles -------------------------------------------------
        ctrl = ttk.LabelFrame(self.root, text="Contrôles en direct")
        ctrl.pack(fill="x", padx=8, pady=2)
        # exposition (µs)
        ttk.Label(ctrl, text="Expo (µs) :").grid(row=0, column=0)
        self.ent_expo = ttk.Entry(ctrl, width=9)
        self.ent_expo.grid(row=0, column=1)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_expo).grid(row=0, column=2,
                                                    padx=(2, 8))
        # gain
        ttk.Label(ctrl, text="Gain :").grid(row=0, column=3)
        self.ent_gain = ttk.Entry(ctrl, width=9)
        self.ent_gain.grid(row=0, column=4)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_gain).grid(row=0, column=5,
                                                    padx=(2, 8))
        # offset
        ttk.Label(ctrl, text="Offset :").grid(row=0, column=6)
        self.ent_offset = ttk.Entry(ctrl, width=9)
        self.ent_offset.grid(row=0, column=7)
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_offset).grid(row=0, column=8,
                                                      padx=(2, 8))
        # TEC
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
        # binning / format / USB / flip
        ttk.Label(ctrl, text="Bin :").grid(row=1, column=0, pady=(6, 0))
        self.cmb_bin = ttk.Combobox(ctrl, width=6, state="disabled",
                                    values=["1"])
        self.cmb_bin.current(0)
        self.cmb_bin.grid(row=1, column=1, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_bin).grid(
            row=1, column=2, padx=(2, 8), pady=(6, 0))
        ttk.Label(ctrl, text="Format :").grid(row=1, column=3,
                                              pady=(6, 0))
        self.cmb_fmt = ttk.Combobox(ctrl, width=9, state="disabled",
                                    values=["RAW16"])
        self.cmb_fmt.current(0)
        self.cmb_fmt.grid(row=1, column=4, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_format).grid(
            row=1, column=5, padx=(2, 8), pady=(6, 0))
        ttk.Label(ctrl, text="USB BP :").grid(row=1, column=6, pady=(6, 0))
        self.ent_usb = ttk.Entry(ctrl, width=7)
        self.ent_usb.grid(row=1, column=7, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_usb).grid(
            row=1, column=8, padx=(2, 8), pady=(6, 0))
        ttk.Label(ctrl, text="Flip :").grid(row=1, column=9, pady=(6, 0))
        self.cmb_flip = ttk.Combobox(ctrl, width=9, state="disabled",
                                     values=["aucun", "horizontal",
                                             "vertical", "les deux"])
        self.cmb_flip.current(0)
        self.cmb_flip.grid(row=1, column=10, pady=(6, 0))
        ttk.Button(ctrl, text="Poser",
                   command=self._tk_pose_flip).grid(
            row=1, column=11, padx=(2, 2), pady=(6, 0))
        self.lbl_temp = ttk.Label(ctrl, text="Capteur : ? · TEC : ?")
        self.lbl_temp.grid(row=1, column=12, columnspan=2, padx=4,
                           pady=(6, 0))

        # --- ROI ------------------------------------------------------------------
        roi = ttk.LabelFrame(self.root, text="ROI (largeur %4==0, hauteur "
                                              "%2==0 — le SDK ajuste : "
                                              "relire)")
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

    # --- actions (côté Tk : ne font QUE de l'UI + _travail) --------------------

    def _maj_lbl_fichiers(self):
        """Affiche les fichiers réellement chargés (leçon du banc QHY : ne
        JAMAIS interpréter un diagnostic sans connaître le fichier exécuté)."""
        def dte(p):
            try:
                return time.strftime("%d/%m/%Y %H:%M",
                                     time.localtime(os.path.getmtime(p)))
            except OSError:
                return "?"
        mp = getattr(mpoa, "__file__", None) or "ABSENT (import impossible)"
        dll = self.chemin_dll or "INTRUVABLE (SDK absent !)"
        self.lbl_fichiers.configure(text=(
            f"DLL SDK   : {dll}  ({dte(dll)})\n"
            f"playerone.py : {mp}  ({dte(mp)})\n"
            f"Structure POAConfigAttributes : layout « {self.layout} » "
            f"(validé à l'ouverture, repli « ancien » prévu)",))
        if self.dll is None:
            self.lbl_fichiers.configure(fg="#aa0000")

    def _action_detecter(self):
        self._travail(self._detecter)

    def _detecter(self):
        """Énumère les caméras + lit la fiche de chacune (thread de travail)."""
        if self.dll is None:
            self._log("✗ SDK Player One introuvable : place PlayerOneCamera"
                      ".dll dans le dossier du projet (ou AVASTACK_PLAYERONE"
                      "_DIR).")
            return
        n = self.dll.POAGetCameraCount()
        self._log(f"POAGetCameraCount() → {n}")
        if n == 0:
            self._log("Aucune caméra Player One détectée (vérifier le câble "
                      "USB et le pilote).")
            return
        self._fiches = []
        noms = []
        for i in range(n):
            p = _POACameraProperties()
            if self.dll.POAGetCameraProperties(i, ctypes.byref(p)) != POA_OK:
                self._log(f"✗ fiche caméra #{i} illisible")
                continue
            self._fiches.append(p)
            noms.append(p.cameraModelName.decode("utf-8", "replace").strip()
                        or f"POA #{i}")
            self._log(f"#{i} : {noms[-1]} · "
                      f"capteur {p.sensorModelName.decode('utf-8','replace')}"
                      f" · {p.maxWidth}×{p.maxHeight} px · "
                      f"{p.bitDepth} bits")
        self._ui_q.put(("cams", (noms, self._fiches)))

    def _maj_fiche(self):
        """Affiche la fiche détaillée de la caméra sélectionnée (Tk)."""
        sel = self.cmb_cams.current()
        if sel < 0 or not getattr(self, "_fiches", None):
            return
        p = self._fiches[sel]
        self.props = p
        bins = dedupliquer([b for b in p.bins_ if 1 <= b <= 4]) \
            if dedupliquer else [b for b in p.bins_ if 1 <= b <= 4]
        fmts = dedupliquer([NOMS_FORMATS.get(f, str(f)) for f in p.imgFormats_
                            if 0 <= f <= 3]) if dedupliquer else \
            [NOMS_FORMATS.get(f, str(f)) for f in p.imgFormats_
             if 0 <= f <= 3]
        coul = "COULEUR" if p.isColorCamera else "mono"
        tec = "TEC OUI" if p.isHasCooler else "TEC non"
        self._log("=== FICHE ===")
        self._log(f"  modèle       : {p.cameraModelName.decode('utf-8','replace')}")
        self._log(f"  capteur      : {p.sensorModelName.decode('utf-8','replace')}"
                  f" ({coul}, {p.bitDepth} bits, Bayer "
                  f"{BAYER.get(p.bayerPattern_, p.bayerPattern_)})")
        self._log(f"  plein champ  : {p.maxWidth}×{p.maxHeight} px"
                  f" · pixel {p.pixelSize:.2f} µm")
        self._log(f"  matériel     : {tec} · ST4 "
                  f"{'oui' if p.isHasST4Port else 'non'}"
                  f" · USB{'3' if p.isUSB3Speed else '2'} · "
                  f"bin matériel {'oui' if p.isSupportHardBin else 'non'}")
        self._log(f"  bins supportés : {bins} · formats : {fmts}")
        self._log(f"  n° série     : {p.SN.decode('utf-8','replace')}")

    def _action_ouvrir(self):
        sel = self.cmb_cams.current()
        if sel < 0:
            return
        self._travail(lambda: self._ouvrir(sel))

    def _ouvrir(self, index):
        """Ouvre la caméra (thread de travail) : open + init + format plein
        champ, puis validation du layout de la structure d'attributs."""
        if not BANC_PRET:
            for ligne in message_appli_trop_ancienne().splitlines():
                self._log(ligne)
            return
        if self.ouverte:
            self._fermer()
        p = self._fiches[index]
        self._log(f"=== OUVERTURE #{index} : "
                  f"{p.cameraModelName.decode('utf-8','replace')} ===")
        if self.dll.POAOpenCamera(p.cameraID) != POA_OK:
            self._log("✗ POAOpenCamera a échoué")
            return
        self._log("  POAOpenCamera OK")
        if self.dll.POAInitCamera(p.cameraID) != POA_OK:
            self._log("✗ POAInitCamera a échoué")
            self.dll.POACloseCamera(p.cameraID)
            return
        self._log("  POAInitCamera OK")
        self.cam_id = p.cameraID
        self.props = p
        self.nom = p.cameraModelName.decode("utf-8", "replace").strip()
        # sonde des capacités : LE MÊME code que l'application
        self.sonde = mpoa.POASonde(self.dll, self.cam_id)
        layout = self._valider_layout()
        if layout is None:
            self._log("⚠ layout de POAConfigAttributes NON reconnu — le "
                      "tableau des contrôles sera douteux (rapporter ce log)")
        else:
            self._log(f"  layout POAConfigAttributes validé sur configs 0 "
                      f"et 7 : « {layout} »")
        # format par défaut : couleur → RGB24 (débayerisation par la caméra,
        # comme dans l'appli), mono → RAW16
        fmt = 2 if p.isColorCamera else 1
        self.dll.POASetImageFormat(self.cam_id, fmt)
        self.dll.POASetImageSize(self.cam_id, p.maxWidth, p.maxHeight)
        w, h = self._lire_taille()
        self._log(f"  format {NOMS_FORMATS.get(fmt)} · taille relu : "
                  f"{w}×{h}")
        # DÉMARRER l'exposition à l'ouverture (constat réel du 19/09/2026 :
        # sans cela, POAImageReady ne répond JAMAIS — le flux n'a reçu des
        # frames que grâce à la relance de diagnostic, 3 s plus tard).
        err = self.dll.POAStartExposure(self.cam_id, 0)
        self._log(f"  POAStartExposure(0) → {self._err(err)}")
        self.ouverte = True
        self._attr_cache = {}
        self._ui_q.put(("ouvert", None))
        # énumération automatique des contrôles + verdict « possibilités »
        self._lister_controles()
        self._travail_temp()

    def _lire_taille(self):
        """→ (w, h) courants de la ROI."""
        w, h = ctypes.c_int(0), ctypes.c_int(0)
        if self.dll.POAGetImageSize(self.cam_id, ctypes.byref(w),
                                    ctypes.byref(h)) != POA_OK:
            return (self.props.maxWidth, self.props.maxHeight)
        return (w.value, h.value)

    def _action_fermer(self):
        self._travail(self._fermer)

    def _fermer(self):
        """Arrête le flux, coupe le TEC et ferme la caméra (thread de
        travail)."""
        self.flux_actif = False
        if not self.ouverte:
            return
        self._log("=== FERMETURE ===")
        self.dll.POAStopExposure(self.cam_id)
        # couper le TEC avant de fermer (même principe que le banc QHY :
        # ne jamais laisser le refroidissement actif pendant la fermeture)
        u = _POAConfigValue()
        u.intValue = 0
        self.dll.POASetConfig(self.cam_id, 18, u, 0)   # POA_COOLER = OFF
        err = self.dll.POACloseCamera(self.cam_id)
        self._log(f"  POACloseCamera → {self._err(err)}")
        self.ouverte = False
        self.cam_id = None
        self._ui_q.put(("ferme", None))

    def _action_lister_controles(self):
        self._travail(self._lister_controles)

    def _lister_controles(self):
        """Énumère TOUS les contrôles supportés avec leurs attributs +
        valeur courante (thread de travail).

        ⚠ Passe par `self.sonde.lister()` et NON par une boucle locale : la
        sonde est la SEULE à remplir son cache de types, sans lequel les
        contrôles FLOTTANTS (température, e-/ADU, « Exp ») étaient relus
        comme des ENTIERS — constat réel du 19/09/2026 : la température
        s'affichait « -1073741824 » (les bits du flottant -2.0 lus en
        entier) et « Exp » « 1202590843 »."""
        if not self.ouverte:
            self._log("Ouvre d'abord la caméra.")
            return
        cache = self.sonde.lister()          # remplit AUSSI son cache de types
        self._attr_cache = cache
        self._log(f"=== {len(cache)} CONTRÔLES SUPPORTÉS ===")
        for cid in sorted(cache):
            a = cache[cid]
            cur = self.sonde.lire(cid)
            curseur = f"courant {cur[0]}" if cur else "courant ?"
            flags = "".join((("W" if a["ecrivable"] else "-"),
                             ("R" if a["lisible"] else "-"),
                             ("A" if a["auto"] else "-")))
            hors = ""
            if a["min"] is not None and a["max"] is not None and \
                    isinstance(a["defaut"], (int, float)) and \
                    not (a["min"] <= a["defaut"] <= a["max"]):
                hors = " ⚠ DÉFAUT HORS BORNES (attribut peu fiable)"
            self._log(f"  {cid:>2} {a['nom']:<28} [{VALEURS[a['type']]:<9}] "
                      f"{flags} min {a['min']} max {a['max']} défaut "
                      f"{a['defaut']} · {curseur}{hors}")
        self._log("(W = écrivable, R = lisible, A = mode auto supporté)")
        self._construire_verdict()

    def _construire_verdict(self):
        """Construit le résumé « possibilités » de la caméra (le livrable
        demandé : capteur, TEC, offset, expo, gain, ROI, binning)."""
        v = []
        p = self.props
        if p is not None:
            v.append("CAMÉRA : " + p.cameraModelName.decode("utf-8",
                                                            "replace").strip())
            v.append("CAPTEUR : "
                    + p.sensorModelName.decode("utf-8", "replace").strip()
                    + f" · {p.maxWidth}×{p.maxHeight} px · "
                      f"{p.bitDepth} bits · pixel {p.pixelSize:.2f} µm"
                    + (" · COULEUR" if p.isColorCamera else " · mono"))
        a_expo = self._attr_cache.get(0)
        a_gain = self._attr_cache.get(1)
        a_off = self._attr_cache.get(7)
        a_tec = self._attr_cache.get(18)
        a_cible = self._attr_cache.get(17)
        a_temp = self._attr_cache.get(3)
        a_egal = self._attr_cache.get(15)
        if a_expo:
            v.append(f"EXPOSITION : {a_expo['min']} µs → "
                     f"{a_expo['max']} µs ({a_expo['max']/1e6:.1f} s)")
        if a_gain:
            unite = ("210 = gain unitaire (IMX585, spec constructeur) "
                     "DANS la plage" if a_gain["min"] <= 210 <= a_gain["max"]
                     else "⚠ 210 HORS plage annoncée — à vérifier en réel")
            v.append(f"GAIN : {a_gain['min']} → {a_gain['max']} (unités SDK) "
                     f"— gain unitaire {unite}")
        if a_off:
            v.append(f"OFFSET : {a_off['min']} → {a_off['max']}")
        if a_egal:
            # e-/ADU : la valeur COURANTE est la seule pertinente ; le
            # « défaut » de l'attribut peut être INCOHÉRENT avec ses propres
            # bornes (constat réel : 11,40 hors de [0, 10] sur l'Uranus-C Pro
            # — attribut peu fiable, l'e-/ADU change de toute façon avec le
            # gain).
            cur = None
            if self.sonde is not None and self.dll is not None:
                try:
                    cur = self.sonde.lire(15)
                except Exception:
                    cur = None
            courant = cur[0] if cur else None
            txt = f"EGAIN : courant {courant:.2f} e-/ADU" if courant is not None \
                else "EGAIN : courant illisible"
            txt += f" · défaut annoncé {a_egal['defaut']:.2f} (bornes " \
                   f"{a_egal['min']}–{a_egal['max']}"
            txt += " ⚠ le défaut est HORS de ses bornes : ne pas s'y fier)"
            v.append(txt)
        # contrôles AU-DELÀ de l'enum documentée (0-30) : la DLL en expose
        # réellement (constat réel : 31 « Exp », exposition en SECONDES avec
        # un maximum différent du contrôle 0 en µs) — les signaler évite de
        # croire qu'une seule plage d'exposition existe.
        extras = [c for c in sorted(self._attr_cache) if c > 30]
        if extras:
            details = " · ".join(
                f"{c} « {self._attr_cache[c]['nom']} » "
                f"{self._attr_cache[c]['min']}→{self._attr_cache[c]['max']}"
                for c in extras)
            v.append(f"CONTRÔLES AU-DELÀ DE L'ENUM DOCUMENTÉE (0-30) : "
                     f"{details}")
        tec_fiche = bool(p.isHasCooler) if p is not None else False
        v.append(f"REFROIDISSEMENT : fiche {'TEC OUI' if tec_fiche else 'TEC non'}"
                 + (f" · contrôle POA_COOLER "
                    f"{'écrivable ✓' if a_tec and a_tec['ecrivable'] else 'INDISPONIBLE'}"
                    if tec_fiche else "")
                 + (f" · consigne {a_cible['min']}→{a_cible['max']} °C"
                    if a_cible else "")
                 + (f" · température lisible "
                    f"{'✓' if a_temp and a_temp['lisible'] else '✗'}"
                    if tec_fiche else ""))
        bins = dedupliquer([b for b in p.bins_ if 1 <= b <= 4]) \
            if p is not None else []
        v.append(f"BINNING : {bins}"
                 + (" · bin MATÉRIEL oui" if p.isSupportHardBin else "")
                 + (" · PIXEL_BIN_SUM dispo" if 29 in self._attr_cache else "")
                 + (" · MONO_BIN dispo" if 30 in self._attr_cache else ""))
        v.append(f"ROI : plein champ {p.maxWidth}×{p.maxHeight} (posé OK au "
                 f"lancement) — largeur multiple de 4, hauteur multiple de 2")
        # formats : tableau de taille FIXE côté SDK, queue de remplissage =
        # « RAW8 » (valeur valide) → dédupliquer (constat réel : 4 × RAW8)
        fmts = dedupliquer([NOMS_FORMATS.get(f, str(f)) for f in p.imgFormats_
                            if 0 <= f <= 3])
        v.append(f"FORMATS : {fmts} · USB3 : "
                 f"{'oui' if p.isUSB3Speed else 'non'} · ST4 : "
                 f"{'oui' if p.isHasST4Port else 'non'}")
        v.append(f"LAYOUT STRUCTURE ATTRIBUTS : « {self.layout} »")
        self._verdict = v
        self._ui_q.put(("verdict", "\n".join(v)))

    def _ent_valeur(self, entry, defaut=0):
        """Lit une valeur entière d'une Entry (Tk) avec repli (thread Tk)."""
        try:
            return int(float(entry.get()))
        except (ValueError, tk.TclError):
            return defaut

    # --- poses de réglages : lecture des widgets DANS le thread Tk, puis
    #     SDK dans le thread de travail (règle du projet : jamais .get() Tk
    #     hors thread principal) ----------------------------------------------

    def _tk_pose_expo(self):
        val = self._ent_valeur(self.ent_expo, 10000)
        self._travail(lambda: self._pose_expo(val))

    def _tk_pose_gain(self):
        val = self._ent_valeur(self.ent_gain, 210)
        self._travail(lambda: self._pose_gain(val))

    def _tk_pose_offset(self):
        val = self._ent_valeur(self.ent_offset, 25)
        self._travail(lambda: self._pose_offset(val))

    def _tk_tec_on(self):
        cible = self._ent_valeur(self.ent_temp, -10)
        self._travail(lambda: self._tec_on(cible))

    def _tk_pose_usb(self):
        val = self._ent_valeur(self.ent_usb, 40)
        self._travail(lambda: self._pose_usb(val))

    def _tk_pose_flip(self):
        choix = self.cmb_flip.get()
        self._travail(lambda: self._pose_flip(choix))

    def _tk_pose_bin(self):
        try:
            bin_val = int(self.cmb_bin.get())
        except ValueError:
            return
        self._travail(lambda: self._pose_bin(bin_val))

    def _tk_pose_format(self):
        inv = {v: k for k, v in NOMS_FORMATS.items()}
        fmt = inv.get(self.cmb_fmt.get())
        if fmt is None:
            return
        self._travail(lambda: self._pose_format(fmt))

    def _tk_pose_roi(self):
        sx = self._ent_valeur(self.ent_roi0, 0)
        sy = self._ent_valeur(self.ent_roi1, 0)
        w = self._ent_valeur(self.ent_roi2, self.props.maxWidth
                             if self.props else 0)
        h = self._ent_valeur(self.ent_roi3, self.props.maxHeight
                             if self.props else 0)
        self._travail(lambda: self._pose_roi(sx, sy, w, h))

    def _pose_expo(self, val):
        if not self.ouverte:
            return
        self._poser_config(0, val)

    def _pose_gain(self, val):
        if not self.ouverte:
            return
        self._poser_config(1, val)

    def _pose_offset(self, val):
        if not self.ouverte:
            return
        self._poser_config(7, val)

    def _tec_on(self, cible):
        """Active la régulation TEC à la consigne (thread de travail)."""
        if not self.ouverte:
            return
        cible = self._ent_valeur(self.ent_temp, -10)
        ok1 = self._poser_config(17, cible)      # POA_TARGET_TEMP
        u = _POAConfigValue()
        u.intValue = 1
        err = self.dll.POASetConfig(self.cam_id, 18, u, 0)   # POA_COOLER ON
        if err == POA_OK:
            self._log(f"❄ POA_COOLER = ON (régulation à {cible} °C) — "
                      f"laisser 1-2 min pour voir la descente")
        else:
            self._log(f"✗ POA_COOLER ON refusé ({self._err(err)}) — "
                      f"vérifier l'alimentation 12 V")
        if ok1:
            self._travail_temp()

    def _tec_off(self):
        if not self.ouverte:
            return
        u = _POAConfigValue()
        u.intValue = 0
        err = self.dll.POASetConfig(self.cam_id, 18, u, 0)
        self._log(("⏹ POA_COOLER = OFF" if err == POA_OK else
                   f"✗ POA_COOLER OFF refusé ({self._err(err)})"))
        self._travail_temp()

    def _pose_usb(self, val):
        if not self.ouverte:
            return
        self._poser_config(28, val)

    def _pose_flip(self, choix):
        """Flip : pose les 4 configs en cohérence (une seule vraie)."""
        if not self.ouverte:
            return
        vals = {22: False, 23: False, 24: False, 25: False}
        if choix == "horizontal":
            vals[23] = True
        elif choix == "vertical":
            vals[24] = True
        elif choix == "les deux":
            vals[25] = True
        else:
            vals[22] = True
        for cid, val in vals.items():
            if cid in self._attr_cache and self._attr_cache[cid]["ecrivable"]:
                self._poser_config(cid, val)

    def _stop_expo_si_besoin(self):
        """Arrête l'exposition (préalable à tout changement ROI/bin/format)."""
        err = self.dll.POAStopExposure(self.cam_id)
        if err != POA_OK and err != 11:            # 11 = EXPOSING (déjà fait)
            self._log(f"⚠ POAStopExposure → {self._err(err)}")

    def _pose_bin(self, bin_val):
        """Change le binning : stop → POASetImageBin → relecture taille/
        position (le SDK divise automatiquement) → start."""
        if not self.ouverte:
            return
        self._stop_expo_si_besoin()
        err = self.dll.POASetImageBin(self.cam_id, bin_val)
        if err != POA_OK:
            self._log(f"✗ POASetImageBin({bin_val}) refusé "
                      f"({self._err(err)})")
            return
        w, h = self._lire_taille()
        sx, sy = self._lire_position()
        b = ctypes.c_int(0)
        self.dll.POAGetImageBin(self.cam_id, ctypes.byref(b))
        self._log(f"✓ bin {bin_val} posé (relu {b.value}) → taille "
                  f"{w}×{h}, départ ({sx},{sy})")
        self.dll.POAStartExposure(self.cam_id, 0)

    def _lire_position(self):
        """→ (startX, startY) courants."""
        sx, sy = ctypes.c_int(0), ctypes.c_int(0)
        if self.dll.POAGetImageStartPos(self.cam_id, ctypes.byref(sx),
                                        ctypes.byref(sy)) != POA_OK:
            return (0, 0)
        return (sx.value, sy.value)

    def _pose_roi(self, sx, sy, w, h):
        """Pose la ROI : stop → start pos → size → relecture (le SDK ajuste
        au multiple imposé) → start."""
        if not self.ouverte:
            return
        self._stop_expo_si_besoin()
        e1 = self.dll.POASetImageStartPos(self.cam_id, sx, sy)
        e2 = self.dll.POASetImageSize(self.cam_id, w, h)
        rw, rh = self._lire_taille()
        rsx, rsy = self._lire_position()
        if e1 == POA_OK and e2 == POA_OK:
            self._log(f"✓ ROI posée ({sx},{sy} {w}×{h}) → relu : "
                      f"({rsx},{rsy}) {rw}×{rh}")
        else:
            self._log(f"✗ ROI refusée : start {self._err(e1)}, "
                      f"size {self._err(e2)} (relu : ({rsx},{rsy}) "
                      f"{rw}×{rh})")
        self.dll.POAStartExposure(self.cam_id, 0)

    def _roi_plein(self):
        if not self.ouverte:
            return
        self._stop_expo_si_besoin()
        self.dll.POASetImageStartPos(self.cam_id, 0, 0)
        self.dll.POASetImageSize(self.cam_id, self.props.maxWidth,
                                 self.props.maxHeight)
        w, h = self._lire_taille()
        rsx, rsy = self._lire_position()
        self._log(f"✓ plein champ relu : ({rsx},{rsy}) {w}×{h}")
        self.dll.POAStartExposure(self.cam_id, 0)

    def _pose_format(self, fmt):
        """Change le format d'image (RAW8=0/RAW16=1/RGB24=2/MONO8=3)."""
        if not self.ouverte:
            return
        self._stop_expo_si_besoin()
        err = self.dll.POASetImageFormat(self.cam_id, fmt)
        if err != POA_OK:
            self._log(f"✗ POASetImageFormat({NOMS_FORMATS[fmt]}) refusé "
                      f"({self._err(err)})")
            return
        f = ctypes.c_int(0)
        self.dll.POAGetImageFormat(self.cam_id, ctypes.byref(f))
        w, h = self._lire_taille()
        self._log(f"✓ format {NOMS_FORMATS.get(f.value)} posé · taille "
                  f"{w}×{h}")
        self.dll.POAStartExposure(self.cam_id, 0)

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
        """Thread de lecture : POAImageReady → POAGetImageData (les mêmes
        primitives que PlayerOneCamera.read(), mais en interrogeant la
        taille/le format À CHAQUE frame — la ROI et le bin peuvent changer).

        DIAGNOSTIC (constat réel du 19/09/2026 : « aucune frame depuis 4 s »
        sans la moindre information) : l'état est journalisé AVANT le départ,
        une relance UNIQUE de l'exposition est tentée à mi-patience, et le
        message d'abandon dit exactement où on en est. Patience = 2× expo
        courante, minimum 6 s (une première frame de 25 Mo peut être lente)."""
        expo = self._lire_config(0)
        expo_s = (expo[0] / 1e6) if expo and expo[0] > 0 else 0.01
        patience = max(2.0 * expo_s, 6.0)
        w, h = self._lire_taille()
        fmt_int = ctypes.c_int(0)
        self.dll.POAGetImageFormat(self.cam_id, ctypes.byref(fmt_int))
        octets = w * h * (3 if fmt_int.value == 2 else
                          (1 if fmt_int.value in (0, 3) else 2))
        self._log(f"▶ flux : format {NOMS_FORMATS.get(fmt_int.value)}, "
                  f"{w}×{h} px, expo {expo_s * 1000:.1f} ms, "
                  f"~{octets / 1e6:.1f} Mo par frame, patience "
                  f"{patience:.0f} s")
        t_derniere = time.time()
        non_prete = 0
        relance_faite = False
        while self.flux_actif and self.ouverte:
            ready = ctypes.c_int(0)
            self.dll.POAImageReady(self.cam_id, ctypes.byref(ready))
            if not ready.value:
                non_prete += 1
                dt = time.time() - t_derniere
                if not relance_faite and dt > patience / 2:
                    relance_faite = True
                    err = self.dll.POAStartExposure(self.cam_id, 0)
                    self._log(f"⚠ aucune frame après {dt:.1f} s "
                              f"({non_prete} appels « non prête ») → relance "
                              f"POAStartExposure(0) → {self._err(err)}")
                if dt > patience:
                    self._log(
                        f"⚠ TOUJOURS aucune frame après {patience:.0f} s "
                        f"(expo {expo_s * 1000:.0f} ms, {non_prete} appels "
                        f"« non prête », format "
                        f"{NOMS_FORMATS.get(fmt_int.value)}, {w}×{h}) — "
                        f"STOP flux. Pistes : format/taille trop lourds pour "
                        f"l'USB (essayer Bin 2 ou une ROI plus petite), ou "
                        f"exposition déjà pilotée par un autre logiciel.")
                    self.flux_actif = False
                    self._ui_q.put(("fluxfini", None))
                time.sleep(0.02)
                continue
            t_derniere = time.time()
            non_prete = 0
            w, h = self._lire_taille()
            f = ctypes.c_int(0)
            self.dll.POAGetImageFormat(self.cam_id, ctypes.byref(f))
            fmt = f.value
            if fmt == 2:                              # RGB24
                buf = np.zeros(h * w * 3, dtype=np.uint8)
            elif fmt == 0 or fmt == 3:                # RAW8 / MONO8
                buf = np.zeros(h * w, dtype=np.uint8)
            else:                                     # RAW16
                buf = np.zeros(h * w * 2, dtype=np.uint8)
            err = self.dll.POAGetImageData(
                self.cam_id, buf.ctypes.data_as(ctypes.c_char_p),
                buf.nbytes, 1000)
            if err != POA_OK:
                self._log(f"⚠ POAGetImageData → {self._err(err)}")
                continue
            if fmt == 2:
                img = buf.reshape(h, w, 3)
            elif fmt == 0 or fmt == 3:
                img = buf.reshape(h, w)
            else:
                img = buf.view(np.uint16).reshape(h, w)
            self._n_frames += 1
            self._fps = self._n_frames / max(time.time() - t0, 0.001)
            self._ui_q.put(("fps", f"{self._n_frames} frames · "
                                   f"{self._fps:.2f} fps · {w}×{h} "
                                   f"({NOMS_FORMATS.get(fmt)})"))
            self._ui_q.put(("frame", img))
        self._ui_q.put(("fluxfini", None))

    def _afficher_frame(self, img):
        """Convertit et affiche une frame dans le label (Tk).

        DÉCIMATION AVANT CALCUL (constat réel : une frame RGB24 plein format
        fait 25 Mo — un percentile plein format coûte des secondes et fait
        « bouchonner » l'aperçu, jusqu'à ne plus rien voir bouger). Le niveau
        bas/haut est donc mesuré sur une version sous-échantillonnée."""
        pas = max(1, int(max(img.shape[0], img.shape[1]) / 900))
        petit = img[::pas, ::pas]
        if petit.ndim == 3:                       # RGB24 : déjà en 8 bits
            u8 = petit
        else:
            lo, hi = np.percentile(petit, (0.1, 99.9))
            if hi <= lo:
                hi = lo + 1
            u8 = np.clip((img[::pas, ::pas].astype(np.float32) - lo)
                         * 255.0 / (hi - lo), 0, 255).astype(np.uint8)
        pil = Image.fromarray(u8)
        # mise à l'échelle pour tenir dans ~460 px de large
        lw = 460
        lh = int(pil.height * lw / pil.width)
        pil = pil.resize((lw, max(1, lh)))
        self._derniere_photo = ImageTk.PhotoImage(pil)
        self.lbl_image.configure(image=self._derniere_photo,
                                 width=lw, height=max(1, lh))

    # --- verdict / rapport ------------------------------------------------------

    def _action_verdict(self):
        txt = "\n".join(self._verdict) or "Lance d'abord « Lister les " \
              "contrôles »."
        self.lbl_verdict.configure(text=txt)
        for ligne in self._verdict:
            self._log("VERDICT : " + ligne)

    def _action_rapport(self):
        """Écrit le rapport complet (fiche + attributs + verdict + log) dans
        %TEMP% et affiche le chemin."""
        def dte(p):
            try:
                return time.strftime("%Y-%m-%d %H:%M",
                                     time.localtime(os.path.getmtime(p)))
            except OSError:
                return "?"
        nom = time.strftime("avastack_poa_diag_%Y%m%d_%H%M%S.txt")
        chemin = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")),
                              nom)
        lignes = ["Rapport banc Player One — " + time.strftime(
            "%d/%m/%Y %H:%M:%S"),
            f"DLL           : {self.chemin_dll} ({dte(self.chemin_dll)})",
            f"playerone.py  : {mpoa.__file__} ({dte(mpoa.__file__)})",
            f"Layout attributs : {self.layout}",
            "",
            "=== VERDICT « POSSIBILITÉS » ==="]
        lignes += self._verdict or ["(lister les contrôles d'abord)"]
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

    # --- mises à jour UI déclenchées par la file --------------------------------

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
            self.btn_verdict.configure(state="disabled")
        elif genre == "ferme":
            self.btn_ouvrir.configure(state="normal")
            self.btn_fermer.configure(state="disabled")
            self.lbl_etat.configure(text="caméra non ouverte",
                                    foreground="#000000")
            self.lbl_verdict.configure(text="")
        elif genre == "verdict":
            self.lbl_verdict.configure(text=contenu)
            self.btn_verdict.configure(state="normal")
            # comboboxes bin/format depuis la fiche, defaults des configs
            p = self.props
            if p is not None:
                bins = [str(b) for b in p.bins_ if 1 <= b <= 4] or ["1"]
                self.cmb_bin.configure(values=bins, state="readonly")
                self.cmb_bin.current(0)
                fmts = [NOMS_FORMATS.get(f) for f in p.imgFormats_
                        if 0 <= f <= 3]
                self.cmb_fmt.configure(values=fmts or ["RAW16"],
                                       state="readonly")
                self.cmb_fmt.current(0)
            self.cmb_flip.configure(state="readonly")
            a0 = self._attr_cache.get(0)
            a1 = self._attr_cache.get(1)
            a7 = self._attr_cache.get(7)
            a28 = self._attr_cache.get(28)
            if a0:
                self.ent_expo.delete(0, "end")
                self.ent_expo.insert(0, str(a0["defaut"]))
            if a1:
                self.ent_gain.delete(0, "end")
                self.ent_gain.insert(0, str(a1["defaut"]))
            if a7:
                self.ent_offset.delete(0, "end")
                self.ent_offset.insert(0, str(a7["defaut"]))
            if a28:
                self.ent_usb.delete(0, "end")
                self.ent_usb.insert(0, str(a28["defaut"]))
        elif genre == "fluxfini":
            pass

    # --- mode console (--console) ----------------------------------------------

    def detection_console(self):
        """Détection rapide sans fenêtre : fiche + contrôles + verdict,
        tout imprimé sur stdout, puis fermeture propre."""
        if not BANC_PRET:
            print(message_appli_trop_ancienne())
            return 2
        if self.dll is None:
            print("SDK Player One introuvable — place PlayerOneCamera.dll "
                  "dans le dossier du projet.")
            return 1
        print("DLL :", self.chemin_dll)
        n = self.dll.POAGetCameraCount()
        print("caméras détectées :", n)
        if n == 0:
            return 1
        p = _POACameraProperties()
        if self.dll.POAGetCameraProperties(0, ctypes.byref(p)) != POA_OK:
            print("fiche illisible")
            return 1
        self._fiches = [p]
        self.props = p
        print("modèle  :", p.cameraModelName.decode("utf-8", "replace"))
        print("capteur :", p.sensorModelName.decode("utf-8", "replace"),
              "·", p.maxWidth, "×", p.maxHeight, "px ·", p.bitDepth,
              "bits · pixel", f"{p.pixelSize:.2f}", "µm")
        print("couleur :", bool(p.isColorCamera), "· TEC :",
              bool(p.isHasCooler), "· USB3 :", bool(p.isUSB3Speed),
              "· ST4 :", bool(p.isHasST4Port))
        print("bins    :", [b for b in p.bins_ if 1 <= b <= 4],
              "· bin matériel :", bool(p.isSupportHardBin))
        print("formats :", [NOMS_FORMATS.get(f, str(f))
                           for f in p.imgFormats_ if 0 <= f <= 3])
        print("série   :", p.SN.decode("utf-8", "replace"))
        # ouverture + énumération complète
        self._ouvrir(0)
        self.ouverte = True
        if self.cam_id is None:
            return 1
        self._lister_controles()
        print()
        for ligne in self._verdict:
            print(ligne)
        # fermeture propre (TEC coupé, caméra fermée)
        self.flux_actif = False
        u = _POAConfigValue()
        u.intValue = 0
        self.dll.POASetConfig(self.cam_id, 18, u, 0)
        self.dll.POAStopExposure(self.cam_id)
        err = self.dll.POACloseCamera(self.cam_id)
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
        banc = BancPOA.__new__(BancPOA)
        banc.root = _Faux()
        banc.mode_console = True
        banc.dll = None
        banc.chemin_dll = None
        banc.layout = "récent"
        banc.cam_id = None
        banc.props = None
        banc.nom = ""
        banc.ouverte = False
        banc.flux_actif = False
        banc._th_flux = None
        banc._ui_q = queue.Queue()
        banc._jobs = queue.Queue()
        banc._verdict = []
        banc._attr_cache = {}
        banc._fps = 0.0
        banc._n_frames = 0
        banc._derniere_photo = None
        banc._frame_attente = None
        banc.sonde = None
        banc._preparer_dll()
        banc._log = print
        sys.exit(banc.detection_console())
    root = tk.Tk()
    banc = BancPOA(root)
    if not BANC_PRET:
        messagebox.showerror("Banc Player One — application trop ancienne",
                             message_appli_trop_ancienne())
    root.mainloop()


if __name__ == "__main__":
    main()












