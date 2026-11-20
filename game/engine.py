"""Le moteur : l'état du jeu et l'application des actions.

Règle d'or : ce module n'importe JAMAIS curses. Il ne sait pas comment le jeu
est affiché ; il ne fait que des calculs sur la carte et les entités.
C'est ce qui permet de le tester avec unittest, sans terminal.
"""

from __future__ import annotations

from game.actions import Action, MoveAction, QuitAction
from game.entities import Entity
from game.fov import compute_fov
from game.map import GameMap

FOV_RADIUS = 8


class Engine:
    def __init__(self, game_map: GameMap, player: Entity, seed: int) -> None:
        self.game_map = game_map
        self.player = player
        self.seed = seed  # gardée pour l'afficher (et rejouer le même donjon)
        self.running = True  # passe à False quand le joueur quitte
        self.update_fov()  # le joueur voit autour de lui dès le départ

    def handle_action(self, action: Action) -> None:
        """Applique une action à l'état du jeu."""
        if isinstance(action, QuitAction):
            self.running = False
        elif isinstance(action, MoveAction):
            if self.move_player(action.dx, action.dy):
                self.update_fov()  # on ne recalcule que si le joueur a bougé

    def move_player(self, dx: int, dy: int) -> bool:
        """Déplace le joueur si la case visée est praticable.

        Retourne True si le déplacement a eu lieu, False s'il a été bloqué
        (mur ou bord de carte). On vérifie AVANT de bouger, plutôt que de bouger
        puis annuler : l'état reste toujours valide.
        """
        new_x = self.player.x + dx
        new_y = self.player.y + dy
        if not self.game_map.is_walkable(new_x, new_y):
            return False
        self.player.x = new_x
        self.player.y = new_y
        return True

    def update_fov(self) -> None:
        """Recalcule ce que voit le joueur et l'ajoute à la mémoire d'exploration."""
        game_map = self.game_map
        game_map.visible = compute_fov(game_map, self.player.x, self.player.y, FOV_RADIUS)
        # |= : union d'ensembles. Ce qui a été vu une fois reste exploré.
        game_map.explored |= game_map.visible
