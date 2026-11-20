"""Le moteur : l'état du jeu et la gestion des tours.

Règle d'or : ce module n'importe JAMAIS curses. Il ne sait pas comment le jeu
est affiché ; il ne fait que des calculs sur la carte et les entités.
C'est ce qui permet de le tester avec unittest, sans terminal.

Déroulement d'un tour :
  1. le joueur agit : se déplacer, attaquer (en « fonçant » sur un monstre),
     attendre, ramasser / utiliser / jeter un objet, descendre ;
  2. si son action a « coûté » un tour, on recalcule sa vision,
     puis chaque monstre vivant agit à son tour ;
  3. si l'action n'a rien fait (foncer dans un mur), le monde ne bouge pas.
"""

from __future__ import annotations

from game.actions import (
    Action,
    DescendAction,
    DropItemAction,
    MoveAction,
    PickupAction,
    QuitAction,
    UseItemAction,
    WaitAction,
)
from game.entities import Actor, Item
from game.fov import compute_fov
from game.map import STAIRS, GameMap
from game.messages import MessageLog, capitalize, elide
from game.procgen import generate_floor

FOV_RADIUS = 8


class Engine:
    def __init__(self, game_map: GameMap, player: Actor, seed: int, depth: int = 1) -> None:
        self.game_map = game_map
        self.player = player
        self.seed = seed  # gardée pour l'afficher et générer les étages suivants
        self.depth = depth  # étage courant (1 = le premier)
        self.running = True  # passe à False quand le joueur quitte
        self.game_over = False  # passe à True à la mort du joueur
        self.log = MessageLog()
        # Le joueur est une entité de la carte comme les autres : ainsi les
        # monstres le voient comme un obstacle (pas de superposition).
        if player not in game_map.entities:
            game_map.entities.append(player)
        self.update_fov()  # le joueur voit autour de lui dès le départ
        self.log.add("Bienvenue ! g ramasser, i inventaire, > descendre, . attendre, q quitter.")

    # --- Actions du joueur -----------------------------------------------------

    def handle_action(self, action: Action) -> None:
        """Applique une action du joueur, puis fait jouer les monstres si besoin."""
        if isinstance(action, QuitAction):
            self.running = False
            return
        if self.game_over:
            return  # mort : plus rien ne se passe, seul « quitter » compte

        # Chaque branche calcule « l'action a-t-elle pris du temps ? ».
        # Une action ratée (mur, sac plein, rien à ramasser…) ne coûte rien.
        took_turn = False
        if isinstance(action, WaitAction):
            took_turn = True
        elif isinstance(action, MoveAction):
            took_turn = self.bump(action.dx, action.dy)
        elif isinstance(action, PickupAction):
            took_turn = self.pickup()
        elif isinstance(action, UseItemAction):
            took_turn = self.use_item(action.index)
        elif isinstance(action, DropItemAction):
            took_turn = self.drop_item(action.index)
        elif isinstance(action, DescendAction):
            self.descend()  # nouvel étage : les monstres n'agissent pas ce tour-ci

        if took_turn:
            self.end_turn()

    def bump(self, dx: int, dy: int) -> bool:
        """« Foncer » dans une direction : attaque s'il y a un monstre, sinon
        déplacement. Retourne True si l'action a consommé un tour."""
        if (dx, dy) == (0, 0):
            return False  # sinon la « cible » serait… le joueur lui-même
        target = self.game_map.get_blocking_entity_at(self.player.x + dx, self.player.y + dy)
        if isinstance(target, Actor) and target.is_alive:
            self.attack(self.player, target)
            return True
        return self.move_player(dx, dy)

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
        # Petit confort : signaler les objets sur la case d'arrivée.
        for item in self.items_at(new_x, new_y):
            self.log.add(f"Vous voyez ici : {item.name} (g pour ramasser).")
        if self.game_map.get_tile(new_x, new_y) is STAIRS:
            self.log.add("Un escalier descend ici (> pour descendre).")
        return True

    # --- Étages ------------------------------------------------------------------

    def descend(self) -> bool:
        """Descend à l'étage suivant si le joueur est sur l'escalier.

        On génère une carte NEUVE, mais on garde le MÊME objet joueur :
        ses PV et son sac le suivent sans rien copier. L'ancien étage est
        simplement oublié (pas de retour en arrière).
        """
        if self.game_map.get_tile(self.player.x, self.player.y) is not STAIRS:
            self.log.add("Il n'y a pas d'escalier ici.")
            return False

        self.depth += 1
        game_map, rooms = generate_floor(self.seed, self.depth)
        self.player.x, self.player.y = rooms[0].center
        game_map.entities.append(self.player)
        self.game_map = game_map
        self.update_fov()
        self.log.add(f"Vous descendez au niveau {self.depth}.")
        return True

    # --- Objets ------------------------------------------------------------------

    def items_at(self, x: int, y: int) -> list[Item]:
        """Les objets posés au sol en (x, y)."""
        return [e for e in self.game_map.entities if isinstance(e, Item) and e.x == x and e.y == y]

    def pickup(self) -> bool:
        """Ramasse UN objet sous le joueur. Retourne True si un tour est passé."""
        inventory = self.player.inventory
        assert inventory is not None
        items = self.items_at(self.player.x, self.player.y)
        if not items:
            self.log.add("Il n'y a rien à ramasser ici.")
            return False
        if inventory.is_full:
            self.log.add("Votre sac est plein.")
            return False
        item = items[0]
        # L'objet QUITTE la carte et ENTRE dans le sac : il n'est jamais aux
        # deux endroits à la fois.
        self.game_map.entities.remove(item)
        inventory.items.append(item)
        self.log.add(f"Ramassé : {item.name}.")
        return True

    def use_item(self, index: int) -> bool:
        """Utilise l'objet n° index du sac. Retourne True si un tour est passé."""
        inventory = self.player.inventory
        assert inventory is not None
        if not 0 <= index < len(inventory.items):
            return False
        item = inventory.items[index]
        if item.consumable is None:
            self.log.add(f"Impossible d'utiliser : {item.name}.")
            return False
        consumed = item.consumable.use(self.player, self)
        if consumed:
            inventory.items.remove(item)
        return consumed

    def drop_item(self, index: int) -> bool:
        """Pose l'objet n° index du sac aux pieds du joueur."""
        inventory = self.player.inventory
        assert inventory is not None
        if not 0 <= index < len(inventory.items):
            return False
        item = inventory.items.pop(index)
        item.x, item.y = self.player.x, self.player.y
        self.game_map.entities.append(item)
        self.log.add(f"Jeté : {item.name}.")
        return True

    # --- Combat ----------------------------------------------------------------

    def attack(self, attacker: Actor, target: Actor) -> None:
        """Une attaque : dégâts = attaque − défense (minimum 0), puis message."""
        assert attacker.fighter is not None and target.fighter is not None
        damage = max(attacker.fighter.attack - target.fighter.defense, 0)

        # Phrase différente selon que c'est le joueur qui attaque ou qui subit.
        if attacker is self.player:
            text = f"Vous attaquez {elide('le', target.name)}"
        elif target is self.player:
            text = capitalize(f"{elide('le', attacker.name)} vous attaque")
        else:
            text = capitalize(f"{elide('le', attacker.name)} attaque {elide('le', target.name)}")

        if damage > 0:
            plural = "s" if damage > 1 else ""
            self.log.add(f"{text} : {damage} dégât{plural}.")
            target.fighter.take_damage(damage)
        else:
            self.log.add(f"{text}, sans effet.")

        if target.fighter.is_dead:
            self.kill(target)

    def kill(self, actor: Actor) -> None:
        """Mort d'un acteur : il devient un cadavre (ou la partie s'arrête)."""
        if actor is self.player:
            self.log.add("Vous êtes mort !")
            actor.char = "%"
            self.game_over = True
            return

        self.log.add(capitalize(f"{elide('le', actor.name)} meurt !"))
        # Transformation sur place : même objet, mais inoffensif et traversable.
        actor.char = "%"
        actor.blocks_movement = False
        actor.ai = None
        actor.name = f"cadavre {elide('de', actor.name)}"

    # --- Fin de tour -------------------------------------------------------------

    def end_turn(self) -> None:
        """Fin du tour du joueur : mise à jour de la vision, puis les monstres."""
        # La vision d'abord : les monstres décident selon la NOUVELLE position
        # du joueur (et ce qu'il voit maintenant).
        self.update_fov()
        self.handle_enemy_turns()

    def handle_enemy_turns(self) -> None:
        """Chaque monstre vivant joue une fois, dans l'ordre de la liste."""
        # list(...) : on parcourt une COPIE, la liste réelle peut ainsi changer
        # pendant la boucle sans effet de bord.
        for entity in list(self.game_map.entities):
            if self.game_over:
                break  # le joueur vient de mourir : les autres n'ont plus à jouer
            if isinstance(entity, Actor) and entity.ai is not None and entity.is_alive:
                entity.ai.take_turn(entity, self)

    def update_fov(self) -> None:
        """Recalcule ce que voit le joueur et l'ajoute à la mémoire d'exploration."""
        game_map = self.game_map
        game_map.visible = compute_fov(game_map, self.player.x, self.player.y, FOV_RADIUS)
        # |= : union d'ensembles. Ce qui a été vu une fois reste exploré.
        game_map.explored |= game_map.visible
