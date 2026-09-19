# -*- coding: utf-8 -*-
"""Caméras QHYCCD via le paquet PyPI `qhyccd`.

Le paquet `qhyccd` (Rust/PyO3, MIT/Apache-2.0) embarque le SDK natif
QHYCCD pour Windows et Linux — rien d'autre à installer :
    pip install qhyccd
Une seule classe gère N'IMPORTE QUELLE caméra QHY branchée (Minicam8M,
QHY268, QHY5III…) : les caractéristiques (résolution, mono/couleur) sont
lues sur la caméra elle-même, jamais codées en dur.

CONSTAT RÉEL (Alain, 1er test Minicam8M, 19/09/2026) : l'appel explicite
de cam.open() APRÈS le constructeur qhyccd.Camera(cid) CRASHAIT
L'APPLICATION sans message — le CONSTRUCTEUR ouvre DÉJÀ la caméra
(vérifié sans matériel : RuntimeError « Failed to open camera: … » sur un
id inexistant) et la double ouverture du handle USB produit un segfault
natif qu'aucun `except` Python ne rattrape. La séquence suit donc la doc
officielle du paquet (README wheel 0.1.3), qui n'appelle JAMAIS open().

Frames : numpy 2D (H, W) mono en RAW8 OU RAW16 selon le mode du SDK —
la normalisation tient compte du dtype réel. Une QHY COULEUR (bayer brut
2D) serait débayerisable via avastack.images._debayer (à activer le jour
d'un test réel ; la Minicam8M d'Alain est mono).

Diagnostic : chaque étape d'open()/close() est tracée dans
avastack_qhy_debug.log (dossier temp) — un crash natif n'affiche rien,
le log identifie la DERNIÈRE étape réussie.
"""

import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

from .base import CameraBase, FILTRES_ROUE
from .sdk_loader import RACINE_PROJET

FICHIER_TRACE = os.path.join(tempfile.gettempdir(), "avastack_qhy_debug.log")
# CREATE_NO_WINDOW (Windows) : l'enfant ne doit pas faire clignoter une
# console (l'application tourne normalement via pythonw, sans console).
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# --- Contrôles SDK (ids d'après l'enum OFFICIEL, crate qhyccd-rs) ---------
# Vérifiés en réel sur la MiniCam8M (banc + relevés d'Alain, 19/09/2026) :
# la roue INTÉGRÉE se pilote par les contrôles (aucune API « filter wheel »
# dans le binding) ; le refroidissement aussi (aucune méthode « cooler »).
CTRL_CUR_TEMP = 14      # CurTemp    : température capteur LUE (°C)
CTRL_CUR_PWM = 15       # CurPWM     : puissance TEC courante (0-255)
CTRL_MANUAL_PWM = 16    # ManualPWM  : PWM manuel 0-255 (bascule le SDK en
                        #             mode manuel — c'est l'« arrêt » du TEC)
CTRL_CFW_PORT = 17      # CfwPort    : position de la roue, ASCII → 48 + n
                        #             (relevé réel : 49 sur le filtre 1 ;
                        #             ctrl 44 « CfwSlotsNum » est INDISPO en
                        #             réel → la disponibilité se teste sur 17)
CTRL_CONSIGNE = 18      # Cooler     : consigne de régulation (°C, mode auto)
VALEUR_ERREUR = 4294967295.0   # sentinelle d'erreur du SDK (0xFFFFFFFF)


def _tracer(message):
    """Trace d'étapes QHY (diagnostic de crash natif) — append + flush."""
    try:
        with open(FICHIER_TRACE, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%H:%M:%S] ") + message + "\n")
    except Exception:
        pass        # la trace ne doit JAMAIS gêner l'acquisition


# État global du SDK natif QHYCCD : init_sdk() ne doit PAS être rappelé
# (constat du banc, 19/09/2026 : deux initialisations dans le même process
# = suspect n°1 du crash « la fenêtre se ferme direct »).
_SDK_PRET = False


