"""Service layer for business logic."""
import os
import uuid
import hashlib
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models import DocAsset, AuditEvent, IndexedStatus, AuditModule, AuditStatus

logger = logging.getLogger(__name__)

# Get uploads directory from environment or use default
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/app/uploads"))
# Ensure directory exists and is writable (created in Dockerfile, but verify)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def generate_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return str(uuid.uuid4())


def hash_prompt(prompt: str) -> str:
    """Generate a hash of the prompt for audit purposes."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


async def save_uploaded_file(file: UploadFile, request_id: str) -> tuple[str, str]:
    """
    Save uploaded file to uploads volume.
    Returns (storage_uri, filename).
    """
    # Generate unique filename to avoid conflicts
    original_filename = file.filename or "unnamed"
    file_extension = Path(original_filename).suffix
    unique_filename = f"{request_id}{file_extension}"
    storage_path = UPLOADS_DIR / unique_filename
    
    # Ensure directory exists
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read file content and save
    content = await file.read()
    with open(storage_path, "wb") as f:
        f.write(content)
    
    # Return relative path for storage_uri
    storage_uri = f"uploads/{unique_filename}"
    
    logger.info(f"Saved file: {original_filename} -> {storage_uri} (request_id: {request_id})")
    return storage_uri, original_filename


def create_doc_asset(
    db: Session,
    filename: str,
    storage_uri: str,
    request_id: str
) -> DocAsset:
    """Create a doc_asset record in the database."""
    doc_asset = DocAsset(
        filename=filename,
        storage_uri=storage_uri,
        indexed_status=IndexedStatus.PENDING
    )
    db.add(doc_asset)
    db.commit()
    db.refresh(doc_asset)
    
    logger.info(f"Created doc_asset: id={doc_asset.id}, filename={filename} (request_id: {request_id})")
    return doc_asset


def create_audit_event(
    db: Session,
    module: AuditModule,
    request_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    prompt_hash: Optional[str] = None,
    sources_json: Optional[dict] = None,
    tool_calls_json: Optional[dict] = None,
    decision_json: Optional[dict] = None,
    status: AuditStatus = AuditStatus.SUCCESS,
    error: Optional[str] = None
) -> AuditEvent:
    """Create an audit event record."""
    audit_event = AuditEvent(
        module=module,
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        prompt_hash=prompt_hash,
        sources_json=sources_json,
        tool_calls_json=tool_calls_json,
        decision_json=decision_json,
        status=status,
        error=error
    )
    db.add(audit_event)
    db.commit()
    db.refresh(audit_event)
    
    logger.info(f"Created audit_event: id={audit_event.id}, module={module}, request_id={request_id}, status={status}")
    return audit_event


def get_all_docs(db: Session) -> list[DocAsset]:
    """Get all non-deleted documents."""
    return db.query(DocAsset).filter(DocAsset.deleted_at.is_(None)).all()


def check_duplicate_filename(db: Session, filename: str) -> Optional[DocAsset]:
    """Check if a document with the same filename already exists (not deleted)."""
    return db.query(DocAsset).filter(
        DocAsset.filename == filename,
        DocAsset.deleted_at.is_(None)
    ).first()
