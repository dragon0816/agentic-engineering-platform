param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-zA-Z_][a-zA-Z0-9_.-]*$')][string]$Actor,
    [string]$BridgeId,
    [ValidatePattern('^[a-z0-9]+(-[a-z0-9]+)*$')][string]$Namespace,
    [string]$PythonExe = "python",
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0"
)
$ErrorActionPreference = "Stop"
$BundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manifest = Get-Content -LiteralPath (Join-Path $BundleRoot "manifest.json") -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($BridgeId)) {
    $NormalizedComputerName = [Environment]::MachineName.ToLowerInvariant() -replace '[^a-z0-9_.-]', '-'
    $NormalizedComputerName = $NormalizedComputerName.Trim([char[]]"-.")
    if ([string]::IsNullOrWhiteSpace($NormalizedComputerName)) {
        throw "Could not derive a Bridge ID from the Windows computer name."
    }
    $BridgeId = "bridge-$NormalizedComputerName"
    Write-Host "Using Bridge ID $BridgeId derived from this computer name."
}
if ($BridgeId -notmatch '^[a-zA-Z_][a-zA-Z0-9_.-]*$') {
    throw "BridgeId must contain only letters, numbers, underscore, dot or hyphen."
}

foreach ($File in $Manifest.files) {
    $Relative = $File.path.Replace('/', [IO.Path]::DirectorySeparatorChar)
    $Path = Join-Path $BundleRoot $Relative
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Bundle file is missing: $Relative"
    }
    $Actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $File.sha256) {
        throw "Bundle integrity check failed: $Relative"
    }
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
# The layout the resident Agent reads. The directories are created empty:
# this package installs no Skill, Workflow or grant, and says so.
New-Item -ItemType Directory -Force -Path (Join-Path $Workspace "assets\skills") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Workspace "assets\workflows") | Out-Null
$Venv = Join-Path $InstallRoot ".venv"
if (-not (Test-Path -LiteralPath (Join-Path $Venv "Scripts\python.exe"))) {
    & $PythonExe -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the preview virtual environment." }
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$PlatformWheels = @(Get-ChildItem -LiteralPath (Join-Path $BundleRoot "wheels") -Filter "agentic_engineering_platform-*.whl")
if ($PlatformWheels.Count -ne 1) { throw "Bundle must contain exactly one platform wheel." }
$PlatformWheel = $PlatformWheels[0]
# By name with its extras, resolved entirely from the bundle's own wheels:
# the extras the bundle carries are reading the weekly workbook (openpyxl)
# and writing it through Excel (pywin32). Extras appended to a wheel *path*
# read to pip as part of the filename, so the requirement form is used and
# the check above is what guarantees the directory holds exactly one build.
# Still --no-index, so a missing wheel fails here rather than reaching for a
# package index.
& $VenvPython -m pip install --disable-pip-version-check --no-index --find-links (Join-Path $BundleRoot "wheels") --force-reinstall "agentic-engineering-platform[excel,windows]"
if ($LASTEXITCODE -ne 0) { throw "Offline wheel installation failed." }

$Config = [ordered]@{
    schema_version = "1"
    device = [ordered]@{
        bridge_id = $BridgeId
        registered_by = $Actor
        device_kind = "company_workstation"
        windows_account_mode = "dedicated_user"
        resource_scope = "corporate_internal"
        local_isolation = "single_user"
        interactive_slots = 1
        status = "active"
    }
    workspace_root = $Workspace
}
if (-not [string]::IsNullOrWhiteSpace($Namespace)) {
    $Config.namespace = $Namespace
}
$Config | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $InstallRoot "host.json") -Encoding UTF8
& (Join-Path $Venv "Scripts\aep-host.exe") doctor --config (Join-Path $InstallRoot "host.json")
if ($LASTEXITCODE -ne 0) { throw "Host doctor failed." }
Write-Host "Installed the local-only preview at $InstallRoot"
Write-Host "The resident Agent is pending: it runs once $Workspace\membership.json names who may use this Bridge."
