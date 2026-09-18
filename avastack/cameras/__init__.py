# -*- coding: utf-8 -*-
"""Caméras / sources d'images pour le live stacking.

Pour ajouter une nouvelle source : créer un fichier ici, hériter de
CameraBase et implémenter open()/read()/close(), puis l'exporter dans
__init__.py (le registre sera enrichi en commit B).
"""

from .base import CameraBase
from .simulated import SimulatedCamera
from .opencv_cam import OpenCVCamera
from .zwo import ZWOASICamera
from .folder import FolderCamera
from .multifolder import MultiFolderCamera
from .qhy import QHYCamera
from .playerone import PlayerOneCamera
from .touptek import TouptekCamera
from .svbony import SVBonyCamera

# Libellés du menu déroulant de l'interface (ordre d'affichage)
SOURCES = ["Simulée (démo)",
           "Dossier surveillé (brutes FITS/PNG/TIFF…)",
           "Composition multi-dossiers (RGB/HOO/SHO/LRGB)",
           "OpenCV 0", "OpenCV 1", "ZWO ASI (SDK)", "QHY (SDK)",
           "Player One (SDK)", "Touptek/Altair (SDK)", "SVBONY (SDK)"]
