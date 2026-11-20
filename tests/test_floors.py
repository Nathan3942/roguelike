"""Tests des étages et de la difficulté (M8)."""

from __future__ import annotations

import unittest

from game.actions import DescendAction, PickupAction
from game.engine import Engine
from game.entities import Actor, make_health_potion, make_player
from game.map import STAIRS, GameMap
from game.procgen import Difficulty, generate_floor


def new_engine(seed: int = 42) -> Engine:
    game_map, rooms = generate_floor(seed, depth=1)
    return Engine(game_map, make_player(*rooms[0].center), seed)


def stairs_positions(game_map: GameMap) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(game_map.height)
        for x in range(game_map.width)
        if game_map.get_tile(x, y) is STAIRS
    ]


def go_to_stairs(engine: Engine) -> None:
    """Téléporte le joueur sur l'escalier (raccourci de test)."""
    (x, y), = stairs_positions(engine.game_map)
    engine.player.x, engine.player.y = x, y


def monsters(game_map: GameMap) -> list[Actor]:
    return [e for e in game_map.entities if isinstance(e, Actor) and e.ai is not None]


def average_max_hp(actors: list[Actor]) -> float:
    return sum(a.fighter.max_hp for a in actors if a.fighter) / len(actors)


class StairsTests(unittest.TestCase):
    def test_exactly_one_stairs_in_last_room(self) -> None:
        for seed in range(50):
            with self.subTest(seed=seed):
                game_map, rooms = generate_floor(seed, 1)
                self.assertEqual(stairs_positions(game_map), [rooms[-1].center])

    def test_descend_refused_off_stairs(self) -> None:
        engine = new_engine()
        old_map = engine.game_map
        engine.handle_action(DescendAction())
        self.assertEqual(engine.depth, 1)
        self.assertIs(engine.game_map, old_map)
        self.assertEqual(engine.log.messages[-1], "Il n'y a pas d'escalier ici.")


class DescendTests(unittest.TestCase):
    def test_new_floor_keeps_player_hp_and_inventory(self) -> None:
        engine = new_engine()
        player = engine.player
        assert player.fighter is not None and player.inventory is not None
        player.fighter.hp = 17
        engine.game_map.entities.append(make_health_potion(player.x, player.y))
        engine.handle_action(PickupAction())
        old_map = engine.game_map

        go_to_stairs(engine)
        engine.handle_action(DescendAction())

        self.assertEqual(engine.depth, 2)
        self.assertIsNot(engine.game_map, old_map)
        self.assertIs(engine.player, player)  # le MÊME objet joueur
        self.assertEqual(player.fighter.hp, 17)
        self.assertEqual([i.name for i in player.inventory.items], ["potion de soin"])
        self.assertEqual(engine.log.messages[-1], "Vous descendez au niveau 2.")

    def test_player_placed_in_first_room_of_new_floor(self) -> None:
        engine = new_engine()
        go_to_stairs(engine)
        engine.handle_action(DescendAction())
        _, rooms = generate_floor(engine.seed, 2)
        self.assertEqual((engine.player.x, engine.player.y), rooms[0].center)
        # Le joueur est sur la nouvelle carte, une seule fois.
        self.assertEqual(engine.game_map.entities.count(engine.player), 1)
        # Et il voit autour de lui dès l'arrivée.
        self.assertIn((engine.player.x, engine.player.y), engine.game_map.visible)

    def test_exploration_resets_on_new_floor(self) -> None:
        engine = new_engine()
        go_to_stairs(engine)
        engine.update_fov()
        explored_before = len(engine.game_map.explored)
        engine.handle_action(DescendAction())
        self.assertGreater(explored_before, 0)
        self.assertEqual(engine.game_map.explored, engine.game_map.visible)

    def test_descend_several_times(self) -> None:
        engine = new_engine()
        for expected_depth in range(2, 7):
            go_to_stairs(engine)
            engine.handle_action(DescendAction())
            self.assertEqual(engine.depth, expected_depth)


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_floor(self) -> None:
        a, _ = generate_floor(7, 3)
        b, _ = generate_floor(7, 3)
        self.assertEqual(a.tiles, b.tiles)
        self.assertEqual(
            [(e.x, e.y, e.char) for e in a.entities], [(e.x, e.y, e.char) for e in b.entities]
        )

    def test_floors_differ(self) -> None:
        a, _ = generate_floor(7, 1)
        b, _ = generate_floor(7, 2)
        self.assertNotEqual(a.tiles, b.tiles)


class DifficultyTests(unittest.TestCase):
    def test_first_floor_matches_previous_settings(self) -> None:
        self.assertEqual(Difficulty.for_depth(1), Difficulty(2, 0.2, 0, 0))

    def test_difficulty_never_decreases(self) -> None:
        for depth in range(1, 20):
            easier, harder = Difficulty.for_depth(depth), Difficulty.for_depth(depth + 1)
            self.assertLessEqual(easier.max_monsters, harder.max_monsters)
            self.assertLessEqual(easier.orc_chance, harder.orc_chance)
            self.assertLess(easier.bonus_hp, harder.bonus_hp)
            self.assertLessEqual(easier.bonus_attack, harder.bonus_attack)

    def test_deeper_monsters_are_stronger(self) -> None:
        shallow = [m for s in range(10) for m in monsters(generate_floor(s, 1)[0])]
        deep = [m for s in range(10) for m in monsters(generate_floor(s, 6)[0])]
        self.assertGreater(len(deep), len(shallow))  # plus nombreux
        self.assertGreater(average_max_hp(deep), average_max_hp(shallow))  # plus costauds


if __name__ == "__main__":
    unittest.main()
