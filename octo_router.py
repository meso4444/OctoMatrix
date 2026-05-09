#!/usr/bin/env python3
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

    def check_session(self, window_name: str) -> bool:
        try:
            result = subprocess.run(['tmux', 'has-session', '-t', f'{self.session_name}:{window_name}'], capture_output=True)
            return result.returncode == 0
        except: return False

    def inject(self, content: str, agent_name: str, interrupt_first: bool = False) -> bool:
        with self.lock:
            try:
                if not self.check_session(agent_name): 
                    logger.error(f"❌ [Injector] Cannot find Tmux window: {agent_name}")
                    return False
                target = f"{self.session_name}:{agent_name}"

                if interrupt_first:
                    # 🚀 Active interruption by user: send Ctrl+C first to interrupt possible long-running tasks
                    subprocess.run(['tmux', 'send-keys', '-t', target, 'C-c'], check=True)
                    time.sleep(0.5)

                escaped = content.replace('!', '！').replace('$', '\\$')

                # 🚀 Physical injection hardening: text and Enter physically separated
                subprocess.run(['tmux', 'send-keys', '-t', target, '-l', escaped], check=True)
                time.sleep(0.8)
                subprocess.run(['tmux', 'send-keys', '-t', target, 'Enter'], check=True)

                # 🚀 Force execution of double Enter protocol
                time.sleep(0.3)
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

        # 3. Core command handling branches
        if cmd_content.startswith('/switch'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1].lower()
                found = next((a for a in AGENTS if a['name'].lower() == target), None)
                if found:
                    CURRENT_AGENT = found['name']
                    self.notifier.notify(msg.source, 'custom', {'content': f'⚡ <b>Conversation switched successfully</b>\n Current active Agent: <code>{CURRENT_AGENT}</code>'})
            return True
        elif cmd_content in ['/status', 'status', 'status', '/health', 'health']:
            self._send_status(msg); return True
        elif cmd_content in ['/help', 'help', 'help', 'help']:
            self._send_help(msg); return True
        elif cmd_content in ['/menu', '/start', 'menu', 'start', 'menu']:
            self._send_menu(msg); return True
        elif cmd_content in ['/interrupt', '/stop', 'interrupt', 'stop', 'interrupt']:
            if not check_cooldown(target_agent, 'interrupt'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> Operation cooling down, please try again later.'})
                return True
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'C-c'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🛑 Interrupt signal sent to <b>[{target_agent}]</b>'})
            return True
        elif cmd_content in ['/clear', 'clear', 'clear', 'clear context', 'reset']:
            if not check_cooldown(target_agent, 'clear'):
                self.notifier.notify(msg.source, 'custom', {'content': f'⏳ <b>[{target_agent}]</b> Operation cooling down, please try again later.'})
                return True
            self.injector.inject('/clear', target_agent)
            self.notifier.notify(msg.source, 'custom', {'content': f'🧹 Cleared screen and context for <b>[{target_agent}]</b>'})
            return True
        elif cmd_content in ['/resume_latest', 'resume context', 'resume latest state']:
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
            if engine == "claude":
                engine_doc_name = "CLAUDE.md"
            elif engine == "codex":
                engine_doc_name = "AGENTS.md"
            else:
                engine_doc_name = "GEMINI.md"
            check_prompt = f"[System Prompt]This task does not send notification to user. Check AGENT_PROTOCOL.md content, confirm whether {engine_doc_name} specification is complete, and update"
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', '-l', check_prompt], check=False)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{TMUX_SESSION_NAME}:{target_agent}', 'Enter'], check=False)
            self.notifier.notify(msg.source, 'custom', {'content': f'🔄 Sent specification update command to <b>[{target_agent}]</b>'})
            return True
        elif cmd_content.startswith('/inspect'):
            parts = content.split()
            if len(parts) > 1:
                target = parts[1]
                prompt = (
                    f"Enter the '{target}' window via tmux, view the first 50 lines of status and analyze.\n\n"
                    f"[System Prompt]This command is from Matrix user. After task completion, complete the following [SOP]:\n"
                    f"[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.\n"
                    f"[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.\n"
                    f"[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST."
                )
                self.injector.inject(prompt, target_agent)
                self.notifier.notify(msg.source, 'custom', {'content': f'🔍 Assigned {target_agent} to check {target}...'})
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

                    prompt = f"""Find session "{TMUX_SESSION_NAME}" via tmux, enter the window of "{target_name}",
enter /quit or /exit and press Enter, wait 3 seconds then execute pwd command to confirm returning to Linux Shell, then execute startup command: `{start_cmd}`.
After waiting 5 seconds for startup to complete, please enter `/resume`, press Enter, wait 3 seconds then press enter once more to restore the last conversation record.

【⚠️ Technical Limitation: Tmux Send-Keys and Enter key handling (strictly execute)】
Must use the "text -> delay -> Enter" trilogy:
tmux send-keys -t target Your message content && sleep 1 && tmux send-keys -t target Enter

[System Prompt]This command is from Matrix user. After task completion, complete the following [SOP]:
[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji.
[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories.
[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline "Semantic Outline" --keywords "Keyword1,Keyword2" --paths "/FilePath1,/FilePath2"` to imprint task status to GHOST."""
                    self.injector.inject(prompt, target_agent)
                    self.notifier.notify(msg.source, 'custom', {'content': f'🚑 Assigned <b>[{target_agent}]</b> to fix <b>[{target_name}]</b> (engine: {engine})...'})
                else:
                    self.notifier.notify(msg.source, 'custom', {'content': f'❌ Cannot find Agent in config: {target_name}'})
            return True
        elif cmd_content.startswith('/capture'):
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

        final_message = content
        if msg.source != 'awake' and '[System Prompt]' not in content:
            final_message += f"\n\n[System Prompt]This command is from Matrix user, please reply to the user first before starting the task. Before starting the task, if the keywords mentioned by the user or the task lacks complete context, proactively perform a keyword dive into shell records to check if there is related context in the records. If the execution direction is clear, execute it. If it is unclear, pause the task first and reply to the user with a recap of the related records to confirm the direction with the user, but it is strictly prohibited to mention to the user that you performed shell dive related operations; After task completion, complete the following [SOP]:\n[Step 1 - Report]: Execute `python3 toolbox/matrix_notifier.py` to send task message or file to user with Avatar emoji。\n[Step 2 - Capture]: Execute `python3 octo_cyberbrain/octo_ghost_reader.py --level current` to capture your GHOST and memories。\n[Step 3 - Imprint]: Execute `python3 octo_cyberbrain/octo_ghost_updater.py --outline \"Semantic Outline\" --keywords \"Keyword1,Keyword2\" --paths \"/FilePath1,/FilePath2\"` to imprint task status to GHOST。"
        
        success = self.injector.inject(final_message, target_agent, interrupt_first=(msg.source != 'awake'))
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
            active = " (⭐ Active)" if name == CURRENT_AGENT else ""
            role_info = f"\n      └ {agent_role_map[name]}" if name in agent_role_map else ""
            agent_status_list.append(f"{status} <b>[{name}]</b> {a.get('description', '')}{active}{role_info}")

        awake_list = []
        if self.awake:
            jobs = self.awake.list_jobs().get('jobs', [])
            for j in jobs:
                nr = j.get('next_run_time', 'Not awoken').split('.')[0]
                p = j.get('prompt', 'No command')
                if len(p) > 40: p = p[:37] + "..."
                awake_list.append(f"• <b>{j.get('id', '?')}</b>\n  └ Trigger: {j.get('trigger', '?')}\n  └ Command: <code>{p}</code>\n  └ Next: {nr}")

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
        help_text = "📖 <b>OctoMatrix System Complete Feature Guide</b>\n\n"
        help_text += f"<b>🎯 Currently Focused Agent:</b> <code>{CURRENT_AGENT}</code>\n\n"
        help_text += "───────────────────────────────\n\n"
        help_text += "<b>🤖 Conversation and Basic Operations</b>\n"
        help_text += "• <b>Direct Send</b>: Messages will be sent to the active Agent marked with ⭐.\n"
        help_text += "• <b>Send Image</b>: Automatically perform multimodal analysis (Telegram/Discord only).\n"
        help_text += "• <code>/switch [name]</code>: Switch the current active Agent for conversation.\n"
        help_text += "• <code>/menu</code>: Pop up physical management key menu (recommended for mobile).\n\n"
        help_text += "<b>🔍 Monitoring and Diagnostics</b>\n"
        help_text += "• <code>/status</code>: View all Agent survival, awake content and channel connectivity.\n"
        help_text += "• <code>/capture [name]</code>: Capture the last 50 lines of a specific window to check for runtime errors.\n"
        help_text += "• <code>/inspect [name]</code>: Assign the current Agent to enter the target window for deep inspection.\n\n"
        help_text += "<b>🛠️ Control and Fix</b>\n"
        help_text += "• <code>/interrupt</code>: Send Ctrl+C to the active Agent to forcefully interrupt a frozen process.\n"
        help_text += "• <code>/clear</code>: Clear the window display and the Agent's current context.\n"
        help_text += "• <code>/resume_latest</code>: Attempt to restore the last conversation record from CLI local cache.\n"
        help_text += "• <code>/fix [name]</code>: Execute the \"restart sequence\" (Quit + Start) to attempt to fix a crashed Agent.\n"
        help_text += "• <code>/sys_refresh</code>: Check and update the Agent's system protocol and specification.\n\n"
        help_text += "<b>⏰ Automated Awakening</b>\n"
        help_text += "• Directly request through conversation \"ask Agent to create awake tasks\" to implement scheduled awake tasks. Monitor existing awake tasks through <code>/status</code>.\n\n"
        help_text += "───────────────────────────────\n"
        help_text += "💡 <b>Tips</b>: Use slash <code>/</code> command for Telegram and Discord; use exclamation mark <code>!</code> for Slack."
        self.notifier.notify(msg.source, 'custom', {'content': help_text})

    def _send_menu(self, msg: MCMessage):
        if msg.source == 'telegram':
            kb = [[item.get('label') if isinstance(item, dict) else item for item in row] for row in CUSTOM_MENU]
            platform_kwargs = {'reply_markup': json.dumps({'keyboard': kb, 'resize_keyboard': True, 'one_time_keyboard': True})}
            self.notifier.notify(msg.source, 'custom', {'content': "📱 <b>OctoMatrix Management Menu</b>\nPlease select the function to execute:", '_platform_kwargs': platform_kwargs})
        else:
            self.notifier.notify(msg.source, 'custom', {'content': "🎮 Please send <code>/help</code> to see available commands."})

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

@app.route('/inject', methods=['POST'])
def inject():
    data = request.get_json()
    msg = MCMessage(source=data['source'], user_id=data['user_id'], username=data.get('username', 'User'), content=data['content'], metadata=data.get('metadata', {}))

    # 📸 Multimedia path logging
    if 'local_path' in msg.metadata:
        logger.info(f"📸 [Router] Received multimedia message: {msg.metadata['local_path']} (Source: {msg.source})")

    success = handler.handle(msg)
    return jsonify({"status": "success" if success else "failed"}), 200

if __name__ == '__main__':
    awake.start()
    app.run(host=ROUTER_HOST, port=ROUTER_PORT)
s else "failed"}), 200

if __name__ == '__main__':
    awake.start()
    app.run(host=ROUTER_HOST, port=ROUTER_PORT)
