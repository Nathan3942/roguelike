"""Tests du combat, de la mort et du journal (M6)."""

from __future__ import annotations

import unittest

from game.actions import MoveAction, QuitAction, WaitAction
from game.components import Fighter
from game.engine import Engine
from game.entities import Actor, make_goblin, make_orc, make_player
from game.map import FLOOR, WALL, GameMap
from game.messages import MAX_MESSAGES, MessageLog, elide


def open_room() -> GameMap:
    """Pièce 12×3 entourée de murs."""
    game_map = GameMap(14, 5, fill=WALL)
    for y in range(1, 4):
        for x in range(1, 13):
            game_map.set_tile(x, y, FLOOR)
    return game_map


def setup(monsters: list[Actor], player: Actor | None = None) -> Engine:
    game_map = open_room()
    game_map.entities.extend(monsters)
    return Engine(game_map, player or make_player(1, 2), seed=0)


class FighterTests(unittest.TestCase):
    def test_damage_never_below_zero_hp(self) -> None:
        fighter = Fighter(max_hp=10, hp=3, attack=1, defense=0)
        fighter.take_damage(50)
        self.assertEqual(fighter.hp, 0)
        self.assertTrue(fighter.is_dead)


class CombatTests(unittest.TestCase):
    def test_bump_attacks_instead_of_moving(self) -> None:
        gob = make_goblin(2, 2)
        engine = setup([gob])
        engine.handle_action(MoveAction(1, 0))
        self.assertEqual((engine.player.x, engine.player.y), (1, 2))  # pas bougé
        assert gob.fighter is not None
        self.assertEqual(gob.fighter.hp, 10 - (5 - 0))  # attaque 5 − défense 0

    def test_player_never_attacks_himself(self) -> None:
        engine = setup([])
        engine.handle_action(MoveAction(0, 0))
        assert engine.player.fighter is not None
        self.assertEqual(engine.player.fighter.hp, 30)
        self.assertFalse(any("le joueur" in m for m in engine.log.messages))

    def test_damage_formula_with_defense(self) -> None:
        orc = make_orc(2, 2)
        engine = setup([orc])
        engine.attack(engine.player, orc)
        assert orc.fighter is not None
        self.assertEqual(orc.fighter.hp, 16 - (5 - 1))

    def test_no_negative_damage(self) -> None:
        tank = make_goblin(2, 2)
        assert tank.fighter is not None
        tank.fighter.defense = 99
        engine = setup([tank])
        engine.attack(engine.player, tank)
        self.assertEqual(tank.fighter.hp, 10)
        self.assertIn("sans effet", engine.log.messages[-1])

    def test_monster_dies_and_becomes_corpse(self) -> None:
        gob = make_goblin(2, 2)
        engine = setup([gob])
        engine.handle_action(MoveAction(1, 0))
        engine.handle_action(MoveAction(1, 0))  # 2 coups de 5 → 10 PV
        self.assertFalse(gob.is_alive)
        self.assertEqual(gob.char, "%")
        self.assertFalse(gob.blocks_movement)
        self.assertIsNone(gob.ai)
        self.assertEqual(gob.name, "cadavre de gobelin")
        self.assertIn("Le gobelin meurt !", engine.log.messages)
        # Le cadavre ne bloque plus : on peut marcher dessus.
        engine.handle_action(MoveAction(1, 0))
        self.assertEqual((engine.player.x, engine.player.y), (2, 2))

    def test_monster_attacks_when_adjacent(self) -> None:
        gob = make_goblin(2, 3)  # en diagonale du joueur
        engine = setup([gob])
        engine.handle_action(WaitAction())
        assert engine.player.fighter is not None
        self.assertEqual(engine.player.fighter.hp, 30 - (3 - 2))
        self.assertEqual(engine.log.messages[-1], "Le gobelin vous attaque : 1 dégât.")

    def test_corpse_does_not_act(self) -> None:
        gob = make_goblin(2, 2)
        engine = setup([gob])
        engine.kill(gob)
        hp_before = engine.player.fighter.hp if engine.player.fighter else 0
        for _ in range(5):
            engine.handle_action(WaitAction())
        assert engine.player.fighter is not None
        self.assertEqual(engine.player.fighter.hp, hp_before)


class PlayerDeathTests(unittest.TestCase):
    def make_doomed_engine(self) -> Engine:
        weak = make_player(1, 2)
        assert weak.fighter is not None
        weak.fighter.hp = 1
        return setup([make_orc(2, 2), make_orc(2, 1)], player=weak)

    def test_player_death_sets_game_over(self) -> None:
        engine = self.make_doomed_engine()
        engine.handle_action(WaitAction())
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.player.char, "%")
        self.assertEqual(engine.log.messages[-1], "Vous êtes mort !")
        # Le 2e orc ne s'acharne pas sur le cadavre.
        self.assertEqual(sum("vous attaque" in m for m in engine.log.messages), 1)

    def test_no_action_after_death_except_quit(self) -> None:
        engine = self.make_doomed_engine()
        engine.handle_action(WaitAction())
        position = (engine.player.x, engine.player.y)
        log_size = len(engine.log.messages)
        engine.handle_action(MoveAction(0, 1))
        engine.handle_action(WaitAction())
        self.assertEqual((engine.player.x, engine.player.y), position)
        self.assertEqual(len(engine.log.messages), log_size)
        engine.handle_action(QuitAction())
        self.assertFalse(engine.running)


class MessageTests(unittest.TestCase):
    def test_elision(self) -> None:
        self.assertEqual(elide("le", "gobelin"), "le gobelin")
        self.assertEqual(elide("le", "orc"), "l'orc")
        self.assertEqual(elide("de", "orc"), "d'orc")

    def test_log_keeps_last_messages_in_order(self) -> None:
        log = MessageLog()
        for i in range(MAX_MESSAGES + 20):
            log.add(f"m{i}")
        self.assertEqual(len(log.messages), MAX_MESSAGES)
        self.assertEqual(log.last(2), [f"m{MAX_MESSAGES + 18}", f"m{MAX_MESSAGES + 19}"])

    def test_orc_messages(self) -> None:
        orc = make_orc(2, 2)
        engine = setup([orc])
        engine.attack(engine.player, orc)
        self.assertEqual(engine.log.messages[-1], "Vous attaquez l'orc : 4 dégâts.")


if __name__ == "__main__":
    unittest.main()
