# Install daily recon scheduled task (local Windows).
# Usage: powershell -ExecutionPolicy Bypass -File install_recon_daily.ps1
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bat = Join-Path $Root 'run_recon_daily.bat'
$TaskName = 'SellfoxBridge-Recon-Daily'

if (-not (Test-Path -LiteralPath $Bat)) { throw "Missing $Bat" }
if (-not (Test-Path -LiteralPath (Join-Path $Root 'recon.py'))) { throw "Missing recon.py" }

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $Bat -WorkingDirectory $Root
# Daily at 08:07 local time (off the hour to reduce fleet pile-up)
$trigger = New-ScheduledTaskTrigger -Daily -At '08:07'
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
  -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Principal $principal `
  -Description 'sellfox-bridge daily recon (read-only). Logs: logs\recon_YYYYMMDD.log. Config: config.g2-3shops.yaml' |
  Out-Null

Write-Host "Registered task: $TaskName"
Write-Host "  Schedule: daily 08:07 (local)"
Write-Host "  Bat: $Bat"
Write-Host "  User: $env:USERNAME"
Write-Host ""
Write-Host "Run once now:  Start-ScheduledTask -TaskName $TaskName"
Write-Host "Or manual:     .\run_recon_daily.bat"
Write-Host "Uninstall:     .\uninstall_recon_daily.ps1"
Write-Host "Status:        Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"