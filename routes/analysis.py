"""routes/analysis.py - AI analysis and component inventory routes"""
import json

from flask import (
    Blueprint, current_app, jsonify, render_template, request, redirect, url_for, flash,
)

from database.models import db, Document, Analysis, Component, Dependency

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")


def get_analysis_service():
    return current_app.extensions["analysis_service"]


@analysis_bp.route("/<int:doc_id>")
def view_analysis(doc_id):
    doc = Document.query.get_or_404(doc_id)
    summary = Analysis.query.filter_by(document_id=doc_id, analysis_type="summary").first()
    components_analysis = Analysis.query.filter_by(document_id=doc_id, analysis_type="components").first()
    inconsistencies = Analysis.query.filter_by(document_id=doc_id, analysis_type="inconsistencies").first()

    summary_data = json.loads(summary.result_json) if summary else {}
    components_data = json.loads(components_analysis.result_json) if components_analysis else {}
    inconsistencies_data = json.loads(inconsistencies.result_json) if inconsistencies else {}

    return render_template(
        "analysis.html",
        doc=doc,
        summary=summary_data,
        components_data=components_data,
        inconsistencies=inconsistencies_data,
    )


@analysis_bp.route("/<int:doc_id>/run", methods=["POST"])
def run_analysis(doc_id):
    """Trigger full AI analysis pipeline (can be slow — consider threading for production)."""
    doc = Document.query.get_or_404(doc_id)
    if doc.status == "processing":
        return jsonify({"status": "already_running"})

    svc = get_analysis_service()
    result = svc.process_document(doc_id)
    if result["success"]:
        return jsonify({"status": "success", "redirect": url_for("analysis.view_analysis", doc_id=doc_id)})
    else:
        return jsonify({"status": "error", "error": result.get("error", "Unknown error")}), 500


@analysis_bp.route("/<int:doc_id>/status")
def analysis_status(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return jsonify({"status": doc.status, "doc_id": doc_id})


# ------------------------------------------------------------------ #
# Component inventory
# ------------------------------------------------------------------ #
@analysis_bp.route("/components")
def components():
    doc_id = request.args.get("doc_id", type=int)
    search = request.args.get("q", "").strip()

    documents = Document.query.filter(Document.status == "analyzed").all()

    query = Component.query
    if doc_id:
        query = query.filter_by(document_id=doc_id)
    if search:
        query = query.filter(
            Component.name.ilike(f"%{search}%") |
            Component.component_type.ilike(f"%{search}%") |
            Component.description.ilike(f"%{search}%")
        )

    components_list = query.order_by(Component.name).all()

    # Get interfaces / signals from analysis JSON if a doc is selected
    interfaces = []
    signals = []
    ports = []
    if doc_id:
        ca = Analysis.query.filter_by(document_id=doc_id, analysis_type="components").first()
        if ca:
            data = json.loads(ca.result_json)
            interfaces = data.get("interfaces", [])
            signals = data.get("signals", [])
            ports = data.get("ports", [])

    return render_template(
        "components.html",
        documents=documents,
        components=components_list,
        interfaces=interfaces,
        signals=signals,
        ports=ports,
        selected_doc_id=doc_id,
        search=search,
    )


# ------------------------------------------------------------------ #
# Inconsistency page
# ------------------------------------------------------------------ #
@analysis_bp.route("/<int:doc_id>/inconsistencies")
def inconsistencies(doc_id):
    doc = Document.query.get_or_404(doc_id)
    analysis = Analysis.query.filter_by(document_id=doc_id, analysis_type="inconsistencies").first()
    data = json.loads(analysis.result_json) if analysis else {}
    return render_template("analysis.html", doc=doc, inconsistencies=data, tab="inconsistencies")


# ------------------------------------------------------------------ #
# Document comparison
# ------------------------------------------------------------------ #
@analysis_bp.route("/compare", methods=["GET", "POST"])
def compare():
    documents = Document.query.filter(Document.status == "analyzed").all()
    comparison_result = None
    doc_a = doc_b = None

    if request.method == "POST":
        doc_id_a = request.form.get("doc_a", type=int)
        doc_id_b = request.form.get("doc_b", type=int)

        if not doc_id_a or not doc_id_b:
            flash("Please select two documents to compare.", "warning")
        elif doc_id_a == doc_id_b:
            flash("Please select two different documents.", "warning")
        else:
            svc = get_analysis_service()
            comparison_result = svc.compare_documents(doc_id_a, doc_id_b)
            doc_a = Document.query.get(doc_id_a)
            doc_b = Document.query.get(doc_id_b)

    return render_template(
        "comparison.html",
        documents=documents,
        comparison=comparison_result,
        doc_a=doc_a,
        doc_b=doc_b,
    )


# ------------------------------------------------------------------ #
# JSON API endpoints
# ------------------------------------------------------------------ #
@analysis_bp.route("/<int:doc_id>/json")
def analysis_json(doc_id):
    analyses = Analysis.query.filter_by(document_id=doc_id).all()
    return jsonify({a.analysis_type: json.loads(a.result_json) for a in analyses})
