<#
dev-deploy.ps1 — SME Ops-Center Docker deploy (development)

Rebuilds, restarts, or stops the local Docker Compose stack for development.
This script does NOT provision Google Cloud resources — use GC-Build.ps1 for that.

================================================================================
QUICK START
================================================================================

PREREQUISITES:
1. Docker Desktop or Docker Engine with Docker Compose v2+
2. Copy and configure environment: cp .env.example .env
3. (Recommended) Run GCP foundation first: .\Scripts\GC-Build.ps1

COMMON COMMANDS:
  # Rebuild images and start all services in background (default)
  .\Scripts\dev-deploy.ps1

  # Start attached (stream logs in this terminal)
  .\Scripts\dev-deploy.ps1 -Foreground

  # Full rebuild without cache
  .\Scripts\dev-deploy.ps1 -Action Rebuild -NoCache

  # Restart specific services only
  .\Scripts\dev-deploy.ps1 -Action Restart -Services api-gateway,frontend

  # Stop and remove containers (keeps named volumes)
  .\Scripts\dev-deploy.ps1 -Action Down

  # Stop, remove containers, and delete named volumes (resets Postgres/Redis data)
  .\Scripts\dev-deploy.ps1 -Action Down -RemoveVolumes

  # Tail logs for all services
  .\Scripts\dev-deploy.ps1 -Action Logs -Follow

================================================================================
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $false)]
  [ValidateSet("Up", "Down", "Restart", "Rebuild", "Stop", "Logs", "Ps")]
  [string]$Action = "Up",

  [Parameter(Mandatory = $false)]
  [string[]]$Services = @(),

  [Parameter(Mandatory = $false)]
  [switch]$Foreground,

  [Parameter(Mandatory = $false)]
  [switch]$Build,

  [Parameter(Mandatory = $false)]
  [switch]$NoBuild,

  [Parameter(Mandatory = $false)]
  [switch]$NoCache,

  [Parameter(Mandatory = $false)]
  [switch]$Pull,

  [Parameter(Mandatory = $false)]
  [switch]$RemoveVolumes,

  [Parameter(Mandatory = $false)]
  [switch]$RemoveOrphans,

  [Parameter(Mandatory = $false)]
  [switch]$Follow,

  [Parameter(Mandatory = $false)]
  [string]$ComposeFile = "docker-compose.yml",

  [Parameter(Mandatory = $false)]
  [string]$ProjectName = "",

  [Parameter(Mandatory = $false)]
  [string]$ProjectRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Compose {
  param(
    [Parameter(Mandatory = $true)][string[]]$Args,
    [Parameter(Mandatory = $false)][string]$Description = ""
  )
  if ($Description) { Write-Host "`n==> $Description" -ForegroundColor Cyan }

  $cmdParts = @("compose")
  if ($script:ProjectName) { $cmdParts += @("-p", $script:ProjectName) }
  $cmdParts += @("-f", $script:ComposeFilePath)
  $cmdParts += $Args

  $display = "docker " + ($cmdParts -join " ")
  Write-Host "    $display" -ForegroundColor DarkGray

  & docker @cmdParts
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose failed (exit $LASTEXITCODE): $display"
  }
}

function Test-Preflight {
  Write-Host "`n==> Preflight checks" -ForegroundColor Cyan

  $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $dockerCmd) {
    throw "docker CLI not found on PATH. Install Docker Desktop or Docker Engine before using this script."
  }

  & docker compose version *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 is required. Ensure 'docker compose' works before using this script."
  }

  if (-not (Test-Path $script:ComposeFilePath)) {
    throw "Compose file not found: $($script:ComposeFilePath)"
  }

  $envPath = Join-Path $script:ProjectRoot ".env"
  if (-not (Test-Path $envPath)) {
    Write-Host "  WARNING: .env not found at $envPath — copy .env.example and configure values." -ForegroundColor Yellow
  }

  $defaultSaKey = Join-Path $script:ProjectRoot "secrets\aiops-gc-poc-pilot__aiops-gc-app-key.json"
  if (-not (Test-Path $defaultSaKey)) {
    Write-Host "  WARNING: Default GCP key not found at $defaultSaKey — run .\Scripts\GC-Build.ps1 or mount your own key." -ForegroundColor Yellow
  }

  Write-Host "  docker:  $($dockerCmd.Source)" -ForegroundColor Gray
  Write-Host "  compose: $script:ComposeFilePath" -ForegroundColor Gray
  Write-Host "  root:    $script:ProjectRoot" -ForegroundColor Gray
}

function Get-EnvValue {
  param(
    [Parameter(Mandatory = $true)][string]$Key,
    [Parameter(Mandatory = $false)][string]$Default = ""
  )
  $envPath = Join-Path $script:ProjectRoot ".env"
  if (-not (Test-Path $envPath)) { return $Default }

  foreach ($line in Get-Content $envPath) {
    if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.+)\s*$") {
      return $Matches[1].Trim().Trim('"').Trim("'")
    }
  }
  return $Default
}

