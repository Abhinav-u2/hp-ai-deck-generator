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
    # 4️⃣ Rule-Based Fallback Parser (no LLM needed)
    # ---------------------------------------------------------
    def fallback_extract(self, query: str) -> Dict:
        LOG.warning("Using fallback requirement parser...")

        # Quantity
        qty = None
        m = re.search(r"(\d+)\s*(?:units|pcs|systems|machines|laptops|notebooks)", query.lower())
        if m:
            qty = int(m.group(1))

        # Budget
        price = None
        m = re.search(r"(\d[\d,]*)\s*(?:rs|₹|inr|rupees)", query.lower())
        if m:
            price = int(m.group(1).replace(",", ""))

        # RAM
        ram = None
        m = re.search(r"(\d+)\s*gb", query.lower())
        if m:
            ram = f"{m.group(1)}GB"

        # GPU
        gpu = None
        if "gpu" in query.lower() or "graphics" in query.lower():
            gpu = "Dedicated"

        # Weight
        weight = None
        m = re.search(r"(\d\.\d+)\s*kg", query.lower())
        if m:
            weight = float(m.group(1))

        # Category heuristic
        category = "Other"
        q = query.lower()

        if "laptop" in q or "notebook" in q:
            category = "Notebook"
        elif "tablet" in q:
            category = "Tablet"
        elif "desktop" in q or "computer" in q:
            category = "Desktop"
        elif "display" in q or "monitor" in q or "27-inch" in q:
            category = "Display"
        elif "docking" in q:
            category = "Docking Station"
        elif "scanner" in q or "mouse" in q or "keyboard" in q or "accessory" in q:
            category = "Accessory"

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
