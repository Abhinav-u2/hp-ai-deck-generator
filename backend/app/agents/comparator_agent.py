import re
import logging
from typing import List, Dict, Any
from backend.app.graph.state import AgentState

LOG = logging.getLogger(__name__)

class ComparatorAgent:
    def __init__(self):
        pass

    def _extract_number(self, text: Any) -> float:
        """Helper to extract the first meaningful number from a string."""
        if not text:
            return 0.0
        text_str = str(text)
        # Matches ints or floats (e.g., '16', '1.5')
        match = re.search(r"(\d+(\.\d+)?)", text_str)
        return float(match.group(1)) if match else 0.0

    def _safe_str(self, value: Any) -> str:
        """Safely converts any value (including None) to a lowercase string."""
        return str(value or "").lower()

    def _calculate_score(self, product: Dict, reqs: Dict) -> float:
        """
        Calculates a match score (0 to 100) based on requirements.
        """
        score = 0.0
        
        # 1. RAM Check (+40 pts)
        req_ram = self._extract_number(reqs.get("specific_requirements", {}).get("ram", "0"))
        prod_ram_val = product.get("spec_ram")
        prod_ram = self._extract_number(prod_ram_val)
        
        # If product max RAM >= User RAM, match.
        if req_ram > 0 and prod_ram >= req_ram:
            score += 40
        elif req_ram == 0:
            score += 20 # Neutral if no RAM asked

        # 2. Category Match (+20 pts)
        req_cat = self._safe_str(reqs.get("product_category"))
        prod_cat = self._safe_str(product.get("category"))
        prod_desc = self._safe_str(product.get("description"))
        
        if req_cat in prod_cat or req_cat in prod_desc:
            score += 20
            
        # 3. GPU / Graphics Check (+30 pts)
        req_gpu = self._safe_str(reqs.get("specific_requirements", {}).get("gpu"))
        prod_gpu = self._safe_str(product.get("spec_gpu"))
        
        if "dedicated" in req_gpu or "good" in req_gpu or "design" in str(reqs).lower():
            # High Performance Indicators
            high_perf_keywords = [
                "nvidia", "amd", "radeon", "geforce", "quadro", "firepro", 
                "discrete", "graphics card", "3d"
            ]
            
            if any(x in prod_gpu for x in high_perf_keywords):
                score += 30
            elif "intel" in prod_gpu or "integrated" in prod_gpu:
                score -= 10 # Penalize integrated if dedicated explicitly asked
            else:
                # If "None" or unknown, give 0 extra points (lower than discrete)
                pass
        else:
            score += 10 # Neutral if GPU not critical

        # 4. Weight Check (+10 pts)
        if "light" in str(reqs).lower():
            w = self._extract_number(product.get("spec_weight"))
            # Under 2.0kg is generally considered light for 2014 standards
            if 0.1 < w < 2.0: 
                score += 10

        return score

    def rank_and_filter(self, products: List[Dict], requirements: Dict) -> List[Dict]:
        """
        Scores products, sorts them, and returns the top 5.
        """
        scored_products = []
        
        for p in products:
            score = self._calculate_score(p, requirements)
            
            # Normalize score 0.0 - 1.0
            normalized_score = min(round(score / 100.0, 2), 1.0)
            
            p["score"] = normalized_score
            p["match_reason"] = f"Match Score: {score}/100"
            
            scored_products.append(p)
            
        # Sort by score descending
        scored_products.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_products[:5]

    def build_comparison_matrix(self, ranked_products: List[Dict]) -> Dict[str, Any]:
        """
        Formats data for Agent 4.
        """
        matrix = {
            "comparison_scores": {},
            "recommended_products": []
        }
        
        for p in ranked_products:
            p_id = str(p.get("product_id") or p.get("product_name"))
            
            matrix["comparison_scores"][p_id] = p["score"]
            matrix["recommended_products"].append({
                "product_id": p_id,
                "name": p.get("product_name"),
                "specs": {
                    "ram": p.get("spec_ram"),
                    "gpu": p.get("spec_gpu"),
                    "weight": p.get("spec_weight"),
                    "storage": p.get("spec_storage", "N/A")
                }
            })
            
        return matrix

# -------------------------------------------------------------
# LangGraph Node Wrapper
# -------------------------------------------------------------
def comparator_node(state: AgentState) -> dict:
    print("--- 3. COMPARATOR NODE: Ranking & Scoring ---")
    
    retrieved = state.get("retrieved_products", [])
    requirements = state.get("requirements", {})
    
    if not retrieved:
        print("⚠️ No products to rank.")
        return {"ranked_products": [], "comparison_matrix": {}}

    agent = ComparatorAgent()
    
    # 1. Rank
    ranked = agent.rank_and_filter(retrieved, requirements)
    
    # 2. Matrix
    matrix_data = agent.build_comparison_matrix(ranked)
    
    print(f"📊 Ranked Top {len(ranked)} Products:")
    for p in ranked:
        # Print detailed GPU/Score info for verification
        print(f"   - {p['product_name']} | Score: {p['score']} | GPU: {p.get('spec_gpu')}")
    
    return {
        "ranked_products": ranked,
        "comparison_matrix": matrix_data
    }