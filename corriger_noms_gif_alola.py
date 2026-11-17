import json
import os
import re
import unicodedata

# Renomme les gifs d'images/gif/alola/normal avec le nom exact de POKEMON/alola.json
# (ex. rattatadalola.gif -> Rattata_d'Alola.gif). Les gifs sans entrée (ex. pikachu.gif) sont ignorés.

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(SCRIPT_DIR, "images", "gif", "alola", "shiny")
JSON_ALOLA = os.path.join(SCRIPT_DIR, "POKEMON", "alola.json")


def slugify(nom):
    # Même logique que download_gif.py / static/js/script.js
    sans_accents = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]+", "", sans_accents.lower())


with open(JSON_ALOLA, encoding="utf-8") as f:
    pokemons = json.load(f)

# slug -> nom exact du JSON
noms = {slugify(p["name"]): p["name"][0].lower() + p["name"][1:] for p in pokemons}

for fichier in sorted(os.listdir(DOSSIER)):
    base, ext = os.path.splitext(fichier)
    if ext.lower() != ".gif" or base not in noms:
        continue
    ancien = os.path.join(DOSSIER, fichier)
    nouveau = os.path.join(DOSSIER, noms[base] + ".gif")
    if ancien == nouveau:
        continue
    os.rename(ancien, nouveau)
    print(f"{fichier} -> {noms[base]}.gif")

print("Renommage terminé !")
