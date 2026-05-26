#!/bin/bash
# 啟動 Telegram → AI Agent 軍團 遠端控制系統

set -e

# 解析為絕對路徑
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.py"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

# 載入環境變數
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "🔐 已載入 .env"
else
    echo "⚠️  警告: .env 檔案不存在"
fi

# 讀取配置
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")

echo "🚀 啟動 OctoMatrix"
echo "==========================================="

# 生成動態 Webhook Secret
SECRET_FILE="$SCRIPT_DIR/webhook_secret.token"
openssl rand -hex 32 > "$SECRET_FILE"
export WEBHOOK_SECRET_TOKEN=$(cat "$SECRET_FILE")

# 終止現有 session
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    echo "🔄 終止現有 session…"
    tmux kill-session -t "$TMUX_SESSION_NAME"
    sleep 1
fi

# 建立主 session（指定獨立的 socket 文件，確保容器隔離）
echo "🧬  建立 tmux session '$TMUX_SESSION_NAME'…"
# 使用明確指定的 socket 檔案路徑建立 session（不依賴 TMUX_TMPDIR 環境變數）
tmux new-session -d -s "$TMUX_SESSION_NAME" -n "init" -c "$SCRIPT_DIR"

# 1. 初始化 Agent 環境
echo "🧬  正在初始化 Agent 生態環境…"
python3 "$SCRIPT_DIR/setup_agent_env.py"

# 2. 動態啟動 AI Agent 軍團
echo "🤖 正在部署 AI Agent 軍團…"
export SCRIPT_DIR
export TMUX_SESSION_NAME

python3 << 'EOF'
import sys
import os
import subprocess
import time
import re

script_dir = os.environ['SCRIPT_DIR']
session_name = os.environ['TMUX_SESSION_NAME']
sys.path.append(script_dir)

def tmux_cmd(tmux_args):
    """Helper function to run tmux commands"""
    return tmux_args

def safe_copy(src, dst):
    if os.path.exists(src):
        subprocess.run(['rm', '-f', dst], check=False)
        subprocess.run(['cp', src, dst], check=True)
        if dst.endswith('.py') or dst.endswith('.sh'):
            subprocess.run(['chmod', 'a-w', dst], check=False)

def wait_for_prompt(session_name, window_name, engine, max_wait=30):
    """等待 tmux pane 出現對應的 CLI 提示符（穩定檢測）

    Args:
        engine: 'claude' 或 'gemini'
        - claude → ❯
        - gemini → * 或 >

    Note: 需要連續檢測到提示符 3 次以上，確保 CLI 完全就緒
    """
    start_time = time.time()
    # 根據引擎選擇對應的提示符
    if engine == 'claude':
        prompt_markers = ['Claude', 'bypass permissions on']
    elif engine == 'codex':
        prompt_markers = ['OpenAI', '› ']
    else:  # gemini
        prompt_markers = ['Gemini', 'YOLO']

    consecutive_detections = 0
    required_detections = 3  # 需要連續檢測 3 次才認為 CLI 已就緒
    trust_handled = False

    while time.time() - start_time < max_wait:
        try:
            result = subprocess.run(
                ['tmux'] + tmux_cmd(['capture-pane', '-t', f'{session_name}:{window_name}', '-p']),
                capture_output=True, text=True
            )
            output = result.stdout
            if not output:
                consecutive_detections = 0
                time.sleep(0.5)
                continue

            # 檢查整個 pane 內容是否包含任何預期的提示符
            detected = False
            for marker in prompt_markers:
                if marker in output:
                    detected = True
                    break

            # 特別處理引擎的 Trust Folder 提示 (自動授權)
            if not trust_handled and ('Trust folder' in output or 'trust the contents' in output.lower() or 'trust' in output.lower()):
                print(f"       🛡️  偵測到 {engine.capitalize()} 信任提示，正在自動授權…")
                subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{window_name}', 'Enter']))
                trust_handled = True
                time.sleep(2)
                continue

            if detected:
                consecutive_detections += 1
                if consecutive_detections >= required_detections:
                    print(f"       ✅ {engine} CLI 完全就緒（提示符穩定檢測 {consecutive_detections} 次）")
                    return True
            else:
                consecutive_detections = 0

        except Exception as e:
            consecutive_detections = 0

        time.sleep(0.5)

    return False

