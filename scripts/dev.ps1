$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$desktopPython = Join-Path $repositoryRoot "desktop\.venv\Scripts\python.exe"
$frontendModules = Join-Path $repositoryRoot "frontend\node_modules"

if (-not (Test-Path -LiteralPath $desktopPython)) {
    throw "Desktop environment is missing. Create desktop/.venv and install backend plus desktop first."
}
if (-not (Test-Path -LiteralPath $frontendModules)) {
    throw "Frontend dependencies are missing. Run npm install in frontend first."
}

Push-Location (Join-Path $repositoryRoot "frontend")
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

& $desktopPython -m blueframe_desktop.launcher
exit $LASTEXITCODE
