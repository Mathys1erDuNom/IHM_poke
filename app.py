import os
import hmac
import json
import secrets
from contextlib import contextmanager
from datetime import timedelta
from urllib.parse import urlencode

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_API_BASE = "https://discord.com/api/v10"

# Remplacement manuel de certains IDs Discord par des pseudos affichés dans l'interface.
# Clé : id Discord (chaîne), Valeur : pseudo affiché.
DISCORD_NAME_OVERRIDES = {
    "456489148061319179": "CrocoBien",
    "457837540452335636": "Le grand Mamba",
    "387534030536704001": "Hepok",
    "763820311098425356": "Maelys",
    "280745299981500418": "Jean Prout",
    "406861648415031297": "TurbbbooGlen",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_GIF_DIR = os.path.join(BASE_DIR, "images", "gif")
POKEMON_DATA_DIR = os.path.join(BASE_DIR, "POKEMON")
QUIZ_QUESTIONS_PATH = os.path.join(BASE_DIR, "quiz_questions.json")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes"},
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)


@contextmanager
def get_cursor():
    """Ouvre une connexion + un curseur le temps d'une requête, puis referme proprement."""
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    finally:
        conn.close()


def ensure_table_exists():
    """
    Crée la table new_captures si elle n'existe pas encore sur cette base
    (même schéma que le bot Discord). Évite un 500 si l'appli web pointe
    vers une base fraîchement créée ou pas encore initialisée par le bot.
    """
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS new_captures (
                user_id     TEXT,
                name        TEXT,
                ivs         JSONB,
                stats       JSONB,
                image       TEXT,
                type        JSONB,
                attacks     JSONB,
                current_xp  INT DEFAULT 0,
                xp_evo      INT DEFAULT 0,
                evo         JSONB DEFAULT '{"name": "pas evo", "file": "pas evo"}'::jsonb
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS argent (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_display_name(user_id):
    """Retourne le pseudo override si défini, sinon l'ID brut."""
    user_id_str = str(user_id)
    return DISCORD_NAME_OVERRIDES.get(user_id_str, user_id_str)


def get_leaderboard(discord_user=None):
    with get_cursor() as cur:
        cur.execute("""
            SELECT user_id, balance
            FROM argent
            ORDER BY balance DESC, user_id ASC
            LIMIT 10
        """)
        rows = cur.fetchall()

    return [
        {
            "user_id": row["user_id"],
            "balance": row["balance"],
            "display_name": (
                discord_user["name"]
                if discord_user and str(row["user_id"]) == discord_user["id"]
                else get_display_name(row["user_id"])
            ),
        }
        for row in rows
    ]


def quiz_answer_digest(challenge_id, answer):
    message = f"{challenge_id}:{answer}".encode("utf-8")
    return hmac.new(app.secret_key.encode("utf-8"), message, "sha256").hexdigest()


def load_quiz_questions():
    with open(QUIZ_QUESTIONS_PATH, encoding="utf-8") as questions_file:
        questions = json.load(questions_file)
    if not isinstance(questions, list) or not questions:
        raise ValueError("Le fichier du quiz doit contenir au moins une question.")
    return questions


def choose_quiz_question():
    questions = load_quiz_questions()
    valid_indices = set(range(len(questions)))
    remaining = session.get("quiz_questions_remaining", [])
    if not isinstance(remaining, list):
        remaining = []
    remaining = [
        index for index in remaining
        if type(index) is int and index in valid_indices
    ]

    if not remaining:
        remaining = list(valid_indices)
        secrets.SystemRandom().shuffle(remaining)

    question_index = remaining.pop()
    session["quiz_questions_remaining"] = remaining
    return questions[question_index]


def load_pokemon_catalog():
    pokemons = []
    for filename in sorted(os.listdir(POKEMON_DATA_DIR)):
        if not filename.lower().endswith(".json"):
            continue
        file_path = os.path.join(POKEMON_DATA_DIR, filename)
        with open(file_path, encoding="utf-8") as pokemon_file:
            entries = json.load(pokemon_file)
        if isinstance(entries, list):
            pokemons.extend(
                pokemon for pokemon in entries
                if isinstance(pokemon, dict)
                and pokemon.get("name")
                and pokemon.get("stats")
            )

    if not pokemons:
        raise ValueError("Aucun Pokémon valide dans le dossier POKEMON.")
    return pokemons


def choose_random_pokemon_reward():
    shiny_reward = secrets.randbelow(64) == 0
    pokemon_pool = [
        pokemon
        for pokemon in load_pokemon_catalog()
        if pokemon["name"].lower().endswith("_shiny") == shiny_reward
    ]
    if not pokemon_pool:
        raise ValueError("Aucun Pokémon disponible pour cette variante.")
    return secrets.choice(pokemon_pool)


ensure_table_exists()


@app.route("/")
def index():
    discord_user = session.get("discord_user")
    return render_template(
        "index.html",
        leaderboard=get_leaderboard(discord_user),
        discord_user=discord_user,
    )


@app.route("/compte")
def compte():
    discord_user = session.get("discord_user")
    if not discord_user:
        return redirect(url_for("connexion"))
    return render_template(
        "compte.html",
        leaderboard=get_leaderboard(discord_user),
        discord_user=discord_user,
    )


@app.route("/pokedex")
def pokedex():
    return render_template("pokedex.html")


@app.route("/connexion")
def connexion():
    errors = {
        "not_configured": "La connexion Discord n’est pas encore configurée par l’administrateur.",
        "cancelled": "La connexion Discord a été annulée.",
        "invalid_state": "La demande de connexion a expiré. Réessaie.",
        "oauth_failed": "La connexion Discord a échoué. Réessaie.",
    }
    return render_template("connexion.html", error=errors.get(request.args.get("error")))


@app.route("/mes-pokemons")
def mes_pokemons():
    discord_user = session.get("discord_user")
    if not discord_user:
        return redirect(url_for("connexion"))
    return render_template("pokedex.html", discord_user=discord_user)


@app.route("/quiz")
def quiz():
    discord_user = session.get("discord_user")
    if not discord_user:
        return redirect(url_for("connexion"))

    quiz_question = choose_quiz_question()
    random_reward = choose_random_pokemon_reward()
    challenge_id = secrets.token_urlsafe(24)
    session["quiz_challenge"] = {
        "id": challenge_id,
        "answer_digest": quiz_answer_digest(challenge_id, quiz_question["answer"]),
        "pokemon": random_reward,
    }
    question = {
        "question": quiz_question["question"],
        "options": quiz_question["options"],
    }
    return render_template(
        "quiz.html",
        discord_user=discord_user,
        question=question,
        challenge_id=challenge_id,
    )


@app.route("/quiz/repondre", methods=["POST"])
def quiz_answer():
    if not session.get("discord_user"):
        return jsonify({"message": "Connecte-toi pour jouer."}), 401

    payload = request.get_json(silent=True)
    challenge = session.get("quiz_challenge")
    if (
        not isinstance(payload, dict)
        or not isinstance(challenge, dict)
        or payload.get("challenge_id") != challenge.get("id")
        or not isinstance(payload.get("answer"), str)
    ):
        return jsonify({"message": "Cette question n'est plus active. Recharge le quiz."}), 409

    submitted_digest = quiz_answer_digest(challenge["id"], payload["answer"])
    if not hmac.compare_digest(submitted_digest, challenge["answer_digest"]):
        session.pop("quiz_challenge", None)
        return jsonify({
            "correct": False,
            "message": "Mauvaise réponse. Tu ne peux plus répondre à cette question.",
        })

    reward = challenge["pokemon"]
    user_id = session["discord_user"]["id"]
    pokemon_name = reward["name"]
    with get_cursor() as cur:
        cur.execute("""
            SELECT name, ivs, stats
            FROM new_captures
            WHERE user_id = %s AND name LIKE %s || '%%'
            ORDER BY CASE WHEN name = %s THEN 0 ELSE 1 END, name
            FOR UPDATE
        """, (user_id, pokemon_name, pokemon_name))
        candidates = cur.fetchall()
        owned_pokemon = next((row for row in candidates if (
            row["name"] == pokemon_name
            or (
                row["name"].startswith(pokemon_name)
                and row["name"][len(pokemon_name):].isdigit()
            )
        )), None)

        if owned_pokemon:
            current_ivs = owned_pokemon["ivs"] or {}
            current_stats = owned_pokemon["stats"] or {}
            improved_ivs = {}
            improved_stats = {}
            total_iv_gain = 0

            for stat, base_value in reward["stats"].items():
                old_iv = int(current_ivs.get(stat, 0) or 0)
                new_iv = min(31, old_iv + 4)
                iv_gain = new_iv - old_iv
                current_stat = int(current_stats.get(stat, base_value + old_iv))
                improved_ivs[stat] = new_iv
                improved_stats[stat] = current_stat + iv_gain
                total_iv_gain += iv_gain

            cur.execute("""
                UPDATE new_captures
                SET ivs = %s, stats = %s
                WHERE user_id = %s AND name = %s
            """, (
                psycopg2.extras.Json(improved_ivs),
                psycopg2.extras.Json(improved_stats),
                user_id,
                owned_pokemon["name"],
            ))
            final_name = owned_pokemon["name"]
            message = (
                f"Les IV de {final_name} sont déjà au maximum."
                if total_iv_gain == 0
                else f"{final_name} gagne +{total_iv_gain} IV au total !"
            )
        else:
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM new_captures
                WHERE user_id = %s AND name LIKE %s || '%%'
            """, (user_id, pokemon_name))
            existing_count = cur.fetchone()["total"]
            final_name = pokemon_name if existing_count == 0 else f"{pokemon_name}{existing_count + 1}"
            evo = reward.get("evo", {"name": "pas evo", "file": "pas evo"})
            initial_ivs = {
                stat: secrets.randbelow(32)
                for stat in reward["stats"]
            }
            initial_stats = {
                stat: int(base_value) + initial_ivs[stat]
                for stat, base_value in reward["stats"].items()
            }
            cur.execute("""
                INSERT INTO new_captures
                    (user_id, name, ivs, stats, image, type, attacks, current_xp, xp_evo, evo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                final_name,
                psycopg2.extras.Json(initial_ivs),
                psycopg2.extras.Json(initial_stats),
                reward.get("image", ""),
                psycopg2.extras.Json(reward.get("type", [])),
                psycopg2.extras.Json(reward.get("attacks", [])),
                reward.get("current_xp", 0),
                reward.get("xp_evo", 0),
                psycopg2.extras.Json(evo),
            ))
            message = f"{final_name} a rejoint ta collection !"

    session.pop("quiz_challenge", None)
    return jsonify({
        "correct": True,
        "message": message,
        "pokemon": {"name": final_name, "image": reward.get("image", "")},
    })


@app.route("/connexion/discord")
def discord_login():
    if not all((DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI)):
        return redirect(url_for("connexion", error="not_configured"))

    state = secrets.token_urlsafe(32)
    session["discord_oauth_state"] = state
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }
    return redirect(f"https://discord.com/oauth2/authorize?{urlencode(params)}")


