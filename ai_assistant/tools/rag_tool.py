"""
RAG Policy Knowledge Tool for SmartDist AI Assistant.
Queries indexed business SOPs and procurement policies, returning citations.
"""

from typing import Dict, Any, List, Optional
from ai_assistant.rag.retriever import RAGRetriever


class RAGPolicyTool:
    """Tool for retrieving business rules, SOPs, and governance policies."""

    name = "rag_policy_lookup"
    description = "Searches SOPs, procurement policies, replenishment formulas, and store operation rules with citations."

    def __init__(self, retriever: Optional[RAGRetriever] = None):
        self.retriever = retriever or RAGRetriever()

    def query_policy(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        """Queries policies and formats citation block."""
        results = self.retriever.retrieve(question, top_k=top_k)
        citation_block = self.retriever.format_citations_block(results)
        return {
            "query": question,
            "passages": results,
            "citation_block": citation_block,
            "top_citation": results[0]["citation"] if results else None,
        }

