import io
import os
import re
import unicodedata

import requests
from PIL import Image, ImageSequence

# Nombre de Pokémon à télécharger, à partir du n°1
NB_POKEMON = 9

# Dossier de destination (doit correspondre à celui utilisé par l'appli web).
# Ancré sur l'emplacement du script pour que ça marche peu importe d'où on le lance.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(SCRIPT_DIR, "images", "gif")

os.makedirs(DOSSIER, exist_ok=True)

# --- Réglages de la normalisation des tailles ---

# Taille du canevas final (carré, en pixels) sur lequel chaque Pokémon est posé.
CANVAS = (250, 250)

# Plage de tailles à l'écran (en pixels) vers laquelle on projette les tailles réelles.
# Le plus petit Pokémon du jeu occupera PX_MIN, le plus grand (après écrêtage) PX_MAX.
# PX_MIN est volontairement assez haut : même le plus petit Pokémon doit rester visible
# et occuper une bonne partie du canevas, pas juste quelques pixels.
PX_MIN = 90
PX_MAX = 240

# Écrêtage de la taille réelle (en mètres) : au-delà de cette hauteur, on n'agrandit plus.
# 2.5 m couvre déjà la quasi-totalité des Pokémon "normaux" ; les quelques géants
# au-delà (Wailord, Steelix, Onix, Groudon...) plafonnent simplement à la taille max,
# comme "très grands", sans écraser l'échelle pour tous les autres.
HAUTEUR_MAX_M = 2.5

# Exposant de compression de l'échelle (0 < GAMMA <= 1).
# GAMMA = 1 donnerait une interpolation strictement linéaire, ce qui écrase les
# Pokémon "normaux" tout en bas de l'échelle pour laisser de la place aux géants.
# GAMMA < 1 gonfle les tailles petites/moyennes (proches de PX_MIN) tout en gardant
# le bon ordre relatif, pour que la grande majorité des Pokémon restent grands et
# lisibles à l'écran.
GAMMA = 0.55


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


def hauteur_metres(pokemon_id):
    """Récupère la hauteur réelle du Pokémon (en mètres) via l'endpoint pokemon de PokeAPI."""
    url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    # PokeAPI donne la hauteur en décimètres
    return data["height"] / 10.0


def taille_cible_px(hauteur_m, hauteur_min_m, hauteur_max_m):
    """
    Convertit une taille réelle (en mètres) en une taille cible à l'écran (en pixels),
    par interpolation linéaire entre [hauteur_min_m, hauteur_max_m] -> [PX_MIN, PX_MAX].
    """
    hauteur_m = min(hauteur_m, hauteur_max_m)
    if hauteur_max_m <= hauteur_min_m:
        return PX_MAX
    ratio = (hauteur_m - hauteur_min_m) / (hauteur_max_m - hauteur_min_m)
    ratio = max(0.0, min(1.0, ratio)) ** GAMMA
    return round(PX_MIN + ratio * (PX_MAX - PX_MIN))


def normaliser_gif(contenu_gif, taille_px):
    """
    Redimensionne chaque frame du gif animé pour que sa plus grande dimension fasse
    'taille_px' pixels, puis la centre horizontalement et l'aligne en bas d'un canevas
    fixe (CANVAS) transparent, comme si chaque Pokémon était "posé au sol" sur la
    même ligne. Renvoie les octets du nouveau gif animé, prêt à être écrit sur disque.
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


# --- Étape 1 : collecter nom + hauteur réelle de chaque Pokémon ---
# (nécessaire avant de normaliser, pour connaître la plus petite hauteur du lot,
# utilisée comme borne basse de l'échelle)

infos = {}  # pokemon_id -> {"nom": str, "slug": str, "hauteur_m": float}

print("Récupération des noms et tailles réelles...")
for pokemon_id in range(1, NB_POKEMON + 1):
    try:
        nom = nom_francais(pokemon_id)
        hauteur_m = hauteur_metres(pokemon_id)
        infos[pokemon_id] = {
            "nom": nom,
            "slug": slugify(nom),
            "hauteur_m": hauteur_m,
        }
        print(f"  #{pokemon_id} {nom} : {hauteur_m} m")
    except requests.RequestException as erreur:
        print(f"❌ Erreur d'info pour le Pokémon #{pokemon_id} : {erreur}")

if infos:
    hauteur_min_m = min(v["hauteur_m"] for v in infos.values())
else:
    hauteur_min_m = 0.1

print(f"\nHauteur minimale observée : {hauteur_min_m} m")
print(f"Hauteur d'écrêtage (au-delà, taille max à l'écran) : {HAUTEUR_MAX_M} m\n")

# --- Étape 2 : télécharger chaque gif et le normaliser ---

for pokemon_id, info in infos.items():
    nom = info["nom"]
    slug = info["slug"]
    hauteur_m = info["hauteur_m"]

    try:
        url_gif = (
            f"https://raw.githubusercontent.com/PokeAPI/sprites/"
            f"master/sprites/pokemon/other/showdown/{pokemon_id}.gif"
        )
        chemin = os.path.join(DOSSIER, f"{slug}.gif")

        print(f"Téléchargement de {nom} (#{pokemon_id}) -> {slug}.gif ...")

        reponse = requests.get(url_gif, timeout=30)
        reponse.raise_for_status()

        px = taille_cible_px(hauteur_m, hauteur_min_m, HAUTEUR_MAX_M)
        gif_normalise = normaliser_gif(reponse.content, px)

        with open(chemin, "wb") as fichier:
            fichier.write(gif_normalise)

        print(f"✅ {slug}.gif enregistré (hauteur réelle {hauteur_m} m -> {px}px)")

    except requests.RequestException as erreur:
        print(f"❌ Erreur de téléchargement pour {nom} (#{pokemon_id}) : {erreur}")
    except Exception as erreur:  # sécurité : un gif corrompu ne doit pas arrêter le script
        print(f"❌ Erreur de traitement pour {nom} (#{pokemon_id}) : {erreur}")

print("\nTéléchargement terminé !")