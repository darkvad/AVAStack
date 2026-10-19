# -*- coding: utf-8 -*-
"""Cadence de re-mesure (P1, lot 2) — QUAND refaire une mesure qui s'approfondit.

PROBLÈME MESURÉ (liste d'Alain du 19/10/2026, P1) : l'astrométrie, les gains
Gaia et la SPCC ne mesuraient qu'UNE fois — dès `ASTRO_MIN_FRAMES = 3`, donc au
pire moment — puis restaient `valide` : un empilement passé de 3 à 80 frames
gardait une mesure faite sur 3. Voulu : re-mesurer en s'approfondissant,
jusqu'à chaque frame en mono-dossier / 1 frame par rôle en multi.

RÈGLE (un seul endroit pour les trois tours, jamais recopiée) :
  1. la PREMIÈRE mesure part dès le seuil (`seuil`, 3 par défaut) ;
  2. une RE-MESURE part quand la profondeur a DOUBLÉ depuis la dernière mesure
     réussie (3 → 6 → 12 → 24…), ET au plus tôt `delai_s` (20 s) après elle ;
  3. un PLAFOND de re-mesures (`max_remesures`, 6) borne le coût d'une session
     — la passe finale n'y est PAS soumise ;
  4. une PASSE FINALE part à la fin de source (transition `_source_epuisee`,
     P3) si la profondeur a augmenté depuis la dernière mesure : la source ne
     grossira plus, attendre serait perdre la mesure.

CE QUI N'EST PAS ICI — LES ÉCHECS. Une tentative qui échoue a sa propre
politique (`MAX_ESSAIS` + délai/backoff, portée par `Photometrie`/`SessionSpcc`
et les tours du worker). La cadence ne compte que les mesures RÉUSSIES : mêler
les deux ferait consommer le quota d'échecs par des succès, et un empilement
qui s'approfondit épuiserait ce quota en quelques minutes.

L'ASTROMÉTRIE n'a pas de re-mesure : le WCS est résolu UNE fois puis PROPAGÉ
(jalon 56). Sa « cadence » est donc celle des ESSAIS tant qu'il n'est pas
résolu — déjà portée par `SuiviAstrometrie.peut_essayer` (doublé + backoff +
plafond). Ce module ne la duplique pas : il ne sert là qu'à PORTER LA DATE de
la mesure et à dire la prochaine échéance.

Banc : `bancs/_test_p1_cadence.py` (chemin de DÉCISION, espion, aucune mesure
réelle). Mesure du coût : `bancs/_mesure_p1_cadence.py`.
"""

import time
from typing import Any

# --- Politique (les bancs la vérifient) -------------------------------------
SEUIL_PROFONDEUR: int = 3       # même valeur que `astrometrie.ASTRO_MIN_FRAMES`
DELAI_MIN_S: float = 20.0       # entre deux mesures RÉUSSIES
MAX_REMESURES: int = 6          # re-mesures réussies d'une session (hors finale)
PASSE_FINALE: bool = True       # une dernière mesure à la fin de source
FACTEUR: float = 2.0            # la cible double à chaque mesure


