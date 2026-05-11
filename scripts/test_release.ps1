param(
  [string]$Version = "dev",
  [switch]$Integration
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $true
}

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

py -m pytest

if ($Integration) {
  $env:OPENMENU_RUN_INTEGRATION = "1"
  py -m pytest -m integration
  Remove-Item Env:\OPENMENU_RUN_INTEGRATION -ErrorAction SilentlyContinue
}

.\scripts\build_portable.ps1 -Version $Version

$Name = "OpenMenuGDEMUManager"
$DistRoot = Join-Path $Root "dist"
$PortableRoot = Join-Path $DistRoot "$Name-Portable"
$ZipPath = Join-Path $DistRoot "$Name-$Version-portable-windows.zip"
$ChecksumPath = "$ZipPath.sha256.txt"

$requiredFiles = @(
  (Join-Path $PortableRoot "$Name.exe"),
  (Join-Path $PortableRoot "README-PORTABLE.txt"),
  (Join-Path $PortableRoot "LICENSE.txt"),
  (Join-Path $PortableRoot "THIRD_PARTY_NOTICES.md"),
  (Join-Path $PortableRoot "_internal\third_party\buildgdi\buildgdi.exe"),
  (Join-Path $PortableRoot "_internal\third_party\buildgdi\LICENSE-DiscUtilsGD.txt"),
  (Join-Path $PortableRoot "_internal\third_party\buildgdi\SHA256SUMS.txt"),
  $ZipPath,
  $ChecksumPath
)

foreach ($path in $requiredFiles) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Missing release artifact: $path"
  }
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  $entries = @($zip.Entries | ForEach-Object { $_.FullName.Replace('\', '/') })
  foreach ($entry in @(
    "$Name.exe",
    "README-PORTABLE.txt",
    "LICENSE.txt",
    "THIRD_PARTY_NOTICES.md",
    "_internal/third_party/buildgdi/buildgdi.exe",
    "_internal/third_party/buildgdi/LICENSE-DiscUtilsGD.txt",
    "_internal/third_party/buildgdi/SHA256SUMS.txt"
  )) {
    if ($entries -notcontains $entry) {
      throw "ZIP is missing required entry: $entry"
    }
  }
  if ($entries -contains "Run-Portable.cmd") {
    throw "ZIP must not include Run-Portable.cmd. Users should launch $Name.exe directly."
  }
}
finally {
  $zip.Dispose()
}

$data = Join-Path $PortableRoot "data"
if (Test-Path -LiteralPath $data) {
  Remove-Item -LiteralPath $data -Recurse -Force
}

$exe = Join-Path $PortableRoot "$Name.exe"
$process = Start-Process -FilePath $exe -WorkingDirectory $PortableRoot -PassThru
Start-Sleep -Seconds 5
$started = -not $process.HasExited
if ($started) {
  $null = $process.CloseMainWindow()
  Start-Sleep -Seconds 2
  if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
}

if (-not $started) {
  throw "$Name.exe exited during smoke test with code $($process.ExitCode)."
}
if (-not (Test-Path -LiteralPath $data)) {
  throw "$Name.exe did not create portable data folder."
}

Write-Host "Release validation passed."
Write-Host (Get-Content $ChecksumPath)
