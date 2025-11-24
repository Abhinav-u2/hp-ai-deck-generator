import fitz
import io
import os
import time
import json
import random
from PIL import Image
from google import genai
from dotenv import load_dotenv
from prompts.prompts import prompt  # your external prompt
from pathlib import Path 

# -----------------------------------------
# DYNAMIC PATHS
# -----------------------------------------
# Calculate root relative to: backend/app/agents/retrieval_agent.py
BASE_DIR = Path(__file__).resolve().parents[3]
BASE_DIR= Path(os.getcwd())

load_dotenv()

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

input_folder = BASE_DIR / "data" / "raw" / "hp catalogue.pdf"
output_base = BASE_DIR / "output"
os.makedirs(output_base, exist_ok=True)


# -------------------------------------------------
# Function: Parse file name → company, year, quarter
# -------------------------------------------------
def parse_filename(file):
    """
    Example: Microsoft_2025_Q4.pdf
    Returns: company, year, quarter, base_name
    """
    base = os.path.basename(file).replace(".pdf", "")
    parts = base.split("_")

    company = parts[0]
    year = parts[1] if len(parts) > 1 else "NA"
    quarter = parts[2] if len(parts) > 2 else "NA"

    return company, year, quarter, base


# -------------------------------------------------
# Gemini call with retries (503 fix)
# -------------------------------------------------
def gemini_request_with_retry(client, model, contents, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents
            )
            return response  # success

        except Exception as e:
            error_msg = str(e)

            # 503 or overloaded → retry
            if "503" in error_msg or "UNAVAILABLE" in error_msg:
                wait = 2 ** attempt + random.uniform(0, 1)
                print(f"⚠️ 503 Overloaded. Retry {attempt}/{max_retries} in {wait:.1f}s...")
                time.sleep(wait)
                continue

            print("❌ Non-retryable error:", error_msg)
            raise e

    print("❌ Gemini model unavailable after all retries.")
    return None


# -------------------------------------------------
# PROCESS A SINGLE PDF
# -------------------------------------------------
def process_pdf(pdf_path):
    print(f"\n\n============================")
    print(f"PROCESSING PDF: {pdf_path}")
    print(f"============================")

    company, year, quarter, base_name = parse_filename(pdf_path)

    # Output folder for this PDF
    pdf_output_dir = os.path.join(output_base, base_name)
    os.makedirs(pdf_output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    output = []

    for page_num, page in enumerate(doc, start=1):
        print(f"\n======== PAGE {page_num} ========")

        slide = {
            "page": page_num,
            "text": "",
            "tables": [],
            "chart_image_file": "",
            "extracted_data": {}
        }

        # ----------------------------------------------------
        # 1) Extract text
        # ----------------------------------------------------
        extracted_text = page.get_text("text")
        slide["text"] = extracted_text.strip()

        # ----------------------------------------------------
        # 2) Extract tables
        # ----------------------------------------------------
        try:
            tables = page.find_tables()
            slide["tables"] = [t.extract() for t in tables]
        except:
            slide["tables"] = []

        # ----------------------------------------------------
        # 3) Save slide image (300 DPI)
        # ----------------------------------------------------
        image_name = f"{company}_{year}_{quarter}_slide{page_num}.png"
        image_path = os.path.join(pdf_output_dir, image_name)

        pix = page.get_pixmap(dpi=300)
        pix.save(image_path)
        slide["chart_image_file"] = image_path

        print(f"Saved image: {image_path}")

        # ----------------------------------------------------
        # 4) Gemini Vision Extraction (with retries)
        # ----------------------------------------------------
        time.sleep(1.2)  # safe delay

        # Adaptive prompting based on slide content
        contextual_instruction = ""

        if "TTM" in slide["text"] and ("Reconciliation" in slide["text"] or "Cash Flow" in slide["text"]):
            contextual_instruction = (
                "This slide contains a reconciliation table. Extract all rows, "
                "columns, values, and headers exactly as shown."
            )

        elif ("Net Sales" in slide["text"] or "Segment Results" in slide["text"]) and "MM" in slide["text"]:
            contextual_instruction = (
                "This slide contains a segmented or stacked bar chart. Extract "
                "ALL segment-level values for each bar, not just totals."
            )

        elif any(x in slide["text"] for x in ["Income", "Revenue", "Shares"]):
            contextual_instruction = (
                "This slide contains financial metrics. Extract each numerical "
                "value, period, and growth rate."
            )

        full_prompt = [prompt]
        if contextual_instruction:
            full_prompt.append(f"ADDITIONAL GUIDANCE: {contextual_instruction}")

        full_prompt.append(Image.open(image_path))

        response = gemini_request_with_retry(
            client=client,
            model="gemini-2.5-flash",
            contents=full_prompt
        )

        # If retries fail → store fallback
        if response is None:
            slide["extracted_data"] = {
                "error": "Gemini overloaded — retries exhausted.",
                "raw_output": ""
            }
            output.append(slide)
            continue

        # ----------------------------------------------------
        # 5) Parse JSON Safely
        # ----------------------------------------------------
        try:
            json_text = response.text.strip()

            if json_text.startswith("```json"):
                json_text = json_text.replace("```json", "").replace("```", "").strip()

            slide["extracted_data"] = json.loads(json_text)

        except json.JSONDecodeError:
            slide["extracted_data"] = {
                "raw_output": response.text,
                "error": "JSON Decode Failure"
            }

        output.append(slide)

    # ----------------------------------------------------
    # Save output JSON
    # ----------------------------------------------------
    json_path = os.path.join(pdf_output_dir, f"{base_name}_output.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"\n📄 JSON saved → {json_path}")
    print("🎉 Completed:", pdf_path)


# -------------------------------------------------
# MAIN: Process a single PDF
# -------------------------------------------------
if __name__ == "__main__":
    pdf_path = BASE_DIR / "data" / "raw" / "hp catalogue.pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
    else:
        process_pdf(pdf_path)
        print("\n🎯 Single PDF processed successfully!")

