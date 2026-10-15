"""services/analysis_service.py - Orchestrates PDF processing and AI analysis"""
import json
import logging
import uuid
from datetime import datetime

from database.models import db, Document, Analysis, Component, Dependency, ChatSession, ChatMessage
from services.gemini_service import GeminiService
from services.pdf_service import PDFService
from services.rag_service import RAGService

logger = logging.getLogger(__name__)


class AnalysisService:
    """High-level orchestration of document analysis tasks."""

    def __init__(self, gemini: GeminiService, rag: RAGService, config):
        self.gemini = gemini
        self.rag = rag
        self.config = config

    # ------------------------------------------------------------------ #
    # Document processing pipeline
    # ------------------------------------------------------------------ #
    def process_document(self, doc_id: int) -> dict:
        """
        Full pipeline: extract text → build vector index → run AI analysis.
        Updates document status throughout.
        """
        doc = db.session.get(Document, doc_id)
        if not doc:
            return {"success": False, "error": "Document not found"}

        try:
            doc.status = "processing"
            db.session.commit()

            # 1. Extract text
            pages = PDFService.extract_text(doc.file_path)
            page_count = PDFService.get_page_count(doc.file_path)

            doc = db.session.get(Document, doc_id)
            doc.page_count = page_count
            doc.extracted_text = json.dumps(pages)

            # 2. Build FAISS index
            chunk_size = self.config.get("CHUNK_SIZE", 800) if isinstance(self.config, dict) else getattr(self.config, "CHUNK_SIZE", 800)
            chunk_overlap = self.config.get("CHUNK_OVERLAP", 150) if isinstance(self.config, dict) else getattr(self.config, "CHUNK_OVERLAP", 150)
            chunks = PDFService.chunk_pages(pages, chunk_size, chunk_overlap)
            if chunks:
                texts = [c["text"] for c in chunks]
                embeddings = self.gemini.embed_texts(texts)
                self.rag.build_index(doc_id, chunks, embeddings)
                doc = db.session.get(Document, doc_id)
                doc.vector_index_key = f"doc_{doc_id}"

            db.session.commit()

            # 3. AI summarization
            full_text = PDFService.get_full_text(pages)
            summary = self.gemini.summarize_document(full_text, doc.original_name)
            self._save_analysis(doc_id, "summary", summary)

            # 4. Component extraction
            components_data = self.gemini.extract_components(full_text)
            self._save_analysis(doc_id, "components", components_data)
            self._save_components(doc_id, components_data)

            # 5. Inconsistency detection
            inconsistencies = self.gemini.detect_inconsistencies(full_text)
            self._save_analysis(doc_id, "inconsistencies", inconsistencies)

            doc = db.session.get(Document, doc_id)
            doc.status = "analyzed"
            db.session.commit()

            return {"success": True, "doc_id": doc_id}

        except Exception as e:
            logger.error("Document processing failed for doc %d: %s", doc_id, e)
            db.session.rollback()
            try:
                err_doc = db.session.get(Document, doc_id)
                if err_doc:
                    err_doc.status = "error"
                    db.session.commit()
            except Exception:
                db.session.rollback()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Chat / Q&A
    # ------------------------------------------------------------------ #
    def get_or_create_session(self, doc_id: int, session_key: str = None) -> ChatSession:
        if session_key:
            sess = ChatSession.query.filter_by(session_key=session_key, document_id=doc_id).first()
            if sess:
                return sess
        new_key = session_key or str(uuid.uuid4())
        sess = ChatSession(document_id=doc_id, session_key=new_key)
        db.session.add(sess)
        db.session.commit()
        return sess

    def chat(self, doc_id: int, session_key: str, question: str) -> dict:
        doc = Document.query.get(doc_id)
        if not doc or doc.status not in ("analyzed", "processing"):
            return {"error": "Document not found or not yet analyzed"}

        session = self.get_or_create_session(doc_id, session_key)

        # Retrieve history
        max_history = self.config.get("MAX_CHAT_HISTORY", 20) if isinstance(self.config, dict) else getattr(self.config, "MAX_CHAT_HISTORY", 20)
        history = [
            {"role": m.role, "content": m.content}
            for m in session.messages[-max_history:]
        ]

        # Semantic search
        context_chunks = []
        if self.rag.index_exists(doc_id):
            query_emb = self.gemini.embed_query(question)
            context_chunks = self.rag.search(doc_id, query_emb, top_k=6)
        else:
            # Fall back to first pages
            pages = json.loads(doc.extracted_text or "[]")
            context_chunks = pages[:4]

        # Generate answer
        result = self.gemini.answer_question(question, context_chunks, history)

        # Persist messages
        user_msg = ChatMessage(session_id=session.id, role="user", content=question)
        db.session.add(user_msg)

        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=result["answer"],
            source_pages=",".join(str(p) for p in result["source_pages"]),
        )
        db.session.add(assistant_msg)
        db.session.commit()

        return {
            "answer": result["answer"],
            "source_pages": result["source_pages"],
            "session_key": session.session_key,
        }

    # ------------------------------------------------------------------ #
    # Document comparison
    # ------------------------------------------------------------------ #
    def compare_documents(self, doc_id_a: int, doc_id_b: int) -> dict:
        doc_a = Document.query.get(doc_id_a)
        doc_b = Document.query.get(doc_id_b)
        if not doc_a or not doc_b:
            return {"error": "One or both documents not found"}

        pages_a = json.loads(doc_a.extracted_text or "[]")
        pages_b = json.loads(doc_b.extracted_text or "[]")
        text_a = PDFService.get_full_text(pages_a)
        text_b = PDFService.get_full_text(pages_b)

        result = self.gemini.compare_documents(text_a, text_b, doc_a.original_name, doc_b.original_name)
        # Cache comparison as analysis
        self._save_analysis(doc_id_a, f"comparison_with_{doc_id_b}", result)
        return result

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #
    def _save_analysis(self, doc_id: int, analysis_type: str, data: dict):
        existing = Analysis.query.filter_by(document_id=doc_id, analysis_type=analysis_type).first()
        if existing:
            existing.result_json = json.dumps(data)
            existing.created_at = datetime.utcnow()
        else:
            analysis = Analysis(
                document_id=doc_id,
                analysis_type=analysis_type,
                result_json=json.dumps(data),
                model_used=self.gemini.model,
            )
            db.session.add(analysis)
        db.session.commit()

    def _save_components(self, doc_id: int, components_data: dict):
        # Remove old components for this document
        Component.query.filter_by(document_id=doc_id).delete()
        db.session.commit()

        for comp in components_data.get("components", []):
            c = Component(
                document_id=doc_id,
                name=comp.get("name", "Unknown"),
                component_type=comp.get("type", ""),
                description=comp.get("description", ""),
                source_pages=str(comp.get("source_hint", "")),
            )
            db.session.add(c)
            db.session.flush()  # get c.id

            # Save dependencies for this component
            for dep in components_data.get("dependencies", []):
                if dep.get("source", "").lower() == comp.get("name", "").lower():
                    d = Dependency(
                        source_component_id=c.id,
                        target_name=dep.get("target", ""),
                        dependency_type=dep.get("dependency_type", ""),
                        description=dep.get("description", ""),
                    )
                    db.session.add(d)

        db.session.commit()
