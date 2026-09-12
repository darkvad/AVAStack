---
globs: '["**/*.py", "**/*.md"]'
description: S'applique à toute édition de fichier .py ou .md (tous projets —
  AVAStack, astromatix, etc.)
alwaysApply: false
---

Éditer tout fichier .py ou .md avec la méthode suivante, pour éviter les corruptions constatées (lignes dont l'indentation passe de 8 à 16 espaces lors d'éditions) :
1. Préférer single_find_and_replace avec une chaîne exacte relue juste avant (read_file) à edit_existing_file sur de gros blocs.
2. Ne JAMAIS inclure dans old_string/new_string des lignes non modifiées — cibler le minimum de lignes.
3. Après CHAQUE édition d'un .py, exécuter automatiquement, SANS demander l'autorisation d'Alain : (a) la vérification de syntaxe (ast.parse pour Python), (b) en cas d'échec, localiser la ligne fautive, corriger directement (script Python ponctuel si nécessaire), revérifier — sans demander validation.
4. Pour les .md : relire la section modifiée après édition pour vérifier que rien d'autre n'a bougé.
5. Les commandes shell de vérification/correction ne demandent JAMAIS de confirmation : Alain a explicitement donné son accord (session renommage AVAStack v1.1.0).
6. Si une édition échoue 2 fois de suite (chaîne introuvable), relire le fichier entier avant de réessayer — ne jamais enchaîner les essais à l'aveugle.