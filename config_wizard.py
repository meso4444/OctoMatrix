import sys
import os
import yaml
import shutil
from datetime import datetime

CONFIG = {}
CONFIG_PATH = ""
ORIGINAL_CONFIG = {}

def prompt_bool(prompt_str, default=True):
    default_str = "Y/n" if default else "y/N"
    while True:
        resp = input(f"{prompt_str} [{default_str}]: ").strip().lower()
        if not resp:
            return default
        if resp in ['y', 'yes']:
            return True
        if resp in ['n', 'no']:
            return False

def save_config():
    try:
        # Reorder keys to follow 13542 sequence (Agent -> Collaboration -> Menu -> Cyberbrain -> Tmux)
        ordered_config = {}
        # Keep server/router first if they exist
        for k in ['server', 'router']:
            if k in CONFIG: ordered_config[k] = CONFIG[k]

        # 1: Agent
        if 'agents' in CONFIG: ordered_config['agents'] = CONFIG['agents']
        if 'default_active_agent' in CONFIG: ordered_config['default_active_agent'] = CONFIG['default_active_agent']

        # 3: Collaboration
        if 'collaboration_groups' in CONFIG: ordered_config['collaboration_groups'] = CONFIG['collaboration_groups']

        # 5: Menu
        if 'menu' in CONFIG: ordered_config['menu'] = CONFIG['menu']

        # 4: Cyberbrain
        if 'octo_cyberbrain' in CONFIG: ordered_config['octo_cyberbrain'] = CONFIG['octo_cyberbrain']

        # 2: Tmux
        if 'tmux' in CONFIG: ordered_config['tmux'] = CONFIG['tmux']

        # Add remaining keys
        for k, v in CONFIG.items():
            if k not in ordered_config:
                ordered_config[k] = v

        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(ordered_config, f, allow_unicode=True, sort_keys=False)
        print("✅ Configuration saved successfully.")
    except Exception as e:
        print(f"❌ Save failed: {e}")

def prompt_model_choice(engine, current_model=None):
    engine = engine.lower()
    options = []
    if 'gemini' in engine:
        options = [("auto", "auto (default)"), ("gemini-3.1-pro-preview", "gemini-3.1-pro-preview"), ("gemini-3-flash-preview", "gemini-3-flash-preview")]
    elif 'claude' in engine:
        options = [("haiku", "haiku (default)"), ("sonnet", "sonnet"), ("opus", "opus")]
    elif 'codex' in engine:
        options = [("gpt-5.4-mini", "gpt-5.4-mini (default)"), ("gpt-5.4", "gpt-5.4")]
    else:
        return input(f"Model (model, press Enter to keep '{current_model or 'default'}'): ").strip()

    print(f"\n  Please select model for {engine}:")
    for i, (val, desc) in enumerate(options):
        print(f"  [{i+1}] {desc}")
    print(f"  [C] Custom Input (Custom)")

    prompt_str = f"Please select model (press Enter to keep '{current_model or options[0][0]}'): "
    while True:
        choice = input(prompt_str).strip()
        choice_lower = choice.lower()
        if not choice:
            return current_model if current_model else options[0][0]
        if choice_lower == 'c':
            return input("Please enter custom model name: ").strip()
        if choice_lower.isdigit():
            idx = int(choice_lower) - 1
            if 0 <= idx < len(options):
                return options[idx][0]

        # Support users entering complete model names directly
        valid_models = [opt[0].lower() for opt in options]
        if choice_lower in valid_models:
            return next(opt[0] for opt in options if opt[0].lower() == choice_lower)

        print("Invalid choice, please re-enter.")

