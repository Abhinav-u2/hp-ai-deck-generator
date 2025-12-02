import json
import sqlite3
import os
from pathlib import Path
 
# ================================
# DYNAMIC CONFIG (Relative Paths)
# ================================
BASE_DIR = Path(__file__).resolve().parents[3]
 
JSON_PATH = BASE_DIR / "output" / "hp catalogue" / "hp catalogue_output.json"
DB_PATH   = BASE_DIR / "backend" / "app" / "database" / "products.db"
KEY_FIELD = "product_name"
 
print(f"📂 Project Root: {BASE_DIR}")
print(f"📄 JSON Path: {JSON_PATH}")
print(f"🗄️ DB Path: {DB_PATH}")
 
 
# ================================
# Helper Functions
# ================================
def normalize_value(v):
    """Convert empty or NA values into None."""
    if v is None:
        return None
    v = str(v).strip()
    if v.lower() in ["na", "n/a", "", "none", "-", "null"]:
        return None
    return v
 
 
# 🔥 SAME NAME CLEANING AS CHROMA
def clean_name(name: str):
    if not name:
        return None
 
    name = name.strip()
    name_lower = name.lower()
 
    # Reject generic, category-level, or series names
    blacklist = [
        "notebook", "notebooks", "tablet", "display",
        "monitor", "pc", "ultrabook", "series"
    ]
 
    for b in blacklist:
        if name_lower == b or b in name_lower:
            return None
 
    return name
 
 
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
 
 
def connect_db(path):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    return sqlite3.connect(path)
 
 
def create_table(conn, spec_keys):
    """Create products table with initial columns."""
    spec_columns = ", ".join([f"spec_{k} TEXT" for k in spec_keys])
    sql = f"""
    CREATE TABLE IF NOT EXISTS products (
        {KEY_FIELD} TEXT PRIMARY KEY,
        product_id TEXT,
        category TEXT,
        description TEXT,
        image_path TEXT,
        source_page INTEGER
        {',' if spec_columns else ''} {spec_columns}
    )
    """
    conn.execute(sql)
    conn.commit()
 
 
def ensure_columns(conn, record):
    """Dynamically add missing columns in case new specs appear."""
    cur = conn.execute("PRAGMA table_info(products)")
    existing_cols = [row[1] for row in cur.fetchall()]
 
    for key in record.keys():
        if key not in existing_cols:
            conn.execute(f"ALTER TABLE products ADD COLUMN {key} TEXT")
 
 
def insert_or_update_product(conn, record):
    # Normalize values
    record = {k: normalize_value(v) for k, v in record.items()}
 
    ensure_columns(conn, record)
 
    # Check if product exists
    cur = conn.execute(
        f"SELECT * FROM products WHERE {KEY_FIELD} = ?",
        (record[KEY_FIELD],)
    )
    existing = cur.fetchone()
 
    if not existing:
        # INSERT new product
        columns = ", ".join(record.keys())
        placeholders = ", ".join(["?"] * len(record))
        conn.execute(
            f"INSERT INTO products ({columns}) VALUES ({placeholders})",
            tuple(record.values())
        )
        return
 
    # UPDATE only empty fields
    existing_dict = {col[0]: existing[idx] for idx, col in enumerate(cur.description)}
    updated = {}
 
    for key, new_val in record.items():
        old_val = normalize_value(existing_dict.get(key))
        if old_val is None and new_val is not None:
            updated[key] = new_val
 
    if updated:
        set_clause = ", ".join([f"{k}=?" for k in updated.keys()])
        params = list(updated.values()) + [record[KEY_FIELD]]
        conn.execute(
            f"UPDATE products SET {set_clause} WHERE {KEY_FIELD} = ?",
            params
        )
 
 
# ================================
# Main Import Logic (Now Matches Chroma)
# ================================
def import_json_to_sql():
    pages = load_json(JSON_PATH)
    conn = connect_db(DB_PATH)
 
    # Detect initial spec keys
    spec_keys = []
    for page_entry in pages:
        if page_entry.get("extracted_data"):
            spec_keys = list(page_entry["extracted_data"][0].get("specs", {}).keys())
            break
 
    create_table(conn, spec_keys)
 
    for page_entry in pages:
        page_num = page_entry.get("page")
        image_path = page_entry.get("chart_image_file", "")
 
        for product in page_entry.get("extracted_data", []):
 
            # CLEAN PRODUCT NAME FIRST (same as Chroma)
            raw_name = product.get("product_name", "").strip()
            name = clean_name(raw_name)
 
            if not name:
                continue  # skip generic/non-products
 
            # Build SQL record
            record = {
                KEY_FIELD: name,
                "product_id": product.get("product_id", "N/A"),
                "category": product.get("category", "N/A"),
                "description": product.get("description", "N/A"),
                "image_path": image_path,
                "source_page": page_num
            }
 
            # Flatten specs into spec_CPU, spec_GPU etc.
            for k, v in product.get("specs", {}).items():
                record[f"spec_{k}"] = v
 
            insert_or_update_product(conn, record)
 
    conn.commit()
    conn.close()
    print(f"✅ SQL Import Completed! {DB_PATH}")
 
 
# ================================
# Run script
# ================================
if __name__ == "__main__":
    import_json_to_sql()