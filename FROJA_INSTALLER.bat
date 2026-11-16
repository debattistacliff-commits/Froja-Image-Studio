<# :
@echo off
rem ===================================================================
rem  Froja Image Studio - one-click installer for Windows
rem  Download this one file, double-click it, answer a few questions.
rem  It asks before it installs anything.
rem ===================================================================
title Froja Image Studio - Installer
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:FROJA_INSTALLER_FILE='%~f0'; Invoke-Expression ([IO.File]::ReadAllText('%~f0'))"
echo.
pause
exit /b
#>

# ------------------------------------------------------------------
# PowerShell part (the lines above only start it).
# For automated tests these environment variables skip the questions:
#   FROJA_ASSUME_YES=1  FROJA_INSTALL_DIR=...  FROJA_COMFY_DIR=...
#   FROJA_SKIP_PACKAGES=1 (never run winget)  FROJA_NO_SHORTCUT=1  FROJA_NO_START=1
#   FROJA_SOURCE_ZIP=<path or url of a Froja zip instead of the latest release>
# ------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Repo = "debattistacliff-commits/Froja-Image-Studio"
$Yes = $env:FROJA_ASSUME_YES -eq "1"

function Say($text, $color = "Gray") { Write-Host $text -ForegroundColor $color }
function Step($n, $text) { Write-Host ""; Write-Host "[$n] $text" -ForegroundColor Cyan }
function Ask-YesNo($question, $default = $true) {
    if ($Yes) { return $default }
    $hint = if ($default) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "$question $hint"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $default }
    return $answer.Trim().ToLower().StartsWith("y")
}
function Ask-Text($question, $default) {
    if ($Yes) { return $default }
    $answer = Read-Host "$question`n  (press Enter for: $default)"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $default }
    return $answer.Trim().Trim('"')
}
function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}
function Get-Version($command, $arguments) {
    try { $out = & $command $arguments 2>&1 | Out-String; if ($out -match "(\d+)\.(\d+)") { return [version]"$($Matches[1]).$($Matches[2])" } } catch {}
    return $null
}
function Ensure-Tool($name, $command, $arguments, $minimum, $wingetId, $downloadUrl) {
    $version = if (Get-Command $command -ErrorAction SilentlyContinue) { Get-Version $command $arguments } else { $null }
    if ($version -and $version -ge $minimum) { Say "  $name $version - OK" "Green"; return }
    if ($version) { Say "  $name $version is too old (Froja needs $minimum or newer)." "Yellow" } else { Say "  $name is not installed." "Yellow" }
    $canWinget = (Get-Command winget -ErrorAction SilentlyContinue) -and $env:FROJA_SKIP_PACKAGES -ne "1"
    if ($canWinget -and (Ask-YesNo "  Install $name now? (it is free; Windows may ask for permission)")) {
        winget install --id $wingetId -e --accept-package-agreements --accept-source-agreements
        Refresh-Path
        $version = if (Get-Command $command -ErrorAction SilentlyContinue) { Get-Version $command $arguments } else { $null }
        if ($version -and $version -ge $minimum) { Say "  $name $version installed - OK" "Green"; return }
    }
    Say "  Please install $name from $downloadUrl and run this installer again." "Yellow"
    if (-not $Yes) { Start-Process $downloadUrl }
    throw "$name is needed to continue."
}

Clear-Host
Say "==================================================" "Cyan"
Say "            Froja Image Studio - Installer" "Cyan"
Say "==================================================" "Cyan"
Say "Froja is a free, local image studio for ComfyUI and Ollama."
Say "This installer downloads Froja, prepares it and adds a desktop shortcut."
Say "It asks before installing anything else. Your models are never copied."

