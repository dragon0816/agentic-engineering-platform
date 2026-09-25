@echo off
rem Run one approved physical DUT request through this computer's resident Agent.
setlocal
set "ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if "%~1"=="" goto usage
if not exist "%ROOT%\host.json" (
  echo Cannot find %ROOT%\host.json
  echo Install the preview first, or edit ROOT in this file.
  exit /b 2
)
set "OUTPUT=%~2"
if "%OUTPUT%"=="" set "OUTPUT=dut-evidence.json"
"%ROOT%\.venv\Scripts\aep-host.exe" dut-validate --config "%ROOT%\host.json" --request "%~1" --output "%OUTPUT%"
exit /b %ERRORLEVEL%

:usage
echo Usage: dut-validate.cmd REQUEST.json [EVIDENCE.json]
echo Edit dut-request.example.json first. Physical execution must also be enabled in host.json.
exit /b 2
