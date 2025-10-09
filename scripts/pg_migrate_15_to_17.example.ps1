Param(
  [string]$VolumeName = "growen_pgdata",
  [string]$BackupDir = "backups/pg_migrate",
  [string]$User = $env:PGUSER,
  [string]$Password = $env:PGPASSWORD,
  [string]$DbName = $env:PGDATABASE,
  [int]$TempPort = 5544,
  [switch]$ResetData
)

# Este script es un ejemplo. No commitees credenciales.
# Copiá este archivo como pg_migrate_15_to_17.ps1 y completá tus variables por ENV o parámetros.

Write-Host "[pg-migrate] Iniciando migración de Postgres 15 -> 17.6 (volumen: $VolumeName)" -ForegroundColor Cyan

function Ensure-Dir($p) { if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }
function Run-OrThrow([string]$cmd) {
  Write-Host "[cmd] $cmd" -ForegroundColor DarkGray
  $proc = Start-Process -FilePath "powershell" -ArgumentList "-NoProfile","-Command", $cmd -NoNewWindow -PassThru -Wait
  if ($proc.ExitCode -ne 0) { throw "Comando falló ($($proc.ExitCode)): $cmd" }
}

if (-not $User -or -not $Password -or -not $DbName) {
  throw "Definí PGUSER/PGPASSWORD/PGDATABASE por variables de entorno o pasa -User/-Password/-DbName"
}

Ensure-Dir $BackupDir

try { docker compose stop db | Out-Null } catch {}
if ($ResetData) { Write-Warning "ResetData=ON: se eliminará el volumen $VolumeName tras backup crudo." }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$rawTgz = Join-Path $BackupDir "pgdata_raw_15_$ts.tgz"
Write-Host "[pg-migrate] Backup crudo -> $rawTgz"
try { docker rm -f pgrawbak | Out-Null } catch {}
Run-OrThrow "docker run --name pgrawbak -v $VolumeName`:/var/lib/postgresql/data alpine:3.19 sh -lc 'apk add --no-cache tar >/dev/null; tar -C /var/lib -cz postgresql > /tmp/pgdata_raw_15_$ts.tgz'"
Run-OrThrow "docker cp pgrawbak`:/tmp/pgdata_raw_15_$ts.tgz \"$rawTgz\""
try { docker rm -f pgrawbak | Out-Null } catch {}

if (-not $ResetData) {
  Write-Host "[pg-migrate] Iniciando contenedor temporal postgres:15..."
  Run-OrThrow "docker run -d --rm --name pg15tmp -e POSTGRES_USER=$User -e POSTGRES_PASSWORD=$Password -e POSTGRES_DB=$DbName -v $VolumeName`:/var/lib/postgresql/data -p $TempPort`:5432 postgres:15"
  $deadline = (Get-Date).AddMinutes(2)
  do { Start-Sleep -Milliseconds 700; $ok = (docker exec pg15tmp pg_isready -U $User 2>$null) -join '' } while((Get-Date) -lt $deadline -and ($ok -notmatch 'accepting'))
  if ($ok -notmatch 'accepting') { throw "Postgres 15 temporal no quedó ready" }
  $dumpFile = Join-Path $BackupDir "dump_15_$ts.sql"
  Write-Host "[pg-migrate] Generando dump lógico -> $dumpFile"
  Run-OrThrow "docker exec pg15tmp bash -lc 'pg_dumpall -U $User > /tmp/dump_15_$ts.sql'"
  Run-OrThrow "docker cp pg15tmp`:/tmp/dump_15_$ts.sql \"$dumpFile\""
  try { docker stop pg15tmp | Out-Null } catch {}
}

Write-Host "[pg-migrate] Para restaurar en 17.6:"
Write-Host "  1) docker compose up -d db" -ForegroundColor Yellow
Write-Host "  2) type backups\\pg_migrate\\dump_15_$ts.sql | docker exec -i growen-postgres psql -U $User -d postgres" -ForegroundColor Yellow
Write-Host "  3) alembic upgrade head" -ForegroundColor Yellow

Write-Host "[pg-migrate] Listo." -ForegroundColor Green
