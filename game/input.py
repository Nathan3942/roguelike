"""Traduction des touches du clavier en actions de jeu.

On sépare « quelle touche a été pressée » de « ce que le jeu doit faire ».
Le reste du programme ne manipule jamais de codes de touches : il reçoit
une action (ici, pour M1, un déplacement ou l'ordre de quitter).
"""

from __future__ import annotations

import curses
from dataclasses import dataclass


@dataclass(frozen=True)
class MoveAction:
    """Déplacement d'une case : dx vers la droite, dy vers le bas."""

    dx: int
    dy: int


@dataclass(frozen=True)
class QuitAction:
    """Le joueur veut quitter le jeu."""


# Une action possible est l'une des classes ci-dessus.
Action = MoveAction | QuitAction


# Table touche -> (dx, dy).
# Attention : en curses, l'axe y va vers le BAS (ligne 0 = haut de l'écran).
MOVE_KEYS: dict[int, tuple[int, int]] = {
    # Flèches
    curses.KEY_UP: (0, -1),
    curses.KEY_DOWN: (0, 1),
    curses.KEY_LEFT: (-1, 0),
    curses.KEY_RIGHT: (1, 0),
    # Touches « vi » : h gauche, j bas, k haut, l droite
    ord("h"): (-1, 0),
    ord("j"): (0, 1),
    ord("k"): (0, -1),
    ord("l"): (1, 0),
    # Diagonales : y haut-gauche, u haut-droite, b bas-gauche, n bas-droite
    ord("y"): (-1, -1),
    ord("u"): (1, -1),
    ord("b"): (-1, 1),
    ord("n"): (1, 1),
}

QUIT_KEYS: set[int] = {ord("q")}


def key_to_action(key: int) -> Action | None:
    """Retourne l'action associée à une touche, ou None si la touche est ignorée."""
    if key in QUIT_KEYS:
        return QuitAction()
    if key in MOVE_KEYS:
        dx, dy = MOVE_KEYS[key]
        return MoveAction(dx, dy)
    return None
