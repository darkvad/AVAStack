# -*- coding: utf-8 -*-
"""Configuration du thread d'acquisition — `WorkerConfig` (TYPÉ).

Jalon 106a du chantier de refactoring. `WorkerConfig` regroupe les PARAMÈTRES que
le thread d'acquisition (`avastack/core/worker.py`) lit pour cadrer son travail,
aujourd'hui dispersés dans `App` : rejet kappa-sigma de l'empilement (méthode,
fenêtre, kappa), cadence de lecture (surveillance de dossier / composition
multi-dossiers) et instantanés thread-safe des réglages caméra (exposition, gain,
offset).

Aucun changement de comportement : ce dataclass est la DÉCLARATION typée du
« seam » qui est CONSOMMÉ depuis le jalon 106b — le rejet kappa-sigma
(`kappa` / `rejet_methode` / `rejet_fenetre`) est lu sur l'instantané dans
`_worker_empiler_frame`, pour un résultat IDENTIQUE AU BIT. Il documente
l'interface du worker et figure dans la liste blanche de `pyright`.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkerConfig:
    """Paramètres du thread d'acquisition (cf. docstring du module)."""

    # Rejet kappa-sigma de l'empilement.
    kappa: float | None
    rejet_methode: str
    rejet_fenetre: int
    # Cadence de lecture (surveillance de dossier / composition multi-dossiers).
    cadence_lecture: int
    # Instantanés thread-safe des réglages caméra (posés par le thread Tk).
    expo_ms: float
    gain_val: float
    offset: float

    @classmethod
    def depuis(cls, app: Any) -> "WorkerConfig":
        """Instantané des paramètres de travail à partir de l'hôte (`App`).

        Lecture DIRECTE sur l'instance, tolérante à l'absence (comme partout
        dans le worker) : appelée par le thread d'acquisition depuis le jalon
        106b (`_worker_empiler_frame`) — même résultat que la lecture directe
        sur `self`."""
        offset = getattr(app, "pending_offset", 0.0)
        return cls(
            kappa=getattr(app, "kappa", None),
            rejet_methode=getattr(app, "rejet_methode", "kappa"),
            rejet_fenetre=int(getattr(app, "rejet_fenetre", 8)),
            cadence_lecture=int(getattr(app, "cadence_lecture", 0)),
            expo_ms=float(getattr(app, "expo_ms", 100.0)),
            gain_val=float(getattr(app, "gain_val", 30.0)),
            offset=float(offset) if offset is not None else 0.0,
        )
