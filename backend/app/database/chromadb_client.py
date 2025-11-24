import json
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
import sqlite3
import os
from pathlib import Path  

# ================================
# DYNAMIC CONFIG (Relative Paths)
# ================================
# Calculates project root by going up 3 levels from this file:
# backend/app/database/sql_db.py -> backend/app/database -> backend/app -> backend -> ROOT

# -----------------------------------------
# DYNAMIC PATHS
# -----------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "backend" / "app" / "database" / "chroma"
json_path = BASE_DIR / "output" / "hp catalogue" / "hp catalogue_output.json"

# Verify paths (Optional, for debugging)
print(f"📂 Project Root: {BASE_DIR}")
print(f"📄 JSON Path: {json_path}")
print(f"🗄️ DB Path: {DB_PATH}")

# ... (Rest of the code stays the same)
# -------------------------------
# Load Dense Model
# -------------------------------
dense_model = SentenceTransformer("all-MiniLM-L6-v2")
 
# -------------------------------
# Connect to Chroma
# -------------------------------
client = PersistentClient(path=DB_PATH)
 
collection = client.get_or_create_collection(
    name="product_specs",
    metadata={"hnsw:space": "cosine"},
    embedding_function=None  # manually passing embeddings
)
 
# -------------------------------
# Load JSON
# -------------------------------
 
with open(json_path, "r", encoding="utf-8-sig") as f:
    pages = json.load(f)
 
# -------------------------------
# Merge Duplicates
# -------------------------------
merged = {}
 
for page in pages:
    for product in page.get("extracted_data", []):
        name = product.get("product_name", "").strip()
        if not name:
            continue
 
        if name not in merged:
            merged[name] = {
                "product_name": name,
                "category": product.get("category"),
                "description": product.get("description", ""),
                "specs": product.get("specs", {}),
                "pages": [page["page"]]
            }
        else:
            if product.get("description"):
                merged[name]["description"] += "\n" + product["description"]
 
            for k, v in product.get("specs", {}).items():
                merged[name]["specs"][k] = v
 
            merged[name]["pages"].append(page["page"])
 
# -------------------------------
# Insert into Chroma
# -------------------------------
doc_id = 1
 
for product_name, product in merged.items():
 
    # Build text
    text_lines = [
        f"Product: {product_name}",
        f"Category: {product.get('category', '')}",
        f"Description: {product.get('description', '')}",
        "\nSpecs:"
    ]
 
    for k, v in product.get("specs", {}).items():
        text_lines.append(f"- {k}: {v}")
 
    text = "\n".join(text_lines)
 
    # Dense embedding
    dense_emb = dense_model.encode(text).tolist()
 
    # Insert (dense-only)
    # Insert (dense-only)
    collection.add(
        ids=[str(doc_id)],
        documents=[text],
        embeddings=[dense_emb],
        metadatas=[{
            "product_name": product_name,
            "category": product.get("category", ""),
            "pages": ",".join(str(p) for p in product["pages"])  # Chroma requires scalar, not list
        }],
    )
 
 
    print(f"Inserted {product_name} → id {doc_id}")
    doc_id += 1
 
print("✅ Successfully ingested with Dense embeddings only!")