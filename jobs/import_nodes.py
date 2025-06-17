import json
import re
from jobs.models.node import Node  # adapte selon ton app

with open("node.js", "r", encoding="utf-8") as f:
    content = f.read()

# ✅ Extraire proprement le tableau d'objets
start = content.find("[")
end = content.rfind("]") + 1
array_js = content[start:end]

# ✅ Supprimer les commentaires ligne JavaScript (// ...)
array_clean = re.sub(r"//.*", "", array_js)

# ✅ Remplacer les clés non-quoted → format JSON valide
# (Ex: id: "XXX" → "id": "XXX")
array_clean = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)","\\1\"\\2\"\\3", array_clean)

# ✅ Parse JSON
try:
    items = json.loads(array_clean)
except json.JSONDecodeError as e:
    print("❌ Erreur JSON :", e)
    print("🔍 Extrait :", array_clean[:500])
    raise

# ✅ Enregistrement dans la base
for item in items:
    Node.objects.update_or_create(
        id=item["id"],
        defaults={
            "en_name": item["en_name"],
            "fr_name": item["fr_name"],
            "en_description": item["en_description"],
            "fr_description": item["fr_description"],
            "type": item["type"],
        },
    )

print(f"✅ {len(items)} nodes importés avec succès.")
