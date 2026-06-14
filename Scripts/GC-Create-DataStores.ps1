<# 
GC-Create-DataStores.ps1 — Create Additional GCS Buckets and Vertex AI Search Data Stores

Creates additional storage buckets and Vertex AI Search data stores for:
- Operations (SOPs, manuals, procedures)
- Compliance/Legal (policies, contracts)
- Finance (tax, accounting documents)

This enables module-specific data stores aligned with PRD modular structure.

PREREQUISITES:
- Run GC-Build.ps1 first to create foundation (project, service account, etc.)
- Requires gc-foundation.json from GC-Build.ps1

USAGE:
  .\Scripts\GC-Create-DataStores.ps1
  .\Scripts\GC-Create-DataStores.ps1 -Region "us-central1"
#>

[CmdletBinding()]
param(
  # Region - defaults to region from gc-foundation.json if not provided
  [Parameter(Mandatory=$false)]
  [string]$Region = ""
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

# Load foundation state from GC-Build
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatePath = Join-Path $PSScriptRoot "..\secrets\gc-foundation.json"

if (-not (Test-Path $StatePath)) {
  throw "Foundation state file not found: $StatePath. Please run GC-Build.ps1 first."
}

$foundation = Get-Content $StatePath -Raw | ConvertFrom-Json
$ProjectId = $foundation.ProjectId
$ProjectNumber = $foundation.ProjectNumber
$Region = if ($Region) { $Region } else { $foundation.Region }
$ClientCode = $foundation.ClientCode
$Env = $foundation.Env
$SaEmail = $foundation.SaEmail
$DeServiceAgent = $foundation.DiscoveryEngineServiceAgent

Write-Host "`n=== Create Additional Data Stores ===" -ForegroundColor White
Write-Host "  PROJECT_ID:   $ProjectId"
Write-Host "  REGION:       $Region"
Write-Host "  SA_EMAIL:     $SaEmail"
Write-Host ""

# Define data stores to create
$DataStores = @(
  @{
    Name = "operations"
    DisplayName = "Operations"
    Description = "SOPs, manuals, and procedure guides"
    ImportPrefix = "operations"
  },
  @{
    Name = "compliance"
    DisplayName = "Compliance/Legal"
    Description = "Policies and contracts"
    ImportPrefix = "compliance"
  },
  @{
    Name = "finance"
    DisplayName = "Finance"
    Description = "Tax and accounting documents"
    ImportPrefix = "finance"
  }
)

$results = @()

foreach ($ds in $DataStores) {
  Write-Host "`n=== Processing: $($ds.DisplayName) ===" -ForegroundColor Cyan
  
  # Generate bucket name: aiops-gc-{clientcode}-{env}-{name}-{suffix}
  $suffix = New-RandomSuffix -Len 6
  $BucketName = ("aiops-gc-{0}-{1}-{2}-{3}" -f $ClientCode, $Env, $ds.Name, $suffix).ToLower()
  
  Write-Host "  Bucket: gs://$BucketName" -ForegroundColor White
  
  # Check if bucket exists
  $bucketExists = (& gcloud storage buckets describe "gs://$BucketName" --format="value(name)" 2>$null)
  
  if (-not $bucketExists) {
    # Create bucket
    Invoke-Checked "gcloud storage buckets create gs://$BucketName --project $ProjectId --location $Region" "Create $($ds.DisplayName) bucket"
    
    # Harden bucket (UBLA + PAP)
    Invoke-Checked "gcloud storage buckets update gs://$BucketName --uniform-bucket-level-access --pap" "Harden bucket (UBLA + PAP)"
    
    # Set IAM permissions (objectAdmin for Discovery Engine so Vertex AI can read objects)
    Invoke-Checked "gcloud storage buckets add-iam-policy-binding gs://$BucketName --member `"serviceAccount:$SaEmail`" --role roles/storage.objectAdmin" "Grant app SA objectAdmin"
    Invoke-Checked "gcloud storage buckets add-iam-policy-binding gs://$BucketName --member `"serviceAccount:$DeServiceAgent`" --role roles/storage.objectAdmin" "Grant Discovery Engine SA objectAdmin (required for storage.objects.get)"
    # Grant current user objectViewer so Vertex AI console can validate path (storage.objects.get)
    $CurrentAccount = (& gcloud config get-value account 2>$null).Trim()
    if ($CurrentAccount) {
      Invoke-Checked "gcloud storage buckets add-iam-policy-binding gs://$BucketName --member `"user:$CurrentAccount`" --role roles/storage.objectViewer" "Grant current user objectViewer (console validation)"
    }
    Write-Host "  ✓ Bucket created and configured" -ForegroundColor Green
  } else {
    Write-Host "  Bucket already exists: gs://$BucketName" -ForegroundColor Yellow
    # Ensure Discovery Engine and current user have access (fixes storage.objects.get when creating datastore)
    Invoke-Checked "gcloud storage buckets add-iam-policy-binding gs://$BucketName --member `"serviceAccount:$DeServiceAgent`" --role roles/storage.objectAdmin" "Ensure Discovery Engine SA objectAdmin"
    $CurrentAccount = (& gcloud config get-value account 2>$null).Trim()
    if ($CurrentAccount) {
      Invoke-Checked "gcloud storage buckets add-iam-policy-binding gs://$BucketName --member `"user:$CurrentAccount`" --role roles/storage.objectViewer" "Ensure current user objectViewer (console validation)"
    }
  }
  
  # Create Vertex AI Search Data Store via console instructions
  # Note: Data store creation via API requires complex setup. We'll provide console instructions.
  Write-Host "`n  ⚠️  Data Store Creation:" -ForegroundColor Yellow
  Write-Host "     Vertex AI Search data stores must be created via console:" -ForegroundColor Yellow
  Write-Host "     1. Go to: https://console.cloud.google.com/gen-app-builder/data-stores?project=$ProjectId" -ForegroundColor White
  Write-Host "     2. Click 'Create Data Store'" -ForegroundColor White
  Write-Host "     3. Select 'Unstructured documents'" -ForegroundColor White
  Write-Host "     4. Select 'Cloud Storage' as source" -ForegroundColor White
  Write-Host "     5. Set import prefix: gs://$BucketName/$($ds.ImportPrefix)/" -ForegroundColor White
  Write-Host "     6. Name: $($ds.DisplayName) Data Store" -ForegroundColor White
  Write-Host "     7. Location: global (or your chosen location)" -ForegroundColor White
  Write-Host "     8. After creation, capture the DATA_STORE_ID from the data store details page" -ForegroundColor White
  
  $results += [ordered]@{
    Name = $ds.Name
    DisplayName = $ds.DisplayName
    Bucket = $BucketName
    ImportPrefix = "gs://$BucketName/$($ds.ImportPrefix)/"
    DataStoreId = ""  # To be filled manually after console creation
    EngineId = ""     # To be filled manually after console creation
  }
}

# Save results to config file
$ConfigPath = Join-Path $PSScriptRoot "..\secrets\datastores-config.json"
try {
  New-Item -ItemType Directory -Force -Path (Split-Path $ConfigPath) | Out-Null
  $config = [ordered]@{
    ProjectId = $ProjectId
    Region = $Region
    CreatedAt = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    DataStores = $results
  }
  $config | ConvertTo-Json -Depth 10 | Out-File -FilePath $ConfigPath -Encoding utf8
  Write-Host "`n✓ Configuration saved to: $ConfigPath" -ForegroundColor Green
} catch {
  Write-Host "`nWARNING: Failed to save config: $_" -ForegroundColor Yellow
}

# Summary
Write-Host "`n=== Summary ===" -ForegroundColor Green
Write-Host ""
Write-Host "Created Buckets:" -ForegroundColor Cyan
foreach ($ds in $results) {
  Write-Host "  $($ds.DisplayName): gs://$($ds.Bucket)" -ForegroundColor White
  Write-Host "    Import prefix: $($ds.ImportPrefix)" -ForegroundColor Gray
}

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "  1. Create Vertex AI Search data stores via console (see instructions above)" -ForegroundColor White
Write-Host "  2. After creating each data store, update secrets\datastores-config.json with:" -ForegroundColor White
Write-Host "     - DataStoreId (from data store details page)" -ForegroundColor White
Write-Host "     - EngineId (if creating separate search apps, or reuse existing ENGINE_ID)" -ForegroundColor White
Write-Host "  3. Update .env with DATA_STORE_ID values (or use module-specific config)" -ForegroundColor White
Write-Host ""
Write-Host "Configuration file: $ConfigPath" -ForegroundColor Gray
