@echo off
setlocal
cd /d "%~dp0"
title sellfox-bridge recon
set PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
echo Running recon (read-only)...
"%PYEXE%" recon.py --config config\config.g2-agnis.yaml --days 7 %*
echo.
pause
endlocal
