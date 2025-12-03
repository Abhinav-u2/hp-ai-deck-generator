import logging
from typing import Dict, List, Any
from backend.app.graph.state import AgentState
import sqlite3
from pathlib import Path

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
            "upsell_opportunities": upsell,
            "extracted_requirements": customer_req    
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
    

    
    # DB_PATH = Path(__file__).resolve().parents[3] / "backend" / "app" / "database" / "products.db"
    DB_PATH = r"C:\Users\vikas.singh1\Desktop\hp-ai-deck-generator\backend\app\database\products.db"

    # --------------------------------------------------------------------
    # Fetch all accessories from SQL DB
    # --------------------------------------------------------------------
    def _fetch_accessories_from_db(self):
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()

        query = """
            SELECT 
                product_name,
                category,
                description,
                image_path
            FROM products
            WHERE LOWER(category) = 'accessories';
        """

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        accessories = []
        for r in rows:
            accessories.append({
                "product_name": r[0],
                "category": r[1],
                "description": r[2] or "",
                "image_path": r[3] or ""
            })

        return accessories



    # --------------------------------------------------------------------
    # Refactored Upsell Function (NO INVENTION)
    # --------------------------------------------------------------------



    def _generate_upsell(self, customer_req, products):
        """
        Return BOTH:
        - Text summary
        - Structured upsell data for PPT
        """

        # 1) Fetch accessories
        accessories = self._fetch_accessories_from_db()

        if not accessories:
            return {
                "text": "No accessories available.",
                "structured": []
            }

        # -------------------------------------------------------
        # 2) LLM INFERS REAL CATEGORY NAMES FROM PRODUCT DATA
        # -------------------------------------------------------
        cat_prompt = f"""
        You are an expert HP accessories classifier.

        TASK:
        For each accessory, infer its REAL category based on
        product_name + description.

        Allowed categories (choose only from these):
        Mouse, Keyboard, Headset, Backpack, Sleeve, Docking Station, Bag, Charger,
        Cable, Hub, Stylus, Webcam, Monitor, Audio, Other

        FORMAT STRICTLY:
        product_name | inferred_category

        Accessories:
        {accessories}
        """

        cat_output = self.llm(cat_prompt)

        # -------------------------------
        # 3) Parse inferred categories
        # -------------------------------
        grouped = {}

        for line in cat_output.split("\n"):
            if "|" not in line:
                continue
            name, cat = [x.strip() for x in line.split("|")]

            # find original accessory object
            item = next((a for a in accessories if a["product_name"] == name), None)
            if not item:
                continue

            grouped.setdefault(cat, []).append(item)

        # -------------------------------------------------------
        # 4) Ask LLM to pick TOP 5 best categories to upsell
        # -------------------------------------------------------
        recommend_prompt = f"""
        Choose the TOP 5 accessory categories to recommend.

        STRICT RULES:
        - Only choose from this list:
        {list(grouped.keys())}
        - Do NOT invent new categories.

        Customer Requirements:
        {customer_req}

        Selected laptop/products:
        {products}

        Return only category names in numbered list:
        1) Mouse
        2) Keyboard
        3) Backpack
        4) Sleeve
        5) Docking Station
        """

        llm_output = self.llm(recommend_prompt)

        final_categories = []
        for line in llm_output.split("\n"):
            if ")" in line:
                cat = line.split(")")[1].strip()
                if cat in grouped:
                    final_categories.append(cat)
            if len(final_categories) == 5:
                break

        # -------------------------------------------------------
        # 5) Select TOP 3 PRODUCTS per chosen category
        # -------------------------------------------------------
        structured = []
        for cat in final_categories:
            structured.append({
                "category": cat,
                "products": grouped[cat][:3]  # pick top 3
            })

        # -------------------------------------------------------
        # 6) Text summary for salesperson
        # -------------------------------------------------------
        summary_prompt = f"""
        Create a short, crisp upsell summary using ONLY these categories & products:

        {structured}

        Keep the summary short and bullet-based.
        """

        upsell_text = self.llm(summary_prompt)

        return {
            "text": upsell_text,
            "structured": structured
        }




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

    # ----------------------------
    # Requirements Extracted
    # ----------------------------
    print("\n🟧 Requirements")
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