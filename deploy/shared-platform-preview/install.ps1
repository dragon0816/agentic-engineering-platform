param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-zA-Z_][a-zA-Z0-9_.-]*$')][string]$Administrator,
    [string]$PythonExe = "python",
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\shared-platform-preview-0.1.0"
)
$ErrorActionPreference = "Stop"
$BundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ManifestPath = Join-Path $BundleRoot "manifest.json"
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json

foreach ($File in $Manifest.files) {
    $Relative = $File.path.Replace('/', [IO.Path]::DirectorySeparatorChar)
    $Path = Join-Path $BundleRoot $Relative
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Bundle file is missing: $Relative"
    }
    $Actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $File.sha256) { throw "Bundle integrity check failed: $Relative" }
}

$Version = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($LASTEXITCODE -ne 0 -or $Version -ne $Manifest.python_minor) {
    throw "This bundle requires 64-bit Python $($Manifest.python_minor)."
}
$Architecture = (& $PythonExe -c "import platform; print(platform.machine().lower())").Trim()
if ($LASTEXITCODE -ne 0 -or $Architecture -notin @("amd64", "x86_64")) {
    throw "This bundle requires 64-bit x86 Windows Python."
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$Workspace = Join-Path $InstallRoot "workspace"
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
$Venv = Join-Path $InstallRoot ".venv"
if (-not (Test-Path -LiteralPath (Join-Path $Venv "Scripts\python.exe"))) {
    & $PythonExe -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Shared Platform virtual environment." }
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$PlatformWheels = @(Get-ChildItem -LiteralPath (Join-Path $BundleRoot "wheels") -Filter "agentic_engineering_platform-*.whl")
if ($PlatformWheels.Count -ne 1) { throw "Bundle must contain exactly one platform wheel." }
& $VenvPython -m pip install --disable-pip-version-check --no-index --find-links (Join-Path $BundleRoot "wheels") --force-reinstall agentic-engineering-platform
if ($LASTEXITCODE -ne 0) { throw "Offline wheel installation failed." }
# This is the Shared Platform role. Do not expose the Personal Agent, Bridge or
# local coding-worker launchers from this installation.
Get-ChildItem -LiteralPath (Join-Path $Venv "Scripts") -Filter "aep-host*" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -LiteralPath (Join-Path $Venv "Scripts") -Filter "aep-local-codex-worker*" -ErrorAction SilentlyContinue | Remove-Item -Force
$PlatformExecutable = Join-Path $Venv "Scripts\aep-platform.exe"
& $PlatformExecutable --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "The installed runtime does not contain aep-platform." }
Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $InstallRoot "bundle-manifest.json") -Force

$ConfigPath = Join-Path $InstallRoot "platform.json"
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    $Config = [ordered]@{
        schema_version = "1"
        administrators = @($Administrator)
        listen_host = "127.0.0.1"
        control_port = 8765
        member_port = 8766
        registry_path = (Join-Path $Workspace "registry.sqlite")
        invitations = @()
    }
    $Config | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
}
else {
    Write-Host "Kept existing platform.json."
}
& $VenvPython -c "import sys; from pathlib import Path; from control_plane.app import SharedPlatformConfiguration; SharedPlatformConfiguration.model_validate_json(Path(sys.argv[1]).read_text(encoding='utf-8-sig')); print('shared platform configuration: valid')" $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "Shared Platform configuration validation failed." }
Write-Host "Installed the Shared Platform preview at $InstallRoot"
Write-Host "Bundle source revision: $($Manifest.source_revision)"
Write-Host "The default listener is loopback only. Read START-HERE.md before exposing it to another computer."
