# API Gateway Service

**FastAPI-based API Gateway for SME Ops-Center**

This service provides the core orchestration, trust enforcement, and audit logging for all business logic.

## Overview

The API Gateway is the single point of entry for all frontend requests. It implements:
- REST API endpoints with OpenAPI documentation
- Database persistence (Postgres)
- Audit logging for all operations
- File upload handling
- Service orchestration (GCS, Redis worker jobs, Agent Search, MCP Bridge)

## Architecture

- **Framework:** FastAPI (Python 3.12)
- **Database:** SQLAlchemy ORM with Alembic migrations
- **API Documentation:** Auto-generated OpenAPI/Swagger docs at `/docs`
- **CORS:** Configured for Streamlit frontend at `localhost:8501`

### Startup Dependencies

The API Gateway service:
- **Waits for Postgres** to be healthy (via Docker Compose health check)
- **Waits for Redis** to be healthy (via Docker Compose health check)
- **Waits for MCP Bridge** to start (via Docker Compose `depends_on`)
- **Runs database migrations** automatically on startup (via `app/migrations.py`)
- **Retries database connection** up to 30 times (2s intervals) before failing

**No manual migration step required** — migrations run automatically when the container starts.

## API Endpoints

### Health & Status

- `GET /health` - Service health check
- `GET /` - Service information
- `GET /gcs/smoke` - GCS smoke test (uploads, verifies, and deletes a test blob)

### Module A: Documents (Ask Your Business)

#### Upload Document
```http
POST /docs/upload
Content-Type: multipart/form-data

file: <file content>
```

**Response:**
```json
{
  "request_id": "uuid",
  "doc_id": 1,
  "filename": "example.pdf",
  "message": "Document uploaded successfully",
  "duplicate_warning": null
}
```

**Duplicate Detection:**
- Checks for existing filename (non-deleted documents) before saving
- If duplicate found, includes `duplicate_warning` in response (MVP: allows duplicates but warns)
- Example with duplicate:
```json
{
  "duplicate_warning": "A document with filename 'example.pdf' already exists (ID: 1). This upload creates a new record."
}
```

**Functionality:**
- Saves file to local volume (`/app/uploads`) or to the GCS staging bucket at `gs://<staging-bucket>/docs/<request_id>/<filename>` when `STORAGE_BACKEND=gcs`
- GCS uploads are staged only; they are not queryable until moved to a business domain
- Creates `doc_asset` record; logs audit event

#### Get Document Domains
```http
GET /docs/domains
```

Returns the staging bucket and configured business domains from `DOC_DOMAIN_REGISTRY_PATH`. Each domain includes bucket, prefix, Agent Search datastore, search app/engine, and serving config readiness.

#### Move Document To Domain
```http
POST /docs/move
Content-Type: application/json

{
  "doc_id": 1,
  "domain": "compliance",
  "archive_staging": true
}
```

**Functionality:**
- Copies the staged object to `gs://<domain-bucket>/docs/<doc_id>/<filename>`
- Verifies the copied object exists
- Archives or deletes the staging object
- Updates `doc_asset.domain`, `storage_uri`, `datastore_ref`, and lifecycle status
- Queues a Redis worker job to import the document into the matching Agent Search datastore
- If Redis is temporarily unavailable after the copy succeeds, the move still succeeds and returns `indexing_error` so indexing can be retried

#### Browse Document Storage
```http
GET /docs/browse
```

**Functionality:**
- Lists GCS objects under staging (`docs/`, `archive/`) and each business-domain bucket (`docs/`)
- Merges bucket listings with `doc_asset` metadata (filename, status, doc ID, errors)
- Marks GCS objects without a database row as untracked
- Reports database rows whose `storage_uri` was not found in bucket listings as `orphan_docs`
- When `STORAGE_BACKEND=local`, returns groups built from Postgres only (`source: db_only`)

**Response:**
```json
{
  "request_id": "uuid",
  "source": "gcs",
  "groups": [
    {
      "id": "staging",
      "label": "Staging (active)",
      "bucket": "aiops-gc-poc-pilot-uploads-8aukzz",
      "prefix": "docs/",
      "file_count": 1,
      "files": [
        {
          "filename": "example.pdf",
          "uri": "gs://aiops-gc-poc-pilot-uploads-8aukzz/docs/uuid/example.pdf",
          "size": 12345,
          "updated_at": "2026-06-17T12:00:00",
          "doc_id": 5,
          "indexed_status": "staged",
          "domain": null,
          "tracked": true,
          "last_error": null
        }
      ],
      "error": null
    }
  ],
  "orphan_docs": []
}
```

#### Get Document Status
```http
GET /docs/status
```

