@echo off
chcp 65001 >nul
title Studio Remaster - DSP Audio Engine
color 0E

echo ========================================================
echo         STUDIO REMASTER (DSP CLEANING & MASTERING)
echo    Очистка ИИ-артефактов, Моно-бас, Панч и 3D-Стерео
echo ========================================================
echo.

set "TARGET=%~1"

if "%TARGET%"=="" (
    echo Перетащите сюда папку со стемсами (или любой файл из нее)
    echo и нажмите клавишу Enter:
    echo.
    set /p "TARGET=> "
)

set "TARGET=%TARGET:"=%"

if not exist "%TARGET%" (
    echo.
    echo [ОШИБКА] Путь не найден: "%TARGET%"
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b
)

"C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" "D:\КЛИПЫ\Reels\stems\remaster_engine.py" "%TARGET%"

echo.
echo Нажмите любую клавишу для завершения...
pause >nul
