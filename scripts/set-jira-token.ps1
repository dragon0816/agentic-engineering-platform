# Run this file interactively; never pass the PAT as a command-line argument.
$ErrorActionPreference = 'Stop'

do {
    $jiraSecret = Read-Host -Prompt 'Paste Jira Personal Access Token, then press Enter' -AsSecureString
} while ($null -eq $jiraSecret -or $jiraSecret.Length -eq 0)

try {
    $jiraToken = ([System.Net.NetworkCredential]::new('', $jiraSecret)).Password
    if ([string]::IsNullOrWhiteSpace($jiraToken)) {
        throw 'The Jira token was empty; no environment variable was changed.'
    }
    [Environment]::SetEnvironmentVariable('AEP_JIRA_TOKEN', $jiraToken, 'User')
    $env:AEP_JIRA_TOKEN = $jiraToken
    if ([Environment]::GetEnvironmentVariable('AEP_JIRA_TOKEN', 'User') -ne $jiraToken) {
        throw 'The Jira token could not be read back from the user environment.'
    }
    Write-Host 'AEP_JIRA_TOKEN saved for this Windows user. Restart the Agent before testing.'
} finally {
    $jiraToken = $null
    if ($null -ne $jiraSecret) { $jiraSecret.Dispose() }
}
