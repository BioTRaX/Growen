# NG-HEADER: Nombre de archivo: diagnose_market.ps1
# NG-HEADER: Ubicación: scripts/diagnose_market.ps1
# NG-HEADER: Descripción: Script de diagnóstico para sistema de actualización de precios de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

Write-Host "=== Diagnóstico de Market Scraping ===" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar Redis
Write-Host "[1/5] Verificando Redis..." -ForegroundColor Yellow
$redisRunning = docker ps --filter "name=redis" --format "{{.Names}}: {{.Status}}" 2>$null
if ($redisRunning) {
    Write-Host "  OK $redisRunning" -ForegroundColor Green
} else {
    Write-Host "  X Redis NO esta corriendo" -ForegroundColor Red
    Write-Host "  -> Ejecuta: docker compose up -d redis" -ForegroundColor Gray
}
Write-Host ""

# 2. Verificar Worker
Write-Host "[2/5] Verificando Worker..." -ForegroundColor Yellow
$workerFound = $false
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
    if ($cmd -like "*market_scraping*" -or $cmd -like "*worker_market*") {
        Write-Host "  OK Worker CORRIENDO (PID: $($_.Id))" -ForegroundColor Green
        $workerFound = $true
    }
}
if (-not $workerFound) {
    Write-Host "  X Worker NO esta corriendo" -ForegroundColor Red
    Write-Host "  -> Ejecuta: .\scripts\start_worker_market.cmd" -ForegroundColor Gray
}
Write-Host ""

# 3. Verificar Cola Redis
Write-Host "[3/5] Verificando cola de mensajes..." -ForegroundColor Yellow
try {
    $queueLength = docker exec growen-redis redis-cli LLEN "dramatiq:market.DQ" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Mensajes en cola 'market': $queueLength" -ForegroundColor Cyan
        if ([int]$queueLength -gt 0) {
            Write-Host "  ! Hay tareas pendientes sin procesar" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  X No se pudo conectar a Redis" -ForegroundColor Red
    }
} catch {
    Write-Host "  X Error al consultar Redis: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# 4. Logs recientes del worker
Write-Host "[4/5] Últimos logs del worker..." -ForegroundColor Yellow
$logPath = "logs\worker_market.log"
if (Test-Path $logPath) {
    Write-Host "  Archivo: $logPath" -ForegroundColor Gray
    $lastLines = Get-Content $logPath -Tail 5 -ErrorAction SilentlyContinue
    if ($lastLines) {
        $lastLines | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Host "  (vacío)" -ForegroundColor Gray
    }
} else {
    Write-Host "  X No hay logs de worker (nunca se inicio)" -ForegroundColor Red
}
Write-Host ""

# 5. Variable REDIS_URL
Write-Host "[5/5] Verificando REDIS_URL..." -ForegroundColor Yellow
try {
    $redisUrl = python -c "import os; print(os.getenv('REDIS_URL', 'NO_CONFIGURADA'))" 2>$null
    if ($redisUrl -eq "NO_CONFIGURADA") {
        Write-Host "  ! REDIS_URL no configurada (usando default)" -ForegroundColor Yellow
        Write-Host "  -> Default: redis://localhost:6379/0" -ForegroundColor Gray
    } else {
        Write-Host "  OK REDIS_URL: $redisUrl" -ForegroundColor Green
    }
} catch {
    Write-Host "  X Error al verificar variable: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Resumen y recomendaciones
Write-Host "=== Resumen ===" -ForegroundColor Cyan
if (-not $redisRunning) {
    Write-Host "CRITICO: Redis no esta corriendo" -ForegroundColor Red
    Write-Host "   1. docker compose up -d redis" -ForegroundColor White
}
if (-not $workerFound) {
    Write-Host "CRITICO: Worker no esta corriendo" -ForegroundColor Red
    Write-Host "   2. .\scripts\start_worker_market.cmd" -ForegroundColor White
}
if ($redisRunning -and $workerFound) {
    Write-Host "OK Sistema OPERATIVO: Redis y Worker estan corriendo" -ForegroundColor Green
    Write-Host "   Los precios deberian actualizarse correctamente" -ForegroundColor Gray
}
Write-Host ""
