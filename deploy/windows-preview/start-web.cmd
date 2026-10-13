@echo off
setlocal
rem Open Agent Web in the browser, starting it in the background first if needed.
set "INSTALL_ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if not "%~1"=="" set "INSTALL_ROOT=%~1"
if not exist "%INSTALL_ROOT%\.venv\Scripts\aep-host.exe" (
  echo AEP is not installed at "%INSTALL_ROOT%". Run install.cmd first. 1>&2
  pause
  exit /b 2
)
"%INSTALL_ROOT%\.venv\Scripts\aep-host.exe" open --config "%INSTALL_ROOT%\host.json"
if errorlevel 1 (
  echo Agent Web did not start. See the newest agent-web-*.err.log in "%INSTALL_ROOT%\workspace\logs". 1>&2
  pause
  exit /b 1
)
exit /b 0
