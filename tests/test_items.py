"""Tests des objets, de l'inventaire et des menus (M7)."""

from __future__ import annotations

import random
import unittest

from game.actions import DropItemAction, PickupAction, UseItemAction
from game.engine import Engine
from game.entities import Actor, Item, make_goblin, make_health_potion, make_player
from game.input import ESCAPE_KEY, Mode, UIState, handle_key
from game.map import FLOOR, WALL, GameMap
from game.procgen import generate_dungeon


def setup(entities: list | None = None) -> Engine:
    """Pièce 12×3 ; joueur en (1, 2)."""
    game_map = GameMap(14, 5, fill=WALL)
    for y in range(1, 4):
        for x in range(1, 13):
            game_map.set_tile(x, y, FLOOR)
    game_map.entities.extend(entities or [])
    return Engine(game_map, make_player(1, 2), seed=0)


def hp(engine: Engine) -> int:
    assert engine.player.fighter is not None
    return engine.player.fighter.hp


def bag(engine: Engine) -> list[Item]:
    assert engine.player.inventory is not None
    return engine.player.inventory.items


class PickupTests(unittest.TestCase):
    def test_pickup_moves_item_from_map_to_bag(self) -> None:
        potion = make_health_potion(1, 2)
        engine = setup([potion])
        engine.handle_action(PickupAction())
        self.assertEqual(bag(engine), [potion])
        self.assertNotIn(potion, engine.game_map.entities)

    def test_pickup_nothing(self) -> None:
        gob = make_goblin(5, 2)
        engine = setup([gob])
        engine.handle_action(PickupAction())
        self.assertEqual(bag(engine), [])
        self.assertEqual(engine.log.messages[-1], "Il n'y a rien à ramasser ici.")
        self.assertEqual((gob.x, gob.y), (5, 2))  # pas de tour consommé

    def test_full_inventory(self) -> None:
        potions = [make_health_potion(1, 2) for _ in range(11)]
        engine = setup(potions)
        for _ in range(11):
            engine.handle_action(PickupAction())
        self.assertEqual(len(bag(engine)), 10)
        self.assertEqual(engine.log.messages[-1], "Votre sac est plein.")
        # La 11e potion est restée au sol, pas perdue.
        self.assertEqual(len(engine.items_at(1, 2)), 1)


class UseTests(unittest.TestCase):
    def test_heal_does_not_exceed_max_hp(self) -> None:
        engine = setup([make_health_potion(1, 2)])
        engine.handle_action(PickupAction())
        assert engine.player.fighter is not None
        engine.player.fighter.hp = 25  # potion = +10, max 30
        engine.handle_action(UseItemAction(0))
        self.assertEqual(hp(engine), 30)
        self.assertEqual(engine.log.messages[-1], "Vous buvez la potion : +5 PV.")
        self.assertEqual(bag(engine), [])

    def test_potion_refused_at_full_hp(self) -> None:
        engine = setup([make_health_potion(1, 2)])
        engine.handle_action(PickupAction())
        engine.handle_action(UseItemAction(0))
        self.assertEqual(len(bag(engine)), 1)  # pas gaspillée
        self.assertEqual(engine.log.messages[-1], "Vous êtes déjà en pleine santé.")

    def test_using_item_takes_a_turn(self) -> None:
        gob = make_goblin(6, 2)
        engine = setup([gob])
        bag(engine).append(make_health_potion(0, 0))
        assert engine.player.fighter is not None
        engine.player.fighter.hp = 10
        engine.handle_action(UseItemAction(0))
        self.assertEqual((gob.x, gob.y), (5, 2))  # le gobelin a joué

    def test_invalid_index_is_ignored(self) -> None:
        engine = setup()
        engine.handle_action(UseItemAction(3))
        engine.handle_action(DropItemAction(3))
        self.assertEqual(bag(engine), [])


class DropTests(unittest.TestCase):
    def test_drop_puts_item_under_player(self) -> None:
        engine = setup([make_health_potion(1, 2)])
        engine.handle_action(PickupAction())
        engine.player.x = 4
        engine.handle_action(DropItemAction(0))
        self.assertEqual(bag(engine), [])
        self.assertEqual([(i.x, i.y) for i in engine.items_at(4, 2)], [(4, 2)])


class PlacementTests(unittest.TestCase):
    def test_items_placed_on_floor_alone(self) -> None:
        for seed in range(100):
            with self.subTest(seed=seed):
                game_map, _ = generate_dungeon(random.Random(seed))
                coords = [(e.x, e.y) for e in game_map.entities]
                self.assertEqual(len(coords), len(set(coords)))
                for item in game_map.entities:
                    if isinstance(item, Item):
                        self.assertTrue(game_map.is_walkable(item.x, item.y))

    def test_some_dungeons_have_potions(self) -> None:
        count = sum(
            isinstance(e, Item) for s in range(20) for e in generate_dungeon(random.Random(s))[0].entities
        )
        self.assertGreater(count, 0)

    def test_monsters_unchanged_by_items(self) -> None:
        # Les objets sont tirés APRÈS les monstres : ceux-ci ne changent pas.
        game_map, _ = generate_dungeon(random.Random(42), max_items_per_room=0)
        with_items, _ = generate_dungeon(random.Random(42))
        monsters = [(e.x, e.y, e.char) for e in game_map.entities if isinstance(e, Actor)]
        monsters2 = [(e.x, e.y, e.char) for e in with_items.entities if isinstance(e, Actor)]
        self.assertEqual(monsters, monsters2)


class MenuTests(unittest.TestCase):
    def test_inventory_flow_use(self) -> None:
        engine = setup()
        bag(engine).append(make_health_potion(0, 0))
        ui = UIState()
        self.assertIsNone(handle_key(ord("i"), ui, engine))
        self.assertIs(ui.mode, Mode.INVENTORY)
        self.assertIsNone(handle_key(ord("a"), ui, engine))
        self.assertIs(ui.mode, Mode.ITEM_MENU)
        self.assertEqual(handle_key(ord("u"), ui, engine), UseItemAction(0))
        self.assertIs(ui.mode, Mode.MAP)

    def test_inventory_flow_drop_with_j(self) -> None:
        engine = setup()
        bag(engine).append(make_health_potion(0, 0))
        ui = UIState(mode=Mode.ITEM_MENU, selected=0)
        # « j » = jeter dans le menu (et non « descendre » comme sur la carte).
        self.assertEqual(handle_key(ord("j"), ui, engine), DropItemAction(0))

    def test_letter_out_of_range_ignored(self) -> None:
        engine = setup()
        ui = UIState(mode=Mode.INVENTORY)
        self.assertIsNone(handle_key(ord("c"), ui, engine))
        self.assertIs(ui.mode, Mode.INVENTORY)

    def test_escape_goes_back(self) -> None:
        engine = setup()
        ui = UIState(mode=Mode.ITEM_MENU)
        handle_key(ESCAPE_KEY, ui, engine)
        self.assertIs(ui.mode, Mode.INVENTORY)
        handle_key(ESCAPE_KEY, ui, engine)
        self.assertIs(ui.mode, Mode.MAP)

    def test_q_in_menu_closes_but_does_not_quit(self) -> None:
        engine = setup()
        ui = UIState(mode=Mode.INVENTORY)
        self.assertIsNone(handle_key(ord("q"), ui, engine))
        self.assertIs(ui.mode, Mode.MAP)
        self.assertTrue(engine.running)


if __name__ == "__main__":
    unittest.main()
