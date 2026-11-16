@echo off
setlocal
title Froja Image Studio
cd /d "%~dp0"
rem Keep this aligned with backend.py's safe default. VPN/Hyper-V networking can
rem reserve blocks of local ports; this machine currently reserves 3190-3289.
set "FROJA_PORT=3310"
set "FROJA_URL=http://127.0.0.1:%FROJA_PORT%"
set "PYTHONUNBUFFERED=1"

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

echo Checking Froja Image-to-Prompt vision service...
powershell -NoProfile -Command "try {(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 2).StatusCode}catch {0}" | findstr /x "200" >nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    start "Froja Vision" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    powershell -NoProfile -Command "for($i=0;$i -lt 20;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 2|Out-Null;exit 0}catch{Start-Sleep -Seconds 1}};exit 1"
    if errorlevel 1 echo WARNING: Ollama did not become ready. Image to Prompt will be unavailable.
  ) else (
    echo WARNING: Ollama is not installed. Image to Prompt will be unavailable.
  )
)

for /f %%A in ('powershell -NoProfile -Command "try {(Invoke-WebRequest -UseBasicParsing $env:FROJA_URL -TimeoutSec 2).StatusCode}catch {0}"') do set FROJA_STATUS=%%A
if "%FROJA_STATUS%"=="200" (
  echo Froja is already running at %FROJA_URL%
  start "" "%FROJA_URL%"
  echo.
  echo Live Froja activity terminal
  echo The server is already running. This window will remain open.
  echo Press Ctrl+C to stop monitoring; this will not stop Froja.
  echo.
  if not exist "logs" mkdir "logs"
  if not exist "logs\backend.out.log" type nul > "logs\backend.out.log"
  if not exist "logs\backend.err.log" type nul > "logs\backend.err.log"
  powershell -NoProfile -Command "Get-Content -LiteralPath 'logs\backend.out.log','logs\backend.err.log' -Tail 0 -Wait"
  exit /b 0
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "$url=$env:FROJA_URL; for($i=0;$i -lt 40;$i++){try{Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2|Out-Null; Start-Process $url; exit}catch{Start-Sleep -Seconds 1}}"

echo Preparing Froja...
if not exist "node_modules" (
  call npm install
  if errorlevel 1 (
    echo ERROR: Froja dependencies could not be installed.
    pause
    exit /b 1
  )
)
if not exist "dist\index.html" (
  call npm run build
  if errorlevel 1 (
    echo ERROR: Froja interface could not be built.
    pause
    exit /b 1
  )
)
rem Do not reuse the optional Ollama check's errorlevel as a preparation result.
ver >nul

rem The image engine's Python comes from config\config.local.json ("comfy_python"), so Froja works on any PC.
set "FROJA_COMFY_PY="
if exist "config\config.local.json" (
  for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "try { (Get-Content -Raw 'config\config.local.json' | ConvertFrom-Json).comfy_python } catch { '' }"`) do set "FROJA_COMFY_PY=%%P"
)

echo Starting Froja Local Media tools...
powershell -NoProfile -Command "try {(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9010/status -TimeoutSec 2).StatusCode}catch {0}" | findstr /x "200" >nul
if errorlevel 1 if defined FROJA_COMFY_PY if exist "%FROJA_COMFY_PY%" (
  start "Froja Local Media" /min "%FROJA_COMFY_PY%" "%~dp0extensions\froja_media_bridge.py"
)

rem Which Python runs Froja: its own .venv first, then ComfyUI's (from the settings), then the system Python.
set "FROJA_PY=python"
if defined FROJA_COMFY_PY if exist "%FROJA_COMFY_PY%" set "FROJA_PY=%FROJA_COMFY_PY%"
if exist ".venv\Scripts\python.exe" set "FROJA_PY=.venv\Scripts\python.exe"

echo Starting Froja at %FROJA_URL%
echo Keep this window open while using Froja.
echo Press Ctrl+C here to stop it.
echo.
"%FROJA_PY%" backend.py

echo.
echo Froja stopped or failed to start.
pause
