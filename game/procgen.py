"""Génération des cartes.

M2 : une seule salle codée en dur (la vraie génération aléatoire arrive en M3).
"""

from __future__ import annotations

from game.map import FLOOR, WALL, GameMap

MAP_WIDTH = 80
MAP_HEIGHT = 40


def generate_test_room() -> tuple[GameMap, tuple[int, int]]:
    """Crée une carte pleine de murs avec une salle creusée dedans.

    Retourne la carte et la position de départ du joueur (x, y).
    """
    game_map = GameMap(MAP_WIDTH, MAP_HEIGHT, fill=WALL)

    # Salle : intérieur de x=10..69 et y=5..34 (bornes incluses).
    for y in range(5, 35):
        for x in range(10, 70):
            game_map.set_tile(x, y, FLOOR)

    # Un pilier 4×3 au milieu, pour tester les collisions ailleurs qu'au bord.
    for y in range(18, 21):
        for x in range(38, 42):
            game_map.set_tile(x, y, WALL)

    start = (20, 20)
    return game_map, start
