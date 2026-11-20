"""Tests de M10 : score (monstres tués) et navigation de l'écran titre."""

from __future__ import annotations

import curses
import tempfile
import unittest
from pathlib import Path

from game.actions import MoveAction
from game.engine import Engine
from game.entities import make_goblin, make_player
from game.input import TitleChoice, title_menu_key
from game.map import FLOOR, WALL, GameMap
from game.save import load_game, save_game

ENTER = 10
ALL = [True, True, True]
NO_SAVE = [True, False, True]  # « Continuer » désactivé


class KillCountTests(unittest.TestCase):
    def test_kills_counted_and_saved(self) -> None:
        game_map = GameMap(10, 3, fill=WALL)
        for x in range(1, 9):
            game_map.set_tile(x, 1, FLOOR)
        game_map.entities.extend([make_goblin(2, 1), make_goblin(4, 1)])
        engine = Engine(game_map, make_player(1, 1), seed=0)

        for _ in range(2):  # 2 coups de 5 → gobelin (10 PV) mort
            engine.handle_action(MoveAction(1, 0))
        self.assertEqual(engine.kills, 1)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_game(engine, path)
            loaded = load_game(path)
        assert loaded is not None
        self.assertEqual(loaded.kills, 1)


class TitleMenuTests(unittest.TestCase):
    def test_enter_validates_selection(self) -> None:
        self.assertEqual(title_menu_key(ENTER, 0, ALL), (0, TitleChoice.NEW))
        self.assertEqual(title_menu_key(ENTER, 2, ALL), (2, TitleChoice.QUIT))

    def test_arrows_move_and_wrap(self) -> None:
        self.assertEqual(title_menu_key(curses.KEY_DOWN, 0, ALL), (1, None))
        self.assertEqual(title_menu_key(curses.KEY_DOWN, 2, ALL), (0, None))  # boucle
        self.assertEqual(title_menu_key(curses.KEY_UP, 0, ALL), (2, None))
        self.assertEqual(title_menu_key(ord("j"), 0, ALL), (1, None))

    def test_disabled_option_is_skipped(self) -> None:
        self.assertEqual(title_menu_key(curses.KEY_DOWN, 0, NO_SAVE), (2, None))
        self.assertEqual(title_menu_key(curses.KEY_UP, 2, NO_SAVE), (0, None))

    def test_shortcuts(self) -> None:
        self.assertEqual(title_menu_key(ord("n"), 2, ALL), (0, TitleChoice.NEW))
        self.assertEqual(title_menu_key(ord("c"), 0, ALL), (1, TitleChoice.CONTINUE))
        self.assertEqual(title_menu_key(ord("q"), 0, ALL), (2, TitleChoice.QUIT))

    def test_disabled_shortcut_does_nothing(self) -> None:
        self.assertEqual(title_menu_key(ord("c"), 0, NO_SAVE), (0, None))

    def test_other_key_ignored(self) -> None:
        self.assertEqual(title_menu_key(ord("z"), 1, ALL), (1, None))


if __name__ == "__main__":
    unittest.main()
