import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = Flask(__name__)


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


@app.route("/")
def index():
    return render_template("index.html")


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
