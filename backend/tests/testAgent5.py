import sys
import os
import json
from pprint import pprint

# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    # Import 4 agents
    from backend.app.agents.requirement_agent import requirement_node
    from backend.app.agents.retrieval_agent import retrieval_node
    from backend.app.agents.comparator_agent import comparator_node
    from backend.app.agents.pitch_agent import sales_pitch_node
    
    # Import final PPT generator agent
    from backend.app.agents.deck_agent import create_professional_ppt

    # State + LLM
    from backend.app.graph.state import AgentState
    from backend.app.llm.llm_client import llm

except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)


def print_section(title):
    print(f"\n{'='*65}")
    print(f" 🕵️  {title}")
    print(f"{'='*65}")


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
        "llm": llm
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

    print("\n🔍 Extracted Requirements:")
    pprint(reqs)

    # ---------------------------------------------------------------
    # 2. RETRIEVAL AGENT
    # ---------------------------------------------------------------
    print_section("STEP 2: AGENT 2 (Product Retrieval)")

    update2 = retrieval_node(state)
    state.update(update2)
    retrieved = state["retrieved_products"]

    print(f"\n📦 Total Products Retrieved: {len(retrieved)}")

    if not retrieved:
        print("❌ Agent 2 Failed (No products found).")
        return

    print("\n📋 Retrieved Products:")
    for p in retrieved[:5]:
        print(f"   - {p.get('product_name')}")

    # ---------------------------------------------------------------
    # 3. COMPARATOR AGENT
    # ---------------------------------------------------------------
    print_section("STEP 3: AGENT 3 (Comparator & Ranking)")

    update3 = comparator_node(state)
    state.update(update3)
    
    ranked = state["ranked_products"]

    print(f"\n🏆 Ranked Products ({len(ranked)}):")
    for i, p in enumerate(ranked[:5]):
        print(f"\n   Rank {i+1}: {p.get('product_name')}")
        print(f"   Score: {p.get('score')}")
        print(f"   Reason: {p.get('match_reason')}")

    # ---------------------------------------------------------------
    # 4. SALES PITCH AGENT
    # ---------------------------------------------------------------
    print_section("STEP 4: AGENT 4 (Sales Pitch Generation)")

    update4 = sales_pitch_node(state)
    state.update(update4)

    pitch = state["sales_pitch"]

    # print("\n📝 Sales Pitch:")
    # print(json.dumps(pitch, indent=2))

    if not pitch:
        print("❌ Sales Pitch Agent Failed")
        return

    # ---------------------------------------------------------------
    # 5. PPT GENERATOR AGENT
    # ---------------------------------------------------------------
    print_section("STEP 5: AGENT 5 (PPT Deck Generation)")

    # Use top 3 ranked products for the deck
    top_products = ranked[:5]

    deck_path = create_professional_ppt(
        sales_pitch=pitch,
        products=top_products,
        customer_query=query,
        output_file="HP_Proposal_Professional.pptx"
    )

    state["deck_file_path"] = deck_path

    print(f"\n📁 PPT Deck Generated Successfully: {deck_path}")

    # ---------------------------------------------------------------
    # FINAL VALIDATION
    # ---------------------------------------------------------------
    print_section("STEP 6: FINAL PIPELINE RESULT")

    if state["deck_file_path"]:
        print("🎉 FULL 5-AGENT PIPELINE SUCCESS!")
    else:
        print("❌ PPT Generation Failed")


if __name__ == "__main__":
    test_full_pipeline()
