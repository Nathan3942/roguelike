"""Le moteur : l'état du jeu et la gestion des tours.

Règle d'or : ce module n'importe JAMAIS curses. Il ne sait pas comment le jeu
est affiché ; il ne fait que des calculs sur la carte et les entités.
C'est ce qui permet de le tester avec unittest, sans terminal.

Déroulement d'un tour :
  1. le joueur agit (se déplacer ou attendre) ;
  2. si son action a « coûté » un tour, on recalcule sa vision,
     puis chaque monstre agit à son tour ;
  3. si l'action n'a rien fait (foncer dans un mur), le monde ne bouge pas.
"""

from __future__ import annotations

from game.actions import Action, MoveAction, QuitAction, WaitAction
from game.entities import Actor
from game.fov import compute_fov
from game.map import GameMap

FOV_RADIUS = 8


class Engine:
    def __init__(self, game_map: GameMap, player: Actor, seed: int) -> None:
        self.game_map = game_map
        self.player = player
        self.seed = seed  # gardée pour l'afficher (et rejouer le même donjon)
        self.running = True  # passe à False quand le joueur quitte
        # Le joueur est une entité de la carte comme les autres : ainsi les
        # monstres le voient comme un obstacle (pas de superposition).
        if player not in game_map.entities:
            game_map.entities.append(player)
        self.update_fov()  # le joueur voit autour de lui dès le départ

    def handle_action(self, action: Action) -> None:
        """Applique une action du joueur, puis fait jouer les monstres si besoin."""
        if isinstance(action, QuitAction):
            self.running = False
        elif isinstance(action, WaitAction):
            self.end_turn()
        elif isinstance(action, MoveAction):
            if self.move_player(action.dx, action.dy):
                self.end_turn()
            # Déplacement bloqué : pas de tour consommé, les monstres attendent.

    def move_player(self, dx: int, dy: int) -> bool:
        """Déplace le joueur si la case visée est libre.

        Retourne True si le déplacement a eu lieu, False s'il a été bloqué
        (mur, bord de carte ou monstre). On vérifie AVANT de bouger, plutôt
        que de bouger puis annuler : l'état reste toujours valide.
        """
        new_x = self.player.x + dx
        new_y = self.player.y + dy
        if not self.game_map.is_free(new_x, new_y):
            return False
        self.player.x = new_x
        self.player.y = new_y
        return True

    def end_turn(self) -> None:
        """Fin du tour du joueur : mise à jour de la vision, puis les monstres."""
        # La vision d'abord : les monstres décident selon la NOUVELLE position
        # du joueur (et ce qu'il voit maintenant).
        self.update_fov()
        self.handle_enemy_turns()

    def handle_enemy_turns(self) -> None:
        """Chaque monstre joue une fois, dans l'ordre de la liste."""
        # list(...) : copie de la liste, pour pouvoir plus tard (M6) retirer un
        # monstre mort pendant qu'on parcourt les entités sans tout casser.
        for entity in list(self.game_map.entities):
            if isinstance(entity, Actor) and entity.ai is not None:
                entity.ai.take_turn(entity, self)

    def update_fov(self) -> None:
        """Recalcule ce que voit le joueur et l'ajoute à la mémoire d'exploration."""
        game_map = self.game_map
        game_map.visible = compute_fov(game_map, self.player.x, self.player.y, FOV_RADIUS)
        # |= : union d'ensembles. Ce qui a été vu une fois reste exploré.
        game_map.explored |= game_map.visible
