# Donjon ASCII

Un roguelike classique qui se joue dans le terminal, en Python + curses.
Descendez le plus profond possible dans un donjon généré aléatoirement, en
combattant gobelins et orcs. La mort est définitive.

```
   #####..#.##
   #...@..g..#        @  vous          g  gobelin     o  orc
   #.........####     !  potion        %  cadavre     >  escalier
   #.........o...     -  |  flèches en vol
   ######.####
```

## Installation

Il faut **Python 3.11 ou plus récent**. Aucune connexion réseau n'est nécessaire
pour jouer.

### Linux (Ubuntu…) / WSL / macOS

`curses` est inclus dans Python : rien à installer.

```bash
python3 main.py
```

### Windows 11

Sous Windows, Python ne fournit pas `curses` : il faut installer
`windows-curses` **une seule fois** (connexion réseau nécessaire pour cette étape).

```powershell
py -m pip install -r requirements.txt
py main.py
```

Utilisez de préférence **Windows Terminal**.

### Taille du terminal

Le jeu a besoin d'au moins **80 colonnes × 46 lignes** : agrandissez la fenêtre
ou réduisez la police. Si le terminal est trop petit, un message l'indique.

## Commandes

| Touche | Action |
|---|---|
| Flèches ou `h` `j` `k` `l` | se déplacer (gauche, bas, haut, droite) |
| `y` `u` `b` `n` | se déplacer en diagonale |
| se déplacer vers un monstre | l'attaquer |
| `w` `a` `s` `d` | tirer une flèche (haut, gauche, bas, droite) |
| `.` ou `5` | attendre un tour |
| `g` | ramasser un objet |
| `i` | ouvrir l'inventaire (lettre : choisir un objet, puis `u` utiliser / `j` jeter) |
| `>` | descendre l'escalier (quand on est dessus) |
| `Échap` | fermer un menu |
| `q` | sauvegarder et quitter |

## Options

```bash
python3 main.py --seed 42   # rejouer exactement le même donjon
```

Chaque donjon est généré à partir d'une **seed** (un nombre). Elle est affichée
en bas de l'écran pendant la partie et sur l'écran de mort : relancez avec
`--seed` pour retenter le même donjon.

## Sauvegarde

- En quittant avec `q`, la partie est sauvegardée automatiquement dans
  `~/.roguelike/save.json` (sous Windows : `C:\Users\<vous>\.roguelike\save.json`).
- Au lancement, choisissez **Continuer** sur l'écran titre pour la reprendre.
- **Permadeath** : à la mort, la sauvegarde est supprimée.

## Règles en bref

- Le jeu est au tour par tour : les monstres n'agissent que quand vous agissez.
- Dégâts d'une attaque = attaque de l'attaquant − défense de la cible.
- Flèches infinies : tirer coûte un tour. Une flèche avance d'une case à chaque
  action, touche le premier monstre rencontré (4 − défense) et se brise sur
  les murs. Le corps à corps (5) fait plus mal.
- Une potion de soin rend 10 PV (sans dépasser le maximum).
- Le sac contient 10 objets au maximum.
- Plus on descend, plus les monstres sont nombreux et forts.
- Score : niveau atteint et nombre de monstres tués.

## Développement

```bash
python3 -m unittest discover tests   # lancer les tests
```

| Fichier | Rôle |
|---|---|
| `main.py` | point d'entrée, écrans (titre, jeu, mort), boucle principale |
| `game/engine.py` | état de la partie, tours, combat, objets, étages |
| `game/procgen.py` | génération des étages et difficulté |
| `game/fov.py` | champ de vision |
| `game/map.py` | carte et tuiles |
| `game/entities.py` | joueur, monstres, objets |
| `game/components.py` | combat, inventaire, IA, effets |
| `game/input.py` | touches → actions, menus |
| `game/render.py` | tout l'affichage curses |
| `game/save.py` | sauvegarde JSON |

La logique (`engine`, `procgen`, `fov`, `map`, `save`…) ne dépend jamais de
curses : elle est entièrement testable sans terminal.
