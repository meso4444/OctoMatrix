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

# setup_agent_env.py
# Responsible for initializing Agent home directory structure and collaboration links

import os
import sys
import argparse
import time
import yaml
import shutil
import subprocess

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.yaml')
AGENT_HOME_BASE = os.path.join(BASE_DIR, 'agent_home')
TEMPLATES_DIR = BASE_DIR

def safe_copy(src, dst, script_dir):
    if os.path.exists(src):
        subprocess.run(['rm', '-f', dst], check=False)
        subprocess.run(['cp', src, dst], check=True)
        filename = os.path.basename(dst)
        if dst.endswith('.py') or dst.endswith('.sh'):
            subprocess.run(['chmod', '755', dst], check=False)
        elif filename in ['GEMINI.md', 'CLAUDE.md', 'AGENT.md']:
            subprocess.run(['chmod', '666', dst], check=False)
        else:
            subprocess.run(['chmod', '644', dst], check=False)
        # 記錄系統派發的檔案路徑
        list_path = os.path.join(script_dir, 'agent_home', '.system_distributed_files.txt')
        with open(list_path, 'a') as list_file:
            list_file.write(dst + '\n')

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Error: Configuration file not found {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def setup_agent_dirs(agent_config, script_dir):
    """建立單一 Agent 的目錄結構與拷貝靜態腳本"""
    agent_name = agent_config['name']
    home = os.path.join(AGENT_HOME_BASE, agent_name)
    
    # 定義所有需要建立且賦予初始權限的子目錄
    subdirs = [
        'toolbox', 
        'knowledge', 
        'my_shared_space', 
        'downloads_temp', 
        'project', 
        'skillbox', 
        'octo_cyberbrain', 
        'octo_cyberbrain/ghost', 
        'octo_cyberbrain/shell', 
        'avatar', 
        'avatar/emojis'
    ]
    
    # 建立主目錄並賦權
    os.makedirs(home, exist_ok=True)
    subprocess.run(['chmod', '1777', home], check=False)
    
    # 迴圈處理所有子目錄的創建與賦權
    for d in subdirs:
        path = os.path.join(home, d)
        os.makedirs(path, exist_ok=True)
        if d in ['avatar', 'avatar/emojis']:
            subprocess.run(['chmod', '755', path], check=False)
        else:
            subprocess.run(['chmod', '1777', path], check=False)

    cyber_tools_dir = os.path.join(script_dir, 'tools', 'cyberbrain')
    if os.path.exists(cyber_tools_dir):
        for item in os.listdir(cyber_tools_dir):
            if item.endswith('.py') or item.endswith('.md'):
                src = os.path.join(cyber_tools_dir, item)
                dst = os.path.join(home, 'octo_cyberbrain', item)
                safe_copy(src, dst, script_dir)

    tools_to_copy = [
        ('tools/notification/matrix_notifier.py', 'matrix_notifier.py'),
        ('tools/notification/agent_intercom.py', 'agent_intercom.py'),
        ('tools/awake/awake_task_manager.py', 'awake_task_manager.py'),
        ('tools/avatar/octo_generator.py', 'octo_generator.py')
    ]
    for src_rel, dst_name in tools_to_copy:
        src = os.path.join(script_dir, src_rel)
        dst = os.path.join(home, 'toolbox', dst_name)
        if os.path.exists(src):
            safe_copy(src, dst, script_dir)

    rule_files_to_copy = ['agent_home_rules.md', 'AGENT_PROTOCOL.md', 'agent_rule_gen_template.txt']
    for rule_file in rule_files_to_copy:
        src_file = os.path.join(script_dir, rule_file)
        dst_file = os.path.join(home, rule_file)
        if os.path.exists(src_file):
            safe_copy(src_file, dst_file, script_dir)

    # 預先建立核心規範文件，確保由系統帳戶持有並設定 666 權限
    engine = agent_config.get('engine', 'gemini')
    engine_doc_name = 'CLAUDE.md'
    if engine == 'gemini' or engine == 'agy':
        engine_doc_name = 'GEMINI.md'
    elif engine == 'codex':
        engine_doc_name = 'AGENTS.md'
        
    touch_path = os.path.join(home, engine_doc_name)
    if not os.path.exists(touch_path):
        try:
            with open(touch_path, 'a'): pass
        except Exception: pass
    if os.path.exists(touch_path):
        subprocess.run(['chmod', '666', touch_path], check=False)

    knowledge_files = [
        ('tools/avatar/AGENT_AVATAR_GUIDE.md', 'AGENT_AVATAR_GUIDE.md'),
        ('tools/awake/AWAKE_FUNCTIONALITY.md', 'AWAKE_FUNCTIONALITY.md')
    ]
    for src_rel, dst_name in knowledge_files:
        src = os.path.join(script_dir, src_rel)
        dst = os.path.join(home, 'knowledge', dst_name)
        if os.path.exists(src):
            safe_copy(src, dst, script_dir)


    parent = script_dir
    while parent and parent != '/':
        subprocess.run(['chmod', '755', parent], check=False, stderr=subprocess.DEVNULL)
        parent = os.path.dirname(parent)
        
    subprocess.run(['chmod', '755', script_dir], check=False)
    subprocess.run(['chmod', '755', os.path.join(script_dir, 'agent_home')], check=False)

    return home

def setup_collaboration_links(agents, groups):
    """全域建立協作軟連結，不分群組，一律互相建立 _shared_space"""
    agent_names = [a['name'] for a in agents]
    
    expected_links = {name: set() for name in agent_names}
    
    print("🔗 處理全域協作連結 (Full Mesh)")
    for me in agent_names:
        my_home = os.path.join(AGENT_HOME_BASE, me)
        for partner in agent_names:
            if me == partner:
                continue
            
            target_real_path = os.path.join(AGENT_HOME_BASE, partner, 'my_shared_space')
            link_name = f"{partner}_shared_space"
            full_link_path = os.path.join(my_home, link_name)
            
            expected_links[me].add(link_name)
            rel_target = os.path.relpath(target_real_path, my_home)
            
            if os.path.lexists(full_link_path):
                try:
                    if os.path.isdir(full_link_path) and not os.path.islink(full_link_path):
                        import shutil
                        shutil.rmtree(full_link_path)
                    else:
                        os.unlink(full_link_path)
                except Exception:
                    pass
                
            try:
                os.symlink(rel_target, full_link_path)
                # print(f"   + 建立連結: {me} -> {partner}")
            except OSError as e:
                print(f"   ⚠️ 建立連結失敗: {e}")

    # 2. 清理過期或不屬於現在配置檔中的連結
    print("🧹 檢查並清理過期協作連結...")
    for agent in agent_names:
        home = os.path.join(AGENT_HOME_BASE, agent)
        if not os.path.exists(home):
            continue
            
        for item in os.listdir(home):
            if item.endswith("_shared_space"):
                full_path = os.path.join(home, item)
                if os.path.islink(full_path):
                    if item not in expected_links[agent]:
                        try:
                            os.unlink(full_path)
                            print(f"   - 移除過期連結: {agent}/{item}")
                        except OSError as e:
                            print(f"   ⚠️ 移除失敗: {e}")

def deploy_skills(agents):
    """Deploy Skills and implement Immutable locking"""
    skills_base_dir = os.path.join(BASE_DIR, 'skills')
    if not os.path.exists(skills_base_dir):
        return

    # Find archives in the root skills directory
    available_archives = {}
    for item in os.listdir(skills_base_dir):
        if item.endswith('.zip'):
            available_archives[item[:-4]] = os.path.join(skills_base_dir, item)
        elif item.endswith('.tar.gz'):
            available_archives[item[:-7]] = os.path.join(skills_base_dir, item)

    for agent in agents:
        agent_name = agent['name']
        agent_skills = agent.get('skills', [])
        if not agent_skills: continue

        skillbox_dir = os.path.join(AGENT_HOME_BASE, agent_name, 'skillbox')

        # 1. Restore permissions and clear old skills
        if os.path.exists(skillbox_dir):
            subprocess.run(['chmod', '-R', 'u+w', skillbox_dir], check=False)
            # Clear subdirectories
            for item in os.listdir(skillbox_dir):
                item_path = os.path.join(skillbox_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                else:
                    try:
                        os.remove(item_path)
                    except: pass

        # 2. Extract required skills
        for skill in agent_skills:
            if skill in available_archives:
                archive_path = available_archives[skill]
                target_dir = os.path.join(skillbox_dir, skill)
                os.makedirs(target_dir, exist_ok=True)
                try:
                    shutil.unpack_archive(archive_path, target_dir)
                    print(f"   📦 {agent_name} mounted skill: {skill}")
                except Exception as e:
                    print(f"   ❌ {agent_name} failed to extract skill {skill}: {e}")

        # 3. Lock as read-only (remove write permissions, keep read/execute)
        if os.path.exists(skillbox_dir) and os.listdir(skillbox_dir):
            subprocess.run(['chmod', '-R', 'a-w,a+rX', skillbox_dir], check=False)
            print(f"   🔒 {agent_name}'s skillbox has been locked to read-only")

def check_permissions():
    """Write permission self-check"""
    home_dir = os.path.expanduser('~')
    test_file = os.path.join(home_dir, '.gemini', 'tmp', 'test_write.tmp')
    try:
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except PermissionError:
        print(f"❌ Error: Insufficient permissions, cannot write to {home_dir}. Please check directory permissions.")
        sys.exit(1)
    except Exception as e:
        pass # Ignore other errors, do not interrupt main flow


def tmux_cmd(tmux_args):
    """Helper function to run tmux commands"""
    return tmux_args


def wait_for_prompt(session_name, window_name, engine, max_wait=30):
    start_time = time.time()
    if engine == 'claude':
        prompt_markers = ['Claude', 'bypass permissions on']
    elif engine == 'codex':
        prompt_markers = ['OpenAI', '› ']
    elif engine == 'agy':
        prompt_markers = ['Antigravity CLI', '>']
    else:  # gemini
        prompt_markers = ['Gemini', 'YOLO']

    consecutive_detections = 0
    required_detections = 3
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

            detected = False
            if all(marker in output for marker in prompt_markers):
                detected = True

            if not trust_handled and ('Trust folder' in output or 'trust the contents' in output.lower() or 'trust' in output.lower()):
                print(f"       🛡️  Detected {engine.capitalize()} trust prompt, auto-authorizing…")
                subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{window_name}', 'Enter']))
                trust_handled = True
                time.sleep(2)
                continue

            if detected:
                consecutive_detections += 1
                if consecutive_detections >= required_detections:
                    print(f"       ✅ {engine} CLI fully ready (prompt stably detected {consecutive_detections} times)")
                    return True
            else:
                consecutive_detections = 0
        except Exception:
            consecutive_detections = 0
        time.sleep(0.5)

    return False

def spawn_agent(agent_config, script_dir, session_name, is_first=False):
    sys.path.append(script_dir)
    from config import COLLABORATION_GROUPS, SYS_PREFIX, AGENT_PASSWORD

    name = agent_config['name']
    engine = agent_config['engine']
    usecase = agent_config.get('usecase', 'No description')
    home_path = os.path.join(script_dir, 'agent_home', name)
    is_docker = os.path.exists('/.dockerenv')

    rules_path = os.path.join(script_dir, 'agent_home_rules.md')
    template_path = os.path.join(script_dir, 'agent_rule_gen_template.txt')
    with open(template_path, 'r') as f:
        gen_template = f.read()

    collab_context_lines = []
    for grp in COLLABORATION_GROUPS:
        if name in grp.get('members', []):
            collab_context_lines.append(f"- Belonging to team: {grp.get('name')} ({grp.get('description', '')})")
            collab_context_lines.append("  Team member responsibilities:")
            roles = grp.get('roles', {})
            for member, role in roles.items():
                marker = " (you)" if member == name else ""
                collab_context_lines.append(f"  * {member}{marker}: {role}")
            collab_context_lines.append("")

    collab_context = "\n".join(collab_context_lines) if collab_context_lines else "No specific collaboration team configuration."

    print(f"   ▸ Starting Agent: {name} ({engine})")
    
    if is_first:
        subprocess.run(['tmux'] + tmux_cmd(['rename-window', '-t', f'{session_name}:0', name]), check=True)
    else:
        # Clear existing window with the same name to prevent send-keys target resolution failure (Crash)
        try:
            result = subprocess.run(['tmux', 'list-windows', '-t', session_name, '-F', '#W:#I'], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if line.startswith(f"{name}:"):
                    win_id = line.split(':')[1]
                    subprocess.run(['tmux', 'kill-window', '-t', f'{session_name}:{win_id}'])
        except Exception:
            pass
        subprocess.run(['tmux'] + tmux_cmd(['new-window', '-t', session_name, '-n', name]), check=True)

    cyber_path = os.path.join(home_path, 'octo_cyberbrain')
    shell_path = os.path.join(cyber_path, 'shell')

    env_file = os.path.join(cyber_path, '.cyberbrain_env')
    with open(env_file, 'w') as ef:
        ef.write(f"AGENT_NAME={name}\nTMUX_SESSION_NAME={session_name}\nROUTER_PORT={os.environ.get('ROUTER_PORT', '12210')}\n")
    subprocess.run(['chmod', '644', env_file], check=False)


    pipe_manager = os.path.join(script_dir, 'tools', 'cyberbrain', 'cyberbrain_pipe_manager.py')
    shell_log_path = os.path.join(shell_path, 'octo_shell.log')
    ghost_json_path = os.path.join(cyber_path, 'ghost', 'octo_ghost.json')
    responder_script = os.path.join(script_dir, 'auto_permission_responder.py')

    pipe_cmd = f"bash -c 'tee >(python3 -u {responder_script} {session_name}:{name}) | python3 -u {pipe_manager} {shell_log_path} {session_name}:{name}'"
    subprocess.run(['tmux'] + tmux_cmd(['pipe-pane', '-o', '-t', f'{session_name}:{name}', pipe_cmd]), check=True)

    # Initialize correct permissions for shell log, ghost json, and task memo
    # octo_shell.log → 644: Only Owner (agent account) can write, Others read-only
    # octo_ghost.json → 666: Readable/writable by all
    if os.path.exists(shell_log_path):
        subprocess.run(['chmod', '644', shell_log_path], check=False)
    if os.path.exists(ghost_json_path):
        subprocess.run(['chmod', '666', ghost_json_path], check=False)

    # Pre-initialize task_memo.txt to ensure Inode and owner are locked with 666 permissions
    task_memo_path = os.path.join(cyber_path, 'task_memo.txt')
    if not os.path.exists(task_memo_path):
        try:
            with open(task_memo_path, 'w', encoding='utf-8') as f:
                f.write("")
        except: pass
    if os.path.exists(task_memo_path):
        subprocess.run(['chmod', '666', task_memo_path], check=False)

    # === 新增：Overlay Virtual Environment 初始化腳本 ===
    main_venv_path = os.path.join(script_dir, '.venv')
    main_python = os.path.join(main_venv_path, 'bin', 'python3')
    main_sp_path = ""
    if os.path.exists(main_python):
        try:
            main_sp_result = subprocess.run([main_python, '-c', "import sysconfig; print(sysconfig.get_paths()['purelib'])"], capture_output=True, text=True)
            main_sp_path = main_sp_result.stdout.strip()
        except: pass

    init_venv_script = os.path.join(home_path, '.init_venv.sh')
    with open(init_venv_script, 'w') as f:
        f.write(f"#!/bin/bash\n")
        f.write(f"if [ ! -d \".venv\" ]; then\n")
        f.write(f"    python3 -m venv .venv\n")
        f.write(f"fi\n")
        f.write(f"if [ -n \"{main_sp_path}\" ] && [ -d \".venv\" ]; then\n")
        f.write(f"    .venv/bin/python3 -c \"import sysconfig, os; p=sysconfig.get_paths()['purelib'] + '/octo_core_overlay.pth'; [os.chmod(p, 0o666) if os.path.exists(p) else None]; open(p, 'w').write('{main_sp_path}\\\\n'); os.chmod(p, 0o444)\"\n")
        f.write(f"fi\n")
    subprocess.run(['chmod', '777', init_venv_script], check=False)
    # ====================================================

    model = agent_config.get('model', '').strip()

    if engine == 'gemini':
        cmd = 'gemini --yolo'
        if model and model.lower() != 'auto': cmd += f' --model {model}'
        engine_doc_name = 'GEMINI.md'
    elif engine == 'codex':
        cmd = 'codex --yolo'
        if model and model.lower() != 'auto': cmd += f' --model {model}'
        engine_doc_name = 'AGENTS.md'
    elif engine == 'agy':
        cmd = 'agy --dangerously-skip-permissions'
        if model: cmd += f' --model "{model}"'
        engine_doc_name = 'GEMINI.md'
    else:
        cmd = 'claude --permission-mode bypassPermissions'
        if model and model.lower() != 'auto': cmd += f' --model {model}'
        engine_doc_name = 'CLAUDE.md'

    agent_user = f"agent_{name.lower()}"


    if is_docker:
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', f'cd {home_path}']), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(1)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'clear', 'Enter']), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['clear-history', '-t', f'{session_name}:{name}']), check=True)
        venv_activate = os.path.join(home_path, '.venv', 'bin', 'activate')
        chained_cmd = f"./.init_venv.sh && [ -f \"{venv_activate}\" ] && source \"{venv_activate}\""
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', chained_cmd, 'Enter']), check=True)
        time.sleep(4)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', cmd]), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
    else:
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', f'su - {agent_user}']), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(2) 
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', AGENT_PASSWORD]), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(2) 
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', f'cd {home_path}']), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(1) 
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'clear', 'Enter']), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['clear-history', '-t', f'{session_name}:{name}']), check=True)
        venv_activate = os.path.join(home_path, '.venv', 'bin', 'activate')
        chained_cmd = f"./.init_venv.sh && [ -f \"{venv_activate}\" ] && source \"{venv_activate}\""
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', chained_cmd, 'Enter']), check=True)
        time.sleep(4)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', cmd]), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

    print(f"     ⏳ Waiting for {name} CLI to start…")
    if not wait_for_prompt(session_name, name, engine, max_wait=60):
        print(f"     ❌ {name} startup failed (no {engine} prompt detected within 60 seconds)")
        return False

    time.sleep(3)

    doc_path = os.path.join(home_path, engine_doc_name)
    if os.path.exists(doc_path) and os.path.getsize(doc_path) > 0:
        print(f"     ✅ {engine_doc_name} already exists and is not empty, skip initialization injection (protect existing specification)")
        print(f"     🔄 Executing conversation recovery process…")
        
        # Unconditionally send ESC to interrupt any running background task (e.g. Codex MCP) or residual Auto-complete menus
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Escape']), check=True)
        time.sleep(1)

        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[200~']))
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', '/resume']), check=True)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[201~']))
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        
        # Unified Fail-Safe Clearance
        agent_dir = os.path.join(AGENT_HOME_BASE, name)
        for f_name in ['.rotation_flag', '.fix_flag']:
            f_path = os.path.join(agent_dir, 'octo_cyberbrain', f_name)
            if os.path.exists(f_path):
                try: os.remove(f_path)
                except: pass
                
        time.sleep(3)

        if engine == 'gemini':
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Down']), check=True)
            time.sleep(1)

        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(1)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'q']), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'BSpace']), check=True)
        time.sleep(0.5)

        print(f"     ⏳ Waiting for prompt recovery…")
        wait_for_prompt(session_name, name, engine, max_wait=10)
        time.sleep(1)
    else:
        print(f"     ✨ Triggering {name} self-construction of specification file…")
        rules_path = os.path.join(home_path, 'agent_home_rules.md')
        protocol_path = os.path.join(home_path, 'AGENT_PROTOCOL.md')

        prompt = f"{SYS_PREFIX}\n" + (gen_template.replace('{agent_name}', name)
                                .replace('{agent_usecase}', usecase)
                                .replace('{engine_doc_name}', engine_doc_name)
                                .replace('{rules_path}', rules_path)
                                .replace('{protocol_path}', protocol_path)
                                .replace('{collaboration_context}', collab_context)
                                .replace('{home_path}', home_path))

        avatar_instruction = "\n\n=== Visual Identity Construction Task ===\nAfter completing the customized self-awareness writing, follow the guidance in ./knowledge/AGENT_AVATAR_GUIDE.md to generate your avatar."
        prompt += avatar_instruction

        prompt_file = os.path.join(script_dir, f".prompt_temp_{name}")
        with open(prompt_file, 'w') as f: f.write(prompt)
        with open(prompt_file, 'r') as pf: prompt_content = pf.read()

        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[200~']))
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', prompt_content]), check=True)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[201~']))
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(0.2)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        os.remove(prompt_file)


    return True


