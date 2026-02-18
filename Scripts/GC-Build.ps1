<# 
GC-Build.ps1 — AIOPS Google Cloud Foundation Bootstrap (per SME)

Creates/updates (idempotent where possible):
- Project:            aiops-gc-<clientcode>-<env>
- Service account:    aiops-gc-app
- Bucket:             aiops-gc-<clientcode>-<env>-uploads-<unique>
- Enables APIs:       aiplatform, discoveryengine, storage, secretmanager
- Grants IAM:         roles/aiplatform.user, roles/discoveryengine.user (plus optional secret accessor)
- Ensures service agents exist (Discovery Engine + Vertex AI)
- Hardens bucket:     Uniform bucket-level access + Public access prevention
- Bucket IAM:         app SA objectAdmin; Discovery Engine service agent objectViewer
- Smoke test:         Upload/delete test file to verify bucket permissions
- (Optional) Generates a dev SA key JSON (DO NOT use long-lived keys in production)

Aligned with: docs/Operational_AI_for_SMEs_GCP_Prereq_Checklist_AIOPS_Naming.md
Covers: Phases 1-4 (Project, APIs, IAM, Storage) + Service Account Key + Smoke Test

================================================================================
QUICK START INSTRUCTIONS
================================================================================

PREREQUISITES:
1. Install Google Cloud SDK (if not already installed):
   - Download from: https://cloud.google.com/sdk/docs/install
   - Ensure gcloud and gsutil are on your PATH

2. Authenticate with Google Cloud:
   PowerShell> gcloud auth login
   (Opens browser to authenticate. Verify with: gcloud auth list)

3. Navigate to project directory:
   PowerShell> cd E:\sme-ops-center

RUNNING THE SCRIPT:
Basic run (defaults: poc/pilot):
   PowerShell> .\Scripts\GC-Build.ps1

With custom parameters:
   PowerShell> .\Scripts\GC-Build.ps1 -ClientCode "acme" -Env "prod"
   PowerShell> .\Scripts\GC-Build.ps1 -Region "us-central1"
   PowerShell> .\Scripts\GC-Build.ps1 -SecretsDir "E:\sme-ops-center-secrets"
   PowerShell> .\Scripts\GC-Build.ps1 -BillingAccountId "01ABCD-EFGHIJ-2KLMNO"
   PowerShell> .\Scripts\GC-Build.ps1 -GenerateDevKey $false

WHAT THE SCRIPT DOES:
- Preflight checks: Verifies gcloud/gsutil exist and you're authenticated
- Creates project: aiops-gc-<clientcode>-<env> (default: aiops-gc-poc-pilot)
- Enables APIs: Vertex AI, Discovery Engine, Storage, Secret Manager
- Creates service account: aiops-gc-app with required IAM roles
- Creates bucket: aiops-gc-<clientcode>-<env>-uploads-<unique> with hardening
- Runs smoke test: Verifies bucket permissions work
- Generates dev key: Saved to secrets/ directory (project-scoped filename)
- Creates state file: secrets/gc-foundation.json with all IDs for handoff pack

AFTER THE SCRIPT COMPLETES:
1. Link billing account (if not automated with -BillingAccountId)
2. Create Vertex AI Search resources via console (Steps 13-16 in checklist)
3. Run final verification checks (Step 19 in checklist)

State file location: secrets/gc-foundation.json contains all foundation values.

TROUBLESHOOTING:
- Permission errors: Run PowerShell as Administrator
- Preflight fails: Error message shows what's missing (usually need gcloud auth login)
- For detailed manual steps: See docs/Operational_AI_for_SMEs_GCP_Prereq_Checklist_AIOPS_Naming.md

