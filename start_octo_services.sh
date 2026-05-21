#!/bin/bash
# Start Telegram → AI Agent squad remote control system

set -e

# Parse as absolute path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.py"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "🔐 Loaded .env"
else
    echo "⚠️  Warning: .env file not found"
fi

# Read configuration
TMUX_SESSION_NAME=$(python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import TMUX_SESSION_NAME; print(TMUX_SESSION_NAME)")

echo "🚀 Starting OctoMatrix"
echo "==========================================="

# Generate dynamic Webhook Secret
SECRET_FILE="$SCRIPT_DIR/webhook_secret.token"
openssl rand -hex 32 > "$SECRET_FILE"
export WEBHOOK_SECRET_TOKEN=$(cat "$SECRET_FILE")

# Kill existing session
if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    echo "🔄 Killing existing session…"
    tmux kill-session -t "$TMUX_SESSION_NAME"
    sleep 1
fi

# Create main session (specify separate socket file for container isolation)
echo "🧬  Creating tmux session '$TMUX_SESSION_NAME'…"
# Use explicitly specified socket file path to create session (not dependent on TMUX_TMPDIR environment variable)
tmux new-session -d -s "$TMUX_SESSION_NAME" -n "init" -c "$SCRIPT_DIR"

# 1. Initialize Agent environment
echo "🧬  Initializing Agent ecosystem environment…"
python3 "$SCRIPT_DIR/setup_agent_env.py"

# 2. Dynamically start AI Agent squad
echo "🤖 Deploying AI Agent squad…"
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
    """Wait for tmux pane to show the corresponding CLI prompt (stable detection)

    Args:
        engine: 'claude' or 'gemini'
        - claude → ❯
        - gemini → * or >

    Note: Requires consecutive prompt detection 3+ times to ensure CLI is fully ready
    """
    start_time = time.time()
    # Choose corresponding prompt based on engine
    if engine == 'claude':
        prompt_markers = ['Claude', 'bypass permissions on']
    elif engine == 'codex':
        prompt_markers = ['OpenAI', '› ']
    else:  # gemini
        prompt_markers = ['Gemini', 'YOLO']

    consecutive_detections = 0
    required_detections = 3  # Need to detect prompt 3 times consecutively to confirm CLI is ready
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

            # Check if pane content contains any expected prompt
            detected = False
            for marker in prompt_markers:
                if marker in output:
                    detected = True
                    break

            # Special handling for engine Trust Folder prompt (auto-authorize)
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
        usecase = agent.get('usecase', 'No description')
        home_path = os.path.join(script_dir, 'agent_home', name)

        # Generate collaboration context
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
        
        if i == 0:
            subprocess.run(['tmux'] + tmux_cmd(['rename-window', '-t', f'{session_name}:0', name]), check=True)
        else:
            subprocess.run(['tmux'] + tmux_cmd(['new-window', '-t', session_name, '-n', name]), check=True)

        # 🧠 Initialize Cyberbrain directory structure and environment file
        cyber_path = os.path.join(home_path, 'octo_cyberbrain')
        ghost_path = os.path.join(cyber_path, 'ghost')
        shell_path = os.path.join(cyber_path, 'shell')
        os.makedirs(ghost_path, exist_ok=True)
        os.makedirs(shell_path, exist_ok=True)

        env_file = os.path.join(cyber_path, '.cyberbrain_env')
        with open(env_file, 'w') as ef:
            ef.write(f"AGENT_NAME={name}\nTMUX_SESSION_NAME={session_name}\nROUTER_PORT={os.environ.get('ROUTER_PORT', '12210')}\n")

        # 🧠 Copy Cyberbrain tools and guides
        cyber_tools_dir = os.path.join(script_dir, 'tools', 'cyberbrain')
        if os.path.exists(cyber_tools_dir):
            for item in os.listdir(cyber_tools_dir):
                if item.endswith('.py') or item.endswith('.md'):
                    src = os.path.join(cyber_tools_dir, item)
                    dst = os.path.join(cyber_path, item)
                    safe_copy(src, dst)

        # Set up pipe-pane (ultimate architecture combining stream triggering and snapshot trimming via cyberbrain_pipe_manager.py)
        pipe_manager = os.path.join(script_dir, 'tools', 'cyberbrain', 'cyberbrain_pipe_manager.py')
        shell_log_path = os.path.join(shell_path, 'octo_shell.log')
        responder_script = os.path.join(script_dir, 'auto_permission_responder.py')

        # Use bash tee >(...) feature to simultaneously distribute stream to responder and pipe_manager
        pipe_cmd = f"bash -c 'tee >(python3 -u {responder_script} {session_name}:{name}) | python3 -u {pipe_manager} {shell_log_path} {session_name}:{name}'"

        subprocess.run(['tmux'] + tmux_cmd(['pipe-pane', '-o', '-t', f'{session_name}:{name}', pipe_cmd]), check=True)

        # 📋 Copy necessary tool scripts to Agent home
        # Copy matrix_notifier.py to agent_home toolbox
        matrix_notifier_src = os.path.join(script_dir, 'tools', 'notification', 'matrix_notifier.py')
        toolbox_path = os.path.join(home_path, 'toolbox')
        os.makedirs(toolbox_path, exist_ok=True)
        matrix_notifier_dst = os.path.join(toolbox_path, 'matrix_notifier.py')
        if os.path.exists(matrix_notifier_src):
            safe_copy(matrix_notifier_src, matrix_notifier_dst)

        # Create shared space, knowledge base and GHOST directory
        shared_space_path = os.path.join(home_path, 'my_shared_space')
        os.makedirs(shared_space_path, exist_ok=True)

        knowledge_path = os.path.join(home_path, 'knowledge')
        os.makedirs(knowledge_path, exist_ok=True)

        # 📚 Unified knowledge document copying logic
        # Copy rules and protocol files (directly to agent_home)
        rule_files_to_copy = ['agent_home_rules.md', 'AGENT_PROTOCOL.md']
        for rule_file in rule_files_to_copy:
            src_file = os.path.join(script_dir, rule_file)
            dst_file = os.path.join(home_path, rule_file)
            if os.path.exists(src_file):
                safe_copy(src_file, dst_file)

        # Copy Template file (directly to agent_home, no subdirectory)
        template_src = os.path.join(script_dir, 'agent_rule_gen_template.txt')
        template_dst = os.path.join(home_path, 'agent_rule_gen_template.txt')
        if os.path.exists(template_src):
            safe_copy(template_src, template_dst)

        # 🎨 Copy Avatar function-related files
        # Copy octo_generator.py to toolbox
        avatar_generator_src = os.path.join(script_dir, 'tools', 'avatar', 'octo_generator.py')
        avatar_generator_dst = os.path.join(toolbox_path, 'octo_generator.py')
        if os.path.exists(avatar_generator_src):
            safe_copy(avatar_generator_src, avatar_generator_dst)

        # Copy Avatar design guide to knowledge
        avatar_guide_src = os.path.join(script_dir, 'tools', 'avatar', 'AGENT_AVATAR_GUIDE.md')
        avatar_guide_dst = os.path.join(knowledge_path, 'AGENT_AVATAR_GUIDE.md')
        if os.path.exists(avatar_guide_src):
            safe_copy(avatar_guide_src, avatar_guide_dst)

        # Copy awake system documentation to knowledge
        awake_src = os.path.join(script_dir, 'tools', 'awake', 'AWAKE_FUNCTIONALITY.md')
        awake_dst = os.path.join(knowledge_path, 'AWAKE_FUNCTIONALITY.md')
        if os.path.exists(awake_src):
            safe_copy(awake_src, awake_dst)

        # Create and verify avatar directory structure
        avatar_path = os.path.join(home_path, 'avatar')
        avatar_emojis_path = os.path.join(avatar_path, 'emojis')
        os.makedirs(avatar_emojis_path, exist_ok=True)

        if not os.path.isdir(avatar_emojis_path):
            print(f"   ⚠️  Warning: Unable to create avatar/emojis directory: {avatar_emojis_path}")
        else:
            print(f"   ✓ Avatar directory confirmed: {avatar_emojis_path}")

        # 🎯 Enter Agent working directory
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', f'cd {home_path}']), check=True)
        time.sleep(1)
        subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

        # Get Agent's specified model
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

        # Wait for CLI to fully initialize (60 second timeout)
        print(f"     ⏳ Waiting for {name} CLI to start…")
        if not wait_for_prompt(session_name, name, engine, max_wait=60):
            print(f"     ❌ {name} startup failed (no {engine} prompt detected within 60 seconds), skipping this Agent")
            continue  # Skip this Agent, continue to next one

        # Extra wait to ensure CLI is fully ready (avoid injecting commands during initialization)
        time.sleep(3)

        # ✅ Check if specification file already exists (avoid duplicate injection and overwriting)
        doc_path = os.path.join(home_path, engine_doc_name)
        if os.path.exists(doc_path):
            print(f"     ✅ {engine_doc_name} already exists, skip initialization injection (protect existing specification)")

            # 🔄 Execute conversation recovery process (/resume)
            print(f"     🔄 Executing conversation recovery process…")

            # Step 1: Input /resume command
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', '/resume']), check=True)
            time.sleep(0.5)

            # Step 2: Execute /resume (enter menu)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
            time.sleep(1)

            # Step 3: Select previous conversation
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)
            time.sleep(1)

            # Step 4: Input q (handle Gemini without previous conversation)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', 'q']), check=True)
            time.sleep(0.5)

            # Step 5: Ctrl+C to ensure exit from menu
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'C-c']), check=True)
            time.sleep(1)

            # Step 6: Wait for CLI prompt to reappear
            print(f"     ⏳ Waiting for prompt recovery…")
            if not wait_for_prompt(session_name, name, engine, max_wait=10):
                print(f"     ⚠️ Prompt recovery timeout, still attempting to inject prompt…")

            # Ensure fully ready, wait 3 seconds
            time.sleep(3)
        else:
            # Trigger Agent specification file construction
            print(f"     ✨ Triggering {name} self-construction of specification file…")

            # Point to local copies in agent_home
            rules_path = os.path.join(home_path, 'agent_home_rules.md')
            protocol_path = os.path.join(home_path, 'AGENT_PROTOCOL.md')  # Reference notification rules

            # Generate initialization Prompt
            prompt = (gen_template.replace('{agent_name}', name)
                                 .replace('{agent_usecase}', usecase)
                                 .replace('{engine_doc_name}', engine_doc_name)
                                 .replace('{rules_path}', rules_path)
                                 .replace('{protocol_path}', protocol_path)
                                 .replace('{collaboration_context}', collab_context)
                                 .replace('{home_path}', home_path))

            prompt_file = os.path.join(script_dir, f".prompt_temp_{name}")
            with open(prompt_file, 'w') as f:
                f.write(prompt)

            with open(prompt_file, 'r') as pf:
                prompt_content = pf.read()

            # Use send-keys -l (literal) to simulate typing, bypassing paste mode
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', '-l', '--', prompt_content]), check=True)
            time.sleep(0.5)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

            # 🔒 Double insurance: All Agents need paste mode confirmation
            # This ensures long prompt is correctly sent
            time.sleep(0.2)
            subprocess.run(['tmux'] + tmux_cmd(['send-keys', '-t', f'{session_name}:{name}', 'Enter']), check=True)

            os.remove(prompt_file)

