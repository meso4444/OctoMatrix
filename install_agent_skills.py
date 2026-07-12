#!/usr/bin/env python3
# Copyright 2026 meso4444

import os
import sys
import hashlib
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, 'skills')
AGENT_HOME_BASE = os.path.join(BASE_DIR, 'agent_home')
CACHE_DIR = os.path.join(SKILLS_DIR, '.global_skills_cache')

def get_os_branch():
    if sys.platform == 'darwin': return 'macos'
    if os.path.exists('/etc/os-release'):
        with open('/etc/os-release') as f:
            content = f.read().lower()
            if 'ubuntu' in content or 'debian' in content: return 'ubuntu'
            if 'centos' in content or 'rhel' in content or 'redhat' in content: return 'centos'
            if 'arch' in content: return 'arch'
            if 'alpine' in content: return 'alpine'
    return 'unknown'

def compute_hash(filepath):
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def main():
    if not os.path.exists(SKILLS_DIR):
        print(f"Skills directory not found at {SKILLS_DIR}")
        sys.exit(0)
    
    os.makedirs(CACHE_DIR, exist_ok=True)
    subprocess.run(['chmod', '755', CACHE_DIR], check=False)
    
    octo_os = get_os_branch()
    print(f"📦 Starting Global Skill Cache Build (Detected OS: {octo_os})")

    for item in os.listdir(SKILLS_DIR):
        if not (item.endswith('.tar.gz') or item.endswith('.zip')):
            continue
            
        skill_name = item[:-7] if item.endswith('.tar.gz') else item[:-4]
        archive_path = os.path.join(SKILLS_DIR, item)
        skill_cache_dir = os.path.join(CACHE_DIR, skill_name)
        hash_file = os.path.join(skill_cache_dir, '.skill_hash')
        
        current_hash = compute_hash(archive_path)
        
        if os.path.exists(skill_cache_dir):
            if os.path.exists(hash_file):
                with open(hash_file, 'r') as f:
                    old_hash = f.read().strip()
                if old_hash == current_hash:
                    print(f"   ✓ {skill_name} is up to date.")
                    continue
            print(f"   🔄 Updating {skill_name}...")
            subprocess.run(['chmod', '-R', 'u+w', skill_cache_dir], check=False, stderr=subprocess.DEVNULL)
            shutil.rmtree(skill_cache_dir, ignore_errors=True)
        else:
            print(f"   ✨ Installing {skill_name}...")

        os.makedirs(skill_cache_dir, exist_ok=True)
        try:
            shutil.unpack_archive(archive_path, skill_cache_dir)
        except Exception as e:
            print(f"   ❌ Failed to unpack {skill_name}: {e}")
            continue

        setup_script = os.path.join(skill_cache_dir, 'setup.sh')
        if os.path.exists(setup_script):
            print(f"   ⚙️ Running setup.sh for {skill_name}...")
            subprocess.run(['chmod', '-R', '777', skill_cache_dir], check=False)
            env = os.environ.copy()
            env['OCTO_OS'] = octo_os
            result = subprocess.run(['bash', 'setup.sh'], cwd=skill_cache_dir, env=env)
            if result.returncode != 0:
                print(f"   ⚠️ setup.sh for {skill_name} returned non-zero exit code.")
        
        with open(hash_file, 'w') as f:
            f.write(current_hash)
            
        subprocess.run(['chmod', '-R', '755', skill_cache_dir], check=False)

    print("✅ Global Skill Build Complete.")

    # Deploy to all agents unconditionally
    print("🌍 Deploying skills to all agents...")
    agent_home_dir = os.path.join(BASE_DIR, 'agent_home')
    if os.path.exists(agent_home_dir):
        for agent_name in os.listdir(agent_home_dir):
            if agent_name.startswith('.'): continue
            
            skillbox_dir = os.path.join(agent_home_dir, agent_name, 'skillbox')
            if not os.path.exists(skillbox_dir):
                continue
                
            subprocess.run(['chmod', '-R', 'u+w', skillbox_dir], check=False, stderr=subprocess.DEVNULL)
            
            for item in os.listdir(skillbox_dir):
                item_path = os.path.join(skillbox_dir, item)
                if os.path.islink(item_path) or os.path.isfile(item_path):
                    try: os.remove(item_path)
                    except: pass
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                    
            if os.path.exists(CACHE_DIR):
                for skill in os.listdir(CACHE_DIR):
                    target_cache_path = os.path.join(CACHE_DIR, skill)
                    if os.path.isdir(target_cache_path):
                        link_path = os.path.join(skillbox_dir, skill)
                        rel_target = os.path.relpath(target_cache_path, skillbox_dir)
                        try:
                            os.symlink(rel_target, link_path)
                        except Exception:
                            pass
            
            subprocess.run(['chmod', 'a-w', skillbox_dir], check=False, stderr=subprocess.DEVNULL)
            print(f"   🔗 Mounted all global skills for {agent_name} and locked skillbox.")

    print("✅ Full execution complete.")


if __name__ == '__main__':
    main()
