#!/usr/bin/env pwsh
# NG-HEADER: Nombre de archivo: status_stack.ps1
# NG-HEADER: Ubicación: scripts/status_stack.ps1
# NG-HEADER: Descripción: Verifica salud de DB (TCP), API (/health) y Frontend (/app) y retorna código de salida.
# NG-HEADER: Lineamientos: Ver AGENTS.md

param(
  [string]$ApiUrl = "http://127.0.0.1:8000",
  [string]$DbHostName = "127.0.0.1",
  [int]$DbPort = 5433
)

$ErrorActionPreference = "SilentlyContinue"

function Test-Tcp($h, $p, $timeoutMs = 800) {
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect($h, $p, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne($timeoutMs, $false)
    if ($ok -and $client.Connected) { $client.Close(); return $true }
    $client.Close(); return $false
  } catch { return $false }
}

function Get-Api($url, $timeoutSec = 2) {
  try {
    $wc = New-Object Net.WebClient
    $wc.Headers.Add('User-Agent','status-stack')
    $wc.Encoding = [System.Text.Encoding]::UTF8
    $wc.DownloadString($url)
  } catch { return $null }
}

$okDb = Test-Tcp $DbHostName $DbPort 800
$health = Get-Api ("$ApiUrl/health") 2
$app = Get-Api ("$ApiUrl/app") 2

if ($okDb) { $dbStatus = 'OK' } else { $dbStatus = 'FAIL' }
if ($health) { $healthStatus = 'OK' } else { $healthStatus = 'FAIL' }
if ($app) { $appStatus = 'OK' } else { $appStatus = 'FAIL' }

$line1 = [string]::Format('DB ({0}:{1}): {2}', $DbHostName, $DbPort, $dbStatus)
$line2 = [string]::Format('/health: {0}', $healthStatus)
$line3 = [string]::Format('/app: {0}', $appStatus)
Write-Host $line1
Write-Host $line2
Write-Host $line3

if (-not $okDb -or -not $health) { exit 1 } else { exit 0 }
