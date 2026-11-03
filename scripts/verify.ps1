$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $repositoryRoot "backend\.venv\Scripts\python.exe"
$frontendModules = Join-Path $repositoryRoot "frontend\node_modules"
$desktopPython = Join-Path $repositoryRoot "desktop\.venv\Scripts\python.exe"

$ranAnySuite = $false

if (Test-Path -LiteralPath $backendPython) {
    $ranAnySuite = $true
    Push-Location (Join-Path $repositoryRoot "backend")
    try {
        & $backendPython -m pytest
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "SKIP backend: backend/.venv is not installed"
}

if (Test-Path -LiteralPath $frontendModules) {
    $ranAnySuite = $true
    Push-Location (Join-Path $repositoryRoot "frontend")
    try {
        & npm test -- --run
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "SKIP frontend: frontend/node_modules is not installed"
}

if (Test-Path -LiteralPath $desktopPython) {
    $ranAnySuite = $true
    Push-Location (Join-Path $repositoryRoot "desktop")
    try {
        & $desktopPython -m pytest
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "SKIP desktop: desktop/.venv is not installed"
}

if (-not $ranAnySuite) {
    Write-Host "No suites ran; install project prerequisites first."
}
