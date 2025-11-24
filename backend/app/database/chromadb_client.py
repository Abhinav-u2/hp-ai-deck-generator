import json
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
from pathlib import Path

# -----------------------------------------
# SAME PATH LOGIC AS SQL IMPORTER
# -----------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "backend" / "app" / "database" / "chroma"
JSON_PATH = BASE_DIR / "output" / "hp catalogue" / "hp catalogue_output.json"

print(f"📂 Project Root: {BASE_DIR}")
print(f"📄 JSON Path: {JSON_PATH}")
print(f"🗄️ Chroma DB Path: {DB_PATH}")

# -----------------------------------------
# Load JSON output
# -----------------------------------------
with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
    pages = json.load(f)

# -----------------------------------------
# Load embedding model
# -----------------------------------------
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# -----------------------------------------
# Connect Chroma
# -----------------------------------------
client = PersistentClient(path=str(DB_PATH))

collection = client.get_or_create_collection(
    name="product_specs",
    metadata={"hnsw:space": "cosine"},
    embedding_function=None
)

# -----------------------------------------
# CLEAN NAME FUNCTION – MUST MATCH SQL LOGIC
# -----------------------------------------
def clean_name(name: str):
    if not name:
        return None
    name = name.strip()
    name_lower = name.lower()

    # Reject generic / category-level names
    blacklist = [
        "notebook", "notebooks", "tablet", "display",
        "monitor", "pc", "ultrabook", "series"
    ]

    for b in blacklist:
        if name_lower == b or b in name_lower:
            return None

    return name


# -----------------------------------------
# MERGE PRODUCTS
# -----------------------------------------
merged = {}

for page in pages:
    page_num = page.get("page")
    for product in page.get("extracted_data", []):

        raw_name = product.get("product_name", "").strip()
        clean = clean_name(raw_name)
        if not clean:
            continue  # skip generic items

        if clean not in merged:
            merged[clean] = {
                "product_name": clean,
                "category": product.get("category"),
                "description": product.get("description", ""),
                "specs": product.get("specs", {}),
                "pages": [page_num]
            }
        else:
            # Merge specs
            for k, v in product.get("specs", {}).items():
                merged[clean]["specs"][k] = v

            # Merge description if missing
            if not merged[clean]["description"] and product.get("description"):
                merged[clean]["description"] = product["description"]

            merged[clean]["pages"].append(page_num)

# -----------------------------------------
# INSERT MERGED PRODUCTS INTO CHROMA
# -----------------------------------------
doc_id = 1

for name, p in merged.items():

    text_lines = [
        f"Product: {name}",
        f"Category: {p.get('category', '')}",
        f"Description: {p.get('description', '')}",
        "\nSpecs:"
    ]

    for k, v in p["specs"].items():
        text_lines.append(f"- {k}: {v}")

    text_lines.append("\nPages: " + ", ".join(map(str, p["pages"])))
    final_text = "\n".join(text_lines)

    embedding = embedder.encode(final_text).tolist()

    collection.add(
        ids=[str(doc_id)],
        documents=[final_text],
        metadatas=[{
            "product_name": name,
            "category": p.get("category", ""),
            "pages": ",".join(map(str, p["pages"])),
            **{f"spec_{k}": v for k, v in p["specs"].items()}   # SAME AS SQL COLUMN NAMES
        }],
        embeddings=[embedding]
    )

    print(f"Inserted: {name}  → id {doc_id}")
    doc_id += 1

print("\n🎉 SUCCESS — Chroma now matches SQL ingestion rules exactly!")
