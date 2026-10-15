"""routes/reports.py - Report generation and export routes"""
import csv
import io
import json
from datetime import datetime

from flask import (
    Blueprint, jsonify, make_response, render_template, request,
)

from database.models import Document, Analysis, Component, Dependency

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
def reports_home():
    documents = Document.query.filter(Document.status == "analyzed").all()
    return render_template("reports.html", documents=documents)


@reports_bp.route("/<int:doc_id>/json")
def export_json(doc_id):
    """Export full analysis as JSON download."""
    doc = Document.query.get_or_404(doc_id)
    analyses = Analysis.query.filter_by(document_id=doc_id).all()
    components = Component.query.filter_by(document_id=doc_id).all()

    data = {
        "document": doc.to_dict(),
        "analyses": {a.analysis_type: json.loads(a.result_json) for a in analyses},
        "components": [c.to_dict() for c in components],
        "dependencies": [],
        "exported_at": datetime.utcnow().isoformat(),
    }
    for comp in components:
        for dep in comp.dependencies:
            data["dependencies"].append({
                "source": comp.name,
                **dep.to_dict(),
            })

    response = make_response(json.dumps(data, indent=2))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="analysis_{doc.original_name}_{datetime.utcnow().strftime("%Y%m%d")}.json"'
    )
    return response


@reports_bp.route("/<int:doc_id>/csv/components")
def export_components_csv(doc_id):
    doc = Document.query.get_or_404(doc_id)
    components = Component.query.filter_by(document_id=doc_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Type", "Description", "Source Pages"])
    for c in components:
        writer.writerow([c.name, c.component_type, c.description, c.source_pages])

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="components_{doc.original_name}_{datetime.utcnow().strftime("%Y%m%d")}.csv"'
    )
    return response


@reports_bp.route("/<int:doc_id>/csv/inconsistencies")
def export_inconsistencies_csv(doc_id):
    doc = Document.query.get_or_404(doc_id)
    analysis = Analysis.query.filter_by(document_id=doc_id, analysis_type="inconsistencies").first()
    data = json.loads(analysis.result_json) if analysis else {}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Category", "Description", "Severity", "Details"])

    for item in data.get("missing_dependencies", []):
        writer.writerow(["Missing Dependency", item.get("description", ""), item.get("severity", ""), item.get("affected_component", "")])
    for item in data.get("inconsistent_interfaces", []):
        writer.writerow(["Inconsistent Interface", item.get("description", ""), item.get("severity", ""), item.get("interface_name", "")])
    for item in data.get("incomplete_info", []):
        writer.writerow(["Incomplete Info", item.get("description", ""), item.get("severity", ""), item.get("section", "")])
    for item in data.get("recommendations", []):
        writer.writerow(["Recommendation", item.get("recommendation", ""), item.get("priority", ""), item.get("rationale", "")])

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="inconsistencies_{doc.original_name}_{datetime.utcnow().strftime("%Y%m%d")}.csv"'
    )
    return response


@reports_bp.route("/<int:doc_id>/html")
def report_html(doc_id):
    """Render a printable HTML analysis report."""
    doc = Document.query.get_or_404(doc_id)
    analyses = Analysis.query.filter_by(document_id=doc_id).all()
    components = Component.query.filter_by(document_id=doc_id).all()

    summary_data = {}
    components_data = {}
    inconsistencies_data = {}

    for a in analyses:
        result = json.loads(a.result_json)
        if a.analysis_type == "summary":
            summary_data = result
        elif a.analysis_type == "components":
            components_data = result
        elif a.analysis_type == "inconsistencies":
            inconsistencies_data = result

    return render_template(
        "report_print.html",
        doc=doc,
        summary=summary_data,
        components_data=components_data,
        inconsistencies=inconsistencies_data,
        db_components=components,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )
