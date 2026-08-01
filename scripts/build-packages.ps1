$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

npm ci
npm run build
npm test

$release = Join-Path $root "release"
$stage = Join-Path $release "Froja-Image-Studio"
if (Test-Path -LiteralPath $stage) {
  $expected = [IO.Path]::GetFullPath((Join-Path $root "release\Froja-Image-Studio"))
  if ([IO.Path]::GetFullPath($stage) -ne $expected) { throw "Unexpected release staging path." }
  Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Path $stage -Force | Out-Null

$archive = Join-Path $release "source.zip"
git archive --format=zip --output=$archive HEAD
Expand-Archive -LiteralPath $archive -DestinationPath $stage -Force
Remove-Item -LiteralPath $archive
Copy-Item -LiteralPath "dist" -Destination (Join-Path $stage "dist") -Recurse

foreach ($folder in "checkpoints", "loras", "vae", "embeddings", "diffusion_models", "text_encoders", "controlnet") {
  New-Item -ItemType Directory -Path (Join-Path $stage "models\$folder") -Force | Out-Null
}

$windowsZip = Join-Path $release "Froja-Image-Studio-Windows.zip"
if (Test-Path $windowsZip) { Remove-Item -LiteralPath $windowsZip }
Compress-Archive -Path $stage -DestinationPath $windowsZip -CompressionLevel Optimal

$linuxArchive = Join-Path $release "Froja-Image-Studio-Linux.tar.gz"
if (Test-Path $linuxArchive) { Remove-Item -LiteralPath $linuxArchive }
tar -czf $linuxArchive -C $release "Froja-Image-Studio"

Write-Host "Created $windowsZip"
Write-Host "Created $linuxArchive"
