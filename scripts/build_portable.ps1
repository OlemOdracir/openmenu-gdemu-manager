param(
  [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $true
}
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
  --add-data "third_party\buildgdi;third_party\buildgdi" `
  --add-data "third_party\openmenu;third_party\openmenu" `
  --distpath $DistRoot `
  --workpath (Join-Path $Root "build\pyinstaller") `
  $Launcher

Move-Item -LiteralPath (Join-Path $DistRoot $Name) -Destination $PortableRoot

@"
OpenMenu GDEMU Manager Portable
Version: $Version

Run OpenMenuGDEMUManager.exe to start the app.
Settings, logs, cache and generated files are kept inside the data folder next to the executable.
The app checks GitHub releases on startup and opens the release page when an update is available.
"@ | Set-Content -Path (Join-Path $PortableRoot "README-PORTABLE.txt") -Encoding UTF8

Copy-Item -LiteralPath (Join-Path $Root "LICENSE") -Destination (Join-Path $PortableRoot "LICENSE.txt") -Force
Copy-Item -LiteralPath (Join-Path $Root "THIRD_PARTY_NOTICES.md") -Destination (Join-Path $PortableRoot "THIRD_PARTY_NOTICES.md") -Force

$ZipPath = Join-Path $DistRoot "$Name-$Version-portable-windows.zip"
for ($attempt = 1; $attempt -le 3; $attempt++) {
  try {
    Compress-Archive -Path (Join-Path $PortableRoot "*") -DestinationPath $ZipPath -Force -ErrorAction Stop
    break
  }
  catch {
    if ($attempt -eq 3) {
      throw
    }
    Start-Sleep -Seconds 2
  }
}
Get-FileHash $ZipPath -Algorithm SHA256 |
  ForEach-Object { "$($_.Hash)  $(Split-Path -Leaf $ZipPath)" } |
  Set-Content -Path "$ZipPath.sha256.txt" -Encoding ASCII
Write-Host "Portable package created in dist."
