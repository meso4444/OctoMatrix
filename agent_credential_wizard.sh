#!/bin/bash
# agent_credential_wizard.sh - AI Agent 認證精靈 (通用版)
# 支持本地和容器兩種環境的認證配置

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "🔐 AI Agent 認證精靈 (Credential Wizard)"
echo "=========================================="
echo ""

# 本地環境認證函數
run_local_auth() {
  while true; do
    echo ""
    echo "📍 環境: 本地 (~)"
    echo "🎯 目標: 透過專屬 Linux 帳號進行隔離認證"
    echo ""
    read -p "請輸入要認證的 Agent 名稱 (例如 gupa, 若留空則按 Enter 返回): " AGENT_NAME
    if [ -z "$AGENT_NAME" ]; then break; fi
    AGENT_USER="agent_${AGENT_NAME,,}"
    
    # 確保帳號存在
    if ! id "$AGENT_USER" &>/dev/null; then
        echo "❌ 找不到專屬帳號 $AGENT_USER。請先透過 setup_config 儲存設定以建立帳號。"
        continue
    fi

    echo "請選擇 AI CLI 工具："
    echo "1) Gemini"
    echo "2) Claude"
    echo "3) Codex"
    echo "R) 返回 / 退出"
    echo ""
    read -p "請輸入選擇 [1-3, R]: " CLI_CHOICE

    case "$CLI_CHOICE" in
      1)
        echo ""
        echo "🚀 啟動 Gemini CLI 認證 (身分: $AGENT_USER)..."
        echo "💡 提示: 完成認證後，憑證將存放在 /home/$AGENT_USER/.gemini"
        echo ""
        sudo su - "$AGENT_USER" -c "gemini --yolo" || true
        echo ""
        echo "✅ Gemini 認證完成！"
        ;;
      2)
        echo ""
        echo "🚀 啟動 Claude CLI 認證 (身分: $AGENT_USER)..."
        echo "💡 提示: 完成認證後，憑證將存放在 /home/$AGENT_USER/.claude"
        echo ""
        sudo su - "$AGENT_USER" -c "claude --permission-mode bypassPermissions" || true
        echo ""
        echo "✅ Claude 認證完成！"
        ;;
      3)
        echo ""
        echo "🚀 啟動 Codex CLI 認證 (身分: $AGENT_USER)..."
        echo "💡 提示: 完成認證後，憑證將存放在 /home/$AGENT_USER/.codex"
        echo ""
        sudo su - "$AGENT_USER" -c "codex --yolo" || true
        echo ""
        echo "✅ Codex 認證完成！"
        ;;
      [Rr])
        break
        ;;
      *)
        echo "❌ 無效選擇"
        ;;
    esac
  done
}

# 容器環境認證函數
run_container_auth() {
  local INSTANCE_NAME="$1"

  if [ -z "$INSTANCE_NAME" ]; then
    echo ""
    echo "📍 環境: 容器"
    echo "🎯 目標: 認證存放在容器 instance 目錄"
    echo ""
    echo "💡 命名建議範例："
    echo "   • 技術環境：dev, staging, production, test, sandbox"
    echo "   • 應用場景：travel_planner, investment_advisor, meditation_coach"
    echo "   • 專案代號：gupta, chod, omega, alpha, nexus"
    echo "   • 個人用途：work, hobby, research, learning, experiment"
    echo ""
    read -p "請輸入 instance 名稱: " INSTANCE_NAME

    if [ -z "$INSTANCE_NAME" ]; then
      echo "❌ Instance 名稱不能為空"
      return
    fi
  fi

  # 建立 instance 目錄
  DOCKER_DEPLOY_DIR="$SCRIPT_DIR/docker-deploy"
  CONTAINER_HOME="$DOCKER_DEPLOY_DIR/container_home/$INSTANCE_NAME"

  echo "📁 確保 instance 目錄存在: $CONTAINER_HOME"
  mkdir -p "$CONTAINER_HOME"
  # 確保 container_home 目錄權限正確（比照標準 home 目錄 750）
  chmod 750 "$CONTAINER_HOME" 2>/dev/null || sudo chmod 750 "$CONTAINER_HOME" 2>/dev/null || true

  while true; do
    echo ""
    echo "📍 容器目標: $INSTANCE_NAME ($CONTAINER_HOME)"
    echo "請選擇 AI CLI 工具："
    echo "1) Gemini"
    echo "2) Claude"
    echo "3) Codex"
    echo "R) 返回 / 退出"
    echo ""
    read -p "請輸入選擇 [1-3, R]: " CLI_CHOICE

    case "$CLI_CHOICE" in
      1)
        echo ""
        echo "🚀 啟動 Gemini CLI 認證..."
        echo "📂 認證路徑: $CONTAINER_HOME"
        echo "💡 提示: 認證將存放在 $CONTAINER_HOME/.gemini"
        echo ""
        if HOME="$CONTAINER_HOME" gemini --yolo; then
          echo ""
          echo "✅ Gemini 認證完成！"
          echo "📦 憑證已存放至: $CONTAINER_HOME/.gemini"
        else
          echo ""
          echo "⚠️  認證過程中出現錯誤，請檢查目錄權限"
          echo "   嘗試執行: sudo chmod 777 $CONTAINER_HOME"
        fi
        ;;
      2)
        echo ""
        echo "🚀 啟動 Claude CLI 認證..."
        echo "📂 認證路徑: $CONTAINER_HOME"
        echo "💡 提示: 認證將存放在 $CONTAINER_HOME/.claude"
        echo ""
        if HOME="$CONTAINER_HOME" claude --permission-mode bypassPermissions; then
          echo ""
          echo "✅ Claude 認證完成！"
          echo "📦 憑證已存放至: $CONTAINER_HOME/.claude"
        else
          echo ""
          echo "⚠️  認證過程中出現錯誤，請檢查目錄權限"
          echo "   嘗試執行: sudo chmod 777 $CONTAINER_HOME"
        fi
        ;;
      3)
        echo ""
        echo "🚀 啟動 Codex CLI 認證..."
        echo "📂 認證路徑: $CONTAINER_HOME"
        echo "💡 提示: 認證將存放在 $CONTAINER_HOME/.codex"
        echo ""
        if HOME="$CONTAINER_HOME" codex --yolo; then
          echo ""
          echo "✅ Codex 認證完成！"
          echo "📦 憑證已存放至: $CONTAINER_HOME/.codex"
        else
          echo ""
          echo "⚠️  認證過程中出現錯誤，請檢查目錄權限"
          echo "   嘗試執行: sudo chmod 777 $CONTAINER_HOME"
        fi
        ;;
      [Rr])
        break
        ;;
      *)
        echo "❌ 無效選擇"
        ;;
    esac
  done
}

# 根據參數決定執行模式
if [ "$1" == "--local" ]; then
  run_local_auth
elif [ "$1" == "--container" ]; then
  if [ -n "$2" ]; then
    run_container_auth "$2"
  else
    run_container_auth ""
  fi
else
  # 互動模式
  while true; do
    echo ""
    echo "請選擇執行環境："
    echo "1) 本地環境 (Local)"
    echo "2) 容器環境 (Container)"
    echo "Q) 離開精靈 (Quit)"
    echo ""
    read -p "請輸入選擇 [1, 2, Q]: " ENV_CHOICE

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
        echo "❌ 無效選擇"
        ;;
    esac
  done
fi

echo ""
echo "=========================================="
echo "🎉 認證精靈執行完成！"
echo "=========================================="
echo ""