#!/bin/bash
# setup_systemd.sh
# 自動將 OctoMatrix 註冊為 Systemd 服務，實現開機自啟

# 1. 準備路徑與變數
# 指向專案根目錄
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
START_SCRIPT="$SCRIPT_DIR/start_octo_services.sh"
STOP_SCRIPT="$SCRIPT_DIR/stop_octo_services.sh"
SERVICE_NAME="octomatrix-services"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# 偵測真實用戶 (避免 sudo 執行時變成 root)
REAL_USER=${SUDO_USER:-$(whoami)}
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

# 檢查 root 權限
if [ "$EUID" -ne 0 ]; then
  echo "❌ 請使用 sudo 執行此腳本 (因為需要寫入 /etc/systemd/system)"
  echo "   範例: sudo ./auto-startup/install_systemd_octomatrix.sh"
  exit 1
fi

echo "🔧 正在配置 Systemd 服務..."
echo "   - 服務名稱: $SERVICE_NAME"
echo "   - 執行用戶: $REAL_USER"
echo "   - 啟動腳本: $START_SCRIPT"

# 2. 建立 Service 檔案
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=OctoMatrix - AI Remote Commander
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$START_SCRIPT
ExecStop=$STOP_SCRIPT
Restart=always
RestartSec=10
RemainAfterExit=yes
Environment="HOME=$USER_HOME"
Environment="PATH=$PATH"
Environment="TERM=xterm-256color"

[Install]
WantedBy=multi-user.target
EOF

echo "✅ 服務檔案已建立: $SERVICE_FILE"

# 3. 啟用服務
echo "🔄 正在啟用服務..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# 4. 檢查 WSL Systemd 支援
if grep -qi "Microsoft" /proc/version; then
    echo "🔍 檢測到 WSL 環境，正在檢查 systemd 設定..."
    WSL_CONF="/etc/wsl.conf"
    
    # 檢查檔案是否存在，若無則建立
    if [ ! -f "$WSL_CONF" ]; then
        echo "   建立新的 $WSL_CONF..."
        touch "$WSL_CONF"
    fi

    # 檢查是否已設定 systemd=true
    if ! grep -q "systemd=true" "$WSL_CONF"; then
        echo "🔧 正在啟用 WSL Systemd 支援..."
        
        # 確保 [boot] 區塊存在
        if ! grep -q "\[boot\]" "$WSL_CONF"; then
            echo -e "\n[boot]" | tee -a "$WSL_CONF" > /dev/null
        fi
        
        # 加入 systemd=true
        echo "systemd=true" | tee -a "$WSL_CONF" > /dev/null
        
        echo "✅ 已更新 $WSL_CONF"
        echo "⚠️  重要提示：您必須完全重啟 WSL 才能使 Systemd 生效！"
        echo "   請在 Windows PowerShell 執行: wsl --shutdown"
        echo "   然後重新進入 Ubuntu。"
    else
        echo "✅ WSL Systemd 設定已存在 ($WSL_CONF)"
    fi
fi

echo "✅ 開機自啟已啟用！"
echo ""
echo "👉 您現在可以使用以下指令管理服務："
echo "   sudo systemctl start $SERVICE_NAME"
echo "   sudo systemctl stop $SERVICE_NAME"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "📝 下一步 (Windows 用戶):"
echo "   請執行 ./auto-startup/setup_windows_scheduler.sh 設定宿主機喚醒排程。"