# API Gateway Service

**FastAPI-based API Gateway for SME Ops-Center**

This service provides the core orchestration, trust enforcement, and audit logging for all business logic.

## Overview

The API Gateway is the single point of entry for all frontend requests. It implements:
- REST API endpoints with OpenAPI documentation
- Database persistence (Postgres)
- Audit logging for all operations
- File upload handling
- Service orchestration (Vertex AI, MCP Bridge)

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
- Saves file to uploads volume (`/app/uploads`)
- Creates `doc_asset` record with `PENDING` status
- Logs audit event

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
      "indexed_status": "pending",
      "storage_uri": "uploads/uuid.pdf",
      "datastore_ref": null,
      "deleted_at": null
    }
  ]
}
```

#### Query Documents (Stub)
```http
POST /docs/query
Content-Type: application/json

{
  "query": "What is our refund policy?"
}
```

**Response (Stub - until Vertex AI Search integrated):**
```json
{
  "request_id": "uuid",
  "answer": "Information not found in internal records.",
  "citations": []
}
```

**Functionality:**
- Currently returns refusal message (hard trust rule: no source = no answer)
- Logs audit event with prompt hash
- Will be replaced with Vertex AI Search integration

### Future Endpoints (Not Yet Implemented)

- `POST /docs/index` - Trigger document indexing
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
- `indexed_status` - Status: `pending`, `indexing`, `ready`, `failed`
- `datastore_ref` - Vertex AI Search datastore reference (when indexed)
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
│   │   └── docs.py          # Module A routes
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

### Volume Mounts

- `./api-gateway:/app` - Source code (development)
- `uploads:/app/uploads` - Named volume for file persistence
- `sessions:/app/sessions` - Named volume for session data

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

# Query (stub)
curl -X POST "http://localhost:8000/docs/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'
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

## Next Steps

1. **Vertex AI Search Integration**
   - Implement document indexing
   - Replace query stub with actual search
   - Return citations from search results

2. **Module B Implementation**
   - Email upload and parsing
   - Classification and extraction
   - Approval workflow

3. **Module C Implementation**
   - Xero OAuth integration
   - MCP Bridge integration
   - Finance query endpoints
