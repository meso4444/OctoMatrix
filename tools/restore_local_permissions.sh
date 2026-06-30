#!/bin/bash
# Copyright 2026 meso4444
# OctoMatrix - Local Agent Permission Precision Recovery Tool
# Used for disaster recovery when container permissions pollute host filesystem.

# 1. Ensure run as root
if [ "$(id -u)" != "0" ]; then
   echo "❌ This script must be executed with sudo or as root!"
   exit 1
fi

# 2. Dynamically identify the manager user (original user running sudo)
MANAGER_USER=${SUDO_USER:-$(whoami)}
MANAGER_GROUP=$(id -gn "$MANAGER_USER" 2>/dev/null || echo "$MANAGER_USER")

if [ "$MANAGER_USER" = "root" ]; then
    echo "⚠️ Warning: You ran this script directly as root. Unable to auto-detect manager user."
    read -p "Please enter the main host administrator username (e.g. kenzan): " MANAGER_USER
    MANAGER_GROUP=$(id -gn "$MANAGER_USER" 2>/dev/null || echo "$MANAGER_USER")
fi

# 3. Dynamically identify agent_home directory path
# Use the first argument if provided, otherwise locate relative to the script location
AGENT_HOME_DIR="$1"
if [ -z "$AGENT_HOME_DIR" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -d "$SCRIPT_DIR/../agent_home" ]; then
        AGENT_HOME_DIR="$(cd "$SCRIPT_DIR/../agent_home" && pwd)"
    elif [ -d "$SCRIPT_DIR/agent_home" ]; then
        AGENT_HOME_DIR="$(cd "$SCRIPT_DIR/agent_home" && pwd)"
    else
        # Try to search upwards in parent directories
        if [[ "$SCRIPT_DIR" == *"/agent_home/"* ]]; then
            AGENT_HOME_DIR="${SCRIPT_DIR%/agent_home/*}/agent_home"
        else
            echo "ℹ️  Unable to automatically locate agent_home directory."
            read -p "Please enter the absolute path to the agent_home directory: " AGENT_HOME_DIR
        fi
    fi
fi

# Strip trailing slash
AGENT_HOME_DIR="${AGENT_HOME_DIR%/}"

if [ ! -d "$AGENT_HOME_DIR" ]; then
    echo "❌ Error: Directory [$AGENT_HOME_DIR] not found!"
    exit 1
fi

echo "🔐 Starting host permission and ownership recovery for all instances..."
echo "📍 agent_home path: $AGENT_HOME_DIR"
echo "👤 Host administrator account: $MANAGER_USER:$MANAGER_GROUP"

# Fix the base directory ownership (non-recursive, owned by manager, permission 755)
chown "$MANAGER_USER:$MANAGER_GROUP" "$AGENT_HOME_DIR"
chmod 755 "$AGENT_HOME_DIR"

