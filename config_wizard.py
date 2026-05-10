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
        print("✅ 設定已成功儲存。")
    except Exception as e:
        print(f"❌ 儲存失敗: {e}")

def prompt_model_choice(engine, current_model=None):
    engine = engine.lower()
    options = []
    if 'gemini' in engine:
        options = [("auto", "auto (預設)"), ("gemini-3.1-pro-preview", "gemini-3.1-pro-preview"), ("gemini-3-flash-preview", "gemini-3-flash-preview")]
    elif 'claude' in engine:
        options = [("haiku", "haiku (預設)"), ("sonnet", "sonnet"), ("opus", "opus")]
    elif 'codex' in engine:
        options = [("gpt-5.4-mini", "gpt-5.4-mini (預設)"), ("gpt-5.4", "gpt-5.4")]
    else:
        return input(f"模型 (model，按 Enter 保留 '{current_model or '預設'}'): ").strip()

    print(f"\n  請選擇 {engine} 的模型:")
    for i, (val, desc) in enumerate(options):
        print(f"  [{i+1}] {desc}")
    print(f"  [C] 自訂輸入 (Custom)")
    
    prompt_str = f"請選擇模型 (按 Enter 保留 '{current_model or options[0][0]}'): "
    while True:
        choice = input(prompt_str).strip()
        choice_lower = choice.lower()
        if not choice:
            return current_model if current_model else options[0][0]
        if choice_lower == 'c':
            return input("請輸入自訂模型名稱: ").strip()
        if choice_lower.isdigit():
            idx = int(choice_lower) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        
        # 支援使用者直接輸入完整的模型名稱
        valid_models = [opt[0].lower() for opt in options]
        if choice_lower in valid_models:
            return next(opt[0] for opt in options if opt[0].lower() == choice_lower)
            
        print("無效選擇，請重新輸入。")

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
        print("  ⚠️ 主層 'skills' 目錄中找不到可用的壓縮檔 (.zip, .tar.gz)。")
        return current_skills or []
        
    print("\n  可掛載的技能清單 (Skills):")
    for i, skill in enumerate(available_skills):
        print(f"  [{i+1}] {skill}")
        
    current_str = ','.join(current_skills) if current_skills else '無'
    prompt_str = f"請輸入要掛載的技能編號或名稱，以逗號分隔 (例如 1,3) [目前: {current_str}] (按 Enter 保留目前設定): "
    
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
            print("  ❌ 無效的選擇，請重新輸入。")
        else:
            return selected

