#!/bin/bash
# agent_credential_wizard.sh - AI Agent Credential Wizard (universal version)
# Support authentication configuration for both local and container environments

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "🔐 AI Agent Credential Wizard"
echo "=========================================="
echo ""

# Local environment authentication function
run_local_auth() {
  while true; do
    echo ""
    echo "📍 Environment: Local (~)"
    echo "🎯 Target: Isolated authentication via dedicated Linux account"
    echo ""
    # 從 config.yaml 獲取 agent 清單
    CONFIG_YAML="$SCRIPT_DIR/config.yaml"
    if [ ! -f "$CONFIG_YAML" ]; then
        echo "❌ Cannot find config.yaml. Please complete system setup first."
        return
    fi
    
    AGENT_LIST=$(python3 -c "import yaml; [print(a.get('name', '')) for a in yaml.safe_load(open('$CONFIG_YAML')).get('agents', [])]" 2>/dev/null)
    if [ -z "$AGENT_LIST" ]; then
        echo "❌ No Agents found. Please add Agents in system setup first."
        return
    fi
    
    echo "Please select an Agent to authenticate:"
    AGENT_ARRAY=()
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            AGENT_ARRAY+=("$line")
        fi
    done <<< "$AGENT_LIST"
    
    for i in "${!AGENT_ARRAY[@]}"; do
        echo "$((i+1))) ${AGENT_ARRAY[$i]}"
    done
    echo "R) Return / Exit"
    echo ""
    read -p "Please enter choice [1-${#AGENT_ARRAY[@]}, R]: " AGENT_CHOICE
    
    if [[ "$AGENT_CHOICE" =~ ^[Rr]$ ]]; then
        break
    fi
    
    if ! [[ "$AGENT_CHOICE" =~ ^[0-9]+$ ]] || [ "$AGENT_CHOICE" -lt 1 ] || [ "$AGENT_CHOICE" -gt "${#AGENT_ARRAY[@]}" ]; then
        echo "❌ Invalid choice"
        continue
    fi
    
    AGENT_NAME="${AGENT_ARRAY[$((AGENT_CHOICE-1))]}"
    AGENT_USER="agent_${AGENT_NAME,,}"
    
    # Check if user exists
    if ! id "$AGENT_USER" &>/dev/null; then
        echo "❌ Cannot find dedicated account $AGENT_USER. Please save settings in setup_config first to create the account."
        continue
    fi

    # Auto-detect engine
    AGENT_ENGINE=$(python3 -c "import yaml; print(next((a.get('engine', 'gemini') for a in yaml.safe_load(open('$CONFIG_YAML')).get('agents', []) if a.get('name', '') == '$AGENT_NAME'), 'gemini'))" 2>/dev/null)
    
    echo ""
    echo "⚙️  Auto-detected engine: $AGENT_ENGINE"
    
    if [[ "${AGENT_ENGINE,,}" == *"claude"* ]]; then
        echo "🚀 Starting Claude CLI authentication (Identity: $AGENT_USER)..."
        echo "💡 Tip: After authentication, credentials will be stored in /home/$AGENT_USER/.claude"
        echo ""
        sudo su - "$AGENT_USER" -c "claude --permission-mode bypassPermissions" || true
        echo ""
        echo "✅ Claude authentication complete!"
    elif [[ "${AGENT_ENGINE,,}" == *"codex"* ]]; then
        echo "🚀 Starting Codex CLI authentication (Identity: $AGENT_USER)..."
        echo "💡 Tip: After authentication, credentials will be stored in /home/$AGENT_USER/.codex"
        echo ""
        sudo su - "$AGENT_USER" -c "codex --yolo" || true
        echo ""
        echo "✅ Codex authentication complete!"
    elif [[ "${AGENT_ENGINE,,}" == *"agy"* ]] || [[ "${AGENT_ENGINE,,}" == *"antigravity"* ]]; then
        echo "🚀 Starting Antigravity CLI authentication (Identity: $AGENT_USER)..."
        echo "💡 Tip: After authentication, credentials will be stored in /home/$AGENT_USER/.gemini"
        echo ""
        sudo su - "$AGENT_USER" -c "agy --dangerously-skip-permissions" || true
        echo ""
        echo "✅ Antigravity authentication complete!"
    else
        echo "🚀 Starting Gemini CLI authentication (Identity: $AGENT_USER)..."
        echo "💡 Tip: After authentication, credentials will be stored in /home/$AGENT_USER/.gemini"
        echo ""
        sudo su - "$AGENT_USER" -c "gemini --yolo" || true
        echo ""
        echo "✅ Gemini authentication complete!"
    fi
  done
}