@app.route("/connexion/discord/callback")
def discord_callback():
    if request.args.get("error"):
        session.pop("discord_oauth_state", None)
        return redirect(url_for("connexion", error="cancelled"))

    expected_state = session.pop("discord_oauth_state", None)
    returned_state = request.args.get("state", "")
    if not expected_state or not secrets.compare_digest(expected_state, returned_state):
        return redirect(url_for("connexion", error="invalid_state"))

    code = request.args.get("code")
    if not code or not all((DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI)):
        return redirect(url_for("connexion", error="oauth_failed"))

    try:
        token_response = requests.post(
            f"{DISCORD_API_BASE}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
            auth=(DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET),
            timeout=10,
        )
        token_response.raise_for_status()
        token_payload = token_response.json()
        if not isinstance(token_payload, dict):
            raise ValueError("Discord returned an invalid token response")
        access_token = token_payload.get("access_token")
        if not access_token:
            raise ValueError("Discord did not return an access token")

        user_response = requests.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        user_response.raise_for_status()
        profile = user_response.json()
        if not isinstance(profile, dict):
            raise ValueError("Discord returned an invalid user profile")
        discord_id = str(profile.get("id", ""))
        if not discord_id.isascii() or not discord_id.isdigit():
            raise ValueError("Discord returned an invalid user ID")
    except (requests.RequestException, ValueError, TypeError):
        return redirect(url_for("connexion", error="oauth_failed"))

    session.clear()
    session.permanent = True
    session["discord_user"] = {
        "id": discord_id,
        "name": profile.get("global_name") or profile.get("username") or discord_id,
    }
    return redirect(url_for("compte"))


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("index"))


