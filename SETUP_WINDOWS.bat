@echo off
setlocal
cd /d "%~dp0"
echo Setting up Froja Image Studio for Windows...
where node >nul 2>nul || (echo ERROR: Install Node.js 22 or newer first. & pause & exit /b 1)
where python >nul 2>nul || (echo ERROR: Install Python 3.10 or newer first. & pause & exit /b 1)
python -m venv .venv
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
call npm install
call npm run build
if not exist config\config.local.json copy config\config.example.json config\config.local.json >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_SHORTCUTS.ps1"
echo.
echo Setup complete. Edit config\config.local.json with your ComfyUI paths,
echo then use the Froja Image Studio shortcut on your Desktop or Start Menu.
pause
