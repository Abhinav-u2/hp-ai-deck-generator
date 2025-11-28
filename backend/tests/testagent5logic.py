import sys
import os
from pathlib import Path

# Fix path to import modules from backend
BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(BASE_DIR))

from backend.app.agents.comparator_agent import ComparatorAgent

# ==========================================
# 🛒 MOCK PRODUCTS (The "Inventory")
# ==========================================
products_db = [
    {
        "product_name": "HP ZBook 17 G2 (Powerhouse)",
        "category": "Workstation",
        "spec_processor": "Intel Core i7-4910MQ (Quad Core)",
        "spec_ram": "32 GB DDR3",
        "spec_gpu": "NVIDIA Quadro K5100M (8GB Dedicated)",
        "spec_storage": "1TB SSD",
        "spec_weight": "3.4 kg"
    },
    {
        "product_name": "HP ProBook 450 G2 (Office Standard)",
        "category": "Notebook",
        "spec_processor": "Intel Core i5-4210U",
        "spec_ram": "8 GB DDR3",
        "spec_gpu": "Intel HD Graphics 4400",
        "spec_storage": "500 GB HDD",
        "spec_weight": "2.1 kg"
    },
    {
        "product_name": "HP 250 G3 (Budget/Entry)",
        "category": "Notebook",
        "spec_processor": "Intel Celeron N2830",
        "spec_ram": "4 GB DDR3",
        "spec_gpu": "Integrated Graphics",
        "spec_storage": "500 GB HDD",
        "spec_weight": "2.2 kg"
    },
    {
        "product_name": "HP Wireless Mouse (Noise)",
        "category": "Accessory",
        "description": "Wireless mouse for travel.",
        "spec_ram": None,
        "spec_gpu": None
    }
]

# ==========================================
# 🧪 TEST SCENARIOS
# ==========================================
scenarios = [
    {
        "name": "SCENARIO 1: Heavy Video Editing",
        "reqs": {
            "product_category": "laptop",
            "user_intent": "I need a machine for 4k video editing and rendering.",
            "specific_requirements": {"ram": "16GB"}  # Explicit requirement
        }
    },
    {
        "name": "SCENARIO 2: Basic Office Work",
        "reqs": {
            "product_category": "laptop",
            "user_intent": "I just need something for browsing, email, and office work.",
            "specific_requirements": {} # No explicit specs
        }
    }
]

# ==========================================
# 🏃 RUNNER
# ==========================================
def run_tests():
    agent = ComparatorAgent()
    
    print(f"{'='*60}")
    print("🚀 TESTING COMPOSITE SCORE LOGIC")
    print(f"{'='*60}\n")

    for scen in scenarios:
        print(f"🔹 {scen['name']}")
        print(f"   Intent: '{scen['reqs']['user_intent']}'")
        if scen['reqs']['specific_requirements']:
            print(f"   Explicit Specs: {scen['reqs']['specific_requirements']}")
        
        # Run Ranking
        results = agent.rank_and_filter(products_db, scen['reqs'])
        
        print("\n   🏆 RANKING RESULTS:")
        for rank, p in enumerate(results, 1):
            print(f"      {rank}. {p['product_name']:<35} | {p['match_reason']}")
            
            # Diagnostic: Print the implicit tier score logic
            # (We can't see internal vars easily, but the score tells the story)
            
        print("-" * 50 + "\n")

if __name__ == "__main__":
    run_tests()