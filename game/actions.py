"""Les actions possibles dans le jeu.

Une action décrit CE QUE le joueur veut faire, indépendamment de la touche
pressée (voir input.py) et de la façon dont le moteur l'exécute (engine.py).
Ce module ne dépend pas de curses : il reste testable partout.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MoveAction:
    """Déplacement d'une case : dx vers la droite, dy vers le bas."""

    dx: int
    dy: int


@dataclass(frozen=True)
class WaitAction:
    """Passer son tour sans bouger (les monstres, eux, agissent)."""


@dataclass(frozen=True)
class PickupAction:
    """Ramasser l'objet sur lequel on se trouve."""


@dataclass(frozen=True)
class UseItemAction:
    """Utiliser l'objet n° `index` de l'inventaire."""

    index: int


@dataclass(frozen=True)
class DropItemAction:
    """Jeter (poser au sol) l'objet n° `index` de l'inventaire."""

    index: int


@dataclass(frozen=True)
class DescendAction:
    """Prendre l'escalier « > » sur lequel on se trouve."""


@dataclass(frozen=True)
class QuitAction:
    """Le joueur veut quitter le jeu."""


# Une action possible est l'une des classes ci-dessus.
Action = (
    MoveAction
    | WaitAction
    | PickupAction
    | UseItemAction
    | DropItemAction
    | DescendAction
    | QuitAction
)
