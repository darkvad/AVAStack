# -*- coding: utf-8 -*-
"""Cœur applicatif (hors interface) — paquet TYPÉ.

Jalon 106a du chantier de refactoring : le THREAD D'ACQUISITION (méthode
`_worker`, extraite de `avastack/ui/app.py`) vit dans `worker.py`, sous forme de
mixin `AcquisitionWorker` dont `App` hérite ; ses PARAMÈTRES sont décrits par
`WorkerConfig` (`config.py`). Jalon 106b : sa partie « boucle » (acquisition +
reset / re-stack) est découpée en sous-méthodes (`_worker_empiler_frame`,
`_worker_reinitialiser`, `_worker_restack`) et `WorkerConfig` est CONSOMMÉ pour
le rejet kappa-sigma. Jalon 106c : sa partie « pilotage » est découpée à son
tour (`_worker_pilotage` — roue/TEC/offset/réglages ; `_worker_cadence_dossier`
— cadence dossier). Jalon 106d : les « mesures » (astrométrie + photométrie /
SPCC) rejoignent à leur tour le mixin — méthodes de CALCUL reprises VERBATIM de
`ui/app.py` (`_astro_tour`, `_astro_aveugle`, `_photo_tour`, `_photo_canaux`,
`_source_rgb`, `_spcc_tour`, `_astro_indices_entete`, `_astro_propager_restack`)
et sous-méthode `_worker_mesures` ; l'AFFICHAGE, lui, reste dans l'interface.
"""
