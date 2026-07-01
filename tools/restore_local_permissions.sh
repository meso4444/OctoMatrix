#!/bin/bash
# Copyright 2026 meso4444
# OctoMatrix - Local Agent Permission Precision Recovery Tool
# Used for disaster recovery when container permissions pollute host filesystem.

# 1. 確保以 root 身份執行
if [ "$(id -u)" != "0" ]; then
   echo "❌ 此腳本必須使用 sudo 或以 root 身份執行！"
   exit 1
fi

# 2. 動態識別管理員用戶名 (執行 sudo 的原始用戶)
MANAGER_USER=${SUDO_USER:-$(whoami)}
MANAGER_GROUP=$(id -gn "$MANAGER_USER" 2>/dev/null || echo "$MANAGER_USER")

if [ "$MANAGER_USER" = "root" ]; then
    echo "⚠️ 警告: 您直接以 root 登入執行，無法自動探測原始管理員用戶。"
    read -p "請輸入宿主機的主要管理員用戶名 (例如 kenzan): " MANAGER_USER
    MANAGER_GROUP=$(id -gn "$MANAGER_USER" 2>/dev/null || echo "$MANAGER_USER")
fi

# 3. 動態識別 agent_home 目錄路徑
# 優先使用第一個參數，若未傳入，則嘗試從腳本所在位置自動定位
AGENT_HOME_DIR="$1"
if [ -z "$AGENT_HOME_DIR" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -d "$SCRIPT_DIR/../agent_home" ]; then
        AGENT_HOME_DIR="$(cd "$SCRIPT_DIR/../agent_home" && pwd)"
    elif [ -d "$SCRIPT_DIR/agent_home" ]; then
        AGENT_HOME_DIR="$(cd "$SCRIPT_DIR/agent_home" && pwd)"
    else
        # 嘗試在當前目錄的父層或祖父層尋找
        if [[ "$SCRIPT_DIR" == *"/agent_home/"* ]]; then
            AGENT_HOME_DIR="${SCRIPT_DIR%/agent_home/*}/agent_home"
        else
            echo "ℹ️  無法自動定位 agent_home 目錄。"
            read -p "請輸入 agent_home 目錄的絕對路徑: " AGENT_HOME_DIR
        fi
    fi
fi

# 去除路徑結尾的斜線
AGENT_HOME_DIR="${AGENT_HOME_DIR%/}"

if [ ! -d "$AGENT_HOME_DIR" ]; then
    echo "❌ 錯誤: 找不到目錄 [$AGENT_HOME_DIR]"
    exit 1
fi

echo "🔐 開始精準修復 Local 各實例之安全權限與擁有權..."
echo "📍 agent_home 目錄: $AGENT_HOME_DIR"
echo "👤 宿主機管理員帳戶: $MANAGER_USER:$MANAGER_GROUP"

# 修復頂層目錄 (非遞迴，保持管理者擁有，權限 755)
chown "$MANAGER_USER:$MANAGER_GROUP" "$AGENT_HOME_DIR"
chmod 755 "$AGENT_HOME_DIR"