class CadenceMesure:
    """Décision de re-mesure d'UNE mesure (astro, photométrie, SPCC).

    Une instance PAR mesure et PAR session : `reset()` au démarrage, à la
    remise à zéro et à chaque nouvelle demande explicite de l'utilisateur
    (case re-cochée) — sinon un `reset()` de la session voisine effacerait la
    profondeur de référence de celle-ci.

    Aucune exception ne sort : `doit_mesurer` rend toujours un couple
    (booléen, raison en clair) ; la raison est journalisée/affichée telle
    quelle, jamais devinée par l'appelant.
    """

    def __init__(self, nom: str = "mesure", seuil: int = SEUIL_PROFONDEUR,
                 delai_s: float = DELAI_MIN_S,
                 max_remesures: int = MAX_REMESURES,
                 passe_finale: bool = PASSE_FINALE) -> None:
        self.nom: str = str(nom)
        self.seuil: int = max(1, int(seuil))
        self.delai_s: float = max(0.0, float(delai_s))
        self.max_remesures: int = max(0, int(max_remesures))
        self.passe_finale: bool = bool(passe_finale)
        self.reset()

    # -- état ---------------------------------------------------------------
    def reset(self) -> None:
        """Session neuve : aucune mesure, aucune échéance."""
        self.profondeur: int = 0      # profondeur de la dernière mesure RÉUSSIE
        self.instant: float = 0.0     # monotonic de cette mesure
        self.remesures: int = 0       # mesures après la première (re-mesures)
        self.mesures: int = 0         # mesures réussies au total
        self.finales: int = 0         # dont passes finales servies

    @property
    def deja_mesure(self) -> bool:
        """Au moins une mesure réussie ?"""
        return self.mesures > 0

    def cible(self) -> int:
        """Profondeur à atteindre pour la PROCHAINE mesure.

        Sans mesure : le seuil. Sinon la profondeur de la dernière mesure
        DOUBLÉE (jamais moins que le seuil : une mesure à 3 ne doit pas
        attendre moins de 6)."""
        if not self.mesures:
            return self.seuil
        return max(self.seuil, int(self.profondeur * FACTEUR))

    # -- décision -----------------------------------------------------------
    def doit_mesurer(self, profondeur: int, maintenant: float | None = None,
                     fin_source: bool = False) -> tuple[bool, str]:
        """Faut-il (re)mesurer MAINTENANT, à cette profondeur ?

        `profondeur` = profondeur de la mesure (par rôle en composition :
        `_profondeur_spcc`), JAMAIS la somme des rôles. `fin_source` = le
        worker est passé par la TRANSITION « des frames → plus rien » (P3) ;
        ce n'est jamais un état (sur une caméra live un `read()` vide est
        normal).

        → (booléen, raison en clair). L'ordre des règles est celui du coût :
        seuil → passe finale → plafond → doublement → délai.
        """
        try:
            n = int(profondeur)
        except (TypeError, ValueError):
            return False, f"profondeur inutilisable ({profondeur!r})"
        if n < self.seuil:
            return False, (f"empilement trop court ({n}/{self.seuil} frames)")
        t = time.monotonic() if maintenant is None else float(maintenant)
        if not self.mesures:
            return True, f"première mesure ({n} frames)"
        # La passe finale PASSE AVANT le plafond et le délai : la source est
        # épuisée, il n'y aura plus jamais d'occasion (et rien ne sert
        # d'attendre un empilement qui ne grossira plus).
        if fin_source and self.passe_finale and n > self.profondeur:
            return True, (f"passe finale — source épuisée ({n} frames, "
                          f"dernière mesure sur {self.profondeur})")
        if self.remesures >= self.max_remesures:
            return False, (f"plafond de {self.max_remesures} re-mesures "
                           f"atteint (dernière sur {self.profondeur} frames)")
        cible = self.cible()
        if n < cible:
            return False, (f"prochaine mesure à {cible} frames "
                           f"(dernière sur {self.profondeur})")
        reste = self.delai_s - (t - self.instant)
        if reste > 0:
            return False, (f"profondeur {n} atteinte, délai en cours "
                           f"({reste:.0f} s)")
        return True, (f"profondeur doublée ({self.profondeur} → {n} frames)")

    def noter_mesure(self, profondeur: int,
                     maintenant: float | None = None) -> None:
        """Enregistre une mesure RÉUSSIE (jamais un échec)."""
        try:
            n = int(profondeur)
        except (TypeError, ValueError):
            return
        if self.mesures:            # la première n'est pas une « re-mesure »
            self.remesures += 1
        self.mesures += 1
        self.profondeur = max(0, n)
        self.instant = (time.monotonic() if maintenant is None
                        else float(maintenant))

    def noter_passe_finale(self) -> None:
        """Compteur de passes finales servies (diagnostic, jamais une règle)."""
        self.finales += 1

    # -- texte d'état -------------------------------------------------------
    def prochaine(self, profondeur_courante: int | None = None) -> str:
        """Échéance en clair pour la ligne d'état (« prochaine mesure à … »).

        Rend "" quand il n'y a rien à dire de plus que la mesure elle-même
        (plafond atteint, aucune source plus profonde à attendre)."""
        if not self.mesures:
            return f"première mesure à {self.seuil} frames"
        if self.remesures >= self.max_remesures:
            return ""
        cible = self.cible()
        if profondeur_courante is not None and int(profondeur_courante) >= cible:
            # La profondeur est là, seul le DELAI retient encore la mesure.
            return f"re-mesure due à {cible} frames (délai en cours)"
        return f"prochaine mesure à {cible} frames"

    def resume(self) -> dict[str, Any]:
        """État sérialisable (journal, bancs, fiche de diagnostic)."""
        return {
            "nom": self.nom,
            "profondeur": int(self.profondeur),
            "mesures": int(self.mesures),
            "remesures": int(self.remesures),
            "finales": int(self.finales),
            "cible": int(self.cible()),
            "plafond": int(self.max_remesures),
        }

    def __repr__(self) -> str:      # utile en console de diagnostic
        r = self.resume()
        return (f"CadenceMesure({r['nom']}: {r['profondeur']} frames, "
                f"{r['mesures']} mesure(s), cible {r['cible']})")


def suffixe_etat(cadence: Any, profondeur_courante: int | None = None) -> str:
    """Suffixe de ligne d'état pour une cadence ("" si rien à ajouter).

    Utilisé par les lignes dédiées de l'UI (`_maj_*_etat`) : l'état dit la
    profondeur MESURÉE et la prochaine échéance, sans dupliquer le texte de la
    mesure elle-même. `cadence` peut être None (bancs anciens) → "".
    """
    if cadence is None or not getattr(cadence, "deja_mesure", False):
        return ""
    txt = cadence.prochaine(profondeur_courante)
    return txt or ""
