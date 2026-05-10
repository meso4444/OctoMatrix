#!/usr/bin/env python3
"""
動態解析註冊技能的依賴項
Extracts requirements.txt and generates prebuild scripts based on registered skills.
"""
import sys
import os
import yaml
import tarfile
import zipfile

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_skill_deps.py <instance_name>")
        sys.exit(1)
        
    instance = sys.argv[1]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, f"config.{instance}.yaml")
    req_out = os.path.join(script_dir, f"dynamic_requirements.{instance}.txt")
    script_out = os.path.join(script_dir, f"dynamic_prebuild.{instance}.sh")
    
    if not os.path.exists(config_file):
        print(f"⚠️ Config not found: {config_file}")
        return

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    agents = config.get('agents', [])
    used_skills = set()
    for agent in agents:
        for skill in agent.get('skills', []):
            used_skills.add(skill)
            
    requirements = set()
    prebuild_steps = []
    
    skills_dir = os.path.abspath(os.path.join(script_dir, "../skills"))
    
    for skill in used_skills:
        archive_path = None
        is_tar = False
        
        tar_path = os.path.join(skills_dir, f"{skill}.tar.gz")
        zip_path = os.path.join(skills_dir, f"{skill}.zip")
        
        if os.path.exists(tar_path):
            archive_path = tar_path
            is_tar = True
        elif os.path.exists(zip_path):
            archive_path = zip_path
            is_tar = False
            
        if not archive_path:
            print(f"⚠️ 找不到技能包: {skill}")
            continue
            
        # Extract requirements.txt
        if is_tar:
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("requirements.txt"):
                        f = tar.extractfile(member)
                        if f:
                            reqs = f.read().decode('utf-8').splitlines()
                            for r in reqs:
                                r = r.strip()
                                if r and not r.startswith('#'):
                                    requirements.add(r)
        else:
            with zipfile.ZipFile(archive_path, "r") as z:
                for name in z.namelist():
                    if name.endswith("requirements.txt"):
                        with z.open(name) as f:
                            reqs = f.read().decode('utf-8').splitlines()
                            for r in reqs:
                                r = r.strip()
                                if r and not r.startswith('#'):
                                    requirements.add(r)

        # Generate prebuild step (Container paths)
        container_archive = f"/app/octomatrix/skills/{os.path.basename(archive_path)}"
        step = f"""
echo "📦 處理技能包: {container_archive}"
if [ -f "{container_archive}" ]; then
    tmp_dir="/tmp/skill_build_{skill}"
    rm -rf "$tmp_dir" && mkdir -p "$tmp_dir"
"""
        if is_tar:
            step += f'    tar -xzf "{container_archive}" -C "$tmp_dir"\n'
        else:
            step += f'    unzip -q "{container_archive}" -d "$tmp_dir"\n'
            
        step += f"""
    setup_script=$(find "$tmp_dir" -name "setup.sh" | head -n 1)
    if [ -n "$setup_script" ]; then
        echo "🚀 執行安裝腳本: $setup_script"
        chmod +x "$setup_script"
        (cd "$(dirname "$setup_script")" && bash setup.sh)
    fi
    echo "📦 重新打包技能包 (包含依賴)..."
"""
        if is_tar:
            step += f'    (cd "$tmp_dir" && tar -czf "{container_archive}" *)\n'
        else:
            step += f'    (cd "$tmp_dir" && zip -rq "{container_archive}" ./*)\n'
            
        step += f"""    rm -rf "$tmp_dir"
fi
"""
        prebuild_steps.append(step)
        
    with open(req_out, 'w', encoding='utf-8') as f:
        for r in sorted(requirements):
            f.write(f"{r}\n")
            
    with open(script_out, 'w', encoding='utf-8') as f:
        f.write("#!/bin/bash\nset -e\n")
        f.write("\n".join(prebuild_steps))

    print(f"✅ 動態解析完成: 發現 {len(used_skills)} 個註冊技能, 提取了 {len(requirements)} 個 Python 依賴項")

if __name__ == '__main__':
    main()