param(
  [string]$Version = "dev",
  [string]$PythonExecutable = "",
  [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $true
}
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $PythonExecutable) {
  $PythonExecutable = (py -c "import sys; print(sys.executable)").Trim()
}
if (-not $SkipDependencyInstall) {
  & $PythonExecutable -m pip install -e ".[build]"
  if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}

$Name = "OpenMenuGDEMUManager"
$DistRoot = Join-Path $Root "dist"
$PortableRoot = Join-Path $DistRoot "$Name-Portable"
$Icon = Join-Path $Root "src\openmenu_gdemu_manager\resources\app\app_icon.ico"
$Launcher = Join-Path $Root "scripts\portable_launcher.py"

if (Test-Path -LiteralPath $PortableRoot) {
  $ResolvedDistRoot = [IO.Path]::GetFullPath($DistRoot)
  $ResolvedPortableRoot = (Resolve-Path -LiteralPath $PortableRoot).Path
  $ExpectedPortableRoot = [IO.Path]::GetFullPath((Join-Path $ResolvedDistRoot "$Name-Portable"))
  if ($ResolvedPortableRoot -ne $ExpectedPortableRoot -or
      -not $ResolvedPortableRoot.StartsWith($ResolvedDistRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Portable cleanup target is outside the expected dist directory."
  }
  Remove-Item -LiteralPath $PortableRoot -Recurse -Force
}

$OriginalPath = $env:PATH
$PythonDirectory = Split-Path -Parent $PythonExecutable
# Unrelated tools on PATH can provide incompatible DLLs with system names
# (for example Poppler's icuuc.dll instead of the Windows ICU used by Qt).
$env:PATH = @(
  $PythonDirectory
  (Join-Path $PythonDirectory "Scripts")
  (Join-Path $env:SystemRoot "System32")
  $env:SystemRoot
) -join [IO.Path]::PathSeparator
try {
  & $PythonExecutable -m PyInstaller `
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
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
  }
}
finally {
  $env:PATH = $OriginalPath
}

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
