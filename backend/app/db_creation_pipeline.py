
import subprocess
import sys
import os
from pathlib import Path
 
# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
PROJECT_ROOT = Path(os.getcwd())
 
# Define the Expected Output for Stage 1 (To check if we can skip it)
# Based on your extract_pdf.py logic: output/<pdf_name>/<pdf_name>_output.json
STAGE_1_OUTPUT_JSON = PROJECT_ROOT / "output" / "hp catalogue" / "hp catalogue_output.json"
 
# Define the Sequence of Scripts to Run
PIPELINE_STEPS = [
    {
        "stage": 1,
        "name": "Gemini PDF Extraction",
        "path": "backend/app/utils/pdf_parser/extract_pdf.py",
        "check_exists": True  # This flag tells logic to check for existing output
    },
    {
        "stage": 2,
        "name": "Image & Title Mining",
        "path": "backend/app/utils/image_parser/trial.py",
        "check_exists": False
    },
    {
        "stage": 3,
        "name": "SQL Database Ingestion",
        "path": "backend/app/database/sql_db.py",
        "check_exists": False
    },
    {
        "stage": 4,
        "name": "Vector Database Ingestion",
        "path": "backend/app/database/qdrantdb_client.py",
        "check_exists": False
    },
    {
        "stage": 5,
        "name": "Image Linking",
        "path": "backend/app/utils/update_image_path.py",
        "check_exists": False
    }
]
 
# ==========================================
# 🔧 HELPER FUNCTION
# ==========================================
def run_script(script_rel_path):
    """Runs a python script as a subprocess using the current python environment."""
    script_path = PROJECT_ROOT / script_rel_path
   
    if not script_path.exists():
        print(f"❌ ERROR: File not found: {script_path}")
        return False
 
    print(f"   ▶️ Running: {script_rel_path}...")
   
    try:
        # 'sys.executable' ensures we use the exact same python (venv) running this script
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
 
        # --- SPECIAL LOGIC FOR STAGE 1 ---
        if step["check_exists"] and STAGE_1_OUTPUT_JSON.exists():
            print(f"✅ JSON Output already exists at:")
            print(f"   {STAGE_1_OUTPUT_JSON}")
            print(f"⏩ SKIPPING Stage {step['stage']} to save API costs.\n")
            continue
       
        # --- RUN THE SCRIPT ---
        success = run_script(step["path"])
       
        if not success:
            print("\n🛑 PIPELINE HALTED due to error in previous step.")
            sys.exit(1)
           
        print(f"✅ Stage {step['stage']} Complete.\n")
 
    print(f"{'='*60}")
    print("🎉 FULL PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"{'='*60}")
 
if __name__ == "__main__":
    main()
 