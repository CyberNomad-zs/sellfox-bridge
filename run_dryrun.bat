@echo off
setlocal
cd /d "%~dp0"
title sellfox-bridge dry-run
echo ========================================
echo  sellfox-bridge dry-run (read-only)
echo  log: bridge.log
echo  stop: Ctrl+C
echo  dir: %CD%
echo ========================================
echo.

set PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYEXE%" (
  echo [ERROR] Python 3.12 not found:
  echo   %PYEXE%
  echo Install Python 3.12 or edit PYEXE in this bat.
  goto END
)

echo Using: %PYEXE%
"%PYEXE%" --version
if errorlevel 1 (
  echo [ERROR] Python failed to start.
  goto END
)

"%PYEXE%" -c "import yaml,requests"
if errorlevel 1 (
  echo [INFO] Installing dependencies...
  "%PYEXE%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  if errorlevel 1 (
    echo [ERROR] pip install failed.
    goto END
  )
)

if not exist "config\config.yaml" (
  echo [ERROR] Missing config\config.yaml
  goto END
)
if not exist "main.py" (
  echo [ERROR] Missing main.py
  goto END
)

echo.
echo Starting at %date% %time%
echo.
"%PYEXE%" main.py --dry-run
echo.
echo Exit code=%errorlevel%

:END
echo.
pause
endlocal
