import json
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

# Load embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# NEW ChromaDB client API
client = PersistentClient(path="backend/app/database/chroma")

collection = client.get_or_create_collection(
    name="product_specs",
    metadata={"hnsw:space": "cosine"}
)

# Load your JSON file
json_path = r"C:\Users\abhinav.pandey\Desktop\hp-ai-deck-generator\output\hp catalogue\hp catalogue_output.json"

with open(json_path, "r", encoding="utf-8-sig") as f:
    pages = json.load(f)

# -----------------------------------------
# STEP 1 — MERGE PRODUCTS FROM ALL PAGES
# -----------------------------------------

products_dict = {}

for page in pages:
    extracted_list = page.get("extracted_data", [])

    if not isinstance(extracted_list, list):
        continue

    for product in extracted_list:
        name = product.get("product_name", "").strip()

        if not name:
            continue

        # If seeing product first time, initialize record
        if name not in products_dict:
            products_dict[name] = {
                "product_name": name,
                "category": product.get("category"),
                "description": product.get("description"),
                "specs": product.get("specs", {}),
                "pages": {page["page"]}
            }
        else:
            # Merge category (if missing)
            if not products_dict[name].get("category") and product.get("category"):
                products_dict[name]["category"] = product.get("category")

            # Merge description
            if not products_dict[name].get("description") and product.get("description"):
                products_dict[name]["description"] = product.get("description")

            # Merge specs dictionary
            for k, v in product.get("specs", {}).items():
                products_dict[name]["specs"][k] = v

            # Track all appearance pages
            products_dict[name]["pages"].add(page["page"])

# -----------------------------------------
# STEP 2 — INSERT MERGED PRODUCTS INTO CHROMADB
# -----------------------------------------

doc_id = 1

for name, pdata in products_dict.items():

    text_lines = [
        f"Product Name: {pdata['product_name']}",
        f"Category: {pdata.get('category', '')}",
        f"Description: {pdata.get('description', '')}",
        "Specs:"
    ]

    for k, v in pdata["specs"].items():
        text_lines.append(f"- {k}: {v}")

    text_lines.append(f"Pages Found: {list(pdata['pages'])}")

    chunk_text = "\n".join(text_lines)

    embedding = embedder.encode(chunk_text).tolist()

    collection.add(
    ids=[str(doc_id)],
    documents=[chunk_text],
    metadatas=[{
        "product_name": pdata['product_name'],
        "category": pdata.get('category'),
        "pages": ",".join(map(str, pdata["pages"]))    # FIX HERE
    }],
    embeddings=[embedding]
)


    print(f"Inserted merged product {name} → id {doc_id}")
    doc_id += 1

print("\n🎉 Stored merged products into ChromaDB successfully!")
