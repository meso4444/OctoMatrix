#!/bin/bash

# ==============================================================================
# 環境初始化：動態定位專案根目錄並掛載虛擬環境 (冪等且相容任意子目錄)
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

# setup_mac_launchd.sh - Configure Mac Auto-Startup for OctoMatrix

echo "=========================================="
echo "🍏 OctoMatrix - Mac Auto-Startup Setup (Launchd)"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OCTO_DIR="$(dirname "$SCRIPT_DIR")"
START_SCRIPT="$OCTO_DIR/start_octo_services.sh"

if [ ! -f "$START_SCRIPT" ]; then
    echo "❌ Error: Startup script not found at $START_SCRIPT"
    exit 1
fi

PLIST_NAME="com.octomatrix.agent.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

# Ensure the target script has execution permissions
chmod +x "$START_SCRIPT"

echo "📂 Project Root: $OCTO_DIR"
echo "📝 Generating config file: $PLIST_PATH"

mkdir -p "$HOME/Library/LaunchAgents"

cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.octomatrix.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$START_SCRIPT</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/mac_autostart.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/mac_autostart_error.log</string>
</dict>
</plist>
EOF

echo "✅ Configuration file generated successfully."

echo "🔄 Registering to system Launchd..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "🎉 Setup complete! OctoMatrix will now start automatically when you log into your Mac."
echo "👉 To disable auto-startup, run: launchctl unload $PLIST_PATH"
echo "=========================================="