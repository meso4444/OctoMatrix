#!/usr/bin/env python3
# setup_agent_env.py
# 負責初始化 Agent 的家目錄結構與協作連結

import os
import sys
import yaml
import shutil
import subprocess

# 定義路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.yaml')
AGENT_HOME_BASE = os.path.join(BASE_DIR, 'agent_home')
TEMPLATES_DIR = BASE_DIR

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 錯誤: 找不到設定檔 {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def setup_agent_dirs(agent_name):
    """建立單一 Agent 的目錄結構"""
    home = os.path.join(AGENT_HOME_BASE, agent_name)
    subdirs = ['toolbox', 'knowledge', 'my_shared_space', 'downloads_temp', 'project', 'skillbox']
    
    for d in subdirs:
        path = os.path.join(home, d)
        if not os.path.exists(path):
            os.makedirs(path)
            # print(f"   + 建立目錄: {d}")
    
    return home

def setup_collaboration_links(agents, groups):
    """建立協作羣組的軟連結，並清理不再協作的舊連結"""
    agent_names = [a['name'] for a in agents]
    
    # 1. 計算所有「應該存在」的連結 (Expected Links)
    # 格式: {agent_home: set([partner_link_name, ...])}
    expected_links = {name: set() for name in agent_names}
    
    if groups:
        for group in groups:
            members = group.get('members', [])
            valid_members = [m for m in members if m in agent_names]
            
            if len(valid_members) < 2:
                continue
                
            print(f"🔗 處理協作羣組: {group.get('name', 'unnamed')} ({', '.join(valid_members)})")
            
            # 全連接 (Full Mesh)
            for me in valid_members:
                my_home = os.path.join(AGENT_HOME_BASE, me)
                for partner in valid_members:
                    if me == partner:
                        continue
                    
                    # 連結目標與名稱
                    target_real_path = os.path.join(AGENT_HOME_BASE, partner, 'my_shared_space')
                    link_name = f"{partner}_shared_space" # 這裡只存檔名
                    full_link_path = os.path.join(my_home, link_name)
                    
                    # 記錄到預期列表
                    expected_links[me].add(link_name)

                    # 計算相對路徑
                    rel_target = os.path.relpath(target_real_path, my_home)

                    # 刪除舊的軟連結（如果存在）
                    if os.path.islink(full_link_path):
                        try:
                            os.unlink(full_link_path)
                        except OSError as e:
                            print(f"   ⚠️ 刪除舊連結失敗: {e}")

                    # 重新建立軟連結
                    try:
                        os.symlink(rel_target, full_link_path)
                        print(f"   + 建立連結: {me} -> {partner}")
                    except OSError as e:
                        print(f"   ⚠️ 建立連結失敗: {e}")

    # 2. 清理不再協作的舊連結 (Cleanup Stale Links)
    print("🧹 檢查並清理過期協作連結...")
    for agent in agent_names:
        home = os.path.join(AGENT_HOME_BASE, agent)
        if not os.path.exists(home):
            continue
            
        # 掃描該 Agent 家中所有檔案
        for item in os.listdir(home):
            # 只處理以此後綴結尾的軟連結
            if item.endswith("_shared_space"):
                full_path = os.path.join(home, item)
                
                # 檢查是否為軟連結
                if os.path.islink(full_path):
                    # 如果這個連結不在預期列表中，則刪除
                    if item not in expected_links[agent]:
                        try:
                            os.unlink(full_path)
                            print(f"   - 移除過期連結: {agent}/{item}")
                        except OSError as e:
                            print(f"   ⚠️ 移除失敗: {e}")

def apply_manual_templates(agent_name, home_path, engine):
    """檢查是否有手動定義的規範範本，若有則複製"""
    template_file = os.path.join(TEMPLATES_DIR, f"{agent_name}.md")
    engine_doc_name = 'AGENTS.md' if engine.lower() == 'codex' else f"{engine.upper()}.md"
    target_file = os.path.join(home_path, engine_doc_name)
    
    if os.path.exists(template_file):
        print(f"   📄 發現自定義規範: {agent_name}.md -> 複製中")
        shutil.copy2(template_file, target_file)
        return True # 代表已有人工規範
    return False

def deploy_skills(agents):
    """部署 Skills 並實作 Immutable 鎖定"""
    skills_base_dir = os.path.join(BASE_DIR, 'skills')
    if not os.path.exists(skills_base_dir):
        return

    # 先找到主層有哪些壓縮檔
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
        
        # 1. 恢復權限並清空舊的 skills
        if os.path.exists(skillbox_dir):
            subprocess.run(['chmod', '-R', 'u+w', skillbox_dir], check=False)
            # 清空子目錄
            for item in os.listdir(skillbox_dir):
                item_path = os.path.join(skillbox_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                else:
                    try:
                        os.remove(item_path)
                    except: pass
                    
        # 2. 解壓縮需要的 skills
        for skill in agent_skills:
            if skill in available_archives:
                archive_path = available_archives[skill]
                target_dir = os.path.join(skillbox_dir, skill)
                os.makedirs(target_dir, exist_ok=True)
                try:
                    shutil.unpack_archive(archive_path, target_dir)
                    print(f"   📦 {agent_name} 掛載技能: {skill}")
                except Exception as e:
                    print(f"   ❌ {agent_name} 解壓技能 {skill} 失敗: {e}")
                    
        # 3. 鎖定唯讀權限 (移除所有人的寫入權限，保留讀取與執行權限)
        if os.path.exists(skillbox_dir) and os.listdir(skillbox_dir):
            subprocess.run(['chmod', '-R', 'a-w,a+rX', skillbox_dir], check=False)
            print(f"   🔒 {agent_name} 的 skillbox 已鎖定唯讀權限")

def main():
    print("🧬  正在初始化 Agent 生態環境...")
    config = load_config()
    agents = config.get('agents', [])
    groups = config.get('collaboration_groups', [])
    
    # 1. 建立目錄
    for agent in agents:
        name = agent['name']
        engine = agent['engine']
        # print(f"   🏠 Agent: {name}")
        home = setup_agent_dirs(name)
        
        # 2. 檢查人工範本
        apply_manual_templates(name, home, engine)
        
    # 3. 建立協作連結
    setup_collaboration_links(agents, groups)
    
    # 4. 部署 Skills
    deploy_skills(agents)
    
    # 5. 清理注入殘留鎖
    print("🧹 清理可能殘留的 inject_block.lock 與暫存檔...")
    for agent in agents:
        agent_dir = os.path.join(AGENT_HOME_BASE, agent['name'])
        lock_file = os.path.join(agent_dir, 'octo_cyberbrain', 'inject_block.lock')
        pending_file = os.path.join(agent_dir, 'octo_cyberbrain', 'pending_inject.txt')
        if os.path.exists(lock_file):
            try: os.remove(lock_file)
            except: pass
        if os.path.exists(pending_file):
            try: os.remove(pending_file)
            except: pass

    print("✅ 環境初始化完成")

if __name__ == '__main__':
    main()
