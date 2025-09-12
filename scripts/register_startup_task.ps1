param(
    [string]$TaskName = 'Growen-StartStack',
    [string]$Trigger = 'Logon'
)

# Registers a Windows Scheduled Task to start Docker, Redis, and Dramatiq worker on user logon.
# Requires running PowerShell as Administrator for registration.

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $root 'scripts' 'start_stack.ps1'
if (!(Test-Path $script)) { throw "Script not found: $script" }

# Build the action to run PowerShell with ExecutionPolicy Bypass
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""

# Trigger: at logon of any user
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Settings: start only if network is available; allow running on AC/battery; restart on failure
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Run with highest privileges to allow Docker start
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Highest

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal

# Register (update if exists)
try {
    $exists = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($exists) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false | Out-Null
    }
} catch { }

Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
Write-Output "Registered task '$TaskName'. It will run at user logon."
