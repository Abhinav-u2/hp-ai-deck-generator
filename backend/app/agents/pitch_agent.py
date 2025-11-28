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
        Generate SHORT and CONCISE product highlights.

        **Rules:**
        - For EACH product: 
        - Show the **Product Title**
        - Provide **exactly 4–5 bullet-point highlights**
        - Highlights must be:
        • Short (1 line each)
        • Benefit-focused (not just specs)
        • Clear and easy to scan
        - No extra explanation, no long paragraphs.
        - Do NOT add any extra information beyond the given product details

        Customer Requirement:
        {customer_req}

        Products (JSON):
        {products}

        Format STRICTLY like this example:
        ---
        **<Product Title>**
        - Bullet 1
        - Bullet 2
        - Bullet 3
        - Bullet 4
        - Bullet 5
        ---
        """
        return self.llm(prompt)



    def _generate_reasons(self, products, req, scores):
        prompt = f"""
        Generate SHORT and CONCISE reasons-to-buy for each product.

        **Rules:**
        - For EACH product:
        - Provide the **Product Title**
        - Give **2–3 bullet points** as reasons-to-buy
        - Reasons must be:
        • Based ONLY on the product information provided
        • Aligned with customer requirements: {req}
        • Reflect comparison scores: {scores}
        • Highlight unique advantages (performance, portability, value, graphics)
        - Do NOT add any extra information beyond the given product details
        - Keep output punchy, customer-facing, and easy to scan

        Products (JSON):
        {products}

        Format STRICTLY like this example:
        ---
        **<Product Title>**
        - Reason 1
        - Reason 2
        - Reason 3
        ---
        """
        return self.llm(prompt)


    def _competitive_advantages(self, products):
        prompt = f"""
        Generate SHORT and CONCISE competitive advantages for each product.

        **Rules:**
        - For EACH product:
        - Provide the **Product Title**
        - Give **3–4 bullet points** highlighting its competitive advantages
        - Focus only on the provided product information
        - Consider:
        • CPU/GPU performance
        • Build quality
        • Battery life and portability
        • Design and durability
        • Business-class features
        - Do NOT add any extra knowledge beyond the products provided
        - Keep bullets punchy, clear, and customer-facing

        Products (JSON):
        {products}

        Format STRICTLY like this example:
        ---
        **<Product Title>**
        - Advantage 1
        - Advantage 2
        - Advantage 3
        - Advantage 4
        - Advantage 5
        ---
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
        Generate a SHORT and CONCISE pitch summary (4–5 lines).

        **Rules:**
        - Use ONLY the information from:
        • Product highlights: {highlights}
        • Competitive advantages: {competitive_adv}
        - No new information or assumptions
        - Tone must be:
        • Professional
        • Confident
        • Sales-oriented
        - Make the pitch easy to read and persuasive
        - Keep it within 4–5 short lines maximum
        """
        return self.llm(prompt)



def format_sales_pitch_output(pitch):
    print("\n" + "="*70)
    print("🎯  FINAL SALES PITCH OUTPUT")
    print("="*70)

    # ----------------------------
    # Pitch Summary
    # ----------------------------
    print("\n📌 PITCH SUMMARY\n")
    print(pitch["pitch_summary"])
    print("\n" + "-"*70)

    # ----------------------------
    # Product Highlights
    # ----------------------------
    print("\n🟦 PRODUCT HIGHLIGHTS")
    print("-"*70)
    print(pitch["product_highlights"])

    # ----------------------------
    # Reasons to Buy
    # ----------------------------
    print("\n🟩 REASONS TO BUY")
    print("-"*70)
    print(pitch["reasons_to_buy"])

    # ----------------------------
    # Competitive Advantages
    # ----------------------------
    print("\n🟪 COMPETITIVE ADVANTAGES")
    print("-"*70)
    print(pitch["competitive_advantages"])

    # ----------------------------
    # Upsell Opportunities
    # ----------------------------
    print("\n🟧 UPSELL OPPORTUNITIES")
    print("-"*70)
    print(pitch["upsell_opportunities"])

    print("\n" + "="*70 + "\n")



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

    # 🔥 NEW: Pretty print formatted output in terminal
    format_sales_pitch_output(pitch_data)

    return {"sales_pitch": pitch_data}