def manage_agents():
    global CONFIG
    if "agents" not in CONFIG or not isinstance(CONFIG["agents"], list):
        CONFIG["agents"] = []
    
    while True:
        print("\n--- 🤖 Agent 軍團配置 ---")
        current_default = CONFIG.get("default_active_agent", "")
        for i, agent in enumerate(CONFIG["agents"]):
            is_default = " (預設活躍)" if agent.get('name') == current_default else ""
            print(f"  [{i+1}] {agent.get('name', 'Unknown')} (Engine: {agent.get('engine', 'N/A')}){is_default}")
        print("-------------------------")
        print(" [A] 新增 Agent")
        print(" [E] 修改 Agent (Edit)")
        print(" [D] 刪除 Agent")
        print(" [S] 設定預設活躍 Agent")
        print(" [R] 返回主選單")
        
        choice = input("請選擇操作: ").strip().lower()
        if choice == 'a':
            name = input("Agent 名稱: ").strip()
            if not name: continue
            engine = input("引擎 (gemini/claude/codex) [gemini]: ").strip() or "gemini"
            model = prompt_model_choice(engine)
            usecase = input("職責 (usecase) [用於 Agent 系統提示認知]: ").strip()
            desc = input("描述 (description) [用於選單與使用者辨認]: ").strip()
            new_agent = {"name": name, "engine": engine, "usecase": usecase, "description": desc}
            if model: new_agent["model"] = model
            CONFIG["agents"].append(new_agent)
            print(f"✅ Agent {name} 已新增！")
            if len(CONFIG["agents"]) == 1:
                 CONFIG["default_active_agent"] = name
        elif choice == 'e':
            idx = input("請輸入要修改的 Agent 數字: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["agents"]):
                    agent = CONFIG["agents"][idx]
                    print(f"\n修改 {agent.get('name')}:")
                    
                    new_name = input(f"新名稱 (按 Enter 保留 '{agent.get('name')}'): ").strip()
                    if new_name:
                        # Update default active agent if name changed
                        if CONFIG.get("default_active_agent") == agent.get('name'):
                            CONFIG["default_active_agent"] = new_name
                        agent['name'] = new_name
                        
                    new_engine = input(f"新引擎 (按 Enter 保留 '{agent.get('engine', 'gemini')}'): ").strip()
                    if new_engine: agent['engine'] = new_engine
                    
                    new_model = prompt_model_choice(agent.get('engine', 'gemini'), agent.get('model'))
                    if new_model: agent['model'] = new_model
                        
                    new_usecase = input(f"新職責 [用於 Agent 系統提示認知] (按 Enter 保留 '{agent.get('usecase', '')}'): ").strip()
                    if new_usecase: agent['usecase'] = new_usecase

                    new_desc = input(f"新描述 [用於選單與使用者辨認] (按 Enter 保留 '{agent.get('description', '')}'): ").strip()
                    if new_desc: agent['description'] = new_desc
                    
                    new_skills = prompt_skills_choice(agent.get('skills', []))
                    if new_skills is not None:
                        if new_skills:
                            agent['skills'] = new_skills
                        else:
                            agent.pop('skills', None)
                    
                    CONFIG["agents"][idx] = agent
                    print(f"✅ Agent 修改完成！")
        elif choice == 'd':
            idx = input("請輸入要刪除的 Agent 數字: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["agents"]):
                    del_name = CONFIG["agents"][idx].get('name', 'Unknown')
                    del CONFIG["agents"][idx]
                    print(f"🗑️ Agent {del_name} 已刪除！")
                    if CONFIG.get("default_active_agent") == del_name:
                        CONFIG["default_active_agent"] = ""
        elif choice == 's':
            agents = CONFIG.get("agents", [])
            if not agents:
                print("⚠️ 請先配置 Agent！")
                continue
            idx = input("請選擇預設 Agent 數字: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(agents):
                    CONFIG["default_active_agent"] = agents[idx].get("name")
                    print(f"✅ 預設 Agent 已更新為 {CONFIG['default_active_agent']}")
        elif choice == 'r':
            break

def manage_tmux():
    global CONFIG
    if "tmux" not in CONFIG or not CONFIG["tmux"]:
        CONFIG["tmux"] = {"session_name": "ai_octomatrix"}
    current = CONFIG["tmux"].get("session_name", "ai_octomatrix")
    print(f"\n--- 🔧 Tmux Session 名稱設定 ---")
    print(f"目前名稱: {current}")
    new_name = input("請輸入新名稱 (按 Enter 保留): ").strip()
    if new_name:
        CONFIG["tmux"]["session_name"] = new_name
        print(f"✅ Tmux Session 已更新為 {new_name}")

def manage_collaboration():
    global CONFIG
    if "collaboration_groups" not in CONFIG or not isinstance(CONFIG["collaboration_groups"], list):
        CONFIG["collaboration_groups"] = []
        
    while True:
        print("\n--- 🤝 協作群組配置 (Collaboration Groups) ---")
        for i, group in enumerate(CONFIG["collaboration_groups"]):
            print(f"  [{i+1}] {group.get('name', 'Unknown')} (Members: {', '.join(group.get('members', []))})")
        print("-------------------------")
        print(" [A] 新增協作群組")
        print(" [E] 修改協作群組 (Edit)")
        print(" [D] 刪除協作群組")
        print(" [R] 返回主選單")
        
        choice = input("請選擇操作: ").strip().lower()
        
        valid_agents = [a.get('name') for a in CONFIG.get('agents', []) if a.get('name')]
        
        if choice == 'a':
            name = input("群組名稱 (例如 core_team): ").strip()
            if not name: continue
            desc = input("群組描述: ").strip()
            print(f"  💡 目前可選的 Agent: {', '.join(valid_agents)}")
            members_str = input("群組成員 (以逗號分隔，例如 Gupa,Chod): ").strip()
            members = [m.strip() for m in members_str.split(',') if m.strip()]
            
            # Validation
            final_members = []
            for m in members:
                if m not in valid_agents:
                    print(f"⚠️  警告: Agent '{m}' 尚未在 Agent 軍團中建立！這可能導致執行時的錯誤。")
                    if prompt_bool(f"是否仍要將 '{m}' 加入群組?", False):
                        final_members.append(m)
                else:
                    final_members.append(m)
            members = final_members
            if not members:
                print("❌ 群組成員不可為空，已取消操作。")
                continue
                    
            roles = {}
            for m in members:
                role = input(f"為 {m} 設定群組內角色與職責: ").strip()
                if role:
                    roles[m] = role
            CONFIG["collaboration_groups"].append({
                "name": name,
                "description": desc,
                "members": members,
                "roles": roles
            })
            print(f"✅ 協作群組 {name} 已新增！")
        elif choice == 'e':
            idx = input("請輸入要修改的群組數字: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["collaboration_groups"]):
                    group = CONFIG["collaboration_groups"][idx]
                    print(f"\n修改協作群組 {group.get('name')}:")
                    
                    new_name = input(f"新群組名稱 (按 Enter 保留 '{group.get('name')}'): ").strip()
                    if new_name: group['name'] = new_name
                    
                    new_desc = input(f"新群組描述 (按 Enter 保留 '{group.get('description', '')}'): ").strip()
                    if new_desc: group['description'] = new_desc
                    
                    print(f"目前成員: {', '.join(group.get('members', []))}")
                    if prompt_bool("是否要重新設定成員與職責?", False):
                        print(f"  💡 目前可選的 Agent: {', '.join(valid_agents)}")
                        members_str = input("新群組成員 (以逗號分隔): ").strip()
                        members = [m.strip() for m in members_str.split(',') if m.strip()]
                        
                        # Validation
                        final_members = []
                        for m in members:
                            if m not in valid_agents:
                                print(f"⚠️  警告: Agent '{m}' 尚未在 Agent 軍團中建立！這可能導致執行時的錯誤。")
                                if prompt_bool(f"是否仍要將 '{m}' 加入群組?", False):
                                    final_members.append(m)
                            else:
                                final_members.append(m)
                        members = final_members
                        if not members:
                            print("❌ 群組成員不可為空，已取消更新成員名單。")
                            continue
                                
                        roles = {}
                        for m in members:
                            old_role = group.get('roles', {}).get(m, '')
                            role = input(f"為 {m} 設定群組內角色與職責 (目前: '{old_role}'): ").strip()
                            if role:
                                roles[m] = role
                            elif old_role:
                                roles[m] = old_role
                        group['members'] = members
                        group['roles'] = roles
                    
                    CONFIG["collaboration_groups"][idx] = group
                    print("✅ 協作群組修改完成！")
        elif choice == 'd':
            idx = input("請輸入要刪除的群組數字: ").strip()
            if idx.isdigit():
                idx = int(idx) - 1
                if 0 <= idx < len(CONFIG["collaboration_groups"]):
                    del_name = CONFIG["collaboration_groups"][idx].get('name', 'Unknown')
                    del CONFIG["collaboration_groups"][idx]
                    print(f"🗑️ 協作群組 {del_name} 已刪除！")
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
        print("\n--- 🧠 電子腦參數設定 (Cyberbrain) ---")
        print(f" [1] GHOST 容量檢測頻率: {CONFIG.get('octo_cyberbrain', {}).get('ghost_check_interval_sec', 60)} 秒")
        print(f" [2] 淺層 GHOST 壓縮閾值: {CONFIG.get('octo_cyberbrain', {}).get('ghost_compression_threshold_kb', 150)} KB")
        print(f" [3] 長期 GHOST 壓縮閥值: {CONFIG.get('octo_cyberbrain', {}).get('ghost_long_term_compression_limit', 12)} 個淺層壓縮GHOST")
        print(f" [4] GHOST 喚醒上下文深度: {CONFIG.get('octo_cyberbrain', {}).get('ghost_awake_context_depth', 50)} 行")
        print(" [R] 返回主選單")
        
        choice = input("請選擇要修改的參數: ").strip().lower()
        if choice == '1':
            val = input("請輸入 GHOST 容量檢測頻率 (秒): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_check_interval_sec"] = int(val)
                print("✅ 參數已更新")
        elif choice == '2':
            val = input("請輸入淺層 GHOST 壓縮閾值 (KB): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_compression_threshold_kb"] = int(val)
                print("✅ 參數已更新")
        elif choice == '3':
            val = input("請輸入長期 GHOST 壓縮閥值 (個): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_long_term_compression_limit"] = int(val)
                print("✅ 參數已更新")
        elif choice == '4':
            val = input("請輸入 GHOST 喚醒上下文深度 (行): ").strip()
            if val.isdigit():
                if "octo_cyberbrain" not in CONFIG: CONFIG["octo_cyberbrain"] = {}
                CONFIG["octo_cyberbrain"]["ghost_awake_context_depth"] = int(val)
                print("✅ 參數已更新")
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
        print("\n--- 🎮 功能鍵設定 (Menu) ---")
        for i, row in enumerate(CONFIG["menu"]):
            labels = []
            for j, item in enumerate(row):
                label = item.get('label') if isinstance(item, dict) else item
                labels.append(f"[{j+1}] {label}")
            print(f"  [Row {i+1}] {' | '.join(labels)}")
        print("-------------------------")
        print(" [A] 新增功能鍵 (Add Item)")
        print(" [G] 自動生成內建功能鍵 (Auto-generate)")
        print(" [E] 修改功能鍵 (Edit Item)")
        print(" [M] 移動功能鍵 (Move Item)")
        print(" [D] 刪除 (Delete Row/Item/All)")
        print(" [R] 返回主選單")
        
        choice = input("請選擇操作: ").strip().lower()
        if choice == 'a':
            label = input("  按鈕顯示文字 (label): ").strip()
            if not label: continue
            
            has_input = prompt_bool("  點擊此按鈕後，是否需要跳出輸入框讓您補充內容 (例如: 請幫我翻譯 ?)?", False)
            if has_input:
                print("  💡 提示: 您可以將問號 ? 放在指令的任何位置代表您要輸入的內容 (例如: 請幫我查詢 ? 的資料)")
                command = input("  對應指令 (若未包含 ? 則自動補在結尾): ").strip()
                if not command: command = label
                if "?" not in command:
                    command = f"{command} ?"
                
                # 將使用者輸入的 ? 轉換為系統底層使用的 {input}
                command = command.replace("?", "{input}")
                
                prompt_txt = input("  輸入提示文字 (prompt): ").strip()
                new_item = {"label": label, "command": command, "prompt": prompt_txt}
            else:
                command = input("  對應指令 (例如: 查天氣): ").strip()
                if not command: command = label
                new_item = {"label": label, "command": command}
            
            print("\n  要插入到哪裡？")
            print("  [T] 最上層 (Top - 建立新 Row)")
            print("  [B] 最底層 (Bottom - 建立新 Row)")
            avail_rows = [idx for idx, r in enumerate(CONFIG["menu"]) if len(r) < 4]
            for r_idx in avail_rows:
                print(f"  [{r_idx+1}] 插入到 Row {r_idx+1} (目前 {len(CONFIG['menu'][r_idx])}/4)")
            
            pos = input("  請選擇插入位置 [T/B/數字]: ").strip().upper()
            if pos == 'T':
                CONFIG["menu"].insert(0, [new_item])
            elif pos == 'B' or not pos:
                CONFIG["menu"].append([new_item])
            elif pos.isdigit() and (int(pos) - 1) in avail_rows:
                CONFIG["menu"][int(pos)-1].append(new_item)
            else:
                CONFIG["menu"].append([new_item])
            print("✅ 功能鍵已新增！")
            
        elif choice == 'g':
            print("\n開始生成內建功能鍵...")
            
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
            if prompt_bool("是否加入帶參數的切換功能 (/switch {input})?", True):
                switch_items.append({"label": "🔄 切換 Agent", "command": "/switch {input}", "prompt": "請輸入要切換的 Agent 名稱:"})
            
            if prompt_bool("是否為目前已建立的 Agent 加入專屬切換快捷鍵?", True):
                agents = CONFIG.get("agents", [])
                for agent in agents:
                    name = agent.get("name")
                    if name:
                        switch_items.append({"label": f"🐙 喚醒 {name}", "command": f"/switch {name}"})
            
            if switch_items:
                append_to_menu(switch_items)
                
            action_items = []
            if prompt_bool("是否加入狀態檢查與擷取修復功能 (/capture, /inspect, /fix, /interrupt)?", True):
                action_items.append({"label": "📸 狀態擷取", "command": "/capture {input}", "prompt": "請輸入要擷取狀態的 Agent 名稱:"})
                action_items.append({"label": "🔍 健檢", "command": "/inspect {input}", "prompt": "請輸入要檢查的 Agent 名稱:"})
                action_items.append({"label": "🚑 修復", "command": "/fix {input}", "prompt": "請輸入要修復的 Agent 名稱:"})
                action_items.append({"label": "🛑 中斷", "command": "/interrupt"})
                append_to_menu(action_items)
                
            sys_items = []
            if prompt_bool("是否加入系統營運與控制功能 (/clear, /resume_latest, /help, /status)?", True):
                sys_items.append({"label": "🧹 清除上下文", "command": "/clear"})
                sys_items.append({"label": "🧠 恢復上下文", "command": "/resume_latest"})
                sys_items.append({"label": "📖 說明書", "command": "/help"})
                sys_items.append({"label": "📊 系統狀態", "command": "/status"})
                append_to_menu(sys_items)
                
            print("✅ 內建功能鍵已自動置底生成！")
            
        elif choice == 'e':
            r_idx = input("請輸入要修改的 Row 數字: ").strip()
            i_idx = input("請輸入該 Row 中的按鈕數字: ").strip()
            if r_idx.isdigit() and i_idx.isdigit():
                r = int(r_idx) - 1
                i = int(i_idx) - 1
                if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                    item = CONFIG["menu"][r][i]
                    if not isinstance(item, dict):
                        item = {"label": item, "command": item}
                    print(f"目前設定: Label='{item.get('label')}', Command='{item.get('command')}'")
                    new_label = input("新顯示文字 (按 Enter 保留): ").strip()
                    if new_label: item["label"] = new_label
                    new_cmd = input("新指令 (按 Enter 保留): ").strip()
                    if new_cmd: item["command"] = new_cmd
                    if "{input}" in item.get("command", ""):
                        new_prompt = input(f"新提示文字 (目前: '{item.get('prompt','')}'): ").strip()
                        if new_prompt: item["prompt"] = new_prompt
                    CONFIG["menu"][r][i] = item
                    print("✅ 修改完成！")
                    
        elif choice == 'm':
            r_idx = input("請輸入要移動的按鈕所在 Row 數字: ").strip()
            i_idx = input("請輸入該 Row 中的按鈕數字: ").strip()
            if r_idx.isdigit() and i_idx.isdigit():
                r = int(r_idx) - 1
                i = int(i_idx) - 1
                if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                    item = CONFIG["menu"][r].pop(i)
                    if not CONFIG["menu"][r]:
                        del CONFIG["menu"][r]
                        
                    print("\n  要移動到哪裡？")
                    print("  [T] 最上層 (建立新 Row)")
                    print("  [B] 最底層 (建立新 Row)")
                    avail_rows = [idx for idx, row in enumerate(CONFIG["menu"]) if len(row) < 4]
                    for idx in avail_rows:
                        print(f"  [{idx+1}] 移動到 Row {idx+1} (目前 {len(CONFIG['menu'][idx])}/4)")
                        
                    pos = input("  請選擇目標位置 [T/B/數字]: ").strip().upper()
                    if pos == 'T':
                        CONFIG["menu"].insert(0, [item])
                    elif pos == 'B' or not pos:
                        CONFIG["menu"].append([item])
                    elif pos.isdigit() and (int(pos) - 1) in avail_rows:
                        CONFIG["menu"][int(pos)-1].append(item)
                    else:
                        CONFIG["menu"].append([item])
                    print("✅ 移動完成！")

        elif choice == 'd':
            print(" [1] 刪除整列 (Row)")
            print(" [2] 刪除單個按鈕 (Item)")
            print(" [3] 清除所有功能鍵 (Clear All)")
            sub_c = input("請選擇: ").strip()
            if sub_c == '1':
                r_idx = input("請輸入要刪除的 Row 數字: ").strip()
                if r_idx.isdigit():
                    r = int(r_idx) - 1
                    if 0 <= r < len(CONFIG["menu"]):
                        del CONFIG["menu"][r]
                        print("🗑️ 選單列已刪除！")
            elif sub_c == '2':
                r_idx = input("請輸入 Row 數字: ").strip()
                i_idx = input("請輸入按鈕數字: ").strip()
                if r_idx.isdigit() and i_idx.isdigit():
                    r = int(r_idx) - 1
                    i = int(i_idx) - 1
                    if 0 <= r < len(CONFIG["menu"]) and 0 <= i < len(CONFIG["menu"][r]):
                        del CONFIG["menu"][r][i]
                        if not CONFIG["menu"][r]:
                            del CONFIG["menu"][r]
                        print("🗑️ 按鈕已刪除！")
            elif sub_c == '3':
                if prompt_bool("⚠️ 確定要清除所有功能鍵嗎?", False):
                    CONFIG["menu"] = []
                    print("🗑️ 所有功能鍵已清除！")
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

                # 確保必要節點存在並賦予預設值
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
            print(f"載入設定檔失敗: {e}")
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
        print("\n🐙 OctoMatrix - 系統設定主控台")
        print("=" * 40)
        print(f"當前設定實例: {os.path.basename(CONFIG_PATH)}")
        print("-" * 30)
        print(" [1] 🤖 Agent 軍團配置")
        print(" [2] 🤝 協作群組配置 (Collaboration)")
        print(" [3] 🎮 功能鍵設定 (Menu)")
        print(" [4] 🧠 電子腦與參數設定 (Cyberbrain)")
        print(" [5] 🔧 Tmux Session 名稱設定")
        print("-" * 30)
        print(" [S] 💾 儲存並退出")
        print(" [Q] ❌ 放棄變更退出")

        choice = input("請選擇操作: ").strip().upper()
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
            print("❌ 已放棄變更。")
            break

if __name__ == '__main__':
    main()
