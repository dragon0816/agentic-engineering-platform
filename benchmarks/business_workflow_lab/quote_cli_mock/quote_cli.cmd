@echo off
rem Runs the synthetic quote CLI: quote_cli.cmd --help
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
python -m quote_cli %*
