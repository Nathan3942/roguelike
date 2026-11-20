"""Tout l'affichage curses. Le seul module de game/ qui connaît curses.

Il LIT l'état du moteur (carte, joueur) mais ne le modifie jamais.
"""

from __future__ import annotations

import curses

from game.engine import Engine
from game.entities import Item
from game.input import Mode, UIState

# Sous la carte : une ligne de statut (PV, seed, touches) + le journal.
MESSAGE_LINES = 5
HUD_HEIGHT = 1 + MESSAGE_LINES
HP_BAR_WIDTH = 10

# Numéro de la paire de couleurs « gris » (les paires se numérotent à partir de 1).
REMEMBERED_PAIR = 1


def init_styles() -> None:
    """Prépare les styles d'affichage. À appeler une fois, après l'init de curses.

    Pour les cases explorées mais plus visibles, on veut du gris :
    - si le terminal a au moins 16 couleurs, la couleur n°8 est un gris foncé
      (« noir brillant ») : on crée une paire gris sur fond par défaut ;
    - sinon, on se rabat sur l'attribut A_DIM (texte atténué).
    """
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()  # -1 = couleur de fond du terminal
        if curses.COLORS >= 16:
            curses.init_pair(REMEMBERED_PAIR, 8, -1)


def get_remembered_style() -> int:
    """Attribut curses pour les cases explorées hors de vue."""
    if curses.has_colors() and curses.COLORS >= 16:
        return curses.color_pair(REMEMBERED_PAIR)
    return curses.A_DIM


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
    """Dessine les cases connues de la carte, depuis le coin haut-gauche.

    - visible  → style normal ;
    - explorée → style « souvenir » (grisé) ;
    - inconnue → rien (erase() a déjà mis un espace).
    On ne parcourt que `explored` (qui contient `visible`) : inutile de
    regarder les cases jamais vues.
    """
    game_map = engine.game_map
    remembered_style = get_remembered_style()
    for x, y in game_map.explored:
        char = game_map.get_tile(x, y).char
        style = curses.A_NORMAL if (x, y) in game_map.visible else remembered_style
        try:
            stdscr.addstr(y, x, char, style)
        except curses.error:
            pass  # coin bas-droit, voir safe_addstr


def hp_bar(hp: int, max_hp: int, width: int = HP_BAR_WIDTH) -> str:
    """Barre de PV en texte, ex. « [==========          ] ».

    Nombre de « = » proportionnel aux PV restants : hp / max_hp × largeur.
    La division entière // arrondit vers le bas ; on garde au moins un « = »
    tant qu'on est en vie, pour ne pas afficher une barre vide à 1 PV.
    """
    filled = hp * width // max_hp
    if hp > 0:
        filled = max(filled, 1)
    return "[" + "=" * filled + " " * (width - filled) + "]"


def draw_status_line(stdscr: curses.window, engine: Engine) -> None:
    """Ligne de statut juste sous la carte : PV, sac, seed, touches utiles."""
    fighter = engine.player.fighter
    inventory = engine.player.inventory
    assert fighter is not None and inventory is not None
    hp_text = f"PV {fighter.hp:>2}/{fighter.max_hp} {hp_bar(fighter.hp, fighter.max_hp)}"
    bag_text = f"Sac {len(inventory.items)}/{inventory.capacity}"
    # Place limitée (80 colonnes) : les autres touches sont rappelées dans le
    # message de bienvenue.
    keys_text = ">:descendre q:quitter"
    text = f"{hp_text}  Niv {engine.depth}  {bag_text}  Seed {engine.seed}  {keys_text}"
    width = stdscr.getmaxyx()[1]
    safe_addstr(stdscr, engine.game_map.height, 0, text[: width - 1])


def draw_messages(stdscr: curses.window, engine: Engine) -> None:
    """Les derniers messages, du plus ancien (en haut) au plus récent (en bas)."""
    top = engine.game_map.height + 1
    width = stdscr.getmaxyx()[1]
    for row, text in enumerate(engine.log.last(MESSAGE_LINES)):
        safe_addstr(stdscr, top + row, 0, text[: width - 1])


