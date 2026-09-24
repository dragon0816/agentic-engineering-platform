@echo off
rem Write the weekly report into the workbook.
rem
rem Double-click this, or make a shortcut to it. It writes, so it asks first.
rem Close the workbook in Excel before running it: a file Excel has open is
rem refused before anything is copied.
rem
rem The week is this week unless one is named:  weekly-apply.cmd 2026_39W
setlocal
set "ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if not exist "%ROOT%\host.json" (
  echo Cannot find %ROOT%\host.json
  echo Install the preview first, or edit ROOT in this file.
  pause
  exit /b 2
)
set "WEEK=%~1"
if "%WEEK%"=="" (set "ASK=weekly.apply") else (set "ASK=weekly.apply %WEEK%")

echo This writes into the workbook named in host.json.
echo Close it in Excel first.
echo.
choice /c YN /m "Write it now"
if errorlevel 2 (
  echo Nothing was written.
  exit /b 0
)
"%ROOT%\.venv\Scripts\aep-host.exe" ask --config "%ROOT%\host.json" --namespace engineering "%ASK%"
if errorlevel 1 (
  echo.
  echo The run did not finish. The message above says why, and the workbook
  echo was left as it was.
  pause
  exit /b 1
)
echo.
echo Written. A backup of the workbook was taken beside it first.
pause
