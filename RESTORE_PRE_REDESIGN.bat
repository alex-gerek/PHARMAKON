@echo off
echo ========================================================
echo   PHARMAKON // RESTORING PRE-REDESIGN BACKUP...
echo ========================================================
set BACKUP_DIR=%~dp0backup_pre_redesign
set TARGET_DIR=%~dp0

copy /Y "%BACKUP_DIR%\remaster_engine.py" "%TARGET_DIR%\remaster_engine.py"
copy /Y "%BACKUP_DIR%\gui\server.py" "%TARGET_DIR%\gui\server.py"
copy /Y "%BACKUP_DIR%\gui\static\*" "%TARGET_DIR%\gui\static\"

echo.
echo [SUCCESS] All files restored to pre-redesign state!
pause
