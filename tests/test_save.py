"""Tests de la sauvegarde (M9). Tout se passe dans un dossier temporaire :
la vraie sauvegarde (~/.roguelike/save.json) n'est jamais touchée."""

from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path

from game.actions import Action, DescendAction, MoveAction, PickupAction, UseItemAction, WaitAction
from game.engine import Engine
from game.entities import Actor, Item, make_health_potion, make_player
from game.map import STAIRS
from game.procgen import generate_floor
from game.save import delete_save, engine_to_dict, load_game, save_exists, save_game


def new_engine(seed: int) -> Engine:
    game_map, rooms = generate_floor(seed, 1)
    return Engine(game_map, make_player(*rooms[0].center), seed)


def random_actions(rng: random.Random, count: int) -> list[Action]:
    """Une suite d'actions de joueur (déplacements surtout)."""
    directions = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    actions: list[Action] = []
    for _ in range(count):
        roll = rng.random()
        if roll < 0.8:
            actions.append(MoveAction(*rng.choice(directions)))
        elif roll < 0.9:
            actions.append(PickupAction())
        elif roll < 0.95:
            actions.append(UseItemAction(0))
        else:
            actions.append(WaitAction())
    return actions


def played_engine(seed: int) -> Engine:
    """Une partie « vécue » : un potion en poche, un étage descendu, des
    monstres qui ont bougé, des cases explorées."""
    engine = new_engine(seed)
    player = engine.player
    engine.game_map.entities.append(make_health_potion(player.x, player.y))
    engine.handle_action(PickupAction())
    # Descente directe par l'escalier.
    m = engine.game_map
    player.x, player.y = next(
        (x, y) for y in range(m.height) for x in range(m.width) if m.get_tile(x, y) is STAIRS
    )
    engine.handle_action(DescendAction())
    for action in random_actions(random.Random(seed), 60):
        if engine.game_over:
            break
        engine.handle_action(action)
    return engine


class SaveTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Dossier temporaire supprimé automatiquement après chaque test.
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sous-dossier" / "save.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()


class RoundTripTests(SaveTestCase):
    def test_save_then_load_restores_everything(self) -> None:
        for seed in range(5):
            with self.subTest(seed=seed):
                engine = played_engine(seed)
                save_game(engine, self.path)
                loaded = load_game(self.path)
                assert loaded is not None

                before, after = engine_to_dict(engine), engine_to_dict(loaded)
                after["log"] = after["log"][:-1]  # sans « Partie reprise. »
                self.assertEqual(before, after)
                # Ce qu'on ne sauve pas mais qu'on recalcule :
                self.assertEqual(loaded.game_map.visible, engine.game_map.visible)

    def test_loaded_objects_have_right_types_and_links(self) -> None:
        engine = played_engine(3)
        save_game(engine, self.path)
        loaded = load_game(self.path)
        assert loaded is not None
        self.assertIn(loaded.player, loaded.game_map.entities)
        self.assertEqual(loaded.depth, 2)
        assert loaded.player.inventory is not None
        for item in loaded.player.inventory.items:
            self.assertIsInstance(item, Item)
        # La tuile escalier rechargée est bien l'objet partagé STAIRS.
        m = loaded.game_map
        self.assertTrue(any(m.get_tile(x, y) is STAIRS for y in range(m.height) for x in range(m.width)))
        monsters = [e for e in m.entities if isinstance(e, Actor) and e.ai is not None]
        self.assertTrue(all(mon.fighter is not None for mon in monsters))

    def test_game_continues_identically_after_reload(self) -> None:
        # Le test le plus fort : on joue la MÊME suite d'actions sur la partie
        # d'origine et sur la partie rechargée. Si un détail manquait dans la
        # sauvegarde (ordre des monstres, PV…), les deux finiraient différentes.
        engine = played_engine(7)
        save_game(engine, self.path)
        loaded = load_game(self.path)
        assert loaded is not None
        for action in random_actions(random.Random(99), 100):
            engine.handle_action(action)
            loaded.handle_action(action)
        a, b = engine_to_dict(engine), engine_to_dict(loaded)
        a.pop("log"), b.pop("log")
        self.assertEqual(a, b)


class FileTests(SaveTestCase):
    def test_file_is_readable_json(self) -> None:
        save_game(new_engine(1), self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["seed"], 1)
        self.assertEqual(len(data["map"]["tiles"]), 40)  # une chaîne par ligne
        self.assertFalse(self.path.with_suffix(".tmp").exists())  # pas de reste

    def test_missing_save(self) -> None:
        self.assertFalse(save_exists(self.path))
        self.assertIsNone(load_game(self.path))

    def test_corrupted_save_returns_none(self) -> None:
        self.path.parent.mkdir(parents=True)
        for content in ["{pas du json", '{"version": 1}', '{"version": 999}', "[]"]:
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                self.assertIsNone(load_game(self.path))

    def test_delete_save(self) -> None:
        save_game(new_engine(1), self.path)
        self.assertTrue(save_exists(self.path))
        delete_save(self.path)
        self.assertFalse(save_exists(self.path))
        delete_save(self.path)  # deuxième fois : pas d'erreur


if __name__ == "__main__":
    unittest.main()
