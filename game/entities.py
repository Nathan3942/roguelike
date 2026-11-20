"""Les entités du jeu : tout ce qui a une position sur la carte."""

from __future__ import annotations

from dataclasses import dataclass

from game.components import HostileAI


@dataclass
class Entity:
    """Un objet positionné sur la carte (plus tard : objets au sol, cadavres…).

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
    ai : le « cerveau » du monstre ; None pour le joueur (c'est toi qui décides).
    """

    blocks_movement: bool = True
    ai: HostileAI | None = None


# --- Fabriques de monstres ---------------------------------------------------
# Une fonction par type de monstre : un seul endroit à modifier pour changer
# un monstre, et chaque appel crée un objet NEUF (avec sa propre IA).


def make_player(x: int, y: int) -> Actor:
    return Actor(x=x, y=y, char="@", name="Joueur")


def make_goblin(x: int, y: int) -> Actor:
    return Actor(x=x, y=y, char="g", name="Gobelin", ai=HostileAI())


def make_orc(x: int, y: int) -> Actor:
    return Actor(x=x, y=y, char="o", name="Orc", ai=HostileAI())
