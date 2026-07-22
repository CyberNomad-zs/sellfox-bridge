$TaskName = 'SellfoxBridge-G2-3shops'
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'main\.py' } |
  ForEach-Object {
    Write-Host "Stopping PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
Write-Host "Bridge stopped."