try {
    # 1) where -----------------------------------------------------------
    Step 1 "Where should Froja live?"
    $defaultDir = if ($env:FROJA_INSTALL_DIR) { $env:FROJA_INSTALL_DIR } else { Join-Path $env:USERPROFILE "Froja Image Studio" }
    $target = Ask-Text "  Folder for Froja" $defaultDir
    $target = [IO.Path]::GetFullPath($target)
    Say "  Froja will be installed in: $target"

    # 2) tools -----------------------------------------------------------
    Step 2 "Checking the tools Froja needs"
    Ensure-Tool "Node.js" "node" "--version" ([version]"22.0") "OpenJS.NodeJS.LTS" "https://nodejs.org/"
    Ensure-Tool "Python" "python" "--version" ([version]"3.10") "Python.Python.3.11" "https://www.python.org/downloads/"

    # 3) download ---------------------------------------------------------
    Step 3 "Downloading Froja"
    $work = Join-Path $env:TEMP ("froja-install-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Force $work | Out-Null
    $zip = Join-Path $work "froja.zip"
    if ($env:FROJA_SOURCE_ZIP) {
        if ($env:FROJA_SOURCE_ZIP -match "^https?://") { Invoke-WebRequest -UseBasicParsing $env:FROJA_SOURCE_ZIP -OutFile $zip } else { Copy-Item $env:FROJA_SOURCE_ZIP $zip }
        $tag = "custom"
    } else {
        $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ "User-Agent" = "Froja-Installer" }
        $tag = $release.tag_name
        Say "  Latest Froja: $tag"
        Invoke-WebRequest -UseBasicParsing "https://github.com/$Repo/archive/refs/tags/$tag.zip" -OutFile $zip
    }
    Expand-Archive $zip -DestinationPath (Join-Path $work "x") -Force
    $source = Get-ChildItem (Join-Path $work "x") -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force $target | Out-Null
    # keep the user's own settings when updating
    $keep = Join-Path $target "config\config.local.json"
    $kept = if (Test-Path $keep) { Get-Content -Raw $keep } else { $null }
    Copy-Item -Path (Join-Path $source.FullName "*") -Destination $target -Recurse -Force
    if ($kept) { [IO.File]::WriteAllText($keep, $kept, (New-Object System.Text.UTF8Encoding($false))); Say "  Your existing settings were kept." }
    Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
    Say "  Froja $tag copied." "Green"

    # 4) prepare ----------------------------------------------------------
    Step 4 "Preparing Froja (this takes a few minutes the first time)"
    Push-Location $target
    try {
        if (-not (Test-Path ".venv\Scripts\python.exe")) { python -m venv .venv }
        & ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
        & ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "Python packages could not be installed." }
        npm install --no-audit --no-fund --loglevel=error
        if ($LASTEXITCODE -ne 0) { throw "Froja's interface packages could not be installed." }
        npm run build --silent
        if ($LASTEXITCODE -ne 0) { throw "Froja's interface could not be built." }
    } finally { Pop-Location }
    Say "  Froja is prepared." "Green"

    # 5) ComfyUI ----------------------------------------------------------
    Step 5 "Connecting ComfyUI (the image engine)"
    $configPath = Join-Path $target "config\config.local.json"
    if (Test-Path $configPath) {
        Say "  Froja already has settings - nothing to change."
    } else {
        $config = Get-Content -Raw (Join-Path $target "config\config.example.json") | ConvertFrom-Json
        $comfy = if ($env:FROJA_COMFY_DIR) { $env:FROJA_COMFY_DIR } elseif ($Yes) { "" } else {
            Say "  Froja makes pictures with ComfyUI. If you have it, paste its folder (the one with main.py)."
            Read-Host "  ComfyUI folder (or press Enter to skip for now)"
        }
        $comfy = "$comfy".Trim().Trim('"')
        if ($comfy -and (Test-Path (Join-Path $comfy "ComfyUI\main.py"))) { $comfy = Join-Path $comfy "ComfyUI" }  # portable package
        if ($comfy -and (Test-Path (Join-Path $comfy "main.py"))) {
            $root = (Resolve-Path $comfy).Path -replace "\\", "/"
            $python = @((Join-Path $comfy ".venv\Scripts\python.exe"), (Join-Path $comfy "venv\Scripts\python.exe"), (Join-Path (Split-Path $comfy -Parent) "python_embeded\python.exe")) | Where-Object { Test-Path $_ } | Select-Object -First 1
            $config.comfy_root = $root
            if ($python) { $config | Add-Member -NotePropertyName comfy_python -NotePropertyValue (($python) -replace "\\", "/") -Force }
            $config.extra_model_paths_config = "$root/extra_model_paths.yaml"
            $config.model_roots.checkpoints = @("$root/models/checkpoints")
            $config.model_roots.loras = @("$root/models/loras")
            $config.model_roots.vae = @("$root/models/vae")
            $config.model_roots.embeddings = @("$root/models/embeddings")
            $config.diffusion_models_root = "$root/models/diffusion_models"
            Say "  ComfyUI found: $root" "Green"
            if ($python) { Say "  ComfyUI's Python: $python" "Green" } else { Say "  ComfyUI's Python was not found; Froja will use its own." "Yellow" }
        } else {
            Say "  ComfyUI skipped. Froja opens anyway; to make pictures, install ComfyUI from" "Yellow"
            Say "  https://www.comfy.org/download  and put its folder in config\config.local.json (comfy_root)." "Yellow"
        }
        [IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))  # no BOM: Python reads it cleanly
        Say "  Settings saved: $configPath"
    }

    # 6) Ollama (optional) ------------------------------------------------
    Step 6 "Ollama for prompt help and Image to Prompt (optional)"
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue) -or (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")
    if ($ollama) { Say "  Ollama is installed - OK" "Green" }
    elseif ((Get-Command winget -ErrorAction SilentlyContinue) -and $env:FROJA_SKIP_PACKAGES -ne "1" -and (Ask-YesNo "  Install Ollama now? (free; you can also skip it)" $false)) {
        winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
        Say "  After it starts, get the models Froja uses:  ollama pull qwen3.5:4b   and   ollama pull qwen3-vl:4b"
    } else { Say "  Skipped. You can install it later from https://ollama.com/" }

    # 7) shortcut ---------------------------------------------------------
    Step 7 "Desktop shortcut"
    if ($env:FROJA_NO_SHORTCUT -ne "1" -and (Ask-YesNo "  Add 'Froja Image Studio' to your desktop and Start menu?")) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $target "INSTALL_SHORTCUTS.ps1")
    } else { Say "  Skipped. Start Froja any time with START_FROJA.bat in $target" }

    Say ""
    Say "==================================================" "Green"
    Say "  Froja is installed!  Folder: $target" "Green"
    Say "==================================================" "Green"
    if ($env:FROJA_NO_START -ne "1" -and (Ask-YesNo "Start Froja now?")) {
        Start-Process "wscript.exe" -ArgumentList ('"' + (Join-Path $target "LAUNCH_FROJA.vbs") + '"')
    }
    exit 0
} catch {
    Say ""
    Say "Sorry - the installation stopped: $($_.Exception.Message)" "Red"
    Say "Nothing on your computer was damaged. Fix the point above and run the installer again." "Red"
    exit 1
}
