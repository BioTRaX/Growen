# NG-HEADER: Nombre de archivo: generate-manifest.ps1
# NG-HEADER: Ubicación: scripts/generate-manifest.ps1
# NG-HEADER: Descripción: Genera el manifiesto y variables de entorno de imágenes publicadas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding()]
param(
    [string]$Registry = "192.168.100.100:5000",
    [string]$SourceRevision = "bb48d80"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$reportDir = [IO.Path]::GetFullPath((Join-Path $repoRoot "backups/security/$($SourceRevision.ToLowerInvariant())"))
[IO.Directory]::CreateDirectory($reportDir) | Out-Null

$builds = @(
    @{ Name="postgres"; Env="GROWEN_POSTGRES_IMAGE" },
    @{ Name="api"; Env="GROWEN_API_IMAGE" },
    @{ Name="frontend"; Env="GROWEN_FRONTEND_IMAGE" },
    @{ Name="telegram"; Env="GROWEN_TELEGRAM_IMAGE" },
    @{ Name="dramatiq"; Env="GROWEN_DRAMATIQ_IMAGE" },
    @{ Name="market-worker"; Env="GROWEN_MARKET_WORKER_IMAGE" },
    @{ Name="mcp-products"; Env="GROWEN_MCP_PRODUCTS_IMAGE" },
    @{ Name="mcp-web-search"; Env="GROWEN_MCP_WEB_SEARCH_IMAGE" },
    @{ Name="mcp-siyuan"; Env="GROWEN_MCP_SIYUAN_IMAGE" },
    @{ Name="meli"; Env="GROWEN_MELI_IMAGE" }
)
$mirrors = @(
    @{ Name="redis"; Env="GROWEN_REDIS_IMAGE"; Source="redis:7-alpine" },
    @{ Name="siyuan"; Env="GROWEN_SIYUAN_IMAGE"; Source="b3log/siyuan:v3.8.1" },
    @{ Name="cloudflared"; Env="GROWEN_CLOUDFLARED_IMAGE"; Source="cloudflare/cloudflared:2026.8.3" }
)

$records = [Collections.Generic.List[object]]::new()
foreach ($item in $builds) {
    $reference = "$Registry/growen/$($item.Name):$($SourceRevision.ToLowerInvariant())"
    $repoDigest = (docker image inspect $reference --format '{{index .RepoDigests 0}}').Trim()
    if (-not $repoDigest) { throw "Missing digest for $($item.Name)" }
    $records.Add([pscustomobject]@{ env=$item.Env; source=$reference; image=$repoDigest })
}
foreach ($item in $mirrors) {
    $reference = "$Registry/growen/$($item.Name):$($SourceRevision.ToLowerInvariant())"
    $repoDigest = (docker image inspect $reference --format '{{index .RepoDigests 0}}').Trim()
    if (-not $repoDigest) { throw "Missing digest for $($item.Name)" }
    $records.Add([pscustomobject]@{ env=$item.Env; source=$item.Source; image=$repoDigest })
}

$manifestPath = Join-Path $reportDir "images.manifest.json"
$environmentPath = Join-Path $reportDir "images.env.ps1"
$utf8NoBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($manifestPath, ($records | ConvertTo-Json -Depth 4), $utf8NoBom)
$envLines = $records | ForEach-Object { '$env:{0}="{1}"' -f $_.env, $_.image }
[IO.File]::WriteAllLines($environmentPath, $envLines, $utf8NoBom)
Write-Output "manifest_generated: $manifestPath"
Write-Output "environment_generated: $environmentPath"
