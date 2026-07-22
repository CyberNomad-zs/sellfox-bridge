$TaskName = 'SellfoxBridge-G2-3shops'
# avoid double instance
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'main\.py' }
if ($running) {
  Write-Host "Already running:"
  $running | ForEach-Object { Write-Host "  PID=$($_.ProcessId) $($_.CommandLine)" }
  exit 0
}
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $t) {
  Write-Host "Task not installed. Run: powershell -ExecutionPolicy Bypass -File install_autostart.ps1"
  # fallback direct start
  $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
  Start-Process -FilePath (Join-Path $Root 'run_g2_3shops_service.bat') -WorkingDirectory $Root -WindowStyle Minimized
  Write-Host "Started via bat (no scheduled task)."
  exit 0
}
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3
.\status_bridge.ps1