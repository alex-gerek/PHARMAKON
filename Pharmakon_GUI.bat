@echo off
chcp 65001 >nul
title PHARMAKON 2.0 Studio Console

set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%launcher.pyw"

REM Detect pythonw for silent start or python as fallback
if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%LAUNCHER%"
    exit /b 0
)

start "" pythonw "%LAUNCHER%"
exit /b 0
