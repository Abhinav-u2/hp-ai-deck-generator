import subprocess
import sys
import os
from pathlib import Path

# Add project root to sys.path
current_file = Path(__file__).resolve()
project_root = current_file.parents[3]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.utils.minio_sync import run_minio_sync 

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
PROJECT_ROOT = Path(os.getcwd())
OUTPUT_DIR = PROJECT_ROOT / "output"

# 1. Define Expected Outputs for Cache Checking
STAGE_1_JSON = OUTPUT_DIR / "hp catalogue" / "hp catalogue_output.json"
STAGE_2_META = OUTPUT_DIR / "image_metadata.json"
STAGE_3_DB   = PROJECT_ROOT / "backend" / "app" / "database" / "products.db" # Check where your sql_db.py actually saves it!
STAGE_4_VEC  = PROJECT_ROOT / "backend" / "app" / "database" / "qdrant"

# NOTE: Based on your previous logs, sql_db.py saves to:
# C:\Users\...\backend\app\database\products.db
# So we use that path for checking.

# Define the Sequence
PIPELINE_STEPS = [
    {
        "stage": 1,
        "name": "Gemini PDF Extraction",
        "path": "backend/app/utils/pdf_parser/extract_pdf.py",
        "check_path": STAGE_1_JSON
    },
    {
        "stage": 2,
        "name": "Image & Title Mining",
        "path": "backend/app/utils/image_parser/trial.py",
        "check_path": STAGE_2_META
    },
    {
        "stage": 3,
        "name": "SQL Database Ingestion",
        "path": "backend/app/database/sql_db.py",
        "check_path": STAGE_3_DB  # Skips if products.db exists
    },
    {
        "stage": 4,
        "name": "Vector Database Ingestion",
        "path": "backend/app/database/qdrantdb_client.py",
        "check_path": STAGE_4_VEC # Skips if qdrant folder exists
    },
    {
        "stage": 5,
        "name": "Image Linking",
        "path": "backend/app/utils/update_image_path.py",
        "check_path": None # Always run linking to ensure updates
    }
]

# ==========================================
# 🔧 HELPER FUNCTION
# ==========================================
def run_script(script_rel_path):
    """Runs a python script as a subprocess."""
    script_path = PROJECT_ROOT / script_rel_path
    
    if not script_path.exists():
        print(f"❌ ERROR: File not found: {script_path}")
        return False

    print(f"   ▶️ Running: {script_rel_path}...")
    
    try:
        subprocess.run([sys.executable, str(script_path)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ FAILED. Error code: {e.returncode}")
        return False

# ==========================================
# 🚀 MAIN EXECUTION
# ==========================================
def main():
    print(f"\n⚡ STARTING PIPELINE from: {PROJECT_ROOT}\n")

    for step in PIPELINE_STEPS:
        print(f"{'='*60}")
        print(f"STAGE {step['stage']}: {step['name']}")
        print(f"{'='*60}")

        # --- CACHE CHECK LOGIC ---
        if step["check_path"] and step["check_path"].exists():
            print(f"✅ Output already exists at:")
            print(f"   {step['check_path']}")
            print(f"⏩ SKIPPING Stage {step['stage']} (Cache Hit).\n")
            continue
        
        # --- RUN THE SCRIPT ---
        success = run_script(step["path"])
        
        if not success:
            print("\n🛑 PIPELINE HALTED due to error in previous step.")
            sys.exit(1)
            
        print(f"✅ Stage {step['stage']} Complete.\n")

    # --- STAGE 6: MINIO SYNC ---
    print(f"{'='*60}")
    print(f"STAGE 6: MinIO Cloud Sync")
    print(f"{'='*60}")
    try:
        run_minio_sync()
        print("✅ Stage 6 Complete.\n")
    except Exception as e:
        print(f"❌ MinIO Sync Failed: {e}")

    print(f"{'='*60}")
    print("🎉 FULL PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()