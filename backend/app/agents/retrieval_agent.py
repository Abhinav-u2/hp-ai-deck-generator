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
    # FIXED: Flexible Category Match
    # -----------------------------------------------------
    def _is_category_match(self, product_category: str, requested_category: str) -> bool:
        """
        More flexible category matching so we do not drop valid notebook models.
        """
        if not requested_category or requested_category.lower() == "other":
            return True

        prod_cat = str(product_category).lower()
        req_cat = str(requested_category).lower()

        # Broad notebook/laptop umbrella (covers ProBook, EliteBook, ZBook etc.)
        if req_cat in ["notebook", "laptop"]:
            return any(keyword in prod_cat for keyword in [
                "notebook", "laptop", "probook", "elitebook", "zbook", "mobile workstation",
                "commercial", "business notebook", "notebook pc"
            ])

        # Default substring match
        return req_cat in prod_cat

    # -----------------------------------------------------
    # MAIN SEARCH FUNCTION (Broad Recall)
    # -----------------------------------------------------
    def search_products(self, query: str, category_filter: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Broad Hybrid Search:
        1. Vector Search (Top 50)
        2. Category Filter
        3. SQL Enrichment
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
            
            if self._is_category_match(prod_cat, category_filter):
                similarity = max(0, 1 - dist)
                filtered_results.append({
                    "product_name": prod_name,
                    "similarity": similarity
                })

        # 3) Sort by similarity
        filtered_results = sorted(filtered_results, key=lambda x: x["similarity"], reverse=True)

        # Keep top N results (typically 20)
        final_candidates = filtered_results[:limit]

        print(f"✅ Found {len(final_candidates)} candidates matching category '{category_filter}'.")

        # ---------------------------------------------------------------
        # 🔥 NEW BLOCK: Print ALL 20 vector results BEFORE SQL filtering
        # ---------------------------------------------------------------
        print("\n📋 Candidate List BEFORE SQL filtering (raw vector results):")
        for idx, item in enumerate(final_candidates, 1):
            print(f"  {idx}. {item['product_name']}  | Similarity: {item['similarity']:.3f}")
        print("-----------------------------------------------------------")

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
    print("--- 2. RETRIEVAL NODE: Broad Category Search ---")
    
    user_query = state.get("user_query", "")
    requirements = state.get("requirements", {})
    
    category = requirements.get("product_category", None)
    
    agent = RetrievalAgent()
    
    products = agent.search_products(user_query, category_filter=category, limit=20)
    
    print(f"📦 Retrieved {len(products)} products for Comparator Agent.")
    
    return {"retrieved_products": products}
