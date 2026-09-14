# -*- coding: utf-8 -*-
"""Outil CLI factice (test headless du jalon 4) : copie l'image d'entrée
vers la sortie et incrémente un compteur d'exécutions — simule GraXpert
sans modèle IA ni téléchargement, pour vérifier le câblage, le cache et
la gestion d'erreur du mode « GraXpert live ».

Usage : python _gx_factice.py <entrée> <sortie> <fichier_compteur>
"""
import shutil
import sys

if len(sys.argv) >= 4:
    with open(sys.argv[3], "a", encoding="utf-8") as f:
        f.write("x\n")
    shutil.copyfile(sys.argv[1], sys.argv[2])
