import sys
import os
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any
from fastapi.responses import StreamingResponse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# ==========================================================
# PATH SETUP
# ==========================================================
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# ================================
# IMPORT AGENT SYSTEM
# ================================
try:
    from backend.app.agents.requirement_agent import requirement_node
    from backend.app.agents.retrieval_agent import retrieval_node
    from backend.app.agents.comparator_agent import comparator_node
    from backend.app.agents.pitch_agent import sales_pitch_node
    from backend.app.agents.deck_agent import create_professional_ppt
    from backend.app.graph.state import AgentState
except ImportError as e:
    print(f"⚠ Agent import error: {e}")

# ================================
# PDF CONVERSION
# ================================
try:
    from backend.tests.pdf_converter import convert_pptx_to_pdf, get_libreoffice_command
except ImportError:
    sys.path.append(str(BASE_DIR / "backend"))
    from pdf_converter import convert_pptx_to_pdf, get_libreoffice_command

# ==========================================================
# APP CONFIGURATION
# ==========================================================
load_dotenv()
app = FastAPI(title="HP Sales Deck Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

OUTPUT_DIR = BASE_DIR / "output"
DECK_DIR = OUTPUT_DIR / "decks"
PDF_DIR = OUTPUT_DIR / "pdfs"

DECK_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

# Shared LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm_client = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    google_api_key=GEMINI_API_KEY
)

# ==========================================================
# MODELS & UTIL
# ==========================================================
class QueryRequest(BaseModel):
    query: str

class CreativityEvalRequest(BaseModel):
    query: str
    sales_pitch: dict
    products: list


def get_deck_filename(query: str) -> str:
    query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
    return f"HP_Proposal_{query_hash}.pptx"

# ==========================================================
# CORE PIPELINE — USED BY BOTH STREAM & BLOCKING
# ==========================================================
def run_pipeline_sync(user_query: str, filename: str) -> Dict[str, Any]:
    """
    Executes all agents in sequence.
    """
    state: AgentState = {
        "user_query": user_query,
        "requirements": {},
        "retrieved_products": [],
        "ranked_products": [],
        "sales_pitch": {},
        "comparison_matrix": {},
        "deck_file_path": None,
        "llm": llm_client
    }

    try:
        state.update(requirement_node(state))
        state.update(retrieval_node(state))
        state.update(comparator_node(state))
        state.update(sales_pitch_node(state))

        deck_path = create_professional_ppt(
            sales_pitch=state["sales_pitch"],
            products=state.get("ranked_products", [])[:5],
            customer_query=user_query,
            output_file=str(DECK_DIR / filename)
        )

        state["deck_file_path"] = deck_path
        return state

    except Exception as e:
        print("❌ Pipeline error:", e)
        raise e

async def execute_pipeline(user_query: str, filename: str):
    """
    Runs pipeline + PDF conversion async safe.
    """
    state = await run_in_threadpool(run_pipeline_sync, user_query, filename)

    pdf_success = False
    deck_path = Path(state["deck_file_path"])
    if deck_path.exists():
        pdf_success = await convert_pptx_to_pdf(str(deck_path), str(PDF_DIR))

    return {
        "state": state,
        "pdf_available": pdf_success,
        "pdf_name": filename.replace(".pptx", ".pdf")
    }

# ==========================================================
# 🔥 STREAMING ENDPOINT FOR FRONT-END UI
# ==========================================================
@app.post("/query-stream")
async def stream_pipeline(request: QueryRequest):

    user_query = request.query
    filename = get_deck_filename(user_query)

    async def stream():
        # Initialize empty state for live update
        state: AgentState = {
            "user_query": user_query,
            "requirements": {},
            "retrieved_products": [],
            "ranked_products": [],
            "sales_pitch": {},
            "deck_file_path": None,
            "llm": llm_client
        }

        # 1️⃣ Requirement
        state.update(requirement_node(state))
        yield json.dumps({"step": 1, "label": "requirements", "data": state["requirements"]}) + "\n"
        await asyncio.sleep(0.05)

        # 2️⃣ Retrieval
        state.update(retrieval_node(state))
        yield json.dumps({"step": 2, "label": "retrieved_products", "data": state["retrieved_products"]}) + "\n"
        await asyncio.sleep(0.05)

        # 3️⃣ Comparator
        state.update(comparator_node(state))
        yield json.dumps({"step": 3, "label": "ranked_products", "data": state["ranked_products"]}) + "\n"
        await asyncio.sleep(0.05)

        # 4️⃣ Pitch Agent
        state.update(sales_pitch_node(state))
        yield json.dumps({"step": 4, "label": "sales_pitch", "data": state["sales_pitch"]}) + "\n"
        await asyncio.sleep(0.05)

        # 5️⃣ Deck + PDF
        deck_path = create_professional_ppt(
            sales_pitch=state["sales_pitch"],
            products=state.get("ranked_products", [])[:5],
            customer_query=user_query,
            output_file=str(DECK_DIR / filename)
        )
        state["deck_file_path"] = deck_path

        # Convert to PDF
        pdf_success = await convert_pptx_to_pdf(str(deck_path), str(PDF_DIR))

        yield json.dumps({
            "step": 5,
            "label": "ppt_ready",
            "filename": filename,
            "pdf_available": pdf_success
        }) + "\n"

        yield "END\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

