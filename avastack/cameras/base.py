# -*- coding: utf-8 -*-
"""Contrat commun de toutes les sources d'images (caméras, dossier, simulation)."""

# Jeu de filtres de la roue INTÉGRÉE (MiniCam8M, relevé réel d'Alain du
# 19/09/2026) : la position 0 est le cran NOIR (obturé — utile pour les
# darks), suivent L R G B SII Ha OIII. Le SDK QHY code la position en
# ASCII : contrôle 17 (« CfwPort ») = 48 + n, soit '0' pour le cran 0 —
# le relevé réel (ctrl 17 = 49 sur le filtre 1) tranche pour 48 + n.
FILTRES_ROUE = ("Dark", "L", "R", "G", "B", "SII", "Ha", "OIII")


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

    # --- roue à filtres (no-op par défaut : seules les caméras qui en
    #     possèdent une redéfinissent — jamais d'erreur pour les autres) ---
    def roue_disponible(self):
        """True si une roue à filtres pilotable est présente (défaut : non)."""
        return False

    def position_filtre(self):
        """Position courante de la roue (0 = cran noir), None si inconnue.
        Relecture À LA DEMANDE, jamais mémorisée (QHY : la position n'est
        fiable qu'une fois la rotation terminée)."""
        return None

    def choisir_filtre(self, n, timeout_s=25.0):
        """Déplace la roue vers la position n (0 = cran noir) et ATTEND la
        fin de la rotation (timeout conseillé par la doc QHY : 25 s).
        BLOQUANT : ne JAMAIS appeler depuis le thread Tk."""
        pass

    # --- refroidissement TEC (no-op par défaut, même esprit) -------------
    def consigne_refroidissement(self, temp_c):
        """Régulation automatique à `temp_c` °C (aucun effet par défaut)."""
        pass

    def lire_refroidissement(self):
        """→ (temp_capteur °C, pwm 0-255, consigne °C) ou None si absent."""
        return None

    def arreter_refroidissement(self):
        """Coupe le refroidissement (aucun effet par défaut)."""
        pass

    def definir_offset(self, offset):
        """Pose l'offset du capteur (aucun effet par défaut : seules les
        caméras SDK qui l'exposent redéfinissent)."""
        pass

    def detecter_capacites(self):
        """→ objet `Capacites` rempli EN DYNAMIQUE depuis la caméra OUVERTE
        (plages expo/gain/offset, TEC, bins, formats…), ou None si la
        marque ne sait pas l'interroger (défaut : None). Nécessite une
        caméra ouverte : appeler APRÈS open(), avant close()."""
        return None
