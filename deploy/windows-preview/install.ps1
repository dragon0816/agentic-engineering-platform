param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-zA-Z_][a-zA-Z0-9_.-]*$')][string]$Actor,
    [string]$BridgeId,
    [ValidatePattern('^[a-z0-9]+(-[a-z0-9]+)*$')][string]$Namespace,
    [string]$PythonExe = "python",
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0"
)
$ErrorActionPreference = "Stop"
$BundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ManifestPath = Join-Path $BundleRoot "manifest.json"
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json

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

# Windows refuses a path of 260 characters or more unless long paths have
# been enabled, and Explorer extracts what fits and silently leaves out the
# rest. That arrives here as a missing bundle file, which reads as a broken
# download and sends the reader looking in the wrong place. Measure first, so
# the installer names the real cause and the fix.
$Longest = ($Manifest.files | ForEach-Object {
        (Join-Path $BundleRoot $_.path.Replace('/', [IO.Path]::DirectorySeparatorChar)).Length
    } | Measure-Object -Maximum).Maximum
if ($Longest -ge 260) {
    throw ("This bundle sits too deep for Windows: one of its files needs a path of " +
        "$Longest characters and Windows allows 259. Move or re-extract the bundle " +
        "somewhere shorter, such as C:\aep, and run install.cmd again. Nothing is wrong " +
        "with the download.")
}

foreach ($File in $Manifest.files) {
    $Relative = $File.path.Replace('/', [IO.Path]::DirectorySeparatorChar)
    $Path = Join-Path $BundleRoot $Relative
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw ("Bundle file is missing: $Relative. Extract the whole zip again, keeping " +
            "every file; an extraction that skipped one leaves the bundle unusable.")
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
$HostExecutable = Join-Path $Venv "Scripts\aep-host.exe"
# All preview packages currently report semantic version 0.1.0. Verify a
# capability introduced by this build so an older 0.1.0 runtime can never look
# like a successful update, then retain the exact source revision for support.
& $HostExecutable dut-validate --help | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "The installed runtime does not match bundle revision $($Manifest.source_revision): dut-validate is missing."
}
Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $InstallRoot "bundle-manifest.json") -Force

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
# Keep what the operator added. The installer owns the device identity and
# the workspace path and writes those afresh, but everything else in this
# file was typed by hand: the Jira or project source, the workbook, which
# environment variable holds which secret, the shared platform. Overwriting
# it on an update loses all of that silently, and the run afterwards fails
# for a reason that looks nothing like the cause.
$ConfigPath = Join-Path $InstallRoot "host.json"
if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    try {
        $Existing = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    }
    catch {
        throw ("There is a host.json at $ConfigPath that cannot be read: $($_.Exception.Message). " +
            "Move it aside and run install.cmd again; everything in it was typed by hand, so it " +
            "is not overwritten.")
    }
    $Kept = @()
    foreach ($Property in $Existing.PSObject.Properties) {
        if (-not $Config.Contains($Property.Name)) {
            $Config[$Property.Name] = $Property.Value
            $Kept += $Property.Name
        }
    }
    if ($Kept.Count -gt 0) {
        Write-Host ("Kept from the existing host.json: " + ($Kept -join ", "))
    }
}
$Config | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
$Membership = [ordered]@{
    device = $Config.device
    bindings = @([ordered]@{
        bridge_id = $BridgeId
        actor = $Actor
        role = "operator"
    })
}
$MembershipPath = Join-Path $Workspace "membership.json"
$Membership | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $MembershipPath -Encoding UTF8
& $HostExecutable doctor --config (Join-Path $InstallRoot "host.json")
if ($LASTEXITCODE -ne 0) { throw "Host doctor failed." }
Write-Host "Installed the local-only preview at $InstallRoot"
Write-Host "Bundle source revision: $($Manifest.source_revision)"
Write-Host "The resident Agent is bound to $Actor on $BridgeId. Capability grants remain separate."
