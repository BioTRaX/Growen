# NG-HEADER: Nombre de archivo: provision-lan-pki.ps1
# NG-HEADER: Ubicación: scripts/provision-lan-pki.ps1
# NG-HEADER: Descripción: Genera una CA interna y certificados LAN fuera del repositorio.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)][string]$IPAddress,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [Parameter(Mandatory = $true)][string]$RootKeyPasswordFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw "powershell_7_or_newer_required"
}

function Test-PathInside([string]$Candidate, [string]$Parent) {
    $candidatePath = [IO.Path]::GetFullPath($Candidate).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $parentPath = [IO.Path]::GetFullPath($Parent).TrimEnd([IO.Path]::DirectorySeparatorChar)
    return $candidatePath.Equals($parentPath, [StringComparison]::OrdinalIgnoreCase) -or
        $candidatePath.StartsWith($parentPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
}

$parsedAddress = $null
if (-not [Net.IPAddress]::TryParse($IPAddress, [ref]$parsedAddress)) {
    throw "invalid_ip_address"
}
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$resolvedOutput = [IO.Path]::GetFullPath($OutputDir)
$resolvedPassword = [IO.Path]::GetFullPath($RootKeyPasswordFile)
if ((Test-PathInside $resolvedOutput $repoRoot) -or (Test-PathInside $resolvedPassword $repoRoot)) {
    throw "pki_material_must_be_outside_repository"
}
if ((Test-Path -LiteralPath $resolvedOutput) -and (Get-ChildItem -LiteralPath $resolvedOutput -Force | Select-Object -First 1)) {
    throw "pki_output_directory_must_be_empty"
}
if (-not $PSCmdlet.ShouldProcess($resolvedOutput, "Generar CA interna y certificados LAN")) {
    Write-Output "pki_plan ip=$IPAddress output=$resolvedOutput"
    return
}
if (-not (Test-Path -LiteralPath $resolvedPassword -PathType Leaf)) {
    throw "root_key_password_file_missing"
}
$rootPassword = (Get-Content -LiteralPath $resolvedPassword -Raw).TrimEnd("`r", "`n")
if ($rootPassword.Length -lt 16) { throw "root_key_password_too_short" }
[IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

function New-SerialNumber {
    $serial = [byte[]]::new(16)
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($serial) } finally { $rng.Dispose() }
    $serial[0] = $serial[0] -band 0x7F
    return $serial
}

$rsaRoot = [Security.Cryptography.RSA]::Create(4096)
try {
    $rootRequest = [Security.Cryptography.X509Certificates.CertificateRequest]::new(
        "CN=Growen LAN Root CA",
        $rsaRoot,
        [Security.Cryptography.HashAlgorithmName]::SHA256,
        [Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
    $rootRequest.CertificateExtensions.Add(
        [Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($true, $false, 0, $true)
    )
    $rootRequest.CertificateExtensions.Add(
        [Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
            [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyCertSign -bor
            [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::CrlSign,
            $true
        )
    )
    $rootRequest.CertificateExtensions.Add(
        [Security.Cryptography.X509Certificates.X509SubjectKeyIdentifierExtension]::new($rootRequest.PublicKey, $false)
    )
    $notBefore = [DateTimeOffset]::UtcNow.AddMinutes(-5)
    $rootCertificate = $rootRequest.CreateSelfSigned($notBefore, $notBefore.AddDays(3650))
    try {
        $pbe = [System.Security.Cryptography.PbeParameters]::new(
            [Security.Cryptography.PbeEncryptionAlgorithm]::Aes256Cbc,
            [Security.Cryptography.HashAlgorithmName]::SHA256,
            200000
        )
        Write-Utf8NoBom (Join-Path $resolvedOutput "growen-lan-root-ca.crt") $rootCertificate.ExportCertificatePem()
        Write-Utf8NoBom (Join-Path $resolvedOutput "growen-lan-root-ca.key") $rsaRoot.ExportEncryptedPkcs8PrivateKeyPem($rootPassword, $pbe)

        foreach ($leaf in @(
            @{ Name = "growen-lan"; CommonName = "Growen LAN" },
            @{ Name = "registry-lan"; CommonName = "Growen Registry LAN" }
        )) {
            $leafKey = [Security.Cryptography.RSA]::Create(3072)
            try {
                $request = [Security.Cryptography.X509Certificates.CertificateRequest]::new(
                    "CN=$($leaf.CommonName)",
                    $leafKey,
                    [Security.Cryptography.HashAlgorithmName]::SHA256,
                    [Security.Cryptography.RSASignaturePadding]::Pkcs1
                )
                $san = [Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
                $san.AddIpAddress($parsedAddress)
                $request.CertificateExtensions.Add($san.Build())
                $request.CertificateExtensions.Add(
                    [Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
                        [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature -bor
                        [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyEncipherment,
                        $true
                    )
                )
                $eku = [Security.Cryptography.OidCollection]::new()
                [void]$eku.Add([Security.Cryptography.Oid]::new("1.3.6.1.5.5.7.3.1"))
                $request.CertificateExtensions.Add(
                    [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($eku, $true)
                )
                $request.CertificateExtensions.Add(
                    [Security.Cryptography.X509Certificates.X509AuthorityKeyIdentifierExtension]::CreateFromCertificate(
                        $rootCertificate,
                        $true,
                        $false
                    )
                )
                $certificate = $request.Create($rootCertificate, $notBefore, $notBefore.AddDays(397), (New-SerialNumber))
                try {
                    Write-Utf8NoBom (Join-Path $resolvedOutput "$($leaf.Name).crt") $certificate.ExportCertificatePem()
                    Write-Utf8NoBom (Join-Path $resolvedOutput "$($leaf.Name).key") $leafKey.ExportPkcs8PrivateKeyPem()
                } finally {
                    $certificate.Dispose()
                }
            } finally {
                $leafKey.Dispose()
            }
        }
    } finally {
        $rootCertificate.Dispose()
    }
} finally {
    $rsaRoot.Dispose()
    $rootPassword = $null
}

& icacls.exe $resolvedOutput /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
Write-Output "pki_created output=$resolvedOutput ip=$IPAddress"
