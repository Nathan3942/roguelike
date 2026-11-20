"""Tests des monstres et du tour par tour (M5)."""

from __future__ import annotations

import random
import unittest

from game.actions import MoveAction, WaitAction
from game.engine import Engine
from game.entities import Actor, make_goblin, make_player
from game.map import FLOOR, WALL, GameMap
from game.procgen import generate_dungeon


def map_from_text(lines: list[str]) -> GameMap:
    """'#' mur, tout le reste sol."""
    game_map = GameMap(len(lines[0]), len(lines), fill=WALL)
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            game_map.set_tile(x, y, WALL if char == "#" else FLOOR)
    return game_map


OPEN_ROOM = [
    "##############",
    "#............#",
    "#............#",
    "#............#",
    "##############",
]


def positions(game_map: GameMap) -> list[tuple[int, int]]:
    return [(e.x, e.y) for e in game_map.entities]


class PlacementTests(unittest.TestCase):
    def test_monsters_on_free_floor_no_overlap(self) -> None:
        for seed in range(100):
            with self.subTest(seed=seed):
                game_map, rooms = generate_dungeon(random.Random(seed))
                monsters = game_map.entities
                coords = positions(game_map)
                self.assertEqual(len(coords), len(set(coords)))  # pas de doublon
                for m in monsters:
                    self.assertTrue(game_map.is_walkable(m.x, m.y))
                    self.assertIn(m.char, ("g", "o"))
                    # Jamais dans la première salle (départ du joueur).
                    r = rooms[0]
                    self.assertFalse(r.x1 < m.x < r.x2 and r.y1 < m.y < r.y2)

    def test_dungeons_do_have_monsters(self) -> None:
        total = sum(len(generate_dungeon(random.Random(s))[0].entities) for s in range(20))
        self.assertGreater(total, 0)


class AITests(unittest.TestCase):
    def setup_engine(self, lines: list[str], player_pos: tuple[int, int],
                     monster_positions: list[tuple[int, int]]) -> tuple[Engine, list[Actor]]:
        game_map = map_from_text(lines)
        monsters = [make_goblin(x, y) for x, y in monster_positions]
        game_map.entities.extend(monsters)
        engine = Engine(game_map, make_player(*player_pos), seed=0)
        return engine, monsters

    def test_visible_monster_approaches(self) -> None:
        # Distance 7 : dans le rayon de vision (8).
        engine, (gob,) = self.setup_engine(OPEN_ROOM, (1, 2), [(8, 2)])
        engine.handle_action(WaitAction())
        self.assertEqual((gob.x, gob.y), (7, 2))

    def test_monster_out_of_sight_waits(self) -> None:
        lines = [
            "##############",
            "#.....#......#",
            "#.....#......#",
            "##############",
        ]
        engine, (gob,) = self.setup_engine(lines, (1, 1), [(10, 1)])
        engine.handle_action(WaitAction())
        self.assertEqual((gob.x, gob.y), (10, 1))

    def test_monster_stops_next_to_player(self) -> None:
        engine, (gob,) = self.setup_engine(OPEN_ROOM, (1, 2), [(5, 2)])
        for _ in range(10):
            engine.handle_action(WaitAction())
        self.assertEqual((gob.x, gob.y), (2, 2))  # au contact, pas dessus

    def test_monsters_never_overlap(self) -> None:
        # Couloir de largeur 1 : trois gobelins en file indienne.
        lines = ["#" * 14, "#" + "." * 12 + "#", "#" * 14]
        engine, gobs = self.setup_engine(lines, (1, 1), [(6, 1), (7, 1), (8, 1)])
        for _ in range(10):
            engine.handle_action(WaitAction())
            coords = positions(engine.game_map)
            self.assertEqual(len(coords), len(set(coords)))
        self.assertEqual(sorted(g.x for g in gobs), [2, 3, 4])

    def test_monster_does_not_cross_walls(self) -> None:
        engine, gobs = self.setup_engine(OPEN_ROOM, (6, 2), [(1, 1), (12, 3)])
        for _ in range(10):
            engine.handle_action(WaitAction())
            for g in gobs:
                self.assertTrue(engine.game_map.is_walkable(g.x, g.y))

    def test_monsters_only_move_when_player_acts(self) -> None:
        engine, (gob,) = self.setup_engine(OPEN_ROOM, (1, 2), [(8, 2)])
        # Foncer dans le mur ne coûte pas de tour : le gobelin ne bouge pas.
        engine.handle_action(MoveAction(-1, 0))
        self.assertEqual((gob.x, gob.y), (8, 2))
        # Un vrai pas (vers le bas) : le gobelin avance en diagonale vers (1, 3).
        engine.handle_action(MoveAction(0, 1))
        self.assertEqual((gob.x, gob.y), (7, 3))

    def test_player_blocked_by_monster(self) -> None:
        engine, _ = self.setup_engine(OPEN_ROOM, (1, 2), [(2, 2)])
        self.assertFalse(engine.move_player(1, 0))
        self.assertEqual((engine.player.x, engine.player.y), (1, 2))


if __name__ == "__main__":
    unittest.main()
