"""Document management routes (Module A)."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    DocQueryRequest,
    DocQueryResponse,
    DocUploadResponse,
    DocStatusResponse,
    DocIndexRequest,
    DocIndexResponse,
    ErrorResponse,
    Citation,
    DocDomainResponse,
    DocMoveRequest,
    DocMoveResponse,
)
from app.services import (
    generate_request_id,
    hash_prompt,
    save_uploaded_file,
    create_doc_asset,
    create_audit_event,
    get_all_docs,
    get_doc_by_id,
    check_duplicate_filename,
    get_pending_gcs_docs,
    update_doc_indexed_status,
    enqueue_index_job,
    move_doc_to_domain,
    query_grounded_domains,
    STORAGE_BACKEND,
)
from app.models import AuditModule, AuditStatus, IndexedStatus
from app.domain_registry import get_domain_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/docs", tags=["docs"])


@router.get("/config")
async def get_storage_config():
    """
    Get storage backend configuration.
    
    Returns the active storage backend (local or gcs) for frontend display.
    """
    from app.services import STORAGE_BACKEND
    return {
        "storage_backend": STORAGE_BACKEND
    }


@router.get("/domains", response_model=DocDomainResponse)
async def get_doc_domains():
    """Get staging and domain bucket/search configuration for the UI."""
    request_id = generate_request_id()
    registry = get_domain_registry()
    domains = []
    for domain in registry["domains"]:
        item = dict(domain)
        item["query_ready"] = bool(item.get("serving_config") or item.get("engine_id"))
        item["index_ready"] = bool(item.get("data_store_id"))
        domains.append(item)
    return DocDomainResponse(
        request_id=request_id,
        staging=registry["staging"],
        domains=domains,
    )


@router.post("/upload", response_model=DocUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a document file.
    
    Writes file to uploads volume, inserts doc_asset row, and logs audit event.
    """
    request_id = generate_request_id()
    
    try:
        # Get original filename
        original_filename = file.filename or "unnamed"
        
        # Check for duplicate filename (informational - we allow duplicates for MVP)
        existing_doc = check_duplicate_filename(db, original_filename)
        if existing_doc:
            logger.warning(f"Duplicate filename detected: {original_filename} (existing doc_id: {existing_doc.id}, request_id: {request_id})")
            # For MVP: allow duplicates but log it. Later we could reject or replace.
        
        # Save file to uploads volume
        storage_uri, filename = await save_uploaded_file(file, request_id)
        
        # Create doc_asset record
        doc_asset = create_doc_asset(db, filename, storage_uri, request_id)
        
        # Log audit event
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            sources_json={"filename": filename, "doc_id": doc_asset.id},
            status=AuditStatus.SUCCESS
        )
        
        # Prepare response with optional duplicate warning
        duplicate_warning = None
        if existing_doc:
            duplicate_warning = f"A document with filename '{filename}' already exists (ID: {existing_doc.id}). This upload creates a new record."
        
        return DocUploadResponse(
            request_id=request_id,
            doc_id=doc_asset.id,
            filename=filename,
            message="Document uploaded successfully",
            duplicate_warning=duplicate_warning
        )
        
    except Exception as e:
        logger.error(f"Upload failed (request_id: {request_id}): {e}", exc_info=True)
        
        # Log failed audit event
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            status=AuditStatus.FAILURE,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                request_id=request_id,
                error="Upload failed",
                detail=str(e)
            ).dict()
        )


@router.post("/index", response_model=DocIndexResponse)
async def trigger_indexing(
    request: Optional[DocIndexRequest] = Body(default=None),
    db: Session = Depends(get_db)
):
    """
    Queue document indexing to Vertex AI Search via the worker.
    Indexes domain-classified docs with gs:// storage URIs. Optionally restrict to doc_id.
    """
    request_id = generate_request_id()
    doc_id = request.doc_id if request else None
    docs = get_pending_gcs_docs(db, doc_id)
    triggered = len(docs)
    succeeded = 0
    failed = 0
    details = []

    for doc in docs:
        try:
            job_id = enqueue_index_job(db, doc, request_id)
            succeeded += 1
            details.append({"doc_id": doc.id, "filename": doc.filename, "status": "indexing", "job_id": job_id, "error": None})
        except Exception as exc:
            update_doc_indexed_status(db, doc, IndexedStatus.FAILED, last_error=str(exc))
            failed += 1
            details.append({"doc_id": doc.id, "filename": doc.filename, "status": "failed", "error": str(exc)})

    create_audit_event(
        db=db,
        module=AuditModule.MODULE_A,
        request_id=request_id,
        sources_json={"triggered": triggered, "succeeded": succeeded, "failed": failed},
        status=AuditStatus.SUCCESS if failed == 0 else AuditStatus.FAILURE,
        error=None if failed == 0 else f"{failed} of {triggered} imports failed"
    )

    return DocIndexResponse(
        request_id=request_id,
        triggered=triggered,
        succeeded=succeeded,
        failed=failed,
        details=details
    )


