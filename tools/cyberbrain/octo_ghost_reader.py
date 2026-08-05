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
        print("## ⚓ Keyword Tags (Keywords)")
        kws = sorted(data["keywords"]) if sort_keywords else data["keywords"]
        for kw in kws:
            print(f"- {kw}")
        print()

    if data.get("file_paths"):
        print("## 📂 Important File Paths (File Paths)")
        for path in sorted(data["file_paths"]):
            print(f"- {path}")
        print()

    if data.get("semantic_outline"):
        print("## 📝 Semantic Logic Outline (Semantic Outline)")
        for out in data["semantic_outline"]:
            print(f"{out}")
        print()

def read_current():
    data = load_json("octo_cyberbrain/ghost/octo_ghost.json")
    format_markdown(data, "🐙 Current Active Soul (Active Ghost)")

def _parse_range(range_str):
    try:
        start_s, end_s = range_str.split('-')
        start, end = int(start_s), int(end_s)
        if start < 1 or end < start:
            raise ValueError
        return start, end
    except Exception:
        raise ValueError(f"--range format error, expected START-END (e.g. 31-100), got: {range_str}")

def read_snapshot(range_str="1-30"):
    start, end = _parse_range(range_str)

    files = sorted(glob.glob("octo_cyberbrain/ghost/octo_ghost.*.json"))
    # Filter out kw and path files
    files = [f for f in files if "_kw." not in f and "_path." not in f]

    if not files:
        print("⚠️ No snapshots exist yet.")
        return

    # Sorted by recency (the sole automated use case is right after a GHOST
    # reset, using time as a proxy for a topic context that doesn't exist
    # yet): iterate from the newest snapshot backward. Each snapshot's own
    # keywords are already ordered by octo_ghost_updater.py (later position
    # = more recently touched), so within a file we must read in reverse
    # (most-recently-touched first). Only record a keyword's position the
    # FIRST time we see it — that first sighting, given our newest-file-first
    # traversal, is always the globally most recent occurrence; a later
    # (older) mention of the same keyword in an older snapshot must be
    # skipped, not allowed to overwrite the already-established recent
    # position. Stop once we've accumulated `end` items — no need to read
    # older snapshots. file_paths/semantic_outline are taken only from the
    # snapshots actually read; a wider range covers further back in time.
    seen = set()
    newest_first = []   # built directly as newest -> oldest, index 0 = latest
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
        print(f"⚠️ No keywords available in range {range_str} (only {len(newest_first)} total, sorted by recency).")
        return

    result = {"keywords": sliced, "file_paths": list(paths_all), "semantic_outline": outline_all}
    format_markdown(
        result,
        f"🐙 Snapshot Range Soul (Snapshot Range {range_str}) - sorted by recency, read {files_used}/{len(files)} snapshots",
        sort_keywords=False,
    )

def _month_year_hint(pattern):
    available = sorted(glob.glob(pattern))
    names = [os.path.basename(f).split('.')[1] for f in available]
    return ", ".join(names) if names else "(none)"

def read_monthly(month):
    if not month:
        print(f"❌ --level monthly requires --month YYYY-MM. Currently available months: {_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????-??.json')}")
        return

    kw_file = f"octo_cyberbrain/ghost/octo_ghost_kw.{month}.json"
    path_file = f"octo_cyberbrain/ghost/octo_ghost_path.{month}.json"

    if not os.path.exists(kw_file) and not os.path.exists(path_file):
        print(f"⚠️ No monthly consolidated file found for {month}. Currently available months: {_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????-??.json')}")
        return

    aggregated = {"keywords": [], "file_paths": []}
    kw_data = load_json(kw_file)
    if isinstance(kw_data, list): aggregated["keywords"] = kw_data
    elif isinstance(kw_data, dict): aggregated["keywords"] = kw_data.get("keywords", [])

    path_data = load_json(path_file)
    if isinstance(path_data, list): aggregated["file_paths"] = path_data
    elif isinstance(path_data, dict): aggregated["file_paths"] = path_data.get("file_paths", [])

    format_markdown(aggregated, f"🐙 Monthly Aggregate Soul (Monthly) - {month}")

def read_yearly(year):
    if not year:
        print(f"❌ --level yearly requires --year YYYY. Currently available years: {_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????.json')}")
        return

    kw_file = f"octo_cyberbrain/ghost/octo_ghost_kw.{year}.json"
    path_file = f"octo_cyberbrain/ghost/octo_ghost_path.{year}.json"

    if not os.path.exists(kw_file) and not os.path.exists(path_file):
        print(f"⚠️ No yearly consolidated file found for {year}. Currently available years: {_month_year_hint('octo_cyberbrain/ghost/octo_ghost_kw.????.json')}")
        return

    aggregated = {"keywords": [], "file_paths": []}
    kw_data = load_json(kw_file)
    if isinstance(kw_data, list): aggregated["keywords"] = kw_data
    elif isinstance(kw_data, dict): aggregated["keywords"] = kw_data.get("keywords", [])

    path_data = load_json(path_file)
    if isinstance(path_data, list): aggregated["file_paths"] = path_data
    elif isinstance(path_data, dict): aggregated["file_paths"] = path_data.get("file_paths", [])

    format_markdown(aggregated, f"🐙 Yearly Aggregate Soul (Yearly) - {year}")

def main():
    parser = argparse.ArgumentParser(description="Read Cyberbrain Ghost status")
    parser.add_argument("--level", choices=["current", "snapshot", "monthly", "yearly"], default="snapshot", help="Read level (default: snapshot)")
    parser.add_argument("--range", type=str, default="1-30", help="[snapshot only] Keyword range, sorted by recency, 1 = most recent. Format START-END, e.g. 31-100. Default 1-30; page further back (31-100, 101-200...) if no relevant keywords are found.")
    parser.add_argument("--month", type=str, default=None, help="[monthly only] Specify month YYYY-MM, required")
    parser.add_argument("--year", type=str, default=None, help="[yearly only] Specify year YYYY, required")
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