try:
    from config import AGENTS, COLLABORATION_GROUPS
    
    rules_path = os.path.join(script_dir, 'agent_home_rules.md')
    template_path = os.path.join(script_dir, 'agent_rule_gen_template.txt')
    
    with open(template_path, 'r') as f:
        gen_template = f.read()

    for i, agent in enumerate(AGENTS):
        name = agent['name']
        engine = agent['engine']
        usecase = agent.get('usecase', '無描述')
        home_path = os.path.join(script_dir, 'agent_home', name)
        
        # 產生協作脈絡
        collab_context_lines = []
        for grp in COLLABORATION_GROUPS:
            if name in grp.get('members', []):
                collab_context_lines.append(f"- 所屬團隊: {grp.get('name')} ({grp.get('description', '')})")
                collab_context_lines.append("  團隊成員權責:")
                roles = grp.get('roles', {})
                for member, role in roles.items():
                    marker = " (你)" if member == name else ""
                    collab_context_lines.append(f"  * {member}{marker}: {role}")
                collab_context_lines.append("")
        
        collab_context = "\n".join(collab_context_lines) if collab_context_lines else "無特定協作團隊配置。"

        print(f"   ▸ 啟動 Agent: {name} ({engine})")
        
        if i == 0:
            subprocess.run(['tmux'] + tmux_cmd(['rename-window', '-t', f'{session_name}:0', name]), check=True)
        else:
            subprocess.run(['tmux'] + tmux_cmd(['new-window', '-t', session_name, '-n', name]), check=True)

        # 🧠 初始化 Cyberbrain 目錄結構與環境檔
        cyber_path = os.path.join(home_path, 'octo_cyberbrain')
        ghost_path = os.path.join(cyber_path, 'ghost')
        shell_path = os.path.join(cyber_path, 'shell')
        os.makedirs(ghost_path, exist_ok=True)
        os.makedirs(shell_path, exist_ok=True)
        
        env_file = os.path.join(cyber_path, '.cyberbrain_env')
        with open(env_file, 'w') as ef:
            ef.write(f"AGENT_NAME={name}\nTMUX_SESSION_NAME={session_name}\nROUTER_PORT={os.environ.get('ROUTER_PORT', '12210')}\n")
            
        # 🧠 複製 Cyberbrain 工具與指南
        cyber_tools_dir = os.path.join(script_dir, 'tools', 'cyberbrain')
        if os.path.exists(cyber_tools_dir):
            for item in os.listdir(cyber_tools_dir):
                if item.endswith('.py') or item.endswith('.md'):
                    src = os.path.join(cyber_tools_dir, item)
                    dst = os.path.join(cyber_path, item)
                    safe_copy(src, dst)

        # 設置 pipe-pane (透過 cyberbrain_pipe_manager.py 結合串流觸發與快照裁切的終極架構)
        pipe_manager = os.path.join(script_dir, 'tools', 'cyberbrain', 'cyberbrain_pipe_manager.py')
        shell_log_path = os.path.join(shell_path, 'octo_shell.log')
        responder_script = os.path.join(script_dir, 'auto_permission_responder.py')
        
        # 使用 bash 的 tee >(...) 功能，同時把串流分發給 responder 和 pipe_manager
        pipe_cmd = f"bash -c 'tee >(python3 -u {responder_script} {session_name}:{name}) | python3 -u {pipe_manager} {shell_log_path} {session_name}:{name}'"
        
        subprocess.run(['tmux'] + tmux_cmd(['pipe-pane', '-o', '-t', f'{session_name}:{name}', pipe_cmd]), check=True)

        # 📋 複製必要的工具腳本到 Agent home
        # 複製 matrix_notifier.py 到 agent_home toolbox
        matrix_notifier_src = os.path.join(script_dir, 'tools', 'notification', 'matrix_notifier.py')
        toolbox_path = os.path.join(home_path, 'toolbox')
        os.makedirs(toolbox_path, exist_ok=True)
        matrix_notifier_dst = os.path.join(toolbox_path, 'matrix_notifier.py')
        if os.path.exists(matrix_notifier_src):
            safe_copy(matrix_notifier_src, matrix_notifier_dst)

        # 建立共享空間、知識庫與 GHOST 目錄
        shared_space_path = os.path.join(home_path, 'my_shared_space')
        os.makedirs(shared_space_path, exist_ok=True)

        knowledge_path = os.path.join(home_path, 'knowledge')
        os.makedirs(knowledge_path, exist_ok=True)

        # 📚 統一複製知識文檔邏輯
        # 複製規則和協議文件（直接到 agent_home）
        rule_files_to_copy = ['agent_home_rules.md', 'AGENT_PROTOCOL.md']
        for rule_file in rule_files_to_copy:
            src_file = os.path.join(script_dir, rule_file)
            dst_file = os.path.join(home_path, rule_file)
            if os.path.exists(src_file):
                safe_copy(src_file, dst_file)

        # 複製 Template 文件（直接複製到 agent_home，不建立子目錄）
        template_src = os.path.join(script_dir, 'agent_rule_gen_template.txt')
        template_dst = os.path.join(home_path, 'agent_rule_gen_template.txt')
        if os.path.exists(template_src):
            safe_copy(template_src, template_dst)

        # 🎨 複製 Avatar 功能相關檔案
        # 複製 octo_generator.py 到 toolbox
        avatar_generator_src = os.path.join(script_dir, 'tools', 'avatar', 'octo_generator.py')
        avatar_generator_dst = os.path.join(toolbox_path, 'octo_generator.py')
        if os.path.exists(avatar_generator_src):
            safe_copy(avatar_generator_src, avatar_generator_dst)

        # 複製 Avatar 設計指引到 knowledge
        avatar_guide_src = os.path.join(script_dir, 'tools', 'avatar', 'AGENT_AVATAR_GUIDE.md')
        avatar_guide_dst = os.path.join(knowledge_path, 'AGENT_AVATAR_GUIDE.md')
        if os.path.exists(avatar_guide_src):
            safe_copy(avatar_guide_src, avatar_guide_dst)

        # 複製喚醒系統文檔到 knowledge
        awake_src = os.path.join(script_dir, 'tools', 'awake', 'AWAKE_FUNCTIONALITY.md')
        awake_dst = os.path.join(knowledge_path, 'AWAKE_FUNCTIONALITY.md')
        if os.path.exists(awake_src):
            safe_copy(awake_src, awake_dst)

        # 建立並驗證 avatar 目錄結構
        avatar_path = os.path.join(home_path, 'avatar')
        avatar_emojis_path = os.path.join(avatar_path, 'emojis')
        os.makedirs(avatar_emojis_path, exist_ok=True)

        if not os.path.isdir(avatar_emojis_path):
            print(f"   ⚠️  警告：無法創建 avatar/emojis 目錄：{avatar_emojis_path}")
        else:
            print(f"   ✓ Avatar 目錄已確認：{avatar_emojis_path}")

        # 🎯 進入 Agent 工作目錄
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', f'cd {home_path}']), check=True)
        time.sleep(1)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

        # 取得 Agent 的指定模型
        model = agent.get('model', '').strip()

        if engine == 'gemini':
            cmd = 'gemini --yolo'
            if model and model.lower() != 'auto':
                cmd += f' --model {model}'
            engine_doc_name = 'GEMINI.md'
        elif engine == 'codex':
            cmd = 'codex --yolo'
            if model and model.lower() != 'auto':
                cmd += f' --model {model}'
            engine_doc_name = 'AGENTS.md'
        else:
            cmd = 'claude --permission-mode bypassPermissions'
            if model and model.lower() != 'auto':
                cmd += f' --model {model}'
            engine_doc_name = 'CLAUDE.md'
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', cmd]), check=True)
        time.sleep(1)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

        # 等待 CLI 完全初始化（60 秒 timeout）
        print(f"     ⏳ 等待 {name} CLI 啟動…")
        if not wait_for_prompt(session_name, name, engine, max_wait=60):
            print(f"     ❌ {name} 啟動失敗（60 秒內未檢測到 {engine} 提示符），跳過此 Agent")
            continue  # 跳過此 Agent，繼續下一個

        # 額外等待以確保 CLI 完全就緒（避免在初始化中途注入命令）
        time.sleep(3)

        # ✅ 檢查規範文件是否已存在（避免重複注入與覆蓋）
        doc_path = os.path.join(home_path, engine_doc_name)
        if os.path.exists(doc_path):
            print(f"     ✅ {engine_doc_name} 已存在，跳過初始化注入（保護現有規範）")

            # 🔄 執行對話恢復流程 (/resume)
            print(f"     🔄 執行對話恢復流程…")

            # Step 1: 輸入 /resume 指令
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[200~']))
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', '/resume']), check=True)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[201~']))
            time.sleep(0.5)

            # Step 2: 執行 /resume (進入菜單)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
            time.sleep(1)

            # Step 3: 選擇前次對話
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
            time.sleep(1)

            # Step 4: 輸入 q (處理 Gemini 沒有前次對話的情況)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[200~']))
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', 'q']), check=True)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[201~']))
            time.sleep(0.5)

            # Step 5: Ctrl+C 確保退出菜單
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'C-c']), check=True)
            time.sleep(1)

            # Step 6: 等待 CLI 提示符重新出現
            print(f"     ⏳ 等待提示符恢復…")
            if not wait_for_prompt(session_name, name, engine, max_wait=10):
                print(f"     ⚠️ 提示符恢復超時，仍然嘗試注入 prompt…")

            # 確保完全就緒，等待 3 秒
            time.sleep(3)
        else:
            # 觸發 Agent 規範文件構建
            print(f"     ✨ 觸發 {name} 自我建構規範文件中…")

            # 指向 agent_home 中的本地副本
            rules_path = os.path.join(home_path, 'agent_home_rules.md')
            protocol_path = os.path.join(home_path, 'AGENT_PROTOCOL.md')  # 參考通知規則

            # 生成初始化 Prompt
            prompt = "【系統提示】\n" + (gen_template.replace('{agent_name}', name)
                                 .replace('{agent_usecase}', usecase)
                                 .replace('{engine_doc_name}', engine_doc_name)
                                 .replace('{rules_path}', rules_path)
                                 .replace('{protocol_path}', protocol_path)
                                 .replace('{collaboration_context}', collab_context)
                                 .replace('{home_path}', home_path))
            
            avatar_instruction = "\n\n=== 視覺形象建構任務 ===\n自我認知的客製化撰寫完成後，依照 ./knowledge/AGENT_AVATAR_GUIDE.md 的指引，生成你的 avatar。"
            prompt += avatar_instruction

            prompt_file = os.path.join(script_dir, f".prompt_temp_{name}")
            with open(prompt_file, 'w') as f:
                f.write(prompt)

            with open(prompt_file, 'r') as pf:
                prompt_content = pf.read()

            # Use send-keys -l (literal) to simulate typing, bypassing paste mode
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[200~']))
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', prompt_content]), check=True)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[201~']))
            time.sleep(0.5)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

            # 🔒 雙重保險: 所有 Agent 都需要粘貼模式確認
            # 這確保長 prompt 被正確發送
            time.sleep(0.2)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

            os.remove(prompt_file)

