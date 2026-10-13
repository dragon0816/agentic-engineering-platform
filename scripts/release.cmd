@echo off
setlocal
rem Make a Windows release for colleagues; see scripts\release_windows.py and docs\RELEASING.zh-TW.md.
"%~dp0..\.venv\Scripts\python.exe" "%~dp0release_windows.py" %*
exit /b %ERRORLEVEL%
