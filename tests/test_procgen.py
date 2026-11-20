"""Tests de la génération procédurale (M3)."""

from __future__ import annotations

import random
import unittest
from collections import deque

from game.map import GameMap
from game.procgen import RectangularRoom, generate_dungeon

SEEDS = range(100)  # on teste beaucoup de donjons, pas un seul


def reachable_from(game_map: GameMap, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Parcours en largeur (BFS) : toutes les cases praticables atteignables.

    On part de `start`, on visite ses 4 voisins praticables, puis leurs voisins,
    etc. Une file (deque) garde les cases « à visiter » ; un ensemble `seen`
    évite de visiter deux fois la même case. 4 directions seulement (pas de
    diagonales) : c'est plus strict que le jeu, donc si ça passe ici, ça passe.
    """
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (x + dx, y + dy)
            if neighbor not in seen and game_map.is_walkable(*neighbor):
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def map_as_text(game_map: GameMap) -> str:
    return "\n".join("".join(t.char for t in row) for row in game_map.tiles)


class ProcgenTests(unittest.TestCase):
    def test_all_rooms_connected(self) -> None:
        for seed in SEEDS:
            with self.subTest(seed=seed):
                game_map, rooms = generate_dungeon(random.Random(seed))
                reachable = reachable_from(game_map, rooms[0].center)
                for room in rooms:
                    self.assertIn(room.center, reachable)
                # Plus fort : TOUT le sol de la carte est atteignable.
                floor = {
                    (x, y)
                    for y in range(game_map.height)
                    for x in range(game_map.width)
                    if game_map.is_walkable(x, y)
                }
                self.assertEqual(floor, reachable)

    def test_rooms_do_not_overlap(self) -> None:
        for seed in SEEDS:
            with self.subTest(seed=seed):
                _, rooms = generate_dungeon(random.Random(seed))
                for i, a in enumerate(rooms):
                    for b in rooms[i + 1 :]:
                        self.assertFalse(a.intersects(b))

    def test_rooms_inside_map(self) -> None:
        for seed in SEEDS:
            with self.subTest(seed=seed):
                game_map, rooms = generate_dungeon(random.Random(seed))
                self.assertGreaterEqual(len(rooms), 2)
                for room in rooms:
                    self.assertTrue(game_map.in_bounds(room.x1, room.y1))
                    self.assertTrue(game_map.in_bounds(room.x2, room.y2))

    def test_same_seed_same_dungeon(self) -> None:
        map_a, _ = generate_dungeon(random.Random(42))
        map_b, _ = generate_dungeon(random.Random(42))
        self.assertEqual(map_as_text(map_a), map_as_text(map_b))

    def test_different_seeds_different_dungeons(self) -> None:
        map_a, _ = generate_dungeon(random.Random(1))
        map_b, _ = generate_dungeon(random.Random(2))
        self.assertNotEqual(map_as_text(map_a), map_as_text(map_b))

    def test_intersects(self) -> None:
        a = RectangularRoom(0, 0, 5, 5)
        self.assertTrue(a.intersects(RectangularRoom(5, 0, 9, 5)))  # mur partagé
        self.assertFalse(a.intersects(RectangularRoom(6, 0, 9, 5)))  # côte à côte


if __name__ == "__main__":
    unittest.main()
