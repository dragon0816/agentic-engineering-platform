# Company Bridge host — Windows technical preview

This preview proves a credential-free, per-user installation and company-device
configuration before the shared-platform enrollment transport exists. It does
not run workflow 7 or 13 and contains no Jira, Excel, Git, browser, email, DUT or
instrument adapter.

## Prerequisite

- 64-bit Windows 10 or 11
- 64-bit CPython 3.12 available as `python`, or its full path

The bundle is offline: its `wheels/` directory contains every Python dependency.
Do not add a password, token, cookie or API key to `host.json`.

## Install and inspect

Open Command Prompt in the extracted bundle and choose stable IDs containing only
letters, numbers, `_`, `.`, or `-`:

```bat
install.cmd -Actor employee.id -BridgeId bridge-company-001
```

If Python is not on PATH:

```bat
install.cmd -Actor employee.id -BridgeId bridge-company-001 -PythonExe "C:\Python312\python.exe"
```

The installer verifies every bundled file, creates a versioned virtual environment
under `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0`, writes only
non-secret device metadata, and runs `aep-host doctor`. It does not contact the
shared platform or any company system.

Run the checks again and export the JSON that will later be submitted through an
authenticated enrollment flow:

```bat
verify.cmd
"%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\.venv\Scripts\aep-host.exe" enrollment-request --config "%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json" --output enrollment-request.json
```

Inspect `enrollment-request.json` before transferring it. It is identity and
capability-advertisement metadata, not proof that the device may execute anything.

## Remove

`uninstall.cmd` shows what it would remove. `uninstall.cmd -Apply` removes only the
versioned preview installation. The extracted bundle and exported enrollment JSON
remain until you remove them yourself.
