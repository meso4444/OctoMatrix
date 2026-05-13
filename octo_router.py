#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 OctoMatrix Router (octo_router.py) - 終極穩定功能對標版 (修復 Loop 遞迴)
"""

import os
import sys
import json
import threading
import logging
import subprocess
import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from flask import Flask, request, jsonify
from config import (
    TELEGRAM_GATEWAY_PORT,
    AGENTS, DEFAULT_ACTIVE_AGENT, TMUX_SESSION_NAME, CUSTOM_MENU,
    COLLABORATION_GROUPS, get_agent_info, AWAKE_YAML_PATH
)
from tools.notification.matrix_notifier import MatrixNotifier
from awake_manager import AwakeManager

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/octo_router.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

ROUTER_PORT = int(os.getenv('ROUTER_PORT', 12210))
ROUTER_HOST = '0.0.0.0'
script_dir = os.path.dirname(os.path.abspath(__file__))
AGENT_HOME_BASE = os.path.join(script_dir, 'agent_home')

# 固化端口訊息
try:
    with open(os.path.join(script_dir, '.router_port'), 'w') as f:
        f.write(str(ROUTER_PORT))
except: pass

@dataclass
class MCMessage:
    source: str
    user_id: str
    username: str
    content: str
    timestamp: str = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None: self.timestamp = datetime.now().isoformat()
        if self.metadata is None: self.metadata = {}

USER_STATES = {}
CURRENT_AGENT = DEFAULT_ACTIVE_AGENT
COMMAND_COOLDOWNS = {}

def check_cooldown(agent_name: str, cmd_type: str, cooldown_sec: int = 10) -> bool:
    global COMMAND_COOLDOWNS
    now = time.time()
    key = f"{agent_name}_{cmd_type}"
    if key in COMMAND_COOLDOWNS and now - COMMAND_COOLDOWNS[key] < cooldown_sec:
        return False
    COMMAND_COOLDOWNS[key] = now
    return True

class AtomicInjector:
    def __init__(self, session_name: str):
        self.session_name = session_name
        self.lock = threading.Lock()
        self.last_inject_time = 0.0

    def check_session(self, window_name: str) -> bool:
        try:
            result = subprocess.run(['tmux', 'has-session', '-t', f'{self.session_name}:{window_name}'], capture_output=True)
            return result.returncode == 0
        except: return False

    def inject(self, content: str, agent_name: str, interrupt_first: bool = False) -> bool:
        with self.lock:
            try:
                now = time.time()
                elapsed = now - self.last_inject_time
                if elapsed < 3.0:
                    time.sleep(3.0 - elapsed)

                if not self.check_session(agent_name): 
                    logger.error(f"❌ [Injector] 找不到 Tmux 視窗: {agent_name}")
                    return False
                target = f"{self.session_name}:{agent_name}"
                
                if interrupt_first:
                    # 🚀 用戶主動中斷：先送出 Ctrl+C 中斷可能的長時間執行任務
                    subprocess.run(['tmux', 'send-keys', '-t', target, 'C-c'], check=True)
                    time.sleep(0.5)

                escaped = content.replace('!', '！').replace('$', '\\$')
                
                # 🚀 物理注入硬化：文字與 Enter 物理分離
                subprocess.run(['tmux', 'send-keys', '-t', target, '-l', escaped], check=True)
                time.sleep(0.8)
                subprocess.run(['tmux', 'send-keys', '-t', target, 'Enter'], check=True)
                
                # 🚀 強制執行雙重 Enter 協議
                time.sleep(0.3)
                subprocess.run(['tmux', 'send-keys', '-t', target, 'Enter'], check=True)
                self.last_inject_time = time.time()
                return True
            except Exception as e:
                logger.error(f"❌ [Injector] 物理注入失敗: {e}")
                return False

class CommandHandler:
    def __init__(self, injector: AtomicInjector, notifier: MatrixNotifier, awake=None):
        self.injector = injector
        self.notifier = notifier
        self.awake = awake

    def handle(self, msg: MCMessage) -> bool:
        global CURRENT_AGENT, USER_STATES
        if not msg.content: return False
        content = msg.content.strip()
        timestamp = datetime.now().strftime('%H:%M:%S')
        target_agent = msg.metadata.get('target_agent', CURRENT_AGENT)

        # 1. 處理等待輸入狀態 (非遞迴)
        if msg.user_id in USER_STATES:
            state = USER_STATES[msg.user_id]
            content = state['command_template'].replace('{input}', content)
            del USER_STATES[msg.user_id]

        # 2. 處理選單標籤轉譯 (非遞迴)
        for row in CUSTOM_MENU:
            for item in row:
                label = item.get('label') if isinstance(item, dict) else item
                if content == label:
                    command = item.get('command', '')
                    if '{input}' in command:
                        USER_STATES[msg.user_id] = {'command_template': command}
                        self.notifier.notify(msg.source, 'custom', {'content': f"📋 <b>等待輸入</b>\n\n{item.get('prompt', '請輸入內容:')}"})
                        return True
                    content = command # 物理替換內容，向下執行，不觸發遞迴

        cmd_content = content.lower().strip()
        
        # 3. 核心指令處理分支
        if cmd_content.startswith('/switch'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1].lower()
                found = next((a for a in AGENTS if a['name'].lower() == target), None)
                if found:
                    CURRENT_AGENT = found['name']
                    self.notifier.notify(msg.source, 'custom', {'content': f'⚡ <b>對話切換成功</b>\n當前活躍 Agent: <code>{CURRENT_AGENT}</code>'})
            return True
        elif cmd_content == '/status':
            self._send_status(msg); return True
        elif cmd_content == '/help':
            self._send_help(msg); return True
        elif cmd_content == '/menu':
            self._send_menu(msg); return True
        elif cmd_content == '/interrupt':
            if not check_cooldown(target_agent, 'interrupt'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> 操作冷卻中，請稍後再試。'})
                return True
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'C-c'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🛑 已發送中斷訊號至 <b>[{target_agent}]</b>'})
            return True
        elif cmd_content == '/clear':
            if not check_cooldown(target_agent, 'clear'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> 操作冷卻中，請稍後再試。'})
                return True
            self.injector.inject('/clear', target_agent)
            self.notifier.notify(msg.source, 'custom', {'content': f'🧹 已清除 <b>[{target_agent}]</b> 的畫面與上下文'})
            return True
        elif cmd_content == '/resume_latest':
            if not check_cooldown(target_agent, 'resume_latest'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> 操作冷卻中，請稍後再試。'})
                return True
            # 🚀 Enter 鍵物理減肥：僅調用 inject，不再手動補發 Enter，防止 Loop
            self.injector.inject('/resume', target_agent)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'Escape'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🧠 已嘗試恢復 <b>[{target_agent}]</b> 最近一次對話'})
            return True
        elif cmd_content == '/sys_refresh':
            if not check_cooldown(target_agent, 'sys_refresh'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> 操作冷卻中，請稍後再試。'})
                return True
            target_info = get_agent_info(target_agent)
            engine = target_info.get('engine', '').lower() if target_info else 'gemini'
            if engine == "claude":
                engine_doc_name = "CLAUDE.md"
            elif engine == "codex":
                engine_doc_name = "AGENTS.md"
            else:
                engine_doc_name = "GEMINI.md"
            check_prompt = f"【系統提示】此任務不發送通知給用戶。檢視 AGENT_PROTOCOL.md 與 agent_home_rules.md 內容,確認{engine_doc_name}的規範是否完備,並更新"
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '-l', check_prompt], check=False)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'Enter'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🔄 已向 <b>[{target_agent}]</b> 發送規範更新指令'})
            return True
        elif cmd_content.startswith('/inspect'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1]
                prompt = (
                    f"透過 tmux 進入 '{target}' 的視窗，查看其前 50 行狀態並分析。\n\n"
                    f"【系統提示】此指令來自 Matrix 用戶。任務完成後，完成以下 [SOP]:\n"
                    f"[Step 1 - 回報]：執行 `python3 toolbox/matrix_notifier.py` 將任務訊息或檔案發送給用戶並搭配Avatar emoji。\n"
                    f"[Step 2 - 收攝]：執行 `python3 octo_cyberbrain/octo_ghost_reader.py --level current` 收攝你的 GHOST 與記憶。\n"
                    f"[Step 3 - 刻印]：執行 `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"語義大綱\" --keywords \"關鍵字1,關鍵字2\" --paths \"/檔案路徑1,/檔案路徑2\"` 將本次任務狀態刻印到GHOST。"
                )
                self.injector.inject(prompt, target_agent)
                self.notifier.notify(msg.source, 'custom', {'content': f'🔍 已指派 {target_agent} 檢查 {target}...'})
            return True
        elif cmd_content.startswith('/fix'):
            parts = content.split()
            if len(parts) > 1:
                target_name = parts[1]
                target_info = get_agent_info(target_name)
                if target_info:
                    engine = target_info.get('engine', '').lower()
                    model = target_info.get('model', '').strip()
                    
                    if 'gemini' in engine:
                        start_cmd = f'gemini --yolo --model {model}' if model and model.lower() != 'auto' else 'gemini --yolo'
                    elif 'codex' in engine:
                        start_cmd = f'codex --yolo --model {model}' if model and model.lower() != 'auto' else 'codex --yolo'
                    else:
                        start_cmd = f'claude --permission-mode bypassPermissions --model {model}' if model and model.lower() != 'auto' else 'claude --permission-mode bypassPermissions'
                        
                    prompt = f"""透過 tmux 查找 session "{TMUX_SESSION_NAME}"，進入 "{target_name}" 的視窗，
