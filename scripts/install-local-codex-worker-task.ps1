[CmdletBinding()]
param(
    [string]$Repository = "dragon0816/agentic-engineering-platform",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$TaskName = "AEP Local Codex Worker"
)

$ErrorActionPreference = "Stop"
$runner = (Resolve-Path (Join-Path $PSScriptRoot "run-local-codex-worker.ps1")).Path
$pwsh = (Get-Command pwsh -ErrorAction Stop).Source
$escapedRunner = $runner.Replace('"', '\"')
$escapedRepo = $RepoRoot.Replace('"', '\"')
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$escapedRunner`" -Repository `"$Repository`" -RepoRoot `"$escapedRepo`""

$action = New-ScheduledTaskAction -Execute $pwsh -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Polls typed GitHub repair requests and runs Codex locally with ChatGPT authentication." `
    -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Started scheduled task: $TaskName"
