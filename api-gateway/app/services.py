"""Service layer for business logic."""
import os
import uuid
import hashlib
import logging
import json
from pathlib import Path
from typing import Any, Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models import DocAsset, AuditEvent, IndexedStatus, AuditModule, AuditStatus
from app.domain_registry import get_domain, get_domain_registry, get_query_domains

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
    status = IndexedStatus.STAGED if STORAGE_BACKEND == "gcs" else IndexedStatus.PENDING
    doc_asset = DocAsset(
        filename=filename,
        storage_uri=storage_uri,
        staging_uri=storage_uri if STORAGE_BACKEND == "gcs" else None,
        indexed_status=status
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
        DocAsset.indexed_status.in_([IndexedStatus.CLASSIFIED, IndexedStatus.FAILED]),
        DocAsset.domain.isnot(None),
        DocAsset.storage_uri.like("gs://%")
    )
    if doc_id is not None:
        q = q.filter(DocAsset.id == doc_id)
    return q.all()


def update_doc_indexed_status(
    db: Session,
    doc_asset: DocAsset,
    status: IndexedStatus,
    datastore_ref: Optional[str] = None,
    index_job_id: Optional[str] = None,
    last_error: Optional[str] = None
) -> None:
    """Update document indexing status."""
    doc_asset.indexed_status = status
    if datastore_ref is not None:
        doc_asset.datastore_ref = datastore_ref
    if index_job_id is not None:
        doc_asset.index_job_id = index_job_id
    doc_asset.last_error = last_error
    db.commit()
    db.refresh(doc_asset)


def move_doc_to_domain(
    db: Session,
    doc_asset: DocAsset,
    domain_name: str,
    request_id: str,
    archive_staging: bool = True
) -> tuple[str, Optional[str], Optional[str]]:
    """Copy a staged GCS object into a domain bucket and queue indexing."""
    from google.cloud import storage as gcs_storage

    if not doc_asset.storage_uri.startswith("gs://"):
        raise ValueError("Only GCS-backed documents can be moved into domain buckets")

    domain = get_domain(domain_name)
    source_bucket_name, source_object = parse_gcs_uri(doc_asset.storage_uri)
    target_bucket_name = domain["bucket"]
    target_prefix = domain["prefix"]
    safe_filename = Path(doc_asset.filename).name
    target_object = f"{target_prefix}{doc_asset.id}/{safe_filename}"
    target_uri = f"gs://{target_bucket_name}/{target_object}"

    update_doc_indexed_status(db, doc_asset, IndexedStatus.MOVING)

    client = gcs_storage.Client()
    source_bucket = client.bucket(source_bucket_name)
    source_blob = source_bucket.blob(source_object)
    if not source_blob.exists():
        raise FileNotFoundError(f"Source object does not exist: {doc_asset.storage_uri}")

    target_bucket = client.bucket(target_bucket_name)
    copied_blob = source_bucket.copy_blob(source_blob, target_bucket, target_object)
    copied_blob.reload()
    if not copied_blob.exists():
        raise RuntimeError(f"Copied object was not found at {target_uri}")

    archive_uri = None
    if archive_staging:
        archive_prefix = get_domain_registry()["staging"].get("archive_prefix", "archive/")
        archive_object = f"{archive_prefix}{doc_asset.id}/{safe_filename}"
        source_bucket.copy_blob(source_blob, source_bucket, archive_object)
        source_blob.delete()
        archive_uri = f"gs://{source_bucket_name}/{archive_object}"

    doc_asset.domain = domain["domain"]
    doc_asset.storage_uri = target_uri
    doc_asset.datastore_ref = domain.get("data_store_id") or None
    doc_asset.indexed_status = IndexedStatus.CLASSIFIED
    doc_asset.last_error = None
    db.commit()
    db.refresh(doc_asset)

    try:
        job_id = enqueue_index_job(db, doc_asset, request_id)
        return target_uri, job_id, None
    except Exception as exc:
        error = f"Document moved, but indexing was not queued: {exc}"
        logger.warning(error)
        update_doc_indexed_status(db, doc_asset, IndexedStatus.FAILED, last_error=error)
        return target_uri, None, error


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    """Parse a gs:// URI into bucket and object name."""
    if not uri.startswith("gs://"):
        raise ValueError(f"Not a GCS URI: {uri}")
    path = uri[5:]
    bucket, _, object_name = path.partition("/")
    if not bucket or not object_name:
        raise ValueError(f"GCS URI must include bucket and object: {uri}")
    return bucket, object_name


