"""
config.py - Application configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).parent


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "autosar-hld-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Gemini API
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

    # File uploads
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
    ALLOWED_EXTENSIONS = {"pdf"}
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # Database
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'autosar_hld.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # FAISS vector store
    FAISS_INDEX_DIR = BASE_DIR / "vector_store"

    # RAG chunking
    CHUNK_SIZE = 800          # characters per chunk
    CHUNK_OVERLAP = 150       # character overlap between chunks

    # Analysis
    MAX_CHAT_HISTORY = 20     # messages kept per session

    @staticmethod
    def init_app(app):
        Config.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        Config.FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
