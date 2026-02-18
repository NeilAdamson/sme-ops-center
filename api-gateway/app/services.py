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
    
    # Generate GCS object path: gs://bucket/docs/<uuid>/<original_filename>
    # docs/ prefix aligns with Vertex AI Search Data Store import prefix (gs://bucket/docs/)
    object_name = f"docs/{request_id}/{filename}"
    
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


def get_doc_by_id(db: Session, doc_id: int) -> Optional[DocAsset]:
    """Get a document by ID (non-deleted only)."""
    return db.query(DocAsset).filter(
        DocAsset.id == doc_id,
        DocAsset.deleted_at.is_(None)
    ).first()


def get_pending_gcs_docs(db: Session, doc_id: Optional[int] = None) -> list[DocAsset]:
    """
    Get documents eligible for Vertex AI Search indexing.
    Returns PENDING docs with gs:// storage URIs. If doc_id provided, filters to that doc.
    """
    q = db.query(DocAsset).filter(
        DocAsset.deleted_at.is_(None),
        DocAsset.indexed_status == IndexedStatus.PENDING,
        DocAsset.storage_uri.like("gs://%")
    )
    if doc_id is not None:
        q = q.filter(DocAsset.id == doc_id)
    return q.all()


def update_doc_indexed_status(
    db: Session,
    doc_asset: DocAsset,
    status: IndexedStatus,
    datastore_ref: Optional[str] = None
) -> None:
    """Update document indexing status."""
    doc_asset.indexed_status = status
    if datastore_ref is not None:
        doc_asset.datastore_ref = datastore_ref
    db.commit()
    db.refresh(doc_asset)


def trigger_vertex_import(storage_uri: str, request_id: str = "") -> tuple[bool, Optional[str]]:
    """
    Trigger Vertex AI Search (Discovery Engine) document import from GCS.
    Returns (success, error_message). On success, error_message is None.
    Requires: GOOGLE_CLOUD_PROJECT, DISCOVERY_ENGINE_LOCATION, DATA_STORE_ID.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("DISCOVERY_ENGINE_LOCATION", "global")
    data_store_id = os.getenv("DATA_STORE_ID")
    if not project_id or not data_store_id:
        return False, "Vertex AI Search not configured (GOOGLE_CLOUD_PROJECT, DATA_STORE_ID required)"
    if not storage_uri.startswith("gs://"):
        return False, f"Storage URI must be gs:// (got {storage_uri[:50]}...)"

    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import discoveryengine

        client_options = (
            ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
            if location != "global"
            else None
        )
        client = discoveryengine.DocumentServiceClient(client_options=client_options)
        parent = client.branch_path(
            project=project_id,
            location=location,
            data_store=data_store_id,
            branch="default_branch",
        )
        request = discoveryengine.ImportDocumentsRequest(
            parent=parent,
            gcs_source=discoveryengine.GcsSource(
                input_uris=[storage_uri],
                data_schema="content",
            ),
            reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        )
        operation = client.import_documents(request=request)
        response = operation.result()
        logger.info(
            f"Vertex import completed for {storage_uri} (request_id: {request_id})"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"Vertex import failed for {storage_uri}: {e} (request_id: {request_id})",
            exc_info=True,
        )
        return False, str(e)
