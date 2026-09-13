# -*- coding: utf-8 -*-
"""Package AVAStack — live stacking (empilement temps réel).

Structure (refactoring v2.0.0, depuis le fichier unique AstroLiveStack.py /
AVAStack.py) :
  avastack.compat       — constantes multiplateforme (Windows/Linux/macOS)
  avastack.config       — persistance config.json
  avastack.images       — E/S image, débayerisation, utilitaires outils externes
  avastack.cameras      — sources d'images (simulée, dossier, OpenCV, ZWO)
  avastack.processing   — calibration, alignement, empilement, affichage
  avastack.external     — détection + enchaînement des outils CLI (GraXpert/BXT)
  avastack.ui           — interface Tkinter
Le point d'entrée reste AVAStack.py à la racine (python AVAStack.py),
ou python -m avastack.
"""

AVASTACK_VERSION = "2.1.0"

# --- Changelog (entrée la plus récente en premier) --------------------------
# v2.1.0 : NOUVELLES CAMERAS QHYCCD + PLAYER ONE (demande Alain, il possede
#          les deux ; Touptek/Altair + SVBONY suivront) :
#          - avastack/cameras/qhy.py : via le paquet PyPI officiel `qhyccd`
#            (SDK natif inclus, `pip install qhyccd`) — NOUVELLE DEPENDANCE
#            OPTIONNELLE (ajoutee en commentaire dans requirements.txt) ;
#          - avastack/cameras/playerone.py : ctypes sur le SDK officiel
#            PlayerOneCamera.dll (telecharge sur player-one-astronomy.com),
#            derive du wrapper pyPOACamera.py (poa_view, Filipe Maia,
#            BSD-2-Clause) ;
#          - avastack/cameras/sdk_loader.py : chargement des SDK natifs
#            (variable d'env dediee AVASTACK_<MARQUE>_DIR, dossier projet,
#            PATH) — les SDK binaires proprietaires restent HORS du depot.
#          - Une seule classe par marque : N'IMPORTE QUELLE camera de la
#            marque (fiche lue sur la camera, rien en dur). Mono → 2D
#            (RAW16), couleur → RGB24 debayerise par la camera.
#          Sources 'QHY (SDK)' et 'Player One (SDK)' ajoutees au menu.
# v2.0.0 : REFACTORING MODULAIRE (demande Alain, préparation aux futures
#          fonctionnalités : nouvelles caméras à driver, nouveaux outils…) :
#          le fichier unique (~1500 lignes) est déplacé dans le package
#          avastack/ découpé par thème (cameras/, processing/, external/,
#          ui/). COMPORTEMENT IDENTIQUE — déménagement, pas réécriture.
#          Point d'entrée : AVAStack.py (lanceur fin) ou python -m avastack.
#          veralux_core_headless.py (tiers GPL-3.0) reste à la racine, tel quel.
# v1.1.0 : COMPATIBILITE MULTIPLATEFORME (demande Alain : Windows/Linux/macOS).
#          - Chemin Windows en dur de BlurXTerminator supprime : detection
#            automatique de GraXpert et rc-astro (variable d'environnement
#            AVASTACK_GRAXPERT / AVASTACK_RC_ASTRO, puis PATH, puis
#            emplacements d'installation courants selon l'OS).
#          - PERSISTANCE des reglages dans config.json (emplacement selon les
#            conventions de l'OS : %APPDATA%\AVAStack, ~/Library/Application
#            Support/AVAStack, ~/.config/AVAStack) : commandes des outils
#            externes (choisies via le bouton « ... » ou detectees), dossier
#            surveille, CFA, cases GraXpert/BXT, reglages d'etirement
#            (sigk/target/gamma/saturation). Plus rien a reconfigurer au
#            lancement suivant.
#          - Bibliotheque SDK ZWO selon l'OS (ASICamera2.dll /
#            libASICamera2.so / libASICamera2.dylib).
#          - Filtre de selection d'executable adapte a l'OS (bouton « ... »).
#          Aucune nouvelle dependance Python (json/sys/shutil : stdlib).
# v1.0.0 : RENOMMAGE (demande Alain) : AstroLiveStack → AVAStack (éviter la
#          confusion avec ALS - Astro Live Stacker). Fichier renommé en
#          AVAStack.py, titre de fenêtre, préfixe des dossiers temporaires
#          (avastack_), variable AVASTACK_VERSION créée (n'existait pas
#          auparavant malgré la convention CLAUDE.md).
