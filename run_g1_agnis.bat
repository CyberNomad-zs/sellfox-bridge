@echo off
setlocal
cd /d "%~dp0"
title sellfox-bridge G1 Agnis
echo ========================================
echo  G1 Agnis gray release
echo  shop: 396706 Agnis ONLY
echo  auto_apply_track_no: OFF
echo  NOT dry-run: local state advances
echo  NO auto logistics order
echo  config: config\config.g1-agnis.yaml
echo ========================================
echo.
echo STOP other bridge windows first (dry-run / HomeCove G1).
echo Do NOT run automation full ship on Agnis at the same time.
echo.
set /p CONFIRM=Type YES to start G1 Agnis: 
if /I not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 1
)

set PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYEXE%" (
  echo [ERROR] Python 3.12 not found
  pause
  exit /b 1
)
if not exist "config\config.g1-agnis.yaml" (
  echo [ERROR] Missing config\config.g1-agnis.yaml
  pause
  exit /b 1
)
echo.
echo Starting G1 Agnis at %date% %time%
echo.
"%PYEXE%" main.py --config config\config.g1-agnis.yaml
echo.
echo Exit code=%errorlevel%
pause
endlocal
