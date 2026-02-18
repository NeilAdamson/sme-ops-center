# Milestone 1 Status - Module A APIs (Partial)

## Status: 🟡 In Progress

**Completed Tasks:**
- ✅ Task 1: Database migrations and core tables
- ✅ Task 2: Module A API endpoints (stub implementation)

**Remaining:**
- ⏳ Vertex AI Search query integration (replace query stub with real retrieval)

**Completed (New):**
- ✅ Task 4: GCS smoke test endpoint (Google Cloud Storage integration test)

**Frontend UI Tasks:**
- ✅ Task 1: Environment variable configuration (`API_BASE_URL`)
- ✅ Task 2: End-to-end UI flow (landing page, Docs module)
- ✅ Task 3: Trust surface (Request ID panel)

---

## Task 1: Database Migrations ✅

### Implemented

- **Alembic migration system** configured
- **Initial migration** created with:
  - `doc_asset` table (id, filename, storage_uri, uploaded_at, indexed_status, datastore_ref, deleted_at)
  - `audit_event` table (id, ts, module, user_id, session_id, request_id, prompt_hash, sources_json, tool_calls_json, decision_json, status, error)
- **Auto-migration on startup** via FastAPI startup event
- **Database connection retry logic** to wait for Postgres to be ready
- **Default values** set in database schema:
  - `doc_asset.indexed_status` defaults to `PENDING`
  - `audit_event.status` defaults to `PENDING`

### Files Created
- `api-gateway/app/database.py` - Database connection and session management
- `api-gateway/app/models.py` - SQLAlchemy models with enums
- `api-gateway/app/migrations.py` - Migration runner with retry logic
- `api-gateway/alembic.ini` - Alembic configuration
- `api-gateway/migrations/env.py` - Alembic environment
- `api-gateway/migrations/versions/001_initial_doc_asset_audit_event.py` - Initial migration

### Acceptance Criteria Met
- ✅ Migrations run on container startup
- ✅ Tables persist across container rebuilds (using named volume `pgdata`)
- ✅ All fields from PRD Section 8 implemented
- ✅ Indexes created for performance

---

## Task 2: Module A APIs ✅

### Implemented Endpoints

#### 1. POST /docs/upload
**Purpose:** Upload document files for indexing

**Functionality:**
- Accepts multipart/form-data file upload
- Saves file to local volume (`/app/uploads`) or GCS at `gs://bucket/docs/<request_id>/<filename>` when `STORAGE_BACKEND=gcs`
- Creates `doc_asset` record; when GCS, triggers Vertex AI Search import and updates `indexed_status` (INDEXING → READY or FAILED)
- Creates `audit_event` for traceability
- Returns `request_id`, `doc_id`, `filename`, success message

**Request:**
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
- Checks database for existing filename (non-deleted documents) before upload
- If duplicate found, includes `duplicate_warning` field in response
- **Allows duplicate uploads** (MVP behavior) but provides warning
- Example with duplicate:
```json
{
  "request_id": "uuid",
  "doc_id": 2,
  "filename": "example.pdf",
  "message": "Document uploaded successfully",
  "duplicate_warning": "A document with filename 'example.pdf' already exists (ID: 1). This upload creates a new record."
}
```

#### 2. POST /docs/index
**Purpose:** Trigger document indexing to Vertex AI Search for PENDING docs in GCS

**Functionality:**
- Indexes PENDING docs with `gs://` storage URIs (only when `STORAGE_BACKEND=gcs`)
- Optional body: `{"doc_id": 1}` to index a specific doc; omit to index all PENDING docs
- Updates `indexed_status` to READY or FAILED per doc
- Returns `triggered`, `succeeded`, `failed` counts and per-doc details

**Request:**
```http
POST /docs/index
Content-Type: application/json

{}
```
or
```http
POST /docs/index
Content-Type: application/json

{"doc_id": 1}
```

**Response:**
```json
{
  "request_id": "uuid",
  "triggered": 2,
  "succeeded": 2,
  "failed": 0,
  "details": [
    {"doc_id": 1, "filename": "example.pdf", "status": "ready", "error": null}
  ]
}
```

#### 3. GET /docs/status
**Purpose:** Get status of all uploaded documents

**Functionality:**
- Returns list of all non-deleted documents
- Includes indexing status, upload timestamp, storage URI
- Creates `audit_event` for the query
- Returns `request_id` for traceability

**Request:**
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
      "indexed_status": "pending",
      "storage_uri": "uploads/uuid.pdf",
      "datastore_ref": null,
      "deleted_at": null
    }
  ]
}
```

#### 4. POST /docs/query (Stub)
**Purpose:** Query documents (stub - returns refusal until Vertex AI Search integrated)

**Functionality:**
- Accepts query text in request body
- Returns hard refusal: `"Information not found in internal records."`
- Returns empty `citations[]` array
- Creates `audit_event` with prompt hash and query details
- Implements "no source = no answer" rule (PRD hard trust rule)

**Request:**
```http
POST /docs/query
Content-Type: application/json