except Exception as e:
    print(f"❌ 部署過程中發生錯誤: {e}")
    sys.exit(1)
EOF

echo "   ✅ 所有 Agent 已就緒"

# Window: MC Router API
echo "🔀 啟動 MC Router (消息路由中樞)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "router" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:router" "python3 $SCRIPT_DIR/octo_router.py"
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:router" Enter

# 等待 Router 啟動
sleep 2

# 檢查平臺啟用狀態並啟動網關
python3 << 'EOF'
import sys
import os
import subprocess
import time

script_dir = os.environ['SCRIPT_DIR']
session_name = os.environ['TMUX_SESSION_NAME']
sys.path.append(script_dir)

try:
    from config import PLATFORMS_ENABLED
    
    # 1. Telegram
    if PLATFORMS_ENABLED.get('telegram', True):
        print("   📱 啟動 Telegram Gateway (Router 轉發)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'telegram', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:telegram', f'python3 {script_dir}/telegram_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Telegram 已禁用，跳過啟動")

    # 2. Discord
    if PLATFORMS_ENABLED.get('discord', True):
        print("   💻 啟動 Discord Gateway (WebSocket 模式)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'discord', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:discord', f'python3 {script_dir}/discord_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Discord 已禁用，跳過啟動")

    # 3. Slack
    if PLATFORMS_ENABLED.get('slack', True):
        print("   ⚡ 啟動 Slack Gateway (Socket Mode)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'slack', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:slack', f'python3 {script_dir}/slack_socket_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Slack 已禁用，跳過啟動")