except Exception as e:
    print(f"❌ Error occurred during deployment: {e}")
    sys.exit(1)
EOF

echo "   ✅ All Agents ready"

# Window: MC Router API
echo "🔀 Starting MC Router (message routing hub)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "router" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:router" "python3 $SCRIPT_DIR/octo_router.py"
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:router" Enter

# Wait for Router to start
sleep 2

# Check platform enabled status and start gateways
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
        print("   📱 Starting Telegram Gateway (Router forwarding)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'telegram', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:telegram', f'python3 {script_dir}/telegram_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Telegram disabled, skipping startup")

    # 2. Discord
    if PLATFORMS_ENABLED.get('discord', True):
        print("   💻 Starting Discord Gateway (WebSocket mode)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'discord', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:discord', f'python3 {script_dir}/discord_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Discord disabled, skipping startup")

    # 3. Slack
    if PLATFORMS_ENABLED.get('slack', True):
        print("   ⚡ Starting Slack Gateway (Socket Mode)…")
        subprocess.run(['tmux', 'new-window', '-t', session_name, '-n', 'slack', '-c', script_dir], check=True)
        subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:slack', f'python3 {script_dir}/slack_socket_gateway.py', 'Enter'], check=True)
        time.sleep(2)
    else:
        print("   ⚪️ Slack disabled, skipping startup")

