# -*- coding: utf-8 -*-
"""Calibration dark/flat appliquée à chaque frame entrante.

Jalon 53 (demande d'Alain) : en mode composition (multi-filtres), chaque
rôle peut avoir SON dark et SON flat — indépendamment l'un de l'autre
(ex. un dark par filtre et un flat unique). Un rôle sans master dédié
retombe sur le dark/flat UNIQUE (compatibilité mono inchangée)."""

import numpy as np

from ..images import load_image


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
