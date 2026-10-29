@echo off
chcp 65001 >nul
title PHARMAKON 2.0 - Audio Antidote and Mastering DSP
color 0E

echo ========================================================
echo         PHARMAKON // AUDIO ANTIDOTE AND MASTERING DSP
echo    AI De-Harshing, Mono Sub-Bass, Punch and 3D Width
echo                  Author: Lex Gerek
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "ENGINE=%SCRIPT_DIR%remaster_engine.py"
set "GUI_LAUNCHER=%SCRIPT_DIR%Pharmakon_GUI.bat"

REM Find the best Python executable
set "PY_EXE="
if exist "C:\Python314\python.exe" (
    set "PY_EXE=C:\Python314\python.exe"
    goto :found_python
)
if exist "C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PY_EXE=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe"
    goto :found_python
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PY_EXE=python"
    goto :found_python
)

where py >nul 2>&1
if not errorlevel 1 (
    set "PY_EXE=py"
    goto :found_python
)

echo [ERROR] Python not found in system PATH.
echo Please install Python 3.9+ from https://www.python.org
echo.
pause
exit /b 1

:found_python

REM Verify dependencies
"%PY_EXE%" -c "import numpy, scipy, soundfile, fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing required libraries: numpy, scipy, soundfile, fastapi, uvicorn...
    "%PY_EXE%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
    echo.
)

set "TARGET=%~1"

REM If file or folder was dragged onto this .bat, run immediately in CLI batch mode
if not "%TARGET%"=="" goto :run_engine

REM If launched without arguments, prompt for GUI or CLI
echo [1] Запустить визуальный интерфейс PHARMAKON Studio Console (Нажмите ENTER)
echo [2] Консольный режим (Drag & Drop в терминал)
echo.
set /p "CHOICE=Выберите режим [1/2, по умолчанию 1]: "

if "%CHOICE%"=="2" goto :cli_prompt

REM Default: Launch GUI Console
call "%GUI_LAUNCHER%"
exit /b 0

:cli_prompt
echo.
echo Drag and drop an audio file [*.wav, *.mp3, *.flac] or stems folder here:
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
