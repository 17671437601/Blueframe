param([Parameter(Mandatory=$true)][string]$PackageDir)
$ErrorActionPreference = "Stop"
$Resolved = (Resolve-Path -LiteralPath $PackageDir).Path
$Manifest = Join-Path $Resolved "_internal\resource-manifest.json"
if (-not (Test-Path -LiteralPath $Manifest)) { $Manifest = Join-Path $Resolved "resource-manifest.json" }
if (-not (Test-Path -LiteralPath $Manifest)) { throw "resource-manifest.json is missing from package." }
$Executable = Join-Path $Resolved "BlueFrameStudio.exe"
if (-not (Test-Path -LiteralPath $Executable)) { throw "BlueFrameStudio.exe is missing." }
# The packaged launcher is a windowed (console=False) process, so callers must
# wait on the process handle instead of relying on $LASTEXITCODE.
$Smoke = Start-Process -FilePath $Executable -ArgumentList "--smoke" -Wait -PassThru
if ($Smoke.ExitCode -ne 0) { throw "Packaged --smoke verification failed with exit code $($Smoke.ExitCode)." }
Write-Host "Package verification passed: $Resolved"
