import os
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


ensure_table_exists()


@app.route("/")
def index():
    with get_cursor() as cur:
        cur.execute("""
            SELECT user_id, balance
            FROM argent
            ORDER BY balance DESC, user_id ASC
            LIMIT 10
        """)
        leaderboard = cur.fetchall()

    leaderboard = [
        {
            "user_id": row["user_id"],
            "balance": row["balance"],
            "display_name": get_display_name(row["user_id"]),
        }
        for row in leaderboard
    ]

    return render_template("index.html", leaderboard=leaderboard, discord_user=session.get("discord_user"))


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
    return redirect(url_for("mes_pokemons"))


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("index"))


@app.route("/images/gif/<path:filename>")
def pokemon_gif(filename):
    """Sert les gif de Pokémon depuis le dossier images/gif  (à côté de app.py)."""
    return send_from_directory(IMAGES_GIF_DIR, filename)


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