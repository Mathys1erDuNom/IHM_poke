# Pokédex des dresseurs

Petite appli web (Flask) qui se connecte à la même base Postgres que ton bot Discord
et affiche, pour chaque dresseur, sa collection de Pokémon (`table new_captures`).

## Installation

```bash
cd pokemon-webapp
python -m venv venv
source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

Crée un fichier `.env` à la racine du dossier (à côté de `app.py`) :

```
DATABASE_URL=postgresql://user:password@host:port/dbname
```

C'est la même variable que celle utilisée par ton bot, donc tu peux copier
la même valeur.

## Lancer l'appli

```bash
python app.py
```

Puis ouvre http://localhost:5000 dans ton navigateur.

## Fonctionnement

- **Sidebar gauche** : liste tous les `user_id` présents dans `new_captures`,
  avec le nombre de Pokémon de chacun. Cliquer sur un dresseur charge sa collection.
  Tu peux aussi coller directement un ID Discord dans le champ du haut.
- **Zone principale** : grille de cartes Pokémon (sprite, types, stats, XP,
  évolution à venir si le seuil n'est pas encore atteint).
- **Recherche globale** : le champ « Retrouver un Pokémon » cherche un nom
  de Pokémon chez tous les dresseurs à la fois (utile pour retrouver qui a
  capturé quoi).

## Endpoints API (réutilisables ailleurs)

- `GET /api/trainers` → `[{ "user_id": "...", "total": 12 }, ...]`
- `GET /api/trainers/<user_id>/pokemons` → collection complète d'un dresseur
- `GET /api/search?q=<nom>` → recherche d'un Pokémon tous dresseurs confondus

## Notes

- L'appli n'a besoin d'aucun token Discord : elle ne fait que lire la base
  Postgres, en parallèle du bot. Les deux peuvent tourner en même temps sans
  se gêner (chaque requête HTTP ouvre sa propre connexion à la base).
- Les noms affichés sont les identifiants Discord bruts (l'appli ne peut pas
  résoudre les pseudos sans appeler l'API Discord). Si tu veux afficher les
  vrais pseudos, il faudrait soit interroger l'API Discord côté serveur avec
  un token de bot, soit stocker le pseudo dans la table au moment de la capture.
- Pour héberger ça en prod, lance-le derrière un vrai serveur WSGI
  (`gunicorn app:app`) plutôt que le serveur de dev Flask.
