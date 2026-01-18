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


def query_documents(query: str) -> Optional[Dict[str, Any]]:
    """Query documents."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/docs/query",
            json={"query": query},
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
