"""Point d'entrée du roguelike.

Lancement : python3 main.py [--seed N]  (Linux)  /  python main.py  (Windows)

Rôle de ce fichier : lire les options, initialiser curses, puis enchaîner
les écrans :

    TITRE ──Nouvelle partie / Continuer──▶ JEU ──q──▶ sauvegarde, fin du programme
      ▲                                      │
      └──────Entrée────── ÉCRAN DE MORT ◀──mort

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
from game.input import ENTER_KEYS, QUIT_KEYS, TITLE_OPTIONS, TitleChoice, UIState, handle_key, title_menu_key
from game.procgen import generate_floor
from game.render import draw, draw_death_screen, draw_title, init_styles, terminal_is_big_enough
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


# --- Écrans ------------------------------------------------------------------------


def title_screen(stdscr: curses.window, notice: str = "") -> TitleChoice:
    """Affiche le menu titre jusqu'à ce qu'un choix soit validé."""
    has_save = save_exists()
    enabled = [choice is not TitleChoice.CONTINUE or has_save for choice, _, _ in TITLE_OPTIONS]
    # Sélection de départ : « Continuer » s'il y a une sauvegarde, sinon « Nouvelle partie ».
    selected = 1 if has_save else 0
    while True:
        draw_title(stdscr, selected, enabled, notice)
        selected, choice = title_menu_key(stdscr.getch(), selected, enabled)
        if choice is not None:
            return choice


def death_screen(stdscr: curses.window, engine: Engine) -> bool:
    """Score de fin. Retourne True pour revenir au titre, False pour quitter."""
    while True:
        draw_death_screen(stdscr, engine)
        key = stdscr.getch()
        if key in ENTER_KEYS:
            return True
        if key in QUIT_KEYS:
            return False


def game_loop(stdscr: curses.window, engine: Engine) -> None:
    """Boucle de jeu, jusqu'à ce que le joueur quitte ou meure."""
    ui = UIState()  # mode d'interface : carte, inventaire, menu d'objet

    while engine.running:
        draw(stdscr, engine, ui)
        key = stdscr.getch()  # bloquant : attend une touche
        # KEY_RESIZE (fenêtre redimensionnée) ne donne aucune action :
        # on reboucle simplement, et draw() s'adapte à la nouvelle taille.

        if engine.game_over:
            return  # le bandeau « VOUS ÊTES MORT » attendait cette touche

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


def run(stdscr: curses.window, seed_arg: int | None) -> Engine | None:
    """Tout ce qui se passe « dans » curses. Retourne la dernière partie jouée
    (None si on a quitté depuis l'écran titre sans jouer)."""
    curses.curs_set(0)  # cache le curseur clignotant du terminal
    # Par défaut, curses attend 1 s après Échap (au cas où ce serait le début
    # d'une séquence comme une flèche). 25 ms suffisent et rendent Échap réactif.
    # hasattr : la version Windows (windows-curses) n'a pas forcément cette fonction.
    if hasattr(curses, "set_escdelay"):
        curses.set_escdelay(25)
    init_styles()  # couleurs

    notice = ""  # message à afficher sur l'écran titre (ex. sauvegarde abîmée)
    engine: Engine | None = None
    while True:
        choice = title_screen(stdscr, notice)
        notice = ""
        if choice is TitleChoice.QUIT:
            return engine

        if choice is TitleChoice.CONTINUE:
            engine = load_game()
            if engine is None:
                notice = "Sauvegarde illisible : lance une nouvelle partie."
                continue
        else:
            # Sans --seed, on en tire une au hasard… mais on la connaît, donc
            # on peut l'afficher et rejouer exactement ce donjon plus tard.
            seed = seed_arg if seed_arg is not None else random.randrange(2**31)
            engine = new_game(seed)

        game_loop(stdscr, engine)

        if engine.game_over:
            if death_screen(stdscr, engine):
                continue  # Entrée : retour à l'écran titre
            return engine
        # On a quitté (q) : sauvegarde automatique, puis fin du programme.
        save_game(engine)
        return engine


if __name__ == "__main__":
    args = parse_args()
    # wrapper() initialise curses (pas d'écho, touches spéciales activées…)
    # et surtout RESTAURE le terminal proprement, même si le jeu plante.
    # Il renvoie ce que renvoie run() : la partie, pour le message final.
    last_game = curses.wrapper(run, args.seed)

    if last_game is None:
        pass  # quitté depuis le titre sans jouer : rien à dire
    elif last_game.game_over:
        print(f"Partie terminée au niveau {last_game.depth}, {last_game.kills} monstre(s) tué(s).")
        print(f"Seed : {last_game.seed}  (rejouer : python3 main.py --seed {last_game.seed})")
    else:
        print(f"Partie sauvegardée dans {SAVE_PATH}")
        print("Relancez le jeu et choisissez « Continuer » pour la reprendre.")
