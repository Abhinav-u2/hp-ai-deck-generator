from typing import TypedDict, Optional, Dict, Any, List

class AgentState(TypedDict):
    """
    Represents the shared state between all agents in the LangGraph workflow.
    """
    # Input
    user_query: str
    
    # Agent 1: Requirements
    requirements: Optional[Dict[str, Any]]
    
    # Agent 2: Retrieval
    retrieved_products: List[Dict[str, Any]]
    
    # Agent 3: Comparator
    ranked_products: List[Dict[str, Any]]
    comparison_matrix: Dict[str, Any]
    
    # Agent 4: Sales Pitch
    sales_pitch: Dict[str, Any]
    
    # Agent 5: Deck Generation
    deck_file_path: Optional[str]