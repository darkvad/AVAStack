# -*- coding: utf-8 -*-
"""Panneaux de la colonne gauche extraits de `avastack/ui/app.py`.

Jalon 105a du chantier de refactoring (cf. CLAUDE.md / AVANCEMENT.md) : la
première vague, « sources » — les panneaux `files` (« Fichiers de travail et
journal »), `camera` (« Caméra »), `cadence` (« Cadence d'empilement ») et
`folder` (« Dossier surveillé »). Chaque module regroupe la construction d'un
panneau sous forme de « mixin » — une classe dont `App` hérite — dont le code
est repris VERBATIM depuis `app.py` : `self` reste l'instance `App`, donc le
comportement (et l'ordre de pose des widgets) est identique AU BIT.
"""
