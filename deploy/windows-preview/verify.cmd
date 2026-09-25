@echo off
setlocal
set "INSTALL_ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if not "%~1"=="" set "INSTALL_ROOT=%~1"
if not exist "%INSTALL_ROOT%\.venv\Scripts\aep-host.exe" (
  echo Preview is not installed at "%INSTALL_ROOT%". 1>&2
  exit /b 2
)
if not exist "%INSTALL_ROOT%\bundle-manifest.json" (
  echo Installed bundle identity is missing. Reinstall from the current package. 1>&2
  exit /b 2
)
for /f "usebackq delims=" %%R in (`powershell.exe -NoProfile -Command "(ConvertFrom-Json (Get-Content -LiteralPath '%INSTALL_ROOT%\bundle-manifest.json' -Raw)).source_revision"`) do set "SOURCE_REVISION=%%R"
echo bundle source revision: %SOURCE_REVISION%
"%INSTALL_ROOT%\.venv\Scripts\aep-host.exe" dut-validate --help >nul
if errorlevel 1 (
  echo Installed runtime does not provide dut-validate. Reinstall from the current package. 1>&2
  exit /b 2
)
"%INSTALL_ROOT%\.venv\Scripts\aep-host.exe" doctor --config "%INSTALL_ROOT%\host.json"
exit /b %ERRORLEVEL%
