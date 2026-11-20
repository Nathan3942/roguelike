"""Les entités du jeu : tout ce qui a une position sur la carte."""

from __future__ import annotations

from dataclasses import dataclass

from game.components import Fighter, Healing, HostileAI, Inventory


@dataclass
class Entity:
    """Un objet positionné sur la carte (cadavres ; plus tard objets au sol…).

    Pas frozen : sa position change quand il bouge.
    blocks_movement : empêche-t-il les autres de venir sur sa case ?
    """

    x: int
    y: int
    char: str
    name: str
    blocks_movement: bool = False


@dataclass
class Actor(Entity):
    """Une entité qui agit : le joueur ou un monstre.

    Hérite de tous les champs d'Entity. Un acteur bloque le passage par défaut
    (deux créatures ne partagent jamais une case).
    ai      : le « cerveau » du monstre ; None pour le joueur (c'est toi qui
              décides) et pour un cadavre.
    fighter : ses stats de combat ; None = ne peut pas se battre.
    """

    blocks_movement: bool = True
    ai: HostileAI | None = None
    fighter: Fighter | None = None
    inventory: Inventory | None = None  # seul le joueur en a un

    @property
    def is_alive(self) -> bool:
        return self.fighter is not None and not self.fighter.is_dead


@dataclass
class Item(Entity):
    """Un objet qu'on peut ramasser. Ne bloque pas le passage (hérité : False).

    consumable : son effet quand on l'utilise (None = objet sans usage).
    """

    consumable: Healing | None = None


# --- Fabriques -----------------------------------------------------------------
# Une fonction par type de créature : un seul endroit à modifier pour changer
# ses stats, et chaque appel crée des objets NEUFS (sa propre IA, ses propres PV).
# Les noms sont en minuscules, sans article : les messages ajoutent « le » / « l' ».


def make_player(x: int, y: int) -> Actor:
    return Actor(
        x=x, y=y, char="@", name="joueur",
        fighter=Fighter(max_hp=30, hp=30, attack=5, defense=2),
        inventory=Inventory(capacity=10),
    )


def make_goblin(x: int, y: int) -> Actor:
    return Actor(
        x=x, y=y, char="g", name="gobelin", ai=HostileAI(),
        fighter=Fighter(max_hp=10, hp=10, attack=3, defense=0),
    )


def make_orc(x: int, y: int) -> Actor:
    return Actor(
        x=x, y=y, char="o", name="orc", ai=HostileAI(),
        fighter=Fighter(max_hp=16, hp=16, attack=4, defense=1),
    )


def make_health_potion(x: int, y: int) -> Item:
    return Item(x=x, y=y, char="!", name="potion de soin", consumable=Healing(amount=10))
