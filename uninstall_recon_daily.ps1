$TaskName = 'SellfoxBridge-Recon-Daily'
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Unregistered $TaskName"