"""Génération procédurale du donjon.

Algorithme (classique, simple à suivre) :
  1. On part d'une carte remplie de murs.
  2. On essaie `max_rooms` fois de poser une salle rectangulaire de taille et de
     position aléatoires. Si elle chevauche une salle déjà posée, on l'abandonne.
  3. Chaque nouvelle salle acceptée est reliée à la PRÉCÉDENTE par un couloir
     en L. Les salles forment ainsi une chaîne 1 → 2 → 3 → … : toutes sont
     forcément connectées (c'est ce que vérifie le test unitaire).
  4. Une fois TOUTES les salles creusées, on place les monstres (sauf dans la
     première salle, où démarre le joueur). Les faire après garde les mêmes
     tirages pour la forme du donjon : une seed donne le même plan qu'en M3.

Reproductibilité : tout le hasard passe par un objet random.Random(seed)
qu'on reçoit en paramètre (jamais le module `random` global). Même seed →
mêmes tirages, dans le même ordre → même donjon.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass

from game.entities import make_goblin, make_orc
from game.map import FLOOR, WALL, GameMap

MAP_WIDTH = 80
MAP_HEIGHT = 40
MAX_ROOMS = 30
ROOM_MIN_SIZE = 6
ROOM_MAX_SIZE = 12
MAX_MONSTERS_PER_ROOM = 2
ORC_CHANCE = 0.2  # 20 % d'orcs, 80 % de gobelins


@dataclass(frozen=True)
class RectangularRoom:
    """Salle rectangulaire, murs compris : coins (x1, y1) et (x2, y2) inclus.

    Le SOL est l'intérieur (sans le contour), donc deux salles qui ne se
    chevauchent pas ont toujours au moins un mur entre elles.
    """

    x1: int
    y1: int
    x2: int
    y2: int

    @classmethod
    def from_size(cls, x: int, y: int, width: int, height: int) -> RectangularRoom:
        return cls(x, y, x + width - 1, y + height - 1)

    @property
    def center(self) -> tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    def inner_tiles(self) -> Iterator[tuple[int, int]]:
        """Toutes les cases (x, y) de l'intérieur de la salle (sans les murs)."""
        for y in range(self.y1 + 1, self.y2):
            for x in range(self.x1 + 1, self.x2):
                yield x, y

    def intersects(self, other: RectangularRoom) -> bool:
        """Vrai si les deux rectangles se touchent ou se chevauchent.

        Deux rectangles NE se chevauchent PAS si l'un est entièrement à gauche,
        à droite, au-dessus ou en dessous de l'autre. On teste l'inverse.
        `<=` (et non `<`) : partager un mur compte comme un chevauchement.
        """
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )


def l_tunnel(
    start: tuple[int, int], end: tuple[int, int], rng: random.Random
) -> Iterator[tuple[int, int]]:
    """Cases d'un couloir en L de start à end.

    On choisit au hasard de partir d'abord à l'horizontale ou à la verticale.
    Le « coude » du L est donc soit (end_x, start_y), soit (start_x, end_y) :

        start ─────┐          start
                   │            │
                  end           └───── end
    """
    (x1, y1), (x2, y2) = start, end
    if rng.random() < 0.5:
        corner = (x2, y1)  # horizontal puis vertical
    else:
        corner = (x1, y2)  # vertical puis horizontal

    yield from straight_line(start, corner)
    yield from straight_line(corner, end)


def straight_line(start: tuple[int, int], end: tuple[int, int]) -> Iterator[tuple[int, int]]:
    """Cases d'un segment horizontal OU vertical, extrémités comprises."""
    (x1, y1), (x2, y2) = start, end
    step_x = 1 if x2 >= x1 else -1
    step_y = 1 if y2 >= y1 else -1
    # Un des deux range ne contient qu'une seule valeur (segment droit).
    for x in range(x1, x2 + step_x, step_x):
        for y in range(y1, y2 + step_y, step_y):
            yield x, y


def generate_dungeon(
    rng: random.Random,
    map_width: int = MAP_WIDTH,
    map_height: int = MAP_HEIGHT,
    max_rooms: int = MAX_ROOMS,
    room_min_size: int = ROOM_MIN_SIZE,
    room_max_size: int = ROOM_MAX_SIZE,
    max_monsters_per_room: int = MAX_MONSTERS_PER_ROOM,
) -> tuple[GameMap, list[RectangularRoom]]:
    """Crée un donjon. Retourne la carte et la liste des salles (dans l'ordre).

    Le joueur commencera au centre de rooms[0].
    """
    game_map = GameMap(map_width, map_height, fill=WALL)
    rooms: list[RectangularRoom] = []

    for _ in range(max_rooms):
        width = rng.randint(room_min_size, room_max_size)
        height = rng.randint(room_min_size, room_max_size)
        # Position telle que la salle reste entièrement dans la carte.
        x = rng.randint(0, map_width - width)
        y = rng.randint(0, map_height - height)
        new_room = RectangularRoom.from_size(x, y, width, height)

        # any() s'arrête au premier chevauchement trouvé.
        if any(new_room.intersects(other) for other in rooms):
            continue  # salle rejetée, on tente la suivante

        for tx, ty in new_room.inner_tiles():
            game_map.set_tile(tx, ty, FLOOR)

        if rooms:
            # Relie cette salle à la précédente (centre à centre).
            for tx, ty in l_tunnel(rooms[-1].center, new_room.center, rng):
                game_map.set_tile(tx, ty, FLOOR)

        rooms.append(new_room)

    # rooms[1:] : la première salle (départ du joueur) reste sans monstre.
    for room in rooms[1:]:
        place_monsters(game_map, room, rng, max_monsters_per_room)

    return game_map, rooms


def place_monsters(
    game_map: GameMap, room: RectangularRoom, rng: random.Random, max_monsters: int
) -> None:
    """Place entre 0 et max_monsters monstres sur des cases libres de la salle."""
    count = rng.randint(0, max_monsters)
    for _ in range(count):
        x = rng.randint(room.x1 + 1, room.x2 - 1)
        y = rng.randint(room.y1 + 1, room.y2 - 1)
        if not game_map.is_free(x, y):
            continue  # case déjà prise : on renonce à ce monstre (plus simple)
        if rng.random() < ORC_CHANCE:
            monster = make_orc(x, y)
        else:
            monster = make_goblin(x, y)
        game_map.entities.append(monster)
