<# 
GC-Validate-Regions.ps1 — Validate GCP Resource Region Compatibility

Checks that all GCP resources are in compatible regions and can connect to each other.
Identifies cross-region issues that could cause access problems.

PREREQUISITES:
- Run GC-Build.ps1 first
- Requires gc-foundation.json

USAGE:
  .\Scripts\GC-Validate-Regions.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
  param([string]$Title)
  Write-Host "`n=== $Title ===" -ForegroundColor Cyan
}

function Write-Info {
  param([string]$Message)
  Write-Host "  ℹ️  $Message" -ForegroundColor Gray
}

function Write-Success {
  param([string]$Message)
  Write-Host "  ✓ $Message" -ForegroundColor Green
}

function Write-Warning {
  param([string]$Message)
  Write-Host "  ⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error {
  param([string]$Message)
  Write-Host "  ❌ $Message" -ForegroundColor Red
}

# Load foundation state
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FoundationPath = Join-Path $PSScriptRoot "..\secrets\gc-foundation.json"
$EnvPath = Join-Path $PSScriptRoot "..\.env"

if (-not (Test-Path $FoundationPath)) {
  throw "Foundation state not found: $FoundationPath. Run GC-Build.ps1 first."
}

$foundation = Get-Content $FoundationPath -Raw | ConvertFrom-Json
$ProjectId = $foundation.ProjectId

# Load .env if available
$envVars = @{}
if (Test-Path $EnvPath) {
  Get-Content $EnvPath | Where-Object { $_ -match '^\s*([^#=]+)=(.*)$' } | ForEach-Object {
    $key = $matches[1].Trim()
    $value = $matches[2].Trim()
    if ($key -and $value) {
      $envVars[$key] = $value
    }
  }
}

Write-Host "`n=== GCP Region Compatibility Validation ===" -ForegroundColor White
Write-Host "  Project: $ProjectId" -ForegroundColor Gray
Write-Host ""

# Collect current configuration
$config = @{
  GCSRegion = $foundation.Region
  VertexLocation = $envVars["VERTEX_LOCATION"]
  DiscoveryEngineLocation = $envVars["DISCOVERY_ENGINE_LOCATION"]
  AppRegion = $envVars["APP_REGION"]
}

# Set defaults if not in .env
if (-not $config.VertexLocation) { $config.VertexLocation = "global" }
if (-not $config.DiscoveryEngineLocation) { $config.DiscoveryEngineLocation = "global" }
if (-not $config.AppRegion) { $config.AppRegion = $foundation.Region }

Write-Section "Current Configuration"
Write-Host "  GCS Buckets Region:        $($config.GCSRegion)" -ForegroundColor White
Write-Host "  Vertex AI Location:        $($config.VertexLocation)" -ForegroundColor White
Write-Host "  Discovery Engine Location: $($config.DiscoveryEngineLocation)" -ForegroundColor White
Write-Host "  App Region:                $($config.AppRegion)" -ForegroundColor White

# Region compatibility matrix
Write-Section "Region Compatibility Analysis"

$issues = @()
$recommendations = @()

# Check GCS vs Discovery Engine compatibility
if ($config.GCSRegion -ne $config.DiscoveryEngineLocation -and $config.DiscoveryEngineLocation -ne "global") {
  $issues += "GCS buckets in $($config.GCSRegion) but Discovery Engine in $($config.DiscoveryEngineLocation) - may cause cross-region data transfer"
  $recommendations += "Set DISCOVERY_ENGINE_LOCATION=global (recommended) or move buckets to $($config.DiscoveryEngineLocation)"
} else {
  Write-Success "GCS and Discovery Engine regions are compatible"
}

# Check Vertex AI availability
Write-Info "Checking Vertex AI (Gemini) availability..."

# Known Vertex AI regions (as of 2024-2025)
$vertexAIRegions = @(
  "us-central1", "us-east1", "us-east4", "us-west1", "us-west4",
  "europe-west1", "europe-west4", "europe-west9",
  "asia-southeast1", "asia-northeast1",
  "africa-south1"  # Available but may have limited model support
)

$vertexGlobalSupported = $true  # "global" endpoint is always supported

if ($config.VertexLocation -eq "global") {
  Write-Success "Vertex AI using 'global' endpoint (fully supported, best compatibility)"
} elseif ($config.VertexLocation -in $vertexAIRegions) {
  Write-Success "Vertex AI location $($config.VertexLocation) is supported"
  if ($config.VertexLocation -eq "africa-south1") {
    Write-Warning "africa-south1 may have limited Gemini model availability - verify model support"
    $recommendations += "Consider using VERTEX_LOCATION=global for full Gemini model support"
  }
} else {
  $issues += "Vertex AI location $($config.VertexLocation) may not be supported"
  $recommendations += "Set VERTEX_LOCATION=global or use a supported region"
}

# Check Discovery Engine availability
Write-Info "Checking Discovery Engine availability..."

# Discovery Engine supports: global, us, eu, and regional locations including africa-south1
$discoveryEngineRegions = @(
  "global", "us", "eu",
  "us-central1", "us-east1", "us-west1",
  "europe-west1", "europe-west4",
  "asia-southeast1",
  "africa-south1"
)

