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
    param([string]$Name = 'growen-redis', [string]$Image = 'redis:7-alpine')
    Write-Log "Ensuring Redis container '$Name' is running..."
    $existing = docker ps -a --filter "name=^/$Name$" --format '{{.Names}}'
    if (-not $existing) {
        Write-Log 'Creating Redis container with restart=unless-stopped...'
        docker run --name $Name --restart unless-stopped -p 6379:6379 -d $Image | Out-Null
    } else {
        Write-Log 'Container exists; enforcing restart policy and starting if stopped.'
        docker update --restart unless-stopped $Name 1>$null 2>$null
        $running = docker inspect -f '{{.State.Running}}' $Name
        if ($running -ne 'true') { docker start $Name | Out-Null }
    }
    # Quick ping
    Write-Log 'Verifying Redis responds on localhost:6379...'
    try {
        # Simple TCP test
        $socket = New-Object Net.Sockets.TcpClient
        $iar = $socket.BeginConnect('127.0.0.1', 6379, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(3000, $false)
        if ($ok -and $socket.Connected) {
            Write-Log 'Redis is reachable.'
        } else {
            Write-Log 'Warning: Redis not reachable yet.'
        }
        $socket.Close()
    } catch { Write-Log "Warning: Redis check failed: $_" }
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
