import logging
from typing import Dict, List, Any
from backend.app.graph.state import AgentState

LOG = logging.getLogger(__name__)

class SalesPitchAgent:

    def __init__(self, llm):
        """
        LLM-Based Sales Pitch Generator.
        """
        self.llm = llm

    # ---------------------------------------------------------
    # Main public method
    # ---------------------------------------------------------
    def generate_pitch(self, customer_req: Dict, products: List[Dict], scores: Dict):
        """
        Generates all sales pitch components using LLM.
        """
        highlights = self._generate_highlights(products, customer_req)
        reasons_to_buy = self._generate_reasons(products, customer_req, scores)
        competitive_adv = self._competitive_advantages(products)
        upsell = self._generate_upsell(customer_req, products)

        pitch_summary = self._summarize_pitch(highlights, competitive_adv)

        return {
            "pitch_summary": pitch_summary,
            "product_highlights": highlights,
            "reasons_to_buy": reasons_to_buy,
            "competitive_advantages": competitive_adv,
            "upsell_opportunities": upsell
        }

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------
    def _generate_highlights(self, products, customer_req):
        prompt = f"""
        Convert product specifications into benefit-oriented highlights.
        Customer Requirement:
        {customer_req}

        Products:
        {products}

        Focus on high-value benefits, design strengths, performance gains,
        and business outcomes for the customer.
        """
        return self.llm(prompt)

    def _generate_reasons(self, products, req, scores):
        prompt = f"""
        For each product, generate 3–5 strong reasons-to-buy based on:
        - Customer requirements: {req}
        - Comparison scores: {scores}
        - Unique advantages in performance, portability, value, or graphics

        Make the output punchy, customer-facing, and easy to consume.
        """
        return self.llm(prompt)

    def _competitive_advantages(self, products):
        prompt = f"""
        Compare these HP models and generate competitive advantages.
        Focus on:
        - CPU/GPU performance
        - Build quality
        - Battery and portability
        - Design and durability
        - Business-class features

        Products:
        {products}
        """
        return self.llm(prompt)

    def _generate_upsell(self, customer_req, products):
        prompt = f"""
        Suggest upsell and cross-sell opportunities for:

        Customer Requirement:
        {customer_req}

        Based on:
        - Product usage
        - HP's accessory ecosystem
        - Productivity or protection enhancements
        """
        return self.llm(prompt)

    def _summarize_pitch(self, highlights, competitive_adv):
        prompt = f"""
        Create a short, persuasive 4–5 line pitch summary using:
        - The best product highlights
        - Key competitive advantages

        Tone: Professional, confident, sales-oriented.
        """
        return self.llm(prompt)


# -------------------------------------------------------------
# LangGraph Node Wrapper (Same style as comparator_node)
# -------------------------------------------------------------
def sales_pitch_node(state: AgentState) -> dict:
    print("--- 4. SALES PITCH NODE: Generating Sales Pitch ---")

    llm = state.get("llm")
    requirements = state.get("requirements", {})
    ranked_products = state.get("ranked_products", [])
    comparison_scores = state.get("comparison_matrix", {}).get("comparison_scores", {})

    if not ranked_products:
        print("⚠️ No ranked products available for sales pitch.")
        return {"sales_pitch": {}}

    agent = SalesPitchAgent(llm)

    pitch_data = agent.generate_pitch(
        customer_req=requirements,
        products=ranked_products,
        scores=comparison_scores
    )

    print("📝 Sales pitch generated successfully.")

    return {"sales_pitch": pitch_data}
