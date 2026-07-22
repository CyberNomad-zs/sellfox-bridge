# One-shot daily recon (same as scheduled task)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
& .\run_recon_daily.bat
Write-Host "Exit code: $LASTEXITCODE"
$day = Get-Date -Format 'yyyyMMdd'
$log = Join-Path $Root "logs\recon_$day.log"
if (Test-Path $log) {
  Write-Host "--- tail $log ---"
  Get-Content -LiteralPath $log -Tail 30 -Encoding UTF8
}