**Response:**
```json
{
  "request_id": "uuid",
  "documents": [
    {
      "id": 1,
      "filename": "example.pdf",
      "uploaded_at": "2026-01-18T15:00:00Z",
      "indexed_status": "ready",
      "storage_uri": "gs://aiops-gc-poc-pilot-compliance-hz2xah/docs/7/example.pdf",
      "staging_uri": null,
      "domain": "compliance",
      "datastore_ref": "aiops-gc-poc-pilot-compliance-store",
      "index_job_id": "uuid",
      "last_error": null,
      "deleted_at": null
    }
  ]
}
```

#### Query Documents
```http
POST /docs/query
Content-Type: application/json

{
  "query": "What is our refund policy?",
  "domain": "compliance"
}
```

Use `"domain": "all"` to fan out across configured domain engines.

**Response:**
```json
{
  "request_id": "uuid",
  "answer": "Grounded answer text...",
  "citations": [
    {
      "doc_name": "example.pdf",
      "snippet": "Source snippet...",
      "page_or_section": "2",
      "uri_or_id": "gs://domain-bucket/docs/7/example.pdf",
      "domain": "compliance"
    }
  ],
  "domains_queried": ["compliance"],
  "grounding_score": 1.0
}
```

**Functionality:**
- Calls Agent Search grounded generation using the selected domain serving config
- Returns refusal message when citations are empty (hard trust rule: no source = no answer)
- Logs audit event with prompt hash

#### Trigger Indexing
```http
POST /docs/index
Content-Type: application/json

{}
```
or `{"doc_id": 1}` to index a specific document.

**Response:** `request_id`, `triggered`, `succeeded`, `failed`, `details[]` (per-doc status).

**Functionality:** Queues eligible classified/failed domain docs with `gs://` URIs for worker import into Agent Search; worker updates `indexed_status` to READY or FAILED.

#### GCS Smoke Test
```http
GET /gcs/smoke
```

**Response:**
```json
{
  "ok": true,
  "bucket": "<GCS_BUCKET_NAME from .env>",
  "object": "smoke/<uuid>.txt",
  "request_id": "uuid"
}
```

**Functionality:**
- Uploads a small test blob to Google Cloud Storage
- Verifies the blob exists (metadata check)
- Deletes the test blob
- Returns success status with bucket and object information
- Useful for testing GCS connectivity and credentials

**Requirements:**
- `GOOGLE_APPLICATION_CREDENTIALS` environment variable must be set
- `GCS_BUCKET_NAME` environment variable must be set
- GCP service account must have Storage Object Admin permissions on the bucket

### Future Endpoints (Not Yet Implemented)

- `POST /inbox/upload` - Upload email for triage (Module B)
- `POST /inbox/process/{id}` - Process email (Module B)
- `GET /inbox/queue` - Get inbox queue (Module B)
- `POST /finance/query` - Query Xero finance data (Module C)
- `GET /audit` - Admin audit log query

## Database

### Tables

#### doc_asset
Stores metadata about uploaded documents.

- `id` - Primary key
- `filename` - Original filename
- `storage_uri` - Path to stored file
- `uploaded_at` - Upload timestamp
- `staging_uri` - Original staged GCS object when applicable
- `domain` - Business document domain (`operations`, `compliance`, `finance`)
- `indexed_status` - Lifecycle status: `pending`, `staged`, `classified`, `moving`, `indexing`, `ready`, `failed`, `archived`
- `datastore_ref` - Vertex AI Search datastore reference (when indexed)
- `index_job_id` - Last Redis worker import job id
- `last_error` - Last lifecycle/indexing error
- `deleted_at` - Soft delete timestamp

#### audit_event
Logs all queries, tool calls, and decisions for auditability.

- `id` - Primary key
- `ts` - Timestamp
- `module` - Module identifier: `module_a`, `module_b`, `module_c`, `admin`, `system`
- `request_id` - UUID for request tracing
- `user_id` - User identifier (optional)
- `session_id` - Session identifier (optional)
- `prompt_hash` - Hash of user prompt (for queries)
- `sources_json` - Retrieved sources/citations (JSON)
- `tool_calls_json` - MCP tool calls made (JSON)
- `decision_json` - Approval/rejection decisions (JSON)
- `status` - Status: `success`, `failure`, `pending`
- `error` - Error message (if status is failure)

### Migrations

- **Tool:** Alembic
- **Location:** `migrations/versions/`
- **Auto-run:** Migrations run automatically on container startup
- **Status:** Initial migration creates `doc_asset` and `audit_event` tables

## Development

### Project Structure

```
api-gateway/
├── app/
│   ├── __init__.py
│   ├── database.py          # Database connection and session
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic request/response models
│   ├── services.py          # Business logic
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── docs.py          # Module A routes
│   │   └── gcs.py           # GCS smoke test routes
│   └── migrations.py        # Migration runner
├── migrations/
│   ├── env.py               # Alembic environment
│   └── versions/            # Migration files
├── alembic.ini              # Alembic configuration
├── main.py                  # FastAPI application
└── requirements.txt         # Python dependencies
```

