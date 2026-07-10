#!/usr/bin/env python3
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
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from flask import Flask, request, jsonify
from config import (
    SYS_PREFIX,
    TELEGRAM_GATEWAY_PORT,
    AGENTS, DEFAULT_ACTIVE_AGENT, TMUX_SESSION_NAME, CUSTOM_MENU,
    COLLABORATION_GROUPS, get_agent_info, AWAKE_YAML_PATH, MATRIX_USERNAME
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

# 暫存的 Avatar 更新 Token，格式： { agent_name: {"token": "...", "expires_at": datetime} }
avatar_tokens = {}

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

    def send_interrupt(self, agent_name: str) -> bool:
        target = f"{self.session_name}:{agent_name}"
        target_info = get_agent_info(agent_name)
        engine = target_info.get('engine', '').lower() if target_info else 'gemini'
        
        if engine == 'codex':
            try:
                res = subprocess.run(['tmux', 'capture-pane', '-p', '-t', target], capture_output=True, text=True)
                lines = [line for line in res.stdout.split('\n') if line.strip()]
                if 'Working (' in '\n'.join(lines[-20:]):
                    subprocess.run(['tmux', 'send-keys', '-t', target, "C-c"], check=False)
                    time.sleep(0.5)
                    subprocess.run(['tmux', 'send-keys', '-t', target, "Escape"], check=False)
                    time.sleep(0.5)
                    return True
                return False
            except Exception as e:
                logger.error(f"❌ [Injector] capture-pane failed: {e}")
                return False
        else:
            subprocess.run(['tmux', 'send-keys', '-t', target, "C-c"], check=False)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', target, "Escape"], check=False)
            time.sleep(0.5)
            return True

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
                    # 🚀 Codex 狀態感知中斷，其他引擎無條件中斷
                    self.send_interrupt(agent_name)

                escaped = content.replace('!', '！').replace('$', '\\$')
                
                # 🚀 物理注入硬化：文字與 Enter 物理分離
                subprocess.run(['tmux', 'send-keys', '-t', target, '\x1b[200~'])
                subprocess.run(['tmux', 'send-keys', '-t', target, '-l', '--', escaped], check=True)
                subprocess.run(['tmux', 'send-keys', '-t', target, '\x1b[201~'])
                time.sleep(1.2)
                subprocess.run(['tmux', 'send-keys', '-t', target, 'Enter'], check=True)
                
                # 🚀 強制執行雙重 Enter 協議
                time.sleep(1.2)
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
                        self.notifier.notify(msg.source, 'custom', {'content': item.get('prompt', '請輸入內容:')})
                        return True
                    content = command # 物理替換內容，向下執行，不觸發遞迴

        cmd_content = content.lower().strip()

        def is_cmd(c, name): return c == name or c.startswith(name + ' ')
        
        # 3. 核心指令處理分支
        interfering_cmds = ['/interrupt', '/clear', '/resume_latest', '/sys_refresh']
        is_interfering = cmd_content in interfering_cmds or is_cmd(cmd_content, '/inspect') or is_cmd(cmd_content, '/fix') or is_cmd(cmd_content, '/avatar_renew')

        if is_interfering:
            flag_file = os.path.join(AGENT_HOME_BASE, target_agent, 'octo_cyberbrain', '.rotation_flag')
            if os.path.exists(flag_file) and msg.source not in ['reaper', 'system_flush']:
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> 系統正在進行 GHOST 深度重整，請待重置完畢後再執行視窗干涉指令。'})
                return True

        if is_cmd(cmd_content, '/switch'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1].lower()
                found = next((a for a in AGENTS if a['name'].lower() == target), None)
                if found:
                    CURRENT_AGENT = found['name']
                    self.notifier.notify(msg.source, 'custom', {'content': f'🫧 <code>{CURRENT_AGENT}</code> 等待著你的呼喚'})
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
            target_info = get_agent_info(target_agent)
            engine = target_info.get('engine', '').lower() if target_info else 'gemini'
            if engine == 'codex':
                target = f'{TMUX_SESSION_NAME}:{target_agent}'
                res = subprocess.run(['tmux', 'capture-pane', '-p', '-t', target], capture_output=True, text=True)
                lines = [line for line in res.stdout.split('\n') if line.strip()]
                if 'Working (' in '\n'.join(lines[-20:]):
                    subprocess.run(['tmux', 'send-keys', '-t', target, "C-c"], check=False)
                    time.sleep(0.5)
                    subprocess.run(['tmux', 'send-keys', '-t', target, "Escape"], check=False)
                    self.notifier.notify(msg.source, 'custom', {'content': f'🛑 已發送中斷訊號至 <b>[{target_agent}]</b>'})
                else:
                    self.notifier.notify(msg.source, 'custom', {'content': f'⚠️ <b>[{target_agent}]</b> 處於空閒狀態，略過中斷。'})
            else:
                subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', "C-c"], check=False)
                time.sleep(0.5)
                subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', "Escape"], check=False)
                self.notifier.notify(msg.source, 'custom', {'content': f'🛑 已發送中斷訊號至 <b>[{target_agent}]</b>'})
            return True
        elif cmd_content == '/clear':
            if not check_cooldown(target_agent, 'clear'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> 操作冷卻中，請稍後再試。'})
                return True
            self.injector.send_interrupt(target_agent)
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
        elif is_cmd(cmd_content, '/sys_refresh'):
            parts = cmd_content.split(' ', 1)
            refresh_target = parts[1].strip() if len(parts) > 1 else target_agent
            agents_to_refresh = [a['name'] for a in AGENTS] if refresh_target == 'all' else [refresh_target]
            
            for t_agent in agents_to_refresh:
                if not check_cooldown(t_agent, 'sys_refresh'):
                    self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{t_agent}]</b> 操作冷卻中，請稍後再試。'})
                    continue
                target_info = get_agent_info(t_agent)
                engine = target_info.get('engine', '').lower() if target_info else 'gemini'
                usecase = target_info.get('usecase', '無描述') if target_info else '無描述'
                if engine == "claude":
                    engine_doc_name = "CLAUDE.md"
                elif engine == "codex":
                    engine_doc_name = "AGENTS.md"
                elif engine == "agy":
                    engine_doc_name = "GEMINI.md"
                else:
                    engine_doc_name = "GEMINI.md"
    
                home_path = os.path.join(AGENT_HOME_BASE, t_agent)
                rules_path = os.path.join(home_path, 'agent_home_rules.md')
                protocol_path = os.path.join(home_path, 'AGENT_PROTOCOL.md')
    
                collab_context_lines = []
                for grp in COLLABORATION_GROUPS:
                    if t_agent in grp.get('members', []):
                        collab_context_lines.append(f"- 所屬團隊: {grp.get('name')} ({grp.get('description', '')})")
                        collab_context_lines.append("  團隊成員權責:")
                        roles = grp.get('roles', {})
                        for member, role in roles.items():
                            marker = " (你)" if member == t_agent else ""
                            collab_context_lines.append(f"  * {member}{marker}: {role}")
                        collab_context_lines.append("")
                collab_context = "\n".join(collab_context_lines) if collab_context_lines else "無特定協作團隊配置。"
    
                template_path = os.path.join(script_dir, 'agent_rule_gen_template.txt')
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        gen_template = f.read()
                    check_prompt = f"{SYS_PREFIX}\n" + (gen_template.replace('{agent_name}', t_agent)
                                         .replace('{agent_usecase}', usecase)
                                         .replace('{engine_doc_name}', engine_doc_name)
                                         .replace('{rules_path}', rules_path)
                                         .replace('{protocol_path}', protocol_path)
                                         .replace('{collaboration_context}', collab_context)
                                         .replace('{home_path}', home_path))
                except Exception as e:
                    logger.error(f"❌ [Router] 無法讀取規範模板: {e}")
                    self.notifier.notify(msg.source, 'custom', {'content': f'❌ <b>[{t_agent}]</b> 規範重建失敗：無法讀取模板 ({e})'})
                    continue
    
                subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{t_agent}', '\x1b[200~'])
                subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{t_agent}', '-l', '--', check_prompt], check=False)
                subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{t_agent}', '\x1b[201~'])
                time.sleep(0.5)
                subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{t_agent}', 'Enter'], check=False)
                self.notifier.notify(msg.source, 'custom', {'content': f'🔄 已向 <b>[{t_agent}]</b> 發送完整規範重建指令'})
            return True
        elif is_cmd(cmd_content, '/avatar_renew'):
            if not check_cooldown(target_agent, 'avatar_renew'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> 操作冷卻中，請稍後再試。'})
                return True
            parts = content.split(' ', 1)
            requirement = parts[1].strip() if len(parts) > 1 else "無特定需求"
            
            # [指令攔截] 檢查是否為歷史管理指令
            req_lower = requirement.lower()
            if req_lower == 'list':
                self._list_avatar_backups(msg, target_agent)
                return True
            elif req_lower.startswith('restore'):
                restore_parts = requirement.split(None, 1)
                restore_target = restore_parts[1].strip() if len(restore_parts) > 1 else ""
                self._restore_avatar_backup(msg, target_agent, restore_target)
                return True
                
            # 產生 5 分鐘後過期的 Token
            token = str(uuid.uuid4())
            avatar_tokens[target_agent] = {
                "token": token,
                "expires_at": datetime.now() + timedelta(minutes=5)
            }
            
            import config
            prompt = config.AVATAR_RENEW_PROMPT.format(token=token, requirement=requirement)

            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '\x1b[200~'])
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '-l', '--', prompt], check=False)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '\x1b[201~'])
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'Enter'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🎨 已指派 <b>[{target_agent}]</b> 進行 Avatar 更新任務...'})
            return True
        elif is_cmd(cmd_content, '/inspect'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1]
                res = subprocess.run(['tmux', 'capture-pane', '-t', f'{TMUX_SESSION_NAME}:{target}', '-p'], capture_output=True, text=True)
                output = "\n".join(res.stdout.split('\n')[-50:])
                import config
                prompt = f"""{config.USER_MESSAGE_SOP}

來自 {MATRIX_USERNAME} 的訊息:
以下是目前 {target} 的狀態，請分析...
{output}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""
                self.injector.inject(prompt, target_agent)
                self.notifier.notify(msg.source, 'custom', {'content': f'🔍 已指派 {target_agent} 檢查 {target}...'})
            return True
        elif is_cmd(cmd_content, '/fix'):
            parts = content.split()
            if len(parts) > 1:
                target_name = parts[1]
                target_info = get_agent_info(target_name)
                if target_info:
                    engine = target_info.get('engine', '').lower()
                    self.notifier.notify(msg.source, 'custom', {'content': f'🚑 系統啟動 <b>[{target_name}]</b> 的硬重置修復 (引擎: {engine})...'})
                    try:
                        # 建立 .fix_flag 標記檔以啟動 pending 緩衝阻斷
                        agent_dir = os.path.join(AGENT_HOME_BASE, target_name)
                        fix_flag = os.path.join(agent_dir, 'octo_cyberbrain', '.fix_flag')
                        try:
                            os.makedirs(os.path.dirname(fix_flag), exist_ok=True)
                            open(fix_flag, 'w').close()
                        except: pass

                        subprocess.run(['tmux', 'kill-window', '-t', f'{TMUX_SESSION_NAME}:{target_name}'], check=False)
                        time.sleep(1)
                        subprocess.Popen(['python3', os.path.join(script_dir, 'setup_agent_env.py'), '--agent', target_name])
                        self.notifier.notify(msg.source, 'custom', {'content': f'✅ <b>[{target_name}]</b> 重啟程序已執行，請等待 Agent 恢復連線。'})
                    except Exception as e:
                        self.notifier.notify(msg.source, 'custom', {'content': f'❌ 修復 {target_name} 失敗: {e}'})
                else:
                    self.notifier.notify(msg.source, 'custom', {'content': f'❌ 找不到配置檔中的 Agent: {target_name}'})
            return True
        elif is_cmd(cmd_content, '/capture'):
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

        # ==========================================
        # 🛡️ 注入標準化 SOP (Matrix 訊息處理流程)
        # ==========================================
        if msg.source in ['telegram', 'discord', 'slack', 'awake'] and '執行以下 [SOP]:' not in content:
            import config
            sop = f"""{config.USER_MESSAGE_SOP}

