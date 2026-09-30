[CmdletBinding()]
param(
    [string]$Path = (Join-Path $PSScriptRoot "..\.env\local.yaml")
)

$allowedNames = @(
    "GH_TOKEN",
    "AEP_GITHUB_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_USER_ID",
    "TELEGRAM_HERMES_BOT_ID",
    "TELEGRAM_CONTROL_CHAT_ID"
)

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "Local environment file not found: $Path. Copy .env/example.yaml to .env/local.yaml first."
}

$loaded = [System.Collections.Generic.List[string]]::new()
$seen = @{}
$lineNumber = 0

foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
    $lineNumber += 1
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
    }

    if ($trimmed -notmatch '^([A-Z][A-Z0-9_]*)\s*:\s*(.*)$') {
        throw 'Invalid local environment entry at line ' + $lineNumber + '. Expected NAME: "value".'
    }

    $name = $Matches[1]
    $value = $Matches[2].Trim()
    if (
        $value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
         ($value.StartsWith("'") -and $value.EndsWith("'")))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    if ($name -notin $allowedNames) {
        throw "Unsupported local environment variable '$name' at line $lineNumber."
    }
    if ($seen.ContainsKey($name)) {
        throw "Duplicate local environment variable '$name' at line $lineNumber."
    }
    $seen[$name] = $true
    if (-not $value) {
        continue
    }

    [Environment]::SetEnvironmentVariable($name, $value, "Process")
    $loaded.Add($name)
}

if ($loaded.Count -eq 0) {
    throw "Local environment file contains no values: $Path"
}

Write-Host ("Loaded local environment variables: " + ($loaded -join ", "))
