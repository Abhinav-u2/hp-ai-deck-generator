import os
import json
from pathlib import Path
from qdrant_client import QdrantClient, models
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client.models import SparseTextEmbedding

from dotenv import load_dotenv
load_dotenv()

# -----------------------------------------
# PATH SETUP (same as SQL ingestion)
# -----------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "backend" / "app" / "database" / "qdrant"
JSON_PATH = BASE_DIR / "output" / "hp catalogue" / "hp catalogue_output.json"

print(f"📂 Project Root: {BASE_DIR}")
print(f"📄 JSON Path: {JSON_PATH}")
print(f"🗄️ Qdrant DB Path: {DB_PATH}")

# -----------------------------------------
# LOAD GOOGLE GEMINI EMBEDDING MODEL
# -----------------------------------------
os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

dense_embedder = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004"
)

def embed_dense(text: str):
    """Generate dense embeddings using Gemini text-embedding-004"""
    return dense_embedder.embed_query(text)

# -----------------------------------------
# Sparse Encoder (SPLADE via FastEmbed)
# -----------------------------------------
sparse_encoder = SparseTextEmbedding(model_name="qdrant/bm25")

def embed_sparse(text: str):
    """Generate sparse BM25 vector."""
    vecs = list(sparse_encoder.embed(text))
    sparse_vec = vecs[0]  # SparseEmbedding

    d = sparse_vec.as_dict()  # {"token_id": score}

    return models.SparseVector(
        indices=[int(k) for k in d.keys()],
        values=list(d.values())
    )


# -----------------------------------------
# LOAD PARSED JSON
# -----------------------------------------
with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
    pages = json.load(f)

# -----------------------------------------
# INIT QDRANT WITH HYBRID CONFIG
# -----------------------------------------
client = QdrantClient(path=str(DB_PATH))

dense_dim = 768  # Gemini text-embedding-004 dimension

client.recreate_collection(
    collection_name="product_specs",
    vectors_config={
        "dense": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE),
    },
    sparse_vectors_config={
        "sparse": models.SparseVectorParams(),
    }
)

# -----------------------------------------
# NAME CLEANING — same logic as SQL loader
# -----------------------------------------
def clean_name(name: str):
    if not name:
        return None
    name = name.strip()
    name_lower = name.lower()

    blacklist = [
        "notebook", "notebooks", "tablet", "display",
        "monitor", "pc", "ultrabook", "series"
    ]

    for b in blacklist:
        if name_lower == b or b in name_lower:
            return None

    return name

# -----------------------------------------
# MERGE PRODUCTS (unchanged logic)
# -----------------------------------------
merged = {}

for page in pages:
    page_num = page.get("page")
    for product in page.get("extracted_data", []):

        raw_name = product.get("product_name", "").strip()
        clean = clean_name(raw_name)
        if not clean:
            continue

        if clean not in merged:
            merged[clean] = {
                "product_name": clean,
                "category": product.get("category"),
                "description": product.get("description", ""),
                "specs": product.get("specs", {}),
                "pages": [page_num]
            }
        else:
            # merge specs
            for k, v in product.get("specs", {}).items():
                merged[clean]["specs"][k] = v

            # merge description
            if not merged[clean]["description"] and product.get("description"):
                merged[clean]["description"] = product["description"]

            merged[clean]["pages"].append(page_num)

# -----------------------------------------
# INSERT INTO QDRANT — same order & IDs
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

    # Dense + Sparse embeddings
    dense_vec = embed_dense(final_text)
    sparse_vec = embed_sparse(final_text)

    # Payload (same as SQL column names)
    payload = {
        "product_name": name,
        "category": p.get("category", ""),
        "pages": ",".join(map(str, p["pages"])),
        **{f"spec_{k}": v for k, v in p["specs"].items()}
    }

    client.upsert(
        collection_name="product_specs",
        points=[
            models.PointStruct(
                id=doc_id,
                payload=payload,
                vector={
                    "dense": dense_vec,
                    "sparse": sparse_vec
                }
            )
        ]
    )

    print(f"Inserted: {name}  → id {doc_id}")
    doc_id += 1

print("\n🎉 SUCCESS — Qdrant now contains merged product list WITH Gemini dense + SPLADE sparse hybrid search!")
