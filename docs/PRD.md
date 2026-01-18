# Operational AI Demo-in-a-Box (SA SME)

## Final Architecture + PRD + Requirements + Tech Spec (Cursor Build Pack)

### Document purpose

A single build specification for Cursor/Antigravity to implement a **Dockerised, decoupled**, production-reusable prototype using **Google Gemini on Vertex + Vertex AI Search + Xero via MCP**, with **trust controls** (citations, approvals, read-only finance), **auditability**, and **incremental delivery**. The initial **Streamlit “demo shell”** must be replaceable later by **Node/Next.js UI** without rewriting backend logic.

---

## 1) Objectives

### Primary objective

Deliver a **visual, product-like demo** in a browser that proves value in minutes:

* **Module A:** “Ask Your Business” — cited answers over messy documents (“no source = no answer”)
* **Module B:** “Inbox Triage” — classify + extract structured fields + draft-only + human approval
* **Module C:** “Xero Finance Lens” — natural language finance queries via Xero MCP, **read-only**, with drill-down verification tables

### Secondary objectives

* The prototype must be reusable as a foundation for client PoCs and production builds.
* Enforce a security-first posture aligned to POPIA expectations (least privilege, audit trail, controlled actions).
* Keep it simple: prove “art of the possible” without boiling the ocean.

---

## 2) Non-goals (explicit exclusions)

* No model training / fine-tuning / custom foundation models.
* No autonomous execution of high-risk actions (payments, refunds, journal posting, contract signing).
* No full email integration (MVP is upload-based only; connectors later).
* No ERP/CRM reimplementation; no full data warehouse; no master data remediation.
* No guarantee of “AI processing in South Africa only” (some managed AI/search capabilities may require global/EU endpoints depending on service availability). Host the app/infra in Johannesburg where feasible; treat endpoint location as a compliance design choice.

---

## 3) Key decisions (must be enforced)

### 3.1 Stack decisions (MVP)

* **Docs retrieval/grounding:** Vertex AI Search (Discovery Engine / Vertex AI Search)
* **LLM:** Gemini on Vertex via `google-genai` SDK

  * **No deprecated model versions.** Do not reference Gemini 1.5.
  * Use configurable model IDs: primary + fallback.
* **Finance integration:** Xero via MCP server running behind an MCP bridge/proxy
* **UI:** Streamlit initially (thin client only)
* **Backend:** API-first (FastAPI recommended)
* **Async processing:** Worker service + Redis queue (ingestion/indexing/email parsing)
* **Persistence:** Postgres for metadata/audit/approvals; named volumes for dev
* **Storage:** Storage abstraction local volume vs GCS (`STORAGE_BACKEND=local|gcs`)

### 3.2 Replaceable UI principle (non-negotiable)

* Streamlit **must never**:

  * call Google Vertex APIs directly
  * call Xero/MCP directly
  * connect to Postgres directly
* Streamlit **only** calls the `api-gateway` via HTTP.
* All domain logic + integrations live behind stable API contracts (OpenAPI/Swagger).

### 3.3 OAuth ownership (critical for decoupling)

* OAuth callbacks **must not** terminate in Streamlit.
* Xero OAuth must be handled by the **mcp-bridge** (recommended) or `api-gateway`.
* Redirect URIs must target `mcp-bridge` (e.g., `http://localhost:3000/oauth/xero/callback`), not the Streamlit port.

---

## 4) Product experience (what the prospect sees)

### 4.1 Landing page (mandatory)

A cohesive landing page with:

* 3 tiles: **Docs / Inbox / Finance**
* “Try it now” per tile
* Pre-canned demo prompts per module (no improvisation required)
* Status badges: Docs indexed / Xero connected / Emails uploaded
* Trust banner: **“Cited answers only • Human approval required • Read-only finance”**

### 4.2 Common UI patterns (all modules)

* Evidence panel (citations/snippets, tool calls summary where relevant)
* “Draft” watermark on any generated action
* One-click export:

  * Module A: export answer + citations
  * Module C: export drill-down table (CSV)

