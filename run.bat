@echo off
REM ---------------------------------------------------------------------------
REM Grammar & Writing Enhancer - launcher
REM Creates a local venv on first run, installs deps, then starts the server.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv || goto :err
  call .venv\Scripts\activate.bat
  echo Installing dependencies...
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt || goto :err
) else (
  call .venv\Scripts\activate.bat
)

echo.
echo Starting server... (Ctrl+C to stop)
python app.py
goto :eof

:err
echo.
echo Setup failed. Make sure Python is installed and on PATH.
pause
exit /b 1