================================================================================
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$false)]
  [ValidatePattern('^[a-z][a-z0-9-]{2,11}$')]
  [string]$ClientCode = "poc",

  [Parameter(Mandatory=$false)]
  [ValidateSet("pilot","prod")]
  [string]$Env = "pilot",

  [Parameter(Mandatory=$false)]
  [string]$Region = "africa-south1",

  # Optional: link billing automatically (partner-owned pilot). For client-owned, leave blank and do Step 2 in console.
  [Parameter(Mandatory=$false)]
  [string]$BillingAccountId = "",

  # Where to store the dev key JSON (if generated). Defaults to repo-relative path, can override to absolute path.
  [Parameter(Mandatory=$false)]
  [string]$SecretsDir = "$PSScriptRoot\..\secrets",

  # Optional: override bucket name instead of using the standard pattern/persisted value.
  [Parameter(Mandatory=$false)]
  [string]$BucketName = "",

  # Generate a dev key JSON by default for local Docker prototypes
  [Parameter(Mandatory=$false)]
  [bool]$GenerateDevKey = $true,

  # Add Secret Manager read access for the app SA (recommended if you plan to store OAuth/client secrets there)
  [Parameter(Mandatory=$false)]
  [bool]$GrantSecretAccessor = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
  param(
    [Parameter(Mandatory=$true)][string]$Cmd,
    [Parameter(Mandatory=$false)][string]$Description = "",
    [Parameter(Mandatory=$false)][bool]$ContinueOnError = $false
  )
  if ($Description) { Write-Host "`n==> $Description" -ForegroundColor Cyan }
  Write-Host "    $Cmd" -ForegroundColor DarkGray
  Invoke-Expression $Cmd
  if ($LASTEXITCODE -ne 0) {
    if ($ContinueOnError) {
      Write-Host "    WARNING: Command failed (exit $LASTEXITCODE) but continuing: $Cmd" -ForegroundColor Yellow
    } else {
      throw "Command failed (exit $LASTEXITCODE): $Cmd"
    }
  }
}

function New-RandomSuffix {
  param([int]$Len = 6)
  $chars = "abcdefghijklmnopqrstuvwxyz0123456789".ToCharArray()
  -join (1..$Len | ForEach-Object { $chars | Get-Random })
}

function Test-Preflight {
  Write-Host "`n==> Preflight checks" -ForegroundColor Cyan

  $gcloudCmd = Get-Command gcloud -ErrorAction SilentlyContinue
  if (-not $gcloudCmd) {
    throw "gcloud CLI not found on PATH. Install gcloud and run 'gcloud auth login' before using this script."
  }

  $activeAccount = (& gcloud auth list --format="value(account)" --filter="status:ACTIVE" 2>$null)
  if (-not $activeAccount) {
    throw "No active gcloud account found. Run 'gcloud auth login' and select an account before using this script."
  }

  Write-Host "  gcloud:  $($gcloudCmd.Source)" -ForegroundColor Gray
  Write-Host "  Active account: $activeAccount" -ForegroundColor Gray
}

function Test-BillingEnabled {
  param([string]$ProjectId)
  
  $billingEnabled = (& gcloud beta billing projects describe $ProjectId --format="value(billingEnabled)" 2>$null)
  return ($billingEnabled -eq "True")
}

# Normalize to lowercase IDs as per checklist (GCP resource IDs must be lowercase)
$ClientCode = $ClientCode.ToLower()
$Env        = $Env.ToLower()

# Run basic environment checks before doing any work
Test-Preflight

# Project and bucket naming aligned with checklist naming standard
$ProjectId = ("aiops-gc-{0}-{1}" -f $ClientCode, $Env).ToLower()
$ProjectDisplay = ("AIOPS-GC-{0}-{1}" -f $ClientCode.ToUpper(), $Env.ToUpper())
$SaId = "aiops-gc-app"
$SaEmail = "$SaId@$ProjectId.iam.gserviceaccount.com"

# Foundation state file (used to persist chosen bucket, etc.)
$KeyPath = $null
$StatePath = Join-Path $SecretsDir "gc-foundation.json"

# Bucket must be globally unique (4-8 chars per checklist) but stable per project on reruns.
$Bucket = $null

# 1) Explicit override wins if provided
if ($BucketName -and $BucketName.Trim().Length -gt 0) {
  $Bucket = $BucketName.ToLower()
}
# 2) Otherwise, reuse from persisted state if available for this project
elseif (Test-Path $StatePath) {
  try {
    $existingState = Get-Content $StatePath -Raw | ConvertFrom-Json
  } catch {
    $existingState = $null
  }
  if ($existingState -and $existingState.ProjectId -eq $ProjectId -and $existingState.Bucket) {
    $Bucket = $existingState.Bucket
  }
}
# 3) Fallback: generate a new suffix and derive bucket name
if (-not $Bucket) {
  $suffix = New-RandomSuffix -Len 6
  $Bucket = ("aiops-gc-{0}-{1}-uploads-{2}" -f $ClientCode, $Env, $suffix).ToLower()
}

