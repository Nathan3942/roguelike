"""Sauvegarde et chargement de la partie (format JSON lisible).

Principe : JSON ne connaît que des types simples (dict, list, str, int,
float, bool, None). On convertit donc nos objets en dictionnaires
(« sérialiser »), et inversement au chargement (« désérialiser »).

Chaque classe a sa paire de fonctions xxx_to_dict / xxx_from_dict, écrites à
la main : c'est un peu long, mais on voit EXACTEMENT ce qui est sauvé, et le
format ne change pas par accident si on renomme un attribut.

Ce qu'on ne sauve PAS, car on sait le recalculer :
  - `visible` : recalculé par update_fov() au chargement ;
  - le mode d'interface (menus) : on reprend toujours sur la carte.

Ce module ne dépend pas de curses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from game.components import Fighter, Healing, HostileAI, Inventory
from game.engine import Engine
from game.entities import Actor, Entity, Item
from game.map import FLOOR, STAIRS, WALL, GameMap, Tile

# ~/.roguelike/save.json — Path.home() marche sous Linux ET Windows
# (C:\Users\<nom>\.roguelike\save.json).
SAVE_PATH = Path.home() / ".roguelike" / "save.json"

# Numéro de format : si un jour le format change, on saura reconnaître (et
# refuser proprement) une ancienne sauvegarde.
SAVE_VERSION = 1

# Une tuile est sauvée par son caractère. Au chargement, on retrouve l'objet
# Tile PARTAGÉ correspondant (le moteur compare avec `is STAIRS`).
TILES_BY_CHAR: dict[str, Tile] = {tile.char: tile for tile in (WALL, FLOOR, STAIRS)}

JSON = dict[str, Any]  # alias de type : « un dictionnaire prêt pour JSON »


# --- Composants ------------------------------------------------------------------


def fighter_to_dict(fighter: Fighter) -> JSON:
    return {"max_hp": fighter.max_hp, "hp": fighter.hp, "attack": fighter.attack, "defense": fighter.defense}


def fighter_from_dict(data: JSON) -> Fighter:
    return Fighter(max_hp=data["max_hp"], hp=data["hp"], attack=data["attack"], defense=data["defense"])


def consumable_to_dict(consumable: Healing | None) -> JSON | None:
    if consumable is None:
        return None
    return {"type": "healing", "amount": consumable.amount}


def consumable_from_dict(data: JSON | None) -> Healing | None:
    if data is None:
        return None
    if data["type"] == "healing":
        return Healing(amount=data["amount"])
    raise ValueError(f"Effet d'objet inconnu : {data['type']}")


# --- Entités -------------------------------------------------------------------
# Un champ "type" indique quelle classe recréer : "entity", "actor" ou "item".


def entity_to_dict(entity: Entity) -> JSON:
    data: JSON = {
        "x": entity.x,
        "y": entity.y,
        "char": entity.char,
        "name": entity.name,
        "blocks_movement": entity.blocks_movement,
    }
    # isinstance teste aussi les sous-classes : on teste donc les classes
    # les plus précises (Actor, Item) avant la classe de base.
    if isinstance(entity, Actor):
        data["type"] = "actor"
        # L'IA n'a pas d'état interne : on note juste sa présence.
        data["ai"] = "hostile" if isinstance(entity.ai, HostileAI) else None
        data["fighter"] = fighter_to_dict(entity.fighter) if entity.fighter else None
        data["inventory"] = (
            {
                "capacity": entity.inventory.capacity,
                "items": [entity_to_dict(item) for item in entity.inventory.items],
            }
            if entity.inventory
            else None
        )
    elif isinstance(entity, Item):
        data["type"] = "item"
        data["consumable"] = consumable_to_dict(entity.consumable)
    else:
        data["type"] = "entity"
    return data


def entity_from_dict(data: JSON) -> Entity:
    common = {
        "x": data["x"],
        "y": data["y"],
        "char": data["char"],
        "name": data["name"],
        "blocks_movement": data["blocks_movement"],
    }
    kind = data["type"]
    if kind == "actor":
        inventory = None
        if data["inventory"] is not None:
            items = [entity_from_dict(item) for item in data["inventory"]["items"]]
            inventory = Inventory(
                capacity=data["inventory"]["capacity"],
                items=[item for item in items if isinstance(item, Item)],
            )
        return Actor(
            **common,  # ** « déballe » le dictionnaire en arguments nommés
            ai=HostileAI() if data["ai"] == "hostile" else None,
            fighter=fighter_from_dict(data["fighter"]) if data["fighter"] else None,
            inventory=inventory,
        )
    if kind == "item":
        return Item(**common, consumable=consumable_from_dict(data["consumable"]))
    if kind == "entity":
        return Entity(**common)
    raise ValueError(f"Type d'entité inconnu : {kind}")


# --- Carte ---------------------------------------------------------------------


def map_to_dict(game_map: GameMap) -> JSON:
    return {
        "width": game_map.width,
        "height": game_map.height,
        # Une chaîne par ligne : le donjon reste lisible dans le fichier JSON !
        "tiles": ["".join(tile.char for tile in row) for row in game_map.tiles],
        # sorted() : même partie → même fichier (un set n'a pas d'ordre fixe).
        "explored": sorted([x, y] for x, y in game_map.explored),
    }


def map_from_dict(data: JSON) -> GameMap:
    game_map = GameMap(data["width"], data["height"])
    for y, row in enumerate(data["tiles"]):
        for x, char in enumerate(row):
            game_map.set_tile(x, y, TILES_BY_CHAR[char])
    game_map.explored = {(x, y) for x, y in data["explored"]}
    return game_map


# --- Partie complète -------------------------------------------------------------


def engine_to_dict(engine: Engine) -> JSON:
    entities = engine.game_map.entities
    return {
        "version": SAVE_VERSION,
        "seed": engine.seed,
        "depth": engine.depth,
        "map": map_to_dict(engine.game_map),
        # On garde l'ORDRE de la liste : c'est l'ordre de jeu des monstres.
        "entities": [entity_to_dict(e) for e in entities],
        # Le joueur est dans la liste ; on note sa position pour le retrouver.
        "player_index": entities.index(engine.player),
        "log": list(engine.log.messages),
    }


def engine_from_dict(data: JSON) -> Engine:
    if not isinstance(data, dict):  # ex. un fichier qui contient « [] »
        raise ValueError("La sauvegarde n'est pas un objet JSON.")
    if data.get("version") != SAVE_VERSION:
        raise ValueError(f"Version de sauvegarde non gérée : {data.get('version')}")
    game_map = map_from_dict(data["map"])
    game_map.entities = [entity_from_dict(e) for e in data["entities"]]
    player = game_map.entities[data["player_index"]]
    if not isinstance(player, Actor):
        raise ValueError("Le joueur sauvegardé n'est pas un acteur.")

    # Le constructeur recalcule la vision (visible ⊂ explored, déjà rempli)…
    engine = Engine(game_map, player, seed=data["seed"], depth=data["depth"])
    # …mais ajoute aussi son message de bienvenue : on le remplace par le
    # journal sauvegardé.
    engine.log.messages = list(data["log"])
    engine.log.add("Partie reprise.")
    return engine


# --- Fichier -------------------------------------------------------------------


def save_exists(path: Path = SAVE_PATH) -> bool:
    return path.is_file()


def save_game(engine: Engine, path: Path = SAVE_PATH) -> None:
    """Écrit la sauvegarde de façon « atomique ».

    On écrit d'abord dans un fichier temporaire, puis on le RENOMME en
    save.json. Le renommage est instantané : si le jeu est coupé en pleine
    écriture, l'ancienne sauvegarde reste intacte au lieu d'être à moitié écrite.
    """
    path.parent.mkdir(parents=True, exist_ok=True)  # crée ~/.roguelike au besoin
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        # ensure_ascii=False : garde les accents lisibles (« dégâts »).
        json.dump(engine_to_dict(engine), file, ensure_ascii=False, indent=1)
    os.replace(temp_path, path)


def load_game(path: Path = SAVE_PATH) -> Engine | None:
    """Charge la sauvegarde. None si absente ou illisible (fichier abîmé…)."""
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
        return engine_from_dict(data)
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        # json.JSONDecodeError est une sous-classe de ValueError.
        return None


def delete_save(path: Path = SAVE_PATH) -> None:
    """Permadeath : supprime la sauvegarde (rien à faire si elle n'existe pas)."""
    path.unlink(missing_ok=True)
