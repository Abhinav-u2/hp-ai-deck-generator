import sqlite3
import os
import re
from typing import List, Dict, Any
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
from pathlib import Path

# -----------------------------------------
# DYNAMIC PATHS
# -----------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]
CHROMA_PATH = BASE_DIR / "backend" / "app" / "database" / "chroma"
SQL_DB_PATH = BASE_DIR / "backend" / "app" / "database" / "products.db"

class RetrievalAgent:
    def __init__(self):
        """
        Initializes connections to ChromaDB and SQLite.
        """
        print("🔌 Initializing Retrieval Agent resources...")
        
        # 1. Connect to Vector DB (Chroma)
        self.chroma_client = PersistentClient(path=str(CHROMA_PATH))
        self.collection = self.chroma_client.get_or_create_collection(name="product_specs")
        
        # 2. Load Embedding Model
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        
        # 3. Store SQL Path
        self.db_path = str(SQL_DB_PATH)

    # -----------------------------------------------------
    # Helper: Basic Category Match
    # -----------------------------------------------------
    def _is_category_match(self, product_category: str, requested_category: str) -> bool:
        """
        Checks if product category matches request (e.g. 'Notebook' == 'Laptop').
        Returns True if match or if no specific category requested.
        """
        if not requested_category or requested_category == "Other":
            return True
            
        prod_cat = str(product_category).lower()
        req_cat = requested_category.lower()
        
        # Aliases
        if req_cat in ["notebook", "laptop"]:
            return prod_cat in ["notebook", "laptop"]
        
        # Substring match (e.g. "Workstation" matches "Mobile Workstation")
        return req_cat in prod_cat

    # -----------------------------------------------------
    # MAIN SEARCH FUNCTION (Broad Recall)
    # -----------------------------------------------------
    def search_products(self, query: str, category_filter: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Broad Hybrid Search:
        1. Vector Search (Get top 50 candidates)
        2. Filter by Category ONLY (Remove Accessories if user wants Laptop)
        3. Return raw list to Comparator Agent
        """
        print(f"🔍 Broad Search for: '{query}' | Category: {category_filter}")
        
        # 1) Dense embedding search - Fetch MANY candidates (Top 50)
        query_emb = self.embedder.encode(query).tolist()
        
        try:
            results = self.collection.query(
                query_embeddings=[query_emb],
                n_results=50, 
                include=["metadatas", "distances"]
            )
        except Exception as e:
            print(f"⚠️ ChromaDB Error: {e}")
            return []

        if not results['metadatas'] or not results['metadatas'][0]:
            print("⚠️ No products found in Vector DB.")
            return []

        metas = results["metadatas"][0]
        scores = results["distances"][0]

        filtered_results = []

        # 2) Category Filter Only
        for meta, dist in zip(metas, scores):
            prod_name = meta["product_name"]
            prod_cat = meta.get("category", "N/A")
            
            # Apply Category Filter
            if self._is_category_match(prod_cat, category_filter):
                # Convert distance to similarity score for sorting
                similarity = max(0, 1 - dist)
                
                filtered_results.append({
                    "product_name": prod_name,
                    "similarity": similarity
                })

        # 3) Sort by vector similarity
        filtered_results = sorted(filtered_results, key=lambda x: x["similarity"], reverse=True)
        
        # Keep top N (default 20 to give Comparator enough options)
        final_candidates = filtered_results[:limit]
        print(f"✅ Found {len(final_candidates)} candidates matching category '{category_filter}'.")

        # 4) Fetch Full SQL Details
        final_products = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                for item in final_candidates:
                    name = item["product_name"]
                    cursor.execute("SELECT * FROM products WHERE product_name = ?", (name,))
                    row = cursor.fetchone()
                    
                    if row:
                        p_dict = dict(row)
                        # Pass similarity to next agent (optional aid)
                        p_dict["vector_score"] = item["similarity"]
                        final_products.append(p_dict)
                        
        except Exception as e:
            print(f"❌ Database Error: {e}")
            return []

        return final_products

# -------------------------------------------------------------
# LangGraph Node Wrapper
# -------------------------------------------------------------
from backend.app.graph.state import AgentState

def retrieval_node(state: AgentState) -> dict:
    """
    LangGraph Node:
    1. Reads 'user_query' and 'requirements'.
    2. Performs BROAD search (high recall).
    3. Updates 'retrieved_products' with a larger list.
    """
    print("--- 2. RETRIEVAL NODE: Broad Category Search ---")
    
    user_query = state.get("user_query", "")
    requirements = state.get("requirements", {})
    
    # Extract category
    category = requirements.get("product_category", None)
    
    agent = RetrievalAgent()
    
    # Fetch up to 20 products to ensure Comparator has enough to rank
    products = agent.search_products(user_query, category_filter=category, limit=20)
    
    print(f"📦 Retrieved {len(products)} products for Comparator Agent.")
    
    return {"retrieved_products": products}