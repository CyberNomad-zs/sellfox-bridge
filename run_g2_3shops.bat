@echo off
setlocal
cd /d "%~dp0"
title sellfox-bridge G2 3-shops
echo ========================================
echo  G2 THREE SHOPS - REAL applyTrackNo
echo  Agnis + HomeCove + Twilight Cove
echo  config: config\config.g2-3shops.yaml
echo ========================================
echo.
echo STOP other bridge processes first.
echo STOP automation full ship on all 3 shops.
echo.
set /p CONFIRM=Type YES to start G2 3-shops: 
if /I not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 1
)

set PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
if not exist "config\config.g2-3shops.yaml" (
  echo [ERROR] missing config
  pause
  exit /b 1
)
echo Starting...
"%PYEXE%" main.py --config config\config.g2-3shops.yaml
echo Exit code=%errorlevel%
pause
endlocal
