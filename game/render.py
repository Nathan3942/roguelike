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

# Dessins de l'écran titre. Chaînes « brutes » (r"""…""") : les antislashs
# « \ » y sont pris tels quels au lieu de démarrer une séquence comme « \n ».
# Piège : une chaîne brute ne peut pas FINIR par un antislash.
TITLE_CASTLE = r"""
       |>>>                          |>>>                          |>>>
       |                             |                _.           |
      /^\        \,/             _   _   _    v      ( (          /^\
     / ' \                      |=|_|=|_|=|           `-'        / ' \
    /' ' '\          v          |   /^\   |                     /' ' '\
   / ' ' ' \                    |   |#|   |                    / ' ' ' \
  /' ' ' ' '\            _   _  |         |  _   _            /' ' ' ' '\
 /___________\          |=|_|=|_|=|_|=|_|=|_|=|_|=|          /___________\
  |_|_|_|_|_|           |_|_|_|_|_|_|_|_|_|_|_|_|_|           |_|_|_|_|_|
  | _|      |           |  .-.               .-.  |           |      |_ |
  |   [|]   | [_]  [_]  |  |*|   /\     /\   |*|  |  [_]  [_] |   [|]   |
  |   [|]   |___________|  |*|   ||     ||   |*|  |___________|   [|]   |
  |      _| |           |  \ /               \ /  |           | |_      |
  |   /^\   |  [|]  [|] |   V     _______     V   | [|]  [|]  |   /^\   |
  |   |#|   |           |        /       \        |           |   |#|   |
  |   |_|   | _|        |   (*) / |-+-+-| \ (*)   |        |_ |   |_|   |
  | _|      |        _| |    |  | |-+-+-| |  |    | |_        |      |_ |
  |      _| |     _|    | _|    | |-+-+-| |    |_ |    |_     | |_      |
  |   [|]   |           |       | |-+-+-| |       |           |   [|]   |
  |  _|     |  _|       |  _|   | |-+-+-| |   |_  |       |_  |     |_  |
  |         |           |       | |-+-+-| |       |           |         |
_______________________________|___________|_______________________________
 ~~~   ~~~~   ~~~   ~~~~   ~~~ |=|=|=|=|=|=|  ~~~~   ~~~   ~~~~   ~~~   ~~~
~~   ~~~~   ~~~~~   ~~~   ~~~~~|=|=|=|=|=|=|~   ~~~   ~~~~~   ~~~   ~~~~~
 ,  ' ,   .  ,  '  ,  .   ' , /             \ ,  '  ,  .   ' ,  .  ,  ' , .
""".strip("\n").splitlines()

TITLE_BIG_TEXT = r"""
 ___     ___    _  _      _    ___    _  _
|   \   / _ \  | \| |  _ | |  / _ \  | \| |
| |) | | (_) | | .` | | || | | (_) | | .` |
|___/   \___/  |_|\_|  \__/   \___/  |_|\_|
""".strip("\n").splitlines()

TITLE_SUBTITLE = "~  A  S  C  I  I  ~"

# Couleur de certains caractères du château ; tout le reste en style « wall ».
CASTLE_CHAR_STYLES = {
    ">": "danger",      # drapeaux rouges
    "~": "stairs",      # douves cyan
    "+": "remembered",  # herse grise
    "*": "title",       # torches et bannières jaunes
    "#": "title",       # fenêtres éclairées
    ",": "goblin",      # herbe verte
}


def art_width(lines: list[str]) -> int:
    return max(len(line) for line in lines)


def draw_art(stdscr: curses.window, top: int, lines: list[str], char_styles: dict[str, str], default: str) -> None:
    """Dessine un bloc ASCII art centré horizontalement, caractère par caractère.

    Toutes les lignes partagent la MÊME marge gauche (calculée sur la plus
    large) : centrer chaque ligne séparément décalerait les murs et déformerait
    le dessin. Les espaces ne sont pas dessinés (le fond reste propre).
    """
    width = stdscr.getmaxyx()[1]
    left = max((width - art_width(lines)) // 2, 0)
    for row, line in enumerate(lines):
        for col, char in enumerate(line):
            if char != " ":
                safe_addstr(stdscr, top + row, left + col, char, style(char_styles.get(char, default)))


def title_menu_lines(selected: int, enabled: list[bool]) -> list[tuple[str, int]]:
    """Les lignes du menu (texte, style), communes aux deux mises en page."""
    lines: list[tuple[str, int]] = []
    for index, (_, label, shortcut) in enumerate(TITLE_OPTIONS):
        if not enabled[index]:
            text, attr = f"   {label} ({shortcut})   ", style("remembered")  # grisée
        elif index == selected:
            # Flèches de part et d'autre + vidéo inverse : bien visible.
            text, attr = f">  {label} ({shortcut})  <", curses.A_REVERSE | curses.A_BOLD
        else:
            text, attr = f"   {label} ({shortcut})   ", curses.A_NORMAL
        lines.append((text, attr))
    return lines


def draw_title(stdscr: curses.window, selected: int, enabled: list[bool], notice: str = "") -> None:
    """Écran titre : château, nom du jeu en grandes lettres, menu.

    Deux mises en page :
    - grand terminal : château + grand titre + menu ;
    - petit terminal : version compacte (le dessin ne tiendrait pas).
    """
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    menu = title_menu_lines(selected, enabled)
    hint = ("Flèches / j k : choisir   Entrée : valider", style("remembered"))
    footer: list[tuple[str, int]] = [("", 0), *menu, ("", 0), hint]
    if notice:
        footer += [("", 0), (notice, style("danger"))]

    # Hauteur totale de la grande version : château, 1 blanc, titre, sous-titre.
    art_height = len(TITLE_CASTLE) + 1 + len(TITLE_BIG_TEXT) + 1
    fits = width > art_width(TITLE_CASTLE) and height >= art_height + len(footer) + 2

    if not fits:
        # Version compacte (celle d'avant), centrée ligne par ligne.
        compact = [(GAME_TITLE.upper(), style("title")), ("", 0)]
        compact.append(("@ . . . g . . . . o . . . ! . . . >", style("stairs")))
        draw_centered(stdscr, compact + [("", 0)] + footer)
        stdscr.refresh()
        return

    # Grande version : tout le bloc est centré verticalement.
    top = max((height - art_height - len(footer)) // 2, 0)
    draw_art(stdscr, top, TITLE_CASTLE, CASTLE_CHAR_STYLES, default="wall")
    title_top = top + len(TITLE_CASTLE) + 1
    draw_art(stdscr, title_top, TITLE_BIG_TEXT, {}, default="title")
    subtitle_row = title_top + len(TITLE_BIG_TEXT)
    left = max((width - len(TITLE_SUBTITLE)) // 2, 0)
    safe_addstr(stdscr, subtitle_row, left, TITLE_SUBTITLE, style("title"))

    # Le menu sous le titre, chaque ligne centrée (pas un dessin : pas de souci).
    for offset, (text, attr) in enumerate(footer, start=1):
        safe_addstr(stdscr, subtitle_row + offset, max((width - len(text)) // 2, 0), text, attr)
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