@app.route("/images/gif/<path:filename>")
def pokemon_gif(filename):
    """Sert les gif de Pokémon depuis le dossier images/gif  (à côté de app.py)."""
    return send_from_directory(IMAGES_GIF_DIR, filename)


@app.route("/images/coin.png")
def coin_image():
    return send_from_directory(os.path.join(BASE_DIR, "images"), "coin.png")


@app.route("/api/collections")
def list_collections():
    """
    Retourne, en un seul appel, la collection complète de chaque dresseur.
    Format : [{ "user_id": "...", "pokemons": [...] }, ...]
    Les dresseurs sont triés par taille de collection décroissante.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT user_id, name, ivs, stats, image, type, attacks, current_xp, xp_evo, evo
            FROM new_captures
            ORDER BY user_id, name ASC
        """)
        rows = cur.fetchall()

    grouped = {}
    for row in rows:
        user_id = row.pop("user_id")
        grouped.setdefault(user_id, []).append(row)

    collections = [
        {
            "user_id": user_id,
            "display_name": get_display_name(user_id),
            "pokemons": pokemons,
        }
        for user_id, pokemons in grouped.items()
    ]
    collections.sort(key=lambda c: len(c["pokemons"]), reverse=True)

    return jsonify(collections)


@app.route("/api/trainers")
def list_trainers():
    """Retourne chaque dresseur (user_id) présent dans la table, avec son nombre de Pokémon."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT user_id, COUNT(*) AS total
            FROM new_captures
            GROUP BY user_id
            ORDER BY total DESC
        """)
        rows = cur.fetchall()
    return jsonify(rows)


