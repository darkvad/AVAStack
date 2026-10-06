# -*- coding: utf-8 -*-
"""MESURES BORNÉES : ne jamais attendre indéfiniment un disque (ni un réseau).

POURQUOI CE MODULE (constat RÉEL d'Alain, 27/09/2026, machine Linux) :

    « cette version ne se lance pas » — sans AUCUN message ni ligne de journal.

MESURE : ses dossiers de couches R/G/B sont sur un **NAS** (et dans
config.json) ; or `nftables` filtre ce NAS, et un `stat`/`listdir` sur un
montage réseau **injoignable ATTEND LE MONTAGE indéfiniment** (autofs n'a pas
de délai par défaut). L'inspection faite AVANT l'affichage bloquait donc
l'application — et comme la ligne de journal était écrite APRÈS la mesure de
l'environnement, elle n'était jamais écrite : panne totale, totale muette.

Règle qui en découle (et que ce module applique) : **une mesure de disque ne
doit JAMAIS pouvoir empêcher l'application de s'ouvrir.** Tout ce qui touche le
disque au démarrage est exécuté dans un fil (thread) DÉMON, avec un délai
maximal ; ce qui n'a pas répondu à temps est ABANDONNÉ et DIT (l'appelant
affiche « mesure non aboutie ») au lieu d'attendre.

Le fil est un démon : si l'appel système reste bloqué dans le noyau, il ne
retient pas la sortie du programme.
"""

import threading
from typing import Any, Callable, TypeVar

DELAI_DEFAUT: float = 5.0

# `borne` rend EXACTEMENT ce que rend `fn` (ou `defaut`) : le type de retour
# est donc lié à celui de `fn` (TypeVar).
_T = TypeVar("_T")


def borne(fn: Callable[[], _T], defaut: _T | None = None,
          delai_s: float = DELAI_DEFAUT) -> tuple[_T | None, bool]:
    """Exécute `fn()` dans un fil démon et rend `(valeur, abouti)`.

    - `abouti` vaut True si `fn` a rendu la main DANS le délai — y compris en
      levant : on rend alors `defaut`, mais l'appelant SAIT que ça a répondu (et
      c'est lui qui journalise la cause) ;
    - au-delà du délai, on rend `(defaut, False)` : le fil poursuit sa vie en
      démon et l'application, elle, n'attend plus.

    Aucune exception ne remonte jamais : c'est une mesure, pas une action."""
    boite: dict[str, Any] = {"valeur": defaut, "fini": [False]}

    def _travail():
        try:
            boite["valeur"] = fn()
        except Exception:
            pass                          # la cause appartient à l'appelant
        finally:
            boite["fini"][0] = True

    fil = threading.Thread(target=_travail, daemon=True, name="mesure-bornee")
    fil.start()
    fil.join(max(0.05, float(delai_s)))
    return boite["valeur"], boite["fini"][0]
