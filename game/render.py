"""Tout l'affichage curses. Le seul module de game/ qui connaît curses.

Il LIT l'état du moteur (carte, joueur) mais ne le modifie jamais.
"""

from __future__ import annotations

import curses

from game.engine import Engine


def terminal_is_big_enough(stdscr: curses.window, engine: Engine) -> bool:
    """La carte entière tient-elle dans le terminal ?"""
    height, width = stdscr.getmaxyx()
    return width >= engine.game_map.width and height >= engine.game_map.height


def safe_addstr(stdscr: curses.window, y: int, x: int, text: str) -> None:
    """addstr qui ignore les erreurs de bord.

    curses lève une erreur quand on écrit dans la toute dernière case de
    l'écran (coin bas-droit), car le curseur ne peut pas avancer après.
    Le texte est pourtant bien affiché : on ignore donc l'erreur.
    """
    try:
        stdscr.addstr(y, x, text)
    except curses.error:
        pass


def draw_too_small(stdscr: curses.window, engine: Engine) -> None:
    """Écran d'avertissement quand le terminal est trop petit pour la carte."""
    height, width = stdscr.getmaxyx()
    lines = [
        "Terminal trop petit !",
        f"Requis : {engine.game_map.width}x{engine.game_map.height}",
        f"Actuel : {width}x{height}",
        "Agrandis la fenetre (ou q pour quitter).",
    ]
    for row, line in enumerate(lines):
        if row >= height:
            break
        # On coupe chaque ligne à la largeur dispo pour ne pas déborder.
        safe_addstr(stdscr, row, 0, line[: max(width - 1, 0)])


def draw_map(stdscr: curses.window, engine: Engine) -> None:
    """Dessine la carte ligne par ligne, depuis le coin haut-gauche.

    Une ligne = un seul appel addstr (bien plus rapide que case par case).
    """
    game_map = engine.game_map
    for y in range(game_map.height):
        row = "".join(tile.char for tile in game_map.tiles[y])
        safe_addstr(stdscr, y, 0, row)


def draw(stdscr: curses.window, engine: Engine) -> None:
    """Redessine tout l'écran.

    Anti-clignotement : erase() (vide le tampon) et non clear() (qui force
    un redessin complet du terminal). refresh() n'envoie que les différences.
    """
    stdscr.erase()
    if not terminal_is_big_enough(stdscr, engine):
        draw_too_small(stdscr, engine)
    else:
        draw_map(stdscr, engine)
        player = engine.player
        # Le joueur est dessiné APRÈS la carte, donc par-dessus.
        safe_addstr(stdscr, player.y, player.x, player.char)
    stdscr.refresh()
