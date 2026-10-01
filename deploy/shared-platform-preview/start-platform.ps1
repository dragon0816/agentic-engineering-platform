param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\shared-platform-preview-0.1.0"
)
$ErrorActionPreference = "Stop"
$Executable = Join-Path $InstallRoot ".venv\Scripts\aep-platform.exe"
$Config = Join-Path $InstallRoot "platform.json"
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Shared Platform is not installed at $InstallRoot"
}
$InvitationOutput = Join-Path $InstallRoot ("invitation-links-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmssfff"))
& $Executable serve --config $Config --invitation-output $InvitationOutput
exit $LASTEXITCODE
