"""Tests des collisions (M2). Lancement : python3 -m unittest discover tests"""

from __future__ import annotations

import unittest

from game.engine import Engine
from game.entities import Entity
from game.map import FLOOR, WALL, GameMap


def make_engine() -> Engine:
    """Petite carte 5×5 : murs partout, sol en (1..3, 1..3), mur en (2, 1)."""
    game_map = GameMap(5, 5, fill=WALL)
    for y in range(1, 4):
        for x in range(1, 4):
            game_map.set_tile(x, y, FLOOR)
    game_map.set_tile(2, 1, WALL)
    player = Entity(x=1, y=1, char="@", name="Joueur")
    return Engine(game_map, player, seed=0)


class CollisionTests(unittest.TestCase):
    def test_move_on_floor(self) -> None:
        engine = make_engine()
        self.assertTrue(engine.move_player(0, 1))
        self.assertEqual((engine.player.x, engine.player.y), (1, 2))

    def test_wall_blocks(self) -> None:
        engine = make_engine()
        self.assertFalse(engine.move_player(1, 0))  # mur intérieur en (2, 1)
        self.assertFalse(engine.move_player(-1, 0))  # mur extérieur
        self.assertEqual((engine.player.x, engine.player.y), (1, 1))

    def test_out_of_bounds_is_not_walkable(self) -> None:
        game_map = GameMap(3, 3, fill=FLOOR)
        self.assertFalse(game_map.is_walkable(-1, 0))
        self.assertFalse(game_map.is_walkable(3, 0))


if __name__ == "__main__":
    unittest.main()
