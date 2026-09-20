# -*- coding: utf-8 -*-
r"""Source « composition » (jalon 19) : PLUSIEURS dossiers surveillés, un
par rôle (filtre : Ha, O3, S2, R, G, B, L…).

Réutilise FolderCamera TELLE QUELLE (logique « fichier complet », ordre
chronologique, réessais de lecture — rien ne change pour la source
« Dossier » unique). La rotation round-robin interroge chaque dossier à
tour de rôle avec un timeout court, pour qu'un dossier silencieux
(filtre en cours d'acquisition ailleurs, poses longues…) ne bloque
jamais les autres.

read() → (image, rôle) : dérive volontairement du contrat CameraBase
(image seule) — le worker doit savoir dans QUEL empilement de rôle
verser la frame. Documenté ici, assumé côté App (mode composition).
"""

import os
import time

from .base import CameraBase
from .folder import FolderCamera


class MultiFolderCamera(CameraBase):
    """N dossiers surveillés (1 à 4), un par rôle de la composition.

    roles_dossiers : liste de couples (rôle, dossier), ex.
        [("Ha", "C:/acquisition/cible/Ha"), ("O3", "C:/acquisition/cible/O3")]
    """

    def __init__(self, roles_dossiers, process_existing=True, poll=0.4):
        if not roles_dossiers:
            raise RuntimeError("MultiFolderCamera : aucun dossier fourni")
        self.roles = [r for r, _ in roles_dossiers]
        self.cams = [FolderCamera(d, process_existing=process_existing,
                                  poll=poll)
                     for _, d in roles_dossiers]
        self.dossiers = dict(roles_dossiers)
        self.name = "Composition : " + " + ".join(self.roles)
        self.poll = poll
        self._idx = 0                 # départ de la prochaine rotation
        self._running = False

    # -- cycle de vie -----------------------------------------------------
    def open(self):
        ouverts = []
        try:
            for cam in self.cams:
                cam.open()
                ouverts.append(cam)
        except Exception:
            for cam in ouverts:       # ne rien laisser à moitié ouvert
                cam.close()
            raise
        self._running = True

    def close(self):
        self._running = False
        for cam in self.cams:
            cam.close()

    def apply_settings(self, *a):
        for cam in self.cams:
            cam.apply_settings(*a)

    # -- lecture round-robin ------------------------------------------------
    def read(self, timeout=1.0):
        """→ (image, rôle) du prochain fichier complet parmi les dossiers,
        ou None si rien n'est arrivé pendant `timeout` secondes.
        Rotation équitable : on reprend au dossier suivant celui qui a
        donné la dernière frame (aucun dossier n'est privilégié, même si
        l'un produit deux fois plus de frames)."""
        t0 = time.time()
        n = len(self.cams)
        while self._running and time.time() - t0 < timeout:
            for i in range(n):
                j = (self._idx + i) % n
                img = self.cams[j].read(timeout=0.02)   # 1 scan rapide
                if img is not None:
                    self._idx = (j + 1) % n
                    return img, self.roles[j]
            time.sleep(self.poll)
        return None

    # -- état pour l'interface (par rôle) -----------------------------------
    def scanner(self):
        """Scan TOUS les dossiers SANS lire (jalon 42 : matière de la
        cadence d'empilement — le worker sait ce qui attend sur le disque
        avant de décider de lire)."""
        for cam in self.cams:
            cam._scan()

    def stats(self):
        """{rôle: {"count": n, "failed": n, "last_file": chemin}} — matière
        des lignes d'état par canal (« Ha: 12 · O3: 9 »)."""
        return {role: {"count": cam.count, "failed": cam.failed,
                       "last_file": cam.last_file}
                for role, cam in zip(self.roles, self.cams)}

    @property
    def pending(self):
        """Frames détectées mais pas encore lues (tous dossiers)."""
        return sum(len(cam._pending) for cam in self.cams)

    @property
    def count(self):
        """Total de frames lues, tous rôles confondus."""
        return sum(cam.count for cam in self.cams)

    @property
    def failed(self):
        """Total de fichiers illisibles, tous rôles confondus."""
        return sum(cam.failed for cam in self.cams)

    @property
    def last_file(self):
        """Dernier fichier lu, tous rôles confondus (ligne d'état)."""
        dernier, t_max = "", -1.0
        for cam in self.cams:
            if cam.last_file and os.path.exists(cam.last_file):
                t = os.path.getmtime(cam.last_file)
                if t > t_max:
                    dernier, t_max = cam.last_file, t
        return dernier