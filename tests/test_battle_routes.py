import unittest

import psycopg2


class FakeDatabase:
    def __init__(self):
        self.battles = {}
        self.captures = []
        self.badges = set()
        self.balances = {}

    def connect(self, *args, **kwargs):
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, database):
        self.database = database

    def cursor(self, cursor_factory=None):
        return FakeCursor(self.database)

    def commit(self):
        pass

    def close(self):
        pass


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self.rows = []
        self.row = None

    def execute(self, query, params=None):
        compact = " ".join(query.lower().split())
        self.rows = []
        self.row = None

        if "from new_captures" in compact:
            self.rows = [dict(capture) for capture in self.database.captures]
            if "any(%s)" in compact:
                selected_names = params[1]
                self.rows = [row for row in self.rows if row["name"] in selected_names]
            elif "name = %s" in compact:
                self.rows = [row for row in self.rows if row["name"] == params[1]]
                if self.rows:
                    self.row = self.rows[0]
            elif "name like %s" in compact:
                target_name = params[1]
                self.rows = [
                    {"name": row["name"]}
                    for row in self.rows
                    if row["name"] == target_name
                    or (row["name"].startswith(target_name) and row["name"][len(target_name):].isdigit())
                ]
        elif compact.startswith("insert into web_battles"):
            self.database.battles[params[0]] = params[2].adapted
        elif compact.startswith("select state from web_battles"):
            state = self.database.battles.get(params[0])
            if state:
                self.row = {"state": state}
        elif compact.startswith("update web_battles"):
            self.database.battles[params[1]] = params[0].adapted
        elif compact.startswith("select badge_id from badges"):
            self.rows = [
                {"badge_id": badge_id}
                for user_id, badge_id in self.database.badges
                if user_id == params[0]
            ]
        elif compact.startswith("insert into badges"):
            badge = (params[0], params[1])
            if badge not in self.database.badges:
                self.database.badges.add(badge)
                self.row = {"badge_id": params[1]}
        elif compact.startswith("insert into argent"):
            user_id, reward = params
            self.database.balances[user_id] = self.database.balances.get(user_id, 0) + reward
        elif compact.startswith("update new_captures"):
            name, ivs, stats, image, pokemon_type, attacks, current_xp, xp_evo, evo, _, old_name = params
            for capture in self.database.captures:
                if capture["name"] == old_name:
                    capture.update({
                        "name": name,
                        "ivs": ivs.adapted,
                        "stats": stats.adapted,
                        "image": image,
                        "type": pokemon_type.adapted,
                        "attacks": attacks.adapted,
                        "current_xp": current_xp,
                        "xp_evo": xp_evo,
                        "evo": evo.adapted,
                    })

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class BattleRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = FakeDatabase()
        psycopg2.connect = cls.database.connect
        import app
        cls.site = app
        cls.site.app.config.update(TESTING=True)

    def setUp(self):
        self.database.battles.clear()
        self.database.badges.clear()
        self.database.balances.clear()
        self.database.captures = [{
            "name": "Pikachu",
            "ivs": {"hp": 20, "attack": 20, "defense": 20, "special_attack": 20, "special_defense": 20, "speed": 20},
            "stats": {"hp": 55, "attack": 75, "defense": 60, "special_attack": 70, "special_defense": 70, "speed": 110},
            "image": "",
            "evo": "pas evo",
        }]
        self.client = self.site.app.test_client()
        with self.client.session_transaction() as browser_session:
            browser_session["discord_user"] = {"id": "trainer-1", "name": "Dresseur"}

    def test_team_battle_can_be_created_and_won(self):
        setup = self.client.get("/combat")
        self.assertEqual(setup.status_code, 200)
        self.assertIn(b"Pikachu", setup.data)
        self.assertIn(b'id="enemy-region"', setup.data)
        self.assertIn(b"Kanto", setup.data)

        response = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": "kanto",
            "enemy_mode": "random",
            "pokemon_names": ["Pikachu"],
        })
        self.assertEqual(response.status_code, 200, response.json)
        battle_id = response.json["battle_id"]
        state = self.client.get(f"/api/battles/{battle_id}").json
        state["player_team"][0]["stats"]["speed"] = 10000
        state["enemy_team"][0]["types"] = ["normal"]
        state["enemy_team"][0]["hp"] = 1
        self.database.battles[battle_id] = state
        move = next(move for move in state["player_team"][0]["moves"] if move["power"] > 0)
        move["power"] = 999
        move["accuracy"] = 100

        turn = self.client.post(f"/api/battles/{battle_id}/turn", json={
            "action": {"kind": "move", "move_id": move["id"]},
        })
        self.assertEqual(turn.status_code, 200, turn.json)
        self.assertEqual(turn.json["status"], "won")

    def test_predefined_team_and_waves_share_the_engine(self):
        region = self.site.BATTLE_DATA.regions[0]
        team_definition = region["teams"][0]
        predefined = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": region["id"],
            "enemy_mode": "predefined",
            "team_id": team_definition["id"],
            "pokemon_names": ["Pikachu"],
        })
        self.assertEqual(predefined.status_code, 200, predefined.json)
        team_state = self.client.get(f"/api/battles/{predefined.json['battle_id']}").json
        self.assertEqual(len(team_state["enemy_team"]), len(team_definition["pokemon"]))

        waves = self.client.post("/api/battles", json={
            "mode": "waves",
            "pokemon_names": ["Pikachu"],
        })
        self.assertEqual(waves.status_code, 200, waves.json)
        battle_id = waves.json["battle_id"]
        state = self.database.battles[battle_id]
        self.assertEqual(state["mode"], "waves")
        self.assertEqual(state["wave"], 1)

        initial_enemy_count = len(state["enemy_team"])
        for defeated_index in range(initial_enemy_count):
            state = self.client.get(f"/api/battles/{battle_id}").json
            previous_enemy_active = state["enemy_active"]
            state["player_team"][state["player_active"]]["stats"]["speed"] = 10000
            enemy = state["enemy_team"][state["enemy_active"]]
            enemy["types"] = ["normal"]
            enemy["hp"] = 1
            move = next(
                move for move in state["player_team"][state["player_active"]]["moves"]
                if move["power"] > 0
            )
            move["power"] = 999
            move["accuracy"] = 100
            self.database.battles[battle_id] = state
            turn = self.client.post(f"/api/battles/{battle_id}/turn", json={
                "action": {"kind": "move", "move_id": move["id"]},
            })
            self.assertEqual(turn.status_code, 200, turn.json)
            state = turn.json
            if defeated_index < initial_enemy_count - 1:
                self.assertEqual(state["wave"], 1)
                self.assertEqual(state["status"], "ongoing")
                self.assertNotEqual(state["enemy_active"], previous_enemy_active)
            if state["wave"] == 2:
                break

        self.assertEqual(state["wave"], 2)
        self.assertEqual(state["status"], "ongoing")
        self.assertNotIn("trainer-1", self.database.balances)
        self.assertTrue(any("Vague 1 remportée" in entry["text"] for entry in state["log"]))

    def _win_battle(self, battle_id):
        state = self.database.battles[battle_id]
        won = None
        for _ in range(len(state["enemy_team"])):
            state = self.client.get(f"/api/battles/{battle_id}").json
            state["player_team"][state["player_active"]]["stats"]["speed"] = 10000
            enemy = state["enemy_team"][state["enemy_active"]]
            enemy["types"] = ["normal"]
            enemy["hp"] = 1
            move = next(
                move for move in state["player_team"][state["player_active"]]["moves"]
                if move["power"] > 0
            )
            move["power"] = 999
            move["accuracy"] = 100
            self.database.battles[battle_id] = state
            won = self.client.post(f"/api/battles/{battle_id}/turn", json={
                "action": {"kind": "move", "move_id": move["id"]},
            })
            self.assertEqual(won.status_code, 200, won.json)
        return won

    def test_predefined_trainer_victory_awards_badge_once(self):
        bulbasaur = self.site.BATTLE_DATA.pokemon_by_id["bulbizarre"]
        bulbasaur_ivs = {stat: 10 for stat in bulbasaur["base_stats"]}
        self.database.captures.append({
            "name": "Bulbizarre",
            "ivs": bulbasaur_ivs,
            "stats": {stat: value + 10 for stat, value in bulbasaur["base_stats"].items()},
            "image": bulbasaur["image"],
            "type": bulbasaur["type"],
            "attacks": bulbasaur["attacks"],
            "current_xp": 310,
            "xp_evo": bulbasaur["xp_evo"],
            "evo": bulbasaur["evo"],
        })
        region = self.site.BATTLE_DATA.regions[0]
        trainer = next(team for team in region["teams"] if team.get("badge"))
        with open(self.site.os.path.join(self.site.BASE_DIR, "badges.json"), encoding="utf-8") as badges_file:
            badge_catalog = self.site.json.load(badges_file)
        badge = next(item for item in badge_catalog if item["name"] == trainer["badge"])
        started = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": region["id"],
            "enemy_mode": "predefined",
            "team_id": trainer["id"],
            "pokemon_names": ["Pikachu", "Bulbizarre"],
        })
        self.assertEqual(started.status_code, 200, started.json)
        battle_id = started.json["battle_id"]
        won = self._win_battle(battle_id)

        self.assertEqual(won.json["status"], "won")
        self.assertIn(("trainer-1", badge["id"]), self.database.badges)
        self.assertEqual(self.database.balances["trainer-1"], 500)
        self.assertEqual(self.database.captures[0]["current_xp"], 200)
        self.assertEqual(self.database.captures[0]["evo"], {"name": "pas evo", "file": "pas evo"})
        self.assertEqual(self.database.captures[0]["ivs"], {stat: 20 for stat in self.database.captures[0]["ivs"]})
        evolved = self.database.captures[1]
        herbizarre = self.site.BATTLE_DATA.pokemon_by_id["herbizarre"]
        self.assertEqual(evolved["name"], "Herbizarre")
        self.assertEqual(evolved["current_xp"], 510)
        self.assertEqual(evolved["xp_evo"], herbizarre["xp_evo"])
        self.assertEqual(evolved["ivs"], {stat: 14 for stat in herbizarre["base_stats"]})
        self.assertEqual(evolved["stats"], {stat: value + 14 for stat, value in herbizarre["base_stats"].items()})
        self.assertEqual(evolved["evo"], herbizarre["evo"])
        self.assertTrue(any(badge["name"] in entry["text"] for entry in won.json["log"]))

    def test_previously_owned_badge_awards_20_croco_dollars(self):
        region = self.site.BATTLE_DATA.regions[0]
        trainer = next(team for team in region["teams"] if team.get("badge"))
        with open(self.site.os.path.join(self.site.BASE_DIR, "badges.json"), encoding="utf-8") as badges_file:
            badge_catalog = self.site.json.load(badges_file)
        badge = next(item for item in badge_catalog if item["name"] == trainer["badge"])
        self.database.badges.add(("trainer-1", badge["id"]))
        started = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": region["id"],
            "enemy_mode": "predefined",
            "team_id": trainer["id"],
            "pokemon_names": ["Pikachu"],
        })
        self.assertEqual(started.status_code, 200, started.json)

        won = self._win_battle(started.json["battle_id"])

        self.assertEqual(won.json["status"], "won")
        self.assertEqual(self.database.balances["trainer-1"], 20)
        self.assertTrue(any("20 Croco Dollars" in entry["text"] for entry in won.json["log"]))

    def test_account_shows_badges_by_region_and_darkens_unowned(self):
        self.database.badges.add(("trainer-1", 17))

        home_response = self.client.get("/")
        response = self.client.get("/compte")

        self.assertEqual(home_response.status_code, 200)
        self.assertNotIn(b"Mes badges", home_response.data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Mes badges", response.data)
        self.assertIn(b"Hoenn", response.data)
        self.assertIn(b"is-locked", response.data)

    def test_invalid_enemy_team_and_unowned_pokemon_are_rejected(self):
        invalid_region = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": "unknown",
            "pokemon_names": ["Pikachu"],
        })
        self.assertEqual(invalid_region.status_code, 400)

        invalid_team = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": "kanto",
            "enemy_mode": "predefined",
            "team_id": "missing",
            "pokemon_names": ["Pikachu"],
        })
        self.assertEqual(invalid_team.status_code, 400)

        unowned = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": "kanto",
            "pokemon_names": ["Mewtwo"],
        })
        self.assertEqual(unowned.status_code, 400)

    def test_player_can_switch_through_api_after_active_pokemon_is_ko(self):
        self.database.captures.append({
            "name": "Carapuce",
            "ivs": {"hp": 15, "attack": 15, "defense": 15, "special_attack": 15, "special_defense": 15, "speed": 15},
            "stats": {"hp": 74, "attack": 78, "defense": 95, "special_attack": 80, "special_defense": 95, "speed": 73},
            "image": "",
        })
        started = self.client.post("/api/battles", json={
            "mode": "team",
            "region_id": "kanto",
            "pokemon_names": ["Pikachu", "Carapuce"],
        })
        self.assertEqual(started.status_code, 200, started.json)
        battle_id = started.json["battle_id"]
        state = self.client.get(f"/api/battles/{battle_id}").json
        state["player_team"][0]["hp"] = 0
        self.database.battles[battle_id] = state

        response = self.client.post(f"/api/battles/{battle_id}/turn", json={
            "action": {"kind": "switch", "index": 1},
        })
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["player_active"], 1)
        self.assertEqual(response.json["status"], "ongoing")

    def test_enemy_knockout_leaves_player_reserves_selectable(self):
        self.database.captures.append({
            "name": "Carapuce",
            "ivs": {"hp": 15, "attack": 15, "defense": 15, "special_attack": 15, "special_defense": 15, "speed": 15},
            "stats": {"hp": 74, "attack": 78, "defense": 95, "special_attack": 80, "special_defense": 95, "speed": 73},
            "image": "",
        })
        started = self.client.post("/api/battles", json={
            "mode": "waves",
            "pokemon_names": ["Pikachu", "Carapuce"],
        })
        self.assertEqual(started.status_code, 200, started.json)
        battle_id = started.json["battle_id"]
        state = self.client.get(f"/api/battles/{battle_id}").json
        state["player_team"][0]["hp"] = 1
        enemy = state["enemy_team"][state["enemy_active"]]
        enemy["stats"]["speed"] = 10000
        enemy["moves"] = [{
            "id": "one-shot", "name": "One-shot", "type": "normal", "power": 999,
            "category": "physique", "accuracy": 100, "effect": None, "effect_chance": 0,
        }]
        self.database.battles[battle_id] = state

        turn = self.client.post(f"/api/battles/{battle_id}/turn", json={
            "action": {"kind": "move", "move_id": state["player_team"][0]["moves"][0]["id"]},
        })
        self.assertEqual(turn.status_code, 200, turn.json)
        self.assertEqual(turn.json["status"], "ongoing")
        self.assertEqual(turn.json["player_team"][0]["hp"], 0)
        self.assertGreater(turn.json["player_team"][1]["hp"], 0)

        switch = self.client.post(f"/api/battles/{battle_id}/turn", json={
            "action": {"kind": "switch", "index": 1},
        })
        self.assertEqual(switch.status_code, 200, switch.json)
        self.assertEqual(switch.json["player_active"], 1)
        self.assertEqual(switch.json["status"], "ongoing")

    def test_battle_api_requires_authentication(self):
        with self.client.session_transaction() as browser_session:
            browser_session.clear()
        response = self.client.post("/api/battles", json={"mode": "waves", "pokemon_names": ["Pikachu"]})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()