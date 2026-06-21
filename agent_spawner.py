#!/usr/bin/env python3
import sys
import os
import subprocess
import time
import argparse

def tmux_cmd(tmux_args):
    """Helper function to run tmux commands"""
    return tmux_args

def safe_copy(src, dst, script_dir):
    if os.path.exists(src):
        subprocess.run(['rm', '-f', dst], check=False)
        subprocess.run(['cp', src, dst], check=True)
        # 無條件拔除 Local 模式下的 Other 寫入權限
        subprocess.run(['chmod', 'o-w', dst], check=False)
        # 記錄系統派發的檔案路徑
        list_path = os.path.join(script_dir, 'agent_home', '.system_distributed_files.txt')
        with open(list_path, 'a') as list_file:
            list_file.write(dst + '\n')

def wait_for_prompt(session_name, window_name, engine, max_wait=30):
    start_time = time.time()
    if engine == 'claude':
        prompt_markers = ['Claude', 'bypass permissions on']
    elif engine == 'codex':
        prompt_markers = ['OpenAI', '› ']
    elif engine == 'agy':
        prompt_markers = ['Antigravity CLI']
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
            for marker in prompt_markers:
                if marker in output:
                    detected = True
                    break

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
        subprocess.run(['tmux'] + tmux_cmd(['new-window', '-t', session_name, '-n', name]), check=True)

    cyber_path = os.path.join(home_path, 'octo_cyberbrain')
    ghost_path = os.path.join(cyber_path, 'ghost')
    shell_path = os.path.join(cyber_path, 'shell')
    os.makedirs(ghost_path, exist_ok=True)
    os.makedirs(shell_path, exist_ok=True)

    env_file = os.path.join(cyber_path, '.cyberbrain_env')
    with open(env_file, 'w') as ef:
        ef.write(f"AGENT_NAME={name}\nTMUX_SESSION_NAME={session_name}\nROUTER_PORT={os.environ.get('ROUTER_PORT', '12210')}\n")

    cyber_tools_dir = os.path.join(script_dir, 'tools', 'cyberbrain')
    if os.path.exists(cyber_tools_dir):
        for item in os.listdir(cyber_tools_dir):
            if item.endswith('.py') or item.endswith('.md'):
                src = os.path.join(cyber_tools_dir, item)
                dst = os.path.join(cyber_path, item)
                safe_copy(src, dst, script_dir)

    pipe_manager = os.path.join(script_dir, 'tools', 'cyberbrain', 'cyberbrain_pipe_manager.py')
    shell_log_path = os.path.join(shell_path, 'octo_shell.log')
    responder_script = os.path.join(script_dir, 'auto_permission_responder.py')

    pipe_cmd = f"bash -c 'tee >(python3 -u {responder_script} {session_name}:{name}) | python3 -u {pipe_manager} {shell_log_path} {session_name}:{name}'"
    subprocess.run(['tmux'] + tmux_cmd(['pipe-pane', '-o', '-t', f'{session_name}:{name}', pipe_cmd]), check=True)

    toolbox_path = os.path.join(home_path, 'toolbox')
    os.makedirs(toolbox_path, exist_ok=True)
    
    tools_to_copy = [
        ('tools/notification/matrix_notifier.py', 'matrix_notifier.py'),
        ('tools/notification/agent_intercom.py', 'agent_intercom.py'),
        ('tools/awake/awake_task_manager.py', 'awake_task_manager.py'),
        ('tools/avatar/octo_generator.py', 'octo_generator.py')
    ]
    for src_rel, dst_name in tools_to_copy:
        src = os.path.join(script_dir, src_rel)
        dst = os.path.join(toolbox_path, dst_name)
        if os.path.exists(src):
            safe_copy(src, dst, script_dir)

    shared_space_path = os.path.join(home_path, 'my_shared_space')
    os.makedirs(shared_space_path, exist_ok=True)
    knowledge_path = os.path.join(home_path, 'knowledge')
    os.makedirs(knowledge_path, exist_ok=True)

    rule_files_to_copy = ['agent_home_rules.md', 'AGENT_PROTOCOL.md', 'agent_rule_gen_template.txt']
    for rule_file in rule_files_to_copy:
        src_file = os.path.join(script_dir, rule_file)
        dst_file = os.path.join(home_path, rule_file)
        if os.path.exists(src_file):
            safe_copy(src_file, dst_file, script_dir)

    knowledge_files = [
        ('tools/avatar/AGENT_AVATAR_GUIDE.md', 'AGENT_AVATAR_GUIDE.md'),
        ('tools/awake/AWAKE_FUNCTIONALITY.md', 'AWAKE_FUNCTIONALITY.md')
    ]
    for src_rel, dst_name in knowledge_files:
        src = os.path.join(script_dir, src_rel)
        dst = os.path.join(knowledge_path, dst_name)
        if os.path.exists(src):
            safe_copy(src, dst, script_dir)

    avatar_path = os.path.join(home_path, 'avatar')
    avatar_emojis_path = os.path.join(avatar_path, 'emojis')
    os.makedirs(avatar_emojis_path, exist_ok=True)

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

    parent = script_dir
    while parent and parent != '/':
        subprocess.run(['chmod', 'o+x', parent], check=False, stderr=subprocess.DEVNULL)
        parent = os.path.dirname(parent)
        
    subprocess.run(['chmod', 'o+rx', script_dir], check=False)
    subprocess.run(['chmod', 'o+rx', os.path.join(script_dir, 'agent_home')], check=False)
    subprocess.run(['chmod', '-R', 'o+rwX', home_path], check=False, stderr=subprocess.DEVNULL)

    if is_docker:
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', f'cd {home_path}']), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(1)
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
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', cmd]), check=True)
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

    print(f"     ⏳ Waiting for {name} CLI to start…")
    if not wait_for_prompt(session_name, name, engine, max_wait=60):
        print(f"     ❌ {name} startup failed (no {engine} prompt detected within 60 seconds)")
        return False

    time.sleep(3)

    doc_path = os.path.join(home_path, engine_doc_name)
    if os.path.exists(doc_path):
        print(f"     ✅ {engine_doc_name} already exists, skip initialization injection (protect existing specification)")
        print(f"     🔄 Executing conversation recovery process…")
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[200~']))
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', '/resume']), check=True)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[201~']))
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(3)

        if engine == 'gemini':
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Down']), check=True)
            time.sleep(1)

        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
        time.sleep(1)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[200~']))
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', 'q']), check=True)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '\x1b[201~']))
        time.sleep(0.5)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'C-c']), check=True)
        time.sleep(1)

        print(f"     ⏳ Waiting for prompt recovery…")
        wait_for_prompt(session_name, name, engine, max_wait=10)
        time.sleep(3)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OctoMatrix Agent Spawner")
    parser.add_argument('--agent', type=str, help='Specific agent to spawn (for /fix)')
    parser.add_argument('--all', action='store_true', help='Spawn all agents from config')
    args = parser.parse_args()

    script_dir = os.environ.get('SCRIPT_DIR')
    session_name = os.environ.get('TMUX_SESSION_NAME')

    if not script_dir or not session_name:
        print("❌ SCRIPT_DIR or TMUX_SESSION_NAME environment variable not set")
        sys.exit(1)

    sys.path.append(script_dir)
    try:
        from config import AGENTS
    except ImportError:
        print("❌ Cannot import config.py")
        sys.exit(1)

    list_path = os.path.join(script_dir, 'agent_home', '.system_distributed_files.txt')
    if args.all and os.path.exists(list_path):
        os.remove(list_path)

    if args.agent:
        agent_config = next((a for a in AGENTS if a['name'] == args.agent), None)
        if not agent_config:
            print(f"❌ Agent {args.agent} not found in config")
            sys.exit(1)
        spawn_agent(agent_config, script_dir, session_name, is_first=False)
        
        try:
            from config import SYS_PREFIX, MATRIX_USERNAME
            test_msg = f"{SYS_PREFIX} Execute `python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/{{mood}}.png` to send a sticker matching your current mood, then execute `python3 toolbox/matrix_notifier.py '{{Greet {MATRIX_USERNAME} and announce you have just been restarted via fix}}'`"
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{args.agent}', test_msg], check=True)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{args.agent}', 'Enter'], check=True)
            print(f"   ✓ Test message sent to: {args.agent}")
        except Exception as e:
            print(f"   ⚠️ Failed to send test message: {e}")
    elif args.all:
        for i, agent_config in enumerate(AGENTS):
            spawn_agent(agent_config, script_dir, session_name, is_first=(i==0))
    else:
        print("❌ Please specify --agent <name> or --all")
        sys.exit(1)
