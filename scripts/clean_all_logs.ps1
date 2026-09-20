# NG-HEADER: Nombre de archivo: clean_all_logs.ps1
# NG-HEADER: Ubicación: scripts/clean_all_logs.ps1
# NG-HEADER: Descripción: Adaptador PowerShell para la limpieza canónica de logs locales de Growen.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [switch]$DryRun,
    [ValidateRange(0, 3650)]
    [int]$KeepDays = 7,
    [switch]$IncludeLatestDevRun,
    [ValidateRange(0, 3650)]
    [int]$ScreenshotsKeepDays = 0,
    [ValidateRange(0, 102400)]
    [int]$ScreenshotsMaxMb = 0
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$cleanup = Join-Path $root 'scripts\cleanup_logs.py'

if (-not (Test-Path -LiteralPath $python)) {
    throw "No se encontró el Python obligatorio del proyecto: $python"
}

$arguments = @($cleanup, '--keep-days', "$KeepDays")
if ($DryRun) { $arguments += '--dry-run' }
if ($IncludeLatestDevRun) { $arguments += '--include-latest-dev-run' }
if ($ScreenshotsKeepDays -gt 0) { $arguments += @('--screenshots-keep-days', "$ScreenshotsKeepDays") }
if ($ScreenshotsMaxMb -gt 0) { $arguments += @('--screenshots-max-mb', "$ScreenshotsMaxMb") }

Write-Host 'La limpieza local usa la misma politica que el panel Vue.' -ForegroundColor Cyan
Write-Host 'Los logs Docker no se truncan: deben administrarse mediante la rotacion del runtime Docker.' -ForegroundColor DarkYellow
& $python @arguments
exit $LASTEXITCODE
