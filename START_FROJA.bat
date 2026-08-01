@echo off
setlocal
title Froja Image Studio
cd /d "%~dp0"

echo ==================================================
echo               Froja Image Studio
echo ==================================================
echo Models are linked from their existing folders.
echo No checkpoints or LoRAs are copied.
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js was not found.
  echo.
  pause
  exit /b 1
)

for /f %%A in ('powershell -NoProfile -Command "try {(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000 -TimeoutSec 2).StatusCode}catch {0}"') do set FROJA_STATUS=%%A
if "%FROJA_STATUS%"=="200" (
  echo Froja is already running at http://127.0.0.1:3000
  start "" http://127.0.0.1:3000
  exit /b 0
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "$url='http://localhost:3000'; for($i=0;$i -lt 40;$i++){try{Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2|Out-Null; Start-Process $url; exit}catch{Start-Sleep -Seconds 1}}"

echo Preparing Froja...
if not exist "node_modules" call npm install
if not exist "dist\index.html" call npm run build
if errorlevel 1 (
  echo ERROR: Froja could not be prepared.
  pause
  exit /b 1
)

echo Starting Froja at http://localhost:3000
echo Keep this window open while using Froja.
echo Press Ctrl+C here to stop it.
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" backend.py
) else (
  python backend.py
)

echo.
echo Froja stopped or failed to start.
pause
