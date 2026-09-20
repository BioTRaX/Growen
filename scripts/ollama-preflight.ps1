# NG-HEADER: Nombre de archivo: ollama-preflight.ps1
# NG-HEADER: Ubicación: scripts/ollama-preflight.ps1
# NG-HEADER: Descripción: Verifica recursos, daemon y modelos Ollama para el perfil GPU de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding()]
param(
    [switch]$RequireModels,
    [int]$MinimumFreeVramMiB = 8192,
    [int]$MinimumFreeRamMiB = 1536,
    [int]$MinimumPagefileMiB = 16384,
    [int]$MinimumFreeDiskGiB = 15
)

$ErrorActionPreference = 'Stop'
$ollamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
$requiredModels = @('llama3.1:8b', 'qwen3-embedding:4b')
$checks = [ordered]@{}

try {
    $gpuLine = & nvidia-smi.exe --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits 2>$null | Select-Object -First 1
    $gpuParts = @($gpuLine -split ',' | ForEach-Object { $_.Trim() })
    $freeVramMiB = [int]$gpuParts[2]
    $checks.gpu = [ordered]@{
        ok = $freeVramMiB -ge $MinimumFreeVramMiB
        name = $gpuParts[0]
        total_vram_mib = [int]$gpuParts[1]
        free_vram_mib = $freeVramMiB
        required_free_vram_mib = $MinimumFreeVramMiB
    }
} catch {
    $checks.gpu = @{ ok = $false; code = 'nvidia_gpu_unavailable' }
}

$computer = Get-CimInstance Win32_ComputerSystem
$operatingSystem = Get-CimInstance Win32_OperatingSystem
$pagefiles = @(Get-CimInstance Win32_PageFileUsage)
$freeRamMiB = [math]::Floor([double]$operatingSystem.FreePhysicalMemory / 1024)
$pagefileMiB = [int](($pagefiles | Measure-Object -Property AllocatedBaseSize -Sum).Sum)
$pagefileOk = [bool]$computer.AutomaticManagedPagefile -or $pagefileMiB -ge $MinimumPagefileMiB
$checks.memory = [ordered]@{
    ok = $freeRamMiB -ge $MinimumFreeRamMiB -and $pagefileOk
    free_ram_mib = $freeRamMiB
    required_free_ram_mib = $MinimumFreeRamMiB
    pagefile_automatic = [bool]$computer.AutomaticManagedPagefile
    pagefile_mib = $pagefileMiB
    required_pagefile_mib_when_fixed = $MinimumPagefileMiB
}

$systemDrive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($env:SystemRoot).Substring(0, 1))
$freeDiskGiB = [math]::Round($systemDrive.Free / 1GB, 2)
$checks.disk = [ordered]@{
    ok = $freeDiskGiB -ge $MinimumFreeDiskGiB
    free_gib = $freeDiskGiB
    required_free_gib = $MinimumFreeDiskGiB
}

$daemonOk = $false
$installedModels = @()
$loadedModels = @()
try {
    $version = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 5
    $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
    $running = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/ps' -TimeoutSec 5
    $daemonOk = $true
    $installedModels = @($tags.models | ForEach-Object { $_.name })
    $loadedModels = @($running.models | ForEach-Object {
        [ordered]@{ name = $_.name; size_vram = $_.size_vram }
    })
    $checks.daemon = @{ ok = $true; version = $version.version }
} catch {
    $checks.daemon = @{ ok = $false; code = 'ollama_daemon_unavailable'; executable_present = (Test-Path -LiteralPath $ollamaExe) }
}

$missingModels = @($requiredModels | Where-Object { $_ -notin $installedModels })
$checks.models = [ordered]@{
    ok = (-not $RequireModels) -or ($daemonOk -and $missingModels.Count -eq 0)
    required = $requiredModels
    missing = $missingModels
    loaded = $loadedModels
}

$ok = -not (@($checks.Values | Where-Object { -not $_.ok }).Count)
[ordered]@{
    ok = $ok
    profile = 'gpu_vram_priority'
    checks = $checks
} | ConvertTo-Json -Depth 7

if (-not $ok) { exit 1 }
