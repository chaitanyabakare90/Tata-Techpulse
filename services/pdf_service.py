"""services/pdf_service.py - PyMuPDF-based PDF extraction"""
import json
import re
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # fallback


class PDFService:
    """Handles PDF text extraction and page-level chunking."""

    @staticmethod
    def extract_text(file_path: str) -> list[dict]:
        """
        Extract text from each page of a PDF.

        Returns:
            list of {"page": int, "text": str}
        """
        pages = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                text = PDFService._clean_text(text)
                if text.strip():
                    pages.append({"page": page_num + 1, "text": text})
            doc.close()
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {e}") from e
        return pages

    @staticmethod
    def get_page_count(file_path: str) -> int:
        try:
            doc = fitz.open(file_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove excessive whitespace and control chars."""
        text = re.sub(r"\x0c", "\n", text)        # form feed → newline
        text = re.sub(r"[ \t]{2,}", " ", text)    # multiple spaces → single
        text = re.sub(r"\n{3,}", "\n\n", text)    # 3+ newlines → 2
        return text.strip()

    @staticmethod
    def chunk_pages(pages: list[dict], chunk_size: int = 800, overlap: int = 150) -> list[dict]:
        """
        Split page texts into overlapping chunks for RAG.

        Returns:
            list of {"chunk_id": str, "page": int, "text": str}
        """
        chunks = []
        chunk_idx = 0
        for page_data in pages:
            text = page_data["text"]
            page_num = page_data["page"]
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk_text = text[start:end]
                if chunk_text.strip():
                    chunks.append({
                        "chunk_id": f"p{page_num}_c{chunk_idx}",
                        "page": page_num,
                        "text": chunk_text.strip(),
                    })
                    chunk_idx += 1
                if end >= len(text):
                    break
                start = end - overlap
        return chunks

    @staticmethod
    def get_full_text(pages: list[dict]) -> str:
        """Concatenate all page text."""
        return "\n\n".join(
            f"[Page {p['page']}]\n{p['text']}" for p in pages
        )
