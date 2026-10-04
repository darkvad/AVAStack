# -*- coding: utf-8 -*-
"""Traitement : calibration, alignement, empilement, affichage temps réel."""

from .calibration import Calibrator
from .alignment import StarAligner
from .stacking import LiveStacker
from .display import DisplayProcessor
from .astrometrie import SuiviAstrometrie as SuiviAstro
from .annotations import (overlay_objets_celebres, overlay_etoiles_brillantes,
                          generer_image_annotee)
