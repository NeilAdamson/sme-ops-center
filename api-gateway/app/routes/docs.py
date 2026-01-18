"""Document management routes (Module A)."""
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    DocQueryRequest,
    DocQueryResponse,
    DocUploadResponse,
    DocStatusResponse,
    ErrorResponse,
    Citation
)
from app.services import (
    generate_request_id,
    hash_prompt,
    save_uploaded_file,
    create_doc_asset,
    create_audit_event,
    get_all_docs,
    check_duplicate_filename
)
from app.models import AuditModule, AuditStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/docs", tags=["docs"])


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
                "datastore_ref": doc.datastore_ref,
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
    Query documents (stub implementation).
    
    Returns refusal message with empty citations until Vertex AI Search is integrated.
    Logs audit event.
    """
    request_id = generate_request_id()
    prompt_hash = hash_prompt(request.query)
    
    # Stub response: refuse if no citations (hard trust rule)
    answer = "Information not found in internal records."
    citations = []
    
    try:
        # Log audit event for the query
        create_audit_event(
            db=db,
            module=AuditModule.MODULE_A,
            request_id=request_id,
            prompt_hash=prompt_hash,
            sources_json={"query": request.query, "citations_count": len(citations)},
            status=AuditStatus.SUCCESS,
            error=None
        )
        
        return DocQueryResponse(
            request_id=request_id,
            answer=answer,
            citations=citations
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
