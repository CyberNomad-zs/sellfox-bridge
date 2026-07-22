$TaskName = 'SellfoxBridge-G2-3shops'
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($t) {
  $i = Get-ScheduledTaskInfo -TaskName $TaskName
  Write-Host "Task: $TaskName  State=$($t.State)  LastResult=$($i.LastTaskResult)  LastRun=$($i.LastRunTime)"
} else {
  Write-Host "Task: $TaskName not installed"
}
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'main\.py' }
if ($procs) {
  Write-Host "Process:"
  $procs | ForEach-Object { Write-Host "  PID=$($_.ProcessId) $($_.CommandLine)" }
} else {
  Write-Host "Process: not running"
}
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log1 = Join-Path $Root 'bridge.log'
$log2 = Join-Path $Root 'logs\g2_stdout.log'
if (Test-Path $log1) {
  Write-Host "--- bridge.log tail ---"
  Get-Content -LiteralPath $log1 -Tail 8 -Encoding UTF8
}
if (Test-Path $log2) {
  Write-Host "--- logs\g2_stdout.log tail ---"
  Get-Content -LiteralPath $log2 -Tail 5 -Encoding UTF8
}