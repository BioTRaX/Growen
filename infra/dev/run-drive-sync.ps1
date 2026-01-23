# NG-HEADER: Nombre de archivo: run-drive-sync.ps1
# NG-HEADER: Ubicación: infra/dev/run-drive-sync.ps1
# NG-HEADER: Descripción: Script para correr worker Drive Sync con hot-reload (watchmedo)
# NG-HEADER: Lineamientos: Ver AGENTS.md

Write-Host "🔄 Starting Drive Sync worker with hot-reload..." -ForegroundColor Cyan
Write-Host "   Watching: ./workers, ./services" -ForegroundColor Gray
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

watchmedo auto-restart `
    --directory=./workers `
    --directory=./services `
    --pattern="*.py" `
    --recursive `
    -- python -m workers.drive_sync
