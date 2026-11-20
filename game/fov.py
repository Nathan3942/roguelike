"""Champ de vision (FOV, « field of view »).

Algorithme choisi : lancer un rayon vers CHAQUE case du cercle de vision.
C'est le plus simple à comprendre (et assez rapide pour un rayon de 8 :
~200 cases × ~8 pas = quelques milliers d'opérations par tour).

Pour chaque case cible dans le cercle :
  1. on trace une ligne droite (Bresenham) du joueur jusqu'à la cible ;
  2. si TOUTES les cases intermédiaires laissent passer le regard, la cible est
     visible (la cible elle-même peut être un mur : on voit le mur, pas derrière).

Défaut connu de cette méthode : en longeant un mur, la ligne vers un mur un peu
plus loin « frôle » le mur et le touche avant d'arriver → ce mur paraîtrait
invisible alors que le sol juste devant est visible. D'où l'étape 3 :
  3. passe de « finition » : un mur est visible s'il borde une case de sol
     visible. Intuitivement : si tu vois le sol, tu vois le mur qui le borde.
     (détail des coins : voir wall_touches_floor)
"""

from __future__ import annotations

from collections.abc import Iterator

from game.map import GameMap


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
    """Cases d'une ligne droite de (x0, y0) à (x1, y1), extrémités comprises.

    Algorithme de Bresenham : on avance case par case le long de l'axe principal
    et on garde une « erreur » entière qui mesure de combien la ligne idéale
    s'écarte de la case courante. Quand l'erreur devient trop grande, on fait
    aussi un pas sur l'autre axe. Que des entiers, pas de flottants.
    """
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)  # négatif : simplifie les comparaisons ci-dessous
    step_x = 1 if x0 < x1 else -1
    step_y = 1 if y0 < y1 else -1
    error = dx + dy

    x, y = x0, y0
    while True:
        yield x, y
        if x == x1 and y == y1:
            return
        doubled = 2 * error
        if doubled >= dy:  # assez en retard sur x → pas horizontal
            error += dy
            x += step_x
        if doubled <= dx:  # assez en retard sur y → pas vertical
            error += dx
            y += step_y


def in_radius(dx: int, dy: int, radius: int) -> bool:
    """Le décalage (dx, dy) est-il dans le cercle de vision ?

    On compare des carrés (pas de racine carrée). Le `+ radius` arrondit un peu
    le cercle : sans lui, il a des « pointes » disgracieuses en haut/bas/côtés.
    """
    return dx * dx + dy * dy <= radius * radius + radius


def has_line_of_sight(game_map: GameMap, x0: int, y0: int, x1: int, y1: int) -> bool:
    """Vrai si rien d'opaque ne se trouve STRICTEMENT entre les deux points."""
    for x, y in bresenham_line(x0, y0, x1, y1):
        if (x, y) in ((x0, y0), (x1, y1)):
            continue  # on ignore le départ (le joueur) et l'arrivée (la cible)
        if not game_map.is_transparent(x, y):
            return False
    return True


def compute_fov(game_map: GameMap, origin_x: int, origin_y: int, radius: int) -> set[tuple[int, int]]:
    """Retourne l'ensemble des cases visibles depuis (origin_x, origin_y)."""
    visible: set[tuple[int, int]] = {(origin_x, origin_y)}

    # Étapes 1 et 2 : un rayon vers chaque case du carré englobant le cercle.
    for y in range(origin_y - radius, origin_y + radius + 1):
        for x in range(origin_x - radius, origin_x + radius + 1):
            if not game_map.in_bounds(x, y):
                continue
            if not in_radius(x - origin_x, y - origin_y, radius):
                continue
            if has_line_of_sight(game_map, origin_x, origin_y, x, y):
                visible.add((x, y))

    # Étape 3 : les murs qui bordent du sol visible sont visibles aussi.
    # On ne part que du sol vu (transparent), pour ne pas « voir à travers »
    # un mur en enchaînant de mur en mur.
    seen_floor = [(x, y) for (x, y) in visible if game_map.is_transparent(x, y)]
    for x, y in seen_floor:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if (
                    game_map.in_bounds(nx, ny)
                    and not game_map.is_transparent(nx, ny)
                    and in_radius(nx - origin_x, ny - origin_y, radius)
                    and wall_touches_floor(game_map, x, y, dx, dy)
                ):
                    visible.add((nx, ny))

    return visible


def wall_touches_floor(game_map: GameMap, x: int, y: int, dx: int, dy: int) -> bool:
    """Le mur en (x+dx, y+dy) « borde »-t-il vraiment le sol en (x, y) ?

    - Voisin par un côté (dx ou dy nul) : oui.
    - Voisin en diagonale : seulement si c'est un COIN, c'est-à-dire si les
      deux cases entre eux sont opaques. Exemple, sol S visible, mur M :

          # M          . M
          S #   oui    S .   non : ce M touche du sol qu'on ne voit
                             peut-être pas, il ne doit pas s'allumer.
    """
    if dx == 0 or dy == 0:
        return True
    return not game_map.is_transparent(x + dx, y) and not game_map.is_transparent(x, y + dy)