---

## 5) Functional requirements

### Module A — Ask Your Business (Docs / RAG)

**Goal:** Trusted answers over messy documents.

**Inputs**

* Upload PDFs (required) + optionally DOCX/TXT.
* Persist originals across container rebuilds.
* Index into Vertex AI Search datastore.

**Query behavior (hard trust rule)**

* **No source = no answer** (default ON, cannot be bypassed in client demos).
* If retrieval returns insufficient evidence:

  * Return exactly: **“Information not found in internal records.”**

**Grounding policy**

* Use a retrieval threshold policy expressed in supported Vertex AI Search terms:

  * Either a strict threshold mode (e.g., HIGH)
  * Or `semanticRelevanceThreshold=0.7` via filter spec (as supported)
    (Expose as config `DOCS_RELEVANCE_MODE` and `DOCS_SEMANTIC_THRESHOLD`.)

**Outputs**

* Answer text
* Citations array: `{doc_name, snippet, page_or_section?, uri_or_id}`
* Evidence panel must show snippets and source identifiers.

**Admin**

* Document list and indexing status (pending/indexing/ready/failed)
* Delete doc (soft delete) + reindex capability

---

### Module B — Inbox Triage (Upload-based, human approval)

**Goal:** Turn emails into structured, reviewable work—draft-only.

**Inputs**

* Upload `.eml` / `.msg` / `.txt` (MVP)
* Parse thread content into canonical text

**Processing**

* Classify into: `Invoices | Sales | HR | Ops | Other`
* Extract **structured JSON** using Gemini (Flash family) with a fixed schema:

Schema (minimum):

* `category`
* `vendor_or_customer_name`
* `amount` (number)
* `currency`
* `vat_number`
* `invoice_number`
* `due_date` (ISO date)
* `action_recommendation` (enum: `draft_reply | create_task | request_missing_info | escalate`)
* `confidence` (0..1)
* `evidence_snippets[]` (strings copied from email text)

**Validation rules**

* `amount` must parse and be positive if present
* `due_date` must parse if present
* If required fields missing for “invoice-like” messages:

  * set `action_recommendation=request_missing_info`
  * lower confidence
  * highlight missing fields in UI

**Hard trust rule**

* System outputs are **draft-only**.
* Human approval required before any external action (sending mail, creating tickets, writing to any system). MVP stops at “approved draft”.

**UI**

* Queue view: new → extracted → awaiting approval → approved/rejected
* Approval page shows:

  * original email
  * extracted JSON
  * draft reply/task
  * approve/reject + comment
* Audit record written for every transition

---

### Module C — Xero Finance Lens (Read-only via MCP)

**Goal:** Answer finance questions from live accounting data with drill-down verification.

**Connection**

* OAuth 2.0 with PKCE handled by `mcp-bridge`.
* Tokens persisted (encrypted) across restarts.
* Streamlit never handles OAuth.

**Integration**

* `mcp-bridge` runs the Xero MCP server.
* `api-gateway` calls `mcp-bridge` over internal HTTP.
* Enforce **deny-by-default tool policy** at the gateway:

  * allow-list read-only actions only
  * block write-capable tools even if exposed by MCP server

**Query rules (hard trust)**

* Every response must include a drill-down table with source records used.
* If tool calls fail or return no data:

  * Return “Insufficient data to answer” and show “what data was queried”.

**Outputs**

* Answer narrative
* Drill-down table rows (invoices/contacts/ageing)
* Export CSV

---

## 6) Non-functional requirements (NFRs)

### 6.1 Decoupling and API stability

* `api-gateway` publishes OpenAPI spec; UI consumes only HTTP endpoints.
* All module logic is in backend services; UI is replaceable.

### 6.2 Docker-first microservices (compose)

All components run via Docker Compose and are independently buildable:

