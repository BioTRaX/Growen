# NG-HEADER: Nombre de archivo: run-discovery.ps1
# NG-HEADER: Ubicación: infra/dev/run-discovery.ps1
# NG-HEADER: Descripción: Script para correr worker Discovery (catalog) con hot-reload (watchmedo)
# NG-HEADER: Lineamientos: Ver AGENTS.md

Write-Host "🔄 Starting Discovery worker with hot-reload..." -ForegroundColor Cyan
Write-Host "   Watching: ./workers, ./services" -ForegroundColor Gray
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

watchmedo auto-restart `
    --directory=./workers `
    --directory=./services `
    --pattern="*.py" `
    --recursive `
    -- python -m workers.discovery
