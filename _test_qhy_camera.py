# -*- coding: utf-8 -*-
"""Test QHY (correctif du crash natif constaté par Alain le 19/09/2026).

Constat réel : QHYCamera.open() rappelait cam.open() APRÈS le constructeur
qhyccd.Camera(cid), alors que le CONSTRUCTEUR OUVRE DÉJÀ la caméra → double
ouverture du handle USB → segfault natif : l'application se fermait sans
message au clic « Démarrer ». Vérifié sans matériel, avec un FAUX module
qhyccd injecté dans sys.modules :
  1. open() ne rappelle JAMAIS cam.open() et suit la séquence officielle ;
  2. read() normalise selon le dtype RÉEL (uint8 → /255, uint16 → /65535)
     et renvoie une COPIE float32 (le ndarray du binding est zero-copy
     côté Rust : son buffer peut être réutilisé à la frame suivante) ;
  3. apply_settings transmet l'exposition en µs et le gain ;
  4. close() stoppe le flux puis referme ;
  5. lister() renvoie [] proprement si le paquet est absent ;
  6. lister_via_sous_processus() renvoie un résultat propre SANS crasher
     même si aucune caméra n'est branchée (isolation du SDK natif).

Autonome (aucun affichage Tk requis).
Exécution : python _test_qhy_camera.py
"""
import sys
import types

import numpy as np

import avastack.cameras.qhy as mqhy
from avastack.cameras.qhy import QHYCamera

# Sortie robuste aux REDIRECTIONS (piège réel : la boucle de tests exécute
# ce fichier avec stdout redirigé → encodage cp1252 → UnicodeEncodeError sur
# « → », « … »… alors qu'en console interactive UTF-8 tout passait).
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

VERIFIES = []


def verifie(cond, label):
    VERIFIES.append((bool(cond), label))
    print(("  OK   " if cond else "ECHEC ") + label)


class _FakeSDK:
    """Substitut du paquet qhyccd : enregistre la séquence d'appels.

    NB : PAS de méthode open() (la vraie classe en a une, mais la séquence
    officielle ne l'appelle jamais) — un rappel lèverait AttributeError ;
    le cas est aussi testé explicitement avec un open() traçant (cf.
    _installer_fake(open_traceur=True)).
    """
    seq = []
    id_scan = ["QHYTEST123"]
    frame = None

    def __init__(self, cid):
        _FakeSDK.seq.append(("ctor", cid))
        self.cid = cid

    def set_stream_mode(self, m):
        _FakeSDK.seq.append(("stream", m))

    def init(self):
        _FakeSDK.seq.append(("init",))

    def set_bin_mode(self, x, y):
        _FakeSDK.seq.append(("bin", x, y))

    def begin_live(self):
        _FakeSDK.seq.append(("live",))

    def get_live_frame(self):
        _FakeSDK.seq.append(("frame",))
        return _FakeSDK.frame

    def set_exposure(self, us):
        _FakeSDK.seq.append(("exposure", us))

    def set_gain(self, g):
        _FakeSDK.seq.append(("gain", g))

    def stop_live(self):
        _FakeSDK.seq.append(("stop",))

    def close(self):
        _FakeSDK.seq.append(("close",))


def _installer_fake(open_traceur=False):
    """Injecte un faux module 'qhyccd' dans sys.modules."""
    if open_traceur:
        def open_(self):
            _FakeSDK.seq.append(("open",))
        _FakeSDK.open = open_          # open() traçant : doit rester ABSENT
    elif hasattr(_FakeSDK, "open"):
        del _FakeSDK.open

    fake = types.ModuleType("qhyccd")
    fake.Camera = _FakeSDK
    fake.init_sdk = lambda: _FakeSDK.seq.append(("init_sdk",))
    fake.scan_cameras = lambda: (
        _FakeSDK.seq.append(("scan",)) or list(_FakeSDK.id_scan))
    sys.modules["qhyccd"] = fake

def main():
    ancien = sys.modules.get("qhyccd")
    try:
        print("[1] open() : séquence officielle, PAS de double ouverture")
        _installer_fake(open_traceur=True)
        _FakeSDK.seq.clear()
        c = QHYCamera(camera_id="QHYTEST123")
        c.open()
        types_app = [s[0] for s in _FakeSDK.seq]
        verifie("open" not in types_app,
                "open() explicite JAMAIS rappelé après le constructeur "
                "(cause du crash réel)")
        verifie(types_app == ["init_sdk", "scan", "ctor", "stream", "init",
                              "bin", "live"],
                f"séquence officielle complète (reçu : {types_app})")
        verifie(c.name == "QHY QHYTEST123", "nom de caméra avec l'id du scan")

        print("[2] read() : normalisation par dtype RÉEL + copie float32")
        _FakeSDK.frame = np.array([[0, 32768], [65535, 65535]],
                                  dtype=np.uint16)
        f = c.read()
        verifie(f is not None and f.dtype == np.float32 and f.max() == 1.0,
                "RAW16 → [0..1] (65535 → 1.0)")
        _FakeSDK.frame = np.full((4, 4), 255, dtype=np.uint8)
        f8 = c.read()
        verifie(f8 is not None and f8.max() == 1.0,
                "RAW8 → [0..1] (255 → 1.0, pas /65535)")
        verifie(not np.shares_memory(f8, _FakeSDK.frame),
                "la frame retournée est une COPIE (buffer Rust non partagé)")
        _FakeSDK.frame = None
        verifie(c.read() is None, "frame None (pas de nouvelle image) → None")

        print("[3] apply_settings : µs + gain transmis")
        _FakeSDK.seq.clear()
        c.apply_settings(100.0, 2.0)
        apps = [s for s in _FakeSDK.seq if s[0] in ("exposure", "gain")]
        verifie(("exposure", 100000) in apps and ("gain", 2.0) in apps,
                "exposition 100 ms → 100000 µs, gain 2.0")

        print("[4] close() : stop puis close")
        _FakeSDK.seq.clear()
        c.close()
        types_app = [s[0] for s in _FakeSDK.seq]
        verifie(types_app == ["stop", "close"], "stop_live puis close")
        verifie(c.cam is None, "handle libéré")

        print("[5] lister() : [] propre sans paquet, ids sinon")
        sys.modules["qhyccd"] = None      # → ImportError sur import qhyccd
        verifie(QHYCamera.lister() == [],
                "paquet absent → [] (pas d'exception)")
        _installer_fake()
        verifie(QHYCamera.lister() == ["QHYTEST123"],
                "paquet présent → ids du scan")

        print("[6] lister_via_sous_processus() : isolation du SDK natif")
        ids, err = mqhy.lister_via_sous_processus(timeout_s=40)
        verifie(err is None and isinstance(ids, list),
                f"retour propre sans crash (ids={ids!r}, err={err!r}) — "
                "isolation OK (pas de caméra branchée : [])")
    finally:
        if ancien is not None:
            sys.modules["qhyccd"] = ancien
        else:
            sys.modules.pop("qhyccd", None)

    echecs = [l for ok, l in VERIFIES if not ok]
    print()
    if echecs:
        print(f"ECHEC : {len(echecs)} verification(s)")
        sys.exit(1)
    print(f"TOUTES LES VERIFICATIONS PASSENT ({len(VERIFIES)})")


if __name__ == "__main__":
    main()
