import json
import os
import re
import unicodedata

# Renomme les gifs shiny d'images/gif/alola/shiny avec le nom de POKEMON/alola.json, suffixé _shiny
# (ex. rattatadalola.gif -> rattata_d'Alola_shiny.gif). Les gifs sans entrée (ex. pikachu.gif) sont ignorés.

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(SCRIPT_DIR, "images", "gif", "alola", "shiny")
JSON_ALOLA = os.path.join(SCRIPT_DIR, "POKEMON", "alola.json")


def slugify(nom):
    # Même logique que download_gif.py / static/js/script.js
    sans_accents = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]+", "", sans_accents.lower())


with open(JSON_ALOLA, encoding="utf-8") as f:
    pokemons = json.load(f)

# slug -> nom exact du JSON (première lettre en minuscule), suffixé _shiny
noms = {slugify(p["name"]): p["name"][0].lower() + p["name"][1:] for p in pokemons}

for fichier in sorted(os.listdir(DOSSIER)):
    base, ext = os.path.splitext(fichier)
    if ext.lower() != ".gif" or base not in noms:
        continue
    ancien = os.path.join(DOSSIER, fichier)
    nouveau = os.path.join(DOSSIER, noms[base] + "_shiny.gif")
    if ancien == nouveau:
        continue
    os.rename(ancien, nouveau)
    print(f"{fichier} -> {noms[base]}_shiny.gif")

print("Renommage terminé !")
