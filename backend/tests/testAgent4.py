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
    from backend.app.agents.pitch_agent import sales_pitch_node
    from backend.app.graph.state import AgentState
    from backend.app.llm.llm_client import llm   # If you have your LLM wrapper here
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)


def print_section(title):
    print(f"\n{'='*60}")
    print(f" 🕵️  {title}")
    print(f"{'='*60}")


def test_full_pipeline():
    # ---------------------------------------------------------------
    # 0. INITIALIZATION
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
        "deck_file_path": None,
        "llm": llm  # Inject LLM here for SalesPitchAgent
    }

    # ---------------------------------------------------------------
    # 1. REQUIREMENT AGENT
    # ---------------------------------------------------------------
    print_section("STEP 1: AGENT 1 (Requirement Understanding)")

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
    # 2. RETRIEVAL AGENT
    # ---------------------------------------------------------------
    print_section("STEP 2: AGENT 2 (Product Retrieval)")
    print(f"🔎 Searching for Category: '{reqs.get('product_category')}'")

    update2 = retrieval_node(state)
    state.update(update2)
    retrieved = state["retrieved_products"]

    print(f"\n📦 Total Candidates Retrieved: {len(retrieved)}")

    if not retrieved:
        print("❌ Agent 2 Failed (No products found). Check DB Sync.")
        return

    print("\n📋 Candidate List (Raw Retrieval):")
    for i, p in enumerate(retrieved):
        print(f"   {i+1}. {p.get('product_name')}")
        print(f"      ├─ RAM:    {p.get('spec_ram', 'N/A')}")
        print(f"      ├─ GPU:    {p.get('spec_gpu', 'N/A')}")
        print(f"      └─ Weight: {p.get('spec_weight', 'N/A')}")

    # ---------------------------------------------------------------
    # 3. COMPARATOR AGENT
    # ---------------------------------------------------------------
    print_section("STEP 3: AGENT 3 (Comparator & Ranking)")

    update3 = comparator_node(state)
    state.update(update3)
    
    ranked = state["ranked_products"]
    matrix = state["comparison_matrix"]

    print(f"\n🏆 Final Ranked List (Top {len(ranked)}):")
    for i, p in enumerate(ranked):
        print(f"\n   🥇 Rank #{i+1}: {p.get('product_name')}")
        print(f"      ★ Match Score: {p.get('score')} / 1.0")
        print(f"      📝 Reason:     {p.get('match_reason')}")
        print(f"      🛠️  Specs:      RAM={p.get('spec_ram')} | GPU={p.get('spec_gpu')}")

    # ---------------------------------------------------------------
    # 4. SALES PITCH AGENT
    # ---------------------------------------------------------------
    print_section("STEP 4: AGENT 4 (Sales Pitch Generation)")

    update4 = sales_pitch_node(state)
    state.update(update4)

    pitch = state["sales_pitch"]

    print("\n📝 Sales Pitch Output:")
    print(json.dumps(pitch, indent=2))

    # ---------------------------------------------------------------
    # 5. FINAL HANDOFF VALIDATION
    # ---------------------------------------------------------------
    print_section("STEP 5: FINAL HANDOFF CHECK")

    if not pitch:
        print("❌ Sales pitch missing")
    else:
        print("✅ Sales pitch generated successfully")

    print("\n🎉 Full 4-Agent Pipeline Test Completed!")


if __name__ == "__main__":
    test_full_pipeline()
