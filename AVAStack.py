#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AVAStack — live stacking (empilement temps réel)
================================================
Point d'entrée de l'application : le code vit dans le package `avastack/`
(découpé par thème, cf. avastack/__init__.py pour la carte et le changelog).

Lancement :  python AVAStack.py   (ou : python -m avastack)

Dépendances : cf. requirements.txt (numpy, opencv-python, pillow ; optionnels :
astropy pour FITS, zwoasi + SDK ASI pour les caméras ZWO).

Test sans matériel : source « Simulée (démo) » → Démarrer.
Test en dossier : choisir le dossier, éventuellement déposer une brute dedans → Démarrer.
"""

import avastack
from avastack.ui.app import main

if __name__ == "__main__":
    print(f"AVAStack v{avastack.AVASTACK_VERSION}")
    main()