def manage_agents():
    global CONFIG
    if "agents" not in CONFIG or not isinstance(CONFIG["agents"], list):
        CONFIG["agents"] = []

    while True:
        print("\n--- 🤖 Agent Squadron Configuration ---")
        current_default = CONFIG.get("default_active_agent", "")
        for i, agent in enumerate(CONFIG["agents"]):
            is_default = " (default active)" if agent.get('name') == current_default else ""
            print(f"  [{i+1}] {agent.get('name', 'Unknown')} (Engine: {agent.get('engine', 'N/A')}){is_default}")
        print("-------------------------")
        print(" [A] Add Agent")
        print(" [E] Edit Agent (Edit)")
        print(" [D] Delete Agent")
        print(" [S] Set Default Active Agent")
        print(" [R] Return to Main Menu")

        choice = input("Please select operation: ").strip().lower()
        if choice == 'a':
            name = input("Agent name: ").strip()
            if not name: continue
            engine = input("Engine (gemini/claude/codex) [gemini]: ").strip() or "gemini"
            model = prompt_model_choice(engine)
            usecase = input("Responsibility (usecase) [for Agent system prompt awareness]: ").strip()
            desc = input("Description (description) [for menu and user identification]: ").strip()
            new_agent = {"name": name, "engine": engine, "usecase": usecase, "description": desc}
            if model: new_agent["model"] = model
            CONFIG["agents"].append(new_agent)
            print(f"✅ Agent {name} has been added!")
            if len(CONFIG["agents"]) == 1:
                 CONFIG["default_active_agent"] = name
        elif choice == 'e':
            idx = input("Please enter Agent number to edit: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["agents"]):
                    agent = CONFIG["agents"][idx]
                    print(f"\nEditing {agent.get('name')}:")

                    new_name = input(f"New name (press Enter to keep '{agent.get('name')}'): ").strip()
                    if new_name:
                        # Update default active agent if name changed
                        if CONFIG.get("default_active_agent") == agent.get('name'):
                            CONFIG["default_active_agent"] = new_name
                        agent['name'] = new_name

                    new_engine = input(f"New engine (press Enter to keep '{agent.get('engine', 'gemini')}'): ").strip()
                    if new_engine: agent['engine'] = new_engine

                    new_model = prompt_model_choice(agent.get('engine', 'gemini'), agent.get('model'))
                    if new_model: agent['model'] = new_model

                    new_usecase = input(f"New responsibility [for Agent system prompt awareness] (press Enter to keep '{agent.get('usecase', '')}'): ").strip()
                    if new_usecase: agent['usecase'] = new_usecase

                    new_desc = input(f"New description [for menu and user identification] (press Enter to keep '{agent.get('description', '')}'): ").strip()
                    if new_desc: agent['description'] = new_desc

                    CONFIG["agents"][idx] = agent
                    print(f"✅ Agent editing completed!")
        elif choice == 'd':
            idx = input("Please enter Agent number to delete: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["agents"]):
                    del_name = CONFIG["agents"][idx].get('name', 'Unknown')
                    del CONFIG["agents"][idx]
                    print(f"🗑️ Agent {del_name} has been deleted!")
                    if CONFIG.get("default_active_agent") == del_name:
                        CONFIG["default_active_agent"] = ""
        elif choice == 's':
            agents = CONFIG.get("agents", [])
            if not agents:
                print("⚠️ Please configure agents first!")
                continue
            idx = input("Please select default Agent number: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(agents):
                    CONFIG["default_active_agent"] = agents[idx].get("name")
                    print(f"✅ Default Agent has been updated to {CONFIG['default_active_agent']}")
        elif choice == 'r':
            break

def manage_tmux():
    global CONFIG
    if "tmux" not in CONFIG or not CONFIG["tmux"]:
        CONFIG["tmux"] = {"session_name": "ai_octomatrix"}
    current = CONFIG["tmux"].get("session_name", "ai_octomatrix")
    print(f"\n--- 🔧 Tmux Session Name Configuration ---")
    print(f"Current name: {current}")
    new_name = input("Please enter new name (press Enter to keep): ").strip()
    if new_name:
        CONFIG["tmux"]["session_name"] = new_name
        print(f"✅ Tmux Session has been updated to {new_name}")

def manage_collaboration():
    global CONFIG
    if "collaboration_groups" not in CONFIG or not isinstance(CONFIG["collaboration_groups"], list):
        CONFIG["collaboration_groups"] = []

    while True:
        print("\n--- 🤝 Collaboration Groups Configuration ---")
        for i, group in enumerate(CONFIG["collaboration_groups"]):
            print(f"  [{i+1}] {group.get('name', 'Unknown')} (Members: {', '.join(group.get('members', []))})")
        print("-------------------------")
        print(" [A] Add Collaboration Group")
        print(" [E] Edit Collaboration Group (Edit)")
        print(" [D] Delete Collaboration Group")
        print(" [R] Return to Main Menu")

        choice = input("Please select operation: ").strip().lower()

        valid_agents = [a.get('name') for a in CONFIG.get('agents', []) if a.get('name')]

        if choice == 'a':
            name = input("Group name (e.g., core_team): ").strip()
            if not name: continue
            desc = input("Group description: ").strip()
            print(f"  💡 Available agents: {', '.join(valid_agents)}")
            members_str = input("Group members (comma-separated, e.g., Gupta,Chod): ").strip()
            members = [m.strip() for m in members_str.split(',') if m.strip()]

            # Validation
            final_members = []
            for m in members:
                if m not in valid_agents:
                    print(f"⚠️  Warning: Agent '{m}' has not been created in the Agent Squadron! This may cause runtime errors.")
                    if prompt_bool(f"Do you still want to add '{m}' to the group?", False):
                        final_members.append(m)
                else:
                    final_members.append(m)
            members = final_members
            if not members:
                print("❌ Group members cannot be empty, operation cancelled.")
                continue

            roles = {}
            for m in members:
                role = input(f"Set role and responsibility in group for {m}: ").strip()
                if role:
                    roles[m] = role
            CONFIG["collaboration_groups"].append({
                "name": name,
                "description": desc,
                "members": members,
                "roles": roles
            })
            print(f"✅ Collaboration group {name} has been added!")
        elif choice == 'e':
            idx = input("Please enter group number to edit: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["collaboration_groups"]):
                    group = CONFIG["collaboration_groups"][idx]
                    print(f"\nEditing collaboration group {group.get('name')}:")

                    new_name = input(f"New group name (press Enter to keep '{group.get('name')}'): ").strip()
                    if new_name: group['name'] = new_name

                    new_desc = input(f"New group description (press Enter to keep '{group.get('description', '')}'): ").strip()
                    if new_desc: group['description'] = new_desc

                    print(f"Current members: {', '.join(group.get('members', []))}")
                    if prompt_bool("Do you want to reconfigure members and responsibilities?", False):
                        print(f"  💡 Available agents: {', '.join(valid_agents)}")
                        members_str = input("New group members (comma-separated): ").strip()
                        members = [m.strip() for m in members_str.split(',') if m.strip()]

                        # Validation
                        final_members = []
                        for m in members:
                            if m not in valid_agents:
                                print(f"⚠️  Warning: Agent '{m}' has not been created in the Agent Squadron! This may cause runtime errors.")
                                if prompt_bool(f"Do you still want to add '{m}' to the group?", False):
                                    final_members.append(m)
                            else:
                                final_members.append(m)
                        members = final_members
                        if not members:
                            print("❌ Group members cannot be empty, member list update cancelled.")
                            continue

                        roles = {}
                        for m in members:
                            old_role = group.get('roles', {}).get(m, '')
                            role = input(f"Set role and responsibility in group for {m} (current: '{old_role}'): ").strip()
                            if role:
                                roles[m] = role
                            elif old_role:
                                roles[m] = old_role
                        group['members'] = members
                        group['roles'] = roles

                    CONFIG["collaboration_groups"][idx] = group
                    print("✅ Collaboration group editing completed!")
        elif choice == 'd':
            idx = input("Please enter group number to delete: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["collaboration_groups"]):
                    del_name = CONFIG["collaboration_groups"][idx].get('name', 'Unknown')
                    del CONFIG["collaboration_groups"][idx]
                    print(f"🗑️ Collaboration group {del_name} has been deleted!")
        elif choice == 'r':
            break

def manage_cyberbrain():
    global CONFIG
    if "octo_cyberbrain" not in CONFIG or not CONFIG["octo_cyberbrain"]:
        CONFIG["octo_cyberbrain"] = {
            "ghost_check_interval_sec": 60,
            "ghost_compression_threshold_kb": 150,
            "ghost_long_term_compression_limit": 12,
            "ghost_awake_context_depth": 50
        }

    while True:
        print("\n--- 🧠 Cyberbrain Parameter Configuration ---")
        print(f" [1] GHOST Capacity Check Frequency: {CONFIG.get('octo_cyberbrain', {}).get('ghost_check_interval_sec', 60)} seconds")
        print(f" [2] Shallow GHOST Compression Threshold: {CONFIG.get('octo_cyberbrain', {}).get('ghost_compression_threshold_kb', 150)} KB")
        print(f" [3] Long-term GHOST Compression Threshold: {CONFIG.get('octo_cyberbrain', {}).get('ghost_long_term_compression_limit', 12)} compressed GHOSTs")
        print(f" [4] GHOST Awake Context Depth: {CONFIG.get('octo_cyberbrain', {}).get('ghost_awake_context_depth', 50)} lines")
        print(" [R] Return to Main Menu")

        choice = input("Please select parameter to modify: ").strip().lower()
        if choice == '1':
            val = input("Please enter GHOST capacity check frequency (seconds): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_check_interval_sec"] = int(val)
                print("✅ Parameter updated")
        elif choice == '2':
            val = input("Please enter shallow GHOST compression threshold (KB): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_compression_threshold_kb"] = int(val)
                print("✅ Parameter updated")
        elif choice == '3':
            val = input("Please enter long-term GHOST compression threshold (count): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_long_term_compression_limit"] = int(val)
                print("✅ Parameter updated")
        elif choice == '4':
            val = input("Please enter GHOST awake context depth (lines): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_awake_context_depth"] = int(val)
                print("✅ Parameter updated")
        elif choice == 'r':
            # Clean up old deprecated keys if they exist
            if "default_cleanup_policy" in CONFIG:
                del CONFIG["default_cleanup_policy"]
            break

def manage_menu():
    global CONFIG
    if "menu" not in CONFIG or not isinstance(CONFIG["menu"], list):
        CONFIG["menu"] = []

    while True:
        print("\n--- 🎮 Function Key Configuration (Menu) ---")
        for i, row in enumerate(CONFIG["menu"]):
            labels = []
            for j, item in enumerate(row):
                label = item.get('label') if isinstance(item, dict) else item
                labels.append(f"[{j+1}] {label}")
            print(f"  [Row {i+1}] {' | '.join(labels)}")
        print("-------------------------")
        print(" [A] Add Function Key (Add Item)")
        print(" [G] Auto-generate Built-in Function Keys (Auto-generate)")
        print(" [E] Edit Function Key (Edit Item)")
        print(" [M] Move Function Key (Move Item)")
        print(" [D] Delete (Delete Row/Item/All)")
        print(" [R] Return to Main Menu")

        choice = input("Please select operation: ").strip().lower()
        if choice == 'a':
            label = input("  Button display text (label): ").strip()
            if not label: continue

            has_input = prompt_bool("  Do you need an input box after clicking this button to add content (e.g., Please translate ?)? ", False)
            if has_input:
                print("  💡 Tip: You can place a question mark ? anywhere in the command to represent content you want to input (e.g., Please help me query ? data)")
                command = input("  Corresponding command (? will be added at the end if not included): ").strip()
                if not command: command = label
                if "?" not in command:
                    command = f"{command} ?"

                # Convert user input ? to system {input}
                command = command.replace("?", "{input}")

                prompt_txt = input("  Input prompt text (prompt): ").strip()
                new_item = {"label": label, "command": command, "prompt": prompt_txt}
            else:
                command = input("  Corresponding command (e.g., check weather): ").strip()
                if not command: command = label
                new_item = {"label": label, "command": command}

            print("\n  Where do you want to insert it?")
            print("  [T] Top (Top - Create new Row)")
            print("  [B] Bottom (Bottom - Create new Row)")
            avail_rows = [idx for idx, r in enumerate(CONFIG["menu"]) if len(r) < 4]
            for r_idx in avail_rows:
                print(f"  [{r_idx+1}] Insert to Row {r_idx+1} (current {len(CONFIG['menu'][r_idx])}/4)")

            pos = input("  Please select insertion position [T/B/number]: ").strip().upper()
            if pos == 'T':
                CONFIG["menu"].insert(0, [new_item])
            elif pos == 'B' or not pos:
                CONFIG["menu"].append([new_item])
            elif pos.isdigit() and (int(pos) - 1) in avail_rows:
                CONFIG["menu"][int(pos)-1].append(new_item)
            else:
                CONFIG["menu"].append([new_item])
            print("✅ Function key has been added!")
            
        elif choice == 'g':
            print("\nStarting to generate built-in function keys...")

            def append_to_menu(items):
                current_row = []
                for item in items:
                    current_row.append(item)
                    if len(current_row) == 4:
                        CONFIG["menu"].append(current_row)
                        current_row = []
                if current_row:
                    CONFIG["menu"].append(current_row)

            switch_items = []
            if prompt_bool("Do you want to add a parametric switch function (/switch {input})?", True):
                switch_items.append({"label": "🔄 Switch Agent", "command": "/switch {input}", "prompt": "Please enter Agent name to switch to:"})

            if prompt_bool("Do you want to add dedicated switch shortcut keys for existing Agents?", True):
                agents = CONFIG.get("agents", [])
                for agent in agents:
                    name = agent.get("name")
                    if name:
                        switch_items.append({"label": f"🐙 Awake {name}", "command": f"/switch {name}"})

            if switch_items:
                append_to_menu(switch_items)

            action_items = []
            if prompt_bool("Do you want to add status check and capture repair functions (/capture, /inspect, /fix, /interrupt)?", True):
                action_items.append({"label": "📸 State Capture", "command": "/capture {input}", "prompt": "Please enter Agent name to capture state:"})
                action_items.append({"label": "🔍 Health Check", "command": "/inspect {input}", "prompt": "Please enter Agent name to check:"})
                action_items.append({"label": "🚑 Repair", "command": "/fix {input}", "prompt": "Please enter Agent name to repair:"})
                action_items.append({"label": "🛑 Interrupt", "command": "/interrupt"})
                append_to_menu(action_items)

            sys_items = []
            if prompt_bool("Do you want to add system operation and control functions (/clear, /resume_latest, /help, /status)?", True):
                sys_items.append({"label": "🧹 Clear Context", "command": "/clear"})
                sys_items.append({"label": "🧠 Restore Context", "command": "/resume_latest"})
                sys_items.append({"label": "📖 Manual", "command": "/help"})
                sys_items.append({"label": "📊 System Status", "command": "/status"})
                append_to_menu(sys_items)

            print("✅ Built-in function keys have been auto-generated!")
            
        elif choice == 'e':
            r_idx = input("Please enter Row number to edit: ").strip()
            i_idx = input("Please enter button number in that Row: ").strip()
            if r_idx.isdigit() and i_idx.isdigit():
                r = int(r_idx) - 1
                i = int(i_idx) - 1
                if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                    item = CONFIG["menu"][r][i]
                    if not isinstance(item, dict):
                        item = {"label": item, "command": item}
                    print(f"Current setting: Label='{item.get('label')}', Command='{item.get('command')}'")
                    new_label = input("New display text (press Enter to keep): ").strip()
                    if new_label: item["label"] = new_label
                    new_cmd = input("New command (press Enter to keep): ").strip()
                    if new_cmd: item["command"] = new_cmd
                    if "{input}" in item.get("command", ""):
                        new_prompt = input(f"New prompt text (current: '{item.get('prompt','')}'): ").strip()
                        if new_prompt: item["prompt"] = new_prompt
                    CONFIG["menu"][r][i] = item
                    print("✅ Editing completed!")

        elif choice == 'm':
            r_idx = input("Please enter Row number of button to move: ").strip()
            i_idx = input("Please enter button number in that Row: ").strip()
            if r_idx.isdigit() and i_idx.isdigit():
                r = int(r_idx) - 1
                i = int(i_idx) - 1
                if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                    item = CONFIG["menu"][r].pop(i)
                    if not CONFIG["menu"][r]:
                        del CONFIG["menu"][r]

                    print("\n  Where do you want to move it?")
                    print("  [T] Top (Create new Row)")
                    print("  [B] Bottom (Create new Row)")
                    avail_rows = [idx for idx, row in enumerate(CONFIG["menu"]) if len(row) < 4]
                    for idx in avail_rows:
                        print(f"  [{idx+1}] Move to Row {idx+1} (current {len(CONFIG['menu'][idx])}/4)")

                    pos = input("  Please select target position [T/B/number]: ").strip().upper()
                    if pos == 'T':
                        CONFIG["menu"].insert(0, [item])
                    elif pos == 'B' or not pos:
                        CONFIG["menu"].append([item])
                    elif pos.isdigit() and (int(pos) - 1) in avail_rows:
                        CONFIG["menu"][int(pos)-1].append(item)
                    else:
                        CONFIG["menu"].append([item])
                    print("✅ Move completed!")

        elif choice == 'd':
            print(" [1] Delete entire row (Row)")
            print(" [2] Delete single button (Item)")
            print(" [3] Clear all function keys (Clear All)")
            sub_c = input("Please select: ").strip()
            if sub_c == '1':
                r_idx = input("Please enter Row number to delete: ").strip()
                if r_idx.isdigit():
                    r = int(r_idx) - 1
                    if 0 <= r < len(CONFIG["menu"]):
                        del CONFIG["menu"][r]
                        print("🗑️ Menu row has been deleted!")
            elif sub_c == '2':
                r_idx = input("Please enter Row number: ").strip()
                i_idx = input("Please enter button number: ").strip()
                if r_idx.isdigit() and i_idx.isdigit():
                    r = int(r_idx) - 1
                    i = int(i_idx) - 1
                    if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                        del CONFIG["menu"][r][i]
                        if not CONFIG["menu"][r]:
                            del CONFIG["menu"][r]
                        print("🗑️ Button has been deleted!")
            elif sub_c == '3':
                if prompt_bool("⚠️ Are you sure you want to clear all function keys?", False):
                    CONFIG["menu"] = []
                    print("🗑️ All function keys have been cleared!")
        elif choice == 'r':
            CONFIG["menu"] = [row for row in CONFIG["menu"] if row]
            break

def main():
    global CONFIG, CONFIG_PATH, ORIGINAL_CONFIG
    if len(sys.argv) < 2:
        print("Usage: python3 config_wizard.py <config_path>")
        sys.exit(1)
    CONFIG_PATH = sys.argv[1]

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                CONFIG = yaml.safe_load(f) or {}

                # Ensure necessary nodes exist and assign default values
                if "tmux" not in CONFIG or not CONFIG["tmux"]:
                    CONFIG["tmux"] = {"session_name": "ai_octomatrix"}
                if "octo_cyberbrain" not in CONFIG or not CONFIG["octo_cyberbrain"]:
                    CONFIG["octo_cyberbrain"] = {
                        "ghost_check_interval_sec": 60,
                        "ghost_compression_threshold_kb": 70,
                        "ghost_long_term_compression_limit": 12,
                        "ghost_awake_context_depth": 50
                    }
                if "collaboration_groups" not in CONFIG:
                    CONFIG["collaboration_groups"] = []
                if "menu" not in CONFIG:
                    CONFIG["menu"] = []
                if "agents" not in CONFIG:
                    CONFIG["agents"] = []

                ORIGINAL_CONFIG = yaml.safe_load(yaml.dump(CONFIG))
        except Exception as e:
            print(f"Failed to load configuration file: {e}")
            sys.exit(1)

        # Scrub deprecated cleanup_policy keys if they exist        if "default_cleanup_policy" in CONFIG:
            del CONFIG["default_cleanup_policy"]
        if "agents" in CONFIG and isinstance(CONFIG["agents"], list):
            for agent in CONFIG["agents"]:
                if "cleanup_policy" in agent:
                    del agent["cleanup_policy"]
                    
    else:
        CONFIG = {"agents": [], "tmux": {"session_name": "ai_octomatrix"}}

    while True:
        print("\n🐙 OctoMatrix - System Configuration Console")
        print("=" * 40)
        print(f"Current configuration instance: {os.path.basename(CONFIG_PATH)}")
        print("-" * 30)
        print(" [1] 🤖 Agent Squadron Configuration")
        print(" [2] 🤝 Collaboration Groups Configuration (Collaboration)")
        print(" [3] 🎮 Function Key Settings (Menu)")
        print(" [4] 🧠 Cyberbrain and Parameter Settings (Cyberbrain)")
        print(" [5] 🔧 Tmux Session Name Settings")
        print("-" * 30)
        print(" [S] 💾 Save and Exit")
        print(" [Q] ❌ Discard Changes and Exit")

        choice = input("Please select operation: ").strip().upper()
        if choice == '1':
            manage_agents()
        elif choice == '2':
            manage_collaboration()
        elif choice == '3':
            manage_menu()
        elif choice == '4':
            manage_cyberbrain()
        elif choice == '5':
            manage_tmux()
        elif choice == 'S':
            save_config()
            break
        elif choice == 'Q':
            print("❌ Changes discarded.")
            break

if __name__ == '__main__':
    main()
