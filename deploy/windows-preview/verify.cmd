@echo off
setlocal
set "INSTALL_ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if not exist "%INSTALL_ROOT%\.venv\Scripts\aep-host.exe" (
  echo Preview is not installed at "%INSTALL_ROOT%". 1>&2
  exit /b 2
)
"%INSTALL_ROOT%\.venv\Scripts\aep-host.exe" doctor --config "%INSTALL_ROOT%\host.json"
exit /b %ERRORLEVEL%