def enqueue_index_job(db: Session, doc_asset: DocAsset, request_id: str) -> Optional[str]:
    """Queue a worker job to import a document into the domain datastore."""
    import redis

    if not doc_asset.domain:
        raise ValueError("Document must have a domain before indexing")
    domain = get_domain(doc_asset.domain)
    data_store_id = domain.get("data_store_id")
    if not data_store_id:
        raise ValueError(f"Domain {doc_asset.domain} has no data_store_id configured")

    job_id = str(uuid.uuid4())
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    payload = {
        "job_id": job_id,
        "request_id": request_id,
        "doc_id": doc_asset.id,
        "domain": doc_asset.domain,
        "storage_uri": doc_asset.storage_uri,
        "data_store_id": data_store_id,
    }
    client = redis.from_url(redis_url)
    client.rpush("doc_index_jobs", json.dumps(payload))
    update_doc_indexed_status(
        db,
        doc_asset,
        IndexedStatus.INDEXING,
        datastore_ref=data_store_id,
        index_job_id=job_id,
    )
    return job_id


def trigger_vertex_import(storage_uri: str, request_id: str = "") -> tuple[bool, Optional[str]]:
    """
    Trigger Vertex AI Search (Discovery Engine) document import from GCS.
    Returns (success, error_message). On success, error_message is None.
    Requires: GOOGLE_CLOUD_PROJECT, DISCOVERY_ENGINE_LOCATION, DATA_STORE_ID.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    project_number = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER") or project_id
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
        parent = (
            f"projects/{project_number}/locations/{location}/collections/"
            f"default_collection/dataStores/{data_store_id}/branches/default_branch"
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


def query_grounded_domain(query: str, domain: dict, request_id: str) -> dict:
    """Generate an Agent Search answer for one configured domain."""
    import requests
    import google.auth
    from google.auth.transport.requests import Request

    serving_config = domain.get("serving_config")
    if not serving_config:
        return {
            "domain": domain["domain"],
            "answer": "",
            "citations": [],
            "grounding_score": None,
            "error": "Domain has no serving_config configured",
        }

    registry = get_domain_registry()
    project_id = registry["project_id"]
    endpoint = f"https://discoveryengine.googleapis.com/v1/{serving_config}:answer"

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
        "x-goog-user-project": project_id,
    }
    body = {
        "query": {"text": query},
        "userPseudoId": f"sme-ops-{request_id}",
        "answerGenerationSpec": {
            "includeCitations": True,
            "ignoreAdversarialQuery": True,
            "ignoreNonAnswerSeekingQuery": True,
            "promptSpec": {
                "preamble": (
                    "Answer only from the provided internal records. "
                    "If the records do not support the answer, say exactly: "
                    "Information not found in internal records."
                )
            },
        },
        "searchSpec": {
            "searchParams": {
                "maxReturnResults": int(os.getenv("DOCS_MAX_RESULTS", "5")),
            }
        },
    }

    response = requests.post(endpoint, headers=headers, data=json.dumps(body), timeout=45)
    if response.status_code >= 400:
        return {
            "domain": domain["domain"],
            "answer": "",
            "citations": [],
            "grounding_score": None,
            "error": f"Agent Search query failed: HTTP {response.status_code}: {response.text[:500]}",
        }

    answer = (response.json().get("answer") or {})
    answer_text = (answer.get("answerText") or "").strip()
    skipped_reasons = answer.get("answerSkippedReasons") or []
    references = answer.get("references") or []
    citations_meta = answer.get("citations") or []
    cited_reference_ids = {
        source.get("referenceId")
        for citation in citations_meta
        for source in citation.get("sources", [])
        if source.get("referenceId")
    }

    if skipped_reasons and not references:
        return {
            "domain": domain["domain"],
            "answer": "",
            "citations": [],
            "grounding_score": None,
            "error": None,
        }

    citations = []
    for reference_index, reference in enumerate(references):
        reference_id = reference.get("id") or reference.get("referenceId") or str(reference_index)
        if cited_reference_ids and reference_id not in cited_reference_ids:
            continue
        chunk_info = reference.get("chunkInfo", {}) or {}
        document_metadata = chunk_info.get("documentMetadata", {}) or {}
        uri = document_metadata.get("uri") or reference.get("uri")
        snippet_text = (
            chunk_info.get("content")
            or reference.get("content")
            or answer_text
        )
        snippet = snippet_text.strip() if snippet_text else ""
        if not snippet:
            continue
        citations.append({
            "doc_name": document_metadata.get("title") or Path(uri or "").name or "Internal document",
            "snippet": snippet,
            "page_or_section": document_metadata.get("pageIdentifier"),
            "uri_or_id": uri or document_metadata.get("document"),
            "domain": domain["domain"],
        })

    return {
        "domain": domain["domain"],
        "answer": answer_text,
        "citations": citations,
        "grounding_score": 1.0 if citations else None,
        "error": None,
    }


def query_grounded_domains(query: str, domain_name: str, request_id: str) -> dict:
    """Query one or more domain engines and merge cited responses."""
    domains = get_query_domains(domain_name)
    results = [query_grounded_domain(query, domain, request_id) for domain in domains]
    threshold = float(os.getenv("DOCS_SEMANTIC_THRESHOLD", "0.7"))

    accepted = []
    for result in results:
        if result.get("error") or not result.get("citations"):
            continue
        score = result.get("grounding_score")
        if score is not None and score < threshold:
            continue
        if not result.get("answer"):
            continue
        accepted.append(result)

    if not accepted:
        return {
            "answer": "Information not found in internal records.",
            "citations": [],
            "domains_queried": [domain["domain"] for domain in domains],
            "grounding_score": None,
            "errors": [result["error"] for result in results if result.get("error")],
        }

    if domain_name.lower() == "all":
        answer = "\n\n".join(
            f"{result['domain'].title()}: {result['answer']}"
            for result in accepted
        )
    else:
        answer = accepted[0]["answer"]

    citations = []
    for result in accepted:
        citations.extend(result["citations"])
    scores = [
        result["grounding_score"] for result in accepted
        if result.get("grounding_score") is not None
    ]
    return {
        "answer": answer,
        "citations": citations,
        "domains_queried": [domain["domain"] for domain in domains],
        "grounding_score": max(scores) if scores else None,
        "errors": [],
    }


def _doc_to_browse_file_item(doc: DocAsset, uri: Optional[str] = None) -> dict[str, Any]:
    """Build a browse file item from a doc_asset row."""
    return {
        "filename": doc.filename,
        "uri": uri or doc.storage_uri,
        "size": None,
        "updated_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "doc_id": doc.id,
        "indexed_status": doc.indexed_status.value,
        "domain": doc.domain,
        "tracked": True,
        "last_error": doc.last_error,
    }


def _blob_to_browse_file_item(
    blob: Any,
    bucket_name: str,
    uri_map: dict[str, DocAsset],
) -> dict[str, Any]:
    """Build a browse file item from a GCS blob, merging doc_asset metadata when matched."""
    uri = f"gs://{bucket_name}/{blob.name}"
    doc = uri_map.get(uri)
    filename = doc.filename if doc else Path(blob.name).name
    return {
        "filename": filename,
        "uri": uri,
        "size": blob.size,
        "updated_at": blob.updated.isoformat() if blob.updated else None,
        "doc_id": doc.id if doc else None,
        "indexed_status": doc.indexed_status.value if doc else None,
        "domain": doc.domain if doc else None,
        "tracked": doc is not None,
        "last_error": doc.last_error if doc else None,
    }


def _list_gcs_prefix_files(
    bucket_name: str,
    prefix: str,
    uri_map: dict[str, DocAsset],
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """List GCS objects under a prefix and merge with doc_asset metadata."""
    from google.cloud import storage as gcs_storage
    from google.cloud.exceptions import GoogleCloudError

    try:
        client = gcs_storage.Client()
        bucket = client.bucket(bucket_name)
        files = []
        for blob in bucket.list_blobs(prefix=prefix):
            if blob.name.endswith("/"):
                continue
            files.append(_blob_to_browse_file_item(blob, bucket_name, uri_map))
        files.sort(key=lambda item: item["filename"].lower())
        return files, None
    except GoogleCloudError as exc:
        logger.error(f"GCS list failed for gs://{bucket_name}/{prefix}: {exc}", exc_info=True)
        return [], str(exc)
    except Exception as exc:
        logger.error(f"Unexpected GCS list error for gs://{bucket_name}/{prefix}: {exc}", exc_info=True)
        return [], str(exc)


def _build_db_only_browse_groups(db: Session, registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Build browse groups from Postgres when storage backend is local."""
    docs = get_all_docs(db)
    staging_docs = [doc for doc in docs if not doc.domain]
    groups: list[dict[str, Any]] = [
        {
            "id": "staging",
            "label": "Staging (active)",
            "bucket": registry["staging"].get("bucket", ""),
            "prefix": registry["staging"].get("prefix", "docs/"),
            "file_count": len(staging_docs),
            "files": [_doc_to_browse_file_item(doc) for doc in staging_docs],
            "error": None,
        }
    ]

    archive_docs = [
        doc for doc in docs
        if doc.staging_uri and doc.staging_uri != doc.storage_uri
    ]
    groups.append({
        "id": "staging_archive",
        "label": "Staging (archive)",
        "bucket": registry["staging"].get("bucket", ""),
        "prefix": registry["staging"].get("archive_prefix", "archive/"),
        "file_count": len(archive_docs),
        "files": [_doc_to_browse_file_item(doc, doc.staging_uri) for doc in archive_docs],
        "error": None,
    })

    for domain in registry["domains"]:
        domain_docs = [doc for doc in docs if doc.domain == domain["domain"]]
        groups.append({
            "id": domain["domain"],
            "label": domain["display_name"],
            "bucket": domain["bucket"],
            "prefix": domain["prefix"],
            "file_count": len(domain_docs),
            "files": [_doc_to_browse_file_item(doc) for doc in domain_docs],
            "error": None,
        })
    return groups


