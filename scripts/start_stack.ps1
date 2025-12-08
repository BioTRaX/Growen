[CmdletBinding()]
param(
    [int]$DockerTimeoutSec = 120,
    [int]$DockerPollMs = 2000
)

# Starts Docker Desktop if needed, ensures Redis is up, and launches the Dramatiq worker.
# Logs to logs/start_stack.log

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDir = Join-Path $root 'logs'
$newLog = $false
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir 'start_stack.log'

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "$ts | $Message" | Out-File -FilePath $log -Encoding UTF8 -Append
}

function Start-DockerDesktopIfNeeded {
    $dockerCli = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCli) {
        Write-Log 'Docker CLI not found in PATH. Attempting to start Docker Desktop anyway.'
    }
    $proc = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
    if (-not $proc) {
        $exe = Join-Path $env:ProgramFiles 'Docker\\Docker\\Docker Desktop.exe'
        if (!(Test-Path $exe)) {
            Write-Log "Docker Desktop not found at $exe. Please install Docker Desktop."
            throw "Docker Desktop not installed"
        }
        Write-Log 'Starting Docker Desktop...'
        Start-Process -FilePath $exe | Out-Null
    } else {
        Write-Log 'Docker Desktop already running.'
    }
}

function Wait-DockerReady {
    Write-Log 'Waiting for Docker engine to be ready...'
    $deadline = (Get-Date).AddSeconds($DockerTimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            docker info 1>$null 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Log 'Docker engine is ready.'
                return
            }
        } catch { }
        Start-Sleep -Milliseconds $DockerPollMs
    }
    Write-Log 'Docker engine did not become ready in time.'
    throw 'Docker not ready'
}

function Ensure-Redis {
    Write-Log 'Ensuring Redis service via docker-compose...'
    $composeFile = Join-Path $root 'docker-compose.yml'
    if (-not (Test-Path $composeFile)) {
        Write-Log "ERROR: docker-compose.yml not found at $composeFile"
        throw "docker-compose.yml not found"
    }
    
    # Verificar si existe un contenedor creado manualmente (sin docker-compose)
    $existing = docker ps -a --filter "name=^/growen-redis$" --format '{{.Names}}' 2>$null
    if ($existing) {
        # Verificar si el contenedor fue creado por docker-compose
        $labels = docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' growen-redis 2>$null
        if (-not $labels) {
            Write-Log 'WARNING: Found manually created Redis container (not from docker-compose).'
            Write-Log 'Removing old container to migrate to docker-compose...'
            docker stop growen-redis 2>$null | Out-Null
            docker rm growen-redis 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Log 'ERROR: Could not remove old Redis container. Please remove it manually: docker rm -f growen-redis'
                throw "Could not remove old Redis container"
            }
            Write-Log 'Old container removed. Proceeding with docker-compose...'
        }
    }
    
    # Usar docker compose para levantar Redis
    Write-Log 'Starting Redis via docker compose up -d redis...'
    $result = docker compose -f $composeFile up -d redis 2>&1
    if ($LASTEXITCODE -ne 0) {
        $errorStr = $result -join ' '
        Write-Log "ERROR: Failed to start Redis via docker-compose: $errorStr"
        throw "Failed to start Redis: $errorStr"
    } else {
        Write-Log 'Redis service started via docker compose.'
    }
    
    # Quick ping
    Write-Log 'Verifying Redis responds on localhost:6379...'
    $maxRetries = 10
    $retry = 0
    $connected = $false
    while ($retry -lt $maxRetries -and -not $connected) {
        try {
            $socket = New-Object Net.Sockets.TcpClient
            $iar = $socket.BeginConnect('127.0.0.1', 6379, $null, $null)
            $ok = $iar.AsyncWaitHandle.WaitOne(1000, $false)
            if ($ok -and $socket.Connected) {
                $connected = $true
                Write-Log 'Redis is reachable.'
            }
            $socket.Close()
        } catch { }
        if (-not $connected) {
            $retry++
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $connected) {
        Write-Log 'WARNING: Redis not reachable after retries. It may still be starting.'
    }
}

function Start-Worker {
    $env:RUN_INLINE_JOBS = '0'  # ensure real queue mode
    if (-not (Test-Path (Join-Path $root '.venv'))) {
        Write-Log 'Virtual env not found (.venv). Please run start.bat once to set up dependencies.'
        throw 'Missing venv'
    }
    $cmd = Join-Path $root 'scripts\\start_worker_images.cmd'
    if (!(Test-Path $cmd)) { throw "Worker script not found: $cmd" }
    Write-Log 'Starting Dramatiq worker...'
    # Launch in a separate window to keep it running independently
    Start-Process -FilePath $cmd -WorkingDirectory $root -WindowStyle Minimized | Out-Null
}

try {
    Write-Log '--- Start stack ---'
    Start-DockerDesktopIfNeeded
    Wait-DockerReady
    Ensure-Redis
    Start-Worker
    Write-Log 'Stack started.'
} catch {
    Write-Log ("ERROR: " + $_)
    throw
}