來自 {MATRIX_USERNAME} 的訊息:
{content}

{SYS_PREFIX}請務必嚴格遵守上述 [SOP] 進行回覆。"""
            final_message = sop
        else:
            final_message = content

        # 👻 GHOST 實體檔案阻塞與積累機制
        agent_dir = os.path.join(AGENT_HOME_BASE, target_agent)
        flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
        fix_flag = os.path.join(agent_dir, 'octo_cyberbrain', '.fix_flag')
        pending_user_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_user.txt')

        if msg.source not in ['reaper', 'system_flush'] and (os.path.exists(flag_file) or os.path.exists(fix_flag)):
            try:
                with open(pending_user_file, 'a', encoding='utf-8') as f:
                    if os.path.exists(pending_user_file) and os.path.getsize(pending_user_file) > 0:
                        f.write("\n\n")
                    f.write(content) # 只存純淨的用戶訊息
                if msg.source not in ['awake', 'reaper_idle']:
                    self.notifier.notify(msg.source, 'custom', {'content': f'🐚 <b>{target_agent}</b> 正在喚醒深海回音，靜靜聆聽……'})
                    sleepy_webm = os.path.join(agent_dir, 'avatar/emojis/sleepy.webm')
                    sleepy_png = os.path.join(agent_dir, 'avatar/emojis/sleepy.png')
                    sleepy_path = sleepy_webm if os.path.exists(sleepy_webm) else sleepy_png
                    if os.path.exists(sleepy_path):
                        self.notifier.notify_file(msg.source, sleepy_path, file_type='sticker')
                return True
            except Exception as e:
                logger.error(f"❌ [Router] 寫入暫存檔失敗: {e}")

        success = self.injector.inject(final_message, target_agent, interrupt_first=(msg.source not in ['awake', 'reaper_idle', 'system_flush']))
        if success and msg.source not in ['awake', 'reaper_idle']:
            self.notifier.notify(msg.source, 'matrix_connected', {'timestamp': timestamp, 'agent_name': target_agent})
            
            # 自動發送 Agent Avatar 貼圖
            avatar_dir = os.path.join(agent_dir, 'avatar')
            base_webm = os.path.join(avatar_dir, 'base.webm')
            base_png = os.path.join(avatar_dir, 'base.png')
            sticker_path = None
            if os.path.exists(base_webm):
                sticker_path = base_webm
            elif os.path.exists(base_png):
                sticker_path = base_png
            else:
                import glob
                webm_files = glob.glob(os.path.join(avatar_dir, '*.webm'))
                if webm_files:
                    sticker_path = webm_files[0]
                else:
                    png_files = glob.glob(os.path.join(avatar_dir, '*.png'))
                    if png_files:
                        sticker_path = png_files[0]
            
            if sticker_path:
                self.notifier.notify_file(msg.source, sticker_path, file_type='sticker')

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
        from config import get_help_text
        help_text = get_help_text(CURRENT_AGENT)
        self.notifier.notify(msg.source, 'custom', {'content': help_text})

    def _send_menu(self, msg: MCMessage):
        if msg.source == 'telegram':
            kb = [[item.get('label') if isinstance(item, dict) else item for item in row] for row in CUSTOM_MENU]
            platform_kwargs = {'reply_markup': json.dumps({'keyboard': kb, 'resize_keyboard': True, 'one_time_keyboard': True})}
            self.notifier.notify(msg.source, 'custom', {'content': "📱 <b>OctoMatrix 管理選單</b>\n請選擇要執行的功能：", '_platform_kwargs': platform_kwargs})
        else:
            self.notifier.notify(msg.source, 'custom', {'content': "🎮 請發送 <code>/help</code> 查看可用指令。"})

    def _list_avatar_backups(self, msg, target_agent):
        import glob
        import zipfile
        avatar_dir = os.path.join(AGENT_HOME_BASE, target_agent, "avatar")
        history_zips = sorted(
            glob.glob(os.path.join(avatar_dir, "history_*.zip")),
            key=os.path.getmtime,
            reverse=True
        )
        if not history_zips:
            self.notifier.notify(msg.source, 'custom', {'content': f'📂 <b>[{target_agent}]</b> 目前沒有任何歷史頭像備份。'})
            return
            
        content_text = f"📂 <b>[{target_agent}] 歷史頭像備份列表：</b>\n\n"
        for idx, path in enumerate(history_zips, 1):
            filename = os.path.basename(path)
            size_kb = os.path.getsize(path) / 1024.0
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            content_text += f"{idx}. <code>{filename}</code> ({size_kb:.1f} KB) - {mtime}\n"
        content_text += "\n💡 提示：使用 <code>/avatar_renew restore &lt;編號&gt;</code> (例如 <code>/avatar_renew restore 1</code>) 即可進行還原。\n⏳ 正在背景解壓並傳送各備份的 `base.webm` 或 `base.png` 預覽圖..."
        self.notifier.notify(msg.source, 'custom', {'content': content_text})

        # 遞迴解壓並傳送 preview 圖
        for idx, path in enumerate(history_zips, 1):
            filename = os.path.basename(path)
            size_kb = os.path.getsize(path) / 1024.0
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            
            temp_preview_path = None
            try:
                with zipfile.ZipFile(path, 'r') as z:
                    target_entry = None
                    for entry in z.namelist():
                        if entry == "base.webm" or entry.endswith("/base.webm"):
                            target_entry = entry
                            break
                    if not target_entry:
                        for entry in z.namelist():
                            if entry == "base.png" or entry.endswith("/base.png"):
                                target_entry = entry
                                break
                    if target_entry:
                        ext = ".webm" if target_entry.endswith(".webm") else ".png"
                        temp_preview_path = os.path.join("/tmp", f"preview_{target_agent}_{idx}_{int(time.time())}{ext}")
                        with open(temp_preview_path, 'wb') as out_f:
                            out_f.write(z.read(target_entry))
                
                if temp_preview_path and os.path.exists(temp_preview_path):
                    caption = f"🖼️ <b>[{target_agent}] 歷史備份 #{idx} 預覽</b>\n檔案：<code>{filename}</code>\n時間：{mtime}\n大小：{size_kb:.1f} KB"
                    file_type = 'sticker' if temp_preview_path.endswith('.webm') else 'photo'
                    if file_type == 'sticker':
                        self.notifier.notify_file(msg.source, temp_preview_path, file_type=file_type)
                        self.notifier.notify(msg.source, 'custom', {'content': caption})
                    else:
                        self.notifier.notify_file(msg.source, temp_preview_path, file_type=file_type, caption=caption)
            except Exception as e:
                logger.error(f"❌ [Router] 提取備份 #{idx} 預覽圖失敗: {e}")
            finally:
                if temp_preview_path and os.path.exists(temp_preview_path):
                    try:
                        os.remove(temp_preview_path)
                    except:
                        pass

    def _restore_avatar_backup(self, msg, target_agent, restore_target):
        import glob
        import zipfile
        if not restore_target:
            self.notifier.notify(msg.source, 'custom', {'content': f'⚠️ 請指定要還原的備份編號或檔名，例如 <code>/avatar_renew restore 1</code>'})
            return
            
        avatar_dir = os.path.join(AGENT_HOME_BASE, target_agent, "avatar")
        history_zips = sorted(
            glob.glob(os.path.join(avatar_dir, "history_*.zip")),
            key=os.path.getmtime,
            reverse=True
        )
        
        target_zip = None
        try:
            idx = int(restore_target)
            if 1 <= idx <= len(history_zips):
                target_zip = history_zips[idx - 1]
        except ValueError:
            pass
            
        if not target_zip:
            for path in history_zips:
                if os.path.basename(path) == restore_target or os.path.basename(path).replace(".zip", "") == restore_target:
                    target_zip = path
                    break
                    
        if not target_zip:
            self.notifier.notify(msg.source, 'custom', {'content': f'❌ 找不到指定的備份檔: <code>{restore_target}</code>。請使用 <code>/avatar_renew list</code> 查看。'})
            return
            
        try:
            base_png_file = os.path.join(avatar_dir, "base.png")
            base_webm_file = os.path.join(avatar_dir, "base.webm")
            if os.path.exists(base_png_file) or os.path.exists(base_webm_file):
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                current_backup = os.path.join(avatar_dir, f"history_{timestamp_str}.zip")
                
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip_file:
                    tmp_zip_name = tmp_zip_file.name
                with zipfile.ZipFile(tmp_zip_name, 'w', zipfile.ZIP_DEFLATED) as hz:
                    for root, dirs, files in os.walk(avatar_dir):
                        for file in files:
                            if file.startswith("history_") and file.endswith(".zip"):
                                continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, avatar_dir)
                            hz.write(file_path, arcname)
                import shutil
                shutil.move(tmp_zip_name, current_backup)
                
            for root, dirs, files in os.walk(avatar_dir, topdown=False):
                for file in files:
                    if file.startswith("history_") and file.endswith(".zip"):
                        continue
                    os.remove(os.path.join(root, file))
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        os.rmdir(dir_path)
                    except:
                        pass
                        
            with zipfile.ZipFile(target_zip, 'r') as z:
                z.extractall(avatar_dir)
                
            history_zips = sorted(
                glob.glob(os.path.join(avatar_dir, "history_*.zip")),
                key=os.path.getmtime
            )
            while len(history_zips) > 5:
                oldest = history_zips.pop(0)
                os.remove(oldest)
                
            self.notifier.notify(msg.source, 'custom', {'content': f'✅ <b>[{target_agent}]</b> 頭像已成功從 <code>{os.path.basename(target_zip)}</code> 還原！'})
            
        except Exception as e:
            logger.error(f"❌ [Router] 還原頭像失敗: {e}")
            self.notifier.notify(msg.source, 'custom', {'content': f'❌ <b>[{target_agent}]</b> 還原頭像失敗: {str(e)}'})

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
@app.route('/awake/jobs/<job_id>', methods=['PUT'])
def awake_update(job_id):
    data = request.get_json(); return jsonify(awake.update_job(job_id, data))
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

@app.route('/inter-agent/message', methods=['POST'])
def inter_agent_message():
    """
    接收 Agent 之間的橫向通訊請求，並透過 Injector 物理注入至目標 Tmux。
    """
    data = request.get_json()
    if not data:
        return jsonify({"status": "failed", "error": "Invalid JSON"}), 400
        
    source = data.get('source')
    target_agent = data.get('target_agent')
    message = data.get('message')
    
    if not source or not target_agent or not message:
        return jsonify({"status": "failed", "error": "Missing required fields: 'source', 'target_agent', 'message'"}), 400
        
    logger.info(f"🔄 [Inter-Agent] 收到橫向通訊請求 | 來源: {source} -> 目標: {target_agent}")
    
    agent_dir = os.path.join(AGENT_HOME_BASE, target_agent)
    flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
    pending_agent_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_agent.txt')

    # 封裝 AGENT_INTERCOM_SOP (將發送方與內容組合為完整 System Prompt)
    from config import get_agent_intercom_sop
    formatted_message = get_agent_intercom_sop(source, message)

    if os.path.exists(flag_file):
        try:
            with open(pending_agent_file, 'a', encoding='utf-8') as f:
                if os.path.exists(pending_agent_file) and os.path.getsize(pending_agent_file) > 0:
                    f.write("\n\n")
                f.write(formatted_message)
            logger.info(f"👻 [Inter-Agent] {target_agent} 正在重整，訊息已暫存至 pending_agent.txt")
            return jsonify({"status": "success", "message": "queued in pending_agent.txt"}), 200
        except Exception as e:
            logger.error(f"❌ [Router] 寫入 pending_agent 暫存檔失敗: {e}")

    # 調用 AtomicInjector 進行物理按鍵注入
    # 強制 interrupt_first=False，保留 User 的絕對中斷特權，Agent 訊息僅能排隊
    success = handler.injector.inject(formatted_message, target_agent, interrupt_first=False)
    
    return jsonify({"status": "success" if success else "failed"}), 200

@app.route('/inject', methods=['POST'])
def inject():
    data = request.get_json()
    msg = MCMessage(source=data['source'], user_id=data['user_id'], username=data.get('username', 'User'), content=data['content'], metadata=data.get('metadata', {}))
    
    # 📸 多媒體路徑日誌
    if 'local_path' in msg.metadata:
        logger.info(f"📸 [Router] 接收到多媒體訊息: {msg.metadata['local_path']} (Source: {msg.source})")
        
    success = handler.handle(msg)
    return jsonify({"status": "success" if success else "failed"}), 200

@app.route('/api/internal/avatar/update', methods=['POST'])
def update_avatar():
    try:
        agent_name = request.form.get('agent_name')
        token = request.form.get('token', '')
        archive = request.files.get('archive')
        
        if not agent_name or not archive:
            return jsonify({"status": "failed", "error": "Missing agent_name or archive"}), 400
            
        avatar_dir = os.path.join(AGENT_HOME_BASE, agent_name, "avatar")
        base_png_file = os.path.join(avatar_dir, "base.png")
        base_webm_file = os.path.join(avatar_dir, "base.webm")
        
        # [機制判斷] 檢查是否為「首刷無頭像」狀態
        is_first_blood = not (os.path.exists(base_png_file) or os.path.exists(base_webm_file))
        
        if is_first_blood:
            # [豁免放行] 首刷期間不強制要求 Token
            logger.info(f"✨ [Router] Agent '{agent_name}' 處於首刷無頭像狀態，豁免 Token 校驗。")
        else:
            # [嚴格審核] 已有頭像，啟動嚴格驗證
            token_data = avatar_tokens.get(agent_name)
            if not token_data or token_data["token"] != token:
                logger.warning(f"❌ [Router] Agent '{agent_name}' 更新 Avatar 失敗：Token 無效或缺失。")
                return jsonify({"status": "failed", "error": "Unauthorized: Invalid or missing token"}), 401
            if datetime.now() > token_data["expires_at"]:
                logger.warning(f"❌ [Router] Agent '{agent_name}' 更新 Avatar 失敗：Token 已過期。")
                return jsonify({"status": "failed", "error": "Unauthorized: Token expired"}), 401
                
            # 驗證成功，立刻銷毀 Token (Burn)
            del avatar_tokens[agent_name]
            logger.info(f"🔥 [Router] Agent '{agent_name}' Token 校驗通過，已立刻銷毀 Token。")
            
        # [備份舊有 Avatar - 保留 5 代]
        if os.path.exists(avatar_dir) and not is_first_blood:
            try:
                import glob
                import shutil
                import zipfile
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                history_zip_path = os.path.join(avatar_dir, f"history_{timestamp_str}.zip")
                
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip_file:
                    tmp_zip_name = tmp_zip_file.name
                
                with zipfile.ZipFile(tmp_zip_name, 'w', zipfile.ZIP_DEFLATED) as hz:
                    for root, dirs, files in os.walk(avatar_dir):
                        for file in files:
                            if file.startswith("history_") and file.endswith(".zip"):
                                continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, avatar_dir)
                            hz.write(file_path, arcname)
                
                shutil.move(tmp_zip_name, history_zip_path)
                logger.info(f"💾 [Router] 已備份舊頭像至 {history_zip_path}")
                
                history_zips = sorted(
                    glob.glob(os.path.join(avatar_dir, "history_*.zip")),
                    key=os.path.getmtime
                )
                while len(history_zips) > 5:
                    oldest = history_zips.pop(0)
                    os.remove(oldest)
                    logger.info(f"🗑️ [Router] 清理最舊的備份檔: {oldest}")
            except Exception as e:
                logger.error(f"⚠️ [Router] 備份舊 Avatar 失敗: {e}")

        # [高權解包代寫] 讀取 ZIP 並覆蓋解壓縮至 avatar/ 目錄
        import zipfile
        import io
        zip_bytes = archive.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            os.makedirs(avatar_dir, exist_ok=True)
            # 安全性檢查：防止 Zip Slip 漏洞
            for member in z.namelist():
                filename = os.path.basename(member)
                if not filename:
                    continue  # 忽略目錄項
                # 限制解壓出來的檔案只能寫在 avatar_dir 之下，不允許相對路徑逃逸
                target_path = os.path.abspath(os.path.join(avatar_dir, member))
                if not target_path.startswith(os.path.abspath(avatar_dir)):
                    logger.warning(f"⚠️ [Router] 偵測到潛在的 Zip Slip 攻擊，拒絕解壓外部路徑: {member}")
                    return jsonify({"status": "failed", "error": "Invalid zip entry path"}), 400
            z.extractall(avatar_dir)
            
        logger.info(f"✅ [Router] Agent '{agent_name}' Avatar 檔案成功解包並寫入目錄。")
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"❌ [Router] 更新 Avatar 過程中發生異常: {e}")
        return jsonify({"status": "failed", "error": str(e)}), 500

if __name__ == '__main__':
    awake.start()
    app.run(host=ROUTER_HOST, port=ROUTER_PORT)
