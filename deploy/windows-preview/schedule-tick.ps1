<#
.SYNOPSIS
Let Windows run one `aep-host schedules tick` every few minutes.

.DESCRIPTION
Scheduled tasks live in this host's own schedule store (no n8n). Each tick
claims what is due, checks the schedule's execution grant and the Bridge's
grants, and runs it through the resident Agent. A schedule that is not
granted, or whose target can send mail or messages, does not run on its own:
it waits in Agent Web's Schedules panel (or `aep-host schedules pending`).

Use this when Agent Web is not left running with `--schedules`. Running both
is safe -- a due occurrence is claimed exactly once -- but one is enough.

.EXAMPLE
.\schedule-tick.ps1
Every 15 minutes while you are signed in.

.EXAMPLE
.\schedule-tick.ps1 -EveryMinutes 5
.\schedule-tick.ps1 -Remove
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 1440)]
    [int]$EveryMinutes = 15,
    [string]$TaskName = "Agentic scheduled tasks",
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0",
    [switch]$Remove
)
$ErrorActionPreference = "Stop"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed the scheduled task '$TaskName'."
    return
}

$hostExe = Join-Path $InstallRoot ".venv\Scripts\aep-host.exe"
$config = Join-Path $InstallRoot "host.json"
if (-not (Test-Path -LiteralPath $hostExe) -or -not (Test-Path -LiteralPath $config)) {
    throw "No host at $InstallRoot. Install the preview first, or pass -InstallRoot."
}

# The task runs as the signed-in user, because the workbook, the tokens and
# Office all belong to that account. A task running as SYSTEM would see none
# of them.
$action = New-ScheduledTaskAction -Execute $hostExe `
    -Argument "schedules --config `"$config`" tick" -WorkingDirectory $InstallRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Force | Out-Null

Write-Host "Scheduled '$TaskName' every $EveryMinutes minute(s)."
Write-Host "Grant each schedule in Agent Web (Schedules) before it can run unattended."
