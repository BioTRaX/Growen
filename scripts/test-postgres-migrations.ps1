# NG-HEADER: Nombre de archivo: test-postgres-migrations.ps1
# NG-HEADER: Ubicación: scripts/test-postgres-migrations.ps1
# NG-HEADER: Descripción: Ejecuta la cadena Alembic sobre PostgreSQL/pgvector efímero.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)][string]$PostgresImage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$containerName = "growen-migration-test-$([Guid]::NewGuid().ToString('N').Substring(0, 12))"

if (-not $PSCmdlet.ShouldProcess($containerName, "Crear PostgreSQL efímero y ejecutar migraciones")) {
    Write-Output "migration_test_plan image=$PostgresImage"
    return
}

$tempDirectory = Join-Path ([IO.Path]::GetTempPath()) $containerName
$passwordFile = Join-Path $tempDirectory "postgres_password"
$passwordBytes = [byte[]]::new(36)
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $rng.GetBytes($passwordBytes)
} finally {
    $rng.Dispose()
}
$password = [Convert]::ToBase64String($passwordBytes)
[IO.Directory]::CreateDirectory($tempDirectory) | Out-Null
[IO.File]::WriteAllText($passwordFile, $password, [Text.UTF8Encoding]::new($false))

try {
    $containerId = docker run -d --name $containerName -p "127.0.0.1::5432" `
        -e POSTGRES_DB=postgres -e POSTGRES_USER=postgres `
        -e POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password `
        -v "${passwordFile}:/run/secrets/postgres_password:ro" $PostgresImage
    if ($LASTEXITCODE -ne 0) { throw "temporary_postgres_start_failed" }

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        docker exec $containerName pg_isready -U postgres -d postgres *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "temporary_postgres_not_ready" }

    $mapping = (docker port $containerName 5432/tcp | Select-Object -First 1).Trim()
    if ($mapping -notmatch ':(\d+)$') { throw "temporary_postgres_port_missing" }
    $port = $Matches[1]
    $encodedPassword = [Uri]::EscapeDataString($password)
    $previousUrl = $env:MIGRATION_TEST_POSTGRES_URL
    try {
        $env:MIGRATION_TEST_POSTGRES_URL = "postgresql+psycopg://postgres:${encodedPassword}@127.0.0.1:${port}/postgres"
        & (Join-Path $repoRoot ".venv\Scripts\python.exe") -m pytest `
            tests\test_migrations_fresh_postgres.py::test_alembic_upgrade_head_from_empty_postgres -q -rs
        if ($LASTEXITCODE -ne 0) { throw "temporary_postgres_migration_test_failed" }
    } finally {
        $env:MIGRATION_TEST_POSTGRES_URL = $previousUrl
    }
} finally {
    if (docker ps -a --format '{{.Names}}' | Select-String -SimpleMatch $containerName) {
        docker rm -f $containerName *> $null
    }
    $resolvedTemp = [IO.Path]::GetFullPath($tempDirectory)
    $systemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTemp.StartsWith($systemTemp, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedTemp).StartsWith("growen-migration-test-")) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
    $password = $null
}

Write-Output "migration_test_ok"