* `frontend` (Streamlit demo shell)
* `api-gateway` (FastAPI)
* `worker` (async jobs)
* `mcp-bridge` (Node: MCP over HTTP + OAuth PKCE)
* `postgres`
* `redis`

### 6.3 Persistence (must survive rebuild/restart)

Named volumes required:

* `pgdata` → Postgres
* `uploads` → local storage backend for docs/emails (dev)
* `sessions` → encrypted token/session material (dev only; production uses Secret Manager/KMS)

Redis is **not** a system of record. It is queue/caching only.

### 6.4 Environment-driven configuration (externalised)

* No hardcoded config values.
* Provide `.env.example` and a startup validator that fails fast if required env vars are missing.
* Separate “app region” (hosting) from “AI feature location” (Vertex endpoints) via env vars.

### 6.5 Versioning and deprecation control

* Maintain `VERSIONS.md` with pinned:

  * base images
  * MCP server package versions
  * Gemini model IDs (primary + fallback)
  * Vertex AI Search configuration
* No floating tags for critical dependencies; pin major/minor at minimum.

### 6.6 Container build best practices

* Slim base images
* Multi-stage builds where relevant
* Non-root user in every container
* Health checks for all services
* Dependency startup ordering based on health checks

### 6.7 Security posture

* Secrets never committed; `.env` ignored.
* Local dev may use key files; production must use runtime identity (no long-lived key files).
* Least privilege IAM for GCP service accounts.
* Full audit event capture for:

  * queries, retrieval sources, tool calls, approvals, errors
* MCP supply-chain controls:

  * pin MCP server versions
  * allow-list tools
  * log all tool calls

---

## 7) Service architecture

### 7.1 Service matrix

| Service       | Tech                    | Port | Purpose                                                             |
| ------------- | ----------------------- | ---: | ------------------------------------------------------------------- |
| `frontend`    | Streamlit (Python 3.12) | 8501 | Thin UI shell; calls `api-gateway` only                             |
| `api-gateway` | FastAPI (Python 3.12)   | 8000 | Core orchestration; Vertex/Gemini calls; trust enforcement; audit   |
| `worker`      | Python (Celery/RQ)      |    — | Background jobs: doc ingest/index trigger, email parsing/extraction |
| `mcp-bridge`  | Node (pinned major)     | 3000 | Runs MCP servers; OAuth PKCE; exposes MCP tools over HTTP           |
| `postgres`    | Postgres                | 5432 | System-of-record: metadata, approvals, audit events                 |
| `redis`       | Redis                   | 6379 | Queue and caching                                                   |

### 7.2 Responsibilities

* **frontend**

  * UI navigation, upload forms, display evidence, approvals
* **api-gateway**

  * stable REST API + OpenAPI
  * Module A routing to Vertex AI Search (with thresholds)
  * Module B Gemini extraction (schema enforcement) + approval workflow
  * Module C query orchestration to `mcp-bridge` + tool allow-list enforcement
  * audit writing to Postgres
* **worker**

  * ingestion pipelines
  * retries/backoff
  * indexing triggers to Vertex AI Search
* **mcp-bridge**

  * OAuth PKCE callbacks for Xero
  * MCP server process management
  * exposes a controlled HTTP interface to MCP tool calls (internal only)

---

## 8) Data model (Postgres)

### Tables (minimum)

* `audit_event`

  * id, ts, module, user_id/session_id, request_id, prompt_hash, sources_json, tool_calls_json, decision_json, status, error
* `doc_asset`

  * id, filename, storage_uri, uploaded_at, indexed_status, datastore_ref, deleted_at
* `email_asset`

  * id, filename, storage_uri, uploaded_at, parsed_text_ref, classification, extracted_json, approval_status, approver_id, approved_at
* `xero_tenant`

  * id, tenant_id, connected_at, token_ref (encrypted), last_used_at

---

## 9) API contracts (UI-to-backend)

### Common rules

* All responses return `request_id` for traceability.
* All module endpoints write an audit event (success/failure).

### Module A

