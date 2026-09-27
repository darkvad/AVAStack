#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AVAStack — live stacking (empilement temps réel)
================================================
Point d'entrée de l'application : le code vit dans le package `avastack/`
(découpé par thème, cf. avastack/__init__.py pour la carte et le changelog).

Lancement :  python AVAStack.py   (ou : python -m avastack)

Dépendances : cf. requirements.txt (numpy, opencv-python, pillow ; optionnels :
astropy pour FITS, zwoasi + SDK ASI pour les caméras ZWO).

Test sans matériel : source « Simulée (démo) » → Démarrer.
Test en dossier : choisir le dossier, éventuellement déposer une brute dedans → Démarrer.

FILET DE DÉMARRAGE (v2.38.7) — constat RÉEL d'Alain (Linux, 27/09/2026) :
« l'appli ne se lance pas sous linux », sans AUCUN message. Lancée par le menu
(entrée .desktop en `Terminal=false`) ou par le lanceur `~/.local/bin/avastack`,
l'application n'avait que son `stderr` pour parler : tout échec AVANT
l'affichage (dépendance absente du venv, `tkinter` manquant, exception dans la
construction de l'interface) était donc invisible ET sans trace écrite.

Ici, le journal est ouvert AVANT le premier import de l'application (il ne
dépend que de la bibliothèque standard), puis TOUT — imports compris — est
enveloppé : l'échec est écrit dans `journal.txt` et MONTRÉ dans une boîte de
dialogue, pour qu'un démarrage raté dise toujours pourquoi.
"""

import sys

# --- ① le journal AVANT tout le reste (stdlib seulement) --------------------
# `avastack/__init__.py` ne contient que la version et la documentation : cet
# import ne peut pas échouer là où l'application, elle, échoue.
try:
    from avastack import journal
except Exception as exc:                 # même le journal est hors service
    journal = None
    print("AVAStack : journal indisponible (%s: %s)" % (type(exc).__name__, exc),
          file=sys.stderr)

try:
    from avastack import delais
except Exception:                        # repli : on mesurera sans borne
    delais = None


def _demarrer():
    """Importe l'application et ouvre la fenêtre (étapes journalisées).

    Les imports vivent ICI et non au niveau du module : c'est ce qui permet de
    les envelopper — une dépendance absente doit dire son nom, pas mourir dans
    un terminal que personne ne regarde.

    v2.38.11 — DEUX GARANTIES DE PLUS, tirées du constat RÉEL du 27/09/2026
    (« cette version ne se lance pas », sans AUCUN message ni ligne de journal) :
    ① la PREMIÈRE ligne est écrite **sans aucun accès disque** (version,
       interpréteur, argv) : le journal ne peut plus rester vide ;
    ② la mesure de l'environnement est **BORNÉE à 5 s** (fil démon) : un accès
       disque bloqué (dossier de couches R/G/B sur un NAS injoignable, pare-feu
       nftables) ne peut plus empêcher l'ouverture — et le journal DIT que la
       mesure n'a pas abouti, au lieu de mourir en silence."""
    import avastack
    if journal:
        journal.note("démarrage", "AVAStack %s — %s — python %s — argv=%s"
                     % (avastack.AVASTACK_VERSION, sys.executable,
                        sys.version.split()[0], " ".join(sys.argv[1:]) or "—"))
        journal.etape("mesure de l'environnement", "accès disque possible")
        if delais is not None:
            env, abouti = delais.borne(journal.trace_env, "", delais.DELAI_DEFAUT)
        else:
            env, abouti = journal.trace_env(), True
        if abouti and env:
            journal.note("démarrage", env)
        else:
            journal.note("démarrage", "environnement NON MESURÉ — un accès "
                         "disque BLOQUE (montage réseau NAS injoignable ? "
                         "pare-feu ?) : l'application continue sans lui")
    from avastack.ui.app import main
    if journal:
        journal.note("démarrage", "interface importée : ouverture de la fenêtre")
    main()
    if journal:
        journal.note("arrêt", "fenêtre fermée (sortie normale)")


def _echec(exc):
    """Démarrage impossible : journal + message VISIBLE + code de sortie 1.

    Le message porte le CONSEIL quand la cause est connue (session SANS BUREAU —
    lancement par SSH, constaté le 27/09/2026 avec la v2.38.7 — ou `tkinter`
    absent).

    NB : la panne de la v2.38.6 lancée par le MENU Applications (aucune fenêtre,
    aucun message) est une AUTRE histoire, restée sans explication ; ce filet ne
    la prétend pas résolue — il la rend seulement mesurable."""
    if journal:
        journal.montrer("AVAStack ne peut pas démarrer",
                        journal.rapport_echec(exc))
    else:                                 # dernier recours : stderr, comme avant
        import traceback
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    return 1


if __name__ == "__main__":
    try:
        import avastack
        print(f"AVAStack v{avastack.AVASTACK_VERSION}")
    except Exception:                     # le message n'est pas vital
        pass
    try:
        _demarrer()
    except SystemExit:
        raise
    except BaseException as e:            # y compris KeyboardInterrupt
        raise SystemExit(_echec(e))
