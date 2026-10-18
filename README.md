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
FLASK_SECRET_KEY=une-cle-aleatoire-longue
DISCORD_CLIENT_ID=identifiant-de-ton-application-discord
DISCORD_CLIENT_SECRET=secret-de-ton-application-discord
DISCORD_REDIRECT_URI=http://localhost:5000/connexion/discord/callback
```

C'est la même variable que celle utilisée par ton bot, donc tu peux copier
la même valeur.

Dans le [portail développeur Discord](https://discord.com/developers/applications),
crée une application et ajoute exactement la valeur de `DISCORD_REDIRECT_URI`
dans **OAuth2 > Redirects**. Le secret client reste côté serveur et ne doit
jamais être publié. Pour générer `FLASK_SECRET_KEY`, utilise
`python -c "import secrets; print(secrets.token_hex(32))"`.

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
- **Connexion** : depuis l’accueil, saisis ton ID Discord pour afficher ta
  collection sur une page dédiée après autorisation OAuth2 Discord (`identify`).

## Endpoints API (réutilisables ailleurs)

- `GET /api/trainers` → `[{ "user_id": "...", "total": 12 }, ...]`
- `GET /api/trainers/<user_id>/pokemons` → collection complète d'un dresseur
- `GET /api/search?q=<nom>` → recherche d'un Pokémon tous dresseurs confondus

## Combats Pokémon

La page `/combat` est réservée aux comptes Discord connectés. Elle permet de choisir une équipe de 1 à 6 Pokémon de sa collection, puis de lancer un combat contre une équipe aléatoire/prédéfinie ou un mode Vagues. Les deux modes utilisent le même moteur dans `battle/engine.py`; les données sont chargées depuis `POKEMON/` et `ATTACK/`.

- `battle/data.py` adapte les JSON locaux, résout les attaques et associe les GIFs de `images/gif/`.
- `battle/enemy.py` génère les équipes et les vagues à partir des tiers configurés.
- `battle/config.json` centralise types, formule de dégâts/stats, STAB, critique, statuts, objets, précision/PP par défaut, taille des équipes et progression des vagues.
- `battle/teams.json` contient les équipes prédéfinies; chaque nom absent du catalogue est ignoré.
- Les JSON d'attaques ne contiennent pas de précision ni de PP: les valeurs configurées sont 100 et 15. Deux Pokémon n'ont pas de défense: le chargeur utilise la valeur de repli configurée à 1. La Lutte est le fallback configuré lorsqu'un Pokémon n'a plus d'attaque avec PP.
- Les doublons de noms d'attaques avec valeurs contradictoires utilisent la première entrée de `ATTACK/attack_data.json`. Les effets `copie`, `vole objet` et `fuite` ne sont pas simulés; ils sont listés dans `data_defaults.unsupported_attack_effects`. Les alias d'attaques sont centralisés dans `data_defaults.attack_aliases`.
- La table `new_captures` ne stocke pas de niveau: les Pokémon du joueur utilisent le niveau défini par `combat.player_level` (50 par défaut). Les niveaux et IV ennemis progressent par tiers dans `enemy_generation.wave_tiers`.

Lancer les tests du moteur et des routes (PostgreSQL simulé):

```bash
python -m unittest discover -s tests -v
```

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