function Write-SummaryLine {
  param(
    [Parameter(Mandatory = $true)][string]$Label,
    [Parameter(Mandatory = $true)][string]$Value,
    [Parameter(Mandatory = $false)][string]$Color = "Gray"
  )
  Write-Host ("  {0,-22} " -f $Label) -NoNewline -ForegroundColor DarkCyan
  Write-Host $Value -ForegroundColor $Color
}

function Show-QuickstartSummary {
  param(
    [Parameter(Mandatory = $false)][string]$EnvironmentLabel = "development"
  )

  $pgUser = Get-EnvValue -Key "POSTGRES_USER" -Default "smeops"
  $pgPassword = Get-EnvValue -Key "POSTGRES_PASSWORD" -Default "change-me"
  $pgDb = Get-EnvValue -Key "POSTGRES_DB" -Default "smeops"
  $gcpProject = Get-EnvValue -Key "GOOGLE_CLOUD_PROJECT" -Default "(not set in .env)"
  $gcsBucket = Get-EnvValue -Key "GCS_BUCKET_NAME" -Default "(not set in .env)"
  $storageBackend = Get-EnvValue -Key "STORAGE_BACKEND" -Default "local"
  $dataStoreId = Get-EnvValue -Key "DATA_STORE_ID" -Default "(not set)"
  $engineId = Get-EnvValue -Key "ENGINE_ID" -Default "(not set)"

  Write-Host "`n================================================================================" -ForegroundColor Green
  Write-Host " QUICKSTART - SME Ops-Center ($EnvironmentLabel)" -ForegroundColor Green
  Write-Host "================================================================================" -ForegroundColor Green

  Write-Host "`nWeb URLs" -ForegroundColor Yellow
  Write-SummaryLine "Frontend (Streamlit)" "http://localhost:8501"
  Write-SummaryLine "API Gateway" "http://localhost:8000"
  Write-SummaryLine "API docs (Swagger)" "http://localhost:8000/docs"
  Write-SummaryLine "MCP Bridge" "http://localhost:3000"
  Write-SummaryLine "Xero OAuth callback" "http://localhost:3000/oauth/xero/callback"

  Write-Host "`nHealth and verification" -ForegroundColor Yellow
  Write-SummaryLine "API health" "http://localhost:8000/health"
  Write-SummaryLine "MCP health" "http://localhost:3000/health"
  Write-SummaryLine "GCS smoke test" "http://localhost:8000/gcs/smoke"
  Write-SummaryLine "Docs status API" "http://localhost:8000/docs/status"

  Write-Host "`nExposed ports" -ForegroundColor Yellow
  Write-SummaryLine "frontend" "8501"
  Write-SummaryLine "api-gateway" "8000"
  Write-SummaryLine "mcp-bridge" "3000"
  Write-SummaryLine "postgres" "5432"
  Write-SummaryLine "redis" "6379"

  Write-Host "`nContainers" -ForegroundColor Yellow
  Write-SummaryLine "frontend" "sme-frontend"
  Write-SummaryLine "api-gateway" "sme-api-gateway"
  Write-SummaryLine "worker" "sme-worker"
  Write-SummaryLine "mcp-bridge" "sme-mcp-bridge"
  Write-SummaryLine "postgres" "sme-postgres"
  Write-SummaryLine "redis" "sme-redis"

  Write-Host "`nDatabase (Postgres)" -ForegroundColor Yellow
  Write-SummaryLine "Host" "localhost:5432"
  Write-SummaryLine "Database" $pgDb
  Write-SummaryLine "User" $pgUser
  Write-SummaryLine "Password" $pgPassword $(if ($pgPassword -eq "change-me") { "Yellow" } else { "Gray" })
  Write-SummaryLine "Connect" "psql -h localhost -U $pgUser -d $pgDb"
  if ($pgPassword -eq "change-me") {
    Write-Host "  WARNING: Postgres still uses the default password - change POSTGRES_PASSWORD in .env and docker-compose.yml." -ForegroundColor Yellow
  }

  Write-Host "`nApp auth" -ForegroundColor Yellow
  Write-SummaryLine "UI / API login" "Not enabled yet (Sprint 3 security baseline)"

  Write-Host "`nConfig (.env)" -ForegroundColor Yellow
  Write-SummaryLine "Storage backend" $storageBackend
  Write-SummaryLine "GCP project" $gcpProject
  Write-SummaryLine "GCS bucket" $gcsBucket
  Write-SummaryLine "Data store ID" $dataStoreId
  Write-SummaryLine "Engine ID" $engineId

  Write-Host "`nUseful commands" -ForegroundColor Yellow
  Write-SummaryLine "Container status" ".\Scripts\dev-deploy.ps1 -Action Ps"
  Write-SummaryLine "Follow logs" ".\Scripts\dev-deploy.ps1 -Action Logs -Follow"
  Write-SummaryLine "Restart API" ".\Scripts\dev-deploy.ps1 -Action Restart -Services api-gateway"
  Write-SummaryLine "Stop stack" ".\Scripts\dev-deploy.ps1 -Action Down"
  Write-SummaryLine "GCS smoke (PS)" "Invoke-RestMethod http://localhost:8000/gcs/smoke"

  Write-Host "`nFirst checks" -ForegroundColor Yellow
  Write-Host "  1. Open http://localhost:8501 - Docs module should load" -ForegroundColor Gray
  Write-Host "  2. Hit http://localhost:8000/health - expect healthy JSON" -ForegroundColor Gray
  Write-Host "  3. Hit http://localhost:8000/gcs/smoke - confirms GCP credentials and bucket access" -ForegroundColor Gray
  Write-Host "================================================================================`n" -ForegroundColor Green
}

