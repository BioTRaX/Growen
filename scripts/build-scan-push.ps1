# NG-HEADER: Nombre de archivo: build-scan-push.ps1
# NG-HEADER: Ubicación: scripts/build-scan-push.ps1
# NG-HEADER: Descripción: Construye, escanea, publica y manifiesta imágenes productivas inmutables.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Registry = "192.168.100.100:5000",
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{7,40}$')][string]$SourceRevision,
    [Parameter(Mandatory = $true)][string]$RegistryPasswordFile,
    [string]$RegistryUser = "growen-deployer",
    [string]$OutputDir = "",
    [switch]$SkipFilesystemScan,
    [int]$TrivyExitCode = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$reportDir = if ($OutputDir) {
    [IO.Path]::GetFullPath($OutputDir)
} else {
    [IO.Path]::GetFullPath((Join-Path $repoRoot "backups/security/$($SourceRevision.ToLowerInvariant())"))
}
$trivyImage = "aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
$trivyCacheVolume = "growen_trivy_cache"

$builds = @(
    @{ Name="postgres"; Env="GROWEN_POSTGRES_IMAGE"; Dockerfile="infra/Dockerfile.postgres" },
    @{ Name="api"; Env="GROWEN_API_IMAGE"; Dockerfile="infra/Dockerfile.api" },
    @{ Name="frontend"; Env="GROWEN_FRONTEND_IMAGE"; Dockerfile="infra/Dockerfile.frontend" },
    @{ Name="telegram"; Env="GROWEN_TELEGRAM_IMAGE"; Dockerfile="infra/Dockerfile.telegram-worker" },
    @{ Name="dramatiq"; Env="GROWEN_DRAMATIQ_IMAGE"; Dockerfile="infra/Dockerfile.dramatiq" },
    @{ Name="market-worker"; Env="GROWEN_MARKET_WORKER_IMAGE"; Dockerfile="infra/Dockerfile.market-worker" },
    @{ Name="mcp-products"; Env="GROWEN_MCP_PRODUCTS_IMAGE"; Dockerfile="mcp_servers/products_server/Dockerfile" },
    @{ Name="mcp-web-search"; Env="GROWEN_MCP_WEB_SEARCH_IMAGE"; Dockerfile="mcp_servers/web_search_server/Dockerfile" },
    @{ Name="mcp-siyuan"; Env="GROWEN_MCP_SIYUAN_IMAGE"; Dockerfile="mcp_servers/siyuan_server/Dockerfile" },
    @{ Name="meli"; Env="GROWEN_MELI_IMAGE"; Dockerfile="infra/Dockerfile.meli-worker" }
)
$mirrors = @(
    @{ Name="redis"; Env="GROWEN_REDIS_IMAGE"; Source="redis:7-alpine" },
    @{ Name="siyuan"; Env="GROWEN_SIYUAN_IMAGE"; Source="b3log/siyuan:v3.8.1" },
    @{ Name="cloudflared"; Env="GROWEN_CLOUDFLARED_IMAGE"; Source="cloudflare/cloudflared:2026.8.3" }
)

if (-not $PSCmdlet.ShouldProcess($Registry, "Construir, escanear y publicar imágenes $SourceRevision")) {
    Write-Output "image_plan revision=$SourceRevision registry=$Registry builds=$($builds.Count) mirrors=$($mirrors.Count)"
    return
}
if (-not (Test-Path -LiteralPath $RegistryPasswordFile -PathType Leaf)) {
    throw "registry_password_file_missing"
}
[IO.Directory]::CreateDirectory($reportDir) | Out-Null
& docker volume create $trivyCacheVolume | Out-Null

function Invoke-CheckedDocker([string[]]$Arguments) {
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker_command_failed:$($Arguments[0])" }
}

function Resolve-PublishedDigest([string]$Reference, [string]$ImageName) {
    $repository = "$Registry/growen/$ImageName"
    $rawManifest = docker buildx imagetools inspect $Reference --format '{{json .Manifest}}'
    if ($LASTEXITCODE -ne 0 -or -not $rawManifest) { throw "image_digest_missing:$ImageName" }
    $manifest = $rawManifest | ConvertFrom-Json
    if ($manifest.digest -notmatch '^sha256:[0-9a-f]{64}$') { throw "registry_image_digest_invalid:$ImageName" }
    return "$repository@$($manifest.digest)"
}

