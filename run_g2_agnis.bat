@echo off
setlocal
cd /d "%~dp0"
title sellfox-bridge G2 Agnis DANGER
echo ========================================
echo  G2 Agnis - REAL applyTrackNo
echo  shop: 396706 Agnis ONLY
echo  WILL call Sellfox logistics order API
echo  packages in CHANNEL_ASSIGNED get ordered
echo  config: config\config.g2-agnis.yaml
echo ========================================
echo.
echo STOP G1 / dry-run first.
echo STOP automation full ship on Agnis.
echo Known CHANNEL_ASSIGNED will be ordered on first round
echo   e.g. P2AS6TCD63996 BLACKCAT-RM
echo.
set /p CONFIRM=Type YES to start G2 REAL order: 
if /I not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 1
)

set PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYEXE%" (
  echo [ERROR] Python not found
  pause
  exit /b 1
)
if not exist "config\config.g2-agnis.yaml" (
  echo [ERROR] Missing config\config.g2-agnis.yaml
  pause
  exit /b 1
)
echo.
echo Starting G2 at %date% %time%
echo.
"%PYEXE%" main.py --config config\config.g2-agnis.yaml
echo.
echo Exit code=%errorlevel%
pause
endlocal