@router.post("/move", response_model=DocMoveResponse)
async def move_document_to_domain(
    request: DocMoveRequest,
    db: Session = Depends(get_db)
):
    """Move a staged document to a selected business-domain bucket."""
    request_id = generate_request_id()
    doc = get_doc_by_id(db, request.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {request.doc_id} not found")

    try:
        source_uri = doc.storage_uri
        target_uri, job_id = move_doc_to_domain(
            db=db,
            doc_asset=doc,
            domain_name=request.domain,
            request_id=request_id,
            archive_staging=request.archive_staging,
        )
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            sources_json={
                "doc_id": doc.id,
                "domain": request.domain,
                "source_uri": source_uri,
                "target_uri": target_uri,
                "index_job_id": job_id,
            },
            status=AuditStatus.SUCCESS,
        )
        return DocMoveResponse(
            request_id=request_id,
            doc_id=doc.id,
            domain=request.domain,
            source_uri=source_uri,
            target_uri=target_uri,
            indexed_status=doc.indexed_status.value,
            index_job_id=job_id,
            message="Document moved and indexing queued",
        )
    except Exception as exc:
        logger.error(f"Document move failed (request_id: {request_id}): {exc}", exc_info=True)
        update_doc_indexed_status(db, doc, IndexedStatus.FAILED, last_error=str(exc))
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            sources_json={"doc_id": doc.id, "domain": request.domain},
            status=AuditStatus.FAILURE,
            error=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                request_id=request_id,
                error="Document move failed",
                detail=str(exc),
            ).dict(),
        )


@router.get("/status", response_model=DocStatusResponse)
async def get_docs_status(
    db: Session = Depends(get_db)
):
    """
    Get status of all documents.
    
    Returns list of documents with their indexing status.
    """
    request_id = generate_request_id()
    
    try:
        docs = get_all_docs(db)
        
        documents = [
            {
                "id": doc.id,
                "filename": doc.filename,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "indexed_status": doc.indexed_status.value,
                "storage_uri": doc.storage_uri,
                "staging_uri": doc.staging_uri,
                "domain": doc.domain,
                "datastore_ref": doc.datastore_ref,
                "index_job_id": doc.index_job_id,
                "last_error": doc.last_error,
                "deleted_at": doc.deleted_at.isoformat() if doc.deleted_at else None
            }
            for doc in docs
        ]
        
        # Log audit event
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            sources_json={"doc_count": len(documents)},
            status=AuditStatus.SUCCESS
        )
        
        return DocStatusResponse(
            request_id=request_id,
            documents=documents
        )
        
    except Exception as e:
        logger.error(f"Status query failed (request_id: {request_id}): {e}", exc_info=True)
        
        # Log failed audit event
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            status=AuditStatus.FAILURE,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                request_id=request_id,
                error="Failed to retrieve document status",
                detail=str(e)
            ).dict()
        )


@router.post("/query", response_model=DocQueryResponse)
async def query_documents(
    request: DocQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Query domain documents with Agent Search grounded generation.
    Enforces no-source/no-answer behavior in the API layer.
    """
    request_id = generate_request_id()
    prompt_hash = hash_prompt(request.query)
    
    try:
        result = query_grounded_domains(request.query, request.domain, request_id)
        citations = [Citation(**citation) for citation in result["citations"]]
        answer = result["answer"] if citations else "Information not found in internal records."

        # Log audit event for the query
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            prompt_hash=prompt_hash,
            sources_json={
                "query": request.query,
                "domain": request.domain,
                "domains_queried": result["domains_queried"],
                "citations_count": len(citations),
                "grounding_score": result["grounding_score"],
            },
            status=AuditStatus.SUCCESS if not result.get("errors") else AuditStatus.FAILURE,
            error="; ".join(result.get("errors", [])) if result.get("errors") else None
        )
        
        return DocQueryResponse(
            request_id=request_id,
            answer=answer,
            citations=citations,
            domains_queried=result["domains_queried"],
            grounding_score=result["grounding_score"],
        )
        
    except Exception as e:
        logger.error(f"Query failed (request_id: {request_id}): {e}", exc_info=True)
        
        # Log failed audit event
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            prompt_hash=prompt_hash,
            status=AuditStatus.FAILURE,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                request_id=request_id,
                error="Query failed",
                detail=str(e)
            ).dict()
        )
