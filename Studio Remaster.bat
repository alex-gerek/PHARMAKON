@echo off
chcp 65001 >nul
title Studio Remaster - Lex Gerek DSP Audio Engine
color 0E

echo ========================================================
echo         STUDIO REMASTER (DSP CLEANING & MASTERING)
echo    Очистка ИИ-артефактов, Моно-бас, Панч и 3D-Стерео
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "ENGINE=%SCRIPT_DIR%remaster_engine.py"

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА / ERROR] Python не найден!
    echo Установите Python 3.9+ с официального сайта: https://www.python.org/downloads/
    echo Обязательно отметьте галочку "Add Python to PATH" при установке!
    echo.
    pause
    exit /b 1
)

:: Check dependencies and auto-install if missing
python -c "import numpy, scipy, soundfile" >nul 2>&1
if %errorlevel% neq 0 (
    echo [НАСТРОЙКА / SETUP] Первый запуск: автоматическая установка библиотек DSP...
    python -m pip install -r "%SCRIPT_DIR%requirements.txt"
    echo.
)

set "TARGET=%~1"

if "%TARGET%"=="" (
    echo Перетащите сюда мышкой папку со стемсами (vocals, drums, bass, other)
    echo или вставьте путь к ней и нажмите Enter:
    echo.
    set /p "TARGET=> "
)

set "TARGET=%TARGET:"=%"

if "%TARGET%"=="" (
    echo Путь не указан.
    pause
    exit /b
)

python "%ENGINE%" "%TARGET%"

echo.
echo ========================================================
echo Готово! Нажмите любую клавишу для завершения...
echo ========================================================
pause >nul
