# -*- coding: utf-8 -*-
"""Banc du jalon 91 : SCAN QHY d'une application GELÉE (PyInstaller).

POURQUOI CE BANC (chantier « Microsoft Store », 02/10/2026) : le scan QHY est
isolé dans un SOUS-PROCESSUS (`avastack/cameras/qhy.py`) — en dev le parent
lance `python -c …`. Une application GELÉE par PyInstaller ne sait PAS exécuter
`-c` : MESURÉ, l'exe ignore ses arguments et rouvre l'interface. Sans correctif,
la DÉTECTION QHY échouerait donc dans le paquet gelé (l'erreur ne dirait RIEN
d'utile : simple délai dépassé).

Ce banc vérifie :
  [1] le DRAPEAU est UN SEUL : `cameras/qhy.DRAPEAU_SCAN` ==
      `AVAStack._MODE_SCAN_QHY` (deux chaînes recopiées finissent par diverger) ;
  [2] la COMMANDE en mode NORMAL (venv) : `python -c …`, racine du projet en
      argv[1] (jamais interpolée), AUCUN drapeau ;
  [3] la COMMANDE en mode GELÉ (`sys.frozen` simulé) : l'exe relancé AVEC le
      drapeau et SANS `-c` — c'est précisément ce qui serait cassé sans lui ;
  [4] BOUT EN BOUT, en réel : `python AVAStack.py --scan-qhy` (faux module
      `qhyccd` posé sur PYTHONPATH) imprime la liste JSON **et n'ouvre AUCUNE
      fenêtre** (le mode interne sort AVANT l'interface) ;
  [5] le CONTRAT du parent est INCHANGÉ : il lit la DERNIÈRE ligne de stdout
      (une ligne parasite en amont ne le perturbe pas).

Autonome (aucune caméra, aucun affichage Tk requis).
Exécution : python bancs/_test_gel_qhy_jalon91.py
"""
import sys as _sys_banc, pathlib as _pl_banc
_RACINE = None
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _RACINE = str(_d_banc)
        _sys_banc.path.insert(0, _RACINE)
        break
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


import avastack.cameras.qhy as qhy                                       # noqa: E402


def _charger_avastack():
    """Charge AVAStack.py comme MODULE (sans lancer l'application)."""
    spec = importlib.util.spec_from_file_location(
        "_avastack_entry", os.path.join(_RACINE, "AVAStack.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AVASTACK = _charger_avastack()

# ==================================== [1] un SEUL drapeau
print("[1] le drapeau de scan est UN SEUL (jamais divergent)")
verifie(AVASTACK._MODE_SCAN_QHY == qhy.DRAPEAU_SCAN,
        "AVAStack._MODE_SCAN_QHY == qhy.DRAPEAU_SCAN (%r)"
        % (qhy.DRAPEAU_SCAN,))

# ==================================== [2] commande en mode NORMAL
print("[2] mode NORMAL : `python -c …`, racine en argv[1], aucun drapeau")
sys.frozen = False
cmd = qhy._commande_scan()
verifie(cmd[0] == sys.executable and len(cmd) >= 3 and cmd[1] == "-c",
        "argv[0:2] = [python, -c] (reçu : %r)" % (cmd[:2],))
verifie(qhy.DRAPEAU_SCAN not in cmd, "aucun drapeau en mode normal")
verifie("QHYCamera.lister()" in cmd[2], "le code enfant appelle QHYCamera.lister()")
verifie(cmd[-1] == qhy.RACINE_PROJET,
        "la racine du projet passe par sys.argv[1] (jamais interpolée)")

# ==================================== [3] commande en mode GELÉ
print("[3] mode GELÉ : exe relancé AVEC le drapeau, SANS `-c`")
sys.frozen = True
try:
    cmd = qhy._commande_scan()
finally:
    del sys.frozen
verifie(cmd == [sys.executable, qhy.DRAPEAU_SCAN],
        "argv = [exe, %s] (reçu : %r)" % (qhy.DRAPEAU_SCAN, cmd))
verifie("-c" not in cmd,
        "AUCUN `-c` (un exe gelé l'ignore : c'est la panne corrigée)")

# ==================================== [4] bout en bout, en réel
print("[4] bout en bout : `python AVAStack.py --scan-qhy` → JSON, aucune fenêtre")
bogue = tempfile.mkdtemp(prefix="banc91_fake_")
with open(os.path.join(bogue, "qhyccd.py"), "w", encoding="utf-8") as f:
    f.write("def init_sdk():\n    pass\n\n\n"
            "def scan_cameras():\n    return ['QHYFAKE1', 'QHYFAKE2']\n")
env = dict(os.environ)
env["PYTHONPATH"] = bogue + os.pathsep + env.get("PYTHONPATH", "")
env["PYTHONDONTWRITEBYTECODE"] = "1"
r = subprocess.run([sys.executable, "AVAStack.py", qhy.DRAPEAU_SCAN],
                   cwd=_RACINE, env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=300)
lignes = (r.stdout or "").strip().splitlines()
verifie(r.returncode == 0, "code retour 0 (reçu %s)" % r.returncode)
verifie(bool(lignes) and json.loads(lignes[-1]) == ["QHYFAKE1", "QHYFAKE2"],
        "dernière ligne de stdout = liste JSON (reçu : %r)"
        % (lignes[-1:] or None,))
verifie("AVAStack v" not in (r.stdout or ""),
        "le mode scan n'imprime RIEN d'autre (pas de bannière de version)")

# ==================================== [5] contrat du parent : dernière ligne
print("[5] le parent lit la DERNIÈRE ligne (une ligne parasite ne le gêne pas)")
aide = os.path.join(bogue, "aide.py")
with open(aide, "w", encoding="utf-8") as f:
    f.write("import json\nprint('ligne parasite')\nprint(json.dumps(['QHYX']))\n")
_vrai = qhy._commande_scan
qhy._commande_scan = lambda: [sys.executable, aide]
try:
    ids, err = qhy.lister_via_sous_processus(timeout_s=60)
finally:
    qhy._commande_scan = _vrai
verifie(err is None and ids == ["QHYX"],
        "ids=%r, err=%r — la dernière ligne est bien le JSON du scan" % (ids, err))

print("")
print("TOUT AU VERT" if ok else "DES ÉCHECS")
sys.exit(0 if ok else 1)
