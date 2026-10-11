# -*- coding: utf-8 -*-
"""Source « dossier surveillé » : empile les brutes au fur et à mesure qu'un
logiciel d'acquisition (N.I.N.A., APT, SGP, ASI Air…) les écrit dedans."""

import os
import time
from collections import deque

from .base import CameraBase
from ..images import load_image


class FolderCamera(CameraBase):
    """Dossier surveillé : empile les brutes au fur et à mesure de leur arrivée.

    Un fichier n'est pris en compte que s'il est complet :
      - taille stable sur 2 scans consécutifs ET mtime > 0,5 s,
      - lecture réussie (3 essais, sinon abandonné et compté 'illisible').
    Les fichiers sont traités dans l'ordre chronologique (mtime, puis nom).
    """
    EXT = (".fits", ".fit", ".fts", ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp")

    def __init__(self, folder, process_existing=True, poll=0.4):
        self.folder = folder
        self.name = f"Dossier : {os.path.basename(folder) or folder}"
        self.process_existing = process_existing
        self.poll = poll
        self._seen = {}                 # nom -> dernière taille vue
        self._queued = set()            # en file d'attente
        self._processed = set()         # traités (ou à ignorer)
        self._pending = deque()
        self.last_file, self.count, self.failed = "", 0, 0
        # Jalon 119 : temps de pose du DERNIER fichier lu (secondes), lu dans
        # l'en-tête FITS en même temps que l'image — None pour PNG/TIFF.
        self.last_exposure = None
        self._running = False

    # -- cycle de vie -----------------------------------------------------
    def open(self):
        if not os.path.isdir(self.folder):
            raise RuntimeError(f"Dossier introuvable : {self.folder}")
        if not self.process_existing:   # ne traiter que ce qui arrivera ensuite
            self._processed = {e.name for e in self._entries()}
        self._running = True

    def close(self):
        self._running = False

    def apply_settings(self, *a):       # exposition/gain déjà « cuits » dans les fichiers
        pass

    # -- surveillance -------------------------------------------------------
    def _entries(self):
        try:
            with os.scandir(self.folder) as it:
                return [e for e in it
                        if e.is_file() and e.name.lower().endswith(self.EXT)]
        except OSError:                 # partage réseau momentanément absent, etc.
            return []

    def _scan(self):
        """Repère les nouveaux fichiers complets et les met en file (ordre chrono)."""
        now = time.time()
        entries = []
        for e in self._entries():
            try:
                st = e.stat()
                entries.append((st.st_mtime, e.name, e.path, st.st_size))
            except OSError:             # disparaît pendant le scan
                continue
        entries.sort()
        for mtime, name, path, size in entries:
            if name in self._processed or name in self._queued:
                continue
            prev = self._seen.get(name)
            if prev is None:                        # 1er aperçu → on attend le scan suivant
                self._seen[name] = size
            elif prev == size and now - mtime > 0.5:
                self._seen.pop(name)                # taille stable + mtime ancien → complet
                self._queued.add(name)
                self._pending.append(path)
            else:
                self._seen[name] = size             # encore en cours d'écriture

    def _try_load(self, path, attempts=3, delay=0.5):
        """→ (image, temps de pose en secondes) ou None. Le temps de pose est
        lu dans l'en-tête FITS (jalon 119) SANS relecture du fichier."""
        for _ in range(attempts):
            try:
                return load_image(path, avec_expo=True)
            except Exception:                       # FITS tronqué… → réessai
                time.sleep(delay)
        return None

    # -- interface CameraBase ---------------------------------------------
    @property
    def pending(self):
        """Fichiers détectés mais pas encore lus (jalon 42 : matière de la
        cadence d'empilement — même contrat que MultiFolderCamera)."""
        return len(self._pending)

    @property
    def exposure_time_sec(self):
        """Temps de pose (secondes) du DERNIER fichier lu, ou None (PNG/TIFF,
        mot-clé absent). Lu avec l'image (en-tête déjà ouvert), donc SANS
        relecture — sert à l'affichage de l'intégration (jalon 119)."""
        return self.last_exposure

    def scanner(self):
        """Repère les nouvelles brutes complètes SANS les lire (jalon 42 :
        permet au worker de savoir ce qui attend sur le disque AVANT de
        décider de lire — la décision de cadence porte alors sur TOUT ce
        qui est arrivé, pas seulement sur ce qui a déjà été détecté)."""
        self._scan()

    def read(self, timeout=1.0):
        """→ prochaine image du dossier (attend jusqu'à `timeout` s), sinon None.
        `timeout` court (rotation round-robin de MultiFolderCamera) : le
        sommeil entre scans est raboté au temps restant, pour ne jamais
        bloquer la rotation plus que demandé."""
        deadline = time.time() + timeout
        while time.time() < deadline and self._running:
            self._scan()
            if self._pending:
                path = self._pending.popleft()
                name = os.path.basename(path)
                self._queued.discard(name)
                lu = self._try_load(path)
                self._processed.add(name)           # tenté = définitif (pas de boucle infinie)
                if lu is not None:
                    img, expo = lu
                    self.last_file, self.count = path, self.count + 1
                    self.last_exposure = expo       # jalon 119 : temps de pose
                    return img
                self.failed += 1
                continue
            time.sleep(min(self.poll, max(0.0, deadline - time.time())))
        return None