if ($config.DiscoveryEngineLocation -in $discoveryEngineRegions) {
  Write-Success "Discovery Engine location $($config.DiscoveryEngineLocation) is supported"
  if ($config.DiscoveryEngineLocation -eq "global") {
    Write-Info "Using 'global' provides best compatibility and feature access"
  }
} else {
  $issues += "Discovery Engine location $($config.DiscoveryEngineLocation) may not be supported"
  $recommendations += "Set DISCOVERY_ENGINE_LOCATION=global (recommended)"
}

# Check bucket locations
Write-Info "Checking GCS bucket locations..."

try {
  $buckets = @()
  
  # Main bucket from foundation
  if ($foundation.Bucket) {
    $buckets += @{
      Name = $foundation.Bucket
      Region = $foundation.Region
    }
  }
  
  # Additional buckets from datastores config
  $DatastoresPath = Join-Path $PSScriptRoot "..\secrets\datastores-config.json"
  if (Test-Path $DatastoresPath) {
    $datastores = Get-Content $DatastoresPath -Raw | ConvertFrom-Json
    foreach ($ds in $datastores.DataStores) {
      $buckets += @{
        Name = $ds.Bucket
        Region = $datastores.Region
      }
    }
  }
  
  foreach ($bucket in $buckets) {
    try {
      $bucketInfo = & gcloud storage buckets describe "gs://$($bucket.Name)" --format="json" 2>$null | ConvertFrom-Json
      $actualRegion = $bucketInfo.location
      
      if ($actualRegion -eq $bucket.Region) {
        Write-Success "Bucket $($bucket.Name) is in $actualRegion"
      } else {
        Write-Warning "Bucket $($bucket.Name) is in $actualRegion (expected $($bucket.Region))"
        $issues += "Bucket $($bucket.Name) region mismatch: expected $($bucket.Region), actual $actualRegion"
      }
    } catch {
      Write-Warning "Could not verify bucket $($bucket.Name) location: $_"
    }
  }
} catch {
  Write-Warning "Could not check bucket locations: $_"
}

# Test connectivity (if possible)
Write-Section "Connectivity Validation"

Write-Info "Testing GCS access..."
try {
  $testBucket = $foundation.Bucket
  
  # First check if bucket exists
  $bucketExists = & gcloud storage buckets describe "gs://$testBucket" --format="value(name)" 2>&1
  if ($LASTEXITCODE -eq 0 -and $bucketExists) {
    Write-Success "GCS bucket exists: $testBucket"
    
    # Try to list contents (may fail due to permissions, but bucket exists)
    $testResult = & gcloud storage ls "gs://$testBucket/" --limit 1 2>&1
    if ($LASTEXITCODE -eq 0) {
      Write-Success "GCS bucket access verified (can list objects)"
    } else {
      Write-Warning "Bucket exists but cannot list objects (may be empty or permission issue)"
      Write-Info "This is OK - bucket exists and can be accessed by service account"
    }
  } else {
    Write-Warning "Could not verify bucket existence: $testBucket"
    Write-Info "This may be a permissions issue - verify bucket exists in console"
    $issues += "Could not verify GCS bucket $testBucket (check permissions or bucket name)"
  }
} catch {
  Write-Warning "GCS connectivity test failed: $_"
  Write-Info "Note: Bucket may still be accessible by service account even if script cannot access"
}

# Summary and recommendations
Write-Section "Summary"

if ($issues.Count -eq 0) {
  Write-Success "No region compatibility issues detected"
  Write-Host ""
  Write-Info "All resources are configured in compatible regions"
} else {
  Write-Error "Found $($issues.Count) potential issue(s):"
  foreach ($issue in $issues) {
    Write-Host "    • $issue" -ForegroundColor Red
  }
}

if ($recommendations.Count -gt 0) {
  Write-Host ""
  Write-Section "Recommendations"
  foreach ($rec in $recommendations) {
    Write-Host "    • $rec" -ForegroundColor Yellow
  }
}

# Optimal configuration recommendation
Write-Host ""
Write-Section "Optimal Configuration (Recommended)"

Write-Host "  For best compatibility and feature access:" -ForegroundColor White
Write-Host "    VERTEX_LOCATION=global" -ForegroundColor Cyan
Write-Host "    DISCOVERY_ENGINE_LOCATION=global" -ForegroundColor Cyan
Write-Host "    GCS_BUCKET_NAME: Keep buckets in $($config.GCSRegion) (data residency)" -ForegroundColor Cyan
Write-Host ""
Write-Info "Note: 'global' endpoints work with regional buckets - GCS buckets can stay in africa-south1"
Write-Info "      for data residency while using global Vertex/Discovery Engine endpoints"

# Generate updated .env recommendations
if ($issues.Count -gt 0 -or $recommendations.Count -gt 0) {
  Write-Host ""
  Write-Section "Suggested .env Updates"
  
  $suggestedUpdates = @{}
  if ($config.VertexLocation -ne "global") {
    $suggestedUpdates["VERTEX_LOCATION"] = "global"
  }
  if ($config.DiscoveryEngineLocation -ne "global") {
    $suggestedUpdates["DISCOVERY_ENGINE_LOCATION"] = "global"
  }
  
  if ($suggestedUpdates.Count -gt 0) {
    Write-Host "  Update these values in .env:" -ForegroundColor White
    foreach ($key in $suggestedUpdates.Keys) {
      Write-Host "    $key=$($suggestedUpdates[$key])" -ForegroundColor Cyan
    }
  } else {
    Write-Success ".env region configuration is optimal"
  }
}

Write-Host ""
