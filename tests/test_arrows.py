"""Tests du tir à l'arc (flèches avec w a s d)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from game.actions import FireAction, MoveAction, WaitAction
from game.engine import Engine
from game.entities import Actor, Projectile, make_goblin, make_orc, make_player
from game.input import Mode, UIState, handle_key
from game.map import FLOOR, WALL, GameMap
from game.save import engine_to_dict, load_game, save_game


def corridor(length: int = 12) -> GameMap:
    """Couloir horizontal : sol de x=1 à x=length, en y=1."""
    game_map = GameMap(length + 2, 3, fill=WALL)
    for x in range(1, length + 1):
        game_map.set_tile(x, 1, FLOOR)
    return game_map


def setup(monsters: list[Actor], length: int = 12) -> Engine:
    game_map = corridor(length)
    game_map.entities.extend(monsters)
    return Engine(game_map, make_player(1, 1), seed=0)


def arrows(engine: Engine) -> list[Projectile]:
    return engine.projectiles()


def hp(actor: Actor) -> int:
    assert actor.fighter is not None
    return actor.fighter.hp


class FireTests(unittest.TestCase):
    def test_arrow_moves_one_tile_per_turn(self) -> None:
        engine = setup([])
        engine.handle_action(FireAction(1, 0))
        (arrow,) = arrows(engine)
        self.assertEqual((arrow.x, arrow.y), (2, 1))  # case voisine après le tir
        engine.handle_action(WaitAction())
        self.assertEqual((arrow.x, arrow.y), (3, 1))
        engine.handle_action(MoveAction(0, 0))  # action sans effet : pas de tour
        self.assertEqual((arrow.x, arrow.y), (3, 1))
        engine.handle_action(WaitAction())
        self.assertEqual((arrow.x, arrow.y), (4, 1))

    def test_arrow_breaks_on_wall(self) -> None:
        engine = setup([], length=4)
        engine.handle_action(FireAction(1, 0))
        for _ in range(3):  # 2 → 3 → 4, puis le mur en x=5
            engine.handle_action(WaitAction())
        self.assertEqual(arrows(engine), [])

    def test_cannot_fire_into_adjacent_wall(self) -> None:
        gob = make_goblin(5, 1)
        engine = setup([gob])
        engine.handle_action(FireAction(0, -1))  # mur au-dessus
        self.assertEqual(arrows(engine), [])
        self.assertEqual((gob.x, gob.y), (5, 1))  # pas de tour consommé
        self.assertEqual(engine.log.messages[-1], "Un mur vous empêche de tirer par là.")

    def test_arrows_are_infinite(self) -> None:
        engine = setup([], length=60)
        for _ in range(40):
            engine.handle_action(FireAction(1, 0))
        self.assertEqual(len(arrows(engine)), 40)  # une flèche par case 2..41


class HitTests(unittest.TestCase):
    def test_adjacent_monster_hit_immediately(self) -> None:
        gob = make_goblin(2, 1)
        engine = setup([gob])
        engine.handle_action(FireAction(1, 0))
        self.assertEqual(hp(gob), 10 - 4)  # puissance 4 − défense 0
        self.assertEqual(arrows(engine), [])  # flèche consommée
        self.assertIn("Votre flèche touche le gobelin : 4 dégâts.", engine.log.messages)

    def test_arrow_hits_approaching_monster(self) -> None:
        # Tour 1 : flèche 2, gobelin 6→5. Tour 2 : flèche 3, gobelin 4.
        # Tour 3 : la flèche avance en 4 → touché.
        gob = make_goblin(6, 1)
        engine = setup([gob])
        engine.handle_action(FireAction(1, 0))
        engine.handle_action(WaitAction())
        self.assertEqual(hp(gob), 10)
        engine.handle_action(WaitAction())
        self.assertEqual(hp(gob), 6)

    def test_monster_cannot_cross_arrow(self) -> None:
        # Le gobelin marche SUR la flèche : il doit être touché, pas la croiser.
        # Tour 1 : flèche 2, gob 7→6. Tour 2 : flèche 3, gob 5.
        # Tour 3 : flèche 4, puis le gobelin avance en 4 → resolve_arrow_hits.
        gob = make_goblin(7, 1)
        engine = setup([gob])
        engine.handle_action(FireAction(1, 0))
        engine.handle_action(WaitAction())
        engine.handle_action(WaitAction())
        self.assertEqual(hp(gob), 6)
        self.assertEqual(arrows(engine), [])

    def test_defense_reduces_damage(self) -> None:
        orc = make_orc(2, 1)
        engine = setup([orc])
        engine.handle_action(FireAction(1, 0))
        self.assertEqual(hp(orc), 16 - (4 - 1))

    def test_arrow_kill_counts_and_leaves_corpse(self) -> None:
        gob = make_goblin(2, 1)
        engine = setup([gob])
        for _ in range(3):  # 4 + 4 + 4 ≥ 10 PV
            engine.handle_action(FireAction(1, 0))
        self.assertFalse(gob.is_alive)
        self.assertEqual(gob.char, "%")
        self.assertEqual(engine.kills, 1)

    def test_arrow_flies_over_corpse(self) -> None:
        gob = make_goblin(3, 1)
        engine = setup([gob])
        engine.kill(gob)
        engine.handle_action(FireAction(1, 0))
        engine.handle_action(WaitAction())
        engine.handle_action(WaitAction())
        (arrow,) = arrows(engine)
        self.assertEqual(arrow.x, 4)  # a traversé la case du cadavre


class InputTests(unittest.TestCase):
    def test_wasd_fire_on_map(self) -> None:
        engine = setup([])
        expected = {"w": (0, -1), "a": (-1, 0), "s": (0, 1), "d": (1, 0)}
        for key, (dx, dy) in expected.items():
            self.assertEqual(handle_key(ord(key), UIState(), engine), FireAction(dx, dy))

    def test_a_still_selects_item_in_inventory(self) -> None:
        engine = setup([])
        assert engine.player.inventory is not None
        from game.entities import make_health_potion

        engine.player.inventory.items.append(make_health_potion(0, 0))
        ui = UIState(mode=Mode.INVENTORY)
        self.assertIsNone(handle_key(ord("a"), ui, engine))
        self.assertIs(ui.mode, Mode.ITEM_MENU)


class SaveTests(unittest.TestCase):
    def test_arrow_in_flight_is_saved(self) -> None:
        engine = setup([make_goblin(9, 1)])
        engine.handle_action(FireAction(1, 0))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_game(engine, path)
            loaded = load_game(path)
        assert loaded is not None
        (arrow,) = arrows(loaded)
        self.assertEqual((arrow.x, arrow.y, arrow.dx, arrow.dy, arrow.char), (2, 1, 1, 0, "-"))
        # Et la suite se déroule pareil dans les deux parties.
        for _ in range(4):
            engine.handle_action(WaitAction())
            loaded.handle_action(WaitAction())
        a, b = engine_to_dict(engine), engine_to_dict(loaded)
        a.pop("log"), b.pop("log")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
