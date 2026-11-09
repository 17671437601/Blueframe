param(
    [Parameter(Mandatory = $true)][string]$PackageDir,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\BlueFrameStudio"),
    [ValidateSet("app", "models", "third-party", "full")][string[]]$Components = @("full"),
    [switch]$Uninstall,
    [switch]$NoShortcut,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$PackageRoot = (Resolve-Path -LiteralPath $PackageDir).Path
$Internal = Join-Path $PackageRoot "_internal"
$ManifestPath = Join-Path $Internal "resource-manifest.json"
$Executable = Join-Path $PackageRoot "BlueFrameStudio.exe"
$MarkerPath = Join-Path $InstallDir ".blueframe-install.json"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Programs")) "BlueFrame Studio.lnk"

function Copy-Tree {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludeDirectories = @()
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $arguments = @($Source, $Destination, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/R:2", "/W:2")
    foreach ($directory in $ExcludeDirectories) {
        $arguments += @("/XD", (Join-Path $Source $directory))
    }
    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Copy failed from $Source to $Destination (robocopy exit code $LASTEXITCODE)"
    }
}

if ($Uninstall) {
    if (-not (Test-Path -LiteralPath $MarkerPath)) {
        throw "Refusing to uninstall: $MarkerPath is missing, so this directory was not installed by BlueFrame Studio."
    }
    if (Test-Path -LiteralPath $InstallDir) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $ShortcutPath) {
        Remove-Item -LiteralPath $ShortcutPath -Force
    }
    Write-Host "Uninstalled BlueFrame Studio from $InstallDir"
    exit 0
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "resource-manifest.json is missing from $Internal"
}
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "BlueFrameStudio.exe is missing from $PackageRoot"
}

$Selected = @(
    $Components | ForEach-Object {
        if ($_ -eq "full") { "app", "models", "third-party" } else { $_ }
    } | Select-Object -Unique
)
if ($Selected -notcontains "app") {
    throw "The app component is required; add 'app' to -Components."
}

$ManifestHash = (Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash
if (Test-Path -LiteralPath $MarkerPath) {
    try {
        $Existing = Get-Content -LiteralPath $MarkerPath -Raw | ConvertFrom-Json
    }
    catch {
        $Existing = $null
    }
    if (
        $null -ne $Existing -and
        $Existing.package_manifest_sha256 -eq $ManifestHash -and
        ((@($Existing.components) -join ",") -eq ($Selected -join ","))
    ) {
        Write-Host "BlueFrame Studio is already installed in $InstallDir"
        exit 0
    }
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -LiteralPath $Executable -Destination (Join-Path $InstallDir "BlueFrameStudio.exe") -Force
Copy-Tree -Source $Internal -Destination (Join-Path $InstallDir "_internal") -ExcludeDirectories @("models", "third-party")
if ($Selected -contains "models") {
    Copy-Tree -Source (Join-Path $Internal "models") -Destination (Join-Path $InstallDir "_internal\models")
}
if ($Selected -contains "third-party") {
    Copy-Tree -Source (Join-Path $Internal "third-party") -Destination (Join-Path $InstallDir "_internal\third-party")
}

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
foreach ($entry in $Manifest.files.PSObject.Properties) {
    $relative = $entry.Name
    if ($relative.StartsWith("models/")) { $component = "models" }
    elseif ($relative.StartsWith("third-party/")) { $component = "third-party" }
    else { $component = "app" }
    if ($Selected -notcontains $component) { continue }
    $target = Join-Path (Join-Path $InstallDir "_internal") ($relative.Replace("/", "\"))
    if (-not (Test-Path -LiteralPath $target)) {
        throw "Installed resource is missing: $relative"
    }
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    if ($actual -ne ([string]$entry.Value).ToUpperInvariant()) {
        throw "Installed resource hash mismatch: $relative"
    }
}

$Marker = [ordered]@{
    package_manifest_sha256 = $ManifestHash
    components              = $Selected
    installed_at            = (Get-Date).ToUniversalTime().ToString("o")
}
$Marker | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $MarkerPath -Encoding UTF8

if (-not $NoShortcut) {
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Join-Path $InstallDir "BlueFrameStudio.exe"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "BlueFrame Studio"
    $Shortcut.Save()
}

if (-not $SkipSmoke) {
    $Smoke = Start-Process -FilePath (Join-Path $InstallDir "BlueFrameStudio.exe") -ArgumentList "--smoke" -Wait -PassThru
    if ($Smoke.ExitCode -ne 0) {
        throw "Installed application smoke check failed with exit code $($Smoke.ExitCode)."
    }
}

Write-Host "Installed BlueFrame Studio to $InstallDir ($($Selected -join ', '))"
