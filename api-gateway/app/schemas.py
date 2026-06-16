"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class Citation(BaseModel):
    """Citation structure for document queries."""
    doc_name: str
    snippet: str
    page_or_section: Optional[str] = None
    uri_or_id: Optional[str] = None
    domain: Optional[str] = None


class DocQueryRequest(BaseModel):
    """Request schema for document query."""
    query: str
    domain: str = "all"


class DocQueryResponse(BaseModel):
    """Response schema for document query."""
    request_id: str
    answer: str
    citations: List[Citation] = []
    domains_queried: List[str] = []
    grounding_score: Optional[float] = None


class DocUploadResponse(BaseModel):
    """Response schema for document upload."""
    request_id: str
    doc_id: int
    filename: str
    message: str
    duplicate_warning: Optional[str] = None  # Warning if duplicate filename detected


class DocStatusResponse(BaseModel):
    """Response schema for document status."""
    request_id: str
    documents: List[Dict[str, Any]]


class DocDomainResponse(BaseModel):
    """Response schema for configured document domains."""
    request_id: str
    staging: Dict[str, Any]
    domains: List[Dict[str, Any]]


class DocMoveRequest(BaseModel):
    """Request schema for moving a staged document into a domain bucket."""
    doc_id: int
    domain: str
    archive_staging: bool = True


class DocMoveResponse(BaseModel):
    """Response schema for manual document movement."""
    request_id: str
    doc_id: int
    domain: str
    source_uri: str
    target_uri: str
    indexed_status: str
    index_job_id: Optional[str] = None
    message: str


class DocIndexRequest(BaseModel):
    """Request schema for trigger indexing (optional doc_id to index specific doc)."""
    doc_id: Optional[int] = None  # If provided, index only this doc; else index all PENDING docs in GCS


class DocIndexResponse(BaseModel):
    """Response schema for trigger indexing."""
    request_id: str
    triggered: int
    succeeded: int
    failed: int
    details: List[Dict[str, Any]] = []  # Per-doc results: doc_id, status, error


class ErrorResponse(BaseModel):
    """Error response schema."""
    request_id: str
    error: str
    detail: Optional[str] = None