except Exception as e:
    print(f"   ❌ 啟動網關時發生異常: {e}")
EOF

# 等待所有 Gateway 啟動
sleep 2

# Window: Octo Reaper (Cyberbrain GHOST 收割者)
echo "🧠 啟動 Cyberbrain GHOST 收割者 (octo_reaper.py)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "reaper" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" "python3 $SCRIPT_DIR/octo_reaper.py"
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" Enter

if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    # Window: ngrok Tunnel
    echo "☁️  建立安全連線隧道 (ngrok)…"
    tmux new-window -t "$TMUX_SESSION_NAME" -n "ngrok" -c "$SCRIPT_DIR"
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" "$SCRIPT_DIR/start_ngrok.sh"
    sleep 1
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" Enter

    echo "⏳ 正在同步網路位址與 Webhook…"
    sleep 5
else
    echo "⚪️ Telegram 已禁用，跳過 Ngrok 啟動"
fi

# 回到第一個 Agent window
tmux select-window -t "$TMUX_SESSION_NAME:0"

# 測試發送訊息
echo "📨 向所有 Agent 發送測試訊息並報上名字..."
python3 << 'EOF'
import os
import sys
import subprocess
import time
sys.path.append(os.environ['SCRIPT_DIR'])
try:
    from config import AGENTS, MATRIX_USERNAME
    session_name = os.environ['TMUX_SESSION_NAME']
    for agent in AGENTS:
        name = agent['name']
        test_msg = f"【系統提示】執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png 發符合當下心情的貼圖，接著執行 python3 toolbox/matrix_notifier.py '{{向 {MATRIX_USERNAME} 問候}}'"
        agent_dir = os.path.join(os.environ['SCRIPT_DIR'], 'agent_home', name)
        flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
        pending_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_inject.txt')
        
        if os.path.exists(flag_file):
            with open(pending_file, 'a', encoding='utf-8') as f:
                if os.path.exists(pending_file) and os.path.getsize(pending_file) > 0:
                    f.write("\n\n")
                f.write(test_msg)
            print(f"   ✓ 已將測試訊息排入 {name} 的 pending 佇列")
        else:
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', test_msg], check=True)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', 'Enter'], check=True)
            print(f"   ✓ 已發送測試訊息給: {name}")
