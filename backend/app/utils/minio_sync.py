import os
import json
import sqlite3
import re
from pathlib import Path
from datetime import timedelta
from minio import Minio
from dotenv import load_dotenv

# Try importing rapidfuzz
try:
    from rapidfuzz import fuzz
except ImportError:
    print("⚠️ RapidFuzz not found. Install: pip install rapidfuzz")
    fuzz = None

# ===============================
# ⚙️ CONFIGURATION
# ===============================
load_dotenv()

# Define Paths relative to Project Root
BASE_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = BASE_DIR / "output"
SQL_DB_PATH = BASE_DIR / r"backend\app\database\products.db"
METADATA_PATH = OUTPUT_DIR / "image_metadata.json"

# MinIO Config
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "hp-catalogue-assets")
# Parse boolean for secure connection
SECURE_CONNECTION = str(os.getenv("MINIO_SECURE", "False")).lower() == "true"

# ===============================
# ☁️ MINIO UPLOADER CLASS
# ===============================
class MinIOUploader:
    def __init__(self):
        # 🔍 DEBUG: Print the exact values being used
        # print(f"🔍 DEBUG: Attempting MinIO Connection...")
        # print(f"   ► Endpoint:   '{MINIO_ENDPOINT}'")
        # print(f"   ► Access Key: '{MINIO_ACCESS_KEY}'")
        # print(f"   ► Secure:     {SECURE_CONNECTION}")

        # AUTO-FIX: Remove http/https prefix if present (Common Error)
        clean_endpoint = MINIO_ENDPOINT.replace("http://", "").replace("https://", "").strip("/")
        if clean_endpoint != MINIO_ENDPOINT:
            print(f"   ⚠️ Auto-Fixing Endpoint: '{MINIO_ENDPOINT}' -> '{clean_endpoint}'")

        try:
            self.client = Minio(
                clean_endpoint,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=SECURE_CONNECTION
            )
            
            # Ensure bucket exists
            if not self.client.bucket_exists(MINIO_BUCKET):
                self.client.make_bucket(MINIO_BUCKET)
                print(f"☁️  Created bucket: {MINIO_BUCKET}")
            
            print("☁️  Connected to MinIO.")
        except Exception as e:
            print(f"❌ Failed to connect to MinIO: {e}")
            self.client = None

    def upload_and_get_link(self, local_path_str, object_name):
        if not self.client: return None
        
        file_path = Path(local_path_str)
        if not file_path.exists(): 
            # Try resolving relative to project root if absolute path fails
            file_path = BASE_DIR / local_path_str
            if not file_path.exists():
                return None

        try:
            # Upload
            self.client.fput_object(MINIO_BUCKET, object_name, str(file_path))
            
            # Generate Presigned URL (7 Days)
            url = self.client.presigned_get_object(
                MINIO_BUCKET, 
                object_name, 
                expires=timedelta(days=7)
            )
            return url
        except Exception as e:
            print(f"   ❌ Upload Error: {e}")
            return None

# ===============================
# 🛠️ HELPER FUNCTIONS
# ===============================
def normalize(text):
    if not text: return ""
    text = text.lower()
    text = re.sub(r"hp\s*", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()

def ensure_cloud_column(conn):
    try:
        conn.execute("ALTER TABLE products ADD COLUMN cloud_url TEXT")
    except sqlite3.OperationalError:
        pass

# ===============================
# 🚀 MAIN SYNC LOGIC
# ===============================
def run_minio_sync():
    print(f"\n🚀 [Stage 5] Starting MinIO Sync (External Module)...")
    
    if not METADATA_PATH.exists():
        print(f"❌ Metadata not found: {METADATA_PATH}")
        return

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    # Pre-process JSON titles for speed
    json_titles = []
    for item in meta_data:
        if item.get("linked_text"):
            json_titles.append({
                "norm": normalize(item["linked_text"]),
                "path": item["image_file"]
            })

    conn = sqlite3.connect(SQL_DB_PATH)
    ensure_cloud_column(conn)
    cursor = conn.cursor()
    
    cursor.execute("SELECT product_name, image_path, cloud_url FROM products")
    rows = cursor.fetchall()
    
    uploader = MinIOUploader()
    matches = 0

    print(f"📦 Scanning {len(rows)} products...")

    for row in rows:
        prod_name = row[0]
        current_cloud = row[2]
        
        # 1. Find Match
        norm_prod = normalize(prod_name)
        best_score = 0
        best_img = None

        for jt in json_titles:
            score = 0
            # Exact Substring (High Confidence)
            if norm_prod in jt["norm"] or jt["norm"] in norm_prod:
                score = 95
            # Fuzzy Match
            elif fuzz:
                score = fuzz.token_set_ratio(norm_prod, jt["norm"])
            
            if score > best_score:
                best_score = score
                best_img = jt["path"]

        # 2. Upload if match found
        if best_score > 70 and best_img:
            # We force upload to ensure link is fresh
            fname = Path(best_img).name
            # Object name structure: products/filename.png
            obj_name = f"products/{fname}"
            
            new_url = uploader.upload_and_get_link(best_img, obj_name)
            
            if new_url:
                cursor.execute(
                    "UPDATE products SET image_path = ?, cloud_url = ? WHERE product_name = ?",
                    (best_img, new_url, prod_name)
                )
                matches += 1

    conn.commit()
    conn.close()
    print(f"✅ [Stage 5] Synced {matches} images to MinIO.")

if __name__ == "__main__":
    run_minio_sync()