# 4. Iterate over all subdirectories under agent_home and match with host accounts
for TARGET_PATH in "$AGENT_HOME_DIR"/*; do
    if [ -d "$TARGET_PATH" ]; then
        AGENT_DIR="$(basename "$TARGET_PATH")"
        
        # Smart mapping: convert directory to lower case and prepend "agent_"
        # E.g. Aleister -> agent_aleister, Dapa -> agent_dapa
        DIR_LOWER=$(echo "$AGENT_DIR" | tr '[:upper:]' '[:lower:]')
        USER_NAME="agent_$DIR_LOWER"
        
        # Check if the matched user exists in the host system
        if id "$USER_NAME" >/dev/null 2>&1; then
            echo "⚡ Rebuilding isolation boundaries for instance [$AGENT_DIR] -> user [$USER_NAME]..."
            
            # A. Restore main instance directory permissions (owned by manager, 1777 isolation)
            chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH"
            chmod 1777 "$TARGET_PATH"

            # B. Subdirectory permissions (directories themselves remain owned by manager)
            for d in "toolbox" "knowledge" "avatar" "avatar/emojis"; do
                if [ -d "$TARGET_PATH/$d" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/$d"
                    if [[ "$d" == "avatar"* ]]; then
                        chmod 755 "$TARGET_PATH/$d"
                    else
                        chmod 1777 "$TARGET_PATH/$d"
                    fi
                fi
            done

            # - skillbox/ directory (Immutable, remove all write permissions)
            if [ -d "$TARGET_PATH/skillbox" ]; then
                chown -R "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/skillbox"
                chmod -R a-w,a+rX "$TARGET_PATH/skillbox" 2>/dev/null || true
            fi

            # - Agent writable directories (directories themselves remain owned by manager, 1777; only files inside are owned by agent)
            for d in "my_shared_space" "downloads_temp" "project"; do
                if [ -d "$TARGET_PATH/$d" ]; then
                    # Recursively chown only the internal items
                    find "$TARGET_PATH/$d" -mindepth 1 -maxdepth 1 | while read -r item; do
                        chown -R "$USER_NAME:$USER_NAME" "$item" 2>/dev/null || true
                    done
                    # Recover directory itself back to manager, 1777
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/$d"
                    chmod 1777 "$TARGET_PATH/$d"
                fi
            done

            # C. Lock down Safe Copy files (immutable system protection)
            echo "   🔒 Locking system configuration files and distribution templates..."

            # - System rules and templates (644)
            for f in "agent_home_rules.md" "AGENT_PROTOCOL.md" "agent_rule_gen_template.txt"; do
                if [ -f "$TARGET_PATH/$f" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/$f"
                    chmod 644 "$TARGET_PATH/$f"
                fi
            done

            # - Toolbox executables (755)
            for f in "matrix_notifier.py" "agent_intercom.py" "awake_task_manager.py" "octo_generator.py"; do
                if [ -f "$TARGET_PATH/toolbox/$f" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/toolbox/$f"
                    chmod 755 "$TARGET_PATH/toolbox/$f"
                fi
            done

            # - Knowledge bases (644)
            for f in "AGENT_AVATAR_GUIDE.md" "AWAKE_FUNCTIONALITY.md"; do
                if [ -f "$TARGET_PATH/knowledge/$f" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/knowledge/$f"
                    chmod 644 "$TARGET_PATH/knowledge/$f"
                fi
            done

            # - Hidden environment config file (644)
            if [ -f "$TARGET_PATH/octo_cyberbrain/.cyberbrain_env" ]; then
                chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/octo_cyberbrain/.cyberbrain_env"
                chmod 644 "$TARGET_PATH/octo_cyberbrain/.cyberbrain_env"
            fi

            # - Direct cyberbrain control scripts (py: 755, md/others: 644)
            if [ -d "$TARGET_PATH/octo_cyberbrain" ]; then
                find "$TARGET_PATH/octo_cyberbrain" -maxdepth 1 -type f | while read -r f; do
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$f"
                    if [[ "$f" == *.py ]]; then
                        chmod 755 "$f"
                    else
                        chmod 644 "$f"
                    fi
                done
            fi
            
            # D. Audit Log & Snapshot Protection Locks (Read-only locks)
            # - Directories themselves (1777)
            for dir in "octo_cyberbrain" "octo_cyberbrain/ghost" "octo_cyberbrain/shell"; do
                if [ -d "$TARGET_PATH/$dir" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/$dir"
                    chmod 1777 "$TARGET_PATH/$dir"
                fi
            done

            # - Historical .zst log archives (644)
            if [ -d "$TARGET_PATH/octo_cyberbrain/shell" ]; then
                find "$TARGET_PATH/octo_cyberbrain/shell" -type f -name "*.zst" | while read -r f; do
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$f"
                    chmod 644 "$f"
                done
            fi

            # - Historical .json snapshot archives (644)
            if [ -d "$TARGET_PATH/octo_cyberbrain/ghost" ]; then
                find "$TARGET_PATH/octo_cyberbrain/ghost" -type f -name "*.json" ! -name "octo_ghost.json" | while read -r f; do
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$f"
                    chmod 644 "$f"
                done
            fi

            # - Active logs and ghost status (owned by Agent for appending writes)
            [ -f "$TARGET_PATH/octo_cyberbrain/shell/octo_shell.log" ] && chown "$USER_NAME:$USER_NAME" "$TARGET_PATH/octo_cyberbrain/shell/octo_shell.log" 2>/dev/null || true
            [ -f "$TARGET_PATH/octo_cyberbrain/ghost/octo_ghost.json" ] && chown "$USER_NAME:$USER_NAME" "$TARGET_PATH/octo_cyberbrain/ghost/octo_ghost.json" 2>/dev/null || true

            # E. Lock .system_distributed_files.txt manifest if it exists (644)
            DIST_LIST="$TARGET_PATH/.system_distributed_files.txt"
            if [ -f "$DIST_LIST" ]; then
                chown "$MANAGER_USER:$MANAGER_GROUP" "$DIST_LIST"
                chmod 644 "$DIST_LIST"
            fi
            echo "   ✓ Successfully secured Safe Copy, environment configuration, and audit logs."
        fi
    fi
done

echo "✅ Host permission recovery completed successfully!"
