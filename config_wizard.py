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
        
        # v4: Create dedicated Linux account (Non-container environment, and exclude generating Docker deployment configs)
        if not os.path.exists('/.dockerenv') and 'docker-deploy' not in os.path.abspath(CONFIG_PATH):
            import subprocess
            password = CONFIG.get("agent_password", "octomatrix")
            print("🔒 Configuring dedicated Linux account isolation...")
            for agent in CONFIG.get('agents', []):
                agent_name = agent.get('name', '').lower()
                if agent_name:
                    agent_user = f"agent_{agent_name}"
                    # Check if user exists
                    if subprocess.run(['id', agent_user], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                        try:
                            subprocess.run(['sudo', 'useradd', '-m', '-s', '/bin/bash', agent_user], check=True)
                            p = subprocess.Popen(['sudo', 'chpasswd'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            p.communicate(input=f"{agent_user}:{password}".encode('utf-8'))
                            print(f"  ✅ Created user: {agent_user}")
                        except Exception as e:
                            print(f"  ❌ Failed to create user {agent_user}: {e}")
                            
    except Exception as e:
        print(f"❌ Save failed: {e}")

def prompt_model_choice(engine, current_model=None):
    engine = engine.lower()
    options = []
    if 'gemini' in engine:
        options = [("auto", "auto (Default)"), ("gemini-3.1-pro-preview", "gemini-3.1-pro-preview"), ("gemini-3-flash-preview", "gemini-3-flash-preview")]
    elif 'claude' in engine:
        options = [("sonnet", "sonnet (Default)"), ("haiku", "haiku"), ("opus", "opus")]
    elif 'codex' in engine:
        options = [("gpt-5.4-mini", "gpt-5.4-mini (Default)"), ("gpt-5.4", "gpt-5.4")]
    elif 'agy' in engine or 'antigravity' in engine:
        options = [("auto", "auto (Default)"), ("gemini-3.5-flash", "gemini-3.5-flash"), ("gemini-3.1-pro", "gemini-3.1-pro"), ("claude-sonnet-4-6", "claude-sonnet-4-6"), ("claude-opus-4-6", "claude-opus-4-6")]
    else:
        return input(f"Model (press Enter to keep '{current_model or 'default'}'): ").strip()

    print(f"\n  Please select model for {engine}:")
    for i, (val, desc) in enumerate(options):
        print(f"  [{i+1}] {desc}")
    print(f"  [C] Custom Input")
    
    prompt_str = f"Select model (press Enter to keep '{current_model or options[0][0]}'): "
    while True:
        choice = input(prompt_str).strip()
        choice_lower = choice.lower()
        if not choice:
            return current_model if current_model else options[0][0]
        if choice_lower == 'c':
            return input("Enter custom model name: ").strip()
        if choice_lower.isdigit():
            idx = int(choice_lower) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        
        # Support direct input of full model names
        valid_models = [opt[0].lower() for opt in options]
        if choice_lower in valid_models:
            return next(opt[0] for opt in options if opt[0].lower() == choice_lower)
            
        print("Invalid choice, please try again.")

def prompt_skills_choice(current_skills=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    skills_dir = os.path.join(base_dir, 'skills')
    available_skills = []
    
    if os.path.exists(skills_dir):
        for item in os.listdir(skills_dir):
            if item.endswith('.zip'):
                available_skills.append(item[:-4])
            elif item.endswith('.tar.gz'):
                available_skills.append(item[:-7])
                
    if not available_skills:
        print("  ⚠️ No available archive files (.zip, .tar.gz) found in the root 'skills' directory.")
        return current_skills or []
        
    print("\n  Mountable Skills List:")
    for i, skill in enumerate(available_skills):
        print(f"  [{i+1}] {skill}")
        
    current_str = ','.join(current_skills) if current_skills else 'None'
    prompt_str = f"Enter skill numbers or names to mount, separated by commas (e.g., 1,3) [Current: {current_str}] (Press Enter to keep current): "
    
    while True:
        choice = input(prompt_str).strip()
        if not choice:
            return current_skills or []
            
        selected = []
        invalid = False
        for p in choice.split(','):
            p = p.strip()
            if not p: continue
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(available_skills):
                    skill_name = available_skills[idx]
                    if skill_name not in selected:
                        selected.append(skill_name)
                else:
                    invalid = True
                    break
            elif p in available_skills:
                if p not in selected:
                    selected.append(p)
            else:
                invalid = True
                break
                
        if invalid:
            print("  ❌ Invalid choice, please try again.")
        else:
            return selected

def manage_agents():
    global CONFIG
    if "agents" not in CONFIG or not isinstance(CONFIG["agents"], list):
        CONFIG["agents"] = []
    
    while True:
        print("\n--- 🤖 Agent Squadron Configuration ---")
        current_default = CONFIG.get("default_active_agent", "")
        for i, agent in enumerate(CONFIG["agents"]):
            is_default = " (Default Active)" if agent.get('name') == current_default else ""
            print(f"  [{i+1}] {agent.get('name', 'Unknown')} (Engine: {agent.get('engine', 'N/A')}){is_default}")
        print("-------------------------")
        print(" [A] Add Agent")
        print(" [E] Edit Agent")
        print(" [D] Delete Agent")
        print(" [S] Set Default Active Agent")
        print(" [R] Return to Main Menu")
        
        choice = input("Select operation: ").strip().lower()
        if choice == 'a':
            name = input("Agent Name: ").strip()
            if not name: continue
            engine = input("Engine (gemini/claude/codex/agy) [gemini]: ").strip() or "gemini"
            model = prompt_model_choice(engine)
            usecase = input("Responsibility (usecase) [for Agent system prompt awareness]: ").strip()
            desc = input("Description (description) [for menu and user identification]: ").strip()
            skills = prompt_skills_choice()
            new_agent = {"name": name, "engine": engine, "usecase": usecase, "description": desc}
            if model: new_agent["model"] = model
            if skills: new_agent["skills"] = skills
            CONFIG["agents"].append(new_agent)
            print(f"✅ Agent {name} added!")
            if len(CONFIG["agents"]) == 1:
                 CONFIG["default_active_agent"] = name
        elif choice == 'e':
            idx = input("Enter Agent number to edit: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["agents"]):
                    agent = CONFIG["agents"][idx]
                    print(f"\nEditing {agent.get('name')}:")
                    
                    new_name = input(f"New Name (press Enter to keep '{agent.get('name')}'): ").strip()
                    if new_name:
                        # Update default active agent if name changed
                        if CONFIG.get("default_active_agent") == agent.get('name'):
                            CONFIG["default_active_agent"] = new_name
                        agent['name'] = new_name
                        
                    new_engine = input(f"New Engine (press Enter to keep '{agent.get('engine', 'gemini')}'): ").strip()
                    if new_engine: agent['engine'] = new_engine
                    
                    new_model = prompt_model_choice(agent.get('engine', 'gemini'), agent.get('model'))
                    if new_model: agent['model'] = new_model
                        
                    new_usecase = input(f"New Responsibility [for Agent system prompt awareness] (press Enter to keep '{agent.get('usecase', '')}'): ").strip()
                    if new_usecase: agent['usecase'] = new_usecase

                    new_desc = input(f"New Description [for menu and user identification] (press Enter to keep '{agent.get('description', '')}'): ").strip()
                    if new_desc: agent['description'] = new_desc
                    
                    new_skills = prompt_skills_choice(agent.get('skills', []))
                    if new_skills is not None:
                        if new_skills:
                            agent['skills'] = new_skills
                        else:
                            agent.pop('skills', None)
                    
                    CONFIG["agents"][idx] = agent
                    print(f"✅ Agent editing completed!")
        elif choice == 'd':
            idx = input("Enter Agent number to delete: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["agents"]):
                    del_name = CONFIG["agents"][idx].get('name', 'Unknown')
                    del CONFIG["agents"][idx]
                    print(f"🗑️ Agent {del_name} deleted!")
                    if CONFIG.get("default_active_agent") == del_name:
                        CONFIG["default_active_agent"] = ""
        elif choice == 's':
            agents = CONFIG.get("agents", [])
            if not agents:
                print("⚠️ Please configure Agents first!")
                continue
            idx = input("Select default Agent number: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(agents):
                    CONFIG["default_active_agent"] = agents[idx].get("name")
                    print(f"✅ Default Agent updated to {CONFIG['default_active_agent']}")
        elif choice == 'r':
            break

def manage_tmux():
    global CONFIG
    if "tmux" not in CONFIG or not CONFIG["tmux"]:
        CONFIG["tmux"] = {"session_name": "ai_octomatrix"}
    current = CONFIG["tmux"].get("session_name", "ai_octomatrix")
    print(f"\n--- 🔧 Tmux Session Name Settings ---")
    print(f"Current Name: {current}")
    new_name = input("Enter new name (press Enter to keep): ").strip()
    if new_name:
        CONFIG["tmux"]["session_name"] = new_name
        print(f"✅ Tmux Session updated to {new_name}")

def manage_collaboration():
    global CONFIG
    if "collaboration_groups" not in CONFIG or not isinstance(CONFIG["collaboration_groups"], list):
        CONFIG["collaboration_groups"] = []
        
    while True:
        print("\n--- 🤝 Collaboration Group Configuration ---")
        for i, group in enumerate(CONFIG["collaboration_groups"]):
            print(f"  [{i+1}] {group.get('name', 'Unknown')} (Members: {', '.join(group.get('members', []))})")
        print("-------------------------")
        print(" [A] Add Collaboration Group")
        print(" [E] Edit Collaboration Group")
        print(" [D] Delete Collaboration Group")
        print(" [R] Return to Main Menu")
        
        choice = input("Select operation: ").strip().lower()
        
        valid_agents = [a.get('name') for a in CONFIG.get('agents', []) if a.get('name')]
        
        if choice == 'a':
            name = input("Group Name (e.g., core_team): ").strip()
            if not name: continue
            desc = input("Group Description: ").strip()
            print(f"  💡 Currently available Agents: {', '.join(valid_agents)}")
            members_str = input("Group Members (comma separated, e.g., Gupa,Chod): ").strip()
            members = [m.strip() for m in members_str.split(',') if m.strip()]
            
            # Validation
            final_members = []
            for m in members:
                if m not in valid_agents:
                    print(f"⚠️  Warning: Agent '{m}' not found in Squadron! This might cause execution errors.")
                    if prompt_bool(f"Still add '{m}' to the group?", False):
                        final_members.append(m)
                else:
                    final_members.append(m)
            members = final_members
            if not members:
                print("❌ Group members cannot be empty. Operation cancelled.")
                continue
                    
            roles = {}
            for m in members:
                role = input(f"Set role and responsibility for {m} in the group: ").strip()
                if role:
                    roles[m] = role
            CONFIG["collaboration_groups"].append({
                "name": name,
                "description": desc,
                "members": members,
                "roles": roles
            })
            print(f"✅ Collaboration Group {name} added!")
        elif choice == 'e':
            idx = input("Enter Group number to edit: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["collaboration_groups"]):
                    group = CONFIG["collaboration_groups"][idx]
                    print(f"\nEditing Collaboration Group {group.get('name')}:")
                    
                    new_name = input(f"New Group Name (press Enter to keep '{group.get('name')}'): ").strip()
                    if new_name: group['name'] = new_name
                    
                    new_desc = input(f"New Group Description (press Enter to keep '{group.get('description', '')}'): ").strip()
                    if new_desc: group['description'] = new_desc
                    
                    print(f"Current Members: {', '.join(group.get('members', []))}")
                    if prompt_bool("Reset members and roles?", False):
                        print(f"  💡 Currently available Agents: {', '.join(valid_agents)}")
                        members_str = input("New Group Members (comma separated): ").strip()
                        members = [m.strip() for m in members_str.split(',') if m.strip()]
                        
                        # Validation
                        final_members = []
                        for m in members:
                            if m not in valid_agents:
                                print(f"⚠️  Warning: Agent '{m}' not found in Squadron! This might cause execution errors.")
                                if prompt_bool(f"Still add '{m}' to the group?", False):
                                    final_members.append(m)
                            else:
                                final_members.append(m)
                        members = final_members
                        if not members:
                            print("❌ Group members cannot be empty. Member list update cancelled.")
                            continue
                                
                        roles = {}
                        for m in members:
                            old_role = group.get('roles', {}).get(m, '')
                            role = input(f"Set role and responsibility for {m} (Current: '{old_role}'): ").strip()
                            if role:
                                roles[m] = role
                            elif old_role:
                                roles[m] = old_role
                        group['members'] = members
                        group['roles'] = roles
                    
                    CONFIG["collaboration_groups"][idx] = group
                    print("✅ Collaboration Group editing completed!")
        elif choice == 'd':
            idx = input("Enter Group number to delete: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["collaboration_groups"]):
                    del_name = CONFIG["collaboration_groups"][idx].get('name', 'Unknown')
                    del CONFIG["collaboration_groups"][idx]
                    print(f"🗑️ Collaboration Group {del_name} deleted!")
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
        print("\n--- 🧠 Cyberbrain Parameter Settings ---")
        print(f" [1] GHOST Capacity Check Frequency: {CONFIG.get('octo_cyberbrain', {}).get('ghost_check_interval_sec', 60)} sec")
        print(f" [2] Shallow GHOST Compression Threshold: {CONFIG.get('octo_cyberbrain', {}).get('ghost_compression_threshold_kb', 150)} KB")
        print(f" [3] Long-term GHOST Compression Threshold: {CONFIG.get('octo_cyberbrain', {}).get('ghost_long_term_compression_limit', 12)} shallow GHOSTs")
        print(f" [4] GHOST Awake Context Depth: {CONFIG.get('octo_cyberbrain', {}).get('ghost_awake_context_depth', 50)} lines")
        print(" [R] Return to Main Menu")
        
        choice = input("Select parameter to edit: ").strip().lower()
        if choice == '1':
            val = input("Enter GHOST Capacity Check Frequency (sec): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_check_interval_sec"] = int(val)
                print("✅ Parameter updated")
        elif choice == '2':
            val = input("Enter Shallow GHOST Compression Threshold (KB): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_compression_threshold_kb"] = int(val)
                print("✅ Parameter updated")
        elif choice == '3':
            val = input("Enter Long-term GHOST Compression Threshold (count): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_long_term_compression_limit"] = int(val)
                print("✅ Parameter updated")
        elif choice == '4':
            val = input("Enter GHOST Awake Context Depth (lines): ").strip()
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
        print("\n--- 🎮 Custom Menu Settings ---")
        for i, row in enumerate(CONFIG["menu"]):
            labels = []
            for j, item in enumerate(row):
                label = item.get('label') if isinstance(item, dict) else item
                labels.append(f"[{j+1}] {label}")
            print(f"  [Row {i+1}] {' | '.join(labels)}")
        print("-------------------------")
        print(" [A] Add Menu Item")
        print(" [G] Auto-generate Built-in Menu Items")
        print(" [E] Edit Menu Item")
        print(" [M] Move Menu Item")
        print(" [D] Delete (Row/Item/All)")
        print(" [R] Return to Main Menu")
        
        choice = input("Select operation: ").strip().lower()
        if choice == 'a':
            label = input("  Button Label (text shown on button): ").strip()
            if not label: continue
            
            has_input = prompt_bool("  Should this button trigger an input box for additional content (e.g., 'Translate ?')?", False)
            if has_input:
                print("  💡 Tip: You can use '?' anywhere in the command to represent your input (e.g., 'Search for ? data')")
                command = input("  Command (if '?' is missing, it will be automatically appended): ").strip()
                if not command: command = label
                if "?" not in command:
                    command = f"{command} ?"
                
                # Convert '?' to '{input}' used by the system
                command = command.replace("?", "{input}")
                
                prompt_txt = input("  Input Box Prompt (text shown in input box): ").strip()
                new_item = {"label": label, "command": command, "prompt": prompt_txt}
            else:
                command = input("  Command (e.g., Check Weather): ").strip()
                if not command: command = label
                new_item = {"label": label, "command": command}
            
            print("\n  Where to insert?")
            print("  [T] Top (Create new Row)")
            print("  [B] Bottom (Create new Row)")
            avail_rows = [idx for idx, r in enumerate(CONFIG["menu"]) if len(r) < 4]
            for r_idx in avail_rows:
                print(f"  [{r_idx+1}] Insert into Row {r_idx+1} (Current {len(CONFIG['menu'][r_idx])}/4)")
            
            pos = input("  Select position [T/B/number]: ").strip().upper()
            if pos == 'T':
                CONFIG["menu"].insert(0, [new_item])
            elif pos == 'B' or not pos:
                CONFIG["menu"].append([new_item])
            elif pos.isdigit() and (int(pos) - 1) in avail_rows:
                CONFIG["menu"][int(pos)-1].append(new_item)
            else:
                CONFIG["menu"].append([new_item])
            print("✅ Menu item added!")
            
        elif choice == 'g':
            print("\nStarting auto-generation of built-in menu items...")
            
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
            if prompt_bool("Add parameterized switch function (/switch {input})?", True):
                switch_items.append({"label": "🔄 Switch Agent", "command": "/switch {input}", "prompt": "Enter Agent name to switch to:"})
            
            if prompt_bool("Add dedicated switch shortcuts for currently configured Agents?", True):
                agents = CONFIG.get("agents", [])
                for agent in agents:
                    name = agent.get("name")
                    if name:
                        switch_items.append({"label": f"🐙 Wake {name}", "command": f"/switch {name}"})
            
            if switch_items:
                append_to_menu(switch_items)
                
            action_items = []
            if prompt_bool("Add status check and capture/fix functions (/capture, /inspect, /fix, /interrupt)?", True):
                action_items.append({"label": "📸 Capture Status", "command": "/capture {input}", "prompt": "Enter Agent name to capture:"})
                action_items.append({"label": "🔍 Health Check", "command": "/inspect {input}", "prompt": "Enter Agent name to inspect:"})
                action_items.append({"label": "🚑 Fix", "command": "/fix {input}", "prompt": "Enter Agent name to fix:"})
                action_items.append({"label": "🛑 Interrupt", "command": "/interrupt"})
                append_to_menu(action_items)
                
            sys_items = []
            if prompt_bool("Add system operation and control functions (/clear, /resume_latest, /help, /status)?", True):
                sys_items.append({"label": "🧹 Clear Context", "command": "/clear"})
                sys_items.append({"label": "🧠 Resume Context", "command": "/resume_latest"})
                sys_items.append({"label": "📖 User Manual", "command": "/help"})
                sys_items.append({"label": "📊 System Status", "command": "/status"})
                append_to_menu(sys_items)

            avatar_items = []
            if prompt_bool("Add visual avatar reconstruction function (/avatar_renew)?", True):
                avatar_items.append({"label": "🎭 Renew Avatar", "command": "/avatar_renew {input}", "prompt": "Please describe the desired visual avatar and persona traits:"})
                append_to_menu(avatar_items)

            print("✅ Built-in menu items have been auto-generated!")            
        elif choice == 'e':
            r_idx = input("Enter Row number: ").strip()
            i_idx = input("Enter Button number in that row: ").strip()
            if r_idx.isdigit() and i_idx.isdigit():
                r = int(r_idx) - 1
                i = int(i_idx) - 1
                if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                    item = CONFIG["menu"][r][i]
                    if not isinstance(item, dict):
                        item = {"label": item, "command": item}
                    print(f"Current Settings: Label='{item.get('label')}', Command='{item.get('command')}'")
                    new_label = input("New Label (press Enter to keep): ").strip()
                    if new_label: item["label"] = new_label
                    new_cmd = input("New Command (press Enter to keep): ").strip()
                    if new_cmd: item["command"] = new_cmd
                    if "{input}" in item.get("command", ""):
                        new_prompt = input(f"New Input Prompt (Current: '{item.get('prompt','')}'): ").strip()
                        if new_prompt: item["prompt"] = new_prompt
                    CONFIG["menu"][r][i] = item
                    print("✅ Editing completed!")
                    
        elif choice == 'm':
            r_idx = input("Enter Row number of the button to move: ").strip()
            i_idx = input("Enter Button number to move: ").strip()
            if r_idx.isdigit() and i_idx.isdigit():
                r = int(r_idx) - 1
                i = int(i_idx) - 1
                if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                    item = CONFIG["menu"][r].pop(i)
                    if not CONFIG["menu"][r]:
                        del CONFIG["menu"][r]
                        
                    print("\n  Where to move?")
                    print("  [T] Top (Create new Row)")
                    print("  [B] Bottom (Create new Row)")
                    avail_rows = [idx for idx, row in enumerate(CONFIG["menu"]) if len(row) < 4]
                    for idx in avail_rows:
                        print(f"  [{idx+1}] Move to Row {idx+1} (Current {len(CONFIG['menu'][idx])}/4)")
                        
                    pos = input("  Select target position [T/B/number]: ").strip().upper()
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
            print(" [1] Delete entire Row")
            print(" [2] Delete single Item")
            print(" [3] Clear All menu items")
            sub_c = input("Select: ").strip()
            if sub_c == '1':
                r_idx = input("Enter Row number to delete: ").strip()
                if r_idx.isdigit():
                    r = int(r_idx) - 1
                    if 0 <= r < len(CONFIG["menu"]):
                        del CONFIG["menu"][r]
                        print("🗑️ Menu row deleted!")
            elif sub_c == '2':
                r_idx = input("Enter Row number: ").strip()
                i_idx = input("Enter Button number: ").strip()
                if r_idx.isdigit() and i_idx.isdigit():
                    r = int(r_idx) - 1
                    i = int(i_idx) - 1
                    if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                        del CONFIG["menu"][r][i]
                        if not CONFIG["menu"][r]:
                            del CONFIG["menu"][r]
                        print("🗑️ Button deleted!")
            elif sub_c == '3':
                if prompt_bool("⚠️ Are you sure you want to clear all menu items?", False):
                    CONFIG["menu"] = []
                    print("🗑️ All menu items cleared!")
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

                # Ensure necessary nodes exist and provide default values
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

        # Scrub deprecated cleanup_policy keys if they exist
        if "default_cleanup_policy" in CONFIG:
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
        print(f"Current Instance: {os.path.basename(CONFIG_PATH)}")
        print("-" * 30)
        print(" [1] 🤖 Agent Squadron Configuration")
        print(" [2] 🤝 Collaboration Group Configuration")
        print(" [3] 🎮 Custom Menu Settings")
        print(" [4] 🧠 Cyberbrain & Parameter Settings")
        print(" [5] 🔧 Tmux Session Name Settings")
        print("-" * 30)
        print(" [S] 💾 Save & Exit")
        print(" [Q] ❌ Quit without saving")

        choice = input("Select operation: ").strip().upper()
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
