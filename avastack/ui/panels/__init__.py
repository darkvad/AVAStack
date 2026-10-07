# -*- coding: utf-8 -*-
"""Panneaux de la colonne gauche extraits de `avastack/ui/app.py`.

Chantier de refactoring (cf. CLAUDE.md / AVANCEMENT.md). Première vague, jalon
105a — les panneaux « sources » : `files` (« Fichiers de travail et journal »),
`camera` (« Caméra »), `cadence` (« Cadence d'empilement ») et `folder`
(« Dossier surveillé »). Deuxième vague, jalon 105b — les panneaux
« traitement » : `compo` (« Composition multi-filtres »), `calib`
(« Calibration »), `stack` (« Empilement »), `bgnoise` (« Fond et grain ») et
`sharp` (« Netteté live »). Chaque module regroupe la construction d'un panneau
sous forme de « mixin » — une classe dont `App` hérite — dont le code est repris
VERBATIM depuis `app.py` : `self` reste l'instance `App`, donc le comportement
(et l'ordre de pose des widgets) est identique AU BIT.
"""
