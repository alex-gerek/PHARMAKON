@echo off
chcp 65001 >nul
title PHARMAKON 3.2 - Create Desktop Shortcut
cd /d "%~dp0"

echo =================================================================
echo   PHARMAKON 3.2 // DESKTOP SHORTCUT CREATOR
echo =================================================================
echo.
echo Current folder: %~dp0
echo.
echo Creating shortcut on your Windows Desktop...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$desktop = [System.Environment]::GetFolderPath('Desktop'); " ^
  "$shortcut = $ws.CreateShortcut((Join-Path $desktop 'PHARMAKON 3.2.lnk')); " ^
  "$currentDir = '%~dp0'.TrimEnd('\'); " ^
  "$target = Join-Path $currentDir 'Start_Pharmakon.bat'; " ^
  "if (-not (Test-Path $target)) { $target = Join-Path $currentDir 'Pharmakon_GUI.bat' }; " ^
  "$shortcut.TargetPath = $target; " ^
  "$shortcut.WorkingDirectory = $currentDir; " ^
  "$shortcut.Description = 'PHARMAKON 3.2 Studio Console // Neural Audio Antidote & Track Intelligence Map'; " ^
  "$ico = Join-Path $currentDir 'pharmakon_hd_256.ico'; " ^
  "if (Test-Path $ico) { $shortcut.IconLocation = \"$ico,0\" }; " ^
  "$shortcut.Save(); " ^
  "Write-Host '[SUCCESS] PHARMAKON 3.2 shortcut created on your Desktop!' -ForegroundColor Green"

echo.
echo Done. You can now launch PHARMAKON 3.2 directly from your Desktop icon.
echo.
timeout /t 3 >nul
exit /b 0
