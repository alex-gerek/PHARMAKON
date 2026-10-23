@echo off
chcp 65001 >nul
title PHARMAKON - Audio Antidote and Mastering DSP
color 0E

echo ========================================================
echo         PHARMAKON - AUDIO ANTIDOTE AND MASTERING DSP
echo    Очистка ИИ-артефактов, Моно-бас, Панч и 3D-Стерео
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "ENGINE=%SCRIPT_DIR%remaster_engine.py"

REM Find the best Python executable
set "PY_EXE="
if exist "C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PY_EXE=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe"
)

if "%PY_EXE%"=="" (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.13 -c "import sys" >nul 2>&1
        if not errorlevel 1 (
            set "PY_EXE=py -3.13"
        )
    )
)

if "%PY_EXE%"=="" (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    echo [ОШИБКА] Python не найден в системе.
    echo Установите Python 3.9+ с официального сайта python.org
    echo.
    pause
    exit /b 1
)

REM Verify dependencies
"%PY_EXE%" -c "import numpy, scipy, soundfile" >nul 2>&1
if errorlevel 1 (
    echo [НАСТРОЙКА] Первый запуск: установка библиотек numpy, scipy, soundfile...
    "%PY_EXE%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
    echo.
)

set "TARGET=%~1"

if "%TARGET%"=="" (
    echo Перетащите сюда мышкой аудиофайл или папку со стемсами
    echo или укажите путь и нажмите Enter:
    echo.
    set /p "TARGET=> "
)

set "TARGET=%TARGET:"=%"

if "%TARGET%"=="" (
    echo [ОШИБКА] Путь к файлу не указан.
    pause
    exit /b 1
)

echo.
echo Запуск обработки: "%TARGET%"
echo.

"%PY_EXE%" "%ENGINE%" "%TARGET%"

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Во время обработки произошел сбой.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo Готово. Нажмите любую клавишу для завершения...
echo ========================================================
pause >nul
