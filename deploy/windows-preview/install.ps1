param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-zA-Z_][a-zA-Z0-9_.-]*$')][string]$Actor,
    [string]$BridgeId,
    [ValidatePattern('^[a-z0-9]+(-[a-z0-9]+)*$')][string]$Namespace,
    [string]$PythonExe = "python",
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0",
    [switch]$NoShortcut,
    # Leave Claude Code, Codex and Copilot as they are (no AEP skills or MCP servers).
    [switch]$NoAgentSkills,
    # Do not install the built-in LLM gateway (docs/phases/LLM_GATEWAY.md);
    # without a gateway, or another model endpoint, the Agent reaches no model.
    [switch]$NoGateway,
    # Install and configure the gateway but do not renew the token, register
    # the logon start or start it (CI and offline checks, no company sign-in).
    [switch]$GatewayInstallOnly
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
# The layout the resident Agent reads. The bundled Skills are installed at
# the end (install-bundled); this package installs no grant.
New-Item -ItemType Directory -Force -Path (Join-Path $Workspace "assets\skills") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Workspace "assets\workflows") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Workspace "assets\knowledge") | Out-Null
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
# the extras the bundle carries are reading the weekly workbook (openpyxl),
# writing it through Excel (pywin32), and drawing the weekly mail chart.
# Extras appended to a wheel *path*
# read to pip as part of the filename, so the requirement form is used and
# the check above is what guarantees the directory holds exactly one build.
# Still --no-index, so a missing wheel fails here rather than reaching for a
# package index.
& $VenvPython -m pip install --disable-pip-version-check --no-index --find-links (Join-Path $BundleRoot "wheels") --force-reinstall "agentic-engineering-platform[excel,windows,weekly-mail]" "pypdf>=6,<7"
if ($LASTEXITCODE -ne 0) { throw "Offline wheel installation failed." }
# This is the Agent + Bridge role. The wheel contains the shared contracts and
# all project entry points, but this installation exposes only its own runtime.
Get-ChildItem -LiteralPath (Join-Path $Venv "Scripts") -Filter "aep-platform*" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -LiteralPath (Join-Path $Venv "Scripts") -Filter "aep-local-codex-worker*" -ErrorAction SilentlyContinue | Remove-Item -Force
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
$GatewayDefault = Join-Path $BundleRoot "gateway-default.json"
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
# The Natural-language model goes through the built-in gateway, but only when
# this host has no model yet: a model someone configured is theirs, and an
# update never replaces it. The credential mapping is added beside it when
# its name is not mapped already.
if (-not $NoGateway -and -not $Config.Contains("models")) {
    $Fragment = Get-Content -LiteralPath $GatewayDefault -Raw | ConvertFrom-Json
    $Config.models = $Fragment.models
    $Credentials = @()
    if ($Config.Contains("credentials") -and $null -ne $Config.credentials) {
        $Credentials = @($Config.credentials)
    }
    foreach ($Mapping in $Fragment.credentials) {
        if (-not ($Credentials | Where-Object { $_.secret -eq $Mapping.secret })) {
            $Credentials += $Mapping
        }
    }
    $Config.credentials = $Credentials
    Write-Host "Set the Natural-language model to the built-in LLM gateway at 127.0.0.1:4000."
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
if ($NoGateway) {
    Write-Host ("Skipped the LLM gateway (-NoGateway). The Agent reaches a model only " +
        "through another endpoint set in Agent Web Settings > Natural-language model.")
}
else {
    # The built-in LLM gateway (docs/phases/LLM_GATEWAY.md): LiteLLM in its own
    # venv (its pins differ from AEP's), from the bundle's own wheels only.
    $GatewayVenv = Join-Path $InstallRoot "gateway-venv"
    # LiteLLM's deepest file is 129 characters below site-packages; Windows
    # refuses 260 or more unless long paths are enabled, and pip would stop
    # half-way with "The filename or extension is too long".
    $Deepest = (Join-Path $GatewayVenv "Lib\site-packages").Length + 1 + 129
    if ($Deepest -ge 260) {
        throw ("The LLM gateway would need $Deepest-character paths under $GatewayVenv and " +
            "Windows allows 259. Install with a shorter -InstallRoot (for example " +
            "C:\aep\preview), or use -NoGateway.")
    }
    $GatewayPython = Join-Path $GatewayVenv "Scripts\python.exe"
    if (Test-Path -LiteralPath $GatewayPython) {
        # A running gateway holds the files this replaces. Only the one AEP
        # started is stopped; one run outside AEP is left alone.
        & $HostExecutable gateway stop | Out-Null
    }
    else {
        & $PythonExe -m venv $GatewayVenv
        if ($LASTEXITCODE -ne 0) { throw "Could not create the LLM gateway's virtual environment." }
    }
    Write-Host "Installing the LLM gateway (LiteLLM, offline; this takes a few minutes)..."
    & $GatewayPython -m pip install --disable-pip-version-check --no-index --no-deps --find-links (Join-Path $BundleRoot "wheels-gateway") -r (Join-Path $BundleRoot "gateway\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "The LLM gateway could not be installed from the bundle." }
    # The launcher is AEP's own llm_gateway package (standard library only).
    & $GatewayPython -m pip install --disable-pip-version-check --no-index --no-deps --force-reinstall $PlatformWheel.FullName
    if ($LASTEXITCODE -ne 0) { throw "The LLM gateway launcher could not be installed." }
    Get-ChildItem -LiteralPath (Join-Path $GatewayVenv "Scripts") -Filter "aep-*" -ErrorAction SilentlyContinue | Remove-Item -Force
    # Settings and configuration in the user's profile, kept on an update; the
    # local key is generated once and put in the user's environment, where
    # host.json's credential mapping (LITELLM_MASTER_KEY) finds it.
    & $HostExecutable gateway init --python $GatewayPython --user-env
    if ($LASTEXITCODE -ne 0) { throw "The LLM gateway could not be configured." }
    if ([string]::IsNullOrWhiteSpace($env:LITELLM_MASTER_KEY)) {
        $env:LITELLM_MASTER_KEY = [Environment]::GetEnvironmentVariable("LITELLM_MASTER_KEY", "User")
    }
    if ($GatewayInstallOnly) {
        Write-Host "Installed the LLM gateway without starting it (-GatewayInstallOnly)."
    }
    else {
        # The company token, with this Windows sign-in (Kerberos); off the
        # domain this fails and says so, and the gateway waits for a token.
        & $HostExecutable gateway refresh-token
        if ($LASTEXITCODE -ne 0) {
            Write-Warning ("The LLM gateway's token could not be renewed now (company domain " +
                "sign-in needed). Agent Web Settings > LLM gateway > Refresh token, later.")
        }
        & $HostExecutable gateway autostart --on
        if ($LASTEXITCODE -ne 0) { Write-Warning "The LLM gateway will not start at sign-in; see above." }
        & $HostExecutable gateway start
        if ($LASTEXITCODE -ne 0) { Write-Warning "The LLM gateway did not start; see Agent Web Settings > LLM gateway." }
    }
}
& $HostExecutable doctor --config (Join-Path $InstallRoot "host.json")
if ($LASTEXITCODE -ne 0) { throw "Host doctor failed." }
if (-not $NoShortcut) {
    # The 'AEP Agent' desktop and Start menu shortcut opens Agent Web, starting it if needed.
    & $HostExecutable shortcut --config $ConfigPath
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not create the AEP Agent shortcut; use start-web.cmd." }
}
if ($NoAgentSkills) {
    Write-Host "Skipped the coding agent setup (-NoAgentSkills). Set it up later in Agent Web Settings > Coding agents."
}
else {
    # AEP's skills (Workflow and Skill creators, AEP Knowledge) and its two MCP
    # servers for every coding agent found here, in that agent's own user
    # settings; only AEP's entries are touched and edited files are backed up.
    Write-Host "Setting up AEP for the coding agents on this computer (Claude Code, Codex, GitHub Copilot):"
    & $HostExecutable assets --config $ConfigPath connect --for all --user
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Some coding agents were not set up; see above, or use Agent Web Settings > Coding agents."
    }
}
# The bundled Skills: AEP's in-use Skills (and the Workflows they call)
# switched on, the Hermes skill pack switched off. What is already here is
# kept as it is, switched on or off; nothing removed is brought back. The
# coding-agent copy of a pack skill reaches Claude Code / Copilot only while
# it is switched on, and not at all with -NoAgentSkills.
$BundledArguments = @("assets", "--config", $ConfigPath, "install-bundled", "--bundle", $BundleRoot)
if ($NoAgentSkills) { $BundledArguments += "--no-agent-skills" }
& $HostExecutable @BundledArguments
if ($LASTEXITCODE -ne 0) { throw "The bundled Skills could not be installed; see above." }
Write-Host "Installed the local-only preview at $InstallRoot"
Write-Host "Bundle source revision: $($Manifest.source_revision)"
Write-Host "The resident Agent is bound to $Actor on $BridgeId. Capability grants remain separate."
