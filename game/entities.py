"""Les entités du jeu : tout ce qui a une position sur la carte."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entity:
    """Un objet positionné sur la carte (joueur ; plus tard monstres, objets).

    Pas frozen : sa position change quand il bouge.
    """

    x: int
    y: int
    char: str
    name: str