def _initialiser_sdk():
    """Initialise le SDK natif UNE SEULE FOIS par process.

    → True si c'est CET appel qui vient de l'initialiser, False s'il était
    déjà prêt (appel ignoré).

    Le SDK QHYCCD garde un état GLOBAL par process : un second init_sdk()
    sans ReleaseQHYCCDResource entre les deux peut laisser le handle de la
    caméra dans un état incohérent, et begin_live()/get_live_frame() plantent
    alors en NATIF (fenêtre fermée sans message, aucun `except` Python ne
    rattrape). Le banc a révélé exactement cette divergence (19/09/2026) :
    « Démarrer » SANS détection préalable appelait QHYCamera.lister()
    (init #1 + scan) PUIS open() (init #2 + scan) — deux initialisations —
    alors que le pas-à-pas, lancé APRÈS le bouton « Détecter », n'en faisait
    qu'une seule et fonctionnait.
    """
    global _SDK_PRET
    if _SDK_PRET:
        return False
    import qhyccd
    qhyccd.init_sdk()
    _SDK_PRET = True
    return True


def lister_via_sous_processus(timeout_s=25):
    """Scan QHY DANS UN SOUS-PROCESSUS isolé → (ids, None) ou (None, message).

    Isolation : le SDK natif est du code externe — s'il segfaulte au scan,
    seul l'enfant meurt et la fonction renvoie un message clair (un scan
    in-process tuerait TOUTE l'application). Le chemin racine est transmis
    via sys.argv, JAMAIS interpolé dans le code (un chemin d'installation
    peut contenir quotes/apostrophes).
    """
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); "
            "from avastack.cameras.qhy import QHYCamera; "
            "print(json.dumps(QHYCamera.lister()))")
    try:
        r = subprocess.run([sys.executable, "-c", code, RACINE_PROJET],
                           capture_output=True, text=True,
                           timeout=timeout_s,
                           creationflags=_CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return None, (f"le scan n'a pas répondu en {timeout_s} s "
                      f"(trace : {FICHIER_TRACE})")
    if r.returncode != 0:
        lignes = (r.stderr or "").strip().splitlines()
        detail = lignes[-1] if lignes else f"code retour {r.returncode}"
        return None, (f"le SDK a planté pendant le scan ({detail}) "
                      f"— trace : {FICHIER_TRACE}")
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), None
    except Exception:
        return None, "sortie inattendue du scan : " + (r.stdout or "")[:200]