def draw_box(stdscr: curses.window, engine: Engine, lines: list[str]) -> None:
    """Dessine une boîte encadrée, centrée sur la carte, contenant `lines`.

    La largeur s'adapte à la plus longue ligne. Sert au game over et aux menus.
    """
    inner_width = max(len(line) for line in lines) + 2  # 1 espace de marge de chaque côté
    border = "+" + "-" * inner_width + "+"
    boxed = [border] + [f"| {line.ljust(inner_width - 2)} |" for line in lines] + [border]

    top = max(engine.game_map.height // 2 - len(boxed) // 2, 0)
    left = max(engine.game_map.width // 2 - len(border) // 2, 0)
    for row, line in enumerate(boxed):
        try:
            stdscr.addstr(top + row, left, line, curses.A_BOLD)
        except curses.error:
            pass


def draw_question(stdscr: curses.window, lines: list[str]) -> None:
    """Écran simple : quelques lignes centrées dans le terminal.

    Utilisé AVANT qu'une partie existe (pas de carte à centrer), d'où un
    centrage sur la taille du terminal plutôt que sur la carte.
    """
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    top = max(height // 2 - len(lines) // 2, 0)
    for row, line in enumerate(lines):
        text = line[: max(width - 1, 0)]
        left = max(width // 2 - len(text) // 2, 0)
        safe_addstr(stdscr, top + row, left, text)
    stdscr.refresh()


def draw_game_over(stdscr: curses.window, engine: Engine) -> None:
    """Bandeau centré par-dessus la carte (on voit encore qui nous a tué)."""
    draw_box(stdscr, engine, ["", "      VOUS ETES MORT      ", "", "  Appuyez sur q pour quitter.", ""])


def draw_inventory(stdscr: curses.window, engine: Engine) -> None:
    """Liste du sac : « a) potion de soin », « b) … »."""
    inventory = engine.player.inventory
    assert inventory is not None
    lines = [f"Inventaire ({len(inventory.items)}/{inventory.capacity})", ""]
    if not inventory.items:
        lines.append("(vide)")
    for index, item in enumerate(inventory.items):
        letter = chr(ord("a") + index)  # 0 → 'a', 1 → 'b'…
        lines.append(f"{letter}) {item.name}")
    lines += ["", "Lettre : choisir   Echap : fermer"]
    draw_box(stdscr, engine, lines)


def draw_item_menu(stdscr: curses.window, engine: Engine, ui: UIState) -> None:
    """Que faire de l'objet choisi ?"""
    inventory = engine.player.inventory
    assert inventory is not None
    item = inventory.items[ui.selected]
    draw_box(stdscr, engine, [item.name, "", "u : utiliser", "j : jeter", "", "Echap : retour"])


def draw(stdscr: curses.window, engine: Engine, ui: UIState) -> None:
    """Redessine tout l'écran.

    Anti-clignotement : erase() (vide le tampon) et non clear() (qui force
    un redessin complet du terminal). refresh() n'envoie que les différences.
    """
    stdscr.erase()
    if not terminal_is_big_enough(stdscr, engine):
        draw_too_small(stdscr, engine)
    else:
        draw_map(stdscr, engine)
        draw_entities(stdscr, engine)
        draw_status_line(stdscr, engine)
        draw_messages(stdscr, engine)
        if engine.game_over:
            draw_game_over(stdscr, engine)
        elif ui.mode is Mode.INVENTORY:
            draw_inventory(stdscr, engine)
        elif ui.mode is Mode.ITEM_MENU:
            draw_item_menu(stdscr, engine, ui)
    stdscr.refresh()


def draw_entities(stdscr: curses.window, engine: Engine) -> None:
    """Dessine les entités VISIBLES, par-dessus la carte.

    Un monstre hors de vue n'est pas affiché, même sur une case explorée :
    on se souvient des lieux, pas de qui s'y trouvait.

    Ordre de dessin (le dernier dessiné est au-dessus) :
      1. les cadavres ;
      2. les objets (une potion sur un cadavre reste visible) ;
      3. ce qui bloque (monstres vivants) ;
      4. le joueur, toujours au-dessus.
    sorted() avec une clé tuple : comparaison élément par élément,
    et False (0) passe avant True (1) → (F, F) < (F, T) < (T, F).
    """
    game_map = engine.game_map
    for entity in sorted(game_map.entities, key=lambda e: (e.blocks_movement, isinstance(e, Item))):
        if entity is engine.player:
            continue
        if (entity.x, entity.y) in game_map.visible:
            safe_addstr(stdscr, entity.y, entity.x, entity.char)
    player = engine.player
    safe_addstr(stdscr, player.y, player.x, player.char)
