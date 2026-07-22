@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir logs
set PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
set CFG=config\config.g2-3shops.yaml
if not exist "%CFG%" set CFG=config\config.yaml
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set DAY=%%I
set LOG=logs\recon_%DAY%.log
echo ===== recon start %date% %time% cfg=%CFG% =====>> "%LOG%"
if not exist "%PYEXE%" (
  echo ERROR: Python not found %PYEXE%>> "%LOG%"
  exit /b 1
)
"%PYEXE%" recon.py --config "%CFG%" --days 7 >> "%LOG%" 2>&1
set RC=%errorlevel%
echo ===== recon end %date% %time% exit=%RC% =====>> "%LOG%"
endlocal & exit /b %RC%
