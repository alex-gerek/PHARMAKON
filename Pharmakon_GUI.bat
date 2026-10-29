@echo off
chcp 65001 >nul
title PHARMAKON 2.0 Studio Console
color 0A

echo ========================================================
echo        PHARMAKON 2.0 // STUDIO CONSOLE LAUNCHER
echo          Audio Antidote & Mastering DSP System
echo                  Author: Lex Gerek
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "SERVER_SCRIPT=%SCRIPT_DIR%gui\server.py"

REM Detect Python
set "PY_EXE=python"
if exist "C:\Python314\python.exe" set "PY_EXE=C:\Python314\python.exe"
if exist "C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" set "PY_EXE=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe"

echo [STARTING] Booting local DSP server on port 7860...
start /b "" "%PY_EXE%" "%SERVER_SCRIPT%"

REM Wait 2 seconds for server to initialize
timeout /t 2 /nobreak >nul

set "URL=http://127.0.0.1:7860"

REM Try Microsoft Edge standalone App Mode
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    echo [UI] Launching Studio Console Window (Edge App)...
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="%URL%" --window-size=1280,900
    goto :done
)

REM Try Google Chrome standalone App Mode
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo [UI] Launching Studio Console Window (Chrome App)...
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="%URL%" --window-size=1280,900
    goto :done
)

REM Fallback to default browser
echo [UI] Opening default browser...
start "" "%URL%"

:done
echo.
echo ========================================================
echo  PHARMAKON Studio Console is live at: %URL%
echo  Keep this console window open while using the app.
echo ========================================================
echo.
pause
