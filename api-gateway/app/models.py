"""Database models for SME Ops-Center."""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.database import Base


class IndexedStatus(str, enum.Enum):
    """Document indexing status."""
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class AuditModule(str, enum.Enum):
    """Module identifiers for audit events."""
    MODULE_A = "module_a"  # Docs/RAG
    MODULE_B = "module_b"  # Inbox Triage
    MODULE_C = "module_c"  # Xero Finance Lens
    ADMIN = "admin"
    SYSTEM = "system"


class AuditStatus(str, enum.Enum):
    """Status for audit events."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


class DocAsset(Base):
    """Document asset table - stores metadata about uploaded documents."""
    __tablename__ = "doc_asset"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(512), nullable=False, index=True)
    storage_uri = Column(String(1024), nullable=False)  # Path to stored file
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    indexed_status = Column(SQLEnum(IndexedStatus), default=IndexedStatus.PENDING, nullable=False, index=True)
    datastore_ref = Column(String(512), nullable=True)  # Vertex AI Search datastore reference
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self):
        return f"<DocAsset(id={self.id}, filename='{self.filename}', status='{self.indexed_status}')>"


class AuditEvent(Base):
    """Audit event table - logs all queries, tool calls, and decisions."""
    __tablename__ = "audit_event"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    module = Column(SQLEnum(AuditModule), nullable=False, index=True)
    user_id = Column(String(128), nullable=True, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    request_id = Column(String(128), nullable=False, index=True)  # UUID for request tracing
    prompt_hash = Column(String(64), nullable=True, index=True)  # Hash of user prompt
    sources_json = Column(JSON, nullable=True)  # Retrieved sources/citations
    tool_calls_json = Column(JSON, nullable=True)  # MCP tool calls made
    decision_json = Column(JSON, nullable=True)  # Approval/rejection decisions
    status = Column(SQLEnum(AuditStatus), default=AuditStatus.PENDING, nullable=False, index=True)
    error = Column(Text, nullable=True)  # Error message if status is FAILURE

    def __repr__(self):
        return f"<AuditEvent(id={self.id}, module='{self.module}', request_id='{self.request_id}', status='{self.status}')>"
