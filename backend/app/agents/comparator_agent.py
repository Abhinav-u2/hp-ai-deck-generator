import re
import logging
from typing import List, Dict, Any, Tuple
from backend.app.graph.state import AgentState

LOG = logging.getLogger(__name__)

class ComparatorAgent:
    def __init__(self):
        # 1. CPU Power Tiers (Higher = Better)
        self.cpu_tiers = {
            "atom": 1, "celeron": 2, "pentium": 3, 
            "i3": 4, "i5": 5, "i7": 6, "i9": 7, "xeon": 8,
            "a4": 2, "a6": 3, "a8": 4, "a10": 5, "fx": 6
        }
        
        # 2. Use Case Intensity Maps
        self.use_case_keywords = {
            "HIGH": ["video", "editing", "cad", "3d", "rendering", "simulation", "gaming", "design", "adobe", "4k", "heavy", "workstation"],
            "MEDIUM": ["coding", "programming", "multitasking", "office", "business", "presentation", "student", "college"],
            "LOW": ["browsing", "internet", "netflix", "entertainment", "movie", "email", "admin", "clerical", "home"]
        }

    # --- HELPER FUNCTIONS ---
    def _safe_str(self, value: Any) -> str:
        return str(value or "").lower()

    def _extract_number(self, text: Any) -> float:
        if not text: return 0.0
        match = re.search(r"(\d+(\.\d+)?)", str(text))
        return float(match.group(1)) if match else 0.0

    def _extract_ram(self, text: Any) -> float:
        if not text: return 0.0
        s = str(text).lower()
        match = re.search(r"(\d+)\s*(gb|mb)", s)
        if match:
            val = float(match.group(1))
            return val if match.group(2) == "gb" else val / 1000
        match = re.search(r"(\d+)", s)
        return float(match.group(1)) if match else 0.0

    def _get_cpu_tier(self, cpu_text: str) -> int:
        cpu_text = self._safe_str(cpu_text)
        tier = 0
        for key, val in self.cpu_tiers.items():
            if key in cpu_text:
                tier = max(tier, val)
        return tier

    def _determine_intensity(self, user_intent: str) -> str:
        """
        Classifies user intent into HIGH, MEDIUM, or LOW.
        (You could replace this with an LLM call if needed)
        """
        intent = user_intent.lower()
        
        # Check High keywords
        if any(k in intent for k in self.use_case_keywords["HIGH"]):
            return "HIGH"
        # Check Medium keywords
        if any(k in intent for k in self.use_case_keywords["MEDIUM"]):
            return "MEDIUM"
        
        # Default to Low/General
        return "LOW"

    # --- SCORING COMPONENTS ---

    def _calculate_explicit_score(self, product: Dict, specifics: Dict) -> float:
        """
        Score based ONLY on what the user explicitly asked for.
        Returns percentage (0.0 to 1.0).
        """
        score = 0.0
        max_points = 0.0
        
        # 1. RAM (if asked)
        req_ram = self._extract_ram(specifics.get("ram"))
        if req_ram > 0:
            max_points += 1
            prod_ram = self._extract_ram(product.get("spec_ram"))
            if prod_ram >= req_ram:
                score += 1
            elif prod_ram >= (req_ram / 2):
                score += 0.5

        # 2. Storage (if asked)
        req_storage = self._safe_str(specifics.get("storage"))
        if req_storage and req_storage not in ["nan", "none"]:
            max_points += 1
            prod_storage = self._safe_str(product.get("spec_storage") or product.get("spec_hard_drive"))
            
            # Simple check: SSD vs HDD preference
            wants_ssd = "ssd" in req_storage
            has_ssd = "ssd" in prod_storage or "solid state" in prod_storage
            
            if wants_ssd and has_ssd: score += 1
            elif wants_ssd and not has_ssd: score += 0.2
            else: score += 1 # If type not specified, any storage is fine

        # 3. GPU (if asked)
        req_gpu = self._safe_str(specifics.get("gpu"))
        if req_gpu and req_gpu not in ["nan", "none"]:
            max_points += 1
            prod_gpu = self._safe_str(product.get("spec_gpu"))
            # Check for dedicated graphics keywords
            is_dedicated = any(x in prod_gpu for x in ["nvidia", "amd", "radeon", "quadro", "firepro"])
            wants_dedicated = "dedicated" in req_gpu or "discrete" in req_gpu
            
            if wants_dedicated and is_dedicated: score += 1
            elif wants_dedicated and not is_dedicated: score += 0.3
            else: score += 1

        # 4. Weight (if asked)
        req_weight = self._safe_str(specifics.get("weight"))
        if "light" in req_weight:
            max_points += 1
            w = self._extract_number(product.get("spec_weight"))
            if 0.1 < w < 1.8: score += 1
            elif 1.8 <= w < 2.3: score += 0.5
            else: score += 0

        if max_points == 0:
            return 1.0 # If no specific specs asked, Explicit Score is perfect (neutral)
            
        return score / max_points

    def _calculate_implicit_score(self, product: Dict, intensity: str, specifics: Dict) -> float:
        """
        Score based on 'Hidden' specs required for the Use Case.
        Only checks specs that were NOT explicitly asked for.
        """
        score = 0.0
        max_points = 0.0
        
        prod_cpu_tier = self._get_cpu_tier(product.get("spec_processor"))
        prod_gpu = self._safe_str(product.get("spec_gpu"))
        has_dedicated_gpu = any(x in prod_gpu for x in ["nvidia", "amd", "radeon", "quadro"])

        # --- CPU Evaluation (Implicit) ---
        if "processor" not in specifics and "cpu" not in specifics:
            max_points += 1
            if intensity == "HIGH":
                # Needs i7 (Tier 6) or better
                if prod_cpu_tier >= 6: score += 1
                elif prod_cpu_tier >= 5: score += 0.5
                else: score += 0
            elif intensity == "MEDIUM":
                # Needs i5 (Tier 5) or better
                if prod_cpu_tier >= 5: score += 1
                elif prod_cpu_tier >= 4: score += 0.7
                else: score += 0.2
            else: # LOW
                # Anything is fine
                score += 1

        # --- GPU Evaluation (Implicit) ---
        if "gpu" not in specifics and "graphics" not in specifics:
            max_points += 1
            if intensity == "HIGH":
                # Needs Dedicated
                if has_dedicated_gpu: score += 1
                else: score += 0.2 # Integrated is bad for high intensity
  # Modified GPU Logic for MEDIUM Intensity
            elif intensity == "MEDIUM":
                if has_dedicated_gpu: 
                    score += 0.5  # Penalty: Workstations are heavy/battery hungry
                else: 
                    score += 1.0  # Reward: Integrated is better for office battery life
            else:
                score += 1

        if max_points == 0: return 1.0
        return score / max_points

    def calculate_composite_score(self, product: Dict, requirements: Dict) -> float:
        reqs_spec = requirements.get("specific_requirements", {})
        user_intent = str(requirements.get("user_intent") or "")
        
        # 1. Determine Use Case Intensity
        intensity = self._determine_intensity(user_intent)
        
        # 2. Calculate Component Scores (0.0 to 1.0)
        explicit_score = self._calculate_explicit_score(product, reqs_spec)
        implicit_score = self._calculate_implicit_score(product, intensity, reqs_spec)
        
        # 3. Apply Category Penalty (The "Accessory Filter")
        # If user wants a "Computer" but product is a "Mouse", score is -1
