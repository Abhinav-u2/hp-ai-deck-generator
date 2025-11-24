import sys
import os
import json
from pprint import pprint

# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    from backend.app.agents.requirement_agent import requirement_node
    from backend.app.agents.retrieval_agent import retrieval_node
    from backend.app.agents.comparator_agent import comparator_node
    from backend.app.graph.state import AgentState
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

def print_section(title):
    print(f"\n{'='*60}")
    print(f" 🕵️  {title}")
    print(f"{'='*60}")

def test_full_pipeline():
    # ---------------------------------------------------------------
    # 1. INITIALIZE
    # ---------------------------------------------------------------
    query = "We need 10 laptops for a design team, around ₹1 lakh each, lightweight, 8GB RAM, and good graphics."
    
    print_section("STEP 0: INITIALIZATION")
    print(f"📝 User Query: \"{query}\"")
    
    state: AgentState = {
        "user_query": query,
        "requirements": {},
        "retrieved_products": [],
        "ranked_products": [],
        "comparison_matrix": {},
        "sales_pitch": {},
        "deck_file_path": None
    }

    # ---------------------------------------------------------------
    # 2. AGENT 1: REQUIREMENT
    # ---------------------------------------------------------------
    print_section("STEP 1: AGENT 1 (Requirement Understanding)")
    
    # Execute Node
    update1 = requirement_node(state)
    state.update(update1)
    reqs = state["requirements"]

    if not reqs:
        print("❌ Agent 1 Failed to extract requirements.")
        return

    print("\n🔍 Extracted Structured Data:")
    print(f"   • Category: {reqs.get('product_category')}")
    print(f"   • Budget:   {reqs.get('budget_per_unit')}")
    print(f"   • Quantity: {reqs.get('quantity')}")
    print(f"   • Specs:    {json.dumps(reqs.get('specific_requirements'), indent=4)}")

    # ---------------------------------------------------------------
    # 3. AGENT 2: RETRIEVAL
    # ---------------------------------------------------------------
    print_section("STEP 2: AGENT 2 (Product Retrieval)")
    print(f"🔎 Searching for Category: '{reqs.get('product_category')}'")
    
    # Execute Node
    update2 = retrieval_node(state)
    state.update(update2)
    retrieved = state["retrieved_products"]
    
    print(f"\n📦 Total Candidates Retrieved: {len(retrieved)}")
    
    if not retrieved:
        print("❌ Agent 2 Failed (No products found). Check DB Sync.")
        return

    print("\n📋 Candidate List (Raw Retrieval):")
    for i, p in enumerate(retrieved):
        # Show limited details to keep it readable but verbose enough
        print(f"   {i+1}. {p.get('product_name')}")
        print(f"      ├─ RAM:    {p.get('spec_ram', 'N/A')}")
        print(f"      ├─ GPU:    {p.get('spec_gpu', 'N/A')}")
        print(f"      └─ Weight: {p.get('spec_weight', 'N/A')}")

    # ---------------------------------------------------------------
    # 4. AGENT 3: COMPARATOR
    # ---------------------------------------------------------------
    print_section("STEP 3: AGENT 3 (Comparator & Ranking)")
    
    # Execute Node
    update3 = comparator_node(state)
    state.update(update3)
    
    ranked = state["ranked_products"]
    matrix = state["comparison_matrix"]

    print(f"\n🏆 Final Ranked List (Top {len(ranked)}):")
    for i, p in enumerate(ranked):
        print(f"\n   🥇 Rank #{i+1}: {p.get('product_name')}")
        print(f"      ★ Match Score: {p.get('score')} / 1.0")
        print(f"      📝 Reason:     {p.get('match_reason', 'N/A')}")
        print(f"      🛠️  Specs:      RAM={p.get('spec_ram')} | GPU={p.get('spec_gpu')}")

    # ---------------------------------------------------------------
    # 5. FINAL OUTPUT VERIFICATION
    # ---------------------------------------------------------------
    print_section("STEP 4: FINAL HANDOFF (Data for Agent 4)")
    
    print("\n📊 Comparison Matrix JSON Structure:")
    print(json.dumps(matrix, indent=2))

    # Validation Check
    valid = True
    if not matrix.get("comparison_scores"):
        print("\n❌ Error: 'comparison_scores' is missing.")
        valid = False
    if not matrix.get("recommended_products"):
        print("\n❌ Error: 'recommended_products' is missing.")
        valid = False
        
    if valid:
        print("\n✅ SUCCESS: Data is perfectly structured for the Deck Generator Agent.")

if __name__ == "__main__":
    test_full_pipeline()