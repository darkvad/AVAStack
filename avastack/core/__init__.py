# -*- coding: utf-8 -*-
"""Cœur applicatif (hors interface) — paquet TYPÉ.

Jalon 106a du chantier de refactoring : le THREAD D'ACQUISITION (méthode
`_worker`, extraite de `avastack/ui/app.py`) vit dans `worker.py`, sous forme de
mixin `AcquisitionWorker` dont `App` hérite ; ses PARAMÈTRES sont décrits par
`WorkerConfig` (`config.py`). Suite du chantier (106b/106c/106d) : découpage de
la boucle en « boucle » (acquisition + reset/re-stack), « pilotage »
(roue/TEC/offset + cadence dossier) et « mesures » (astrométrie/photométrie/
SPCC).
"""
