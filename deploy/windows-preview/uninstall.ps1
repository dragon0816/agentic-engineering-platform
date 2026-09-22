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
if (-not $Apply) {
    Write-Host "Dry run: would remove the versioned preview directory $Target"
    Write-Host "Run uninstall.cmd -Apply to perform this removal."
    exit 0
}
Remove-Item -LiteralPath $Target -Recurse -Force
Write-Host "Removed $Target"
