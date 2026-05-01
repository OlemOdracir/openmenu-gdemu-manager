param(
  [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

py -m pip install -e ".[build]"

$Name = "OpenMenuGDEMUManager"
$DistRoot = Join-Path $Root "dist"
$PortableRoot = Join-Path $DistRoot "$Name-Portable"
$Icon = Join-Path $Root "src\openmenu_gdemu_manager\resources\app\app_icon.ico"
$Launcher = Join-Path $Root "scripts\portable_launcher.py"

if (Test-Path -LiteralPath $PortableRoot) {
  Remove-Item -LiteralPath $PortableRoot -Recurse -Force
}

py -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name $Name `
  --icon $Icon `
  --paths "src" `
  --add-data "src\openmenu_gdemu_manager\resources;openmenu_gdemu_manager\resources" `
  --distpath $DistRoot `
  --workpath (Join-Path $Root "build\pyinstaller") `
  $Launcher

Move-Item -LiteralPath (Join-Path $DistRoot $Name) -Destination $PortableRoot

@"
@echo off
set "OPENMENU_GDEMU_MANAGER_HOME=%~dp0data"
set "OPENMENU_GDEMU_MANAGER_DOCUMENTS=%~dp0data\Documents"
start "" "%~dp0$Name.exe"
"@ | Set-Content -Path (Join-Path $PortableRoot "Run-Portable.cmd") -Encoding ASCII

@"
OpenMenu GDEMU Manager Portable
Version: $Version

Run Run-Portable.cmd to keep settings, logs and cache inside this folder.
The app checks GitHub releases on startup and opens the release page when an update is available.
"@ | Set-Content -Path (Join-Path $PortableRoot "README-PORTABLE.txt") -Encoding UTF8

Compress-Archive -Path (Join-Path $PortableRoot "*") -DestinationPath (Join-Path $DistRoot "$Name-$Version-portable-windows.zip") -Force
Write-Host "Portable package created in dist."
