#!/bin/bash
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

# ============================================================================
# OctoMatrix - [Entrypoint] Lean Delegation Version (Using gosu for de-escalation)
# ============================================================================
set -e

echo "🧬 [Entrypoint] Container awakening..."

# 1. Environment variable preparation
export SCRIPT_DIR="/app/octomatrix"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Fallback to appuser if APP_USER is not set
export APP_USER=${APP_USER:-appuser}
export APP_UID=$(id -u $APP_USER 2>/dev/null || echo 1000)
export APP_GID=$(id -g $APP_USER 2>/dev/null || echo 1000)

# 2. Fix permissions on mounted volumes as root (One-time initialization)
if [ "$(id -u)" = "0" ]; then
    echo "🔐 [Root] Initializing container internal user environment..."

    # Ensure dynamic user home and tmux directory exist and are writable
    if [ ! -d "/home/$APP_USER/.tmux" ]; then
        mkdir -p "/home/$APP_USER/.tmux"
        chown -R $APP_UID:$APP_GID "/home/$APP_USER/.tmux"
        chmod 700 "/home/$APP_USER/.tmux"
    fi

    echo "✅ Container internal environment initialization completed"
fi

# 3. Use gosu to switch to the dynamic user and execute the startup script
# This ensures the container runs as a non-root user throughout
cd "$SCRIPT_DIR"

if [ -f "./start_octo_services.sh" ]; then
    echo "🚀 Using gosu to switch to user $APP_USER and execute startup script..."
    # Ensure HOME variable points to the home directory inside the container
    export HOME="/home/$APP_USER"
    gosu $APP_USER bash ./start_octo_services.sh
else
    echo "❌ Fatal Error: Could not find /app/octomatrix/start_octo_services.sh"
    exit 1
fi



echo "🏁 [Entrypoint] Startup sequence completed. Container entering daemon mode."
# Keep container running
tail -f /dev/null
