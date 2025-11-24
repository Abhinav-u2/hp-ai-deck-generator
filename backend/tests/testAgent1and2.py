import sys
import os
from pprint import pprint

# Ensure the project root is in the Python path
sys.path.append(os.getcwd())

# Import the node functions you created
try:
    from backend.app.agents.requirement_agent import requirement_node
    from backend.app.agents.retrieval_agent import retrieval_node
    from backend.app.graph.state import AgentState
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Please ensure you have created 'backend/app/graph/state.py' and added the node functions.")
    sys.exit(1)

def test_pipeline():
    # ---------------------------------------------------------------
    # 1. INITIALIZE STATE
    # ---------------------------------------------------------------
    query = "We need 10 laptops with 8GB RAM or more."
    
    print(f"\n🧪 TEST STARTING with Query: '{query}'\n")
    
    # Mock initial state (mimicking what LangGraph would provide)
    current_state: AgentState = {
        "user_query": query,
        "requirements": {},
        "retrieved_products": [],
        "ranked_products": [],
        "comparison_matrix": {},
        "sales_pitch": {},
        "deck_file_path": None
    }

    # ---------------------------------------------------------------
    # 2. RUN AGENT 1 (Requirement Understanding)
    # ---------------------------------------------------------------
    print("--- 🤖 Running Agent 1: Requirement Node ---")
    update_1 = requirement_node(current_state)
    
    # Merge the update into our state (LangGraph does this automatically)
    current_state.update(update_1)
    
    print("\n👉 Output from Agent 1 (Requirements):")
    pprint(current_state["requirements"])

    if not current_state["requirements"]:
        print("❌ Agent 1 failed to extract requirements. Stopping.")
        return

    # ---------------------------------------------------------------
    # 3. RUN AGENT 2 (Product Retrieval)
    # ---------------------------------------------------------------
    print("\n--- 🤖 Running Agent 2: Retrieval Node ---")
    update_2 = retrieval_node(current_state)
    
    # Merge the update
    current_state.update(update_2)
    
    products = current_state["retrieved_products"]
    print(f"\n👉 Output from Agent 2: Retrieved {len(products)} products.")

    # ---------------------------------------------------------------
    # 4. VERIFY RESULTS
    # ---------------------------------------------------------------
    if products:
        print("\n✅ SUCCESS! Here are the top 3 retrieved products:")
        for i, p in enumerate(products):
            name = p.get("product_name", "Unknown")
            category = p.get("category", "N/A")
            # Try to print some specs to verify SQL fetch worked
            ram = p.get("spec_ram", "N/A")
            gpu = p.get("spec_gpu", "N/A")
            print(f"   {i+1}. {name} [{category}]")
            print(f"      - RAM: {ram}")
            print(f"      - GPU: {gpu}")
    else:
        print("\n⚠️ WARNING: Agent 2 ran but found no products.")

if __name__ == "__main__":
    test_pipeline()