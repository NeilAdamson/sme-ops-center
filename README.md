# SME Ops-Center

**Operational AI Demo-in-a-Box (SA SME)**

A Dockerized, decoupled, production-reusable prototype using **Google Gemini on Vertex + Vertex AI Search + Xero via MCP**, with trust controls (citations, approvals, read-only finance), auditability, and incremental delivery.

## Quick Start

### Prerequisites
- Docker Desktop or Docker Engine with Docker Compose v2+
- Git

### Setup

1. **Clone the repository:**
```bash
git clone <repo-url>
cd sme-ops-center
```

2. **Copy environment template:**
```bash
cp .env.example .env
```

3. **Edit `.env` with your actual values:**
   - `STORAGE_BACKEND=gcs` (required for Vertex AI Search document ingestion)
   - `GOOGLE_CLOUD_PROJECT` — your GCP project ID
   - `GCS_BUCKET_NAME` — your GCS bucket name
   - `DATA_STORE_ID` and `ENGINE_ID` — from Vertex AI Search console (Steps 13–15 in GCP checklist)
   - `DISCOVERY_ENGINE_LOCATION=global`
   - Xero OAuth credentials (for Module C)
   - Database passwords
   - Other configuration as needed

   **Data Store import prefix:** When creating the Vertex AI Search Data Store, set the import prefix to `gs://<bucket>/docs/` so it matches where the app uploads documents.

4. **Configure Google Cloud Storage credentials:**
   - Run `.\Scripts\GC-Build.ps1` to create the project and generate a dev key, or place your GCP service account JSON in `secrets/`
   - The key file is mounted as `./secrets/aiops-gc-poc-pilot__aiops-gc-app-key.json` → `/run/secrets/gcp-sa.json` (read-only) in the api-gateway container
   - Ensure `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-sa.json` (set via docker-compose)

5. **Start all services:**
```bash
docker compose up --build
```

**Startup Sequence:**
Docker Compose automatically handles the startup dependencies:
1. **Postgres & Redis** start first and wait for health checks
2. **MCP Bridge** starts independently
3. **API Gateway** waits for Postgres/Redis to be healthy, then:
   - Runs database migrations automatically
   - Waits for database to be ready (retry logic)
   - Starts the FastAPI server
4. **Worker** waits for Postgres, Redis, and API Gateway to start
5. **Frontend** waits for API Gateway to start

**No manual build sequence needed** — just run `docker compose up --build` and all services will start in the correct order.

6. **Access services:**
   - Frontend: http://localhost:8501
   - API Gateway: http://localhost:8000
   - MCP Bridge: http://localhost:3000
   - Postgres: localhost:5432
   - Redis: localhost:6379

### Health Checks

- API Gateway: http://localhost:8000/health
- MCP Bridge: http://localhost:3000/health
- GCS Smoke Test: http://localhost:8000/gcs/smoke (tests Google Cloud Storage connectivity)

## Architecture

### Services

| Service       | Technology      | Port | Purpose                                      |
|---------------|-----------------|------|----------------------------------------------|
| `frontend`    | Streamlit       | 8501 | Thin UI shell; calls `api-gateway` only      |
| `api-gateway` | FastAPI         | 8000 | Core orchestration; trust enforcement; audit |
| `worker`      | Python          | —    | Background jobs (doc ingest, email parsing)  |
| `mcp-bridge`  | Node.js         | 3000 | MCP servers; OAuth PKCE; HTTP interface      |
| `postgres`    | PostgreSQL 16   | 5432 | System-of-record: metadata, approvals, audit |
| `redis`       | Redis 7         | 6379 | Queue and caching                            |

### Key Principles

- **Docker-first**: Everything runs via Docker Compose
- **Strict decoupling**: Frontend only calls `api-gateway` over HTTP
- **API-first**: All business logic behind stable REST endpoints
- **Incremental delivery**: Milestone 0 → Module A → Module B → Module C → hardening
- **Security**: Non-root containers, no secrets in repo, audit logging
- **No deprecated models**: Gemini 2.x/2.5 via Vertex only

## Project Status

### Milestone 0: ✅ Complete
- Docker Compose scaffold with all services
- Health endpoints for API Gateway and MCP Bridge
- Named volumes for persistence
- Environment configuration aligned with PRD

