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

def format_markdown(data, title, sort_keywords=True):
    print(f"# {title}\n")
    if data.get("keywords"):
        print("## ⚓ 關鍵字標籤 (Keywords)")
        # 剝除開頭的 "-"：避免關鍵字（常是自我指涉的 CLI 參數片段，如 "-C"／"--range"）
        # 被 dive_into_the_shell.py 的 argparse 誤判為選項而解析失敗。子字串比對的
        # 特性保證剝除後比對命中只會持平或變多，不會漏收。
        kws = [kw.lstrip("-") for kw in data["keywords"]]
        kws = sorted(kws) if sort_keywords else kws
        for kw in kws:
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

def _parse_range(range_str):
    try:
        start_s, end_s = range_str.split('-')
        start, end = int(start_s), int(end_s)
        if start < 1 or end < start:
            raise ValueError
        return start, end
    except Exception:
        raise ValueError(f"--range 格式錯誤，應為 START-END（例如 31-100），收到: {range_str}")

def read_snapshot(range_str="1-30"):
    start, end = _parse_range(range_str)

    files = sorted(glob.glob("octo_cyberbrain/ghost/octo_ghost.*.json"))
    # Filter out kw and path files
    files = [f for f in files if "_kw." not in f and "_path." not in f]

    if not files:
        print("⚠️ 尚未有任何快照 (Snapshot) 存在。")
        return

    # 依新鮮度排序（GHOST 重置的專屬語意權重）：從最新快照往回疊代，每份
    # 快照內部的 keywords 已因 octo_ghost_updater.py 保序（越後面代表越晚
    # 觸及），所以在檔案內部要反過來讀（最晚觸及的優先）。只在第一次見到
    # 某個關鍵字時記錄它的位置——第一次一定是在目前檔案疊代順序下「最新」
    # 的那次觸及，之後在更舊的快照裡重複看到同一個關鍵字要略過，不能因為
    # 舊快照也提過就覆蓋掉已經確立的新鮮位置。累積到 end 個就停止，不需要
    # 讀更舊的快照。file_paths／semantic_outline 只取自實際讀到的這些快照，
    # 範圍越大涵蓋越久遠。
    seen = set()
    newest_first = []   # 直接建成「新 -> 舊」，index 0 = 最新
    paths_all = set()
    outline_all = []
    files_used = 0
    for f in reversed(files):
        data = load_json(f)
        for kw in reversed(data.get("keywords", [])):
            if kw not in seen:
                seen.add(kw)
                newest_first.append(kw)
        paths_all.update(data.get("file_paths", []))
        outline_all = data.get("semantic_outline", []) + outline_all
        files_used += 1
        if len(newest_first) >= end:
            break

    sliced = newest_first[start - 1:end]

    if not sliced:
        print(f"⚠️ 範圍 {range_str} 沒有可用的關鍵字（依新鮮度排序總共只有 {len(newest_first)} 個）。")
        return

    result = {"keywords": sliced, "file_paths": list(paths_all), "semantic_outline": outline_all}
    format_markdown(
        result,
        f"🐙 快照範圍靈魂 (Snapshot Range {range_str}) - 依新鮮度排序，已讀取 {files_used}/{len(files)} 份快照",
        sort_keywords=False,
    )

def _month_year_hint(pattern):
    available = sorted(glob.glob(pattern))
    names = [os.path.basename(f).split('.')[1] for f in available]
    return "、".join(names) if names else "（無）"

def read_monthly(month):
    if not month:
        print(f"❌ --level monthly 需要指定 --month YYYY-MM。目前可用月份：{_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????-??.json')}")
        return

    kw_file = f"octo_cyberbrain/ghost/octo_ghost_kw.{month}.json"
    path_file = f"octo_cyberbrain/ghost/octo_ghost_path.{month}.json"

    if not os.path.exists(kw_file) and not os.path.exists(path_file):
        print(f"⚠️ 找不到 {month} 的月度歸併檔。目前可用月份：{_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????-??.json')}")
        return

    aggregated = {"keywords": [], "file_paths": []}
    kw_data = load_json(kw_file)
    if isinstance(kw_data, list): aggregated["keywords"] = kw_data
    elif isinstance(kw_data, dict): aggregated["keywords"] = kw_data.get("keywords", [])

    path_data = load_json(path_file)
    if isinstance(path_data, list): aggregated["file_paths"] = path_data
    elif isinstance(path_data, dict): aggregated["file_paths"] = path_data.get("file_paths", [])

    format_markdown(aggregated, f"🐙 月度歸併靈魂 (Monthly) - {month}")

def read_yearly(year):
    if not year:
        print(f"❌ --level yearly 需要指定 --year YYYY。目前可用年份：{_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????.json')}")
        return

    kw_file = f"octo_cyberbrain/ghost/octo_ghost_kw.{year}.json"
    path_file = f"octo_cyberbrain/ghost/octo_ghost_path.{year}.json"

    if not os.path.exists(kw_file) and not os.path.exists(path_file):
        print(f"⚠️ 找不到 {year} 的年度歸併檔。目前可用年份：{_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????.json')}")
        return

    aggregated = {"keywords": [], "file_paths": []}
    kw_data = load_json(kw_file)
    if isinstance(kw_data, list): aggregated["keywords"] = kw_data
    elif isinstance(kw_data, dict): aggregated["keywords"] = kw_data.get("keywords", [])

    path_data = load_json(path_file)
    if isinstance(path_data, list): aggregated["file_paths"] = path_data
    elif isinstance(path_data, dict): aggregated["file_paths"] = path_data.get("file_paths", [])

    format_markdown(aggregated, f"🐙 年度歸併靈魂 (Yearly) - {year}")

def main():
    parser = argparse.ArgumentParser(description="讀取電子腦 Ghost 狀態")
    parser.add_argument("--level", choices=["current", "snapshot", "monthly", "yearly"], default="snapshot", help="讀取層級 (預設: snapshot)")
    parser.add_argument("--range", type=str, default="1-30", help="[snapshot 專用] 關鍵字範圍，依新鮮度排序，1 為最新。格式 START-END，例如 31-100。預設 1-30，找不到相關關鍵字時可自行往回翻頁（31-100、101-200...）。")
    parser.add_argument("--month", type=str, default=None, help="[monthly 專用] 指定月份 YYYY-MM，必填")
    parser.add_argument("--year", type=str, default=None, help="[yearly 專用] 指定年份 YYYY，必填")
    args = parser.parse_args()

    if args.level == "current":
        read_current()
    elif args.level == "snapshot":
        read_snapshot(args.range)
    elif args.level == "monthly":
        read_monthly(args.month)
    elif args.level == "yearly":
        read_yearly(args.year)

if __name__ == "__main__":
    main()
