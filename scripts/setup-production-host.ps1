# NG-HEADER: Nombre de archivo: setup-production-host.ps1
# NG-HEADER: Ubicación: scripts/setup-production-host.ps1
# NG-HEADER: Descripción: Configura firewall de Windows y confianza del certificado raíz CA LAN para producción Swarm
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [string]$CaPath = "C:\Users\alete\.growen\pki\2026091002\growen-lan-root-ca.crt",
    [string]$ExpectedThumbprint = "314D2EBE85AEABD00F091BE25D243337827A7A1C",
    [string]$LanSubnet = "192.168.100.0/24",
    [string]$HostIp = "192.168.100.100"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 1. Comprobar privilegios de Administrador
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Este script requiere elevación como Administrador para configurar el Firewall y Cert:\LocalMachine\Root."
    Write-Host "Por favor, ejecute PowerShell como Administrador y vuelva a correr este script." -ForegroundColor Yellow
    exit 1
}

Write-Host "=== 1. Limpieza de certificados CA obsoletos en CurrentUser y LocalMachine ===" -ForegroundColor Cyan
$storeLocations = @(
    [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser,
    [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine
)

foreach ($loc in $storeLocations) {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::Root, $loc)
    try {
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $certsToRemove = @()
        foreach ($c in $store.Certificates) {
            if ($c.Subject -like "*CN=Growen LAN Root CA*" -and $c.Thumbprint -ne $ExpectedThumbprint) {
                $certsToRemove += $c
            }
        }
        foreach ($oldCert in $certsToRemove) {
            Write-Host "Removiendo CA obsoleta en $($loc): $($oldCert.Thumbprint)" -ForegroundColor Yellow
            $store.Remove($oldCert)
        }
    } catch {
        Write-Warning "No se pudo limpiar en $($loc): $($_.Exception.Message)"
    } finally {
        $store.Close()
    }
}

Write-Host "`n=== 2. Instalación de nueva CA raíz en Cert:\LocalMachine\Root ===" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $CaPath -PathType Leaf)) {
    throw "No se encontró el archivo de certificado en: $CaPath"
}

$certObj = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CaPath)
if ($certObj.Thumbprint -ne $ExpectedThumbprint) {
    throw "La huella del certificado ($($certObj.Thumbprint)) no coincide con la esperada ($ExpectedThumbprint)"
}

$lmStore = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::Root, [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine)
try {
    $lmStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $alreadyInstalled = $false
    foreach ($c in $lmStore.Certificates) {
        if ($c.Thumbprint -eq $ExpectedThumbprint) {
            $alreadyInstalled = $true
            break
        }
    }
    if (-not $alreadyInstalled) {
        $lmStore.Add($certObj)
        Write-Host "[OK] CA instalada con éxito en LocalMachine\Root (Huella: $ExpectedThumbprint)" -ForegroundColor Green
    } else {
        Write-Host "[OK] La CA ya está presente en LocalMachine\Root (Huella: $ExpectedThumbprint)" -ForegroundColor Green
    }
} finally {
    $lmStore.Close()
}

Write-Host "`n=== 3. Configuración de reglas de Firewall de Windows ===" -ForegroundColor Cyan
$rules = @(
    @{ Name = "Growen LAN HTTP"; Port = 80; Desc = "Permite tráfico HTTP LAN hacia Growen" },
    @{ Name = "Growen LAN HTTPS"; Port = 443; Desc = "Permite tráfico HTTPS LAN seguro hacia Growen" },
    @{ Name = "Growen LAN Registry"; Port = 5000; Desc = "Permite acceso al registro Docker LAN seguro" }
)

foreach ($r in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-NetFirewallRule -DisplayName $r.Name
        Write-Host "Regla preexistente eliminada para actualizar: $($r.Name)" -ForegroundColor Yellow
    }
    New-NetFirewallRule `
        -DisplayName $r.Name `
        -Group "Growen LAN Production" `
        -Description $r.Desc `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $r.Port `
        -LocalAddress $HostIp `
        -RemoteAddress $LanSubnet `
        -Profile Private | Out-Null
    Write-Host "[OK] Regla de firewall activa: $($r.Name) (Puerto $($r.Port))" -ForegroundColor Green
}

Write-Host "`n=== 4. Verificación de perfil de red y reglas activas ===" -ForegroundColor Cyan
Get-NetConnectionProfile | Select-Object InterfaceAlias, NetworkCategory, IPv4Connectivity | Format-Table -AutoSize
Get-NetFirewallRule -Group "Growen LAN Production" | Select-Object DisplayName, Enabled, Direction, Action | Format-Table -AutoSize

Write-Host "=== Tareas de host completadas exitosamente ===" -ForegroundColor Green
Write-Host 'ACCIÓN REQUERIDA: Reinicia Docker Desktop ahora para que tome la nueva CA de Windows.' -ForegroundColor Yellow

