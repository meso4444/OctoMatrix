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

# disable_systemd_octomatrix.sh
# Removes Systemd autostart for OctoMatrix

SERVICE_NAME="octomatrix-services"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run this script using sudo"
  echo "   Example: sudo ./auto-startup/disable_systemd_octomatrix.sh"
  exit 1
fi

echo "🛑 Removing Systemd service: $SERVICE_NAME"

if systemctl is-active --quiet $SERVICE_NAME; then
    echo "   Stopping service..."
    systemctl stop $SERVICE_NAME
fi

if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
    echo "   Disabling autostart..."
    systemctl disable $SERVICE_NAME
fi

if [ -f "$SERVICE_FILE" ]; then
    echo "   Removing config: $SERVICE_FILE"
    rm "$SERVICE_FILE"
    systemctl daemon-reload
    echo "✅ Service fully removed"
else
    echo "⚠️  Config not found, might already be removed"
fi

echo ""
echo "💡 To re-enable, run install_systemd_octomatrix.sh"