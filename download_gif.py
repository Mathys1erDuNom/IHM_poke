import os
import re
import unicodedata

import requests

# Nombre de Pokémon à télécharger, à partir du n°1
NB_POKEMON = 20

# Dossier de destination (doit correspondre à celui utilisé par l'appli web).
# Ancré sur l'emplacement du script pour que ça marche peu importe d'où on le lance.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(SCRIPT_DIR, "images", "GIF")

os.makedirs(DOSSIER, exist_ok=True)


def slugify(nom):
    """
    Convertit un nom de Pokémon en nom de fichier attendu par l'appli web :
    minuscules, sans accents, sans espaces ni apostrophes.
    Ex. "Salamèche" -> "salameche", "Mr. Mime" -> "mrmime"
    """
    nom_sans_accents = unicodedata.normalize("NFD", nom)
    nom_sans_accents = nom_sans_accents.encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]+", "", nom_sans_accents.lower())


def nom_francais(pokemon_id):
    """Récupère le nom français d'un Pokémon via l'endpoint pokemon-species de PokeAPI."""
    url = f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    for entree in data["names"]:
        if entree["language"]["name"] == "fr":
            return entree["name"]

    # Repli si jamais le nom français manquait (ne devrait pas arriver)
    return data["name"]


for pokemon_id in range(1, NB_POKEMON + 1):
    try:
        nom = nom_francais(pokemon_id)
        slug = slugify(nom)

        url_gif = (
            f"https://raw.githubusercontent.com/PokeAPI/sprites/"
            f"master/sprites/pokemon/other/showdown/{pokemon_id}.gif"
        )
        chemin = os.path.join(DOSSIER, f"{slug}.gif")

        print(f"Téléchargement de {nom} (#{pokemon_id}) -> {slug}.gif ...")

        reponse = requests.get(url_gif, timeout=30)
        reponse.raise_for_status()

        with open(chemin, "wb") as fichier:
            fichier.write(reponse.content)

        print(f"✅ {slug}.gif enregistré")

    except requests.RequestException as erreur:
        print(f"❌ Erreur pour le Pokémon #{pokemon_id} ({nom if 'nom' in locals() else '?'}) : {erreur}")

print("\nTéléchargement terminé !")