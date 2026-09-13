# -*- coding: utf-8 -*-
"""Caméras QHYCCD via le paquet PyPI officiel `qhyccd`.

Le paquet `qhyccd` (Rust/PyO3, MIT/Apache-2.0) embarque le SDK natif QHYCCD
pour Windows et Linux — rien d'autre à installer :
    pip install qhyccd
Une seule classe gère N'IMPORTE QUELLE caméra QHY branchée (Minicam8M,
QHY268, QHY5III…) : les caractéristiques (résolution, mono/couleur) sont
lues sur la caméra elle-même, jamais codées en dur.

Frames : le SDK renvoie un numpy 2D (H, W) mono (RAW8/RAW16 → [0..1] par
la normalisation de CameraBase via le pipeline d'affichage). Le cas d'une
caméra COULEUR QHY (bayer brut 2D) serait débayerisable via
avastack.images._debayer — à activer le jour où on teste une QHY couleur
réelle (Minicam8M d'Alain est mono).
"""

import numpy as np

from .base import CameraBase


class QHYCamera(CameraBase):
    """Une caméra QHYCCD connectée (index = position dans le scan USB)."""

    # --- énumération (appelée par le registre / l'UI) ---------------------
    @staticmethod
    def lister():
        """→ liste des noms des caméras QHY branchées (sans les ouvrir)."""
        try:
            import qhyccd
            qhyccd.init_sdk()
            return list(qhyccd.scan_cameras())
        except Exception:
            return []          # paquet absent ou SDK incompatible → pas de QHY

    # --- cycle de vie -----------------------------------------------------
    def __init__(self, camera_id="", index=0):
        self.camera_id = camera_id
        self.index = index
        self.name = f"QHY {camera_id}" if camera_id else f"QHY #{index}"
        self.cam = None

    def open(self):
        try:
            import qhyccd
        except ImportError:
            raise RuntimeError("SDK manquant :  pip install qhyccd")
        qhyccd.init_sdk()
        ids = qhyccd.scan_cameras()
        if not ids:
            raise RuntimeError("Aucune caméra QHY détectée")
        # camera_id fourni par l'UI (nom exact), sinon l'index du scan
        cid = self.camera_id if self.camera_id in ids else ids[self.index]
        self.cam = qhyccd.Camera(cid)
        self.cam.open()
        self.cam.set_stream_mode(1)          # 1 = live (streaming continu)
        self.cam.init()
        self.name = f"QHY {cid}"
        # ROI par défaut de la caméra (pleine capteur) : laissée telle quelle,
        # le SDK dimensionne lui-même son buffer à l'init.
        self.cam.begin_live()

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
        return np.asarray(frame).astype(np.float32) / 65535.0  # RAW16 → [0..1]

    def apply_settings(self, exposure_ms, gain):
        if self.cam is None:
            return
        try:
            self.cam.set_exposure(int(exposure_ms * 1000))   # µs
            self.cam.set_gain(float(gain))
        except Exception:
            pass        # certaines valeurs hors limites firmware → ignorées

    def close(self):
        if self.cam is not None:
            try:
                self.cam.stop_live()
                self.cam.close()
            except Exception:
                pass
            finally:
                self.cam = None