def main():
    parser = argparse.ArgumentParser(description="OctoMatrix Agent Setup and Spawner")
    parser.add_argument('--agent', type=str, help='Specific agent to spawn (for /fix)')
    parser.add_argument('--all', action='store_true', help='Spawn all agents from config')
    args = parser.parse_args()

    print("🧬  正在初始化 Agent 生態環境...")
    check_permissions()
    
    script_dir = os.environ.get('SCRIPT_DIR', BASE_DIR)
    session_name = os.environ.get('TMUX_SESSION_NAME', load_config().get('tmux', {}).get('session_name', 'ai_octomatrix'))
    
    config = load_config()
    agents = config.get('agents', [])
    groups = config.get('collaboration_groups', [])
    
    # 防呆：確保 Tmux Session 存在，否則自動建立
    result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
    if result.returncode != 0:
        print(f"   [Auto-Fix] Tmux session '{session_name}' not found. Creating it automatically...")
        subprocess.run(['tmux', 'new-session', '-d', '-s', session_name], check=True)
    
    # Determine which agents to process
    target_agents = []
    if args.agent:
        target_agents = [a for a in agents if a['name'] == args.agent]
        if not target_agents:
            print(f"❌ 找不到 Agent {args.agent} 於配置檔")
            sys.exit(1)
    elif args.all:
        target_agents = agents
    else:
        print("❌ Please specify --agent <name> or --all")
        sys.exit(1)

    # 1. 建立目錄 (只針對目標 agent，但 collaboration links 還是全局更新比較好，這裡保持全部更新或只更新部分)
    for agent in target_agents:
        setup_agent_dirs(agent, script_dir)

    # 3. 建立協作連結 (全局)
    setup_collaboration_links(agents, groups)
    
    # 4. 部署 Skills
    deploy_skills(target_agents)
    
    # 5. 清理注入殘留鎖
    for agent in target_agents:
        agent_dir = os.path.join(AGENT_HOME_BASE, agent['name'])
        pending_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_user.txt')
        if os.path.exists(pending_file):
            try: os.remove(pending_file)
            except: pass

    list_path = os.path.join(script_dir, 'agent_home', '.system_distributed_files.txt')
    if args.all and os.path.exists(list_path):
        os.remove(list_path)

    # 6. 啟動 Tmux 與注入
    if args.agent:
        spawn_agent(target_agents[0], script_dir, session_name, is_first=False)
        try:
            from config import SYS_PREFIX, MATRIX_USERNAME
            test_msg = f"{SYS_PREFIX}執行 python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.webm 發符合當下心情的貼圖，接著執行 python3 toolbox/matrix_notifier.py '{{向 {MATRIX_USERNAME} 問候，並說明你剛從修復程序中重啟}}'"
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{args.agent}', test_msg], check=True)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{args.agent}', 'Enter'], check=True)
            print(f"   ✓ 已發送測試訊息至: {args.agent}")
        except Exception as e:
            print(f"   ⚠️ 發送測試訊息失敗: {e}")
    elif args.all:
        for i, agent_config in enumerate(target_agents):
            spawn_agent(agent_config, script_dir, session_name, is_first=(i==0))

    print("✅ 環境初始化與啟動完成")

if __name__ == '__main__':
    main()
