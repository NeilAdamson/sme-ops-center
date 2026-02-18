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


class DocQueryRequest(BaseModel):
    """Request schema for document query."""
    query: str


class DocQueryResponse(BaseModel):
    """Response schema for document query."""
    request_id: str
    answer: str
    citations: List[Citation] = []


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