{
  "query": "What is our refund policy?"
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "answer": "Information not found in internal records.",
  "citations": []
}
```

### Features Implemented

- ✅ **Request ID generation** - UUID for all requests (traceability)
- ✅ **Audit logging** - All endpoints create `audit_event` records (success and failure)
- ✅ **File persistence** - Files saved to named volume (survives rebuilds)
- ✅ **Error handling** - Try/except with audit logging on failures
- ✅ **CORS configuration** - Enabled for Streamlit frontend (`localhost:8501`)
- ✅ **Response format compliance** - All responses include `request_id` per PRD
- ✅ **Prompt hashing** - Queries are hashed for audit purposes

### Files Created
- `api-gateway/app/schemas.py` - Pydantic models for request/response validation
- `api-gateway/app/services.py` - Business logic (file handling, audit logging, DB operations)
- `api-gateway/app/routes/docs.py` - Module A API routes
- `api-gateway/app/routes/__init__.py` - Routes package
- `api-gateway/main.py` - Updated with router and CORS middleware
- `api-gateway/requirements.txt` - Added `python-multipart` for file uploads

---

## API Contract Compliance

All endpoints follow PRD Section 9 requirements:

- ✅ All responses include `request_id` for traceability
- ✅ All endpoints write audit events (success/failure)
- ✅ Query endpoint returns `{answer, citations[]}` format
- ✅ Query endpoint refuses when citations are empty (hard trust rule)
- ✅ All module endpoints tagged as `MODULE_A` in audit events

---

## Database Schema

### doc_asset Table
- `id` (Integer, Primary Key)
- `filename` (String 512, Indexed)
- `storage_uri` (String 1024) - Path to stored file
- `uploaded_at` (DateTime, Timezone-aware, Default: now())
- `indexed_status` (Enum: PENDING/INDEXING/READY/FAILED, Default: PENDING, Indexed)
- `datastore_ref` (String 512, Nullable) - Vertex AI Search reference (not used yet)
- `deleted_at` (DateTime, Nullable, Indexed) - Soft delete

### audit_event Table
- `id` (Integer, Primary Key)
- `ts` (DateTime, Timezone-aware, Default: now(), Indexed)
- `module` (Enum: MODULE_A/MODULE_B/MODULE_C/ADMIN/SYSTEM, Indexed)
- `user_id` (String 128, Nullable, Indexed)
- `session_id` (String 128, Nullable, Indexed)
- `request_id` (String 128, Required, Indexed) - UUID for request tracing
- `prompt_hash` (String 64, Nullable, Indexed) - Hash of user prompt
- `sources_json` (JSON, Nullable) - Retrieved sources/citations
- `tool_calls_json` (JSON, Nullable) - MCP tool calls made
- `decision_json` (JSON, Nullable) - Approval/rejection decisions
- `status` (Enum: SUCCESS/FAILURE/PENDING, Default: PENDING, Indexed)
- `error` (Text, Nullable) - Error message if status is FAILURE

---

## Next Steps

1. **Vertex AI Search Query Integration** (requires GCP credentials):
   - Replace stub query endpoint with Vertex AI Search retrieval
   - Implement citation extraction from search results
   - Return actual answers with citations (only if citations exist)
   - Requires `DATA_STORE_ID`, `ENGINE_ID` in `.env`

2. **Document Processing** (optional enhancements):
   - Add document parsing (PDF, DOCX, TXT)
   - Validate file types
   - Extract text content for indexing

3. **Frontend Integration**: ✅ COMPLETE
   - ✅ Streamlit UI for document upload
   - ✅ Display document status list
   - ✅ Query interface with citation display (stub)
   - ✅ Landing page with module tiles
   - ✅ Request ID panel for trust/traceability
   - ✅ Environment variable configuration (`API_BASE_URL`)

---

## Testing

### Manual Testing

1. **Upload a document:**
```bash
curl -X POST "http://localhost:8000/docs/upload" \
  -F "file=@example.pdf"
