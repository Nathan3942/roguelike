"""Composants : des « briques » de comportement qu'on attache aux entités.

- Fighter   : tout ce qui peut se battre (PV, attaque, défense) — M6
- HostileAI : le « cerveau » des monstres — M5
(M7 ajoutera Inventory.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

# TYPE_CHECKING vaut False à l'exécution : ces imports ne servent qu'aux
# annotations de type. Ça évite un import circulaire (entities importe
# components, engine importe entities…).
if TYPE_CHECKING:
    from game.engine import Engine
    from game.entities import Actor


@dataclass
class Fighter:
    """Statistiques de combat.

    Dégâts d'une attaque = attack de l'attaquant − defense de la cible
    (jamais négatifs). Pas de hasard : le combat est prévisible, donc lisible.
    """

    max_hp: int
    hp: int
    attack: int
    defense: int

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0

    def take_damage(self, amount: int) -> None:
        """Retire des PV, sans descendre sous 0."""
        self.hp = max(self.hp - amount, 0)


def sign(value: int) -> int:
    """-1, 0 ou 1 selon le signe de value."""
    return (value > 0) - (value < 0)


class HostileAI:
    """IA basique : au contact, j'attaque ; si je vois le joueur, je me
    rapproche ; sinon j'attends.

    « Je vois le joueur » = je suis sur une case que le joueur voit. La vision
    est (presque) symétrique : si tu me vois, je te vois. Ça évite de calculer
    un champ de vision par monstre.
    """

    def take_turn(self, actor: Actor, engine: Engine) -> None:
        game_map = engine.game_map
        player = engine.player

        if (actor.x, actor.y) not in game_map.visible:
            return  # le joueur est hors de vue : j'attends

        dx = player.x - actor.x
        dy = player.y - actor.y
        if max(abs(dx), abs(dy)) <= 1:
            engine.attack(actor, player)  # au contact (diagonale comprise)
            return

        # Un pas dans la direction du joueur : chaque axe vaut -1, 0 ou +1.
        step_x, step_y = sign(dx), sign(dy)

        # Si la diagonale est bloquée (mur, autre monstre), on tente de
        # glisser le long d'un seul axe. Ordre : diagonale, puis x, puis y.
        candidates = [(step_x, step_y), (step_x, 0), (0, step_y)]
        for move_x, move_y in candidates:
            if (move_x, move_y) == (0, 0):
                continue
            if game_map.is_free(actor.x + move_x, actor.y + move_y):
                actor.x += move_x
                actor.y += move_y
                return
        # Tout est bloqué : le monstre reste sur place ce tour-ci.
