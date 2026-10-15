"""routes/chatbot.py - AI chatbot Q&A routes"""
import json

from flask import (
    Blueprint, current_app, jsonify, render_template, request, session,
)

from database.models import Document, ChatSession, ChatMessage

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chat")


def get_analysis_service():
    return current_app.extensions["analysis_service"]


@chatbot_bp.route("/")
def chat_home():
    documents = Document.query.filter(Document.status.in_(["analyzed"])).all()
    return render_template("chatbot.html", documents=documents, selected_doc=None, messages=[])


@chatbot_bp.route("/<int:doc_id>")
def chat_with_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    documents = Document.query.filter(Document.status == "analyzed").all()

    session_key = request.args.get("session_key") or session.get(f"chat_session_{doc_id}")
    messages = []

    if session_key:
        chat_session = ChatSession.query.filter_by(
            session_key=session_key, document_id=doc_id
        ).first()
        if chat_session:
            messages = [m.to_dict() for m in chat_session.messages]
            session[f"chat_session_{doc_id}"] = session_key

    return render_template(
        "chatbot.html",
        documents=documents,
        selected_doc=doc,
        messages=messages,
        session_key=session_key,
    )


@chatbot_bp.route("/<int:doc_id>/ask", methods=["POST"])
def ask(doc_id):
    """API endpoint: POST JSON {question, session_key}"""
    doc = Document.query.get_or_404(doc_id)

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    question = data.get("question", "").strip()
    session_key = data.get("session_key") or session.get(f"chat_session_{doc_id}")

    if not question:
        return jsonify({"error": "Question is required"}), 400

    if len(question) > 2000:
        return jsonify({"error": "Question too long (max 2000 chars)"}), 400

    svc = get_analysis_service()
    result = svc.chat(doc_id, session_key, question)

    if "error" in result:
        return jsonify(result), 400

    # Store session key in Flask session
    session[f"chat_session_{doc_id}"] = result["session_key"]

    return jsonify(result)


@chatbot_bp.route("/<int:doc_id>/history")
def history(doc_id):
    session_key = request.args.get("session_key") or session.get(f"chat_session_{doc_id}")
    if not session_key:
        return jsonify({"messages": []})

    chat_session = ChatSession.query.filter_by(session_key=session_key, document_id=doc_id).first()
    if not chat_session:
        return jsonify({"messages": []})

    return jsonify({"messages": [m.to_dict() for m in chat_session.messages]})


@chatbot_bp.route("/<int:doc_id>/clear", methods=["POST"])
def clear_history(doc_id):
    session_key = session.pop(f"chat_session_{doc_id}", None)
    if session_key:
        chat_session = ChatSession.query.filter_by(session_key=session_key, document_id=doc_id).first()
        if chat_session:
            from database.models import db
            db.session.delete(chat_session)
            db.session.commit()
    return jsonify({"success": True})
