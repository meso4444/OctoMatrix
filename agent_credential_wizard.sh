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

# agent_credential_wizard.sh - AI Agent 認證精靈 (通用版)
# 支持本地和容器兩種環境的認證配置

set -e

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
    # 從 config.yaml 獲取 agent 清單
    CONFIG_YAML="$SCRIPT_DIR/config.yaml"
    if [ ! -f "$CONFIG_YAML" ]; then
        echo "❌ 找不到 config.yaml，請先完成系統設定。"
        return
    fi
    
    if ! AGENT_LIST=$(CONFIG_YAML_ENV="$CONFIG_YAML" python3 -c "
import os, yaml
data = yaml.safe_load(open(os.environ['CONFIG_YAML_ENV'])) or {}
for a in data.get('agents', []):
    print(a.get('name', ''))
" 2>&1); then
        echo "❌ 讀取 config.yaml 的 Agent 清單失敗，請確認檔案格式是否正確:"
        echo "$AGENT_LIST"
        return
    fi
    if [ -z "$AGENT_LIST" ]; then
        echo "❌ 目前沒有建立任何 Agent，請先至系統設定新增 Agent。"
        return
    fi
    
    echo "請選擇要認證的 Agent："
    AGENT_ARRAY=()
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            AGENT_ARRAY+=("$line")
        fi
    done <<< "$AGENT_LIST"
    
    for i in "${!AGENT_ARRAY[@]}"; do
        echo "$((i+1))) ${AGENT_ARRAY[$i]}"
    done
    echo "R) 返回 / 退出"
    echo ""
    read -p "請輸入選擇 [1-${#AGENT_ARRAY[@]}, R]: " AGENT_CHOICE
    
    if [[ "$AGENT_CHOICE" =~ ^[Rr]$ ]]; then
        break
    fi
    
    if ! [[ "$AGENT_CHOICE" =~ ^[0-9]+$ ]] || [ "$AGENT_CHOICE" -lt 1 ] || [ "$AGENT_CHOICE" -gt "${#AGENT_ARRAY[@]}" ]; then
        echo "❌ 無效選擇"
        continue
    fi
    
    AGENT_NAME="${AGENT_ARRAY[$((AGENT_CHOICE-1))]}"
    # 用 tr 取代 ${VAR,,}，因為該語法僅 Bash 4+ 支援，macOS 內建 /bin/bash 為 3.2 版會直接報錯退出
    AGENT_USER="agent_$(echo "$AGENT_NAME" | tr '[:upper:]' '[:lower:]')"

    # 確保帳號存在
    if ! id "$AGENT_USER" &>/dev/null; then
        echo "❌ 找不到專屬帳號 $AGENT_USER。請先透過 setup_config 儲存設定以建立帳號。"
        continue
    fi

    # 動態解析實際 Home 目錄 (Linux 為 /home/xxx，macOS 為 /Users/xxx)，避免寫死路徑
    AGENT_HOME_DIR="$(eval echo ~"$AGENT_USER")"

    # 自動判斷引擎 (透過環境變數傳遞 AGENT_NAME/CONFIG_YAML，避免特殊字元break Python字串字面值)
    if ! AGENT_ENGINE=$(AGENT_NAME_ENV="$AGENT_NAME" CONFIG_YAML_ENV="$CONFIG_YAML" python3 -c "
import os, yaml
name = os.environ['AGENT_NAME_ENV']
data = yaml.safe_load(open(os.environ['CONFIG_YAML_ENV'])) or {}
print(next((a.get('engine', 'gemini') for a in data.get('agents', []) if a.get('name', '') == name), 'gemini'))
" 2>&1); then
        echo "⚠️  自動偵測引擎失敗，將使用預設值 gemini。錯誤訊息:"
        echo "$AGENT_ENGINE"
        AGENT_ENGINE="gemini"
    fi

    echo ""
    echo "⚙️  自動偵測引擎: $AGENT_ENGINE"
    # 用 tr 取代 ${VAR,,}，因為該語法僅 Bash 4+ 支援，macOS 內建 /bin/bash 為 3.2 版會直接報錯退出
    AGENT_ENGINE_LOWER=$(echo "$AGENT_ENGINE" | tr '[:upper:]' '[:lower:]')

    if [[ "$AGENT_ENGINE_LOWER" == *"claude"* ]]; then
        echo "🚀 啟動 Claude CLI 認證 (身分: $AGENT_USER)..."
        echo "💡 提示: 完成認證後，憑證將存放在 $AGENT_HOME_DIR/.claude"
        echo ""
        sudo su - "$AGENT_USER" -c "claude --permission-mode bypassPermissions" || true
        echo ""
        echo "✅ Claude 認證完成！"
    elif [[ "$AGENT_ENGINE_LOWER" == *"codex"* ]]; then
        echo "🚀 啟動 Codex CLI 認證 (身分: $AGENT_USER)..."
        echo "💡 提示: 完成認證後，憑證將存放在 $AGENT_HOME_DIR/.codex"
        echo ""
        sudo su - "$AGENT_USER" -c "codex --yolo" || true
        echo ""
        echo "✅ Codex 認證完成！"
    elif [[ "$AGENT_ENGINE_LOWER" == *"agy"* ]] || [[ "$AGENT_ENGINE_LOWER" == *"antigravity"* ]]; then
        echo "🚀 啟動 Antigravity CLI 認證 (身分: $AGENT_USER)..."
        echo "💡 提示: 完成認證後，憑證將存放在 $AGENT_HOME_DIR/.gemini"
        echo ""
        sudo su - "$AGENT_USER" -c "agy --dangerously-skip-permissions" || true
        echo ""
        echo "✅ Antigravity 認證完成！"
    else
        echo "🚀 啟動 Gemini CLI 認證 (身分: $AGENT_USER)..."
        echo "💡 提示: 完成認證後，憑證將存放在 $AGENT_HOME_DIR/.gemini"
        echo ""
        sudo su - "$AGENT_USER" -c "gemini --yolo" || true
        echo ""
        echo "✅ Gemini 認證完成！"
    fi
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
    echo "4) Antigravity (agy)"
    echo "R) 返回 / 退出"
    echo ""
    read -p "請輸入選擇 [1-4, R]: " CLI_CHOICE

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
      4)
        echo ""
        echo "🚀 啟動 Antigravity CLI 認證..."
        echo "📂 認證路徑: $CONTAINER_HOME"
        echo "💡 提示: 認證將存放在 $CONTAINER_HOME/.gemini"
        echo ""
        if HOME="$CONTAINER_HOME" agy --dangerously-skip-permissions; then
          echo ""
          echo "✅ Antigravity 認證完成！"
          echo "📦 憑證已存放至: $CONTAINER_HOME/.gemini"
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