---
description: S'applique à toute édition de fichier du projet AVAStack
  (AVAStack.py, CLAUDE.md, requirements.txt)
alwaysApply: false
---

Éditer AVAStack.py avec la méthode suivante, pour éviter les corruptions d'indentation constatées (lignes passées de 8 à 16 espaces) :
1. Préférer single_find_and_replace avec une chaîne exacte relue juste avant (read_file) à edit_existing_file sur de gros blocs.
2. Ne JAMAIS inclure dans old_string/new_string des lignes non modifiées — cibler le minimum de lignes.
3. Après CHAQUE édition, exécuter automatiquement, SANS demander l'autorisation d'Alain : (a) la vérification ast.parse de AVAStack.py, (b) en cas d'échec, localiser la ligne fautive, corriger directement (script Python ponctuel si nécessaire), revérifier — sans demander validation.
4. Les commandes shell de vérification/correction ne demandent JAMAIS de confirmation : Alain a explicitement donné son accord (session du renommage v1.1.0).
5. Si une édition échoue 2 fois de suite (chaîne introuvable), relire le fichier entier avant de réessayer — ne jamais enchaîner les essais à l'aveugle.