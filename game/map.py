"""La carte du donjon : une grille 2D de tuiles, plus ce que le joueur en voit."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tile:
    """Un type de case. frozen=True : une tuile ne change jamais, on la partage.

    char        : caractère affiché à l'écran
    walkable    : peut-on marcher dessus ?
    transparent : la lumière (le regard) passe-t-elle à travers ?
    """

    char: str
    walkable: bool
    transparent: bool


# Les deux tuiles du jeu pour l'instant. Toutes les cases « mur » de la carte
# pointent vers le MÊME objet WALL : pas de copie, économie de mémoire.
WALL = Tile(char="#", walkable=False, transparent=False)
FLOOR = Tile(char=".", walkable=True, transparent=True)


class GameMap:
    """Grille de tuiles de taille fixe (indépendante de la taille du terminal).

    Stockage : self.tiles[y][x] → une liste par LIGNE, comme l'écran.
    Utilise plutôt get_tile() / set_tile() qui prennent (x, y) dans le bon ordre.

    Vision du joueur (M4) — chaque case est dans l'un de trois états :
      - visible  : dans `visible` (vue en ce moment) ;
      - explorée : dans `explored` mais pas dans `visible` (vue autrefois) ;
      - inconnue : dans aucun des deux (jamais vue → rien à l'écran).
    `visible` est toujours inclus dans `explored`.
    """

    def __init__(self, width: int, height: int, fill: Tile = WALL) -> None:
        self.width = width
        self.height = height
        # Attention au piège : [[fill] * width] * height créerait `height` fois
        # la MÊME liste. La compréhension crée bien une liste par ligne.
        self.tiles: list[list[Tile]] = [[fill] * width for _ in range(height)]
        self.visible: set[tuple[int, int]] = set()
        self.explored: set[tuple[int, int]] = set()

    def in_bounds(self, x: int, y: int) -> bool:
        """La case (x, y) est-elle dans la carte ?"""
        return 0 <= x < self.width and 0 <= y < self.height

    def get_tile(self, x: int, y: int) -> Tile:
        return self.tiles[y][x]

    def set_tile(self, x: int, y: int, tile: Tile) -> None:
        self.tiles[y][x] = tile

    def is_walkable(self, x: int, y: int) -> bool:
        """Vrai si on peut marcher en (x, y). Hors carte = jamais."""
        return self.in_bounds(x, y) and self.get_tile(x, y).walkable

    def is_transparent(self, x: int, y: int) -> bool:
        """Vrai si le regard traverse (x, y). Hors carte = opaque."""
        return self.in_bounds(x, y) and self.get_tile(x, y).transparent
