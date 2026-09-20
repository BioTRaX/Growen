# NG-HEADER: Nombre de archivo: diagnose_market.ps1
# NG-HEADER: Ubicación: scripts/diagnose_market.ps1
# NG-HEADER: Descripción: Diagnóstico read-only del broker, consumidor y logs del worker Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$logPath = Join-Path $projectRoot "logs\worker_market.log"

Push-Location $projectRoot
try {
    Write-Host "=== Diagnóstico de Market Scraping ===" -ForegroundColor Cyan

    Write-Host "`n[1/5] Redis" -ForegroundColor Yellow
    $redisStatus = docker compose ps redis --format json 2>$null
    $redisRunning = $LASTEXITCODE -eq 0 -and $redisStatus
    if ($redisRunning) {
        Write-Host "  OK Redis figura activo en Compose" -ForegroundColor Green
    } else {
        Write-Host "  ERROR Redis no está activo o Docker no responde" -ForegroundColor Red
    }

    Write-Host "`n[2/5] Consumidor market" -ForegroundColor Yellow
    $workerPids = @()
    if (Test-Path $pythonExe) {
        $workerPids = @(& $pythonExe -c "import os, psutil; excluded={os.getpid(), *(p.pid for p in psutil.Process().parents())}; print('\n'.join(str(p.info['pid']) for p in psutil.process_iter(['pid','cmdline']) if p.info['pid'] not in excluded and 'dramatiq' in ' '.join(p.info.get('cmdline') or []).lower() and 'market_scraping' in ' '.join(p.info.get('cmdline') or []).lower()))" 2>$null) | Where-Object { $_ }
    }
    if ($workerPids.Count -gt 0) {
        Write-Host "  OK Worker activo (PID: $($workerPids -join ', '))" -ForegroundColor Green
    } else {
        Write-Host "  ERROR No hay consumidor de la cola market" -ForegroundColor Red
    }

    Write-Host "`n[3/5] Colas Dramatiq" -ForegroundColor Yellow
    $ready = 0
    $delayed = 0
    if ($redisRunning) {
        $readyValue = docker compose exec -T redis redis-cli LLEN "dramatiq:market" 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = [int]$readyValue }
        $delayedValue = docker compose exec -T redis redis-cli ZCARD "dramatiq:market.DQ" 2>$null
        if ($LASTEXITCODE -eq 0) { $delayed = [int]$delayedValue }
    }
    Write-Host "  Listos: $ready | diferidos: $delayed" -ForegroundColor Cyan
    if (($ready + $delayed) -gt 0 -and $workerPids.Count -eq 0) {
        Write-Host "  ERROR Hay trabajos sin consumidor" -ForegroundColor Red
    }

    Write-Host "`n[4/5] Log" -ForegroundColor Yellow
    if (Test-Path $logPath) {
        Get-Item $logPath | Select-Object FullName, Length, LastWriteTime
        Get-Content $logPath -Tail 10
    } else {
        Write-Host "  INFO El worker todavía no generó su log" -ForegroundColor Gray
    }

    Write-Host "`n[5/5] Configuración" -ForegroundColor Yellow
    if ($env:REDIS_URL) {
        Write-Host "  OK REDIS_URL está definida (valor oculto)" -ForegroundColor Green
    } else {
        Write-Host "  INFO Se usará el default local seguro 127.0.0.1:6379" -ForegroundColor Gray
    }

    Write-Host "`n=== Resultado ===" -ForegroundColor Cyan
    if ($redisRunning -and $workerPids.Count -gt 0) {
        Write-Host "OPERATIVO: broker y consumidor market activos" -ForegroundColor Green
        exit 0
    }

    Write-Host "NO OPERATIVO: iniciar Redis y luego .\scripts\start_worker_market.cmd" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
