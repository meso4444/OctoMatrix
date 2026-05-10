#!/bin/bash
echo "🔧 Calling Windows PowerShell to setup autostart..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PS1_PATH=$(wslpath -w "$SCRIPT_DIR/setup_autostart.ps1")
LAUNCHER="run_setup_tmp.bat"
LAUNCHER_PATH="$SCRIPT_DIR/$LAUNCHER"

cat > "$LAUNCHER_PATH" <<EOF
@echo off
title OctoMatrix - Setup
echo Starting PowerShell Setup Script...
echo Script: "$PS1_PATH"
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS1_PATH"

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script execution failed.
) else (
    echo [SUCCESS] Script finished.
)
echo.
pause
del "%~f0" &:: self-destruct
EOF

sed -i 's/$/\r/' "$LAUNCHER_PATH"
BAT_PATH=$(wslpath -w "$LAUNCHER_PATH")

echo "📍 Launcher path: $BAT_PATH"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
    "Start-Process cmd -Verb RunAs -ArgumentList '/c \"$BAT_PATH\"'"

echo "✅ Request sent! Please check the UAC prompt and the new CMD window."