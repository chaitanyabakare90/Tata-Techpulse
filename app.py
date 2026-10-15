"""
app.py - Main Flask application for AUTOSAR HLD Document Analysis Assistant
"""
import logging
import os

from flask import Flask

from config import Config
from database.models import db
from routes.main import main_bp
from routes.documents import documents_bp
from routes.analysis import analysis_bp
from routes.chatbot import chatbot_bp
from routes.reports import reports_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize config (create dirs etc.)
    config_class.init_app(app)

    # Init database
    db.init_app(app)

    # Initialize services
    _init_services(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(reports_bp)

    # Create DB tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created/verified.")

    # Template filters
    @app.template_filter("filesizeformat")
    def filesizeformat(value):
        for unit in ["B", "KB", "MB", "GB"]:
            if value < 1024:
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TB"

    @app.template_filter("short_date")
    def short_date(value):
        if hasattr(value, "strftime"):
            return value.strftime("%d %b %Y %H:%M")
        return str(value)

    return app


def _init_services(app: Flask):
    """Initialize Gemini, RAG, and Analysis services and attach to app.extensions."""
    api_key = app.config.get("GEMINI_API_KEY", "")
    gemini = None

    if not api_key:
        logger.warning(
            "GEMINI_API_KEY is not set. AI features will be unavailable. "
            "Copy .env.example to .env and add your key."
        )
    else:
        try:
            from services.gemini_service import GeminiService
            gemini = GeminiService(
                api_key=api_key,
                model=app.config["GEMINI_MODEL"],
                embed_model=app.config["GEMINI_EMBED_MODEL"],
            )
            logger.info("Gemini service initialized with model: %s", app.config["GEMINI_MODEL"])
        except Exception as e:
            logger.error("Failed to initialize Gemini service: %s", e)

    from services.rag_service import RAGService
    rag = RAGService(index_dir=app.config["FAISS_INDEX_DIR"])

    from services.analysis_service import AnalysisService

    class _FallbackGemini:
        """Placeholder when no API key is configured."""
        model = "unavailable"

        def _no_key(self, *a, **kw):
            raise RuntimeError(
                "Gemini API key not configured. "
                "Please add GEMINI_API_KEY to your .env file and restart."
            )

        embed_texts = embed_query = summarize_document = extract_components = (
            detect_inconsistencies
        ) = answer_question = compare_documents = _no_key

    analysis_svc = AnalysisService(
        gemini=gemini or _FallbackGemini(),
        rag=rag,
        config=app.config,
    )

    app.extensions["gemini_service"] = gemini
    app.extensions["rag_service"] = rag
    app.extensions["analysis_service"] = analysis_svc

    # Make api_key_configured available in all templates
    @app.context_processor
    def inject_globals():
        return {
            "api_key_configured": bool(api_key),
            "app_name": "AUTOSAR HLD Analysis Assistant",
        }


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
