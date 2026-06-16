"""Utility functions for API calls."""
import requests
import os
import logging
from typing import Optional, Dict, Any

# Read API base URL from environment (default for Docker Compose networking)
API_BASE_URL = os.getenv("API_BASE_URL", "http://api-gateway:8000")

logger = logging.getLogger(__name__)


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
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                return error_data
            except:
                return {"error": f"HTTP {e.response.status_code}: {str(e)}"}
        return {"error": str(e)}


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
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                return error_data
            except:
                return {"error": f"HTTP {e.response.status_code}: {str(e)}"}
        return {"error": str(e)}


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
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                return error_data
            except:
                return {"error": f"HTTP {e.response.status_code}: {str(e)}"}
        return {"error": str(e)}


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
        if hasattr(e, "response") and e.response is not None:
            try:
                return e.response.json()
            except:
                return {"error": f"HTTP {e.response.status_code}: {str(e)}"}
        return {"error": str(e)}


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
        if hasattr(e, "response") and e.response is not None:
            try:
                return e.response.json()
            except:
                return {"error": f"HTTP {e.response.status_code}: {str(e)}"}
        return {"error": str(e)}


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
        if hasattr(e, "response") and e.response is not None:
            try:
                return e.response.json()
            except:
                return {"error": f"HTTP {e.response.status_code}: {str(e)}"}
        return {"error": str(e)}