* `POST /docs/upload`
* `POST /docs/index` (trigger indexing)
* `GET /docs/status`
* `POST /docs/query` → returns `{answer, citations[]}`

  * Must refuse if citations are empty.

### Module B

* `POST /inbox/upload`
* `POST /inbox/process/{id}`
* `GET /inbox/queue`
* `GET /inbox/{id}`
* `POST /inbox/{id}/approve` (approve/reject + comment)

### Module C

* `GET /finance/status` (connected yes/no)
* `POST /finance/query` → `{answer, rows[], query_trace}`

  * Must include verification rows.

### Admin

* `GET /audit` (filters by module, status, date)
* `GET /health`

---

## 10) Environment parameters (`.env.example`)

```bash
# App basics
APP_ENV=local
APP_REGION=africa-south1
API_BASE_URL=http://api-gateway:8000
STORAGE_BACKEND=local   # local|gcs

# GCP / Vertex
GOOGLE_CLOUD_PROJECT="your-project-id"
GOOGLE_GENAI_USE_VERTEXAI=True
VERTEX_LOCATION="global"              # or your chosen Vertex GenAI location
DISCOVERY_ENGINE_LOCATION="global"    # Vertex AI Search location (commonly global)
GCS_BUCKET_NAME="sme-ops-center-uploads"

# Vertex AI Search / RAG controls
DOCS_RELEVANCE_MODE="HIGH"            # or FILTER_SPEC
DOCS_SEMANTIC_THRESHOLD=0.7           # used if FILTER_SPEC
DOCS_MAX_RESULTS=5

# Gemini models (no deprecated IDs)
GEMINI_MODEL_PRIMARY="gemini-2.5-flash"
GEMINI_MODEL_FALLBACK="gemini-2.0-flash"
GEMINI_MAX_OUTPUT_TOKENS=1024

# Xero (OAuth handled by mcp-bridge)
XERO_CLIENT_ID="your-client-id"
XERO_CLIENT_SECRET="your-client-secret"
XERO_REDIRECT_URI="http://localhost:3000/oauth/xero/callback"

# Security
SECRET_KEY="generate-a-secure-key"
ENCRYPTION_SALT="for-token-storage"
ALLOWED_ORIGINS="http://localhost:8501"

# Database
POSTGRES_HOST=postgres
POSTGRES_DB=smeops
POSTGRES_USER=smeops
POSTGRES_PASSWORD="change-me"

# Redis
REDIS_URL=redis://redis:6379/0
```

Startup validation must fail-fast if required vars are absent.

---

## 11) Docker / Compose requirements

### Compose requirements

* Use named volumes:

  * `pgdata` (Postgres)
  * `uploads` (local storage dev)
  * `sessions` (dev token/session persistence for bridge, encrypted)
  * `redis-data` (Redis persistence)
* All application services run as non-root (UID 1000 for Python/Node containers).
* **Postgres/Redis**: Do NOT override user; use official image default non-root users (they handle initialization).
* Health checks for Postgres/Redis/API.
* **Important**: For Node services with bind mounts, use anonymous volume for `node_modules` to preserve installed dependencies (e.g., `/app/node_modules`).

### Persistence rules

* Uploaded docs/emails must survive rebuilds.
* Token/session data must survive restarts (encrypted at rest for dev volume; production uses managed secrets).
* `node_modules` in Node services should be preserved via anonymous volume when source is bind-mounted.

### Base Images and Versions

* Python services: `python:3.12-slim`
* Node services: `node:20-slim` (pinned in package.json engines)
* Postgres: `postgres:16-alpine`
* Redis: `redis:7-alpine`

### Known Configuration Issues Resolved (Milestone 0)

* **Node UID conflict**: Node images already have `node` user (UID 1000); use existing user instead of creating new one.
* **Empty requirements.txt**: Use conditional pip install to handle empty/comment-only requirements files.
* **npm ci vs npm install**: Use `npm install` for scaffold phase (no package-lock.json yet); switch to `npm ci` once lock file exists.
* **Volume mount overwrites**: Anonymous volumes preserve `node_modules` when source code is bind-mounted for development.
* **Postgres/Redis permissions**: Official images initialize correctly with their default users; do not override with custom UIDs.

