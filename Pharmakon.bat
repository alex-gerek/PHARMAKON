@echo off
chcp 65001 >nul
title PHARMAKON - Audio Antidote and Mastering DSP
color 0E

echo ========================================================
echo         PHARMAKON // AUDIO ANTIDOTE AND MASTERING DSP
echo    AI De-Harshing, Mono Sub-Bass, Punch and 3D Width
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "ENGINE=%SCRIPT_DIR%remaster_engine.py"

REM Find the best Python executable
set "PY_EXE="
if exist "C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PY_EXE=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe"
    goto :found_python
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3.13 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXE=py -3.13"
        goto :found_python
    )
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PY_EXE=python"
    goto :found_python
)

echo [ERROR] Python not found in system PATH.
echo Please install Python 3.9+ from https://www.python.org
echo.
pause
exit /b 1

:found_python

REM Verify dependencies
"%PY_EXE%" -c "import numpy, scipy, soundfile" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing required libraries: numpy, scipy, soundfile...
    "%PY_EXE%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
    echo.
)

set "TARGET=%~1"

if not "%TARGET%"=="" goto :run_engine

echo Drag and drop an audio file [*.wav, *.mp3, *.flac] or stems folder here
echo [Перетащите сюда аудиофайл или папку со стемами]:
echo.
set /p "TARGET=> "

:run_engine
set "TARGET=%TARGET:"=%"

if "%TARGET%"=="" (
    echo [ERROR] No target file or folder provided.
    pause
    exit /b 1
)

echo.
echo Processing target: "%TARGET%"
echo.

"%PY_EXE%" "%ENGINE%" "%TARGET%"

if errorlevel 1 (
    echo.
    echo [ERROR] An error occurred during audio processing.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo SUCCESS! Processing complete. Press any key to exit...
echo ========================================================
pause >nul
