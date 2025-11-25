import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any

from qdrant_client import QdrantClient, models
from fastembed.sparse.sparse_text_embedding import SparseTextEmbedding
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]
QDRANT_PATH = BASE_DIR / "backend" / "app" / "database" / "qdrant"
SQL_DB_PATH = BASE_DIR / "backend" / "app" / "database" / "products.db"

# Load API key
from dotenv import load_dotenv
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------
# DENSE EMBEDDING MODEL (Gemini 004)
# ---------------------------------------------------------
dense_embedder = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=GEMINI_KEY
)

# ---------------------------------------------------------
# SPARSE MODEL (SPLADE)
# ---------------------------------------------------------
sparse_embedder = SparseTextEmbedding(model_name="qdrant/bm25")


# =========================================================
#                    RETRIEVAL AGENT
# =========================================================
class RetrievalAgent:
    def __init__(self):
        print("🔌 Initializing Hybrid Retrieval Agent...")
        self.qdrant = QdrantClient(path=str(QDRANT_PATH))
        self.db_path = str(SQL_DB_PATH)

    # ---------------------------------------------------------
    # Convert SPLADE dict → indices/values
    # ---------------------------------------------------------
    def _convert_sparse(self, sparse_dict: dict):
        if not sparse_dict:
            return [], []
        return list(sparse_dict.keys()), list(sparse_dict.values())

    # ---------------------------------------------------------
    # Category Logic
    # ---------------------------------------------------------
    def _is_category_match(self, product_category: str, requested_category: str) -> bool:
        if not requested_category or requested_category.lower() == "other":
            return True

        prod_cat = str(product_category).lower()
        req_cat = str(requested_category).lower()

        if req_cat in ["notebook", "laptop"]:
            return any(k in prod_cat for k in [
                "notebook", "laptop", "probook",
                "elitebook", "zbook",
                "mobile workstation", "commercial"
            ])

        return req_cat in prod_cat

    # ---------------------------------------------------------
    # HYBRID SEARCH (Separate queries + RRF fusion)
    # ---------------------------------------------------------
    def search_products(self, query: str, category_filter: str = None, limit: int = 20):

        print(f"\n🔍 Hybrid Search for: '{query}' (Category={category_filter})")

        try:
            # Dense vector
            print("  📊 Generating dense embedding...")
            dense_vec = dense_embedder.embed_query(query)

            # Sparse vector
            print("  📊 Generating sparse embedding...")
            splade = next(sparse_embedder.embed(query))
            sparse_dict = splade.as_dict()
            sparse_indices, sparse_values = self._convert_sparse(sparse_dict)

            # ---------------------------------------------------------
            # OPTION 1: Try new API with FusionQuery
            # ---------------------------------------------------------
            try:
                print("  🔄 Attempting FusionQuery API...")
                search_result = self.qdrant.query_points(
                    collection_name="product_specs",
                    prefetch=[
                        models.Prefetch(
                            query=dense_vec,
                            using="dense",
                            limit=50
                        ),
                        models.Prefetch(
                            query=models.SparseVector(
                                indices=sparse_indices,
                                values=sparse_values
                            ),
                            using="sparse",
                            limit=50
                        )
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=limit * 2,
                    with_payload=True,
                    with_vectors=False
                )
                
                if search_result and hasattr(search_result, 'points') and search_result.points:
                    print("  ✅ FusionQuery succeeded!")
                    results = self._process_results(search_result.points, category_filter, limit)
                    return self._join_sql(results)
                    
            except (AttributeError, TypeError) as e:
                print(f"  ⚠️ FusionQuery failed ({e}), falling back to separate queries...")

            # ---------------------------------------------------------
            # OPTION 2: Fallback - Separate searches + manual RRF
            # ---------------------------------------------------------
            print("  🔄 Running separate dense + sparse searches...")
            
            # Dense search
            dense_results = self.qdrant.search(
                collection_name="product_specs",
                query_vector=models.NamedVector(
                    name="dense",
                    vector=dense_vec
                ),
                limit=50,
                with_payload=True
            )

            # Sparse search
            sparse_results = self.qdrant.search(
                collection_name="product_specs",
                query_vector=models.NamedVector(
                    name="sparse",
                    vector=models.SparseVector(
                        indices=sparse_indices,
                        values=sparse_values
                    )
                ),
                limit=50,
                with_payload=True
            )

            print(f"  ✅ Dense: {len(dense_results)} results, Sparse: {len(sparse_results)} results")

            # Manual RRF fusion
            fused_results = self._reciprocal_rank_fusion(dense_results, sparse_results, k=60)
            
            # Process and filter
            processed = self._process_results(fused_results, category_filter, limit)
            return self._join_sql(processed)

        except Exception as e:
            print(f"❌ Error in search_products: {e}")
            import traceback
            traceback.print_exc()
            return []

    # ---------------------------------------------------------
    # Reciprocal Rank Fusion (Manual Implementation)
    # ---------------------------------------------------------
    def _reciprocal_rank_fusion(self, dense_results, sparse_results, k=60):
        """
        Combine dense and sparse results using RRF algorithm
        RRF score = sum(1 / (k + rank))
        """
        scores = {}
        
        # Score dense results
        for rank, result in enumerate(dense_results, start=1):
            product_name = result.payload.get("product_name")
            if product_name:
                if product_name not in scores:
                    scores[product_name] = {
                        "payload": result.payload,
                        "score": 0.0
                    }
                scores[product_name]["score"] += 1.0 / (k + rank)
        
        # Score sparse results
        for rank, result in enumerate(sparse_results, start=1):
            product_name = result.payload.get("product_name")
            if product_name:
                if product_name not in scores:
                    scores[product_name] = {
                        "payload": result.payload,
                        "score": 0.0
                    }
                scores[product_name]["score"] += 1.0 / (k + rank)
        
        # Sort by RRF score
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )
        
        # Convert back to result format
        class FusedResult:
            def __init__(self, payload, score):
                self.payload = payload
                self.score = score
        
        return [
            FusedResult(item[1]["payload"], item[1]["score"])
            for item in sorted_results
        ]

    # ---------------------------------------------------------
    # Process and filter results
    # ---------------------------------------------------------
    def _process_results(self, results, category_filter, limit):
        """Process search results with category filtering"""
        final = []
        for pt in results:
            payload = pt.payload if hasattr(pt, 'payload') else {}
            name = payload.get("product_name")
            cat = payload.get("category", "")
            score = pt.score if hasattr(pt, 'score') else 0.0

            if name and self._is_category_match(cat, category_filter):
                final.append({
                    "product_name": name,
                    "similarity": score
                })

        final = sorted(final, key=lambda x: x["similarity"], reverse=True)
        candidates = final[:limit]

        print(f"✅ Hybrid retrieved {len(candidates)} matching products.\n")

        print("📋 Candidate List BEFORE SQL join:")
        for i, c in enumerate(candidates, 1):
            print(f"  {i}. {c['product_name']} | Score={c['similarity']:.3f}")
        print("--------------------------------------------------------------")

        return candidates

    # ---------------------------------------------------------
    # SQL JOIN
    # ---------------------------------------------------------
    def _join_sql(self, candidates):
        """Join vector results with SQL database"""
        results = []
        
        if not candidates:
            return results
            
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            for item in candidates:
                try:
                    cur.execute(
                        "SELECT * FROM products WHERE product_name = ?",
                        (item["product_name"],)
                    )
                    row = cur.fetchone()

                    if row:
                        p = dict(row)
                        p["vector_score"] = item["similarity"]
                        results.append(p)
                except sqlite3.Error as e:
                    print(f"⚠️ SQL error for {item['product_name']}: {e}")
                    continue

        print(f"✅ SQL JOIN complete: {len(results)} products with full specs.\n")
        return results


# =========================================================
# LangGraph Node Wrapper
# =========================================================
from backend.app.graph.state import AgentState

def retrieval_node(state: AgentState) -> dict:
    """
    LangGraph node wrapper for retrieval agent
    """
    print("--- 2. HYBRID RETRIEVAL NODE ---")

    user_query = state.get("user_query", "")
    requirements = state.get("requirements", {})
    category = requirements.get("product_category", None)

    if not user_query:
        print("⚠️ No user query found in state!")
        return {"retrieved_products": []}

    agent = RetrievalAgent()
    products = agent.search_products(user_query, category_filter=category, limit=20)

    print(f"📦 Retrieved {len(products)} products for Comparator Agent.")
    
    if products:
        print("\n📋 Sample Retrieved Products:")
        for i, p in enumerate(products[:3], 1):
            print(f"  {i}. {p.get('product_name', 'Unknown')} - Score: {p.get('vector_score', 0):.3f}")

    return {"retrieved_products": products}