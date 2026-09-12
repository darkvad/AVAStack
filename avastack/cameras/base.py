# -*- coding: utf-8 -*-
"""Contrat commun de toutes les sources d'images (caméras, dossier, simulation)."""


class CameraBase:
    """Classe de base : toute source doit implémenter open()/read()/close().
    read() → float32 [0..1] de forme (H,W) mono ou (H,W,3) RGB, ou None."""
    name = "?"

    def open(self):
        pass

    def close(self):
        pass

    def read(self):
        raise NotImplementedError

    def apply_settings(self, exposure_ms, gain):
        pass