def browse_document_storage(db: Session) -> dict[str, Any]:
    """
    List document storage grouped by staging and business domains.
    Merges GCS bucket listings with doc_asset metadata when STORAGE_BACKEND=gcs.
    """
    registry = get_domain_registry()
    docs = get_all_docs(db)
    uri_map: dict[str, DocAsset] = {}
    for doc in docs:
        uri_map[doc.storage_uri] = doc
        if doc.staging_uri:
            uri_map.setdefault(doc.staging_uri, doc)

    if STORAGE_BACKEND == "gcs":
        source = "gcs"
        groups: list[dict[str, Any]] = []
        staging = registry["staging"]
        staging_bucket = staging["bucket"]

        active_files, active_error = _list_gcs_prefix_files(
            staging_bucket, staging["prefix"], uri_map
        )
        groups.append({
            "id": "staging",
            "label": "Staging (active)",
            "bucket": staging_bucket,
            "prefix": staging["prefix"],
            "file_count": len(active_files),
            "files": active_files,
            "error": active_error,
        })

        archive_prefix = staging.get("archive_prefix", "archive/")
        archive_files, archive_error = _list_gcs_prefix_files(
            staging_bucket, archive_prefix, uri_map
        )
        groups.append({
            "id": "staging_archive",
            "label": "Staging (archive)",
            "bucket": staging_bucket,
            "prefix": archive_prefix,
            "file_count": len(archive_files),
            "files": archive_files,
            "error": archive_error,
        })

        for domain in registry["domains"]:
            domain_files, domain_error = _list_gcs_prefix_files(
                domain["bucket"], domain["prefix"], uri_map
            )
            groups.append({
                "id": domain["domain"],
                "label": domain["display_name"],
                "bucket": domain["bucket"],
                "prefix": domain["prefix"],
                "file_count": len(domain_files),
                "files": domain_files,
                "error": domain_error,
            })
    else:
        source = "db_only"
        groups = _build_db_only_browse_groups(db, registry)

    listed_uris = {
        file_item["uri"]
        for group in groups
        for file_item in group["files"]
    }
    orphan_docs = [
        {
            "doc_id": doc.id,
            "filename": doc.filename,
            "storage_uri": doc.storage_uri,
            "indexed_status": doc.indexed_status.value,
            "domain": doc.domain,
        }
        for doc in docs
        if doc.storage_uri.startswith("gs://") and doc.storage_uri not in listed_uris
    ]

    return {
        "source": source,
        "groups": groups,
        "orphan_docs": orphan_docs,
    }


