import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory
#sszd
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_GIF_DIR = os.path.join(BASE_DIR, "images", "gif")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
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
        conn.commit()
    finally:
        conn.close()


ensure_table_exists()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/images/gif/<path:filename>")
def pokemon_gif(filename):
    """Sert les gif de Pokémon depuis le dossier images/gif (à côté de app.py)."""
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
        {"user_id": user_id, "pokemons": pokemons}
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