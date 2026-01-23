# NG-HEADER: Nombre de archivo: run-telegram.ps1
# NG-HEADER: Ubicación: infra/dev/run-telegram.ps1
# NG-HEADER: Descripción: Script para correr worker Telegram con hot-reload (watchmedo)
# NG-HEADER: Lineamientos: Ver AGENTS.md

Write-Host "🔄 Starting Telegram worker with hot-reload..." -ForegroundColor Cyan
Write-Host "   Watching: ./workers, ./services, ./ai" -ForegroundColor Gray
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

watchmedo auto-restart `
    --directory=./workers `
    --directory=./services `
    --directory=./ai `
    --pattern="*.py" `
    --recursive `
    -- python -m workers.telegram_polling
