# NG-HEADER: Nombre de archivo: start-dev.ps1
# NG-HEADER: Ubicación: scripts/start-dev.ps1
# NG-HEADER: Descripción: Inicia PostgreSQL, servicios asíncronos opcionales, API, MCP y Vue con trazabilidad.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [int]$DatabaseTimeoutSec = 60,
    [int]$ApiTimeoutSec = 90,
    [int]$FrontendTimeoutSec = 60,
    [ValidateSet('Core', 'All', 'Off')]
    [string]$McpMode = 'Core',
    [switch]$WithCatalogWorker,
    [switch]$WithMarketWorker,
    [switch]$WithEnrichmentWorker,
    [switch]$WithKnowledgeWorker,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding

# Algunas sesiones de Windows heredan Path y PATH como entradas separadas.
# Start-Process usa un diccionario case-insensitive y falla ante ese duplicado.
$normalizedPath = [Environment]::GetEnvironmentVariable('Path', 'Process')
[Environment]::SetEnvironmentVariable('Path', $null, 'Process')
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $normalizedPath, 'Process')

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $root 'docker-compose.yml'
$python = Join-Path $root '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $root 'frontend-vue'
$frontendPackage = Join-Path $frontendRoot 'package.json'
$envFile = Join-Path $root '.env'
$runId = Get-Date -Format 'yyyyMMdd_HHmmss'
$logRoot = Join-Path $root 'logs\dev'
$runLogDir = Join-Path $logRoot $runId
$mainLog = Join-Path $runLogDir 'start-dev.log'
$databaseLog = Join-Path $runLogDir 'database.log'
$migrationLog = Join-Path $runLogDir 'migrations.log'
$dependenciesLog = Join-Path $runLogDir 'frontend-dependencies.log'
$apiStdoutLog = Join-Path $runLogDir 'api.stdout.log'
$apiStderrLog = Join-Path $runLogDir 'api.stderr.log'
$frontendStdoutLog = Join-Path $runLogDir 'frontend-vue.stdout.log'
$frontendStderrLog = Join-Path $runLogDir 'frontend-vue.stderr.log'
$mcpProductsStdoutLog = Join-Path $runLogDir 'mcp-products.stdout.log'
$mcpProductsStderrLog = Join-Path $runLogDir 'mcp-products.stderr.log'
$mcpWebStdoutLog = Join-Path $runLogDir 'mcp-web-search.stdout.log'
$mcpWebStderrLog = Join-Path $runLogDir 'mcp-web-search.stderr.log'
$enrichmentWorkerStdoutLog = Join-Path $runLogDir 'enrichment-worker.stdout.log'
$enrichmentWorkerStderrLog = Join-Path $runLogDir 'enrichment-worker.stderr.log'
$knowledgeWorkerStdoutLog = Join-Path $runLogDir 'knowledge-worker.stdout.log'
$knowledgeWorkerStderrLog = Join-Path $runLogDir 'knowledge-worker.stderr.log'
$stateFile = Join-Path $runLogDir 'state.json'
$startedProcesses = New-Object System.Collections.Generic.List[System.Diagnostics.Process]
$localCatalogWorkerPids = @()

New-Item -ItemType Directory -Path $runLogDir -Force | Out-Null

function Write-DevLog {
    param(
        [Parameter(Mandatory)]
        [string]$Message,
        [ValidateSet('INFO', 'OK', 'WARN', 'ERROR')]
        [string]$Level = 'INFO'
    )

    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Add-Content -LiteralPath $mainLog -Value $line -Encoding UTF8

    $color = switch ($Level) {
        'OK' { 'Green' }
        'WARN' { 'Yellow' }
        'ERROR' { 'Red' }
        default { 'Cyan' }
    }
    Write-Host $line -ForegroundColor $color
}

function Stop-DevelopmentProcessTree {
    param([Parameter(Mandatory)][int]$ProcessId)

    & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Assert-PathExists {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "No se encontró ${Description}: $Path"
    }
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory)]
        [string]$HostName,
        [Parameter(Mandatory)]
        [int]$Port,
        [int]$TimeoutMs = 750
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $client.BeginConnect($HostName, $Port, $null, $null)
        return $connection.AsyncWaitHandle.WaitOne($TimeoutMs, $false) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-TcpPort {
    param(
        [Parameter(Mandatory)]
        [string]$HostName,
        [Parameter(Mandatory)]
        [int]$Port,
        [Parameter(Mandatory)]
        [int]$TimeoutSec
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -HostName $HostName -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 750
    }
    return $false
}

