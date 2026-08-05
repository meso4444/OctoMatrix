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

# 【定位加固】確保腳本能定位到正確的 Agent Home
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_HOME = os.path.dirname(SCRIPT_DIR)
GHOST_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/ghost/octo_ghost.json")
FLAG_FILE = os.path.join(AGENT_HOME, "octo_cyberbrain/.rotation_flag")
ROTATE_SCRIPT = os.path.join(AGENT_HOME, "octo_cyberbrain/internal_matrix_rotate.py")

def load_ghost():
    # 【結構守護】偵測非標準路徑並提出警告
    rogue_brain = os.path.join(AGENT_HOME, "octo_cyberbrain/brain")
    if os.path.exists(rogue_brain):
        print("⚠️ [結構警告] 偵測到非標準目錄 octo_cyberbrain/brain/！")
        print("⚠️ 請立即停止使用該目錄，並將數據遷移至標準 ghost 目錄。")
        
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
    parser = argparse.ArgumentParser(description="🐙 Ghost 語義狀態更新程序")
    parser.add_argument("--outline", help="語義邏輯大綱內容")
    parser.add_argument("--keywords", help="關鍵字標籤 (以逗號分隔)")
    parser.add_argument("--paths", help="重要檔案絕對路徑 (以逗號分隔)")
    args = parser.parse_args()

    outline_lines = []
    kw_input = ""
    path_input = ""

    # 判斷是否為參數模式
    is_cli_mode = any([args.outline, args.keywords, args.paths])

    if is_cli_mode:
        print("🚀 [CLI 模式] 正在自動注入語義狀態...")
        if args.outline: outline_lines = [args.outline]
        kw_input = args.keywords or ""
        path_input = args.paths or ""
    else:
        print("🐙 [互動模式] 啟動 Ghost 語義更新程序...")
        # Step 1: Semantic Outline
        print("📝 Step 1: 請輸入語義邏輯大綱 (詳細決策、任務紀錄，輸入 'EOF' 或空行連續兩次結束):")
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
        print("📌 Step 2: 請從上述大綱中萃取「真實關鍵字」(核心原則：禁止轉譯、禁止解釋、保持原始字樣)")
        try:
            kw_input = input("   請輸入關鍵字標籤 (以逗號分隔，留空跳過): ").strip()
        except EOFError: pass
        
        # Step 3: File Paths
        print("📂 Step 3: 請輸入本次修改或參考的重要檔案絕對路徑")
        try:
            path_input = input("   請輸入檔案路徑 (以逗號分隔，留空跳過): ").strip()
        except EOFError: pass
    
    ghost_data = load_ghost()
    
    # 1. 處理大綱 (Outline Processing)
    if outline_lines:
        outline_text = "\n".join(outline_lines).strip()
        if outline_text:
            ghost_data.setdefault("semantic_outline", []).append(outline_text)

    # 2. 處理關鍵字 (Keywords Processing)
    # 用保留「最後觸及順序」的結構取代無序 set：越後面代表越晚被觸及，
    # 供 read_snapshot() 的 --range 分頁機制依新鮮度排序使用。
    if kw_input:
        new_kws = [k.strip() for k in kw_input.split(',') if k.strip()]
        kw_dict = dict.fromkeys(ghost_data.get("keywords", []))
        for k in new_kws:
            kw_dict.pop(k, None)   # 若已存在，先移除舊位置
            kw_dict[k] = None      # 重新插入到最後 = 標記為最新
        ghost_data["keywords"] = list(kw_dict)
        
    # 3. 處理檔案路徑 (File Paths Processing)
    if path_input:
        new_paths = [p.strip() for p in path_input.split(',') if p.strip()]
        path_set = set(ghost_data.get("file_paths", []))
        path_set.update(new_paths)
        ghost_data["file_paths"] = list(path_set)
            
    save_ghost(ghost_data)
    print("✅ Ghost 更新完成！")
    
    if os.path.exists(FLAG_FILE) and os.path.getsize(FLAG_FILE) == 0:
        print("⚡ 偵測到新的 Rotation 請求，準備移交給 Reaper 進行背景重置...")
        with open(FLAG_FILE, 'w') as f:
            f.write("READY_FOR_REAPER")

if __name__ == "__main__":
    main()