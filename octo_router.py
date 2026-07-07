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
🔄 OctoMatrix Router (octo_router.py) - Ultimate Stable Feature Parity Version (Fix Loop Recursion)
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

# Solidify port information
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
                    subprocess.run(['tmux', 'send-keys', '-t', target, 'C-c', 'Escape'], check=False)
                    time.sleep(0.5)
                    return True
                return False
            except Exception as e:
                logger.error(f"❌ [Injector] capture-pane failed: {e}")
                return False
        else:
            subprocess.run(['tmux', 'send-keys', '-t', target, 'C-c', 'Escape'], check=False)
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
                    logger.error(f"❌ [Injector] Cannot find Tmux window: {agent_name}")
                    return False
                target = f"{self.session_name}:{agent_name}"

                if interrupt_first:
                    # 🚀 State-aware interruption for Codex, unconditional for others
                    self.send_interrupt(agent_name)

                escaped = content.replace('!', '！').replace('$', '\\$')

                # 🚀 Physical injection hardening: text and Enter physically separated
                subprocess.run(['tmux', 'send-keys', '-t', target, '\x1b[200~'])
                subprocess.run(['tmux', 'send-keys', '-t', target, '-l', '--', escaped], check=True)
                subprocess.run(['tmux', 'send-keys', '-t', target, '\x1b[201~'])
                time.sleep(1.2)
                subprocess.run(['tmux', 'send-keys', '-t', target, 'Enter'], check=True)

                # 🚀 Force execution of double Enter protocol
                time.sleep(1.2)
                subprocess.run(['tmux', 'send-keys', '-t', target, 'Enter'], check=True)
                self.last_inject_time = time.time()
                return True
            except Exception as e:
                logger.error(f"❌ [Injector] Physical injection failed: {e}")
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

        # 1. Handle waiting for input state (non-recursive)
        if msg.user_id in USER_STATES:
            state = USER_STATES[msg.user_id]
            content = state['command_template'].replace('{input}', content)
            del USER_STATES[msg.user_id]

        # 2. Handle menu label translation (non-recursive)
        for row in CUSTOM_MENU:
            for item in row:
                label = item.get('label') if isinstance(item, dict) else item
                if content == label:
                    command = item.get('command', '')
                    if '{input}' in command:
                        USER_STATES[msg.user_id] = {'command_template': command}
                        self.notifier.notify(msg.source, 'custom', {'content': f"📋 <b>Waiting for Input</b>\n\n{item.get('prompt', 'Please enter content:')}"})
                        return True
                    content = command # Physical content replacement, execute downward, no recursion

        cmd_content = content.lower().strip()

        def is_cmd(c, name): return c == name or c.startswith(name + ' ')

        # 3. Core command handling branches
        interfering_cmds = ['/interrupt', '/clear', '/resume_latest', '/sys_refresh']
        is_interfering = cmd_content in interfering_cmds or is_cmd(cmd_content, '/inspect') or is_cmd(cmd_content, '/fix') or is_cmd(cmd_content, '/avatar_renew')

        if is_interfering:
            flag_file = os.path.join(AGENT_HOME_BASE, target_agent, 'octo_cyberbrain', '.rotation_flag')
            if os.path.exists(flag_file) and msg.source != 'system_flush':
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> System is undergoing GHOST deep reorganization, please wait until reset completes before executing window-interfering commands.'})
                return True

        if is_cmd(cmd_content, '/switch'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1].lower()
                found = next((a for a in AGENTS if a['name'].lower() == target), None)
                if found:
                    CURRENT_AGENT = found['name']
                    self.notifier.notify(msg.source, 'custom', {'content': f'🫧 <code>{CURRENT_AGENT}</code> is waiting for your call'})
            return True
        elif cmd_content == '/status':
            self._send_status(msg); return True
        elif cmd_content == '/help':
            self._send_help(msg); return True
        elif cmd_content == '/menu':
            self._send_menu(msg); return True
        elif cmd_content == '/interrupt':
            if not check_cooldown(target_agent, 'interrupt'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> Operation cooling down, please try again later.'})
                return True
            target_info = get_agent_info(target_agent)
            engine = target_info.get('engine', '').lower() if target_info else 'gemini'
            if engine == 'codex':
                target = f'{TMUX_SESSION_NAME}:{target_agent}'
                res = subprocess.run(['tmux', 'capture-pane', '-p', '-t', target], capture_output=True, text=True)
                lines = [line for line in res.stdout.split('\n') if line.strip()]
                if 'Working (' in '\n'.join(lines[-20:]):
                    subprocess.run(['tmux', 'send-keys', '-t', target, 'C-c', 'Escape'], check=False)
                    self.notifier.notify(msg.source, 'custom', {'content': f'🛑 Interrupt signal sent to <b>[{target_agent}]</b>'})
                else:
                    self.notifier.notify(msg.source, 'custom', {'content': f'⚠️ <b>[{target_agent}]</b> is idle. Interrupt bypassed.'})
            else:
                subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'C-c', 'Escape'], check=False)
                self.notifier.notify(msg.source, 'custom', {'content': f'🛑 Interrupt signal sent to <b>[{target_agent}]</b>'})
            return True
        elif cmd_content == '/clear':
            if not check_cooldown(target_agent, 'clear'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> Operation cooling down, please try again later.'})
                return True
            self.injector.send_interrupt(target_agent)
            self.injector.inject('/clear', target_agent)
            self.notifier.notify(msg.source, 'custom', {'content': f'🧹 Cleared screen and context for <b>[{target_agent}]</b>'})
            return True
        elif cmd_content == '/resume_latest':
            if not check_cooldown(target_agent, 'resume_latest'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> Operation cooling down, please try again later.'})
                return True
            # 🚀 Enter key physical optimization: only call inject, no manual Enter supplement to prevent Loop
            self.injector.inject('/resume', target_agent)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'Escape'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🧠 Attempted to resume <b>[{target_agent}]</b> latest conversation'})
            return True
        elif cmd_content == '/sys_refresh':
            if not check_cooldown(target_agent, 'sys_refresh'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> Operation cooling down, please try again later.'})
                return True
            target_info = get_agent_info(target_agent)
            engine = target_info.get('engine', '').lower() if target_info else 'gemini'
            usecase = target_info.get('usecase', 'No description') if target_info else 'No description'
            if engine == "claude":
                engine_doc_name = "CLAUDE.md"
            elif engine == "codex":
                engine_doc_name = "AGENTS.md"
            elif engine == "agy":
                engine_doc_name = "GEMINI.md"
            else:
                engine_doc_name = "GEMINI.md"

            home_path = os.path.join(AGENT_HOME_BASE, target_agent)
            rules_path = os.path.join(home_path, 'agent_home_rules.md')
            protocol_path = os.path.join(home_path, 'AGENT_PROTOCOL.md')

            collab_context_lines = []
            for grp in COLLABORATION_GROUPS:
                if target_agent in grp.get('members', []):
                    collab_context_lines.append(f"- Team: {grp.get('name')} ({grp.get('description', '')})")
                    collab_context_lines.append("  Team member responsibilities:")
                    roles = grp.get('roles', {})
                    for member, role in roles.items():
                        marker = " (You)" if member == target_agent else ""
                        collab_context_lines.append(f"  * {member}{marker}: {role}")
                    collab_context_lines.append("")
            collab_context = "\n".join(collab_context_lines) if collab_context_lines else "No specific collaboration team configuration."

            template_path = os.path.join(script_dir, 'agent_rule_gen_template.txt')
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    gen_template = f.read()
                check_prompt = f"{SYS_PREFIX}\n" + (gen_template.replace('{agent_name}', target_agent)
                                     .replace('{agent_usecase}', usecase)
                                     .replace('{engine_doc_name}', engine_doc_name)
                                     .replace('{rules_path}', rules_path)
                                     .replace('{protocol_path}', protocol_path)
                                     .replace('{collaboration_context}', collab_context)
                                     .replace('{home_path}', home_path))
            except Exception as e:
                logger.error(f"❌ [Router] Cannot read specification template: {e}")
                self.notifier.notify(msg.source, 'custom', {'content': f'❌ <b>[{target_agent}]</b> Specification rebuild failed: Cannot read template ({e})'})
                return True

            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '\x1b[200~'])
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '-l', '--', check_prompt], check=False)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '\x1b[201~'])
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'Enter'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🔄 Sent full specification rebuild command to <b>[{target_agent}]</b>'})
            return True
        elif is_cmd(cmd_content, '/avatar_renew'):
            if not check_cooldown(target_agent, 'avatar_renew'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> Operation cooling down, please try again later.'})
                return True
            parts = content.split(' ', 1)
            requirement = parts[1].strip() if len(parts) > 1 else "No specific requirement"
            
            # [Command Intercept] Check if it is a history management command
            req_lower = requirement.lower()
            if req_lower == 'list':
                self._list_avatar_backups(msg, target_agent)
                return True
            elif req_lower.startswith('restore'):
                restore_parts = requirement.split(None, 1)
                restore_target = restore_parts[1].strip() if len(restore_parts) > 1 else ""
                self._restore_avatar_backup(msg, target_agent, restore_target)
                return True
                
            # Generate Token expiring in 5 minutes
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
            self.notifier.notify(msg.source, 'custom', {'content': f'🎨 Assigned <b>[{target_agent}]</b> to update Avatar...'})
            return True
        elif is_cmd(cmd_content, '/inspect'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1]
                res = subprocess.run(['tmux', 'capture-pane', '-t', f'{TMUX_SESSION_NAME}:{target}', '-p'], capture_output=True, text=True)
                output = "\n".join(res.stdout.split('\n')[-50:])
                import config
                prompt = f"""{config.USER_MESSAGE_SOP}

Message from {MATRIX_USERNAME}:
以下是目前 {target} 的狀態，請分析...
{output}

{SYS_PREFIX} Please strictly follow the [SOP] above to reply."""
                self.injector.inject(prompt, target_agent)
                self.notifier.notify(msg.source, 'custom', {'content': f'🔍 Assigned {target_agent} to inspect {target}...'})
            return True
        elif is_cmd(cmd_content, '/fix'):
            parts = content.split()
            if len(parts) > 1:
                target_name = parts[1]
                target_info = get_agent_info(target_name)
                if target_info:
                    engine = target_info.get('engine', '').lower()
                    self.notifier.notify(msg.source, 'custom', {'content': f'🚑 System initiating Hard Reset for <b>[{target_name}]</b> (engine: {engine})...'})
                    try:
                        # Create .fix_flag to activate pending message block
                        agent_dir = os.path.join(AGENT_HOME_BASE, target_name)
                        fix_flag = os.path.join(agent_dir, 'octo_cyberbrain', '.fix_flag')
                        try:
                            os.makedirs(os.path.dirname(fix_flag), exist_ok=True)
                            open(fix_flag, 'w').close()
                        except: pass

                        subprocess.run(['tmux', 'kill-window', '-t', f'{TMUX_SESSION_NAME}:{target_name}'], check=False)
                        time.sleep(1)
                        # Call setup_agent_env.py directly to rebuild the agent window
                        subprocess.Popen(['python3', os.path.join(script_dir, 'setup_agent_env.py'), '--agent', target_name])
                        self.notifier.notify(msg.source, 'custom', {'content': f'✅ <b>[{target_name}]</b> restart sequence initiated. Please wait for the agent to reconnect.'})
                    except Exception as e:
                        self.notifier.notify(msg.source, 'custom', {'content': f'❌ Failed to reset {target_name}: {e}'})
                else:
                    self.notifier.notify(msg.source, 'custom', {'content': f'❌ Cannot find Agent in config: {target_name}'})
            return True
        elif is_cmd(cmd_content, '/capture'):
            parts = content.split()
            if len(parts) > 1:
                cap_target = parts[1]
                res = subprocess.run(['tmux', 'capture-pane', '-t', f'{TMUX_SESSION_NAME}:{cap_target}', '-p'], capture_output=True, text=True)
                output = "\n".join(res.stdout.split('\n')[-50:])
                self.notifier.notify(msg.source, 'custom', {'content': f"📸 <b>[{cap_target}]</b> Screen capture:\n<code>{output}</code>"})
            return True

        # Status recording and injection
        if msg.source in ['telegram', 'discord', 'slack']:
            source_file = os.path.join(script_dir, '.last_source')
            try:
                source_data = {'platform': msg.source, 'user_id': msg.user_id, 'username': msg.username, 'timestamp': datetime.now().isoformat()}
                with open(source_file, 'w') as f: json.dump(source_data, f)
            except: pass

        # 🛡️ Inject standard SOP (Matrix message processing flow)
        # ==========================================
        if msg.source in ['telegram', 'discord', 'slack', 'awake'] and 'Execute the following [SOP]:' not in content:
            from config import USER_MESSAGE_SOP
            sop = f"""{USER_MESSAGE_SOP}

Message from {MATRIX_USERNAME}:
{content}

{SYS_PREFIX} Please strictly follow the [SOP] above to reply."""
            final_message = sop
        else:
            final_message = content

        # 👻 GHOST physical file blocking and accumulation mechanism
        agent_dir = os.path.join(AGENT_HOME_BASE, target_agent)
        flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
        fix_flag = os.path.join(agent_dir, 'octo_cyberbrain', '.fix_flag')
        pending_user_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_user.txt')

        if msg.source != 'system_flush' and (os.path.exists(flag_file) or os.path.exists(fix_flag)):
            try:
                with open(pending_user_file, 'a', encoding='utf-8') as f:
                    if os.path.exists(pending_user_file) and os.path.getsize(pending_user_file) > 0:
                        f.write("\n\n")
                    f.write(content) # Only store pure user messages
                if msg.source != 'awake':
                    self.notifier.notify(msg.source, 'custom', {'content': f'🐚 <b>{target_agent}</b> 正在喚醒深海回音，靜靜聆聽……'})
                    sleepy_path = os.path.join(agent_dir, 'avatar/emojis/sleepy.png')
                    if os.path.exists(sleepy_path):
                        self.notifier.notify_file(msg.source, sleepy_path, file_type='sticker')
                return True
            except Exception as e:
                logger.error(f"❌ [Router] Failed to write temporary file: {e}")

        success = self.injector.inject(final_message, target_agent, interrupt_first=(msg.source not in ['awake', 'system_flush']))
        if success and msg.source != 'awake':
            self.notifier.notify(msg.source, 'matrix_connected', {'timestamp': timestamp, 'agent_name': target_agent})
            
            # Automatically send Agent Avatar sticker
            avatar_dir = os.path.join(agent_dir, 'avatar')
            base_png = os.path.join(avatar_dir, 'base.png')
            sticker_path = None
            if os.path.exists(base_png):
                sticker_path = base_png
            else:
                import glob
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
            active = " (⭐ Active)" if name == CURRENT_AGENT else ""
            role_info = f"\n      └ {agent_role_map[name]}" if name in agent_role_map else ""
            agent_status_list.append(f"{status} <b>[{name}]</b> {a.get('description', '')}{active}{role_info}")

        awake_list = []
        if self.awake:
            jobs = self.awake.list_jobs().get('jobs', [])
            for j in jobs:
                nr = j.get('next_run_time', 'Not awoken').split('.')[0]
                p = j.get('prompt', 'No command')
                if len(p) > 500: p = p[:497] + "..."
                awake_list.append(f"• <b>{j.get('id', '?')}</b>\n  └ Target: {j.get('target_agent', 'Unspecified')}\n  └ Trigger: {j.get('trigger', '?')}\n  └ Command: <code>{p}</code>\n  └ Next: {nr}")

        channels_status = []
        try:
            tg_stat = "🟢" if subprocess.run(['curl', '-s', f'http://localhost:{TELEGRAM_GATEWAY_PORT}/health'], timeout=2).returncode == 0 else "🔴"
        except: tg_stat = "🔴"
        channels_status.append(f"• Telegram: {tg_stat}")
        channels_status.append(f"• Discord: {'🟢' if subprocess.run(['pgrep', '-f', 'discord_gateway.py']).returncode == 0 else '🔴'}")
        channels_status.append(f"• Slack: {'🟢' if subprocess.run(['pgrep', '-f', 'slack_socket_gateway.py']).returncode == 0 else '🔴'}")

        status_text = "📊 <b>OctoMatrix Status Report</b>\n\n" + \
                      "🤖 <b>Agent Squad:</b>\n" + "\n".join(agent_status_list) + "\n\n" + \
                      "⏰ <b>Awake System:</b>\n" + ("\n".join(awake_list) if awake_list else "No active tasks") + "\n\n" + \
                      "🌐 <b>Channel Status:</b>\n" + "\n".join(channels_status)
        self.notifier.notify(msg.source, 'custom', {'content': status_text})

    def _send_help(self, msg: MCMessage):
        import config
        help_text = config.get_help_text(CURRENT_AGENT)
        self.notifier.notify(msg.source, 'custom', {'content': help_text})

    def _send_menu(self, msg: MCMessage):
        if msg.source == 'telegram':
            kb = [[item.get('label') if isinstance(item, dict) else item for item in row] for row in CUSTOM_MENU]
            platform_kwargs = {'reply_markup': json.dumps({'keyboard': kb, 'resize_keyboard': True, 'one_time_keyboard': True})}
            self.notifier.notify(msg.source, 'custom', {'content': "📱 <b>OctoMatrix Management Menu</b>\nPlease select the function to execute:", '_platform_kwargs': platform_kwargs})
        else:
            self.notifier.notify(msg.source, 'custom', {'content': "🎮 Please send <code>/help</code> to see available commands."})

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
            self.notifier.notify(msg.source, 'custom', {'content': f'📂 <b>[{target_agent}]</b> Currently has no historical avatar backups.'})
            return
            
        content_text = f"📂 <b>[{target_agent}] Historical Avatar Backups:</b>\n\n"
        for idx, path in enumerate(history_zips, 1):
            filename = os.path.basename(path)
            size_kb = os.path.getsize(path) / 1024.0
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            content_text += f"{idx}. <code>{filename}</code> ({size_kb:.1f} KB) - {mtime}\n"
        content_text += "\n💡 Tips: Use <code>/avatar_renew restore &lt;index&gt;</code> (e.g., <code>/avatar_renew restore 1</code>) to restore.\n⏳ Extracting and sending `base.png` previews for each backup in the background..."
        self.notifier.notify(msg.source, 'custom', {'content': content_text})

        # Extract and send preview images sequentially
        for idx, path in enumerate(history_zips, 1):
            filename = os.path.basename(path)
            size_kb = os.path.getsize(path) / 1024.0
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            
            temp_preview_path = os.path.join("/tmp", f"preview_{target_agent}_{idx}_{int(time.time())}.png")
            try:
                with zipfile.ZipFile(path, 'r') as z:
                    target_entry = None
                    for entry in z.namelist():
                        if entry == "base.png" or entry.endswith("/base.png"):
                            target_entry = entry
                            break
                    if target_entry:
                        with open(temp_preview_path, 'wb') as out_f:
                            out_f.write(z.read(target_entry))
                
                if os.path.exists(temp_preview_path):
                    caption = f"🖼️ <b>[{target_agent}] History Backup #{idx} Preview</b>\nFile: <code>{filename}</code>\nTime: {mtime}\nSize: {size_kb:.1f} KB"
                    self.notifier.notify_file(msg.source, temp_preview_path, file_type='photo', caption=caption)
            except Exception as e:
                logger.error(f"❌ [Router] Failed to extract backup #{idx} preview: {e}")
            finally:
                if os.path.exists(temp_preview_path):
                    try:
                        os.remove(temp_preview_path)
                    except:
                        pass

    def _restore_avatar_backup(self, msg, target_agent, restore_target):
        import glob
        import zipfile
        if not restore_target:
            self.notifier.notify(msg.source, 'custom', {'content': f'⚠️ Please specify the backup index or filename to restore, e.g., <code>/avatar_renew restore 1</code>'})
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
            self.notifier.notify(msg.source, 'custom', {'content': f'❌ Cannot find specified backup: <code>{restore_target}</code>. Use <code>/avatar_renew list</code> to see available backups.'})
            return
            
        try:
            base_png_file = os.path.join(avatar_dir, "base.png")
            if os.path.exists(base_png_file):
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
                
            self.notifier.notify(msg.source, 'custom', {'content': f'✅ <b>[{target_agent}]</b> Avatar has been successfully restored from <code>{os.path.basename(target_zip)}</code>!'})
            
        except Exception as e:
            logger.error(f"❌ [Router] Failed to restore avatar: {e}")
            self.notifier.notify(msg.source, 'custom', {'content': f'❌ <b>[{target_agent}]</b> Failed to restore avatar: {str(e)}'})

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
        # 🚀 Relax timeout to 60 seconds to prevent image download delays from triggering Telegram retry mechanism
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
    Receive horizontal communication requests between Agents, and physically inject into target Tmux via Injector.
    """
    data = request.get_json()
    if not data:
        return jsonify({"status": "failed", "error": "Invalid JSON"}), 400
        
    source = data.get('source')
    target_agent = data.get('target_agent')
    message = data.get('message')
    
    if not source or not target_agent or not message:
        return jsonify({"status": "failed", "error": "Missing required fields: 'source', 'target_agent', 'message'"}), 400
        
    logger.info(f"🔄 [Inter-Agent] Received horizontal communication request | Source: {source} -> Target: {target_agent}")
    
    agent_dir = os.path.join(AGENT_HOME_BASE, target_agent)
    flag_file = os.path.join(agent_dir, 'octo_cyberbrain', '.rotation_flag')
    pending_agent_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_agent.txt')

    # Encapsulate AGENT_INTERCOM_SOP (combine sender and content into full System Prompt)
    from config import get_agent_intercom_sop
    formatted_message = get_agent_intercom_sop(source, message)

    if os.path.exists(flag_file):
        try:
            with open(pending_agent_file, 'a', encoding='utf-8') as f:
                if os.path.exists(pending_agent_file) and os.path.getsize(pending_agent_file) > 0:
                    f.write("\n\n")
                f.write(formatted_message)
            logger.info(f"👻 [Inter-Agent] {target_agent} is reorganizing, message queued to pending_agent.txt")
            return jsonify({"status": "success", "message": "queued in pending_agent.txt"}), 200
        except Exception as e:
            logger.error(f"❌ [Router] Failed to write to pending_agent temporary file: {e}")

    # Call AtomicInjector for physical keystroke injection
    # Force interrupt_first=False, retaining User's absolute interrupt privilege, Agent messages can only queue
    success = handler.injector.inject(formatted_message, target_agent, interrupt_first=False)
    
    return jsonify({"status": "success" if success else "failed"}), 200

@app.route('/inject', methods=['POST'])
def inject():
    data = request.get_json()
    msg = MCMessage(source=data['source'], user_id=data['user_id'], username=data.get('username', 'User'), content=data['content'], metadata=data.get('metadata', {}))

    # 📸 Multimedia path logging
    if 'local_path' in msg.metadata:
        logger.info(f"📸 [Router] Received multimedia message: {msg.metadata['local_path']} (Source: {msg.source})")

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
        
        # [Mechanics Check] Check if agent is in "First-Blood" (no base avatar) state
        is_first_blood = not os.path.exists(base_png_file)
        
        if is_first_blood:
            # [Exempt Pass] Bypass Token validation during First-Blood phase
            logger.info(f"✨ [Router] Agent '{agent_name}' is in First-Blood state. Bypassing Token validation.")
        else:
            # [Strict Check] Verification is required once base avatar exists
            token_data = avatar_tokens.get(agent_name)
            if not token_data or token_data["token"] != token:
                logger.warning(f"❌ [Router] Agent '{agent_name}' failed to update Avatar: Invalid or missing token.")
                return jsonify({"status": "failed", "error": "Unauthorized: Invalid or missing token"}), 401
            if datetime.now() > token_data["expires_at"]:
                logger.warning(f"❌ [Router] Agent '{agent_name}' failed to update Avatar: Token expired.")
                return jsonify({"status": "failed", "error": "Unauthorized: Token expired"}), 401
                
            # Burn Token immediately upon success
            del avatar_tokens[agent_name]
            logger.info(f"🔥 [Router] Agent '{agent_name}' Token validation passed. Token has been burned.")
            
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

        # [High-Privilege Archive Unpacking] Read ZIP and extract with overwrite to avatar/ directory
        import zipfile
        import io
        zip_bytes = archive.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            os.makedirs(avatar_dir, exist_ok=True)
            # Security Check: Prevent Zip Slip Vulnerability
            for member in z.namelist():
                filename = os.path.basename(member)
                if not filename:
                    continue  # Ignore directories
                # Limit extraction strictly under avatar_dir
                target_path = os.path.abspath(os.path.join(avatar_dir, member))
                if not target_path.startswith(os.path.abspath(avatar_dir)):
                    logger.warning(f"⚠️ [Router] Potential Zip Slip attack detected. Refusing to extract entry: {member}")
                    return jsonify({"status": "failed", "error": "Invalid zip entry path"}), 400
            z.extractall(avatar_dir)
            
        logger.info(f"✅ [Router] Agent '{agent_name}' Avatar archive unpacked and written successfully.")
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"❌ [Router] Exception occurred during Avatar update: {e}")
        return jsonify({"status": "failed", "error": str(e)}), 500

if __name__ == '__main__':
    awake.start()
    app.run(host=ROUTER_HOST, port=ROUTER_PORT)