---

## 12) Incremental build milestones (must follow)

### Milestone 0 — Scaffold

* repo + docker compose boots cleanly
* API health endpoint
* Postgres migrations run
* Audit event write works
* Streamlit loads and can call API

### Milestone 1 — Module A

* Upload docs → persist → index job → query returns citations or refuses
* Evidence panel works
* Index status view works

### Milestone 2 — Module B

* Upload email → parse → classify/extract JSON (schema-validated)
* Approval workflow works end-to-end
* Draft replies/tasks shown only (no external actions)

### Milestone 3 — Module C

* Xero OAuth via bridge works
* Finance queries return narrative + drill-down rows
* Read-only tool allow-list enforced and tested

### Milestone 4 — Demo hardening

* Guided demo mode with pre-canned prompts
* Export CSV (finance) + export answer/citations (docs)
* Robust error states and status badges

---

## 13) Repository structure (recommended)

```text
repo/
  README.md
  PRD.md
  VERSIONS.md
  .env.example
  .gitignore
  docker-compose.yml
  frontend/
    Dockerfile
    app.py
    requirements.txt
  api-gateway/
    Dockerfile
    app/
      main.py
      routes/
      services/
      schemas/
      security/
      storage/
    requirements.txt
  worker/
    Dockerfile
    app/
      worker.py
      jobs/
    requirements.txt
  mcp-bridge/
    Dockerfile
    package.json
    src/
      server.ts
      oauth/
      mcp/
      allowlist/
  db/
    migrations/
  .cursor/
    rules/
      architecture.mdc
```

---

## 14) Cursor rules (`.cursor/rules/architecture.mdc`) — required content

Add a rule file that enforces:

* Docker-only execution
* UI calls only API (no direct provider/system calls)
* Strict milestones (no big-bang)
* No secrets in repo
* No deprecated model IDs
* Read-only allow-list for Xero tools
* Audit logging mandatory per request
* Persistent volumes for Postgres/uploads/sessions

---

## 15) “Interrogate requirements” checklist (Cursor must follow)

Before implementing any feature:

* Identify module + acceptance criteria
* Identify data needed + where it is persisted
* Identify API contract impact
* Identify security implications (secrets, OAuth, audit, tool allow-list)
* Confirm Dockerisation + restart survival
* Confirm no deprecated model/package usage
* Confirm simplest path (MVP first)

---

# Copy-paste “Master Cursor Instructions”

> Act as a Senior Lead Architect. Initialize a monorepo `sme-ops-center` with a decoupled microservices architecture.
>
> 1. Create `docker-compose.yml` defining `frontend` (Streamlit), `api-gateway` (FastAPI), `worker`, `mcp-bridge` (Node), `postgres`, and `redis`, all running as non-root with named volumes for persistence.
> 2. Enforce decoupling: frontend must only call REST endpoints on `api-gateway`; it must not call GCP, Xero, or Postgres directly.
> 3. Implement environment validation on startup from `.env` and provide `.env.example`. No secrets committed.
> 4. Implement Module A using Vertex AI Search with strict grounding and “no source = no answer”.
> 5. Implement Module B using Gemini on Vertex (no deprecated model IDs) with schema-validated JSON extraction + human approval workflow; generate drafts only.
> 6. Implement Module C using Xero MCP server behind `mcp-bridge`. OAuth callback must be owned by bridge/gateway (not Streamlit). Enforce read-only tool allow-list and always return drill-down tables.
> 7. Build incrementally: Milestone 0 → Module A → Module B → Module C → hardening. Do not build everything at once.
> 8. Generate OpenAPI for `api-gateway` and keep UI replaceable by a future Node/Next.js frontend without backend rewrite.

---
