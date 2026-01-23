# NG-HEADER: Nombre de archivo: run-all-workers.ps1
# NG-HEADER: Ubicación: infra/dev/run-all-workers.ps1
# NG-HEADER: Descripción: Script para correr todos los workers con hot-reload en terminales separadas
# NG-HEADER: Lineamientos: Ver AGENTS.md

Write-Host "🚀 Starting all workers with hot-reload..." -ForegroundColor Green
Write-Host ""

$scriptDir = $PSScriptRoot
$projectRoot = Resolve-Path "$scriptDir/../.."

# Abrir cada worker en una nueva ventana de terminal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\infra\dev\run-telegram.ps1" -WindowStyle Normal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\infra\dev\run-market.ps1" -WindowStyle Normal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\infra\dev\run-images.ps1" -WindowStyle Normal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\infra\dev\run-drive-sync.ps1" -WindowStyle Normal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\infra\dev\run-discovery.ps1" -WindowStyle Normal

Write-Host "✅ All workers started in separate terminal windows" -ForegroundColor Green
Write-Host "   Each window will auto-restart on .py file changes" -ForegroundColor Gray
