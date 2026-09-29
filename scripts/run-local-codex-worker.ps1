[CmdletBinding()]
param(
    [string]$Repository = "dragon0816/agentic-engineering-platform",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [switch]$Once
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "import-local-env.ps1")
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required."
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI is required."
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Repository virtual environment not found: $python"
}

gh auth status --hostname github.com
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI authentication is not ready." }
gh auth setup-git --hostname github.com
if ($LASTEXITCODE -ne 0) { throw "GitHub Git credential integration is not ready." }
codex login status
if ($LASTEXITCODE -ne 0) { throw "Codex Pro login is not ready. Run: codex login" }

$arguments = @(
    "-m", "development.codex_worker",
    "--repository", $Repository,
    "--repo-root", $RepoRoot
)
if (-not $Once) {
    $arguments += @("--loop", "--interval", "60")
}

& $python @arguments
exit $LASTEXITCODE

