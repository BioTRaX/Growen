[CmdletBinding()]
param(
  [string[]]$Files = @(
    'start.bat',
    'stop.bat',
    'scripts/run_migrations.cmd',
    'scripts/start_worker_images.cmd'
  )
)

function Remove-BomInPlace([string]$Path) {
  if (!(Test-Path $Path)) { return $false }
  try {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
      $new = $bytes[3..($bytes.Length-1)]
      [System.IO.File]::WriteAllBytes($Path, $new)
      Write-Output "fixed: $Path (UTF-8 BOM removed)"
      return $true
    }
    return $false
  } catch {
    Write-Warning "skip: $Path -> $($_.Exception.Message)"
    return $false
  }
}

$root = Split-Path -Parent $PSScriptRoot
$fixed = 0
foreach ($rel in $Files) {
  $p = Join-Path $root $rel
  if (Remove-BomInPlace -Path $p) { $fixed++ }
}
Write-Output ("BOM fixes: {0}" -f $fixed)
