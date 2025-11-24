import sqlite3
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

# -----------------------------------------
# Connections
# -----------------------------------------
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma = PersistentClient(path="backend/app/database/chroma")
collection = chroma.get_collection("product_specs")

sqlite_path = "backend/app/database/products.db"
conn = sqlite3.connect(sqlite_path)
cur = conn.cursor()

# -----------------------------------------
# Test Query
# -----------------------------------------
query = "HP laptop 16GB RAM"

print("\n🔍 Step 1 — Semantic Search (ChromaDB)")
query_emb = embedder.encode(query).tolist()

results = collection.query(
    query_embeddings=[query_emb],
    n_results=50
)

product_names = [meta["product_name"] for meta in results["metadatas"][0]]
print("Top products:", product_names)

print("\n🗄️ Step 2 — SQL Fetch from products table")
specs = {}

for name in product_names:
    cur.execute("SELECT * FROM products WHERE product_name = ?", (name,))
    row = cur.fetchone()
    specs[name] = row

print("\nFetched Specs:")
for product, data in specs.items():
    print(product, "→", data)

print("\n✅ End-to-end RAG test successful!")

conn.close()
