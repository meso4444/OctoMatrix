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
    parser = argparse.ArgumentParser(description="Deep-dive retrieval tool (Dive into the Shell)")
    parser.add_argument("--level", choices=["current", "snapshot", "monthly", "yearly"], default="snapshot", help="Retrieval level")
    parser.add_argument("-C", "--context", type=int, default=50, help="Context lines (default: 50)")
    parser.add_argument("--keyword", nargs='+', required=True, help="Search keywords (supports multiple, will take union)")
    parser.add_argument("--offset", type=int, default=0, help="Skip last N lines for pagination to retrieve deeper GHOST (default: 0)")
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
        print(f"⚠️ No searchable shell at {args.level} level yet.")
        return

    # Build zstdgrep command
    pattern = "|".join([re.escape(kw) for kw in args.keyword])
    cmd = ["zstdgrep", f"-C{args.context}", "-E", pattern]
    cmd.extend(existing_files)

    print(f"🌊 Deep-diving into shell (Diving into the Shell) - Level: {args.level}, Target files: {len(existing_files)}, Keywords: {args.keyword}")

    # Execute content reading (latest first + offset pagination)
    try:
        p_grep = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

        # Core pagination logic (keep only tail mode): tail -n {LIMIT + offset} | head -n {LIMIT}
        p_slice = subprocess.Popen(["tail", "-n", str(LIMIT + args.offset)], stdin=p_grep.stdout, stdout=subprocess.PIPE, text=True)
        p_final = subprocess.Popen(["head", "-n", str(LIMIT)], stdin=p_slice.stdout, stdout=subprocess.PIPE, text=True)

        p_grep.stdout.close()
        p_slice.stdout.close()

        output, _ = p_final.communicate()

        if not output.strip():
            print("🕳️ No matching results (or pagination out of range).")
        else:
            print(f"📖 Reading 'latest' records from line {args.offset + 1} to {args.offset + LIMIT}:\n")
            print(output)
            print(f"\n💡 [Navigation hint] To continue digging deeper history, add `--offset {args.offset + LIMIT}` to the command.")

    except Exception as e:
        print(f"❌ Retrieval failed: {e}")

if __name__ == "__main__":
    main()
