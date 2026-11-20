"""Tout l'affichage curses. Le seul module de game/ qui connaît curses.

Il LIT l'état du moteur (carte, joueur) mais ne le modifie jamais.
"""

from __future__ import annotations

import curses

from game.engine import Engine
from game.entities import Entity, Item, Projectile
from game.input import TITLE_OPTIONS, Mode, UIState

# Sous la carte : une ligne de statut (PV, seed, touches) + le journal.
MESSAGE_LINES = 5
HUD_HEIGHT = 1 + MESSAGE_LINES
HP_BAR_WIDTH = 10

# --- Styles (couleurs) ---------------------------------------------------------
#
# En curses, une couleur s'utilise via une « paire » numérotée
# (couleur du texte, couleur du fond), créée par init_pair(n, texte, fond).
# color_pair(n) donne l'attribut à passer à addstr ; on peut le combiner
# avec d'autres attributs par « | » (ex. gras : A_BOLD).
#
# On donne un NOM à chaque style ("player", "orc"…) : le reste du code
# demande style("orc") sans savoir comment c'est obtenu.

# nom → (couleur du texte, attribut en plus)
COLOR_STYLES: dict[str, tuple[int, int]] = {
    "player": (curses.COLOR_YELLOW, curses.A_BOLD),
    "goblin": (curses.COLOR_GREEN, curses.A_NORMAL),
    "orc": (curses.COLOR_RED, curses.A_BOLD),
    "potion": (curses.COLOR_MAGENTA, curses.A_BOLD),
    "arrow": (curses.COLOR_WHITE, curses.A_BOLD),
    "corpse": (curses.COLOR_RED, curses.A_NORMAL),
    "stairs": (curses.COLOR_CYAN, curses.A_BOLD),
    "wall": (curses.COLOR_WHITE, curses.A_BOLD),  # mur visible : blanc vif
    "floor": (curses.COLOR_WHITE, curses.A_NORMAL),
    "title": (curses.COLOR_YELLOW, curses.A_BOLD),
    "danger": (curses.COLOR_RED, curses.A_BOLD),
}

# Terminal sans couleurs : on se contente d'attributs (gras / atténué).
MONOCHROME_STYLES: dict[str, int] = {
    "player": curses.A_BOLD,
    "stairs": curses.A_BOLD,
    "wall": curses.A_BOLD,
    "title": curses.A_BOLD,
    "danger": curses.A_BOLD,
    "remembered": curses.A_DIM,
}

# Rempli par init_styles() (il faut que curses soit démarré pour créer les paires).
STYLES: dict[str, int] = {}

# Quel style pour quel caractère.
ENTITY_STYLE_BY_CHAR = {
    "@": "player",
    "g": "goblin",
    "o": "orc",
    "!": "potion",
    "%": "corpse",
    "-": "arrow",
    "|": "arrow",
}
TILE_STYLE_BY_CHAR = {"#": "wall", ".": "floor", ">": "stairs"}


def init_styles() -> None:
    """Crée les paires de couleurs. À appeler une fois, après l'init de curses."""
    STYLES.clear()
    if not curses.has_colors():
        STYLES.update(MONOCHROME_STYLES)
        return

    curses.start_color()
    try:
        curses.use_default_colors()  # -1 = garder le fond du terminal
        background = -1
    except curses.error:
        background = curses.COLOR_BLACK  # terminal qui ne le permet pas

    for pair_number, (name, (color, extra)) in enumerate(COLOR_STYLES.items(), start=1):
        curses.init_pair(pair_number, color, background)
        STYLES[name] = curses.color_pair(pair_number) | extra

    # Cases explorées hors de vue : la couleur n°8 est un gris foncé, mais
    # n'existe qu'avec au moins 16 couleurs. Sinon : texte atténué.
    if curses.COLORS >= 16:
        gray_pair = len(COLOR_STYLES) + 1
        curses.init_pair(gray_pair, 8, background)
        STYLES["remembered"] = curses.color_pair(gray_pair)
    else:
        STYLES["remembered"] = curses.A_DIM


def style(name: str) -> int:
    """L'attribut curses d'un style nommé (normal si inconnu)."""
    return STYLES.get(name, curses.A_NORMAL)


# --- Petits outils ---------------------------------------------------------------


def required_size(engine: Engine) -> tuple[int, int]:
    """Taille minimale du terminal (largeur, hauteur) : carte + HUD."""
    return engine.game_map.width, engine.game_map.height + HUD_HEIGHT


def terminal_is_big_enough(stdscr: curses.window, engine: Engine) -> bool:
    """La carte entière et le HUD tiennent-ils dans le terminal ?"""
    height, width = stdscr.getmaxyx()
    min_width, min_height = required_size(engine)
    return width >= min_width and height >= min_height


