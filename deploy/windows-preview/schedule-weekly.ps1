<#
.SYNOPSIS
Run the weekly report's dry run on a schedule, through Windows itself.

.DESCRIPTION
The old system's schedule lived in n8n. This platform does not require n8n,
and until something replaces that part of it, Windows' own scheduler is what
runs a thing weekly on a workstation. It needs no service, no server and no
account other than the one already signed in.

The task runs the preview, which writes nothing. Writing stays a thing a
person does, because it changes the team's workbook.

.EXAMPLE
.\schedule-weekly.ps1
Every Friday at 16:00, which is when the source's own schedule ran.

.EXAMPLE
.\schedule-weekly.ps1 -DayOfWeek Monday -At 09:00 -Remove
#>
[CmdletBinding()]
param(
    [ValidateSet("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")]
    [string]$DayOfWeek = "Friday",
    [string]$At = "16:00",
    [string]$TaskName = "Agentic weekly report preview",
    [string]$InstallRoot = "$env:LOCALAPPDATA\AgenticEngineeringPlatform\preview-0.1.0",
    [switch]$Remove
)
$ErrorActionPreference = "Stop"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed the scheduled task '$TaskName'."
    return
}

$script = Join-Path $PSScriptRoot "weekly-preview.cmd"
if (-not (Test-Path -LiteralPath $script)) {
    throw "weekly-preview.cmd is not beside this script; run it from the extracted bundle."
}
if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot "host.json"))) {
    throw "No host at $InstallRoot. Install the preview first, or pass -InstallRoot."
}

# The task runs as the signed-in user, because the workbook, the token and
# Excel all belong to that account. A task running as SYSTEM would see none
# of them.
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$script`"" -WorkingDirectory $InstallRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Scheduled '$TaskName' for every $DayOfWeek at $At."
Write-Host "It runs the preview and writes nothing. Remove it with -Remove."
