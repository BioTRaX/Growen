# NG-HEADER: Nombre de archivo: rotate_dev_db_password.ps1
# NG-HEADER: Ubicación: scripts/rotate_dev_db_password.ps1
# NG-HEADER: Descripción: Rota sin imprimir la credencial local de PostgreSQL y actualiza .env.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    throw 'No existe .env; no se puede rotar la credencial local.'
}

$original = [System.IO.File]::ReadAllText($envPath)
function Read-EnvValue([string]$content, [string]$name, [string]$fallback) {
    $match = [regex]::Match($content, "(?m)^$([regex]::Escape($name))=(.*)$")
    if ($match.Success -and $match.Groups[1].Value.Trim()) { return $match.Groups[1].Value.Trim() }
    return $fallback
}
function Set-EnvValue([string]$content, [string]$name, [string]$value) {
    $pattern = "(?m)^$([regex]::Escape($name))=.*$"
    if ([regex]::IsMatch($content, $pattern)) {
        return [regex]::Replace($content, $pattern, "$name=$value")
    }
    return $content.TrimEnd() + [Environment]::NewLine + "$name=$value" + [Environment]::NewLine
}

$dbUser = Read-EnvValue $original 'POSTGRES_USER' 'growen'
$dbName = Read-EnvValue $original 'POSTGRES_DB' 'growen'
if ($dbUser -notmatch '^[A-Za-z_][A-Za-z0-9_]*$' -or $dbName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
    throw 'POSTGRES_USER o POSTGRES_DB contienen caracteres no admitidos por el rotador.'
}

$randomBytes = [byte[]]::new(32)
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
$newPassword = ([System.BitConverter]::ToString($randomBytes) -replace '-', '').ToLowerInvariant()
$updated = Set-EnvValue $original 'POSTGRES_PASSWORD' $newPassword
$updated = Set-EnvValue $updated 'DB_PASS' $newPassword
$dbUrlMatch = [regex]::Match(
    $updated,
    '(?m)^DB_URL=(?<prefix>.*://.*?:)(?<password>.*?)(?<suffix>@.*)$'
)
if ($dbUrlMatch.Success) {
    $updated = $updated.Remove($dbUrlMatch.Groups['password'].Index, $dbUrlMatch.Groups['password'].Length)
    $updated = $updated.Insert($dbUrlMatch.Groups['password'].Index, $newPassword)
}
$tempPath = "$envPath.rotate.tmp"

try {
    [System.IO.File]::WriteAllText($tempPath, $updated, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempPath -Destination $envPath -Force
    $sql = "ALTER ROLE `"$dbUser`" WITH PASSWORD '$newPassword';"
    $previousOutputEncoding = $OutputEncoding
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    try {
        $sql | docker compose --project-directory $repoRoot exec -T db psql -U $dbUser -d $dbName -v ON_ERROR_STOP=1 --quiet
    } finally {
        $OutputEncoding = $previousOutputEncoding
    }
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL rechazó la rotación.' }
    Write-Host '[OK] Credencial local rotada e invalidada; el valor no fue impreso.' -ForegroundColor Green
} catch {
    [System.IO.File]::WriteAllText($envPath, $original, [System.Text.UTF8Encoding]::new($false))
    throw
} finally {
    if (Test-Path -LiteralPath $tempPath) { Remove-Item -LiteralPath $tempPath -Force }
    $newPassword = $null
}