# 4. 遍歷 agent_home 下的所有子目錄，動態匹配 Agent 用戶
for TARGET_PATH in "$AGENT_HOME_DIR"/*; do
    if [ -d "$TARGET_PATH" ]; then
        AGENT_DIR="$(basename "$TARGET_PATH")"
        
        # 智慧命名對照：將目錄名轉小寫並拼裝 "agent_" 前綴
        # 例如: Aleister -> agent_aleister, Dapa -> agent_dapa
        DIR_LOWER=$(echo "$AGENT_DIR" | tr '[:upper:]' '[:lower:]')
        USER_NAME="agent_$DIR_LOWER"
        
        # 檢查該用戶在宿主機 Local 系統中是否存在
        if id "$USER_NAME" >/dev/null 2>&1; then
            echo "⚡ 正在重整實例 [$AGENT_DIR] -> 用戶 [$USER_NAME] 的隔離防線..."
            
            # A. 恢復工作區主目錄權限與所有權 (管理者擁有，1777 隔離)
            chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH"
            chmod 1777 "$TARGET_PATH"

            # B. 子目錄權限與擁有人重設 (目錄本身為管理者擁有)
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

            # - 技能目錄 (Immutable，移除所有人寫入權限)
            if [ -d "$TARGET_PATH/skillbox" ]; then
                chown -R "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/skillbox"
                chmod -R a-w,a+rX "$TARGET_PATH/skillbox" 2>/dev/null || true
            fi

            # - Agent 可寫目錄 (目錄本身為管理者擁有；僅內部檔案歸 Agent 擁有)
            for d in "my_shared_space" "downloads_temp" "project"; do
                if [ -d "$TARGET_PATH/$d" ]; then
                    # 僅遞迴 chown 目錄內部的檔案
                    find "$TARGET_PATH/$d" -mindepth 1 -maxdepth 1 | while read -r item; do
                        chown -R "$USER_NAME:$USER_NAME" "$item" 2>/dev/null || true
                    done
                    # 目錄本身收歸管理員所有，維持 1777
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/$d"
                    chmod 1777 "$TARGET_PATH/$d"
                fi
            done

            # C. 精準修復安全分發核心腳本 (Safe Copy 保護)
            echo "   🔒 正在鎖定安全分發 (Safe Copy) 與環境安全鎖..."

            # - 工作目錄下的系統規則與範本 (644)
            for f in "agent_home_rules.md" "AGENT_PROTOCOL.md" "agent_rule_gen_template.txt"; do
                if [ -f "$TARGET_PATH/$f" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/$f"
                    chmod 644 "$TARGET_PATH/$f"
                fi
            done

            # - toolbox/ 中的核心監控與發送工具 (755)
            for f in "matrix_notifier.py" "agent_intercom.py" "awake_task_manager.py" "octo_generator.py"; do
                if [ -f "$TARGET_PATH/toolbox/$f" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/toolbox/$f"
                    chmod 755 "$TARGET_PATH/toolbox/$f"
                fi
            done

            # - knowledge/ 中的核心規範文檔 (644)
            for f in "AGENT_AVATAR_GUIDE.md" "AWAKE_FUNCTIONALITY.md"; do
                if [ -f "$TARGET_PATH/knowledge/$f" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/knowledge/$f"
                    chmod 644 "$TARGET_PATH/knowledge/$f"
                fi
            done

            # - octo_cyberbrain/ 中的隱藏環境變數檔案 (644)
            if [ -f "$TARGET_PATH/octo_cyberbrain/.cyberbrain_env" ]; then
                chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/octo_cyberbrain/.cyberbrain_env"
                chmod 644 "$TARGET_PATH/octo_cyberbrain/.cyberbrain_env"
            fi

            # - octo_cyberbrain/ 中的核心 Ghost/Shell 控制腳本 (py: 755, md/others: 644)
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
            
            # D. 歷史日誌與歷史快照安全鎖定 (防竄改與防銷毀審計防線)
            # - ghost/ 與 shell/ 目錄以及 octo_cyberbrain 本身 (1777)
            for dir in "octo_cyberbrain" "octo_cyberbrain/ghost" "octo_cyberbrain/shell"; do
                if [ -d "$TARGET_PATH/$dir" ]; then
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$TARGET_PATH/$dir"
                    chmod 1777 "$TARGET_PATH/$dir"
                fi
            done

            # - 歷史 .zst 壓縮日誌包 (644)
            if [ -d "$TARGET_PATH/octo_cyberbrain/shell" ]; then
                find "$TARGET_PATH/octo_cyberbrain/shell" -type f -name "*.zst" | while read -r f; do
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$f"
                    chmod 644 "$f"
                done
            fi

            # - 歷史快照 .json (644)
            if [ -d "$TARGET_PATH/octo_cyberbrain/ghost" ]; then
                find "$TARGET_PATH/octo_cyberbrain/ghost" -type f -name "*.json" ! -name "octo_ghost.json" | while read -r f; do
                    chown "$MANAGER_USER:$MANAGER_GROUP" "$f"
                    chmod 644 "$f"
                done
            fi

            # - 活動日誌：擁有者為 Agent 帳戶，只有 Owner 可寫 (644)
            if [ -f "$TARGET_PATH/octo_cyberbrain/shell/octo_shell.log" ]; then
                chown "$USER_NAME:$USER_NAME" "$TARGET_PATH/octo_cyberbrain/shell/octo_shell.log" 2>/dev/null || true
                chmod 644 "$TARGET_PATH/octo_cyberbrain/shell/octo_shell.log" 2>/dev/null || true
            fi
            # - 活動 Ghost JSON：擁有者為 Agent 帳戶，Others 可寫 (646) 供 updater 調用寫入
            if [ -f "$TARGET_PATH/octo_cyberbrain/ghost/octo_ghost.json" ]; then
                chown "$USER_NAME:$USER_NAME" "$TARGET_PATH/octo_cyberbrain/ghost/octo_ghost.json" 2>/dev/null || true
                chmod 646 "$TARGET_PATH/octo_cyberbrain/ghost/octo_ghost.json" 2>/dev/null || true
            fi

            # E. 額外修復並鎖定 .system_distributed_files.txt 清單檔 (如果存在)
            DIST_LIST="$TARGET_PATH/.system_distributed_files.txt"
            if [ -f "$DIST_LIST" ]; then
                chown "$MANAGER_USER:$MANAGER_GROUP" "$DIST_LIST"
                chmod 644 "$DIST_LIST"
            fi
            echo "   ✓ 已修復並鎖定所有 Safe Copy 系統保護與審計防線檔案。"
        fi
    fi
done

echo "✅ 所有實例安全防線與權限精準重組完成！"