except Exception as e:
    print(f"   ⚠️ 發送測試訊息失敗: {e}")
EOF

echo "==========================================="
echo "🎉 OctoMatrix 已全員部署！"
echo ""
echo "📋 運行摘要:"
echo "   Session: $TMUX_SESSION_NAME"
echo "   已啟動通訊網關:"
python3 << 'EOF'
import os
import sys
sys.path.append(os.environ['SCRIPT_DIR'])
try:
    from config import PLATFORMS_ENABLED
    if PLATFORMS_ENABLED.get('telegram', True): print("      📱 Telegram Gateway (Router 轉發)")
    if PLATFORMS_ENABLED.get('discord', True): print("      💻 Discord Gateway (WebSocket + 自動重連)")
    if PLATFORMS_ENABLED.get('slack', True): print("      ⚡ Slack Gateway (Socket Mode + 自動重連)")
    if not any(PLATFORMS_ENABLED.values()): print("      ⚪️ 無啟用任何通訊網關")
except Exception: pass
EOF
echo "   已啟動中樞服務:"
echo "      🔀 MC Router (消息標準化 + 原子注入)"
echo "      🧠 Octo Reaper (電子腦 GHOST 收割者)"
if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    echo "      ☁️  ngrok (Webhook 安全隧道)"
fi
echo ""
echo "   所有 tmux 視窗:"
tmux list-windows -t "$TMUX_SESSION_NAME" -F "      • Window #{window_index}: #{window_name}"
echo ""
echo "🚀 連接 Session: tmux attach -t $TMUX_SESSION_NAME"
echo ""
echo "✅ 驗證步驟:"
echo "   1. tmux attach -t $TMUX_SESSION_NAME"
echo "   2. 檢查 router 窗口: curl http://localhost:12210/health"
echo "   3. 在 Telegram/Discord/Slack 發送訊息並驗證 router 日誌"
