@echo off
rem Build the WinForms Expense app with the .NET Framework 4.x compiler (C# 5).
rem Output: expense_desktop_mock\bin\ExpenseApp.exe
setlocal
set "HERE=%~dp0"
set "FW=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319"
if not exist "%FW%\csc.exe" set "FW=%WINDIR%\Microsoft.NET\Framework\v4.0.30319"
if not exist "%FW%\csc.exe" (
  echo csc.exe not found under %WINDIR%\Microsoft.NET 1>&2
  exit /b 1
)
if not exist "%HERE%bin" mkdir "%HERE%bin"
"%FW%\csc.exe" /nologo /codepage:65001 /target:winexe /optimize+ /langversion:5 ^
  /out:"%HERE%bin\ExpenseApp.exe" ^
  /reference:System.dll /reference:System.Core.dll /reference:System.Drawing.dll ^
  /reference:System.Windows.Forms.dll /reference:"%FW%\System.Web.Extensions.dll" ^
  "%HERE%ExpenseApp.cs"
exit /b %ERRORLEVEL%
