"""
RAG Retriever for SmartDist AI.
Performs semantic similarity search over indexed SOPs and policy documents,
returning relevant passages with structured source citations.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from ai_assistant.rag.document_indexer import DocumentIndexer, CHROMA_AVAILABLE


class RAGRetriever:
    """Retrieves relevant policy passages with structured citations."""

    def __init__(self, indexer: Optional[DocumentIndexer] = None):
        self.indexer = indexer or DocumentIndexer()
        if not self.indexer.load_index():
            self.indexer.build_index()

    def retrieve(self, query: str, top_k: int = 3, min_similarity: float = 0.05) -> List[Dict[str, Any]]:
        """
        Retrieves top_k most relevant document chunks for the query.
        Falls back to ChromaDB if available or TF-IDF cosine similarity.
        """
        if not query or not query.strip():
            return []

        # Try ChromaDB if available and populated
        if CHROMA_AVAILABLE and self.indexer.chroma_collection:
            try:
                results = self.indexer.chroma_collection.query(
                    query_texts=[query],
                    n_results=top_k,
                )
                if results and results.get("documents") and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                    distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

                    formatted = []
                    for doc_text, meta, dist in zip(docs, metas, distances):
                        # Convert L2 distance or cosine distance to similarity score
                        sim = max(0.0, 1.0 - (dist if dist else 0.0))
                        formatted.append({
                            "doc_id": meta.get("doc_id", "DOC"),
                            "title": meta.get("title", "Policy"),
                            "category": meta.get("category", "General"),
                            "section": meta.get("section", "Policy"),
                            "content": doc_text,
                            "similarity_score": round(sim, 3),
                            "citation": f"[{meta.get('doc_id')}] {meta.get('title')} — Section: {meta.get('section')}",
                        })
                    return formatted
            except Exception:
                pass

        # TF-IDF cosine similarity retrieval
        if not self.indexer.vectorizer or self.indexer.tfidf_matrix is None or not self.indexer.chunks:
            return []

        query_vec = self.indexer.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.indexer.tfidf_matrix).flatten()

        # Get top indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score >= min_similarity:
                chunk = self.indexer.chunks[idx]
                results.append({
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "category": chunk.category,
                    "section": chunk.section,
                    "content": chunk.content,
                    "similarity_score": round(score, 3),
                    "citation": f"[{chunk.doc_id}] {chunk.title} — Section: {chunk.section}",
                })

        return results

    def format_citations_block(self, results: List[Dict[str, Any]]) -> str:
        """Formats citations into a clean Markdown block."""
        if not results:
            return ""

        lines = ["\n### Policy & SOP Citations:"]
        for idx, r in enumerate(results, start=1):
            lines.append(f"{idx}. **{r['citation']}** (Relevance: {r['similarity_score']:.0%})")
            lines.append(f"   > *\"{r['content'][:200]}...\"*")

        return "\n".join(lines)

