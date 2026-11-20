"""Point d'entrée du roguelike.

Lancement : python3 main.py [--seed N]  (Linux)  /  python main.py  (Windows)

Rôle de ce fichier : lire les options, initialiser curses, choisir entre
nouvelle partie et sauvegarde, puis faire tourner la boucle
« dessiner → lire une touche → appliquer l'action ».
Toute la logique est dans game/engine.py, tout l'affichage dans game/render.py,
la sauvegarde dans game/save.py.
"""

from __future__ import annotations

import argparse
import curses
import random

from game.actions import QuitAction
from game.engine import Engine
from game.entities import make_player
from game.input import QUIT_KEYS, UIState, handle_key
from game.procgen import generate_floor
from game.render import draw, draw_question, init_styles, terminal_is_big_enough
from game.save import SAVE_PATH, delete_save, load_game, save_exists, save_game


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
    game_map, rooms = generate_floor(seed, depth=1)
    start_x, start_y = rooms[0].center
    player = make_player(start_x, start_y)
    return Engine(game_map, player, seed)


def ask_yes_no(stdscr: curses.window, lines: list[str]) -> bool:
    """Affiche une question et attend « o » (oui) ou « n » (non)."""
    while True:
        draw_question(stdscr, lines)
        key = stdscr.getch()
        if key in (ord("o"), ord("O")):
            return True
        if key in (ord("n"), ord("N")):
            return False
        # Autre touche (ou redimensionnement) : on redessine et on redemande.


def choose_game(stdscr: curses.window, seed_arg: int | None) -> Engine:
    """Reprendre la sauvegarde si elle existe et que le joueur le veut,
    sinon nouvelle partie."""
    load_failed = False
    if save_exists():
        if ask_yes_no(stdscr, ["Une partie sauvegardée existe.", "", "Reprendre ? (o/n)"]):
            engine = load_game()
            if engine is not None:
                return engine
            load_failed = True  # fichier abîmé : on repart de zéro

    # Sans --seed, on en tire une au hasard… mais on la connaît, donc on
    # peut l'afficher et rejouer exactement ce donjon plus tard.
    seed = seed_arg if seed_arg is not None else random.randrange(2**31)
    engine = new_game(seed)
    if load_failed:
        engine.log.add("Sauvegarde illisible : nouvelle partie.")
    return engine


def game_loop(stdscr: curses.window, engine: Engine) -> None:
    """Boucle principale, jusqu'à ce que le joueur quitte."""
    ui = UIState()  # mode d'interface : carte, inventaire, menu d'objet

    while engine.running:
        draw(stdscr, engine, ui)

        key = stdscr.getch()  # bloquant : attend une touche
        # KEY_RESIZE (fenêtre redimensionnée) ne donne aucune action :
        # on reboucle simplement, et draw() s'adapte à la nouvelle taille.

        # Terminal trop petit : le joueur ne voit pas la carte, on n'accepte
        # donc que « quitter » pour éviter de jouer à l'aveugle.
        if not terminal_is_big_enough(stdscr, engine):
            if key in QUIT_KEYS:
                engine.handle_action(QuitAction())
            continue

        action = handle_key(key, ui, engine)
        if action is not None:
            engine.handle_action(action)

        if engine.game_over:
            # Permadeath : la sauvegarde disparaît DÈS la mort (et pas
            # seulement en quittant) : couper le terminal ne la sauve pas.
            delete_save()


def run(stdscr: curses.window, seed_arg: int | None) -> Engine:
    """Tout ce qui se passe « dans » curses. Retourne la partie jouée."""
    curses.curs_set(0)  # cache le curseur clignotant du terminal
    # Par défaut, curses attend 1 s après Échap (au cas où ce serait le début
    # d'une séquence comme une flèche). 25 ms suffisent et rendent Échap réactif.
    curses.set_escdelay(25)
    init_styles()  # couleurs / atténuation pour les zones explorées

    engine = choose_game(stdscr, seed_arg)
    game_loop(stdscr, engine)

    # On a quitté (q) : sauvegarde automatique, sauf si le joueur est mort.
    if not engine.game_over:
        save_game(engine)
    return engine


if __name__ == "__main__":
    args = parse_args()
    # wrapper() initialise curses (pas d'écho, touches spéciales activées…)
    # et surtout RESTAURE le terminal proprement, même si le jeu plante.
    # Il renvoie ce que renvoie run() : la partie, pour le message final.
    engine = curses.wrapper(run, args.seed)

    if engine.game_over:
        print(f"Vous êtes mort au niveau {engine.depth}. Seed : {engine.seed}")
    else:
        print(f"Partie sauvegardée dans {SAVE_PATH}")
        print("Relancez le jeu pour la reprendre.")
