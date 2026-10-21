# -*- coding: utf-8 -*-
"""Banc MULTIFOLDER — détection LIVE et `last_file` SANS I/O (v2.98.4, 21/10/2026).

POURQUOI CE BANC. Le 21/10/2026, `perf-6` a montré que le fil d'interface
passait **96,9 %** de son temps à ATTENDRE (`tick_avant` : 439,6 s d'attente
pour 14,3 s de CPU, `cores_moyens` 0,98) ; la pile du Guet de gel désignait
`MultiFolderCamera.last_file`, qui faisait `os.path.exists` + `os.path.getmtime`
sur 5 dossiers à CHAQUE tour (mesuré 178 ms/tour sur un partage SMB). Le
correctif déplace ce calcul dans le fil d'ACQUISITION, une fois par image lue.

LE RISQUE À COUVRIR, et c'est tout l'objet de ce banc : ne pas casser la
DÉTECTION des images qui arrivent au fur et à mesure (acquisition live faite par
un autre logiciel, ex. NINA, qui dépose ses fichiers dans le dossier).

CE QUE CE BANC VERROUILLE (aucun écran, aucune caméra, aucun réseau)
  [1] DÉTECTION LIVE : des fichiers déposés UN PAR UN dans DEUX dossiers sont
      détectés et lus **une fois chacun**, dans le bon dossier (rôle), dans
      l'ordre chronologique ;
  [2] FICHIER EN COURS D'ÉCRITURE : un fichier qui vient d'être écrit n'est PAS
      pris (anti-écriture partielle) ; il l'est dès qu'il est stable ;
  [3] `last_file` rend EXACTEMENT la valeur de l'ANCIENNE formule (exists +
      getmtime sur les derniers fichiers lus) — les DEUX implémentations sont
      comparées au même instant ;
  [4] `last_file` ne fait AUCUNE I/O : `os.path.exists` et `os.path.getmtime`
      sont ESPIONNÉS pendant 200 lectures ⇒ **0 appel** ;
  [5] la valeur SUIT les lectures (elle n'est pas figée) : un fichier plus
      récent lu dans l'autre dossier devient `last_file` ;
  [6] `stats()` (ligne d'état par rôle) est INCHANGÉ.

Exécution : python bancs/_test_multifolder_last_file.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
import shutil
import sys
import tempfile
import time

import cv2
import numpy as np

from avastack.cameras.multifolder import MultiFolderCamera

if hasattr(sys.stdout, "reconfigure"):      # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def depot(dossier, nom, il_y_a_s):
    """Dépose une image comme le ferait le logiciel d'acquisition.

    `il_y_a_s` recule volontairement la date de modification : c'est la règle
    « taille stable + mtime ancien ⇒ fichier complet » de `FolderCamera._scan`
    (sinon il faudrait attendre 0,5 s réelle par fichier).
    """
    chemin = os.path.join(dossier, nom)
    cv2.imwrite(chemin, np.zeros((8, 8), np.uint8))
    t = time.time() - il_y_a_s
    os.utime(chemin, (t, t))
    return chemin


def reference_ancienne(cam):
    """L'ANCIENNE formule de `last_file` (v2.98.3), recopiée telle quelle.

    Elle sert de TÉMOIN : si le correctif changeait la valeur rendue, ce banc le
    verrait. Elle fait de vraies I/O — donc uniquement sur des dossiers locaux.
    """
    dernier, t_max = "", -1.0
    for c in cam.cams:
        if c.last_file and os.path.exists(c.last_file):
            t = os.path.getmtime(c.last_file)
            if t > t_max:
                dernier, t_max = c.last_file, t
    return dernier


racine = tempfile.mkdtemp(prefix="banc_multifolder_")
dir_a = os.path.join(racine, "A")
dir_b = os.path.join(racine, "B")
os.makedirs(dir_a)
os.makedirs(dir_b)
mc = MultiFolderCamera([("A", dir_a), ("B", dir_b)],
                       process_existing=False, poll=0.01)
mc.open()

# ============================================================================
# [1] DÉTECTION LIVE — fichiers déposés un par un
# ============================================================================
print("[1] Détection live : fichiers déposés UN PAR UN (comme NINA en direct)")
verifie(mc.last_file == "", "avant toute image, `last_file` est VIDE")
verifie(mc.count == 0 and mc.pending == 0, "aucune image, aucune en attente")

p_a1 = depot(dir_a, "A1.png", 50)
img, role = mc.read(timeout=2.0)
verifie(img is not None and role == "A", "1re image dans A ⇒ lue, rôle « A »")
verifie(mc.cams[0].last_file == p_a1, "…le dossier A retient BIEN ce fichier")

p_b1 = depot(dir_b, "B1.png", 40)
img, role = mc.read(timeout=2.0)
verifie(img is not None and role == "B", "image déposée dans B ⇒ lue, rôle « B »")
verifie(mc.cams[1].last_file == p_b1, "…le dossier B retient BIEN ce fichier")

p_a2 = depot(dir_a, "A2.png", 30)
img, role = mc.read(timeout=2.0)
verifie(img is not None and role == "A" and mc.cams[0].last_file == p_a2,
        "2e image dans A ⇒ lue, dans l'ordre")

p_a3 = depot(dir_a, "A3.png", 20)
img, role = mc.read(timeout=2.0)
verifie(img is not None and role == "A" and mc.cams[0].last_file == p_a3,
        "3e image dans A ⇒ lue, dans l'ordre")
verifie(mc.count == 4, f"4 images déposées ⇒ 4 images lues (count = {mc.count})")

# ============================================================================
# [2] Fichier en cours d'écriture : ignoré tant qu'il n'est pas stable
# ============================================================================
print("\n[2] Fichier encore EN COURS d'écriture (date fraîche)")
p_ecrit = os.path.join(dir_a, "en_cours.png")
cv2.imwrite(p_ecrit, np.zeros((8, 8), np.uint8))      # mtime = maintenant
verifie(mc.read(timeout=0.20) is None,
        "un fichier qui vient d'apparaître n'est PAS pris (FITS tronqué évité)")
t_vieux = time.time() - 60
os.utime(p_ecrit, (t_vieux, t_vieux))                 # écriture terminée
img, role = mc.read(timeout=2.0)
verifie(img is not None and role == "A" and mc.cams[0].last_file == p_ecrit,
        "…et il est pris DÈS qu'il est stable (détection intacte)")
verifie(mc.read(timeout=0.30) is None,
        "aucun fichier relu deux fois (la file se vide vraiment)")
verifie(mc.count == 5, f"5 images lues au total (count = {mc.count})")

# ============================================================================
# [3] `last_file` == ANCIENNE formule (zéro changement de comportement)
# ============================================================================
print("\n[3] `last_file` rend la MÊME valeur que l'ancienne formule")
attendu = reference_ancienne(mc)
verifie(mc.last_file == attendu,
        f"valeur identique à l'ancien calcul "
        f"({os.path.basename(mc.last_file)})")
verifie(mc.last_file == p_b1,
        "c'est bien le fichier le PLUS RÉCENT parmi les derniers lus (B1)")

# ============================================================================
# [4] AUCUNE I/O : le défaut mesuré dans `perf-6`
# ============================================================================
print("\n[4] `last_file` ne touche NI le disque NI le réseau (0 appel)")
vrai_exists, vrai_getmtime = os.path.exists, os.path.getmtime
appels = {"n": 0}


def _exists_espion(*a, **k):
    appels["n"] += 1
    return vrai_exists(*a, **k)


def _getmtime_espion(*a, **k):
    appels["n"] += 1
    return vrai_getmtime(*a, **k)


os.path.exists, os.path.getmtime = _exists_espion, _getmtime_espion
try:
    valeurs = {mc.last_file for _ in range(200)}
finally:
    os.path.exists, os.path.getmtime = vrai_exists, vrai_getmtime
verifie(appels["n"] == 0,
        f"200 lectures de `last_file` ⇒ {appels['n']} appel(s) système "
        "(l'ancienne version en faisait 400 : c'étaient les 439,6 s d'attente)")
verifie(len(valeurs) == 1, "…et la valeur est STABLE entre deux lectures")

# ============================================================================
# [5] La valeur SUIT les lectures (elle n'est pas figée)
# ============================================================================
print("\n[5] La valeur SUIT les lectures (pas une photo figée)")
p_b2 = depot(dir_b, "B2.png", 10)
img, role = mc.read(timeout=2.0)
verifie(img is not None and role == "B" and mc.cams[1].last_file == p_b2,
        "nouvelle image dans B ⇒ lue")
verifie(mc.last_file == p_b2,
        f"…et `last_file` la SUIT ({os.path.basename(mc.last_file)})")
verifie(mc.last_file == reference_ancienne(mc),
        "…toujours identique à l'ancienne formule")

# ============================================================================
# [6] `stats()` (ligne d'état par rôle) est inchangé
# ============================================================================
print("\n[6] `stats()` par rôle : inchangé")
st = mc.stats()
verifie(set(st) == {"A", "B"}, f"les deux rôles sont présents ({sorted(st)})")
verifie(st["A"]["last_file"] == p_ecrit and st["B"]["last_file"] == p_b2,
        "chaque rôle publie SON dernier fichier")
verifie(st["A"]["count"] == 4 and st["B"]["count"] == 2,
        f"compteurs par rôle exacts (A={st['A']['count']}, B={st['B']['count']})")
verifie(mc.count == 6, f"total des lectures = 6 (count = {mc.count})")

mc.close()
shutil.rmtree(racine, ignore_errors=True)

# ============================================================================
print()
print("BANC MULTIFOLDER (détection live + `last_file` sans I/O) : "
      + ("TOUT PASSE ✅" if ok else "ÉCHEC ✗"))
sys.exit(0 if ok else 1)
