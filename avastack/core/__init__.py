# -*- coding: utf-8 -*-
"""Cœur applicatif (hors interface) — paquet TYPÉ.

Jalon 106a du chantier de refactoring : le THREAD D'ACQUISITION (méthode
`_worker`, extraite de `avastack/ui/app.py`) vit dans `worker.py`, sous forme de
mixin `AcquisitionWorker` dont `App` hérite ; ses PARAMÈTRES sont décrits par
`WorkerConfig` (`config.py`). Jalon 106b : sa partie « boucle » (acquisition +
reset / re-stack) est découpée en sous-méthodes (`_worker_empiler_frame`,
`_worker_reinitialiser`, `_worker_restack`) et `WorkerConfig` est CONSOMMÉ pour
le rejet kappa-sigma. Suite du chantier (106c/106d) : découpage de « pilotage »
(roue/TEC/offset + cadence dossier) et « mesures » (astrométrie/photométrie/
SPCC).
"""
