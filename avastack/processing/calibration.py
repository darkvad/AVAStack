# -*- coding: utf-8 -*-
"""Calibration dark/flat appliquée à chaque frame entrante.

Jalon 53 (demande d'Alain) : en mode composition (multi-filtres), chaque
rôle peut avoir SON dark et SON flat — indépendamment l'un de l'autre
(ex. un dark par filtre et un flat unique). Un rôle sans master dédié
retombe sur le dark/flat UNIQUE (compatibilité mono inchangée).

v2.98.7 : les CHEMINS des maîtres sont PERSISTÉS dans `config.json` (défaut
corrigé : ils ne l'étaient pas, d'où une re-sélection à chaque session). Les
deux fonctions qui font l'aller-retour (`cles_persistees` /
`lire_cles_persistees`) sont PURES et vivent ici, à côté de la façon dont un
maître est identifié (« unique » ou un rôle) : elles se testent sans écran.
"""

from typing import Any, Mapping

import numpy as np

from ..images import load_image

# Clés de persistance des maîtres (v2.98.7). Une clé par CIBLE :
#   `calib_dark_unique` / `calib_flat_unique`      → maître « toutes couches »
#   `calib_dark_<rôle>` / `calib_flat_<rôle>`      → maître de la couche (jalon 53)
PREFIXE_DARK = "calib_dark"
PREFIXE_FLAT = "calib_flat"
CIBLE_UNIQUE = "unique"


class Calibrator:
    def __init__(self) -> None:
        self.dark: np.ndarray | None = None
        self.flat: np.ndarray | None = None
        # Jalon 53 : masters PAR RÔLE (filtre) — {rôle: image}. Un rôle
        # absent des dictionnaires = pas de master dédié → repli sur le
        # dark/flat unique ci-dessus. Les `*_sources` mémorisent le fichier
        # d'origine de chaque master (affichage dans l'UI).
        self.darks: dict[str, np.ndarray] = {}
        self.flats: dict[str, np.ndarray] = {}
        self.dark_source: str | None = None
        self.flat_source: str | None = None
        self.darks_sources: dict[str, str] = {}
        self.flats_sources: dict[str, str] = {}

    def load_dark(self, path: str, role: str | None = None) -> None:
        img = load_image(path)
        if role is None:
            self.dark = img
            self.dark_source = path
        else:
            self.darks[role] = img
            self.darks_sources[role] = path

    def load_flat(self, path: str, role: str | None = None) -> None:
        img = load_image(path)
        if role is None:
            self.flat = img
            self.flat_source = path
        else:
            self.flats[role] = img
            self.flats_sources[role] = path

    def poser_dark(self, img: np.ndarray, path: str,
                   role: str | None = None) -> None:
        """Pose un dark DÉJÀ CHARGÉ (aucune I/O ici).

        v2.98.7 : utilisé par la RESTAURATION au démarrage — la lecture du
        fichier a eu lieu dans un fil démon borné (le fil d'interface ne fait
        JAMAIS d'I/O, leçon v2.98.4 : un maître peut vivre sur un NAS), et
        c'est ici, dans le fil d'interface, que l'état est modifié.
        """
        if role is None:
            self.dark = img
            self.dark_source = path
        else:
            self.darks[role] = img
            self.darks_sources[role] = path

    def poser_flat(self, img: np.ndarray, path: str,
                   role: str | None = None) -> None:
        """Pose un flat DÉJÀ CHARGÉ (aucune I/O ici) — cf. `poser_dark`."""
        if role is None:
            self.flat = img
            self.flat_source = path
        else:
            self.flats[role] = img
            self.flats_sources[role] = path

    def clear(self) -> None:
        self.dark = self.flat = None
        self.darks.clear()
        self.flats.clear()
        self.dark_source = self.flat_source = None
        self.darks_sources.clear()
        self.flats_sources.clear()

    def apply(self, img: np.ndarray, role: str | None = None) -> np.ndarray:
        # Jalon 53 : master DU RÔLE d'abord, repli sur l'unique — pour les
        # darks ET les flats indépendamment (ex. dark par filtre + flat
        # unique, ou l'inverse).
        dark = self.darks.get(role) if role is not None else None
        if dark is None:
            dark = self.dark
        flat = self.flats.get(role) if role is not None else None
        if flat is None:
            flat = self.flat
        out = img
        if dark is not None and dark.shape == img.shape:
            out = out - dark
        if flat is not None and flat.shape == img.shape:
            m = float(np.median(flat))
            if m > 1e-6:
                out = out / np.clip(flat / m, 0.2, None)
        return np.clip(out, 0, None)


def cles_persistees(calib: Calibrator) -> dict[str, str]:
    """État VIVANT du calibrateur → clés à écrire dans `config.json` (PURE).

    v2.98.7 — POURQUOI : `_load_dark`/`_load_flat` chargeaient l'image en
    mémoire SANS rien persister ; les maîtres étaient donc à re-sélectionner à
    chaque session. Ce que l'on écrit est le CHEMIN, jamais l'image.

    Un maître « unique » (toutes les couches) et un maître PAR RÔLE (jalon 53)
    coexistent : chacun a SA clé. Un maître ABSENT ne produit AUCUNE clé —
    l'appelant doit donc RETIRER les anciennes, sinon un maître effacé
    reviendrait à la session suivante.
    """
    out: dict[str, str] = {}
    if calib.dark_source:
        out[f"{PREFIXE_DARK}_{CIBLE_UNIQUE}"] = calib.dark_source
    if calib.flat_source:
        out[f"{PREFIXE_FLAT}_{CIBLE_UNIQUE}"] = calib.flat_source
    for role, chemin in calib.darks_sources.items():
        if chemin:
            out[f"{PREFIXE_DARK}_{role}"] = chemin
    for role, chemin in calib.flats_sources.items():
        if chemin:
            out[f"{PREFIXE_FLAT}_{role}"] = chemin
    return out


def lire_cles_persistees(conf: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """`config.json` → [(famille, cible, chemin)] des maîtres persistés (PURE).

    `famille` ∈ {"dark", "flat"} ; `cible` = « unique » ou le RÔLE de la couche.
    TOLÉRANTE par construction : une clé ou une valeur qui n'est pas une chaîne
    non vide est IGNORÉE (config d'une autre version, clé vidée à la main) — la
    restauration ne doit jamais échouer sur une entrée douteuse. L'ordre est
    STABLE (uniques puis rôles, dans l'ordre du fichier) : deux exécutions
    donnent la même liste.
    """
    out: list[tuple[str, str, str]] = []
    for famille, prefixe in (("dark", PREFIXE_DARK), ("flat", PREFIXE_FLAT)):
        for cle, valeur in conf.items():
            if not isinstance(cle, str) or not cle.startswith(prefixe + "_"):
                continue
            if not isinstance(valeur, str) or not valeur.strip():
                continue
            cible = cle[len(prefixe) + 1:]
            if cible:
                out.append((famille, cible, valeur))
    return out
