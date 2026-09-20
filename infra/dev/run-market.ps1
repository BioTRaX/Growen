# NG-HEADER: Nombre de archivo: run-market.ps1
# NG-HEADER: Ubicación: infra/dev/run-market.ps1
# NG-HEADER: Descripción: Script para correr worker Market Scraping con hot-reload (watchmedo)
# NG-HEADER: Lineamientos: Ver AGENTS.md

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$workerScript = Join-Path $projectRoot "scripts\start_worker_market.cmd"

if (-not (Test-Path $workerScript)) {
    throw "No se encontró el launcher canónico: $workerScript"
}

Write-Host "Iniciando worker Mercado con el launcher canónico..." -ForegroundColor Cyan
& $workerScript
exit $LASTEXITCODE
