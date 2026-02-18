"""GCS smoke test routes."""
import logging
import os
import uuid
from fastapi import APIRouter, HTTPException
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from app.services import generate_request_id
from app.schemas import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gcs", tags=["gcs"])


@router.get("/smoke")
async def gcs_smoke_test():
    """
    GCS smoke test endpoint.
    
    Uploads a small text blob to gs://<bucket>/smoke/<uuid>.txt,
    verifies it exists, deletes it, and returns success status.
    """
    request_id = generate_request_id()
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    
    if not bucket_name:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                request_id=request_id,
                error="GCS_BUCKET_NAME not configured",
                detail="GCS_BUCKET_NAME environment variable is required"
            ).dict()
        )
    
    # Generate unique object name
    object_name = f"smoke/{uuid.uuid4()}.txt"
    test_content = f"GCS smoke test - request_id: {request_id}\nTimestamp: {uuid.uuid4()}"
    
    try:
        # Initialize GCS client
        # GOOGLE_APPLICATION_CREDENTIALS should be set in environment
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        # Upload the blob
        logger.info(f"Uploading test blob: gs://{bucket_name}/{object_name} (request_id: {request_id})")
        blob.upload_from_string(test_content, content_type="text/plain")
        
        # Verify it exists (get metadata)
        blob.reload()
        if not blob.exists():
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    request_id=request_id,
                    error="Upload verification failed",
                    detail="Blob was uploaded but does not exist"
                ).dict()
            )
        
        logger.info(f"Verified blob exists: gs://{bucket_name}/{object_name} (size: {blob.size} bytes)")
        
        # Delete the blob
        blob.delete()
        
        # Verify deletion
        if blob.exists():
            logger.warning(f"Blob still exists after deletion: gs://{bucket_name}/{object_name}")
            # Don't fail - just log a warning
        
        logger.info(f"GCS smoke test completed successfully (request_id: {request_id})")
        
        return {
            "ok": True,
            "bucket": bucket_name,
            "object": object_name,
            "request_id": request_id
        }
        
    except GoogleCloudError as e:
        logger.error(f"GCS error during smoke test (request_id: {request_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                request_id=request_id,
                error="GCS operation failed",
                detail=str(e)
            ).dict()
        )
    except Exception as e:
        logger.error(f"Unexpected error during GCS smoke test (request_id: {request_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                request_id=request_id,
                error="Smoke test failed",
                detail=str(e)
            ).dict()
        )
