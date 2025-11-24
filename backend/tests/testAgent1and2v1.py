import sys
import os
from pprint import pprint

# Ensure the project root is in the Python path
sys.path.append(os.getcwd())

try:
    from backend.app.agents.requirement_agent import requirement_node
    from backend.app.agents.retrieval_agent import retrieval_node
    from backend.app.graph.state import AgentState
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

def test_pipeline():
    # ---------------------------------------------------------------
    # 1. INITIALIZE STATE
    # ---------------------------------------------------------------
    query = "We need 10 laptops with 8GB RAM or more."
    
    print(f"\n🧪 TEST STARTING with Query: '{query}'\n")
    
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
    current_state.update(update_1)
    
    print("\n👉 Output from Agent 1 (Requirements):")
    pprint(current_state["requirements"])

    if not current_state["requirements"]:
        print("❌ Agent 1 failed. Stopping.")
        return

    # ---------------------------------------------------------------
    # 3. RUN AGENT 2 (Product Retrieval)
    # ---------------------------------------------------------------
    print("\n--- 🤖 Running Agent 2: Retrieval Node ---")
    update_2 = retrieval_node(current_state)
    current_state.update(update_2)
    
    products = current_state["retrieved_products"]

    # ---------------------------------------------------------------
    # 4. VERIFY RESULTS (Display ALL products)
    # ---------------------------------------------------------------
    if products:
        print(f"\n✅ SUCCESS! Retrieved {len(products)} products in total:\n")
        
        # Loop through ALL products (Removed [:3] limit)
        for i, p in enumerate(products):
            name = p.get("product_name", "Unknown")
            category = p.get("category", "N/A")
            ram = p.get("spec_ram", "N/A")
            score = p.get("vector_score", 0.0) # If available from new agent code
            
            print(f"{i+1}. {name} [{category}]")
            print(f"   - RAM: {ram}")
            print(f"   - Retrieval Score: {score:.4f}")
            print("-" * 40)
            
        if len(products) < 14:
            print(f"\n⚠️ Note: Vector DB found more candidates, but only {len(products)} had full SQL details.")
            print("   To see all 14+, run the DB ingestion scripts to sync SQL and Chroma.")
    else:
        print("\n⚠️ WARNING: Agent 2 ran but returned 0 products.")

if __name__ == "__main__":
    test_pipeline()