See [MILESTONE0_STATUS.md](./MILESTONE0_STATUS.md) for detailed status and issues resolved.

### Milestone 1: 🟡 In Progress (95% Complete)
- ✅ Task 1: Database migrations and core tables (`doc_asset`, `audit_event`)
- ✅ Task 2: Module A API endpoints (upload, status, index, query stub)
- ✅ Task 3: Frontend UI implementation (end-to-end flow with trust surface)
- ✅ Task 4: GCS smoke test endpoint (Google Cloud Storage integration test)
- ✅ Task 5a: Vertex AI Search document ingestion (GCS `docs/` path + Discovery Engine import)
- ⏳ Task 5b: Vertex AI Search query integration (replace stub with real retrieval)

**Implemented APIs:**
- `POST /docs/upload` - Upload documents; when `STORAGE_BACKEND=gcs`, saves to `gs://bucket/docs/` and triggers Vertex AI Search import
- `POST /docs/index` - Trigger indexing for PENDING docs in GCS (optional `doc_id` to index specific doc)
- `GET /docs/status` - Get document status list (including `indexed_status`: pending/indexing/ready/failed)
- `POST /docs/query` - Query stub (returns refusal until Vertex AI Search query API integrated)
- `GET /gcs/smoke` - GCS smoke test (uploads, verifies, and deletes a test blob)

**Implemented Frontend:**
- Landing page with 3 module tiles (Docs enabled, Inbox/Finance coming soon)
- Docs module with Upload, Status, and Query tabs
- Request ID panel (trust surface) showing last request_id for each operation
- Environment variable configuration (`API_BASE_URL`) - no hardcoding

See [MILESTONE1_STATUS.md](./MILESTONE1_STATUS.md) for detailed status.

### Next Milestones
- **Milestone 1** (remaining): Vertex AI Search query API integration (replace query stub)
- **Milestone 2**: Module B - Email triage and approval workflow
- **Milestone 3**: Module C - Xero Finance Lens with read-only MCP
- **Milestone 4**: Demo hardening

## GCP Setup Scripts

### GC-Build.ps1 — Foundation Setup
Creates the base GCP infrastructure (project, service account, APIs, main bucket).

```powershell
.\Scripts\GC-Build.ps1
```

### GC-Create-DataStores.ps1 — Additional Data Stores
Creates additional GCS buckets and Vertex AI Search data stores for:
- **Operations** — SOPs, manuals, procedures
- **Compliance/Legal** — Policies, contracts  
- **Finance** — Tax, accounting documents

**Prerequisites:** Run `GC-Build.ps1` first.

```powershell
.\Scripts\GC-Create-DataStores.ps1
```

This enables module-specific data stores aligned with the PRD's modular structure (Module A vs Module C), allowing code to filter queries by functional area.

**After running:** Create Vertex AI Search data stores via console (script provides instructions). Use a `docs/` folder per bucket (e.g. `gs://bucket-name/docs/`) and update `secrets/datastores-config.json` with `DATA_STORE_ID` values.

### GC-Fix-DiscoveryEngine-Permissions.ps1 — Fix Connector Permissions
If Vertex AI Search connector fails or you see "Missing required permissions: storage.objects.get" when creating a data store, run:

```powershell
.\Scripts\GC-Fix-DiscoveryEngine-Permissions.ps1
```

This grants the Discovery Engine service agent project-level `storage.admin` and bucket-level `storage.objectAdmin`, and grants your console user `storage.objectViewer` on each bucket so the Vertex AI console can validate the GCS path.

### GC-Validate-Regions.ps1 — Region Compatibility Check
Validates that all GCP resources are in compatible regions and can connect to each other. Identifies cross-region issues that could cause access problems.

```powershell
.\Scripts\GC-Validate-Regions.ps1
```

**What it checks:**
- GCS bucket regions vs Discovery Engine location
- Vertex AI location compatibility
- Connectivity between resources
- Provides recommendations for optimal region configuration

**Note:** Using `global` endpoints for Vertex AI and Discovery Engine while keeping GCS buckets in `africa-south1` is recommended for data residency compliance while maintaining full feature access.

