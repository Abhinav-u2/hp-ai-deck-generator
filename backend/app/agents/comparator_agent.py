import json
import logging
import os
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.app.graph.state import AgentState
from dotenv import load_dotenv
 
# Load env to get API key
load_dotenv()
 
LOG = logging.getLogger(__name__)
 
# ==========================================
# 🧠 LLM PROMPT
# ==========================================
COMPARATOR_PROMPT = """
You are an expert Sales Engineer. Your goal is to RANK and SCORE a list of products based on how well they match the user's specific requirements.
 
### 1. User Request
- **Category:** {category}
- **Intent/Use Case:** "{intent}"
- **Specific Requirements:** {specs}
 
### 2. Candidate Products
{products_json}
 
### 3. Your Task
For each product, calculate a **Match Score (0-100)** and provide a **Reason**.
- **100** = Perfect match (Meets all specs + fits use case perfectly).
- **80-90** = Great match (Meets critical specs, maybe overkill or slight trade-off).
- **50-70** = Acceptable (Meets minimums but might struggle with heavy workloads).
- **0-40** = Poor match (Missing critical features, wrong category, or too weak).
 
**CRITICAL RULES:**
1. If the product is an **Accessory** (Mouse, Bag, Dock, Adapter) but the user wants a **Computer/Laptop**, score it **0**.
2. If the user needs "Video Editing" or "CAD", prioritize Workstations/GPUs (NVIDIA/AMD).
3. If the user needs "Travel", prioritize low weight (< 2.0 kg).
4. Be strict. Do not recommend a weak laptop (Celeron/Pentium) for heavy tasks.
 
### 4. Output Format
Return a JSON object with a list "ranked_products". Each item must have:
- "product_id": (String) The ID provided in the input.
- "score": (Float) 0.0 to 1.0 (e.g. 95 becomes 0.95).
- "match_reason": (String) A short, persuasive reason why this product is good (or bad) for this specific user.
 
Example Output:
{{
  "ranked_products": [
    {{ "product_id": "HP_ZBook_15", "score": 0.95, "match_reason": "Perfect for CAD with its Quadro GPU and high RAM." }},
    {{ "product_id": "HP_Mouse_X1", "score": 0.0, "match_reason": "This is an accessory, not a computer." }}
  ]
}}
"""
 
class ComparatorAgent:
    def __init__(self):
        # Initialize LLM
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            LOG.error("GEMINI_API_KEY not found. Comparator Agent may fail.")
       
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1, # Low temperature for consistent, logical scoring
            google_api_key=api_key
        )
        self.parser = JsonOutputParser()
        self.prompt_template = ChatPromptTemplate.from_template(COMPARATOR_PROMPT)
 
    def rank_and_filter(self, products: List[Dict], requirements: Dict) -> List[Dict]:
        """
        Sends products + requirements to LLM for intelligent scoring.
        Returns top 5 products with 'score' and 'match_reason' fields added.
        """
        if not products:
            return []
 
        # 1. Prepare Data for Prompt (Minimize tokens by sending only relevant fields)
        clean_products = []
        for p in products:
            # Use product_name as ID if product_id is missing
            p_id = str(p.get("product_name") or "unknown")
           
            clean_products.append({
                "product_id": p_id,
                "name": p.get("product_name"),
                "category": p.get("category"),
                "specs": {
                    "cpu": p.get("spec_processor") or p.get("spec_CPU"),
                    "ram": p.get("spec_ram") or p.get("spec_RAM"),
                    "gpu": p.get("spec_gpu") or p.get("spec_Graphics"),
                    "storage": p.get("spec_storage") or p.get("spec_Hard_drive"),
                    "weight": p.get("spec_weight")
                }
            })
       
        # 2. Build Chain & Invoke
        chain = self.prompt_template | self.llm | self.parser
       
        try:
            print("   🧠 Comparator: Asking LLM to rank products...")
            response = chain.invoke({
                "category": requirements.get("product_category", "General"),
                "intent": requirements.get("user_intent", "General usage"),
                "specs": json.dumps(requirements.get("specific_requirements", {})),
                "products_json": json.dumps(clean_products, indent=2)
            })
           
            # 3. Map LLM Scores back to Original Products
            # Create a lookup dict for O(1) access
            ranked_map = {item["product_id"]: item for item in response.get("ranked_products", [])}
           
            scored_products = []
            for p in products:
                # Match using the same ID logic as above
                p_id = str(p.get("product_name") or "unknown")
               
                if p_id in ranked_map:
                    match_data = ranked_map[p_id]
                    p["score"] = float(match_data.get("score", 0.0))
                    p["match_reason"] = match_data.get("match_reason", "Evaluated by AI.")
                   
                    # Filter out poor matches (Accessory penalty logic handling)
                    if p["score"] > 0.1:
                        scored_products.append(p)
                else:
                    # Fallback if LLM missed one (rare)
                    p["score"] = 0.0
                    p["match_reason"] = "Not ranked by AI."
 
            # 4. Sort by Score (Highest first)
            scored_products.sort(key=lambda x: x["score"], reverse=True)
           
            # Return Top 5
            return scored_products[:5]
 
        except Exception as e:
            LOG.error(f"❌ LLM Scoring Failed: {e}")
            print(f"❌ LLM Scoring Failed: {e}")
            return []
 
    def build_comparison_matrix(self, ranked_products: List[Dict]) -> Dict[str, Any]:
        """
        Formats data exactly as the Deck Agent expects it.
        """
        matrix = {
            "comparison_scores": {},
            "recommended_products": []
        }
       
        for p in ranked_products:
            # Use product_name as key to ensure consistency
            p_id = str(p.get("product_name") or "Unknown")
           
            matrix["comparison_scores"][p_id] = p["score"]
           
            matrix["recommended_products"].append({
                "product_id": p_id,
                "name": p.get("product_name"),
                # Include reason for Pitch Agent
                "reason": p.get("match_reason", ""),
                # Map extracted specs to standardized keys expected by Deck Agent
                "specs": {
                    "cpu": p.get("spec_processor") or p.get("spec_CPU") or "N/A",
                    "ram": p.get("spec_ram") or p.get("spec_RAM") or "N/A",
                    "storage": p.get("spec_storage") or p.get("spec_Hard_drive") or "N/A",
                    "gpu": p.get("spec_gpu") or p.get("spec_Graphics") or "N/A",
                    "weight": p.get("spec_weight") or "N/A",
                }
            })
           
        return matrix
 
# -------------------------------------------------------------
# LangGraph Node Wrapper (Preserves exact interface)
# -------------------------------------------------------------
def comparator_node(state: AgentState) -> dict:
    print("--- 3. COMPARATOR NODE: LLM-Based Ranking ---")
   
    retrieved = state.get("retrieved_products", [])
    requirements = state.get("requirements", {})
   
    if not retrieved:
        print("⚠️ No products to rank.")
        return {"ranked_products": [], "comparison_matrix": {}}
 
    agent = ComparatorAgent()
   
    # 1. Rank (LLM)
    ranked = agent.rank_and_filter(retrieved, requirements)
   
    # 2. Matrix (Format)
    matrix_data = agent.build_comparison_matrix(ranked)
   
    print(f"📊 Ranked Top {len(ranked)} Products:")
    for p in ranked:
        print(f"   - {p.get('product_name')} | Score: {p['score']} | Reason: {p.get('match_reason')[:60]}...")
   
    return {
        "ranked_products": ranked,
        "comparison_matrix": matrix_data
    }