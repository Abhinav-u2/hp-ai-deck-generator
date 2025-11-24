# backend/app/agents/requirement_agent.py

from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


LOG = logging.getLogger(__name__)


# -------------------------------------------------------------
# 1️⃣ Pydantic Schema for Structured Output
# -------------------------------------------------------------
class ProductRequest(BaseModel):
    product_category: str = Field(
        description=(
            "The product category: Notebook, Tablet, Desktop, Workstation, "
            "Display, Docking Station, Retail Solution, POS System, Accessory, "
            "Peripheral, Other."
        )
    )
    quantity: Optional[int] = Field(
        description="Number of units requested; default = 1 if missing"
    )
    budget_per_unit: Optional[int] = Field(
        description="Maximum budget per unit. Remove currency symbols."
    )
    specific_requirements: Dict[str, Any] = Field(
        description="Extracted technical constraints (RAM, GPU, weight, size, etc.)"
    )


# -------------------------------------------------------------
# 2️⃣ Requirement Agent
# -------------------------------------------------------------
class RequirementAgent:
    """
    Extracts structured product requirements from natural-language queries.

    Features:
    - Primary: Structured LLM extraction using Pydantic
    - Secondary: Rule-based fallback parser
    - Category classifier for HP catalogue use cases
    """

    CATEGORIES = [
        "Notebook", "Laptop", "Tablet", "Desktop", "Workstation",
        "Display", "Monitor", "Thin Client", "Retail Solution",
        "POS System", "Accessory", "Docking Station", "Peripheral", "Other"
    ]

    def __init__(self, llm_api_key: Optional[str] = None):
        self.llm = None
        if llm_api_key:
            self.llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=llm_api_key)

    # ---------------------------------------------------------
    # 3️⃣ LLM Extraction
    # ---------------------------------------------------------
    def extract_with_llm(self, query: str) -> Dict:
        try:
            structured_llm = self.llm.with_structured_output(ProductRequest)

            system_prompt = (
                "You are an HP Pre-Sales Requirement Extraction Agent. "
                "Your task: Convert user queries into structured fields:\n\n"
                "1. Correct HP product category\n"
                "2. Quantity\n"
                "3. Budget per unit (numeric)\n"
                "4. Technical requirements (RAM, GPU, CPU, screen size, weight, etc.)\n\n"
                "Always choose the most accurate category from the list."
            )

            result = structured_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ])

            LOG.info("LLM successfully extracted requirements")
            return result.model_dump()

        except Exception as e:
            LOG.error("LLM extraction failed: %s", str(e))
            return None

   # ---------------------------------------------------------
    # 4️⃣ Rule-Based Fallback Parser (Improved)
    # ---------------------------------------------------------
    def fallback_extract(self, query: str) -> Dict:
        LOG.warning("Using fallback requirement parser...")
        q = query.lower()

        # 1. Quantity
        qty = None
        # Looks for "10 laptops", "5 units", etc.
        m_qty = re.search(r"(\d+)\s*(?:units|pcs|systems|machines|laptops|notebooks)", q)
        if m_qty:
            qty = int(m_qty.group(1))

        # 2. Budget (Handle 'Lakh', 'k', and standard numbers)
        price = None
        
        # Check for 'Lakh' (e.g., "1.5 lakh", "1 lakh")
        m_lakh = re.search(r"(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)\s*lakh", q)
        if m_lakh:
            price = int(float(m_lakh.group(1)) * 100000)
        
        # Check for 'k' (e.g., "100k")
        elif "k" in q:
            m_k = re.search(r"(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)\s*k", q)
            if m_k:
                price = int(float(m_k.group(1)) * 1000)
        
        # Standard numbers (e.g., "100000", "1,00,000")
        if not price:
            m_num = re.search(r"(?:rs\.?|₹|inr)\s*(\d[\d,]*)", q)
            if m_num:
                price = int(m_num.group(1).replace(",", ""))

        # 3. RAM
        ram = None
        m_ram = re.search(r"(\d+)\s*gb", q)
        if m_ram:
            ram = f"{m_ram.group(1)}GB"

        # 4. GPU
        gpu = None
        if "gpu" in q or "graphics" in q or "nvidia" in q:
            gpu = "Dedicated"

        # 5. Weight
        weight = None
        if "light" in q:
            weight = "Lightweight" # Abstract constraint
        
        m_weight = re.search(r"(\d\.\d+)\s*kg", q)
        if m_weight:
            weight = f"{m_weight.group(1)} kg"

        # 6. Category Heuristic
        category = "Other"
        if "laptop" in q or "notebook" in q:
            category = "Notebook"
        elif "workstation" in q or "zbook" in q:
            category = "Workstation" # Specific overrides
        elif "tablet" in q:
            category = "Tablet"
        elif "desktop" in q or "computer" in q or "pc" in q:
            category = "Desktop"
        elif "display" in q or "monitor" in q:
            category = "Display"
        elif "bag" in q or "backpack" in q or "mouse" in q:
            category = "Accessories"

        return {
            "product_category": category,
            "quantity": qty or 1,
            "budget_per_unit": price,
            "specific_requirements": {
                "ram": ram,
                "gpu": gpu,
                "weight": weight
            }
        }

    # ---------------------------------------------------------
    # 5️⃣ Public Method
    # ---------------------------------------------------------
    def parse(self, query: str) -> Dict:
        """
        Main entry point used by orchestrator.
        Attempts LLM extraction → otherwise fallback parser.
        """
        # Try LLM first
        if self.llm:
            result = self.extract_with_llm(query)
            if result:
                return result

        # Fallback parser
        return self.fallback_extract(query)


# -------------------------------------------------------------
# Quick Test
# -------------------------------------------------------------
if __name__ == "__main__":
    agent = RequirementAgent(llm_api_key=None)  # no LLM → fallback only

    test_query = "We need 10 laptops for design team, ₹1,00,000 each, 16GB RAM, lightweight, dedicated GPU."
    print(agent.parse(test_query))

# ... [Your existing code ends here] ...

# -------------------------------------------------------------
# 6️⃣ LangGraph Node Wrapper
# -------------------------------------------------------------
from backend.app.graph.state import AgentState

def requirement_node(state: AgentState) -> dict:
    """
    LangGraph Node:
    1. Reads 'user_query' from state.
    2. Uses RequirementAgent to parse it.
    3. Updates 'requirements' in state.
    """
    print("--- 1. REQUIREMENT NODE: Parsing Query ---")
    query = state["user_query"]
    
    # Initialize agent (Ensure API key is set in env if using LLM)
    agent = RequirementAgent(llm_api_key=None) 
    
    # Use the parse method from your existing class
    structured_data = agent.parse(query)
    
    if structured_data:
        print(f"✅ Extracted: {structured_data}")
        return {"requirements": structured_data}
    else:
        print("❌ Failed to extract requirements.")
        return {"requirements": {}}