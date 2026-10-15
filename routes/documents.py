"""routes/documents.py - Upload and document management routes"""
import json
import os
import uuid
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, jsonify, redirect,
    render_template, request, send_from_directory, url_for,
)
from werkzeug.utils import secure_filename

from database.models import db, Document
from services.pdf_service import PDFService

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


@documents_bp.route("/")
def list_documents():
    docs = Document.query.order_by(Document.upload_date.desc()).all()
    return render_template("documents.html", documents=docs)


@documents_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.", "danger")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.", "danger")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Only PDF files are allowed.", "danger")
            return redirect(request.url)

        # Secure filename and save
        original_name = file.filename
        ext = original_name.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        upload_folder.mkdir(parents=True, exist_ok=True)
        save_path = upload_folder / unique_name
        file.save(str(save_path))

        file_size = save_path.stat().st_size
        page_count = PDFService.get_page_count(str(save_path))

        doc = Document(
            filename=unique_name,
            original_name=secure_filename(original_name),
            file_path=str(save_path),
            file_size=file_size,
            page_count=page_count,
            status="uploaded",
        )
        db.session.add(doc)
        db.session.commit()

        flash(f'"{original_name}" uploaded successfully! Click "Analyze" to start AI analysis.', "success")
        return redirect(url_for("documents.view", doc_id=doc.id))

    return render_template("upload.html")


@documents_bp.route("/<int:doc_id>")
def view(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template("documents.html", doc=doc, documents=Document.query.order_by(Document.upload_date.desc()).all())


@documents_bp.route("/<int:doc_id>/delete", methods=["POST"])
def delete(doc_id):
    doc = Document.query.get_or_404(doc_id)
    # Remove file
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception:
        pass
    # Remove FAISS index
    try:
        from flask import current_app
        rag = current_app.extensions.get("rag_service")
        if rag:
            rag.delete_index(doc_id)
    except Exception:
        pass
    db.session.delete(doc)
    db.session.commit()
    flash("Document deleted.", "info")
    return redirect(url_for("documents.list_documents"))


@documents_bp.route("/<int:doc_id>/text")
def get_text(doc_id):
    """Return extracted page text as JSON."""
    doc = Document.query.get_or_404(doc_id)
    pages = json.loads(doc.extracted_text or "[]")
    return jsonify({"pages": pages, "total": len(pages)})


@documents_bp.route("/download/<int:doc_id>")
def download(doc_id):
    doc = Document.query.get_or_404(doc_id)
    folder = str(Path(doc.file_path).parent)
    return send_from_directory(folder, doc.filename, as_attachment=True, download_name=doc.original_name)
