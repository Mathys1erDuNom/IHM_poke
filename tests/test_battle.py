import unittest

from battle.data import BattleData
from battle.enemy import EnemyGenerator
from battle.engine import BattleEngine


class FixedRandom:
    def __init__(self, value=0.99):
        self.value = value

    def random(self):
        return self.value

    def uniform(self, low, high):
        return high

    def randint(self, low, high):
        return low

    def choice(self, values):
        return values[0]

    def sample(self, values, count):
        return list(values[:count])


class BattleEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = BattleData()

    def setUp(self):
        self.rng = FixedRandom()
        self.engine = BattleEngine(self.data, rng=self.rng)
        self.generator = EnemyGenerator(self.data, rng=self.rng)

    def pokemon(self, name):
        return self.data.enemy_battler(self.data.pokemon_by_id[name.lower()], 0, 0)

    @staticmethod
    def move(
        move_id="test", attack_type="normal", power=40, category="physique",
        accuracy=100, pp=5, effect=None, effect_chance=0,
    ):
        return {
            "id": move_id,
            "name": move_id,
            "type": attack_type,
            "power": power,
            "category": category,
            "accuracy": accuracy,
            "max_pp": pp,
            "pp": pp,
            "effect": effect,
            "effect_chance": effect_chance,
        }

    def test_catalog_has_local_gifs_and_resolvable_attacks(self):
        self.assertEqual(len(self.data.pokemon), 1296)
        self.assertTrue(all(pokemon["gif_url"] for pokemon in self.data.pokemon))
        move_ids = set(self.data.attacks)
        for pokemon in self.data.pokemon:
            self.assertTrue(set(pokemon["move_ids"]).issubset(move_ids))

    def test_double_type_effectiveness_and_immunity(self):
        self.assertEqual(self.engine.type_effectiveness("eau", ["feu", "sol"]), 4)
        self.assertEqual(self.engine.type_effectiveness("electrik", ["eau", "vol"]), 4)
        self.assertEqual(self.engine.type_effectiveness("electrik", ["sol"]), 0)
        self.assertEqual(self.engine.type_effectiveness("feu", ["eau"]), 0.5)

    def test_damage_applies_stab_and_critical(self):
        attacker = self.pokemon("pikachu")
        defender = self.pokemon("carapuce")
        move = self.move(attack_type="electrik", category="special")
        self.rng.value = 0
        result = self.engine.calculate_damage(attacker, defender, move)
        self.assertTrue(result["stab"])
        self.assertTrue(result["critical"])
        self.assertGreater(result["damage"], 0)

    def test_battlers_have_no_level_and_stats_are_base_plus_iv(self):
        ivs = {stat: 12 for stat in ("hp", "attack", "defense", "special_attack", "special_defense", "speed")}
        player = self.data.player_battler({"name": "Pikachu", "ivs": ivs, "stats": {}})
        species = self.data.pokemon_by_id["pikachu"]
        self.assertNotIn("level", player)
        for stat, base in species["base_stats"].items():
            self.assertEqual(player["stats"][stat], base + 12)

    def test_accuracy_miss_consumes_pp_without_damage(self):
        attacker = self.pokemon("pikachu")
        defender = self.pokemon("carapuce")
        attacker["stats"]["speed"] = 10000
        move = self.move(accuracy=0)
        attacker["moves"] = [move]
        state = self.engine.create_battle([attacker], [defender])
        old_hp = defender["hp"]
        self.engine.play_turn(state, {"kind": "move", "move_id": move["id"]})
        self.assertEqual(defender["hp"], old_hp)
        self.assertEqual(move["pp"], 4)
        self.assertTrue(any(entry["kind"] == "miss" for entry in state["log"]))

    def test_poison_and_burn_residual_damage(self):
        pokemon = self.pokemon("pikachu")
        state = self.engine.create_battle([pokemon], [self.pokemon("carapuce")])
        for status in ("poison", "burn"):
            pokemon["status"] = status
            old_hp = pokemon["hp"]
            self.engine._apply_residual(state, "player")
            self.assertLess(pokemon["hp"], old_hp)

    def test_sleep_duration_and_paralysis_speed(self):
        pokemon = self.pokemon("pikachu")
        state = self.engine.create_battle([pokemon], [self.pokemon("carapuce")])
        pokemon["status"] = "sleep"
        pokemon["status_turns"] = 2
        self.assertFalse(self.engine._can_act(pokemon, state))
        self.assertEqual(pokemon["status_turns"], 1)
        self.assertFalse(self.engine._can_act(pokemon, state))
        self.assertEqual(pokemon["status_turns"], 0)
        self.assertTrue(self.engine._can_act(pokemon, state))
        self.assertIsNone(pokemon["status"])

        base_speed = self.engine.effective_stat(pokemon, "speed")
        pokemon["status"] = "paralysis"
        self.assertEqual(self.engine.effective_stat(pokemon, "speed"), base_speed // 2)

    def test_fainted_enemy_is_replaced_without_free_action(self):
        player = self.pokemon("pikachu")
        player["stats"]["speed"] = 10000
        move = self.move(power=999)
        player["moves"] = [move]
        first = self.pokemon("carapuce")
        second = self.pokemon("bulbizarre")
        first["hp"] = 1
        state = self.engine.create_battle([player], [first, second])
        second_hp = second["hp"]
        self.engine.play_turn(state, {"kind": "move", "move_id": move["id"]})
        self.assertEqual(first["hp"], 0)
        self.assertEqual(state["enemy_active"], 1)
        self.assertEqual(second["hp"], second_hp)

    def test_player_can_switch_and_use_configured_potion(self):
        first = self.pokemon("pikachu")
        second = self.pokemon("carapuce")
        enemy = self.pokemon("bulbizarre")
        enemy["moves"] = [self.move(move_id="miss", accuracy=0)]
        state = self.engine.create_battle([first, second], [enemy])
        self.engine.play_turn(state, {"kind": "switch", "index": 1})
        self.assertEqual(state["player_active"], 1)
        second["hp"] -= 40
        old_hp = second["hp"]
        self.engine.play_turn(state, {"kind": "item", "item_id": "potion"})
        self.assertGreater(second["hp"], old_hp)
        self.assertEqual(state["player_items"]["potion"], 2)

    def test_player_can_switch_after_active_pokemon_is_ko(self):
        fainted = self.pokemon("pikachu")
        reserve = self.pokemon("carapuce")
        enemy = self.pokemon("bulbizarre")
        state = self.engine.create_battle([fainted, reserve], [enemy])
        fainted["hp"] = 0

        self.engine.play_turn(state, {"kind": "switch", "index": 1})

        self.assertEqual(state["player_active"], 1)
        self.assertGreater(reserve["hp"], 0)
        self.assertTrue(any(entry["kind"] == "switch" for entry in state["log"]))

    def test_struggle_only_when_all_player_moves_have_no_pp(self):
        player = self.pokemon("pikachu")
        player["stats"]["speed"] = 10000
        player["hp"] = player["max_hp"] = 1000
        spent_move = self.move(move_id="spent", pp=1)
        spent_move["pp"] = 0
        player["moves"] = [spent_move]
        enemy = self.pokemon("bulbizarre")
        state = self.engine.create_battle([player], [enemy])
        old_hp = enemy["hp"]
        self.engine.play_turn(state, {"kind": "move", "move_id": "lutte"})
        self.assertLess(enemy["hp"], old_hp)
        self.assertEqual(spent_move["pp"], 0)
        with self.assertRaises(ValueError):
            self.engine.play_turn(state, {"kind": "move", "move_id": "spent"})

    def test_team_and_wave_generators_respect_tier_bounds(self):
        self.assertEqual(len(self.generator.predefined_team("classiques")), 6)
        team = self.generator.random_team(3)
        self.assertEqual(len(team), 3)
        early = self.generator.random_wave_team(1)
        late = self.generator.random_wave_team(20)
        self.assertEqual(len(early), 3)
        self.assertEqual(len(late), 6)
        self.assertTrue(all(min(pokemon["ivs"].values()) >= 0 for pokemon in early))
        self.assertTrue(all(min(pokemon["ivs"].values()) >= 20 for pokemon in late))
        self.assertTrue(all(max(pokemon["ivs"].values()) <= 31 for pokemon in late))

    def test_enemy_ai_uses_effectiveness_immunities_and_healing_context(self):
        attacker = self.pokemon("pikachu")
        water = self.pokemon("carapuce")
        attacker["moves"] = [
            self.move(move_id="feu", attack_type="feu", power=50, category="special"),
            self.move(move_id="electrik", attack_type="electrik", power=50, category="special"),
        ]
        state = self.engine.create_battle([water], [attacker])
        self.assertEqual(self.engine._enemy_action(state)["move_id"], "electrik")

        plant_poison = self.pokemon("bulbizarre")
        attacker["moves"] = [
            self.move(move_id="toxic", attack_type="poison", power=0, category="statut", effect="poison", effect_chance=100),
            self.move(move_id="flamme", attack_type="feu", power=50, category="special"),
        ]
        state = self.engine.create_battle([plant_poison], [attacker])
        self.assertEqual(self.engine._enemy_action(state)["move_id"], "flamme")

        attacker["moves"] = [
            self.move(move_id="charge", power=40),
            self.move(move_id="soin", power=0, category="statut", effect="heal", effect_chance=100),
        ]
        attacker["hp"] = int(attacker["max_hp"] * 0.25)
        state = self.engine.create_battle([water], [attacker])
        self.assertEqual(self.engine._enemy_action(state)["move_id"], "soin")

    def test_wave_iv_minimum_increases_every_five_waves(self):
        expected_minima = {1: 0, 4: 0, 5: 5, 9: 5, 10: 10, 15: 15, 30: 30, 35: 31, 40: 31, 1000: 31}
        for wave, minimum in expected_minima.items():
            team = self.generator.random_wave_team(wave)
            self.assertTrue(all(min(pokemon["ivs"].values()) >= minimum for pokemon in team), wave)
            self.assertTrue(all(max(pokemon["ivs"].values()) <= 31 for pokemon in team), wave)

    def test_wave_victory_advances_with_new_enemy_team(self):
        player = self.pokemon("pikachu")
        enemy = self.pokemon("carapuce")
        next_enemy = self.pokemon("bulbizarre")
        state = self.engine.create_battle([player], [enemy], mode="waves", wave=1)
        enemy["hp"] = 0
        self.engine._check_result(state)
        self.assertEqual(state["status"], "wave_complete")
        self.engine.advance_wave(state, [next_enemy])
        self.assertEqual(state["wave"], 2)
        self.assertEqual(state["status"], "ongoing")
        self.assertIs(self.engine.active(state, "enemy"), next_enemy)


if __name__ == "__main__":
    unittest.main()