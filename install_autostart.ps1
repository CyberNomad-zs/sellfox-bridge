# Register sellfox-bridge G2 3-shops as a startup scheduled task (local Windows).
# Run in PowerShell (建议管理员):  powershell -ExecutionPolicy Bypass -File install_autostart.ps1
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bat  = Join-Path $Root 'run_g2_3shops_service.bat'
$TaskName = 'SellfoxBridge-G2-3shops'

if (-not (Test-Path -LiteralPath $Bat)) { throw "Missing $Bat" }

# Stop existing bridge if any (avoid double instance)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'main\.py' } |
  ForEach-Object {
    Write-Host "Stopping existing PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $Bat -WorkingDirectory $Root
# At logon of current user (reliable with user-local Python under AppData)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -RestartCount 999 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -MultipleInstances IgnoreNew

# Run as current user, highest privilege; only while logged on is OK for local admin box
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Principal $principal `
  -Description 'sellfox-bridge G2 three shops (Agnis/HomeCove/Twilight). Config: config\config.g2-3shops.yaml' |
  Out-Null

Write-Host "Registered task: $TaskName"
Write-Host "  bat: $Bat"
Write-Host "  user: $env:USERNAME (AtLogOn)"
Write-Host ""
Write-Host "Start now:  Start-ScheduledTask -TaskName $TaskName"
Write-Host "Stop:       .\stop_bridge.ps1"
Write-Host "Status:     .\status_bridge.ps1"
Write-Host "Uninstall:  .\uninstall_autostart.ps1"