function Find-PreviousLogSourceHint {
    param(
        [Parameter(Mandatory)][string]$Component,
        [Parameter(Mandatory)][string]$FileName
    )

    if (-not (Test-Path -LiteralPath $logRoot)) {
        return $null
    }
    $reusedProperty = "${Component}_reused"
    foreach ($directory in (Get-ChildItem -LiteralPath $logRoot -Directory | Sort-Object Name -Descending)) {
        if ($directory.FullName -eq $runLogDir) {
            continue
        }
        $previousStateFile = Join-Path $directory.FullName 'state.json'
        if (-not (Test-Path -LiteralPath $previousStateFile)) {
            continue
        }
        try {
            $previousState = Get-Content -LiteralPath $previousStateFile -Raw | ConvertFrom-Json
            $wasReused = $previousState.PSObject.Properties[$reusedProperty]
            if ($wasReused -and -not [bool]$wasReused.Value) {
                $candidate = Join-Path $directory.FullName $FileName
                if (Test-Path -LiteralPath $candidate) {
                    return $candidate
                }
            }
        }
        catch {
            continue
        }
    }
    return $null
}

function Test-HttpEndpoint {
    param(
        [Parameter(Mandatory)]
        [string]$Uri
    )

    try {
        Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory)]
        [string]$Uri,
        [Parameter(Mandatory)]
        [int]$TimeoutSec,
        [System.Diagnostics.Process]$Process,
        [string]$ErrorLog
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpEndpoint -Uri $Uri) {
            return $true
        }
        if ($Process -and $Process.HasExited) {
            Write-DevLog "El proceso terminó antes de responder en $Uri (exit code $($Process.ExitCode))." 'ERROR'
            if ($ErrorLog -and (Test-Path -LiteralPath $ErrorLog)) {
                Get-Content -LiteralPath $ErrorLog -Tail 40 | ForEach-Object {
                    Write-DevLog "stderr: $_" 'ERROR'
                }
            }
            return $false
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Invoke-NativeProcess {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,
        [Parameter(Mandatory)]
        [string[]]$ArgumentList,
        [string]$WorkingDirectory = $root
    )

    $command = Get-Command $FilePath -ErrorAction Stop
    $captureId = [Guid]::NewGuid().ToString('N')
    $stdoutCapture = Join-Path $runLogDir "$captureId.stdout.tmp"
    $stderrCapture = Join-Path $runLogDir "$captureId.stderr.tmp"

    try {
        $process = Start-Process -FilePath $command.Source `
            -ArgumentList $ArgumentList `
            -WorkingDirectory $WorkingDirectory `
            -RedirectStandardOutput $stdoutCapture `
            -RedirectStandardError $stderrCapture `
            -WindowStyle Hidden `
            -Wait `
            -PassThru

        $stdout = if (Test-Path -LiteralPath $stdoutCapture) {
            @(Get-Content -LiteralPath $stdoutCapture -Encoding Default)
        }
        else { @() }
        $stderr = if (Test-Path -LiteralPath $stderrCapture) {
            @(Get-Content -LiteralPath $stderrCapture -Encoding Default)
        }
        else { @() }

        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Stdout = $stdout
            Stderr = $stderr
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutCapture, $stderrCapture -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-LoggedNativeCommand {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,
        [Parameter(Mandatory)]
        [string[]]$ArgumentList,
        [Parameter(Mandatory)]
        [string]$LogPath,
        [Parameter(Mandatory)]
        [string]$Description,
        [string]$WorkingDirectory = $root
    )

    Write-DevLog $Description
    $result = Invoke-NativeProcess -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory
    @($result.Stdout) + @($result.Stderr) | Add-Content -LiteralPath $LogPath -Encoding UTF8
    $result.Stdout | ForEach-Object { Write-Host $_ }
    $result.Stderr | ForEach-Object { Write-Host $_ -ForegroundColor DarkYellow }

    if ($result.ExitCode -ne 0) {
        throw "$Description falló con exit code $($result.ExitCode). Ver: $LogPath"
    }
}

function Assert-DevelopmentPrerequisites {
    Assert-PathExists -Path $composeFile -Description 'docker-compose.yml'
    Assert-PathExists -Path $python -Description 'Python del entorno virtual'
    Assert-PathExists -Path $frontendPackage -Description 'package.json de frontend-vue'
    Assert-PathExists -Path $envFile -Description 'archivo local .env'

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker CLI no está disponible. Se necesita únicamente para PostgreSQL.'
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw 'Node.js no está disponible en PATH.'
    }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw 'npm.cmd no está disponible en PATH.'
    }

    $composeCheck = Invoke-NativeProcess -FilePath 'docker' -ArgumentList @('compose', 'config', '--quiet')
    if ($composeCheck.ExitCode -ne 0) {
        throw 'docker-compose.yml no es válido. Ejecutar docker compose config para ver el detalle.'
    }

    $pythonCheck = Invoke-NativeProcess -FilePath $python -ArgumentList @('--version')
    $pythonVersionText = (@($pythonCheck.Stdout) + @($pythonCheck.Stderr) -join ' ').Trim()
    $versionMatch = [regex]::Match($pythonVersionText, '^Python\s+3\.14\.(\d+)')
    if ($pythonCheck.ExitCode -ne 0 -or -not $versionMatch.Success -or [int]$versionMatch.Groups[1].Value -lt 6) {
        throw 'La venv está rota o no usa Python 3.14.6+. Ejecutar scripts\bootstrap-dev.ps1 -RecreateVenv.'
    }

    $imports = Invoke-NativeProcess -FilePath $python -ArgumentList @(
        '-c',
        "__import__('fastapi');__import__('mcp');__import__('openai');__import__('sqlalchemy')"
    )
    if ($imports.ExitCode -ne 0) {
        throw 'Faltan dependencias de desarrollo o MCP. Ejecutar scripts\bootstrap-dev.ps1.'
    }

    Write-DevLog 'Prerrequisitos locales verificados.' 'OK'
}

function Start-DevelopmentMcp {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Module,
        [Parameter(Mandatory)][int]$Port,
        [Parameter(Mandatory)][string]$StdoutLog,
        [Parameter(Mandatory)][string]$StderrLog
    )

    $healthUri = "http://127.0.0.1:$Port/health"
    if (Test-TcpPort -HostName '127.0.0.1' -Port $Port) {
        if (Test-HttpEndpoint -Uri $healthUri) {
            Write-DevLog "$Name ya está saludable en el puerto $Port; se reutilizará." 'OK'
            return $null
        }
        throw "El puerto $Port está ocupado, pero $Name no responde en /health."
    }

    Write-DevLog "Iniciando $Name con MCP Streamable HTTP."
    $process = Start-Process -FilePath $python `
        -ArgumentList @('-m', 'uvicorn', "${Module}:app", '--host', '127.0.0.1', '--port', "$Port", '--log-level', 'info') `
        -WorkingDirectory $root `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog `
        -WindowStyle Hidden `
        -PassThru
    $startedProcesses.Add($process)

    if (-not (Wait-HttpEndpoint -Uri $healthUri -TimeoutSec $ApiTimeoutSec -Process $process -ErrorLog $StderrLog)) {
        throw "$Name no alcanzó un estado saludable. Ver: $StdoutLog y $StderrLog"
    }
    Write-DevLog "$Name disponible en http://127.0.0.1:$Port/mcp." 'OK'
    return $process
}

function Ensure-DevelopmentDatabase {
    Invoke-LoggedNativeCommand -FilePath 'docker' `
        -ArgumentList @('info', '--format', '{{.ServerVersion}}') `
        -LogPath $databaseLog `
        -Description 'Verificando que el motor Docker esté disponible'

    $composeResult = Invoke-NativeProcess -FilePath 'docker' `
        -ArgumentList @('compose', 'ps', '--services', '--status', 'running')
    @($composeResult.Stdout) + @($composeResult.Stderr) | Add-Content -LiteralPath $databaseLog -Encoding UTF8
    if ($composeResult.ExitCode -ne 0) {
        throw "No se pudo consultar Docker Compose. Ver: $databaseLog"
    }

    $databaseIsRunning = @($composeResult.Stdout | Where-Object { "$_".Trim() -eq 'db' }).Count -gt 0
    if ($databaseIsRunning) {
        Write-DevLog 'El servicio Docker db ya está levantado; se reutilizará.' 'OK'
        if (-not (Wait-TcpPort -HostName '127.0.0.1' -Port 5433 -TimeoutSec 5)) {
            Write-DevLog 'db figura running pero no publica 127.0.0.1:5433; se reconciliará su configuración Compose.' 'WARN'
            Invoke-LoggedNativeCommand -FilePath 'docker' `
                -ArgumentList @('compose', 'up', '-d', 'db') `
                -LogPath $databaseLog `
                -Description 'Reconciliando PostgreSQL mediante Docker Compose'
        }
    }
    else {
        Invoke-LoggedNativeCommand -FilePath 'docker' `
            -ArgumentList @('compose', 'up', '-d', 'db') `
            -LogPath $databaseLog `
            -Description 'Levantando únicamente PostgreSQL mediante Docker Compose'
    }

    if (-not (Wait-TcpPort -HostName '127.0.0.1' -Port 5433 -TimeoutSec $DatabaseTimeoutSec)) {
        throw "PostgreSQL no respondió en 127.0.0.1:5433. Ver: $databaseLog"
    }
    Write-DevLog 'PostgreSQL responde en 127.0.0.1:5433.' 'OK'
}

function Ensure-CatalogWorker {
    if (-not $WithCatalogWorker) {
        return
    }

    if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        $script:localCatalogWorkerPids = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -and $_.CommandLine -match 'dramatiq' -and $_.CommandLine -match 'services\.jobs\.catalog_jobs'
        } | Select-Object -ExpandProperty ProcessId -Unique)
        if ($script:localCatalogWorkerPids.Count -gt 0) {
            Write-DevLog "Hay consumidores catalog locales activos (PID: $($script:localCatalogWorkerPids -join ', ')). También se verificará Dramatiq Docker; los jobs pueden repartirse entre ambos logs." 'WARN'
        }
    }

    Invoke-LoggedNativeCommand -FilePath 'docker' `
        -ArgumentList @('compose', '--profile', 'optional', 'up', '-d', 'redis', 'dramatiq') `
        -LogPath $databaseLog `
        -Description 'Levantando Redis y Dramatiq para trabajos de catálogo'

    if (-not (Wait-TcpPort -HostName '127.0.0.1' -Port 6379 -TimeoutSec 30)) {
        throw "Redis no respondió en 127.0.0.1:6379. Ver: $databaseLog"
    }

    $running = Invoke-NativeProcess -FilePath 'docker' `
        -ArgumentList @('compose', '--profile', 'optional', 'ps', '--services', '--status', 'running')
    @($running.Stdout) + @($running.Stderr) | Add-Content -LiteralPath $databaseLog -Encoding UTF8
    $runningNames = @($running.Stdout | ForEach-Object { "$_".Trim() })
    if ($running.ExitCode -ne 0 -or $runningNames -notcontains 'redis' -or $runningNames -notcontains 'dramatiq') {
        throw "Redis o Dramatiq no quedaron en ejecución. Ver: $databaseLog"
    }
    Write-DevLog 'Redis y Dramatiq están disponibles para la cola catalog.' 'OK'
}