Write-Host "`n=== AIOPS Google Cloud Foundation Bootstrap ===" -ForegroundColor White
Write-Host "  PROJECT_ID:   $ProjectId"
Write-Host "  PROJECT_NAME: $ProjectDisplay"
Write-Host "  SA_ID:        $SaId"
Write-Host "  SA_EMAIL:     $SaEmail"
Write-Host "  BUCKET:       gs://$Bucket"
Write-Host "  REGION:       $Region"
Write-Host ""

# 1) Create project (or verify exists) — Step 1
$existing = (& gcloud projects describe $ProjectId --format="value(projectId)" 2>$null)
if (-not $existing) {
  Invoke-Checked "gcloud projects create $ProjectId --name `"$ProjectDisplay`"" "Step 1 — Create project"
} else {
  Write-Host "`n==> Step 1 — Project already exists: $ProjectId" -ForegroundColor Yellow
}

Invoke-Checked "gcloud config set project $ProjectId" "Set active project"

# 2) Billing (optional automation) — Step 2
if ($BillingAccountId -and $BillingAccountId.Trim().Length -gt 0) {
  Invoke-Checked "gcloud beta billing projects link $ProjectId --billing-account $BillingAccountId" "Step 2 (optional) — Link billing"
} else {
  Write-Host "`n==> Step 2 — Billing link is MANUAL (recommended client-owned billing)." -ForegroundColor Yellow
  Write-Host "    Verify: gcloud beta billing projects describe $ProjectId --format=`"value(billingEnabled)`""
  Write-Host "    See checklist Step 2-3 for billing account link + budget configuration."
}

# Check billing status before enabling APIs
Write-Host "`n==> Checking billing status..." -ForegroundColor Cyan
$billingEnabled = Test-BillingEnabled -ProjectId $ProjectId

if (-not $billingEnabled) {
  Write-Host "`n⚠️  WARNING: Billing is NOT enabled for project $ProjectId" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "Some APIs require billing to be enabled. You have two options:" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "Option 1: Link billing account now (if you have a billing account ID):" -ForegroundColor Cyan
  Write-Host "  .\Scripts\GC-Build.ps1 -BillingAccountId `"YOUR_BILLING_ACCOUNT_ID`"" -ForegroundColor White
  Write-Host ""
  Write-Host "Option 2: Link billing manually, then rerun this script:" -ForegroundColor Cyan
  Write-Host "  1. Go to: https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId" -ForegroundColor White
  Write-Host "  2. Link your billing account" -ForegroundColor White
  Write-Host "  3. Rerun this script (it will skip already-created resources)" -ForegroundColor White
  Write-Host ""
  Write-Host "Attempting to enable Storage API (may work without billing)..." -ForegroundColor Yellow
  
  # Try to enable storage API first (usually doesn't require billing for basic operations)
  Invoke-Checked "gcloud services enable storage.googleapis.com" "Step 4 — Enable Storage API (no billing required)" -ContinueOnError $true
  
  Write-Host ""
  Write-Host "❌ Cannot continue: APIs that require billing cannot be enabled:" -ForegroundColor Red
  Write-Host "  - aiplatform.googleapis.com (Vertex AI)" -ForegroundColor Red
  Write-Host "  - discoveryengine.googleapis.com (Vertex AI Search)" -ForegroundColor Red
  Write-Host "  - secretmanager.googleapis.com (Secret Manager)" -ForegroundColor Red
  Write-Host ""
  Write-Host "Please link billing and rerun this script. The script is idempotent and will" -ForegroundColor Yellow
  Write-Host "skip already-created resources (project, etc.) and continue from where it left off." -ForegroundColor Yellow
  exit 1
} else {
  Write-Host "  ✓ Billing is enabled" -ForegroundColor Green
}

# 4) Enable APIs — Step 4
Invoke-Checked "gcloud services enable aiplatform.googleapis.com discoveryengine.googleapis.com storage.googleapis.com secretmanager.googleapis.com" "Step 4 — Enable mandatory APIs"

# 5) Create app service account (idempotent) — Step 5
$saExists = (& gcloud iam service-accounts list --format="value(email)" | Select-String -SimpleMatch $SaEmail)
if (-not $saExists) {
  Invoke-Checked "gcloud iam service-accounts create $SaId --display-name `"AIOPS-GC-APP`"" "Step 5 — Create app service account"
} else {
  Write-Host "`n==> Step 5 — Service account already exists: $SaEmail" -ForegroundColor Yellow
}

# 6) Grant project IAM roles — Step 6
Invoke-Checked "gcloud projects add-iam-policy-binding $ProjectId --member `"serviceAccount:$SaEmail`" --role roles/aiplatform.user" "Step 6 — Grant roles/aiplatform.user to app SA"
Invoke-Checked "gcloud projects add-iam-policy-binding $ProjectId --member `"serviceAccount:$SaEmail`" --role roles/discoveryengine.user" "Step 6 — Grant roles/discoveryengine.user to app SA"

if ($GrantSecretAccessor) {
  Invoke-Checked "gcloud projects add-iam-policy-binding $ProjectId --member `"serviceAccount:$SaEmail`" --role roles/secretmanager.secretAccessor" "Step 6 (optional) — Grant roles/secretmanager.secretAccessor to app SA"
}

# 7) Ensure Google-managed service agents exist — Step 7
# (Some environments only create these on first use; creating explicitly avoids later confusion.)
Invoke-Checked "gcloud beta services identity create --service discoveryengine.googleapis.com --project $ProjectId" "Step 7 — Ensure Discovery Engine service agent exists" -ContinueOnError $true
Invoke-Checked "gcloud beta services identity create --service aiplatform.googleapis.com --project $ProjectId" "Step 7 — Ensure Vertex AI service agent exists" -ContinueOnError $true

# Get project number for service agent identities
$ProjectNumber = (& gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()
if (-not $ProjectNumber) { throw "Could not resolve project number for $ProjectId" }
$DeServiceAgent = "service-$ProjectNumber@gcp-sa-discoveryengine.iam.gserviceaccount.com"

Write-Host "`nResolved identities:" -ForegroundColor White
Write-Host "  PROJECT_NUMBER:     $ProjectNumber"
Write-Host "  DE_SERVICE_AGENT:   $DeServiceAgent"
Write-Host ""

# 8) Create bucket — Step 8
# Use gcloud storage for bucket management.
$bucketExists = (& gcloud storage buckets describe "gs://$Bucket" --format="value(name)" 2>$null)
if (-not $bucketExists) {
  Invoke-Checked "gcloud storage buckets create gs://$Bucket --project $ProjectId --location $Region" "Step 8 — Create uploads bucket"
} else {
  Write-Host "`n==> Step 8 — Bucket already exists: gs://$Bucket" -ForegroundColor Yellow
}

# 8B) Bucket hardening (UBLA + PAP) — Step 8 recommended settings
Invoke-Checked "gcloud storage buckets update gs://$Bucket --uniform-bucket-level-access --pap" "Step 8B — Harden bucket (UBLA + PAP)"

# 10) Bucket IAM — Step 10
Invoke-Checked -Cmd "gcloud storage buckets add-iam-policy-binding gs://$Bucket --member `"serviceAccount:$SaEmail`" --role roles/storage.objectAdmin" -Description "Step 10A — Bucket IAM for app SA (objectAdmin)"
Invoke-Checked -Cmd "gcloud storage buckets add-iam-policy-binding gs://$Bucket --member `"serviceAccount:$DeServiceAgent`" --role roles/storage.objectViewer" -Description "Step 10B — Bucket IAM for Discovery Engine service agent (objectViewer)"

# 10C) Grant script runner (current gcloud account) objectAdmin so smoke test can upload/delete
$CurrentAccount = (& gcloud config get-value account 2>$null).Trim()
if ($CurrentAccount) {
  Invoke-Checked -Cmd "gcloud storage buckets add-iam-policy-binding gs://$Bucket --member `"user:$CurrentAccount`" --role roles/storage.objectAdmin" -Description "Step 10C — Bucket IAM for script runner (smoke test)"
}

# 11) Bucket smoke test — Step 11
Write-Host "`n==> Step 11 — Bucket smoke test" -ForegroundColor Cyan
$tmp = Join-Path $env:TEMP ("aiops-smoke-{0}.txt" -f ([guid]::NewGuid().ToString("N")))
"hello" | Out-File -FilePath $tmp -Encoding ascii
try {
  Invoke-Checked "gcloud storage cp `"$tmp`" gs://$Bucket/smoke/$(Split-Path $tmp -Leaf)" "  Upload test file"
  Invoke-Checked "gcloud storage rm gs://$Bucket/smoke/$(Split-Path $tmp -Leaf)" "  Delete test file"
  Write-Host "  Smoke test PASSED" -ForegroundColor Green
} catch {
  Write-Host "  Smoke test FAILED — check bucket permissions" -ForegroundColor Red
  throw
} finally {
  if (Test-Path $tmp) { Remove-Item $tmp -Force }
}

# 18) Dev key (optional; for local Docker only) — Step 18
if ($GenerateDevKey) {
  New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null
  $KeyPath = Join-Path $SecretsDir ("{0}__aiops-gc-app-key.json" -f $ProjectId)
  Write-Host "`n==> Step 18 — Generate dev key" -ForegroundColor Cyan
  Write-Host "WARNING: Generating a long-lived service account key (dev only). Do not use this approach in production." -ForegroundColor Yellow
  Invoke-Checked "gcloud iam service-accounts keys create `"$KeyPath`" --iam-account $SaEmail" "  Create key file"
  Write-Host "  Key written to: $KeyPath" -ForegroundColor White
} else {
  Write-Host "`n==> Step 18 — Dev key generation skipped (-GenerateDevKey:`$false)." -ForegroundColor Yellow
}

# Persist foundation state for reruns / handoff pack
try {
  New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null
  $state = [ordered]@{
    ProjectId                      = $ProjectId
    ProjectNumber                  = $ProjectNumber
    Region                         = $Region
    ClientCode                     = $ClientCode
    Env                            = $Env
    Bucket                         = $Bucket
    SaEmail                        = $SaEmail
    DiscoveryEngineServiceAgent    = $DeServiceAgent
  }
  if ($GenerateDevKey -and $KeyPath) {
    $state.KeyPath = $KeyPath
  }
  $state | ConvertTo-Json | Out-File -FilePath $StatePath -Encoding utf8
  Write-Host "`nFoundation state written to: $StatePath" -ForegroundColor Gray
} catch {
  Write-Host "`nWARNING: Failed to write foundation state file: $StatePath" -ForegroundColor Yellow
}

# Summary
Write-Host "`n=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Created Resources:" -ForegroundColor Cyan
Write-Host "  Project ID:        $ProjectId"
Write-Host "  Project Name:      $ProjectDisplay"
Write-Host "  Project Number:    $ProjectNumber"
Write-Host "  Bucket:            gs://$Bucket"
Write-Host "  Service Account:   $SaEmail"
if ($GenerateDevKey) {
  Write-Host "  Key File:          $KeyPath"
}
Write-Host ""
Write-Host "Next Manual Steps (per checklist):" -ForegroundColor Yellow
Write-Host "  [Step 2-3] Link billing account and configure budget/alerts (if not automated)" -ForegroundColor Yellow
Write-Host "  [Step 13-15] Create Vertex AI Search datastore/app from console and capture DATA_STORE_ID / ENGINE_ID" -ForegroundColor Yellow
Write-Host "  [Step 19] Run platform verification checks" -ForegroundColor Yellow
Write-Host "  [Step 20] Test your local /gcs/smoke endpoint once Docker credentials are wired" -ForegroundColor Yellow
Write-Host ""
Write-Host "For full checklist, see: docs/Operational_AI_for_SMEs_GCP_Prereq_Checklist_AIOPS_Naming.md" -ForegroundColor Gray
