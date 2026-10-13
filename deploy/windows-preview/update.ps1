param(
    [string]$PythonExe = "python",
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0",
    # Leave the desktop and Start menu shortcuts as they are.
    [switch]$NoShortcut
)
# Update an existing installation from this bundle. The person, the Bridge ID,
# host.json and the workspace are kept: install.ps1 rewrites only the device
# identity and keeps every other host.json setting.
$ErrorActionPreference = "Stop"
$ConfigPath = Join-Path $InstallRoot "host.json"
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw ("AEP is not installed at $InstallRoot yet. For a first installation run " +
        "install.cmd -Actor <your id> instead.")
}
$Existing = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$Actor = $Existing.device.registered_by
$BridgeId = $Existing.device.bridge_id
if ([string]::IsNullOrWhiteSpace($Actor) -or [string]::IsNullOrWhiteSpace($BridgeId)) {
    throw "host.json does not name its user and Bridge ID; run install.cmd -Actor <your id>."
}

# A running Agent Web holds the files the update replaces; stop it first.
$Venv = [IO.Path]::GetFullPath((Join-Path $InstallRoot ".venv"))
$Running = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and
        [IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($Venv, [StringComparison]::OrdinalIgnoreCase)
    })
if ($Running.Count -gt 0) {
    Write-Host "Stopping the running Agent Web ($($Running.Count) process(es)) for the update."
    $Running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

$Previous = Join-Path $InstallRoot "bundle-manifest.json"
if (Test-Path -LiteralPath $Previous) {
    $From = (Get-Content -LiteralPath $Previous -Raw | ConvertFrom-Json).source_revision
    Write-Host "Installed revision before the update: $From"
}
& (Join-Path $PSScriptRoot "install.ps1") -Actor $Actor -BridgeId $BridgeId `
    -PythonExe $PythonExe -InstallRoot $InstallRoot -NoShortcut:$NoShortcut
Write-Host "Updated. Open Agent Web again with the 'AEP Agent' shortcut or start-web.cmd."
