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
import glob
import argparse
import subprocess
import re

def main():
    parser = argparse.ArgumentParser(description="深潛檢索工具 (Dive into the Shell)")
    parser.add_argument("--level", choices=["current", "snapshot", "monthly", "yearly"], default="snapshot", help="檢索層級")
    parser.add_argument("-C", "--context", type=int, default=50, help="前後文行數 (預設: 50)")
    parser.add_argument("--keyword", nargs='+', required=True, help="檢索關鍵字 (支援多個，將取聯集)")
    parser.add_argument("--offset", type=int, default=0, help="跳過最後的行數，用於分頁追溯更深層 GHOST (預設: 0)")
    args = parser.parse_args()

    LIMIT = 1000

    # Determine files to search
    if args.level == "current":
        files = ["octo_cyberbrain/shell/octo_shell.log"]
    elif args.level == "snapshot":
        files = sorted(glob.glob("octo_cyberbrain/shell/octo_shell.log.*.zst"))
        # Filter out monthly/yearly
        files = [f for f in files if len(os.path.basename(f).split('.')) > 3 and '-' in os.path.basename(f)]
    elif args.level == "monthly":
        files = sorted(glob.glob("octo_cyberbrain/shell/octo_shell.log.????-??.zst"))
    else:
        files = sorted(glob.glob("octo_cyberbrain/shell/octo_shell.log.????.zst"))
        
    existing_files = [f for f in files if os.path.exists(f)]
    
    if not existing_files:
        print(f"⚠️ 在 {args.level} 層級尚未有可檢索的殼 (Shell) 存在。")
        return

    # Build zstdgrep command
    pattern = "|".join([re.escape(kw) for kw in args.keyword])
    cmd = ["zstdgrep", f"-C{args.context}", "-E", pattern]
    cmd.extend(existing_files)
    
    print(f"🌊 深潛入殼 (Diving into the Shell) - 層級: {args.level}, 目標檔數: {len(existing_files)}, 關鍵字: {args.keyword}")
    
    # 執行內容讀取 (最新優先 + Offset 分頁)
    try:
        p_grep = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        
        # 核心分頁邏輯 (僅保留 tail 模式): tail -n {LIMIT + offset} | head -n {LIMIT}
        p_slice = subprocess.Popen(["tail", "-n", str(LIMIT + args.offset)], stdin=p_grep.stdout, stdout=subprocess.PIPE, text=True)
        p_final = subprocess.Popen(["head", "-n", str(LIMIT)], stdin=p_slice.stdout, stdout=subprocess.PIPE, text=True)
        
        p_grep.stdout.close()
        p_slice.stdout.close()
        
        output, _ = p_final.communicate()
        
        if not output.strip():
            print("🕳️ 無匹配結果 (或分頁已超出範圍).")
        else:
            print(f"📖 正在讀取「最新」的第 {args.offset + 1} 至 {args.offset + LIMIT} 行紀錄：\n")
            print(output)
            print(f"\n💡 [導航提示] 若需繼續挖掘更深歷史，請在指令中增加 `--offset {args.offset + LIMIT}`。")
            
    except Exception as e:
        print(f"❌ 檢索失敗: {e}")

if __name__ == "__main__":
    main()
