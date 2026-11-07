$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$desktopPython = Join-Path $repositoryRoot "desktop\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $desktopPython)) {
    throw "Desktop environment is missing."
}

Push-Location $repositoryRoot
try {
    & $desktopPython -m blueframe_desktop.smoke
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
