"""Point d'entrée du roguelike.

Lancement : python3 main.py [--seed N]  (Linux)  /  python main.py  (Windows)

Rôle de ce fichier : lire les options, initialiser curses et faire tourner la
boucle « dessiner → lire une touche → appliquer l'action ».
Toute la logique est dans game/engine.py, tout l'affichage dans game/render.py.
"""

from __future__ import annotations

import argparse
import curses
import random

from game.actions import QuitAction
from game.engine import Engine
from game.entities import make_player
from game.input import key_to_action
from game.procgen import generate_dungeon
from game.render import draw, init_styles, terminal_is_big_enough


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Roguelike en terminal.")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="graine du donjon (même seed = même donjon). Aléatoire si absente.",
    )
    return parser.parse_args()


def new_game(seed: int) -> Engine:
    """Crée une partie complète à partir d'une seed."""
    rng = random.Random(seed)  # générateur DÉDIÉ, pas le random global
    game_map, rooms = generate_dungeon(rng)
    start_x, start_y = rooms[0].center
    player = make_player(start_x, start_y)
    return Engine(game_map, player, seed)


def main(stdscr: curses.window, engine: Engine) -> None:
    """Boucle principale. curses.wrapper() nous fournit stdscr déjà initialisé."""
    curses.curs_set(0)  # cache le curseur clignotant du terminal
    init_styles()  # couleurs / atténuation pour les zones explorées

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
    args = parse_args()
    # Sans --seed, on en tire une au hasard… mais on la connaît, donc on
    # peut l'afficher et rejouer exactement ce donjon plus tard.
    seed = args.seed if args.seed is not None else random.randrange(2**31)

    engine = new_game(seed)
    # wrapper() initialise curses (pas d'écho, touches spéciales activées…)
    # et surtout RESTAURE le terminal proprement, même si le jeu plante.
    curses.wrapper(main, engine)
    print(f"Seed de la partie : {seed}  (rejouer : python3 main.py --seed {seed})")