def delete_local_file(storage_uri: str) -> bool:
    """Delete a local file from the uploads directory."""
    if not storage_uri:
        return False
    # If storage_uri starts with "uploads/", extract the filename.
    filename = storage_uri
    if storage_uri.startswith("uploads/"):
        filename = storage_uri[len("uploads/"):]
    elif "/" in storage_uri:
        filename = Path(storage_uri).name
        
    local_path = UPLOADS_DIR / filename
    try:
        if local_path.exists():
            local_path.unlink()
            logger.info(f"Deleted local file: {local_path}")
            return True
        else:
            logger.warning(f"Local file does not exist: {local_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete local file {local_path}: {e}")
        return False


def delete_gcs_file(storage_uri: str) -> bool:
    """Delete a blob from GCS."""
    if not storage_uri or not storage_uri.startswith("gs://"):
        return False
    try:
        from google.cloud import storage as gcs_storage
        bucket_name, object_name = parse_gcs_uri(storage_uri)
        client = gcs_storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        if blob.exists():
            blob.delete()
            logger.info(f"Deleted GCS blob: {storage_uri}")
            return True
        else:
            logger.warning(f"GCS blob does not exist: {storage_uri}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete GCS blob {storage_uri}: {e}")
        return False


def delete_document(
    db: Session,
    doc_id: int,
    hard_delete: bool = False,
    delete_storage: bool = True
) -> tuple[bool, bool, str, str]:
    """
    Delete a document asset.
    - If hard_delete is True: deletes row from DB completely.
    - If hard_delete is False: soft deletes row in DB by setting deleted_at = datetime.utcnow().
    - If delete_storage is True: deletes the storage file (local filesystem or GCS blob).
    Returns (db_deleted, storage_deleted, filename, message).
    """
    if hard_delete:
        doc = db.query(DocAsset).filter(DocAsset.id == doc_id).first()
    else:
        doc = db.query(DocAsset).filter(
            DocAsset.id == doc_id,
            DocAsset.deleted_at.is_(None)
        ).first()
        
    if not doc:
        return False, False, "", "Document not found"
        
    filename = doc.filename
    storage_uri = doc.storage_uri
    staging_uri = doc.staging_uri
    
    storage_deleted = False
    if delete_storage:
        # Delete main storage blob/file
        if storage_uri.startswith("gs://"):
            storage_deleted = delete_gcs_file(storage_uri)
        else:
            storage_deleted = delete_local_file(storage_uri)
            
        # Delete staging blob/file if it exists and is different from storage_uri
        if staging_uri and staging_uri != storage_uri:
            if staging_uri.startswith("gs://"):
                delete_gcs_file(staging_uri)
            else:
                delete_local_file(staging_uri)
                
    db_deleted = False
    if hard_delete:
        db.delete(doc)
        db.commit()
        db_deleted = True
        message = f"Document '{filename}' permanently deleted from database"
    else:
        from datetime import datetime
        doc.deleted_at = datetime.utcnow()
        db.commit()
        db_deleted = True
        message = f"Document '{filename}' soft-deleted"
        
    return db_deleted, storage_deleted, filename, message

