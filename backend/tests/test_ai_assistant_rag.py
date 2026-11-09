"""
Tests for RAG Knowledge System: indexing, chunking, and semantic retrieval.
"""

import pytest
from ai_assistant.rag.document_indexer import DocumentIndexer
from ai_assistant.rag.retriever import RAGRetriever


def test_rag_document_indexing():
    indexer = DocumentIndexer()
    count = indexer.build_index()
    assert count > 0
    assert len(indexer.chunks) > 0

    # Verify chunk structure
    first_chunk = indexer.chunks[0]
    assert first_chunk.chunk_id
    assert first_chunk.doc_id.startswith(("SOP-", "POL-"))
    assert first_chunk.title
    assert first_chunk.category
    assert first_chunk.section
    assert len(first_chunk.content) > 10


def test_rag_retriever_inventory_sop():
    retriever = RAGRetriever()
    results = retriever.retrieve("What is the formula for safety stock and reorder point?", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert top["doc_id"] == "SOP-INV-001"
    assert "citation" in top
    assert top["similarity_score"] > 0.05


def test_rag_retriever_procurement_policy():
    retriever = RAGRetriever()
    results = retriever.retrieve("What are the purchase order approval thresholds and spending limits?", top_k=2)
    assert len(results) > 0
    doc_ids = [r["doc_id"] for r in results]
    assert "POL-PROC-002" in doc_ids


def test_rag_retriever_anomaly_guidelines():
    retriever = RAGRetriever()
    results = retriever.retrieve("What are the steps to investigate a critical sales anomaly?", top_k=2)
    assert len(results) > 0
    doc_ids = [r["doc_id"] for r in results]
    assert "SOP-OPS-003" in doc_ids


def test_rag_citation_formatting():
    retriever = RAGRetriever()
    results = retriever.retrieve("Safety stock calculations", top_k=2)
    block = retriever.format_citations_block(results)
    assert "### Policy & SOP Citations:" in block
    assert "SOP-INV-001" in block

