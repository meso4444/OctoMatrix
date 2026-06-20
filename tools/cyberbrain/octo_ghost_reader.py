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
import glob
import argparse
from datetime import datetime

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"keywords": [], "file_paths": [], "semantic_outline": []}

def format_markdown(data, title):
    print(f"# {title}\n")
    if data.get("keywords"):
        print("## ⚓ 關鍵字標籤 (Keywords)")
        for kw in sorted(data["keywords"]):
            print(f"- {kw}")
        print()
        
    if data.get("file_paths"):
        print("## 📂 重要檔案路徑 (File Paths)")
        for path in sorted(data["file_paths"]):
            print(f"- {path}")
        print()
        
    if data.get("semantic_outline"):
        print("## 📝 語義邏輯大綱 (Semantic Outline)")
        for out in data["semantic_outline"]:
            print(f"{out}")
        print()

def read_current():
    data = load_json("octo_cyberbrain/ghost/octo_ghost.json")
    format_markdown(data, "🐙 當前活動靈魂 (Active Ghost)")

def read_snapshot():
    files = sorted(glob.glob("octo_cyberbrain/ghost/octo_ghost.*.json"))
    # Filter out kw and path files
    files = [f for f in files if "_kw." not in f and "_path." not in f]
    
    if not files:
        print("⚠️ 尚未有任何快照 (Snapshot) 存在。")
        return
        
    aggregated = {"keywords": set(), "file_paths": set(), "semantic_outline": []}
    for f in files:
        data = load_json(f)
        aggregated["keywords"].update(data.get("keywords", []))
        aggregated["file_paths"].update(data.get("file_paths", []))
        aggregated["semantic_outline"].extend(data.get("semantic_outline", []))
        
    aggregated["keywords"] = list(aggregated["keywords"])
    aggregated["file_paths"] = list(aggregated["file_paths"])
    
    format_markdown(aggregated, f"🐙 快照聚合靈魂 (Snapshot Aggregate) - 包含 {len(files)} 份快照")

def read_monthly(months):
    # 月度檔名格式為 octo_ghost_kw.YYYY-MM.json，過濾掉年度檔 YYYY.json
    kw_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_kw.????-??.json")])[-months:]
    path_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_path.????-??.json")])[-months:]
    
    if not kw_files and not path_files:
        print("⚠️ 尚未有任何月度歸併檔存在。")
        return
        
    aggregated = {"keywords": set(), "file_paths": set(), "semantic_outline": []}
    for f in kw_files:
        data = load_json(f)
        if isinstance(data, list): aggregated["keywords"].update(data)
        elif isinstance(data, dict): aggregated["keywords"].update(data.get("keywords", []))
            
    for f in path_files:
        data = load_json(f)
        if isinstance(data, list): aggregated["file_paths"].update(data)
        elif isinstance(data, dict): aggregated["file_paths"].update(data.get("file_paths", []))
            
    aggregated["keywords"] = list(aggregated["keywords"])
    aggregated["file_paths"] = list(aggregated["file_paths"])
    
    format_markdown(aggregated, f"🐙 月度聚合靈魂 (Monthly Aggregate) - 涵蓋近 {len(kw_files)} 個月")

def read_yearly(years):
    # 年度檔名格式為 octo_ghost_kw.YYYY.json
    kw_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_kw.????.json")])[-years:]
    path_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_path.????.json")])[-years:]
    
    if not kw_files and not path_files:
        print("⚠️ 尚未有任何年度歸併檔存在。")
        return
        
    aggregated = {"keywords": set(), "file_paths": set(), "semantic_outline": []}
    for f in kw_files:
        data = load_json(f)
        if isinstance(data, list): aggregated["keywords"].update(data)
        elif isinstance(data, dict): aggregated["keywords"].update(data.get("keywords", []))
            
    for f in path_files:
        data = load_json(f)
        if isinstance(data, list): aggregated["file_paths"].update(data)
        elif isinstance(data, dict): aggregated["file_paths"].update(data.get("file_paths", []))
            
    aggregated["keywords"] = list(aggregated["keywords"])
    aggregated["file_paths"] = list(aggregated["file_paths"])
    
    format_markdown(aggregated, f"🐙 年度聚合靈魂 (Yearly Aggregate) - 涵蓋近 {len(kw_files)} 年")

def main():
    parser = argparse.ArgumentParser(description="讀取電子腦 Ghost 狀態")
    parser.add_argument("--level", choices=["current", "snapshot", "monthly", "yearly"], default="snapshot", help="讀取層級 (預設: snapshot)")
    parser.add_argument("--months", type=int, default=3, help="讀取過去幾個月 (針對 monthly)")
    parser.add_argument("--years", type=int, default=1, help="讀取過去幾年 (針對 yearly)")
    args = parser.parse_args()

    if args.level == "current":
        read_current()
    elif args.level == "snapshot":
        read_snapshot()
    elif args.level == "monthly":
        read_monthly(args.months)
    elif args.level == "yearly":
        read_yearly(args.years)

if __name__ == "__main__":
    main()