except Exception as e:
    print(f"   ❌ Exception occurred while starting gateways: {e}")
EOF

# Wait for all Gateways to start
sleep 2

# Window: Octo Reaper (Cyberbrain GHOST reaper)
echo "🧠 Starting Cyberbrain GHOST reaper (octo_reaper.py)…"
tmux new-window -t "$TMUX_SESSION_NAME" -n "reaper" -c "$SCRIPT_DIR"
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" "python3 $SCRIPT_DIR/octo_reaper.py"
sleep 1
tmux send-keys -t "$TMUX_SESSION_NAME:reaper" Enter

if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    # Window: ngrok Tunnel
    echo "☁️  Establishing secure connection tunnel (ngrok)…"
    tmux new-window -t "$TMUX_SESSION_NAME" -n "ngrok" -c "$SCRIPT_DIR"
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" "$SCRIPT_DIR/start_ngrok.sh"
    sleep 1
    tmux send-keys -t "$TMUX_SESSION_NAME:ngrok" Enter

    echo "⏳ Synchronizing network address and Webhook…"
    sleep 5
else
    echo "⚪️ Telegram disabled, skipping Ngrok startup"
fi

# Back to first Agent window
tmux select-window -t "$TMUX_SESSION_NAME:0"

# Send test message
echo "📨 Sending test message to all Agents and requesting identification..."
python3 << 'EOF'
import os
import sys
import subprocess
import time
sys.path.append(os.environ['SCRIPT_DIR'])
try:
    from config import AGENTS
    session_name = os.environ['TMUX_SESSION_NAME']
    for agent in AGENTS:
        name = agent['name']
        test_msg = "[System Prompt] Send test message and identify yourself"
        agent_dir = os.path.join(os.environ['SCRIPT_DIR'], '..', 'agent_home', name)
        lock_file = os.path.join(agent_dir, 'octo_cyberbrain', 'inject_block.lock')
        pending_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_inject.txt')
        
        if os.path.exists(lock_file):
            with open(pending_file, 'a', encoding='utf-8') as f:
                if os.path.exists(pending_file) and os.path.getsize(pending_file) > 0:
                    f.write("\n\n")
                f.write(test_msg)
            print(f"   ✓ Queued test message for {name}")
        else:
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', test_msg], check=True)
            time.sleep(0.5)
            subprocess.run(['tmux', 'send-keys', '-t', f'{session_name}:{name}', 'Enter'], check=True)
            print(f"   ✓ Test message sent to: {name}")
