# NG-HEADER: Nombre de archivo: setup-siyuan.ps1
# NG-HEADER: Ubicación: scripts/setup-siyuan.ps1
# NG-HEADER: Descripción: Bootstrap idempotente de SiYuan, secretos locales y notebook Nice Grow.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [switch]$StartHttpMcp,
    [int]$TimeoutSec = 180
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$secretDir = if ($env:GROWEN_SECRET_DIR) { $env:GROWEN_SECRET_DIR } else { Join-Path $repoRoot '..\growen-secrets' }
$workspaceDir = if ($env:SIYUAN_WORKSPACE_DIR) { $env:SIYUAN_WORKSPACE_DIR } else { Join-Path $repoRoot '..\growen-siyuan\workspace' }
$accessCodeFile = Join-Path $secretDir 'siyuan_access_auth_code'
$apiTokenFile = Join-Path $secretDir 'siyuan_api_token'
$mcpSecretFile = Join-Path $secretDir 'mcp_siyuan_secret_key'

function New-RandomSecret {
    param([int]$Bytes = 32)
    $buffer = New-Object byte[] $Bytes
    $rng = New-Object Security.Cryptography.RNGCryptoServiceProvider
    try {
        $rng.GetBytes($buffer)
    } finally {
        $rng.Dispose()
    }
    return ([BitConverter]::ToString($buffer) -replace '-', '').ToLowerInvariant()
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Value
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Value, $utf8NoBom)
}

function Ensure-SecretFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Utf8NoBom -Path $Path -Value (New-RandomSecret)
    }
}

New-Item -ItemType Directory -Force -Path $secretDir, $workspaceDir | Out-Null
Ensure-SecretFile -Path $accessCodeFile
Ensure-SecretFile -Path $mcpSecretFile

$env:SIYUAN_ACCESS_AUTH_CODE = (Get-Content -Raw -LiteralPath $accessCodeFile).Trim()
$env:MCP_SIYUAN_SECRET_KEY = (Get-Content -Raw -LiteralPath $mcpSecretFile).Trim()
$env:SIYUAN_WORKSPACE_DIR = (Resolve-Path -LiteralPath $workspaceDir).Path
$env:SIYUAN_API_TOKEN_FILE = (Join-Path $secretDir 'siyuan_api_token')

Push-Location $repoRoot
try {
    docker compose --profile siyuan up -d siyuan
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar el contenedor SiYuan.' }

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        try {
            $null = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:6806/api/system/version' -TimeoutSec 3
            $ready = $true
        } catch {
            $ready = $false
            Start-Sleep -Milliseconds 750
        }
    } until ($ready -or (Get-Date) -ge $deadline)
    if (-not $ready) { throw 'SiYuan no respondió en el puerto 6806 dentro del timeout.' }

    $confPath = Join-Path $workspaceDir 'conf\conf.json'
    while (-not (Test-Path -LiteralPath $confPath) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path -LiteralPath $confPath)) { throw 'SiYuan no generó conf/conf.json.' }
    $conf = Get-Content -Raw -LiteralPath $confPath | ConvertFrom-Json
    $apiToken = [string]$conf.api.token
    if ([string]::IsNullOrWhiteSpace($apiToken)) { throw 'SiYuan no generó un API Token utilizable.' }
    Write-Utf8NoBom -Path $apiTokenFile -Value $apiToken.Trim()

    $headers = @{ Authorization = "Token $($apiToken.Trim())" }
    $listed = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:6806/api/notebook/lsNotebooks' -Headers $headers -ContentType 'application/json' -Body '{}'
    if ($listed.code -ne 0) { throw 'No se pudo listar notebooks de SiYuan.' }
    $notebook = @($listed.data.notebooks) | Where-Object { $_.name -eq 'Nice Grow' } | Select-Object -First 1
    if (-not $notebook) {
        $body = @{ name = 'Nice Grow' } | ConvertTo-Json -Compress
        $created = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:6806/api/notebook/createNotebook' -Headers $headers -ContentType 'application/json' -Body $body
        if ($created.code -ne 0) { throw 'No se pudo crear el notebook Nice Grow.' }
    }

    if ($StartHttpMcp) {
        docker compose --profile siyuan up -d mcp_siyuan
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar MCP SiYuan HTTP.' }
    }
    Write-Host 'SiYuan quedó configurado en http://127.0.0.1:6806 sin exponer secretos.' -ForegroundColor Green
} finally {
    Pop-Location
}
