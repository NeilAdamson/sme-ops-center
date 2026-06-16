#!/usr/bin/env python3
"""Background worker for document indexing jobs."""
import json
import time
import logging
import os

import redis
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUEUE_NAME = os.getenv("DOC_INDEX_QUEUE", "doc_index_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://smeops:change-me@postgres:5432/smeops")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "aiops-gc-poc-pilot")
LOCATION = os.getenv("DISCOVERY_ENGINE_LOCATION", "global")

redis_client = redis.from_url(REDIS_URL)
db_engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def update_doc_status(doc_id, status, datastore_ref=None, last_error=None):
    """Update document lifecycle status from the worker."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE doc_asset
                SET indexed_status = CAST(:status AS indexedstatus),
                    datastore_ref = COALESCE(:datastore_ref, datastore_ref),
                    last_error = :last_error,
                    updated_at = now()
                WHERE id = :doc_id
                """
            ),
            {
                "doc_id": doc_id,
                "status": status,
                "datastore_ref": datastore_ref,
                "last_error": last_error,
            },
        )


def import_document(storage_uri, data_store_id, request_id):
    """Import one GCS document into a Discovery Engine datastore."""
    client_options = (
        ClientOptions(api_endpoint=f"{LOCATION}-discoveryengine.googleapis.com")
        if LOCATION != "global"
        else None
    )
    client = discoveryengine.DocumentServiceClient(client_options=client_options)
    parent = client.branch_path(
        project=PROJECT_ID,
        location=LOCATION,
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
    logger.info("Waiting for import operation: %s", operation.operation.name)
    operation.result()
    logger.info("Imported %s into %s (request_id=%s)", storage_uri, data_store_id, request_id)


def process_job(raw_payload):
    """Process one queued indexing job."""
    payload = json.loads(raw_payload)
    doc_id = payload["doc_id"]
    storage_uri = payload["storage_uri"]
    data_store_id = payload["data_store_id"]
    request_id = payload.get("request_id", "")

    try:
        update_doc_status(doc_id, "INDEXING", datastore_ref=data_store_id)
        import_document(storage_uri, data_store_id, request_id)
        update_doc_status(doc_id, "READY", datastore_ref=data_store_id)
    except Exception as exc:
        logger.exception("Index job failed for doc_id=%s", doc_id)
        update_doc_status(doc_id, "FAILED", datastore_ref=data_store_id, last_error=str(exc))


logger.info("Worker started - polling %s", QUEUE_NAME)

# Keep worker running
try:
    while True:
        try:
            item = redis_client.blpop(QUEUE_NAME, timeout=30)
            if item is None:
                logger.debug("Worker heartbeat - no index jobs")
                continue
            _, raw_payload = item
            process_job(raw_payload)
        except redis.RedisError:
            logger.exception("Redis polling failed")
            time.sleep(5)
except KeyboardInterrupt:
    logger.info("Worker shutting down")
