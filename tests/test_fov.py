"""Tests du champ de vision (M4)."""

from __future__ import annotations

import unittest

from game.actions import MoveAction
from game.engine import Engine
from game.entities import Entity
from game.fov import bresenham_line, compute_fov, wall_touches_floor
from game.map import FLOOR, WALL, GameMap


def map_from_text(lines: list[str]) -> GameMap:
    """Construit une carte depuis du texte : '#' mur, tout le reste sol."""
    game_map = GameMap(len(lines[0]), len(lines), fill=WALL)
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            game_map.set_tile(x, y, WALL if char == "#" else FLOOR)
    return game_map


# Deux pièces séparées par un mur plein en x=10.
TWO_ROOMS = [
    "#####################",
    "#.........#.........#",
    "#.........#.........#",
    "#.........#.........#",
    "#####################",
]


class BresenhamTests(unittest.TestCase):
    def test_endpoints_included(self) -> None:
        line = list(bresenham_line(0, 0, 5, 2))
        self.assertEqual(line[0], (0, 0))
        self.assertEqual(line[-1], (5, 2))

    def test_line_is_contiguous(self) -> None:
        # Chaque case est voisine (8 directions) de la précédente.
        line = list(bresenham_line(3, 7, -4, 1))
        for (ax, ay), (bx, by) in zip(line, line[1:]):
            self.assertLessEqual(max(abs(ax - bx), abs(ay - by)), 1)


class FovTests(unittest.TestCase):
    def test_origin_is_visible(self) -> None:
        game_map = map_from_text(TWO_ROOMS)
        self.assertIn((2, 2), compute_fov(game_map, 2, 2, radius=8))

    def test_wall_blocks_view(self) -> None:
        game_map = map_from_text(TWO_ROOMS)
        visible = compute_fov(game_map, 8, 2, radius=8)
        self.assertIn((10, 2), visible)  # on voit le mur…
        self.assertNotIn((12, 2), visible)  # …mais pas derrière
        self.assertNotIn((11, 1), visible)

    def test_radius_limits_view(self) -> None:
        game_map = GameMap(41, 41, fill=FLOOR)  # grande salle vide
        visible = compute_fov(game_map, 20, 20, radius=8)
        self.assertIn((28, 20), visible)  # à distance 8
        self.assertNotIn((29, 20), visible)  # à distance 9

    def test_room_walls_fully_visible(self) -> None:
        # Debout dans une pièce, on doit voir tout son contour proche,
        # y compris les murs qu'on « longe » (le défaut corrigé par l'étape 3).
        game_map = map_from_text(TWO_ROOMS)
        visible = compute_fov(game_map, 1, 1, radius=8)
        for x in range(0, 9):
            self.assertIn((x, 0), visible, f"mur du haut en x={x}")


    def test_diagonal_wall_lit_only_at_corners(self) -> None:
        game_map = map_from_text(
            [
                "###",
                "#..",  # (1, 1) sol ; (2, 1) sol
                "#.#",  # (1, 2) sol ; (2, 2) mur
            ]
        )
        # (0, 0) est un vrai coin de (1, 1) : (1, 0) et (0, 1) sont des murs.
        self.assertTrue(wall_touches_floor(game_map, 1, 1, -1, -1))
        # (2, 2) touche (1, 1) en diagonale, mais (2, 1) entre eux est du sol.
        self.assertFalse(wall_touches_floor(game_map, 1, 1, 1, 1))


class ExplorationTests(unittest.TestCase):
    def test_exploration_is_remembered(self) -> None:
        # Long couloir horizontal de 30 cases.
        game_map = map_from_text(["#" * 32, "#" + "." * 30 + "#", "#" * 32])
        engine = Engine(game_map, Entity(1, 1, "@", "Joueur"), seed=0)
        self.assertIn((2, 1), game_map.visible)

        # On s'éloigne de 20 cases : (2, 1) sort du rayon de vision (8)…
        for _ in range(20):
            engine.handle_action(MoveAction(1, 0))

        self.assertEqual(engine.player.x, 21)
        self.assertNotIn((2, 1), game_map.visible)
        self.assertIn((2, 1), game_map.explored)  # …mais reste mémorisé

    def test_visible_subset_of_explored(self) -> None:
        game_map = map_from_text(TWO_ROOMS)
        Engine(game_map, Entity(5, 2, "@", "Joueur"), seed=0)
        self.assertTrue(game_map.visible <= game_map.explored)


if __name__ == "__main__":
    unittest.main()
