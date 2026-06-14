<# 
GC-Fix-DiscoveryEngine-Permissions.ps1 — Fix Discovery Engine Service Agent Permissions

Grants the Discovery Engine service agent and your console user the necessary
permissions on GCS buckets so Vertex AI Search connectors and "Create data store"
path validation succeed.

PREREQUISITES:
- Run GC-Build.ps1 first
- Requires gc-foundation.json

USAGE:
  # Apply to all buckets in gc-foundation.json + datastores-config.json
  .\Scripts\GC-Fix-DiscoveryEngine-Permissions.ps1

  # Also apply to specific bucket(s) (e.g. new bucket not yet in config)
  .\Scripts\GC-Fix-DiscoveryEngine-Permissions.ps1 -BucketNames "aiops-gc-poc-pilot-compliance-hz2xah"

  # Only apply to specific bucket(s), skip config-based list
  .\Scripts\GC-Fix-DiscoveryEngine-Permissions.ps1 -BucketNames "aiops-gc-poc-pilot-compliance-hz2xah" -OnlyTheseBuckets
#>

[CmdletBinding()]
param(
  # Optional: additional bucket names (no gs://) to apply permissions to
  [Parameter(Mandatory=$false)]
  [string[]]$BucketNames = @(),
  # If true, only apply to -BucketNames (ignore foundation and datastores-config)
  [Parameter(Mandatory=$false)]
  [switch]$OnlyTheseBuckets = $false
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

# Load foundation state
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FoundationPath = Join-Path $PSScriptRoot "..\secrets\gc-foundation.json"

if (-not (Test-Path $FoundationPath)) {
  throw "Foundation state not found: $FoundationPath. Run GC-Build.ps1 first."
}

$foundation = Get-Content $FoundationPath -Raw | ConvertFrom-Json
$ProjectId = $foundation.ProjectId
$DeServiceAgent = $foundation.DiscoveryEngineServiceAgent

Write-Host "`n=== Fix Discovery Engine Service Agent Permissions ===" -ForegroundColor White
Write-Host "  Project: $ProjectId" -ForegroundColor Gray
Write-Host "  Service Agent: $DeServiceAgent" -ForegroundColor Gray
Write-Host ""

# Grant project-level storage.buckets.create permission
# Discovery Engine connectors may need to create temporary buckets during processing
Write-Host "Granting project-level Storage Admin role to Discovery Engine service agent..." -ForegroundColor Cyan
Write-Host "  Note: This allows Discovery Engine to create temporary buckets if needed" -ForegroundColor Yellow
Write-Host ""

# Grant project-level storage.admin (includes storage.buckets.create)
Invoke-Checked "gcloud projects add-iam-policy-binding $ProjectId --member `"serviceAccount:$DeServiceAgent`" --role roles/storage.admin" "Grant storage.admin role to Discovery Engine service agent"

# Also ensure bucket-level permissions are correct (upgrade to objectAdmin for full access)
Write-Host ""
Write-Host "Updating bucket-level permissions..." -ForegroundColor Cyan

# Build bucket list: from config (unless -OnlyTheseBuckets) plus any -BucketNames
$buckets = @()
if (-not $OnlyTheseBuckets) {
  if ($foundation.Bucket) {
    $buckets += $foundation.Bucket
  }
  $DatastoresPath = Join-Path $PSScriptRoot "..\secrets\datastores-config.json"
  if (Test-Path $DatastoresPath) {
    $datastores = Get-Content $DatastoresPath -Raw | ConvertFrom-Json
    foreach ($ds in $datastores.DataStores) {
      if ($ds.Bucket) {
        $buckets += $ds.Bucket
      }
    }
  }
}
foreach ($b in $BucketNames) {
  $trimmed = $b.Trim() -replace '^gs://', '' -replace '/$', ''
  if ($trimmed) { $buckets += $trimmed }
}

$uniqueBuckets = $buckets | Select-Object -Unique
if ($uniqueBuckets.Count -eq 0) {
  Write-Host "No buckets to update. Add buckets to datastores-config.json or pass -BucketNames." -ForegroundColor Yellow
  exit 0
}

Write-Host "Buckets to update: $($uniqueBuckets -join ', ')" -ForegroundColor Gray
Write-Host ""

foreach ($bucket in $uniqueBuckets) {
  Write-Host "  Updating permissions for: gs://$bucket" -ForegroundColor Gray
  # Discovery Engine service agent needs objectAdmin (includes storage.objects.get)
  Invoke-Checked "gcloud storage buckets add-iam-policy-binding gs://$bucket --member `"serviceAccount:$DeServiceAgent`" --role roles/storage.objectAdmin" "Grant objectAdmin to Discovery Engine SA on $bucket"
  # Console validates path using current user - grant so 'Missing required permissions: storage.objects.get' is resolved
  $CurrentAccount = (& gcloud config get-value account 2>$null).Trim()
  if ($CurrentAccount) {
    Invoke-Checked "gcloud storage buckets add-iam-policy-binding gs://$bucket --member `"user:$CurrentAccount`" --role roles/storage.objectViewer" "Grant objectViewer to current user (console validation)"
  }
}

Write-Host ""
Write-Host "✓ Permissions updated successfully" -ForegroundColor Green
Write-Host ""
Write-Host "The Discovery Engine service agent now has:" -ForegroundColor White
Write-Host "  • storage.admin (project-level) - allows bucket creation if needed" -ForegroundColor Gray
Write-Host "  • storage.objectAdmin (bucket-level) - full read/write access to buckets" -ForegroundColor Gray
Write-Host ""
Write-Host "Your console user has been granted storage.objectViewer on each bucket" -ForegroundColor White
Write-Host "  (fixes 'Missing required permissions: storage.objects.get' when creating datastore)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Wait 1-2 minutes for IAM propagation" -ForegroundColor White
Write-Host "  2. Refresh the Vertex AI 'Create data store' page and re-enter the GCS path" -ForegroundColor White
Write-Host "  3. Click Continue - the permission error should be gone" -ForegroundColor White
Write-Host ""
Write-Host "Note: Console user = the account from 'gcloud config get-value account'." -ForegroundColor Gray
Write-Host "      If you use a different Google account in the browser, grant that user" -ForegroundColor Gray
Write-Host "      Storage Object Viewer on the bucket in GCP Console → Storage → Bucket → Permissions." -ForegroundColor Gray
Write-Host ""
Write-Host "New datastore / bucket: To apply permissions to a bucket not in datastores-config.json," -ForegroundColor Gray
Write-Host "  .\Scripts\GC-Fix-DiscoveryEngine-Permissions.ps1 -BucketNames 'bucket-name'" -ForegroundColor Gray
Write-Host ""
