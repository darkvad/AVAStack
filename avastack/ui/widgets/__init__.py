# -*- coding: utf-8 -*-
"""Widgets d'interface (Tkinter) extraits de `avastack/ui/app.py`.

Jalon 103 du chantier de refactoring (cf. CLAUDE.md / AVANCEMENT.md) : chaque
module regroupe un widget cohérent sous forme de « mixin » — une classe dont
`App` hérite — dont les méthodes sont reprises VERBATIM depuis `app.py` : le
code n'est pas réécrit, `self` reste l'instance `App`, donc le comportement (et
le rendu) est identique AU BIT.
"""
