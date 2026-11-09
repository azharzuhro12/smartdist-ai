"""
Document Indexer for SmartDist AI RAG Knowledge System.
Loads SOPs and policy documents, chunks them into semantic passages,
and indexes them with metadata into ChromaDB and hybrid vector stores.
"""

import os
import re
import json
import pickle
from typing import List, Dict, Any, Optional
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ChromaDB import guarded for resilience
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None
    CHROMA_AVAILABLE = False


DOCUMENTS_DIR = Path(__file__).resolve().parent / "documents"
STORAGE_DIR = Path(__file__).resolve().parent / "chroma_storage"
INDEX_CACHE_FILE = STORAGE_DIR / "rag_index_cache.pkl"


class DocumentChunk:
    """Represents a chunked passage with rich metadata and citation info."""
    def __init__(
        self,
        chunk_id: str,
        doc_id: str,
        title: str,
        category: str,
        section: str,
        content: str,
    ):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.title = title
        self.category = category
        self.section = section
        self.content = content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "section": self.section,
            "content": self.content,
        }


class DocumentIndexer:
    """Chunks, indexes, and persists business SOP and policy documents."""

    def __init__(self, docs_dir: Optional[Path] = None, storage_dir: Optional[Path] = None):
        self.docs_dir = docs_dir or DOCUMENTS_DIR
        self.storage_dir = storage_dir or STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.chunks: List[DocumentChunk] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.chroma_client = None
        self.chroma_collection = None

    def _parse_metadata(self, text: str) -> Dict[str, str]:
        """Extracts standard metadata fields from markdown document header."""
        metadata = {
            "doc_id": "UNKNOWN",
            "title": "Untitled Policy",
            "category": "Operations",
            "section": "General",
        }

        # Match Document Title (# Title)
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1).strip()

        # Match metadata lines: **Document ID:** XYZ
        doc_id_match = re.search(r"\*\*Document ID:\*\*\s*([^\n\r]+)", text)
        if doc_id_match:
            metadata["doc_id"] = doc_id_match.group(1).strip()

        cat_match = re.search(r"\*\*Category:\*\*\s*([^\n\r]+)", text)
        if cat_match:
            metadata["category"] = cat_match.group(1).strip()

        sec_match = re.search(r"\*\*Section:\*\*\s*([^\n\r]+)", text)
        if sec_match:
            metadata["section"] = sec_match.group(1).strip()

        return metadata

    def chunk_document(self, file_path: Path) -> List[DocumentChunk]:
        """Reads a markdown file and splits it into semantic chunks by sections."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        metadata = self._parse_metadata(content)
        chunks: List[DocumentChunk] = []

        # Split on section headings (## or ###)
        sections = re.split(r"\n(?=##+\s+)", content)
        chunk_idx = 0

        for sec in sections:
            sec_text = sec.strip()
            if not sec_text:
                continue

            # Extract section heading
            heading_match = re.match(r"^(##+\s+[^\n]+)", sec_text)
            section_title = heading_match.group(1).strip("# \t") if heading_match else metadata["section"]

            # If section is longer than 600 characters, chunk by paragraphs
            paragraphs = sec_text.split("\n\n")
            current_chunk = ""

            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    continue

                if len(current_chunk) + len(p_clean) < 500:
                    current_chunk += "\n\n" + p_clean if current_chunk else p_clean
                else:
                    if current_chunk:
                        chunk_id = f"{metadata['doc_id']}_c{chunk_idx}"
                        chunks.append(DocumentChunk(
                            chunk_id=chunk_id,
                            doc_id=metadata["doc_id"],
                            title=metadata["title"],
                            category=metadata["category"],
                            section=section_title,
                            content=current_chunk,
                        ))
                        chunk_idx += 1
                    current_chunk = p_clean

            if current_chunk:
                chunk_id = f"{metadata['doc_id']}_c{chunk_idx}"
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=metadata["doc_id"],
                    title=metadata["title"],
                    category=metadata["category"],
                    section=section_title,
                    content=current_chunk,
                ))
                chunk_idx += 1

        return chunks

    def build_index(self) -> int:
        """Indexes all documents in documents directory."""
        all_chunks: List[DocumentChunk] = []

        if not self.docs_dir.exists():
            return 0

        for file_path in self.docs_dir.glob("*.md"):
            doc_chunks = self.chunk_document(file_path)
            all_chunks.extend(doc_chunks)

        self.chunks = all_chunks

        if not self.chunks:
            return 0

        # Build TF-IDF vector matrix
        corpus = [c.content for c in self.chunks]
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

        # Cache TF-IDF index
        with open(INDEX_CACHE_FILE, "wb") as f:
            pickle.dump({
                "chunks": [c.to_dict() for c in self.chunks],
                "vectorizer": self.vectorizer,
                "tfidf_matrix": self.tfidf_matrix,
            }, f)

        # Index in ChromaDB if available
        if CHROMA_AVAILABLE:
            try:
                self.chroma_client = chromadb.PersistentClient(path=str(self.storage_dir / "chroma"))
                self.chroma_collection = self.chroma_client.get_or_create_collection("smartdist_policies")

                # Upsert chunks
                ids = [c.chunk_id for c in self.chunks]
                docs = [c.content for c in self.chunks]
                metadatas = [
                    {
                        "doc_id": c.doc_id,
                        "title": c.title,
                        "category": c.category,
                        "section": c.section,
                    }
                    for c in self.chunks
                ]
                self.chroma_collection.upsert(ids=ids, documents=docs, metadatas=metadatas)
            except Exception:
                pass

        return len(self.chunks)

    def load_index(self) -> bool:
        """Loads cached index if available, otherwise builds it."""
        if INDEX_CACHE_FILE.exists():
            try:
                with open(INDEX_CACHE_FILE, "rb") as f:
                    data = pickle.load(f)
                    self.chunks = [
                        DocumentChunk(**c) for c in data["chunks"]
                    ]
                    self.vectorizer = data["vectorizer"]
                    self.tfidf_matrix = data["tfidf_matrix"]
                return True
            except Exception:
                pass

        return self.build_index() > 0