輸入 /quit 或 /exit 並執行 Enter，等待3秒後執行 pwd 指令確認回到 Linux Shell 後，再執行啟動指令：`{start_cmd}`。
等待5秒啟動完成後，請輸入 `/resume` ,執行 Enter, 等待3秒後再執行1次enter, 以恢復最近一次的對話紀錄。

【⚠️ 技術限制：Tmux Send-Keys 與 Enter 鍵處理 (嚴格執行)】
必須採用 「文字 -> 延遲 -> Enter」 的三部曲寫法：
tmux send-keys -t target 您的訊息內容 && sleep 1 && tmux send-keys -t target Enter

【系統提示】此指令來自 Matrix 用戶。任務完成後，完成以下 [SOP]:
[Step 1 - 回報]：執行 `python3 toolbox/matrix_notifier.py` 將任務訊息或檔案發送給用戶並搭配Avatar emoji。
[Step 2 - 收攝]：執行 `python3 octo_cyberbrain/octo_ghost_reader.py --level current` 收攝你的 GHOST 與記憶。
[Step 3 - 刻印]：執行 `python3 octo_cyberbrain/octo_ghost_updater.py --outline "語義大綱" --keywords "關鍵字1,關鍵字2" --paths "/檔案路徑1,/檔案路徑2"` 將本次任務狀態刻印到GHOST。"""
                    self.injector.inject(prompt, target_agent)
                    self.notifier.notify(msg.source, 'custom', {'content': f'🚑 已指派 <b>[{target_agent}]</b> 去修復 <b>[{target_name}]</b> (引擎: {engine})...'})
                else:
                    self.notifier.notify(msg.source, 'custom', {'content': f'❌ 找不到配置檔中的 Agent: {target_name}'})
            return True
        elif cmd_content.startswith('/capture'):
            parts = content.split()
            if len(parts) > 1:
                cap_target = parts[1]
                res = subprocess.run(['tmux', 'capture-pane', '-t', f'{TMUX_SESSION_NAME}:{cap_target}', '-p'], capture_output=True, text=True)
                output = "\n".join(res.stdout.split('\n')[-50:])
                self.notifier.notify(msg.source, 'custom', {'content': f"📸 <b>[{cap_target}]</b> 畫面擷取:\n<code>{output}</code>"})
            return True

        # 狀態記錄與注入
        if msg.source in ['telegram', 'discord', 'slack']:
            source_file = os.path.join(script_dir, '.last_source')
            try:
                source_data = {'platform': msg.source, 'user_id': msg.user_id, 'username': msg.username, 'timestamp': datetime.now().isoformat()}
                with open(source_file, 'w') as f: json.dump(source_data, f)
            except: pass

        final_message = content
        if msg.source != 'awake' and '【系統提示】' not in content:
            final_message += f"\n\n【系統提示】此指令來自 Matrix 用戶，請先回用戶訊息再開始任務。任務開始前，若用戶所提及關鍵字或任務缺少完整上下文脈絡時，主動進行關鍵字深潛shell紀錄，確認紀錄中是否有相關脈絡，若執行方向明確就執行，若有不明確就先暫停任務並回訊用戶相關紀錄的recap向用戶確認方向，但禁止向用戶提及你做了shell深潛的相關操作; 任務完成後，完成以下 [SOP]:\n[Step 1 - 回報]：執行 `python3 toolbox/matrix_notifier.py` 將任務訊息或檔案發送給用戶並搭配Avatar emoji。\n[Step 2 - 收攝]：執行 `python3 octo_cyberbrain/octo_ghost_reader.py --level current` 收攝你的 GHOST 與記憶。\n[Step 3 - 刻印]：執行 `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"語義大綱\" --keywords \"關鍵字1,關鍵字2\" --paths \"/檔案路徑1,/檔案路徑2\"` 將本次任務狀態刻印到GHOST。"

        # 👻 GHOST 實體檔案阻塞與積累機制
        agent_dir = os.path.join(AGENT_HOME_BASE, target_agent)
        lock_file = os.path.join(agent_dir, 'octo_cyberbrain', 'inject_block.lock')
        pending_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_inject.txt')

        if msg.source not in ['reaper', 'system_flush'] and os.path.exists(lock_file):
            try:
                with open(pending_file, 'a', encoding='utf-8') as f:
                    if os.path.exists(pending_file) and os.path.getsize(pending_file) > 0:
                        f.write("\n\n")
                    f.write(content) # 只存純淨的用戶訊息
                if msg.source != 'awake':
                    self.notifier.notify(msg.source, 'custom', {'content': f'👻 <b>[{target_agent}]</b> 正在重整思緒中，請稍候...'})
                return True
            except Exception as e:
                logger.error(f"❌ [Router] 寫入暫存檔失敗: {e}")

        success = self.injector.inject(final_message, target_agent, interrupt_first=(msg.source not in ['awake', 'system_flush']))
        if success and msg.source != 'awake':
            self.notifier.notify(msg.source, 'matrix_connected', {'timestamp': timestamp, 'agent_name': target_agent})
        return success

    def _send_status(self, msg: MCMessage):
        agent_role_map = {}
        for grp in COLLABORATION_GROUPS:
            roles = grp.get('roles', {})
            for member, role in roles.items():
                agent_role_map[member] = f"[{grp.get('name')}] {role}"

        agent_status_list = []
        for a in AGENTS:
            name = a['name']
            status = "🟢" if self.injector.check_session(name) else "🔴"
            active = " (⭐ 活躍)" if name == CURRENT_AGENT else ""
            role_info = f"\n      └ {agent_role_map[name]}" if name in agent_role_map else ""
            agent_status_list.append(f"{status} <b>[{name}]</b> {a.get('description', '')}{active}{role_info}")
        
        awake_list = []
        if self.awake:
            jobs = self.awake.list_jobs().get('jobs', [])
            for j in jobs:
                nr = j.get('next_run_time', '未喚醒').split('.')[0]
                p = j.get('prompt', '無指令')
                if len(p) > 500: p = p[:497] + "..."
                awake_list.append(f"• <b>{j.get('id', '?')}</b>\n  └ 對象: {j.get('target_agent', '未指定')}\n  └ 觸發: {j.get('trigger', '?')}\n  └ 指令: <code>{p}</code>\n  └ 下次: {nr}")

        channels_status = []
        try:
            tg_stat = "🟢" if subprocess.run(['curl', '-s', f'http://localhost:{TELEGRAM_GATEWAY_PORT}/health'], timeout=2).returncode == 0 else "🔴"
        except: tg_stat = "🔴"
        channels_status.append(f"• Telegram: {tg_stat}")
        channels_status.append(f"• Discord: {'🟢' if subprocess.run(['pgrep', '-f', 'discord_gateway.py']).returncode == 0 else '🔴'}")
        channels_status.append(f"• Slack: {'🟢' if subprocess.run(['pgrep', '-f', 'slack_socket_gateway.py']).returncode == 0 else '🔴'}")

        status_text = "📊 <b>OctoMatrix 狀態報告</b>\n\n" + \
                      "🤖 <b>Agent 軍團:</b>\n" + "\n".join(agent_status_list) + "\n\n" + \
                      "⏰ <b>喚醒系統 (Awake):</b>\n" + ("\n".join(awake_list) if awake_list else "無活躍任務") + "\n\n" + \
                      "🌐 <b>通道狀態:</b>\n" + "\n".join(channels_status)
        self.notifier.notify(msg.source, 'custom', {'content': status_text})

    def _send_help(self, msg: MCMessage):
        help_text = "📖 <b>OctoMatrix 系統全功能指南</b>\n\n"
        help_text += f"<b>🎯 當前關注 Agent:</b> <code>{CURRENT_AGENT}</code>\n\n"
        help_text += "───────────────────────────────\n\n"
        help_text += "<b>🤖 對話與基礎操作</b>\n"
        help_text += "• <b>直接發送</b>：訊息將傳送給標註 ⭐ 的活躍 Agent。\n"
        help_text += "• <b>發送圖片</b>：自動執行多模態分析（僅限 Telegram/Discord）。\n"
        help_text += "• <code>/switch [名稱]</code>：切換當前對話的活躍 Agent。\n"
        help_text += "• <code>/menu</code>：彈出實體管理按鍵選單（手機端推薦）。\n\n"
        help_text += "<b>🔍 監控與診斷</b>\n"
        help_text += "• <code>/status</code>：查看所有 Agent 存活、喚醒內容與通道連通性。\n"
        help_text += "• <code>/capture [名稱]</code>：擷取指定視窗最近 50 行內容，檢查運行報錯。\n"
        help_text += "• <code>/inspect [名稱]</code>：指派當前 Agent 進入目標視窗執行深度巡檢。\n\n"
        help_text += "<b>🛠️ 控制與修復</b>\n"
        help_text += "• <code>/interrupt</code>：向活躍 Agent 發送 Ctrl+C 強制中斷卡死的程序。\n"
        help_text += "• <code>/clear</code>：清除視窗畫面與 Agent 的當前上下文。\n"
        help_text += "• <code>/resume_latest</code>：嘗試從 CLI 本地快取恢復最近一次的對話紀錄。\n"
        help_text += "• <code>/fix [名稱]</code>：執行「重啟序列」（Quit + Start）嘗試修復崩潰的 Agent。\n"
        help_text += "• <code>/sys_refresh</code>：檢查並更新 Agent 的系統協定與規範。\n\n"
        help_text += "<b>⏰ 自動化喚醒</b>\n"
        help_text += "• 請直接透過對話「要求 Agent 建立喚醒任務」，即可實現定時喚醒任務。可透過 <code>/status</code> 監控現有喚醒任務。\n\n"
        help_text += "───────────────────────────────\n"
        help_text += "💡 <b>提示</b>：Telegram 與 Discord 請使用斜線 <code>/</code> 指令；Slack 請使用驚嘆號 <code>!</code> 引導。"
        self.notifier.notify(msg.source, 'custom', {'content': help_text})

    def _send_menu(self, msg: MCMessage):
        if msg.source == 'telegram':
            kb = [[item.get('label') if isinstance(item, dict) else item for item in row] for row in CUSTOM_MENU]
            platform_kwargs = {'reply_markup': json.dumps({'keyboard': kb, 'resize_keyboard': True, 'one_time_keyboard': True})}
            self.notifier.notify(msg.source, 'custom', {'content': "📱 <b>OctoMatrix 管理選單</b>\n請選擇要執行的功能：", '_platform_kwargs': platform_kwargs})
        else:
            self.notifier.notify(msg.source, 'custom', {'content': "🎮 請發送 <code>/help</code> 查看可用指令。"})

app = Flask(__name__)
notifier = MatrixNotifier()
awake = AwakeManager()
injector = AtomicInjector(TMUX_SESSION_NAME)
handler = CommandHandler(injector, notifier, awake)

@app.route('/awake/jobs/register', methods=['POST'])
def awake_register():
    data = request.get_json(); return jsonify(awake.register_job(data))
@app.route('/awake/jobs/<job_id>', methods=['DELETE'])
def awake_delete(job_id): return jsonify(awake.delete_job(job_id))
@app.route('/awake/jobs', methods=['GET'])
def awake_list(): return jsonify(awake.list_jobs())

@app.route('/notify', methods=['POST'])
def notify_proxy():
    data = request.get_json()
    success = notifier.notify(data.get('platform', 'telegram'), data.get('template_id', 'custom'), data.get('context', {}), data.get('target_id'))
    return jsonify({"status": "success" if success else "failed"}), 200

@app.route('/notify_file', methods=['POST'])
def notify_file_proxy():
    p = request.form.get('platform', 'telegram'); ft = request.form.get('file_type', 'document'); c = request.form.get('caption', ''); tid = request.form.get('target_id')
    if 'file' not in request.files: return jsonify({"status": "failed", "error": "No file"}), 400
    file = request.files['file']; temp = os.path.join('/tmp', file.filename); file.save(temp)
    try:
        success = notifier.notify_file(p, temp, ft, c, tid); os.remove(temp)
        return jsonify({"status": "success" if success else "failed"}), 200
    except Exception as e:
        if os.path.exists(temp): os.remove(temp)
        return jsonify({"status": "failed", "error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health(): return jsonify({"status": "healthy"}), 200

@app.route('/telegram_webhook', methods=['POST'])
def proxy_telegram_webhook():
    try:
        data = request.get_data(); headers = {k: v for k, v in request.headers if k != 'Host'}
        # 🚀 放寬 timeout 至 60 秒，避免圖片下載耗時觸發 Telegram 重試機制
        resp = requests.post(f"http://127.0.0.1:{TELEGRAM_GATEWAY_PORT}/telegram_webhook", data=data, headers=headers, timeout=60)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e: return jsonify({"status": "failed", "error": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "status": "healthy",
        "current_agent": CURRENT_AGENT,
        "active_agents": [a['name'] for a in AGENTS]
    }), 200

@app.route('/inject', methods=['POST'])
def inject():
    data = request.get_json()
    msg = MCMessage(source=data['source'], user_id=data['user_id'], username=data.get('username', 'User'), content=data['content'], metadata=data.get('metadata', {}))
    
    # 📸 多媒體路徑日誌
    if 'local_path' in msg.metadata:
        logger.info(f"📸 [Router] 接收到多媒體訊息: {msg.metadata['local_path']} (Source: {msg.source})")
        
    success = handler.handle(msg)
    return jsonify({"status": "success" if success else "failed"}), 200

if __name__ == '__main__':
    awake.start()
    app.run(host=ROUTER_HOST, port=ROUTER_PORT)
