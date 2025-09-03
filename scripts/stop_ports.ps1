# Stops processes listening on ports (safe fallback to netstat)
#
# NOTE: If you run a PowerShell one-line syntax check using
# [System.Management.Automation.Language.Parser]::ParseFile, you must
# pass actual reference variables (e.g. [ref]$errors) — do NOT use
# `[ref]$null` directly because that produces the error
# "Argumento: '2' debe ser System.Management.Automation.PSReference. Use [ref]."
#
# Example (recommended):
# $errors = $null; $tokens = $null; 
# [System.Management.Automation.Language.Parser]::ParseFile('\path\to\script.ps1',[ref]$errors,[ref]$tokens) | Out-Null; Write-Host 'PARSE_OK'
param(
    [int[]]
    $Ports = @(8000, 5173)
)

foreach ($port in $Ports) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($conns) {
            # Ensure PIDs are ints
            $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { [int]$_ }
            foreach ($procId in $procIds) {
                Write-Output ("Stopping PID {0} on port {1}" -f $procId, $port)
                try {
                    Stop-Process -Id $procId -Force -ErrorAction Stop
                } catch {
                    $errMsg = $_.Exception.Message
                    Write-Warning ("Could not stop PID {0}: {1}" -f $procId, $errMsg)
                }
            }
        } else {
            Write-Output ("No process on port {0}" -f $port)
        }
    } catch {
        Write-Warning ("Get-NetTCPConnection failed, falling back to netstat for port {0}" -f $port)
        # Select-String returns MatchInfo objects; use the .Line property to get the raw text
    $pattern = ":$port"
    $lines = netstat -ano | Select-String $pattern | ForEach-Object { $_.Line }
        if ($lines) {
            foreach ($l in $lines) {
                # Try to extract the process id string using a regex that captures the last integer in the line
                $netstatProcessStr = $null
                if ($l -match '\b(\d+)\s*$') {
                    $netstatProcessStr = $Matches[1]
                } else {
                    Write-Warning ("Could not parse process id from netstat line: {0}" -f $l)
                    continue
                }
                # Validate process id is integer before calling Stop-Process
                $processIdInt = 0
                $ok = [int]::TryParse($netstatProcessStr, [ref]$processIdInt)
                if ($ok) {
                    Write-Output ("Stopping process {0} (netstat) for port {1}" -f $processIdInt, $port)
                    try {
                        Stop-Process -Id $processIdInt -Force -ErrorAction Stop
                    } catch {
                        $errMsg = $_.Exception.Message
                        Write-Warning ("Could not stop process {0}: {1}" -f $processIdInt, $errMsg)
                    }
                } else {
                    Write-Warning ("Skipping invalid process id '{0}' found in netstat output for port {1}" -f $netstatProcessStr, $port)
                }
            }
        } else {
            Write-Output ("No process on port {0} (netstat)" -f $port)
        }
    }
}

Write-Output "Done stopping ports."
