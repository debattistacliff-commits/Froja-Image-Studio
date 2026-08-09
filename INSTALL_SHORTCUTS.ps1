$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $project "LAUNCH_FROJA.vbs"
$icon = Join-Path $project "assets\froja.ico"
$wscript = Join-Path $env:WINDIR "System32\wscript.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
$destinations = @(
    (Join-Path $desktop "Froja Image Studio.lnk"),
    (Join-Path $programs "Froja Image Studio.lnk")
)

$shell = New-Object -ComObject WScript.Shell
foreach ($destination in $destinations) {
    $shortcut = $shell.CreateShortcut($destination)
    $shortcut.TargetPath = $wscript
    $shortcut.Arguments = '"' + $launcher + '"'
    $shortcut.WorkingDirectory = $project
    $shortcut.IconLocation = $icon + ",0"
    $shortcut.Description = "Launch Froja Image Studio"
    $shortcut.Save()
    Write-Host "Installed: $destination"
}