```

2. **Check document status:**
```bash
curl "http://localhost:8000/docs/status"
```

3. **Query documents (stub):**
```bash
curl -X POST "http://localhost:8000/docs/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our policy?"}'
```

### Verification

- ✅ Files persist in uploads volume after container rebuild
- ✅ Database records persist in Postgres volume
- ✅ All requests generate audit events
- ✅ Query endpoint returns refusal when no citations
- ✅ Request IDs are unique and traceable

---

## Files Modified

- `api-gateway/requirements.txt` - Added database and file upload dependencies
- `api-gateway/main.py` - Added startup migrations, router, CORS
- `docker-compose.yml` - Updated depends_on to wait for Postgres health

---

---

## Startup Dependencies & Robustness

### Configuration

All startup dependencies are properly configured in `docker-compose.yml`:

- **Postgres & Redis**: Health checks ensure they're ready before dependent services start
- **API Gateway**: 
  - Waits for Postgres (healthy) and Redis (healthy) via `depends_on` with `condition: service_healthy`
  - Runs database migrations automatically on startup with retry logic (waits up to 60 seconds)
  - Has health check endpoint for dependent services
- **Worker**: Waits for Postgres (healthy), Redis (healthy), and API Gateway (started)
- **Frontend**: Waits for API Gateway (started)
- **MCP Bridge**: No dependencies (starts independently)

### Robustness Features

1. **Database Connection Retry**: `app/migrations.py` includes `wait_for_db()` function that retries up to 30 times (2s intervals) before failing
2. **Health Check Endpoints**: All services expose health endpoints that verify service and database connectivity
3. **Graceful Startup**: Services wait for dependencies using Docker Compose `depends_on` with health check conditions
4. **Automatic Migrations**: Migrations run automatically on API Gateway startup, no manual step required
5. **Volume Persistence**: All data (Postgres, uploads, sessions, Redis) persists across container rebuilds via named volumes

### User Experience

**Users can simply run:**
```bash
docker compose up --build
```

**No manual steps required:**
- ✅ No manual database initialization
- ✅ No manual migration commands
- ✅ No specific build order
- ✅ All dependencies handled automatically
- ✅ Services start in correct order with health checks

---

## Task 4: GCS Smoke Test Endpoint ✅

### Implemented

- **GCS smoke test endpoint** at `GET /gcs/smoke`
- **Google Cloud Storage integration** using `google-cloud-storage` library
- **Credentials mounting** via Docker Compose volume mount
- **Environment configuration** for `GCS_BUCKET_NAME` and `GOOGLE_APPLICATION_CREDENTIALS`

### Functionality

The smoke test endpoint:
1. **Uploads** a small text blob to `gs://<bucket>/smoke/<uuid>.txt`
2. **Verifies** the blob exists (reloads metadata)
3. **Deletes** the test blob
4. **Returns** success response with `ok`, `bucket`, `object`, and `request_id`

**Request:**
```http
GET /gcs/smoke
```

**Response:**
```json
{
  "ok": true,
  "bucket": "sme-ops-center-uploads-sme-ai-prototype",
  "object": "smoke/7ac7d93b-ebb6-4c2e-9dea-07bc22118ae3.txt",
  "request_id": "fd7fab49-1ed5-4c4e-84f7-485e8da84155"
}
```

### Configuration

**Docker Compose:**
- Volume mount: `E:\sme-ops-center-secrets\smeops-api-sa.json:/run/secrets/gcp-sa.json:ro` (read-only)
- Environment variable: `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-sa.json`
- Environment variable: `GCS_BUCKET_NAME=sme-ops-center-uploads-sme-ai-prototype`

**Environment:**
- `.env` file sets `STORAGE_BACKEND=gcs` (not committed, as per security best practices)
- GCS credentials are mounted as a secret file (read-only)

### Files Created/Modified

- `api-gateway/app/routes/gcs.py` - New GCS smoke test route
- `api-gateway/main.py` - Added GCS router
- `api-gateway/requirements.txt` - Added `google-cloud-storage==2.14.0`
- `docker-compose.yml` - Added credentials volume mount and environment variables
- `.env` - Set `STORAGE_BACKEND=gcs` (local file, not committed)

### Acceptance Criteria Met

- ✅ GCS smoke test endpoint implemented
- ✅ Credentials mounted securely (read-only)
- ✅ Environment variables configured
- ✅ Test successfully uploads, verifies, and deletes blobs
- ✅ Error handling for missing configuration or GCS errors
- ✅ Returns proper response format with `request_id`

### Testing

**Test the endpoint:**
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:8000/gcs/smoke" -Method Get | ConvertTo-Json
```

```bash
# curl
curl http://localhost:8000/gcs/smoke
```

**Or visit in browser:**
```
http://localhost:8000/gcs/smoke
```

### Next Steps

1. **Vertex AI Search query API** - Replace query stub with Discovery Engine search/answer API
2. **Implement GCS file retrieval** - For serving uploaded documents (if needed)

---

### Task 5a: Vertex AI Search Document Ingestion ✅

**Implemented:**
- GCS save path changed from `uploads/` to `docs/` (aligns with Data Store import prefix `gs://bucket/docs/`)
- Discovery Engine `DocumentServiceClient.import_documents()` called after GCS upload
- Automatic import on upload when `STORAGE_BACKEND=gcs`; `indexed_status` updated to READY/FAILED
- `POST /docs/index` endpoint to trigger indexing for PENDING docs (all or by `doc_id`)
- `DATA_STORE_ID` and `ENGINE_ID` added to `.env.example` and PRD
- `google-cloud-discoveryengine==1.14.0` added to api-gateway requirements

**Required env vars:** `GOOGLE_CLOUD_PROJECT`, `DATA_STORE_ID`, `DISCOVERY_ENGINE_LOCATION`, `GCS_BUCKET_NAME` (when using GCS)

---

**Milestone 1 Progress: 5/6 tasks complete (83%)**
