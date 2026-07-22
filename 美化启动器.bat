@echo off
rem Graphical launcher for sellfox-bridge (opens gui.py).
cd /d "%~dp0"
where pythonw >nul 2>nul && ( start "" pythonw "%~dp0gui.py" & goto :eof )
if exist "%LocalAppData%\Programs\Python\Python312\pythonw.exe" (
  start "" "%LocalAppData%\Programs\Python\Python312\pythonw.exe" "%~dp0gui.py"
  goto :eof
)
where python >nul 2>nul && ( start "" python "%~dp0gui.py" & goto :eof )
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  start "" "%LocalAppData%\Programs\Python\Python312\python.exe" "%~dp0gui.py"
  goto :eof
)
py -3.12 "%~dp0gui.py"
if errorlevel 1 pause
