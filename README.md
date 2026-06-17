# SME Ops-Center

**SME AI control plane (`gcp-sa`)**

A Dockerized, decoupled, production-reusable implementation of the `gcp-sa` profile: **Google/GCP runtime + Google Gemini on Vertex + Vertex AI Search / Agent Search + official Xero MCP behind gateway controls**, with trust controls (citations, approvals, read-only finance), auditability, and incremental delivery.

The first target profile is **Xero + Google/GCP**. App infrastructure and original document storage should use `africa-south1` where feasible; Vertex AI Search / Agent Search and AI inference may use documented `global` endpoints and must be disclosed as a compliance design choice.

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
   - `GOOGLE_CLOUD_PROJECT_NUMBER` — your numeric GCP project number, required by Agent Search serving/import paths
   - `GCS_BUCKET_NAME` — the staging upload bucket only
   - `DOC_DOMAIN_REGISTRY_PATH` — points to `secrets/domain-registry.json` in local Docker
   - `DISCOVERY_ENGINE_LOCATION=global`
   - Xero OAuth credentials (for Module C)
   - Database passwords
   - Other configuration as needed

   **Domain registry:** Module A no longer relies on one global `DATA_STORE_ID` / `ENGINE_ID`. The registry defines one document domain per business area: `operations`, `compliance`, and `finance`. Each domain has a source-of-truth bucket, `docs/` prefix, Agent Search data store, search app/engine, and serving config. The upload bucket is staging only.

4. **Configure Google Cloud Storage credentials:**
   - Run `.\Scripts\GC-Build.ps1` to create the project and generate a dev key, or place your GCP service account JSON in `secrets/`
   - The key file is mounted as `./secrets/aiops-gc-poc-pilot__aiops-gc-app-key.json` → `/run/secrets/gcp-sa.json` (read-only) in the api-gateway container
   - Ensure `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-sa.json` (set via docker-compose)

5. **Start all services (development):**
```powershell
.\Scripts\dev-deploy.ps1
```

Runs detached in the background by default (`docker compose up --build -d`). To stream logs in the terminal:
```powershell
.\Scripts\dev-deploy.ps1 -Foreground
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

**No manual build sequence needed** — run `.\Scripts\dev-deploy.ps1` (or `docker compose up --build`) and all services will start in the correct order.

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
- **Incremental delivery**: Sprint 0 → Sprint 1 Module A query → Sprint 2 worker/doc lifecycle → Sprint 3 security baseline → Sprint 4 Xero / Sprint 5 Inbox → Sprint 6 hardening
- **Security**: Non-root containers, no secrets in repo, audit logging
- **No deprecated models**: Gemini 2.x/2.5 via Vertex only
- **Scoped provider strategy**: Provider-neutral interfaces remain an architecture principle, but OpenAI/Microsoft adapters are deferred until a second real customer profile exists

## Project Status

### Milestone 0: ✅ Complete
- Docker Compose scaffold with all services
- Health endpoints for API Gateway and MCP Bridge
- Named volumes for persistence
- Environment configuration aligned with PRD

See [MILESTONE0_STATUS.md](./MILESTONE0_STATUS.md) for detailed status and issues resolved.

### Milestone 1: ✅ Complete For Domain RAG Flow
- ✅ Task 1: Database migrations and core tables (`doc_asset`, `audit_event`)
- ✅ Task 2: Module A API endpoints (upload, domains, move, status, index, query)
- ✅ Task 3: Frontend UI implementation (upload, file manager, status, query, trust surface)
- ✅ Task 4: GCS smoke test endpoint (Google Cloud Storage integration test)
- ✅ Task 5a: Domain bucket movement and Redis/worker Agent Search import
- ✅ Task 5b: Agent Search grounded generation with citations and no-source refusal

**Implemented APIs:**
- `GET /docs/domains` - Return staging and business-domain registry
- `POST /docs/upload` - Upload documents to the staging bucket only
- `POST /docs/move` - Manually classify and move a staged document into a domain bucket
- `POST /docs/index` - Queue worker indexing for classified domain documents
- `GET /docs/status` - Get document lifecycle status (`staged`, `classified`, `indexing`, `ready`, `failed`, etc.)
- `POST /docs/query` - Query one domain or all domains through Agent Search grounded generation; refuses without citations
- `GET /gcs/smoke` - GCS smoke test (uploads, verifies, and deletes a test blob)

**Implemented Frontend:**
- Landing page with 3 module tiles (Docs enabled, Inbox/Finance coming soon)
- Docs module with Upload, File Manager, Status, and Query tabs
- Request ID panel (trust surface) showing last request_id for each operation
- Environment variable configuration (`API_BASE_URL`) - no hardcoding

See [MILESTONE1_STATUS.md](./MILESTONE1_STATUS.md) for detailed status.

### Six-Sprint Roadmap
- **Sprint 0**: Doc rebaseline - SME AI control plane, `gcp-sa`, POPIA/residency wording
- **Sprint 1**: Module A query - Agent Search grounded generation, citations, refusal tests, demo corpus
- **Sprint 2**: Worker + doc lifecycle - Redis/worker indexing, soft delete, reindex, export, portable secrets
- **Sprint 3**: Security baseline - auth, tenant IDs, RBAC, env validator, audit export, tool-call ledger
- **Sprint 4**: Module C Xero - official `XeroAPI/xero-mcp-server` behind read-only gateway, OAuth, drill-down, CSV
- **Sprint 5**: Module B Inbox - upload-only extraction, approval workflow, draft-only UI
- **Sprint 6**: Production hardening - evals, threat model, observability, onboarding checklist, guided demo mode

**Sequencing rule:** Sprint 1 is the critical path. Live Xero integration must wait until Sprint 3 security baseline is complete.

## Docker Deploy Scripts

Use these scripts to rebuild, restart, or stop containers. They wrap `docker compose` with consistent parameters for dev and prod.

| Script | Environment | Purpose |
|--------|-------------|---------|
| `dev-deploy.ps1` | Development (Windows/PowerShell) | Rebuild and start the local stack |
| `prod-deploy.sh` | Production (Linux/bash) | Rebuild and start the hosted stack |

**Note:** These scripts manage **Docker containers only**. GCP project, bucket, and service-account setup is separate — see `GC-Build.ps1` below.

### dev-deploy.ps1 — Development

```powershell
# Rebuild images and start in background (default)
.\Scripts\dev-deploy.ps1

