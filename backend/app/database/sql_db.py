import json
import sqlite3
import os

# ================================
# CONFIG — set your paths here
# ================================
import json
import sqlite3
import os
from pathlib import Path  # <--- Add this import

# ================================
# DYNAMIC CONFIG (Relative Paths)
# ================================
# Calculates project root by going up 3 levels from this file:
# backend/app/database/sql_db.py -> backend/app/database -> backend/app -> backend -> ROOT
BASE_DIR = Path(__file__).resolve().parents[3]

# Construct paths relative to the project root
JSON_PATH = BASE_DIR / "output" / "hp catalogue" / "hp catalogue_output.json"
DB_PATH   = BASE_DIR / "backend" / "app" / "database" / "products.db"
KEY_FIELD = "product_name"

# Verify paths (Optional, for debugging)
print(f"📂 Project Root: {BASE_DIR}")
print(f"📄 JSON Path: {JSON_PATH}")
print(f"🗄️ DB Path: {DB_PATH}")




# ================================
# Helper functions
# ================================
def normalize_value(v):
    """Convert empty or NA values into None."""
    if v is None:
        return None
    v = str(v).strip()
    if v.lower() in ["na", "n/a", "", "none", "-", "null"]:
        return None
    return v


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
    # Normalize all values
    record = {k: normalize_value(v) for k, v in record.items()}

    # Ensure all columns exist
    ensure_columns(conn, record)

    # Check if product exists
    cur = conn.execute(f"SELECT * FROM products WHERE {KEY_FIELD} = ?", (record[KEY_FIELD],))
    existing = cur.fetchone()

    if not existing:
        # INSERT new product
        columns = ", ".join(record.keys())
        placeholders = ", ".join(["?"] * len(record))
        conn.execute(f"INSERT INTO products ({columns}) VALUES ({placeholders})", tuple(record.values()))
        return

    # UPDATE existing: only fill NA fields
    existing_dict = {col[0]: existing[idx] for idx, col in enumerate(cur.description)}
    updated_fields = {}
    for key, new_val in record.items():
        old_val = normalize_value(existing_dict.get(key))
        if old_val is None and new_val is not None:
            updated_fields[key] = new_val

    if updated_fields:
        set_clause = ", ".join([f"{k} = ?" for k in updated_fields.keys()])
        params = list(updated_fields.values()) + [record[KEY_FIELD]]
        conn.execute(f"UPDATE products SET {set_clause} WHERE {KEY_FIELD} = ?", params)


# ================================
# Main import function
# ================================
def import_json_to_sql():
    pages = load_json(JSON_PATH)
    conn = connect_db(DB_PATH)

    # Determine initial spec keys from first product that exists
    spec_keys = []
    for page_entry in pages:
        if page_entry.get("extracted_data"):
            spec_keys = list(page_entry["extracted_data"][0].get("specs", {}).keys())
            break

    create_table(conn, spec_keys)

    # Process each page and each product
    for page_entry in pages:
        page_num = page_entry.get("page")
        image_path = page_entry.get("chart_image_file", "")

        for product in page_entry.get("extracted_data", []):
            # Build record dict
            record = {
                KEY_FIELD: product.get("product_name", "Unknown Product"),
                "product_id": product.get("product_id", "N/A"),
                "category": product.get("category", "N/A"),
                "description": product.get("description", "N/A"),
                "image_path": image_path,
                "source_page": page_num
            }

            # Flatten specs
            for k, v in product.get("specs", {}).items():
                record[f"spec_{k}"] = v

            insert_or_update_product(conn, record)

    conn.commit()
    conn.close()
    print(f"✅ Import completed! Database saved at: {DB_PATH}")


# ================================
# Run script
# ================================
if __name__ == "__main__":
    import_json_to_sql()
