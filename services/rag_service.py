"""services/rag_service.py - FAISS-based RAG for semantic document search"""
import json
import logging
import os
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class RAGService:
    """
    FAISS vector store for semantic retrieval of document chunks.
    Each document gets its own index stored on disk.
    """

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self, doc_id: int):
        return self.index_dir / f"doc_{doc_id}.faiss"

    def _chunks_path(self, doc_id: int):
        return self.index_dir / f"doc_{doc_id}_chunks.pkl"

    # ------------------------------------------------------------------ #
    def build_index(self, doc_id: int, chunks: list[dict], embeddings: list[list[float]]) -> bool:
        """
        Build and persist a FAISS index for a document.

        Args:
            doc_id: document primary key
            chunks: list of {"chunk_id", "page", "text"}
            embeddings: parallel list of embedding vectors
        """
        try:
            import faiss  # noqa: F401 - imported here to give a clear error
            dim = len(embeddings[0])
            index = faiss.IndexFlatIP(dim)  # inner-product (cosine after normalization)
            vectors = np.array(embeddings, dtype="float32")
            # L2-normalize for cosine similarity
            faiss.normalize_L2(vectors)
            index.add(vectors)

            # Save index
            faiss.write_index(index, str(self._index_path(doc_id)))

            # Save chunk metadata
            with open(self._chunks_path(doc_id), "wb") as f:
                pickle.dump(chunks, f)

            logger.info("Built FAISS index for doc %d with %d chunks", doc_id, len(chunks))
            return True
        except ImportError:
            logger.error("faiss-cpu not installed. Run: pip install faiss-cpu")
            return False
        except Exception as e:
            logger.error("Failed to build FAISS index: %s", e)
            return False

    def search(self, doc_id: int, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """
        Retrieve top-k relevant chunks for a query embedding.

        Returns:
            list of {"page": int, "text": str, "score": float, "chunk_id": str}
        """
        idx_path = self._index_path(doc_id)
        chunks_path = self._chunks_path(doc_id)

        if not idx_path.exists() or not chunks_path.exists():
            logger.warning("No FAISS index found for doc %d", doc_id)
            return []

        try:
            import faiss
            index = faiss.read_index(str(idx_path))
            with open(chunks_path, "rb") as f:
                chunks = pickle.load(f)

            query_vec = np.array([query_embedding], dtype="float32")
            faiss.normalize_L2(query_vec)

            scores, indices = index.search(query_vec, min(top_k, index.ntotal))
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(chunks):
                    chunk = chunks[idx].copy()
                    chunk["score"] = float(score)
                    results.append(chunk)
            return results
        except Exception as e:
            logger.error("FAISS search failed: %s", e)
            return []

    def delete_index(self, doc_id: int):
        """Remove stored index files for a document."""
        for p in [self._index_path(doc_id), self._chunks_path(doc_id)]:
            if p.exists():
                p.unlink()

    def index_exists(self, doc_id: int) -> bool:
        return self._index_path(doc_id).exists()
