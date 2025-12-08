import sys
import os
import subprocess
import platform
import logging
from fastapi.concurrency import run_in_threadpool
 
# Configure logging to print to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
def get_libreoffice_command():
    """
    Detects the LibreOffice executable path based on the OS.
    Returns the command string or None if not found.
    """
    system = platform.system()
   
    if system == "Linux":
        # Standard command on Linux (often in PATH)
        return "soffice"
   
    elif system == "Windows":
        # Check common Windows installation paths
        possible_paths = [
            os.getenv("LIBREOFFICE_PATH"),  # Allow custom path via Env Var
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
        for path in possible_paths:
            if path and os.path.exists(path):
                return path
               
    elif system == "Darwin":  # macOS
        possible_paths = [
             "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
 
    return None
 
def _run_conversion_process(pptx_path: str, output_dir: str) -> bool:
    """
    Synchronous function to run the subprocess.
    """
    soffice_cmd = get_libreoffice_command()
   
    if not soffice_cmd:
        logger.error("❌ LibreOffice not found. Cannot convert PDF.")
        return False
 
    try:
        # LibreOffice command to convert to PDF
        # --headless: run without GUI
        # --convert-to pdf: target format
        # --outdir: where to save
        cmd = [
            soffice_cmd,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            pptx_path
        ]
       
        logger.info(f"🔄 Converting {pptx_path} to PDF...")
       
        # Run subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60 # Timeout after 60 seconds
        )
       
        if result.returncode == 0:
            logger.info("✅ Conversion successful.")
            return True
        else:
            logger.error(f"⚠️ Conversion failed: {result.stderr}")
            return False
           
    except subprocess.TimeoutExpired:
        logger.error("❌ Conversion timed out.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during conversion: {e}")
        return False
 
async def convert_pptx_to_pdf(pptx_path: str, output_dir: str) -> bool:
    """
    Async wrapper that runs the conversion in a separate thread
    to prevent blocking the main FastAPI event loop.
    """
    return await run_in_threadpool(_run_conversion_process, pptx_path, output_dir)