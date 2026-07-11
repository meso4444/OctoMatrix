#!/bin/bash

# ==============================================================================
# Environment initialization: dynamically locate project root and mount virtual environment (idempotent and compatible with any subdirectory)
# ==============================================================================
if [ -z "$VIRTUAL_ENV" ]; then
    find_project_root() {
        local dir="$1"
        while [ "$dir" != "/" ]; do
            if [ -f "$dir/install_dependencies.sh" ]; then echo "$dir"; return 0; fi
            dir=$(dirname "$dir")
        done
        return 1
    }
    export PROJECT_ROOT=$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")
    if [ -n "$PROJECT_ROOT" ] && [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi
fi

# Copyright 2026 meso4444
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

echo "🔧 Calling Windows PowerShell to setup autostart..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 0. Find powershell.exe path
PS_CMD="powershell.exe"
if ! command -v $PS_CMD &> /dev/null; then
    # Try common Windows paths
    COMMON_PS_PATH="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    if [ -f "$COMMON_PS_PATH" ]; then
        PS_CMD="$COMMON_PS_PATH"
    else
        echo "❌ Error: powershell.exe not found. Please ensure you are in a WSL environment and Windows paths are added to PATH."
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

sed -i 's/$/\r/' "$LAUNCHER_PATH"
BAT_PATH=$(wslpath -w "$LAUNCHER_PATH")

echo "📍 Launcher path: $BAT_PATH"

$PS_CMD -NoProfile -ExecutionPolicy Bypass -Command \
    "Start-Process cmd -Verb RunAs -ArgumentList '/c \"$BAT_PATH\"'"

echo ""
echo "✅ Request sent!"
echo "👉 Please check the new CMD window, it will automatically call PowerShell."