### Dependencies

- `fastapi==0.109.0` - Web framework
- `uvicorn[standard]==0.27.0` - ASGI server
- `sqlalchemy==2.0.23` - ORM
- `alembic==1.12.1` - Database migrations
- `psycopg2-binary==2.9.9` - PostgreSQL driver
- `python-multipart==0.0.6` - File upload support
- `python-dotenv==1.0.0` - Environment variable management
- `google-cloud-storage==2.14.0` - Google Cloud Storage client library

### Running Locally

1. **Set environment variables:**
```bash
export DATABASE_URL=postgresql://smeops:change-me@localhost:5432/smeops
```

2. **Run migrations:**
```bash
cd api-gateway
alembic upgrade head
```

3. **Start server:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### API Documentation

When the service is running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Configuration

### Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string (for future queue integration)
- `MCP_BRIDGE_URL` - MCP Bridge service URL (default: http://mcp-bridge:3000)
- `UPLOADS_DIR` - Directory for uploaded files (default: /app/uploads)
- `CORS_ORIGINS` - Allowed CORS origins (default: http://localhost:8501)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to GCP service account JSON (default: /run/secrets/gcp-sa.json)
- `GCS_BUCKET_NAME` - GCS bucket name (from `.env`; required when `STORAGE_BACKEND=gcs`)
- `STORAGE_BACKEND` - `local` or `gcs` (from `.env`)
- `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_PROJECT_NUMBER`, `DISCOVERY_ENGINE_LOCATION` - Required for Agent Search import/query paths
- `DOC_DOMAIN_REGISTRY_PATH` - JSON registry for staging/domain buckets, data stores, engines, and serving configs
- `DATA_STORE_ID`, `ENGINE_ID` - Legacy single-store values only; current domain flow should use the registry

### Volume Mounts

- `./api-gateway:/app` - Source code (development)
- `uploads:/app/uploads` - Named volume for file persistence
- `sessions:/app/sessions` - Named volume for session data
- `./secrets/aiops-gc-poc-pilot__aiops-gc-app-key.json:/run/secrets/gcp-sa.json:ro` - GCP service account credentials (read-only; from GC-Build.ps1)

## Security

- ✅ All containers run as non-root user (UID 1000)
- ✅ Audit logging for all operations
- ✅ CORS restricted to frontend origin
- ✅ Request ID generation for traceability
- ✅ Prompt hashing for privacy (audit logs)

## Testing

### Manual API Testing

```bash
# Health check
curl http://localhost:8000/health

# Upload document
curl -X POST "http://localhost:8000/docs/upload" \
  -F "file=@example.pdf"

# Get status
curl http://localhost:8000/docs/status

# Query domain RAG
curl -X POST "http://localhost:8000/docs/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "domain": "compliance"}'

# GCS smoke test
curl http://localhost:8000/gcs/smoke
```

### Database Verification

```bash
# Connect to Postgres
docker exec -it sme-postgres psql -U smeops -d smeops

# Check tables
\dt

# Query documents
SELECT * FROM doc_asset;

# Query audit events
SELECT * FROM audit_event ORDER BY ts DESC LIMIT 10;
```

## Google Cloud Storage Integration

The API Gateway supports Google Cloud Storage for document storage. This is configured via environment variables and Docker Compose volume mounts.

### Setup

1. **Run `.\Scripts\GC-Build.ps1`** to create project, bucket, service account, and key (saved to `secrets/`)
2. **Set `.env`**: `STORAGE_BACKEND=gcs`, `GCS_BUCKET_NAME=<staging bucket from gc-foundation.json>`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_PROJECT_NUMBER`, `DOC_DOMAIN_REGISTRY_PATH`
3. **Credentials**: Mounted from `./secrets/aiops-gc-poc-pilot__aiops-gc-app-key.json` (docker-compose); `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-sa.json`
4. **Agent Search domain resources**: Run `.\Scripts\GC-Provision-Domain-RAG.ps1` to create/verify domain data stores and search apps, then update `secrets/domain-registry.json`

### Testing

Test GCS connectivity using the smoke test endpoint:
```bash
curl http://localhost:8000/gcs/smoke
```

This will upload, verify, and delete a test blob, confirming that:
- Credentials are correctly mounted
- Service account has proper permissions
- GCS bucket is accessible

## Next Steps

1. **Module A Hardening**
   - Add automated tests for move/index/query/refusal behavior
   - Add retry/backoff around long-running import operations
   - Add soft delete, reindex, and export endpoints

2. **Module B Implementation**
   - Email upload and parsing
   - Classification and extraction
   - Approval workflow

3. **Module C Implementation**
   - Xero OAuth integration
   - MCP Bridge integration
   - Finance query endpoints
