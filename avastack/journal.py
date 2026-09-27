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


def sans_affichage(exc=None, env=None):
    """L'échec vient-il de l'ABSENCE de session graphique (bureau) ?

    Constat RÉEL d'Alain (Linux, 27/09/2026) : lancée par SSH — donc sans
    bureau —, la v2.38.7 est morte sur `tk.Tk()` :
    `_tkinter.TclError: no display name and no $DISPLAY environment variable`.
    C'est une ERREUR D'USAGE normale (il faut un bureau), pas une panne : elle
    mérite une phrase actionnable, pas un traceback.

    NB IMPORTANT (à ne pas confondre) : la panne du même jour par le MENU
    Applications (v2.38.6 : aucune fenêtre, AUCUN message) est une AUTRE affaire,
    restée sans explication — le lancement par SSH n'en est PAS la cause.

    Deux indices, jamais un seul : le message de Tk (`no display name`,
    `couldn't connect to display`), et — sous Linux seulement, où `DISPLAY`
    existe — un `DISPLAY` vide. Un `env` FOURNI (bancs, tests) est la seule
    autorité : il permet de rejouer le cas Linux depuis n'importe quel OS.
    Sous Windows/macOS sans `env` fourni, on ne conclut QUE sur le message, pour
    ne jamais refuser à tort."""
    txt = str(exc or "")
    if ("no display name" in txt or "$DISPLAY" in txt
            or "couldn't connect to display" in txt):
        return True
    if env is not None:              # environnement explicite : il décide
        return "TclError" in txt and not env.get("DISPLAY")
    if os.name == "nt" or sys.platform == "darwin":
        return False                 # `DISPLAY` ne veut rien dire ici
    return "TclError" in txt and not os.environ.get("DISPLAY")


def conseil_installation(exc=None):
    """Conseil ACTIONNABLE pour un échec de démarrage CONNU, sinon "".

    Deux cas nommés, ceux que le journal a réellement rencontrés :
      ① session sans bureau (SSH sans redirection X, pas de `DISPLAY`) ;
      ② `tkinter` absent du python utilisé (« No module named '_tkinter' ») —
         sous Linux il ne s'installe PAS par pip : c'est un paquet système.
    Ne jamais inventer un conseil pour une cause inconnue : l'absence de
    correspondance doit rendre "" (l'appelant affiche alors le message générique)."""
    txt = str(exc or "")
    if sans_affichage(exc):
        return ("AVAStack a besoin d'un BUREAU (session graphique) : celle-ci n'en "
                "a pas.\n"
                "  · depuis ton bureau : lance « avastack » (ou le menu "
                "Applications) ;\n"
                "  · par SSH : ajoute -X à la connexion (ssh -X …) pour rediriger "
                "l'affichage, ou renseigne DISPLAY (par exemple DISPLAY=:0).")
    if "'_tkinter'" in txt or "No module named 'tkinter'" in txt or \
            "No module named \"tkinter\"" in txt:
        return ("L'interface graphique de Python (Tkinter) n'est pas installée pour "
                "ce python :\n"
                "  Debian/Ubuntu : sudo apt install python3-tk\n"
                "  Fedora        : sudo dnf install python3-tkinter\n"
                "  Arch/Manjaro  : sudo pacman -S tk\n"
                "puis relance l'installateur (bash installer/install_avastack.sh).")
    return ""


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


def rapport_echec(exc, contexte="démarrage"):
    """Texte à MONTRER pour un échec fatal : CONSEIL (si la cause est connue),
    message court avec fichier et ligne, chemin du journal.

    Une seule mise en forme, donc un seul comportement pour les deux points
    d'entrée. Le traceback complet, lui, reste dans le journal (cf. `erreur`).
    Le conseil sert quand la cause est CONNUE — typiquement une session sans
    bureau (lancement par SSH), qui doit se comprendre sans lire un traceback."""
    court = erreur(contexte, exc)
    conseil = conseil_installation(exc)
    morceaux = [conseil, court] if conseil else [court]
    morceaux.append("Le détail complet est dans le journal (bouton « Journal » "
                    "de la fenêtre) :\n" + chemin_journal())
    return "\n\n".join(morceaux)


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
