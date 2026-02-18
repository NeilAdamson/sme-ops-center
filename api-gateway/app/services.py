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

# Get storage backend from environment (default to 'local')
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

# Get uploads directory from environment or use default
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/app/uploads"))
# Ensure directory exists and is writable (created in Dockerfile, but verify)
if STORAGE_BACKEND == "local":
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def generate_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return str(uuid.uuid4())


def hash_prompt(prompt: str) -> str:
    """Generate a hash of the prompt for audit purposes."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


async def save_uploaded_file(file: UploadFile, request_id: str) -> tuple[str, str]:
    """
    Save uploaded file to storage backend (local or GCS).
    Returns (storage_uri, filename).
    """
    original_filename = file.filename or "unnamed"
    
    # Read file content once (needed for both backends)
    content = await file.read()
    
    if STORAGE_BACKEND == "gcs":
        # Upload to Google Cloud Storage
        return await _save_to_gcs(file, original_filename, content, request_id)
    else:
        # Save to local volume (default behavior)
        return _save_to_local(original_filename, content, request_id)


def _save_to_local(filename: str, content: bytes, request_id: str) -> tuple[str, str]:
    """Save file to local uploads volume."""
    file_extension = Path(filename).suffix
    unique_filename = f"{request_id}{file_extension}"
    storage_path = UPLOADS_DIR / unique_filename
    
    # Ensure directory exists
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file content
    with open(storage_path, "wb") as f:
        f.write(content)
    
    # Return relative path for storage_uri
    storage_uri = f"uploads/{unique_filename}"
    
    logger.info(f"Saved file to local: {filename} -> {storage_uri} (request_id: {request_id})")
    return storage_uri, filename


async def _save_to_gcs(file: UploadFile, filename: str, content: bytes, request_id: str) -> tuple[str, str]:
    """Save file to Google Cloud Storage."""
    from google.cloud import storage as gcs_storage
    from google.cloud.exceptions import GoogleCloudError
    
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("GCS_BUCKET_NAME environment variable is required when STORAGE_BACKEND=gcs")
    
    # Generate GCS object path: gs://bucket/uploads/<uuid>/<original_filename>
    object_name = f"uploads/{request_id}/{filename}"
    
    try:
        # Initialize GCS client
        client = gcs_storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        # Determine content type from file
        content_type = file.content_type or "application/octet-stream"
        
        # Upload to GCS
        blob.upload_from_string(content, content_type=content_type)
        
        # Construct full gs:// URI
        storage_uri = f"gs://{bucket_name}/{object_name}"
        
        logger.info(f"Saved file to GCS: {filename} -> {storage_uri} (request_id: {request_id})")
        return storage_uri, filename
        
    except GoogleCloudError as e:
        logger.error(f"GCS upload failed: {e} (request_id: {request_id})", exc_info=True)
        raise RuntimeError(f"Failed to upload to GCS: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error during GCS upload: {e} (request_id: {request_id})", exc_info=True)
        raise RuntimeError(f"Unexpected error during GCS upload: {str(e)}") from e


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
