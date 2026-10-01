@echo off
setlocal
set "INSTALL_ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-preview-0.1.0"
if not "%~1"=="" set "INSTALL_ROOT=%~1"
if not exist "%INSTALL_ROOT%\.venv\Scripts\aep-platform.exe" (
  echo Shared Platform is not installed at "%INSTALL_ROOT%". 1>&2
  exit /b 2
)
if not exist "%INSTALL_ROOT%\bundle-manifest.json" (
  echo Installed bundle identity is missing. Reinstall from the current package. 1>&2
  exit /b 2
)
if not exist "%INSTALL_ROOT%\platform.json" (
  echo Shared Platform configuration is missing. 1>&2
  exit /b 2
)
for /f "usebackq delims=" %%R in (`powershell.exe -NoProfile -Command "(ConvertFrom-Json (Get-Content -LiteralPath '%INSTALL_ROOT%\bundle-manifest.json' -Raw)).source_revision"`) do set "SOURCE_REVISION=%%R"
echo bundle source revision: %SOURCE_REVISION%
"%INSTALL_ROOT%\.venv\Scripts\aep-platform.exe" --help >nul
if errorlevel 1 exit /b 2
"%INSTALL_ROOT%\.venv\Scripts\python.exe" -c "import sys; from pathlib import Path; from control_plane.app import SharedPlatformConfiguration; SharedPlatformConfiguration.model_validate_json(Path(sys.argv[1]).read_text(encoding='utf-8-sig')); print('shared platform configuration: valid')" "%INSTALL_ROOT%\platform.json"
exit /b %ERRORLEVEL%
