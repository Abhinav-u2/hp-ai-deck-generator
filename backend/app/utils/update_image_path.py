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
# with open(JSON_PATH, "r", encoding="utf-8") as f:
#     json_data = json.load(f)

# # Convert JSON list into a dict for faster lookup
# # { linked_text: image_file }
# json_lookup = {item['linked_text']: item['image_file'] for item in json_data}

# # -------------------------------
# # CONNECT TO DB
# # -------------------------------
# conn = sqlite3.connect(DB_PATH)
# cursor = conn.cursor()

# # Fetch all product names and their current image_path
# cursor.execute("SELECT product_id, product_name, image_path FROM products")
# rows = cursor.fetchall()

# # -------------------------------
# # UPDATE IMAGE PATHS
# # -------------------------------
# for row in rows:
#     product_id, product_name, current_image = row
#     # Check if product_name matches any linked_text in JSON
#     if product_name in json_lookup:
#         new_image_path = json_lookup[product_name]
#         # Update only if the path is different
#         if new_image_path != current_image:
#             cursor.execute(
#                 "UPDATE products SET image_path = ? WHERE product_id = ?",
#                 (new_image_path, product_id)
#             )

# # Commit changes and close connection
# conn.commit()
# conn.close()

# print("Database update complete!")



# from rapidfuzz import fuzz

# # -------------------------------
# # CONFIG
# # -------------------------------
# # DB_PATH = "your_database.db"   # path to your SQL database
# # JSON_PATH = "products.json"    # path to your JSON file
# SIMILARITY_THRESHOLD = 50      # minimum match percentage

# # -------------------------------
# # LOAD JSON FILE
# # -------------------------------
# with open(JSON_PATH, "r", encoding="utf-8") as f:
#     json_data = json.load(f)

# linked_text_list = [item['linked_text'] for item in json_data]
# json_lookup = {item['linked_text']: item['image_file'] for item in json_data}

# # -------------------------------
# # CONNECT TO DB
# # -------------------------------
# conn = sqlite3.connect(DB_PATH)
# cursor = conn.cursor()
# cursor.execute("SELECT product_id, product_name, image_path FROM products")
# rows = cursor.fetchall()

# # -------------------------------
# # PREFIX-BASED FUZZY MATCH
# # -------------------------------
# for row in rows:
#     product_id, product_name, current_image = row
#     best_match = None
#     best_score = 0

#     for linked_text in linked_text_list:
#         # Check if linked_text starts with product_name (prefix match)
#         if linked_text.lower().startswith(product_name.lower()):
#             # Calculate similarity (strict order, only length of product_name considered)
#             score = fuzz.partial_ratio(product_name, linked_text)
#             if score > best_score:
#                 best_score = score
#                 best_match = linked_text

#     if best_match and best_score >= SIMILARITY_THRESHOLD:
#         new_image_path = json_lookup[best_match]
#         if new_image_path != current_image:
#             cursor.execute(
#                 "UPDATE products SET image_path = ? WHERE product_id = ?",
#                 (new_image_path, product_id)
#             )
#             print(f"Updated '{product_name}' -> '{new_image_path}' (Score: {best_score})")

# conn.commit()
# conn.close()
# print("Database update complete with prefix-based matching!")



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


# import re
# # import json
# # import sqlite3

# # -----------------------
# # CONFIG
# # -----------------------
# def normalize(text):
#     if not text:
#         return ""
#     text = text.lower()
#     text = re.sub(r"hp\s*", "", text)            # remove "hp" prefix
#     text = re.sub(r"[^a-z0-9]+", " ", text)      # remove symbols
#     text = re.sub(r"\s+", " ", text).strip()
#     return text

# # -----------------------
# # LOAD JSON
# # -----------------------
# with open(JSON_PATH, "r", encoding="utf-8") as f:
#     json_data = json.load(f)

# json_map = {}     # norm → image path + raw

# for item in json_data:
#     if item["linked_text"]:
#         norm_title = normalize(item["linked_text"])
#         json_map[norm_title] = {
#             "raw": item["linked_text"],
#             "image": item["image_file"]
#         }

# # -----------------------
# # CONNECT DB
# # -----------------------
# conn = sqlite3.connect(DB_PATH)
# cursor = conn.cursor()
# cursor.execute("SELECT product_id, product_name FROM products")
# rows = cursor.fetchall()

# # -----------------------
# # EXACT MATCHING
# # -----------------------

# count = 0

# for product_id, product_name in rows:
#     norm_name = normalize(product_name)

#     if norm_name in json_map:
#         best_img = json_map[norm_name]["image"]

#         cursor.execute(
#             "UPDATE products SET image_path = ? WHERE product_name = ?",
#             (best_img, product_name)
#         )

#         print(f"[UPDATED] {product_name} → {best_img}")
#         count += 1

#     else:
#         print(f"[NO MATCH] {product_name}")

# conn.commit()
# conn.close()

# print("Done!")
# print(count)
