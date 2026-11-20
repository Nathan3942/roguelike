"""Point d'entrée du roguelike.

Lancement : python main.py   (ou python3 main.py)

M1 : un « @ » qui se déplace à l'écran avec les flèches / hjkl / yubn,
et « q » pour quitter.
"""

from __future__ import annotations

import curses

from game.input import MoveAction, QuitAction, key_to_action


def clamp(value: int, low: int, high: int) -> int:
    """Ramène value dans l'intervalle [low, high]."""
    return max(low, min(value, high))


def draw(stdscr: curses.window, player_x: int, player_y: int) -> None:
    """Dessine l'écran complet.

    Anti-clignotement : on utilise erase() et non clear().
    - clear() force curses à redessiner TOUT le terminal au prochain refresh
      → l'écran « flashe » à chaque touche.
    - erase() vide seulement le tampon en mémoire ; au refresh(), curses compare
      avec ce qui est déjà affiché et n'envoie que les cases modifiées.
    """
    stdscr.erase()
    try:
        stdscr.addstr(player_y, player_x, "@")
    except curses.error:
        # curses lève une erreur quand on écrit dans la toute dernière case
        # (coin bas-droit), car le curseur ne peut pas avancer après.
        # Le caractère est quand même affiché : on peut ignorer l'erreur.
        pass
    stdscr.refresh()


def main(stdscr: curses.window) -> None:
    """Boucle principale. curses.wrapper() nous fournit stdscr déjà initialisé."""
    curses.curs_set(0)  # cache le curseur clignotant du terminal

    height, width = stdscr.getmaxyx()
    player_x = width // 2
    player_y = height // 2

    while True:
        draw(stdscr, player_x, player_y)

        key = stdscr.getch()  # bloquant : attend une touche

        if key == curses.KEY_RESIZE:
            # Le terminal a été redimensionné : on garde le @ dans l'écran.
            height, width = stdscr.getmaxyx()
            player_x = clamp(player_x, 0, width - 1)
            player_y = clamp(player_y, 0, height - 1)
            continue

        action = key_to_action(key)
        if isinstance(action, QuitAction):
            break
        if isinstance(action, MoveAction):
            # On calcule la nouvelle position puis on la borne aux limites
            # de l'écran : le @ ne peut pas sortir.
            player_x = clamp(player_x + action.dx, 0, width - 1)
            player_y = clamp(player_y + action.dy, 0, height - 1)


if __name__ == "__main__":
    # wrapper() initialise curses (pas d'écho, touches spéciales activées…)
    # et surtout RESTAURE le terminal proprement, même si le jeu plante.
    curses.wrapper(main)
