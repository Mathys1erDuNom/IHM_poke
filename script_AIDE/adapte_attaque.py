import json
from pathlib import Path

FICHIER = Path(__file__).resolve().parent.parent / "ATTACK" / "attack_data.json"

attaques = json.loads(FICHIER.read_text(encoding="utf-8"))

for attaque in attaques:
    # setdefault : relancer le script n'écrase pas les valeurs remplies à la main
    attaque.setdefault("effect", None)
    attaque.setdefault("probas_effect", None)

assert all("effect" in a and "probas_effect" in a for a in attaques)

FICHIER.write_text(json.dumps(attaques, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(attaques)} attaques mises à jour dans {FICHIER}")