@app.route("/api/trainers/<user_id>/pokemons")
def list_pokemons(user_id):
    """Retourne la collection complète d'un dresseur, triée par ordre alphabétique."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT name, ivs, stats, image, type, attacks, current_xp, xp_evo, evo
            FROM new_captures
            WHERE user_id = %s
            ORDER BY name ASC
        """, (str(user_id),))
        rows = cur.fetchall()
    return jsonify(rows)


@app.route("/api/me/pokemons")
def list_my_pokemons():
    discord_user = session.get("discord_user")
    if not discord_user:
        return jsonify({"error": "Authentification requise"}), 401

    with get_cursor() as cur:
        cur.execute("""
            SELECT name, ivs, stats, image, type, attacks, current_xp, xp_evo, evo
            FROM new_captures
            WHERE user_id = %s
            ORDER BY name ASC
        """, (discord_user["id"],))
        rows = cur.fetchall()
    return jsonify(rows)


@app.route("/api/search")
def search_pokemon():
    """Recherche un Pokémon par nom, tous dresseurs confondus (utile pour retrouver qui a quoi)."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    with get_cursor() as cur:
        cur.execute("""
            SELECT user_id, name, ivs, stats, image, type, attacks, current_xp, xp_evo, evo
            FROM new_captures
            WHERE name ILIKE %s
            ORDER BY name ASC
        """, (f"%{query}%",))
        rows = cur.fetchall()
    return jsonify(rows)



if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)