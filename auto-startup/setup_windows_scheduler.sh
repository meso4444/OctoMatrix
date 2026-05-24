#!/bin/bash
# Call Windows PowerShell from Linux (WSL) to set up Task Scheduler
# Uses a temporary .bat to ensure stability and solve UNC path argument issues

echo "🔧 Calling Windows PowerShell to set up auto-startup..."

# Get script directory (fixes path issues when running from root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 0. Find powershell.exe path
PS_CMD="powershell.exe"
if ! command -v $PS_CMD &> /dev/null; then
    # Try common Windows paths
    COMMON_PS_PATH="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    if [ -f "$COMMON_PS_PATH" ]; then
        PS_CMD="$COMMON_PS_PATH"
    else
        echo "❌ Error: powershell.exe not found. Please ensure you are in WSL and Windows path is in PATH."
        exit 1
    fi
fi


# 1. Get Windows path of setup_autostart.ps1
PS1_PATH=$(wslpath -w "$SCRIPT_DIR/setup_autostart.ps1")

# 2. Generate a temporary .bat launcher
# This makes Start-Process arguments simpler and pauses the window
LAUNCHER="run_setup_tmp.bat"
# Ensure .bat is generated in the script directory
LAUNCHER_PATH="$SCRIPT_DIR/$LAUNCHER"

cat > "$LAUNCHER_PATH" <<EOF
@echo off
title OctoMatrix - Setup
echo Starting PowerShell Setup Script...
echo Script: "$PS1_PATH"
echo.

:: Call PowerShell to execute .ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS1_PATH"

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script execution failed.
    echo Please check the error message above.
) else (
    echo [SUCCESS] Script finished.
)
echo.
pause
del "%~f0" &:: self-destruct
EOF

# Critical fix: Convert .bat to Windows CRLF format
# Otherwise CMD might parse it incorrectly
sed -i 's/$/\r/' "$LAUNCHER_PATH"

# 3. Get Windows path of the .bat file
BAT_PATH=$(wslpath -w "$LAUNCHER_PATH")

echo "📍 Launcher path: $BAT_PATH"

# 4. Trigger Windows UAC and run the .bat
# Using cmd /c to run the .bat is the most stable way
$PS_CMD -NoProfile -ExecutionPolicy Bypass -Command \
    "Start-Process cmd -Verb RunAs -ArgumentList '/c \"$BAT_PATH\"'"

echo ""
echo "✅ Request sent!"
echo "👉 Please check the pop-up CMD window, it will automatically call PowerShell."