except Exception as e:
    print(f"   ⚠️ Failed to send test message: {e}")
EOF

echo "==========================================="
echo "🎉 OctoMatrix fully deployed!"
echo ""
echo "📋 Execution summary:"
echo "   Session: $TMUX_SESSION_NAME"
echo "   Communication gateways started:"
python3 << 'EOF'
import os
import sys
sys.path.append(os.environ['SCRIPT_DIR'])
try:
    from config import PLATFORMS_ENABLED
    if PLATFORMS_ENABLED.get('telegram', True): print("      📱 Telegram Gateway (Router forwarding)")
    if PLATFORMS_ENABLED.get('discord', True): print("      💻 Discord Gateway (WebSocket + auto-reconnect)")
    if PLATFORMS_ENABLED.get('slack', True): print("      ⚡ Slack Gateway (Socket Mode + auto-reconnect)")
    if not any(PLATFORMS_ENABLED.values()): print("      ⚪️ No communication gateways enabled")
except Exception: pass
EOF
echo "   Hub services started:"
echo "      🔀 MC Router (message normalization + atomic injection)"
echo "      🧠 Octo Reaper (Cyberbrain GHOST reaper)"
if python3 -c "import sys; sys.path.append('$SCRIPT_DIR'); from config import PLATFORMS_ENABLED; print(PLATFORMS_ENABLED.get('telegram', True))" | grep -q "True"; then
    echo "      ☁️  ngrok (Webhook secure tunnel)"
fi
echo ""
echo "   All tmux windows:"
tmux list-windows -t "$TMUX_SESSION_NAME" -F "      • Window #{window_index}: #{window_name}"
echo ""
echo "🚀 Attach to session: tmux attach -t $TMUX_SESSION_NAME"
echo ""
echo "✅ Verification steps:"
echo "   1. tmux attach -t $TMUX_SESSION_NAME"
echo "   2. Check router window: curl http://localhost:12210/health"
echo "   3. Send message in Telegram/Discord/Slack and verify router logs"
