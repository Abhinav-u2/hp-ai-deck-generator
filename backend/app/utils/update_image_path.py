import sqlite3
import json

# -------------------------------
# CONFIG
# -------------------------------
DB_PATH = r"C:\Users\vikas.singh1\Desktop\hp-ai-deck-generator\backend\app\database\products.db"   # path to your SQL database
JSON_PATH = r"C:\Users\vikas.singh1\Desktop\hp-ai-deck-generator\output\image_metadata.json"    # path to your JSON file

# # -------------------------------
# # LOAD JSON FILE
# # -------------------------------


import re
from rapidfuzz import fuzz, process

# -----------------------
# CONFIG
# -----------------------
SIMILARITY_THRESHOLD = 70

def normalize(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"hp\s*", "", text)            # remove "hp" prefix
    text = re.sub(r"[^a-z0-9]+", " ", text)      # remove symbols
    text = re.sub(r"\s+", " ", text).strip()
    return text

# -----------------------
# LOAD JSON
# -----------------------
with open(JSON_PATH, "r", encoding="utf-8") as f:
    json_data = json.load(f)

json_titles = []
for item in json_data:
    if item["linked_text"]:
        json_titles.append({
            "norm": normalize(item["linked_text"]),
            "raw": item["linked_text"],
            "image": item["image_file"]
        })

# -----------------------
# CONNECT DB
# -----------------------
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT product_id, product_name, image_path FROM products")
rows = cursor.fetchall()

# -----------------------
# MATCHING
# -----------------------

count = 0

for product_id, product_name, current_image in rows:
    norm_name = normalize(product_name)

    best_score = 0
    best_img = None

    for jt in json_titles:

        # ---------- 1. Hard Prefix Match ----------
        if jt["norm"].startswith(norm_name):
            score = 100
        else:
            # ---------- 2. Fuzzy token match ----------
            score = fuzz.token_set_ratio(norm_name, jt["norm"])

        if score > best_score:
            best_score = score
            best_img = jt["image"]

    # ------------------- Update DB -------------------
    if best_score >= SIMILARITY_THRESHOLD and best_img:
        cursor.execute(
            "UPDATE products SET image_path = ? WHERE product_name = ?",
            (best_img, product_name)
        )
        print(f"[UPDATED] {product_name} -> {best_img}  (score {best_score})")
        count += 1
    else:
        print(f"[SKIPPED] {product_name} (no good match)")

conn.commit()
conn.close()
print("Done!")
print(count)