# Container environment authentication function
run_container_auth() {
  local INSTANCE_NAME="$1"

  if [ -z "$INSTANCE_NAME" ]; then
    echo ""
    echo "📍 Environment: Container"
    echo "🎯 Target: Authenticate credentials stored in container instance directory"
    echo ""
    echo "💡 Naming suggestion examples:"
    echo "   • Technical environments: dev, staging, production, test, sandbox"
    echo "   • Application scenarios: travel_planner, investment_advisor, meditation_coach"
    echo "   • Project codes: gupta, chod, omega, alpha, nexus"
    echo "   • Personal use: work, hobby, research, learning, experiment"
    echo ""
    read -p "Please enter instance name: " INSTANCE_NAME

    if [ -z "$INSTANCE_NAME" ]; then
      echo "❌ Instance name cannot be empty"
      return
    fi
  fi

  # Create instance directory
  DOCKER_DEPLOY_DIR="$SCRIPT_DIR/docker-deploy"
  CONTAINER_HOME="$DOCKER_DEPLOY_DIR/container_home/$INSTANCE_NAME"

  echo "📁 Ensuring instance directory exists: $CONTAINER_HOME"
  mkdir -p "$CONTAINER_HOME"
  # Ensure container_home directory permissions are correct (matching standard home directory 750)
  chmod 750 "$CONTAINER_HOME" 2>/dev/null || sudo chmod 750 "$CONTAINER_HOME" 2>/dev/null || true

  while true; do
    echo ""
    echo "📍 Container target: $INSTANCE_NAME ($CONTAINER_HOME)"
    echo "Please select AI CLI tool:"
    echo "1) Gemini"
    echo "2) Claude"
    echo "3) Codex"
    echo "4) Antigravity (agy)"
    echo "R) Return / Exit"
    echo ""
    read -p "Please enter your choice [1-4, R]: " CLI_CHOICE

    case "$CLI_CHOICE" in
      1)
        echo ""
        echo "🚀 Starting Gemini CLI authentication..."
        echo "📂 Authentication path: $CONTAINER_HOME"
        echo "💡 Tip: Authentication will be stored in $CONTAINER_HOME/.gemini"
        echo ""
        if HOME="$CONTAINER_HOME" gemini --yolo; then
          echo ""
          echo "✅ Gemini authentication completed!"
          echo "📦 Credentials stored at: $CONTAINER_HOME/.gemini"
        else
          echo ""
          echo "⚠️  Error occurred during authentication, please check directory permissions"
          echo "   Try running: sudo chmod 777 $CONTAINER_HOME"
        fi
        ;;
      2)
        echo ""
        echo "🚀 Starting Claude CLI authentication..."
        echo "📂 Authentication path: $CONTAINER_HOME"
        echo "💡 Tip: Authentication will be stored in $CONTAINER_HOME/.claude"
        echo ""
        if HOME="$CONTAINER_HOME" claude --permission-mode bypassPermissions; then
          echo ""
          echo "✅ Claude authentication completed!"
          echo "📦 Credentials stored at: $CONTAINER_HOME/.claude"
        else
          echo ""
          echo "⚠️  Error occurred during authentication, please check directory permissions"
          echo "   Try running: sudo chmod 777 $CONTAINER_HOME"
        fi
        ;;
      3)
        echo ""
        echo "🚀 Starting Codex CLI authentication..."
        echo "📂 Authentication path: $CONTAINER_HOME"
        echo "💡 Tip: Authentication will be stored in $CONTAINER_HOME/.codex"
        echo ""
        if HOME="$CONTAINER_HOME" codex --yolo; then
          echo ""
          echo "✅ Codex authentication completed!"
          echo "📦 Credentials stored at: $CONTAINER_HOME/.codex"
        else
          echo ""
          echo "⚠️  Error occurred during authentication, please check directory permissions"
          echo "   Try running: sudo chmod 777 $CONTAINER_HOME"
        fi
        ;;
      4)
        echo ""
        echo "🚀 Starting Antigravity CLI authentication..."
        echo "📂 Auth path: $CONTAINER_HOME"
        echo "💡 Hint: Credentials will be stored in $CONTAINER_HOME/.gemini"
        echo ""
        if HOME="$CONTAINER_HOME" agy --dangerously-skip-permissions; then
          echo ""
          echo "✅ Antigravity authentication complete!"
          echo "📦 Credentials stored at: $CONTAINER_HOME/.gemini"
        else
          echo ""
          echo "⚠️  Error occurred during authentication, please check directory permissions"
          echo "   Try running: sudo chmod 777 $CONTAINER_HOME"
        fi
        ;;
      [Rr])
        break
        ;;
      *)
        echo "❌ Invalid choice"
        ;;
    esac
  done
}

# Determine execution mode based on arguments
if [ "$1" == "--local" ]; then
  run_local_auth
elif [ "$1" == "--container" ]; then
  if [ -n "$2" ]; then
    run_container_auth "$2"
  else
    run_container_auth ""
  fi
else
  # Interactive mode
  while true; do
    echo ""
    echo "Please select execution environment:"
    echo "1) Local Environment (Local)"
    echo "2) Container Environment (Container)"
    echo "Q) Exit Wizard (Quit)"
    echo ""
    read -p "Please enter your choice [1, 2, Q]: " ENV_CHOICE

    case "$ENV_CHOICE" in
      1)
        run_local_auth
        ;;
      2)
        run_container_auth ""
        ;;
      [Qq])
        break
        ;;
      *)
        echo "❌ Invalid choice"
        ;;
    esac
  done
fi

echo ""
echo "=========================================="
echo "🎉 Credential Wizard execution completed!"
echo "=========================================="
echo ""