function Ensure-MarketWorker {
    if (-not $WithMarketWorker) {
        return
    }
    Invoke-LoggedNativeCommand -FilePath 'docker' `
        -ArgumentList @('compose', 'up', '-d', 'redis') `
        -LogPath $databaseLog `
        -Description 'Iniciando Redis para el worker Mercado'
    Invoke-LoggedNativeCommand -FilePath 'docker' `
        -ArgumentList @('compose', '--profile', 'optional', 'up', '-d', '--build', '--no-deps', 'market_worker') `
        -LogPath $databaseLog `
        -Description 'Compilando e iniciando el worker Docker de Mercado'
    if (-not (Wait-TcpPort -HostName '127.0.0.1' -Port 6379 -TimeoutSec 30)) {
        throw "Redis no respondió para el worker Mercado. Ver: $databaseLog"
    }
    $running = Invoke-NativeProcess -FilePath 'docker' `
        -ArgumentList @('compose', '--profile', 'optional', 'ps', '--services', '--status', 'running')
    $runningNames = @($running.Stdout | ForEach-Object { "$_".Trim() })
    if ($running.ExitCode -ne 0 -or $runningNames -notcontains 'market_worker') {
        throw "El worker Mercado no quedó en ejecución. Ver: $databaseLog"
    }
    Write-DevLog 'Worker Docker Mercado disponible para la cola market.' 'OK'
}

function Ensure-EnrichmentInfrastructure {
    if (-not $WithEnrichmentWorker -and -not $WithKnowledgeWorker) {
        return
    }
    Invoke-LoggedNativeCommand -FilePath 'docker' `
        -ArgumentList @('compose', 'up', '-d', 'redis') `
        -LogPath $databaseLog `
        -Description 'Iniciando Redis para Enrich v2'
    if (-not (Wait-TcpPort -HostName '127.0.0.1' -Port 6379 -TimeoutSec 30)) {
        throw "Redis no respondió para Enrich v2. Ver: $databaseLog"
    }
}

