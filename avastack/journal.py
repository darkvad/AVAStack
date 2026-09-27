# -*- coding: utf-8 -*-
"""JOURNAL d'exécution d'AVAStack : « si l'application ne démarre pas, elle le dit ».

POURQUOI CE MODULE (constat RÉEL d'Alain, 27/09/2026, machine Linux, v2.38.6) :

    « l'appli ne se lance pas sous linux » — et AUCUN message.

Diagnostic : lancée par l'entrée de menu (`avastack.desktop`, `Terminal=false`)
ou par le lanceur `~/.local/bin/avastack`, l'application n'avait que son
`stderr` pour parler — que personne ne lit. Un échec AVANT l'affichage
(dépendance absente du venv : numpy/OpenCV/astropy, `tkinter` manquant,
exception dans la construction de l'interface) produit donc exactement ce que
constate Alain : aucune fenêtre, aucun message, aucune trace. C'est le MÊME
défaut de méthode que le silence de l'astrométrie (v2.38.4) : « l'application
n'a pas de journal ».

Ce module donne à l'application les trois choses qui manquaient :

  ① un JOURNAL sur disque (`<dossier de config>/journal.txt` — `%APPDATA%\\
     AVAStack` sous Windows, `~/.config/AVAStack` sous Linux, rotation à
     1 Mio) : les étapes du démarrage y sont écrites AVANT que la fenêtre
     n'existe, donc un plantage précoce laisse une trace datée ;
  ② un RAPPORT D'ERREUR qui se MONTRE : `montrer()` ouvre une boîte de
     dialogue Tk (visible, y compris lancé par le menu) et retombe sur
     `stderr` si Tk est lui-même indisponible ;
  ③ l'état du système au démarrage (`trace_env`) : versions d'AVAStack, de
     Python et de Tk, exécutable utilisé, OS, répertoire courant et DOSSIER DE
     TRAVAIL avec son espace libre — les questions qu'on se pose en premier
     devant un démarrage raté.

Convention (celle du dépôt) : JAMAIS d'exception. Journaliser est un service,
pas une dépendance : dossier de configuration inaccessible → repli sur le
dossier personnel ; et en dernier ressort tout est abandonné silencieusement —
c'est l'application qui doit démarrer, pas le journal qui doit empêcher.
"""

import os
import sys
import time
import traceback

# Rotation : au-delà, le journal courant devient `journal.txt.1` (un seul
# fichier précédent conservé — de quoi voir le démarrage d'avant un plantage).
TAILLE_MAX = 1 << 20
NOM_FICHIER = "journal.txt"


def dossier_journal():
    """Dossier du journal = dossier de configuration (repli : dossier personnel).

    Import PARESSEUX de `config` : ce module doit rester importable même quand
    le reste de l'application ne l'est pas — c'est tout son intérêt ici."""
    try:
        from .config import dossier_config
        return dossier_config()
    except Exception:                    # config illisible : repli
        return os.path.expanduser("~")


def chemin_journal():
    """Chemin du journal (`<config>/journal.txt`)."""
    return os.path.join(dossier_journal(), NOM_FICHIER)


def ecrire(ligne):
    """Ajoute UNE ligne au journal. → True si écrite (jamais d'exception).

    Rotation AVANT écriture : un journal qui grossit sans fin finirait par
    peser sur le disque de travail."""
    chemin = chemin_journal()
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        try:
            if os.path.getsize(chemin) > TAILLE_MAX:
                os.replace(chemin, chemin + ".1")
        except OSError:
            pass                         # absent ou non renommable : on écrit
        with open(chemin, "a", encoding="utf-8", errors="replace") as f:
            f.write(str(ligne).rstrip("\n") + "\n")
        return True
    except Exception:
        return False


def note(etape, detail=""):
    """Écrit une ligne horodatée « étape — détail » (jamais d'exception)."""
    ligne = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + str(etape)
    if detail:
        ligne += " — " + str(detail)
    return ecrire(ligne)


def _libre(dossier):
    """Espace libre du volume de `dossier`, en texte (« — » si illisible)."""
    try:
        from . import travail
        return travail.texte_octets(travail.espace_libre(dossier))
    except Exception:
        return "—"


def trace_env():
    """Ce qu'il faut savoir devant un démarrage raté : version, Python, Tk, OS,
    exécutable, répertoire courant, dossier de travail et son espace libre.

    Une seule ligne (c'est un journal, pas un rapport) ; chaque élément est
    calculé dans son propre `try` — un Python cassé ne doit pas empêcher de
    dire POURQUOI il est cassé."""
    from . import AVASTACK_VERSION
    elements = ["AVAStack " + AVASTACK_VERSION]
    try:
        elements.append("%s %s" % (sys.implementation.name,
                                   sys.version.split()[0]))
    except Exception:
        pass
    elements.append("exe=" + (sys.executable or "?"))
    try:
        import platform
        elements.append(platform.platform())
    except Exception:
        pass
    try:
        import tkinter as tk
        elements.append("Tk " + str(tk.TkVersion) + "/" + str(tk.TclVersion))
    except Exception as exc:
        elements.append("Tk INDISPONIBLE (" + type(exc).__name__ + ")")
    try:
        elements.append("cwd=" + os.getcwd())
    except Exception:
        pass
    try:
        from . import travail
        d = travail.dossier_travail()
        elements.append("travail=" + d + " (" + _libre(d) + " libres"
                        + (", en RAM (tmpfs)" if travail.est_tmpfs(d) else "")
                        + ")")
    except Exception as exc:
        elements.append("travail INDISPONIBLE (" + str(exc) + ")")
    return " · ".join(elements)


