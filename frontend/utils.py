"""Utility functions for API calls."""
import requests
import os
import logging
from typing import Optional, Dict, Any

# Read API base URL from environment (default for Docker Compose networking)
API_BASE_URL = os.getenv("API_BASE_URL", "http://api-gateway:8000")

logger = logging.getLogger(__name__)


def _error_payload(exc: requests.exceptions.RequestException, fallback: str) -> Dict[str, Any]:
    """Normalize API error payloads for Streamlit success/error checks."""
    response = getattr(exc, "response", None)
    if response is None:
        return {"error": str(exc)}
    try:
        data = response.json()
    except Exception:
        return {"error": f"HTTP {response.status_code}: {str(exc)}"}

    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        return {
            "error": detail.get("error") or fallback,
            "detail": detail.get("detail"),
            "request_id": detail.get("request_id"),
            "raw": data,
        }
    if isinstance(detail, str):
        return {"error": fallback, "detail": detail, "raw": data}
    if isinstance(data, dict) and data.get("error"):
        return data
    return {"error": fallback, "raw": data}


def upload_document(file_bytes: bytes, filename: str) -> Optional[Dict[str, Any]]:
    """Upload a document to the API Gateway."""
    try:
        files = {"file": (filename, file_bytes)}
        response = requests.post(
            f"{API_BASE_URL}/docs/upload",
            files=files,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Upload failed: {e}")
        return _error_payload(e, "Upload failed")


def get_document_status() -> Optional[Dict[str, Any]]:
    """Get status of all uploaded documents."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/docs/status",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Status query failed: {e}")
        return _error_payload(e, "Status query failed")


def get_doc_browse() -> Optional[Dict[str, Any]]:
    """Browse document storage grouped by staging and business domains."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/docs/browse",
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Browse query failed: {e}")
        return _error_payload(e, "Browse query failed")


def query_documents(query: str, domain: str = "all") -> Optional[Dict[str, Any]]:
    """Query documents."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/docs/query",
            json={"query": query, "domain": domain},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Query failed: {e}")
        return _error_payload(e, "Query failed")


def get_storage_config() -> Optional[Dict[str, Any]]:
    """Get storage backend configuration."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/docs/config",
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Config query failed: {e}")
        # Return default if error (fallback to local)
        return {"storage_backend": "local"}


def get_doc_domains() -> Optional[Dict[str, Any]]:
    """Get configured document domains."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/docs/domains",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Domain config query failed: {e}")
        return _error_payload(e, "Domain config query failed")


def move_document(doc_id: int, domain: str, archive_staging: bool = True) -> Optional[Dict[str, Any]]:
    """Move a staged document into a domain bucket."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/docs/move",
            json={
                "doc_id": doc_id,
                "domain": domain,
                "archive_staging": archive_staging,
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Document move failed: {e}")
        return _error_payload(e, "Document move failed")


def trigger_index(doc_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Queue indexing for one document or all eligible documents."""
    try:
        payload = {"doc_id": doc_id} if doc_id is not None else {}
        response = requests.post(
            f"{API_BASE_URL}/docs/index",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Index queue request failed: {e}")
        return _error_payload(e, "Index queue request failed")


def delete_document(doc_id: int, hard_delete: bool = False, delete_storage: bool = True) -> Optional[Dict[str, Any]]:
    """Delete a document asset from DB and optionally storage."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/docs/{doc_id}/delete",
            json={
                "hard_delete": hard_delete,
                "delete_storage": delete_storage,
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Delete failed: {e}")
        return _error_payload(e, "Document delete failed")


def delete_storage_file(storage_uri: str) -> Optional[Dict[str, Any]]:
    """Delete an untracked file directly from storage."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/docs/delete-storage",
            json={"storage_uri": storage_uri},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Storage delete failed: {e}")
        return _error_payload(e, "Storage delete failed")


