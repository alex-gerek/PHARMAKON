@echo off
chcp 65001 >nul
title PHARMAKON 3.2 Studio Console
cd /d "%~dp0"

if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%~dp0launcher.pyw"
    exit /b 0
)
if exist "%~dp0dist\PHARMAKON\Pharmakon.exe" (
    start "" "%~dp0dist\PHARMAKON\Pharmakon.exe"
    exit /b 0
)
start "" pythonw "%~dp0launcher.pyw"
exit /b 0
