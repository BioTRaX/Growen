#!/usr/bin/env pwsh
# NG-HEADER: Nombre de archivo: status_stack.ps1
# NG-HEADER: Ubicación: scripts/status_stack.ps1
# NG-HEADER: Descripción: Verifica DB, API, Vue y servidores MCP usando state.json cuando existe.
# NG-HEADER: Lineamientos: Ver AGENTS.md

param(
  [string]$ApiUrl = "http://127.0.0.1:8000",
  [string]$DbHostName = "127.0.0.1",
  [int]$DbPort = 5433,
  [string]$FrontendUrl = "http://127.0.0.1:5176",
  [string]$McpProductsUrl = "http://127.0.0.1:8100",
  [string]$McpWebSearchUrl = "http://127.0.0.1:8102",
  [string]$StateFile,
  [switch]$RequireWebSearch
)

$ErrorActionPreference = "SilentlyContinue"
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not $StateFile) {
  $latestState = Get-ChildItem -LiteralPath (Join-Path $root 'logs\dev') -Filter state.json -Recurse -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($latestState) { $StateFile = $latestState.FullName }
}
if ($StateFile -and (Test-Path -LiteralPath $StateFile)) {
  $state = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($state.api_url) { $ApiUrl = [string]$state.api_url }
  if ($state.frontend_url) { $FrontendUrl = [string]$state.frontend_url }
  if ($state.mcp_products_url) { $McpProductsUrl = ([string]$state.mcp_products_url) -replace '/mcp/?$', '' }
  if ($state.mcp_web_search_url) { $McpWebSearchUrl = ([string]$state.mcp_web_search_url) -replace '/mcp/?$', '' }
}

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
$frontend = Get-Api ("$FrontendUrl/") 2
$mcpProducts = Get-Api ("$McpProductsUrl/health") 2
$mcpWebSearch = Get-Api ("$McpWebSearchUrl/health") 2

if ($okDb) { $dbStatus = 'OK' } else { $dbStatus = 'FAIL' }
if ($health) { $healthStatus = 'OK' } else { $healthStatus = 'FAIL' }
if ($frontend) { $frontendStatus = 'OK' } else { $frontendStatus = 'FAIL' }
if ($mcpProducts) { $mcpProductsStatus = 'OK' } else { $mcpProductsStatus = 'FAIL' }
if ($mcpWebSearch) { $mcpWebSearchStatus = 'OK' } else { $mcpWebSearchStatus = 'OFF' }

$line1 = [string]::Format('DB ({0}:{1}): {2}', $DbHostName, $DbPort, $dbStatus)
$line2 = [string]::Format('/health: {0}', $healthStatus)
$line3 = [string]::Format('Vue: {0}', $frontendStatus)
$line4 = [string]::Format('MCP Products: {0}', $mcpProductsStatus)
$line5 = [string]::Format('MCP Web Search: {0}', $mcpWebSearchStatus)
Write-Host $line1
Write-Host $line2
Write-Host $line3
Write-Host $line4
Write-Host $line5

if (-not $okDb -or -not $health -or -not $frontend -or -not $mcpProducts) { exit 1 }
if ($RequireWebSearch -and -not $mcpWebSearch) { exit 1 }
exit 0