class QHYCamera(CameraBase):
    """Une caméra QHYCCD connectée (index = position dans le scan USB)."""

    # --- énumération (appelée par le registre / l'UI) ---------------------
    @staticmethod
    def lister():
        """→ liste des noms des caméras QHY branchées (sans les ouvrir)."""
        try:
            import qhyccd
            _initialiser_sdk()
            return list(qhyccd.scan_cameras())
        except Exception:
            return []          # paquet absent ou SDK incompatible → pas de QHY

    # --- cycle de vie -----------------------------------------------------
    def __init__(self, camera_id="", index=0):
        self.camera_id = camera_id
        self.index = index
        self.name = f"QHY {camera_id}" if camera_id else f"QHY #{index}"
        self.cam = None

    def open(self, roi=None):
        """Ouvre la caméra et démarre le flux live.

        roi : (largeur, hauteur) imposée AVANT begin_live, ou None pour
        essayer les tailles candidates (« 3840×2160 » = pleine définition
        IMX585 de la MiniCam8M en premier). Une ROI REFUSÉE par le SDK n'est
        pas fatale ; en revanche, si AUCUNE taille n'est acceptée, on lève une
        erreur Python CLAIRE au lieu d'appeler begin_live() : sans résolution
        posée, begin_live/get_live_frame plantent en natif (fenêtre fermée
        sans message — aucun `except` ne rattrape un segfault).
        """
        try:
            import qhyccd
        except ImportError:
            raise RuntimeError("SDK QHY manquant : pip install qhyccd")
        _tracer(f"--- open() : id={self.camera_id!r} index={self.index} "
                f"roi={roi!r}")
        if _initialiser_sdk():
            _tracer("init_sdk OK (1re initialisation du process)")
        else:
            _tracer("init_sdk DÉJÀ fait — ré-initialisation ÉVITÉE "
                    "(état global du SDK)")
        ids = list(qhyccd.scan_cameras())
        _tracer(f"scan_cameras -> {ids}")
        if not ids:
            raise RuntimeError("Aucune caméra QHY détectée (scan USB vide)")
        # camera_id fourni par l'UI (id exact du scan), sinon l'index
        cid = self.camera_id if self.camera_id in ids else ids[self.index]
        # Le CONSTRUCTEUR ouvre la caméra (doc officielle du paquet ; vérifié
        # en réel : RuntimeError "Failed to open camera" sur id inexistant).
        # NE PAS appeler open() ensuite — double ouverture = segfault natif
        # (constat Alain 19/09/2026 : l'application se fermait sans message).
        self.cam = qhyccd.Camera(cid)
        self.name = f"QHY {cid}"
        _tracer(f"Camera({cid!r}) ouverte (constructeur)")
        self.cam.set_stream_mode(1)          # 1 = live (streaming continu)
        _tracer("set_stream_mode(1) OK")
        self.cam.init()                      # init matériel + registres
        _tracer("init() OK")
        self.cam.set_bin_mode(1, 1)          # 1x1 (séquence officielle)
        _tracer("set_bin_mode(1,1) OK")
        # ROI : SANS résolution posée, begin_live/get_live_frame segfaultent
        # (constat réel 19/09/2026 — la fenêtre mourait sans message). Une
        # ROI imposée (paramètre ou banc) est essayée EN PREMIER, puis les
        # tailles candidates. 3840×2160 = pleine définition IMX585 de la
        # MiniCam8M (la fiche 3856×2180 de Player One est REFUSÉE par le SDK
        # QHY). Une taille refusée (erreur 0xFFFFFFFF) n'est PAS fatale.
        tailles = []
        for t in ([(int(roi[0]), int(roi[1]))] if roi else []) + [
                (3840, 2160), (3856, 2180), (3848, 2168), (1920, 1080)]:
            if t not in tailles:
                tailles.append(t)
        posee = False
        for w, h in tailles:
            try:
                self.cam.set_resolution(0, 0, w, h)
                _tracer(f"set_resolution(0,0,{w},{h}) OK — ROI posée")
                posee = True
                break
            except Exception as e:
                _tracer(f"set_resolution(0,0,{w},{h}) refusée ({e})")
        if not posee:
            # On NE va PAS plus loin : begin_live() sans ROI = crash natif.
            # self.cam remis à None pour que l'appelant (l'UI) n'essaie pas
            # de lire un handle inutilisable ; le handle reste ouvert jusqu'à
            # la fermeture de l'application (la refermer ici serait un appel
            # natif de plus, non testé, dans un chemin déjà en échec).
            self.cam = None
            raise RuntimeError(
                "aucune ROI acceptée par le SDK (essayées : "
                + ", ".join(f"{w}×{h}" for w, h in tailles)
                + ") — le SDK QHY exige une résolution posée AVANT "
                "begin_live, sinon il plante. Relance l'application.\n"
                f"Trace : {FICHIER_TRACE}")
        self.cam.begin_live()
        _tracer("begin_live() OK")

    def read(self):
        """→ frame numpy 2D mono (float32 [0..1]) ou None."""
        if self.cam is None:
            return None
        try:
            frame = self.cam.get_live_frame()
        except Exception:
            return None
        if frame is None:
            return None
        # np.array(float32) COPIE : indispensable — le ndarray du binding est
        # zero-copy côté Rust et son buffer peut être réutilisé à la frame
        # suivante. La normalisation tient compte du dtype RÉEL (RAW8 → /255,
        # RAW16 → /65535 : un /65535 en dur aurait rendu une frame RAW8 noire).
        a = np.asarray(frame)
        if a.ndim != 2 or a.size == 0:
            return None
        plein = 255.0 if a.dtype == np.uint8 else 65535.0
        return np.array(a, dtype=np.float32) / plein

    def apply_settings(self, exposure_ms, gain):
        if self.cam is None:
            return
        try:
            self.cam.set_exposure(int(exposure_ms * 1000))   # µs
            self.cam.set_gain(float(gain))
        except Exception as e:
            _tracer(f"apply_settings ignoré ({e})")   # hors limites firmware

    # --- roue à filtres intégrée (contrôles 17/44 du SDK) ----------------
    def roue_disponible(self):
        """True si le contrôle de position (17) est disponible.

        Relevé réel (Alain, 19/09/2026) : ctrl 44 « CfwSlotsNum » répond
        INDISPO alors que la roue FONCTIONNE (17 accepte les écritures et la
        roue tourne) → c'est 17, et lui seul, qui fait foi.
        """
        if self.cam is None:
            return False
        try:
            dispo = bool(self.cam.is_control_available(CTRL_CFW_PORT))
        except Exception as e:
            _tracer(f"roue_disponible : {e}")
            return False
        _tracer(f"roue_disponible : ctrl {CTRL_CFW_PORT} → {dispo}")
        return dispo

    def position_filtre(self):
        """→ position courante (0 = cran noir), None si inconnue.

        Le contrôle renvoie un code ASCII : 48 + n (relevé réel : 49 sur le
        filtre 1). Toute autre valeur (sentinelle d'erreur, code < 48) est
        « position inconnue » — jamais une erreur : la roue peut être en
        rotation, ou le logiciel lancé avant le retour au home de la roue.
        """
        if self.cam is None:
            return None
        try:
            v = float(self.cam.get_param(CTRL_CFW_PORT))
        except Exception as e:
            _tracer(f"position_filtre : {e}")
            return None
        if v == VALEUR_ERREUR:
            return None
        n = int(v) - 48
        return n if n >= 0 else None

    def choisir_filtre(self, n, timeout_s=25.0, attente_s=0.3):
        """Déplace la roue vers la position n (0 = cran noir) et attend.

        Écriture de 48 + n dans le contrôle 17, puis relecture EN BOUCLE
        jusqu'à la position cible — la position n'est fiable qu'une fois la
        rotation terminée (doc QHY) —, timeout 25 s (valeur conseillée par
        la doc). BLOQUANT : à appeler UNIQUEMENT depuis le thread de travail.
        Lève une RuntimeError claire si la rotation n'est pas confirmée.
        """
        if self.cam is None:
            raise RuntimeError("caméra fermée — la roue n'est pas accessible")
        n = int(n)
        cible = 48 + n
        _tracer(f"choisir_filtre({n}) : set_param({CTRL_CFW_PORT}, {cible})")
        self.cam.set_param(CTRL_CFW_PORT, cible)
        pos = None
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout_s:
            time.sleep(attente_s)
            pos = self.position_filtre()
            _tracer(f"choisir_filtre({n}) : relecture → {pos}")
            if pos == n:
                return n
        raise RuntimeError(
            f"la roue n'a pas confirmé la position {n} "
            f"({FILTRES_ROUE[n] if 0 <= n < len(FILTRES_ROUE) else '?'}) en "
            f"{timeout_s:.0f} s — dernière relecture : {pos}")

    # --- refroidissement TEC (contrôles 14/15/16/18 du SDK) --------------
    def consigne_refroidissement(self, temp_c):
        """Régulation automatique à `temp_c` °C (set_param du contrôle 18)."""
        if self.cam is None:
            raise RuntimeError("caméra fermée — TEC inaccessible")
        self.cam.set_param(CTRL_CONSIGNE, float(temp_c))
        _tracer(f"consigne_refroidissement : set_param(18, {float(temp_c):g})")

    def lire_refroidissement(self):
        """→ (temp capteur °C, PWM 0-255, consigne °C), None si indisponible.

        Une sentinelle d'erreur (0xFFFFFFFF) sur l'une des trois lectures
        signifie « refroidissement absent/inactif » → None, jamais d'erreur.
        """
        if self.cam is None:
            return None
        vals = []
        for cid in (CTRL_CUR_TEMP, CTRL_CUR_PWM, CTRL_CONSIGNE):
            try:
                v = float(self.cam.get_param(cid))
            except Exception as e:
                _tracer(f"lire_refroidissement : ctrl {cid} : {e}")
                return None
            if v == VALEUR_ERREUR:
                return None
            vals.append(v)
        return tuple(vals)

    def arreter_refroidissement(self):
        """Coupe le TEC : PWM MANUEL (contrôle 16) à 0.

        Le passage en mode manuel (toute écriture dans 16) sort le SDK du
        mode auto — PWM 0 = plus de refroidissement (mais la caméra reste
        ouverte et le flux continue)."""
        if self.cam is None:
            raise RuntimeError("caméra fermée — TEC inaccessible")
        self.cam.set_param(CTRL_MANUAL_PWM, 0.0)
        _tracer("arreter_refroidissement : set_param(16, 0) — TEC coupé")

    def close(self):
        if self.cam is not None:
            try:
                self.cam.stop_live()
                self.cam.close()
                _tracer("close OK")
            except Exception as e:
                _tracer(f"close : {e}")
            finally:
                self.cam = None
