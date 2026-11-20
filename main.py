"""Point d'entrée du roguelike.

Lancement : python3 main.py  (Linux)  /  python main.py  (Windows)

Rôle de ce fichier : initialiser curses et faire tourner la boucle
« dessiner → lire une touche → appliquer l'action ».
Toute la logique est dans game/engine.py, tout l'affichage dans game/render.py.
"""

from __future__ import annotations

import curses

from game.actions import QuitAction
from game.engine import Engine
from game.entities import Entity
from game.input import key_to_action
from game.procgen import generate_test_room
from game.render import draw, terminal_is_big_enough


def main(stdscr: curses.window) -> None:
    """Boucle principale. curses.wrapper() nous fournit stdscr déjà initialisé."""
    curses.curs_set(0)  # cache le curseur clignotant du terminal

    game_map, (start_x, start_y) = generate_test_room()
    player = Entity(x=start_x, y=start_y, char="@", name="Joueur")
    engine = Engine(game_map, player)

    while engine.running:
        draw(stdscr, engine)

        key = stdscr.getch()  # bloquant : attend une touche
        # KEY_RESIZE (fenêtre redimensionnée) n'a pas d'action associée :
        # on reboucle simplement, et draw() s'adapte à la nouvelle taille.
        action = key_to_action(key)
        if action is None:
            continue

        # Terminal trop petit : le joueur ne voit pas la carte, on n'accepte
        # donc que « quitter » pour éviter de bouger à l'aveugle.
        if not terminal_is_big_enough(stdscr, engine) and not isinstance(action, QuitAction):
            continue

        engine.handle_action(action)


if __name__ == "__main__":
    # wrapper() initialise curses (pas d'écho, touches spéciales activées…)
    # et surtout RESTAURE le terminal proprement, même si le jeu plante.
    curses.wrapper(main)
