# NG-HEADER: Nombre de archivo: stop-dev.ps1
# NG-HEADER: Ubicación: scripts/stop-dev.ps1
# NG-HEADER: Descripción: Detiene procesos locales iniciados por start-dev.ps1.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [string]$StateFile
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logRoot = Join-Path $root 'logs\dev'

if (-not $StateFile) {
    $latest = Get-ChildItem -LiteralPath $logRoot -Filter state.json -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw "No se encontró state.json bajo $logRoot."
    }
    $StateFile = $latest.FullName
}

$state = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json

function Stop-RegisteredProcessTree {
    param([Parameter(Mandatory)][int]$ProcessId)

    & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$entries = @(
    @{ Name = 'Frontend Vue'; Pid = $state.frontend_pid; StartedAt = $state.frontend_process_started_at; Reused = $state.frontend_reused },
    @{ Name = 'MCP Web Search'; Pid = $state.mcp_web_search_pid; StartedAt = $state.mcp_web_search_process_started_at; Reused = $state.mcp_web_search_reused },
    @{ Name = 'MCP Products'; Pid = $state.mcp_products_pid; StartedAt = $state.mcp_products_process_started_at; Reused = $state.mcp_products_reused },
    @{ Name = 'API'; Pid = $state.api_pid; StartedAt = $state.api_process_started_at; Reused = $state.api_reused }
)

foreach ($entry in $entries) {
    if (-not $entry.Pid -or $entry.Reused) {
        continue
    }
    $process = Get-Process -Id ([int]$entry.Pid) -ErrorAction SilentlyContinue
    if ($process) {
        if (-not $entry.StartedAt -or $process.StartTime.ToString('o') -ne [string]$entry.StartedAt) {
            Write-Warning "Se omitió $($entry.Name): el PID existe, pero no corresponde al proceso registrado."
            continue
        }
        Stop-RegisteredProcessTree -ProcessId $process.Id
        Write-Host "Detenido $($entry.Name) (PID $($process.Id))." -ForegroundColor Green
    }
}

Write-Host 'PostgreSQL no fue detenido; se administra de forma independiente mediante Docker Compose.' -ForegroundColor Cyan
