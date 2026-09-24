@echo off
rem Run the weekly report's dry run and show what it would write.
rem
rem Double-click this, or make a shortcut to it on the desktop. It writes
rem nothing to the workbook: it produces the plan and prints it.
rem
rem The week is this week unless one is named:  weekly-preview.cmd 2026_39W
setlocal
set "ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if not exist "%ROOT%\host.json" (
  echo Cannot find %ROOT%\host.json
  echo Install the preview first, or edit ROOT in this file.
  pause
  exit /b 2
)
set "WEEK=%~1"
if "%WEEK%"=="" (set "ASK=weekly.preview") else (set "ASK=weekly.preview %WEEK%")

rem Written in UTF-8 by the host itself, never redirected by the shell: a
rem Windows PowerShell redirect writes UTF-16 and the file is then unreadable.
"%ROOT%\.venv\Scripts\aep-host.exe" ask --config "%ROOT%\host.json" --namespace engineering --json --output "%ROOT%\plan.json" "%ASK%"
if errorlevel 1 (
  echo.
  echo The run did not finish. The message above says why.
  pause
  exit /b 1
)
"%ROOT%\.venv\Scripts\python.exe" -c "import json;print(json.load(open(r'%ROOT%\plan.json',encoding='utf-8'))['workflow']['step_results'][-1]['data']['preview'])"
echo.
echo Nothing was written. Run weekly-apply.cmd to write it.
pause
