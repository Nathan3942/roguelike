"""Traduction des touches du clavier en actions de jeu.

On sépare « quelle touche a été pressée » de « ce que le jeu doit faire ».
Le moteur ne manipule jamais de codes de touches : il reçoit une action
(voir actions.py).

Depuis M7, la même touche n'a pas le même sens partout (« j » = descendre
sur la carte, mais « jeter » dans un menu). On garde donc un MODE d'interface,
qui forme une petite machine à états :

    CARTE ──i──▶ INVENTAIRE ──lettre──▶ MENU OBJET ──u / j──▶ CARTE
      ▲             │                      │
      └──Échap/i/q──┘          ◀──Échap/q──┘ (retour à l'inventaire)

Ce mode est de l'état d'INTERFACE, pas de jeu : il vit ici (et est lu par
render.py), jamais dans le moteur.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from game.actions import (
    Action,
    DescendAction,
    DropItemAction,
    FireAction,
    MoveAction,
    PickupAction,
    QuitAction,
    UseItemAction,
    WaitAction,
)

if TYPE_CHECKING:
    from game.engine import Engine

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

# Tir à l'arc : w haut, a gauche, s bas, d droite (4 directions).
FIRE_KEYS: dict[int, tuple[int, int]] = {
    ord("w"): (0, -1),
    ord("a"): (-1, 0),
    ord("s"): (0, 1),
    ord("d"): (1, 0),
}

QUIT_KEYS: set[int] = {ord("q")}
# « . » (comme le sol) ou « 5 » (centre du pavé numérique) : passer son tour.
WAIT_KEYS: set[int] = {ord("."), ord("5")}
PICKUP_KEY = ord("g")
INVENTORY_KEY = ord("i")
DESCEND_KEY = ord(">")
ESCAPE_KEY = 27
CLOSE_MENU_KEYS: set[int] = {ESCAPE_KEY, ord("q")}

# Dans le menu d'un objet.
USE_KEY = ord("u")
DROP_KEY = ord("j")


class Mode(Enum):
    MAP = auto()  # on joue sur la carte
    INVENTORY = auto()  # liste du sac affichée, on choisit un objet
    ITEM_MENU = auto()  # objet choisi : utiliser ou jeter ?


@dataclass
class UIState:
    mode: Mode = Mode.MAP
    selected: int = 0  # index de l'objet choisi (utile en mode ITEM_MENU)


def letter_to_index(key: int) -> int | None:
    """'a' → 0, 'b' → 1… ; None si ce n'est pas une lettre minuscule."""
    if ord("a") <= key <= ord("z"):
        return key - ord("a")
    return None


def handle_key(key: int, ui: UIState, engine: Engine) -> Action | None:
    """Traite une touche selon le mode courant.

    Peut changer de mode (ui est modifié sur place) et/ou retourner une action
    pour le moteur. None = rien à faire côté jeu.
    """
    if ui.mode is Mode.MAP:
        return handle_map_key(key, ui, engine)
    if ui.mode is Mode.INVENTORY:
        return handle_inventory_key(key, ui, engine)
    return handle_item_menu_key(key, ui)


def handle_map_key(key: int, ui: UIState, engine: Engine) -> Action | None:
    if key in QUIT_KEYS:
        return QuitAction()
    if engine.game_over:
        return None  # mort : seul « quitter » répond
    if key == INVENTORY_KEY:
        ui.mode = Mode.INVENTORY
        return None
    if key == PICKUP_KEY:
        return PickupAction()
    if key == DESCEND_KEY:
        return DescendAction()
    if key in WAIT_KEYS:
        return WaitAction()
    if key in MOVE_KEYS:
        dx, dy = MOVE_KEYS[key]
        return MoveAction(dx, dy)
    if key in FIRE_KEYS:
        dx, dy = FIRE_KEYS[key]
        return FireAction(dx, dy)
    return None


def handle_inventory_key(key: int, ui: UIState, engine: Engine) -> Action | None:
    if key in CLOSE_MENU_KEYS or key == INVENTORY_KEY:
        ui.mode = Mode.MAP
        return None
    index = letter_to_index(key)
    inventory = engine.player.inventory
    assert inventory is not None
    if index is not None and index < len(inventory.items):
        ui.selected = index
        ui.mode = Mode.ITEM_MENU
    return None


def handle_item_menu_key(key: int, ui: UIState) -> Action | None:
    if key in CLOSE_MENU_KEYS:
        ui.mode = Mode.INVENTORY  # retour à la liste
        return None
    if key == USE_KEY:
        ui.mode = Mode.MAP
        return UseItemAction(ui.selected)
    if key == DROP_KEY:
        ui.mode = Mode.MAP
        return DropItemAction(ui.selected)
    return None


# --- Écran titre (M10) ----------------------------------------------------------
# La navigation est une fonction PURE (pas d'affichage, pas de curses.window) :
# on peut la tester sans terminal. render.py dessine, main.py fait la boucle.


class TitleChoice(Enum):
    NEW = auto()
    CONTINUE = auto()
    QUIT = auto()


# (choix, libellé, raccourci clavier)
TITLE_OPTIONS: list[tuple[TitleChoice, str, str]] = [
    (TitleChoice.NEW, "Nouvelle partie", "n"),
    (TitleChoice.CONTINUE, "Continuer", "c"),
    (TitleChoice.QUIT, "Quitter", "q"),
]

# Entrée peut arriver sous trois codes selon le terminal.
ENTER_KEYS: set[int] = {10, 13, curses.KEY_ENTER}
MENU_UP_KEYS: set[int] = {curses.KEY_UP, ord("k")}
MENU_DOWN_KEYS: set[int] = {curses.KEY_DOWN, ord("j")}


def next_enabled(selected: int, step: int, enabled: list[bool]) -> int:
    """Index de la prochaine option active dans la direction `step` (±1).

    Le modulo % fait « boucler » : après la dernière option, on revient à la
    première. Une option désactivée (Continuer sans sauvegarde) est sautée.
    """
    index = selected
    for _ in range(len(enabled)):
        index = (index + step) % len(enabled)
        if enabled[index]:
            return index
    return selected


def title_menu_key(key: int, selected: int, enabled: list[bool]) -> tuple[int, TitleChoice | None]:
    """Traite une touche sur l'écran titre.

    Retourne (nouvelle sélection, choix validé ou None).
    """
    if key in MENU_UP_KEYS:
        return next_enabled(selected, -1, enabled), None
    if key in MENU_DOWN_KEYS:
        return next_enabled(selected, +1, enabled), None
    if key in ENTER_KEYS:
        return selected, TITLE_OPTIONS[selected][0]
    # Raccourci direct : « n », « c » ou « q ».
    for index, (choice, _, shortcut) in enumerate(TITLE_OPTIONS):
        if key == ord(shortcut) and enabled[index]:
            return index, choice
    return selected, None
