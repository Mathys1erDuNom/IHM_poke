# Graph Report - IHM_poke  (2026-11-13)

## Corpus Check
- Large corpus: 1383 files · ~81,348 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 317 nodes · 665 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 69 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Flask Routes & Rewards
- Battle Engine Core
- Battle Tests & DB
- Pokédex Frontend Script
- GIF Download Scripts
- Battle UI Script
- Battle Package Modules
- Battle Data Loading
- README, API & Config
- Enemy Team Generation
- Battle Setup Script
- Quiz Frontend Script

## God Nodes (most connected - your core abstractions)
1. `BattleEngine` - 27 edges
2. `BattleEngineTests` - 25 edges
3. `BattleData` - 20 edges
4. `get_cursor()` - 15 edges
5. `normalize_name()` - 14 edges
6. `EnemyGenerator` - 14 edges
7. `BattleRouteTests` - 14 edges
8. `Combats Pokémon (/combat battle feature)` - 13 edges
9. `create_battle()` - 12 edges
10. `add_log()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `index()` --references--> `Home page (index.html)`  [INFERRED]
  app.py → templates/index.html
- `compte()` --references--> `Account page (compte.html)`  [INFERRED]
  app.py → templates/compte.html
- `pokedex()` --references--> `Pokédex collection page (pokedex.html)`  [INFERRED]
  app.py → templates/pokedex.html
- `connexion()` --references--> `Login page (connexion.html)`  [INFERRED]
  app.py → templates/connexion.html
- `mes_pokemons()` --references--> `Pokédex collection page (pokedex.html)`  [INFERRED]
  app.py → templates/pokedex.html

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Full pages sharing the Pokédex device shell layout (device-header, lens-cluster, screen)** — templates_index, templates_connexion, templates_compte, templates_pokedex, templates_quiz, templates_combat_select, templates_combat [INFERRED 0.95]
- **Battle flow: team setup, battle creation, turn play and next wave** — templates_combat_select, templates_combat, app_create_battle, app_get_battle, app_play_battle_turn, app_next_battle_wave [INFERRED 0.85]
- **Logged-in trainer area: account page with badges, leaderboard, collection, quiz and combat entry points** — templates_compte, templates__badges, templates__leaderboard, templates_quiz, templates_combat_select, templates_pokedex [EXTRACTED 1.00]

## Communities (13 total, 3 thin omitted)

### Community 0 - "Flask Routes & Rewards"
Cohesion: 0.08
Nodes (45): award_trainer_xp(), badge_image(), choose_quiz_question(), choose_random_pokemon_reward(), coin_image(), combat_setup(), combat_view(), compte() (+37 more)

### Community 1 - "Battle Engine Core"
Cohesion: 0.14
Nodes (5): BattleEngine, damage_score(), score(), add_log(), BattleEngineTests

### Community 2 - "Battle Tests & DB"
Cohesion: 0.06
Nodes (5): FixedRandom, BattleRouteTests, FakeConnection, FakeCursor, FakeDatabase

### Community 3 - "Pokédex Frontend Script"
Cohesion: 0.09
Nodes (34): allCollections, buildCard(), buildEvoBlock(), buildIvRows(), buildXpBlock(), DISCORD_NAME_OVERRIDES, emptyStateEl, escapeHtml() (+26 more)

### Community 4 - "GIF Download Scripts"
Cohesion: 0.12
Nodes (11): hauteur_metres(), nom_francais(), normaliser_gif(), hauteur_metres(), nom_francais(), normaliser_gif(), slugify(), taille_cible_px() (+3 more)

### Community 5 - "Battle UI Script"
Cohesion: 0.15
Nodes (23): battleApp, battleLog, byId(), continueToNextWave(), itemsPanel, movesPanel, nextWaveButton, partyPanel (+15 more)

### Community 6 - "Battle Package Modules"
Cohesion: 0.13
Nodes (4): effectiveness_text(), Combats Pokémon (/combat battle feature), Engine and route unit tests (simulated PostgreSQL), Wave mode (Vagues) progression

### Community 8 - "README, API & Config"
Cohesion: 0.18
Nodes (11): search_pokemon(), REST API endpoints (/api/trainers, /api/trainers/<user_id>/pokemons, /api/search), Discord OAuth2 login (identify scope), .env configuration (DATABASE_URL, FLASK_SECRET_KEY, DISCORD_CLIENT_ID/SECRET, DISCORD_REDIRECT_URI), Global Pokémon search across trainers, new_captures table, Pokédex des dresseurs (Flask web app), Flask 3.0.3 (+3 more)

### Community 10 - "Battle Setup Script"
Cohesion: 0.38
Nodes (5): filteredPokemon(), form, renderPokemonPage(), resetPageAndRender(), setup

### Community 11 - "Quiz Frontend Script"
Cohesion: 0.29
Nodes (6): answerButtons, feedback, quizApp, rewardImage, rewardMessage, rewardPanel

## Knowledge Gaps
- **1 isolated node(s):** `Engine and route unit tests (simulated PostgreSQL)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 103 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Pokédex collection page (pokedex.html)` connect `Flask Routes & Rewards` to `README, API & Config`, `Pokédex Frontend Script`?**
  _High betweenness centrality (0.202) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `BattleEngineTests` (e.g. with `BattleData` and `EnemyGenerator`) actually correct?**
  _`BattleEngineTests` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Engine and route unit tests (simulated PostgreSQL)` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Flask Routes & Rewards` be split into smaller, more focused modules?**
  _Cohesion score 0.0763888888888889 - nodes in this community are weakly interconnected._
- **Why does `Battle page (combat.html)` connect `Flask Routes & Rewards` to `Battle UI Script`, `Battle Package Modules`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Should `Battle Engine Core` be split into smaller, more focused modules?**
  _Cohesion score 0.1406423034330011 - nodes in this community are weakly interconnected._
- **Why does `BattleEngine` connect `Battle Engine Core` to `Flask Routes & Rewards`, `Battle Tests & DB`, `Battle Package Modules`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._