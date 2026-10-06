# -*- coding: utf-8 -*-
"""Ressources embarquées d'AVAStack — l'icône de l'application.

L'icône vit dans `assets/` à la racine du dépôt, et les installateurs
l'embarquent (gel inclus) :
  - `avastack.ico` : Windows — barre de titres, barre des tâches, exécutable ;
  - `avastack.png` : 512×512, icône Linux/macOS et SOURCE des vignettes MSIX.

Le dossier est résolu depuis `__file__`, JAMAIS depuis le répertoire courant :
une application gelée (PyInstaller) place `assets/` au même niveau relatif que
le package (`_internal/assets` pour le package `_internal/avastack`), donc la
MÊME formule fonctionne dans les deux cas — comme `cameras/sdk_loader`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:                        # typage SEUL : tkinter reste importé
    import tkinter as tk                 # paresseusement, dans la fonction

DOSSIER: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
FICHIER_ICO: str = "avastack.ico"
FICHIER_PNG: str = "avastack.png"


def chemin(nom: str) -> str:
    """Chemin d'une ressource (peut ne pas exister : jamais d'exception)."""
    return os.path.join(DOSSIER, nom)


def poser_icone_fenetre(fenetre: tk.Tk) -> bool:
    """Pose l'icône de la fenêtre principale (barre de titres + barre des tâches).

    Windows : le `.ico` multirésolution (net à toutes les tailles) ; ailleurs :
    le PNG via `iconphoto`. → True si posée. Ne lève JAMAIS : une icône absente
    ne doit pas empêcher l'ouverture de l'application."""
    try:
        ico = chemin(FICHIER_ICO)
        if os.name == "nt" and os.path.isfile(ico):
            fenetre.iconbitmap(ico)
            return True
        png = chemin(FICHIER_PNG)
        if os.path.isfile(png):
            import tkinter as tk
            image = tk.PhotoImage(file=png)
            fenetre.iconphoto(True, image)
            # Tk ne garde QUE l'objet passé : sans référence conservée, il est
            # collecté et l'icône disparaît (piège classique de `iconphoto`).
            # Marqueur RUNTIME volontaire (garde l'image en vie) : pyright ne
            # connaît pas cet attribut ajouté à la volée → ignore CIBLÉ.
            fenetre._avastack_icone = image  # pyright: ignore[reportAttributeAccessIssue]
            return True
    except Exception:
        pass
    return False