# Stream logs in this terminal
.\Scripts\dev-deploy.ps1 -Foreground

# Full no-cache rebuild
.\Scripts\dev-deploy.ps1 -Action Rebuild -NoCache

# Restart specific services
.\Scripts\dev-deploy.ps1 -Action Restart -Services api-gateway,frontend

# Stop containers (keep volumes)
.\Scripts\dev-deploy.ps1 -Action Down

# Reset Postgres/Redis volumes
.\Scripts\dev-deploy.ps1 -Action Down -RemoveVolumes
```

| Parameter | Description |
|-----------|-------------|
| `-Action` | `Up` (default), `Down`, `Restart`, `Rebuild`, `Stop`, `Logs`, `Ps` |
| `-Services` | Comma-separated service names (e.g. `api-gateway,worker`) |
| `-Foreground` | Stream logs in terminal (default is detached `-d`) |

After a successful `Up` or `Rebuild`, the script prints a **quickstart summary** with URLs, ports, Postgres credentials (from `.env`), container names, and verification steps.
| `-NoBuild` | Start without rebuilding images |
| `-NoCache` | Rebuild without Docker layer cache (`Rebuild` action) |
| `-Pull` | Pull newer base images before build |
| `-RemoveVolumes` | Delete named volumes on `Down` (destructive) |
| `-Follow` | Follow log output (`Logs` action) |

### prod-deploy.sh — Production

```bash
chmod +x ./Scripts/prod-deploy.sh   # once, on the host

# Pull, rebuild, and start detached (production default)
./Scripts/prod-deploy.sh

# Full no-cache rebuild
./Scripts/prod-deploy.sh --action rebuild --no-cache

# Restart one service
./Scripts/prod-deploy.sh --action restart --services api-gateway

# Stop stack
./Scripts/prod-deploy.sh --action down
```

Production defaults: detached, `--build`, `--pull always`, and `--remove-orphans`. Use `--no-pull` or `--no-build` to skip those steps when appropriate.

## GCP Setup Scripts

### GC-Build.ps1 — Foundation Setup (not Docker)
Creates the base GCP infrastructure (project, service account, APIs, main bucket).

```powershell
.\Scripts\GC-Build.ps1
```

### GC-Provision-Domain-RAG.ps1 — Domain RAG Resources
Creates or verifies one Agent Search data store and one search app per document domain, then updates `secrets/domain-registry.json`.

```powershell
.\Scripts\GC-Provision-Domain-RAG.ps1
```

The registry-backed domains are:
- **Operations** — SOPs, manuals, procedures
- **Compliance/Legal** — Policies, contracts
- **Finance** — Tax, accounting documents

The app uses `aiops-gc-poc-pilot-uploads-8aukzz` as staging only. Manual classification moves files to `gs://<domain-bucket>/docs/<doc_id>/<filename>`, then the worker imports the document into the matching domain Agent Search datastore.

**Prerequisites:** Run `GC-Build.ps1` first and ensure the domain buckets exist.

### GC-Create-DataStores.ps1 — Legacy Bucket/Data Store Helper
This older helper creates domain buckets and provides console guidance. Prefer `GC-Provision-Domain-RAG.ps1` for the current registry-backed Agent Search setup.

```powershell
.\Scripts\GC-Create-DataStores.ps1
```

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

**Note:** Using `global` endpoints for Vertex AI and Discovery Engine while keeping GCS buckets in `africa-south1` is the current `gcp-sa` profile. Do not claim South Africa-only AI processing; disclose the endpoint split in customer onboarding.

## Documentation

- **[Product Requirements Document (PRD)](./docs/PRD.md)** - Complete specification
- **[GCP Prerequisite Checklist](./docs/Operational_AI_for_SMEs_GCP_Prereq_Checklist_AIOPS_Naming.md)** - Manual GCP setup and script reference
- **[Feasibility and Architecture Review](./docs/Project_Feasibility_Architecture_Review_2026-06-14.md)** - Current feasibility, runtime landscape, POPIA view, and sprint sequencing
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
├── secrets/                # GCP keys and config (gitignored); gc-foundation.json, domain-registry.json
├── Scripts/                # Deploy and GCP setup
│   ├── dev-deploy.ps1      # Docker rebuild/restart (development)
│   ├── prod-deploy.sh      # Docker rebuild/restart (production)
│   ├── GC-Build.ps1        # GCP foundation (project, bucket, SA, IAM)
│   ├── GC-Provision-Domain-RAG.ps1 # Domain datastores, search apps, serving configs
│   ├── GC-Create-DataStores.ps1   # Legacy Operations, Compliance, Finance bucket helper
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
│   │   └── services.py     # Business logic (GCS move, Redis queue, Agent Search query/import)
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
3. **Volume initialization**: If Postgres/Redis fail to start, reset volumes with `.\Scripts\dev-deploy.ps1 -Action Down -RemoveVolumes` (or `docker compose down -v`)

See [MILESTONE0_STATUS.md](./MILESTONE0_STATUS.md) for detailed issue resolution.

## License

[License information]