# ==========================================================
# BLOCKING (API USE)
# ==========================================================
@app.post("/query")
async def handle_query(request: QueryRequest):
    try:
        filename = get_deck_filename(request.query)
        result = await execute_pipeline(request.query, filename)

        return {
            "status": "success",
            "filename": filename,
            "pdf_available": result["pdf_available"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================
# DOWNLOAD PPT
# ==========================================================
@app.get("/get_ppt")
async def get_ppt(query: str):
    filename = get_deck_filename(query)
    path = DECK_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="PPT not found")
    return FileResponse(path, filename="HP_Sales_Proposal.pptx")

# ==========================================================
# DOWNLOAD PDF
# ==========================================================
@app.get("/get_pdf")
async def get_pdf(query: str):
    pdf_filename = get_deck_filename(query).replace(".pptx", ".pdf")
    path = PDF_DIR / pdf_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(path, filename="HP_Sales_Proposal_Preview.pdf", media_type="application/pdf")

# ==========================================================

# ==========================================================
# 🔥 ADVANCED LLM-BASED CREATIVITY EVALUATION
# ==========================================================
@app.post("/evaluate-creativity-llm")
async def evaluate_creativity_llm(request: CreativityEvalRequest):
    """
    Uses Gemini LLM to evaluate creativity in the generated pitch.
    Produces scores per metric (1–10) + short explanation.
    """

    # ---- FIX: Ensure sales_pitch is dictionary ----
    sales_pitch = request.sales_pitch
    if isinstance(sales_pitch, str):
        try:
            sales_pitch = json.loads(sales_pitch)
        except:
            sales_pitch = {"pitch_summary": sales_pitch}

    # ---- FIX: Ensure products is list ----
    products = request.products
    if isinstance(products, str):
        try:
            products = json.loads(products)
        except:
            products = []

    pitch_summary = sales_pitch.get("pitch_summary", "")
    product_highlights = sales_pitch.get("product_highlights", "")
    reasons_to_buy = sales_pitch.get("reasons_to_buy", "")

    prompt = f"""
You are a senior HP sales presentation expert.

Evaluate the creativity and customer impact of the sales pitch below.

-----------------------
User Requirement:
{request.query}
-----------------------
Generated Sales Pitch:
Pitch Summary:
{pitch_summary}

Product Highlights:
{product_highlights}

Reasons to Buy:
{reasons_to_buy}

Products Included:
{json.dumps(products, indent=2)}
-----------------------

Evaluate on the following metrics:

1️⃣ Narrative Coherence (1-10):
- Is there a connected story flow?
- Clear transitions?
- Logical reasons?

2️⃣ Personalization (1-10):
- Does it adapt to user intent?
- Does it talk like it's written *for them*?

3️⃣ Emotional Appeal (1-10):
- Uses persuasive language?
- Creates confidence, urgency, aspiration?

4️⃣ Visual Creativity (1-10):
- Recommendations that support visually impressive storytelling?
- (Even if PPT not provided)

5️⃣ Solution Innovation (1-10):
- Does it introduce unique thinking?
- Upsell ideas? Alternatives? Future-proofing?

Respond ONLY IN JSON exactly like this:

{{
  "narrative_coherence": {{"score": 0, "reason": ""}},
  "personalization": {{"score": 0, "reason": ""}},
  "emotional_appeal": {{"score": 0, "reason": ""}},
  "visual_creativity": {{"score": 0, "reason": ""}},
  "solution_innovation": {{"score": 0, "reason": ""}},
  "final_score": 0
}}
"""

    response = llm_client.invoke(prompt)

    raw = response.content

    # Cleanup LLM fenced code block
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    raw = raw.strip()

    # Remove ```json or ``` if exists
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    # Remove accidental leading or trailing text outside JSON
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    raw = raw[first_brace:last_brace+1]

    try:
        evaluation = json.loads(raw)
    except Exception as e:
        print("⚠ JSON Parse Failed → cleaned text:", raw)
        raise HTTPException(status_code=500, detail="LLM returned invalid JSON")

    return evaluation


@app.get("/health")
async def health_check():
    return {
        "status": "running",
        "pdf_engine": get_libreoffice_command() is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
