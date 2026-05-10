#!/usr/bin/env python3
# setup_agent_env.py
# Responsible for initializing Agent home directory structure and collaboration links

import os
import sys
import yaml
import shutil
import subprocess

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.yaml')
AGENT_HOME_BASE = os.path.join(BASE_DIR, 'agent_home')
TEMPLATES_DIR = BASE_DIR

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Error: Configuration file not found {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def setup_agent_dirs(agent_name):
    """Create directory structure for a single Agent"""
    home = os.path.join(AGENT_HOME_BASE, agent_name)
    subdirs = ['toolbox', 'knowledge', 'my_shared_space', 'downloads_temp']

    for d in subdirs:
        path = os.path.join(home, d)
        if not os.path.exists(path):
            os.makedirs(path)
            # print(f"   + Create directory: {d}")

    return home

def setup_collaboration_links(agents, groups):
    """Create symlinks for collaboration groups and clean up stale links"""
    agent_names = [a['name'] for a in agents]

    # 1. Calculate all "should exist" links (Expected Links)
    # Format: {agent_home: set([partner_link_name, ...])}
    expected_links = {name: set() for name in agent_names}

    if groups:
        for group in groups:
            members = group.get('members', [])
            valid_members = [m for m in members if m in agent_names]

            if len(valid_members) < 2:
                continue

            print(f"🔗 Processing collaboration group: {group.get('name', 'unnamed')} ({', '.join(valid_members)})")

            # Full mesh
            for me in valid_members:
                my_home = os.path.join(AGENT_HOME_BASE, me)
                for partner in valid_members:
                    if me == partner:
                        continue

                    # Link target and name
                    target_real_path = os.path.join(AGENT_HOME_BASE, partner, 'my_shared_space')
                    link_name = f"{partner}_shared_space" # Store filename only here
                    full_link_path = os.path.join(my_home, link_name)

                    # Record to expected list
                    expected_links[me].add(link_name)

                    # Calculate relative path
                    rel_target = os.path.relpath(target_real_path, my_home)

                    # Delete old symlink if exists
                    if os.path.islink(full_link_path):
                        try:
                            os.unlink(full_link_path)
                        except OSError as e:
                            print(f"   ⚠️ Failed to delete old link: {e}")

                    # Recreate symlink
                    try:
                        os.symlink(rel_target, full_link_path)
                        print(f"   + Create link: {me} -> {partner}")
                    except OSError as e:
                        print(f"   ⚠️ Failed to create link: {e}")

    # 2. Clean up stale links (Cleanup Stale Links)
    print("🧹 Checking and cleaning up stale collaboration links...")
    for agent in agent_names:
        home = os.path.join(AGENT_HOME_BASE, agent)
        if not os.path.exists(home):
            continue

        # Scan all files in Agent home
        for item in os.listdir(home):
            # Only process symlinks with this suffix
            if item.endswith("_shared_space"):
                full_path = os.path.join(home, item)

                # Check if it's a symlink
                if os.path.islink(full_path):
                    # Delete if this link is not in expected list
                    if item not in expected_links[agent]:
                        try:
                            os.unlink(full_path)
                            print(f"   - Remove stale link: {agent}/{item}")
                        except OSError as e:
                            print(f"   ⚠️ Failed to remove: {e}")

def apply_manual_templates(agent_name, home_path, engine):
    """Check if there is a manually defined specification template and copy if exists"""
    template_file = os.path.join(TEMPLATES_DIR, f"{agent_name}.md")
    engine_doc_name = 'AGENTS.md' if engine.lower() == 'codex' else f"{engine.upper()}.md"
    target_file = os.path.join(home_path, engine_doc_name)

    if os.path.exists(template_file):
        print(f"   📄 Found custom specification: {agent_name}.md -> copying")
        shutil.copy2(template_file, target_file)
        return True # Indicates manual specification exists
    return False

def deploy_skills(agents):
    """Deploy Skills and implement Immutable locking"""
    skills_base_dir = os.path.join(BASE_DIR, 'skills')
    if not os.path.exists(skills_base_dir):
        return

    # First find which archive files exist in the root directory
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

        # 2. Extract needed skills
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

        # 3. Lock with read-only permissions (remove write permission for all, keep read and execute)
        if os.path.exists(skillbox_dir) and os.listdir(skillbox_dir):
            subprocess.run(['chmod', '-R', 'a-w,a+rX', skillbox_dir], check=False)
            print(f"   🔒 {agent_name}'s skillbox has been locked to read-only")

def main():
    print("🧬  Initializing Agent ecosystem...")
    config = load_config()
    agents = config.get('agents', [])
    groups = config.get('collaboration_groups', [])

    # 1. Create directories
    for agent in agents:
        name = agent['name']
        engine = agent['engine']
        # print(f"   🏠 Agent: {name}")
        home = setup_agent_dirs(name)

        # 2. Check manual templates
        apply_manual_templates(name, home, engine)

    # 3. Setup collaboration links
    setup_collaboration_links(agents, groups)

    # 4. Deploy Skills
    deploy_skills(agents)

    print("✅ Environment initialization completed")

if __name__ == '__main__':
    main()
