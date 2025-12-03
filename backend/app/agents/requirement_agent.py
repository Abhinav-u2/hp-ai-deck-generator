from __future__ import annotations
import re
import logging
import json
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
 
load_dotenv()
LOG = logging.getLogger(__name__)
 
# -------------------------------------------------------------
# 1️⃣ Pydantic Schema (Relaxed for Stability)
# -------------------------------------------------------------
class ProductRequest(BaseModel):
    product_category: str = Field(
        description="The product category: Notebook, Tablet, Desktop, Workstation, Display, Accessory, etc."
    )
    quantity: int = Field(
        description="Number of units requested. Return 1 if not specified."
    )
    budget_per_unit: Optional[int] = Field(
        description="Maximum budget per unit in numbers only (e.g. 100000). Null if not mentioned."
    )
    # Changed to Any to prevent crash on bad LLM output
    specific_requirements: Any = Field(
        description="Technical specs as key-value pairs. Example: {'ram': '16GB', 'gpu': 'Nvidia', 'weight': 'light'}."
    )
    user_intent: str = Field(
        description="A short summary of the user's goal (e.g., 'Video Editing', 'Travel')."
    )
 
 
# -------------------------------------------------------------
# 2️⃣ Requirement Agent
# -------------------------------------------------------------
class RequirementAgent:
    def __init__(self, llm_api_key: Optional[str] = None):
        self.llm = None
        api_key = llm_api_key or os.getenv("GEMINI_API_KEY")
       
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0,
                google_api_key=api_key
            )
        else:
            LOG.warning("⚠️ No GEMINI_API_KEY found. Agent will use fallback mode only.")
 
    # ---------------------------------------------------------
    # 3️⃣ LLM Extraction
    # ---------------------------------------------------------
    def extract_with_llm(self, query: str) -> Dict:
        if not self.llm: return None
           
        try:
            structured_llm = self.llm.with_structured_output(ProductRequest)
 
            system_prompt = """
            You are an HP Sales Assistant. Extract structured data from the user's query.
           
            IMPORTANT RULES:
            1. Return 'specific_requirements' as a valid JSON Object, NOT a string.
               CORRECT: {"ram": "16GB", "gpu": "Nvidia"}
               WRONG: "16GB ram with nvidia gpu"
            2. Convert currency to integers (e.g. '1.5 Lakh' -> 150000).
            3. Infer the 'user_intent' based on context.
            """
 
            result = structured_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ])
           
            # --- DEBUGGING: Print Raw Output ---
            # print(f"🔍 DEBUG RAW LLM RESPONSE: {result}")
 
            data = result.model_dump()
 
            # --- FIX: Handle if specific_requirements came back as string ---
            specs = data.get("specific_requirements")
            if isinstance(specs, str):
                try:
                    # Try parsing if it looks like JSON
                    if specs.strip().startswith("{"):
                        data["specific_requirements"] = json.loads(specs)
                    else:
                        # Fallback: wrap the string in a generic key
                        data["specific_requirements"] = {"description": specs}
                except:
                    data["specific_requirements"] = {}
           
            elif specs is None:
                data["specific_requirements"] = {}
 
            return data
 
        except Exception as e:
            print(f"❌ Gemini extraction failed: {e}")
            return None
 
    # ---------------------------------------------------------
    # 4️⃣ Rule-Based Fallback Parser
    # ---------------------------------------------------------
    def fallback_extract(self, query: str) -> Dict:
        print("⚠️ Using fallback regex parser...")
        q = query.lower()
 
        qty = 1
        m_qty = re.search(r"(\d+)\s*(?:units|pcs|systems|machines|laptops)", q)
        if m_qty: qty = int(m_qty.group(1))
 
        price = None
        m_lakh = re.search(r"(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)\s*lakh", q)
        if m_lakh: price = int(float(m_lakh.group(1)) * 100000)
       
        ram = None
        m_ram = re.search(r"(\d+)\s*gb", q)
        if m_ram: ram = f"{m_ram.group(1)}GB"
 
        gpu = "Dedicated" if any(x in q for x in ["gpu", "nvidia", "rendering"]) else None
        weight = "Lightweight" if "light" in q or "travel" in q else None
 
        category = "Other"
        if any(x in q for x in ["laptop", "notebook"]): category = "Notebook"
        elif "workstation" in q: category = "Workstation"
        elif "desktop" in q: category = "Desktop"
        elif any(x in q for x in ["bag", "mouse"]): category = "Accessory"
 
        intent = "General Usage"
        if any(x in q for x in ["video", "edit", "render"]): intent = "High Performance"
        elif "travel" in q: intent = "Travel"
 
        return {
            "product_category": category,
            "quantity": qty,
            "budget_per_unit": price,
            "specific_requirements": {
                "ram": ram,
                "gpu": gpu,
                "weight": weight
            },
            "user_intent": intent
        }
 
    # ---------------------------------------------------------
    # 5️⃣ Main Entry Point
    # ---------------------------------------------------------
    def parse(self, query: str) -> Dict:
        result = self.extract_with_llm(query)
        if result: return result
        return self.fallback_extract(query)
 
# -------------------------------------------------------------
# 6️⃣ LangGraph Node Wrapper
# -------------------------------------------------------------
def requirement_node(state: AgentState) -> dict:
    print("--- 1. REQUIREMENT NODE: Parsing Query ---")
    query = state.get("user_query", "")
    agent = RequirementAgent()
    structured_data = agent.parse(query)
   
    if structured_data:
        print(f"✅ Extracted: {structured_data}")
        return {"requirements": structured_data}
    else:
        return {"requirements": {}}