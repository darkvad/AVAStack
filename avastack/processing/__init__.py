# -*- coding: utf-8 -*-
"""Traitement : calibration, alignement, empilement, affichage temps réel.

Ré-exports : la surface publique historique (`Calibrator`, `StarAligner`,
`LiveStacker`, `DisplayProcessor`, `SuiviAstro` et les fonctions d'annotation)
est offerte pour compatibilité avec `avastack.ui.app`. `__all__` les déclare
(comme `catalogues/__init__.py`) → ruff reconnaît ces ré-exports et n'y voit
plus des imports inutilisés.
"""

from .calibration import Calibrator
from .alignment import StarAligner
from .stacking import LiveStacker
from .display import DisplayProcessor
from .astrometrie import SuiviAstrometrie as SuiviAstro
from .annotations import (overlay_objets_celebres, overlay_etoiles_brillantes,
                          generer_image_annotee, WcsEchelle)

__all__ = [
    "Calibrator", "StarAligner", "LiveStacker", "DisplayProcessor",
    "SuiviAstro", "overlay_objets_celebres", "overlay_etoiles_brillantes",
    "generer_image_annotee", "WcsEchelle",
]
