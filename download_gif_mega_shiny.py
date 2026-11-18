import io
import os

import requests
from PIL import Image, ImageSequence

# Formes méga shiny (ids PokeAPI 10033 à 10089). Seules les formes contenant "-mega" sont gardées :
# Floette éternelle, Kyogre/Groudon primal, les Pikachu costumés et Hoopa libéré sont ignorés.
ID_DEBUT = 10033
ID_FIN = 10089

# Dossier de destination. Ancré sur l'emplacement du script pour que ça marche peu importe d'où on le lance.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(SCRIPT_DIR, "images", "gif", "mega", "shiny")

os.makedirs(DOSSIER, exist_ok=True)

# --- Réglages de la normalisation des tailles (identiques aux autres scripts de gif) ---

CANVAS = (250, 250)
PX_MIN = 90
PX_MAX = 240
HAUTEUR_MAX_M = 2.5
GAMMA = 0.55


def nom_mega(nom_api, espece_fr):
    """
    Construit le nom de fichier demandé à partir de l'espèce en français.
    Ex. ("mewtwo-mega-x", "Mewtwo") -> "Mega-Mewtwo-X", ("venusaur-mega", "Florizarre") -> "Mega-Florizarre"
    """
    forme = nom_api.partition("-mega")[2].strip("-")
    morceaux = ["Mega", espece_fr]
    if forme:
        morceaux.append(forme.upper())
    return "-".join(morceaux)


def infos_pokemon(pokemon_id):
    """Renvoie (nom PokeAPI, nom français de l'espèce, hauteur en mètres) via PokeAPI."""
    url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    response = requests.get(data["species"]["url"], timeout=30)
    response.raise_for_status()
    espece = response.json()
    nom_fr = next(
        (e["name"] for e in espece["names"] if e["language"]["name"] == "fr"),
        espece["name"],
    )
    # PokeAPI donne la hauteur en décimètres
    return data["name"], nom_fr, data["height"] / 10.0


def taille_cible_px(hauteur_m, hauteur_min_m, hauteur_max_m):
    """Convertit une taille réelle (m) en taille à l'écran (px), par interpolation puis compression GAMMA."""
    hauteur_m = min(hauteur_m, hauteur_max_m)
    if hauteur_max_m <= hauteur_min_m:
        return PX_MAX
    ratio = (hauteur_m - hauteur_min_m) / (hauteur_max_m - hauteur_min_m)
    ratio = max(0.0, min(1.0, ratio)) ** GAMMA
    return round(PX_MIN + ratio * (PX_MAX - PX_MIN))


def normaliser_gif(contenu_gif, taille_px):
    """
    Redimensionne chaque frame du gif animé pour que sa plus grande dimension fasse 'taille_px',
    puis la centre horizontalement et l'aligne en bas d'un canevas transparent (CANVAS).
    """
    im = Image.open(io.BytesIO(contenu_gif))

    frames = []
    durations = []
    for frame in ImageSequence.Iterator(im):
        f = frame.convert("RGBA")
        ratio = taille_px / max(f.size)
        nouvelle_taille = (
            max(1, round(f.size[0] * ratio)),
            max(1, round(f.size[1] * ratio)),
        )
        f = f.resize(nouvelle_taille, Image.LANCZOS)

        toile = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        x = (CANVAS[0] - nouvelle_taille[0]) // 2
        y = CANVAS[1] - nouvelle_taille[1]  # aligné en bas (posé au sol)
        toile.paste(f, (x, y), f)

        frames.append(toile)
        durations.append(frame.info.get("duration", 100))

    tampon = io.BytesIO()
    frames[0].save(
        tampon,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
    )
    return tampon.getvalue()


# --- Étape 1 : collecter nom + hauteur réelle des formes méga ---

infos = {}  # pokemon_id -> {"nom": str, "hauteur_m": float}

print("Récupération des noms et tailles réelles...")
for pokemon_id in range(ID_DEBUT, ID_FIN + 1):
    try:
        nom_api, nom_fr, hauteur_m = infos_pokemon(pokemon_id)
    except requests.RequestException as erreur:
        print(f"❌ Erreur d'info pour le Pokémon #{pokemon_id} : {erreur}")
        continue
    if "-mega" not in nom_api:
        print(f"  #{pokemon_id} {nom_api} ignoré (pas une méga)")
        continue
    infos[pokemon_id] = {"nom": nom_mega(nom_api, nom_fr), "hauteur_m": hauteur_m}
    print(f"  #{pokemon_id} {nom_api} -> {infos[pokemon_id]['nom']} : {hauteur_m} m")

if infos:
    hauteur_min_m = min(v["hauteur_m"] for v in infos.values())
else:
    hauteur_min_m = 0.1

print(f"\nHauteur minimale observée : {hauteur_min_m} m")
print(f"Hauteur d'écrêtage (au-delà, taille max à l'écran) : {HAUTEUR_MAX_M} m\n")

# --- Étape 2 : télécharger chaque gif shiny et le normaliser ---

for pokemon_id, info in infos.items():
    nom = info["nom"]
    hauteur_m = info["hauteur_m"]

    try:
        url_gif = (
            f"https://raw.githubusercontent.com/PokeAPI/sprites/"
            f"master/sprites/pokemon/other/showdown/shiny/{pokemon_id}.gif"
        )
        chemin = os.path.join(DOSSIER, f"{nom}.gif")

        print(f"Téléchargement de {nom} (shiny, #{pokemon_id}) -> {nom}.gif ...")

        reponse = requests.get(url_gif, timeout=30)
        reponse.raise_for_status()

        px = taille_cible_px(hauteur_m, hauteur_min_m, HAUTEUR_MAX_M)
        gif_normalise = normaliser_gif(reponse.content, px)

        with open(chemin, "wb") as fichier:
            fichier.write(gif_normalise)

        print(f"✅ {nom}.gif enregistré (hauteur réelle {hauteur_m} m -> {px}px)")

    except requests.RequestException as erreur:
        print(f"❌ Erreur de téléchargement pour {nom} (#{pokemon_id}) : {erreur}")
    except Exception as erreur:  # sécurité : un gif corrompu ne doit pas arrêter le script
        print(f"❌ Erreur de traitement pour {nom} (#{pokemon_id}) : {erreur}")

print("\nTéléchargement terminé !")
