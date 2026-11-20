"""Tout l'affichage curses. Le seul module de game/ qui connaît curses.

Il LIT l'état du moteur (carte, joueur) mais ne le modifie jamais.
"""

from __future__ import annotations

import curses

from game.engine import Engine

# Lignes réservées sous la carte (pour l'instant : une ligne de statut).
HUD_HEIGHT = 1


def required_size(engine: Engine) -> tuple[int, int]:
    """Taille minimale du terminal (largeur, hauteur) : carte + HUD."""
    return engine.game_map.width, engine.game_map.height + HUD_HEIGHT


def terminal_is_big_enough(stdscr: curses.window, engine: Engine) -> bool:
    """La carte entière et le HUD tiennent-ils dans le terminal ?"""
    height, width = stdscr.getmaxyx()
    min_width, min_height = required_size(engine)
    return width >= min_width and height >= min_height


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
    min_width, min_height = required_size(engine)
    lines = [
        "Terminal trop petit !",
        f"Requis : {min_width}x{min_height}",
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


def draw_status_line(stdscr: curses.window, engine: Engine) -> None:
    """Ligne de statut juste sous la carte."""
    text = f"Seed : {engine.seed}   |   q : quitter"
    safe_addstr(stdscr, engine.game_map.height, 0, text)


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
        draw_status_line(stdscr, engine)
        player = engine.player
        # Le joueur est dessiné APRÈS la carte, donc par-dessus.
        safe_addstr(stdscr, player.y, player.x, player.char)
    stdscr.refresh()
