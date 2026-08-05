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

import os
import sys
import json
import subprocess
import argparse

# [Positioning reinforcement] Ensure script can locate correct Agent Home
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_HOME = os.path.dirname(SCRIPT_DIR)
GHOST_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/ghost/octo_ghost.json")
FLAG_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/.rotation_flag")
ROTATE_SCRIPT = os.path.join(AGENT_HOME, "octo_cyberbrain/internal_matrix_rotate.py")

def load_ghost():
    # [Structure protection] Detect non-standard paths and issue warning
    rogue_brain = os.path.join(AGENT_HOME, "octo_cyberbrain/brain")
    if os.path.exists(rogue_brain):
        print("⚠️ [Structure warning] Non-standard directory octo_cyberbrain/brain/ detected!")
        print("⚠️ Please immediately stop using that directory and migrate data to standard ghost directory.")
        
    if os.path.exists(GHOST_FILE):
        try:
            with open(GHOST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"keywords": [], "file_paths": [], "semantic_outline": []}

def save_ghost(data):
    os.makedirs(os.path.dirname(GHOST_FILE), exist_ok=True)
    with open(GHOST_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    parser = argparse.ArgumentParser(description="🐙 Ghost semantic state update program")
    parser.add_argument("--outline", help="Semantic logic outline content")
    parser.add_argument("--keywords", help="Keyword tags (comma-separated)")
    parser.add_argument("--paths", help="Important file absolute paths (comma-separated)")
    args = parser.parse_args()

    outline_lines = []
    kw_input = ""
    path_input = ""

    # Determine if CLI mode
    is_cli_mode = any([args.outline, args.keywords, args.paths])

    if is_cli_mode:
        print("🚀 [CLI mode] Auto-injecting semantic state...")
        if args.outline: outline_lines = [args.outline]
        kw_input = args.keywords or ""
        path_input = args.paths or ""
    else:
        print("🐙 [Interactive mode] Starting Ghost semantic update program...")
        # Step 1: Semantic Outline
        print("📝 Step 1: Please input semantic logic outline (detailed decisions, task records, input 'EOF' or two empty lines to end):")
        empty_count = 0
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip().upper() == 'EOF':
                break
            if not line.strip():
                empty_count += 1
                if empty_count >= 2:
                    break
            else:
                empty_count = 0
            outline_lines.append(line)

        # Step 2: Literal Keywords
        print("📌 Step 2: Extract 'real keywords' from above outline (core principle: no translation, no interpretation, keep original form)")
        try:
            kw_input = input("   Please input keyword tags (comma-separated, leave empty to skip): ").strip()
        except EOFError: pass

        # Step 3: File Paths
        print("📂 Step 3: Please input important file absolute paths modified or referenced in this session")
        try:
            path_input = input("   Please input file paths (comma-separated, leave empty to skip): ").strip()
        except EOFError: pass

    ghost_data = load_ghost()

    # 1. Outline processing
    if outline_lines:
        outline_text = "\n".join(outline_lines).strip()
        if outline_text:
            ghost_data.setdefault("semantic_outline", []).append(outline_text)

    # 2. Keywords processing
    # Replace unordered set with an order-preserving structure: later position
    # means more recently touched, used by read_snapshot()'s --range pagination
    # to sort by recency.
    if kw_input:
        new_kws = [k.strip() for k in kw_input.split(',') if k.strip()]
        kw_dict = dict.fromkeys(ghost_data.get("keywords", []))
        for k in new_kws:
            kw_dict.pop(k, None)   # if already present, drop old position
            kw_dict[k] = None      # reinsert at the end = mark as most recent
        ghost_data["keywords"] = list(kw_dict)

    # 3. File paths processing
    if path_input:
        new_paths = [p.strip() for p in path_input.split(',') if p.strip()]
        path_set = set(ghost_data.get("file_paths", []))
        path_set.update(new_paths)
        ghost_data["file_paths"] = list(path_set)

    save_ghost(ghost_data)
    print("✅ Ghost update completed!")

    if os.path.exists(FLAG_FILE) and os.path.getsize(FLAG_FILE) == 0:
        print("⚡ New rotation request detected, preparing to hand over to Reaper for background reset...")
        with open(FLAG_FILE, 'w') as f:
            f.write("READY_FOR_REAPER")

if __name__ == "__main__":
    main()