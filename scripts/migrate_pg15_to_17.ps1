#!/usr/bin/env pwsh
# NG-HEADER: Nombre de archivo: migrate_pg15_to_17.ps1
# NG-HEADER: Ubicación: scripts/migrate_pg15_to_17.ps1
# NG-HEADER: Descripción: Migra un volumen Postgres 15 a 17.6 (backup crudo + dump lógico + restauración).
# NG-HEADER: Lineamientos: Ver AGENTS.md

param(
  [string]$VolumeName = 'growen_pgdata',
  [string]$DbContainer = 'growen-postgres',
  [string]$Pg15Image   = 'postgres:15.10-bookworm',
  [string]$Pg17Service = 'db',
  [string]$User = $env:POSTGRES_USER,
  [string]$Password = $env:POSTGRES_PASSWORD,
  [string]$DbName = $env:POSTGRES_DB
)

$ErrorActionPreference = 'Stop'

function Read-DotEnv($path){
  $dict = @{}
  if(Test-Path $path){
    Get-Content -Raw -Path $path -Encoding UTF8 | ForEach-Object {
      foreach($line in $_ -split "`n"){
        $line = $line.Trim()
        if(-not $line -or $line.StartsWith('#')){ continue }
        $eq = $line.IndexOf('=')
        if($eq -gt 0){
          $k = $line.Substring(0,$eq).Trim()
          $v = $line.Substring($eq+1).Trim()
          $dict[$k] = $v
        }
      }
    }
  }
  return $dict
}

function Invoke-Docker([string[]]$DockerArgs){
  Write-Host "[DOCKER] docker $($DockerArgs -join ' ')" -ForegroundColor Cyan
  & docker @DockerArgs
}

function Wait-ContainerReady([string]$Name, [int]$Retries = 30){
  for($i=0; $i -lt $Retries; $i++){
    $row = & docker ps --format '{{.Names}}\t{{.Status}}' | Select-String -SimpleMatch $Name -ErrorAction SilentlyContinue
    if($row -and $row.ToString().Contains('Up')){ return $true }
    Start-Sleep -Seconds 2
  }
  return $false
}

# 1) Verificaciones iniciales
Write-Host "==> Iniciando migración PG15 → PG17.6" -ForegroundColor Green
& docker version | Out-Null

# Cargar .env si faltan credenciales
if(-not $User -or -not $Password -or -not $DbName){
  $envPath = Join-Path (Resolve-Path '.').Path '.env'
  $d = Read-DotEnv $envPath
  if(-not $User){ $User = $d['POSTGRES_USER'] }
  if(-not $Password){ $Password = $d['POSTGRES_PASSWORD'] }
  if(-not $DbName){ $DbName = $d['POSTGRES_DB'] }
}
if(-not $User -or -not $Password -or -not $DbName){
  throw "Faltan credenciales POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB (en entorno o .env)"
}

# 2) Parar DB si está corriendo
try{ & docker stop $DbContainer 2>$null | Out-Null } catch { }

# 3) Backup crudo del volumen
$ts  = Get-Date -Format 'yyyyMMdd-HHmmss'
$raw = Join-Path (Resolve-Path '.').Path ("backups/pg/raw-$ts")
New-Item -ItemType Directory -Force -Path $raw | Out-Null

Invoke-Docker @('run','--rm',
  '-v',"${VolumeName}:/var/lib/postgresql/data:ro",
  '-v',"${raw}:/backup",
  'alpine:3.19','sh','-lc','cd /var/lib/postgresql && tar -cf /backup/pgdata.tar data'
)

$rawTar = Join-Path $raw 'pgdata.tar'
if(-not (Test-Path $rawTar)){
  throw "No se generó $rawTar"
}
Write-Host "[OK] RAW: $rawTar" -ForegroundColor Green

# 4) Contenedor temporal PG15 para dump lógico
Invoke-Docker @('run','-d','--rm','--name','pg15tmp',
  '-e',"POSTGRES_USER=$User",'-e',"POSTGRES_PASSWORD=$Password",'-e',"POSTGRES_DB=$DbName",
  '-v',"${VolumeName}:/var/lib/postgresql/data",
  '-p','5435:5432',$Pg15Image
)

# Esperar readiness (verifica servicio, evita collation warning conectando a 'postgres')
$ready=$false
for($i=0;$i -lt 30;$i++){
  $proc = Start-Process -FilePath docker -ArgumentList @('exec','pg15tmp','pg_isready','-U',$User,'-d','postgres') -NoNewWindow -PassThru -Wait
  if($proc.ExitCode -eq 0){ $ready=$true; break }
  Start-Sleep -Seconds 2
}
if(-not $ready){ throw 'pg15tmp no quedó listo' }

Invoke-Docker @('exec','-e',"PGPASSWORD=$Password",'pg15tmp','pg_dump','-U',$User,'-d',$DbName,'-Fc','-f','/tmp/growen_15.dump')
Invoke-Docker @('cp','pg15tmp:/tmp/growen_15.dump', (Join-Path $raw 'growen_15.dump'))
Invoke-Docker @('rm','-f','pg15tmp') | Out-Null

$dumpPath = Join-Path $raw 'growen_15.dump'
if(-not (Test-Path $dumpPath)){
  throw "No se copió $dumpPath"
}
Write-Host "[OK] DUMP: $dumpPath" -ForegroundColor Green

# 5) Recrear volumen y levantar PG17.6
try{ Invoke-Docker @('volume','rm',$VolumeName) | Out-Null } catch { }

Write-Host "[UP] Levantando servicio $Pg17Service (PG17.6)" -ForegroundColor Cyan
& docker compose up -d $Pg17Service | Out-Null
if(-not (Wait-ContainerReady -Name $DbContainer -Retries 30)){
  throw "El contenedor $DbContainer no quedó 'Up'"
}

# 6) Restaurar dump en PG17.6
Invoke-Docker @('cp',$dumpPath, "${DbContainer}:/tmp/growen_15.dump")
Invoke-Docker @('exec','-e',"PGPASSWORD=$Password",$DbContainer,'sh','-lc',
  "pg_restore -U $User -d $DbName -c -j 4 /tmp/growen_15.dump")

Write-Host "[OK] Restauración completada en PG17.6" -ForegroundColor Green
Write-Host "Siguiente: ejecutar 'alembic upgrade head' y levantar api/frontend (docker compose up -d api frontend)." -ForegroundColor Yellow
