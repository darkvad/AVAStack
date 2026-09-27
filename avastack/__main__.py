# -*- coding: utf-8 -*-
"""Lancement AVAStack : `python -m avastack` (strictement équivalent à AVAStack.py).

POURQUOI `runpy` (v2.38.7) : le FILET DE DÉMARRAGE (journal écrit sur disque +
message visible, cf. `avastack.journal` et l'en-tête d'`AVAStack.py`) doit
exister UNE seule fois. Deux points d'entrée qui recopient le même enchaînement
d'imports finissent toujours par diverger — et celui-ci doit justement rester
en tête de chaîne, puisque c'est lui qui parle quand l'application ne démarre
pas. `python -m avastack` exécute donc le MÊME script que `python AVAStack.py`.
"""

import os
import runpy
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, "AVAStack.py")

if not os.path.isfile(SCRIPT):                # paquet incomplet : le dire net
    sys.stderr.write("AVAStack : AVAStack.py introuvable (%s) — paquet "
                     "incomplet.\n" % SCRIPT)
    raise SystemExit(1)

# `avastack` est importable (c'est le paquet en cours d'exécution) : le script
# retrouve donc `import avastack` sans manipulation de `sys.path`.
runpy.run_path(SCRIPT, run_name="__main__")

