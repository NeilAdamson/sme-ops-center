# Operational AI for SMEs — Google Cloud Prerequisite Checklist (per SME)

This runbook defines the **mandatory Google Cloud setup** that must be completed and verified **before** deploying any custom code (Docker services, MCP bridges, UI shells, agents).

It is designed so you can hand it to a junior engineer and get consistent outcomes.

---

## Quick Start — Using the Automation Script

For **Phases 1–4** (foundation setup), you can use the automated PowerShell script instead of manual steps. Follow these instructions:

### Prerequisites

1. **Install Google Cloud SDK** (if not already installed):
   - Download from: https://cloud.google.com/sdk/docs/install
   - Ensure `gcloud` and `gsutil` are on your PATH

2. **Authenticate with Google Cloud**:
   ```powershell
   gcloud auth login
   ```
   This opens a browser to authenticate. After authentication, verify:
   ```powershell
   gcloud auth list
   ```
   You should see at least one account with `ACTIVE` status.

3. **Navigate to project directory**:
   ```powershell
   cd E:\sme-ops-center
   ```

### Running the Script

**Basic run (defaults: `poc`/`pilot`):**
```powershell
.\Scripts\GC-Build.ps1
```

**With custom parameters:**
```powershell
# Custom client/environment
.\Scripts\GC-Build.ps1 -ClientCode "acme" -Env "prod"

# Custom region
.\Scripts\GC-Build.ps1 -ClientCode "poc" -Env "pilot" -Region "us-central1"

# Custom secrets directory (absolute path)
.\Scripts\GC-Build.ps1 -SecretsDir "E:\sme-ops-center-secrets"

# With billing account (partner-owned pilot)
.\Scripts\GC-Build.ps1 -BillingAccountId "01ABCD-EFGHIJ-2KLMNO"

# Skip dev key generation
.\Scripts\GC-Build.ps1 -GenerateDevKey $false
```

### What Happens When You Run the Script

The script automatically:
- ✅ **Preflight checks**: Verifies `gcloud`/`gsutil` exist and you're authenticated
- ✅ **Creates project**: `aiops-gc-<clientcode>-<env>` (default: `aiops-gc-poc-pilot`)
- ✅ **Enables APIs**: Vertex AI, Discovery Engine, Storage, Secret Manager
- ✅ **Creates service account**: `aiops-gc-app` with required IAM roles
- ✅ **Creates bucket**: `aiops-gc-<clientcode>-<env>-uploads-<unique>` with hardening
- ✅ **Runs smoke test**: Verifies bucket permissions work
- ✅ **Generates dev key**: Saved to `secrets/` directory (project-scoped filename)
- ✅ **Creates state file**: `secrets/gc-foundation.json` with all IDs for handoff pack

### After the Script Completes

The script outputs all created resources. You still need to complete these **manual steps**:

1. **Link billing account** (if not automated with `-BillingAccountId`):
   - See Step 2–3 in the checklist below
   - Configure budget/alerts

2. **Create Vertex AI Search resources** (console-driven):
   - See Steps 13–16 in the checklist below
   - Create datastore and search app
   - Capture `DATA_STORE_ID` and `ENGINE_ID`

3. **Run final verification**:
   - See Step 19 in the checklist below

**State file location**: `secrets/gc-foundation.json` contains all foundation values (project ID, bucket, service account, etc.) ready for your handoff pack.

### Troubleshooting

**Permission errors with gcloud:**
- Run PowerShell as Administrator, or
- Fix gcloud config directory permissions:
  ```powershell
  gcloud info --format="value(config.paths.global_config_dir)"
  ```

**Script fails at preflight checks:**
- The error message will tell you what's missing
- Most common: need to run `gcloud auth login`

**Script fails with "Billing account not found" error:**
- **This is expected** if billing isn't linked yet
- The script will check billing status and provide clear instructions
- **Option 1**: Link billing via script parameter:
  ```powershell
  .\Scripts\GC-Build.ps1 -BillingAccountId "YOUR_BILLING_ACCOUNT_ID"
  ```
