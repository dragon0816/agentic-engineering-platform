param(
    [switch]$Apply,
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\shared-platform-preview-0.1.0"
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
if (-not $Apply) {
    Write-Host "Dry run: would remove $Target, including its Registry database."
    Write-Host "Back up workspace\registry.sqlite, then run uninstall.cmd -Apply if removal is intended."
    exit 0
}
Remove-Item -LiteralPath $Target -Recurse -Force
Write-Host "Removed $Target"
