"""Chargement et adaptation des données Pokémon et attaques du projet."""

import json
import random
import re
import unicodedata
import uuid
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent


def normalize_name(value):
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return "".join(char.lower() for char in unaccented if char.isalnum())


class BattleData:
    def __init__(self):
        self.config = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
        self.team_definitions = json.loads((Path(__file__).parent / "teams.json").read_text(encoding="utf-8"))
        self.attack_aliases = {
            normalize_name(source): normalize_name(target)
            for source, target in self.config["data_defaults"]["attack_aliases"].items()
        }
        self.type_aliases = {
            normalize_name(source): normalize_name(target)
            for source, target in self.config["type_aliases"].items()
        }
        self.effect_aliases = {
            normalize_name(source): target
            for source, target in self.config["effect_aliases"].items()
        }
        self.attacks = self._load_attacks()
        self.pokemon = self._load_pokemon()
        self.pokemon_by_id = {normalize_name(pokemon["name"]): pokemon for pokemon in self.pokemon}
        self.teams = self._load_teams()

    def _resolve_attack_id(self, name):
        attack_id = normalize_name(name)
        return self.attack_aliases.get(attack_id, attack_id)

    def _load_attacks(self):
        path = PROJECT_DIR / "ATTACK" / "attack_data.json"
        records = json.loads(path.read_text(encoding="utf-8"))
        attacks = {}
        defaults = self.config["data_defaults"]

        for record in records:
            if not isinstance(record, dict) or not record.get("name"):
                continue
            attack_id = self._resolve_attack_id(record["name"])
            if attack_id in attacks:
                continue
            category = normalize_name(record.get("category", "physique"))
            if category in {"special", "speciale"}:
                category = "special"
            elif category not in {"physique", "statut"}:
                category = "physique"
            effect_id = self.effect_aliases.get(normalize_name(record.get("effect")))
            attacks[attack_id] = {
                "id": attack_id,
                "name": record["name"],
                "type": self.normalize_type(record.get("type")),
                "power": max(0, int(record.get("damage", 0) or 0)),
                "category": category,
                "accuracy": max(0, min(100, int(record.get("accuracy", record.get("precision", defaults["attack_accuracy"])) or 0))),
                "max_pp": max(1, int(record.get("pp", record.get("max_pp", defaults["attack_pp"])) or defaults["attack_pp"])),
                "effect": effect_id,
                "effect_chance": 100 if category == "statut" else int(self.config["combat"]["secondary_status_chance"] * 100),
            }

        fallback = dict(defaults["fallback_move"])
        fallback["id"] = normalize_name(fallback["name"])
        fallback["power"] = int(fallback.pop("damage"))
        fallback["max_pp"] = int(fallback.pop("pp"))
        fallback["accuracy"] = int(fallback["accuracy"])
        fallback["type"] = self.normalize_type(fallback["type"])
        fallback["category"] = "physique"
        fallback["effect"] = None
        fallback["effect_chance"] = 0
        attacks[fallback["id"]] = fallback
        return attacks

    def _load_pokemon(self):
        records = []
        pokemon_dir = PROJECT_DIR / "POKEMON"
        for path in sorted(pokemon_dir.glob("pokemon_*.json")):
            try:
                entries = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict) or not entry.get("name"):
                    continue
                stats = entry.get("stats")
                if not isinstance(stats, dict) or not stats:
                    continue
                record = dict(entry)
                record["types"] = self.normalize_types(entry.get("type", []))
                record["base_stats"] = {
                    stat: max(1, int(stats.get(stat, self.config["data_defaults"]["missing_stat"]) or self.config["data_defaults"]["missing_stat"]))
                    for stat in ("hp", "attack", "defense", "special_attack", "special_defense", "speed")
                }
                record["move_ids"] = []
                for move_name in entry.get("attacks", []):
                    move_id = self._resolve_attack_id(move_name)
                    if move_id in self.attacks and move_id not in record["move_ids"]:
                        record["move_ids"].append(move_id)
                record["gif_url"] = self.gif_url(entry["name"])
                record["source_file"] = path.name
                records.append(record)
        return records

    def _load_teams(self):
        available = {normalize_name(pokemon["name"]): pokemon for pokemon in self.pokemon if not pokemon["name"].lower().endswith("_shiny")}
        teams = []
        for team in self.team_definitions:
            valid_names = [name for name in team.get("pokemon", []) if normalize_name(name) in available]
            if valid_names:
                teams.append({"id": team.get("id", normalize_name(team.get("name"))), "name": team.get("name", "Équipe"), "pokemon": valid_names})
        return teams

    def normalize_type(self, value):
        type_id = normalize_name(value)
        return self.type_aliases.get(type_id, type_id or self.config["data_defaults"]["missing_type"])

    def normalize_types(self, values):
        if isinstance(values, str):
            values = re.split(r"[/,;]", values)
        output = []
        for value in values or []:
            for component in re.split(r"[/,;]", str(value)):
                normalized = self.normalize_type(component)
                if normalized and normalized not in output:
                    output.append(normalized)
        return output or [self.config["data_defaults"]["missing_type"]]

    def gif_url(self, pokemon_name):
        is_shiny = str(pokemon_name).lower().endswith("_shiny")
        base_name = str(pokemon_name)[:-6] if is_shiny else str(pokemon_name)
        slug = normalize_name(base_name)
        folder = "shiny" if is_shiny else "normal"
        gif_path = PROJECT_DIR / "images" / "gif" / folder / f"{slug}.gif"
        return f"/images/gif/{folder}/{slug}.gif" if gif_path.is_file() else None

    def find_owned_species(self, owned_record):
        name = str(owned_record.get("name", ""))
        if normalize_name(name) in self.pokemon_by_id:
            return self.pokemon_by_id[normalize_name(name)]

        base_name = re.sub(r"\d+$", "", name)
        species_id = normalize_name(base_name)
        if species_id in self.pokemon_by_id:
            return self.pokemon_by_id[species_id]
        return None

    def get_moves_for_pokemon(self, pokemon_record):
        moves = [dict(self.attacks[move_id]) for move_id in pokemon_record.get("move_ids", []) if move_id in self.attacks][:4]
        if not moves:
            moves = [dict(self.config["data_defaults"]["fallback_move"])]
            moves[0]["id"] = normalize_name(moves[0]["name"])
            moves[0]["power"] = int(moves[0].pop("damage"))
            moves[0]["max_pp"] = int(moves[0].pop("pp"))
            moves[0]["type"] = self.normalize_type(moves[0]["type"])
            moves[0]["effect"] = None
            moves[0]["effect_chance"] = 0
        for move in moves:
            move["pp"] = move["max_pp"]
        return moves

    def create_battler(self, pokemon_record, iv_min=0, iv_max=31, owned_record=None):
        if not pokemon_record or not pokemon_record.get("base_stats"):
            return None
        base_stats = dict(pokemon_record["base_stats"])
        source_ivs = (owned_record or {}).get("ivs") or {}
        ivs = {}
        for stat in base_stats:
            source_iv = source_ivs.get(stat)
            value = random.SystemRandom().randint(iv_min, iv_max) if source_iv is None else int(source_iv)
            ivs[stat] = max(0, min(31, value))
        calculated_stats = {}
        owned_stats = (owned_record or {}).get("stats") or {}
        for stat, base in base_stats.items():
            saved_stat = owned_stats.get(stat)
            calculated_stats[stat] = max(1, int(saved_stat if saved_stat is not None else base + ivs[stat]))

        is_shiny = pokemon_record["name"].lower().endswith("_shiny")
        moves = self.get_moves_for_pokemon(pokemon_record)
        return {
            "id": str(uuid.uuid4()),
            "species": pokemon_record["name"],
            "name": (owned_record or {}).get("name", pokemon_record["name"]),
            "types": list(pokemon_record["types"]),
            "base_stats": base_stats,
            "stats": calculated_stats,
            "ivs": ivs,
            "hp": calculated_stats["hp"],
            "max_hp": calculated_stats["hp"],
            "status": None,
            "status_turns": 0,
            "stages": {stat: 0 for stat in ("attack", "defense", "special_attack", "special_defense", "speed", "accuracy")},
            "moves": moves,
            "gif_url": pokemon_record["gif_url"],
            "image": pokemon_record.get("image", ""),
            "evo": pokemon_record.get("evo", {"name": "pas evo", "file": "pas evo"}),
            "original_stats": owned_stats,
            "shiny": is_shiny,
        }

    def player_battler(self, owned_record, iv_min=0, iv_max=31):
        species = self.find_owned_species(owned_record)
        if not species:
            return None
        return self.create_battler(species, iv_min, iv_max, owned_record)

    def enemy_battler(self, pokemon_record, iv_min, iv_max):
        return self.create_battler(pokemon_record, iv_min, iv_max)