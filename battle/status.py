"""Gestion de tous les statuts de combat. Les valeurs chiffrées sont dans config.json ("statuses")."""

from .messages import add_log

INFLICT_MESSAGES = {
    "burn": "{name} est brûlé !",
    "poison": "{name} est empoisonné !",
    "paralysis": "{name} est paralysé !",
    "sleep": "{name} s'endort !",
    "freeze": "{name} est gelé !",
}

RESIDUAL_MESSAGES = {
    "burn": "{name} souffre de sa brûlure ({damage} PV) !",
    "poison": "Le poison inflige {damage} dégâts à {name} !",
}


class StatusManager:
    def __init__(self, config, rng):
        self.statuses = config["statuses"]
        self.chart = config["effectiveness"]
        self.rng = rng

    def from_move(self, move):
        """Statut qu'une attaque peut infliger, ou None."""
        effect = move.get("effect")
        if effect in self.statuses:
            return effect
        if effect == "random_paralysis_sleep":
            return self.rng.choice(["paralysis", "sleep"])
        return None

    def is_immune(self, pokemon, status):
        status_config = self.statuses.get(status, {})
        types = pokemon.get("types", [])
        if set(types).intersection(status_config.get("immune_types", [])):
            return True
        # ex. brûlure : immunisé si le type feu n'a aucun effet (x0) sur le Pokémon
        attack_chart = self.chart.get(status_config.get("immune_if_no_effect_from"), {})
        return any(attack_chart.get(pokemon_type, 1) == 0 for pokemon_type in types)

    def try_inflict(self, target, move, state):
        """Tire la probabilité de l'attaque (effect_chance, en %) puis applique son statut."""
        status = self.from_move(move)
        if not status:
            return False
        chance = max(0, min(100, int(move.get("effect_chance", 100))))
        if self.rng.random() * 100 >= chance:
            return False
        return self.apply(target, status, state)

    def apply(self, pokemon, status, state):
        status_config = self.statuses.get(status)
        if not status_config:
            return False
        if self.is_immune(pokemon, status):
            add_log(state, f"{pokemon['name']} ne peut pas subir ce statut.", "system")
            return False
        if pokemon.get("status"):
            return False
        pokemon["status"] = status
        if status == "sleep":
            pokemon["status_turns"] = self.rng.randint(status_config["minimum_turns"], status_config["maximum_turns"])
        message = INFLICT_MESSAGES.get(status, "{name} subit " + status_config["label"] + " !")
        add_log(state, message.format(name=pokemon["name"]), "status")
        return True

    def attack_multiplier(self, pokemon, physical):
        """Brûlure : l'attaque physique est divisée par deux."""
        if physical and pokemon.get("status") == "burn":
            return self.statuses["burn"]["physical_attack_multiplier"]
        return 1

    def speed_multiplier(self, pokemon):
        if pokemon.get("status") == "paralysis":
            return self.statuses["paralysis"]["speed_multiplier"]
        return 1

    def can_act(self, pokemon, state):
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
            if self.rng.random() >= self.statuses["freeze"]["thaw_chance"]:
                add_log(state, f"{pokemon['name']} est gelé et ne peut pas agir !", "status")
                return False
            pokemon["status"] = None
            add_log(state, f"{pokemon['name']} dégèle !", "status")
        elif status == "paralysis" and self.rng.random() < self.statuses["paralysis"]["immobilize_chance"]:
            add_log(state, f"{pokemon['name']} est paralysé ! Il ne peut pas attaquer.", "status")
            return False
        return True

    def residual(self, pokemon, state):
        """Dégâts de fin de tour (brûlure : 1/16 des PV max, poison : 1/8)."""
        status = pokemon.get("status")
        damage_fraction = self.statuses.get(status, {}).get("damage_fraction", 0)
        if not damage_fraction:
            return
        damage = max(1, int(pokemon["max_hp"] * damage_fraction))
        pokemon["hp"] = max(0, pokemon["hp"] - damage)
        add_log(state, RESIDUAL_MESSAGES[status].format(name=pokemon["name"], damage=damage), "status")
        if pokemon["hp"] == 0:
            add_log(state, f"{pokemon['name']} est K.O. !", "faint")