function Invoke-Trivy([string]$Reference, [string]$SafeName) {
    $mount = "${reportDir}:/out"
    Invoke-CheckedDocker @(
        "run", "--rm", "-v", "${trivyCacheVolume}:/root/.cache", "-v", "/var/run/docker.sock:/var/run/docker.sock", "-v", $mount,
        $trivyImage, "image", "--exit-code", "$TrivyExitCode", "--severity", "HIGH,CRITICAL",
        "--scanners", "vuln",
        "--format", "json", "--output", "/out/$SafeName.vulnerabilities.json", $Reference
    )
    Invoke-CheckedDocker @(
        "run", "--rm", "-v", "${trivyCacheVolume}:/root/.cache", "-v", "/var/run/docker.sock:/var/run/docker.sock", "-v", $mount,
        $trivyImage, "image", "--format", "cyclonedx", "--output", "/out/$SafeName.sbom.cdx.json", $Reference
    )
}

function Invoke-TrivyFilesystem {
    $sourceMount = "${repoRoot}:/src:ro"
    $outputMount = "${reportDir}:/out"
    Invoke-CheckedDocker @(
        "run", "--rm", "-v", "${trivyCacheVolume}:/root/.cache", "-v", $sourceMount, "-v", $outputMount,
        $trivyImage, "fs", "--exit-code", "$TrivyExitCode", "--severity", "HIGH,CRITICAL",
        "--scanners", "vuln", "--timeout", "30m",
        "--skip-dirs", "/src/.venv",
        "--skip-dirs", "/src/.git",
        "--skip-dirs", "/src/frontend-vue/node_modules",
        "--skip-dirs", "/src/frontend/node_modules",
        "--skip-dirs", "/src/backups",
        "--skip-dirs", "/src/logs",
        "--skip-dirs", "/src/catalogos",
        "--skip-dirs", "/src/certs",
        "--skip-dirs", "/src/ImagenesTest",
        "--skip-dirs", "/src/data",
        "--skip-dirs", "/src/PR",
        "--format", "json",
        "--output", "/out/filesystem.vulnerabilities.json", "/src"
    )
}

if (-not $SkipFilesystemScan) {
    Invoke-TrivyFilesystem
}
& cmd.exe /c "type `"$RegistryPasswordFile`" | docker login $Registry --username $RegistryUser --password-stdin"
if ($LASTEXITCODE -ne 0) { throw "registry_login_failed" }

$records = [Collections.Generic.List[object]]::new()
foreach ($item in $builds) {
    $reference = "$Registry/growen/$($item.Name):$($SourceRevision.ToLowerInvariant())"
    Invoke-CheckedDocker @(
        "build", "--pull", "--label", "org.opencontainers.image.revision=$SourceRevision",
        "-f", (Join-Path $repoRoot $item.Dockerfile), "-t", $reference, $repoRoot
    )
    Invoke-Trivy $reference $item.Name
    Invoke-CheckedDocker @("push", $reference)
    $repoDigest = Resolve-PublishedDigest $reference $item.Name
    $records.Add([pscustomobject]@{ env=$item.Env; source=$reference; image=$repoDigest })
}

foreach ($item in $mirrors) {
    $reference = "$Registry/growen/$($item.Name):$($SourceRevision.ToLowerInvariant())"
    Invoke-CheckedDocker @("pull", $item.Source)
    Invoke-Trivy $item.Source $item.Name
    Invoke-CheckedDocker @("tag", $item.Source, $reference)
    Invoke-CheckedDocker @("push", $reference)
    $repoDigest = Resolve-PublishedDigest $reference $item.Name
    $records.Add([pscustomobject]@{ env=$item.Env; source=$item.Source; image=$repoDigest })
}

$manifestPath = Join-Path $reportDir "images.manifest.json"
$environmentPath = Join-Path $reportDir "images.env.ps1"
$utf8NoBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($manifestPath, ($records | ConvertTo-Json -Depth 4), $utf8NoBom)
$envLines = $records | ForEach-Object { '$env:{0}="{1}"' -f $_.env, $_.image }
[IO.File]::WriteAllLines($environmentPath, $envLines, $utf8NoBom)
Write-Output "images_published manifest=$manifestPath"

