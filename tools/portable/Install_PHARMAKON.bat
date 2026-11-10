@echo off
chcp 65001 >nul
title PHARMAKON 3.2 Setup & Installation
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_wizard.ps1"
exit /b 0