## Documentation

- **[Product Requirements Document (PRD)](./docs/PRD.md)** - Complete specification
- **[Architecture Rules](./.cursor/rules/architecture.mdc)** - Development guidelines
- **[GCP Prerequisite Checklist](./docs/Operational_AI_for_SMEs_GCP_Prereq_Checklist_AIOPS_Naming.md)** - Manual GCP setup and script reference
- **[Milestone 0 Status](./MILESTONE0_STATUS.md)** - Docker Compose scaffold status
- **[Milestone 1 Status](./MILESTONE1_STATUS.md)** - Module A APIs status (in progress)
- **[Frontend UI Implementation](./FRONTEND_UI_IMPLEMENTATION.md)** - Frontend UI implementation summary
- **[Versions](./VERSIONS.md)** - Pinned dependency versions

## Development

### Project Structure

```
sme-ops-center/
├── docker-compose.yml      # Service orchestration
├── .env.example            # Environment template
├── secrets/                # GCP keys and config (gitignored); gc-foundation.json, datastores-config.json
├── Scripts/                # GCP setup and validation
│   ├── GC-Build.ps1        # Foundation (project, bucket, SA, IAM)
│   ├── GC-Create-DataStores.ps1   # Operations, Compliance, Finance buckets
│   ├── GC-Fix-DiscoveryEngine-Permissions.ps1
│   └── GC-Validate-Regions.ps1
├── frontend/               # Streamlit UI
│   ├── app.py              # Main UI application
│   ├── utils.py            # API client utilities
│   └── requirements.txt    # Python dependencies
├── api-gateway/            # FastAPI backend
│   ├── app/                # Application code
│   │   ├── routes/         # API routes (docs, gcs)
│   │   ├── models.py       # Database models
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── services.py     # Business logic (GCS, Discovery Engine import)
│   └── migrations/         # Alembic migrations
├── worker/                 # Background jobs
├── mcp-bridge/             # Node.js MCP server
└── docs/                   # Documentation
```

### Key Configuration Files

- `.env.example` - Environment variable template (see PRD Section 10)
- `docker-compose.yml` - Service definitions and volumes
- `VERSIONS.md` - Pinned versions for reproducibility

## Important Notes

### Security
- Never commit `.env` file (it's gitignored)
- All containers run as non-root users
- Secrets must use environment variables or secret management
- Production deployments should use managed secrets (not `.env` files)

### Container User IDs
- **Application containers** (frontend, api-gateway, worker, mcp-bridge): UID 1000
- **Postgres/Redis**: Use official image default non-root users (do not override)

### Startup Dependencies

All startup dependencies are configured in `docker-compose.yml`:

- **API Gateway** → waits for Postgres and Redis to be healthy (health checks)
- **Worker** → waits for Postgres, Redis (healthy), and API Gateway (started)
- **Frontend** → waits for API Gateway (started)
- **MCP Bridge** → no dependencies (starts independently)

**Health Checks:**
- Postgres: `pg_isready` check (10s interval, 5 retries)
- Redis: `redis-cli ping` check (10s interval, 5 retries)
- API Gateway: HTTP health endpoint check (10s interval, 5 retries, 30s start period)

**Automatic Migrations:**
API Gateway automatically runs database migrations on startup (via `app/migrations.py`) with retry logic to wait for Postgres to be ready. No manual migration step required.

### Volume Mounts
- Source code is bind-mounted for development (`./service:/app`)
- `mcp-bridge` uses anonymous volume for `node_modules` to preserve dependencies
- Named volumes (`pgdata`, `uploads`, `sessions`, `redis-data`) persist across rebuilds
- `api-gateway` mounts GCP credentials from `./secrets/aiops-gc-poc-pilot__aiops-gc-app-key.json` to `/run/secrets/gcp-sa.json` (read-only)

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure Docker has proper permissions on host directories
2. **Port conflicts**: Check if ports 8501, 8000, 3000, 5432, 6379 are available
3. **Volume initialization**: If Postgres/Redis fail to start, try `docker compose down -v` to reset volumes

See [MILESTONE0_STATUS.md](./MILESTONE0_STATUS.md) for detailed issue resolution.

## License

[License information]
