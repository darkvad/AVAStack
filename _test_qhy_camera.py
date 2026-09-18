# -*- coding: utf-8 -*-
"""Test QHY (correctif du crash natif constaté par Alain le 19/09/2026).

Constat réel : QHYCamera.open() rappelait cam.open() APRÈS le constructeur
qhyccd.Camera(cid), alors que le CONSTRUCTEUR OUVRE DÉJÀ la caméra → double
ouverture du handle USB → segfault natif : l'application se fermait sans
message au clic « Démarrer ». Vérifié sans matériel, avec un FAUX module
qhyccd injecté dans sys.modules :
  1. open() ne rappelle JAMAIS cam.open() et suit la séquence officielle
     (avec set_resolution AVANT begin_live) ;
  1b. si AUCUNE ROI n'est acceptée, open() lève une erreur Python CLAIRE au
     lieu d'appeler begin_live() — qui planterait en natif (segfault) ;
  2. read() normalise selon le dtype RÉEL (uint8 → /255, uint16 → /65535)
     et renvoie une COPIE float32 (le ndarray du binding est zero-copy
     côté Rust : son buffer peut être réutilisé à la frame suivante) ;
  3. apply_settings transmet l'exposition en µs et le gain ;
  4. close() stoppe le flux puis referme ;
  5. lister() renvoie [] proprement si le paquet est absent ;
  6. lister_via_sous_processus() renvoie un résultat propre SANS crasher
     même si aucune caméra n'est branchée (isolation du SDK natif) ;
  7. init_sdk() n'est appelé qu'UNE SEULE fois par process, même après un
     lister() puis un open() (constat du banc : « Démarrer » sans détection
     préalable = deux initialisations = fermeture brutale de la fenêtre).

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
    erreur_ctor = None
    roi_refusees = set()
    params = {}

    @staticmethod
    def reset():
        """Remet le faux SDK dans son état initial."""
        _FakeSDK.seq.clear()
        _FakeSDK.id_scan = ["QHYTEST123"]
        _FakeSDK.frame = None
        _FakeSDK.erreur_ctor = None
        _FakeSDK.roi_refusees = set()
        _FakeSDK.params = {}

    def __init__(self, cid):
        if _FakeSDK.erreur_ctor is not None:
            raise RuntimeError(_FakeSDK.erreur_ctor)
        _FakeSDK.seq.append(("ctor", cid))
        self.cid = cid

    def set_stream_mode(self, m):
        _FakeSDK.seq.append(("stream", m))

    def init(self):
        _FakeSDK.seq.append(("init",))

    def set_bin_mode(self, x, y):
        _FakeSDK.seq.append(("bin", x, y))

    def set_resolution(self, x, y, w, h):
        _FakeSDK.seq.append(("res", w, h))
        if (w, h) in _FakeSDK.roi_refusees:
            raise RuntimeError("Operation failed with error code: 4294967295")

    def set_param(self, cid, val):
        _FakeSDK.seq.append(("param", cid, val))

    def get_param(self, cid):
        _FakeSDK.seq.append(("get_param", cid))
        return _FakeSDK.params.get(cid, 0.0)

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
    """Injecte un faux module 'qhyccd' dans sys.modules.

    Le drapeau mqhy._SDK_PRET est remis à False : il simule un process
    NEUF (le garde-fou « une seule init_sdk par process » de qhy.py est
    testé explicitement en [7]).
    """
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
    mqhy._SDK_PRET = False

def main():
    ancien = sys.modules.get("qhyccd")
    try:
        print("[1] open() : séquence officielle, PAS de double ouverture")
        _installer_fake(open_traceur=True)
        _FakeSDK.reset()
        c = QHYCamera(camera_id="QHYTEST123")
        c.open(roi=(3840, 2160))
        types_app = [s[0] for s in _FakeSDK.seq]
        verifie("open" not in types_app,
                "open() explicite JAMAIS rappelé après le constructeur "
                "(cause du crash réel)")
        verifie(types_app == ["init_sdk", "scan", "ctor", "stream", "init",
                              "bin", "res", "live"],
                f"séquence officielle complète (reçu : {types_app})")
        verifie(("res", 3840, 2160) in _FakeSDK.seq,
                "la ROI imposée est transmise par set_resolution")
        verifie(c.name == "QHY QHYTEST123", "nom de caméra avec l'id du scan")

        print("[1b] sécurité : AUCUNE ROI acceptée → erreur Python, "
              "jamais begin_live")
        _installer_fake()
        _FakeSDK.reset()
        _FakeSDK.roi_refusees = {(3840, 2160), (3856, 2180), (3848, 2168),
                                 (1920, 1080)}
        c1b = QHYCamera(camera_id="QHYTEST123")
        err = None
        try:
            c1b.open()
        except RuntimeError as e:
            err = e
        verifie(err is not None and "ROI" in str(err),
                f"erreur claire au lieu du crash natif (reçu : {err})")
        verifie("live" not in [s[0] for s in _FakeSDK.seq],
                "begin_live JAMAIS appelé sans ROI posée (cause du segfault)")
        verifie(c1b.cam is None, "handle neutralisé après l'échec")

        print("[2] read() : normalisation par dtype RÉEL + copie float32")
        _installer_fake()
        _FakeSDK.reset()
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

        print("[7] garde-fou init_sdk : UNE SEULE initialisation par process")
        _installer_fake()
        _FakeSDK.reset()
        QHYCamera.lister()                     # init #1 (scan de découverte)
        c7 = QHYCamera(camera_id="QHYTEST123")
        c7.open()                              # ne doit PAS réinitialiser
        nb = [s[0] for s in _FakeSDK.seq].count("init_sdk")
        verifie(nb == 1,
                f"lister() puis open() → un seul init_sdk (reçu : {nb}) — "
                "cause du « Démarrer ferme l'appli » sans détection préalable")
        verifie(mqhy._SDK_PRET, "drapeau _SDK_PRET levé après ouverture")
        c7.close()
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
