# -*- coding: utf-8 -*-
"""Diagnostic SDK QHYCCD (paquet pip qhyccd) — SANS caméra branchée.

Répond à la question du crash « Démarrer → l'appli se ferme sans message » :
  - init_sdk / scan_cameras se chargent-ils (DLL SDK) ?
  - le CONSTRUCTEUR Camera(id) tente-t-il d'ouvrir la caméra lui-même
    (exception propre sur un id inexistant) ? Si oui, l'appel explicite
    cam.open() de QHYCamera.open() est une DOUBLE ouverture — suspect n°1
    du crash natif constaté par Alain le soir du test Minicam8M.

Exécution : venv/Scripts/python.exe _diag_qhy_sdk.py
"""
import sys

print("A: import qhyccd", flush=True)
import qhyccd

print("B: init_sdk()...", flush=True)
qhyccd.init_sdk()
print("C: init_sdk OK", flush=True)

cams = qhyccd.scan_cameras()
print("D: scan_cameras ->", cams, flush=True)

print("E: Camera('ID_INEXISTANT_TEST')...", flush=True)
try:
    c = qhyccd.Camera("ID_INEXISTANT_TEST")
    print("F: constructeur SANS exception ->", type(c), flush=True)
except Exception as e:
    print("F: constructeur a leve ->", type(e).__name__, ":", e, flush=True)

print("G: fin propre", flush=True)
