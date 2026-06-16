<#
Creates or verifies Agent Search data stores and search apps for document domains.

This script reads secrets/domain-registry.json, creates one data store and one
search app per domain when missing, and writes the resulting IDs back to the
registry file used by Docker containers.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$false)]
  [string]$RegistryPath = "$PSScriptRoot\..\secrets\domain-registry.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-AccessToken {
  $token = (& cmd /c "gcloud auth print-access-token 2>NUL").Trim()
  if (-not $token) {
    throw "Could not get gcloud access token. Run 'gcloud auth login' first."
  }
  return $token
}

function New-Headers {
  param([string]$ProjectId)
  return @{
    Authorization = "Bearer $(Get-AccessToken)"
    "Content-Type" = "application/json"
    "X-Goog-User-Project" = $ProjectId
  }
}

function Invoke-DiscoveryRequest {
  param(
    [string]$Method,
    [string]$Uri,
    [string]$ProjectId,
    [object]$Body = $null,
    [bool]$AllowNotFound = $false
  )

  $params = @{
    Method = $Method
    Uri = $Uri
    Headers = (New-Headers -ProjectId $ProjectId)
  }
  if ($null -ne $Body) {
    $params.Body = ($Body | ConvertTo-Json -Depth 20)
  }

  try {
    return Invoke-RestMethod @params
  } catch {
    $response = $_.Exception.Response
    if ($AllowNotFound -and $response -and [int]$response.StatusCode -eq 404) {
      return $null
    }
    throw
  }
}

function Wait-EngineExists {
  param(
    [string]$EngineUri,
    [string]$ProjectId
  )

  for ($i = 0; $i -lt 60; $i++) {
    $engine = Invoke-DiscoveryRequest -Method Get -Uri $EngineUri -ProjectId $ProjectId -AllowNotFound $true
    if ($engine) {
      return
    }
    Start-Sleep -Seconds 5
  }
  throw "Timed out waiting for engine: $EngineUri"
}

function New-ResourceId {
  param(
    [string]$ProjectId,
    [string]$Domain,
    [string]$Suffix
  )
  return ("{0}-{1}-{2}" -f $ProjectId, $Domain, $Suffix).ToLower() -replace "[^a-z0-9_-]", "-"
}

if (-not (Test-Path $RegistryPath)) {
  throw "Domain registry not found: $RegistryPath"
}

$registry = Get-Content $RegistryPath -Raw | ConvertFrom-Json
$projectId = $registry.project_id
$resourceProject = if ($registry.project_number) { $registry.project_number } else { $projectId }
$location = if ($registry.location) { $registry.location } else { "global" }
$baseUri = "https://discoveryengine.googleapis.com/v1/projects/$projectId/locations/$location/collections/default_collection"

Write-Host "Provisioning domain RAG resources for project $projectId in $location" -ForegroundColor Cyan

foreach ($domain in $registry.domains) {
  $domainId = $domain.domain.ToLower()
  $dataStoreId = if ($domain.data_store_id) { $domain.data_store_id } else { New-ResourceId -ProjectId $projectId -Domain $domainId -Suffix "store" }
  $engineId = if ($domain.engine_id) { $domain.engine_id } else { New-ResourceId -ProjectId $projectId -Domain $domainId -Suffix "search" }

  Write-Host "`n==> $($domain.display_name)" -ForegroundColor Cyan

  $dataStoreUri = "$baseUri/dataStores/$dataStoreId"
  $existingDataStore = Invoke-DiscoveryRequest -Method Get -Uri $dataStoreUri -ProjectId $projectId -AllowNotFound $true
  if ($existingDataStore) {
    Write-Host "Data store exists: $dataStoreId" -ForegroundColor Yellow
  } else {
    $dataStoreBody = @{
      displayName = "$($domain.display_name) Documents"
      industryVertical = "GENERIC"
      solutionTypes = @("SOLUTION_TYPE_SEARCH")
      contentConfig = "CONTENT_REQUIRED"
    }
    Invoke-DiscoveryRequest -Method Post -Uri "$baseUri/dataStores?dataStoreId=$dataStoreId" -ProjectId $projectId -Body $dataStoreBody | Out-Null
    Write-Host "Created data store: $dataStoreId" -ForegroundColor Green
  }

  $engineUri = "$baseUri/engines/$engineId"
  $existingEngine = Invoke-DiscoveryRequest -Method Get -Uri $engineUri -ProjectId $projectId -AllowNotFound $true
  if ($existingEngine) {
    Write-Host "Search app exists: $engineId" -ForegroundColor Yellow
  } else {
    $engineBody = @{
      displayName = "$($domain.display_name) Search"
      dataStoreIds = @($dataStoreId)
      solutionType = "SOLUTION_TYPE_SEARCH"
      industryVertical = "GENERIC"
      searchEngineConfig = @{
        searchTier = "SEARCH_TIER_ENTERPRISE"
        searchAddOns = @("SEARCH_ADD_ON_LLM")
      }
    }
    $operation = Invoke-DiscoveryRequest -Method Post -Uri "$baseUri/engines?engineId=$engineId" -ProjectId $projectId -Body $engineBody
    if ($operation.name) {
      Write-Host "Waiting for search app: $engineId" -ForegroundColor Gray
      Wait-EngineExists -EngineUri $engineUri -ProjectId $projectId
    }
    Write-Host "Created search app: $engineId" -ForegroundColor Green
  }

  $domain.data_store_id = $dataStoreId
  $domain.engine_id = $engineId
  $domain.serving_config = "projects/$resourceProject/locations/$location/collections/default_collection/engines/$engineId/servingConfigs/default_search"
}

$registry | ConvertTo-Json -Depth 20 | Set-Content -Path $RegistryPath -Encoding utf8
Write-Host "`nUpdated registry: $RegistryPath" -ForegroundColor Green