# 3. Apply Category Penalty (The "Accessory Filter")
        prod_cat = self._safe_str(product.get("category"))
        prod_name = self._safe_str(product.get("product_name")) # Check Name too!
        req_cat = self._safe_str(requirements.get("product_category"))
        
        # Expanded Blacklist
        accessory_keywords = [
            "case", "mouse", "adapter", "keyboard", "dock", "monitor", 
            "accessory", "drive", "headset", "carry", "bag", "cable"
        ]
        
        # Check if product is an accessory (by category OR name)
        is_accessory = (
            any(k in prod_cat for k in accessory_keywords) or 
            any(k in prod_name for k in accessory_keywords)
        )
        
        # Check if user explicitly WANTS an accessory
        wants_accessory = any(k in req_cat for k in accessory_keywords)
        
        if is_accessory and not wants_accessory:
            return -1.0 # Force filter out

        # 4. Weighted Composite Score
        # 60% Explicit + 40% Implicit
        final_score = (explicit_score * 60) + (implicit_score * 40)
        
        return round(final_score, 1)

    def rank_and_filter(self, products: List[Dict], requirements: Dict) -> List[Dict]:
        scored_products = []
        
        # Debugging: Print inferred intensity once
        intent = requirements.get("user_intent", "")
        intensity = self._determine_intensity(intent)
        print(f"   ℹ️  Inferred Use Case Intensity: {intensity}")

        for p in products:
            score = self.calculate_composite_score(p, requirements)
            
            if score < 0: continue # Filter out mismatches
            
            # Normalize to 0.0 - 1.0 for the UI
            normalized = min(score / 100.0, 1.0)
            
            p["score"] = normalized
            p["match_reason"] = f"Composite Score: {score}/100 ({intensity} Intensity)"
            scored_products.append(p)
            
        scored_products.sort(key=lambda x: x["score"], reverse=True)
        return scored_products[:5]

    def build_comparison_matrix(self, ranked_products: List[Dict]) -> Dict[str, Any]:
        matrix = {
            "comparison_scores": {},
            "recommended_products": []
        }
        for p in ranked_products:
            p_id = str(p.get("product_id") or p.get("product_name") or "Unknown")
            matrix["comparison_scores"][p_id] = p["score"]
            matrix["recommended_products"].append({
                "product_id": p_id,
                "name": p.get("product_name"),
                "specs": {
                    "cpu": p.get("spec_processor", "N/A"),
                    "ram": p.get("spec_ram", "N/A"),
                    "storage": p.get("spec_storage") or p.get("spec_hard_drive", "N/A"),
                    "gpu": p.get("spec_gpu", "N/A"),
                    "weight": p.get("spec_weight", "N/A"),
                }
            })
        return matrix

def comparator_node(state: AgentState) -> dict:
    print("--- 3. COMPARATOR NODE: Ranking & Scoring (Composite) ---")
    retrieved = state.get("retrieved_products", [])
    requirements = state.get("requirements", {})
    
    if not retrieved:
        return {"ranked_products": [], "comparison_matrix": {}}

    agent = ComparatorAgent()
    ranked = agent.rank_and_filter(retrieved, requirements)
    matrix_data = agent.build_comparison_matrix(ranked)
    
    print(f"📊 Ranked Top {len(ranked)} Products:")
    for p in ranked:
        print(f"   - {p.get('product_name')} | Score: {p['score']}")
    
    return {"ranked_products": ranked, "comparison_matrix": matrix_data}