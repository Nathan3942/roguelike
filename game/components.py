"""Composants : des « briques » de comportement qu'on attache aux entités.

- Fighter   : tout ce qui peut se battre (PV, attaque, défense) — M6
- HostileAI : le « cerveau » des monstres — M5
- Inventory : le sac du joueur — M7
- Healing   : l'effet d'une potion de soin — M7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# TYPE_CHECKING vaut False à l'exécution : ces imports ne servent qu'aux
# annotations de type. Ça évite un import circulaire (entities importe
# components, engine importe entities…).
if TYPE_CHECKING:
    from game.engine import Engine
    from game.entities import Actor, Item


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

    def heal(self, amount: int) -> int:
        """Rend des PV sans dépasser max_hp. Retourne les PV VRAIMENT rendus."""
        new_hp = min(self.hp + amount, self.max_hp)
        healed = new_hp - self.hp
        self.hp = new_hp
        return healed


@dataclass
class Inventory:
    """Le sac : une liste d'objets, avec une capacité maximale.

    field(default_factory=list) : chaque inventaire reçoit SA PROPRE liste.
    (Écrire `items: list = []` ferait partager la même liste à tous les sacs,
    piège classique des valeurs par défaut mutables en Python.)
    """

    capacity: int
    items: list[Item] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return len(self.items) >= self.capacity


@dataclass
class Healing:
    """Effet « soigne de `amount` PV ». Attaché à un objet (potion)."""

    amount: int

    def use(self, user: Actor, engine: Engine) -> bool:
        """Applique l'effet. Retourne True si l'objet a été consommé.

        À PV max, on refuse : la potion reste dans le sac et le tour n'est pas
        perdu (gaspiller une potion par erreur serait frustrant).
        """
        assert user.fighter is not None
        if user.fighter.hp >= user.fighter.max_hp:
            engine.log.add("Vous êtes déjà en pleine santé.")
            return False
        healed = user.fighter.heal(self.amount)
        engine.log.add(f"Vous buvez la potion : +{healed} PV.")
        return True


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
