@echo off
REM ===========================================================================
REM Self-hosted LanguageTool server launcher
REM
REM Downloads LanguageTool on first run (~250 MB), then starts the HTTP server
REM on http://localhost:8081 with CORS enabled so the standalone.html page
REM can call it from the browser.
REM
REM Requirements: Java 17+ on PATH (you already have Eclipse Temurin 17).
REM ===========================================================================
setlocal enableextensions
cd /d "%~dp0"

set "LT_DIR=lt-server"
set "LT_JAR=%LT_DIR%\languagetool-server.jar"
set "LT_VERSION=6.4"
set "LT_URL=https://languagetool.org/download/LanguageTool-%LT_VERSION%.zip"
set "LT_ZIP=lt.zip"
set "PORT=8081"

REM --- Check Java ---------------------------------------------------------
where java >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Java not found on PATH. Install Eclipse Temurin JDK 17+ and retry.
  pause
  exit /b 1
)

REM --- Download + extract on first run ------------------------------------
if not exist "%LT_JAR%" (
  echo Downloading LanguageTool %LT_VERSION% (about 250 MB)...
  powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%LT_URL%' -OutFile '%LT_ZIP%'" || goto :err
  echo Extracting...
  powershell -NoProfile -Command "Expand-Archive -Path '%LT_ZIP%' -DestinationPath '.' -Force" || goto :err
  REM Extracted folder is "LanguageTool-<version>" — rename to lt-server
  if exist "LanguageTool-%LT_VERSION%" (
    if exist "%LT_DIR%" rmdir /s /q "%LT_DIR%"
    ren "LanguageTool-%LT_VERSION%" "%LT_DIR%"
  )
  del "%LT_ZIP%" >nul 2>nul
  if not exist "%LT_JAR%" (
    echo [ERROR] Server JAR not found after extraction.
    goto :err
  )
)

REM --- Start the server ---------------------------------------------------
echo.
echo Starting LanguageTool server at http://localhost:%PORT% ...
echo CORS enabled for browser access. Press Ctrl+C to stop.
echo.

java -cp "%LT_JAR%" org.languagetool.server.HTTPServer ^
     --port %PORT% --allow-origin "*"

goto :eof

:err
echo.
echo [FAILED] LanguageTool setup failed. Check your internet connection.
pause
exit /b 1