function Get-ServiceArgs {
  if ($Services.Count -eq 0) { return @() }
  return $Services
}

# Resolve project root (repo root) from Scripts/
if (-not $ProjectRoot -or $ProjectRoot.Trim().Length -eq 0) {
  $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

$ComposeFilePath = if ([System.IO.Path]::IsPathRooted($ComposeFile)) {
  $ComposeFile
} else {
  Join-Path $ProjectRoot $ComposeFile
}

Test-Preflight

$normalizedAction = $Action.ToLowerInvariant()
$serviceArgs = Get-ServiceArgs

switch ($normalizedAction) {
  "up" {
    if ($Foreground.IsPresent) {
      Show-QuickstartSummary
      Write-Host "Starting attached - logs stream below. Press Ctrl+C to stop containers.`n" -ForegroundColor Yellow
    }
    $upArgs = @("up")
    # Dev default: rebuild images on start (equivalent to docker compose up --build)
    if ($NoBuild.IsPresent) {
      # skip --build
    } elseif (-not $PSBoundParameters.ContainsKey("Build") -or $Build.IsPresent) {
      $upArgs += "--build"
    }
    if (-not $Foreground.IsPresent) { $upArgs += "-d" }
    if ($RemoveOrphans.IsPresent) { $upArgs += "--remove-orphans" }
    if ($Pull.IsPresent) { $upArgs += @("--pull", "always") }
    $upArgs += $serviceArgs
    Invoke-Compose -Args $upArgs -Description "Start development stack"
  }

  "rebuild" {
    $buildArgs = @("build")
    if ($NoCache.IsPresent) { $buildArgs += "--no-cache" }
    if ($Pull.IsPresent) { $buildArgs += "--pull" }
    $buildArgs += $serviceArgs
    Invoke-Compose -Args $buildArgs -Description "Rebuild images"

    if ($Foreground.IsPresent) {
      Show-QuickstartSummary
      Write-Host "Starting attached - logs stream below. Press Ctrl+C to stop containers.`n" -ForegroundColor Yellow
    }

    $upArgs = @("up", "--remove-orphans")
    if (-not $Foreground.IsPresent) { $upArgs += "-d" }
    $upArgs += $serviceArgs
    $startDesc = if ($Foreground.IsPresent) { "Start rebuilt stack (foreground)" } else { "Start rebuilt stack (detached)" }
    Invoke-Compose -Args $upArgs -Description $startDesc
  }

  "restart" {
    $restartArgs = @("restart")
    $restartArgs += $serviceArgs
    Invoke-Compose -Args $restartArgs -Description "Restart services"
  }

  "stop" {
    $stopArgs = @("stop")
    $stopArgs += $serviceArgs
    Invoke-Compose -Args $stopArgs -Description "Stop services"
  }

  "down" {
    $downArgs = @("down")
    if ($RemoveVolumes.IsPresent) { $downArgs += "-v" }
    if ($RemoveOrphans.IsPresent) { $downArgs += "--remove-orphans" }
    Invoke-Compose -Args $downArgs -Description "Stop and remove containers"
  }

  "logs" {
    $logsArgs = @("logs")
    if ($Follow.IsPresent) { $logsArgs += "-f" }
    $logsArgs += $serviceArgs
    Invoke-Compose -Args $logsArgs -Description "Show service logs"
  }

  "ps" {
    Invoke-Compose -Args @("ps") -Description "List running services"
  }

  default {
    throw "Unsupported action: $Action"
  }
}

Write-Host "`n==> Done ($Action)" -ForegroundColor Green
if ($normalizedAction -in @("up", "rebuild") -and -not $Foreground.IsPresent) {
  Show-QuickstartSummary
}