function Start-KnowledgeWorker {
    if (-not $WithKnowledgeWorker) {
        return $null
    }
    Write-DevLog 'Iniciando knowledge_worker local (1 proceso, 1 thread).'
    $process = Start-Process -FilePath $python `
        -ArgumentList @(
            '-m', 'dramatiq', 'services.jobs.knowledge_jobs',
            '--processes', '1', '--threads', '1', '--queues', 'canonical_knowledge'
        ) `
        -WorkingDirectory $root `
        -RedirectStandardOutput $knowledgeWorkerStdoutLog `
        -RedirectStandardError $knowledgeWorkerStderrLog `
        -WindowStyle Hidden `
        -PassThru
    $startedProcesses.Add($process)
    $healthUri = 'http://127.0.0.1:8000/health/knowledge-worker'
    if (-not (Wait-HttpEndpoint -Uri $healthUri -TimeoutSec $ApiTimeoutSec -Process $process -ErrorLog $knowledgeWorkerStderrLog)) {
        throw "knowledge_worker no alcanzó un estado saludable. Ver: $knowledgeWorkerStderrLog"
    }
    Write-DevLog 'knowledge_worker saludable y consumiendo canonical_knowledge.' 'OK'
    return $process
}

function Start-EnrichmentWorker {
    if (-not $WithEnrichmentWorker) {
        return $null
    }
    Write-DevLog 'Iniciando enrichment_worker local (1 proceso, 2 threads).'
    $process = Start-Process -FilePath $python `
        -ArgumentList @(
            '-m', 'dramatiq', 'services.jobs.enrichment_jobs',
            '--processes', '1', '--threads', '2', '--queues', 'enrichment'
        ) `
        -WorkingDirectory $root `
        -RedirectStandardOutput $enrichmentWorkerStdoutLog `
        -RedirectStandardError $enrichmentWorkerStderrLog `
        -WindowStyle Hidden `
        -PassThru
    $startedProcesses.Add($process)
    $healthUri = 'http://127.0.0.1:8000/health/enrichment-worker'
    if (-not (Wait-HttpEndpoint -Uri $healthUri -TimeoutSec $ApiTimeoutSec -Process $process -ErrorLog $enrichmentWorkerStderrLog)) {
        throw "enrichment_worker no alcanzó un estado saludable. Ver: $enrichmentWorkerStderrLog"
    }
    Write-DevLog 'enrichment_worker saludable y consumiendo la cola enrichment.' 'OK'
    return $process
}

