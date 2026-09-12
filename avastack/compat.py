# -*- coding: utf-8 -*-
"""Compatibilite multiplateforme (Windows / Linux / macOS).

Constantes liees a l'OS, centralisees ici pour qu'aucun autre module
n'ait besoin de tester lui-meme la plateforme.
"""

import os
import sys

IS_WINDOWS = (os.name == "nt")
IS_MACOS = (sys.platform == "darwin")

# Nom de bibliotheque du SDK ZWO selon l'OS (DLL Windows, .so Linux, .dylib macOS)
ZWO_DLL_NAME = "ASICamera2.dll" if IS_WINDOWS else (
    "libASICamera2.dylib" if IS_MACOS else "libASICamera2.so")
