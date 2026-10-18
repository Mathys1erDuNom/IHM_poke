"""Génération contrôlée des équipes adverses."""

import random


class EnemyGenerator:
    def __init__(self, data, rng=None):
        self.data = data
        self.config = data.config["enemy_generation"]
        self.rng = rng or random.Random()
        self.normal_pokemon = [
            pokemon for pokemon in data.pokemon
            if not pokemon["name"].lower().endswith("_shiny")
        ]

    def _tier_for_wave(self, wave):
        return next(
            tier for tier in self.config["wave_tiers"]
            if tier["waves"][0] <= wave <= tier["waves"][1]
        )

    def _generate(self, pool, team_size, level_min, level_max, iv_min, iv_max):
        team_size = max(1, min(int(team_size), len(pool)))
        selected = self.rng.sample(pool, team_size)
        return [
            self.data.enemy_battler(
                pokemon,
                self.rng.randint(level_min, level_max),
                iv_min,
                iv_max,
            )
            for pokemon in selected
        ]

    def random_team(self, team_size, difficulty="team"):
        if not self.normal_pokemon:
            return []
        if difficulty == "team":
            params = self.config["team_mode"]
            return self._generate(
                self.normal_pokemon,
                team_size,
                params["level_min"],
                params["level_max"],
                params["iv_min"],
                params["iv_max"],
            )

        wave = max(1, int(difficulty))
        tier = self._tier_for_wave(wave)
        pool = [
            pokemon for pokemon in self.normal_pokemon
            if tier["base_stat_min"] <= sum(pokemon["base_stats"].values()) <= tier["base_stat_max"]
        ]
        if len(pool) < team_size:
            pool = sorted(
                self.normal_pokemon,
                key=lambda pokemon: abs(sum(pokemon["base_stats"].values()) - (tier["base_stat_min"] + tier["base_stat_max"]) / 2),
            )[:max(team_size, min(60, len(self.normal_pokemon)))]
        return self._generate(
            pool,
            team_size,
            tier["level_min"],
            tier["level_max"],
            tier["iv_min"],
            tier["iv_max"],
        )

    def random_wave_team(self, wave):
        sizes = self.config["wave_team_sizes"]
        team_size = sizes[min(max(0, wave - 1), len(sizes) - 1)]
        return self.random_team(team_size, difficulty=wave)

    def predefined_team(self, team_id, level=None, iv_min=None, iv_max=None):
        definition = next((team for team in self.data.teams if team["id"] == team_id), None)
        if not definition:
            return []
        params = self.config["team_mode"]
        output = []
        for name in definition["pokemon"]:
            pokemon = self.data.pokemon_by_id.get(self.data_name_id(name))
            if not pokemon:
                continue
            output.append(self.data.enemy_battler(
                pokemon,
                level or self.rng.randint(params["level_min"], params["level_max"]),
                params["iv_min"] if iv_min is None else iv_min,
                params["iv_max"] if iv_max is None else iv_max,
            ))
        return output

    @staticmethod
    def data_name_id(name):
        from .data import normalize_name
        return normalize_name(name)