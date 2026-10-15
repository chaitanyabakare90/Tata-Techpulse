"""services/gemini_service.py - Google Gemini API integration"""
import json
import logging
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiService:
    """Wrapper around the google-genai SDK for AUTOSAR HLD analysis tasks."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", embed_model: str = "gemini-embedding-001"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Check your .env file.")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        # Strip 'models/' prefix if provided
        self.embed_model = embed_model.replace("models/", "") if embed_model else "gemini-embedding-001"

    # ------------------------------------------------------------------ #
    # Text generation helpers
    # ------------------------------------------------------------------ #
    def _generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        """Call Gemini and return text response."""
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=8192,
        )
        if system:
            config.system_instruction = system

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return response.text.strip()

    def _generate_json(self, prompt: str, system: str = "") -> dict | list:
        """Call Gemini and parse JSON from the response."""
        raw = self._generate(prompt, system=system)
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            # Remove opening fence (```json or ```)
            lines = lines[1:] if lines[0].startswith("```") else lines
            # Remove closing fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from Gemini response: %s", raw[:500])
            return {}

    # ------------------------------------------------------------------ #
    # Embeddings
    # ------------------------------------------------------------------ #
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = []
        for text in texts:
            try:
                result = self.client.models.embed_content(
                    model=self.embed_model,
                    contents=text,
                )
                embeddings.append(result.embeddings[0].values)
            except Exception as e:
                logger.warning("Embedding with %s failed (%s), retrying with gemini-embedding-001", self.embed_model, e)
                result = self.client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                )
                embeddings.append(result.embeddings[0].values)
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string."""
        try:
            result = self.client.models.embed_content(
                model=self.embed_model,
                contents=query,
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.warning("Query embedding with %s failed (%s), retrying with gemini-embedding-001", self.embed_model, e)
            result = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=query,
            )
            return result.embeddings[0].values

    # ------------------------------------------------------------------ #
    # Document summarization
    # ------------------------------------------------------------------ #
    def summarize_document(self, full_text: str, doc_name: str = "") -> dict:
        """
        Summarize an AUTOSAR HLD document.

        Returns dict with keys: title, summary, key_topics, document_type, autosar_version
        """
        system = (
            "You are an expert AUTOSAR automotive software architect. "
            "Analyze AUTOSAR High-Level Design (HLD) documents accurately. "
            "Return only valid JSON. Do not invent information not present in the document."
        )
        prompt = f"""Analyze this AUTOSAR HLD document and return a JSON object with these keys:
- "title": inferred document title (string)
- "summary": comprehensive 3-5 sentence summary (string)
- "key_topics": list of main topics covered (list of strings)
- "document_type": type of document (e.g., System HLD, Software HLD, Component HLD)
- "autosar_version": AUTOSAR version mentioned (string, or "Not specified")
- "ecu_names": list of ECU names mentioned (list of strings)
- "total_components_found": approximate number of SW components (integer)

Document name: {doc_name}

Document content (first 12000 chars):
{full_text[:12000]}

Return only valid JSON, no explanation."""
        result = self._generate_json(prompt, system=system)
        if not result:
            result = {
                "title": doc_name or "Unknown",
                "summary": "Unable to generate summary. Please check the document content.",
                "key_topics": [],
                "document_type": "Unknown",
                "autosar_version": "Not specified",
                "ecu_names": [],
                "total_components_found": 0,
            }
        return result

    # ------------------------------------------------------------------ #
    # Component extraction
    # ------------------------------------------------------------------ #
    def extract_components(self, full_text: str) -> dict:
        """
        Extract AUTOSAR components, interfaces, ports, signals, and dependencies.

        Returns dict with keys: components, interfaces, ports, signals, dependencies, functional_flows
        """
        system = (
            "You are an expert AUTOSAR software architect. "
            "Extract structured information from AUTOSAR HLD documents. "
            "Only include elements explicitly mentioned in the document. "
            "Return valid JSON only."
        )
        prompt = f"""Extract AUTOSAR architecture elements from the document below. Return a JSON object with:
- "components": list of objects with {{name, type (SWC/BSW/ECU/Other), description, source_hint}}
- "interfaces": list of objects with {{name, type (SenderReceiver/ClientServer/NvData/Parameter), description}}
- "ports": list of objects with {{name, port_type (P-Port/R-Port), interface_name, component_name}}
- "signals": list of objects with {{name, data_type, description, direction}}
- "dependencies": list of objects with {{source, target, dependency_type (requires/provides/calls/sends), description}}
- "functional_flows": list of objects with {{name, description, steps (list of strings)}}

Important: Only extract information explicitly present in the document. Do not invent components.

Document (up to 15000 chars):
{full_text[:15000]}

Return only valid JSON."""
        result = self._generate_json(prompt, system=system)
        defaults = {
            "components": [], "interfaces": [], "ports": [],
            "signals": [], "dependencies": [], "functional_flows": [],
        }
        if not isinstance(result, dict):
            return defaults
        for key in defaults:
            if key not in result:
                result[key] = defaults[key]
        return result

    # ------------------------------------------------------------------ #
    # Inconsistency detection
    # ------------------------------------------------------------------ #
    def detect_inconsistencies(self, full_text: str) -> dict:
        """
        Detect architectural inconsistencies and missing information.

        Returns dict with keys: missing_dependencies, inconsistent_interfaces,
                                incomplete_info, recommendations, severity_summary
        """
        system = (
            "You are an AUTOSAR architecture review expert. "
            "Identify real inconsistencies and gaps in HLD documents. "
            "Be specific and cite page/section references where possible. "
            "Return valid JSON only. Do not fabricate issues."
        )
        prompt = f"""Review this AUTOSAR HLD document for architectural issues. Return a JSON object with:
- "missing_dependencies": list of {{description, affected_component, severity (High/Medium/Low)}}
- "inconsistent_interfaces": list of {{description, interface_name, severity}}
- "incomplete_info": list of {{description, section, severity}}
- "recommendations": list of {{recommendation, priority (High/Medium/Low), rationale}}
- "severity_summary": {{high_count: int, medium_count: int, low_count: int}}

Focus on:
1. Components referenced but not defined
2. Interfaces with mismatched port types
3. Missing signal definitions
4. Incomplete ECU mapping
5. Undocumented dependencies

Document (up to 15000 chars):
{full_text[:15000]}

Return only valid JSON."""
        result = self._generate_json(prompt, system=system)
        defaults = {
            "missing_dependencies": [],
            "inconsistent_interfaces": [],
            "incomplete_info": [],
            "recommendations": [],
            "severity_summary": {"high_count": 0, "medium_count": 0, "low_count": 0},
        }
        if not isinstance(result, dict):
            return defaults
        for key in defaults:
            if key not in result:
                result[key] = defaults[key]
        return result

    # ------------------------------------------------------------------ #
    # RAG-based Q&A
    # ------------------------------------------------------------------ #
    def answer_question(self, question: str, context_chunks: list[dict], chat_history: list[dict] = None) -> dict:
        """
        Answer a question using retrieved document chunks (RAG).

        Args:
            question: User's question
            context_chunks: list of {"page": int, "text": str}
            chat_history: list of {"role": str, "content": str}

        Returns:
            {"answer": str, "source_pages": list[int], "confidence": str}
        """
        system = (
            "You are an AUTOSAR HLD document analysis assistant. "
            "Answer questions ONLY based on the provided document context. "
            "If the answer is not in the context, say so clearly. "
            "Always cite the page numbers where information was found. "
            "Be precise and technical."
        )
        # Build context string
        context_str = ""
        pages_used = []
        for chunk in context_chunks:
            context_str += f"\n[Page {chunk['page']}]\n{chunk['text']}\n"
            if chunk["page"] not in pages_used:
                pages_used.append(chunk["page"])

        # Build history string
        history_str = ""
        if chat_history:
            for msg in chat_history[-6:]:  # last 3 exchanges
                role = "User" if msg["role"] == "user" else "Assistant"
                history_str += f"{role}: {msg['content']}\n"

        prompt = f"""Document Context:
{context_str}

{"Previous conversation:" + chr(10) + history_str if history_str else ""}

User Question: {question}

Instructions:
- Answer based ONLY on the document context above
- Cite specific page numbers (e.g., "According to page 3...")
- If information is not in the context, state: "This information is not found in the provided document sections."
- Be technical and precise for AUTOSAR engineering questions

Provide your answer:"""

        answer = self._generate(prompt, system=system, temperature=0.1)
        return {
            "answer": answer,
            "source_pages": sorted(pages_used),
            "confidence": "high" if context_chunks else "low",
        }

    # ------------------------------------------------------------------ #
    # Document comparison
    # ------------------------------------------------------------------ #
    def compare_documents(self, text_a: str, text_b: str, name_a: str, name_b: str) -> dict:
        """
        Compare two AUTOSAR HLD documents and identify differences.
        """
        system = (
            "You are an AUTOSAR architecture expert comparing two HLD documents. "
            "Identify meaningful architectural differences. Return valid JSON only."
        )
        # Truncate to stay within limits
        max_chars = 7000
        prompt = f"""Compare these two AUTOSAR HLD documents and return a JSON object with:
- "common_components": list of component names present in both documents
- "only_in_a": list of elements only in Document A
- "only_in_b": list of elements only in Document B
- "interface_differences": list of {{description, severity (High/Medium/Low)}}
- "architectural_differences": list of {{aspect, document_a_approach, document_b_approach}}
- "compatibility_issues": list of {{issue, recommendation}}
- "similarity_score": estimated percentage similarity (0-100, integer)
- "summary": 2-3 sentence comparison summary

Document A ({name_a}) - first {max_chars} chars:
{text_a[:max_chars]}

Document B ({name_b}) - first {max_chars} chars:
{text_b[:max_chars]}

Return only valid JSON."""
        result = self._generate_json(prompt, system=system)
        defaults = {
            "common_components": [],
            "only_in_a": [],
            "only_in_b": [],
            "interface_differences": [],
            "architectural_differences": [],
            "compatibility_issues": [],
            "similarity_score": 0,
            "summary": "Comparison could not be completed.",
        }
        if not isinstance(result, dict):
            return defaults
        for key in defaults:
            if key not in result:
                result[key] = defaults[key]
        return result
