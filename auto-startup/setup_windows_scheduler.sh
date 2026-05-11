#!/bin/bash
echo "🔧 Calling Windows PowerShell to setup autostart..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 0. 尋找 powershell.exe 路徑
PS_CMD="powershell.exe"
if ! command -v $PS_CMD &> /dev/null; then
    # 嘗試常見的 Windows 路徑
    COMMON_PS_PATH="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    if [ -f "$COMMON_PS_PATH" ]; then
        PS_CMD="$COMMON_PS_PATH"
    else
        echo "❌ 錯誤: 找不到 powershell.exe。請確保您在 WSL 環境中且 Windows 路徑已加入 PATH。"
        exit 1
    fi
fi

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

$PS_CMD -NoProfile -ExecutionPolicy Bypass -Command \
    "Start-Process cmd -Verb RunAs -ArgumentList '/c \"$BAT_PATH\"'"

echo "✅ Request sent! Please check the UAC prompt and the new CMD window."