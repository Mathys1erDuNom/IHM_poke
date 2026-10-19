"""Moteur de combat partagé, indépendant des routes et du rendu Flask."""

import math
import random

from .messages import add_log, effectiveness_text


class BattleEngine:
    def __init__(self, data, rng=None):
        self.data = data
        self.config = data.config
        self.rules = self.config["combat"]
        self.chart = self.config["effectiveness"]
        self.rng = rng or random.Random()

    def create_battle(self, player_team, enemy_team, mode="team", wave=0):
        if not player_team or not enemy_team:
            raise ValueError("Les deux équipes doivent contenir au moins un Pokémon.")
        state = {
            "mode": mode,
            "wave": int(wave),
            "turn": 1,
            "status": "ongoing",
            "player_team": player_team,
            "enemy_team": enemy_team,
            "player_active": 0,
            "enemy_active": 0,
            "player_items": {
                item_id: item["uses_per_battle"]
                for item_id, item in self.rules.get("items", {}).items()
            },
            "item_labels": {
                item_id: item["label"]
                for item_id, item in self.rules.get("items", {}).items()
            },
            "log": [],
        }
        add_log(state, "Le combat commence !", "system")
        add_log(state, f"{self.active(state, 'player')['name']} entre en combat !", "system")
        add_log(state, f"{self.active(state, 'enemy')['name']} apparaît !", "system")
        return state

    @staticmethod
    def active(state, side):
        team = state[f"{side}_team"]
        index = state[f"{side}_active"]
        return team[index] if 0 <= index < len(team) else None

    @staticmethod
    def alive(pokemon):
        return bool(pokemon and pokemon.get("hp", 0) > 0)

    @staticmethod
    def living_indices(team):
        return [index for index, pokemon in enumerate(team) if pokemon.get("hp", 0) > 0]

    def type_effectiveness(self, attack_type, defender_types):
        attack_type = self.data.normalize_type(attack_type)
        multiplier = 1.0
        for defender_type in defender_types or [self.config["data_defaults"]["missing_type"]]:
            normalized = self.data.normalize_type(defender_type)
            multiplier *= self.chart.get(attack_type, {}).get(normalized, 1.0)
        return multiplier

    def _stage_multiplier(self, stage):
        stage = max(self.rules["stage_min"], min(self.rules["stage_max"], int(stage or 0)))
        return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)

    def effective_stat(self, pokemon, stat):
        value = max(1, int(pokemon.get("stats", {}).get(stat, 1)))
        value *= self._stage_multiplier(pokemon.get("stages", {}).get(stat, 0))
        if stat == "speed" and pokemon.get("status") == "paralysis":
            value *= self.config["statuses"]["paralysis"]["speed_multiplier"]
        return max(1, int(value))

    def calculate_damage(self, attacker, defender, move):
        power = max(0, int(move.get("power", 0)))
        if power == 0:
            return {"damage": 0, "effectiveness": self.type_effectiveness(move.get("type"), defender.get("types", [])), "critical": False, "stab": False}

        physical = move.get("category") == "physique"
        attack_stat = "attack" if physical else "special_attack"
        defense_stat = "defense" if physical else "special_defense"
        attack_value = self.effective_stat(attacker, attack_stat)
        if physical and attacker.get("status") == "burn":
            attack_value = max(1, int(attack_value * self.config["statuses"]["burn"]["physical_attack_multiplier"]))
        defense_value = self.effective_stat(defender, defense_stat)
        effectiveness = self.type_effectiveness(move.get("type"), defender.get("types", []))
        stab = self.data.normalize_type(move.get("type")) in attacker.get("types", [])
        critical = effectiveness > 0 and self.rng.random() < self.rules["critical_chance"]

        if effectiveness == 0:
            damage = 0
        else:
            level = max(1, int(attacker.get("level", 1)))
            formula = self.config["damage_formula"]
            level_factor = 2 * level / formula["level_divisor"] + formula["level_offset"]
            base = (level_factor * power * attack_value / defense_value) / formula["power_divisor"]
            base += formula["base_add"]
            modifier = self.rng.uniform(self.rules["damage_random_min"], self.rules["damage_random_max"])
            modifier *= self.rules["stab_multiplier"] if stab else 1
            modifier *= self.rules["critical_multiplier"] if critical else 1
            damage = max(formula["minimum_damage"], math.floor(base * modifier * effectiveness))
        return {"damage": damage, "effectiveness": effectiveness, "critical": critical, "stab": stab}

    def _status_effect(self, move):
        effect = move.get("effect")
        if effect in self.config["statuses"]:
            return effect
        if effect == "random_paralysis_sleep":
            return self.rng.choice(["paralysis", "sleep"])
        return None

    def _apply_status(self, pokemon, status, state):
        status_config = self.config["statuses"].get(status)
        if not status_config:
            return False
        types = set(pokemon.get("types", []))
        if types.intersection(status_config.get("immune_types", [])):
            add_log(state, f"{pokemon['name']} ne peut pas subir ce statut.", "system")
            return False
        if pokemon.get("status"):
            return False
        pokemon["status"] = status
        if status == "sleep":
            pokemon["status_turns"] = self.rng.randint(status_config["minimum_turns"], status_config["maximum_turns"])
        messages = {
            "burn": f"{pokemon['name']} est brûlé !",
            "poison": f"{pokemon['name']} est empoisonné !",
            "paralysis": f"{pokemon['name']} est paralysé !",
            "sleep": f"{pokemon['name']} s'endort !",
            "freeze": f"{pokemon['name']} est gelé !",
        }
        add_log(state, messages.get(status, f"{pokemon['name']} subit {status_config['label']} !"), "status")
        return True

    def _change_stage(self, pokemon, stat, delta, state):
        stages = pokemon.setdefault("stages", {})
        old = int(stages.get(stat, 0))
        new = max(self.rules["stage_min"], min(self.rules["stage_max"], old + delta))
        stages[stat] = new
        actual_delta = new - old
        if actual_delta:
            direction = "augmente" if actual_delta > 0 else "baisse"
            add_log(state, f"{stat.replace('_', ' ').capitalize()} de {pokemon['name']} {direction} !", "status")
        return actual_delta

    def _apply_move_effect(self, user, target, move, state):
        effect = move.get("effect")
        effect_to_stage = {
            "lower_attack": ("attack", -1),
            "lower_defense": ("defense", -1),
            "raise_defense": ("defense", 1),
            "lower_accuracy": ("accuracy", -1),
            "lower_speed": ("speed", -1),
        }
        if effect in effect_to_stage:
            stat, delta = effect_to_stage[effect]
            self._change_stage(target, stat, delta, state)
            return
        if effect == "heal":
            amount = max(1, int(user["max_hp"] * 0.5))
            healed = min(amount, user["max_hp"] - user["hp"])
            user["hp"] += healed
            add_log(state, f"{user['name']} récupère {healed} PV !", "status")
            return
        status = self._status_effect(move)
        if status:
            chance = max(0, min(100, int(move.get("effect_chance", 100))))
            if self.rng.random() * 100 < chance:
                self._apply_status(target, status, state)

    def _can_act(self, pokemon, state):
        status = pokemon.get("status")
        if status == "sleep":
            turns_left = max(0, int(pokemon.get("status_turns", 0)))
            if turns_left > 0:
                pokemon["status_turns"] = turns_left - 1
                add_log(state, f"{pokemon['name']} dort profondément.", "status")
                return False
            pokemon["status"] = None
            add_log(state, f"{pokemon['name']} se réveille !", "status")
        elif status == "freeze":
            if self.rng.random() >= self.config["statuses"]["freeze"]["thaw_chance"]:
                add_log(state, f"{pokemon['name']} est gelé et ne peut pas agir !", "status")
                return False
            pokemon["status"] = None
            add_log(state, f"{pokemon['name']} dégèle !", "status")
        elif status == "paralysis" and self.rng.random() < self.config["statuses"]["paralysis"]["immobilize_chance"]:
            add_log(state, f"{pokemon['name']} est paralysé ! Il ne peut pas attaquer.", "status")
            return False
        return True

    def _accuracy(self, attacker, move):
        stage = attacker.get("stages", {}).get("accuracy", 0)
        return max(1, min(100, float(move.get("accuracy", 100)) * self._stage_multiplier(stage)))

    def _enemy_action(self, state):
        enemy = self.active(state, "enemy")
        player = self.active(state, "player")
        if not self.alive(enemy) or not self.alive(player):
            return {"kind": "wait"}
        usable = [move for move in enemy["moves"] if move.get("pp", 0) > 0]
        if not usable:
            fallback = self.data.get_moves_for_pokemon({"move_ids": []})[0]
            return {"kind": "move", "move_id": fallback["id"], "fallback": fallback}

        def score(move):
            if move.get("category") == "statut":
                return 5 if not player.get("status") and self._status_effect(move) else 0
            multiplier = self.type_effectiveness(move.get("type"), player.get("types", []))
            stab = self.rules["stab_multiplier"] if self.data.normalize_type(move.get("type")) in enemy.get("types", []) else 1
            return max(0, move.get("power", 0)) * multiplier * stab

        usable.sort(key=score, reverse=True)
        best_score = score(usable[0])
        top_moves = [move for move in usable if score(move) >= best_score * 0.85]
        return {"kind": "move", "move_id": self.rng.choice(top_moves)["id"]}

    def _switch(self, state, side, new_index):
        team = state[f"{side}_team"]
        if not isinstance(new_index, int) or not 0 <= new_index < len(team) or team[new_index].get("hp", 0) <= 0:
            return False
        old = self.active(state, side)
        if old and old.get("hp", 0) > 0 and new_index == state[f"{side}_active"]:
            return False
        state[f"{side}_active"] = new_index
        add_log(state, f"{team[new_index]['name']} entre sur le terrain !", "switch")
        return True

    def _process_action(self, state, side, action):
        if action.get("kind") == "switch":
            if side == "player":
                self._switch(state, side, action.get("index"))
            return

        user = self.active(state, side)
        if not self.alive(user):
            return

        if action.get("kind") == "item":
            if side != "player":
                return
            item_id = action.get("item_id")
            item = self.rules.get("items", {}).get(item_id)
            remaining = state.setdefault("player_items", {}).get(item_id, 0)
            if not item or remaining <= 0:
                add_log(state, "Cet objet ne peut plus être utilisé.", "system")
                return
            amount = max(1, int(user["max_hp"] * item["heal_fraction"]))
            healed = min(amount, user["max_hp"] - user["hp"])
            if healed <= 0:
                add_log(state, f"{user['name']} n'a pas besoin de soin.", "system")
                return
            user["hp"] += healed
            state["player_items"][item_id] = remaining - 1
            add_log(state, f"{item['label']} : {user['name']} récupère {healed} PV !", "item")
            return
        if action.get("kind") != "move" or not self._can_act(user, state):
            return

        move = action.get("fallback")
        if not move:
            move = next((candidate for candidate in user["moves"] if candidate["id"] == action.get("move_id")), None)
        if not move or move.get("pp", 0) <= 0:
            add_log(state, "Cette attaque ne peut plus être utilisée.", "system")
            return

        if not action.get("fallback"):
            move["pp"] -= 1
        target_side = "enemy" if side == "player" else "player"
        target = self.active(state, target_side)
        if not self.alive(target):
            return
        add_log(state, f"{user['name']} utilise {move['name']} !", "attack")
        if self.rng.random() * 100 >= self._accuracy(user, move):
            add_log(state, f"{target['name']} esquive l'attaque !", "miss")
            return

        result = self.calculate_damage(user, target, move)
        if result["critical"] and move.get("power", 0) > 0:
            add_log(state, "Coup critique !", "critical")
        efficacy = effectiveness_text(result["effectiveness"])
        if efficacy:
            add_log(state, efficacy, "effectiveness")
        if result["damage"]:
            target["hp"] = max(0, target["hp"] - result["damage"])
            add_log(state, f"{target['name']} perd {result['damage']} PV !", "damage")
            if target["hp"] == 0:
                add_log(state, f"{target['name']} est K.O. !", "faint")
        if target["hp"] > 0 and move.get("effect"):
            self._apply_move_effect(user, target, move, state)
        recoil_fraction = float(move.get("recoil_fraction", 0) or 0)
        if recoil_fraction and result["damage"]:
            recoil = max(1, int(result["damage"] * recoil_fraction))
            user["hp"] = max(0, user["hp"] - recoil)
            add_log(state, f"{user['name']} subit {recoil} dégâts de recul !", "damage")
            if user["hp"] == 0:
                add_log(state, f"{user['name']} est K.O. !", "faint")

    def _apply_residual(self, state, side):
        pokemon = self.active(state, side)
        if not self.alive(pokemon):
            return
        status = pokemon.get("status")
        status_config = self.config["statuses"].get(status, {})
        damage_fraction = status_config.get("damage_fraction", 0)
        if damage_fraction:
            damage = max(1, int(pokemon["max_hp"] * damage_fraction))
            pokemon["hp"] = max(0, pokemon["hp"] - damage)
            if status == "burn":
                add_log(state, f"{pokemon['name']} souffre de sa brûlure ({damage} PV) !", "status")
            else:
                add_log(state, f"Le poison inflige {damage} dégâts à {pokemon['name']} !", "status")
            if pokemon["hp"] == 0:
                add_log(state, f"{pokemon['name']} est K.O. !", "faint")

    def _check_result(self, state):
        if not self.living_indices(state["player_team"]):
            state["status"] = "lost"
            add_log(state, "Ton équipe n'a plus de Pokémon capables de combattre.", "result")
            return
        if not self.living_indices(state["enemy_team"]):
            if state["mode"] == "waves":
                state["status"] = "wave_complete"
                add_log(state, f"Vague {state['wave']} remportée !", "result")
            else:
                state["status"] = "won"
                add_log(state, "Tu as remporté le combat !", "result")

    def play_turn(self, state, player_action):
        if state.get("status") != "ongoing":
            return state
        if not self.living_indices(state["player_team"]):
            self._check_result(state)
            return state
        if not self.living_indices(state["enemy_team"]):
            self._check_result(state)
            return state

        player = self.active(state, "player")
        player_switch = player_action.get("kind") == "switch"
        player_item = player_action.get("kind") == "item"
        if player_action.get("kind") not in {"move", "switch", "item"}:
            raise ValueError("Action de combat invalide.")
        if not self.alive(player) and not player_switch:
            raise ValueError("Choisis un Pokémon encore capable de combattre.")
        if player_switch:
            target_index = player_action.get("index")
            team = state["player_team"]
            if not isinstance(target_index, int) or not 0 <= target_index < len(team) or team[target_index].get("hp", 0) <= 0:
                raise ValueError("Ce Pokémon ne peut pas combattre.")
            if self.alive(player) and target_index == state["player_active"]:
                raise ValueError("Ce Pokémon est déjà au combat.")
        if player_item:
            item_id = player_action.get("item_id")
            if item_id not in self.rules.get("items", {}) or state.get("player_items", {}).get(item_id, 0) <= 0:
                raise ValueError("Cet objet n'est plus disponible.")
        if player_action.get("kind") == "move":
            selected_move = next(
                (move for move in player.get("moves", []) if move.get("id") == player_action.get("move_id")),
                None,
            )
            if selected_move:
                if selected_move.get("pp", 0) <= 0:
                    raise ValueError("Cette attaque ne peut plus être utilisée.")
            else:
                struggle = self.data.get_moves_for_pokemon({"move_ids": []})[0]
                if (
                    player_action.get("move_id") != struggle["id"]
                    or any(move.get("pp", 0) > 0 for move in player.get("moves", []))
                ):
                    raise ValueError("Cette attaque n'appartient pas à ton Pokémon.")
                player_action = dict(player_action, fallback=struggle)

        enemy_action = self._enemy_action(state)
        player_priority = 1 if player_switch or player_item else 0
        actions = [("player", player_action, player_priority), ("enemy", enemy_action, 0)]
        actions.sort(key=lambda entry: (
            -entry[2],
            -self.effective_stat(self.active(state, entry[0]), "speed") if self.alive(self.active(state, entry[0])) else 0,
            self.rng.random(),
        ))
        for side, action, _priority in actions:
            self._process_action(state, side, action)

        enemy = self.active(state, "enemy")
        if not self.alive(enemy):
            replacement = self.living_indices(state["enemy_team"])
            if replacement:
                self._switch(state, "enemy", replacement[0])
        self._apply_residual(state, "player")
        self._apply_residual(state, "enemy")
        enemy = self.active(state, "enemy")
        if not self.alive(enemy):
            replacement = self.living_indices(state["enemy_team"])
            if replacement:
                self._switch(state, "enemy", replacement[0])
        self._check_result(state)
        state["turn"] += 1
        return state

    def advance_wave(self, state, enemy_team):
        if state.get("mode") != "waves" or state.get("status") != "wave_complete":
            raise ValueError("La vague actuelle n'est pas terminée.")
        if not enemy_team:
            raise ValueError("La prochaine vague doit avoir une équipe ennemie.")
        state["wave"] += 1
        state["enemy_team"] = enemy_team
        state["enemy_active"] = 0
        state["status"] = "ongoing"
        add_log(state, f"La vague {state['wave']} commence !", "system")
        add_log(state, f"{self.active(state, 'enemy')['name']} apparaît !", "system")
        return state