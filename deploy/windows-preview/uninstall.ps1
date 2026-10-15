param(
    [switch]$Apply,
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0"
)
$ErrorActionPreference = "Stop"
$ExpectedParent = [IO.Path]::GetFullPath("$env:LOCALAPPDATA\AgenticEngineeringPlatform")
$Target = [IO.Path]::GetFullPath($InstallRoot)
if (-not $Target.StartsWith($ExpectedParent + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove a path outside $ExpectedParent"
}
if (-not (Test-Path -LiteralPath $Target)) {
    Write-Host "Nothing is installed at $Target"
    exit 0
}
$HostExecutable = Join-Path $Target ".venv\Scripts\aep-host.exe"
$ConfigPath = Join-Path $Target "host.json"
if (-not $Apply) {
    Write-Host "Dry run: would remove AEP's skills and MCP servers from Claude Code, Codex and Copilot"
    Write-Host "Dry run: would remove the versioned preview directory $Target"
    Write-Host "Run uninstall.cmd -Apply to perform this removal."
    exit 0
}
# The coding agents' AEP entries point into this installation; take them out
# first (only AEP's own entries; the agents' other settings stay).
if (Test-Path -LiteralPath $HostExecutable) {
    & $HostExecutable assets --config $ConfigPath connect --for all --user --remove
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not remove AEP from every coding agent; see above." }
}
Remove-Item -LiteralPath $Target -Recurse -Force
Write-Host "Removed $Target"
