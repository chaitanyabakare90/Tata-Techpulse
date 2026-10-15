"""routes/main.py - Dashboard and home routes"""
from flask import Blueprint, render_template
from database.models import Document, Analysis, Component, ChatMessage

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    total_docs = Document.query.count()
    analyzed_docs = Document.query.filter_by(status="analyzed").count()
    total_components = Component.query.count()
    total_analyses = Analysis.query.count()
    total_chats = ChatMessage.query.filter_by(role="user").count()

    # Recent documents
    recent_docs = Document.query.order_by(Document.upload_date.desc()).limit(5).all()

    # Recent analyses
    recent_analyses = Analysis.query.order_by(Analysis.created_at.desc()).limit(5).all()

    stats = {
        "total_docs": total_docs,
        "analyzed_docs": analyzed_docs,
        "total_components": total_components,
        "total_analyses": total_analyses,
        "total_chats": total_chats,
    }

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_docs=recent_docs,
        recent_analyses=recent_analyses,
    )