- **Option 2**: Link billing manually:
  1. Go to: https://console.cloud.google.com/billing/linkedaccount?project=YOUR_PROJECT_ID
  2. Link your billing account
  3. Rerun the script (it's idempotent and will continue from where it left off)
- **Note**: Some APIs (Vertex AI, Discovery Engine, Secret Manager) require billing to be enabled

**For detailed manual steps** (if not using automation), see the full checklist below.

---

## Terminology (avoid confusion)

- **Google Account**: your login identity.
- **Google Cloud Project**: the isolation boundary for resources (Vertex AI, Vertex AI Search, buckets, service accounts, logs).
- **Cloud Billing Account**: who pays. A billing account can pay for **many** projects; a project links to **one** billing account at a time.
- **Organization** (optional): enterprise governance layer above projects (Workspace / Cloud Identity).

**Target delivery model (recommended):** 1 SME = 1 Google Cloud Project (and ideally client-owned billing).

---

## Naming Standard (mandatory, per SME)

You asked for: `AIOPS-GC-<name>`.

Important constraint: **Google Cloud resource IDs (project IDs, bucket names, service account IDs) cannot use uppercase** and have strict character rules. Therefore we use:

- **Human-facing Display Names:** `AIOPS-GC-<CLIENT>-<ENV>-<RESOURCE>` (uppercase allowed)
- **Machine IDs (used in commands):** `aiops-gc-<clientcode>-<env>-<resource>` (lowercase only)

### Recommended per-SME naming set

Use a short **clientcode** (3–12 chars, lowercase) and **env** (`pilot` or `prod`).

1. **Project**
   - Project ID: `aiops-gc-<clientcode>-<env>`
   - Project display name: `AIOPS-GC-<CLIENT>-<ENV>`

2. **Application service account**
   - Service account ID: `aiops-gc-app` (inside the project)
   - Service account display name: `AIOPS-GC-APP`

3. **Primary storage bucket** (must be globally unique)
   - Bucket name: `aiops-gc-<clientcode>-<env>-uploads-<unique>`
   - `<unique>`: 4–8 lowercase chars/digits, e.g. `k9p3` (you make it up; it just prevents name collisions)

4. **Vertex AI Search resources**
   - Data Store display name: `AIOPS-GC-<CLIENT>-<ENV>-DOCS`
   - Search App / Engine display name: `AIOPS-GC-<CLIENT>-<ENV>-SEARCH`

### Prefix layout inside the bucket (keep stable)
- `gs://<bucket>/docs/` (Module A source docs)
- `gs://<bucket>/emails/` (Module B raw email assets)
- `gs://<bucket>/smoke/` (smoke tests)

---

---

## Step 0 — Decide the tenant model (must be written down)

**Owner:** Solution owner + SME finance/admin  
**Console path:** N/A  
**Command equivalent:** N/A  
**Expected output:** A written decision captured in the onboarding pack  
**Fail symptoms:** unclear billing liability, hard offboarding, “shared environment” accusations

Choose one:

### Option A (recommended for production): Client-owned
- SME creates/owns the **billing account** (and ideally an Organization).
- You build/operate inside the SME project via IAM access.
- SME receives Google invoices directly.

### Option B (acceptable for pilot/demo): Partner-owned pilot (with transfer plan)
- You create/host the SME project under your billing account.
- You commit to transferring billing/project ownership before production.

---

# Phase 1 — Project and Billing Foundation

## Step 1 — Create the SME project
**Owner:** SME Admin (or Partner Admin if pilot)  
**Console path:** IAM & Admin → Manage resources → Create project  
**Command equivalent (Cloud Shell):**
```bash
gcloud projects create <PROJECT_ID> --name="AIOPS-GC-<CLIENT>-<ENV>"
gcloud config set project <PROJECT_ID>
gcloud config get-value project
```
**Expected output:** Project exists; active project equals `<PROJECT_ID>`

**Project ID rules:** lowercase letters/digits/hyphens only; must start with a letter.  
**Fail symptoms:** permission denied creating projects / wrong project selected

---

## Step 2 — Link billing account to the project
**Owner:** SME Billing Admin  
**Console path:** Billing → Account Management → My projects → Link project  
**Command equivalent (verify):**
```bash
gcloud beta billing projects describe <PROJECT_ID> --format="value(billingEnabled)"
```
**Expected output:** `True`  
**Fail symptoms:** later AI services fail, quota errors, API enablement issues

---

## Step 3 — Set cost guardrails (minimum)
**Owner:** SME Billing Admin  
**Console path:** Billing → Budgets & alerts  
**Command equivalent:** (console is typical)  
**Expected output:** Monthly budget + alert email recipients defined  
**Fail symptoms:** unexpected bill; uncontrolled spend during pilot

Recommended labels (optional but helpful):
- `client=<clientcode>`
- `env=pilot|prod`
- `owner=<email>`

---

# Phase 2 — Enable Required APIs

## Step 4 — Enable mandatory APIs
**Owner:** Cloud Engineer (Project Editor/Owner)  
**Console path:** APIs & Services → Library  
**Command equivalent:**
```bash
gcloud services enable \
  aiplatform.googleapis.com \
  discoveryengine.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com
```
**Expected output (verify):**
```bash
gcloud services list --enabled --format="value(config.name)" | egrep "aiplatform|discoveryengine|storage|secretmanager"
```
**Fail symptoms:** “API not enabled” errors from console wizards or your app

Optional only if you choose managed database:
- Cloud SQL Admin API

---

# Phase 3 — IAM and Service Accounts (App Identity)

## Step 5 — Create the application service account
**Owner:** Cloud Engineer  
**Console path:** IAM & Admin → Service accounts → Create  
**Command equivalent:**
```bash
SA_NAME="aiops-gc-app"
gcloud iam service-accounts create "$SA_NAME" --display-name="AIOPS Ops Center App SA"
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="$SA_NAME@${PROJECT_ID}.iam.gserviceaccount.com"
echo "$SA_EMAIL"
```
**Expected output:** SA exists; email printed  
**Fail symptoms:** SA created in wrong project / cannot find SA in list

**Naming note:** Service account *ID* must be lowercase. The display name can be uppercase.

---

## Step 6 — Grant project-level roles to the app service account (prototype baseline)
**Owner:** Cloud Engineer (Project Owner typical)  
**Console path:** IAM & Admin → IAM → Grant access  
**Command equivalent:**
```bash
PROJECT_ID=$(gcloud config get-value project)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user"

# For Vertex AI Search / Discovery Engine query access:
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/discoveryengine.user"
```
**Expected output (verify):**
```bash
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten="bindings[].members" \
  --format="table(bindings.role, bindings.members)" \
  --filter="bindings.members:serviceAccount:$SA_EMAIL"
```
**Fail symptoms:** permission denied when querying Search or calling Vertex AI models

**Note:** If you need to *create* Search apps/datastores via automation, temporarily use a broader role (e.g. `roles/discoveryengine.admin`) during provisioning, then reduce afterwards.

---

## Step 7 — Ensure Google-managed service agents exist (important for Search ingestion)
**Owner:** Cloud Engineer  
**Console path:** N/A  
**Command equivalent:**
```bash
gcloud beta services identity create --service=discoveryengine.googleapis.com
gcloud beta services identity create --service=aiplatform.googleapis.com
```
**Expected output:** identity creation returns success output  
**Fail symptoms:** Search import fails later with bucket access errors / cannot locate service agent identity

---

# Phase 4 — Cloud Storage (Documents and Email Assets)

## Step 8 — Create the SME uploads bucket
**Owner:** Cloud Engineer  
**Console path:** Cloud Storage → Buckets → Create  
**Command equivalent:**
```bash
PROJECT_ID=$(gcloud config get-value project)

# Bucket names must be globally unique, lowercase, DNS-compliant.
BUCKET="aiops-gc-<clientcode>-<env>-uploads-<unique>"

gsutil mb -p "$PROJECT_ID" -l africa-south1 "gs://$BUCKET"
```
**Expected output:** bucket exists  
**Fail symptoms:** invalid bucket name / name collision / wrong region

Recommended bucket settings:
- Uniform bucket-level access: ON
- Public access prevention: ENFORCED
- Location: choose and record (default for SA: `africa-south1`)

---

## Step 9 — Define bucket prefix layout (keep ingestion clean)
**Owner:** Cloud Engineer  
**Console path:** N/A (prefixes are implicit)  
**Expected output:** the team uses consistent prefixes
- `gs://<bucket>/docs/` (Module A source docs)
- `gs://<bucket>/emails/` (Module B raw email assets)
- `gs://<bucket>/smoke/` (smoke tests)

---

## Step 10 — Grant bucket permissions (two principals often required)
**Owner:** Cloud Engineer  
**Console path:** Storage → Bucket → Permissions

### A) App service account (runtime uploads/downloads)
Recommended for pilot:
- `roles/storage.objectAdmin` on the bucket (read/write/delete objects)

Command equivalent:
```bash
gsutil iam ch "serviceAccount:$SA_EMAIL:roles/storage.objectAdmin" "gs://$BUCKET"
```

### B) Discovery Engine service agent (only if Search ingests from bucket; required for some setups)
Grant (bucket-level):
- `roles/storage.objectViewer`

Command equivalent:
```bash
PROJECT_NUMBER=$(gcloud projects describe "$(gcloud config get-value project)" --format="value(projectNumber)")
DE_SA="service-$PROJECT_NUMBER@gcp-sa-discoveryengine.iam.gserviceaccount.com"
gsutil iam ch "serviceAccount:$DE_SA:roles/storage.objectViewer" "gs://$BUCKET"
```

**Expected output:** `gsutil iam get gs://<bucket>` shows bindings  
**Fail symptoms:** Vertex AI Search import fails due to bucket access

---

## Step 11 — Bucket smoke test (must pass)
**Owner:** Cloud Engineer  
**Command equivalent:**
```bash
echo "hello" > aiops-smoke.txt
gsutil cp aiops-smoke.txt "gs://$BUCKET/smoke/aiops-smoke.txt"
gsutil rm "gs://$BUCKET/smoke/aiops-smoke.txt"
rm aiops-smoke.txt
```
**Expected output:** copy succeeds; delete succeeds  
**Fail symptoms:** permission denied / bucket not found

**Note:** The automation script (`Scripts/GC-Build.ps1`) automatically runs this smoke test as part of Step 11.

---

# Phase 5 — Vertex AI (Gemini via Vertex) readiness

## Step 12 — Decide and record Vertex AI location strategy
**Owner:** Architect + SME compliance owner  
**Console path:** Vertex AI (varies by feature)  
**Expected output:** recorded decision in onboarding pack

Record:
- `VERTEX_AI_LOCATION` (e.g., `us-central1`, `europe-west4`, or `global` where supported)
- `GEMINI_PRIMARY_MODEL_ID`
- `GEMINI_FALLBACK_MODEL_ID`

**Fail symptoms:** runtime errors “model not available in region” or unexpected latency.

---

# Phase 6 — Module A: Vertex AI Search (Discovery Engine) setup

## Step 13 — Create the Data Store (unstructured docs from Cloud Storage)
**Owner:** Cloud Engineer (needs Discovery Engine provisioning rights)  
**Console path:** Vertex AI Search / Search & Conversation → Data Stores → Create

Configuration checklist:
- Data store type: Unstructured documents
- Source: Cloud Storage
- Import prefix: `gs://<bucket>/docs/`
- Choose and record Search resource location/collection (often `global` resources)

**Expected output:** datastore shows “Ready” and document count increases after import  
**Fail symptoms:** import stuck/failing (usually bucket permissions or bad file pattern)

---

## Step 14 — Create the Search App (Engine) and attach the Data Store
**Owner:** Cloud Engineer  
**Console path:** Vertex AI Search → Apps (Search Apps) → Create

Configuration checklist:
- App type: Search (general)
- Attach data store created above
- Enable generative answers only if you will enforce “no source = no answer” in your API layer

**Expected output:** engine created and has a serving config  
**Fail symptoms:** cannot attach datastore / datastore not ready

---

## Step 15 — Capture IDs for application configuration (handoff pack)
**Owner:** Cloud Engineer  
**Console path:** Search app and datastore detail pages

Record these values exactly:
- `GCP_PROJECT_ID`
- `GCS_BUCKET_NAME`
- `DISCOVERY_ENGINE_LOCATION` (as created/used by console)
- `DATA_STORE_ID`
- `ENGINE_ID`
- `SERVING_CONFIG_ID` (if shown)

**Expected output:** completed handoff pack  
**Fail symptoms:** developers guess IDs, APIs return 404

---

## Step 16 — Console Preview Test (must pass)
**Owner:** Cloud Engineer + SME sponsor (witness test)  
**Console path:** Vertex AI Search → App → Preview

Test:
- Upload 5–20 documents to `gs://<bucket>/docs/`
- Ask a question you know the docs answer

**Expected output:** relevant answer and/or retrieved results with references  
**Fail symptoms:** no results → ingestion not complete or permissions wrong

---

# Phase 7 — Secrets and Local Dev Authentication

## Step 17 — Decide: service account key (dev) vs keyless (prod)
**Owner:** Architect  
**Expected output:** written decision (prototype uses key; production uses keyless)

Prototype:
- JSON key stored outside repo and mounted read-only into container

Production (preferred):
- no long-lived keys (use attached SA on GCP runtime or Workload Identity Federation)

---

## Step 18 — Create a dev key (only if required)
**Owner:** Cloud Engineer  
**Console path:** IAM → Service accounts → Keys → Add key  
**Command equivalent:**
```bash
gcloud iam service-accounts keys create aiops-gc-app-key.json --iam-account "$SA_EMAIL"
```
**Expected output:** JSON key file downloaded/stored securely  
**Fail symptoms:** key created for wrong SA/project

**Note:** The automation script (`Scripts/GC-Build.ps1`) generates dev keys automatically with project-scoped filenames to avoid collisions across multiple SMEs:
- Format: `<PROJECT_ID>__aiops-gc-app-key.json`
- Example: `aiops-gc-poc-pilot__aiops-gc-app-key.json`
- Stored in `secrets/` directory (or `$SecretsDir` if overridden)

---

# Phase 8 — Final “Go/No-Go” Verification (before any custom code deploy)

## Step 19 — Minimum platform checks (Cloud Shell)
**Owner:** Cloud Engineer  
**Commands:**
```bash
gcloud config get-value project
gcloud beta billing projects describe "$(gcloud config get-value project)" --format="value(billingEnabled)"
gcloud services list --enabled --format="value(config.name)" | egrep "aiplatform|discoveryengine|storage|secretmanager"
gsutil ls -b "gs://$BUCKET"
```
**Expected output:** correct project, billing True, APIs enabled, bucket listed  
**Fail symptoms:** stop and fix before proceeding

---

## Step 20 — Runtime verification from local Docker (once credentials wired)
**Owner:** Developer  
**Test:** call your local `/gcs/smoke` endpoint (upload/verify/delete object)  
**Expected output:** JSON ok response, object lifecycle works  
**Fail symptoms:** credential mount wrong, bucket var wrong, IAM insufficient

---

# Deliverable: “AIOPS Google Cloud Handoff Pack” (per SME)

Produce a single page with:
- `PROJECT_ID` and `PROJECT_NUMBER`
- `GCS_BUCKET_NAME` + region
- Vertex AI strategy: `VERTEX_AI_LOCATION`, Gemini model IDs
- Vertex AI Search: `DATA_STORE_ID`, `ENGINE_ID`, `SERVING_CONFIG_ID`, location/collection used
- App service account email (`SA_EMAIL`)
- IAM roles granted (project-level + bucket-level)
- Verification evidence (paste outputs from Step 11 and Step 19, plus one screenshot of Search preview)

**Automation note:** If you used `Scripts/GC-Build.ps1`, the script automatically generates `secrets/gc-foundation.json` containing:
- `ProjectId`, `ProjectNumber`, `Region`
- `Bucket`, `SaEmail`, `DiscoveryEngineServiceAgent`
- `KeyPath` (if dev key generated)

This JSON file provides most foundation values for your handoff pack. You still need to manually add:
- Vertex AI Search IDs (from Steps 13–15)
- Vertex AI location/model strategy (from Step 12)
- Verification evidence

---

## Appendix A — Automation Script (Optional)

For **Phases 1–4** (project creation, APIs, IAM, storage), you can use the automated PowerShell script instead of manual console/CLI steps:

**Script:** `Scripts/GC-Build.ps1`

**Usage:**
```powershell
# Default: poc/pilot
.\Scripts\GC-Build.ps1

# Custom client/environment
.\Scripts\GC-Build.ps1 -ClientCode "acme" -Env "prod"

# Custom region
.\Scripts\GC-Build.ps1 -ClientCode "poc" -Env "pilot" -Region "us-central1"

# Override bucket name (instead of auto-generated)
.\Scripts\GC-Build.ps1 -BucketName "aiops-gc-poc-pilot-uploads-custom123"

# With billing account (partner-owned pilot)
.\Scripts\GC-Build.ps1 -BillingAccountId "01ABCD-EFGHIJ-2KLMNO"

# Custom secrets directory (absolute path)
.\Scripts\GC-Build.ps1 -SecretsDir "E:\sme-ops-center-secrets"

# Skip dev key generation
.\Scripts\GC-Build.ps1 -GenerateDevKey $false
```

**What the script automates:**
- ✅ **Preflight checks**: Verifies `gcloud`/`gsutil` exist and active account is authenticated
- ✅ Step 1: Project creation (`aiops-gc-<clientcode>-<env>`) — idempotent
- ✅ Step 2: Optional billing link (if `-BillingAccountId` provided)
- ✅ Step 4: Enable mandatory APIs
- ✅ Steps 5–7: Service account creation, project IAM, service agents — idempotent
- ✅ Steps 8–10: Bucket creation, hardening (UBLA + PAP), bucket IAM — idempotent
- ✅ Step 11: Bucket smoke test (upload/delete verification)
- ✅ Step 18: Generate dev service account key (project-scoped filename)

**What remains manual (script cannot automate):**
- ⚠️ Steps 2–3: Billing account link + budget/alerts (manual unless `-BillingAccountId` provided)
- ⚠️ Steps 13–16: Vertex AI Search datastore/app creation (console-driven)
- ⚠️ Step 19: Platform verification checks (run after script completes)

**Prerequisites:**
- `gcloud` CLI installed and on PATH (script verifies automatically)
- `gsutil` installed and on PATH (script verifies automatically)
- Active `gcloud` account authenticated (`gcloud auth login` — script verifies automatically)
- Permissions: Project Creator (or Org Admin), Billing Account User (for billing link)
- PowerShell 5.1+ (Windows) or PowerShell Core (cross-platform)

**Key Features:**

1. **Idempotent operations**: Script safely reruns on existing projects/buckets/service accounts without errors.

2. **Bucket persistence**: On first run, generates a unique bucket name (`aiops-gc-<clientcode>-<env>-uploads-<suffix>`). On reruns, reuses the same bucket from the state file. Override with `-BucketName` if needed.

3. **State file**: Automatically creates `secrets/gc-foundation.json` (or `$SecretsDir/gc-foundation.json`) containing:
   - `ProjectId`, `ProjectNumber`, `Region`
   - `Bucket`, `SaEmail`, `DiscoveryEngineServiceAgent`
   - `KeyPath` (if dev key generated)
   - This file serves as both:
     - **Rerun persistence** (bucket name reuse)
     - **Handoff pack** (ready-to-use JSON for `.env` population)

4. **Project-scoped dev keys**: Dev key filename includes project ID to avoid collisions:
   - Format: `<PROJECT_ID>__aiops-gc-app-key.json`
   - Example: `aiops-gc-poc-pilot__aiops-gc-app-key.json`

5. **Preflight validation**: Script checks prerequisites before any work:
   - Verifies `gcloud` and `gsutil` exist
   - Verifies active authentication
   - Shows which account will be used

**After running the script:**
1. Review the generated `gc-foundation.json` file in your secrets directory (contains all IDs for handoff pack)
2. Verify billing is linked (Step 2) and configure budget (Step 3) if not automated
3. Create Vertex AI Search resources via console (Steps 13–15)
4. Complete verification checks (Step 19)

**Rerunning the script:**
- Safe to rerun on the same project — all operations are idempotent
- Bucket name is automatically reused from state file (no new bucket created)
- Existing resources are detected and skipped
- State file is updated with current values

---

## Appendix B — Common fail patterns (quick triage)

- **API not enabled**: enable Step 4 APIs and retry.
- **Permission denied to bucket**: fix Step 10A (app SA) and Step 10B (Discovery Engine service agent).
- **Search import fails**: bucket agent permissions + correct import prefix in Step 13.
- **Model not available in region**: Step 12 location mismatch; adjust Vertex AI location/model selection.
- **Budget panic**: Step 3 missing; configure budgets/alerts and cap pilot usage.
