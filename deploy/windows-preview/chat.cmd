@echo off
rem Open a window and talk to the Agent on this computer.
rem
rem Double-click this, or make a shortcut to it. It is the same Agent the
rem command line and Telegram reach, so Telegram is not needed to use it.
rem
rem Type a command such as  weekly.preview 2026_39W
rem Nothing is written to the workbook unless the command says so.
setlocal
set "ROOT=%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0"
if not exist "%ROOT%\host.json" (
  echo Cannot find %ROOT%\host.json
  echo Install the preview first, or edit ROOT in this file.
  pause
  exit /b 2
)
rem This console stays open behind the window. It is not decoration: a
rem configuration this host cannot read, or a Python built without Tk, is
rem reported here, and hiding it with pythonw.exe would leave a machine that
rem opens nothing and says nothing.
"%ROOT%\.venv\Scripts\aep-host.exe" chat --config "%ROOT%\host.json"
if errorlevel 1 (
  echo.
  echo The window could not be opened. The message above says why.
  pause
  exit /b 1
)
