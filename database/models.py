"""database/models.py - SQLAlchemy models for AUTOSAR HLD Assistant"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # bytes
    page_count = db.Column(db.Integer, default=0)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="uploaded")
    # extracted text stored as JSON list of {page, text}
    extracted_text = db.Column(db.Text, default="[]")
    # vector store index key
    vector_index_key = db.Column(db.String(255), nullable=True)

    analyses = db.relationship("Analysis", backref="document", lazy=True, cascade="all, delete-orphan")
    components = db.relationship("Component", backref="document", lazy=True, cascade="all, delete-orphan")
    chat_sessions = db.relationship("ChatSession", backref="document", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "upload_date": self.upload_date.isoformat(),
            "status": self.status,
        }


class Analysis(db.Model):
    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    analysis_type = db.Column(db.String(100), nullable=False)  # summary, components, inconsistencies, comparison
    result_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    model_used = db.Column(db.String(100), default="")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "document_id": self.document_id,
            "analysis_type": self.analysis_type,
            "result": json.loads(self.result_json),
            "created_at": self.created_at.isoformat(),
            "model_used": self.model_used,
        }


class Component(db.Model):
    __tablename__ = "components"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    component_type = db.Column(db.String(100), default="")  # SWC, BSW, ECU, Interface, Port, Signal
    description = db.Column(db.Text, default="")
    source_pages = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    dependencies = db.relationship(
        "Dependency",
        foreign_keys="Dependency.source_component_id",
        backref="source_component",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "name": self.name,
            "type": self.component_type,
            "description": self.description,
            "source_pages": self.source_pages,
        }


class Dependency(db.Model):
    __tablename__ = "dependencies"

    id = db.Column(db.Integer, primary_key=True)
    source_component_id = db.Column(db.Integer, db.ForeignKey("components.id"), nullable=False)
    target_name = db.Column(db.String(255), nullable=False)
    dependency_type = db.Column(db.String(100), default="")  # requires, provides, calls, sends
    description = db.Column(db.Text, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "source_component_id": self.source_component_id,
            "target_name": self.target_name,
            "dependency_type": self.dependency_type,
            "description": self.description,
        }


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    session_key = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship("ChatMessage", backref="session", lazy=True, cascade="all, delete-orphan")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    source_pages = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "source_pages": self.source_pages,
            "created_at": self.created_at.isoformat(),
        }
