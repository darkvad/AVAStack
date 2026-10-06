# -*- coding: utf-8 -*-
"""Stubs de typage pour le paquet `zwoasi` (caméras ZWO ASI) — jalon 100.

`zwoasi` (pur Python) n'embarque pas d'annotations et n'est pas installé sur
toutes les machines (dépendance OPTIONNELLE, cf. requirements.txt). Ces stubs
sont lus par `pyright` via `stubPath = avastack/stubs` (pyproject.toml) : ils
décrivent la surface RÉELLEMENT utilisée par `avastack/cameras/zwo.py`, sans
prétendre couvrir tout le SDK. Fichier de DÉVELOPPEMENT uniquement — jamais
embarqué dans l'application, ne change AUCUN comportement.
"""

from typing import Any

import numpy as np

# --- Fonctions de module -----------------------------------------------------

def init(library_path: str = ...) -> None:
    """Charge la bibliothèque native du SDK ASI (ASICamera2.dll/.so/.dylib)."""
    ...

def get_num_cameras() -> int:
    """Nombre de caméras ASI connectées."""
    ...

# --- Constantes du SDK (ASI_CONTROL_TYPE / ASI_IMG_TYPE) utilisées ----------

ASI_FALSE: int
ASI_TRUE: int
ASI_BANDWIDTHOVERLOAD: int
ASI_EXPOSURE: int
ASI_GAIN: int
ASI_HIGH_SPEED_MODE: int
ASI_RGB24: int

# --- Classe Camera ----------------------------------------------------------

class Camera:
    """Une caméra ASI OUVERTE (index = position dans l'énumération)."""

    def __init__(self, camera_id: int) -> None: ...
    def open(self) -> None: ...
    def close(self) -> None: ...
    def set_control_value(self, control_type: int, value: int,
                          auto: bool = ...) -> int: ...
    def get_control_value(self, control_type: int) -> Any: ...
    def get_roi_format(self) -> Any: ...
    def set_roi_format(self, width: int, height: int, bins: int,
                       image_type: int) -> None: ...
    def start_video_capture(self) -> None: ...
    def stop_video_capture(self) -> None: ...
    def capture_video_frame(self, timeout: int = ...) -> np.ndarray: ...
