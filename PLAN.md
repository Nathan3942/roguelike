# Plan de projet — Roguelike en terminal (Python + curses)

## Contexte

Projet perso et fun, codé principalement **dans le train** : sessions courtes (~30 min), réseau souvent absent.
Objectif : un roguelike classique en ASCII, jouable dès les premières étapes, enrichi milestone par milestone.

## Règles de travail pour Claude Code

- **Une milestone à la fois.** Implémente uniquement la milestone demandée, puis arrête-toi.
- À la fin de chaque milestone :
  1. vérifie que le jeu se lance (`python main.py`) et que les critères d'acceptation sont remplis ;
  2. explique brièvement ce qui a été fait et les concepts clés (en français) ;
  3. propose un message de commit (format : `feat(mX): description`) ;
  4. mets à jour la section **Suivi** en bas de ce fichier.
- Je veux **comprendre** le code : privilégie la lisibilité à la concision, commente les algos (génération, FOV, pathfinding).
- **Zéro dépendance externe** à part `windows-curses` sur Windows. Bibliothèque standard uniquement.
- Le projet doit tourner **hors ligne** : pas d'appel réseau, pas d'asset à télécharger.
- Compatible Linux (Ubuntu) et Windows 11.
- Python **3.11+**, type hints partout, `dataclasses` pour les entités.
- Si un choix de design n'est pas couvert ici, choisis l'option la plus simple et signale-le.

## Stack et structure cible

```
roguelike/
├── main.py              # point d'entrée, init curses, boucle principale
├── game/
│   ├── __init__.py
│   ├── engine.py        # état du jeu, gestion des tours
│   ├── input.py         # mapping touches -> actions
│   ├── render.py        # tout l'affichage curses (carte, HUD, messages)
│   ├── map.py           # GameMap, tuiles
│   ├── procgen.py       # génération de donjon
│   ├── fov.py           # champ de vision
│   ├── entities.py      # Entity, Actor, Item (dataclasses)
│   ├── components.py    # Fighter, Inventory, AI
│   ├── actions.py       # Move, Attack, PickUp, UseItem, Descend...
│   ├── messages.py      # journal de messages
│   └── save.py          # sauvegarde / chargement
├── tests/               # tests unittest (procgen, fov, combat)
├── PLAN.md
└── README.md
```

Architecture : la **logique** (engine, actions, map) ne dépend jamais de curses. Seul `render.py` et `main.py` touchent à curses → la logique reste testable.

Contrôles : flèches **et** `hjkl` (+ `yubn` diagonales), `g` ramasser, `i` inventaire, `>` descendre, `q` quitter.

## Milestones

### M1 — Boucle de jeu
- Init curses (`curses.wrapper`), curseur caché.
- Afficher `@` au centre, déplacement avec flèches / hjkl, `q` pour quitter.
- **OK si** : le `@` bouge sans clignotement et ne sort pas de l'écran.

### M2 — Carte et collisions
- Classe `GameMap` (grille 2D de tuiles : mur `#`, sol `.`).
- Une salle codée en dur ; le joueur ne traverse pas les murs.
- Séparer logique / rendu (`engine.py`, `render.py`).
- **OK si** : collisions fonctionnelles, taille de carte fixe (ex. 80×40) indépendante du terminal ; message clair si le terminal est trop petit.

### M3 — Génération procédurale
- Salles rectangulaires aléatoires sans chevauchement, reliées par des couloirs en L.
- Joueur placé dans la première salle.
- **Seed** paramétrable (`--seed`) et affichée.
- **OK si** : chaque lancement donne un donjon différent, même seed = même donjon ; test unitaire vérifiant que toutes les salles sont connectées.

### M4 — Champ de vision (FOV)
- Rayon de vision (ex. 8), algorithme simple (raycasting ou shadowcasting commenté).
- Trois états : visible, déjà exploré (grisé / dim), inconnu (rien).
- **OK si** : les murs bloquent la vue, l'exploration est mémorisée.

### M5 — Monstres et tours
- Entités `Actor` (gobelin `g`, orc `o`) placées dans les salles.
- Système au tour par tour : le joueur agit, puis chaque monstre.
- IA basique : si le monstre voit le joueur, il se rapproche ; sinon il attend.
- **OK si** : les monstres ne se superposent pas, ne traversent pas les murs, ne bougent que quand le joueur agit.

### M6 — Combat et messages
- Composant `Fighter` (hp, max_hp, attack, defense). Se déplacer sur un monstre = attaquer.
- Mort : monstre → cadavre `%` ; joueur → écran de game over.
- Barre de stats (PV) + journal des 5 derniers messages en bas de l'écran.
- **OK si** : combat lisible dans le journal, le jeu ne crash pas à la mort du joueur.

### M7 — Objets et inventaire
- Potions de soin `!`, ramassage avec `g`, inventaire limité (ex. 10 objets).
- Menu inventaire (`i`) : utiliser / jeter.
- **OK si** : utiliser une potion soigne sans dépasser max_hp ; inventaire plein géré.

### M8 — Étages
- Escalier `>` dans la dernière salle ; `>` génère un nouvel étage.
- Difficulté croissante (plus de monstres, monstres plus forts) selon la profondeur.
- Afficher l'étage courant dans le HUD.
- **OK si** : le joueur garde ses PV et son inventaire entre les étages.

### M9 — Sauvegarde
- Sauvegarde automatique en quittant (`q`), proposition de reprendre au lancement.
- Format JSON (lisible) dans un dossier utilisateur (`~/.roguelike/save.json`).
- Supprimer la sauvegarde à la mort (permadeath).
- **OK si** : quitter puis relancer restaure exactement la partie (carte, exploration, entités, inventaire).

### M10 — Polish
- Couleurs curses (joueur, monstres, objets, murs explorés vs visibles).
- Écran titre (nouvelle partie / continuer / quitter).
- Écran de mort avec score (étage atteint, monstres tués) et seed.
- README avec contrôles et instructions d'installation.

## Bonus (après M10, au choix)
- Pathfinding A* pour les monstres.
- Nouveaux objets : parchemins (éclair, confusion, boule de feu avec ciblage).
- Équipement (arme, armure) et montée de niveau / XP.
- Pièges, portes, boss au dernier étage.
- Classes de personnage.

## Suivi

| Milestone | Statut | Notes |
|-----------|--------|-------|
| M1 | fait | `main.py` + `game/input.py` (touche → action). Diagonales `yubn` déjà incluses. Redimensionnement du terminal géré. |
| M2 | fait | Carte 80×40 dessinée en haut à gauche (pas de caméra). Terminal trop petit → message, seul `q` accepté. Actions déplacées dans `actions.py` (sans curses). 3 tests : `python3 -m unittest discover tests`. |
| M3 | fait | `generate_dungeon(rng)` avec `random.Random(seed)` dédié. Salles en chaîne (chacune reliée à la précédente). Seed affichée sur une ligne de statut sous la carte (terminal min 80×41) et rappelée en quittant. Tests : connexité (BFS) sur 100 seeds, non-chevauchement, déterminisme. |
| M4 | à faire | |
| M5 | à faire | |
| M6 | à faire | |
| M7 | à faire | |
| M8 | à faire | |
| M9 | à faire | |
| M10 | à faire | |
