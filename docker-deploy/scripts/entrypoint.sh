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
    echo "🔐 [Root] Fixing ownership and permissions for mounted volumes..."

    # Fix directory permissions scoped to specific instance subdirectory to avoid interference
    if [ -d "$SCRIPT_DIR/agent_home" ]; then
        chown $APP_UID:$APP_GID "$SCRIPT_DIR/agent_home" 2>/dev/null || true

        # Smartly identify the current Agent directory name (capitalized first letter)
        AGENT_DIR=""
        if [ ! -z "$INSTANCE_NAME" ]; then
            AGENT_DIR=$(echo "$INSTANCE_NAME" | awk '{print toupper(substr($0,1,1))tolower(substr($0,2))}')
        elif [ ! -z "$APP_USER" ]; then
            PURE_NAME=${APP_USER#agent_}
            AGENT_DIR=$(echo "$PURE_NAME" | awk '{print toupper(substr($0,1,1))tolower(substr($0,2))}')
        fi

        # Iterate and precisely fix specific agent subdirectories (avoid recursive pollution on toolbox, knowledge, avatar, skillbox, and logs)
        for NAME in "$AGENT_DIR" "$INSTANCE_NAME" "${APP_USER#agent_}"; do
            TARGET_PATH="$SCRIPT_DIR/agent_home/$NAME"
            if [ ! -z "$NAME" ] && [ -d "$TARGET_PATH" ]; then
                echo "🔐 [Root] Precisely fixing permissions for instance directory: agent_home/$NAME"
                # Only chown the agent home directory itself non-recursively
                chown $APP_UID:$APP_GID "$TARGET_PATH" 2>/dev/null || true
                
                # Only recursively chown specific agent-writable subdirectories
                for sub in "my_shared_space" "downloads_temp" "project"; do
                    if [ -d "$TARGET_PATH/$sub" ]; then
                        chown -R $APP_UID:$APP_GID "$TARGET_PATH/$sub" 2>/dev/null || true
                    fi
                done
                
                # Non-recursively chown octo_cyberbrain and its subdirectories itself
                for sub in "octo_cyberbrain" "octo_cyberbrain/ghost" "octo_cyberbrain/shell"; do
                    if [ -d "$TARGET_PATH/$sub" ]; then
                        chown $APP_UID:$APP_GID "$TARGET_PATH/$sub" 2>/dev/null || true
                    fi
                done
                
                # Only chown active log and ghost files to allow Agent writes
                [ -f "$TARGET_PATH/octo_cyberbrain/shell/octo_shell.log" ] && chown $APP_UID:$APP_GID "$TARGET_PATH/octo_cyberbrain/shell/octo_shell.log" 2>/dev/null || true
                [ -f "$TARGET_PATH/octo_cyberbrain/ghost/octo_ghost.json" ] && chown $APP_UID:$APP_GID "$TARGET_PATH/octo_cyberbrain/ghost/octo_ghost.json" 2>/dev/null || true
            fi
        done
    fi

    # Ensure dynamic user home and tmux directory exist and are writable
    if [ ! -d "/home/$APP_USER/.tmux" ]; then
        mkdir -p "/home/$APP_USER/.tmux"
        chown -R $APP_UID:$APP_GID "/home/$APP_USER/.tmux"
        chmod 700 "/home/$APP_USER/.tmux"
    fi

    echo "🔓 [Root] Unlocking core scripts to allow overwriting updates..."
    if [ -f "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" ]; then
        xargs -a "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" chattr -i 2>/dev/null || true
    fi

    echo "✅ Permissions fix and unlock completed"
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

if [ "$(id -u)" = "0" ]; then
    echo "🔒 [Root] Services started, precisely locking system distributed scripts to prevent tampering..."
    if [ -f "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" ]; then
        xargs -a "$SCRIPT_DIR/agent_home/.system_distributed_files.txt" chattr +i 2>/dev/null || true
    fi
fi

echo "🏁 [Entrypoint] Startup sequence completed. Container entering daemon mode."
# Keep container running
tail -f /dev/null