def _emplacement(exc):
    """« (fichier, ligne N) » du dernier cadre du traceback, ou ""."""
    try:
        tb = getattr(exc, "__traceback__", None)
        while tb is not None and tb.tb_next is not None:
            tb = tb.tb_next
        if tb is not None:
            return " (%s, ligne %d)" % (tb.tb_frame.f_code.co_filename,
                                        tb.tb_lineno)
    except Exception:
        pass
    return ""


def erreur(contexte="", exc=None):
    """Journalise une EXCEPTION (la courante par défaut) avec son traceback
    COMPLET, et renvoie un texte COURT — celui que `montrer()` affiche :

        ERREUR démarrage : ImportError: libGL.so.1: cannot open …
          (dans /home/…/avastack/ui/app.py, ligne 14)

    Le journal, lui, garde toutes les lignes du traceback : c'est lui qu'on
    envoie pour diagnostic."""
    if exc is None:
        exc = sys.exc_info()[1]
    if exc is None:                      # appelé sans exception : on le dit
        note("erreur signalée sans exception", str(contexte))
        return str(contexte)
    try:
        complet = "".join(traceback.format_exception(
            type(exc), exc, getattr(exc, "__traceback__", None)))
    except Exception:
        complet = "%s: %s" % (type(exc).__name__, exc)
    court = "ERREUR%s : %s: %s%s" % (((" " + str(contexte)) if contexte else ""),
                                     type(exc).__name__, exc, _emplacement(exc))
    ecrire(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + court)
    for ligne in complet.splitlines():
        ecrire("    | " + ligne)
    return court


def rapport_callback(type_exc, valeur, traceback_):
    """Remplace `Tk.report_callback_exception` : une erreur dans un RAPPEL
    d'interface (clic, curseur, touche) est JOURNALISÉE et IMPRIMÉE.

    Sans cela Tk se contente d'écrire le traceback sur `stderr` : lancé par le
    menu, c'est un échec totalement silencieux — le même angle mort que le
    démarrage. Le message complet reste dans le journal."""
    court = erreur("rappel d'interface", valeur)
    try:
        sys.stderr.write("AVAStack — " + court + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def montrer(titre, message):
    """Montre `message` à l'utilisateur : boîte Tk si possible, sinon `stderr`.

    → "boite", "stderr" ou "aucun" (la valeur sert aux bancs). POURQUOI une
    boîte Tk : c'est le SEUL canal visible pour une application lancée par une
    entrée de menu (`Terminal=false`). Tk est importé ICI, dans son `try` : si
    Tk est précisément ce qui manque, on retombe sur `stderr`.

    `AVASTACK_SANS_DIALOGUE=1` force le mode `stderr` : nécessaire aux bancs et
    aux exécutions sans personne devant l'écran (une boîte de dialogue attend
    indéfiniment qu'on la ferme)."""
    texte = str(message).rstrip() + "\n\nJournal complet : " + chemin_journal()
    if os.environ.get("AVASTACK_SANS_DIALOGUE"):
        try:
            sys.stderr.write("AVAStack — %s : %s\n" % (titre, texte))
            sys.stderr.flush()
            return "stderr"
        except Exception:
            return "aucun"
    try:
        import tkinter as tk
        from tkinter import messagebox
        racine = tk.Tk()
        try:
            racine.withdraw()
            try:
                racine.attributes("-topmost", True)
            except Exception:
                pass
            messagebox.showerror(str(titre), texte, parent=racine)
        finally:
            try:
                racine.destroy()
            except Exception:
                pass
        return "boite"
    except Exception:
        pass
    try:
        sys.stderr.write("AVAStack — %s : %s\n" % (titre, texte))
        sys.stderr.flush()
        return "stderr"
    except Exception:
        return "aucun"


def ouvrir():
    """Ouvre le journal dans l'outil par défaut de l'OS.
    → "" si la commande est partie, sinon le message d'erreur (jamais
    d'exception : l'appelant l'affiche tel quel)."""
    try:
        from . import travail
    except Exception as exc:
        return str(exc)
    if not os.path.isfile(chemin_journal()):   # rien à ouvrir : on le note
        note("journal", "ouvert avant tout incident enregistré")
    return travail.ouvrir_chemin(chemin_journal())
