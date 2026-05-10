@echo off
title OctoMatrix Launcher
echo ========================================================
echo   OctoMatrix - WSL Launcher
echo ========================================================
echo.

echo [1/2] Checking OctoMatrix location in WSL...

wsl -d Ubuntu bash -c "SCRIPT_DIR=\"$(dirname \"$(wslpath '%~dp0')\")\"; cd \"$SCRIPT_DIR\" && ./start_octo_services.sh"

echo.
echo [2/2] Done.
pause