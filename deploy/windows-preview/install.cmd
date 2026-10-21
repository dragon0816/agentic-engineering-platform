@echo off
setlocal
rem Windows PowerShell 5.1 started from a PowerShell 7 window inherits pwsh's
rem module path and cannot load its own modules; let it use its defaults.
set "PSModulePath="
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" pause
exit /b %CODE%