function Invoke-DatabaseMigrations {
    Invoke-LoggedNativeCommand -FilePath $python `
        -ArgumentList @('-m', 'alembic', 'upgrade', 'head') `
        -LogPath $migrationLog `
        -Description 'Aplicando migraciones Alembic hasta head'
    Write-DevLog 'Migraciones Alembic aplicadas correctamente.' 'OK'
}

function Ensure-FrontendDependencies {
    $nodeModules = Join-Path $frontendRoot 'node_modules'
    if (-not (Test-Path -LiteralPath $nodeModules)) {
        Invoke-LoggedNativeCommand -FilePath 'npm.cmd' `
            -ArgumentList @('ci') `
            -LogPath $dependenciesLog `
            -Description 'Instalando dependencias de frontend-vue' `
            -WorkingDirectory $frontendRoot
        Write-DevLog 'Dependencias de frontend-vue instaladas.' 'OK'
        return
    }

    $npmResult = Invoke-NativeProcess -FilePath 'npm.cmd' `
        -ArgumentList @('ls', '--depth=0') `
        -WorkingDirectory $frontendRoot
    @($npmResult.Stdout) + @($npmResult.Stderr) | Add-Content -LiteralPath $dependenciesLog -Encoding UTF8

    if ($npmResult.ExitCode -eq 0) {
        Write-DevLog 'Dependencias de frontend-vue verificadas.' 'OK'
        return
    }

    Write-DevLog 'Las dependencias Vue no coinciden con package-lock.json; se ejecutará npm ci.' 'WARN'
    Invoke-LoggedNativeCommand -FilePath 'npm.cmd' `
        -ArgumentList @('ci') `
        -LogPath $dependenciesLog `
        -Description 'Sincronizando dependencias de frontend-vue' `
        -WorkingDirectory $frontendRoot
    Write-DevLog 'Dependencias de frontend-vue sincronizadas.' 'OK'
}

function Start-DevelopmentApi {
    $healthUri = 'http://127.0.0.1:8000/health'
    if (Test-TcpPort -HostName '127.0.0.1' -Port 8000) {
        if (Test-HttpEndpoint -Uri $healthUri) {
            Write-DevLog 'La API ya está saludable en el puerto 8000; se reutilizará.' 'OK'
            return $null
        }
        throw 'El puerto 8000 está ocupado, pero /health no responde correctamente.'
    }

    Write-DevLog 'Iniciando API local con hot reload.'
    $process = Start-Process -FilePath $python `
        -ArgumentList @('-m', 'uvicorn', 'services.api:app', '--reload', '--host', '127.0.0.1', '--port', '8000', '--log-level', 'info') `
        -WorkingDirectory $root `
        -RedirectStandardOutput $apiStdoutLog `
        -RedirectStandardError $apiStderrLog `
        -WindowStyle Hidden `
        -PassThru
    $startedProcesses.Add($process)

    Write-DevLog "API iniciada con PID $($process.Id); esperando $healthUri."
    if (-not (Wait-HttpEndpoint -Uri $healthUri -TimeoutSec $ApiTimeoutSec -Process $process -ErrorLog $apiStderrLog)) {
        throw "La API no alcanzó un estado saludable. Ver: $apiStdoutLog y $apiStderrLog"
    }
    Write-DevLog 'API saludable en http://127.0.0.1:8000.' 'OK'
    return $process
}

function Start-DevelopmentFrontend {
    $frontendUri = 'http://127.0.0.1:5176/'
    if (Test-TcpPort -HostName '127.0.0.1' -Port 5176) {
        if (Test-HttpEndpoint -Uri $frontendUri) {
            Write-DevLog 'Vue ya responde en el puerto 5176; se reutilizará.' 'OK'
            return $null
        }
        throw 'El puerto 5176 está ocupado, pero el frontend no responde correctamente.'
    }

    Write-DevLog 'Iniciando frontend Vue 3/Vuetify con Vite.'
    $process = Start-Process -FilePath 'npm.cmd' `
        -ArgumentList @('run', 'dev') `
        -WorkingDirectory $frontendRoot `
        -RedirectStandardOutput $frontendStdoutLog `
        -RedirectStandardError $frontendStderrLog `
        -WindowStyle Hidden `
        -PassThru
    $startedProcesses.Add($process)

    Write-DevLog "Frontend Vue iniciado con PID $($process.Id); esperando $frontendUri."
    if (-not (Wait-HttpEndpoint -Uri $frontendUri -TimeoutSec $FrontendTimeoutSec -Process $process -ErrorLog $frontendStderrLog)) {
        throw "Vue no comenzó a responder. Ver: $frontendStdoutLog y $frontendStderrLog"
    }
    Write-DevLog 'Vue disponible en http://127.0.0.1:5176/.' 'OK'
    return $process
}

try {
    Write-DevLog "Inicio del entorno de desarrollo. Raíz: $root"
    Assert-DevelopmentPrerequisites
    if ($CheckOnly) {
        Write-DevLog "Configuración válida. MCP mode: $McpMode. Catalog worker: $([bool]$WithCatalogWorker). Market worker: $([bool]$WithMarketWorker). Enrichment worker: $([bool]$WithEnrichmentWorker). Knowledge worker: $([bool]$WithKnowledgeWorker). No se iniciaron servicios ni migraciones." 'OK'
        exit 0
    }

    # Los procesos hijos heredan estas URLs locales. Docker Compose conserva
    # sus propios nombres de servicio mediante docker-compose.yml.
    $env:API_BASE_URL = 'http://127.0.0.1:8000'
    $env:MCP_PRODUCTS_URL = 'http://127.0.0.1:8100/mcp'
    $env:MCP_WEB_SEARCH_URL = 'http://127.0.0.1:8102/mcp'
    $env:GROWEN_DEV_RUN_LOG_DIR = $runLogDir

    Ensure-FrontendDependencies
    Ensure-DevelopmentDatabase
    Ensure-CatalogWorker
    Ensure-MarketWorker
    Ensure-EnrichmentInfrastructure
    Invoke-DatabaseMigrations

    $apiProcess = Start-DevelopmentApi
    $mcpProductsProcess = $null
    $mcpWebProcess = $null
    if ($McpMode -in @('Core', 'All')) {
        $mcpProductsProcess = Start-DevelopmentMcp `
            -Name 'MCP Products' `
            -Module 'mcp_servers.products_server.main' `
            -Port 8100 `
            -StdoutLog $mcpProductsStdoutLog `
            -StderrLog $mcpProductsStderrLog
    }
    if ($McpMode -eq 'All' -or $WithEnrichmentWorker -or $WithKnowledgeWorker) {
        $mcpWebProcess = Start-DevelopmentMcp `
            -Name 'MCP Web Search' `
            -Module 'mcp_servers.web_search_server.main' `
            -Port 8102 `
            -StdoutLog $mcpWebStdoutLog `
            -StderrLog $mcpWebStderrLog
    }
    $enrichmentWorkerProcess = Start-EnrichmentWorker
    $knowledgeWorkerProcess = Start-KnowledgeWorker
    $frontendProcess = Start-DevelopmentFrontend

    $state = [ordered]@{
        started_at = (Get-Date).ToString('o')
        database = 'docker-compose:db'
        api_url = 'http://127.0.0.1:8000'
        api_pid = if ($apiProcess) { $apiProcess.Id } else { $null }
        api_process_started_at = if ($apiProcess) { $apiProcess.StartTime.ToString('o') } else { $null }
        api_reused = ($null -eq $apiProcess)
        api_health = 'healthy'
        api_log_source_hint = if ($apiProcess) { $apiStderrLog } else { Find-PreviousLogSourceHint -Component 'api' -FileName 'api.stderr.log' }
        catalog_worker_mode = if ($WithCatalogWorker) { 'docker-compose' } else { 'off' }
        redis_url = if ($WithCatalogWorker -or $WithMarketWorker -or $WithEnrichmentWorker -or $WithKnowledgeWorker) { 'redis://127.0.0.1:6379/0' } else { $null }
        redis_health = if ($WithCatalogWorker -or $WithMarketWorker -or $WithEnrichmentWorker -or $WithKnowledgeWorker) { 'healthy' } else { 'off' }
        catalog_worker_health = if ($WithCatalogWorker) { 'running' } else { 'off' }
        catalog_worker_log_command = if ($WithCatalogWorker) { 'docker compose --profile optional logs -f dramatiq redis' } else { $null }
        catalog_worker_competing_local_pids = if ($WithCatalogWorker) { @($localCatalogWorkerPids) } else { @() }
        market_worker_mode = if ($WithMarketWorker) { 'docker-compose' } else { 'off' }
        market_worker_health = if ($WithMarketWorker) { 'running' } else { 'off' }
        market_worker_log_command = if ($WithMarketWorker) { 'docker compose --profile optional logs -f market_worker redis' } else { $null }
        enrichment_worker_mode = if ($WithEnrichmentWorker) { 'local' } else { 'off' }
        enrichment_worker_pid = if ($enrichmentWorkerProcess) { $enrichmentWorkerProcess.Id } else { $null }
        enrichment_worker_health = if ($WithEnrichmentWorker) { 'healthy' } else { 'off' }
        enrichment_worker_log_source_hint = if ($WithEnrichmentWorker) { $enrichmentWorkerStderrLog } else { $null }
        knowledge_worker_mode = if ($WithKnowledgeWorker) { 'local' } else { 'off' }
        knowledge_worker_pid = if ($knowledgeWorkerProcess) { $knowledgeWorkerProcess.Id } else { $null }
        knowledge_worker_health = if ($WithKnowledgeWorker) { 'healthy' } else { 'off' }
        knowledge_worker_log_source_hint = if ($WithKnowledgeWorker) { $knowledgeWorkerStderrLog } else { $null }
        mcp_mode = $McpMode
        mcp_products_url = if ($McpMode -in @('Core', 'All')) { 'http://127.0.0.1:8100/mcp' } else { $null }
        mcp_products_pid = if ($mcpProductsProcess) { $mcpProductsProcess.Id } else { $null }
        mcp_products_process_started_at = if ($mcpProductsProcess) { $mcpProductsProcess.StartTime.ToString('o') } else { $null }
        mcp_products_reused = ($McpMode -in @('Core', 'All')) -and ($null -eq $mcpProductsProcess)
        mcp_products_health = if ($McpMode -in @('Core', 'All')) { 'healthy' } else { 'off' }
        mcp_products_log_source_hint = if ($mcpProductsProcess) { $mcpProductsStderrLog } elseif ($McpMode -in @('Core', 'All')) { Find-PreviousLogSourceHint -Component 'mcp_products' -FileName 'mcp-products.stderr.log' } else { $null }
        mcp_web_search_url = if ($McpMode -eq 'All' -or $WithEnrichmentWorker -or $WithKnowledgeWorker) { 'http://127.0.0.1:8102/mcp' } else { $null }
        mcp_web_search_pid = if ($mcpWebProcess) { $mcpWebProcess.Id } else { $null }
        mcp_web_search_process_started_at = if ($mcpWebProcess) { $mcpWebProcess.StartTime.ToString('o') } else { $null }
        mcp_web_search_reused = ($McpMode -eq 'All' -or $WithEnrichmentWorker -or $WithKnowledgeWorker) -and ($null -eq $mcpWebProcess)
        mcp_web_search_health = if ($McpMode -eq 'All' -or $WithEnrichmentWorker -or $WithKnowledgeWorker) { 'healthy' } else { 'off' }
        mcp_web_search_log_source_hint = if ($mcpWebProcess) { $mcpWebStderrLog } elseif ($McpMode -eq 'All' -or $WithEnrichmentWorker -or $WithKnowledgeWorker) { Find-PreviousLogSourceHint -Component 'mcp_web_search' -FileName 'mcp-web-search.stderr.log' } else { $null }
        frontend_url = 'http://127.0.0.1:5176'
        frontend_pid = if ($frontendProcess) { $frontendProcess.Id } else { $null }
        frontend_process_started_at = if ($frontendProcess) { $frontendProcess.StartTime.ToString('o') } else { $null }
        frontend_reused = ($null -eq $frontendProcess)
        frontend_health = 'healthy'
        frontend_log_source_hint = if ($frontendProcess) { $frontendStderrLog } else { Find-PreviousLogSourceHint -Component 'frontend' -FileName 'frontend-vue.stderr.log' }
        logs = $runLogDir
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8

    Write-DevLog 'Entorno de desarrollo iniciado correctamente.' 'OK'
    Write-DevLog 'API: http://127.0.0.1:8000/docs' 'OK'
    Write-DevLog 'Vue: http://127.0.0.1:5176/login' 'OK'
    Write-DevLog "Logs de esta ejecución: $runLogDir" 'OK'
}
catch {
    Write-DevLog $_.Exception.Message 'ERROR'
    for ($index = $startedProcesses.Count - 1; $index -ge 0; $index--) {
        $startedProcess = $startedProcesses[$index]
        if ($startedProcess -and -not $startedProcess.HasExited) {
            Stop-DevelopmentProcessTree -ProcessId $startedProcess.Id
            Write-DevLog "Proceso iniciado por esta ejecución detenido: PID $($startedProcess.Id)." 'WARN'
        }
    }
    Write-DevLog "Revisar logs en: $runLogDir" 'ERROR'
    exit 1
}
