import re
import logging
from typing import List, Dict, Any
from backend.app.graph.state import AgentState

LOG = logging.getLogger(__name__)

class ComparatorAgent:
    def __init__(self):
        # Tiered ranking for processors to allow comparison (High > Low)
        self.cpu_tiers = {
            "atom": 1, "celeron": 2, "pentium": 3, 
            "i3": 4, "i5": 5, "i7": 6, "i9": 7, "xeon": 8,
            "a4": 2, "a6": 3, "a8": 4, "a10": 5, "fx": 6 # AMD examples
        }

    def _extract_storage_capacity(self, text: Any) -> float:
        """Converts storage strings (1TB, 500GB) into a unified GB float."""
        if not text: return 0.0
        s = str(text).lower().replace(" ", "")
        
        # Match number + unit
        match = re.search(r"(\d+(\.\d+)?)(tb|gb|mb)", s)
        if not match:
            return 0.0
        
        val = float(match.group(1))
        unit = match.group(3)
        
        if unit == "tb": return val * 1000
        if unit == "mb": return val / 1000
        return val # GB

    def _extract_ram(self, text: Any) -> float:
        """Extracts RAM specifically, handling 'MB' vs 'GB'."""
        if not text: return 0.0
        s = str(text).lower()
        
        # Often formatted like "4 GB 1600 MHz"
        match = re.search(r"(\d+)\s*(gb|mb)", s)
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            return val if unit == "gb" else val / 1000
        
        # Fallback to raw number if no unit found (assuming GB for RAM usually)
        match = re.search(r"(\d+)", s)
        return float(match.group(1)) if match else 0.0

    def _safe_str(self, value: Any) -> str:
        return str(value or "").lower()

    def _analyze_cpu_score(self, prod_cpu: str, req_desc: str) -> float:
        """Returns a score 0-10 based on CPU capability vs requirements."""
        prod_cpu = prod_cpu.lower()
        req_desc = req_desc.lower()
        
        prod_tier = 0
        for key, tier in self.cpu_tiers.items():
            if key in prod_cpu:
                prod_tier = max(prod_tier, tier)
        
        # If user explicitly asks for high performance/workstation
        if any(x in req_desc for x in ["workstation", "rendering", "heavy", "simulation", "cad"]):
            if prod_tier >= 6: return 10.0 # i7/Xeon
            if prod_tier >= 5: return 5.0  # i5
            return 0.0
            
        return 5.0 # Neutral score if no specific CPU asked

    def _calculate_score(self, product: Dict, reqs: Dict) -> float:
        score = 0.0
        max_possible = 0.0
        
        # Data Prep
        prod_name = self._safe_str(product.get("product_name"))
        prod_cat = self._safe_str(product.get("category"))
        prod_desc = self._safe_str(product.get("description"))
        req_cat = self._safe_str(reqs.get("product_category"))
        specifics = reqs.get("specific_requirements", {})
        
        # --- 1. Category Integrity (High Priority) ---
        # Heavy penalty for accessories if looking for main units
        is_accessory = any(x in prod_cat or x in prod_name for x in ["case", "mouse", "adapter", "keyboard", "dock", "monitor"])
        user_wants_accessory = any(x in req_cat for x in ["case", "mouse", "adapter", "keyboard", "dock", "monitor", "accessory"])
        
        if is_accessory and not user_wants_accessory:
            return -50.0  # Filter out noise immediately
            
        if req_cat in prod_cat or req_cat in prod_desc:
            score += 40
        max_possible += 40

        # --- 2. RAM (Dynamic Weight) ---
        req_ram = self._extract_ram(specifics.get("ram", "0"))
        if req_ram > 0:
            max_possible += 30
            prod_ram = self._extract_ram(product.get("spec_ram"))
            if prod_ram >= req_ram:
                score += 30
            elif prod_ram >= (req_ram / 2): # Partial credit
                score += 10

        # --- 3. GPU / Workstation Checks ---
        req_gpu = self._safe_str(specifics.get("gpu"))
        prod_gpu = self._safe_str(product.get("spec_gpu"))
        needs_gpu = "dedicated" in req_gpu or "design" in str(reqs).lower()
        
        if needs_gpu:
            max_possible += 25
            high_perf = ["nvidia", "amd", "radeon", "quadro", "firepro"]
            if any(x in prod_gpu for x in high_perf):
                score += 25
            elif "intel" in prod_gpu:
                score += 5 # Low score for integrated if dedicated needed

        # --- 4. Storage (New Logic) ---
        req_storage = specifics.get("storage")
        if req_storage:
            max_possible += 15
            prod_storage_str = self._safe_str(product.get("spec_storage") or product.get("spec_hard_drive"))
            
            # Check Type (SSD vs HDD)
            wants_ssd = "ssd" in str(req_storage).lower()
            has_ssd = "ssd" in prod_storage_str or "solid state" in prod_storage_str
            
            if wants_ssd and has_ssd:
                score += 15
            elif wants_ssd and not has_ssd:
                score += 0
            else:
                score += 10 # Default points if type not specified but storage exists

        # --- 5. Portability / Weight ---
        if "light" in str(reqs).lower() or "travel" in str(reqs).lower():
            max_possible += 20
            w = self._extract_number(product.get("spec_weight"))
            # Extract number logic from original class assumed here or improved above
            if 0.1 < w < 1.8: score += 20
            elif 1.8 <= w < 2.5: score += 10
            
        # Calculate Percentage
        if max_possible == 0: return 0
        
        final_score = (score / max_possible) * 100
        return final_score

    def _extract_number(self, text: Any) -> float:
        """Helper to extract the first meaningful number from a string."""
        if not text: return 0.0
        match = re.search(r"(\d+(\.\d+)?)", str(text))
        return float(match.group(1)) if match else 0.0

    def rank_and_filter(self, products: List[Dict], requirements: Dict) -> List[Dict]:
        scored_products = []
        
        for p in products:
            score = self._calculate_score(p, requirements)
            
            # Skip products with negative scores (Accessories mismatch)
            if score < 0: continue 
            
            # Normalize score 0.0 - 1.0
            normalized_score = min(round(score / 100.0, 2), 1.0)
            
            p["score"] = normalized_score
            p["match_reason"] = f"Match: {int(score)}%"
            scored_products.append(p)
            
        # Sort by score descending
        scored_products.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_products[:5]

    def build_comparison_matrix(self, ranked_products: List[Dict]) -> Dict[str, Any]:
        matrix = {
            "comparison_scores": {},
            "recommended_products": []
        }
        
        for p in ranked_products:
            # Fallback to index if no ID/Name
            p_id = str(p.get("product_id") or p.get("product_name") or "Unknown")
            
            matrix["comparison_scores"][p_id] = p["score"]
            matrix["recommended_products"].append({
                "product_id": p_id,
                "name": p.get("product_name"),
                "specs": {
                    "cpu": p.get("spec_processor", "N/A"), # Added CPU
                    "ram": p.get("spec_ram", "N/A"),
                    "storage": p.get("spec_storage") or p.get("spec_hard_drive", "N/A"), # Added Storage
                    "gpu": p.get("spec_gpu", "N/A"),
                    "weight": p.get("spec_weight", "N/A"),
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
        print(f"   - {p.get('product_name')} | Score: {p['score']}")
    
    return {
        "ranked_products": ranked,
        "comparison_matrix": matrix_data
    }