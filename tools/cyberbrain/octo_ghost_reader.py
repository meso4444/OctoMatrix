#!/usr/bin/env python3
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
        print("## ⚓ Keyword Tags (Keywords)")
        for kw in sorted(data["keywords"]):
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

def read_snapshot():
    files = sorted(glob.glob("octo_cyberbrain/ghost/octo_ghost.*.json"))
    # Filter out kw and path files
    files = [f for f in files if "_kw." not in f and "_path." not in f]
    
    if not files:
        print("⚠️ No snapshots exist yet.")
        return

    aggregated = {"keywords": set(), "file_paths": set(), "semantic_outline": []}
    for f in files:
        data = load_json(f)
        aggregated["keywords"].update(data.get("keywords", []))
        aggregated["file_paths"].update(data.get("file_paths", []))
        aggregated["semantic_outline"].extend(data.get("semantic_outline", []))

    aggregated["keywords"] = list(aggregated["keywords"])
    aggregated["file_paths"] = list(aggregated["file_paths"])

    format_markdown(aggregated, f"🐙 Snapshot Aggregate Soul (Snapshot Aggregate) - Contains {len(files)} snapshots")

def read_monthly(months):
    # Monthly filename format is octo_ghost_kw.YYYY-MM.json, filter out yearly files YYYY.json
    kw_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_kw.????-??.json")])[-months:]
    path_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_path.????-??.json")])[-months:]

    if not kw_files and not path_files:
        print("⚠️ No monthly consolidated files exist yet.")
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

    format_markdown(aggregated, f"🐙 Monthly Aggregate Soul (Monthly Aggregate) - Covers last {len(kw_files)} months")

def read_yearly(years):
    # Yearly filename format is octo_ghost_kw.YYYY.json
    kw_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_kw.????.json")])[-years:]
    path_files = sorted([f for f in glob.glob("octo_cyberbrain/ghost/octo_ghost_path.????.json")])[-years:]

    if not kw_files and not path_files:
        print("⚠️ No yearly consolidated files exist yet.")
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

    format_markdown(aggregated, f"🐙 Yearly Aggregate Soul (Yearly Aggregate) - Covers last {len(kw_files)} years")

def main():
    parser = argparse.ArgumentParser(description="Read Cyberbrain Ghost status")
    parser.add_argument("--level", choices=["current", "snapshot", "monthly", "yearly"], default="snapshot", help="Read level (default: snapshot)")
    parser.add_argument("--months", type=int, default=3, help="Read past N months (for monthly)")
    parser.add_argument("--years", type=int, default=1, help="Read past N years (for yearly)")
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
