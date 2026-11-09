param(
    [string]$PythonPath = $env:BLUEFRAME_PYTHON311,
    [string]$ResourceSource = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) { throw "Set BLUEFRAME_PYTHON311 to a Python 3.11 x64 executable." }
$Version = & $PythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($Version -ne "3.11") { throw "Offline build requires Python 3.11; found $Version." }
Push-Location (Join-Path $Repo "frontend")
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally { Pop-Location }
$BuildVenv = Join-Path $Repo ".build\py311"
if (-not (Test-Path -LiteralPath (Join-Path $BuildVenv "Scripts\python.exe"))) { & $PythonPath -m venv $BuildVenv }
$BuildPython = Join-Path $BuildVenv "Scripts\python.exe"
& $BuildPython -m pip install --disable-pip-version-check --upgrade pip PyInstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed." }
& $BuildPython -m pip install --disable-pip-version-check -e (Join-Path $Repo "backend") -e (Join-Path $Repo "desktop")
if ($LASTEXITCODE -ne 0) { throw "BlueFrame build dependency installation failed." }
& $BuildPython -m pip install --disable-pip-version-check "funasr==1.0.25" "numpy==1.26.4" "torch==2.3.0" "torchaudio==2.3.0"
if ($LASTEXITCODE -ne 0) { throw "Offline ASR runtime installation failed." }
& $BuildPython (Join-Path $Repo "packaging\prepare_resources.py") --source-root $ResourceSource --output (Join-Path $Repo "packaging\generated\resource-manifest.json")
if ($LASTEXITCODE -ne 0) { throw "Resource manifest generation failed." }
$env:BLUEFRAME_RESOURCE_SOURCE = (Resolve-Path -LiteralPath $ResourceSource).Path
& $BuildPython -m PyInstaller --noconfirm --clean --distpath (Join-Path $Repo "dist") --workpath (Join-Path $Repo ".build\pyinstaller") (Join-Path $Repo "packaging\blueframe-studio.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
& (Join-Path $Repo "scripts\verify-package.ps1") -PackageDir (Join-Path $Repo "dist\BlueFrameStudio")
$Zip = Join-Path $Repo "dist\BlueFrameStudio-Windows-x64.zip"
if (Test-Path -LiteralPath $Zip) { Remove-Item -LiteralPath $Zip }
Compress-Archive -Path (Join-Path $Repo "dist\BlueFrameStudio\*") -DestinationPath $Zip -CompressionLevel Optimal
Write-Host "Built $Zip"
