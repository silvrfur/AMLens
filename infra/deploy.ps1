<#
.SYNOPSIS
  Provisions and deploys AMLens to Azure Container Apps (see DEPLOY.md).

.DESCRIPTION
  1. Creates/updates the platform (VNet, private PostgreSQL, registry, Key Vault, identities,
     Container Apps environment) from infra/main.bicep.
  2. Builds the images in Azure Container Registry (no local Docker needed).
  3. Deploys RAG, then the backend, then the frontend, plus the migrate (and seed) jobs.
  4. Runs `alembic upgrade head` (and the one-off data load with -Seed) inside the VNet.
  5. Checks /api/backend/health through the public frontend.

  Safe to re-run: generated secrets (PostgreSQL password, proxy key) are read back from
  Key Vault instead of being regenerated, and the seed job refuses to load twice.

  Secrets are never passed on the command line. Read from the environment or local files:
    TOKEN_SECRET            $env:AMLENS_TOKEN_SECRET, else backend\.env  (must be the team's value)
    Entra sign-in secret    $env:AMLENS_AUTH_CLIENT_SECRET               (with -AuthClientId)
    AI keys (-AIAuth keys)  $env:AMLENS_AZURE_OPENAI_KEY / $env:AMLENS_AZURE_SEARCH_KEY,
                            else backend\.env AZURE_OPENAI_API_KEY and RAG\.env AZURE_SEARCH_ADMIN_KEY

.EXAMPLE
  # Production-style: managed identity for Azure OpenAI / AI Search, Entra ID sign-in, load sample data
  $env:AMLENS_AUTH_CLIENT_SECRET = "<app registration secret>"
  .\infra\deploy.ps1 -AzureOpenAIEndpoint https://<openai>.openai.azure.com/ `
      -AzureSearchEndpoint https://<search>.search.windows.net `
      -AzureOpenAIResourceId /subscriptions/.../Microsoft.CognitiveServices/accounts/<openai> `
      -AzureSearchResourceId /subscriptions/.../Microsoft.Search/searchServices/<search> `
      -AuthClientId <app registration client id> -Seed
#>
[CmdletBinding()]
param(
    [string]$ResourceGroup = 'rg-amlens',
    [string]$Location = 'centralindia',
    [Parameter(Mandatory = $true)][string]$AzureOpenAIEndpoint,
    [Parameter(Mandatory = $true)][string]$AzureSearchEndpoint,
    [string]$AzureOpenAIChatDeployment = 'gpt-4.1-mini',
    [string]$AzureOpenAIEmbeddingDeployment = 'text-embedding-3-small',
    [ValidateSet('managedIdentity', 'keys')][string]$AIAuth = 'managedIdentity',
    [string]$AzureOpenAIResourceId = '',
    [string]$AzureSearchResourceId = '',
    [string]$AuthClientId = '',
    [switch]$AllowAnonymous,   # no sign-in: ONLY for a throwaway deployment without real data
    [switch]$Seed,             # load the sample data (infra/seed/seed.sql) into an empty database
    [string]$ImageTag = ''
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Az {
    # Runs az, fails loudly on a non-zero exit (az does not throw by itself).
    $out = & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed (exit $LASTEXITCODE)" }
    return $out
}

function Read-DotEnv([string]$path, [string]$name) {
    if (-not (Test-Path $path)) { return '' }
    foreach ($line in Get-Content $path) {
        if ($line -match "^\s*$name\s*=\s*(.*)$") { return $Matches[1].Trim() }
    }
    return ''
}

function New-Secret([int]$bytes = 32) {
    $buf = New-Object byte[] $bytes
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
    return -join ($buf | ForEach-Object { $_.ToString('x2') })
}

function Invoke-AcaJob([string]$job) {
    Write-Host "  starting job $job ..."
    $exec = Invoke-Az containerapp job start -n $job -g $ResourceGroup --query name -o tsv
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 10
        $status = Invoke-Az containerapp job execution show -n $job -g $ResourceGroup --job-execution-name $exec --query properties.status -o tsv
        if ($status -eq 'Succeeded') { Write-Host "  $job succeeded"; return }
        if ($status -eq 'Failed') { throw "Job $job failed; see: az containerapp job logs show -n $job -g $ResourceGroup --execution $exec --container $(($job -split '-')[-1])" }
    }
    throw "Job $job did not finish within 15 minutes"
}

# ---------------------------------------------------------------- preflight
Write-Host '== Checking Azure sign-in'
$account = Invoke-Az account show -o json | ConvertFrom-Json
Write-Host "  subscription: $($account.name)"

if (-not $AuthClientId -and -not $AllowAnonymous) {
    throw 'Pass -AuthClientId (Entra ID sign-in) or, for a throwaway test with no real data, -AllowAnonymous.'
}
$authSecret = ''
if ($AuthClientId) {
    $authSecret = $env:AMLENS_AUTH_CLIENT_SECRET
    if (-not $authSecret) { throw 'Set $env:AMLENS_AUTH_CLIENT_SECRET to the app registration client secret.' }
}
if ($AIAuth -eq 'managedIdentity' -and (-not $AzureOpenAIResourceId -or -not $AzureSearchResourceId)) {
    throw 'Managed identity needs -AzureOpenAIResourceId and -AzureSearchResourceId (or use -AIAuth keys).'
}
$openAIKey = ''; $searchKey = ''
if ($AIAuth -eq 'keys') {
    $openAIKey = $env:AMLENS_AZURE_OPENAI_KEY; if (-not $openAIKey) { $openAIKey = Read-DotEnv 'backend\.env' 'AZURE_OPENAI_API_KEY' }
    $searchKey = $env:AMLENS_AZURE_SEARCH_KEY; if (-not $searchKey) { $searchKey = Read-DotEnv 'RAG\.env' 'AZURE_SEARCH_ADMIN_KEY' }
    if (-not $openAIKey -or -not $searchKey) { throw 'Keys mode: Azure OpenAI or AI Search key not found.' }
}
$tokenSecret = $env:AMLENS_TOKEN_SECRET; if (-not $tokenSecret) { $tokenSecret = Read-DotEnv 'backend\.env' 'TOKEN_SECRET' }
if ($tokenSecret.Length -lt 32) { throw 'TOKEN_SECRET (>= 32 chars, the team value) not found in $env:AMLENS_TOKEN_SECRET or backend\.env.' }
if ($Seed -and -not (Test-Path 'infra\seed\seed.sql')) { throw 'Run `bash infra/seed/make-seed.sh` first to create infra\seed\seed.sql.' }

if (-not $ImageTag) {
    $ImageTag = (git rev-parse --short HEAD).Trim()
    if (git status --porcelain) { $ImageTag += '-dirty' + (Get-Date -Format 'MMddHHmm') }
}
Write-Host "  image tag: $ImageTag"
$deployer = (Invoke-Az ad signed-in-user show --query id -o tsv).Trim()

# ---------------------------------------------------------------- secrets (reuse if present)
Invoke-Az group create -n $ResourceGroup -l $Location -o none
$kvName = (Invoke-Az keyvault list -g $ResourceGroup --query '[0].name' -o tsv)
function Get-KvSecret([string]$name) {
    if (-not $kvName) { return '' }
    $v = & az keyvault secret show --vault-name $kvName -n $name --query value -o tsv 2>$null
    if ($LASTEXITCODE -ne 0) { return '' }
    return "$v".Trim()
}
$pgPassword = Get-KvSecret 'pg-admin-password'; if (-not $pgPassword) { $pgPassword = 'Pg' + (New-Secret 24) }
$proxyKey = Get-KvSecret 'proxy-key'; if (-not $proxyKey) { $proxyKey = New-Secret 32 }

# Parameters go through a temp file so secrets never appear in the process list.
$paramFile = Join-Path $env:TEMP ("amlens-params-{0}.json" -f [guid]::NewGuid())
function Invoke-Deployment([bool]$apps) {
    $p = @{
        location = $Location; deployerObjectId = $deployer
        postgresAdminPassword = $pgPassword; tokenSecret = $tokenSecret; proxyKey = $proxyKey
        azureOpenAIEndpoint = $AzureOpenAIEndpoint; azureOpenAIChatDeployment = $AzureOpenAIChatDeployment
        azureOpenAIEmbeddingDeployment = $AzureOpenAIEmbeddingDeployment; azureSearchEndpoint = $AzureSearchEndpoint
        aiAuth = $AIAuth; azureOpenAIResourceId = $AzureOpenAIResourceId; azureSearchResourceId = $AzureSearchResourceId
        azureOpenAIKey = $openAIKey; azureSearchKey = $searchKey
        authClientId = $AuthClientId; authClientSecret = $authSecret
        deployApps = $apps; imageTag = $ImageTag; deploySeedJob = [bool]$Seed
    }
    $doc = @{ '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'; contentVersion = '1.0.0.0'; parameters = @{} }
    foreach ($k in $p.Keys) { $doc.parameters[$k] = @{ value = $p[$k] } }
    $doc | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 $paramFile
    try {
        $name = 'amlens-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        return (Invoke-Az deployment group create -g $ResourceGroup -n $name -f infra\main.bicep -p "@$paramFile" --query properties.outputs -o json | ConvertFrom-Json)
    } finally { Remove-Item $paramFile -ErrorAction SilentlyContinue }
}

# ---------------------------------------------------------------- 1. platform
Write-Host '== 1/5 Platform (network, PostgreSQL, registry, Key Vault, identities, environment) - first run ~10 min'
$out = Invoke-Deployment $false
$acr = $out.acrName.value

# ---------------------------------------------------------------- 2. images
Write-Host "== 2/5 Building images in $acr"
Invoke-Az acr build -r $acr -t "amlens-rag:$ImageTag" RAG -o none
Invoke-Az acr build -r $acr -t "amlens-backend:$ImageTag" -f backend/Dockerfile . -o none
Invoke-Az acr build -r $acr -t "amlens-frontend:$ImageTag" frontend -o none
if ($Seed) { Invoke-Az acr build -r $acr -t "amlens-seed:$ImageTag" infra/seed -o none }

# ---------------------------------------------------------------- 3. apps
Write-Host '== 3/5 Deploying RAG, backend, frontend and jobs'
$out = Invoke-Deployment $true

# ---------------------------------------------------------------- 4. database
Write-Host '== 4/5 Database schema and data'
Invoke-AcaJob $out.migrateJobName.value
if ($Seed) { Invoke-AcaJob $out.seedJobName.value }
# The backend refuses to start on an out-of-date schema; restart it now that migrations ran.
$rev = Invoke-Az containerapp revision list -n $out.appNames.value.backend -g $ResourceGroup --query "[?properties.active].name | [0]" -o tsv
Invoke-Az containerapp revision restart -n $out.appNames.value.backend -g $ResourceGroup --revision $rev -o none

# ---------------------------------------------------------------- 5. check
Write-Host '== 5/5 Health check'
$url = $out.frontendUrl.value
for ($i = 0; $i -lt 30; $i++) {
    try {
        $h = Invoke-RestMethod "$url/api/backend/health" -TimeoutSec 10
        if ($h.backend -eq 'healthy' -and $h.agent -eq 'healthy' -and $h.rag -eq 'healthy') { break }
    } catch { }
    Start-Sleep -Seconds 10
}
Write-Host "  health: $($h | ConvertTo-Json -Compress)"
if (-not $h -or $h.rag -ne 'healthy' -or $h.backend -ne 'healthy') { throw 'Services did not become healthy; check the app logs in Log Analytics.' }
Write-Host "`nDone. Open $url, sign in, and run one investigation (DEPLOY.md, step 6)."

