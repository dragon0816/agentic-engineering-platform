@echo off
rem Draft this week's report mail in Outlook.
rem
rem Double-click this, or make a shortcut to it. It SAVES A DRAFT and does
rem not send: nothing in this platform can send a mail. Open the draft in
rem Outlook, read it, and send it yourself.
rem
rem It does not touch the workbook, so the workbook may stay open in Excel.
rem
rem The week is this week unless one is named:  weekly-mail.cmd 2026_39W
setlocal
set "ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if not exist "%ROOT%\host.json" (
  echo Cannot find %ROOT%\host.json
  echo Install the preview first, or edit ROOT in this file.
  pause
  exit /b 2
)
set "WEEK=%~1"
if "%WEEK%"=="" (set "ASK=weekly.mail") else (set "ASK=weekly.mail %WEEK%")

"%ROOT%\.venv\Scripts\aep-host.exe" ask --config "%ROOT%\host.json" --namespace engineering "%ASK%"
if errorlevel 1 (
  echo.
  echo No draft was made. The message above says why.
  pause
  exit /b 1
)
echo.
echo The draft is in your Outlook Drafts folder. Nothing was sent.
pause