def safe_addstr(stdscr: curses.window, y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
    """addstr qui ignore les erreurs de bord.

    curses lève une erreur quand on écrit dans la toute dernière case de
    l'écran (coin bas-droit), car le curseur ne peut pas avancer après.
    Le texte est pourtant bien affiché : on ignore donc l'erreur.
    """
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_centered(stdscr: curses.window, lines: list[tuple[str, int]]) -> None:
    """Lignes (texte, style) centrées dans tout le terminal (écrans plein écran)."""
    height, width = stdscr.getmaxyx()
    top = max(height // 2 - len(lines) // 2, 0)
    for row, (line, attr) in enumerate(lines):
        text = line[: max(width - 1, 0)]
        left = max(width // 2 - len(text) // 2, 0)
        safe_addstr(stdscr, top + row, left, text, attr)


def draw_too_small(stdscr: curses.window, engine: Engine) -> None:
    """Écran d'avertissement quand le terminal est trop petit pour la carte."""
    height, width = stdscr.getmaxyx()
    min_width, min_height = required_size(engine)
    lines = [
        "Terminal trop petit !",
        f"Requis : {min_width}x{min_height}",
        f"Actuel : {width}x{height}",
        "Agrandis la fenêtre (ou q pour quitter).",
    ]
    for row, line in enumerate(lines):
        if row >= height:
            break
        # On coupe chaque ligne à la largeur dispo pour ne pas déborder.
        safe_addstr(stdscr, row, 0, line[: max(width - 1, 0)])


# --- Carte et entités --------------------------------------------------------------


def draw_map(stdscr: curses.window, engine: Engine) -> None:
    """Dessine les cases connues de la carte, depuis le coin haut-gauche.

    - visible  → couleur de la tuile (mur blanc vif, escalier cyan…) ;
    - explorée → gris (« souvenir »), quelle que soit la tuile ;
    - inconnue → rien (erase() a déjà mis un espace).
    On ne parcourt que `explored` (qui contient `visible`) : inutile de
    regarder les cases jamais vues.
    """
    game_map = engine.game_map
    remembered = style("remembered")
    for x, y in game_map.explored:
        char = game_map.get_tile(x, y).char
        if (x, y) in game_map.visible:
            attr = style(TILE_STYLE_BY_CHAR.get(char, ""))
        else:
            attr = remembered
        safe_addstr(stdscr, y, x, char, attr)


def render_layer(entity: Entity) -> int:
    """Couche de dessin : les couches basses sont dessinées d'abord, donc
    recouvertes par les suivantes si elles partagent une case.

      0 cadavres, 1 objets (une potion sur un cadavre reste visible),
      2 flèches en vol, 3 créatures vivantes (ce qui bloque le passage).
    """
    if entity.blocks_movement:
        return 3
    if isinstance(entity, Projectile):
        return 2
    if isinstance(entity, Item):
        return 1
    return 0


def entity_style(entity: Entity) -> int:
    return style(ENTITY_STYLE_BY_CHAR.get(entity.char, ""))


def draw_entities(stdscr: curses.window, engine: Engine) -> None:
    """Dessine les entités VISIBLES, par-dessus la carte.

    Un monstre hors de vue n'est pas affiché, même sur une case explorée :
    on se souvient des lieux, pas de qui s'y trouvait.

    Ordre de dessin : voir render_layer. Le joueur est dessiné en tout dernier.
    """
    game_map = engine.game_map
    for entity in sorted(game_map.entities, key=render_layer):
        if entity is engine.player:
            continue
        if (entity.x, entity.y) in game_map.visible:
            safe_addstr(stdscr, entity.y, entity.x, entity.char, entity_style(entity))
    player = engine.player
    safe_addstr(stdscr, player.y, player.x, player.char, entity_style(player))


# --- HUD -----------------------------------------------------------------------------


def hp_bar(hp: int, max_hp: int, width: int = HP_BAR_WIDTH) -> str:
    """Barre de PV en texte, ex. « [=====     ] ».

    Nombre de « = » proportionnel aux PV restants : hp / max_hp × largeur.
    La division entière // arrondit vers le bas ; on garde au moins un « = »
    tant qu'on est en vie, pour ne pas afficher une barre vide à 1 PV.
    """
    filled = hp * width // max_hp
    if hp > 0:
        filled = max(filled, 1)
    return "[" + "=" * filled + " " * (width - filled) + "]"


def draw_status_line(stdscr: curses.window, engine: Engine) -> None:
    """Ligne de statut juste sous la carte : PV, niveau, sac, seed, touches.

    La partie PV passe en rouge sous 1/3 des PV max : un signal d'alerte.
    """
    fighter = engine.player.fighter
    inventory = engine.player.inventory
    assert fighter is not None and inventory is not None
    row = engine.game_map.height
    width = stdscr.getmaxyx()[1]

    hp_text = f"PV {fighter.hp:>2}/{fighter.max_hp} {hp_bar(fighter.hp, fighter.max_hp)}"
    low_hp = fighter.hp * 3 <= fighter.max_hp
    safe_addstr(stdscr, row, 0, hp_text, style("danger") if low_hp else curses.A_NORMAL)

    bag_text = f"Sac {len(inventory.items)}/{inventory.capacity}"
    # Place limitée (80 colonnes) : les autres touches sont rappelées dans le
    # message de bienvenue.
    keys_text = ">:descendre q:quitter"
    rest = f"  Niv {engine.depth}  {bag_text}  Seed {engine.seed}  {keys_text}"
    safe_addstr(stdscr, row, len(hp_text), rest[: max(width - 1 - len(hp_text), 0)])


def draw_messages(stdscr: curses.window, engine: Engine) -> None:
    """Les derniers messages, du plus ancien (en haut) au plus récent (en bas).

    Le plus récent est en gras : on voit tout de suite ce qui vient d'arriver.
    """
    top = engine.game_map.height + 1
    width = stdscr.getmaxyx()[1]
    messages = engine.log.last(MESSAGE_LINES)
    for row, text in enumerate(messages):
        attr = curses.A_BOLD if row == len(messages) - 1 else curses.A_NORMAL
        safe_addstr(stdscr, top + row, 0, text[: width - 1], attr)


# --- Boîtes par-dessus la carte -----------------------------------------------------


def draw_box(stdscr: curses.window, engine: Engine, lines: list[str]) -> None:
    """Dessine une boîte encadrée, centrée sur la carte, contenant `lines`.

    La largeur s'adapte à la plus longue ligne. Sert aux menus et à la mort.
    """
    inner_width = max(len(line) for line in lines) + 2  # 1 espace de marge de chaque côté
    border = "+" + "-" * inner_width + "+"
    boxed = [border] + [f"| {line.ljust(inner_width - 2)} |" for line in lines] + [border]

    top = max(engine.game_map.height // 2 - len(boxed) // 2, 0)
    left = max(engine.game_map.width // 2 - len(border) // 2, 0)
    for row, line in enumerate(boxed):
        safe_addstr(stdscr, top + row, left, line, curses.A_BOLD)


def draw_death_banner(stdscr: curses.window, engine: Engine) -> None:
    """Bandeau par-dessus la carte, juste après la mort (on voit qui nous a tué)."""
    draw_box(stdscr, engine, ["", "      VOUS ÊTES MORT      ", "", "  Appuyez sur une touche...", ""])


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
    lines += ["", "Lettre : choisir   Échap : fermer"]
    draw_box(stdscr, engine, lines)


def draw_item_menu(stdscr: curses.window, engine: Engine, ui: UIState) -> None:
    """Que faire de l'objet choisi ?"""
    inventory = engine.player.inventory
    assert inventory is not None
    item = inventory.items[ui.selected]
    draw_box(stdscr, engine, [item.name, "", "u : utiliser", "j : jeter", "", "Échap : retour"])


def draw(stdscr: curses.window, engine: Engine, ui: UIState) -> None:
    """Redessine tout l'écran de jeu.

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
            draw_death_banner(stdscr, engine)
        elif ui.mode is Mode.INVENTORY:
            draw_inventory(stdscr, engine)
        elif ui.mode is Mode.ITEM_MENU:
            draw_item_menu(stdscr, engine, ui)
    stdscr.refresh()


# --- Écrans plein écran (titre, mort) --------------------------------------------------

GAME_TITLE = "Donjon ASCII"  # nom affiché (modifiable librement)


def draw_title(stdscr: curses.window, selected: int, enabled: list[bool], notice: str = "") -> None:
    """Écran titre : nom du jeu, options (la sélection est en vidéo inverse)."""
    stdscr.erase()
    lines: list[tuple[str, int]] = [(GAME_TITLE.upper(), style("title")), ("", 0)]
    lines.append(("@ . . . g . . . . o . . . ! . . . >", style("stairs")))
    lines += [("", 0), ("", 0)]
    for index, (_, label, shortcut) in enumerate(TITLE_OPTIONS):
        text = f"  {label} ({shortcut})  "
        if not enabled[index]:
            attr = style("remembered")  # option grisée (pas de sauvegarde)
        elif index == selected:
            attr = curses.A_REVERSE | curses.A_BOLD  # vidéo inverse = sélection
        else:
            attr = curses.A_NORMAL
        lines.append((text, attr))
    lines += [("", 0), ("Flèches / j k : choisir   Entrée : valider", style("remembered"))]
    if notice:
        lines += [("", 0), (notice, style("danger"))]
    draw_centered(stdscr, lines)
    stdscr.refresh()


def draw_death_screen(stdscr: curses.window, engine: Engine) -> None:
    """Écran de fin de partie : le score."""
    stdscr.erase()
    draw_centered(
        stdscr,
        [
            ("VOUS ÊTES MORT", style("danger")),
            ("", 0),
            (f"Niveau atteint : {engine.depth}", curses.A_BOLD),
            (f"Monstres tués : {engine.kills}", curses.A_BOLD),
            (f"Seed : {engine.seed}", curses.A_NORMAL),
            ("", 0),
            (f"(rejouer ce donjon : --seed {engine.seed})", style("remembered")),
            ("", 0),
            ("Entrée : écran titre     q : quitter", curses.A_NORMAL),
        ],
    )
    stdscr.refresh()
