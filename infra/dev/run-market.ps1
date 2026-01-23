# NG-HEADER: Nombre de archivo: run-market.ps1
# NG-HEADER: Ubicación: infra/dev/run-market.ps1
# NG-HEADER: Descripción: Script para correr worker Market Scraping con hot-reload (watchmedo)
# NG-HEADER: Lineamientos: Ver AGENTS.md

Write-Host "🔄 Starting Market Scraping worker with hot-reload..." -ForegroundColor Cyan
Write-Host "   Watching: ./workers, ./services" -ForegroundColor Gray
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

watchmedo auto-restart `
    --directory=./workers `
    --directory=./services `
    --pattern="*.py" `
    --recursive `
    -- python -m workers.market_scraping
