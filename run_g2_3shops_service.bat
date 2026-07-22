@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir logs
set PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYEXE%" (
  echo [%date% %time%] ERROR: Python not found: %PYEXE%>> logs\g2_service.log
  exit /b 1
)
if not exist "config\config.g2-3shops.yaml" (
  echo [%date% %time%] ERROR: missing config\config.g2-3shops.yaml>> logs\g2_service.log
  exit /b 1
)
echo [%date% %time%] starting G2 3shops>> logs\g2_service.log
"%PYEXE%" main.py --config config\config.g2-3shops.yaml >> logs\g2_stdout.log 2>&1
echo [%date% %time%] exited code=%errorlevel%>> logs\g2_service.log
endlocal
exit /b %errorlevel%
