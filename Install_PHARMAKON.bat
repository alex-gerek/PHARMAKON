@echo off
chcp 65001 >nul
title PHARMAKON 2.0 Setup & Installation
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_wizard.ps1"
exit /b 0
